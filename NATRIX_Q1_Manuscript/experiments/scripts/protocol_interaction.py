"""Quantify the protocol x view interaction with paired bootstrap intervals.

The manuscript's central claim is that the ranking of detectors depends on the
split protocol and on whether the path is visible.  The tables report the point
estimates; this script attaches an interval to the *change* in the ranking.

Every number is recomputed from the out-of-fold predictions that produced the
published tables, with the same leave-one-fold-out FPR <= 2% threshold rule
(``compare_v3_v4.best_threshold``).  The script first asserts that the
recomputed point estimates match the manuscript, then bootstraps the paired
difference-in-differences over requests.

Usage
-----
    python experiments/scripts/protocol_interaction.py
    python experiments/scripts/protocol_interaction.py --n-boot 5000
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
from compare_v3_v4 import best_threshold, metrics_from_pred  # noqa: E402

CORPORA = {
    "csic": "corpora",
    "ecml": "corpora",
    "srbh20k": "baselines",
}

# Published Table 4 values (accuracy %, FPR %) used as a regression guard.
EXPECTED = {
    ("csic", "P1", "natrix"): (95.55, 1.93),
    ("csic", "P1", "lex_full"): (96.57, 1.96),
    ("csic", "P1", "lex_payload"): (96.90, 1.88),
    ("csic", "P2", "natrix"): (78.85, 6.50),
    ("csic", "P2", "lex_full"): (69.53, 21.57),
    ("csic", "P2", "lex_payload"): (96.03, 2.43),
    ("ecml", "P1", "natrix"): (91.96, 1.67),
    ("ecml", "P1", "lex_full"): (93.93, 0.43),
    ("ecml", "P2", "natrix"): (91.60, 1.75),
    ("srbh20k", "P1", "natrix"): (90.79, 1.96),
    ("srbh20k", "P1", "lex_full"): (95.41, 1.98),
    ("srbh20k", "P1", "lex_payload"): (36.20, 2.00),
    ("srbh20k", "P2", "natrix"): (90.62, 1.88),
    ("srbh20k", "P2", "lex_full"): (94.75, 2.01),
    ("srbh20k", "P2", "lex_payload"): (36.27, 1.88),
}


def load(corpus: str, protocol: str, model: str):
    base = C.RESULTS
    if model == "natrix":
        if corpus == "srbh20k":
            path = base / "baselines" / f"natrix_srbh_sample20k{'' if protocol == 'P1' else '_P2'}_oof.npz"
        else:
            path = base / "corpora" / f"{corpus}_{protocol}_oof.npz"
    else:
        view = "full" if model == "lex_full" else "payload"
        if corpus == "srbh20k":
            stem = f"lexical_srbh{'' if protocol == 'P1' else '20k_P2'}_{view}_oof.npz"
        else:
            stem = f"lexical_{corpus}{'' if protocol == 'P1' else '_P2'}_{view}_oof.npz"
        path = base / "baselines" / stem
    z = np.load(path, allow_pickle=True)
    folds = [np.asarray(f, dtype=int) for f in z["folds"]] if "folds" in z.files else None
    return z["proba"], z["y"].astype(int), folds


def folds_for(corpus: str, protocol: str, model: str, z_folds):
    if z_folds is not None:
        return [np.asarray(f, dtype=int) for f in z_folds]
    if corpus == "srbh20k":
        path = C.RESULTS / "baselines" / "srbh20k_P2_folds_seed42.npz"
    else:
        path = C.RESULTS / "corpora" / f"{corpus}_{protocol}_folds_seed42.npz"
    z = np.load(path, allow_pickle=True)
    return [z[f"te_{k}"] for k in range(5)]


def crossfit_correct(proba, y, folds, cap=0.02):
    correct = np.zeros(len(y), dtype=bool)
    thresholds = []
    for te in folds:
        mask = np.ones(len(y), dtype=bool)
        mask[te] = False
        t = best_threshold(proba[mask], y[mask], fpr_cap=cap)
        correct[te] = (proba[te] >= t).astype(int) == y[te]
        thresholds.append(float(t))
    return correct, thresholds


def bootstrap_stat(corrects: list[np.ndarray], stat, n_boot=2000, seed=42, chunk=25):
    """Percentile CI for an arbitrary statistic of per-request correctness."""
    n = len(corrects[0])
    rng = np.random.default_rng(seed)
    vals = []
    for start in range(0, n_boot, chunk):
        take = min(chunk, n_boot - start)
        idx = rng.integers(0, n, size=(take, n))
        means = [c[idx].mean(axis=1) for c in corrects]
        vals.append(stat(*means))
    vals = np.concatenate(vals)
    lo, hi = np.quantile(vals, [0.025, 0.975])
    p = 2 * min(float((vals <= 0).mean()), float((vals >= 0).mean()))
    return float(lo), float(hi), float(p), vals


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-boot", type=int, default=2000)
    parser.add_argument("--out", default=str(C.RESULTS / "protocol_interaction.json"))
    args = parser.parse_args()

    data: dict[str, dict] = {}
    guard_failures = []

    for corpus in CORPORA:
        data[corpus] = {}
        for protocol in ("P1", "P2"):
            rows = {}
            for model in ("natrix", "lex_full", "lex_payload"):
                proba, y, folds = load(corpus, protocol, model)
                folds = folds_for(corpus, protocol, model, folds)
                correct, thresholds = crossfit_correct(proba, y, folds)
                acc = float(correct.mean())
                # FPR: among clean rows, fraction predicted positive
                clean = y == 0
                fpr = float((~correct[clean]).mean())
                rows[model] = {
                    "accuracy": acc,
                    "fpr": fpr,
                    "n": int(len(y)),
                    "threshold_mean": float(np.mean(thresholds)),
                    "correct": correct,
                }
                key = (corpus, protocol, model)
                if key in EXPECTED:
                    ea, ef = EXPECTED[key]
                    if abs(100 * acc - ea) > 0.02 or abs(100 * fpr - ef) > 0.02:
                        guard_failures.append(
                            f"{key}: got {100*acc:.2f}/{100*fpr:.2f}, expected {ea}/{ef}"
                        )
            data[corpus][protocol] = rows

    if guard_failures:
        print("REGRESSION GUARD FAILED")
        for g in guard_failures:
            print("  ", g)
        raise SystemExit(1)

    tests = {}

    def add(name, key, sign=1.0):
        """Interaction of (a - b) between P2 and P1."""
        corpus, model_a, model_b = key
        a_key = (corpus, model_a, model_b)
        c = [
            data[corpus]["P2"][model_a]["correct"],
            data[corpus]["P2"][model_b]["correct"],
            data[corpus]["P1"][model_a]["correct"],
            data[corpus]["P1"][model_b]["correct"],
        ]

        def stat(a2, b2, a1, b1):
            return sign * ((a2 - b2) - (a1 - b1))

        lo, hi, p, _ = bootstrap_stat(c, stat, n_boot=args.n_boot)
        point = float(
            sign
            * (
                (data[corpus]["P2"][model_a]["accuracy"] - data[corpus]["P2"][model_b]["accuracy"])
                - (data[corpus]["P1"][model_a]["accuracy"] - data[corpus]["P1"][model_b]["accuracy"])
            )
        )
        tests[name] = {"interaction_points": 100 * point, "ci95_points": [100 * lo, 100 * hi], "p": p}

    # NATRIX versus the lexical full-request baseline, protocol change.
    add("csic_natrix_minus_lexfull", ("csic", "natrix", "lex_full"))
    add("ecml_natrix_minus_lexfull", ("ecml", "natrix", "lex_full"))
    add("srbh_natrix_minus_lexfull", ("srbh20k", "natrix", "lex_full"))

    # Payload view minus full view, protocol change (the view effect).
    add("csic_payload_minus_full", ("csic", "lex_payload", "lex_full"))
    add("ecml_payload_minus_full", ("ecml", "lex_payload", "lex_full"))
    add("srbh_payload_minus_full", ("srbh20k", "lex_payload", "lex_full"))

    # The corpus interaction: the view effect is protocol-sensitive on CSIC,
    # not on SR-BH.  Reported as the difference of the two interactions.
    csic = tests["csic_payload_minus_full"]["interaction_points"]
    srbh = tests["srbh_payload_minus_full"]["interaction_points"]
    tests["csic_vs_srbh_view_protocol"] = {
        "difference_points": csic - srbh,
        "note": "difference of two independently bootstrapped interactions; not itself bootstrapped",
    }

    out = {
        "cells": {
            corpus: {
                protocol: {
                    model: {
                        "accuracy_pct": 100 * rows["accuracy"],
                        "fpr_pct": 100 * rows["fpr"],
                        "n": rows["n"],
                        "threshold_mean": rows["threshold_mean"],
                    }
                    for model, rows in data[corpus][protocol].items()
                }
                for protocol in ("P1", "P2")
            }
            for corpus in CORPORA
        },
        "tests": tests,
        "n_boot": args.n_boot,
    }
    Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")

    print("cells (accuracy/FPR %)")
    for corpus in CORPORA:
        for protocol in ("P1", "P2"):
            cells = out["cells"][corpus][protocol]
            print(
                f"  {corpus:8s} {protocol}  "
                + "  ".join(f"{m}={100*cells[m]['accuracy_pct']:.2f}/{100*cells[m]['fpr_pct']:.2f}" for m in cells)
            )
    print("interactions (points, 95% CI)")
    for name, t in tests.items():
        if "interaction_points" in t:
            print(f"  {name:28s} {t['interaction_points']:+7.2f}  [{t['ci95_points'][0]:+7.2f}, {t['ci95_points'][1]:+7.2f}]  p={t['p']:.4f}")
        else:
            print(f"  {name:28s} {t['difference_points']:+7.2f}")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
