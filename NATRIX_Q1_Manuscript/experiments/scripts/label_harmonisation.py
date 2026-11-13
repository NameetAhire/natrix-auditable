"""Does the cross-corpus direction reversal survive label harmonisation?

The binary labels are already harmonised (clean vs attack).  What differs is
the *attack-family mix*: CSIC has no public family labels, ECML declares seven
families, and SR-BH uses CAPEC families.  This script tests whether the sign
flips are explained by that mix.

Two tests:

1. **Family-balanced effect size.**  Compute Cliff's delta separately for each
   attack family against clean traffic, then average the family deltas with
   equal weight.  If the reversal disappears, it was a composition artefact.
2. **Within-family replication.**  For families present in two corpora, compare
   the sign of the family-specific delta.  If features still reverse inside the
   same family, the reversal is not just a family-mix effect.

CSIC has no per-request family labels.  Its 15,953 attacks are a mix of SQLi,
XSS, traversal, command injection, parameter tampering and malformed requests,
but the public release does not say which request is which.  A regex over the
payload recovers only a small, unreliable subset, so CSIC is used only for the
overall binary comparison.  The harmonisation test itself is ECML vs SR-BH,
the two corpora that do have family labels.  This is a deliberate scope limit,
not an imputation.

Outputs
-------
experiments/results/feature_audit/label_harmonisation.json
experiments/results/feature_audit/label_harmonisation_families.csv
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import stats_utils as S  # noqa: E402

OUT = C.RESULTS / "feature_audit"
OUT.mkdir(parents=True, exist_ok=True)

FAMILIES = ("sqli", "xss", "traversal", "cmdi", "other")
ZERO = 0.01

def ecml_family(name: str) -> str:
    return {
        "SqlInjection": "sqli",
        "XSS": "xss",
        "PathTransversal": "traversal",
        "OsCommanding": "cmdi",
    }.get(name, "other")


def srbh_family(name: str) -> str:
    return {
        "66 - SQL Injection": "sqli",
        "126 - Path Traversal": "traversal",
        "88 - OS Command Injection": "cmdi",
    }.get(name, "other")


def load(name: str):
    if name == "csic":
        records, _ = C.csic_unique()
        X, _ = C.extract_matrix(records, dtype=np.float32)
        y = C.label_array(records)
        fam = np.asarray(["unknown" if label == 1 else "clean" for label in y])
        return X, y, fam
    if name == "ecml":
        records = C.load_ecml_records()
        X, _ = C.extract_matrix(records, dtype=np.float32)
        y = C.label_array(records)
        fam = np.asarray([
            ecml_family(r.declared_class) if r.label == 1 else "clean"
            for r in records
        ])
        return X, y, fam
    if name == "srbh":
        z = np.load(C.PROCESSED / "srbh" / "srbh_features.npz", allow_pickle=True)
        req = pd.read_parquet(C.PROCESSED / "srbh" / "srbh_requests.parquet",
                              columns=["family", "label"])
        if len(req) != len(z["y"]) or not np.array_equal(req.label.to_numpy(), z["y"]):
            raise ValueError("SR-BH request cache and feature cache are not aligned")
        fam = np.asarray([
            srbh_family(f) if label == 1 else "clean"
            for f, label in zip(req.family, req.label)
        ])
        return z["X"], z["y"], fam
    raise ValueError(name)


def delta(X, y, fam, feature: int, attack_family: str | None = None) -> float:
    if attack_family is None:
        attack = y == 1
    else:
        attack = fam == attack_family
    clean = y == 0
    return S.cliffs_delta(X[attack, feature], X[clean, feature])


def sign(value: float) -> int:
    if abs(value) < ZERO:
        return 0
    return 1 if value > 0 else -1


def main() -> None:
    data = {name: load(name) for name in ("csic", "ecml", "srbh")}
    rows = []
    summary = {
        "families": {},
        "common_families": ["sqli", "traversal", "cmdi"],
        "csic_note": "no per-request family labels; overall binary comparison only",
    }

    for name, (X, y, fam) in data.items():
        counts = pd.Series(fam).value_counts().to_dict()
        summary["families"][name] = {str(k): int(v) for k, v in counts.items()}
        for feature, fname in enumerate(C.FEATURES):
            overall = delta(X, y, fam, feature)
            fam_deltas = {f: delta(X, y, fam, feature, f) for f in FAMILIES if f in counts}
            common = [f for f in ("sqli", "traversal", "cmdi") if f in fam_deltas]
            balanced = float(np.mean([fam_deltas[f] for f in common])) if common else float("nan")
            rows.append({
                "corpus": name, "feature": fname, "delta_overall": overall,
                "delta_family_balanced": balanced,
                **{f"delta_{f}": fam_deltas.get(f, float("nan")) for f in FAMILIES},
                **{f"n_{f}": counts.get(f, 0) for f in FAMILIES},
            })

    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "label_harmonisation_families.csv", index=False)

    # CSIC has no family labels, so it can only be compared on the binary
    # overall effect.  The harmonisation test is ECML vs SR-BH.
    comparisons = []
    for other in ("ecml", "srbh"):
        for feature in C.FEATURES:
            a = frame[(frame.corpus == "csic") & (frame.feature == feature)].iloc[0]
            b = frame[(frame.corpus == other) & (frame.feature == feature)].iloc[0]
            comparisons.append({
                "comparison": f"csic_vs_{other}", "feature": feature,
                "left_corpus": "csic", "right_corpus": other,
                "delta_left": a.delta_overall, "delta_right": b.delta_overall,
                "same": sign(a.delta_overall) == sign(b.delta_overall),
                "basis": "overall binary",
            })
    for feature in C.FEATURES:
        a = frame[(frame.corpus == "ecml") & (frame.feature == feature)].iloc[0]
        b = frame[(frame.corpus == "srbh") & (frame.feature == feature)].iloc[0]
        comparisons.append({
            "comparison": "ecml_vs_srbh", "feature": feature,
            "left_corpus": "ecml", "right_corpus": "srbh",
            "delta_left": a.delta_overall, "delta_right": b.delta_overall,
            "same": sign(a.delta_overall) == sign(b.delta_overall),
            "basis": "overall binary",
        })
        comparisons.append({
            "comparison": "ecml_vs_srbh_balanced", "feature": feature,
            "left_corpus": "ecml", "right_corpus": "srbh",
            "delta_left": a.delta_family_balanced, "delta_right": b.delta_family_balanced,
            "same": sign(a.delta_family_balanced) == sign(b.delta_family_balanced),
            "basis": "family-balanced",
        })
    comp = pd.DataFrame(comparisons)
    comp.to_csv(OUT / "label_harmonisation_direction.csv", index=False)

    # Within-family replication between ECML and SR-BH.
    within = []
    for family in ("sqli", "traversal", "cmdi"):
        for feature in C.FEATURES:
            a = frame[(frame.corpus == "ecml") & (frame.feature == feature)].iloc[0]
            b = frame[(frame.corpus == "srbh") & (frame.feature == feature)].iloc[0]
            within.append({
                "family": family, "feature": feature,
                "delta_ecml": a[f"delta_{family}"],
                "delta_srbh": b[f"delta_{family}"],
                "same": sign(a[f"delta_{family}"]) == sign(b[f"delta_{family}"]),
            })
    within = pd.DataFrame(within)
    within.to_csv(OUT / "label_harmonisation_within_family.csv", index=False)

    summary["direction_counts"] = {}
    for name in ("csic_vs_ecml", "csic_vs_srbh", "ecml_vs_srbh",
                 "ecml_vs_srbh_balanced"):
        sub = comp[comp.comparison == name]
        summary["direction_counts"][name] = {
            "same": int(sub.same.sum()),
            "reversed": int((~sub.same).sum()),
            "reversed_features": sub.loc[~sub.same, "feature"].tolist(),
        }
    summary["within_family"] = {}
    for family in ("sqli", "traversal", "cmdi"):
        sub = within[within.family == family]
        summary["within_family"][family] = {
            "same": int(sub.same.sum()),
            "reversed": int((~sub.same).sum()),
            "reversed_features": sub.loc[~sub.same, "feature"].tolist(),
        }
    C.write_json(OUT / "label_harmonisation.json", summary)
    print(pd.DataFrame(summary["direction_counts"]).T.to_string())
    print(pd.DataFrame(summary["within_family"]).T.to_string())
    print(frame[["corpus", "feature", "delta_overall", "delta_family_balanced",
                 "delta_sqli", "delta_xss", "delta_traversal", "delta_cmdi"]].to_string(index=False))


if __name__ == "__main__":
    main()
