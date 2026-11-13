"""Apply the three admission gates to the v3-D path-feature block.

The nine v3-D features form two operational blocks: five per-parameter
maxima and four path ratios.  Gate C rejects the value block on the real
corpus (0.35 ms p95 against 0.15 ms) and accepts the path block (0.08 ms).
This script applies Gate B to the four path features and records the first
positive admission outcome of the mechanism.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import mannwhitneyu
from sklearn.inspection import permutation_importance
from sklearn.model_selection import StratifiedKFold

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import dilution_resistant as D  # noqa: E402
from compare_v3_v4 import best_threshold, metrics_from_pred  # noqa: E402
import stats_utils as S  # noqa: E402

OUT = C.RESULTS / "feature_audit"
OUT.mkdir(parents=True, exist_ok=True)
SEED = 42
N_SPLITS = 5
ACC_MARGIN = 0.002
FPR_MARGIN = 0.0010
PATH_NAMES = D.EXTRA_NAMES[5:]
PATH_IDX = list(range(22, 31))[5:]  # columns 27..30 in the 31-D matrix


def t_interval(values):
    arr = np.asarray(values, dtype=float)
    n = len(arr)
    mean = float(arr.mean())
    if n < 2:
        return mean, float("-inf"), float("inf")
    se = float(arr.std(ddof=1) / np.sqrt(n))
    half = float(stats.t.ppf(0.975, n - 1) * se)
    return mean, mean - half, mean + half


def fit_predict(X, y, folds):
    oof = np.zeros(len(y), dtype=np.float32)
    for tr, te in folds:
        model = C.make_rf(random_state=SEED)
        model.fit(X[tr], y[tr])
        oof[te] = model.predict_proba(X[te])[:, 1]
    pred = np.zeros(len(y), dtype=int)
    thresholds = []
    for tr, te in folds:
        t = best_threshold(oof[tr], y[tr], fpr_cap=0.02)
        pred[te] = (oof[te] >= t).astype(int)
        thresholds.append(float(t))
    return oof, pred, thresholds


def paired_bootstrap(y, pred_a, pred_b, n_boot=1000, seed=SEED):
    rng = np.random.default_rng(seed)
    correct_a = (pred_a == y).astype(float)
    correct_b = (pred_b == y).astype(float)
    deltas = np.empty(n_boot)
    n = len(y)
    for i in range(n_boot):
        idx = rng.integers(0, n, n)
        deltas[i] = correct_a[idx].mean() - correct_b[idx].mean()
    return float(np.percentile(deltas, 2.5)), float(np.percentile(deltas, 97.5))


def main() -> None:
    records, _ = C.csic_unique()
    base, _ = C.extract_matrix(records, dtype=np.float32)
    extra = np.asarray([D.extra_vector(r) for r in records], dtype=np.float32)
    y = C.label_array(records)
    X_path = np.hstack([base, extra[:, 5:9]])

    folds = list(
        StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=SEED).split(X_path, y)
    )
    oof, pred, thresholds = fit_predict(X_path, y, folds)
    full = metrics_from_pred(y, pred)
    print("full 26-D:", full, flush=True)

    # Permutation importance on the held-out fold.
    perm = {name: [] for name in PATH_NAMES}
    for k, (tr, te) in enumerate(folds):
        model = C.make_rf(random_state=SEED).fit(X_path[tr], y[tr])
        result = permutation_importance(
            model, X_path[te], y[te], n_repeats=10, random_state=SEED, n_jobs=1
        )
        for j, name in enumerate(PATH_NAMES):
            perm[name].append(float(result.importances_mean[22 + j]))
        print(f"  fold {k} permutation done", flush=True)

    perm_stats = {name: t_interval(vals) for name, vals in perm.items()}
    q25 = float(np.quantile([v[0] for v in perm_stats.values()], 0.25))

    # Univariate screen.
    uni = {}
    pvals = []
    for j, name in enumerate(PATH_NAMES):
        col = X_path[:, 22 + j]
        clean, attack = col[y == 0], col[y == 1]
        if len(np.unique(col)) <= 2:
            p = float(mannwhitneyu(clean, attack, alternative="two-sided").pvalue)
        else:
            p = float(mannwhitneyu(clean, attack, alternative="two-sided").pvalue)
        pvals.append(p)
        uni[name] = {
            "p_value": p,
            "cliffs_delta": float(S.cliffs_delta(attack, clean)),
            "clean_zero_frac": float(np.mean(clean == 0)),
            "attack_zero_frac": float(np.mean(attack == 0)),
        }
    p_bh = S.bh_correction(pvals)
    for name, q in zip(PATH_NAMES, p_bh):
        uni[name]["p_bh"] = float(q)

    # Leave-one-feature-out ablation.
    rows = []
    for j, name in enumerate(PATH_NAMES):
        keep = [c for c in range(X_path.shape[1]) if c != 22 + j]
        _, pred_drop, _ = fit_predict(X_path[:, keep], y, folds)
        drop = metrics_from_pred(y, pred_drop)
        d_acc = float(drop["accuracy"] - full["accuracy"])
        d_fpr = float(drop["fpr"] - full["fpr"])
        d_fnr = float(drop["fnr"] - full["fnr"])
        lo, hi = paired_bootstrap(y, pred, pred_drop)
        u = uni[name]
        near_constant = u["clean_zero_frac"] >= 0.99 and u["attack_zero_frac"] >= 0.99
        c1 = bool((u["p_bh"] >= 0.05 and abs(u["cliffs_delta"]) < 0.10) or near_constant)
        perm_mean, perm_lo, perm_hi = perm_stats[name]
        c2 = bool(perm_mean <= q25 and perm_lo <= 0.0 <= perm_hi)
        c3 = bool(d_acc >= -ACC_MARGIN and lo >= -ACC_MARGIN and d_fpr <= FPR_MARGIN)
        c4 = True  # no path ratio is on the safety list
        drop_decision = bool(c1 and c2 and c3 and c4)
        rows.append({
            "feature": name,
            "p_bh": u["p_bh"],
            "cliffs_delta": u["cliffs_delta"],
            "clean_zero_frac": u["clean_zero_frac"],
            "attack_zero_frac": u["attack_zero_frac"],
            "perm_importance_mean": perm_mean,
            "perm_ci_lo": perm_lo,
            "perm_ci_hi": perm_hi,
            "bottom_quartile": bool(perm_mean <= q25),
            "ablation_delta_accuracy": d_acc,
            "ablation_delta_accuracy_ci_lo": lo,
            "ablation_delta_accuracy_ci_hi": hi,
            "ablation_delta_fpr": d_fpr,
            "ablation_delta_fnr": d_fnr,
            "c1_univariate": c1,
            "c2_importance": c2,
            "c3_ablation": c3,
            "c4_not_safety": c4,
            "decision": "dropped" if drop_decision else "admitted",
            "reason": "all four conditions met" if drop_decision else "retained: " + ",".join(
                n for n, ok in [("c1", c1), ("c2", c2), ("c3", c3), ("c4", c4)] if not ok
            ),
        })
        print(f"  {name}: d_acc={d_acc:+.4f} ci=[{lo:+.4f},{hi:+.4f}] "
              f"p_bh={u['p_bh']:.2g} delta={u['cliffs_delta']:.3f} "
              f"perm={perm_mean:.4f} -> {rows[-1]['decision']}", flush=True)

    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "v3d_path_gate.csv", index=False)

    cost = C.read_json(C.RESULTS / "latency" / "v3d_cost.json")
    gate_c = cost["real_traffic"]["sets"]["path_4"]
    admitted = frame.loc[frame.decision == "admitted", "feature"].tolist()
    summary = {
        "candidate_set": "v3-D path block (four features)",
        "corpus": "CSIC 2010 unique",
        "n": int(len(y)),
        "full_26d": full,
        "thresholds": thresholds,
        "gate_c": gate_c,
        "gate_c_pass": bool(gate_c["p95_ms"] <= 0.15),
        "admitted": admitted,
        "dropped": frame.loc[frame.decision == "dropped", "feature"].tolist(),
        "n_admitted": len(admitted),
        "n_dropped": int((frame.decision == "dropped").sum()),
        "note": (
            "The four path features are a post-freeze positive-control block, "
            "not part of the pre-registered v3 contract. They are reported to "
            "show that the gate can admit, not to change v4."
        ),
    }
    C.write_json(OUT / "v3d_path_gate.json", summary)
    print("\nadmitted:", admitted)
    print("dropped:", summary["dropped"])


if __name__ == "__main__":
    main()
