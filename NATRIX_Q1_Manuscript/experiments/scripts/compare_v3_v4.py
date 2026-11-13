"""Headline v3 vs v4 comparison with nested threshold selection.

Protocol (analysis_plan.md §5):
  * outer 5-fold x 3 seeds;
  * inside each outer training fold, 5-fold inner CV selects the decision
    threshold that maximises F1 (and, separately, the largest threshold whose
    FPR is <= 1%);
  * the test fold is scored once with *that fold's* selected threshold, so the
    selected operating point never sees the test fold.

The learner is the shipped Random Forest (200 trees, random_state=42).

Outputs
-------
experiments/results/v3_v4/comparison_metrics.csv
experiments/results/v3_v4/comparison_summary.json
experiments/results/v3_v4/oof_<set>_seed<seed>.npz
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import candidate_features as CF  # noqa: E402
import stats_utils as S  # noqa: E402

OUT = C.RESULTS / "v3_v4"
OUT.mkdir(parents=True, exist_ok=True)

SEEDS = [42, 123, 2026]
OUTER = 5
INNER = 5
THRESHOLDS = np.round(np.arange(0.01, 1.00, 0.01), 2)


def best_threshold(proba, y, fpr_cap: float | None = None) -> float:
    # If no threshold satisfies the cap, fall back to a conservative high
    # threshold rather than silently returning a cap-violating point.
    best_t = 0.99 if fpr_cap is not None else 0.5
    best_f1 = -1.0
    for t in THRESHOLDS:
        pred = (proba >= t).astype(int)
        tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
        fpr = fp / (fp + tn) if (fp + tn) else 0.0
        if fpr_cap is not None and fpr > fpr_cap:
            continue
        score = f1_score(y, pred, zero_division=0)
        if score > best_f1:
            best_f1, best_t = score, float(t)
    return best_t


def metrics_from_pred(y, pred) -> dict:
    pred = np.asarray(pred, dtype=int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    acc = (tp + tn) / (tp + tn + fp + fn)
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    fnr = fn / (fn + tp) if (fn + tp) else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "accuracy": float(acc), "fpr": float(fpr), "fnr": float(fnr),
        "precision": float(precision), "recall": float(recall), "f1": float(f1),
        "tp": int(tp), "tn": int(tn), "fp": int(fp), "fn": int(fn),
    }


def ci_for_pred(y, pred, metric: str) -> tuple[float, float]:
    pred = np.asarray(pred, dtype=int)
    if metric == "accuracy":
        values = (pred == y).astype(float)
    elif metric == "fpr":
        mask = y == 0
        values = pred[mask].astype(float)
    elif metric == "fnr":
        mask = y == 1
        values = (pred[mask] == 0).astype(float)
    else:
        raise ValueError(metric)
    return S.bootstrap_ci(values)


def run_set(name, X, y, seed):
    outer = StratifiedKFold(n_splits=OUTER, shuffle=True, random_state=seed)
    proba = np.zeros(len(y), dtype=float)
    pred_f1 = np.zeros(len(y), dtype=int)
    pred_fpr = np.zeros(len(y), dtype=int)
    pred_fpr2 = np.zeros(len(y), dtype=int)
    thresholds_f1, thresholds_fpr, thresholds_fpr2 = [], [], []

    for fold, (tr, te) in enumerate(outer.split(X, y)):
        inner = StratifiedKFold(n_splits=INNER, shuffle=True, random_state=seed + fold)
        oof_inner = np.zeros(len(tr), dtype=float)
        for itr, iva in inner.split(X[tr], y[tr]):
            model = C.make_rf()
            model.fit(X[tr][itr], y[tr][itr])
            oof_inner[iva] = model.predict_proba(X[tr][iva])[:, 1]
        t_f1 = best_threshold(oof_inner, y[tr])
        t_fpr = best_threshold(oof_inner, y[tr], fpr_cap=0.01)
        t_fpr2 = best_threshold(oof_inner, y[tr], fpr_cap=0.02)
        thresholds_f1.append(t_f1)
        thresholds_fpr.append(t_fpr)
        thresholds_fpr2.append(t_fpr2)

        model = C.make_rf()
        model.fit(X[tr], y[tr])
        proba[te] = model.predict_proba(X[te])[:, 1]
        pred_f1[te] = (proba[te] >= t_f1).astype(int)
        pred_fpr[te] = (proba[te] >= t_fpr).astype(int)
        pred_fpr2[te] = (proba[te] >= t_fpr2).astype(int)
        print(f"  {name} seed {seed} fold {fold}: thr_f1={t_f1:.2f} "
              f"thr_fpr1={t_fpr:.2f} thr_fpr2={t_fpr2:.2f}", flush=True)

    return (proba, pred_f1, pred_fpr, pred_fpr2,
            thresholds_f1, thresholds_fpr, thresholds_fpr2)


def main() -> None:
    started = time.time()
    records, _ = C.csic_unique()
    X3 = C.extract_matrix(records, dtype=np.float32)[0]
    Cmat = np.asarray([CF.extract(rec) for rec in records], dtype=np.float32)
    y = C.label_array(records)
    names = list(C.FEATURES)

    definition = C.read_json(C.ARTIFACTS / "feature_selection" / "v4_definition.json")
    core = definition["retained_core"]
    accepted = definition["accepted_candidates"]
    cols_v4 = [names.index(f) for f in core] + [
        X3.shape[1] + CF.CANDIDATE_NAMES.index(f) for f in accepted
    ]
    X4 = np.hstack([X3, Cmat])[:, cols_v4]

    sets = {"v3": X3, "v4": X4}
    rows = []
    store = {}

    for name, matrix in sets.items():
        for seed in SEEDS:
            (proba, pred_f1, pred_fpr, pred_fpr2,
             t_f1, t_fpr, t_fpr2) = run_set(name, matrix, y, seed)
            store[(name, seed)] = (proba, pred_f1, pred_fpr, pred_fpr2)
            np.savez(OUT / f"oof_{name}_seed{seed}.npz", proba=proba, y=y,
                     pred_f1=pred_f1, pred_fpr=pred_fpr, pred_fpr2=pred_fpr2,
                     thresholds_f1=np.asarray(t_f1),
                     thresholds_fpr1=np.asarray(t_fpr),
                     thresholds_fpr2=np.asarray(t_fpr2))

            for policy, pred, thresholds in [
                ("f1", pred_f1, t_f1),
                ("fpr1", pred_fpr, t_fpr),
                ("fpr2", pred_fpr2, t_fpr2),
            ]:
                m = metrics_from_pred(y, pred)
                m.update({"features": name, "seed": seed, "policy": policy,
                          "threshold_mean": float(np.mean(thresholds)),
                          "thresholds": ";".join(f"{v:.2f}" for v in thresholds),
                          "accuracy_ci_lo": ci_for_pred(y, pred, "accuracy")[0],
                          "accuracy_ci_hi": ci_for_pred(y, pred, "accuracy")[1],
                          "fpr_ci_lo": ci_for_pred(y, pred, "fpr")[0],
                          "fpr_ci_hi": ci_for_pred(y, pred, "fpr")[1]})
                rows.append(m)
            print(f"{name} seed {seed} done ({time.time() - started:.0f}s)", flush=True)

    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "comparison_metrics.csv", index=False)

    # Paired comparison at seed 42 (headline) using each set's own fold-wise
    # F1-optimal decisions, and separately at the deployment FPR<=2% point.
    p3, pred3, _, pred3_fpr2 = store[("v3", 42)]
    p4, pred4, _, pred4_fpr2 = store[("v4", 42)]
    correct3 = pred3 == y
    correct4 = pred4 == y
    mcnemar = S.mcnemar(correct4, correct3)
    delta = float(correct4.mean() - correct3.mean())
    lo, hi = S.paired_bootstrap_delta(correct4.astype(float), correct3.astype(float))

    correct3_fpr2 = pred3_fpr2 == y
    correct4_fpr2 = pred4_fpr2 == y
    mcnemar_fpr2 = S.mcnemar(correct4_fpr2, correct3_fpr2)
    delta_fpr2 = float(correct4_fpr2.mean() - correct3_fpr2.mean())
    lo_fpr2, hi_fpr2 = S.paired_bootstrap_delta(
        correct4_fpr2.astype(float), correct3_fpr2.astype(float)
    )

    summary = {
        "seeds": SEEDS,
        "n_records": int(len(y)),
        "v3_features": len(names),
        "v4_features": int(X4.shape[1]),
        "v4_definition": definition,
        "decision_rule": "fold-specific threshold selected by inner CV; test fold scored once",
        "mcnemar_v4_vs_v3": mcnemar,
        "accuracy_delta_v4_minus_v3": {"mean": delta, "ci_lo": lo, "ci_hi": hi},
        "mcnemar_v4_vs_v3_fpr2": mcnemar_fpr2,
        "accuracy_delta_v4_minus_v3_fpr2": {
            "mean": delta_fpr2, "ci_lo": lo_fpr2, "ci_hi": hi_fpr2
        },
        "non_inferiority_margin": 0.005,
        "non_inferior_accuracy": bool(lo >= -0.005),
        "non_inferior_accuracy_fpr2": bool(lo_fpr2 >= -0.005),
        "per_seed": frame.groupby(["features", "policy"])[
            ["accuracy", "fpr", "fnr", "f1"]
        ].mean().reset_index().to_dict("records"),
    }
    C.write_json(OUT / "comparison_summary.json", summary)
    print(frame[["features", "seed", "policy", "threshold_mean", "accuracy",
                 "fpr", "fnr", "f1"]].to_string(index=False))
    print("\nMcNemar v4 vs v3:", mcnemar)
    print("accuracy delta:", summary["accuracy_delta_v4_minus_v3"])


if __name__ == "__main__":
    main()
