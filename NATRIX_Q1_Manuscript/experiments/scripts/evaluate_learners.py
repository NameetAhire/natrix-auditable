"""Secondary-learner check for the v3/v4 feature sets (analysis plan §5).

The headline comparison uses the shipped Random Forest.  This script repeats the
same outer folds and nested threshold selection with two unrelated learners:

  * histogram gradient boosting (non-linear, different inductive bias);
  * L2-regularised logistic regression on standardised features (linear).

The point is not to beat the forest but to show that the v4 feature decision is
not an artefact of one model class.  Protocol: outer 5-fold x 3 seeds, inner
5-fold threshold selection, thresholds chosen on training folds only.

Outputs
-------
experiments/results/learners/learner_metrics.csv
experiments/results/learners/learner_summary.json
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import candidate_features as CF  # noqa: E402
import stats_utils as S  # noqa: E402

OUT = C.RESULTS / "learners"
OUT.mkdir(parents=True, exist_ok=True)

SEEDS = [42, 123, 2026]
OUTER = 5
INNER = 5
THRESHOLDS = np.round(np.arange(0.01, 1.00, 0.01), 2)


def make_learner(name: str):
    if name == "rf":
        return C.make_rf()
    if name == "hgb":
        return HistGradientBoostingClassifier(
            max_iter=300, learning_rate=0.08, max_leaf_nodes=31,
            l2_regularization=1.0, random_state=C.SEED,
        )
    if name == "logreg":
        return Pipeline([
            ("scale", StandardScaler()),
            ("clf", LogisticRegression(
                C=1.0, max_iter=3000, solver="lbfgs", random_state=C.SEED,
            )),
        ])
    raise ValueError(name)


def best_threshold(proba, y, fpr_cap=None):
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
            best_f1, best_t = float(score), float(t)
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


def run_set(features, X, y, learner_name, seed):
    outer = StratifiedKFold(n_splits=OUTER, shuffle=True, random_state=seed)
    proba = np.zeros(len(y), dtype=float)
    preds = {k: np.zeros(len(y), dtype=int) for k in ("f1", "fpr2")}
    thresholds = {k: [] for k in ("f1", "fpr2")}

    for fold, (tr, te) in enumerate(outer.split(X, y)):
        inner = StratifiedKFold(n_splits=INNER, shuffle=True, random_state=seed + fold)
        oof_inner = np.zeros(len(tr), dtype=float)
        for itr, iva in inner.split(X[tr], y[tr]):
            model = make_learner(learner_name)
            model.fit(X[tr][itr], y[tr][itr])
            oof_inner[iva] = model.predict_proba(X[tr][iva])[:, 1]

        t_f1 = best_threshold(oof_inner, y[tr])
        t_fpr2 = best_threshold(oof_inner, y[tr], fpr_cap=0.02)
        thresholds["f1"].append(t_f1)
        thresholds["fpr2"].append(t_fpr2)

        model = make_learner(learner_name)
        model.fit(X[tr], y[tr])
        proba[te] = model.predict_proba(X[te])[:, 1]
        preds["f1"][te] = (proba[te] >= t_f1).astype(int)
        preds["fpr2"][te] = (proba[te] >= t_fpr2).astype(int)
        print(f"  {features}/{learner_name} seed {seed} fold {fold}: "
              f"thr_f1={t_f1:.2f} thr_fpr2={t_fpr2:.2f}", flush=True)

    return proba, preds, thresholds


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
    for learner_name in ("hgb", "logreg"):
        for features, matrix in sets.items():
            for seed in SEEDS:
                proba, preds, thresholds = run_set(
                    features, matrix, y, learner_name, seed
                )
                store[(learner_name, features, seed)] = (proba, preds)
                np.savez(
                    OUT / f"oof_{learner_name}_{features}_seed{seed}.npz",
                    proba=proba, y=y,
                    pred_f1=preds["f1"], pred_fpr2=preds["fpr2"],
                    thresholds_f1=np.asarray(thresholds["f1"]),
                    thresholds_fpr2=np.asarray(thresholds["fpr2"]),
                )
                for policy in ("f1", "fpr2"):
                    m = metrics_from_pred(y, preds[policy])
                    m.update({
                        "learner": learner_name, "features": features, "seed": seed,
                        "policy": policy,
                        "threshold_mean": float(np.mean(thresholds[policy])),
                        "thresholds": ";".join(f"{v:.2f}" for v in thresholds[policy]),
                    })
                    rows.append(m)
                print(f"{learner_name}/{features} seed {seed} done "
                      f"({time.time() - started:.0f}s)", flush=True)

    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "learner_metrics.csv", index=False)

    summary_rows = []
    for (learner_name, features, seed), (_, preds) in store.items():
        for policy in ("f1", "fpr2"):
            correct = preds[policy] == y
            summary_rows.append({
                "learner": learner_name, "features": features, "seed": seed,
                "policy": policy, "accuracy": float(correct.mean()),
            })
    summary = pd.DataFrame(summary_rows)
    pivot = summary.groupby(["learner", "features", "policy"])[
        ["accuracy"]].agg(["mean", "std"]).reset_index()
    pivot.columns = ["learner", "features", "policy", "accuracy_mean", "accuracy_std"]

    # Paired v4-vs-v3 test inside each learner at seed 42, F1 policy.
    tests = []
    for learner_name in ("hgb", "logreg"):
        _, p3 = store[(learner_name, "v3", 42)]
        _, p4 = store[(learner_name, "v4", 42)]
        c3 = p3["f1"] == y
        c4 = p4["f1"] == y
        lo, hi = S.paired_bootstrap_delta(c4.astype(float), c3.astype(float))
        tests.append({
            "learner": learner_name, "policy": "f1",
            "delta_accuracy": float(c4.mean() - c3.mean()),
            "ci_lo": lo, "ci_hi": hi,
            "mcnemar": S.mcnemar(c4, c3),
        })

    C.write_json(OUT / "learner_summary.json", {
        "seeds": SEEDS,
        "protocol": "outer 5-fold x 3 seeds; inner 5-fold threshold; test scored once",
        "learners": {
            "hgb": "HistGradientBoostingClassifier(max_iter=300, lr=0.08, leaves=31, l2=1.0)",
            "logreg": "StandardScaler + LogisticRegression(C=1.0, lbfgs, max_iter=3000)",
        },
        "v4_definition": definition,
        "per_learner": pivot.to_dict("records"),
        "paired_v4_vs_v3_seed42_f1": tests,
    })
    print(pivot.to_string(index=False))
    print(pd.DataFrame(tests).to_string(index=False))


if __name__ == "__main__":
    main()
