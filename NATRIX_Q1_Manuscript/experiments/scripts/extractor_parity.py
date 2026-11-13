"""Cross-language extractor parity: Python FeatureRegistry vs proxy JS.

The existing ONNX parity test compares Python inference with ONNX inference on
the same Python-extracted vectors.  That leaves the JavaScript extractor, which
is the code actually on the request path, untested.  This script sends the same
payload/UA/method triples through both extractors and compares all 22 values.

Output: experiments/results/parity/extractor_parity.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

OUT = C.RESULTS / "parity"
OUT.mkdir(parents=True, exist_ok=True)
JS = C.AI_ROOT / "proxy" / "feature_extractor.js"


def sample_cases(n: int) -> list[dict]:
    records = []
    csic, _ = C.csic_unique()
    records.extend(csic)
    records.extend(C.load_ecml_records())
    # Deterministic, class-balanced sample.
    rng = np.random.default_rng(C.SEED)
    by_label = {0: [], 1: []}
    for rec in records:
        by_label[int(rec.label)].append(rec)
    take = []
    for label, group in by_label.items():
        idx = rng.choice(len(group), size=min(n // 2, len(group)), replace=False)
        take.extend(group[i] for i in idx)
    return [
        {
            "payload": r.payload,
            "user_agent": r.user_agent,
            "method": r.method,
            "label": int(r.label),
            "source": r.source,
        }
        for r in take
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=2000)
    args = parser.parse_args()

    cases = sample_cases(args.n)
    in_path = OUT / "extractor_parity_cases.jsonl"
    out_path = OUT / "extractor_parity_js.jsonl"
    with open(in_path, "w", encoding="utf-8") as handle:
        for case in cases:
            handle.write(json.dumps(case, ensure_ascii=False) + "\n")

    subprocess.run(
        ["node", str(OUT.parent.parent / "scripts" / "extractor_parity.js"),
         str(in_path), str(out_path)],
        check=True,
        cwd=str(C.AI_ROOT / "proxy"),
    )

    js_rows = [json.loads(line) for line in open(out_path, encoding="utf-8")]
    py_rows = []
    for case in cases:
        feats = C.registry.extract_features(
            case["payload"], user_agent=case["user_agent"],
            method=case["method"], version="v3",
        )
        py_rows.append(C.registry.feature_dict_to_vector(feats, version="v3"))

    py = np.asarray(py_rows, dtype=np.float64)
    js = np.asarray([row["vector"] for row in js_rows], dtype=np.float64)
    delta = np.abs(py - js)
    names = C.FEATURES
    per_feature = {
        name: {
            "max_abs_delta": float(delta[:, i].max()),
            "mean_abs_delta": float(delta[:, i].mean()),
            "mismatch_count": int((delta[:, i] > 1e-9).sum()),
        }
        for i, name in enumerate(names)
    }
    result = {
        "cases": len(cases),
        "features": names,
        "max_abs_delta": float(delta.max()),
        "mean_abs_delta": float(delta.mean()),
        "exact_mismatch_count": int((delta > 1e-9).any(axis=1).sum()),
        "per_feature": per_feature,
        "tolerance": 1e-9,
        "sources": {s: sum(1 for c in cases if c["source"] == s) for s in set(c["source"] for c in cases)},
    }
    C.write_json(OUT / "extractor_parity.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
