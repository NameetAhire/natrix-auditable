"""Matched-FPR comparison of NATRIX, the lexical baseline, and CRS.

Three operating points are reported for every score-based detector:

* ``threshold_0.5``: the raw probability threshold;
* ``fpr2_crossfit``: leave-one-fold-out threshold selection, the deployable
  policy used elsewhere in the paper;
* ``fpr2_oracle``: the threshold that achieves the FPR target on the evaluation
  set itself.  This is an upper bound, not a deployable number, but it is the
  fair way to compare detectors whose probability scales differ.

CRS is a binary detector at its frozen operating point; it has no score, so it
appears only in the single-point comparison.

Outputs
-------
experiments/results/baselines/matched_fpr_{corpus}.json
experiments/results/baselines/matched_fpr_{corpus}.csv
experiments/results/baselines/matched_fpr_all.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import stats_utils as S  # noqa: E402
from compare_v3_v4 import best_threshold, metrics_from_pred  # noqa: E402

OUT = C.RESULTS / "baselines"
OUT.mkdir(parents=True, exist_ok=True)


def load_natrix(corpus: str):
    if corpus in ("srbh", "wcp"):
        path = OUT / f"natrix_{corpus}_sample20k_oof.npz"
        z = np.load(path, allow_pickle=True)
        folds = [np.asarray(te, dtype=int) for te in z["folds"]]
    else:
        z = np.load(C.RESULTS / "corpora" / f"{corpus}_P1_oof.npz", allow_pickle=True)
        f = np.load(C.RESULTS / "corpora" / f"{corpus}_P1_folds_seed42.npz", allow_pickle=True)
        folds = [f[f"te_{i}"] for i in range(5)]
    return z["proba"], z["y"].astype(int), folds


def load_lexical(corpus: str, view: str):
    path = OUT / f"lexical_{corpus}_{view}_oof.npz"
    z = np.load(path, allow_pickle=True)
    return z["proba"], z["y"].astype(int), [
        np.asarray(te, dtype=int) for te in z["folds"]
    ]


def crossfit(proba, y, folds, cap=0.02):
    pred = np.zeros(len(y), dtype=int)
    thresholds = []
    for te in folds:
        mask = np.ones(len(y), dtype=bool)
        mask[te] = False
        t = best_threshold(proba[mask], y[mask], fpr_cap=cap)
        pred[te] = (proba[te] >= t).astype(int)
        thresholds.append(float(t))
    return pred, thresholds


def oracle(proba, y, cap=0.02):
    t = best_threshold(proba, y, fpr_cap=cap)
    return (proba >= t).astype(int), float(t)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", choices=["csic", "ecml", "srbh", "wcp"], required=True)
    args = parser.parse_args()

    rows = []
    details = {"corpus": args.corpus}

    for name, (proba, y, folds) in {
        "natrix_v3": load_natrix(args.corpus),
        "lexical_full": load_lexical(args.corpus, "full"),
    }.items():
        pred05 = (proba >= 0.5).astype(int)
        pred_cf, th_cf = crossfit(proba, y, folds, 0.02)
        pred_or, th_or = oracle(proba, y, 0.02)
        for policy, pred, extra in (
            ("threshold_0.5", pred05, {}),
            ("fpr2_crossfit", pred_cf, {"threshold_mean": float(np.mean(th_cf)), "thresholds": th_cf}),
            ("fpr2_oracle", pred_or, {"threshold": th_or}),
        ):
            m = metrics_from_pred(y, pred)
            m.update({"detector": name, "policy": policy, **extra})
            rows.append(m)
        details[name] = {
            "roc_auc": float(roc_auc_score(y, proba)),
            "n": int(len(y)),
            "labels": {"clean": int((y == 0).sum()), "attack": int((y == 1).sum())},
        }

    # CRS is binary and only available for corpora that were replayed.
    crs_path = OUT / f"crs_pl1_{args.corpus}_requests.parquet"
    if crs_path.exists():
        crs = pd.read_parquet(crs_path)
        y_crs = crs["label"].to_numpy(dtype=int)
        blocked = crs["blocked"].to_numpy(dtype=int)
        if len(y_crs) != len(y):
            raise SystemExit(f"CRS rows {len(y_crs)} != score rows {len(y)}")
        if not np.array_equal(y_crs, y):
            raise SystemExit("CRS labels are not in the same order as the score matrices")
        m = metrics_from_pred(y, blocked)
        m.update({"detector": "crs_pl1", "policy": "frozen"})
        rows.append(m)
        details["crs_pl1"] = {"n": int(len(y))}
        # Paired comparison against NATRIX at its oracle FPR2 point.
        natrix_oracle = next(r for r in rows if r["detector"] == "natrix_v3" and r["policy"] == "fpr2_oracle")
        # Recompute the NATRIX oracle predictions for the paired test.
        proba, y_n, folds_n = load_natrix(args.corpus)
        pred_n, _ = oracle(proba, y_n, 0.02)
        details["crs_vs_natrix_oracle"] = {
            "accuracy": {
                "delta": float((blocked == y).mean() - (pred_n == y).mean()),
                "mcnemar": S.mcnemar(blocked == y, pred_n == y),
            },
            "recall": {
                "delta": float(blocked[y == 1].mean() - pred_n[y == 1].mean()),
                "mcnemar": S.mcnemar(blocked[y == 1] == 1, pred_n[y == 1] == 1),
            },
            "fpr": {
                "delta": float(blocked[y == 0].mean() - pred_n[y == 0].mean()),
                "mcnemar": S.mcnemar(blocked[y == 0] == 1, pred_n[y == 0] == 1),
            },
        }
    else:
        details["crs_pl1"] = {"status": "missing", "path": str(crs_path)}

    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / f"matched_fpr_{args.corpus}.csv", index=False)
    C.write_json(OUT / f"matched_fpr_{args.corpus}.json", {"details": details, "metrics": rows})
    print(frame[["detector", "policy", "accuracy", "fpr", "recall", "f1",
                 "tp", "tn", "fp", "fn"]].to_string(index=False))
    print(details)


if __name__ == "__main__":
    main()
