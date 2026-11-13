"""Render the Gate C per-candidate cost table from candidate_cost.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


def main() -> None:
    data = json.loads((C.RESULTS / "latency" / "candidate_cost.json").read_text(encoding="utf-8"))
    costs = {r["feature"]: r for r in data["per_candidate"]}
    screen_path = C.RESULTS / "v4_screening" / "candidate_screening.csv"
    accepted = set()
    if screen_path.exists():
        import pandas as pd

        screen = pd.read_csv(screen_path)
        accepted = set(screen.loc[screen["accepted"], "candidate"])

    lines = [
        "# Gate C: measured extraction cost per candidate",
        "",
        "Batch timing (10 calls per batch, 60 batches) on the 8 KiB",
        "delimiter-heavy worst case. Marginal cost excludes the shared parse;",
        "the set rows include it because the candidate extractor is an",
        "additional pass over the payload. The budget is 0.15 ms for the",
        "whole admitted block, not a per-feature allowance.",
        "",
        "| candidate | accepted by Gate B | marginal p95 (ms) | typical p95 (ms) | marginal <= 0.15 ms |",
        "|---|---|---:|---:|---|",
    ]
    for name, row in sorted(costs.items(), key=lambda kv: kv[1]["worst_p95_ms"], reverse=True):
        lines.append(
            f"| `{name}` | {'yes' if name in accepted else 'no'} | "
            f"{row['worst_p95_ms']:.3f} | {row['typical_p95_ms']:.4f} | "
            f"{'yes' if row['within_budget'] else 'no'} |"
        )
    lines += ["", "## Set-level cost", "", "| set | features | p95 (ms) |", "|---|---:|---:|"]
    for label, info in data.get("subset_costs", {}).items():
        pretty = {"all_24": "all candidates", "accepted_12": "Gate B accepted",
                  "accepted_cheap": "accepted, marginal <= 0.15 ms"}.get(label, label)
        lines.append(f"| {pretty} | {info['n_features']} | {info['worst_p95_ms']:.3f} |")
    lines += [
        "",
        "The full pass is 2.33 ms and the Gate B accepted block is 1.71 ms,",
        "both above the 0.15 ms envelope. Even the nine accepted candidates",
        "whose marginal cost is below 0.15 ms cost 0.73 ms as a set because",
        "each shares the second parse. The gate is therefore applied to the",
        "block; selecting a cheap subset after inspecting this table would be",
        "the post-hoc search the protocol forbids.",
        "",
    ]
    out = C.ROOT / "tables" / "candidate_cost.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
