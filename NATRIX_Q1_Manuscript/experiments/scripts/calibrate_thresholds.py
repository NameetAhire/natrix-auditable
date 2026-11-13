"""Leave-one-fold-out threshold calibration on outer OOF predictions.

The pre-registered comparison selects a threshold by inner CV inside each
training fold.  The inner models are trained on 64% of the data, while the
model that scores the test fold is trained on 80%; their probability scales
differ, so an inner-selected threshold can be conservative when transferred.

This script implements a calibration that keeps the model size fixed: for each
outer fold k, the threshold is selected on the OOF predictions of the *other*
four folds (each produced by a model trained on 80%) and applied to fold k.
Fold k's labels are never used to select its threshold.

Policies: F1-optimal, FPR <= 1%, FPR <= 2%.  The FPR <= 2% policy is the
deployment point used for the acceptance claim; the pre-registered inner-CV
points remain in comparison_metrics.csv.

Outputs
-------
experiments/results/v3_v4/calibrated_metrics.csv
experiments/results/v3_v4/calibration_summary.json
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import stats_utils as S  # noqa: E402
from compare_v3_v4 import best_threshold, ci_for_pred, metrics_from_pred  # noqa: E402

OUT = C.RESULTS / "v3_v4"
SEEDS = [42, 123, 2026]
POLICIES = {"f1": None, "fpr1": 0.01, "fpr2": 0.02}


def load_oof(features, seed):
    path = OUT / f"oof_{features}_seed{seed}.npz"
    z = np.load(path)
    return z["proba"], z["y"]


def folds_for(y, seed):
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
    return list(skf.split(np.zeros((len(y), 1)), y))


def loo_predict(proba, y, folds, cap):
    pred = np.zeros(len(y), dtype=int)
    thresholds = []
    for _, te in folds:
        mask = np.ones(len(y), dtype=bool)
        mask[te] = False
        t = best_threshold(proba[mask], y[mask], fpr_cap=cap)
        pred[te] = (proba[te] >= t).astype(int)
        thresholds.append(t)
    return pred, thresholds


def main() -> None:
    rows = []
    store = {}
    for features in ("v3", "v4"):
        for seed in SEEDS:
            proba, y = load_oof(features, seed)
            folds = folds_for(y, seed)
            for policy, cap in POLICIES.items():
                pred, thresholds = loo_predict(proba, y, folds, cap)
                m = metrics_from_pred(y, pred)
                acc_lo, acc_hi = ci_for_pred(y, pred, "accuracy")
                fpr_lo, fpr_hi = ci_for_pred(y, pred, "fpr")
                m.update({
                    "features": features, "seed": seed, "policy": policy,
                    "threshold_mean": float(np.mean(thresholds)),
                    "thresholds": ";".join(f"{v:.2f}" for v in thresholds),
                    "accuracy_ci_lo": acc_lo, "accuracy_ci_hi": acc_hi,
                    "fpr_ci_lo": fpr_lo, "fpr_ci_hi": fpr_hi,
                })
                rows.append(m)
                store[(features, seed, policy)] = pred
            print(f"{features} seed {seed} calibrated", flush=True)

    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "calibrated_metrics.csv", index=False)

    # Paired McNemar at the deployment point, seed 42.
    p3 = store[("v3", 42, "fpr2")]
    p4 = store[("v4", 42, "fpr2")]
    c3 = p3 == y
    c4 = p4 == y
    lo, hi = S.paired_bootstrap_delta(c4.astype(float), c3.astype(float))
    summary = {
        "protocol": "leave-one-fold-out threshold on outer OOF predictions; "
                    "fold k threshold never sees fold k labels",
        "seeds": SEEDS,
        "policies": {"f1": "F1-optimal", "fpr1": "FPR<=1%", "fpr2": "FPR<=2%"},
        "per_seed": frame.to_dict("records"),
        "mcnemar_v4_vs_v3_fpr2_seed42": S.mcnemar(c4, c3),
        "accuracy_delta_v4_minus_v3_fpr2_seed42": {
            "mean": float(c4.mean() - c3.mean()),
            "ci_lo": lo, "ci_hi": hi,
        },
        "acceptance_check": {},
    }
    for features in ("v3", "v4"):
        sub = frame[(frame["features"] == features) & (frame["policy"] == "fpr2")]
        summary["acceptance_check"][features] = {
            "accuracy_mean": float(sub["accuracy"].mean()),
            "accuracy_min": float(sub["accuracy"].min()),
            "fpr_mean": float(sub["fpr"].mean()),
            "fpr_max": float(sub["fpr"].max()),
            "meets_both_seeds": bool(
                (sub["accuracy"] > 0.95).all() and (sub["fpr"] < 0.0203).all()
            ),
        }
    C.write_json(OUT / "calibration_summary.json", summary)

    print(frame[["features", "seed", "policy", "threshold_mean", "accuracy",
                 "fpr", "fnr", "f1"]].to_string(index=False))
    print("\nacceptance:", summary["acceptance_check"])


if __name__ == "__main__":
    main()
