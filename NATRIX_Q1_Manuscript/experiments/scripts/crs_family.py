"""Per-attack-family block rate for the frozen CRS replay.

The score-based detectors already have per-family tables from
``roc_and_family.py``.  This script adds the same view for CRS, so the paper can
show where the signature channel helps and where it does not.  Family labels
come from the corpus, never from a classifier.  CSIC has no per-request family
labels, so only ECML and SR-BH are supported.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

OUT = C.RESULTS / "baselines"


def families(corpus: str, n: int) -> np.ndarray:
    if corpus == "ecml":
        records = C.load_ecml_records()
        if len(records) != n:
            raise SystemExit(f"ECML rows {len(records)} != CRS rows {n}")
        return np.asarray([r.declared_class if r.label == 1 else "Valid" for r in records])
    if corpus in ("srbh", "wcp"):
        frame = pd.read_parquet(OUT / f"{corpus}_sample20k_requests.parquet")
        if len(frame) != n:
            raise SystemExit(f"{corpus} sample rows {len(frame)} != CRS rows {n}")
        return frame["family"].to_numpy()
    raise SystemExit("CSIC has no per-request family labels")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", choices=["ecml", "srbh", "wcp"], required=True)
    args = parser.parse_args()

    frame = pd.read_parquet(OUT / f"crs_pl1_{args.corpus}_requests.parquet")
    y = frame["label"].to_numpy(dtype=int)
    blocked = frame["blocked"].to_numpy(dtype=int)
    fam = families(args.corpus, len(frame))

    rows = []
    for family in sorted(set(fam[y == 1])):
        sel = (y == 1) & (fam == family)
        rows.append({
            "corpus": args.corpus, "family": family, "n": int(sel.sum()),
            "recall": float(blocked[sel].mean()),
        })
    table = pd.DataFrame(rows)
    table.to_csv(OUT / f"crs_family_recall_{args.corpus}.csv", index=False)
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()
