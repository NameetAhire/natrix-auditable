"""WCP endpoint-matched subset analysis.

The OpenAppSec WCP 2024 corpus stores every malicious request with path ``/``:
all 73,924 attacks share that one endpoint, while the 137,820 legitimate
requests span 692 sites and thousands of paths.  A full-request model can
therefore separate the classes from the endpoint alone.  The endpoint-only
lexical baseline confirms this (100% recall at 1.3% FPR on the shared 20k
sample), so the random-split WCP result is not evidence of payload detection.

This script restricts the shared sample to requests whose path is exactly
``/``.  Path is constant inside the subset, so any remaining separation comes
from method, query, body, and headers.  The clean side of the subset is small
(170 rows in the 20k sample), so FPR is reported with a Wilson interval and the
subset is described as a diagnostic, not as a headline benchmark.

Outputs
-------
experiments/results/baselines/wcp_endpoint_subset.json
experiments/results/baselines/wcp_endpoint_subset.csv
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
from compare_v3_v4 import best_threshold, metrics_from_pred  # noqa: E402

OUT = C.RESULTS / "baselines"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return float(max(0.0, centre - half)), float(min(1.0, centre + half))


def summarise(y: np.ndarray, pred: np.ndarray) -> dict:
    m = metrics_from_pred(y, pred)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    lo, hi = wilson(int(fp), int(fp + tn))
    m["fpr_ci95"] = [lo, hi]
    return m


def main() -> None:
    sample = pd.read_parquet(OUT / "wcp_sample20k_requests.parquet")
    mask = sample["path"].to_numpy() == "/"
    y = sample["label"].to_numpy(dtype=int)
    y_sub = y[mask]
    print(f"endpoint subset: {int(mask.sum()):,} rows "
          f"({int((y_sub == 0).sum()):,} clean, {int((y_sub == 1).sum()):,} attack)",
          flush=True)

    scores = {}
    nz = np.load(OUT / "natrix_wcp_sample20k_oof.npz", allow_pickle=True)
    scores["natrix_v3"] = nz["proba"]
    for view in ("full", "payload", "endpoint"):
        p = OUT / f"lexical_wcp_{view}_oof.npz"
        if p.exists():
            scores[f"lexical_{view}"] = np.load(p, allow_pickle=True)["proba"]

    rows = []
    for name, proba in scores.items():
        proba_sub = proba[mask]
        pred05 = (proba_sub >= 0.5).astype(int)
        m = summarise(y_sub, pred05)
        m.update({"detector": name, "policy": "threshold_0.5"})
        rows.append(m)
        # Oracle 2% FPR on the subset; upper bound, not deployable.
        t = best_threshold(proba_sub, y_sub, fpr_cap=0.02)
        m2 = summarise(y_sub, (proba_sub >= t).astype(int))
        m2.update({"detector": name, "policy": "fpr2_oracle", "threshold": float(t)})
        rows.append(m2)

    crs_path = OUT / "crs_pl1_wcp_requests.parquet"
    if crs_path.exists():
        crs = pd.read_parquet(crs_path)
        if len(crs) != len(sample):
            raise SystemExit(f"CRS rows {len(crs)} != sample rows {len(sample)}")
        if not np.array_equal(crs["label"].to_numpy(dtype=int), y):
            raise SystemExit("CRS labels are not aligned with the WCP sample")
        # Keep only rows that reached ModSecurity; 400/414 are nginx
        # non-decisions, not CRS allows or blocks.
        crs_status = crs["status"].to_numpy(dtype=int)
        crs_mask = mask & np.isin(crs_status, [200, 403])
        m = summarise(y[crs_mask], crs["blocked"].to_numpy(dtype=int)[crs_mask])
        m.update({"detector": "crs_pl1", "policy": "frozen_decisions_only"})
        rows.append(m)
    else:
        print("CRS replay not available yet", flush=True)

    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "wcp_endpoint_subset.csv", index=False)
    result = {
        "corpus": "wcp",
        "subset": "path == '/'",
        "n": int(mask.sum()),
        "labels": {"clean": int((y_sub == 0).sum()), "attack": int((y_sub == 1).sum())},
        "metrics": frame.to_dict("records"),
        "notes": [
            "All WCP malicious rows in the full corpus share path '/', so the random-split result is endpoint-confounded.",
            "Path is constant in this subset; separation comes from method/query/body/headers.",
            "The clean subset is small, so FPR has a wide Wilson interval.",
            "Oracle FPR2 thresholds are upper bounds, not deployable policies.",
        ],
    }
    (OUT / "wcp_endpoint_subset.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(frame[["detector", "policy", "accuracy", "fpr", "recall", "f1",
                 "tp", "tn", "fp", "fn"]].to_string(index=False))


if __name__ == "__main__":
    main()
