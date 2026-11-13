"""NATRIX on the 20k SR-BH comparison sample.

The CRS and lexical baselines bound their SR-BH replay with a stratified 20,000
request sample.  This script reproduces that sample exactly, trains the shipped
forest with the same 5-fold protocol used by the lexical baseline, and saves the
out-of-fold probabilities so all three detectors can be compared on identical
rows.
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
LIMIT = 20_000
SEED = 42


def sample_frame() -> pd.DataFrame:
    frame = pd.read_parquet(C.PROCESSED / "srbh" / "srbh_requests.parquet")
    parts = []
    for _, group in frame.groupby("label", sort=True):
        take = max(1, int(round(LIMIT * len(group) / len(frame))))
        parts.append(group.sample(n=min(take, len(group)), random_state=SEED))
    return pd.concat(parts).sample(frac=1.0, random_state=SEED).reset_index(drop=True)


def main() -> None:
    frame = sample_frame()
    print(f"sample: {len(frame):,} labels={frame.label.value_counts().to_dict()}", flush=True)
    frame.to_parquet(OUT / "srbh_sample20k_requests.parquet", index=False)

    records = [
        C.make_request(
            rid=str(i), source="srbh", label=int(row.label),
            method=row.method,
            target=row.path + (("?" + row.query) if row.query else ""),
            body=row.body, user_agent=row.user_agent,
            declared_class=row.family,
        )
        for i, row in enumerate(frame.itertuples(index=False))
    ]
    X, _ = C.extract_matrix(records, dtype=np.float32)
    y = frame.label.to_numpy(dtype=int)
    folds = list(StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED).split(X, y))
    proba = np.zeros(len(y), dtype=np.float32)
    for tr, te in folds:
        model = C.make_rf(random_state=SEED)
        model.fit(X[tr], y[tr])
        proba[te] = model.predict_proba(X[te])[:, 1]

    pred05 = (proba >= 0.5).astype(int)
    pred_fpr2 = np.zeros(len(y), dtype=int)
    thresholds = []
    for te in [te for _, te in folds]:
        mask = np.ones(len(y), dtype=bool)
        mask[te] = False
        t = best_threshold(proba[mask], y[mask], fpr_cap=0.02)
        pred_fpr2[te] = (proba[te] >= t).astype(int)
        thresholds.append(float(t))

    np.savez(
        OUT / "natrix_srbh_sample20k_oof.npz",
        proba=proba, y=y,
        folds=np.asarray([te for _, te in folds], dtype=object),
    )
    result = {
        "corpus": "srbh", "limit": LIMIT, "n": int(len(y)),
        "labels": {"clean": int((y == 0).sum()), "attack": int((y == 1).sum())},
        "threshold_0.5": metrics_from_pred(y, pred05),
        "fpr2_crossfit": {
            **metrics_from_pred(y, pred_fpr2),
            "threshold_mean": float(np.mean(thresholds)),
            "thresholds": thresholds,
        },
    }
    C.write_json(OUT / "natrix_srbh_sample20k.json", result)
    print(result)


if __name__ == "__main__":
    main()
