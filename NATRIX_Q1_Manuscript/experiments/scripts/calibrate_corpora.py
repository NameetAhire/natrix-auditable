"""Cross-fitted threshold sensitivity for every labelled corpus.

The per-corpus tables in ``corpora_metrics.csv`` score the 22-D gate at the
default 0.5 threshold.  A fixed threshold does not transfer across corpora with
different score scales and class priors, so this script reports the same
operating-point analysis that the CSIC v3/v4 comparison uses (deviation D13):

    for each outer fold k, select the threshold on the OOF predictions of the
    other four folds and apply it to fold k.

No model is refitted and no label from fold k is used to choose its threshold.
The caveat recorded in D13 still applies: the OOF models that score the other
folds were trained on data that includes fold k, so this is a cross-fitted
threshold sensitivity analysis, not a fully nested selection.  The
pre-registered inner-CV points remain in ``corpora_metrics.csv`` when that
script is run with ``--operating-points``.

Outputs
-------
experiments/results/corpora/corpora_calibrated.csv
experiments/results/corpora/corpora_calibration.json
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
from compare_v3_v4 import best_threshold, metrics_from_pred  # noqa: E402
from evaluate_corpora import load_corpus  # noqa: E402

OUT = C.RESULTS / "corpora"
POLICIES = {"f1": None, "fpr1": 0.01, "fpr2": 0.02}
CORPORA = ("csic", "ecml", "srbh")
PROTOCOLS = ("P1", "P2")


def folds_for(corpus: str, protocol: str, y: np.ndarray, seed: int = C.SEED):
    cache = OUT / f"{corpus}_{protocol}_folds_seed{seed}.npz"
    if cache.exists():
        z = np.load(cache)
        return [(z[f"tr_{i}"], z[f"te_{i}"]) for i in range(5)]
    if protocol == "P1":
        splitter = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
        folds = list(splitter.split(np.zeros((len(y), 1)), y))
    else:
        _, _, groups = load_corpus(corpus)
        splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
        folds = list(splitter.split(np.zeros((len(y), 1)), y, groups))
    np.savez_compressed(
        cache, **{f"tr_{i}": tr for i, (tr, _) in enumerate(folds)},
        **{f"te_{i}": te for i, (_, te) in enumerate(folds)},
    )
    return folds


def loo_predict(proba, y, folds, cap):
    pred = np.zeros(len(y), dtype=int)
    thresholds = []
    for _, te in folds:
        mask = np.ones(len(y), dtype=bool)
        mask[te] = False
        t = best_threshold(proba[mask], y[mask], fpr_cap=cap)
        pred[te] = (proba[te] >= t).astype(int)
        thresholds.append(t)
    return pred, thresholds


def main() -> None:
    rows = []
    missing = []
    for corpus in CORPORA:
        for protocol in PROTOCOLS:
            path = OUT / f"{corpus}_{protocol}_oof.npz"
            if not path.exists():
                missing.append(path.name)
                continue
            z = np.load(path)
            proba, y = z["proba"], z["y"]
            folds = folds_for(corpus, protocol, y)
            for policy, cap in POLICIES.items():
                pred, thresholds = loo_predict(proba, y, folds, cap)
                m = metrics_from_pred(y, pred)
                m.update({
                    "corpus": corpus, "protocol": protocol, "policy": policy,
                    "features": "22-D",
                    "threshold_mean": float(np.mean(thresholds)),
                    "thresholds": ";".join(f"{v:.2f}" for v in thresholds),
                    "n": int(len(y)),
                })
                rows.append(m)
            print(f"{corpus} {protocol}: calibrated", flush=True)

    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "corpora_calibrated.csv", index=False)

    summary = {
        "protocol": "leave-one-fold-out threshold on saved outer OOF predictions; "
                    "fold k threshold never sees fold k labels",
        "caveat": "D13: OOF models for other folds were trained on data that "
                  "includes fold k; cross-fitted sensitivity, not fully nested",
        "policies": {"f1": "F1-optimal", "fpr1": "FPR<=1%", "fpr2": "FPR<=2%"},
        "missing": missing,
        "per_corpus": frame.to_dict("records"),
        "acceptance_check": {},
    }
    for corpus in CORPORA:
        for protocol in PROTOCOLS:
            sub = frame[(frame["corpus"] == corpus) &
                        (frame["protocol"] == protocol) &
                        (frame["policy"] == "fpr2")]
            if sub.empty:
                continue
            summary["acceptance_check"][f"{corpus}_{protocol}"] = {
                "accuracy": float(sub["accuracy"].iloc[0]),
                "fpr": float(sub["fpr"].iloc[0]),
                "fnr": float(sub["fnr"].iloc[0]),
                "f1": float(sub["f1"].iloc[0]),
                "threshold_mean": float(sub["threshold_mean"].iloc[0]),
                "meets_both": bool(
                    (sub["accuracy"] > 0.95).all() and (sub["fpr"] < 0.0203).all()
                ),
            }
    C.write_json(OUT / "corpora_calibration.json", summary)

    if not frame.empty:
        print(frame[["corpus", "protocol", "policy", "threshold_mean",
                     "accuracy", "fpr", "fnr", "f1"]].to_string(index=False))
    if missing:
        print("missing:", ", ".join(missing))
    print("acceptance:", summary["acceptance_check"])


if __name__ == "__main__":
    main()
