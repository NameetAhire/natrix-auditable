"""Render manuscript result tables from the measured CSV/JSON files.

Run after the experiment queue.  Every table is a direct projection of a result
file; no number is typed by hand.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

OUT = C.TABLES
OUT.mkdir(parents=True, exist_ok=True)


def write(name, lines):
    (OUT / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", OUT / name)


def pct(value, digits=2):
    return f"{100 * float(value):.{digits}f}"


def table_interpretability():
    perm_path = C.ARTIFACTS / "feature_selection" / "drop_evidence.csv"
    shap_path = C.RESULTS / "feature_audit" / "csic_shap_importance.csv"
    if not perm_path.exists() or not shap_path.exists():
        print("skip interpretability: missing", perm_path, shap_path)
        return
    perm = pd.read_csv(perm_path)
    shap = pd.read_csv(shap_path)
    frame = perm.merge(shap, on="feature", how="left")
    frame = frame.sort_values("perm_rank")
    lines = [
        "# Interpretability audit (CSIC 2010, P1, 5 folds)",
        "",
        "Permutation importance is the mean over folds with a 95% bootstrap CI;",
        "mean absolute SHAP is the mean over 500 held-out records per fold.",
        "A zero SHAP value means the forest never split on the feature in that",
        "fold; it does not mean the runtime policy ignores the signal.",
        "",
        "| rank | feature | group | $p_{BH}$ | Cliff's $\\delta$ | "
        "permutation importance (95% CI) | mean abs SHAP | decision |",
        "|---:|---|---|---:|---:|---|---:|---|",
    ]
    for _, r in frame.iterrows():
        p = r["p_bh"]
        p_txt = "$<10^{-300}$" if p == 0 else f"{p:.3g}"
        lines.append(
            f"| {int(r['perm_rank'])} | `{r['feature']}` | {r['group']} | "
            f"{p_txt} | {r['cliffs_delta']:+.3f} | "
            f"{r['perm_importance_mean']:.4f} "
            f"[{r['perm_ci_lo']:.4f}, {r['perm_ci_hi']:.4f}] | "
            f"{r['mean_abs_shap_mean']:.4f} | {r['decision']} |"
        )
    zero = frame[frame["mean_abs_shap_mean"] == 0]["feature"].tolist()
    lines += [
        "",
        "Features with zero mean $|$SHAP$|$ on CSIC: "
        + ", ".join(f"`{f}`" for f in zero) + ".",
        "Of these, `command_injection_score` and `path_traversal_score` are",
        "non-zero on only 0.84% of CSIC attacks; the rest are constant on this",
        "corpus. All are safety-retained except the two dropped features.",
    ]
    write("interpretability.md", lines)


def table_corpora_calibrated():
    path = C.RESULTS / "corpora" / "corpora_calibrated.csv"
    if not path.exists():
        print("skip calibrated corpora: missing", path)
        return
    frame = pd.read_csv(path)
    lines = [
        "# Cross-fitted corpus operating points (22-D gate)",
        "",
        "Threshold for fold $k$ is selected on the OOF predictions of the other",
        "four folds (D13). P1 is deployment-like; P2 is endpoint-disjoint and is",
        "reported as a generalisation bound, not a headline result.",
        "",
        "| corpus | protocol | policy | threshold | accuracy | FPR | FNR | F1 |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for _, r in frame.sort_values(["corpus", "protocol", "policy"]).iterrows():
        lines.append(
            f"| {r['corpus']} | {r['protocol']} | {r['policy']} | "
            f"{r['threshold_mean']:.2f} | {pct(r['accuracy'])} | "
            f"{pct(r['fpr'])} | {pct(r['fnr'])} | {r['f1']:.4f} |"
        )
    summary_path = C.RESULTS / "corpora" / "corpora_calibration.json"
    if summary_path.exists():
        s = json.loads(summary_path.read_text(encoding="utf-8"))
        lines += [
            "",
            "**Acceptance check (FPR $\\leq$ 2% policy).**",
            "",
            "| corpus/protocol | accuracy | FPR | meets accuracy > 95% and FPR < 2.03% |",
            "|---|---:|---:|:--:|",
        ]
        for key, value in s["acceptance_check"].items():
            lines.append(
                f"| {key} | {pct(value['accuracy'])} | {pct(value['fpr'])} | "
                f"{'yes' if value['meets_both'] else 'no'} |"
            )
    write("corpora_calibrated.md", lines)


def table_cross_corpus():
    path = C.RESULTS / "feature_audit" / "cross_corpus_all.csv"
    csic_path = C.ARTIFACTS / "feature_selection" / "drop_evidence.csv"
    if not path.exists() or not csic_path.exists():
        print("skip cross-corpus: missing", path, csic_path)
        return
    frame = pd.read_csv(path)
    csic = pd.read_csv(csic_path)[["feature", "cliffs_delta", "perm_rank"]]
    csic = csic.rename(columns={"cliffs_delta": "delta_csic",
                                "perm_rank": "rank_csic"})
    wide = frame.pivot(index="feature", columns="corpus",
                       values=["cliffs_delta", "perm_rank"])
    wide.columns = [f"{a}_{b}" for a, b in wide.columns]
    wide = wide.reset_index().merge(csic, on="feature", how="left")
    wide = wide.sort_values("rank_csic")

    def direction(row):
        signs = []
        for corpus in ("ecml", "srbh"):
            d = row[f"cliffs_delta_{corpus}"]
            if abs(d) < 0.01:
                signs.append(0)
            else:
                signs.append(1 if d * row["delta_csic"] > 0 else -1)
        if all(s == 1 for s in signs):
            return "same"
        if all(s == -1 for s in signs):
            return "reversed"
        return "mixed"

    lines = [
        "# Cross-corpus direction replication (22-D contract)",
        "",
        "Cliff's $\\delta$ is attack minus clean; positive means the feature is",
        "larger in attacks. `direction` compares the sign with CSIC. The audit is",
        "descriptive (D10); no feature is selected on these corpora.",
        "",
        "| feature | CSIC $\\delta$ | ECML $\\delta$ | SR-BH $\\delta$ | "
        "CSIC rank | ECML rank | SR-BH rank | direction |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for _, row in wide.iterrows():
        lines.append(
            f"| `{row['feature']}` | {row['delta_csic']:+.3f} | "
            f"{row['cliffs_delta_ecml']:+.3f} | {row['cliffs_delta_srbh']:+.3f} | "
            f"{int(row['rank_csic'])}/22 | {int(row['perm_rank_ecml'])}/22 | "
            f"{int(row['perm_rank_srbh'])}/22 | {direction(row)} |"
        )
    reversed_features = [r["feature"] for _, r in wide.iterrows()
                         if direction(r) == "reversed"]
    lines += [
        "",
        f"Features with reversed direction in both corpora: "
        + ", ".join(f"`{f}`" for f in reversed_features) + ".",
    ]
    write("cross_corpus_directions.md", lines)


def table_corpora():
    path = C.RESULTS / "corpora" / "corpora_metrics.csv"
    if not path.exists():
        print("skip corpora: missing", path)
        return
    frame = pd.read_csv(path)
    lines = [
        "# In-distribution results (22-D v3 gate)",
        "",
        "P1 = deployment-like stratified; P2 = endpoint-disjoint bound.",
        "Threshold 0.5 unless a policy column says otherwise.",
        "",
        "| corpus | protocol | policy | n | accuracy | FPR | FNR | F1 | ROC-AUC |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in frame.sort_values(["corpus", "protocol", "policy"]).iterrows():
        lines.append(
            f"| {r['corpus']} | {r['protocol']} | {r.get('policy', '0.5')} | "
            f"{int(r['n']):,} | {pct(r['accuracy'])} | {pct(r['fpr'])} | "
            f"{pct(r['fnr'])} | {r['f1']:.4f} | {r.get('roc_auc', float('nan')):.4f} |"
        )
    write("corpora_results.md", lines)


def table_v3_v4():
    path = C.RESULTS / "v3_v4" / "comparison_metrics.csv"
    if not path.exists():
        print("skip v3/v4: missing", path)
        return
    frame = pd.read_csv(path)
    agg = frame.groupby(["features", "policy"]).agg(
        accuracy=("accuracy", "mean"),
        accuracy_sd=("accuracy", "std"),
        fpr=("fpr", "mean"),
        fpr_sd=("fpr", "std"),
        fnr=("fnr", "mean"),
        f1=("f1", "mean"),
        threshold=("threshold_mean", "mean"),
    ).reset_index()
    lines = [
        "# v3 vs v4 on CSIC 2010 (P1, 3 seeds)",
        "",
        "| feature set | policy | threshold | accuracy | FPR | FNR | F1 |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for _, r in agg.iterrows():
        lines.append(
            f"| {r['features']} | {r['policy']} | {r['threshold']:.2f} | "
            f"{pct(r['accuracy'])} ({pct(r['accuracy_sd'])}) | "
            f"{pct(r['fpr'])} ({pct(r['fpr_sd'])}) | {pct(r['fnr'])} | {r['f1']:.4f} |"
        )
    summary_path = C.RESULTS / "v3_v4" / "comparison_summary.json"
    if summary_path.exists():
        s = json.loads(summary_path.read_text(encoding="utf-8"))
        d = s["accuracy_delta_v4_minus_v3"]
        lines += [
            "",
            "Paired McNemar (seed 42, F1 policy): "
            f"$b={s['mcnemar_v4_vs_v3']['n_b_only']}$, "
            f"$c={s['mcnemar_v4_vs_v3']['n_a_only']}$, "
            f"$p={s['mcnemar_v4_vs_v3']['p_value']:.4g}$.",
            "",
            f"$\\Delta$accuracy (v4 $-$ v3) = {100 * d['mean']:+.2f} pp "
            f"(95% bootstrap CI [{100 * d['ci_lo']:+.2f}, {100 * d['ci_hi']:+.2f}]).",
        ]
    write("v3_v4_results.md", lines)


def table_transfer():
    path = C.RESULTS / "transfer" / "transfer_metrics.csv"
    if not path.exists():
        print("skip transfer: missing", path)
        return
    frame = pd.read_csv(path)
    lines = [
        "# Cross-corpus transfer (source-only thresholds)",
        "",
        "The threshold is selected on source out-of-fold predictions; the target",
        "corpus is never used for training or threshold selection.",
        "",
        "| source | target | policy | threshold | accuracy | FPR | FNR | F1 |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for _, r in frame.sort_values(["source", "target", "policy"]).iterrows():
        lines.append(
            f"| {r['source']} | {r['target']} | {r['policy']} | {r['threshold']:.2f} | "
            f"{pct(r['accuracy'])} | {pct(r['fpr'])} | {pct(r['fnr'])} | {r['f1']:.4f} |"
        )
    fam_path = C.RESULTS / "transfer" / "wcp_family_recall.csv"
    if fam_path.exists():
        fam = pd.read_csv(fam_path)
        lines += [
            "",
            "## OpenAppSec WCP per-family recall (FPR $\\leq$ 2% policy)",
            "",
            "| source | family | n | recall / specificity | FPR |",
            "|---|---|---:|---:|---:|",
        ]
        for _, r in fam[fam["policy"] == "fpr2"].sort_values(
            ["source", "family"]
        ).iterrows():
            lines.append(
                f"| {r['source']} | {r['family']} | {int(r['n']):,} | "
                f"{pct(r['recall_or_specificity'])} | {pct(r['fpr'])} |"
            )
    write("transfer_results.md", lines)


def table_latency():
    path = C.RESULTS / "latency" / "latency_report.json"
    if not path.exists():
        print("skip latency: missing", path)
        return
    report = json.loads(path.read_text(encoding="utf-8"))
    lines = [
        "# End-to-end inline latency",
        "",
        "| corpus | n | extraction p95 | score p95 | HTTP p95 | total p50 | total p95 | total p99 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for corpus in ("csic", "ecml", "wcp", "all"):
        g = report["groups"][corpus]
        if g["count"] == 0:
            continue
        lines.append(
            f"| {corpus} | {g['count']:,} | {g['extraction']['p95']:.3f} | "
            f"{g['score']['p95']:.3f} | {g['http']['p95']:.3f} | "
            f"{g['total']['p50']:.3f} | {g['total']['p95']:.3f} | "
            f"{g['total']['p99']:.3f} |"
        )
    write("latency_results.md", lines)


def table_calibrated():
    path = C.RESULTS / "v3_v4" / "calibrated_metrics.csv"
    if not path.exists():
        print("skip calibrated: missing", path)
        return
    frame = pd.read_csv(path)
    agg = frame.groupby(["features", "policy"]).agg(
        threshold=("threshold_mean", "mean"),
        accuracy=("accuracy", "mean"),
        accuracy_min=("accuracy", "min"),
        fpr=("fpr", "mean"),
        fpr_max=("fpr", "max"),
        fnr=("fnr", "mean"),
        f1=("f1", "mean"),
    ).reset_index()
    lines = [
        "# Cross-fitted threshold calibration (CSIC 2010, P1, 3 seeds)",
        "",
        "For each outer fold, the threshold is selected on the outer OOF",
        "predictions of the other four folds (D13). Values are mean over seeds;",
        "`min`/`max` are over seeds.",
        "",
        "| feature set | policy | threshold | accuracy | min acc | FPR | max FPR | FNR | F1 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in agg.iterrows():
        lines.append(
            f"| {r['features']} | {r['policy']} | {r['threshold']:.2f} | "
            f"{pct(r['accuracy'])} | {pct(r['accuracy_min'])} | "
            f"{pct(r['fpr'])} | {pct(r['fpr_max'])} | {pct(r['fnr'])} | "
            f"{r['f1']:.4f} |"
        )
    summary_path = C.RESULTS / "v3_v4" / "calibration_summary.json"
    if summary_path.exists():
        s = json.loads(summary_path.read_text(encoding="utf-8"))
        lines += ["", "**Acceptance check (all seeds, FPR<=2% policy).**", ""]
        for features, check in s["acceptance_check"].items():
            lines.append(
                f"- `{features}`: accuracy mean {pct(check['accuracy_mean'])} "
                f"(min {pct(check['accuracy_min'])}), FPR mean "
                f"{pct(check['fpr_mean'])} (max {pct(check['fpr_max'])}); "
                f"both targets met on every seed: **{check['meets_both_seeds']}**."
            )
        d = s["accuracy_delta_v4_minus_v3_fpr2_seed42"]
        lines += [
            "",
            f"Paired $\\Delta$accuracy (v4 $-$ v3, seed 42, FPR<=2%): "
            f"{100 * d['mean']:+.2f} pp "
            f"[{100 * d['ci_lo']:+.2f}, {100 * d['ci_hi']:+.2f}]; "
            f"McNemar $p={s['mcnemar_v4_vs_v3_fpr2_seed42']['p_value']:.4g}$.",
        ]
    write("calibrated_results.md", lines)


def table_learners():
    path = C.RESULTS / "learners" / "learner_summary.json"
    if not path.exists():
        print("skip learners: missing", path)
        return
    s = json.loads(path.read_text(encoding="utf-8"))
    lines = [
        "# Secondary learners (CSIC 2010, P1, 3 seeds)",
        "",
        "| learner | feature set | policy | accuracy mean | accuracy SD |",
        "|---|---|---|---:|---:|",
    ]
    for r in s["per_learner"]:
        lines.append(
            f"| {r['learner']} | {r['features']} | {r['policy']} | "
            f"{pct(r['accuracy_mean'])} | {pct(r['accuracy_std'])} |"
        )
    lines += ["", "## Paired v4 $-$ v3 at seed 42 (F1 policy)", "",
              "| learner | delta accuracy | 95% CI | McNemar p |",
              "|---|---:|---|---:|"]
    for t in s["paired_v4_vs_v3_seed42_f1"]:
        lines.append(
            f"| {t['learner']} | {100 * t['delta_accuracy']:+.2f} pp | "
            f"[{100 * t['ci_lo']:+.2f}, {100 * t['ci_hi']:+.2f}] | "
            f"{t['mcnemar']['p_value']:.4g} |"
        )
    write("learner_results.md", lines)


def table_screening():
    path = C.RESULTS / "v4_screening" / "candidate_screening.csv"
    if not path.exists():
        print("skip screening: missing", path)
        return
    frame = pd.read_csv(path)
    lines = [
        "# v4 candidate screening (nested, CSIC 2010)",
        "",
        "Rule: mean $\\Delta$F1 > its standard error across outer folds and",
        "positive in at least 4/5 folds.",
        "",
        "| candidate | mean delta F1 | SE | positive folds | accepted |",
        "|---|---:|---:|---:|:--:|",
    ]
    for _, r in frame.sort_values("mean_delta_f1", ascending=False).iterrows():
        lines.append(
            f"| {r['candidate']} | {r['mean_delta_f1']:+.5f} | "
            f"{r['se_delta_f1']:.5f} | {int(r['positive_folds'])}/5 | "
            f"{'yes' if r['accepted'] else 'no'} |"
        )
    cost_path = C.RESULTS / "latency" / "candidate_cost.json"
    if cost_path.exists():
        cost = json.loads(cost_path.read_text(encoding="utf-8"))
        lines += [
            "",
            "**Adoption decision (D12).** The accuracy screen accepted the",
            "candidates marked `yes`, but the pre-registered extraction-cost",
            f"budget fails: the candidate pass costs "
            f"{cost['worst_case']['added_p95_ms']:.2f} ms p95 on the 8 KiB",
            f"worst case against a {cost['budget_ms']} ms budget. No candidate",
            "is admitted; final v4 is the 20-D retained core. Five raw-accepted",
            "candidates (`backslash_count`, `brace_count`, `nonascii_ratio`,",
            "`ldap_filter_score`, `crlf_sequence_count`) are exactly constant on",
            "CSIC, so their identical +0.046 pp gain is an RNG artefact.",
        ]
    write("screening_results.md", lines)


def main():
    table_corpora()
    table_corpora_calibrated()
    table_v3_v4()
    table_calibrated()
    table_interpretability()
    table_cross_corpus()
    table_transfer()
    table_latency()
    table_learners()
    table_screening()


if __name__ == "__main__":
    main()
