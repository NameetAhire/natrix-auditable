"""The reviewer control: lexical + a generic GBM, not another NATRIX variant.

Question
--------
The strongest result is NATRIX + lexical.  Is that gain specific to NATRIX, or
does stacking *any* second, different model recover it?  This script trains a
generic gradient-boosted model on request-shape/statistical features that are
deliberately *not* NATRIX's curated security contract, then applies the same
cross-fitted logistic stacker and matched-FPR policy used for NATRIX.

Generic control features (17)
-----------------------------
method id, path/query/body/total length, path depth, query/body parameter
counts, body-to-URL ratio, special-character ratio, digit ratio, uppercase
ratio, Shannon entropy, longest token, mean value length, has-query, has-body.

These are ordinary request-shape descriptors.  They contain no SQL/XSS/
traversal keyword scores, no scanner User-Agent list, and no NATRIX feature.

Protocol
--------
* Base scores are out-of-fold predictions on identical rows and folds.
* The stacker is fitted on four folds and applied to the fifth.
* Thresholds are selected leave-one-fold-out at FPR <= 2%.
* The control stack is lexical + generic GBM.  The NATRIX stack is
  NATRIX + lexical.  A third stack adds all three.

Outputs
-------
experiments/results/baselines/control_{corpus}_{protocol}.json
experiments/results/baselines/control_{corpus}_{protocol}.csv
experiments/results/baselines/generic_{corpus}_{protocol}_oof.npz
"""

from __future__ import annotations

import argparse
import math
import sys
import urllib.parse
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import stats_utils as S  # noqa: E402
from compare_v3_v4 import best_threshold, metrics_from_pred  # noqa: E402
from p2_protocol import load_corpus  # noqa: E402

OUT = C.RESULTS / "baselines"
OUT.mkdir(parents=True, exist_ok=True)

METHODS = {"GET": 0, "POST": 1, "PUT": 2, "DELETE": 3, "PATCH": 4, "HEAD": 5, "OPTIONS": 6}


def _entropy(text: str) -> float:
    if not text:
        return 0.0
    counts = Counter(text)
    n = len(text)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def generic_vector(row) -> list[float]:
    method = str(row.method or "GET").upper()
    path = str(row.path or "")
    query = str(row.query or "")
    body = str(row.body or "")
    target = path + (("?" + query) if query else "")
    text = target + ((" " + body) if body else "")
    length = max(1, len(text))
    qpairs = urllib.parse.parse_qsl(query, keep_blank_values=True)
    bpairs = urllib.parse.parse_qsl(body, keep_blank_values=True)
    values = [v for _, v in qpairs + bpairs]
    special = sum(1 for ch in text if not ch.isalnum() and not ch.isspace())
    digits = sum(1 for ch in text if ch.isdigit())
    upper = sum(1 for ch in text if ch.isupper())
    tokens = text.split()
    longest = max((len(tok) for tok in tokens), default=0)
    mean_value = float(np.mean([len(v) for v in values])) if values else 0.0
    return [
        float(METHODS.get(method, 7)),
        float(len(path)),
        float(len(query)),
        float(len(body)),
        float(len(text)),
        float(path.count("/")),
        float(len(qpairs)),
        float(len(bpairs)),
        float(len(body) / (len(target) + 1)),
        float(special / length),
        float(digits / length),
        float(upper / length),
        float(_entropy(text)),
        float(longest),
        float(mean_value),
        1.0 if query else 0.0,
        1.0 if body else 0.0,
    ]


def load_rows(corpus: str) -> pd.DataFrame:
    if corpus in ("csic", "ecml", "srbh20k"):
        rows, _, _, _ = load_corpus(corpus)
        return rows
    raise ValueError(corpus)


def fold_sets(corpus: str, protocol: str, n: int):
    if corpus in ("csic", "ecml"):
        path = C.RESULTS / "corpora" / f"{corpus}_{protocol}_folds_seed42.npz"
        z = np.load(path, allow_pickle=True)
        return [(z[f"tr_{i}"], z[f"te_{i}"]) for i in range(5)]
    if corpus == "srbh20k":
        if protocol == "P1":
            z = np.load(OUT / "natrix_srbh_sample20k_oof.npz", allow_pickle=True)
            return [(np.setdiff1d(np.arange(n), te), np.asarray(te, dtype=int)) for te in z["folds"]]
        z = np.load(OUT / "srbh20k_P2_folds_seed42.npz", allow_pickle=True)
        return [(z[f"tr_{i}"], z[f"te_{i}"]) for i in range(5)]
    raise ValueError(corpus)


def base_scores(corpus: str, protocol: str, n: int, lexical_view: str = "full"):
    if corpus in ("csic", "ecml"):
        nz = np.load(C.RESULTS / "corpora" / f"{corpus}_{protocol}_oof.npz", allow_pickle=True)
        lexical_name = (
            f"lexical_{corpus}_{lexical_view}_oof.npz"
            if protocol == "P1"
            else f"lexical_{corpus}_{protocol}_{lexical_view}_oof.npz"
        )
        lz = np.load(OUT / lexical_name, allow_pickle=True)
    else:
        nz = np.load(
            OUT / ("natrix_srbh_sample20k_oof.npz" if protocol == "P1" else "natrix_srbh_sample20k_P2_oof.npz"),
            allow_pickle=True,
        )
        lexical_name = (
            f"lexical_srbh_{lexical_view}_oof.npz"
            if protocol == "P1"
            else f"lexical_srbh20k_P2_{lexical_view}_oof.npz"
        )
        lz = np.load(OUT / lexical_name, allow_pickle=True)
    y = nz["y"].astype(int)
    if not np.array_equal(y, lz["y"].astype(int)):
        raise SystemExit("base score labels are not aligned")
    # Keep the base scores in the dtype produced by the forest.  Casting to
    # float64 moves a handful of probabilities across the 0.01 threshold grid
    # and changes the matched-FPR point by ~0.03 pp (95.55 -> 95.52 on CSIC).
    return nz["proba"].astype(np.float32), lz["proba"].astype(np.float32), y


def generic_oof(rows: pd.DataFrame, y: np.ndarray, folds) -> np.ndarray:
    import lightgbm as lgb

    X = np.asarray([generic_vector(r) for r in rows.itertuples(index=False)], dtype=np.float32)
    proba = np.zeros(len(y), dtype=np.float64)
    for k, (tr, te) in enumerate(folds):
        model = lgb.LGBMClassifier(
            n_estimators=300,
            learning_rate=0.05,
            num_leaves=31,
            min_child_samples=20,
            subsample=0.9,
            colsample_bytree=0.9,
            random_state=C.SEED,
            n_jobs=4,
            verbosity=-1,
            deterministic=True,
            force_col_wise=True,
        )
        model.fit(X[tr], y[tr])
        proba[te] = model.predict_proba(X[te])[:, 1]
        print(f"  generic {k}: done", flush=True)
    return proba


def logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p.astype(np.float64), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def crossfit_threshold(proba: np.ndarray, y: np.ndarray, folds, cap: float = 0.02):
    pred = np.zeros(len(y), dtype=int)
    thresholds = []
    for tr, te in folds:
        t = best_threshold(proba[tr], y[tr], fpr_cap=cap)
        pred[te] = (proba[te] >= t).astype(int)
        thresholds.append(float(t))
    return pred, thresholds


def stack_scores(columns, y, folds):
    features = np.column_stack([logit(c) for c in columns])
    out = np.zeros(len(y), dtype=np.float64)
    for tr, te in folds:
        model = LogisticRegression(C=1.0, max_iter=1000)
        model.fit(features[tr], y[tr])
        out[te] = model.predict_proba(features[te])[:, 1]
    return out


def paired(a, b, mask):
    lo, hi = S.paired_bootstrap_delta(
        (a[mask] == 1).astype(float), (b[mask] == 1).astype(float)
    )
    return {
        "delta": float((a[mask] == 1).mean() - (b[mask] == 1).mean()),
        "ci_lo": lo,
        "ci_hi": hi,
        "mcnemar": S.mcnemar(a[mask] == 1, b[mask] == 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", choices=["csic", "ecml", "srbh20k"], required=True)
    parser.add_argument("--protocol", choices=["P1", "P2"], required=True)
    parser.add_argument("--lexical-view", choices=["full", "payload", "endpoint"], default="full")
    args = parser.parse_args()

    rows = load_rows(args.corpus)
    n = len(rows)
    folds = fold_sets(args.corpus, args.protocol, n)
    natrix, lexical, y = base_scores(args.corpus, args.protocol, n, args.lexical_view)
    assert len(y) == n

    gpath = OUT / f"generic_{args.corpus}_{args.protocol}_oof.npz"
    if gpath.exists():
        generic = np.load(gpath, allow_pickle=True)["proba"].astype(np.float32)
    else:
        generic = generic_oof(rows, y, folds)
        np.savez(gpath, proba=generic, y=y, folds=np.asarray([te for _, te in folds], dtype=object))

    stack_nl = stack_scores([natrix, lexical], y, folds)
    stack_gl = stack_scores([generic, lexical], y, folds)
    stack_ngl = stack_scores([natrix, generic, lexical], y, folds)

    scores = {
        "natrix": natrix,
        "lexical": lexical,
        "generic": generic,
        "stack_natrix_lexical": stack_nl,
        "stack_generic_lexical": stack_gl,
        "stack_natrix_generic_lexical": stack_ngl,
    }
    preds = {}
    thresholds = {}
    for name, score in scores.items():
        preds[name], thresholds[name] = crossfit_threshold(score, y, folds)

    rows_out = []
    for name, pred in preds.items():
        m = metrics_from_pred(y, pred)
        m.update({"detector": name, "corpus": args.corpus, "protocol": args.protocol, "n": n})
        rows_out.append(m)
    frame = pd.DataFrame(rows_out)
    suffix = f"{args.corpus}_{args.protocol}_{args.lexical_view}"
    frame.to_csv(OUT / f"control_{suffix}.csv", index=False)

    attack = y == 1
    clean = y == 0
    result = {
        "corpus": args.corpus,
        "protocol": args.protocol,
        "lexical_view": args.lexical_view,
        "n": n,
        "thresholds": thresholds,
        "metrics": frame.to_dict("records"),
        "stack_natrix_vs_lexical": {
            "accuracy": paired(preds["stack_natrix_lexical"] == y, preds["lexical"] == y, np.ones(n, bool)),
            "recall": paired(preds["stack_natrix_lexical"], preds["lexical"], attack),
            "fpr": paired(preds["stack_natrix_lexical"], preds["lexical"], clean),
        },
        "stack_generic_vs_lexical": {
            "accuracy": paired(preds["stack_generic_lexical"] == y, preds["lexical"] == y, np.ones(n, bool)),
            "recall": paired(preds["stack_generic_lexical"], preds["lexical"], attack),
            "fpr": paired(preds["stack_generic_lexical"], preds["lexical"], clean),
        },
        "stack_natrix_vs_generic": {
            "accuracy": paired(preds["stack_natrix_lexical"] == y, preds["stack_generic_lexical"] == y, np.ones(n, bool)),
            "recall": paired(preds["stack_natrix_lexical"], preds["stack_generic_lexical"], attack),
            "fpr": paired(preds["stack_natrix_lexical"], preds["stack_generic_lexical"], clean),
        },
    }
    C.write_json(OUT / f"control_{suffix}.json", result)
    print(frame[["detector", "accuracy", "fpr", "recall", "f1", "tp", "tn", "fp", "fn"]].to_string(index=False))
    print("NATRIX stack vs lexical:", result["stack_natrix_vs_lexical"])
    print("generic stack vs lexical:", result["stack_generic_vs_lexical"])
    print("NATRIX stack vs generic stack:", result["stack_natrix_vs_generic"])


if __name__ == "__main__":
    main()
