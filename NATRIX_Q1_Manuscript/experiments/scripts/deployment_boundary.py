"""Measure the deployed enforcement boundary ("applicable" predicate).

The shipped proxy does not block on a learned score alone.  It blocks only
when the request also carries an independent lexical signal
(`gateHasLexicalSignal` in proxy/server.js).  This script reproduces that
predicate on the labelled corpora and reports what the conjunctive rule
costs and buys relative to the model-only rule at the deployed threshold.

Outputs:
  experiments/results/deployment_boundary.json
  tables/deployment_boundary.md
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

OUT = C.RESULTS / "deployment_boundary"
OUT.mkdir(parents=True, exist_ok=True)
THRESHOLD = 0.5


def applicable(features: dict) -> bool:
    """Mirror of gateHasLexicalSignal() in Ai-Agent/proxy/server.js."""
    return bool(
        features.get("null_byte_score", 0) > 0
        or features.get("command_injection_score", 0) > 0
        or features.get("sql_keyword_score", 0) > 0
        or features.get("xss_keyword_score", 0) > 0
        or features.get("path_traversal_score", 0) > 0
        or features.get("hex_encoding_ratio", 0) > 0.2
        or features.get("suspicious_extension_flag", 0) > 0
    )


def applicability(records) -> np.ndarray:
    flags = []
    for rec in records:
        feats = C.registry.extract_features(
            rec.payload, user_agent=rec.user_agent, method=rec.method, version="v3"
        )
        flags.append(applicable(feats))
    return np.asarray(flags, dtype=bool)


def metrics(y: np.ndarray, pred: np.ndarray) -> dict:
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    n = len(y)
    return {
        "n": int(n),
        "tp": int(tp), "fp": int(fp), "tn": int(tn), "fn": int(fn),
        "accuracy": round(float((tp + tn) / n), 4),
        "fpr": round(float(fp / (fp + tn)) if (fp + tn) else 0.0, 4),
        "recall": round(float(tp / (tp + fn)) if (tp + fn) else 0.0, 4),
        "precision": round(float(tp / (tp + fp)) if (tp + fp) else 0.0, 4),
    }


def load_applicability(corpus: str):
    cache = OUT / f"applicability_{corpus}.npz"
    if cache.exists():
        return np.load(cache)["flags"]
    if corpus == "csic":
        records, _ = C.csic_unique()
    elif corpus == "ecml":
        records = C.load_ecml_records()
    elif corpus == "srbh20k":
        frame = pd.read_parquet(C.RESULTS / "baselines" / "srbh_sample20k_requests.parquet")
        records = [
            C.make_request(
                rid=str(i), source="srbh", label=int(row.label),
                method=row.method,
                target=row.path + (("?" + row.query) if row.query else ""),
                body=row.body, user_agent=row.user_agent,
                declared_class=row.family,
            )
            for i, row in enumerate(frame.itertuples(index=False))
        ]
    else:
        raise ValueError(corpus)
    flags = applicability(records)
    np.savez(cache, flags=flags)
    return flags


def evaluate(corpus: str, protocol: str, oof_path: Path) -> dict:
    z = np.load(oof_path, allow_pickle=True)
    y = z["y"].astype(int)
    proba = z["proba"].astype(float)
    flags = load_applicability(corpus)
    assert len(flags) == len(y), f"{corpus} {protocol}: flags {len(flags)} != labels {len(y)}"
    model = (proba >= THRESHOLD).astype(int)
    conjunctive = ((proba >= THRESHOLD) & flags).astype(int)
    return {
        "corpus": corpus,
        "protocol": protocol,
        "threshold": THRESHOLD,
        "applicable_rate_clean": round(float(flags[y == 0].mean()), 4),
        "applicable_rate_attack": round(float(flags[y == 1].mean()), 4),
        "model_only": metrics(y, model),
        "conjunctive": metrics(y, conjunctive),
    }


def main() -> None:
    cases = [
        ("csic", "P1", C.RESULTS / "corpora" / "csic_P1_oof.npz"),
        ("csic", "P2", C.RESULTS / "corpora" / "csic_P2_oof.npz"),
        ("ecml", "P1", C.RESULTS / "corpora" / "ecml_P1_oof.npz"),
        ("ecml", "P2", C.RESULTS / "corpora" / "ecml_P2_oof.npz"),
        ("srbh20k", "P1", C.RESULTS / "baselines" / "natrix_srbh_sample20k_oof.npz"),
        ("srbh20k", "P2", C.RESULTS / "baselines" / "natrix_srbh_sample20k_P2_oof.npz"),
    ]
    rows = [evaluate(*case) for case in cases]
    C.write_json(OUT / "deployment_boundary.json", {"rows": rows})

    lines = [
        "| Corpus | Split | Applicable clean | Applicable attack | Model-only accuracy | Model-only FPR | Model-only recall | Conjunctive accuracy | Conjunctive FPR | Conjunctive recall |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        m, c = r["model_only"], r["conjunctive"]
        lines.append(
            f"| {r['corpus']} | {r['protocol']} | {r['applicable_rate_clean']*100:.1f}% | "
            f"{r['applicable_rate_attack']*100:.1f}% | {m['accuracy']*100:.2f} | {m['fpr']*100:.2f} | "
            f"{m['recall']*100:.2f} | {c['accuracy']*100:.2f} | {c['fpr']*100:.2f} | {c['recall']*100:.2f} |"
        )
    (C.TABLES / "deployment_boundary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
