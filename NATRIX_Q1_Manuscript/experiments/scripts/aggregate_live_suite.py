"""Aggregate the repeated live gateway runs into one deployment-audit record.

Each run is the same labelled 20-probe suite (10 benign first, then 10 attack)
against the deployed gateway.  The script reports per-run consistency and a
pooled confusion matrix; it deliberately reports latency per run rather than a
single pooled percentile, because the deployed hop is the dominant term and
varies with cold start.

Inputs
------
experiments/results/live_gate/live_suite_run{1,2,3}.json

Outputs
-------
experiments/results/live_gate/aggregate.json
experiments/results/live_gate/aggregate.md
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[1] / "experiments" / "results" / "live_gate"
RUNS = [OUT / f"live_suite_run{i}.json" for i in (1, 2, 3)]


def main() -> None:
    runs = [json.loads(path.read_text(encoding="utf-8")) for path in RUNS]
    rows = []
    totals = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    for i, run in enumerate(runs, start=1):
        m = run["metrics"]
        for key in totals:
            totals[key] += m[key]
        rows.append(
            {
                "run": i,
                "generated_at": run["generated_at"],
                "probes": m["probes"],
                "tp": m["tp"], "fp": m["fp"], "tn": m["tn"], "fn": m["fn"],
                "accuracy": m["accuracy"],
                "false_positive_rate": m["false_positive_rate"],
                "benign_p50_ms": m["benign_latency_ms"]["p50"],
                "benign_p95_ms": m["benign_latency_ms"]["p95"],
                "attack_p50_ms": m["attack_latency_ms"]["p50"],
                "attack_p95_ms": m["attack_latency_ms"]["p95"],
                "origin_rendered": run["origin_rendered"],
                "home_title": run["home_title"],
            }
        )

    n = sum(r["probes"] for r in rows)
    aggregate = {
        "suite": "labelled live probes through the deployed gateway",
        "gateway_url": runs[0]["gateway_url"],
        "runs": rows,
        "pooled": {
            "probes": n,
            **totals,
            "accuracy": (totals["tp"] + totals["tn"]) / n,
            "false_positive_rate": totals["fp"] / (totals["fp"] + totals["tn"]),
            "recall": totals["tp"] / (totals["tp"] + totals["fn"]),
        },
        "consistent": all(
            r["tp"] == 10 and r["fp"] == 0 and r["tn"] == 10 and r["fn"] == 0
            and r["origin_rendered"] for r in rows
        ),
        "caveat": (
            "Policy check on a fixed 20-probe suite, not a generalisation estimate. "
            "The gate's raw score is not the enforcing condition; see "
            "experiments/results/deployment_boundary.json."
        ),
    }
    (OUT / "aggregate.json").write_text(json.dumps(aggregate, indent=2), encoding="utf-8")

    lines = [
        "| Run | Probes | TP | FP | TN | FN | Benign p50/p95 (ms) | Attack p50/p95 (ms) | Origin |",
        "|---:|---:|---:|---:|---:|---:|---|---|:--:|",
    ]
    for r in rows:
        lines.append(
            f"| {r['run']} | {r['probes']} | {r['tp']} | {r['fp']} | {r['tn']} | {r['fn']} | "
            f"{r['benign_p50_ms']:.0f} / {r['benign_p95_ms']:.0f} | "
            f"{r['attack_p50_ms']:.0f} / {r['attack_p95_ms']:.0f} | "
            f"{'yes' if r['origin_rendered'] else 'no'} |"
        )
    p = aggregate["pooled"]
    lines.append(
        f"| **pooled** | {p['probes']} | {p['tp']} | {p['fp']} | {p['tn']} | {p['fn']} | "
        f"- | - | - |"
    )
    lines.append("")
    lines.append(
        f"All three runs reproduced TP={rows[0]['tp']}, FP={rows[0]['fp']}, "
        f"TN={rows[0]['tn']}, FN={rows[0]['fn']}; consistent: {aggregate['consistent']}."
    )
    (OUT / "aggregate.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
