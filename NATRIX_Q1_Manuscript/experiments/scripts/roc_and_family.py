"""ROC operating points and per-family recall for the paper's comparison table.

The ROC points are oracle thresholds on the evaluation set: they answer "what
recall does this detector reach if it is allowed an FPR of x%?"  They are an
upper bound, not a deployable policy, and are labelled as such.  The deployable
cross-fitted points remain in ``matched_fpr_*.json``.

Per-family recall uses the same oracle 2% FPR threshold for both detectors, so
the comparison is matched.  Families come from the corpus labels, never from a
classifier.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
from compare_v3_v4 import best_threshold, metrics_from_pred  # noqa: E402

OUT = C.RESULTS / "baselines"
OUT.mkdir(parents=True, exist_ok=True)
TARGETS = (0.005, 0.01, 0.02, 0.05, 0.10)


def load_scores(corpus: str):
    out = {}
    if corpus in ("srbh", "wcp"):
        z = np.load(OUT / f"natrix_{corpus}_sample20k_oof.npz", allow_pickle=True)
        out["natrix_v3"] = (z["proba"], z["y"].astype(int))
        for view in ("full", "payload"):
            p = OUT / f"lexical_{corpus}_{view}_oof.npz"
            if p.exists():
                lz = np.load(p, allow_pickle=True)
                out[f"lexical_{view}"] = (lz["proba"], lz["y"].astype(int))
    else:
        z = np.load(C.RESULTS / "corpora" / f"{corpus}_P1_oof.npz", allow_pickle=True)
        out["natrix_v3"] = (z["proba"], z["y"].astype(int))
        for view in ("full", "payload"):
            p = OUT / f"lexical_{corpus}_{view}_oof.npz"
            if p.exists():
                lz = np.load(p, allow_pickle=True)
                out[f"lexical_{view}"] = (lz["proba"], lz["y"].astype(int))
    return out


def family_labels(corpus: str, n: int):
    if corpus in ("srbh", "wcp"):
        frame = pd.read_parquet(OUT / f"{corpus}_sample20k_requests.parquet")
        return frame["family"].to_numpy()
    if corpus == "ecml":
        records = C.load_ecml_records()
        return np.asarray([r.declared_class if r.label == 1 else "Valid" for r in records])
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", choices=["csic", "ecml", "srbh", "wcp"], required=True)
    args = parser.parse_args()

    scores = load_scores(args.corpus)
    rows = []
    for name, (proba, y) in scores.items():
        for target in TARGETS:
            t = best_threshold(proba, y, fpr_cap=target)
            pred = (proba >= t).astype(int)
            m = metrics_from_pred(y, pred)
            rows.append({
                "corpus": args.corpus, "detector": name, "target_fpr": target,
                "threshold": float(t), "fpr": m["fpr"], "recall": m["recall"],
                "accuracy": m["accuracy"], "f1": m["f1"],
            })
    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / f"roc_points_{args.corpus}.csv", index=False)

    # Per-family recall at the oracle 2% FPR point.
    families = family_labels(args.corpus, len(next(iter(scores.values()))[1]))
    family_rows = []
    if families is not None:
        for name, (proba, y) in scores.items():
            t = best_threshold(proba, y, fpr_cap=0.02)
            pred = (proba >= t).astype(int)
            for family in sorted(set(families[y == 1])):
                sel = (y == 1) & (families == family)
                family_rows.append({
                    "corpus": args.corpus, "detector": name, "family": family,
                    "n": int(sel.sum()), "recall": float(pred[sel].mean()),
                })
    family_frame = pd.DataFrame(family_rows)
    if len(family_frame):
        family_frame.to_csv(OUT / f"family_recall_{args.corpus}.csv", index=False)

    print(frame.pivot_table(index="detector", columns="target_fpr",
                            values="recall").to_string())
    if len(family_frame):
        print(family_frame.pivot_table(index="family", columns="detector",
                                       values="recall").to_string())


if __name__ == "__main__":
    main()
