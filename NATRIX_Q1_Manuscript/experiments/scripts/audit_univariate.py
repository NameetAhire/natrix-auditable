"""Univariate audit of the 22 v3 features on CSIC 2010.

Produces the descriptive/effect-size table that feeds the drop-evidence pack.
Multivariate importance, stability and ablation are in audit_model.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency, mannwhitneyu

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import stats_utils as S  # noqa: E402

OUT = C.RESULTS / "feature_audit"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> None:
    records, ambiguous = C.csic_unique()
    X, _static = C.extract_matrix(records)
    y = C.label_array(records)

    print(f"CSIC unique: {len(y):,}  clean={int((y == 0).sum()):,}  attack={int((y == 1).sum()):,}")
    print(f"ambiguous dropped: {len(ambiguous)}")

    groups = C.registry.get_feature_groups()
    group_of = {name: g for g, names in groups.items() for name in names}

    rows = []
    pvals = []
    for j, name in enumerate(C.FEATURES):
        col = X[:, j]
        clean = col[y == 0]
        attack = col[y == 1]
        n_unique = len(np.unique(col))

        zero_clean = float(np.mean(clean == 0))
        zero_attack = float(np.mean(attack == 0))

        if n_unique <= 2:
            table = np.array(
                [
                    [int(np.sum((clean == 0))), int(np.sum((clean != 0)))],
                    [int(np.sum((attack == 0))), int(np.sum((attack != 0)))],
                ]
            )
            if (table.sum(axis=0) == 0).any() or (table.sum(axis=1) == 0).any():
                stat, p = 0.0, 1.0
            else:
                stat, p, _, _ = chi2_contingency(table, correction=False)
            test = "chi2"
        else:
            res = mannwhitneyu(clean, attack, alternative="two-sided")
            stat, p = float(res.statistic), float(res.pvalue)
            test = "mannwhitney"

        pvals.append(p)
        rows.append(
            {
                "feature": name,
                "group": group_of.get(name, "unknown"),
                "n_unique": n_unique,
                "clean_zero_frac": round(zero_clean, 6),
                "attack_zero_frac": round(zero_attack, 6),
                "clean_median": float(np.median(clean)),
                "attack_median": float(np.median(attack)),
                "clean_iqr": float(np.subtract(*np.percentile(clean, [75, 25]))),
                "attack_iqr": float(np.subtract(*np.percentile(attack, [75, 25]))),
                "clean_mean": float(clean.mean()),
                "attack_mean": float(attack.mean()),
                "test": test,
                "statistic": stat,
                "p_value": p,
                "cliffs_delta": S.cliffs_delta(attack, clean),
                "cohens_d": S.cohens_d(attack, clean),
            }
        )

    frame = pd.DataFrame(rows)
    frame["p_bh"] = S.bh_correction(pvals)
    frame = frame.sort_values("p_bh")

    frame.to_csv(OUT / "csic_univariate.csv", index=False)

    constant = frame[(frame.clean_zero_frac >= 0.99) & (frame.attack_zero_frac >= 0.99)]
    weak = frame[(frame.p_bh >= 0.05) & (frame.cliffs_delta.abs() < 0.10)]
    strong = frame[(frame.p_bh < 0.05) & (frame.cliffs_delta.abs() >= 0.30)]

    summary = {
        "n_records": int(len(y)),
        "n_features": len(C.FEATURES),
        "near_constant_both_classes": constant.feature.tolist(),
        "weak_effect_nonsignificant": weak.feature.tolist(),
        "strong_effect": strong.feature.tolist(),
        "top_by_effect": frame.reindex(frame.cliffs_delta.abs().sort_values(ascending=False).index)
        .head(10)[["feature", "cliffs_delta", "p_bh"]]
        .to_dict("records"),
    }
    C.write_json(OUT / "csic_univariate_summary.json", summary)
    print(frame[["feature", "clean_zero_frac", "attack_zero_frac", "cliffs_delta", "p_bh"]].to_string(index=False))
    print("\n" + str(summary["near_constant_both_classes"]))
    print("weak:", summary["weak_effect_nonsignificant"])


if __name__ == "__main__":
    main()
