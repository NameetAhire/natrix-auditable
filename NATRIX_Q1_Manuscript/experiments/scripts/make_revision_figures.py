"""Generate the revision figures from the generated tables.

The tables under ``tables/`` are themselves generated from measured result
files, so reading them here keeps every plotted value identical to the value
printed in the manuscript.  No number is typed by hand.

Outputs: figures/revision_*.pdf and .png (300 dpi).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

FIG = C.FIGURES
FIG.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 9,
    "axes.labelsize": 9,
    "axes.titlesize": 10,
    "legend.fontsize": 8,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "figure.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02,
})

COLORS = {
    "natrix": "#0072B2",
    "lex_full": "#D55E00",
    "lex_payload": "#009E73",
    "generic": "#CC79A7",
    "grey": "#666666",
    "v3": "#0072B2",
    "v3d": "#D55E00",
}


def save(fig, name):
    fig.savefig(FIG / f"{name}.pdf")
    fig.savefig(FIG / f"{name}.png")
    plt.close(fig)
    print(f"wrote figures/{name}.pdf/.png")


def md_tables(path: Path) -> list[list[dict[str, str]]]:
    """Return every pipe table in a Markdown file as a list of row dicts."""
    tables: list[list[dict[str, str]]] = []
    rows: list[list[str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            rows.append(cells)
        elif rows:
            tables.append(rows)
            rows = []
    if rows:
        tables.append(rows)

    parsed = []
    for block in tables:
        if len(block) < 3:
            continue
        header = block[0]
        body = [
            row for row in block[2:]
            if not all(set(cell) <= {"-", ":", " "} for cell in row)
        ]
        parsed.append([dict(zip(header, row)) for row in body])
    return parsed


def number(value: str) -> float:
    return float(value.replace(",", "").replace("%", "").strip())


def fig_protocol_sensitivity():
    tables = md_tables(C.TABLES / "detector_comparison.md")
    if len(tables) < 2:
        print("skip protocol sensitivity: table not ready")
        return
    p1 = pd.DataFrame(tables[0])
    p2 = pd.DataFrame(tables[1])
    p1["protocol"] = "P1"
    p2["protocol"] = "P2"
    frame = pd.concat([p1, p2], ignore_index=True)
    frame["detector"] = frame["detector"].replace(
        {"NATRIX (20k)": "NATRIX"}
    )
    keep = ["NATRIX", "Lex-full", "Lex-payload"]
    frame = frame[frame["detector"].isin(keep)]

    corpora = ["CSIC", "ECML", "SR-BH"]
    groups = [(corpus, protocol) for corpus in corpora for protocol in ("P1", "P2")]
    colors = {
        "NATRIX": COLORS["natrix"],
        "Lex-full": COLORS["lex_full"],
        "Lex-payload": COLORS["lex_payload"],
    }

    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.0))
    width = 0.26
    x = np.arange(len(groups))
    for axis, metric, label, upper in (
        (axes[0], "accuracy", "Accuracy (%)", 100),
        (axes[1], "FPR", "False positive rate (%)", 25),
    ):
        for offset, detector in zip((-width, 0.0, width), keep):
            values = []
            for corpus, protocol in groups:
                row = frame[
                    (frame["corpus"] == corpus)
                    & (frame["protocol"] == protocol)
                    & (frame["detector"] == detector)
                ]
                values.append(number(row.iloc[0][metric]) if len(row) else np.nan)
            axis.bar(
                x + offset, values, width, label=detector,
                color=colors[detector], edgecolor="white", linewidth=0.4,
            )
        axis.set_xticks(x)
        axis.set_xticklabels(
            [f"{corpus}\n{protocol}" for corpus, protocol in groups],
            fontsize=7.5,
        )
        axis.set_ylabel(label)
        axis.set_ylim(0, upper)
        axis.grid(axis="y", linewidth=0.3, alpha=0.4)
        axis.set_axisbelow(True)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles, labels, loc="lower center", ncol=3, frameon=False,
        bbox_to_anchor=(0.5, -0.01),
    )
    axes[0].set_title("(a) Accuracy at matched FPR policy")
    axes[1].set_title("(b) Realised false positive rate")
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    save(fig, "revision_protocol_sensitivity")


def fig_view_ablation():
    tables = md_tables(C.TABLES / "view_ablation.md")
    if not tables:
        print("skip view ablation: table not ready")
        return
    frame = pd.DataFrame(tables[0])
    frame["group"] = frame["corpus"] + " " + frame["protocol"]
    groups = ["SR-BH 20k P1", "SR-BH 20k P2", "CSIC P2"]
    views = ["full", "no_path", "path_only", "query_only", "body_only"]
    colors = ["#0072B2", "#56B4E9", "#009E73", "#E69F00", "#CC79A7"]

    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.1))
    width = 0.16
    x = np.arange(len(groups))
    for axis, metric, label in (
        (axes[0], "accuracy", "Accuracy (%)"),
        (axes[1], "recall", "Recall (%)"),
    ):
        for offset, view, color in zip(
            np.linspace(-2 * width, 2 * width, len(views)), views, colors
        ):
            values = []
            for group in groups:
                row = frame[(frame["group"] == group) & (frame["view"] == view)]
                values.append(number(row.iloc[0][metric]) if len(row) else np.nan)
            axis.bar(
                x + offset, values, width, label=view, color=color,
                edgecolor="white", linewidth=0.4,
            )
        axis.set_xticks(x)
        axis.set_xticklabels(groups, fontsize=7.5)
        axis.set_ylabel(label)
        axis.set_ylim(0, 100)
        axis.grid(axis="y", linewidth=0.3, alpha=0.4)
        axis.set_axisbelow(True)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles, labels, loc="lower center", ncol=5, frameon=False,
        bbox_to_anchor=(0.5, -0.01), fontsize=7.5,
    )
    axes[0].set_title("(a) Accuracy by request view")
    axes[1].set_title("(b) Recall by request view")
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    save(fig, "revision_view_ablation")


def fig_srbh_learning():
    path = C.RESULTS / "corpora" / "srbh_sample_gap.json"
    if not path.exists():
        print("skip learning curve: missing", path)
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data["rows"]
    nested = sorted(
        [row for row in rows if row["subset"].startswith("nested")],
        key=lambda row: row["n"],
    )
    full = next(row for row in rows if row["subset"] == "full")
    sample = next(row for row in rows if row["subset"] == "sample20k")

    sizes = [row["n"] for row in nested] + [full["n"]]
    accuracy = [100 * row["accuracy"] for row in nested] + [100 * full["accuracy"]]
    recall = [100 * row["recall"] for row in nested] + [100 * full["recall"]]

    fig, ax = plt.subplots(figsize=(3.6, 2.7))
    ax.plot(sizes, accuracy, marker="o", markersize=3.5, linewidth=1.2,
            color=COLORS["natrix"], label="Accuracy")
    ax.plot(sizes, recall, marker="s", markersize=3.5, linewidth=1.2,
            color=COLORS["lex_full"], linestyle="--", label="Recall")
    ax.scatter(
        [sample["n"]], [100 * sample["accuracy"]], marker="o", s=34,
        facecolors="none", edgecolors=COLORS["natrix"], linewidths=0.9,
        label="Shared 20k sample",
    )
    ax.set_xscale("log")
    ax.set_xticks([10_000, 20_000, 50_000, 100_000, 200_000, 422_054])
    ax.set_xticklabels(["10k", "20k", "50k", "100k", "200k", "full"])
    ax.set_xlabel("Training/test population (requests)")
    ax.set_ylabel("Percent")
    ax.set_ylim(80, 100)
    ax.grid(linewidth=0.3, alpha=0.4)
    ax.legend(frameon=False, loc="lower right", fontsize=7)
    ax.set_title("SR-BH scale sensitivity (P1)")
    fig.tight_layout()
    save(fig, "revision_srbh_learning")


def fig_crs_paranoia():
    tables = md_tables(C.TABLES / "crs_paranoia.md")
    if not tables:
        print("skip CRS paranoia: table not ready")
        return
    frame = pd.DataFrame(tables[0])
    if len(frame) < 3:
        print("skip CRS paranoia: need PL1-PL3")
        return
    levels = frame["paranoia level"].tolist()
    x = np.arange(len(levels))

    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.9))
    width = 0.36
    axes[0].bar(x - width / 2, [number(v) for v in frame["accuracy"]],
                width, color=COLORS["natrix"], label="Accuracy")
    axes[0].bar(x + width / 2, [number(v) for v in frame["recall"]],
                width, color=COLORS["lex_full"], label="Recall")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(levels)
    axes[0].set_ylabel("Percent")
    axes[0].set_ylim(0, 100)
    axes[0].legend(frameon=False)
    axes[0].set_title("(a) Decision quality")
    axes[0].grid(axis="y", linewidth=0.3, alpha=0.4)
    axes[0].set_axisbelow(True)

    axes[1].bar(x, [number(v) for v in frame["FPR"]], width * 1.4,
                color=COLORS["grey"])
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(levels)
    axes[1].set_ylabel("False positive rate (%)")
    axes[1].set_title("(b) False positive cost")
    axes[1].grid(axis="y", linewidth=0.3, alpha=0.4)
    axes[1].set_axisbelow(True)
    for index, value in enumerate(number(v) for v in frame["FPR"]):
        axes[1].text(index, value + 0.8, f"{value:.2f}", ha="center", fontsize=7.5)
    fig.tight_layout()
    save(fig, "revision_crs_paranoia")


def fig_dilution():
    tables = md_tables(C.TABLES / "dilution_fix.md")
    if len(tables) < 2:
        print("skip dilution: table not ready")
        return
    bounded = pd.DataFrame(tables[0])
    targeted = pd.DataFrame(tables[1])
    contracts = bounded["contract"].tolist()

    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.9))
    width = 0.34
    x = np.arange(len(contracts))
    for axis, frame, clean_col, mutated_col, title in (
        (axes[0], bounded, "clean recall", "mutated recall",
         "(a) Bounded mutation suite"),
        (axes[1], targeted, "original recall", "mutated recall",
         "(b) Targeted dilution subset"),
    ):
        axis.bar(x - width / 2, [number(v) for v in frame[clean_col]],
                 width, color=COLORS["natrix"], label="Before mutation")
        axis.bar(x + width / 2, [number(v) for v in frame[mutated_col]],
                 width, color=COLORS["lex_full"], label="After mutation")
        axis.set_xticks(x)
        axis.set_xticklabels(contracts)
        axis.set_ylabel("Recall (%)")
        axis.set_ylim(0, 100)
        axis.set_title(title)
        axis.grid(axis="y", linewidth=0.3, alpha=0.4)
        axis.set_axisbelow(True)
        for index, (before, after) in enumerate(zip(
            (number(v) for v in frame[clean_col]),
            (number(v) for v in frame[mutated_col]),
        )):
            axis.text(index, max(before, after) + 2.0, f"{after - before:+.1f} pp",
                      ha="center", fontsize=7.5)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles, labels, loc="lower center", ncol=2, frameon=False,
        bbox_to_anchor=(0.5, -0.01),
    )
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    save(fig, "revision_dilution")


def main():
    fig_protocol_sensitivity()
    fig_view_ablation()
    fig_srbh_learning()
    fig_crs_paranoia()
    fig_dilution()


if __name__ == "__main__":
    main()
