"""Dilution is a design flaw; this is the cheap fix, measured.

The v3 ratios (special characters, digits, uppercase, entropy, encoding) are
computed over the whole request.  Appending a long benign parameter therefore
dilutes the attack signal even though the attack is unchanged.  The fix tested
here is a per-parameter contract: for every parameter value compute the same
lexical quantities and aggregate with a maximum, and do the same for the path
segment.  A benign appended parameter can lower an average but cannot lower a
maximum.

Variant v3-D adds nine features to the 22-D v3 contract:

    max_value_digit_ratio, max_value_uppercase_ratio, max_value_entropy,
    max_value_hex_ratio, max_value_keyword_score,
    path_special_char_ratio, path_digit_ratio, path_uppercase_ratio,
    path_keyword_score

The test retrains both contracts on the same CSIC folds and scores the same
mutated requests at the same leave-one-fold-out FPR <= 2% policy.  It reports
the bounded mutation suite and a targeted dilution-only suite.

Outputs
-------
experiments/results/adversarial/dilution_resistant.json
experiments/results/adversarial/dilution_resistant.csv
"""

from __future__ import annotations

import argparse
import math
import re
import sys
import types
import urllib.parse
from collections import Counter
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import adversarial_evasion as A  # noqa: E402
from compare_v3_v4 import best_threshold, metrics_from_pred  # noqa: E402

OUT = C.RESULTS / "adversarial"
OUT.mkdir(parents=True, exist_ok=True)
SEED = 42

SQL = re.compile(r"\b(select|union|where|from|and|or|order|by|insert|update|delete|drop|sleep|benchmark)\b", re.I)
XSS = re.compile(r"\b(script|svg|iframe|img|body|html|onerror|onload)\b", re.I)
TRAV = re.compile(r"(\.\./|\.\.%2f|%2e%2e)", re.I)
ESCAPE = re.compile(r"%[0-9a-fA-F]{2}")

EXTRA_NAMES = [
    "max_value_digit_ratio",
    "max_value_uppercase_ratio",
    "max_value_entropy",
    "max_value_hex_ratio",
    "max_value_keyword_score",
    "path_special_char_ratio",
    "path_digit_ratio",
    "path_uppercase_ratio",
    "path_keyword_score",
]


def _entropy(text: str) -> float:
    if not text:
        return 0.0
    counts = Counter(text)
    n = len(text)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def _special_ratio(text: str) -> float:
    return sum(1 for ch in text if not ch.isalnum() and not ch.isspace()) / len(text) if text else 0.0


def _digit_ratio(text: str) -> float:
    return sum(1 for ch in text if ch.isdigit()) / len(text) if text else 0.0


def _upper_ratio(text: str) -> float:
    return sum(1 for ch in text if ch.isupper()) / len(text) if text else 0.0


def _hex_ratio(text: str) -> float:
    consumed = sum(len(m.group(0)) for m in ESCAPE.finditer(text))
    return consumed / len(text) if text else 0.0


def _keyword_score(text: str) -> float:
    return float(len(SQL.findall(text)) + len(XSS.findall(text)) + len(TRAV.findall(text)))


def prepare_extra(rec):
    values = [
        v
        for _, v in urllib.parse.parse_qsl(rec.query or "", keep_blank_values=True)
        + urllib.parse.parse_qsl(rec.body or "", keep_blank_values=True)
    ]
    return types.SimpleNamespace(values=values, path=rec.path or "")


def x_max_value_digit_ratio(s) -> float:
    return max((_digit_ratio(v) for v in s.values), default=0.0)


def x_max_value_uppercase_ratio(s) -> float:
    return max((_upper_ratio(v) for v in s.values), default=0.0)


def x_max_value_entropy(s) -> float:
    return max((_entropy(v) for v in s.values), default=0.0)


def x_max_value_hex_ratio(s) -> float:
    return max((_hex_ratio(v) for v in s.values), default=0.0)


def x_max_value_keyword_score(s) -> float:
    return max((_keyword_score(v) for v in s.values), default=0.0)


def x_path_special_char_ratio(s) -> float:
    return _special_ratio(s.path)


def x_path_digit_ratio(s) -> float:
    return _digit_ratio(s.path)


def x_path_uppercase_ratio(s) -> float:
    return _upper_ratio(s.path)


def x_path_keyword_score(s) -> float:
    return _keyword_score(s.path)


EXTRA_FUNCS = [
    x_max_value_digit_ratio,
    x_max_value_uppercase_ratio,
    x_max_value_entropy,
    x_max_value_hex_ratio,
    x_max_value_keyword_score,
    x_path_special_char_ratio,
    x_path_digit_ratio,
    x_path_uppercase_ratio,
    x_path_keyword_score,
]

assert [fn.__name__[2:] for fn in EXTRA_FUNCS] == EXTRA_NAMES


def extra_vector(rec) -> list[float]:
    state = prepare_extra(rec)
    return [fn(state) for fn in EXTRA_FUNCS]


def build(records):
    base, _ = C.extract_matrix(records, dtype=np.float32)
    extra = np.asarray([extra_vector(r) for r in records], dtype=np.float32)
    return base, np.hstack([base, extra])


def fit_contract(X, y, folds):
    oof = np.zeros(len(y), dtype=np.float32)
    models = []
    for tr, te in folds:
        model = C.make_rf(random_state=SEED)
        model.fit(X[tr], y[tr])
        oof[te] = model.predict_proba(X[te])[:, 1]
        models.append(model)
    pred = np.zeros(len(y), dtype=int)
    thresholds = []
    for (tr, te), model in zip(folds, models):
        t = best_threshold(oof[tr], y[tr], fpr_cap=0.02)
        pred[te] = (oof[te] >= t).astype(int)
        thresholds.append(float(t))
    return pred, thresholds, models


def apply_to_mutated(Xm, folds, thresholds, models, target_orig_idx):
    """Score each mutated row with the model whose test fold owns the original.

    ``target_orig_idx[j]`` is the index in ``records`` of the attack that
    produced mutated row ``j``.  The targeted dilution subset is smaller than
    the attack set, so the mapping cannot be a positional attack index.
    """
    out = np.zeros(len(Xm), dtype=int)
    for (tr, te), t, model in zip(folds, thresholds, models):
        te_set = set(int(i) for i in te)
        sel = np.asarray(
            [j for j, orig in enumerate(target_orig_idx) if int(orig) in te_set],
            dtype=int,
        )
        if len(sel):
            out[sel] = (model.predict_proba(Xm[sel])[:, 1] >= t).astype(int)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targeted", action="store_true", help="also run dilution-only")
    args = parser.parse_args()

    records, _ = C.csic_unique()
    attacks = [r for r in records if r.label == 1]
    print(f"unique attacks: {len(attacks):,}", flush=True)

    # Bounded suite (same deterministic operators as the paper).
    mutated = []
    ops = []
    for r in attacks:
        new_rec, applied = A.mutate(r)
        mutated.append(new_rec)
        ops.append(applied)

    y = C.label_array(records)
    Xb, Xd = build(records)
    Xmb, Xmd = build(mutated)
    folds = list(StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED).split(Xb, y))
    attack_idx = np.asarray([i for i, r in enumerate(records) if r.label == 1], dtype=int)

    results = {}
    fitted = {}
    for name, X, Xm in (("v3", Xb, Xmb), ("v3-D", Xd, Xmd)):
        pred, thresholds, models = fit_contract(X, y, folds)
        fitted[name] = (thresholds, models, pred)
        mut_pred = apply_to_mutated(Xm, folds, thresholds, models, attack_idx)
        orig_attack = pred[attack_idx]
        clean = metrics_from_pred(y, pred)
        bounded = {
            "recall_original": float(orig_attack.mean()),
            "recall_mutated": float(mut_pred.mean()),
            "delta": float(mut_pred.mean() - orig_attack.mean()),
            "evaded": int(((orig_attack == 1) & (mut_pred == 0)).sum()),
        }
        per_op = []
        for op in A.ORDER:
            sel = np.asarray([op in o for o in ops])
            if not sel.any():
                continue
            per_op.append(
                {
                    "operator": op,
                    "n": int(sel.sum()),
                    "recall_original": float(orig_attack[sel].mean()),
                    "recall_mutated": float(mut_pred[sel].mean()),
                    "delta": float(mut_pred[sel].mean() - orig_attack[sel].mean()),
                    "evaded": int(((orig_attack[sel] == 1) & (mut_pred[sel] == 0)).sum()),
                }
            )
        results[name] = {
            "clean": clean,
            "thresholds": thresholds,
            "bounded": bounded,
            "per_operator": per_op,
        }
        print(name, clean, bounded, flush=True)

    # Targeted dilution: append the benign parameter to every attack that has
    # a query or body.  This isolates the operator instead of relying on the
    # hash-selected bounded suite.
    targeted = []
    targeted_idx = []
    for idx, rec in enumerate(records):
        if rec.label != 1:
            continue
        if rec.query:
            q = rec.query + "&natrix_probe=" + "a" * 48
            b = rec.body
        elif rec.body:
            q = rec.query
            b = rec.body + "&natrix_probe=" + "a" * 48
        else:
            continue
        payload = rec.path + (("?" + q) if q else "") + ((" " + b) if b else "")
        targeted.append(replace(rec, query=q, body=b, payload=payload))
        targeted_idx.append(idx)
    targeted_idx = np.asarray(targeted_idx, dtype=int)
    Xtb, Xtd = build(targeted)
    print(f"targeted dilution attacks: {len(targeted):,}", flush=True)

    targeted_results = {}
    for name, Xt in (("v3", Xtb), ("v3-D", Xtd)):
        thresholds, models, pred = fitted[name]
        mut_pred = apply_to_mutated(Xt, folds, thresholds, models, targeted_idx)
        orig_attack = pred[targeted_idx]
        targeted_results[name] = {
            "recall_original": float(orig_attack.mean()),
            "recall_mutated": float(mut_pred.mean()),
            "delta": float(mut_pred.mean() - orig_attack.mean()),
            "evaded": int(((orig_attack == 1) & (mut_pred == 0)).sum()),
        }
        print("targeted", name, targeted_results[name], flush=True)

    out = {
        "corpus": "CSIC 2010",
        "attacks": len(attacks),
        "variant": "v3-D (22 + 9 per-parameter/path maxima)",
        "extra_features": EXTRA_NAMES,
        "bounded_suite": results,
        "targeted_dilution": targeted_results,
    }
    C.write_json(OUT / "dilution_resistant.json", out)
    rows = []
    for name, res in results.items():
        rows.append({"contract": name, **res["bounded"]})
    pd.DataFrame(rows).to_csv(OUT / "dilution_resistant.csv", index=False)
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
