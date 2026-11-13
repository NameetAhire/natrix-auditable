"""Why is SR-BH full-corpus accuracy higher than the 20k sample?

The paper reports 95.70% for the full 422,054-request SR-BH corpus and 90.79%
for the shared 20,000-request sample at the same FPR<=2% policy.  A reviewer is
right to ask whether the gap is a class-prior artefact or a sample-selection
artefact.  This script separates the two:

* it reports the class and attack-family mix of the sample and the full corpus;
* it measures a learning curve on nested stratified subsets (10k, 20k, 50k,
  100k, 200k, full) using the same 200-tree forest, the same P1 folds, and the
  same cross-fitted FPR<=2% threshold policy.

If the curve rises smoothly with training size while the class mix is stable,
the gap is a sample-size effect, not a prior artefact.

Outputs
-------
experiments/results/corpora/srbh_sample_gap.json
experiments/results/corpora/srbh_sample_gap.csv
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
from compare_v3_v4 import best_threshold, metrics_from_pred  # noqa: E402

OUT = C.RESULTS / "corpora"
OUT.mkdir(parents=True, exist_ok=True)
SEED = 42


def metrics_at_fpr2(proba, y, folds):
    pred = np.zeros(len(y), dtype=int)
    thresholds = []
    for tr, te in folds:
        t = best_threshold(proba[tr], y[tr], fpr_cap=0.02)
        pred[te] = (proba[te] >= t).astype(int)
        thresholds.append(float(t))
    m = metrics_from_pred(y, pred)
    m["threshold_mean"] = float(np.mean(thresholds))
    return m


def nested_subset(y, n_total, seed=SEED):
    """Return a stratified subset of size n_total, nested across sizes."""
    rng = np.random.default_rng(seed)
    by_class = {}
    for label in (0, 1):
        idx = np.flatnonzero(y == label)
        rng.shuffle(idx)
        by_class[label] = idx
    prevalence = y.mean()
    n_attack = int(round(n_total * prevalence))
    n_clean = n_total - n_attack
    n_attack = min(n_attack, len(by_class[1]))
    n_clean = min(n_clean, len(by_class[0]))
    chosen = np.concatenate([by_class[0][:n_clean], by_class[1][:n_attack]])
    rng.shuffle(chosen)
    return chosen


def main() -> None:
    z = np.load(C.PROCESSED / "srbh" / "srbh_features.npz", allow_pickle=True)
    X = z["X"]
    y = z["y"].astype(int)
    print(f"full: n={len(y):,} clean={int((y == 0).sum()):,} attack={int((y == 1).sum()):,}")

    full_oof = np.load(C.RESULTS / "corpora" / "srbh_P1_oof.npz", allow_pickle=True)
    # Preserve float32; casting to float64 moves a few probabilities across
    # the 0.01 threshold grid and reports 90.70 instead of 90.79 on the 20k row.
    full_proba = full_oof["proba"].astype(np.float32)
    full_y = full_oof["y"].astype(int)
    assert np.array_equal(full_y, y)
    f = np.load(C.RESULTS / "corpora" / "srbh_P1_folds_seed42.npz", allow_pickle=True)
    full_folds = [(f[f"tr_{i}"], f[f"te_{i}"]) for i in range(5)]

    sample = pd.read_parquet(
        C.RESULTS / "baselines" / "srbh_sample20k_requests.parquet",
        columns=["label", "family"],
    )
    sample_oof = np.load(
        C.RESULTS / "baselines" / "natrix_srbh_sample20k_oof.npz", allow_pickle=True
    )
    sample_proba = sample_oof["proba"].astype(np.float32)
    sample_y = sample_oof["y"].astype(int)
    sample_folds = [
        (np.setdiff1d(np.arange(len(sample_y)), np.asarray(te, dtype=int)), np.asarray(te, dtype=int))
        for te in sample_oof["folds"]
    ]

    full_family = pd.read_parquet(
        C.PROCESSED / "srbh" / "srbh_requests.parquet", columns=["label", "family"]
    )
    family_table = []
    for name, frame in (("full", full_family), ("sample20k", sample)):
        counts = frame.groupby(["family", "label"]).size().unstack(fill_value=0)
        for family, row in counts.iterrows():
            family_table.append(
                {
                    "corpus": name,
                    "family": str(family),
                    "clean": int(row.get(0, 0)),
                    "attack": int(row.get(1, 0)),
                }
            )

    rows = []
    full_m = metrics_at_fpr2(full_proba, full_y, full_folds)
    rows.append({"subset": "full", "n": int(len(y)), **full_m})
    sample_m = metrics_at_fpr2(sample_proba, sample_y, sample_folds)
    rows.append({"subset": "sample20k", "n": int(len(sample_y)), **sample_m})

    for n_total in (10_000, 20_000, 50_000, 100_000, 200_000):
        idx = nested_subset(y, n_total)
        Xs = X[idx]
        ys = y[idx]
        folds = list(
            StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED).split(Xs, ys)
        )
        proba = np.zeros(len(ys), dtype=np.float32)
        for k, (tr, te) in enumerate(folds):
            model = C.make_rf(random_state=SEED)
            model.fit(Xs[tr], ys[tr])
            proba[te] = model.predict_proba(Xs[te])[:, 1]
            print(f"  n={n_total:,} fold {k} done", flush=True)
        m = metrics_at_fpr2(proba, ys, folds)
        rows.append({"subset": f"nested{n_total}", "n": int(n_total), **m})
        print(
            f"n={n_total:,}: acc={m['accuracy']:.4f} fpr={m['fpr']:.4f} "
            f"recall={m['recall']:.4f}",
            flush=True,
        )

    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "srbh_sample_gap.csv", index=False)
    result = {
        "corpus": "SR-BH 2020",
        "protocol": "P1",
        "policy": "cross-fitted FPR<=2%",
        "full_prior": float(y.mean()),
        "sample20k_prior": float(sample_y.mean()),
        "rows": frame.to_dict("records"),
        "family_mix": family_table,
    }
    C.write_json(OUT / "srbh_sample_gap.json", result)
    print(frame[["subset", "n", "accuracy", "fpr", "recall", "f1"]].to_string(index=False))


if __name__ == "__main__":
    main()
