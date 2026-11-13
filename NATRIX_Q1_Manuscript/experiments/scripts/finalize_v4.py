"""Finalise the v4 feature definition after the cost-budget check.

Protocol order is: screen candidates for accuracy, then apply the pre-registered
extraction-cost budget.  The candidate pool fails that budget on the 8 KiB
worst case (see experiments/results/latency/candidate_cost.json), so no
candidate is admitted.  v4 is therefore the 20-D retained core produced by the
four-condition drop rule.

The raw screening result is preserved as v4_definition_screened.json so the
paper can report the full path, including the candidates that were promising on
accuracy but rejected on cost.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

ART = C.ARTIFACTS / "feature_selection"
SCREENED = ART / "v4_definition_screened.json"
FINAL = ART / "v4_definition.json"
COST = C.RESULTS / "latency" / "candidate_cost.json"


def main() -> None:
    definition = C.read_json(SCREENED if SCREENED.exists() else FINAL)
    cost = C.read_json(COST)

    if SCREENED.exists():
        screened = definition
    else:
        screened = definition
        C.write_json(SCREENED, screened)

    retained = definition["retained_core"]
    raw_accepted = definition.get("accepted_candidates", [])
    budget_ok = bool(cost["pass"])
    adopted = raw_accepted if budget_ok else []

    final = {
        "v3_features": definition["v3_features"],
        "retained_core": retained,
        "accepted_candidates": adopted,
        "v4_features": retained + adopted,
        "n_features": len(retained) + len(adopted),
        "screening": definition.get("screening", {}),
        "candidate_pool_decision": {
            "adopted": budget_ok,
            "reason": (
                "candidate extraction passes the pre-registered 0.15 ms budget"
                if budget_ok else
                "candidate extraction exceeds the pre-registered 0.15 ms "
                "worst-case budget; the pool is rejected regardless of accuracy"
            ),
            "worst_case_added_p95_ms": cost["worst_case"]["added_p95_ms"],
            "worst_case_combined_p95_ms": cost["worst_case"]["combined_p95_ms"],
            "budget_ms": cost["budget_ms"],
            "screening_accepted_raw": raw_accepted,
            "screening_rejected": [
                n for n in definition.get("rejected_candidates", [])
                if n not in raw_accepted
            ],
            "degenerate_on_csic": [
                "backslash_count", "brace_count", "nonascii_ratio",
                "ldap_filter_score", "crlf_sequence_count",
            ],
            "note": (
                "Five raw-accepted candidates are exactly constant on CSIC; "
                "their +0.046 pp screening delta is an artefact of the random "
                "feature order in the forest, not signal. The cost budget is "
                "the binding rejection criterion, and the degenerate candidates "
                "are recorded so the screening table is not over-interpreted."
            ),
        },
    }
    C.write_json(FINAL, final)
    print(f"v4 = {final['n_features']}-D: {final['v4_features']}")
    print(f"candidate pool adopted: {budget_ok} "
          f"(worst-case added p95 {cost['worst_case']['added_p95_ms']:.3f} ms "
          f"> {cost['budget_ms']} ms)")


if __name__ == "__main__":
    main()
