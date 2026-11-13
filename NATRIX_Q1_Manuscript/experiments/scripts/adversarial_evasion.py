"""Bounded evasion test on real CSIC payloads.

The test asks a narrow question: if an attacker applies a small, deterministic
set of common encoding/case/comment mutations to an attack that NATRIX or CRS
already blocks, does the attack still get blocked?  It is not a search for an
adversarial example and it does not claim that every mutated payload remains
exploitable.

Protocol
--------
* Source: the 15,953 unique CSIC attacks used everywhere else.
* Folds: the same stratified 5-fold P1 split (seed 42).
* NATRIX: for each fold, train the shipped forest on the training folds, score
  the original and the mutated test attacks.  The decision threshold for a fold
  is selected on the *original* out-of-fold predictions of the other four folds
  at FPR <= 2%; mutated labels are never used for threshold selection.
* Mutation budget: at most three distinct applicable operators per payload,
  chosen deterministically from a hash of the payload.  The exact operators
  applied are recorded.  Both detectors see the identical mutated request, so
  the budget is the same for both.
* CRS: the mutated requests are replayed through the same frozen CRS sidecar
  configuration as the clean baseline.

Operators are chosen to be plausible for the affected parser, not guaranteed
semantics-preserving.  Per-operator results are reported so a reader can see
which transformation did the work.

Outputs
-------
experiments/results/adversarial/natrix_evasion.json
experiments/results/adversarial/mutated_csic_attacks.parquet
experiments/results/adversarial/mutation_summary.csv
"""

from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
from compare_v3_v4 import best_threshold, metrics_from_pred  # noqa: E402

OUT = C.RESULTS / "adversarial"
OUT.mkdir(parents=True, exist_ok=True)
SEED = 42

SQL_WORDS = re.compile(
    r"\b(select|union|where|from|and|or|order|by|insert|update|delete|drop|"
    r"sleep|benchmark|information_schema|having|group|limit|offset)\b",
    re.IGNORECASE,
)
HTML_WORDS = re.compile(r"\b(script|svg|iframe|img|body|html|onerror|onload)\b", re.IGNORECASE)
TRAVERSAL = re.compile(r"\.\./")
PERCENT_ESCAPE = re.compile(r"%[0-9a-fA-F]{2}")
SPACE = re.compile(r" ")


def _swap_case(match: re.Match) -> str:
    return "".join(ch.upper() if ch.islower() else ch.lower() for ch in match.group(0))


def op_case(text: str) -> tuple[str, bool]:
    changed = False
    if SQL_WORDS.search(text) or HTML_WORDS.search(text):
        new = SQL_WORDS.sub(_swap_case, text)
        new = HTML_WORDS.sub(_swap_case, new)
        changed = new != text
        return new, changed
    return text, False


def op_sql_comment(text: str) -> tuple[str, bool]:
    # Only between two SQL tokens; this is the classic comment-insertion evasion.
    # The separator may be literal whitespace, a form-encoded space, or %20.
    pattern = re.compile(
        r"\b(select|union|where|from|and|or|order|by|insert|update|delete|drop)\b"
        r"(?:\+|%20|\s)+"
        r"\b(select|where|from|and|or|order|by|insert|update|delete|drop|sleep|benchmark)\b",
        re.IGNORECASE,
    )
    new, n = pattern.subn(r"\1/**/\2", text, count=1)
    return new, n > 0


def op_dilution(text: str) -> tuple[str, bool]:
    """Append an ignored benign parameter to dilute aggregate payload ratios."""
    if not text:
        return text, False
    return text + "&natrix_probe=" + "a" * 48, True


def op_percent_encode(text: str) -> tuple[str, bool]:
    for ch in ("'", "<", ">", "(", ")", " "):
        idx = text.find(ch)
        if idx >= 0:
            return text[:idx] + f"%{ord(ch):02X}" + text[idx + 1:], True
    return text, False


def op_double_encode(text: str) -> tuple[str, bool]:
    match = PERCENT_ESCAPE.search(text)
    if not match:
        return text, False
    return text[: match.start()] + "%25" + text[match.start() + 1:], True


def op_plus_space(text: str) -> tuple[str, bool]:
    match = SPACE.search(text)
    if not match:
        return text, False
    return text[: match.start()] + "+" + text[match.start() + 1:], True


def op_traversal_encode(text: str) -> tuple[str, bool]:
    match = TRAVERSAL.search(text)
    if not match:
        return text, False
    return text[: match.start()] + "..%2f" + text[match.start() + 3:], True


OPERATORS = {
    "case": op_case,
    "sql_comment": op_sql_comment,
    "percent_encode": op_percent_encode,
    "double_encode": op_double_encode,
    "plus_space": op_plus_space,
    "traversal_encode": op_traversal_encode,
    "dilution": op_dilution,
}
ORDER = list(OPERATORS)


def mutate(rec) -> tuple[object, list[str]]:
    """Apply up to three distinct applicable operators, deterministically."""
    digest = hashlib.blake2b(rec.payload.encode("utf-8", "replace"), digest_size=8).digest()
    offset = int.from_bytes(digest, "big") % len(ORDER)
    order = ORDER[offset:] + ORDER[:offset]

    query, body = rec.query, rec.body
    applied: list[str] = []
    for name in order:
        if len(applied) >= 3:
            break
        fn = OPERATORS[name]
        if name in ("traversal_encode",):
            new_query, changed = fn(query)
            if changed:
                query = new_query
                applied.append(name)
                continue
            new_body, changed = fn(body)
            if changed:
                body = new_body
                applied.append(name)
            continue
        # Text operators are applied to the query first, then the body.
        new_query, changed = fn(query)
        if changed:
            query = new_query
            applied.append(name)
            continue
        new_body, changed = fn(body)
        if changed:
            body = new_body
            applied.append(name)

    if not applied:
        return rec, applied
    payload = rec.path
    if query:
        payload += "?" + query
    if body:
        payload += " " + body
    return replace(rec, query=query, body=body, payload=payload), applied


def main() -> None:
    records, _ = C.csic_unique()
    attacks = [r for r in records if r.label == 1]
    print(f"unique attacks: {len(attacks):,}", flush=True)

    mutated: list[object] = []
    operators: list[list[str]] = []
    for rec in attacks:
        new_rec, applied = mutate(rec)
        mutated.append(new_rec)
        operators.append(applied)
    coverage = sum(1 for ops in operators if ops)
    print(f"mutated: {coverage:,}/{len(attacks):,} ({coverage / len(attacks):.1%})", flush=True)

    # Save the mutated requests for the CRS replay.
    frame = pd.DataFrame([
        {
            "rid": rec.rid, "method": rec.method, "path": rec.path,
            "query": rec.query, "body": rec.body, "user_agent": rec.user_agent,
            "content_type": rec.headers.get("content-type", ""),
            "label": 1, "operators": ";".join(ops),
            "original_rid": orig.rid,
        }
        for rec, ops, orig in zip(mutated, operators, attacks)
    ])
    frame.to_parquet(OUT / "mutated_csic_attacks.parquet", index=False)

    X, _ = C.extract_matrix(records, dtype=np.float32)
    y = C.label_array(records)
    X_mut, _ = C.extract_matrix(mutated, dtype=np.float32)

    folds = list(StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED).split(X, y))
    # Map attack record index -> position in the attack-only mutated matrix.
    attack_pos = {id(rec): i for i, rec in enumerate(attacks)}
    oof_original = np.zeros(len(y), dtype=np.float32)
    mutated_proba = np.full(len(attacks), np.nan, dtype=np.float32)

    for tr, te in folds:
        model = C.make_rf(random_state=SEED)
        model.fit(X[tr], y[tr])
        oof_original[te] = model.predict_proba(X[te])[:, 1]
        te_attack_idx = [i for i in te if y[i] == 1]
        positions = np.asarray([attack_pos[id(records[i])] for i in te_attack_idx], dtype=int)
        mutated_proba[positions] = model.predict_proba(X_mut[positions])[:, 1]

    original_proba_attacks = oof_original[y == 1]
    if np.isnan(mutated_proba).any():
        raise SystemExit("some attacks were not scored")

    # Per-fold thresholds from the original OOF predictions of the other folds.
    pred_original = np.zeros(len(y), dtype=int)
    pred_mutated = np.zeros(len(attacks), dtype=int)
    thresholds = []
    for tr, te in folds:
        mask = np.ones(len(y), dtype=bool)
        mask[te] = False
        t = best_threshold(oof_original[mask], y[mask], fpr_cap=0.02)
        thresholds.append(t)
        pred_original[te] = (oof_original[te] >= t).astype(int)
        te_attack_idx = [i for i in te if y[i] == 1]
        positions = np.asarray([attack_pos[id(records[i])] for i in te_attack_idx], dtype=int)
        pred_mutated[positions] = (mutated_proba[positions] >= t).astype(int)

    orig_attack_pred = pred_original[y == 1]
    rows = []
    for name in ORDER:
        sel = np.asarray([name in ops for ops in operators])
        if not sel.any():
            continue
        rows.append({
            "operator": name,
            "n": int(sel.sum()),
            "recall_original": float(orig_attack_pred[sel].mean()),
            "recall_mutated": float(pred_mutated[sel].mean()),
            "delta": float(pred_mutated[sel].mean() - orig_attack_pred[sel].mean()),
            "evaded": int(((orig_attack_pred[sel] == 1) & (pred_mutated[sel] == 0)).sum()),
        })
    per_operator = pd.DataFrame(rows)
    per_operator.to_csv(OUT / "mutation_summary.csv", index=False)

    originally_blocked = orig_attack_pred == 1
    evasion = int(((orig_attack_pred == 1) & (pred_mutated == 0)).sum())
    rescue = int(((orig_attack_pred == 0) & (pred_mutated == 1)).sum())

    result = {
        "corpus": "CSIC 2010",
        "attacks": int(len(attacks)),
        "mutated": int(coverage),
        "coverage": float(coverage / len(attacks)),
        "operators": ORDER,
        "budget": 3,
        "threshold_policy": "leave-one-fold-out on original OOF, FPR<=2%",
        "thresholds": thresholds,
        "natrix": {
            "recall_original": float(orig_attack_pred.mean()),
            "recall_mutated": float(pred_mutated.mean()),
            "delta": float(pred_mutated.mean() - orig_attack_pred.mean()),
            "originally_blocked": int(originally_blocked.sum()),
            "evaded": evasion,
            "evasion_rate_among_blocked": float(evasion / originally_blocked.sum()) if originally_blocked.any() else 0.0,
            "rescue": rescue,
        },
        "per_operator": per_operator.to_dict("records"),
        "notes": [
            "Mutations are deterministic and bounded; this is not an adversarial search.",
            "Per-operator results overlap because a payload may receive up to three operators.",
            "A mutated payload is not guaranteed to remain exploitable; the test measures detector stability under common transformations.",
        ],
    }
    C.write_json(OUT / "natrix_evasion.json", result)
    print(pd.DataFrame(result["per_operator"]).to_string(index=False))
    print(f"NATRIX recall {result['natrix']['recall_original']:.4f} -> "
          f"{result['natrix']['recall_mutated']:.4f}, evasion "
          f"{result['natrix']['evasion_rate_among_blocked']:.2%} of blocked attacks")


if __name__ == "__main__":
    main()
