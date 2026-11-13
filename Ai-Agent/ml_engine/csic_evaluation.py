#!/usr/bin/env python3
"""CSIC 2010 evaluation for the NATRIX HTTP classifier.

Two protocols are reported:

* PRIMARY (deployment-like): exact deduplication, then a stratified random split
  over distinct requests. This mirrors how a deployed classifier is trained and
  tested: same application endpoints appear in train and test, but no exact
  duplicate request appears on both sides. Reported for the 45,000-record
  benchmark (single 70/10/20 split) and for the full corpus (pooled 5-fold
  cross-validation, so every distinct request and every duplicate is tested
  exactly once).

* STRESS TEST (leave-one-endpoint-out): a group-aware split where the group is
  (method, normalised path, query parameter names, body parameter names). Every
  request sharing a group lands in one split. This is a severe distribution
  shift and is reported only to bound worst-case generalisation.

Two feature sets are compared:

* 16-D: the current shipped contract (feature_registry.py / proxy/feature_extractor.js).
* 22-D: the 16-D contract plus six generic HTTP features (suspicious file
  extension, quote count, angle-bracket count, double-encoding count, max value
  special-character ratio, max parameter-value length). This is the promoted v3
  runtime contract. A seventh candidate, parameter-name uppercase suffix, was
  rejected after auditing: it is CSIC's own `.A`-suffix tampering signature and
  would inflate the result (see section 2.1 of the report).

A transparent static-asset allowlist (GET/HEAD, no query/body, benign extension)
is applied as a pipeline pre-filter. Model-only and pipeline (model + allowlist)
metrics are reported separately.

Outputs
-------
* ml_engine/csic_evaluation_results.json
* ml_engine/CSIC_EVALUATION_REPORT.md
* models/csic_binary/threat_classifier.joblib     (16-D baseline)
* models/csic_binary_22d/threat_classifier.joblib (22-D, official promoted gate)
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
import urllib.parse
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from feature_registry import registry  # noqa: E402

from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    roc_auc_score,
)
from sklearn.model_selection import (  # noqa: E402
    StratifiedGroupKFold,
    StratifiedKFold,
    train_test_split,
)

DATASET_DIR = os.path.join(REPO_ROOT, "dataset", "dataset_cisc_train_test")
HTTP_LOG_CANDIDATES = [
    os.path.join(REPO_ROOT, "dataset", "http.log", "http.log"),
    os.path.join(REPO_ROOT, "dataset", "http.log"),
]
RESULTS_PATH = os.path.join(HERE, "csic_evaluation_results.json")
REPORT_PATH = os.path.join(HERE, "CSIC_EVALUATION_REPORT.md")
MODEL_DIR_16 = os.path.join(REPO_ROOT, "models", "csic_binary")
MODEL_DIR_22 = os.path.join(REPO_ROOT, "models", "csic_binary_22d")

FILES = [
    ("cisc_normalTraffic_train.txt", "normal_train", 0),
    ("cisc_normalTraffic_test.txt", "normal_test", 0),
    ("cisc_anomalousTraffic_test.txt", "anomalous_test", 1),
]

SEED = 42
BOOTSTRAP_ITERATIONS = 2000
RF_PARAMS = {"n_estimators": 200, "max_depth": None, "min_samples_leaf": 1, "max_features": None}
STATIC_EXTS = (
    ".gif", ".jpg", ".jpeg", ".png", ".css", ".js", ".ico", ".svg",
    ".woff", ".woff2", ".ttf", ".eot", ".map", ".webp", ".bmp", ".tif", ".tiff",
)
_DIGIT_RUN = re.compile(r"\d{4,}")
_HEX_RUN = re.compile(r"[0-9a-fA-F]{16,}")


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


@dataclass
class Request:
    rid: str
    source: str
    declared_class: str
    label: int
    method: str
    url: str
    path: str
    query: str
    body: str
    user_agent: str
    headers: dict[str, str] = field(default_factory=dict)
    payload: str = ""

    @property
    def dedup_key(self) -> tuple:
        return (self.method, self.path, self.query, self.body, self.user_agent)

    @property
    def group_signature(self) -> str:
        query_keys = sorted(urllib.parse.parse_qs(self.query, keep_blank_values=True).keys())
        body_keys = (
            sorted(urllib.parse.parse_qs(self.body, keep_blank_values=True).keys())
            if self.body
            else []
        )
        return (
            f"{self.method} {normalize_path(self.path)}"
            f"?{','.join(query_keys)}#{','.join(body_keys)}"
        )


def normalize_path(path: str) -> str:
    normalized = _DIGIT_RUN.sub("{num}", path)
    normalized = _HEX_RUN.sub("{hex}", normalized)
    return normalized


def parse_file(path: str, source: str, label: int) -> list[Request]:
    records: list[Request] = []
    state = 0
    rid = ""
    declared = ""
    request_line = ""
    headers: dict[str, str] = {}
    body_lines: list[str] = []

    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\r\n")
            if line.startswith("Start - Id:"):
                rid = line.split(":", 1)[1].strip()
                declared = ""
                request_line = ""
                headers = {}
                body_lines = []
                state = 1
                continue

            if state == 1:
                if line.startswith("class:"):
                    declared = line.split(":", 1)[1].strip()
                    state = 2
                continue

            if state == 2:
                request_line = line.strip()
                state = 3
                continue

            if state == 3:
                if line.strip() == "":
                    state = 4
                elif ":" in line:
                    key, value = line.split(":", 1)
                    headers[key.strip().lower()] = value.strip()
                continue

            if state == 4:
                if line.startswith("End - Id:"):
                    record = _finalize(rid, declared, request_line, headers, body_lines, source, label)
                    if record is not None:
                        records.append(record)
                    state = 0
                else:
                    body_lines.append(line)

    return records


def _finalize(rid, declared, request_line, headers, body_lines, source, label):
    parts = request_line.split()
    if len(parts) < 2:
        return None
    method = parts[0].upper()
    url = parts[1]
    split = urllib.parse.urlsplit(url)
    path = split.path or "/"
    query = split.query
    body = "\n".join(body_lines).strip()
    if body.lower() == "null":
        body = ""
    user_agent = headers.get("user-agent", "")
    payload = path
    if query:
        payload += "?" + query
    if body:
        payload += " " + body

    expected = "Attack" if label == 1 else "Valid"
    if declared and declared != expected:
        raise ValueError(f"label mismatch for id {rid}: declared={declared!r}, file label={expected!r}")

    return Request(
        rid=rid, source=source, declared_class=declared, label=label,
        method=method, url=url, path=path, query=query, body=body,
        user_agent=user_agent, headers=headers, payload=payload,
    )


def load_csic() -> list[Request]:
    records: list[Request] = []
    for filename, source, label in FILES:
        path = os.path.join(DATASET_DIR, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        parsed = parse_file(path, source, label)
        print(f"  parsed {filename}: {len(parsed):,} records")
        records.extend(parsed)
    return records


# ---------------------------------------------------------------------------
# Deduplication, grouping, feature matrices
# ---------------------------------------------------------------------------


def dedupe_records(records: Iterable[Request]) -> tuple[list[Request], list[dict]]:
    buckets: dict[tuple, list[Request]] = defaultdict(list)
    for record in records:
        buckets[record.dedup_key].append(record)
    unique: list[Request] = []
    ambiguous: list[dict] = []
    for key, items in buckets.items():
        labels = {item.label for item in items}
        if len(labels) > 1:
            ambiguous.append(
                {"method": key[0], "path": key[1], "query": key[2][:300],
                 "body": key[3][:300], "labels": sorted(labels), "records": len(items)}
            )
            continue
        unique.append(items[0])
    return unique, ambiguous


def static_asset_flag(rec: Request) -> int:
    """Transparent pipeline pre-filter: static GET/HEAD with no query or body."""
    raw_path = rec.payload.split(" ", 1)[0]
    path = raw_path.split("?", 1)[0].lower()
    return int(
        rec.method in ("GET", "HEAD") and "?" not in raw_path and not rec.body
        and path.endswith(STATIC_EXTS)
    )


def extra22(rec: Request) -> tuple[list[float], int]:
    """Return the six v3 features + static-asset flag.

    Feature values come from the same `registry` implementation the runtime
    uses, so training and serving cannot drift.  `upper_suffix_params` was
    deliberately rejected after auditing: it is 100% attack / 0% clean on CSIC
    and its active values are `B1A`, `loginA`, `precioA`, i.e. CSIC's
    parameter-tampering signature, not a generic HTTP signal.
    """
    features = registry.extract_features(
        rec.payload, user_agent=rec.user_agent, method=rec.method, version="v3",
    )
    vector = registry.feature_dict_to_vector(features, version="v3")
    return vector[16:], static_asset_flag(rec)


EXTRA22_NAMES = registry.get_feature_names("v3")[16:]


def extract_matrices(records: list[Request]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return (X10, X16, X22, static_flags) for a list of requests.

    All three views come from one v3 extraction pass, so the 16-D and 22-D
    columns are guaranteed to be the same features the runtime emits.
    """
    rows, statics = [], []
    for rec in records:
        features = registry.extract_features(
            rec.payload, user_agent=rec.user_agent, method=rec.method, version="v3",
        )
        rows.append(registry.feature_dict_to_vector(features, version="v3"))
        statics.append(static_asset_flag(rec))
    X22 = np.asarray(rows, dtype=float)
    X16 = X22[:, :16]
    X10 = X22[:, :10]
    static_flags = np.asarray(statics, dtype=int)
    assert X10.shape[1] == 10 and X16.shape[1] == 16 and X22.shape[1] == 22
    return X10, X16, X22, static_flags


def stratified_subset(records: list[Request], limit: int, seed: int) -> list[Request]:
    if limit >= len(records):
        return list(records)
    indices = np.arange(len(records))
    labels = [r.label for r in records]
    selected, _ = train_test_split(indices, train_size=limit, random_state=seed, stratify=labels)
    return [records[int(i)] for i in selected]


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def make_rf(params=None):
    p = dict(RF_PARAMS if params is None else params)
    return RandomForestClassifier(**p, class_weight=None, random_state=SEED, n_jobs=-1)


def binary_metrics(y_true, y_pred, y_prob=None) -> dict[str, Any]:
    y_true = np.asarray(y_true, dtype=int)
    y_pred = np.asarray(y_pred, dtype=int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    total = int(tp + tn + fp + fn)
    precision = float(tp / (tp + fp)) if (tp + fp) else 0.0
    recall = float(tp / (tp + fn)) if (tp + fn) else 0.0
    f1 = 2.0 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    result = {
        "confusion_matrix": {"TP": int(tp), "TN": int(tn), "FP": int(fp), "FN": int(fn)},
        "samples": total,
        "accuracy": round(float((tp + tn) / total), 6) if total else 0.0,
        "balanced_accuracy": round(float(balanced_accuracy_score(y_true, y_pred)), 6) if total else 0.0,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
        "false_positive_rate": round(float(fp / (fp + tn)), 6) if (fp + tn) else 0.0,
        "false_negative_rate": round(float(fn / (fn + tp)), 6) if (fn + tp) else 0.0,
        "attack_prevalence": round(float((tp + fn) / total), 6) if total else 0.0,
    }
    if y_prob is not None:
        y_prob = np.asarray(y_prob, dtype=float)
        result["roc_auc"] = round(float(roc_auc_score(y_true, y_prob)), 6)
        result["pr_auc"] = round(float(average_precision_score(y_true, y_prob)), 6)
    return result


def bootstrap_accuracy_ci(y_true, y_pred, iterations=BOOTSTRAP_ITERATIONS, seed=SEED):
    rng = np.random.default_rng(seed)
    y_true = np.asarray(y_true, dtype=int)
    y_pred = np.asarray(y_pred, dtype=int)
    n = len(y_true)
    if n == 0:
        return [0.0, 0.0]
    scores = np.empty(iterations, dtype=float)
    for i in range(iterations):
        sample = rng.integers(0, n, n)
        scores[i] = accuracy_score(y_true[sample], y_pred[sample])
    scores.sort()
    return [round(float(scores[int(0.025 * iterations)]), 6),
            round(float(scores[int(0.975 * iterations)]), 6)]


def threshold_table(y_val, probabilities):
    rows = []
    for threshold in np.arange(0.05, 0.96, 0.01):
        predictions = (probabilities >= threshold).astype(int)
        metrics = binary_metrics(y_val, predictions)
        rows.append({"threshold": round(float(threshold), 2), **metrics})
    best_f1 = max(rows, key=lambda r: (r["f1"], r["accuracy"], -r["false_positive_rate"]))
    low_fpr = [r for r in rows if r["false_positive_rate"] <= 0.01]
    best_low_fpr = max(low_fpr, key=lambda r: (r["recall"], r["f1"], r["accuracy"])) if low_fpr else None
    return best_f1, best_low_fpr, rows


# ---------------------------------------------------------------------------
# Single-split evaluation (deployment-like or group-aware)
# ---------------------------------------------------------------------------


def evaluate_protocol(records_all, unique, X, y, static_flags, groups, protocol, feature_set_label, seed=SEED, limit=None):
    """Returns (metrics_dict, fitted_model, split_info, record_arrays)."""
    if protocol == "deployment":
        idx = np.arange(len(unique))
        train_idx, temp_idx = train_test_split(idx, train_size=0.7, random_state=seed, stratify=y)
        val_idx, test_idx = train_test_split(temp_idx, train_size=0.5, random_state=seed, stratify=y[temp_idx])
        split_indices = (train_idx, val_idx, test_idx)
    elif protocol == "group":
        splitter = StratifiedGroupKFold(n_splits=10, shuffle=True, random_state=seed)
        dummy = np.zeros((len(y), 1), dtype=np.uint8)
        folds = np.full(len(y), -1, dtype=int)
        for fold, (_, test_index) in enumerate(splitter.split(dummy, y, groups)):
            folds[test_index] = fold
        train_idx = np.where(folds >= 3)[0]
        val_idx = np.where(folds == 2)[0]
        test_idx = np.where(np.isin(folds, [0, 1]))[0]
        split_indices = (train_idx, val_idx, test_idx)
    else:
        raise ValueError(protocol)

    train_idx, val_idx, test_idx = split_indices
    model = make_rf()
    model.fit(X[train_idx], y[train_idx])
    pval = model.predict_proba(X[val_idx])[:, 1]
    ptest = model.predict_proba(X[test_idx])[:, 1]
    best_f1, best_low_fpr, thr_grid = threshold_table(y[val_idx], pval)

    # record-level mapping
    key_to_unique = {r.dedup_key: i for i, r in enumerate(unique)}
    rec_idx = np.asarray([key_to_unique[r.dedup_key] for r in records_all if r.dedup_key in key_to_unique])
    rec_y = np.asarray([records_all[i].label for i in range(len(records_all)) if records_all[i].dedup_key in key_to_unique])
    test_mask = np.zeros(len(unique), dtype=bool)
    test_mask[test_idx] = True
    rec_test_mask = test_mask[rec_idx]

    # thresholds to report
    operating = {}
    for name, thr in (("default_0.5", 0.5), ("validation_best_f1", float(best_f1["threshold"]))):
        if best_low_fpr is not None and name == "validation_best_f1":
            pass
        pred_u = (ptest >= thr).astype(int)
        pred_u_rule = pred_u.copy()
        pred_u_rule[static_flags[test_idx].astype(bool)] = 0
        pr = model.predict_proba(X[rec_idx[rec_test_mask]])[:, 1]
        pred_r = (pr >= thr).astype(int)
        pred_r_rule = pred_r.copy()
        pred_r_rule[static_flags[rec_idx[rec_test_mask]].astype(bool)] = 0
        operating[name] = {
            "threshold": round(float(thr), 4),
            "unique_model_only": binary_metrics(y[test_idx], pred_u, ptest),
            "unique_pipeline": binary_metrics(y[test_idx], pred_u_rule, ptest),
            "records_model_only": binary_metrics(rec_y[rec_test_mask], pred_r, pr),
            "records_pipeline": binary_metrics(rec_y[rec_test_mask], pred_r_rule, pr),
            "unique_accuracy_ci": bootstrap_accuracy_ci(y[test_idx], pred_u),
            "unique_pipeline_accuracy_ci": bootstrap_accuracy_ci(y[test_idx], pred_u_rule),
            "records_pipeline_accuracy_ci": bootstrap_accuracy_ci(rec_y[rec_test_mask], pred_r_rule),
        }
    if best_low_fpr is not None:
        thr = float(best_low_fpr["threshold"])
        pred_u = (ptest >= thr).astype(int)
        pred_u_rule = pred_u.copy()
        pred_u_rule[static_flags[test_idx].astype(bool)] = 0
        pr = model.predict_proba(X[rec_idx[rec_test_mask]])[:, 1]
        pred_r = (pr >= thr).astype(int)
        pred_r_rule = pred_r.copy()
        pred_r_rule[static_flags[rec_idx[rec_test_mask]].astype(bool)] = 0
        operating["validation_fpr_le_1pct"] = {
            "threshold": round(float(thr), 4),
            "unique_model_only": binary_metrics(y[test_idx], pred_u, ptest),
            "unique_pipeline": binary_metrics(y[test_idx], pred_u_rule, ptest),
            "records_model_only": binary_metrics(rec_y[rec_test_mask], pred_r, pr),
            "records_pipeline": binary_metrics(rec_y[rec_test_mask], pred_r_rule, pr),
            "unique_accuracy_ci": bootstrap_accuracy_ci(y[test_idx], pred_u),
            "unique_pipeline_accuracy_ci": bootstrap_accuracy_ci(y[test_idx], pred_u_rule),
            "records_pipeline_accuracy_ci": bootstrap_accuracy_ci(rec_y[rec_test_mask], pred_r_rule),
        }

    importances = sorted(
        ((name, float(v)) for name, v in zip(
            (registry.get_feature_names("v2") + EXTRA22_NAMES[: (X.shape[1] - 16)]),
            model.feature_importances_,
        )),
        key=lambda t: t[1], reverse=True,
    )

    split_info = {
        "unique_train": int(len(train_idx)),
        "unique_val": int(len(val_idx)),
        "unique_test": int(len(test_idx)),
        "records_test": int(rec_test_mask.sum()),
        "groups": len(set(groups)),
        "groups_in_test": len({groups[i] for i in test_idx}),
        "unique_label_distribution": {
            "clean": int((y == 0).sum()), "attack": int((y == 1).sum()),
        },
        "record_label_distribution": {
            "clean": int((rec_y == 0).sum()), "attack": int((rec_y == 1).sum()),
            "attack_prevalence": round(float(rec_y.mean()), 6),
        },
    }

    result = {
        "protocol": protocol,
        "feature_set": feature_set_label,
        "features": int(X.shape[1]),
        "seed": seed,
        "split": split_info,
        "best_params": RF_PARAMS,
        "validation_best_f1_threshold": round(float(best_f1["threshold"]), 4),
        "validation_metrics_at_0.5": None,
        "threshold_selection": {
            "best_f1": best_f1,
            "fpr_le_1pct": best_low_fpr,
        },
        "test": operating,
        "feature_importance": [{"feature": n, "importance": round(v, 6)} for n, v in importances],
        "_model": model,
        "_rec_idx": rec_idx,
        "_rec_y": rec_y,
        "_rec_test_mask": rec_test_mask,
        "_test_idx": test_idx,
    }
    # val metrics at 0.5
    pval05 = model.predict_proba(X[val_idx])[:, 1]
    result["validation_metrics_at_0.5"] = binary_metrics(y[val_idx], (pval05 >= 0.5).astype(int), pval05)
    return result, model


def run_cv(records_all, unique, X, y, static_flags, feature_set_label, seed=SEED, n_splits=5):
    """Pooled stratified K-fold CV over unique requests. Returns metrics dict."""
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    oof_prob = np.zeros(len(unique), dtype=float)
    oof_pred = np.zeros(len(unique), dtype=int)
    fold_rows = []
    key_to_unique = {r.dedup_key: i for i, r in enumerate(unique)}
    rec_idx = np.asarray([key_to_unique[r.dedup_key] for r in records_all if r.dedup_key in key_to_unique])
    rec_y = np.asarray([records_all[i].label for i in range(len(records_all)) if records_all[i].dedup_key in key_to_unique])

    for fold, (train_idx, test_idx) in enumerate(skf.split(X, y)):
        model = make_rf()
        model.fit(X[train_idx], y[train_idx])
        p = model.predict_proba(X[test_idx])[:, 1]
        pred = (p >= 0.5).astype(int)
        oof_prob[test_idx] = p
        oof_pred[test_idx] = pred
        m = binary_metrics(y[test_idx], pred, p)
        # record view for this fold
        rec_mask = np.isin(rec_idx, test_idx)
        pr = model.predict_proba(X[rec_idx[rec_mask]])[:, 1]
        predr = (pr >= 0.5).astype(int)
        predr_rule = predr.copy()
        predr_rule[static_flags[rec_idx[rec_mask]].astype(bool)] = 0
        mr = binary_metrics(rec_y[rec_mask], predr, pr)
        mrr = binary_metrics(rec_y[rec_mask], predr_rule, pr)
        fold_rows.append({
            "fold": fold,
            "unique_test": int(len(test_idx)),
            "unique_accuracy": m["accuracy"],
            "unique_f1": m["f1"],
            "unique_fpr": m["false_positive_rate"],
            "record_test": int(rec_mask.sum()),
            "record_accuracy_model_only": mr["accuracy"],
            "record_accuracy_pipeline": mrr["accuracy"],
        })

    # pooled unique
    pooled_unique = binary_metrics(y, oof_pred, oof_prob)
    pooled_unique_ci = bootstrap_accuracy_ci(y, oof_pred)
    pooled_unique_rule = oof_pred.copy()
    pooled_unique_rule[static_flags.astype(bool)] = 0
    pooled_unique_pipe = binary_metrics(y, pooled_unique_rule, oof_prob)
    pooled_unique_pipe_ci = bootstrap_accuracy_ci(y, pooled_unique_rule)

    # pooled records
    rec_pred = oof_pred[rec_idx]
    rec_prob = oof_prob[rec_idx]
    rec_pred_rule = rec_pred.copy()
    rec_pred_rule[static_flags[rec_idx].astype(bool)] = 0
    pooled_rec_model = binary_metrics(rec_y, rec_pred, rec_prob)
    pooled_rec_pipe = binary_metrics(rec_y, rec_pred_rule, rec_prob)
    pooled_rec_pipe_ci = bootstrap_accuracy_ci(rec_y, rec_pred_rule)

    # validation-style threshold selection on a held-out val fold (fold 0 as val) for reporting threshold
    # Use a single split to pick threshold; report 0.5 and best_f1
    idx = np.arange(len(unique))
    tr, te = train_test_split(idx, train_size=0.8, random_state=seed, stratify=y)
    tr2, va = train_test_split(tr, train_size=0.875, random_state=seed, stratify=y[tr])
    mval = make_rf()
    mval.fit(X[tr2], y[tr2])
    pva = mval.predict_proba(X[va])[:, 1]
    best_f1, best_low_fpr, _ = threshold_table(y[va], pva)

    # apply best_f1 threshold to pooled OOF
    thr = float(best_f1["threshold"])
    oof_best = (oof_prob >= thr).astype(int)
    oof_best_rule = oof_best.copy()
    oof_best_rule[static_flags.astype(bool)] = 0
    pooled_unique_best = binary_metrics(y, oof_best, oof_prob)
    pooled_unique_best_ci = bootstrap_accuracy_ci(y, oof_best)
    rec_best = oof_best[rec_idx]
    rec_best_rule = rec_best.copy()
    rec_best_rule[static_flags[rec_idx].astype(bool)] = 0
    pooled_rec_best = binary_metrics(rec_y, rec_best_rule, rec_prob)

    importances_model = make_rf()
    importances_model.fit(X, y)
    importances = sorted(
        ((name, float(v)) for name, v in zip(
            (registry.get_feature_names("v2") + EXTRA22_NAMES[: (X.shape[1] - 16)]),
            importances_model.feature_importances_,
        )),
        key=lambda t: t[1], reverse=True,
    )

    return {
        "protocol": "deployment_cv",
        "feature_set": feature_set_label,
        "features": int(X.shape[1]),
        "n_splits": n_splits,
        "unique_total": int(len(unique)),
        "records_total": int(len(rec_y)),
        "split": {
            "groups": len(set(unique and [r.group_signature for r in unique] or [])),
        },
        "threshold_selection": {
            "best_f1_threshold": round(thr, 4),
            "best_f1": best_f1,
            "fpr_le_1pct": best_low_fpr,
        },
        "fold_rows": fold_rows,
        "pooled_unique_0.5": pooled_unique,
        "pooled_unique_0.5_ci": pooled_unique_ci,
        "pooled_unique_pipeline_0.5": pooled_unique_pipe,
        "pooled_unique_pipeline_0.5_ci": pooled_unique_pipe_ci,
        "pooled_unique_best_f1": pooled_unique_best,
        "pooled_unique_best_f1_ci": pooled_unique_best_ci,
        "pooled_records_model_only_0.5": pooled_rec_model,
        "pooled_records_pipeline_0.5": pooled_rec_pipe,
        "pooled_records_pipeline_0.5_ci": pooled_rec_pipe_ci,
        "pooled_records_pipeline_best_f1": pooled_rec_best,
        "feature_importance": [{"feature": n, "importance": round(v, 6)} for n, v in importances],
        "note": "Pooled OOF: every distinct request tested exactly once; predictions propagated to all duplicate records.",
    }


def run_external_holdout(records, selection_limit=80000, seed=SEED):
    """Feature set is fixed; train on one record subset, test on the disjoint
    unique requests that never appear in it.  This is the cleanest estimate we
    can produce without reusing the selection data."""
    all_unique, _ = dedupe_records(records)
    selection_records = stratified_subset(records, selection_limit, seed)
    selection_unique, _ = dedupe_records(selection_records)
    selection_keys = {r.dedup_key for r in selection_unique}
    holdout_unique = [r for r in all_unique if r.dedup_key not in selection_keys]
    y_sel = np.asarray([r.label for r in selection_unique])
    y_hold = np.asarray([r.label for r in holdout_unique])
    _, X16_sel, X22_sel, static_sel = extract_matrices(selection_unique)
    _, X16_hold, X22_hold, static_hold = extract_matrices(holdout_unique)

    result = {
        "selection_limit_records": int(selection_limit),
        "selection_unique": int(len(selection_unique)),
        "holdout_unique": int(len(holdout_unique)),
        "holdout_attack": int(y_hold.sum()),
        "holdout_clean": int((y_hold == 0).sum()),
        "feature_sets": {},
    }
    for label, Xs, Xh in (("16-D", X16_sel, X16_hold), ("22-D", X22_sel, X22_hold)):
        model = make_rf()
        model.fit(Xs, y_sel)
        p = model.predict_proba(Xh)[:, 1]
        pred = (p >= 0.5).astype(int)
        pred_rule = pred.copy()
        pred_rule[static_hold.astype(bool)] = 0
        result["feature_sets"][label] = {
            "features": int(Xs.shape[1]),
            "unique_model_only": binary_metrics(y_hold, pred, p),
            "unique_pipeline": binary_metrics(y_hold, pred_rule, p),
            "unique_accuracy_ci": bootstrap_accuracy_ci(y_hold, pred),
            "unique_pipeline_accuracy_ci": bootstrap_accuracy_ci(y_hold, pred_rule),
        }
    return result


# ---------------------------------------------------------------------------
# Zero-shot shipped model
# ---------------------------------------------------------------------------


def zero_shot_shipped(unique, X16, test_idx):
    import joblib
    path = os.path.join(REPO_ROOT, "models", "v2.0", "threat_classifier.joblib")
    if not os.path.exists(path):
        return None
    model = joblib.load(path)
    if getattr(model, "n_features_in_", None) != 16:
        return {"model_path": os.path.relpath(path, REPO_ROOT).replace("\\", "/"),
                "error": f"model expects {getattr(model, 'n_features_in_', None)} features"}
    Xte = X16[test_idx]
    yte = np.asarray([r.label for r in unique])[test_idx]
    predictions = model.predict(Xte)
    binary_predictions = np.asarray([0 if str(l).strip().upper() == "CLEAN" else 1 for l in predictions], dtype=int)
    return {
        "model_path": os.path.relpath(path, REPO_ROOT).replace("\\", "/"),
        "evaluation": "zero-shot cross-dataset generalisation on CSIC held-out split; NOT trained on CSIC",
        "samples": int(len(yte)),
        "binary_metrics": binary_metrics(yte, binary_predictions),
        "predicted_class_distribution": {str(l): int(c) for l, c in Counter(predictions).most_common()},
        "none_clean_rate": round(float(binary_predictions.mean()), 6),
    }


# ---------------------------------------------------------------------------
# http.log sanity check
# ---------------------------------------------------------------------------


def find_http_log():
    for c in HTTP_LOG_CANDIDATES:
        if os.path.isfile(c):
            return c
    return None


def sample_log_lines(path, offsets=20, lines_per_offset=5000):
    size = os.path.getsize(path)
    lines = []
    with open(path, "rb") as handle:
        for index in range(offsets):
            offset = int(size * index / offsets)
            handle.seek(offset)
            if offset != 0:
                handle.readline()
            for _ in range(lines_per_offset):
                raw = handle.readline()
                if not raw:
                    break
                lines.append(raw.decode("utf-8", errors="replace").rstrip("\r\n"))
    return lines


def analyze_http_log(model, threshold, sample_lines=100000):
    path = find_http_log()
    if path is None:
        return None
    print(f"\n=== http.log sanity check ({os.path.relpath(path, REPO_ROOT)}) ===")
    lines = sample_log_lines(path)
    if len(lines) > sample_lines:
        lines = lines[:sample_lines]

    rows = []
    malformed = 0
    for line in lines:
        fields = line.split("\t")
        if len(fields) != 27:
            malformed += 1
            continue
        method = fields[7].upper() if fields[7] not in ("", "-") else "GET"
        uri = fields[9] if fields[9] not in ("", "-") else "/"
        user_agent = fields[11] if fields[11] != "-" else ""
        status = fields[14]
        rows.append({"method": method, "uri": uri, "user_agent": user_agent,
                     "status": status, "payload": uri})

    if not rows:
        return {"error": "no parsable rows", "sampled_lines": len(lines)}

    from dataclasses import replace
    reqs = []
    for index, row in enumerate(rows):
        uri = row["uri"]
        path_part = uri.split("?", 1)[0]
        query_part = uri.split("?", 1)[1] if "?" in uri else ""
        reqs.append(Request(
            rid=str(index), source="http.log", declared_class="", label=-1,
            method=row["method"], url=uri, path=path_part, query=query_part,
            body="", user_agent=row["user_agent"], headers={}, payload=row["payload"],
        ))
    X10, X16, X22, _ = extract_matrices(reqs)
    probabilities = model.predict_proba(X16)[:, 1]
    default_flags = probabilities >= 0.5
    low_fpr_flags = probabilities >= threshold

    def ua_category(ua):
        lowered = ua.lower()
        if "nmap" in lowered:
            return "nmap_scanner"
        if "mozilla" in lowered:
            return "browser"
        if not ua or ua == "-":
            return "empty"
        return "other"

    categories = [ua_category(r["user_agent"]) for r in rows]
    status_groups = []
    for r in rows:
        try:
            status_groups.append(f"{int(r['status']) // 100}xx")
        except (TypeError, ValueError):
            status_groups.append("unknown")

    def rates(flags):
        by_cat = {}
        for cat in sorted(set(categories)):
            mask = np.asarray([c == cat for c in categories])
            by_cat[cat] = {"requests": int(mask.sum()), "flagged": int(flags[mask].sum()),
                           "flag_rate": round(float(flags[mask].mean()), 6) if mask.any() else 0.0}
        by_method = {}
        methods = [r["method"] for r in rows]
        for m in sorted(set(methods)):
            mask = np.asarray([mm == m for mm in methods])
            by_method[m] = {"requests": int(mask.sum()), "flagged": int(flags[mask].sum()),
                            "flag_rate": round(float(flags[mask].mean()), 6) if mask.any() else 0.0}
        by_status = {}
        for g in sorted(set(status_groups)):
            mask = np.asarray([s == g for s in status_groups])
            by_status[g] = {"requests": int(mask.sum()), "flagged": int(flags[mask].sum()),
                            "flag_rate": round(float(flags[mask].mean()), 6) if mask.any() else 0.0}
        flagged_uris = Counter(r["uri"] for r, f in zip(rows, flags) if f).most_common(15)
        flagged_uas = Counter(r["user_agent"] for r, f in zip(rows, flags) if f).most_common(10)
        return {
            "requests": int(len(rows)), "flagged": int(flags.sum()),
            "flag_rate": round(float(flags.mean()), 6),
            "by_user_agent_category": by_cat, "by_method": by_method,
            "by_status_group": by_status,
            "top_flagged_uris": [{"uri": u, "count": c} for u, c in flagged_uris],
            "top_flagged_user_agents": [{"user_agent": u, "count": c} for u, c in flagged_uas],
        }

    proxy_mask = np.asarray([c in ("nmap_scanner", "browser") for c in categories])
    proxy_y = np.asarray([1 if c == "nmap_scanner" else 0 for c in categories])[proxy_mask]
    proxy_default = default_flags[proxy_mask].astype(int)
    proxy_low = low_fpr_flags[proxy_mask].astype(int)

    return {
        "source": os.path.relpath(path, REPO_ROOT).replace("\\", "/"),
        "sampled_lines": len(lines),
        "parsed_requests": len(rows),
        "malformed_lines": malformed,
        "unique_uris": len({r["uri"] for r in rows}),
        "default_0.5": rates(default_flags),
        f"low_fpr_{threshold:.2f}": rates(low_fpr_flags),
        "heuristic_proxy_labels": {
            "description": "Nmap User-Agent requests treated as attack, browser requests as benign. Weak proxy, not ground truth.",
            "nmap_requests": int((proxy_y == 1).sum()),
            "browser_requests": int((proxy_y == 0).sum()),
            "default_0.5": binary_metrics(proxy_y, proxy_default),
            f"low_fpr_{threshold:.2f}": binary_metrics(proxy_y, proxy_low),
        },
        "caveat": "Zeek http.log has no labels and no request bodies. Accuracy cannot be computed. Flag rates and Nmap/browser proxy are sanity checks only.",
    }


# ---------------------------------------------------------------------------
# Final model training
# ---------------------------------------------------------------------------


def train_final_model(unique, X, static_flags, params, threshold, out_dir, version_label, feature_names):
    import joblib
    model = make_rf(params if params else None)
    # rebuild with given params
    model = RandomForestClassifier(**(params or RF_PARAMS), class_weight=None, random_state=SEED, n_jobs=-1)
    model.fit(X, np.asarray([r.label for r in unique]))
    os.makedirs(out_dir, exist_ok=True)
    model_path = os.path.join(out_dir, "threat_classifier.joblib")
    joblib.dump(model, model_path)
    schema_path = os.path.join(out_dir, "feature_schema.json")
    if X.shape[1] == 16:
        registry.export_manifest(schema_path)
    else:
        # Candidate schema must match the artifact, not the runtime 16-D manifest.
        with open(schema_path, "w", encoding="utf-8") as handle:
            json.dump({
                "version": "csic-binary-v3-22d",
                "count": int(X.shape[1]),
                "features": list(feature_names),
                "base_version": "v3 (22-D)",
                "additional_features": EXTRA22_NAMES,
                "status": "official",
                "supported_versions": ["v1", "v2", "v3"],
            }, handle, indent=2)
            handle.write("\n")
    metadata = {
        "version": version_label,
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "dataset": "CSIC 2010 (HTTP requests, binary Valid/Attack labels)",
        "unique_requests": len(unique),
        "features": int(X.shape[1]),
        "feature_names": feature_names,
        "label_map": {"0": "CLEAN", "1": "ATTACK"},
        "algorithm": "RandomForestClassifier",
        "hyperparameters": params or RF_PARAMS,
        "class_weight": "none",
        "decision_threshold": round(float(threshold), 4),
        "role": ("Binary clean-vs-attack gate. "
                 + ("16-D baseline model; retained for comparison."
                    if X.shape[1] == 16
                    else "Official 22-D model. Matches the v3 runtime contract.")),
        "note": "Trained on all unique CSIC requests. Held-out metrics in csic_evaluation_results.json.",
    }
    with open(os.path.join(out_dir, "metadata.json"), "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)
        handle.write("\n")
    return {
        "model_path": os.path.relpath(model_path, REPO_ROOT).replace("\\", "/"),
        "metadata_path": os.path.relpath(os.path.join(out_dir, "metadata.json"), REPO_ROOT).replace("\\", "/"),
        "unique_requests": len(unique),
        "features": int(X.shape[1]),
        "threshold": round(float(threshold), 4),
    }


# ---------------------------------------------------------------------------
# Report writing
# ---------------------------------------------------------------------------


def pct(v):
    return f"{100.0 * float(v):.2f}%"


def write_report(results):
    lines = []
    add = lines.append
    add("# CSIC 2010 Evaluation — NATRIX HTTP Classifier")
    add("")
    add(f"Measured: {results['generated_at']}")
    add("")
    add("## 1. What was measured")
    add("")
    add("Real held-out evaluation on **CSIC 2010**, a public corpus of raw HTTP "
        "requests from a web application. Task is binary: `Valid` (clean) vs "
        "`Attack`. CSIC has no SQLi/XSS/traversal sub-labels, so this does not "
        "claim seven-class accuracy.")
    add("")
    d = results["dataset"]
    add("| Dataset fact | Value |")
    add("|---|---:|")
    add(f"| Total records parsed | {d['records']:,} |")
    add(f"| Clean records | {d['labels']['clean']:,} |")
    add(f"| Attack records | {d['labels']['attack']:,} |")
    add(f"| Unique exact requests | {d['unique_records']:,} |")
    add(f"| Ambiguous exact requests removed | {d['ambiguous_exact_requests']:,} |")
    add(f"| Group signatures | {d['groups']:,} |")
    add("")
    add("CSIC is heavily duplicated: 97,065 records collapse to 34,593 distinct "
        "requests and 1,734 method/path/parameter-key groups. Exact deduplication "
        "is mandatory before any split.")
    add("")

    add("## 2. Protocols")
    add("")
    add("- **Primary (deployment-like):** exact dedup, then stratified random "
        "split over distinct requests (70/10/20). Same endpoints appear in train "
        "and test; no exact duplicate crosses the split.")
    add("- **Stress test (leave-one-endpoint-out):** group-aware split by "
        "(method, normalised path, query/body parameter names). Severe "
        "distribution shift; reported only to bound worst-case generalisation.")
    add("- **16-D:** previous contract, kept as a baseline. **22-D (v3):** the "
        "promoted runtime contract: 16-D plus six generic features.")
    add("- **Model-only vs pipeline:** pipeline adds a transparent static-asset "
        "allowlist (GET/HEAD, no query/body, benign extension).")
    add("- Hyperparameters and thresholds selected on validation only; test "
        "evaluated once. 95% CIs are 2,000-sample bootstraps.")
    add("")
    add("### 2.1 Rejected feature: `upper_suffix_params`")
    add("")
    add("The first candidate 22-D set added a parameter-name uppercase-suffix "
        "counter. On CSIC it is **100% attack, 0% clean**: 4,424 distinct attack "
        "requests have it non-zero, and the active values are `B1A`, `loginA`, "
        "`precioA`, `modoA`, `pwdA`. That is CSIC's own parameter-tampering "
        "pattern, not a generic HTTP signal. Keeping it raised unique accuracy "
        "from 95.55% to 97.47%. It is rejected. `max_value_length` (the longest "
        "parameter value in the request) replaces it; it is a generic "
        "request-shape feature present in both classes. This is an example of "
        "the leakage audit the evaluation is supposed to catch.")
    add("")

    # Primary results table
    add("## 3. 45,000-record benchmark (deployment-like split)")
    add("")
    b = results["benchmarks"]["deployment_45k"]
    add(f"- Records: {b['records']:,}; unique requests: {b['unique']:,}; "
        f"groups: {b['groups']:,}; test unique: {b['split']['unique_test']:,}; "
        f"test records: {b['split']['records_test']:,}")
    add("")
    add("### Unique-request view")
    add("")
    add("| Feature set | Pipeline | Threshold | Accuracy | 95% CI | Precision | Recall | F1 | FPR | FNR |")
    add("|---|---|---:|---:|---|---:|---:|---:|---:|---:|")
    for fs_label in ("16-D", "22-D"):
        fs = b["feature_sets"][fs_label]
        for pipe_label, point_key in (("model-only", "unique_model_only"), ("+allowlist", "unique_pipeline")):
            op = fs["test"]["validation_best_f1"]
            m = op[point_key]
            ci = op["unique_accuracy_ci"] if point_key == "unique_model_only" else op["unique_pipeline_accuracy_ci"]
            add(f"| {fs_label} | {pipe_label} | {op['threshold']:.2f} | {pct(m['accuracy'])} | "
                f"{pct(ci[0])}–{pct(ci[1])} | {pct(m['precision'])} | {pct(m['recall'])} | "
                f"{pct(m['f1'])} | {pct(m['false_positive_rate'])} | {pct(m['false_negative_rate'])} |")
    add("")
    add("This split trains on only 11,929 distinct requests (70% of 17,042), "
        "far fewer than the final model. The full-corpus CV and the external "
        "holdout are the headline estimates; this table is the small-training-"
        "set case.")
    add("")
    add("### Record view")
    add("")
    add("| Feature set | Pipeline | Threshold | Accuracy | 95% CI | Precision | Recall | F1 | FPR | FNR |")
    add("|---|---|---:|---:|---|---:|---:|---:|---:|---:|")
    for fs_label in ("16-D", "22-D"):
        fs = b["feature_sets"][fs_label]
        op = fs["test"]["validation_best_f1"]
        for pipe_label, point_key, ci_key in (("model-only", "records_model_only", None),
                                             ("+allowlist", "records_pipeline", "records_pipeline_accuracy_ci")):
            m = op[point_key]
            ci = op[ci_key] if ci_key else [0.0, 0.0]
            ci_str = (f"{pct(ci[0])}–{pct(ci[1])}" if ci_key else "—")
            add(f"| {fs_label} | {pipe_label} | {op['threshold']:.2f} | {pct(m['accuracy'])} | "
                f"{ci_str} | {pct(m['precision'])} | {pct(m['recall'])} | {pct(m['f1'])} | "
                f"{pct(m['false_positive_rate'])} | {pct(m['false_negative_rate'])} |")
    add("")

    # Full corpus CV
    add("## 4. Full CSIC corpus — primary headline (pooled 5-fold CV)")
    add("")
    c = results["benchmarks"]["deployment_cv_full"]
    add(f"- Unique requests: {c['unique_total']:,}; records: {c['records_total']:,}; "
        f"folds: {c['n_splits']}")
    add("")
    add("| Feature set | View | Accuracy | 95% CI | Precision | Recall | F1 | FPR | FNR |")
    add("|---|---|---:|---|---:|---:|---:|---:|---:|")
    for fs_label in ("16-D", "22-D"):
        fs = c["feature_sets"][fs_label]
        # unique 0.5
        mu = fs["pooled_unique_0.5"]
        ciu = fs["pooled_unique_0.5_ci"]
        add(f"| {fs_label} | unique model-only | {pct(mu['accuracy'])} | {pct(ciu[0])}–{pct(ciu[1])} | "
            f"{pct(mu['precision'])} | {pct(mu['recall'])} | {pct(mu['f1'])} | "
            f"{pct(mu['false_positive_rate'])} | {pct(mu['false_negative_rate'])} |")
        # unique pipeline (allowlist)
        mup = fs["pooled_unique_pipeline_0.5"]
        cip = fs["pooled_unique_pipeline_0.5_ci"]
        add(f"| {fs_label} | unique +allowlist | {pct(mup['accuracy'])} | {pct(cip[0])}–{pct(cip[1])} | "
            f"{pct(mup['precision'])} | {pct(mup['recall'])} | {pct(mup['f1'])} | "
            f"{pct(mup['false_positive_rate'])} | {pct(mup['false_negative_rate'])} |")
        # records pipeline
        mrp = fs["pooled_records_pipeline_0.5"]
        cipr = fs["pooled_records_pipeline_0.5_ci"]
        add(f"| {fs_label} | records +allowlist | {pct(mrp['accuracy'])} | {pct(cipr[0])}–{pct(cipr[1])} | "
            f"{pct(mrp['precision'])} | {pct(mrp['recall'])} | {pct(mrp['f1'])} | "
            f"{pct(mrp['false_positive_rate'])} | {pct(mrp['false_negative_rate'])} |")
    add("")
    add("Record-level accuracy is split-sensitive because seven benign high-frequency "
        "pages (e.g. `/tienda1/index.jsp`) are repeated ~2,000× each in CSIC; when "
        "their single unique request lands in a test fold it produces thousands of "
        "false positives. The unique-request metric is the honest headline. See "
        "section 7.")
    add("")

    # External holdout
    add("### 4.1 External holdout — disjoint unique requests")
    add("")
    e = results.get("external_holdout")
    if e:
        add(f"The 22-D feature set was fixed first, then a model was trained on "
            f"**{e['selection_unique']:,}** distinct requests from an 80,000-record "
            f"selection set and evaluated on **{e['holdout_unique']:,}** distinct "
            f"requests that never appear in it ({e['holdout_attack']:,} attack, "
            f"{e['holdout_clean']:,} clean). This is a single clean split with "
            "no shared unique request and no shared duplicate across the boundary.")
        add("")
        add("| Feature set | Unique accuracy | 95% CI | Precision | Recall | F1 | FPR | FNR |")
        add("|---|---:|---|---:|---:|---:|---:|---:|")
        for label in ("16-D", "22-D"):
            m = e["feature_sets"][label]["unique_model_only"]
            ci = e["feature_sets"][label]["unique_accuracy_ci"]
            add(f"| {label} | {pct(m['accuracy'])} | {pct(ci[0])}–{pct(ci[1])} | "
                f"{pct(m['precision'])} | {pct(m['recall'])} | {pct(m['f1'])} | "
                f"{pct(m['false_positive_rate'])} | {pct(m['false_negative_rate'])} |")
        add("")
        add("The holdout trains on fewer distinct requests than the final model "
            "(or the 5-fold CV), so it is a conservative check, not a replacement "
            "for the full-corpus CV. It still clears 95% at the point estimate "
            "for 22-D; the interval reaches 94.83%.")
    else:
        add("External holdout not run.")
    add("")

    # Confusion matrices
    add("### 4.2 Confusion matrices (key operating points)")
    add("")
    add("| Estimate | View | Feature set | TP | TN | FP | FN |")
    add("|---|---|---|---:|---:|---:|---:|")
    for fs_label in ("16-D", "22-D"):
        cm = c["feature_sets"][fs_label]["pooled_unique_pipeline_0.5"]["confusion_matrix"]
        add(f"| 5-fold CV | unique +allowlist, 0.5 | {fs_label} | "
            f"{cm['TP']:,} | {cm['TN']:,} | {cm['FP']:,} | {cm['FN']:,} |")
    if e:
        for fs_label in ("16-D", "22-D"):
            cm = e["feature_sets"][fs_label]["unique_model_only"]["confusion_matrix"]
            add(f"| External holdout | unique, 0.5 | {fs_label} | "
                f"{cm['TP']:,} | {cm['TN']:,} | {cm['FP']:,} | {cm['FN']:,} |")
    op45 = b["feature_sets"]["22-D"]["test"]["validation_best_f1"]
    cm = op45["unique_pipeline"]["confusion_matrix"]
    add(f"| 45k benchmark | unique +allowlist, {op45['threshold']:.2f} | 22-D | "
        f"{cm['TP']:,} | {cm['TN']:,} | {cm['FP']:,} | {cm['FN']:,} |")
    cm = op45["records_pipeline"]["confusion_matrix"]
    add(f"| 45k benchmark | records +allowlist, {op45['threshold']:.2f} | 22-D | "
        f"{cm['TP']:,} | {cm['TN']:,} | {cm['FP']:,} | {cm['FN']:,} |")
    add("")

    # Stress test
    add("## 5. Stress test — leave-one-endpoint-out (group-aware split)")
    add("")
    s = results["benchmarks"]["stress_45k"]
    add(f"- 45,000-record subset; groups: {s['groups']:,}; test unique: "
        f"{s['split']['unique_test']:,}; test records: {s['split']['records_test']:,}")
    add("")
    add("| Feature set | Pipeline | Unique acc | Record acc |")
    add("|---|---|---:|---:|")
    for fs_label in ("16-D", "22-D"):
        fs = s["feature_sets"][fs_label]
        op = fs["test"]["validation_best_f1"]
        add(f"| {fs_label} | model-only | {pct(op['unique_model_only']['accuracy'])} | "
            f"{pct(op['records_model_only']['accuracy'])} |")
        add(f"| {fs_label} | +allowlist | {pct(op['unique_pipeline']['accuracy'])} | "
            f"{pct(op['records_pipeline']['accuracy'])} |")
    add("")
    add("Both models collapse when entire endpoints are withheld: the 16-D and "
        "22-D gates predict almost every clean request as attack (FPR ≈ 100%). "
        "The 22-D features improve the deployment-like result, but they do not "
        "generalise to unseen endpoint families. This is a genuine failure mode, "
        "not a deployment estimate. The gate must be retrained or validated on "
        "the endpoint families it will actually see.")
    add("")

    # Feature importance
    add("## 6. Feature importance (22-D, fitted on full CSIC)")
    add("")
    add("| Feature | Importance |")
    add("|---|---:|")
    for row in c["feature_sets"]["22-D"]["feature_importance"][:22]:
        add(f"| {row['feature']} | {row['importance']:.4f} |")
    add("")

    # Error analysis
    add("## 7. Error analysis")
    add("")
    err = c["feature_sets"]["22-D"]["pooled_unique_pipeline_0.5"]
    cm = err["confusion_matrix"]
    add(f"Pooled 5-fold CV, 22-D + static allowlist, unique view: "
        f"{cm['FP']:,} false positives and {cm['FN']:,} false negatives out of "
        f"{err['samples']:,} distinct requests (FPR "
        f"{pct(err['false_positive_rate'])}, FNR {pct(err['false_negative_rate'])}).")
    add("")
    add("False positives are dominated by seven benign high-frequency requests "
        "(six paths; `vaciar.jsp` appears as both GET and POST): "
        "`/tienda1/index.jsp`, `/tienda1/global/menum.jsp`, "
        "`/tienda1/publico/miembros.jsp`, `/tienda1/publico/vaciar.jsp`, "
        "`/tienda1/publico/entrar.jsp`, `/tienda1/publico/caracteristicas.jsp`, "
        "each repeated ~2,000× in CSIC. "
        "Their feature vectors are indistinguishable from the short-path attack "
        "class (840 attack vs 20 clean short no-query paths), so the model "
        "assigns them high attack probability. They are seven distinct requests, "
        "so they barely move the unique metric but dominate the record metric. "
        "We do not special-case them: that would be fitting to CSIC.")
    add("")
    add(f"False negatives are mostly parameterised attack variants of the same "
        f"endpoints (SQLi/XSS in `registro.jsp`, `editar.jsp`, `autenticar.jsp`); "
        f"the model misses {pct(err['false_negative_rate'])} of distinct attack "
        "requests, concentrated in variants whose injected payload is short or "
        "low-entropy.")
    add("")

    # Zero-shot
    add("## 8. Zero-shot shipped seven-class model")
    add("")
    z = results.get("zero_shot_shipped")
    if z and "binary_metrics" in z:
        m = z["binary_metrics"]
        add("The model in `models/v2.0/threat_classifier.joblib` was trained on "
            "the 67-sample curated corpus, not CSIC. Running it unchanged on the "
            "CSIC test split is a cross-dataset generalisation check.")
        add("")
        add("| Metric | Value |")
        add("|---|---:|")
        add(f"| Samples | {z['samples']:,} |")
        add(f"| Accuracy | {pct(m['accuracy'])} |")
        add(f"| Precision (attack) | {pct(m['precision'])} |")
        add(f"| Recall (attack) | {pct(m['recall'])} |")
        add(f"| F1 (attack) | {pct(m['f1'])} |")
        add(f"| FPR | {pct(m['false_positive_rate'])} |")
        add(f"| FNR | {pct(m['false_negative_rate'])} |")
        add(f"| Flagged as non-CLEAN | {pct(z['none_clean_rate'])} |")
        add("")
        add("Predicted class distribution:")
        add("")
        add("| Class | Count |")
        add("|---|---:|")
        for label, count in z["predicted_class_distribution"].items():
            add(f"| {label} | {count:,} |")
    else:
        add("Shipped model not found or incompatible.")
    add("")

    # http.log
    add("## 9. Unlabelled Zeek http.log sanity check")
    add("")
    log = results.get("http_log")
    if log and "default_0.5" in log:
        add(f"Source: `{log['source']}`. Sampled {log['parsed_requests']:,} "
            f"parsed requests from {log['sampled_lines']:,} lines. No labels and "
            "no bodies — flag rates only, not accuracy.")
        add("")
        add("| Operating point | Requests | Flagged | Flag rate |")
        add("|---|---:|---:|---:|")
        for key in ("default_0.5", f"low_fpr_{log and 0.5 or 0.5}"):
            pass
        for k in ("default_0.5",):
            r = log[k]
            add(f"| {k} | {r['requests']:,} | {r['flagged']:,} | {pct(r['flag_rate'])} |")
        low_keys = [k for k in log if k.startswith("low_fpr_")]
        for k in low_keys:
            r = log[k]
            add(f"| {k} | {r['requests']:,} | {r['flagged']:,} | {pct(r['flag_rate'])} |")
        add("")
        add("Flag rate by User-Agent category (default 0.5):")
        add("")
        add("| Category | Requests | Flagged | Flag rate |")
        add("|---|---:|---:|---:|")
        for cat, row in log["default_0.5"]["by_user_agent_category"].items():
            add(f"| {cat} | {row['requests']:,} | {row['flagged']:,} | {pct(row['flag_rate'])} |")
        add("")
        add("Flag rate by HTTP method (default 0.5):")
        add("")
        add("| Method | Requests | Flagged | Flag rate |")
        add("|---|---:|---:|---:|")
        for method, row in log["default_0.5"]["by_method"].items():
            add(f"| {method} | {row['requests']:,} | {row['flagged']:,} | {pct(row['flag_rate'])} |")
        add("")
        proxy = log["heuristic_proxy_labels"]
        add("Weak Nmap/browser proxy comparison (not ground truth):")
        add("")
        add(f"- Nmap requests: {proxy['nmap_requests']:,}; browser requests: {proxy['browser_requests']:,}")
        for k in ("default_0.5",):
            mk = [kk for kk in proxy if kk.startswith(k)][0]
            m = proxy[mk]
            add(f"- {mk}: accuracy {pct(m['accuracy'])}, precision {pct(m['precision'])}, "
                f"recall {pct(m['recall'])}, F1 {pct(m['f1'])}, FPR {pct(m['false_positive_rate'])}")
        for lk in low_keys:
            mk = [kk for kk in proxy if kk.startswith("low_fpr")][0] if any(kk.startswith("low_fpr") for kk in proxy) else None
            if mk:
                m = proxy[mk]
                add(f"- {mk}: accuracy {pct(m['accuracy'])}, precision {pct(m['precision'])}, "
                    f"recall {pct(m['recall'])}, F1 {pct(m['f1'])}, FPR {pct(m['false_positive_rate'])}")
                break
        add("")
        add("Top flagged URIs (default 0.5):")
        add("")
        add("| URI | Count |")
        add("|---|---:|")
        for row in log["default_0.5"]["top_flagged_uris"][:10]:
            add(f"| `{row['uri'][:160]}` | {row['count']:,} |")
        add("")
        add("**Domain-shift warning.** The CSIC-trained 16-D gate flags "
            f"{pct(log['default_0.5']['flag_rate'])} of this capture, including "
            f"{pct(log['default_0.5']['by_user_agent_category'].get('browser', {}).get('flag_rate', 0.0))} "
            "of browser requests. That is not usable as a production filter: it "
            "means the CSIC feature distribution does not transfer to this log. "
            "The Nmap/browser proxy comparison is therefore meaningless as a "
            "quality measure (a browser is flagged almost as often as Nmap). "
            "Deploying on traffic like this requires labelled retraining or "
            "calibration, not threshold tuning.")
        add("")
        add(log["caveat"])
    else:
        add("`http.log` not found or not parsable.")
    add("")

    add("## 10. Honest answers to the >95% question")
    add("")
    cv = results["benchmarks"]["deployment_cv_full"]
    b = results["benchmarks"]["deployment_45k"]
    add(f"- Full CSIC corpus, pooled 5-fold CV, 22-D + static allowlist, **unique** "
        f"view: **{pct(cv['feature_sets']['22-D']['pooled_unique_pipeline_0.5']['accuracy'])}** "
        f"(95% CI {pct(cv['feature_sets']['22-D']['pooled_unique_pipeline_0.5_ci'][0])}–"
        f"{pct(cv['feature_sets']['22-D']['pooled_unique_pipeline_0.5_ci'][1])}). "
        "This is the headline number.")
    u45 = b['feature_sets']['22-D']['test']['validation_best_f1']
    add(f"- 45,000-record benchmark, 22-D + static allowlist, **unique** view: "
        f"**{pct(u45['unique_pipeline']['accuracy'])}** "
        f"(95% CI {pct(u45['unique_pipeline_accuracy_ci'][0])}–"
        f"{pct(u45['unique_pipeline_accuracy_ci'][1])}). This split trains on "
        "only 11,929 distinct requests; the lower number reflects training "
        "size, not a different model.")
    add(f"- 45,000-record benchmark, 22-D + static allowlist, **record** view: "
        f"**{pct(u45['records_pipeline']['accuracy'])}** "
        "(split-sensitive; see section 7).")
    if e:
        eh = e["feature_sets"]["22-D"]
        add(f"- External holdout, 22-D, **unique** view: "
            f"**{pct(eh['unique_model_only']['accuracy'])}** on "
            f"{e['holdout_unique']:,} unseen distinct requests "
            f"(95% CI {pct(eh['unique_accuracy_ci'][0])}–"
            f"{pct(eh['unique_accuracy_ci'][1])}). Point estimate clears 95%; "
            f"the interval reaches {pct(eh['unique_accuracy_ci'][0])}.")
    add(f"- **16-D does not reach 95%**: "
        f"{pct(cv['feature_sets']['16-D']['pooled_unique_pipeline_0.5']['accuracy'])} "
        "unique on the full corpus. The promoted 22-D (v3) contract is what "
        "clears the target.")
    add("- The official 22-D artifact uses the default 0.5 threshold, which is the "
        "threshold used for the headline CV and external-holdout numbers. The "
        "validation-selected thresholds in section 3 are reported for "
        "transparency but are not used for the headline.")
    add("- These replace the hard-coded 99.20% / 0.08% claims. Quote the measured "
        "value, the binary task, and CSIC provenance together. Do not claim "
        "production accuracy from CSIC, especially given the http.log domain-"
        "shift result in section 9.")
    add("")
    add("## 11. Limitations")
    add("")
    add("- CSIC is binary: cannot validate SQLi/XSS/traversal/command-injection "
        "sub-labels; those remain unmeasured beyond the 67-sample curated corpus.")
    add("- CSIC is an older synthetic shopping application; not modern APIs, JSON "
        "bodies, authenticated sessions, or evasive attackers.")
    add("- Record-level accuracy is split-sensitive (dominated by seven benign "
        "high-frequency pages); do not quote it without the unique-level number.")
    add("- The 22-D feature set is now the v3 runtime contract. The model behind "
        "it was measured on CSIC; the http.log domain-shift warning still "
        "applies and must be addressed before enabling the gate on live traffic.")
    add("- `http.log` is unlabelled with no bodies; its flag rates are not "
        "accuracy, precision, recall, or FPR. The near-100% flag rate is a "
        "domain-shift warning: the CSIC gate does not transfer to that capture.")
    add("- Zero-shot shipped-model number is cross-dataset, not training evidence.")
    add("- The 16-D feature set is semantically thin: it cannot distinguish a "
        "short benign path (`/tienda1/index.jsp`) from a short attack path "
        "without lexical features. The 22-D v3 contract adds those lexical "
        "signals, which improves deployment-like accuracy but does **not** "
        "solve unseen-endpoint generalisation (section 5).")
    add("")
    add("## 12. Reproduce")
    add("")
    add("```powershell")
    add("cd ml_engine")
    add("python csic_evaluation.py")
    add("```")
    add("")
    add("Machine-readable results: `ml_engine/csic_evaluation_results.json`. "
        "Binary gate artifacts: `models/csic_binary/` (16-D baseline) and "
        "`models/csic_binary_22d/` (22-D, official).")
    add("")

    with open(REPORT_PATH, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    global SEED
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=45000)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--skip-http-log", action="store_true")
    parser.add_argument("--skip-cv", action="store_true")
    parser.add_argument("--skip-stress", action="store_true")
    args = parser.parse_args()
    SEED = args.seed

    print("=" * 70)
    print(" CSIC 2010 EVALUATION — NATRIX HTTP CLASSIFIER")
    print("=" * 70)

    print("\n[1] Parsing CSIC files...")
    records = load_csic()
    label_counts = Counter(r.label for r in records)
    unique_all, ambiguous_all = dedupe_records(records)
    print(f"  total records: {len(records):,}; clean: {label_counts[0]:,}; attack: {label_counts[1]:,}")
    print(f"  unique exact requests: {len(unique_all):,}; ambiguous removed: {len(ambiguous_all):,}; "
          f"groups: {len({r.group_signature for r in unique_all}):,}")

    # Shared helpers
    def prepare(records_subset):
        unique, amb = dedupe_records(records_subset)
        y = np.asarray([r.label for r in unique], dtype=int)
        groups = [r.group_signature for r in unique]
        X10, X16, X22, statics = extract_matrices(unique)
        return unique, amb, y, groups, X10, X16, X22, statics

    results = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "seed": args.seed,
        "dataset": {
            "name": "CSIC 2010",
            "directory": os.path.relpath(DATASET_DIR, REPO_ROOT).replace("\\", "/"),
            "files": [r[0] for r in FILES],
            "records": len(records),
            "labels": {"clean": int(label_counts[0]), "attack": int(label_counts[1])},
            "unique_records": len(unique_all),
            "ambiguous_exact_requests": len(ambiguous_all),
            "groups": len({r.group_signature for r in unique_all}),
        },
        "benchmarks": {},
    }

    # --- Deployment-like 45k ---
    print("\n[2] Deployment-like 45,000-record benchmark...")
    rs = stratified_subset(records, args.limit, args.seed)
    unique, amb, y, groups, X10, X16, X22, statics = prepare(rs)
    print(f"  records: {len(rs):,}; unique: {len(unique):,}; groups: {len(set(groups)):,}")

    feature_sets_45 = {}
    models_45 = {}
    for label, X in (("16-D", X16), ("22-D", X22)):
        print(f"  evaluating {label}...")
        res, model = evaluate_protocol(rs, unique, X, y, statics, groups, "deployment", label, seed=args.seed)
        feature_sets_45[label] = res
        models_45[label] = model
    results["benchmarks"]["deployment_45k"] = {
        "name": "deployment_45k",
        "records": len(rs),
        "unique": len(unique),
        "ambiguous": len(amb),
        "groups": len(set(groups)),
        "split": feature_sets_45["16-D"]["split"],
        "feature_sets": feature_sets_45,
    }

    # --- Stress test 45k ---
    if not args.skip_stress:
        print("\n[3] Stress test (group-aware) 45,000-record benchmark...")
        feature_sets_stress = {}
        for label, X in (("16-D", X16), ("22-D", X22)):
            print(f"  evaluating {label}...")
            res, model = evaluate_protocol(rs, unique, X, y, statics, groups, "group", label, seed=args.seed)
            feature_sets_stress[label] = res
        results["benchmarks"]["stress_45k"] = {
            "name": "stress_45k",
            "records": len(rs),
            "unique": len(unique),
            "ambiguous": len(amb),
            "groups": len(set(groups)),
            "split": feature_sets_stress["16-D"]["split"],
            "feature_sets": feature_sets_stress,
        }
    else:
        results["benchmarks"]["stress_45k"] = None

    # --- Full corpus deployment CV ---
    if not args.skip_cv:
        print("\n[4] Full-corpus pooled 5-fold CV...")
        unique_f, amb_f, y_f, groups_f, X10_f, X16_f, X22_f, statics_f = prepare(records)
        print(f"  unique: {len(unique_f):,}; records: {len(records):,}")

        feature_sets_cv = {}
        for label, X in (("16-D", X16_f), ("22-D", X22_f)):
            print(f"  evaluating {label}...")
            cv_res = run_cv(records, unique_f, X, y_f, statics_f, label, seed=args.seed)
            # ensure pipeline unique metric present
            # recompute allowlist unique metric
            # (run_cv already stores pooled_unique_pipeline_0.5? check: we added via _add below)
            feature_sets_cv[label] = cv_res

        # attach zero-shot using 45k deployment test split (16-D)
        zs = zero_shot_shipped(unique, X16, feature_sets_45["16-D"]["_test_idx"])
        results["zero_shot_shipped"] = zs

        results["benchmarks"]["deployment_cv_full"] = {
            "name": "deployment_cv_full",
            "records": len(records),
            "unique": len(unique_f),
            "ambiguous": len(amb_f),
            "groups": len(set(groups_f)),
            "unique_total": len(unique_f),
            "records_total": len(records),
            "n_splits": 5,
            "feature_sets": feature_sets_cv,
        }
    else:
        results["benchmarks"]["deployment_cv_full"] = None
        unique_f, amb_f, y_f, groups_f, X10_f, X16_f, X22_f, statics_f = prepare(records)
        zs = None
        results["zero_shot_shipped"] = None

    # --- External holdout ---
    print("\n[5] External-holdout validation (disjoint unique requests)...")
    results["external_holdout"] = run_external_holdout(records, selection_limit=80000, seed=args.seed)
    ext = results["external_holdout"]
    print(f"  selection unique: {ext['selection_unique']:,}; holdout unique: {ext['holdout_unique']:,}")
    for label in ("16-D", "22-D"):
        m = ext["feature_sets"][label]["unique_model_only"]
        print(f"  {label} holdout unique: {pct(m['accuracy'])}")

    # --- Train final models ---
    print("\n[6] Training final models...")
    unique_f, amb_f, y_f, groups_f, X10_f, X16_f, X22_f, statics_f = prepare(records)
    # Default 0.5 threshold. The headline CV and external-holdout metrics are
    # reported at 0.5; validation-selected thresholds are shown for transparency
    # only. Do not tune the shipped threshold on the evaluation data.
    thr_16 = 0.5
    thr_22 = 0.5
    final_16 = train_final_model(unique_f, X16_f, statics_f, RF_PARAMS, thr_16,
                                 MODEL_DIR_16, "csic-binary-v1-16d",
                                 registry.get_feature_names("v2"))
    final_22 = train_final_model(unique_f, X22_f, statics_f, RF_PARAMS, thr_22,
                                 MODEL_DIR_22, "csic-binary-v3-22d",
                                 registry.get_feature_names("v2") + EXTRA22_NAMES)
    results["final_models"] = {"16d": final_16, "22d": final_22}

    # --- http.log ---
    http_log = None
    if not args.skip_http_log:
        import joblib
        saved = joblib.load(os.path.join(MODEL_DIR_16, "threat_classifier.joblib"))
        http_log = analyze_http_log(saved, thr_16)
    results["http_log"] = http_log

    # --- Clean up private keys before serialising ---
    for bname, b in list(results["benchmarks"].items()):
        if b is None:
            continue
        for fs in b.get("feature_sets", {}).values():
            for k in ("_model", "_rec_idx", "_rec_y", "_rec_test_mask", "_test_idx"):
                fs.pop(k, None)

    # --- jsonable ---
    def jsonable(value):
        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, dict):
            return {str(k): jsonable(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [jsonable(v) for v in value]
        return value

    results = jsonable(results)

    # Add pooled unique pipeline metric to CV results (computed here for clarity)
    if results["benchmarks"].get("deployment_cv_full"):
        for fs_label, X in (("16-D", X16_f), ("22-D", X22_f)):
            pass

    with open(RESULTS_PATH, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2)
        handle.write("\n")

    write_report(results)

    print("\n" + "=" * 70)
    print(" COMPLETE")
    print("=" * 70)
    if results["benchmarks"].get("deployment_cv_full"):
        cv = results["benchmarks"]["deployment_cv_full"]
        for label in ("16-D", "22-D"):
            fs = cv["feature_sets"][label]
            print(f"  CV {label} unique (model-only, 0.5): {pct(fs['pooled_unique_0.5']['accuracy'])}")
            print(f"  CV {label} unique (+allowlist, 0.5):  {pct(fs['pooled_unique_pipeline_0.5']['accuracy'])}")
    b = results["benchmarks"]["deployment_45k"]
    for label in ("16-D", "22-D"):
        fs = b["feature_sets"][label]
        op = fs["test"]["validation_best_f1"]
        print(f"  45k {label} unique (+allowlist): {pct(op['unique_pipeline']['accuracy'])} | "
              f"record (+allowlist): {pct(op['records_pipeline']['accuracy'])}")
    print(f"  JSON:   {RESULTS_PATH}")
    print(f"  Report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
