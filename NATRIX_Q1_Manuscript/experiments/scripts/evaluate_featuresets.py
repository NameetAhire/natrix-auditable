"""Out-of-fold evaluation for arbitrary feature subsets.

One 5-fold deployment-like split, fixed Random Forest (the shipped gate
configuration), OOF probabilities at threshold 0.5.  Used for:

  * leave-one-feature-out ablation of the 22 v3 features
  * full v3 vs v4 comparison (same folds, same learner)

Threshold policy for this script is fixed at 0.5 so that every variant is
compared under an identical decision rule; nested threshold selection is done
separately for the headline v3/v4 numbers.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import stats_utils as S  # noqa: E402


def metrics(y_true, proba, threshold=0.5) -> dict:
    pred = (proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    return {
        "accuracy": float(accuracy_score(y_true, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, pred)),
        "precision": float(precision_score(y_true, pred, zero_division=0)),
        "recall": float(recall_score(y_true, pred, zero_division=0)),
        "f1": float(f1_score(y_true, pred, zero_division=0)),
        "fpr": float(fp / (fp + tn)) if (fp + tn) else 0.0,
        "fnr": float(fn / (fn + tp)) if (fn + tp) else 0.0,
        "roc_auc": float(roc_auc_score(y_true, proba)),
        "pr_auc": float(average_precision_score(y_true, proba)),
        "tp": int(tp), "tn": int(tn), "fp": int(fp), "fn": int(fn),
    }


def run_subsets(X_all, y, subsets: dict, n_splits=5, seed=C.SEED, n_jobs=6):
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    folds = list(skf.split(X_all, y))
    out = {}
    for name, cols in subsets.items():
        X = X_all[:, cols]
        proba = np.zeros(len(y))
        for tr, te in folds:
            model = C.make_rf(random_state=seed, n_jobs=n_jobs)
            model.fit(X[tr], y[tr])
            proba[te] = model.predict_proba(X[te])[:, 1]
        out[name] = proba
        print(f"  {name:<28} done", flush=True)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=str, default="")
    parser.add_argument("--out", type=str, default="ablation_csic")
    args = parser.parse_args()

    records, _ = C.csic_unique()
    X_all, _ = C.extract_matrix(records)
    y = C.label_array(records)
    names = C.FEATURES

    if args.spec:
        spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
        subsets = {k: [names.index(f) for f in v] for k, v in spec.items()}
    else:
        subsets = {"full_22": list(range(len(names)))}
        for j, name in enumerate(names):
            subsets[f"drop_{name}"] = [k for k in range(len(names)) if k != j]

    print(f"subsets: {len(subsets)}  records: {len(y):,}")
    out = run_subsets(X_all, y, subsets)

    base_name = "full_22" if "full_22" in out else next(iter(out))
    base_correct = (out[base_name] >= 0.5).astype(int) == y

    rows = []
    for name, proba in out.items():
        m = metrics(y, proba)
        correct = (proba >= 0.5).astype(int) == y
        delta = correct.astype(float) - base_correct.astype(float)
        lo, hi = S.paired_bootstrap_delta(correct.astype(float), base_correct.astype(float))
        mc = S.mcnemar(correct, base_correct)
        row = {"subset": name, **m,
               "delta_accuracy": float(correct.mean() - base_correct.mean()),
               "delta_accuracy_ci_lo": lo, "delta_accuracy_ci_hi": hi,
               "mcnemar_p": mc["p_value"]}
        rows.append(row)

    frame = pd.DataFrame(rows).sort_values("accuracy", ascending=False)
    OUT = C.RESULTS / args.out
    OUT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT / "metrics.csv", index=False)
    np.savez(OUT / "oof.npz", **{k: v for k, v in out.items()}, y=y)
    print(frame[["subset", "accuracy", "fpr", "fnr", "f1", "delta_accuracy", "mcnemar_p"]].to_string(index=False))


if __name__ == "__main__":
    main()
