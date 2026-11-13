"""Replay an arbitrary request parquet through the frozen CRS sidecar.

Used by the adversarial test: the mutated CSIC attacks are replayed with the
same client and the same CRS configuration as the clean baseline.  The script
does not import the NATRIX model or feature registry.
"""

from __future__ import annotations

import argparse
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

OUT = C.RESULTS / "adversarial"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--tag", default="crs_mutated_csic")
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    frame = pd.read_parquet(args.input)
    required = {"method", "path", "query", "body", "user_agent", "label"}
    missing = required - set(frame.columns)
    if missing:
        raise SystemExit(f"missing columns: {sorted(missing)}")
    if args.limit and args.limit < len(frame):
        frame = frame.sample(n=args.limit, random_state=C.SEED).reset_index(drop=True)

    started = time.time()
    local = threading.local()

    def work(item):
        idx, rec = item
        if not hasattr(local, "client"):
            local.client = Client()
        status, elapsed, error = local.client.send(rec)
        return idx, status, elapsed, error

    results = [None] * len(frame)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(work, (i, rec)) for i, rec in enumerate(frame.to_dict("records"))]
        done = 0
        for fut in as_completed(futures):
            idx, status, elapsed, error = fut.result()
            results[idx] = (status, elapsed, error)
            done += 1
            if done % 1000 == 0:
                rate = done / max(time.time() - started, 1e-9)
                print(f"  {done:,}/{len(frame):,}  {rate:,.0f} req/s  "
                      f"{time.time() - started:,.0f}s", flush=True)

    status = np.asarray([r[0] for r in results], dtype=int)
    latency = np.asarray([r[1] for r in results], dtype=float)
    errors = np.asarray([r[2] for r in results], dtype=object)
    blocked = (status == 403).astype(int)

    detail = frame.copy()
    detail["status"] = status
    detail["blocked"] = blocked
    detail["latency_ms"] = latency
    detail["error"] = errors
    detail.to_parquet(OUT / f"{args.tag}_requests.parquet", index=False)

    result = {
        "input": str(args.input),
        "tag": args.tag,
        "n": int(len(frame)),
        "blocked": int(blocked.sum()),
        "block_rate": float(blocked.mean()),
        "status_counts": {str(k): int(v) for k, v in zip(*np.unique(status, return_counts=True))},
        "errors": int((status == 0).sum()),
        "elapsed_seconds": round(time.time() - started, 1),
        "throughput_rps": round(len(frame) / max(time.time() - started, 1e-9), 1),
        "latency_ms": {
            "p50": float(np.percentile(latency[latency > 0], 50)),
            "p95": float(np.percentile(latency[latency > 0], 95)),
        },
    }

    # Per-operator block rates (overlapping: a payload may have several).
    if "operators" in detail.columns:
        per_operator = []
        for token in sorted({op for ops in detail["operators"].fillna("") for op in str(ops).split(";") if op}):
            sel = detail["operators"].fillna("").str.split(";").apply(lambda ops: token in ops)
            per_operator.append({
                "operator": token,
                "n": int(sel.sum()),
                "block_rate": float(detail.loc[sel, "blocked"].mean()),
            })
        result["per_operator"] = per_operator

    C.write_json(OUT / f"{args.tag}.json", result)
    print(result)


if __name__ == "__main__":
    main()
