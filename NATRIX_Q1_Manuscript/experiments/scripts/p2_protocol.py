"""P2 (endpoint-disjoint) baselines and the SR-BH 20k sample split.

The earlier baseline table used the deployment-like P1 split only.  Lexical
full-request includes the path, so P1 gives it the endpoint prior for free.
This script re-runs the lexical baseline under the *same* endpoint-disjoint
folds used for NATRIX P2 and, for the 20k SR-BH comparison sample, creates the
matching group-disjoint folds and NATRIX out-of-fold scores.

Outputs
-------
experiments/results/baselines/lexical_{corpus}_P2_{view}.json
experiments/results/baselines/lexical_{corpus}_P2_{view}_oof.npz
experiments/results/baselines/srbh20k_P2_folds_seed42.npz
experiments/results/baselines/natrix_srbh_sample20k_P2_oof.npz
experiments/results/baselines/natrix_srbh_sample20k_P2.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.linear_model import SGDClassifier
from sklearn.model_selection import StratifiedGroupKFold

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
from compare_v3_v4 import best_threshold, metrics_from_pred  # noqa: E402

OUT = C.RESULTS / "baselines"
OUT.mkdir(parents=True, exist_ok=True)


def _text(row, view: str) -> str:
    if view == "endpoint":
        return f"{row.method} {row.path}"
    if view == "payload":
        return f"{row.query} {row.body}"
    return f"{row.path} {row.query} {row.body}"


def _srbh_group(row) -> str:
    qkeys = sorted(urllib.parse.parse_qs(row.query, keep_blank_values=True).keys())
    bkeys = (
        sorted(urllib.parse.parse_qs(row.body, keep_blank_values=True).keys())
        if row.body
        else []
    )
    return (
        f"{row.method} {C.ce.normalize_path(row.path)}"
        f"?{','.join(qkeys)}#{','.join(bkeys)}"
    )


def load_corpus(corpus: str):
    if corpus == "csic":
        records, _ = C.csic_unique()
        rows = pd.DataFrame(
            [
                {
                    "method": r.method,
                    "path": r.path,
                    "query": r.query,
                    "body": r.body,
                    "user_agent": r.user_agent,
                    "label": int(r.label),
                }
                for r in records
            ]
        )
        groups = np.asarray([r.group_signature for r in records])
        folds_path = C.RESULTS / "corpora" / "csic_P2_folds_seed42.npz"
    elif corpus == "ecml":
        records = C.load_ecml_records()
        rows = pd.DataFrame(
            [
                {
                    "method": r.method,
                    "path": r.path,
                    "query": r.query,
                    "body": r.body,
                    "user_agent": r.user_agent,
                    "label": int(r.label),
                }
                for r in records
            ]
        )
        groups = np.asarray([r.group_signature for r in records])
        folds_path = C.RESULTS / "corpora" / "ecml_P2_folds_seed42.npz"
    elif corpus == "srbh20k":
        rows = pd.read_parquet(
            OUT / "srbh_sample20k_requests.parquet",
            columns=["method", "path", "query", "body", "user_agent", "label"],
        )
        groups = np.asarray([_srbh_group(r) for r in rows.itertuples(index=False)])
        folds_path = OUT / "srbh20k_P2_folds_seed42.npz"
        if not folds_path.exists():
            splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=C.SEED)
            folds = list(splitter.split(rows, rows.label.to_numpy(), groups))
            np.savez(
                folds_path,
                **{f"tr_{i}": tr for i, (tr, _) in enumerate(folds)},
                **{f"te_{i}": te for i, (_, te) in enumerate(folds)},
            )
            print(f"wrote {folds_path} ({len(folds)} folds, {len(set(groups)):,} groups)")
    else:
        raise ValueError(corpus)

    z = np.load(folds_path, allow_pickle=True)
    folds = [(z[f"tr_{i}"], z[f"te_{i}"]) for i in range(5)]
    y = rows.label.to_numpy(dtype=int)
    assert len(rows) == len(y)
    return rows, y, groups, folds


def lexical_oof(texts, y, folds, view: str, corpus: str) -> dict:
    started = time.time()
    vectorizer = HashingVectorizer(
        analyzer="char_wb",
        ngram_range=(2, 4),
        n_features=2 ** 18,
        alternate_sign=False,
        norm="l2",
        lowercase=True,
    )
    X = vectorizer.transform(texts)
    proba = np.zeros(len(y), dtype=np.float32)
    for k, (tr, te) in enumerate(folds):
        model = SGDClassifier(
            loss="log_loss",
            penalty="l2",
            alpha=1e-5,
            max_iter=30,
            tol=1e-4,
            random_state=C.SEED,
            average=True,
        )
        model.fit(X[tr], y[tr])
        proba[te] = model.predict_proba(X[te])[:, 1]
        print(f"  lexical {corpus}/{view} fold {k}: {time.time() - started:.0f}s", flush=True)

    pred05 = (proba >= 0.5).astype(int)
    pred_fpr2 = np.zeros(len(y), dtype=int)
    thresholds = []
    for tr, te in folds:
        t = best_threshold(proba[tr], y[tr], fpr_cap=0.02)
        pred_fpr2[te] = (proba[te] >= t).astype(int)
        thresholds.append(float(t))

    result = {
        "corpus": corpus,
        "protocol": "P2",
        "view": view,
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
    np.savez(
        OUT / f"lexical_{corpus}_P2_{view}_oof.npz",
        proba=proba,
        y=y,
        folds=np.asarray([te for _, te in folds], dtype=object),
    )
    C.write_json(OUT / f"lexical_{corpus}_P2_{view}.json", result)
    print(
        f"{corpus} P2 {view}: acc={result['fpr2_crossfit']['accuracy']:.4f} "
        f"fpr={result['fpr2_crossfit']['fpr']:.4f} "
        f"recall={result['fpr2_crossfit']['recall']:.4f}"
    )
    return result


def natrix_srbh20k_p2(rows, y, folds) -> dict:
    records = [
        C.make_request(
            rid=str(i),
            source="srbh",
            label=int(row.label),
            method=row.method,
            target=row.path + (("?" + row.query) if row.query else ""),
            body=row.body,
            user_agent=row.user_agent,
        )
        for i, row in enumerate(rows.itertuples(index=False))
    ]
    X, _ = C.extract_matrix(records, dtype=np.float32)
    proba = np.zeros(len(y), dtype=np.float32)
    for k, (tr, te) in enumerate(folds):
        model = C.make_rf(random_state=C.SEED)
        model.fit(X[tr], y[tr])
        proba[te] = model.predict_proba(X[te])[:, 1]
        print(f"  natrix srbh20k P2 fold {k}", flush=True)

    pred05 = (proba >= 0.5).astype(int)
    pred_fpr2 = np.zeros(len(y), dtype=int)
    thresholds = []
    for tr, te in folds:
        t = best_threshold(proba[tr], y[tr], fpr_cap=0.02)
        pred_fpr2[te] = (proba[te] >= t).astype(int)
        thresholds.append(float(t))

    result = {
        "corpus": "srbh20k",
        "protocol": "P2",
        "limit": 20000,
        "n": int(len(y)),
        "threshold_0.5": metrics_from_pred(y, pred05),
        "fpr2_crossfit": {
            **metrics_from_pred(y, pred_fpr2),
            "threshold_mean": float(np.mean(thresholds)),
            "thresholds": thresholds,
        },
    }
    np.savez(
        OUT / "natrix_srbh_sample20k_P2_oof.npz",
        proba=proba,
        y=y,
        folds=np.asarray([te for _, te in folds], dtype=object),
    )
    C.write_json(OUT / "natrix_srbh_sample20k_P2.json", result)
    print(
        f"NATRIX srbh20k P2: acc={result['fpr2_crossfit']['accuracy']:.4f} "
        f"fpr={result['fpr2_crossfit']['fpr']:.4f} "
        f"recall={result['fpr2_crossfit']['recall']:.4f}"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", choices=["csic", "ecml", "srbh20k"], required=True)
    parser.add_argument("--views", nargs="+", default=["full", "payload", "endpoint"])
    args = parser.parse_args()

    rows, y, groups, folds = load_corpus(args.corpus)
    print(
        f"{args.corpus}: n={len(y):,} groups={len(set(groups)):,} "
        f"labels={np.bincount(y).tolist()}"
    )

    if args.corpus == "srbh20k":
        natrix_srbh20k_p2(rows, y, folds)

    for view in args.views:
        texts = [_text(row, view) for row in rows.itertuples(index=False)]
        lexical_oof(texts, y, folds, view, args.corpus)


if __name__ == "__main__":
    main()
