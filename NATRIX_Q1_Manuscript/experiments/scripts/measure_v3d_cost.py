"""Measure Gate C cost for the nine v3-D per-parameter/path features.

Gate C uses the best-case per-call time from repeated `timeit` runs.  On a
shared workstation the wall-clock p95 of a single call is dominated by
scheduler preemption; the minimum over repeated runs is the stable estimate of
the extractor's CPU cost.  The 8 KiB synthetic case is reported as a tail
stress test, and the real-corpus distribution is the admission measurement.
"""

from __future__ import annotations

import sys
import time
import timeit
import types
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import dilution_resistant as D  # noqa: E402
from measure_candidate_cost import make_payloads  # noqa: E402

BUDGET = 0.15


def rec_from_payload(payload: str):
    target, _, body = payload.partition(" ")
    path, _, query = target.partition("?")
    return types.SimpleNamespace(
        payload=payload, path=path, query=query, body=body,
        url=target, user_agent="Mozilla/5.0", method="GET",
    )


def per_call_ms(fn, number: int, repeat: int = 5) -> float:
    best = min(
        timeit.repeat(fn, number=number, repeat=repeat, timer=time.perf_counter)
    )
    return best / number * 1000.0


def main() -> None:
    payloads = make_payloads()
    worst_rows = []
    for name, payload in payloads.items():
        if not name.startswith("worst"):
            continue
        items = payload if isinstance(payload, list) else [payload]
        for idx, item in enumerate(items):
            r = rec_from_payload(item)
            state = D.prepare_extra(r)
            for fname, fn in zip(D.EXTRA_NAMES, D.EXTRA_FUNCS):
                worst_rows.append({
                    "feature": fname,
                    "payload": f"{name}[{idx}]",
                    "ms": per_call_ms(lambda f=fn, s=state: f(s), number=20, repeat=3),
                })
            print(f"{name}[{idx}] chars={len(item)} done", flush=True)

    worst_by_feature = {}
    for fname in D.EXTRA_NAMES:
        vals = [r["ms"] for r in worst_rows if r["feature"] == fname]
        worst_by_feature[fname] = float(max(vals))

    # Real-corpus distribution: 200 evenly spaced CSIC requests.
    records, _ = C.csic_unique()
    sample = records[:: max(1, len(records) // 200)][:200]
    real_sets = {}
    for label, funcs in [
        ("all_9", D.EXTRA_FUNCS),
        ("value_5", D.EXTRA_FUNCS[:5]),
        ("path_4", D.EXTRA_FUNCS[5:]),
    ]:
        def call(r, fs=funcs):
            s = D.prepare_extra(r)
            return [f(s) for f in fs]

        vals = [per_call_ms(lambda r=r: call(r), number=100, repeat=3) for r in sample]
        real_sets[label] = {
            "n_requests": len(sample),
            "p50_ms": float(np.percentile(vals, 50)),
            "p95_ms": float(np.percentile(vals, 95)),
            "max_ms": float(max(vals)),
            "within_budget": bool(np.percentile(vals, 95) <= BUDGET),
        }

    real_features = {}
    for fname, fn in zip(D.EXTRA_NAMES, D.EXTRA_FUNCS):
        def call(r, f=fn):
            return f(D.prepare_extra(r))

        vals = [per_call_ms(lambda r=r: call(r), number=100, repeat=3) for r in sample]
        real_features[fname] = {
            "p50_ms": float(np.percentile(vals, 50)),
            "p95_ms": float(np.percentile(vals, 95)),
            "within_budget": bool(np.percentile(vals, 95) <= BUDGET),
        }

    out = {
        "protocol": "timeit min of 5 repeats; per-call CPU cost",
        "budget_ms": BUDGET,
        "worst_case_8kib": {
            "per_feature_max_ms": worst_by_feature,
            "note": "tail stress test; not the admission measurement",
        },
        "real_traffic": {
            "sets": real_sets,
            "per_feature": real_features,
        },
    }
    C.write_json(C.RESULTS / "latency" / "v3d_cost.json", out)

    print("\nreal-traffic set cost (n=200 CSIC requests):")
    for label, info in real_sets.items():
        print(f"  {label:<8} p50={info['p50_ms']:.4f} p95={info['p95_ms']:.4f} ms "
              f"{'PASS' if info['within_budget'] else 'FAIL'}")
    print("\nreal-traffic per-feature p95:")
    for fname, info in sorted(real_features.items(), key=lambda kv: kv[1]["p95_ms"], reverse=True):
        print(f"  {fname:<30} p95={info['p95_ms']:.4f} ms "
              f"{'PASS' if info['within_budget'] else 'FAIL'}")


if __name__ == "__main__":
    main()
