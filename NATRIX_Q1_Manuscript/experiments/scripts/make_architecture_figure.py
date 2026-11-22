"""Draw the NATRIX agent mesh and the measured inline path.

UML component notation: component icon in each box, an actor for the client,
and «interface» labels on the connectors that cross a boundary.  The topology
is the paper's, not the design mock-up: five inline roles in the shaded timed
band, four governance roles outside it, no Event Bus, no CPPP Validation and
no Federated Consensus blocks.  The canvas is 4.9 in wide, the width at which
the figure is included, so the type is not scaled down.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, Rectangle

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

FIG = C.FIGURES
FIG.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "DejaVu Sans"],
    "font.size": 6.4,
    "figure.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02,
})

INLINE = "#DCE9F5"
ASYNC = "#F4E3D7"
EDGE = "#222222"
MUTED = "#555555"

W, H = 4.9, 2.95


def component_icon(ax, x, y):
    """UML component icon: a rectangle with two tabs on its left edge."""
    ax.add_patch(Rectangle((x, y), 0.085, 0.055, linewidth=0.6,
                           edgecolor=EDGE, facecolor="white", zorder=4))
    for dy in (0.012, 0.033):
        ax.add_patch(Rectangle((x - 0.020, y + dy), 0.020, 0.010, linewidth=0.6,
                               edgecolor=EDGE, facecolor="white", zorder=4))


def component(ax, cx, cy, w, h, name, sub=None, name_dy=0.10, sub_dy=-0.20):
    ax.add_patch(Rectangle((cx - w / 2, cy - h / 2), w, h,
                           linewidth=0.8, edgecolor=EDGE, facecolor="white",
                           zorder=2))
    ax.text(cx, cy + name_dy, name, ha="center", va="center",
            fontsize=5.8, fontweight="bold", linespacing=1.15, zorder=3)
    if sub:
        ax.text(cx, cy + sub_dy, sub, ha="center", va="center",
                fontsize=5.4, color="#333333", linespacing=1.1, zorder=3)
    component_icon(ax, cx + w / 2 - 0.115, cy + h / 2 - 0.085)


def arrow(ax, start, end, linestyle="-", color=EDGE, lw=0.8):
    ax.add_patch(FancyArrowPatch(
        start, end, arrowstyle="-|>", mutation_scale=7,
        linewidth=lw, color=color, linestyle=linestyle,
        shrinkA=0, shrinkB=0, zorder=5,
    ))


def actor(ax, x, y):
    ax.add_patch(Circle((x, y + 0.20), 0.042, fill=False, linewidth=0.8,
                        edgecolor=EDGE, zorder=4))
    ax.plot([x, x], [y + 0.16, y - 0.06], color=EDGE, linewidth=0.8, zorder=4)
    ax.plot([x - 0.075, x + 0.075], [y + 0.10, y + 0.10],
            color=EDGE, linewidth=0.8, zorder=4)
    ax.plot([x - 0.065, x], [y - 0.19, y - 0.06], color=EDGE, linewidth=0.8,
            zorder=4)
    ax.plot([x + 0.065, x], [y - 0.19, y - 0.06], color=EDGE, linewidth=0.8,
            zorder=4)
    ax.text(x, y - 0.23, "Client", ha="center", va="top", fontsize=6.2,
            zorder=4)


def main() -> None:
    fig, ax = plt.subplots(figsize=(W, H))
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.set_aspect("equal")
    ax.axis("off")

    # Inline band: five roles, timed end-to-end.
    ax.add_patch(Rectangle((0.62, 1.45), 4.26, 1.48,
                           linewidth=0.0, facecolor=INLINE, zorder=0))
    ax.text(0.70, 2.85, "Synchronous inline path  {timed end-to-end}",
            fontsize=7.2, fontweight="bold", va="top", color="#111111")
    ax.text(0.70, 1.51,
            "latency_bench.js times this band end-to-end",
            fontsize=5.4, color="#0072B2", va="bottom")

    actor(ax, 0.20, 2.10)
    arrow(ax, (0.28, 2.10), (0.685, 2.10))
    ax.text(0.50, 2.24, "\u00abrequest\u00bb", ha="center", va="bottom",
            fontsize=5.4, style="italic", color=MUTED)

    y = 2.12
    bh = 0.78
    xs = [1.050, 1.900, 2.750, 3.600, 4.450]
    bws = [0.73, 0.73, 0.73, 0.73, 0.80]
    for i in range(len(xs) - 1):
        arrow(ax, (xs[i] + bws[i] / 2, y), (xs[i + 1] - bws[i + 1] / 2, y))

    component(ax, xs[0], y, bws[0], bh, "Telemetry\nIngestion",
              "22-D extractor", name_dy=0.12, sub_dy=-0.21)
    component(ax, xs[1], y, bws[1], bh, "Zero-Trust\nVerifier")
    component(ax, xs[2], y, bws[2], bh, "Threat\nIntelligence")
    component(ax, xs[3], y, bws[3], bh, "ML Engine",
              "ONNX gate +\nthreat typing", name_dy=0.19, sub_dy=-0.15)
    component(ax, xs[4], y, bws[4], bh, "Remediation\nOrchestrator")

    # Async band: four governance roles, outside the timed path.
    ax.add_patch(Rectangle((0.02, 0.02), 4.86, 1.03,
                           linewidth=0.0, facecolor=ASYNC, zorder=0))
    ax.text(2.45, 0.12, "Asynchronous / post-decision roles  {not timed}",
            fontsize=7.2, fontweight="bold", ha="center", va="bottom",
            color="#111111")

    async_xs = [0.62, 1.84, 3.06, 4.28]
    for x, label in zip(async_xs, ["Risk Scoring\nAgent", "Adaptive\nMemory",
                                   "Policy Agent\n(CPPP)", "Containment\nAgent"]):
        component(ax, x, 0.66, 1.00, 0.60, label, name_dy=0.02)

    # Post-decision connector: one dashed bus, no Event Bus component.
    bus_y = 1.22
    ax.plot([xs[4], xs[4], async_xs[0]], [y - bh / 2, bus_y, bus_y],
            color=MUTED, linewidth=0.7, linestyle=(0, (3, 2)), zorder=1)
    for x in async_xs:
        arrow(ax, (x, bus_y), (x, 0.96), linestyle=(0, (3, 2)),
              color=MUTED, lw=0.7)
    ax.text(2.35, 1.25, "\u00abasync telemetry\u00bb", ha="center", va="bottom",
            fontsize=5.6, style="italic", color=MUTED)

    fig.savefig(FIG / "architecture.pdf")
    fig.savefig(FIG / "architecture.png")
    plt.close(fig)
    print("wrote figures/architecture.pdf/.png")


if __name__ == "__main__":
    main()
