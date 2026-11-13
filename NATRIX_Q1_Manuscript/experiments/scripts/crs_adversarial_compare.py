"""Compare CRS on the original CSIC attacks and on the bounded mutations.

The mutated parquet was produced by ``adversarial_evasion.py`` and keeps the
``original_rid`` of each source attack.  The clean CRS replay has one row per
original request.  Joining on that key gives a paired before/after comparison
on exactly the attacks that were mutated.

Treatments of non-WAF statuses
------------------------------
* ``all_non403_allow``: only 403 is a block; 400/405/transport are allows.
* ``decisions_only``: keep rows where both the clean and mutated request
  reached ModSecurity (200/403).
* ``edge_reject_as_block``: count 400/403/405 as blocks; drop transport
  failures.  This treats an nginx parser rejection as a refusal, not as a CRS
  decision, and is reported as a sensitivity.

Outputs
-------
experiments/results/adversarial/crs_evasion.json
experiments/results/adversarial/crs_evasion_by_operator.csv
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

BASE = C.RESULTS / "baselines"
ADV = C.RESULTS / "adversarial"


def summarise(frame: pd.DataFrame, label: str) -> dict:
    blocked = frame["mutated_blocked"].to_numpy(dtype=int)
    clean = frame["clean_blocked"].to_numpy(dtype=int)
    orig_recall = float(clean.mean())
    mut_recall = float(blocked.mean())
    originally_blocked = int(clean.sum())
    evaded = int(((clean == 1) & (blocked == 0)).sum())
    rescued = int(((clean == 0) & (blocked == 1)).sum())
    return {
        "treatment": label,
        "n": int(len(frame)),
        "recall_original": orig_recall,
        "recall_mutated": mut_recall,
        "delta": mut_recall - orig_recall,
        "originally_blocked": originally_blocked,
        "evaded": evaded,
        "evasion_rate_among_blocked": (
            float(evaded / originally_blocked) if originally_blocked else 0.0
        ),
        "rescue": rescued,
    }


def main() -> None:
    clean = pd.read_parquet(BASE / "crs_pl1_csic_requests.parquet")
    mutated = pd.read_parquet(ADV / "crs_mutated_csic_requests.parquet")
    if "original_rid" not in mutated.columns:
        raise SystemExit("mutated replay is missing original_rid")

    # CSIC rids repeat across source files, so they are not a unique join key.
    # The mutation builder writes one row per attack in attack order, and the
    # replay preserves that order; map the i-th mutated row to the i-th attack
    # position in the deduplicated frame.  Verify with the recorded rid.
    records, _ = C.csic_unique()
    if len(records) != len(clean):
        raise SystemExit(
            f"clean replay has {len(clean)} rows but csic_unique has {len(records)}"
        )
    attack_rows = np.asarray([i for i, r in enumerate(records) if r.label == 1], dtype=int)
    if len(attack_rows) != len(mutated):
        raise SystemExit(
            f"mutated rows {len(mutated)} != CSIC attacks {len(attack_rows)}"
        )
    expected = np.asarray([records[i].rid for i in attack_rows], dtype=object)
    if not np.array_equal(expected, mutated["original_rid"].to_numpy(dtype=object)):
        raise SystemExit("mutated row order does not match CSIC attack order")

    clean = clean.assign(clean_row=np.arange(len(clean), dtype=int))
    clean = clean[["clean_row", "status", "blocked"]].rename(
        columns={"status": "clean_status", "blocked": "clean_blocked"}
    )
    merged = mutated.assign(clean_row=attack_rows).merge(
        clean, on="clean_row", how="left", validate="many_to_one"
    )
    if merged["clean_blocked"].isna().any():
        missing = int(merged["clean_blocked"].isna().sum())
        raise SystemExit(f"{missing} mutated rows have no clean replay row")

    merged["clean_blocked"] = merged["clean_blocked"].astype(int)
    merged["mutated_blocked"] = merged["blocked"].astype(int)

    treatments = {
        "all_non403_allow": merged,
        "decisions_only": merged[
            merged["clean_status"].isin([200, 403]) & merged["status"].isin([200, 403])
        ],
        "edge_reject_as_block": merged[~merged["status"].isin([0, 502, 503, 504])].assign(
            mutated_blocked=lambda d: d["status"].isin([400, 403, 405]).astype(int)
        ),
    }
    summaries = {name: summarise(sub, name) for name, sub in treatments.items()}
    primary = treatments["decisions_only"]

    rows = []
    for token in sorted(
        {op for ops in primary["operators"].fillna("") for op in str(ops).split(";") if op}
    ):
        sel = primary["operators"].fillna("").str.split(";").apply(lambda ops: token in ops)
        sub = primary[sel]
        sub_blocked = int(sub["clean_blocked"].sum())
        rows.append({
            "operator": token,
            "n": int(len(sub)),
            "recall_original": float(sub["clean_blocked"].mean()),
            "recall_mutated": float(sub["mutated_blocked"].mean()),
            "delta": float(sub["mutated_blocked"].mean() - sub["clean_blocked"].mean()),
            "evaded": int(((sub["clean_blocked"] == 1) & (sub["mutated_blocked"] == 0)).sum()),
            "evasion_rate_among_blocked": (
                float(((sub["clean_blocked"] == 1) & (sub["mutated_blocked"] == 0)).sum() / sub_blocked)
                if sub_blocked else 0.0
            ),
        })
    per_operator = pd.DataFrame(rows)
    per_operator.to_csv(ADV / "crs_evasion_by_operator.csv", index=False)

    result = {
        "corpus": "CSIC 2010",
        "detector": "ModSecurity CRS 4.25.2 PL1",
        "mutated_attacks": int(len(merged)),
        "status_counts_clean": {
            str(k): int(v) for k, v in zip(*np.unique(merged["clean_status"], return_counts=True))
        },
        "status_counts_mutated": {
            str(k): int(v) for k, v in zip(*np.unique(merged["status"], return_counts=True))
        },
        "primary": summaries["decisions_only"],
        "treatments": summaries,
        "per_operator": per_operator.to_dict("records"),
        "notes": [
            "Mutations are deterministic and bounded, not an adversarial search.",
            "A mutated payload is not guaranteed to remain exploitable.",
            "Operator groups overlap; a payload may receive up to three operators.",
            "Primary treatment keeps only rows where both clean and mutated requests reached ModSecurity.",
        ],
    }
    (ADV / "crs_evasion.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    for name, s in summaries.items():
        print(f"{name:24s} n={s['n']:6d} recall {s['recall_original']:.4f} -> "
              f"{s['recall_mutated']:.4f}, evasion {s['evasion_rate_among_blocked']:.2%}")
    print(per_operator.to_string(index=False))


if __name__ == "__main__":
    main()
