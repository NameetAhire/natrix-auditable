"""Recover the SR-BH v3 vs v4 comparison from the saved out-of-fold scores.

``evaluate_v4_corpora.py --corpora srbh`` completed both models but then
crashed in the paired bootstrap: the helper draws a (2000, 422054) index matrix,
which needs 6.3 GiB.  The OOF predictions were already saved, so this script
recomputes the same summary and a memory-bounded paired bootstrap without
retraining.  It then merges the SR-BH rows into the existing
``corpora_v3_v4.{json,csv}`` produced by the ECML run.

The fold definition is reconstructed exactly: StratifiedKFold(5, shuffle=True,
random_state=42) over the same label vector.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import stats_utils as S  # noqa: E402
from compare_v3_v4 import best_threshold, metrics_from_pred  # noqa: E402

OUT = C.RESULTS / "v3_v4"
SEED = 42


def chunked_delta(a: np.ndarray, b: np.ndarray, n_boot: int = 2000,
                  seed: int = 42, chunk: int = 25) -> tuple[float, float]:
    """Paired bootstrap CI without materialising (n_boot, n) indices."""
    rng = np.random.default_rng(seed)
    deltas = []
    for start in range(0, n_boot, chunk):
        take = min(chunk, n_boot - start)
        idx = rng.integers(0, len(a), size=(take, len(a)))
        deltas.append(a[idx].mean(axis=1) - b[idx].mean(axis=1))
    deltas = np.concatenate(deltas)
    lo, hi = np.quantile(deltas, [0.025, 0.975])
    return float(lo), float(hi)


def loo_threshold(proba, y, folds, cap=0.02):
    pred = np.zeros(len(y), dtype=int)
    thresholds = []
    for _, te in folds:
        mask = np.ones(len(y), dtype=bool)
        mask[te] = False
        t = best_threshold(proba[mask], y[mask], fpr_cap=cap)
        pred[te] = (proba[te] >= t).astype(int)
        thresholds.append(float(t))
    return pred, thresholds


def main() -> None:
    v3 = np.load(OUT / "srbh_v3_oof.npz", allow_pickle=True)
    v4 = np.load(OUT / "srbh_v4_oof.npz", allow_pickle=True)
    y = v3["y"].astype(int)
    if not np.array_equal(y, v4["y"].astype(int)):
        raise SystemExit("v3/v4 labels differ")
    proba3, proba4 = v3["proba"], v4["proba"]
    folds = list(
        StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
        .split(np.zeros((len(y), 1), dtype=np.uint8), y)
    )

    rows = []
    for features, proba in (("v3", proba3), ("v4", proba4)):
        pred05 = (proba >= 0.5).astype(int)
        pred_cf, thresholds = loo_threshold(proba, y, folds, 0.02)
        for policy, pred in (("threshold_0.5", pred05), ("fpr2_crossfit", pred_cf)):
            m = metrics_from_pred(y, pred)
            m.update({"corpus": "srbh", "features": features, "policy": policy,
                      "n": int(len(y))})
            if policy == "fpr2_crossfit":
                m["threshold_mean"] = float(np.mean(thresholds))
                m["thresholds"] = thresholds
            rows.append(m)
            print(f"{features} {policy}: acc={m['accuracy']:.4f} "
                  f"fpr={m['fpr']:.4f} f1={m['f1']:.4f}", flush=True)

    paired = []
    for policy, cap in (("threshold_0.5", None), ("fpr2_crossfit", 0.02)):
        if cap is None:
            p3 = (proba3 >= 0.5).astype(int)
            p4 = (proba4 >= 0.5).astype(int)
        else:
            p3 = loo_threshold(proba3, y, folds, cap)[0]
            p4 = loo_threshold(proba4, y, folds, cap)[0]
        c3, c4 = p3 == y, p4 == y
        lo, hi = chunked_delta(c4.astype(float), c3.astype(float))
        entry = {
            "corpus": "srbh", "policy": policy,
            "accuracy_delta_v4_minus_v3": float(c4.mean() - c3.mean()),
            "ci_lo": lo, "ci_hi": hi,
            "mcnemar": S.mcnemar(c4, c3),
        }
        paired.append(entry)
        print(entry, flush=True)

    json_path = OUT / "corpora_v3_v4.json"
    existing = json.loads(json_path.read_text(encoding="utf-8"))
    existing["results"] = [r for r in existing["results"] if r["corpus"] != "srbh"] + rows
    existing["paired"] = [p for p in existing["paired"] if p["corpus"] != "srbh"] + paired
    existing.setdefault("notes", []).append(
        "SR-BH rows recovered from saved OOF scores; the original run crashed in "
        "the all-at-once bootstrap allocation after both models had been scored."
    )
    json_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    pd.DataFrame(existing["results"]).to_csv(OUT / "corpora_v3_v4.csv", index=False)
    print("merged into", json_path)


if __name__ == "__main__":
    main()
