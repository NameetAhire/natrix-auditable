"""Merge the four evidence streams into one drop-decision table.

Inputs
------
experiments/results/feature_audit/csic_univariate.csv
experiments/results/feature_audit/csic_model_importance.csv
experiments/results/feature_audit/csic_permutation_raw.csv
experiments/results/ablation_csic/metrics.csv

Output
------
artifacts/feature_selection/drop_evidence.csv
artifacts/feature_selection/v4_core.json

The four-condition rule is the one frozen in protocol/analysis_plan.md.  The
safety exception list is in protocol/safety_features.md and was fixed before
the ablation was inspected.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

AUDIT = C.RESULTS / "feature_audit"
ABLATION = C.RESULTS / "ablation_csic" / "metrics.csv"
OUT = C.ARTIFACTS / "feature_selection"
OUT.mkdir(parents=True, exist_ok=True)

SAFETY = {
    "sql_keyword_score",
    "xss_keyword_score",
    "path_traversal_score",
    "command_injection_score",
    "null_byte_score",
    "request_method_risk",
    "user_agent_anomaly",
}

ACC_MARGIN = 0.002   # 0.2 pp
FPR_MARGIN = 0.0010  # 0.10 pp


def t_interval(values) -> tuple[float, float, float]:
    arr = np.asarray(values, dtype=float)
    n = len(arr)
    mean = float(arr.mean())
    if n < 2:
        return mean, float("-inf"), float("inf")
    se = float(arr.std(ddof=1) / np.sqrt(n))
    half = float(stats.t.ppf(0.975, n - 1) * se)
    return mean, mean - half, mean + half


def main() -> None:
    uni = pd.read_csv(AUDIT / "csic_univariate.csv").set_index("feature")
    imp = pd.read_csv(AUDIT / "csic_model_importance.csv").set_index("feature")
    perm_raw = pd.read_csv(AUDIT / "csic_permutation_raw.csv")

    if ABLATION.exists():
        abl = pd.read_csv(ABLATION).set_index("subset")
        full = abl.loc["full_22"]
    else:
        abl = None
        full = None

    perm_ci = {}
    for feature, group in perm_raw.groupby("feature"):
        perm_ci[feature] = t_interval(group["importance_mean"])

    importance_values = imp["importance_mean"].to_numpy(dtype=float)
    q25 = float(np.quantile(importance_values, 0.25))

    rows = []
    for feature in C.FEATURES:
        u = uni.loc[feature]
        i = imp.loc[feature]
        perm_mean, perm_lo, perm_hi = perm_ci[feature]

        near_constant = u["clean_zero_frac"] >= 0.99 and u["attack_zero_frac"] >= 0.99
        c1 = bool(
            (u["p_bh"] >= 0.05 and abs(u["cliffs_delta"]) < 0.10) or near_constant
        )
        bottom_quartile = perm_mean <= q25
        ci_contains_zero = perm_lo <= 0.0 <= perm_hi
        c2 = bool(bottom_quartile and ci_contains_zero)

        if abl is not None and f"drop_{feature}" in abl.index:
            a = abl.loc[f"drop_{feature}"]
            d_acc = float(a["accuracy"] - full["accuracy"])
            d_fpr = float(a["fpr"] - full["fpr"])
            d_fnr = float(a["fnr"] - full["fnr"])
            d_lo = float(a["delta_accuracy_ci_lo"])
            d_hi = float(a["delta_accuracy_ci_hi"])
            c3 = bool(d_acc >= -ACC_MARGIN and d_lo >= -ACC_MARGIN and d_fpr <= FPR_MARGIN)
        else:
            d_acc = d_fpr = d_fnr = d_lo = d_hi = float("nan")
            c3 = False

        c4 = feature not in SAFETY
        drop = bool(c1 and c2 and c3 and c4)

        if feature in SAFETY:
            reason = "retained_safety"
        elif drop:
            reason = "all four conditions met"
        else:
            failed = [
                name
                for name, ok in [("c1_univariate", c1), ("c2_importance", c2),
                                 ("c3_ablation", c3), ("c4_not_safety", c4)]
                if not ok
            ]
            reason = "retained: " + ",".join(failed)

        rows.append(
            {
                "feature": feature,
                "group": u["group"],
                "p_bh": float(u["p_bh"]),
                "cliffs_delta": float(u["cliffs_delta"]),
                "zero_frac_clean": float(u["clean_zero_frac"]),
                "zero_frac_attack": float(u["attack_zero_frac"]),
                "perm_importance_mean": perm_mean,
                "perm_ci_lo": perm_lo,
                "perm_ci_hi": perm_hi,
                "perm_rank": int(i["perm_rank"]),
                "bottom_quartile": bottom_quartile,
                "ablation_delta_accuracy": d_acc,
                "ablation_delta_accuracy_ci_lo": d_lo,
                "ablation_delta_accuracy_ci_hi": d_hi,
                "ablation_delta_fpr": d_fpr,
                "ablation_delta_fnr": d_fnr,
                "c1_univariate": c1,
                "c2_importance": c2,
                "c3_ablation": c3,
                "c4_not_safety": c4,
                "decision": "dropped" if drop else "retained",
                "reason": reason,
            }
        )

    frame = pd.DataFrame(rows).sort_values(["decision", "perm_rank"])
    frame.to_csv(OUT / "drop_evidence.csv", index=False)

    retained = frame.loc[frame.decision == "retained", "feature"].tolist()
    dropped = frame.loc[frame.decision == "dropped", "feature"].tolist()
    C.write_json(
        OUT / "v4_core.json",
        {
            "retained_core": retained,
            "dropped": dropped,
            "n_retained": len(retained),
            "n_dropped": len(dropped),
            "criteria": {
                "univariate": "BH p>=0.05 and |Cliff delta|<0.10, or zero in >=99% of both classes",
                "importance": "permutation importance in bottom quartile and 95% CI contains 0",
                "ablation": f"delta accuracy >= -{ACC_MARGIN}, CI lower >= -{ACC_MARGIN}, delta FPR <= {FPR_MARGIN}",
                "safety": sorted(SAFETY),
            },
        },
    )
    print(frame[["feature", "c1_univariate", "c2_importance", "c3_ablation",
                 "c4_not_safety", "decision"]].to_string(index=False))
    print(f"\nretained {len(retained)}: {retained}")
    print(f"dropped  {len(dropped)}: {dropped}")


if __name__ == "__main__":
    main()
