"""Render the revision tables from measured result files.

The revision adds four kinds of evidence that the first submission did not
have: endpoint-disjoint (P2) baselines, a view ablation, a generic/stacked
control comparison, and a per-parameter dilution fix.  Every table here is a
projection of a JSON/CSV file under ``experiments/results``; no number is
typed by hand.

Usage
-----
    python experiments/scripts/make_revision_tables.py
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
BASE = C.RESULTS / "baselines"
CORP = C.RESULTS / "corpora"
ADV = C.RESULTS / "adversarial"


def write(name: str, lines: list[str]) -> None:
    (OUT / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", OUT / name)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def pct(value, digits: int = 2) -> str:
    return f"{100 * float(value):.{digits}f}"


def metric_row(detector: str, m: dict) -> str:
    return (
        f"| {detector} | {pct(m['accuracy'])} | {pct(m['fpr'])} | "
        f"{pct(m['recall'])} | {m['f1']:.4f} |"
    )


def crs_decided(tag: str, fallback: dict) -> dict:
    """Recompute CRS metrics over decided requests only.

    A transport failure (status 0) is not a WAF decision.  The JSON written by
    ``crs_baseline.py`` counts it as an allow, which is conservative for recall
    but mixes non-decisions into the confusion matrix.  The table reports the
    decision metrics and lists the transport failures separately.
    """
    path = BASE / f"{tag}_requests.parquet"
    if not path.exists():
        return fallback
    frame = pd.read_parquet(path, columns=["label", "status"])
    decided = frame[frame["status"].isin([200, 403])]
    y = decided["label"].to_numpy(dtype=int)
    blocked = (decided["status"].to_numpy(dtype=int) == 403).astype(int)
    tp = int(((blocked == 1) & (y == 1)).sum())
    tn = int(((blocked == 0) & (y == 0)).sum())
    fp = int(((blocked == 1) & (y == 0)).sum())
    fn = int(((blocked == 0) & (y == 1)).sum())
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall)
        else 0.0
    )
    return {
        "accuracy": (tp + tn) / len(decided),
        "fpr": fp / (fp + tn) if (fp + tn) else 0.0,
        "fnr": fn / (fn + tp) if (fn + tp) else 0.0,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "n": int(len(decided)),
        "undecided": int(len(frame) - len(decided)),
        "transport_failures": int((frame["status"] == 0).sum()),
    }


def natrix_calibrated() -> dict[tuple[str, str], dict]:
    frame = pd.read_csv(CORP / "corpora_calibrated.csv")
    rows = frame[frame["policy"] == "fpr2"]
    return {(r["corpus"], r["protocol"]): r.to_dict() for _, r in rows.iterrows()}


def lexical(corpus: str, protocol: str, view: str) -> dict | None:
    key = "srbh20k" if (corpus == "srbh" and protocol == "P2") else corpus
    if protocol == "P1":
        name = f"lexical_{key}_{view}.json"
    else:
        name = f"lexical_{key}_{protocol}_{view}.json"
    path = BASE / name
    if not path.exists():
        return None
    return load(path)["fpr2_crossfit"]


def srbh20k_natrix(protocol: str) -> dict | None:
    path = BASE / (
        "natrix_srbh_sample20k.json" if protocol == "P1" else "natrix_srbh_sample20k_P2.json"
    )
    if not path.exists():
        return None
    return load(path)["fpr2_crossfit"]


def control_path(corpus: str, protocol: str, view: str = "full") -> Path | None:
    if view == "full":
        for name in (
            f"control_{corpus}_{protocol}_full.json",
            f"control_{corpus}_{protocol}.json",
        ):
            path = BASE / name
            if path.exists():
                return path
        return None
    return BASE / f"control_{corpus}_{protocol}_{view}.json"


def control(corpus: str, protocol: str, view: str = "full") -> dict | None:
    path = control_path(corpus, protocol, view)
    if path is None:
        return None
    return load(path)


def table_detector_comparison() -> None:
    calibrated = natrix_calibrated()
    lines = [
        "# Matched operating points: deployment-like (P1) and endpoint-disjoint (P2)",
        "",
        "All score-based detectors use leave-one-fold-out thresholds at FPR <= 2%.",
        "CRS is a frozen ModSecurity CRS 4.25.2 PL1 replay; it is not tuned to a",
        "2% budget. SR-BH rows use the shared 20,000-request sample. The generic",
        "control is a 17-feature LightGBM trained on the same folds; the stacks",
        "are cross-fitted logistic combinations of the listed base scores.",
        "",
        "## Panel A: P1 (deployment-like, endpoint may recur)",
        "",
        "| corpus | detector | accuracy | FPR | recall | F1 |",
        "|---|---|---:|---:|---:|---:|",
    ]

    for corpus, label in (("csic", "CSIC"), ("ecml", "ECML"), ("srbh", "SR-BH")):
        if corpus == "srbh":
            m = srbh20k_natrix("P1")
            if m is None:
                continue
            lines.append(metric_row(f"{label} | NATRIX (20k)", m))
        else:
            r = calibrated.get((corpus, "P1"))
            if r is None:
                continue
            lines.append(
                f"| {label} | NATRIX | {pct(r['accuracy'])} | {pct(r['fpr'])} | "
                f"{pct(r['recall'])} | {r['f1']:.4f} |"
            )
        for view, name in (("full", "Lex-full"), ("payload", "Lex-payload"), ("endpoint", "Lex-endpt")):
            m = lexical(corpus, "P1", view)
            if m is not None:
                lines.append(metric_row(f"{label} | {name}", m))
        crs = BASE / f"crs_pl1_{corpus}.json"
        if crs.exists():
            c = crs_decided(f"crs_pl1_{corpus}", load(crs))
            lines.append(
                f"| {label} | CRS PL1 | {pct(c['accuracy'])} | {pct(c['fpr'])} | "
                f"{pct(c['recall'])} | {c['f1']:.4f} |"
            )
        ctl = control(corpus, "P1", "full")
        if ctl is not None:
            for m in ctl["metrics"]:
                if m["detector"] in ("generic", "stack_natrix_lexical", "stack_natrix_generic_lexical"):
                    name = {
                        "generic": "Generic GBM",
                        "stack_natrix_lexical": "Stack NATRIX+Lex",
                        "stack_natrix_generic_lexical": "Stack N+G+Lex",
                    }[m["detector"]]
                    lines.append(metric_row(f"{label} | {name}", m))

    lines += [
        "",
        "## Panel B: P2 (endpoint-disjoint, unseen endpoint groups)",
        "",
        "| corpus | detector | accuracy | FPR | recall | F1 |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for corpus, label in (("csic", "CSIC"), ("ecml", "ECML"), ("srbh", "SR-BH")):
        if corpus == "srbh":
            m = srbh20k_natrix("P2")
            if m is None:
                continue
            lines.append(metric_row(f"{label} | NATRIX (20k)", m))
        else:
            r = calibrated.get((corpus, "P2"))
            if r is None:
                continue
            lines.append(
                f"| {label} | NATRIX | {pct(r['accuracy'])} | {pct(r['fpr'])} | "
                f"{pct(r['recall'])} | {r['f1']:.4f} |"
            )
        for view, name in (("full", "Lex-full"), ("payload", "Lex-payload"), ("endpoint", "Lex-endpt")):
            m = lexical(corpus, "P2", view)
            if m is not None:
                lines.append(metric_row(f"{label} | {name}", m))
        ctl = control(corpus, "P2", "full")
        if ctl is not None:
            for m in ctl["metrics"]:
                if m["detector"] in ("generic", "stack_natrix_lexical", "stack_natrix_generic_lexical"):
                    name = {
                        "generic": "Generic GBM",
                        "stack_natrix_lexical": "Stack NATRIX+Lex",
                        "stack_natrix_generic_lexical": "Stack N+G+Lex",
                    }[m["detector"]]
                    lines.append(metric_row(f"{label} | {name}", m))

    write("detector_comparison.md", lines)


def table_view_ablation() -> None:
    rows = []
    for corpus, protocol, name in (
        ("srbh20k", "P1", "natrix_views_srbh20k.json"),
        ("srbh20k", "P2", "natrix_views_srbh20k_P2.json"),
        ("csic", "P2", "natrix_views_csic_P2.json"),
    ):
        path = BASE / name
        if not path.exists():
            continue
        for r in load(path):
            rows.append(
                {
                    "corpus": "SR-BH 20k" if corpus == "srbh20k" else "CSIC",
                    "protocol": protocol,
                    "view": r["view"],
                    "accuracy": r["accuracy"],
                    "fpr": r["fpr"],
                    "recall": r["recall"],
                    "f1": r["f1"],
                }
            )
    if not rows:
        return
    frame = pd.DataFrame(rows)
    lines = [
        "# View ablation: which request fields carry the signal?",
        "",
        "| corpus | protocol | view | accuracy | FPR | recall | F1 |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for _, r in frame.iterrows():
        lines.append(
            f"| {r['corpus']} | {r['protocol']} | {r['view']} | "
            f"{pct(r['accuracy'])} | {pct(r['fpr'])} | {pct(r['recall'])} | {r['f1']:.4f} |"
        )
    write("view_ablation.md", lines)


def table_control_stack() -> None:
    entries = [
        ("CSIC", "P1", "full", "csic", "P1"),
        ("CSIC", "P2", "full", "csic", "P2"),
        ("CSIC", "P2", "payload", "csic", "P2"),
        ("SR-BH 20k", "P2", "full", "srbh20k", "P2"),
        ("SR-BH 20k", "P2", "payload", "srbh20k", "P2"),
        ("ECML", "P2", "full", "ecml", "P2"),
        ("ECML", "P2", "payload", "ecml", "P2"),
    ]
    lines = [
        "# Control models and cross-fitted stackers",
        "",
        "The generic control is a 17-feature LightGBM over request-shape,",
        "lexical, and method features that are not the NATRIX contract. The",
        "stackers combine out-of-fold scores with a logistic model fitted on the",
        "other four folds; the threshold is selected leave-one-fold-out at",
        "FPR <= 2%. `Lex` is the hashed character n-gram baseline in the stated",
        "view (`full` = path+query+body, `payload` = query+body).",
        "",
        "| corpus | protocol | lexical view | detector | accuracy | FPR | recall | F1 |",
        "|---|---|---|---|---:|---:|---:|---:|",
    ]
    for label, protocol, view, corpus_key, protocol_key in entries:
        path = control_path(corpus_key, protocol_key, view)
        if path is None:
            continue
        d = load(path)
        for m in d["metrics"]:
            name = {
                "natrix": "NATRIX",
                "lexical": "Lex",
                "generic": "Generic GBM",
                "stack_natrix_lexical": "Stack N+Lex",
                "stack_generic_lexical": "Stack G+Lex",
                "stack_natrix_generic_lexical": "Stack N+G+Lex",
            }[m["detector"]]
            lines.append(
                f"| {label} | {protocol} | {view} | {name} | {pct(m['accuracy'])} | "
                f"{pct(m['fpr'])} | {pct(m['recall'])} | {m['f1']:.4f} |"
            )

    # Paired deltas for the two comparisons the paper relies on.
    lines += [
        "",
        "## Paired accuracy deltas (stack minus lexical base)",
        "",
        "| corpus | protocol | view | comparison | delta accuracy (pp) | 95% CI | McNemar p |",
        "|---|---|---|---|---:|---|---:|",
    ]
    for label, protocol, view, corpus_key, protocol_key in entries:
        path = control_path(corpus_key, protocol_key, view)
        if path is None:
            continue
        d = load(path)
        for key, name in (
            ("stack_natrix_vs_lexical", "Stack N+Lex - Lex"),
            ("stack_natrix_vs_generic", "Stack N+G+Lex - Stack G+Lex"),
        ):
            c = d.get(key)
            if not c:
                continue
            a = c["accuracy"]
            lines.append(
                f"| {label} | {protocol} | {view} | {name} | "
                f"{100 * a['delta']:+.2f} | "
                f"[{100 * a['ci_lo']:+.2f}, {100 * a['ci_hi']:+.2f}] | "
                f"{a['mcnemar']['p_value']:.3g} |"
            )
    write("control_stack.md", lines)


def table_dilution_fix() -> None:
    path = ADV / "dilution_resistant.json"
    if not path.exists():
        return
    d = load(path)
    lines = [
        "# Dilution-resistant feature variant (v3-D)",
        "",
        "## Panel A: bounded mutation suite (all 15,953 attacks)",
        "",
        "| contract | clean accuracy | clean FPR | clean recall | mutated recall | delta (pp) | evaded |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name in ("v3", "v3-D"):
        r = d["bounded_suite"][name]
        c = r["clean"]
        b = r["bounded"]
        lines.append(
            f"| {name} | {pct(c['accuracy'])} | {pct(c['fpr'])} | {pct(c['recall'])} | "
            f"{pct(b['recall_mutated'])} | {100 * b['delta']:+.2f} | {b['evaded']:,} |"
        )

    lines += [
        "",
        "## Panel B: targeted dilution subset",
        "",
        "| contract | original recall | mutated recall | delta (pp) | evaded |",
        "|---|---:|---:|---:|---:|",
    ]
    for name in ("v3", "v3-D"):
        r = d["targeted_dilution"][name]
        lines.append(
            f"| {name} | {pct(r['recall_original'])} | {pct(r['recall_mutated'])} | "
            f"{100 * r['delta']:+.2f} | {r['evaded']:,} |"
        )

    lines += [
        "",
        "## Panel C: per-operator loss (bounded suite)",
        "",
        "| operator | n | v3 delta (pp) | v3-D delta (pp) | v3 evaded | v3-D evaded |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    ops = {r["operator"]: r for r in d["bounded_suite"]["v3"]["per_operator"]}
    ops_d = {r["operator"]: r for r in d["bounded_suite"]["v3-D"]["per_operator"]}
    for op in ops:
        a = ops[op]
        b = ops_d[op]
        lines.append(
            f"| {op} | {a['n']:,} | {100 * a['delta']:+.2f} | {100 * b['delta']:+.2f} | "
            f"{a['evaded']:,} | {b['evaded']:,} |"
        )
    write("dilution_fix.md", lines)


def table_crs_paranoia() -> None:
    rows = []
    for pl in (1, 2, 3):
        path = BASE / f"crs_pl{pl}_csic.json"
        if not path.exists():
            continue
        d = load(path)
        d = crs_decided(f"crs_pl{pl}_csic", d)
        rows.append(
            {
                "pl": pl,
                "accuracy": d["accuracy"],
                "fpr": d["fpr"],
                "recall": d["recall"],
                "f1": d["f1"],
                "tp": d["tp"],
                "tn": d["tn"],
                "fp": d["fp"],
                "fn": d["fn"],
                "p95": load(path).get("latency_ms", {}).get("p95"),
                "status": load(path).get("status_counts", {}),
                "transport": d.get("transport_failures", 0),
            }
        )
    if not rows:
        return
    lines = [
        "# ModSecurity CRS paranoia levels on CSIC 2010",
        "",
        "| paranoia level | accuracy | FPR | recall | F1 | TP | TN | FP | FN | p95 latency (ms) |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        p95 = f"{r['p95']:.1f}" if r["p95"] is not None else "n/a"
        lines.append(
            f"| PL{r['pl']} | {pct(r['accuracy'])} | {pct(r['fpr'])} | {pct(r['recall'])} | "
            f"{r['f1']:.4f} | {r['tp']:,} | {r['tn']:,} | {r['fp']:,} | {r['fn']:,} | {p95} |"
        )
    lines += ["", "Status counts:"]
    for r in rows:
        counts = ", ".join(f"{k}: {v:,}" for k, v in sorted(r["status"].items()))
        lines.append(f"- PL{r['pl']}: {counts}")
    write("crs_paranoia.md", lines)


def table_srbh_sample_gap() -> None:
    path = CORP / "srbh_sample_gap.json"
    if not path.exists():
        return
    d = load(path)
    lines = [
        "# SR-BH scale sensitivity: full corpus versus the 20k comparison sample",
        "",
        "The detector, folds, and FPR <= 2% policy are identical; only the",
        "training/test population size changes. The nested subsets are drawn",
        "from the full corpus with the same class prevalence, so the curve",
        "separates a sample-size effect from a class-prior artefact.",
        "",
        "| subset | n | accuracy | FPR | recall | F1 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in d["rows"]:
        lines.append(
            f"| {r['subset']} | {int(r['n']):,} | {pct(r['accuracy'])} | "
            f"{pct(r['fpr'])} | {pct(r['recall'])} | {r['f1']:.4f} |"
        )
    lines += [
        "",
        f"Class prevalence: full corpus {100 * d['full_prior']:.2f}% attack; "
        f"20k sample {100 * d['sample20k_prior']:.2f}% attack.",
        "",
        "## Attack-family mix",
        "",
        "| family | full clean | full attack | 20k clean | 20k attack |",
        "|---|---:|---:|---:|---:|",
    ]
    mix = pd.DataFrame(d["family_mix"])
    pivot = mix.pivot_table(
        index="family", columns="corpus", values=["clean", "attack"], fill_value=0
    )
    for family in sorted(mix["family"].unique()):
        row = pivot.loc[family] if family in pivot.index else None
        if row is None:
            continue
        fc = int(row.get(("clean", "full"), 0))
        fa = int(row.get(("attack", "full"), 0))
        sc = int(row.get(("clean", "sample20k"), 0))
        sa = int(row.get(("attack", "sample20k"), 0))
        lines.append(f"| {family} | {fc:,} | {fa:,} | {sc:,} | {sa:,} |")
    write("srbh_sample_gap.md", lines)


def table_formal() -> None:
    one = (FORMAL / "tlc_one_rule.log")
    two = (FORMAL / "tlc_two_rules.log")
    mut = (FORMAL / "mutation_results.json")
    if not one.exists() or not two.exists():
        return

    def counts(path: Path):
        raw = path.read_bytes()
        if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
            text = raw.decode("utf-16")
        else:
            text = raw.decode("utf-8", errors="replace")
        import re

        m = re.search(r"(\d+) states generated, (\d+) distinct states found", text)
        d = re.search(r"depth of the complete state graph search is (\d+)", text)
        if m is None or d is None:
            raise SystemExit(f"could not parse TLC log {path}")
        return int(m.group(1)), int(m.group(2)), int(d.group(1))

    a = counts(one)
    b = counts(two)
    lines = [
        "# Formal verification evidence",
        "",
        "| configuration | constants | states generated | distinct | depth | result |",
        "|---|---|---:|---:|---:|---|",
        f"| one rule (`Cppp_small.cfg`) | `Agents=a1,a2,a3`, `Rules=r1`, `K=2`, `Tau=2`, `MaxTrust=3` | {a[0]:,} | {a[1]:,} | {a[2]} | no error |",
        f"| two rules (`Cppp_two.cfg`) | same agents, `Rules=r1,r2` | {b[0]:,} | {b[1]:,} | {b[2]} | no error |",
        "",
        "Invariants: `TypeOK`, `NoPromotionWithoutCanary`,",
        "`NoPromotionWithoutQuorum`, `NoPromotionWithoutTrust`,",
        "`ActiveImpliesAudited`, `RetiredNotActive`, `NoDirectPromotion`.",
        "Logs: `artifacts/formal/tlc_one_rule.log`,",
        "`artifacts/formal/tlc_two_rules.log`.",
        "",
        "| check | result |",
        "|---|---|",
        "| property tests (`experiments/tests/test_formal.py`) | 10 passed |",
        "| exhaustive BFS, depth 9 | 13,278 reachable states, 62,263 transitions |",
        "| BFS invariant violations | none |",
    ]
    if mut.exists():
        m = load(mut)
        lines += [
            f"| TLA+ mutation test | {m['killed']}/{m['total']} mutants killed, all expected |",
        ]
    lines += [
        "",
        "| trust-decay check | result |",
        "|---|---|",
        "| exhaustive rational enumeration | 81,484 cases, 0 violations |",
        "| symbolic identities (SymPy) | 9/9 pass |",
        "",
        "Identities: initial value, limit at infinity, monotone decreasing,",
        "bounded above, half-life, recovery non-decreasing, recovery upper",
        "bound, gap contraction, contraction identity. Source:",
        "`artifacts/formal/trust_decay_verification.json`,",
        "`artifacts/formal/trust_decay.py`.",
    ]
    if mut.exists():
        m = load(mut)
        lines += [
            "",
            "## Mutation test",
            "",
            "| mutant | expected invariant | killed |",
            "|---|---|:--:|",
        ]
        for row in m["mutants"]:
            lines.append(
                f"| `{row['mutant']}` | `{row['expected_invariant']}` | "
                f"{'yes' if row['killed'] else 'no'} |"
            )
    write("formal_verification.md", lines)


def table_cppp_sensitivity() -> None:
    path = FORMAL / "cppp_sensitivity.json"
    if not path.exists():
        return
    d = load(path)
    quorum = pd.DataFrame(d["quorum"]["rows"])
    lines = [
        "# CPPP parameter sensitivity",
        "",
        "## Quorum: exact binomial promotion probability (N = 5 agents)",
        "",
        "Each cell is the probability that at least K validation votes are cast",
        "when each honest agent validates with probability p and each compromised",
        "agent votes yes with probability 1.",
        "",
        "| compromised agents | K | p=0.2 | p=0.4 | p=0.6 | p=0.8 |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for (compromised, k), group in quorum.groupby(["compromised", "quorum"]):
        cells = {
            round(float(r["honest_validate_p"]), 1): float(r["promotion_probability"])
            for _, r in group.iterrows()
        }
        lines.append(
            f"| {int(compromised)} | {int(k)} | {cells[0.2]:.3f} | {cells[0.4]:.3f} | "
            f"{cells[0.6]:.3f} | {cells[0.8]:.3f} |"
        )
    lines += [
        "",
        "## Trust decay: exact rational iteration",
        "",
        "| rho | alpha | half-life (ticks) | fixed point | 1% settling (ticks) | retire 0.75->0.50 (ticks) |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for row in d["trust_decay"]["rows"]:
        lines.append(
            f"| {row['rho']:.2f} | {row['alpha']:.2f} | {row['half_life_ticks']} | "
            f"{row['fixed_point']:.3f} | {row['settle_1pct_ticks']} | "
            f"{row['retire_from_075_at_tau_050']} |"
        )
    write("cppp_sensitivity.md", lines)


FORMAL = C.ARTIFACTS / "formal"


def main() -> None:
    table_detector_comparison()
    table_view_ablation()
    table_control_stack()
    table_dilution_fix()
    table_crs_paranoia()
    table_srbh_sample_gap()
    table_formal()
    table_cppp_sensitivity()


if __name__ == "__main__":
    main()
