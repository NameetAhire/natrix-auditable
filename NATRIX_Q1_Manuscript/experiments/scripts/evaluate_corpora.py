"""In-distribution evaluation of the 22-D contract on each labelled corpus.

Two protocols per corpus:
  P1 stratified over unique requests (deployment-like)
  P2 group-disjoint (endpoint-disjoint), the generalisation bound

Outputs per-corpus metrics and OOF probabilities for later comparison.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix, f1_score
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
from evaluate_featuresets import metrics  # noqa: E402

OUT = C.RESULTS / "corpora"


def metrics_from_pred(y, pred) -> dict:
    pred = np.asarray(pred, dtype=int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    acc = (tp + tn) / (tp + tn + fp + fn)
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    fnr = fn / (fn + tp) if (fn + tp) else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "accuracy": float(acc), "fpr": float(fpr), "fnr": float(fnr),
        "precision": float(precision), "recall": float(recall), "f1": float(f1),
        "tp": int(tp), "tn": int(tn), "fp": int(fp), "fn": int(fn),
    }


def load_corpus(name: str):
    if name == "csic":
        records, _ = C.csic_unique()
        X, _ = C.extract_matrix(records, dtype=np.float32)
        y = C.label_array(records)
        groups = np.asarray([r.group_signature for r in records])
        return X, y, groups
    if name == "srbh":
        z = np.load(C.PROCESSED / "srbh" / "srbh_features.npz", allow_pickle=True)
        return z["X"], z["y"], z["group_ids"].astype(np.int64)
    if name == "ecml":
        records = C.load_ecml_records()
        X, _ = C.extract_matrix(records, dtype=np.float32)
        y = C.label_array(records)
        groups = np.asarray([r.group_signature for r in records])
        return X, y, groups
    raise ValueError(name)


def oof_predict(X, y, groups, protocol: str, seed: int = C.SEED):
    if protocol == "P1":
        splitter = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
        folds = list(splitter.split(X, y))
    else:
        splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
        folds = list(splitter.split(X, y, groups))
    proba = np.zeros(len(y), dtype=np.float32)
    for tr, te in folds:
        model = C.make_rf(random_state=seed)
        model.fit(X[tr], y[tr])
        proba[te] = model.predict_proba(X[te])[:, 1]
    return proba, folds


def best_threshold(proba, y, fpr_cap=None):
    """Largest-F1 threshold, optionally under an FPR cap (inner CV only)."""
    best_t = 0.99 if fpr_cap is not None else 0.5
    best_f1 = -1.0
    for t in np.round(np.arange(0.01, 1.00, 0.01), 2):
        pred = (proba >= t).astype(int)
        tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
        fpr = fp / (fp + tn) if (fp + tn) else 0.0
        if fpr_cap is not None and fpr > fpr_cap:
            continue
        score = f1_score(y, pred, zero_division=0)
        if score > best_f1:
            best_f1, best_t = float(score), float(t)
    return best_t


def nested_predict(X, y, groups, protocol: str, seed: int = C.SEED):
    """Fold-specific thresholds selected by inner CV, test fold scored once."""
    if protocol == "P1":
        outer = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
        folds = list(outer.split(X, y))
    else:
        outer = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
        folds = list(outer.split(X, y, groups))

    proba = np.zeros(len(y), dtype=np.float32)
    preds = {k: np.zeros(len(y), dtype=int) for k in ("f1", "fpr1", "fpr2")}
    thresholds = {k: [] for k in ("f1", "fpr1", "fpr2")}

    for fold, (tr, te) in enumerate(folds):
        if protocol == "P1":
            inner = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed + fold)
            inner_folds = list(inner.split(X[tr], y[tr]))
        else:
            inner = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed + fold)
            inner_folds = list(inner.split(X[tr], y[tr], groups[tr]))
        oof_inner = np.zeros(len(tr), dtype=float)
        for itr, iva in inner_folds:
            model = C.make_rf(random_state=seed)
            model.fit(X[tr][itr], y[tr][itr])
            oof_inner[iva] = model.predict_proba(X[tr][iva])[:, 1]

        t_f1 = best_threshold(oof_inner, y[tr])
        t_fpr1 = best_threshold(oof_inner, y[tr], fpr_cap=0.01)
        t_fpr2 = best_threshold(oof_inner, y[tr], fpr_cap=0.02)
        thresholds["f1"].append(t_f1)
        thresholds["fpr1"].append(t_fpr1)
        thresholds["fpr2"].append(t_fpr2)

        model = C.make_rf(random_state=seed)
        model.fit(X[tr], y[tr])
        proba[te] = model.predict_proba(X[te])[:, 1]
        preds["f1"][te] = (proba[te] >= t_f1).astype(int)
        preds["fpr1"][te] = (proba[te] >= t_fpr1).astype(int)
        preds["fpr2"][te] = (proba[te] >= t_fpr2).astype(int)
        print(f"    fold {fold}: thr_f1={t_f1:.2f} thr_fpr1={t_fpr1:.2f} "
              f"thr_fpr2={t_fpr2:.2f}", flush=True)
    return proba, preds, thresholds


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpora", nargs="+", default=["csic", "ecml", "srbh"])
    parser.add_argument("--protocols", nargs="+", default=["P1", "P2"])
    parser.add_argument("--operating-points", action="store_true",
                        help="also run nested F1/FPR<=1%%/FPR<=2%% threshold selection")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    all_rows = []
    for corpus in args.corpora:
        started = time.time()
        X, y, groups = load_corpus(corpus)
        print(f"{corpus}: X={X.shape} labels={np.bincount(y).tolist()} groups={len(np.unique(groups)):,}", flush=True)
        for protocol in args.protocols:
            if args.operating_points:
                proba, preds, thresholds = nested_predict(X, y, groups, protocol)
                for policy, pred in preds.items():
                    m = metrics_from_pred(y, pred)
                    m.update({"corpus": corpus, "protocol": protocol, "features": "22-D",
                              "policy": policy,
                              "threshold_mean": float(np.mean(thresholds[policy])),
                              "thresholds": ";".join(f"{v:.2f}" for v in thresholds[policy]),
                              "n": int(len(y)), "elapsed_s": round(time.time() - started, 1)})
                    all_rows.append(m)
                np.savez(OUT / f"{corpus}_{protocol}_oof.npz", proba=proba, y=y,
                         **{f"pred_{k}": v for k, v in preds.items()})
                for policy, pred in preds.items():
                    m = metrics_from_pred(y, pred)
                    print(f"  {protocol} [{policy}]: acc={m['accuracy']:.4f} "
                          f"fpr={m['fpr']:.4f} fnr={m['fnr']:.4f} f1={m['f1']:.4f}", flush=True)
            else:
                proba, folds = oof_predict(X, y, groups, protocol)
                m = metrics(y, proba)
                m.update({"corpus": corpus, "protocol": protocol, "features": "22-D",
                          "policy": "threshold_0.5", "n": int(len(y)),
                          "elapsed_s": round(time.time() - started, 1)})
                all_rows.append(m)
                np.savez(OUT / f"{corpus}_{protocol}_oof.npz", proba=proba, y=y)
                print(f"  {protocol}: acc={m['accuracy']:.4f} fpr={m['fpr']:.4f} "
                      f"fnr={m['fnr']:.4f} f1={m['f1']:.4f} auc={m['roc_auc']:.4f}", flush=True)

    frame = pd.DataFrame(all_rows)
    metrics_path = OUT / "corpora_metrics.csv"
    if metrics_path.exists():
        old = pd.read_csv(metrics_path)
        frame = pd.concat([old, frame], ignore_index=True)
        keys = [k for k in ("corpus", "protocol", "policy") if k in frame.columns]
        if keys:
            frame = frame.drop_duplicates(subset=keys, keep="last")
    frame.to_csv(metrics_path, index=False)
    C.write_json(OUT / "corpora_metrics.json", frame.to_dict("records"))
    print(frame[["corpus", "protocol", "policy", "accuracy", "fpr", "fnr", "f1"]].to_string(index=False))


if __name__ == "__main__":
    main()
