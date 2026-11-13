"""Lexical linear baseline and endpoint-prior diagnostic.

Two questions:

* How much of the P1 result can a request-line-only model recover?  If a model
  that never sees the query or body is competitive, the headline number is
  mostly an endpoint prior.
* How does a standard character n-gram linear learner compare with NATRIX when
  it sees the full request text?

The learner is a hashed character n-gram representation (2-4 grams) with an
L2-regularised logistic-loss SGD classifier.  It is deliberately simple,
single-pass, and untuned; the point is a reference point, not a new model.

Views
-----
endpoint : method + path only (no query, no body)
payload  : query + body only (no path)
full     : path + query + body

Outputs
-------
experiments/results/baselines/lexical_{corpus}_{view}.json
experiments/results/baselines/lexical_{corpus}_{view}_oof.npz
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import StratifiedKFold

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
from compare_v3_v4 import best_threshold, metrics_from_pred  # noqa: E402

OUT = C.RESULTS / "baselines"
OUT.mkdir(parents=True, exist_ok=True)


def load_text(corpus: str, view: str, limit: int | None):
    if corpus == "csic":
        records, _ = C.csic_unique()
        rows = [{
            "method": r.method, "path": r.path, "query": r.query,
            "body": r.body, "label": int(r.label),
        } for r in records]
    elif corpus == "ecml":
        records = C.load_ecml_records()
        rows = [{
            "method": r.method, "path": r.path, "query": r.query,
            "body": r.body, "label": int(r.label),
        } for r in records]
    elif corpus == "srbh":
        frame = pd.read_parquet(
            C.PROCESSED / "srbh" / "srbh_requests.parquet",
            columns=["method", "path", "query", "body", "label"],
        )
        rows = frame.to_dict("records")
    elif corpus == "wcp":
        path = OUT / "wcp_sample20k_requests.parquet"
        if not path.exists():
            raise SystemExit(f"missing {path}; run evaluate_wcp_sample.py")
        frame = pd.read_parquet(
            path, columns=["method", "path", "query", "body", "label"]
        )
        rows = frame.to_dict("records")
    else:
        raise ValueError(corpus)

    frame = pd.DataFrame.from_records(rows)
    if corpus == "wcp":
        # The saved sample is already the shared 20k comparison set; do not
        # resample it or the detectors will no longer see identical rows.
        limit = None
    if limit is not None and limit < len(frame):
        parts = []
        for label, group in frame.groupby("label"):
            take = max(1, int(round(limit * len(group) / len(frame))))
            parts.append(group.sample(n=min(take, len(group)), random_state=C.SEED))
        frame = pd.concat(parts).sample(frac=1.0, random_state=C.SEED).reset_index(drop=True)

    def make_text(row):
        if view == "endpoint":
            return f"{row.method} {row.path}"
        if view == "payload":
            return f"{row.query} {row.body}"
        return f"{row.path} {row.query} {row.body}"

    return [make_text(r) for r in frame.itertuples(index=False)], frame.label.to_numpy(dtype=int)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", choices=["csic", "ecml", "srbh", "wcp"], required=True)
    parser.add_argument("--view", choices=["endpoint", "payload", "full"], required=True)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--folds", type=int, default=5)
    args = parser.parse_args()

    started = time.time()
    texts, y = load_text(args.corpus, args.view, args.limit)
    print(f"{args.corpus}/{args.view}: {len(y):,} rows", flush=True)

    vectorizer = HashingVectorizer(
        analyzer="char_wb",
        ngram_range=(2, 4),
        n_features=2 ** 18,
        alternate_sign=False,
        norm="l2",
        lowercase=True,
    )
    X = vectorizer.transform(texts)
    print(f"  hashed matrix: {X.shape}, nnz={X.nnz:,}", flush=True)

    folds = list(StratifiedKFold(
        n_splits=args.folds, shuffle=True, random_state=C.SEED
    ).split(X, y))
    proba = np.zeros(len(y), dtype=np.float32)
    for k, (tr, te) in enumerate(folds):
        model = SGDClassifier(
            loss="log_loss", penalty="l2", alpha=1e-5, max_iter=30,
            tol=1e-4, random_state=C.SEED, average=True,
        )
        model.fit(X[tr], y[tr])
        proba[te] = model.predict_proba(X[te])[:, 1]
        print(f"  fold {k}: {time.time() - started:.0f}s", flush=True)

    pred05 = (proba >= 0.5).astype(int)
    pred_fpr2 = np.zeros(len(y), dtype=int)
    thresholds = []
    for _, te in folds:
        mask = np.ones(len(y), dtype=bool)
        mask[te] = False
        t = best_threshold(proba[mask], y[mask], fpr_cap=0.02)
        pred_fpr2[te] = (proba[te] >= t).astype(int)
        thresholds.append(t)

    result = {
        "corpus": args.corpus, "view": args.view, "limit": args.limit,
        "learner": "HashingVectorizer(char_wb 2-4, 2^18) + SGD log-loss",
        "elapsed_seconds": round(time.time() - started, 1),
        "threshold_0.5": metrics_from_pred(y, pred05),
        "fpr2_crossfit": {
            **metrics_from_pred(y, pred_fpr2),
            "threshold_mean": float(np.mean(thresholds)),
            "thresholds": ";".join(f"{t:.2f}" for t in thresholds),
        },
        "n": int(len(y)),
    }
    np.savez(OUT / f"lexical_{args.corpus}_{args.view}_oof.npz", proba=proba, y=y,
             folds=np.asarray([te for _, te in folds], dtype=object))
    C.write_json(OUT / f"lexical_{args.corpus}_{args.view}.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
