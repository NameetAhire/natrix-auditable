"""v3 vs v4 on the independent corpora.

Reviewer concern: the two features dropped on CSIC are constant there, but
``html_tag_density`` is not constant on ECML.  Dropping them on CSIC evidence
alone may therefore be unjustified for deployment.  This script measures the
v3/v4 difference on ECML/PKDD 2007 and SR-BH 2020 under the same P1 protocol
and the same shipped forest.

Outputs
-------
experiments/results/v3_v4/corpora_v3_v4.csv
experiments/results/v3_v4/corpora_v3_v4.json
experiments/results/v3_v4/{corpus}_{features}_oof.npz
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import StratifiedKFold

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import stats_utils as S  # noqa: E402
from compare_v3_v4 import best_threshold, metrics_from_pred  # noqa: E402

OUT = C.RESULTS / "v3_v4"
OUT.mkdir(parents=True, exist_ok=True)
SEED = 42


def load_corpus(name: str):
    if name == "csic":
        records, _ = C.csic_unique()
        X, _ = C.extract_matrix(records, dtype=np.float32)
        return X, C.label_array(records)
    if name == "ecml":
        records = C.load_ecml_records()
        X, _ = C.extract_matrix(records, dtype=np.float32)
        return X, C.label_array(records)
    if name == "srbh":
        z = np.load(C.PROCESSED / "srbh" / "srbh_features.npz", allow_pickle=True)
        return z["X"], z["y"]
    raise ValueError(name)


def v4_indices() -> list[int]:
    import json
    definition = json.loads(
        (C.ARTIFACTS / "feature_selection" / "v4_definition.json").read_text(encoding="utf-8")
    )
    return [C.FEATURES.index(name) for name in definition["v4_features"]]


def oof(X, y, seed=SEED):
    folds = list(StratifiedKFold(n_splits=5, shuffle=True, random_state=seed).split(X, y))
    proba = np.zeros(len(y), dtype=np.float32)
    for tr, te in folds:
        model = C.make_rf(random_state=seed)
        model.fit(X[tr], y[tr])
        proba[te] = model.predict_proba(X[te])[:, 1]
    return proba, folds


def loo_threshold(proba, y, folds, cap=0.02):
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpora", nargs="+", default=["ecml", "srbh"])
    args = parser.parse_args()

    idx = v4_indices()
    rows = []
    detail = {}
    for corpus in args.corpora:
        started = time.time()
        X, y = load_corpus(corpus)
        print(f"{corpus}: X={X.shape} labels={np.bincount(y).tolist()}", flush=True)

        dropped = [i for i in range(len(C.FEATURES)) if i not in idx]
        for i in dropped:
            col = X[:, i]
            detail.setdefault("dropped_feature_distribution", []).append({
                "corpus": corpus,
                "feature": C.FEATURES[i],
                "zero_frac_clean": float(np.mean(col[y == 0] == 0)),
                "zero_frac_attack": float(np.mean(col[y == 1] == 0)),
                "mean_clean": float(col[y == 0].mean()),
                "mean_attack": float(col[y == 1].mean()),
            })

        for features, cols in (("v3", list(range(X.shape[1]))), ("v4", idx)):
            proba, folds = oof(X[:, cols], y)
            np.savez(OUT / f"{corpus}_{features}_oof.npz", proba=proba, y=y)

            for policy, pred in (
                ("threshold_0.5", (proba >= 0.5).astype(int)),
                ("fpr2_crossfit", loo_threshold(proba, y, folds, 0.02)[0]),
            ):
                m = metrics_from_pred(y, pred)
                m.update({
                    "corpus": corpus, "features": features, "policy": policy,
                    "n": int(len(y)), "elapsed_s": round(time.time() - started, 1),
                })
                rows.append(m)
                print(f"  {features} {policy}: acc={m['accuracy']:.4f} "
                      f"fpr={m['fpr']:.4f} f1={m['f1']:.4f}", flush=True)

            if features == "v4":
                v4_proba = proba
                v4_folds = folds
            else:
                v3_proba = proba
                v3_folds = folds

        # Paired comparison on identical P1 folds.
        for policy, cap in (("threshold_0.5", None), ("fpr2_crossfit", 0.02)):
            if cap is None:
                p3 = (v3_proba >= 0.5).astype(int)
                p4 = (v4_proba >= 0.5).astype(int)
            else:
                p3 = loo_threshold(v3_proba, y, v3_folds, cap)[0]
                p4 = loo_threshold(v4_proba, y, v4_folds, cap)[0]
            c3 = p3 == y
            c4 = p4 == y
            bootstrap = (
                S.paired_bootstrap_delta_chunked if len(y) > 100_000
                else S.paired_bootstrap_delta
            )
            lo, hi = bootstrap(c4.astype(float), c3.astype(float))
            detail.setdefault("paired", []).append({
                "corpus": corpus, "policy": policy,
                "accuracy_delta_v4_minus_v3": float(c4.mean() - c3.mean()),
                "ci_lo": lo, "ci_hi": hi,
                "mcnemar": S.mcnemar(c4, c3),
            })

    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "corpora_v3_v4.csv", index=False)
    C.write_json(OUT / "corpora_v3_v4.json", {
        "protocol": "P1 stratified 5-fold, shipped 200-tree forest, seed 42",
        "features": {"v3": C.FEATURES, "v4": [C.FEATURES[i] for i in idx]},
        "results": frame.to_dict("records"),
        **detail,
    })
    print(frame[["corpus", "features", "policy", "accuracy", "fpr", "fnr", "f1"]].to_string(index=False))
    print(pd.DataFrame(detail.get("paired", [])).to_string(index=False))


if __name__ == "__main__":
    main()
