"""Measure the extraction cost of the pre-registered v4 candidates.

Protocol/feature_candidates.md sets a per-candidate budget of <= 0.15 ms added
to Python extraction p95 and <= 0.05 ms added to Node extraction p95, measured
on the 8 KiB worst case.

The candidate extractor is an *additional* pass over the payload, so its own
p95 is a lower bound on the added cost.  The script also times the combined
v3 + candidate pass to report the total v4 extraction cost.  The measurement is
deliberately pessimistic: the worst-case payload is filled with parameter
separators, percent escapes, braces and long runs.

Outputs
-------
experiments/results/latency/candidate_cost.json
"""

from __future__ import annotations

import sys
import time
import types
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import candidate_features as CF  # noqa: E402


def pct(values, p):
    return float(np.percentile(values, p))


def make_payloads():
    # Worst case: 8 KiB of delimiters, escapes and parameter pairs.
    pairs = "&".join(f"p{i}=%7bvalue{i}%7d%24%3b" for i in range(180))
    path = "/" + "/".join(f"seg{i}" for i in range(40))
    worst = (path + "?" + pairs)[:8192]
    if len(worst) < 8192:
        worst = worst + (";" * (8192 - len(worst)))

    # Long-run case: no delimiters, stresses the longest-token loop.
    long_run = "A" * 8192

    # Body-heavy form case.
    body = "&".join(f"field{i}=value{i}" for i in range(300))[:8192]

    # Typical traffic cases.
    typical = [
        "/catalogo/productos.php?id=123&category=libros",
        "/login?user=alice&password=hunter2",
        "/search?q=web+application+firewall&page=2",
        "/api/v1/items/42?fields=name,price",
        "/index.php?option=com_content&view=article&id=17",
    ]
    return {
        "worst_delimiters": worst,
        "worst_long_run": long_run,
        "worst_body": body,
        "typical": typical,
    }


def rec(payload):
    return types.SimpleNamespace(
        payload=payload, url=payload.split(" ")[0], user_agent="Mozilla/5.0",
        method="GET",
    )


def time_call(fn, arg, warmup=5, batches=60, batch=10):
    """Batch timing: average per-call cost over a short batch.

    Per-call wall-clock timing on a shared workstation is dominated by
    scheduler preemption; the batch mean is the stable quantity that matters
    for an inline per-request budget.
    """
    for _ in range(warmup):
        for _ in range(batch):
            fn(arg)
    samples = []
    for _ in range(batches):
        t0 = time.perf_counter_ns()
        for _ in range(batch):
            fn(arg)
        t1 = time.perf_counter_ns()
        samples.append((t1 - t0) / 1e6 / batch)
    return samples


def v3_features(x):
    return C.registry.extract_features(
        x.payload, user_agent=x.user_agent, method=x.method, version="v3"
    )


def both(x):
    v3_features(x)
    CF.extract(x)


def extract_selected(rec, funcs):
    state = CF.prepare(rec)
    return [fn(state) for fn in funcs]


def main() -> None:
    payloads = make_payloads()
    rows = []
    all_v3 = []
    all_cand = []
    all_both = []
    per_candidate = {name: [] for name in CF.CANDIDATE_NAMES}

    for name, payload in payloads.items():
        items = payload if isinstance(payload, list) else [payload]
        for idx, item in enumerate(items):
            r = rec(item)
            v3 = time_call(v3_features, r)
            cand = time_call(CF.extract, r)
            combined = time_call(both, r)
            all_v3.extend(v3)
            all_cand.extend(cand)
            all_both.extend(combined)
            rows.append({
                "payload": f"{name}[{idx}]",
                "chars": len(item),
                "v3_p50_ms": pct(v3, 50),
                "v3_p95_ms": pct(v3, 95),
                "candidates_p50_ms": pct(cand, 50),
                "candidates_p95_ms": pct(cand, 95),
                "combined_p50_ms": pct(combined, 50),
                "combined_p95_ms": pct(combined, 95),
                "added_p95_ms": pct(cand, 95),
            })
            print(f"{rows[-1]['payload']:<24} chars={len(item):5d} "
                  f"v3_p95={rows[-1]['v3_p95_ms']:.3f} "
                  f"cand_p95={rows[-1]['candidates_p95_ms']:.3f} "
                  f"combined_p95={rows[-1]['combined_p95_ms']:.3f}", flush=True)

            # Per-candidate marginal cost on the same shared parse.
            state = CF.prepare(r)
            for fname, fn in zip(CF.CANDIDATE_NAMES, CF.FEATURE_FUNCS):
                samples = time_call(fn, state)
                per_candidate[fname].append({
                    "payload": f"{name}[{idx}]",
                    "chars": len(item),
                    "p50_ms": pct(samples, 50),
                    "p95_ms": pct(samples, 95),
                })

    worst = [r for r in rows if r["payload"].startswith("worst")]
    per_candidate_summary = []
    for fname, measurements in per_candidate.items():
        worst_rows = [m for m in measurements if m["payload"].startswith("worst")]
        typical_rows = [m for m in measurements if m["payload"].startswith("typical")]
        worst_p95 = max(m["p95_ms"] for m in worst_rows)
        typical_p95 = float(np.median([m["p95_ms"] for m in typical_rows]))
        per_candidate_summary.append({
            "feature": fname,
            "worst_p95_ms": worst_p95,
            "typical_p95_ms": typical_p95,
            "within_budget": bool(worst_p95 <= 0.15),
            "measurements": measurements,
        })
    per_candidate_summary.sort(key=lambda r: r["worst_p95_ms"], reverse=True)
    cost_by_name = {r["feature"]: r["worst_p95_ms"] for r in per_candidate_summary}
    accepted_names = []
    screen_path = C.RESULTS / "v4_screening" / "candidate_screening.csv"
    if screen_path.exists():
        import pandas as pd

        screen = pd.read_csv(screen_path)
        accepted_names = screen.loc[screen["accepted"], "candidate"].tolist()
    cheap_names = [n for n in accepted_names if cost_by_name.get(n, 1e9) <= 0.15]
    subsets = {
        "all_24": list(CF.CANDIDATE_NAMES),
        "accepted_12": accepted_names,
        "accepted_cheap": cheap_names,
    }
    subset_costs = {}
    for label, names in subsets.items():
        if not names:
            continue
        funcs = [fn for name, fn in zip(CF.CANDIDATE_NAMES, CF.FEATURE_FUNCS) if name in set(names)]
        values = []
        for pname, payload in payloads.items():
            if not pname.startswith("worst"):
                continue
            items = payload if isinstance(payload, list) else [payload]
            for item in items:
                r = rec(item)
                values.extend(time_call(lambda x: extract_selected(x, funcs), r))
        subset_costs[label] = {
            "n_features": len(names),
            "features": names,
            "worst_p95_ms": pct(values, 95),
        }
    summary = {
        "protocol": "5 warmup batches + 60 timed batches of 10 calls; perf_counter_ns; per-call batch mean",
        "python_version": sys.version,
        "per_payload": rows,
        "per_candidate": per_candidate_summary,
        "subset_costs": subset_costs,
        "overall": {
            "v3_p50_ms": pct(all_v3, 50),
            "v3_p95_ms": pct(all_v3, 95),
            "candidates_p50_ms": pct(all_cand, 50),
            "candidates_p95_ms": pct(all_cand, 95),
            "combined_p50_ms": pct(all_both, 50),
            "combined_p95_ms": pct(all_both, 95),
        },
        "worst_case": {
            "v3_p95_ms": max(r["v3_p95_ms"] for r in worst),
            "candidates_p95_ms": max(r["candidates_p95_ms"] for r in worst),
            "combined_p95_ms": max(r["combined_p95_ms"] for r in worst),
            "added_p95_ms": max(r["added_p95_ms"] for r in worst),
        },
        "budget_ms": 0.15,
        "pass": max(r["added_p95_ms"] for r in worst) <= 0.15,
    }
    C.write_json(C.RESULTS / "latency" / "candidate_cost.json", summary)
    print(f"\nworst-case candidate pass p95: "
          f"{summary['worst_case']['added_p95_ms']:.3f} ms "
          f"(budget {summary['budget_ms']} ms) -> "
          f"{'PASS' if summary['pass'] else 'FAIL'}")
    print("\nper-candidate marginal cost (shared parse excluded):")
    for r in per_candidate_summary:
        print(f"  {r['feature']:<28} worst p95={r['worst_p95_ms']:.4f} ms "
              f"typical p95={r['typical_p95_ms']:.4f} ms "
              f"{'PASS' if r['within_budget'] else 'FAIL'}")
    print("\nsubset cost on the 8 KiB worst case:")
    for label, info in subset_costs.items():
        print(f"  {label:<18} n={info['n_features']:2d} "
              f"p95={info['worst_p95_ms']:.4f} ms")


if __name__ == "__main__":
    main()
