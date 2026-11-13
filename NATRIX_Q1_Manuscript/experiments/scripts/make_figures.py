"""Generate the manuscript figures from measured result files.

All inputs are produced by the experiment scripts; nothing is synthesised here.
Missing inputs are skipped with a warning so the script can be run while the
experiment queue is still filling.

Outputs: figures/*.pdf and figures/*.png (300 dpi).
"""

from __future__ import annotations

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

PALETTE = {"v3": "#0072B2", "v4": "#D55E00", "grey": "#666666"}


def save(fig, name):
    fig.savefig(FIG / f"{name}.pdf")
    fig.savefig(FIG / f"{name}.png")
    plt.close(fig)
    print(f"wrote figures/{name}.pdf/.png")


def fig_importance():
    path = C.RESULTS / "feature_audit" / "csic_model_importance.csv"
    if not path.exists():
        print("skip importance: missing", path)
        return
    frame = pd.read_csv(path).sort_values("importance_mean")
    fig, ax = plt.subplots(figsize=(3.5, 4.6))
    y = np.arange(len(frame))
    ax.barh(y, frame["importance_mean"], color=PALETTE["v3"], height=0.7)
    ax.set_yticks(y)
    ax.set_yticklabels(frame["feature"], fontsize=7)
    ax.axvline(0, color="black", linewidth=0.6)
    ax.set_xlabel("Permutation importance\n(mean over 5 folds)")
    ax.set_title("CSIC 2010, 22-D v3 gate")
    save(fig, "feature_importance")


def fig_ablation():
    path = C.RESULTS / "ablation_csic" / "metrics.csv"
    if not path.exists():
        print("skip ablation: missing", path)
        return
    frame = pd.read_csv(path)
    frame = frame[frame["subset"].str.startswith("drop_")]
    frame = frame.sort_values("delta_accuracy")
    fig, ax = plt.subplots(figsize=(3.5, 4.6))
    y = np.arange(len(frame))
    ax.errorbar(
        frame["delta_accuracy"] * 100, y,
        xerr=[
            (frame["delta_accuracy"] - frame["delta_accuracy_ci_lo"]) * 100,
            (frame["delta_accuracy_ci_hi"] - frame["delta_accuracy"]) * 100,
        ],
        fmt="o", color=PALETTE["v3"], ecolor=PALETTE["grey"], capsize=2,
    )
    ax.set_yticks(y)
    ax.set_yticklabels(
        [s.replace("drop_", "") for s in frame["subset"]], fontsize=7
    )
    ax.axvline(0, color="black", linewidth=0.6)
    ax.set_xlabel("$\\Delta$ accuracy when feature is removed (pp)")
    ax.set_title("Leave-one-feature-out ablation")
    save(fig, "ablation_delta")


def _roc(y, proba):
    from sklearn.metrics import roc_curve
    fpr, tpr, _ = roc_curve(y, proba)
    return fpr, tpr


def _pr(y, proba):
    from sklearn.metrics import precision_recall_curve
    precision, recall, _ = precision_recall_curve(y, proba)
    return recall, precision


def fig_v3_v4_curves():
    path3 = C.RESULTS / "v3_v4" / "oof_v3_seed42.npz"
    path4 = C.RESULTS / "v3_v4" / "oof_v4_seed42.npz"
    if not (path3.exists() and path4.exists()):
        print("skip v3/v4 curves: missing OOF files")
        return
    z3 = np.load(path3)
    z4 = np.load(path4)
    y = z3["y"]

    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.0))
    for key, z, color in (("v3", z3, PALETTE["v3"]), ("v4", z4, PALETTE["v4"])):
        fpr, tpr = _roc(y, z["proba"])
        axes[0].plot(fpr, tpr, color=color, linewidth=1.2, label=key)
        rec, prec = _pr(y, z["proba"])
        axes[1].plot(rec, prec, color=color, linewidth=1.2, label=key)
    axes[0].plot([0, 1], [0, 1], color="black", linewidth=0.5, linestyle="--")
    axes[0].set_xlabel("False positive rate")
    axes[0].set_ylabel("True positive rate")
    axes[0].set_title("ROC, CSIC 2010 (P1)")
    axes[0].legend(frameon=False)
    axes[1].set_xlabel("Recall")
    axes[1].set_ylabel("Precision")
    axes[1].set_title("Precision-recall, CSIC 2010 (P1)")
    axes[1].legend(frameon=False)
    save(fig, "v3_v4_roc_pr")


def fig_threshold_tradeoff():
    path3 = C.RESULTS / "v3_v4" / "oof_v3_seed42.npz"
    path4 = C.RESULTS / "v3_v4" / "oof_v4_seed42.npz"
    if not (path3.exists() and path4.exists()):
        print("skip threshold trade-off: missing OOF files")
        return
    z3 = np.load(path3)
    z4 = np.load(path4)
    y = z3["y"]
    thresholds = np.arange(0.05, 0.96, 0.01)
    fig, ax = plt.subplots(figsize=(3.5, 2.8))
    for key, z, color in (("v3", z3, PALETTE["v3"]), ("v4", z4, PALETTE["v4"])):
        acc, fpr = [], []
        for t in thresholds:
            pred = (z["proba"] >= t).astype(int)
            acc.append((pred == y).mean() * 100)
            neg = y == 0
            fpr.append(pred[neg].mean() * 100)
        ax.plot(fpr, acc, color=color, linewidth=1.2, label=key)
    ax.axvline(2.03, color="black", linewidth=0.5, linestyle=":")
    ax.axhline(95.0, color="black", linewidth=0.5, linestyle=":")
    ax.set_xlabel("False positive rate (%)")
    ax.set_ylabel("Accuracy (%)")
    ax.set_title("Operating-point trade-off, CSIC 2010")
    ax.legend(frameon=False)
    save(fig, "threshold_tradeoff")


def fig_transfer():
    path = C.RESULTS / "transfer" / "transfer_metrics.csv"
    if not path.exists():
        print("skip transfer: missing", path)
        return
    frame = pd.read_csv(path)
    frame = frame[frame["policy"] == "fpr2"]
    if frame.empty:
        return
    pivot = frame.pivot_table(
        index="source", columns="target", values="accuracy", aggfunc="mean"
    )
    fig, ax = plt.subplots(figsize=(3.5, 2.4))
    values = np.ma.masked_invalid(pivot.values * 100)
    im = ax.imshow(values, cmap="viridis", vmin=0, vmax=100)
    ax.set_xticks(range(pivot.shape[1]))
    ax.set_xticklabels(pivot.columns)
    ax.set_yticks(range(pivot.shape[0]))
    ax.set_yticklabels(pivot.index)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            value = pivot.values[i, j] * 100
            if np.isnan(value):
                continue
            ax.text(j, i, f"{value:.1f}", ha="center", va="center",
                    color="white" if value < 60 else "black", fontsize=8)
    ax.set_xlabel("Target corpus")
    ax.set_ylabel("Source corpus")
    ax.set_title("Transfer accuracy at source-selected\nFPR $\\leq$ 2%")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Accuracy (%)")
    save(fig, "transfer_accuracy")


def fig_latency():
    path = C.RESULTS / "latency" / "latency_samples.csv"
    if not path.exists():
        print("skip latency: missing", path)
        return
    frame = pd.read_csv(path)
    frame = frame[frame["ok"] == True]  # noqa: E712
    fig, ax = plt.subplots(figsize=(3.5, 2.6))
    for corpus, color in (("csic", PALETTE["v3"]), ("ecml", PALETTE["v4"]),
                          ("wcp", PALETTE["grey"])):
        values = np.sort(frame.loc[frame["corpus"] == corpus, "totalMs"].values)
        if len(values) == 0:
            continue
        ax.plot(values, np.arange(1, len(values) + 1) / len(values),
                color=color, linewidth=1.0, label=corpus.upper())
    ax.axvline(5.0, color="black", linewidth=0.6, linestyle="--")
    ax.set_xlim(0, 8)
    ax.text(5.2, 0.55, "5 ms reference", fontsize=7, va="center")
    ax.set_xlabel("End-to-end decision latency (ms)")
    ax.set_ylabel("ECDF")
    ax.set_title("Inline path, 10,000 requests")
    ax.legend(frameon=False, loc="lower right")
    save(fig, "latency_ecdf")


def main():
    fig_importance()
    fig_ablation()
    fig_v3_v4_curves()
    fig_threshold_tradeoff()
    fig_transfer()
    fig_latency()


if __name__ == "__main__":
    main()
