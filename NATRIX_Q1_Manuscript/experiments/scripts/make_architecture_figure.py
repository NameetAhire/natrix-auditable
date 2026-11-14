"""Draw the NATRIX agent mesh and the measured inline path.

The figure is a block diagram, not a data plot: every box corresponds to a
module that exists in the repository (see protocol/runtime_gap.md).  The
synchronous boxes are the ones timed by latency_bench.js; the asynchronous
boxes are drawn outside the shaded inline band so the latency claim is not
misread as covering them.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

FIG = C.FIGURES
FIG.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 8,
    "figure.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.03,
})

INLINE = "#DCE9F5"
ASYNC = "#F4E3D7"
EDGE = "#333333"


def box(ax, x, y, w, h, text, face, fontsize=7.2):
    patch = FancyBboxPatch(
        (x - w / 2, y - h / 2), w, h,
        boxstyle="round,pad=0.012,rounding_size=0.02",
        linewidth=0.8, edgecolor=EDGE, facecolor=face,
    )
    ax.add_patch(patch)
    ax.text(x, y, text, ha="center", va="center", fontsize=fontsize,
            linespacing=1.15)


def arrow(ax, start, end, linestyle="-", color=EDGE, lw=0.8):
    ax.add_patch(FancyArrowPatch(
        start, end, arrowstyle="-|>", mutation_scale=8,
        linewidth=lw, color=color, linestyle=linestyle,
        shrinkA=1, shrinkB=1,
    ))


def main() -> None:
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5.5)
    ax.axis("off")

    # Inline band.
    ax.add_patch(FancyBboxPatch(
        (0.15, 2.75), 9.7, 2.55,
        boxstyle="round,pad=0.01,rounding_size=0.03",
        linewidth=0.0, facecolor=INLINE, alpha=0.55, zorder=0,
    ))
    ax.text(0.30, 5.10, "Synchronous inline path (timed end-to-end)",
            fontsize=8.2, fontweight="bold", va="top")

    y = 3.95
    box(ax, 0.78, y, 1.05, 0.85, "HTTP\nrequest", "#FFFFFF")
    box(ax, 2.16, y, 1.55, 0.95, "Telemetry\nIngestion\n22-D extractor", INLINE)
    box(ax, 3.72, y, 1.25, 0.95, "Zero-Trust\nVerifier", INLINE)
    box(ax, 5.20, y, 1.25, 0.95, "Threat\nIntelligence", INLINE)
    box(ax, 6.83, y, 1.55, 0.95, "ML Engine\nONNX gate +\nthreat typing", INLINE)
    box(ax, 8.70, y, 1.45, 0.95, "Remediation\nOrchestrator", INLINE)

    for x0, x1 in [(1.31, 1.385), (2.935, 3.095), (4.345, 4.575),
                   (5.825, 6.055), (7.605, 7.975)]:
        arrow(ax, (x0, y), (x1, y))

    # Async band.
    ax.add_patch(FancyBboxPatch(
        (0.15, 0.15), 9.7, 1.90,
        boxstyle="round,pad=0.01,rounding_size=0.03",
        linewidth=0.0, facecolor=ASYNC, alpha=0.55, zorder=0,
    ))
    ax.text(5.00, 0.36, "Asynchronous / post-decision roles",
            fontsize=8.2, fontweight="bold", va="center", ha="center")
    async_boxes = [
        (1.30, "Risk Scoring\nAgent"),
        (3.20, "Adaptive\nMemory"),
        (5.30, "Policy Agent\n(CPPP)"),
        (7.60, "Containment\nAgent"),
    ]
    for x, label in async_boxes:
        box(ax, x, 1.28, 1.45, 0.80, label, ASYNC)

    # Bus from the orchestrator to the async roles.
    bus_y = 2.18
    ax.plot([8.70, 8.70, 1.30], [3.47, bus_y, bus_y],
            color="#555555", linewidth=0.7, linestyle="--", zorder=1)
    for x, _ in async_boxes:
        arrow(ax, (x, bus_y), (x, 1.70), linestyle="--", color="#555555", lw=0.7)

    ax.text(4.85, 2.48,
            "latency_bench.js times the shaded band end-to-end",
            ha="center", va="bottom", fontsize=7, color="#0072B2")

    # CPPP lifecycle annotation under the policy box.
    ax.text(5.30, 0.63,
            "observed $\\rightarrow$ canary $\\rightarrow$ promoted $\\rightarrow$ retired\n"
            "quorum $K$ + trust $\\tau$ + audit",
            ha="center", va="center", fontsize=6.6, color="#333333")

    fig.savefig(FIG / "architecture.pdf")
    fig.savefig(FIG / "architecture.png")
    plt.close(fig)
    print("wrote figures/architecture.pdf/.png")


if __name__ == "__main__":
    main()
