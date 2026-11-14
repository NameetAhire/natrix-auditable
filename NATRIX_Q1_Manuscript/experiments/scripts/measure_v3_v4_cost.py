"""Measure the v3 (22-D) versus v4 (20-D) extraction and ONNX cost.

The shipped extractor is v3 and the shipped gate is 22-D.  This script measures
the contract difference directly on the frozen latency inputs:

  * v3 extraction uses the production FeatureRegistry;
  * v4 extraction is a benchmark-only path that skips the two dropped
    features, using the same production helpers;
  * ONNX inference compares the shipped 22-D gate with a 20-D forest trained
    for timing only.  The 20-D model is not an accuracy artifact.

The timing model is trained on the same CSIC records with the shipped forest
configuration and exported to a temporary file; nothing in Ai-Agent is changed.

Output: experiments/results/latency/v3_v4_cost.json
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import feature_registry as FR  # noqa: E402

WARMUP = 300
OUT = C.RESULTS / "latency" / "v3_v4_cost.json"
SHIPPED_ONNX = C.ARTIFACTS / "models" / "gate_22d.onnx"


def pct(values, p):
    return float(np.percentile(values, p))


def payloads():
    items = json.loads((C.RESULTS / "latency" / "latency_inputs.json").read_text(encoding="utf-8"))
    for item in items:
        yield item["url"] + " " + (item["body"] or ""), item["userAgent"], item["method"]


def extract_v3(payload, ua, method):
    return FR.registry.extract_features(payload, user_agent=ua, method=method, version="v3")


def extract_v4(payload, ua, method):
    """Production helpers, minus the two CSIC-constant features."""
    features = FR.registry.extract_features(payload, user_agent=ua, method=method, version="v1")
    text = str(payload or "")[: FR.MAX_PAYLOAD_CHARS]
    length = len(text)
    lower = text.lower()
    combined = lower + " " + urllib.parse.unquote(text).lower()
    hex_chars = sum(len(m.group(0)) for m in FR.HEX_PATTERN.finditer(text))
    features.update({
        "command_injection_score": FR._command_injection_score(combined),
        "hex_encoding_ratio": FR._round4(hex_chars / max(1, length)),
        "null_byte_score": 1 if FR.NULL_BYTE_PATTERN.search(text) else 0,
        "request_method_risk": FR.METHOD_RISK_WEIGHTS.get(str(method or "GET").upper(), 0.5),
    })
    features.update(FR._lexical_features(text))
    return features


def time_extraction(fn, rows):
    times = []
    for i, (payload, ua, method) in enumerate(rows):
        t0 = time.perf_counter_ns()
        fn(payload, ua, method)
        t1 = time.perf_counter_ns()
        if i >= WARMUP:
            times.append((t1 - t0) / 1e6)
    return times


def median_p95_extraction(fn, rows, passes=3):
    return float(np.median([pct(time_extraction(fn, rows), 95) for _ in range(passes)]))


def median_p50_extraction(fn, rows, passes=3):
    return float(np.median([pct(time_extraction(fn, rows), 50) for _ in range(passes)]))


def time_onnx(session, matrix):
    times = []
    name = session.get_inputs()[0].name
    for i, row in enumerate(matrix):
        x = np.asarray(row, dtype=np.float32).reshape(1, -1)
        t0 = time.perf_counter_ns()
        session.run(None, {name: x})
        t1 = time.perf_counter_ns()
        if i >= WARMUP:
            times.append((t1 - t0) / 1e6)
    return times


def median_p95(session, matrix, passes=3):
    return float(np.median([pct(time_onnx(session, matrix), 95) for _ in range(passes)]))


def median_p50(session, matrix, passes=3):
    return float(np.median([pct(time_onnx(session, matrix), 50) for _ in range(passes)]))


def convert_v4_model(X3, y):
    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType

    names = list(C.FEATURES)
    definition = C.read_json(C.ARTIFACTS / "feature_selection" / "v4_definition.json")
    cols = [names.index(f) for f in definition["retained_core"]]
    X4 = X3[:, cols]
    model = C.make_rf()
    model.fit(X4, y)
    onnx_model = convert_sklearn(
        model,
        initial_types=[("input", FloatTensorType([None, len(cols)]))],
        target_opset=15,
        options={id(model): {"zipmap": False}},
    )
    return onnx_model, X4, cols


def main() -> None:
    rows = list(payloads())
    print(f"inputs: {len(rows):,}")

    import psutil
    proc = psutil.Process()
    proc.cpu_affinity([0])
    proc.nice(psutil.HIGH_PRIORITY_CLASS)

    v3_p95 = median_p95_extraction(extract_v3, rows)
    v4_p95 = median_p95_extraction(extract_v4, rows)
    v3_p50 = median_p50_extraction(extract_v3, rows)
    v4_p50 = median_p50_extraction(extract_v4, rows)
    print(f"extraction v3 p95={v3_p95:.4f} ms; v4 p95={v4_p95:.4f} ms")

    # The v4 vector must equal the v3 vector with the two dropped columns.
    definition = C.read_json(C.ARTIFACTS / "feature_selection" / "v4_definition.json")
    names = list(C.FEATURES)
    keep = [names.index(f) for f in definition["retained_core"]]
    dropped = [names.index(f) for f in definition["v3_features"] if f not in definition["retained_core"]]
    for payload, ua, method in rows[::997]:
        a = extract_v3(payload, ua, method)
        b = extract_v4(payload, ua, method)
        va = FR.registry.feature_dict_to_vector(a, version="v3")
        vb = FR.registry.feature_dict_to_vector(b, version="v3")
        assert [va[i] for i in keep] == [vb[i] for i in keep], "v4 vector mismatch"
        assert all(va[i] == 0 for i in dropped), "dropped feature is not constant zero"

    import onnxruntime as ort

    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL

    v3_sess = ort.InferenceSession(str(SHIPPED_ONNX), sess_options=options,
                                  providers=["CPUExecutionProvider"])
    records, _ = C.csic_unique()
    X3, _ = C.extract_matrix(records, dtype=np.float32)
    v4_model, X4, cols = convert_v4_model(X3, C.label_array(records))

    with tempfile.TemporaryDirectory() as tmp:
        v4_path = Path(tmp) / "gate_20d_timing.onnx"
        v4_path.write_bytes(v4_model.SerializeToString())
        v4_sess = ort.InferenceSession(str(v4_path), sess_options=options,
                                      providers=["CPUExecutionProvider"])
        v3_onnx_p95 = median_p95(v3_sess, X3)
        v4_onnx_p95 = median_p95(v4_sess, X4)
        v3_onnx_p50 = median_p50(v3_sess, X3)
        v4_onnx_p50 = median_p50(v4_sess, X4)

    report = {
        "protocol": (
            "single-row wall-clock, 300 warm-up, 3 passes, median p95; "
            "ONNX Runtime single-threaded; same machine and frozen inputs"
        ),
        "inputs": {
            "n": len(rows),
            "source": "experiments/results/latency/latency_inputs.json",
            "warmup": WARMUP,
        },
        "extraction": {
            "v3_22d_p95_ms": v3_p95,
            "v3_22d_p50_ms": v3_p50,
            "v4_20d_p95_ms": v4_p95,
            "v4_20d_p50_ms": v4_p50,
            "delta_p95_ms": v4_p95 - v3_p95,
        },
        "onnx_inference": {
            "v3_22d_p95_ms": v3_onnx_p95,
            "v3_22d_p50_ms": v3_onnx_p50,
            "v4_20d_p95_ms": v4_onnx_p95,
            "v4_20d_p50_ms": v4_onnx_p50,
            "delta_p95_ms": v4_onnx_p95 - v3_onnx_p95,
        },
        "note": (
            "v4 extraction uses the production helpers but skips the two "
            "CSIC-constant features; the v4 ONNX forest is trained for timing "
            "only and is not used for any accuracy claim."
        ),
    }
    C.write_json(OUT, report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
