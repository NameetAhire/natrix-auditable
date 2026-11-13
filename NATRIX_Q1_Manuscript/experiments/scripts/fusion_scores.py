"""Score-level fusion of the NATRIX gate and the lexical baseline.

CRS is a binary signature channel and adds almost nothing on CSIC because its
true positives are nearly a subset of the gate's.  This script asks a different
question: if the second agent is a complementary *learned* payload detector,
does fusion buy recall at the same FPR?

Protocol
--------
* Base scores are the out-of-fold probabilities already produced by NATRIX and
  the lexical baseline on identical rows and identical folds.
* For each fold, a two-feature logistic stacker is trained on the other four
  folds' scores and labels, then applied to the held-out fold.  The test fold's
  labels are never used to fit the stacker.
* The stacker's threshold is selected leave-one-fold-out at FPR <= 2%, the same
  deployable policy used for the individual detectors.
* OR and AND of the two base decisions at their own cross-fitted thresholds are
  reported as reference points.

This is an offline fusion analysis.  The lexical agent is not in the shipped
proxy, so the result is headroom, not a deployment claim.

Outputs
-------
experiments/results/baselines/fusion_scores_{corpus}.json
experiments/results/baselines/fusion_scores_{corpus}.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import stats_utils as S  # noqa: E402
from compare_v3_v4 import best_threshold, metrics_from_pred  # noqa: E402

OUT = C.RESULTS / "baselines"
OUT.mkdir(parents=True, exist_ok=True)


def load_pair(corpus: str):
    if corpus in ("srbh", "wcp"):
        nz = np.load(OUT / f"natrix_{corpus}_sample20k_oof.npz", allow_pickle=True)
        lz = np.load(OUT / f"lexical_{corpus}_full_oof.npz", allow_pickle=True)
        folds = [np.asarray(te, dtype=int) for te in nz["folds"]]
    else:
        nz = np.load(C.RESULTS / "corpora" / f"{corpus}_P1_oof.npz", allow_pickle=True)
        f = np.load(C.RESULTS / "corpora" / f"{corpus}_P1_folds_seed42.npz", allow_pickle=True)
        folds = [f[f"te_{i}"] for i in range(5)]
        lz = np.load(OUT / f"lexical_{corpus}_full_oof.npz", allow_pickle=True)
    if not np.array_equal(nz["y"].astype(int), lz["y"].astype(int)):
        raise SystemExit("base score labels are not aligned")
    return nz["proba"], lz["proba"], nz["y"].astype(int), folds


def logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p.astype(np.float64), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def crossfit_threshold(proba: np.ndarray, y: np.ndarray, folds, cap=0.02):
    pred = np.zeros(len(y), dtype=int)
    thresholds = []
    for te in folds:
        mask = np.ones(len(y), dtype=bool)
        mask[te] = False
        t = best_threshold(proba[mask], y[mask], fpr_cap=cap)
        pred[te] = (proba[te] >= t).astype(int)
        thresholds.append(float(t))
    return pred, thresholds


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", choices=["csic", "ecml", "srbh", "wcp"], required=True)
    args = parser.parse_args()

    natrix, lexical, y, folds = load_pair(args.corpus)
    stack = np.zeros(len(y), dtype=np.float64)
    all_idx = np.arange(len(y))
    for te in folds:
        tr = np.setdiff1d(all_idx, te)
        features = np.column_stack([logit(natrix), logit(lexical)])
        model = LogisticRegression(C=1.0, max_iter=1000)
        model.fit(features[tr], y[tr])
        stack[te] = model.predict_proba(features[te])[:, 1]

    pred_n, th_n = crossfit_threshold(natrix, y, folds, 0.02)
    pred_l, th_l = crossfit_threshold(lexical, y, folds, 0.02)
    pred_s, th_s = crossfit_threshold(stack, y, folds, 0.02)
    policies = {
        "natrix": pred_n,
        "lexical": pred_l,
        "stack": pred_s,
        "or": ((pred_n == 1) | (pred_l == 1)).astype(int),
        "and": ((pred_n == 1) & (pred_l == 1)).astype(int),
    }

    rows = []
    for name, pred in policies.items():
        m = metrics_from_pred(y, pred)
        m.update({"detector": name, "corpus": args.corpus, "n": int(len(y))})
        rows.append(m)
    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / f"fusion_scores_{args.corpus}.csv", index=False)

    attack = y == 1
    clean = y == 0

    def paired(a, b, mask):
        lo, hi = S.paired_bootstrap_delta((a[mask] == 1).astype(float),
                                          (b[mask] == 1).astype(float))
        return {
            "delta": float((a[mask] == 1).mean() - (b[mask] == 1).mean()),
            "ci_lo": lo, "ci_hi": hi,
            "mcnemar": S.mcnemar(a[mask] == 1, b[mask] == 1),
        }

    result = {
        "corpus": args.corpus, "n": int(len(y)),
        "thresholds": {"natrix": th_n, "lexical": th_l, "stack": th_s},
        "metrics": frame.to_dict("records"),
        "stack_vs_lexical": {
            "accuracy": paired(pred_s == y, pred_l == y, np.ones(len(y), dtype=bool)),
            "recall": paired(pred_s, pred_l, attack),
            "fpr": paired(pred_s, pred_l, clean),
        },
        "stack_vs_natrix": {
            "accuracy": paired(pred_s == y, pred_n == y, np.ones(len(y), dtype=bool)),
            "recall": paired(pred_s, pred_n, attack),
            "fpr": paired(pred_s, pred_n, clean),
        },
        "or_vs_lexical": {
            "accuracy": paired(policies["or"] == y, pred_l == y, np.ones(len(y), dtype=bool)),
            "recall": paired(policies["or"], pred_l, attack),
            "fpr": paired(policies["or"], pred_l, clean),
        },
        "stacker_coefficients": None,
    }
    # Report the last fold's coefficients as a descriptive summary.
    result["stacker_coefficients"] = {
        "natrix": float(model.coef_[0][0]),
        "lexical": float(model.coef_[0][1]),
        "intercept": float(model.intercept_[0]),
    }
    C.write_json(OUT / f"fusion_scores_{args.corpus}.json", result)
    print(frame[["detector", "accuracy", "fpr", "recall", "f1", "tp", "tn", "fp", "fn"]].to_string(index=False))
    print("stack vs lexical:", result["stack_vs_lexical"])
    print("stack vs natrix:", result["stack_vs_natrix"])
    print("or vs lexical:", result["or_vs_lexical"])


if __name__ == "__main__":
    main()
