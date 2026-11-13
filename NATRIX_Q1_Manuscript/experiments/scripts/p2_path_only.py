"""P2 sensitivity: group by normalized path only.

The main P2 protocol groups by method + normalized path + sorted query/body
parameter names.  That is the strictest *endpoint* definition that still lets
the same path appear with different parameter names.  A reviewer asked whether
the ranking survives a coarser, path-only grouping, which is stricter because
every request to the same normalized path must stay in one fold.

This script rebuilds the folds with path-only groups, reruns NATRIX and the
lexical full/payload baselines under the same cross-fitted FPR <= 2% policy,
and reports group size and label purity for both definitions.

Outputs
-------
experiments/results/baselines/p2_path_only_{corpus}.json
experiments/results/baselines/p2_path_only_{corpus}_folds.npz
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


def _path_group(row) -> str:
    return f"{row.method} {C.ce.normalize_path(row.path)}"


def load_rows(corpus: str) -> pd.DataFrame:
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
                    "endpoint_group": r.group_signature,
                }
                for r in records
            ]
        )
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
                    "endpoint_group": r.group_signature,
                }
                for r in records
            ]
        )
    elif corpus == "srbh20k":
        rows = pd.read_parquet(
            OUT / "srbh_sample20k_requests.parquet",
            columns=["method", "path", "query", "body", "user_agent", "label"],
        )
        rows["endpoint_group"] = [
            f"{r.method} {C.ce.normalize_path(r.path)}?"
            f"{','.join(sorted(urllib.parse.parse_qs(r.query, keep_blank_values=True).keys()))}"
            f"#{','.join(sorted(urllib.parse.parse_qs(r.body, keep_blank_values=True).keys())) if r.body else ''}"
            for r in rows.itertuples(index=False)
        ]
    else:
        raise ValueError(corpus)
    return rows


def group_stats(rows: pd.DataFrame, groups: np.ndarray) -> dict:
    sizes = pd.Series(groups).value_counts()
    frame = pd.DataFrame({"group": groups, "label": rows.label.to_numpy()})
    mixed = frame.groupby("group")["label"].nunique() > 1
    rows_in_mixed = frame.groupby("group")["label"].transform("nunique").gt(1).sum()
    return {
        "n_rows": int(len(rows)),
        "n_groups": int(len(sizes)),
        "median_group_size": float(sizes.median()),
        "p95_group_size": float(sizes.quantile(0.95)),
        "max_group_size": int(sizes.max()),
        "n_mixed_groups": int(mixed.sum()),
        "pct_mixed_groups": float(mixed.mean() * 100),
        "pct_rows_in_mixed_groups": float(rows_in_mixed / len(rows) * 100),
    }


def natrix_oof(rows, y, folds, corpus: str) -> dict:
    started = time.time()
    records = [
        C.make_request(
            rid=str(i),
            source=corpus,
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
        print(f"  natrix {corpus} fold {k}: {time.time() - started:.0f}s", flush=True)

    pred = np.zeros(len(y), dtype=int)
    thresholds = []
    for tr, te in folds:
        t = best_threshold(proba[tr], y[tr], fpr_cap=0.02)
        pred[te] = (proba[te] >= t).astype(int)
        thresholds.append(float(t))
    return {
        "view": "natrix",
        "metrics": {
            **metrics_from_pred(y, pred),
            "threshold_mean": float(np.mean(thresholds)),
            "thresholds": thresholds,
        },
    }


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

    pred = np.zeros(len(y), dtype=int)
    thresholds = []
    for tr, te in folds:
        t = best_threshold(proba[tr], y[tr], fpr_cap=0.02)
        pred[te] = (proba[te] >= t).astype(int)
        thresholds.append(float(t))
    return {
        "view": f"lexical_{view}",
        "metrics": {
            **metrics_from_pred(y, pred),
            "threshold_mean": float(np.mean(thresholds)),
            "thresholds": thresholds,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", choices=["csic", "ecml", "srbh20k"], required=True)
    parser.add_argument("--views", nargs="+", default=["full", "payload"])
    args = parser.parse_args()

    rows = load_rows(args.corpus)
    y = rows.label.to_numpy(dtype=int)
    path_groups = np.asarray([_path_group(r) for r in rows.itertuples(index=False)])
    endpoint_groups = rows.endpoint_group.to_numpy()

    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=C.SEED)
    folds = list(splitter.split(rows, y, path_groups))
    np.savez(
        OUT / f"p2_path_only_{args.corpus}_folds.npz",
        **{f"tr_{i}": tr for i, (tr, _) in enumerate(folds)},
        **{f"te_{i}": te for i, (_, te) in enumerate(folds)},
    )

    # Verify that no normalized path appears in both train and test.
    overlap = []
    for tr, te in folds:
        overlap.append(len(set(path_groups[tr]) & set(path_groups[te])))
    print(f"{args.corpus}: n={len(y):,} path_groups={len(set(path_groups)):,} "
          f"endpoint_groups={len(set(endpoint_groups)):,} "
          f"train/test overlap={overlap}", flush=True)

    result = {
        "corpus": args.corpus,
        "protocol": "P2-path-only",
        "n": int(len(y)),
        "path_grouping": group_stats(rows, path_groups),
        "endpoint_grouping": group_stats(rows, endpoint_groups),
        "train_test_path_overlap": overlap,
        "detectors": [],
    }
    result["detectors"].append(natrix_oof(rows, y, folds, args.corpus))
    for view in args.views:
        texts = [_text(row, view) for row in rows.itertuples(index=False)]
        result["detectors"].append(lexical_oof(texts, y, folds, view, args.corpus))

    C.write_json(OUT / f"p2_path_only_{args.corpus}.json", result)
    print(json.dumps(result["detectors"], indent=2))


if __name__ == "__main__":
    main()
