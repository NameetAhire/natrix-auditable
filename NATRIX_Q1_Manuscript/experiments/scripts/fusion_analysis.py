"""Gate + CRS fusion: does the signature/TI channel add anything?

The gate is the NATRIX v3 random forest scored out-of-fold under the P1
protocol.  The signature channel is the frozen ModSecurity CRS replay.  Both
see the same deduplicated request, so the comparison is paired.

Policies
--------
gate : NATRIX at the leave-one-fold-out FPR<=2% threshold
crs  : CRS 403
or   : block if either blocks (recall-oriented)
and  : block only if both block (precision-oriented)

Outputs
-------
experiments/results/baselines/fusion_{corpus}.json
experiments/results/baselines/fusion_{corpus}.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import stats_utils as S  # noqa: E402
from compare_v3_v4 import best_threshold, metrics_from_pred  # noqa: E402

OUT = C.RESULTS / "baselines"
OUT.mkdir(parents=True, exist_ok=True)


def gate_data(corpus: str):
    if corpus in ("srbh", "wcp"):
        # CRS and the lexical baseline are replayed on the shared 20k sample,
        # so the gate must be scored on exactly those rows.
        oof = np.load(OUT / f"natrix_{corpus}_sample20k_oof.npz", allow_pickle=True)
        folds = [np.asarray(te, dtype=int) for te in oof["folds"]]
        return oof["proba"], oof["y"].astype(int), folds
    oof = np.load(C.RESULTS / "corpora" / f"{corpus}_P1_oof.npz", allow_pickle=True)
    folds_npz = np.load(
        C.RESULTS / "corpora" / f"{corpus}_P1_folds_seed42.npz", allow_pickle=True
    )
    folds = [folds_npz[f"te_{i}"] for i in range(5)]
    return oof["proba"], oof["y"].astype(int), folds


def loo_predict(proba: np.ndarray, y: np.ndarray, folds, cap: float = 0.02):
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

    proba, y, folds = gate_data(args.corpus)
    gate_pred, thresholds = loo_predict(proba, y, folds, 0.02)

    crs_path = OUT / f"crs_pl1_{args.corpus}_requests.parquet"
    if not crs_path.exists():
        raise SystemExit(f"missing {crs_path}; run crs_baseline.py first")
    crs = pd.read_parquet(crs_path)
    if len(crs) != len(y):
        raise SystemExit(f"row count mismatch: CRS {len(crs)} vs gate {len(y)}")
    if "label" in crs.columns and not np.array_equal(crs["label"].to_numpy(dtype=int), y):
        raise SystemExit("label order mismatch between CRS replay and gate OOF")
    crs_pred = crs["blocked"].to_numpy(dtype=int)

    policies = {
        "gate": gate_pred,
        "crs": crs_pred,
        "or": ((gate_pred == 1) | (crs_pred == 1)).astype(int),
        "and": ((gate_pred == 1) & (crs_pred == 1)).astype(int),
    }

    rows = []
    for name, pred in policies.items():
        m = metrics_from_pred(y, pred)
        m.update({"policy": name, "corpus": args.corpus, "n": int(len(y))})
        rows.append(m)
    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / f"fusion_{args.corpus}.csv", index=False)

    def paired(a: np.ndarray, b: np.ndarray, mask: np.ndarray | None = None):
        if mask is not None:
            a = a[mask]
            b = b[mask]
        ca = (a == 1)
        cb = (b == 1)
        lo, hi = S.paired_bootstrap_delta(ca.astype(float), cb.astype(float))
        return {
            "delta": float(ca.mean() - cb.mean()),
            "ci_lo": lo,
            "ci_hi": hi,
            "mcnemar": S.mcnemar(ca, cb),
        }

    attack = y == 1
    clean = y == 0
    gate_correct = gate_pred == y
    or_correct = policies["or"] == y
    and_correct = policies["and"] == y

    result = {
        "corpus": args.corpus,
        "n": int(len(y)),
        "gate_thresholds": thresholds,
        "gate_threshold_mean": float(np.mean(thresholds)),
        "metrics": frame.to_dict("records"),
        "or_vs_gate": {
            "accuracy": paired(or_correct, gate_correct),
            "recall": paired(policies["or"], gate_pred, attack),
            "fpr": paired(policies["or"], gate_pred, clean),
            "attacks_gate_missed_crs_caught": int(
                ((gate_pred == 0) & (crs_pred == 1) & attack).sum()
            ),
            "clean_gate_allowed_crs_blocked": int(
                ((gate_pred == 0) & (crs_pred == 1) & clean).sum()
            ),
        },
        "and_vs_gate": {
            "accuracy": paired(and_correct, gate_correct),
            "recall": paired(policies["and"], gate_pred, attack),
            "fpr": paired(policies["and"], gate_pred, clean),
        },
    }
    C.write_json(OUT / f"fusion_{args.corpus}.json", result)
    print(frame[["policy", "accuracy", "fpr", "recall", "f1", "tp", "tn", "fp", "fn"]].to_string(index=False))
    print("OR vs gate:", result["or_vs_gate"])
    print("AND vs gate:", result["and_vs_gate"])


if __name__ == "__main__":
    main()
