"""Retry CRS replay rows that failed at the transport or proxy layer.

A status of 0 (client error) or 502 (proxy could not reach the origin) is not a
WAF decision.  Treating those rows as "allowed" is conservative for recall but
it is not a clean measurement, so this script replays only the failed rows with
a small worker pool and rewrites the detail parquet and summary JSON.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
from crs_baseline import Client, metrics  # noqa: E402

OUT = C.RESULTS / "baselines"
# 400 is included because nginx rejects a request line containing an invalid
# percent escape before ModSecurity evaluates it.  The client now encodes such
# escapes, so these rows can be replayed faithfully instead of being counted
# as WAF allows.
RETRY = {0, 400, 500, 502, 503, 504}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument(
        "--dir",
        default=str(OUT),
        help="directory holding <tag>_requests.parquet (default: results/baselines)",
    )
    args = parser.parse_args()

    out = Path(args.dir)
    path = out / f"{args.tag}_requests.parquet"
    frame = pd.read_parquet(path)
    bad = frame["status"].isin(RETRY)
    print(f"{args.tag}: {int(bad.sum()):,}/{len(frame):,} rows to retry", flush=True)
    if not bad.any():
        return

    subset = frame.loc[bad].copy()
    local = threading.local()

    def work(item):
        idx, rec = item
        if not hasattr(local, "client"):
            local.client = Client()
        status, elapsed, error = local.client.send(rec)
        return idx, status, elapsed, error

    started = time.time()
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(work, (i, rec)) for i, rec in enumerate(subset.to_dict("records"))]
        for fut in as_completed(futures):
            results.append(fut.result())
    for idx, status, elapsed, error in results:
        row = subset.index[idx]
        frame.at[row, "status"] = status
        frame.at[row, "blocked"] = int(status == 403)
        frame.at[row, "latency_ms"] = elapsed
        frame.at[row, "error"] = error
    frame.to_parquet(path, index=False)

    status = frame["status"].to_numpy(dtype=int)
    blocked = frame["blocked"].to_numpy(dtype=int)
    y = frame["label"].to_numpy(dtype=int)
    result = {
        "tag": args.tag,
        "retried": int(bad.sum()),
        "remaining_errors": int(np.isin(status, list(RETRY)).sum()),
        "status_counts": {str(k): int(v) for k, v in zip(*np.unique(status, return_counts=True))},
        **metrics(y, blocked),
        "latency_ms": {
            "p50": float(np.percentile(frame.loc[frame.latency_ms > 0, "latency_ms"], 50)),
            "p95": float(np.percentile(frame.loc[frame.latency_ms > 0, "latency_ms"], 95)),
        },
        "elapsed_seconds_retry": round(time.time() - started, 1),
    }
    C.write_json(out / f"{args.tag}.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
