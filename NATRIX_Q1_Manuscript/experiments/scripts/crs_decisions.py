"""CRS metrics under three treatments of non-WAF statuses.

Nginx can reject a request line before ModSecurity evaluates it (HTTP 400 for
malformed or traversal paths, 405 for TRACE).  Those are edge decisions, not CRS
decisions.  This script reports:

* ``all_non403_allow``: the conservative treatment used by the replay harness
  (only 403 is a block; every other status is an allow);
* ``decisions_only``: restrict to 200/403, i.e. requests that reached the WAF;
* ``edge_reject_as_block``: count 400/405 as blocks but still drop transport
  failures (0/502), because the edge did refuse the request.

Outputs
-------
experiments/results/baselines/crs_decisions_{corpus}.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

OUT = C.RESULTS / "baselines"


def metrics(y: np.ndarray, blocked: np.ndarray) -> dict:
    tn, fp, fn, tp = confusion_matrix(y, blocked, labels=[0, 1]).ravel()
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "n": int(len(y)),
        "accuracy": float((tp + tn) / len(y)),
        "fpr": float(fp / (fp + tn)) if (fp + tn) else 0.0,
        "recall": float(recall),
        "precision": float(precision),
        "f1": float(f1),
        "tp": int(tp), "tn": int(tn), "fp": int(fp), "fn": int(fn),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", choices=["csic", "ecml", "srbh", "wcp"], required=True)
    args = parser.parse_args()

    frame = pd.read_parquet(OUT / f"crs_pl1_{args.corpus}_requests.parquet")
    y = frame["label"].to_numpy(dtype=int)
    status = frame["status"].to_numpy(dtype=int)

    treatments = {
        "all_non403_allow": (
            np.ones(len(frame), dtype=bool),
            (status == 403).astype(int),
        ),
        "decisions_only": (
            np.isin(status, [200, 403]),
            (status == 403).astype(int),
        ),
        "edge_reject_as_block": (
            ~np.isin(status, [0, 502, 503, 504]),
            np.isin(status, [400, 403, 405, 413, 414]).astype(int),
        ),
    }

    result = {
        "corpus": args.corpus,
        "status_counts": {str(k): int(v) for k, v in zip(*np.unique(status, return_counts=True))},
        "treatments": {},
    }
    for name, (mask, blocked) in treatments.items():
        result["treatments"][name] = metrics(y[mask], blocked[mask])
    (OUT / f"crs_decisions_{args.corpus}.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    for name, m in result["treatments"].items():
        print(f"{name:24s} n={m['n']:6d} acc={m['accuracy']:.4f} "
              f"fpr={m['fpr']:.4f} recall={m['recall']:.4f} f1={m['f1']:.4f}")


if __name__ == "__main__":
    main()
