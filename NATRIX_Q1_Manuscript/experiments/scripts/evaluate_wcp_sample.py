"""NATRIX on a 20k sample of the OpenAppSec WAF Comparison corpus (2024).

The WCP corpus is the newest labelled HTTP set in the project: 137,820
legitimate requests from 692 sites plus 73,924 malicious payloads across seven
families.  A full 211,744-row replay is unnecessary for a comparison table, so
this script fixes a stratified 20,000-row sample that the CRS and lexical
baselines reuse.  Features come from the existing cache; the script verifies
that the cache labels still match the request parquet.

Caveat: the legitimate traffic is clustered by site, so a random P1 split can
leak site-specific paths.  The result is an in-distribution point, not a
site-disjoint generalisation claim.  The paper must say so.

Outputs
-------
experiments/results/baselines/wcp_sample20k_requests.parquet
experiments/results/baselines/natrix_wcp_sample20k_oof.npz
experiments/results/baselines/natrix_wcp_sample20k.json
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
from compare_v3_v4 import best_threshold, metrics_from_pred  # noqa: E402

OUT = C.RESULTS / "baselines"
OUT.mkdir(parents=True, exist_ok=True)
WCP = C.PROCESSED / "openappsec"
LIMIT = 20_000
SEED = 42


def main() -> None:
    frame = pd.read_parquet(WCP / "wcp_requests.parquet")
    frame["orig_index"] = np.arange(len(frame), dtype=np.int64)
    parts = []
    for _, group in frame.groupby("label", sort=True):
        take = max(1, int(round(LIMIT * len(group) / len(frame))))
        parts.append(group.sample(n=min(take, len(group)), random_state=SEED))
    sample = (
        pd.concat(parts)
        .sample(frac=1.0, random_state=SEED)
        .reset_index(drop=True)
    )
    sample.to_parquet(OUT / "wcp_sample20k_requests.parquet", index=False)
    print(f"sample: {len(sample):,} labels={sample.label.value_counts().to_dict()}",
          flush=True)

    cache = np.load(WCP / "wcp_features.npz", allow_pickle=True)
    idx = sample["orig_index"].to_numpy(dtype=int)
    y = sample["label"].to_numpy(dtype=int)
    if not np.array_equal(cache["y"][idx].astype(int), y):
        raise SystemExit("cached WCP labels do not align with the sampled rows")
    X = cache["X"][idx]

    folds = list(
        StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED).split(X, y)
    )
    proba = np.zeros(len(y), dtype=np.float32)
    for tr, te in folds:
        model = C.make_rf(random_state=SEED)
        model.fit(X[tr], y[tr])
        proba[te] = model.predict_proba(X[te])[:, 1]

    pred05 = (proba >= 0.5).astype(int)
    pred_fpr2 = np.zeros(len(y), dtype=int)
    thresholds = []
    for _, te in folds:
        mask = np.ones(len(y), dtype=bool)
        mask[te] = False
        t = best_threshold(proba[mask], y[mask], fpr_cap=0.02)
        pred_fpr2[te] = (proba[te] >= t).astype(int)
        thresholds.append(float(t))

    np.savez(
        OUT / "natrix_wcp_sample20k_oof.npz",
        proba=proba, y=y,
        folds=np.asarray([te for _, te in folds], dtype=object),
    )
    result = {
        "corpus": "wcp", "limit": LIMIT, "n": int(len(y)),
        "labels": {"clean": int((y == 0).sum()), "attack": int((y == 1).sum())},
        "threshold_0.5": metrics_from_pred(y, pred05),
        "fpr2_crossfit": {
            **metrics_from_pred(y, pred_fpr2),
            "threshold_mean": float(np.mean(thresholds)),
            "thresholds": thresholds,
        },
        "notes": [
            "Random P1 split; legitimate traffic is site-clustered, so this is not site-disjoint.",
            "WCP 2024 legitimate requests were capped at 200 per site by the builder.",
        ],
    }
    C.write_json(OUT / "natrix_wcp_sample20k.json", result)
    print(result)


if __name__ == "__main__":
    main()
