"""Serve the shipped NATRIX models through ONNX Runtime on port 5001.

This is a serving adapter, not a model change:

  * the 22-D gate and the 16-D threat-typing forest are the same artifacts
    shipped in Ai-Agent/models, converted by convert_gate_onnx.py;
  * the request validation, feature ordering, thresholding and response schema
    are the real functions from ml_engine/model_service.py;
  * only the estimator backend changes (scikit-learn -> ONNX Runtime), because
    sklearn's per-call overhead on a single row is ~9 ms and cannot meet the
    5 ms inline SLO.

Parity is verified in artifacts/models/onnx_parity.json.
"""

from __future__ import annotations

import argparse
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
ML_ENGINE = ROOT.parent / "Ai-Agent" / "ml_engine"
sys.path.insert(0, str(ML_ENGINE))

import model_service as ms  # noqa: E402


class OnnxForest:
    """Small adapter exposing the sklearn estimator surface used by the service."""

    def __init__(self, path: Path, classes, n_features: int):
        import onnxruntime as ort

        self.session = ort.InferenceSession(
            str(path), providers=["CPUExecutionProvider"]
        )
        self.classes_ = np.asarray(classes)
        self.n_features_in_ = n_features
        self.input_name = self.session.get_inputs()[0].name

    def predict_proba(self, X):
        matrix = np.asarray(X, dtype=np.float32)
        if matrix.ndim == 1:
            matrix = matrix.reshape(1, -1)
        return self.session.run(None, {self.input_name: matrix})[1]

    def predict(self, X):
        proba = self.predict_proba(X)
        return self.classes_[np.argmax(proba, axis=1)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5001)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    gate = OnnxForest(ROOT / "artifacts" / "models" / "gate_22d.onnx", [0, 1], 22)
    threat = OnnxForest(
        ROOT / "artifacts" / "models" / "threat_16d.onnx",
        ms.CLF_MODEL.classes_ if ms.CLF_MODEL is not None else [],
        16,
    )

    ms.BINARY_GATE = gate
    ms.BINARY_GATE_FEATURES = 22
    ms.BINARY_GATE_THRESHOLD = 0.5
    ms.BINARY_GATE_PATH = "artifacts/models/gate_22d.onnx"
    ms.CLF_MODEL = threat
    ms.THREAT_MODEL_FEATURES = 16
    ms.ACTIVE_SCHEMA_VERSION = "v3"
    ms.ACTIVE_FEATURE_COUNT = 22
    ms.ACTIVE_MODEL_VERSION = "v3-onnx"

    server = ThreadingHTTPServer((args.host, args.port), ms.MLSafetyHandler)
    server.daemon_threads = True
    print(
        f"[NATRIX] ONNX gate + typing service on {args.host}:{args.port} "
        f"(gate 22-D, threat 16-D)",
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
