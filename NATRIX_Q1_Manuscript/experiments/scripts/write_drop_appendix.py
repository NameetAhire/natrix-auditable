"""Render the feature-drop evidence table and the Phase-2 appendix.

Input : artifacts/feature_selection/drop_evidence.csv
Output: tables/drop_evidence.md
        tables/drop_evidence.tex

Every retained and dropped feature gets an explicit four-condition verdict, so
the appendix can state why a feature is present or absent without prose that is
not backed by a row in the CSV.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

OUT = C.TABLES
OUT.mkdir(parents=True, exist_ok=True)


def flag(value: bool) -> str:
    return "yes" if bool(value) else "no"


def fmt_p_md(value: float) -> str:
    if value == 0 or value < 1e-300:
        return "<1e-300"
    return f"{value:.3g}"


def fmt_p_tex(value: float) -> str:
    if value == 0 or value < 1e-300:
        return "$<10^{-300}$"
    if value < 0.001:
        mantissa, exponent = f"{value:.2e}".split("e")
        return f"${mantissa}\\times10^{{{int(exponent)}}}$"
    return f"{value:.3g}"


def sentence(row: pd.Series) -> str:
    if row["reason"] == "retained_safety":
        return (
            f"`{row['feature']}` is retained by the pre-registered safety "
            "exception: it is a direct runtime policy signal, so its statistical "
            "importance does not decide whether the rule exists. Removing it from "
            "the model contract would not remove the policy rule."
        )
    if row["decision"] == "dropped":
        return (
            f"`{row['feature']}` is dropped: BH-adjusted p={row['p_bh']:.3g} "
            f"with Cliff's delta={row['cliffs_delta']:+.4f}, permutation "
            f"importance {row['perm_importance_mean']:+.6f} "
            f"(95% CI [{row['perm_ci_lo']:+.6f}, {row['perm_ci_hi']:+.6f}], "
            f"rank {int(row['perm_rank'])}/22), and leave-one-out ablation "
            f"delta accuracy {row['ablation_delta_accuracy']:+.4%} "
            f"(95% CI [{row['ablation_delta_accuracy_ci_lo']:+.4%}, "
            f"{row['ablation_delta_accuracy_ci_hi']:+.4%}]) with delta FPR "
            f"{row['ablation_delta_fpr']:+.4%}. All four drop conditions hold."
        )
    failed = []
    if not row["c1_univariate"]:
        failed.append(
            f"C1 (univariate: p={row['p_bh']:.3g}, "
            f"delta={row['cliffs_delta']:+.4f})"
        )
    if not row["c2_importance"]:
        failed.append(
            f"C2 (importance: mean={row['perm_importance_mean']:+.6f}, "
            f"rank={int(row['perm_rank'])}/22)"
        )
    if not row["c3_ablation"]:
        failed.append(
            f"C3 (ablation: delta accuracy={row['ablation_delta_accuracy']:+.4%}, "
            f"delta FPR={row['ablation_delta_fpr']:+.4%})"
        )
    if not row["c4_not_safety"]:
        failed.append("C4 (safety exception)")
    return (
        f"`{row['feature']}` is retained because at least one condition fails: "
        + "; ".join(failed)
        + "."
    )


def main() -> None:
    path = C.ARTIFACTS / "feature_selection" / "drop_evidence.csv"
    frame = pd.read_csv(path)
    frame = frame.sort_values(
        ["decision", "perm_rank"], ascending=[True, True]
    )

    md = [
        "# Feature-drop evidence (Phase 2 appendix)",
        "",
        "Drop rule (frozen in `protocol/analysis_plan.md`): a feature is removed",
        "only when all four conditions hold — C1 univariate null or near-constant,",
        "C2 permutation importance in the bottom quartile with a 95% CI containing",
        "zero, C3 leave-one-feature-out ablation within the practical-equivalence",
        "margin, and C4 not on the pre-registered safety list.",
        "",
        "| feature | group | p (BH) | Cliff δ | perm. imp. | 95% CI | rank | Δacc | ΔFPR | C1 | C2 | C3 | C4 | decision |",
        "|---|---|---:|---:|---:|---|---:|---:|---:|:--:|:--:|:--:|:--:|---|",
    ]
    for _, row in frame.iterrows():
        md.append(
            "| `{feature}` | {group} | {p} | {d:+.4f} | {imp:+.6f} | "
            "[{lo:+.6f}, {hi:+.6f}] | {rank}/22 | {da:+.4%} | {df:+.4%} | "
            "{c1} | {c2} | {c3} | {c4} | **{decision}** |".format(
                feature=row["feature"], group=row["group"], p=fmt_p_md(row["p_bh"]),
                d=row["cliffs_delta"], imp=row["perm_importance_mean"],
                lo=row["perm_ci_lo"], hi=row["perm_ci_hi"],
                rank=int(row["perm_rank"]), da=row["ablation_delta_accuracy"],
                df=row["ablation_delta_fpr"],
                c1=flag(row["c1_univariate"]), c2=flag(row["c2_importance"]),
                c3=flag(row["c3_ablation"]), c4=flag(row["c4_not_safety"]),
                decision=row["decision"],
            )
        )
    md += ["", "## Per-feature justification", ""]
    for _, row in frame.iterrows():
        md.append(f"- {sentence(row)}")
    md.append("")

    (OUT / "drop_evidence.md").write_text("\n".join(md), encoding="utf-8")

    uni = [
        "# Univariate screen (CSIC 2010)",
        "",
        "Zero fractions are the proportion of exact zeros in each class. The",
        "decision column repeats the four-condition verdict; the multivariate",
        "evidence is in `drop_multivariate.md`.",
        "",
        "| feature | group | p (BH) | Cliff $\\delta$ | zero clean | zero attack | decision |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for _, row in frame.iterrows():
        uni.append(
            "| `{feature}` | {group} | {p} | {d:+.4f} | {zc:.3f} | {za:.3f} | "
            "**{decision}** |".format(
                feature=row["feature"], group=row["group"],
                p=fmt_p_md(row["p_bh"]), d=row["cliffs_delta"],
                zc=row["zero_frac_clean"], za=row["zero_frac_attack"],
                decision=row["decision"],
            )
        )
    (OUT / "drop_univariate.md").write_text("\n".join(uni) + "\n", encoding="utf-8")

    multi = [
        "# Multivariate and ablation evidence (CSIC 2010)",
        "",
        "Permutation importance is the mean over five folds; the CI is a 95%",
        "bootstrap interval. Ablation removes one feature at a time from the",
        "22-D gate. `failed` lists the conditions that prevented a drop; a",
        "dropped feature has all four conditions satisfied.",
        "",
        "| feature | perm. imp. (95% CI) | rank | $\\Delta$acc (95% CI) | $\\Delta$FPR | failed | decision |",
        "|---|---|---:|---|---:|---|---|",
    ]
    for _, row in frame.iterrows():
        failed = []
        if not row["c1_univariate"]:
            failed.append("C1")
        if not row["c2_importance"]:
            failed.append("C2")
        if not row["c3_ablation"]:
            failed.append("C3")
        if not row["c4_not_safety"]:
            failed.append("C4")
        failed_txt = ", ".join(failed) if failed else "none (all hold)"
        multi.append(
            "| `{feature}` | {imp:+.4f} [{lo:+.4f}, {hi:+.4f}] | {rank}/22 | "
            "{da:+.2f}% [{dlo:+.2f}, {dhi:+.2f}] | {df:+.2f}% | {failed} | "
            "**{decision}** |".format(
                feature=row["feature"], imp=row["perm_importance_mean"],
                lo=row["perm_ci_lo"], hi=row["perm_ci_hi"],
                rank=int(row["perm_rank"]),
                da=100 * row["ablation_delta_accuracy"],
                dlo=100 * row["ablation_delta_accuracy_ci_lo"],
                dhi=100 * row["ablation_delta_accuracy_ci_hi"],
                df=100 * row["ablation_delta_fpr"],
                failed=failed_txt, decision=row["decision"],
            )
        )
    (OUT / "drop_multivariate.md").write_text(
        "\n".join(multi) + "\n", encoding="utf-8"
    )

    tex = [
        "\\begin{table*}[t]",
        "\\centering",
        "\\caption{Four-condition feature-drop evidence on CSIC 2010.",
        "C1: BH-adjusted $p\\ge0.05$ and $|\\delta|<0.10$, or zero in $\\ge99\\%$",
        "of both classes. C2: permutation importance in the bottom quartile with a",
        "95\\% CI containing zero. C3: leave-one-out ablation within 0.2~pp accuracy",
        "and 0.10~pp FPR. C4: not a safety-retained policy feature.",
        "A feature is dropped only when all four columns are `Y'.",
        "\\texttt{token\\_count} is retained even though its permutation CI is",
        "entirely negative (C2 = N): the frozen rule requires a CI containing zero,",
        "so a strictly harmful estimate does not satisfy C2. This conservative",
        "limitation is discussed in the text.}",
        "\\label{tab:drop-evidence}",
        "\\scriptsize",
        "\\begin{tabular}{lrrrrrccccr}",
        "\\toprule",
        "Feature & $p_{\\mathrm{BH}}$ & Cliff $\\delta$ & Perm. imp. & "
        "$\\Delta$Acc & $\\Delta$FPR & C1 & C2 & C3 & C4 & Decision \\\\",
        "\\midrule",
    ]
    for _, row in frame.iterrows():
        tex.append(
            "{feat} & {p} & {d:+.3f} & {imp:+.5f} & {da:+.2f}\\% & "
            "{df:+.2f}\\% & {c1} & {c2} & {c3} & {c4} & {dec} \\\\".format(
                feat=row["feature"].replace("_", "\\_"), p=fmt_p_tex(row["p_bh"]),
                d=row["cliffs_delta"], imp=row["perm_importance_mean"],
                da=100 * row["ablation_delta_accuracy"],
                df=100 * row["ablation_delta_fpr"],
                c1="Y" if row["c1_univariate"] else "N",
                c2="Y" if row["c2_importance"] else "N",
                c3="Y" if row["c3_ablation"] else "N",
                c4="Y" if row["c4_not_safety"] else "N",
                dec=row["decision"],
            )
        )
    tex += ["\\bottomrule", "\\end{tabular}", "\\end{table*}", ""]
    (OUT / "drop_evidence.tex").write_text("\n".join(tex), encoding="utf-8")
    print(f"wrote {OUT / 'drop_evidence.md'} and .tex")


if __name__ == "__main__":
    main()
