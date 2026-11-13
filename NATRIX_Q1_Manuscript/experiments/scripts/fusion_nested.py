"""Fully nested check of the NATRIX + lexical stacker on CSIC.

The cross-fitted stacker in ``fusion_scores.py`` uses base scores that were
produced by models trained on folds that include the stacker's test fold.  That
is the same D13 caveat as the cross-fitted threshold.  This script removes it:

For each outer fold k:
  1. split the training folds into four inner folds;
  2. train NATRIX and lexical base models on inner-train, score inner-val;
  3. train a stacker on the inner OOF scores and select its threshold on a
     leave-one-inner-fold-out stacker prediction;
  4. retrain both base models on the full outer-train, score outer-test;
  5. apply the stacker and the threshold from step 3.

The outer-test labels are never used for training or threshold selection.  The
script is deliberately limited to CSIC because the lexical refits dominate the
cost.

Outputs
-------
experiments/results/baselines/fusion_nested_csic.json
experiments/results/baselines/fusion_nested_csic.csv
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.model_selection import StratifiedKFold

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
from compare_v3_v4 import best_threshold, metrics_from_pred  # noqa: E402

OUT = C.RESULTS / "baselines"
OUT.mkdir(parents=True, exist_ok=True)
SEED = 42


def logit(p):
    p = np.clip(np.asarray(p, dtype=np.float64), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def lexical_model():
    return SGDClassifier(
        loss="log_loss", penalty="l2", alpha=1e-5, max_iter=30,
        tol=1e-4, random_state=SEED, average=True,
    )


def natrix_model():
    return C.make_rf(random_state=SEED)


def fit_predict_natrix(X, y, tr, te):
    model = natrix_model()
    model.fit(X[tr], y[tr])
    return model.predict_proba(X[te])[:, 1]


def fit_predict_lexical(Xl, y, tr, te):
    model = lexical_model()
    model.fit(Xl[tr], y[tr])
    return model.predict_proba(Xl[te])[:, 1]


def main() -> None:
    started = time.time()
    records, _ = C.csic_unique()
    X, _ = C.extract_matrix(records, dtype=np.float32)
    y = C.label_array(records)
    texts = [f"{r.path} {r.query} {r.body}" for r in records]
    vectorizer = HashingVectorizer(
        analyzer="char_wb", ngram_range=(2, 4), n_features=2 ** 18,
        alternate_sign=False, norm="l2", lowercase=True,
    )
    Xl = vectorizer.transform(texts)
    print(f"X={X.shape} Xl={Xl.shape} nnz={Xl.nnz:,}", flush=True)

    outer = list(StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED).split(X, y))
    stack_oof = np.zeros(len(y), dtype=np.float64)
    natrix_oof = np.zeros(len(y), dtype=np.float64)
    lexical_oof = np.zeros(len(y), dtype=np.float64)
    thresholds = {"natrix": [], "lexical": [], "stack": []}

    for k, (tr, te) in enumerate(outer):
        inner = list(StratifiedKFold(n_splits=4, shuffle=True, random_state=SEED).split(X[tr], y[tr]))
        inner_n = np.zeros(len(tr), dtype=np.float64)
        inner_l = np.zeros(len(tr), dtype=np.float64)
        for itr, iva in inner:
            inner_n[iva] = fit_predict_natrix(X[tr], y[tr], itr, iva)
            inner_l[iva] = fit_predict_lexical(Xl[tr], y[tr], itr, iva)
        inner_features = np.column_stack([logit(inner_n), logit(inner_l)])

        # Stacker OOF inside the training folds, used only for the threshold.
        stack_inner = np.zeros(len(tr), dtype=np.float64)
        for itr, iva in inner:
            st = LogisticRegression(C=1.0, max_iter=1000)
            st.fit(inner_features[itr], y[tr][itr])
            stack_inner[iva] = st.predict_proba(inner_features[iva])[:, 1]

        # Base models on the full outer-train, stacker on all inner OOF.
        n_test = fit_predict_natrix(X, y, tr, te)
        l_test = fit_predict_lexical(Xl, y, tr, te)
        st = LogisticRegression(C=1.0, max_iter=1000)
        st.fit(inner_features, y[tr])
        test_features = np.column_stack([logit(n_test), logit(l_test)])
        s_test = st.predict_proba(test_features)[:, 1]

        natrix_oof[te] = n_test
        lexical_oof[te] = l_test
        stack_oof[te] = s_test

        # Thresholds are selected on training-fold predictions only.
        t_n = best_threshold(inner_n, y[tr], fpr_cap=0.02)
        t_l = best_threshold(inner_l, y[tr], fpr_cap=0.02)
        t_s = best_threshold(stack_inner, y[tr], fpr_cap=0.02)
        thresholds["natrix"].append(float(t_n))
        thresholds["lexical"].append(float(t_l))
        thresholds["stack"].append(float(t_s))
        print(f"fold {k}: n={t_n:.3f} l={t_l:.3f} s={t_s:.3f} "
              f"({time.time() - started:.0f}s)", flush=True)

    # Apply each fold's threshold to its outer-test predictions.
    preds = {"natrix": np.zeros(len(y), dtype=int),
             "lexical": np.zeros(len(y), dtype=int),
             "stack": np.zeros(len(y), dtype=int)}
    for k, (_, te) in enumerate(outer):
        preds["natrix"][te] = (natrix_oof[te] >= thresholds["natrix"][k]).astype(int)
        preds["lexical"][te] = (lexical_oof[te] >= thresholds["lexical"][k]).astype(int)
        preds["stack"][te] = (stack_oof[te] >= thresholds["stack"][k]).astype(int)

    rows = []
    for name, pred in preds.items():
        m = metrics_from_pred(y, pred)
        m.update({"detector": name, "corpus": "csic", "n": int(len(y))})
        rows.append(m)
    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "fusion_nested_csic.csv", index=False)
    result = {
        "corpus": "csic",
        "protocol": "fully nested: outer 5-fold, inner 4-fold base OOF, stacker and threshold inside outer-train",
        "n": int(len(y)),
        "thresholds": thresholds,
        "metrics": frame.to_dict("records"),
        "elapsed_seconds": round(time.time() - started, 1),
    }
    C.write_json(OUT / "fusion_nested_csic.json", result)
    print(frame[["detector", "accuracy", "fpr", "recall", "f1", "tp", "tn", "fp", "fn"]].to_string(index=False))
    print(f"elapsed {result['elapsed_seconds']}s")


if __name__ == "__main__":
    main()
