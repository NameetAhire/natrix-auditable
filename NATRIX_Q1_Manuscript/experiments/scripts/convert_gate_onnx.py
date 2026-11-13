"""Convert the shipped joblib forests to ONNX and verify numeric parity.

The inline path needs single-row inference well below 1 ms.  scikit-learn's
per-call overhead on a single row is ~9 ms even with n_jobs=1, while the same
forest executed by ONNX Runtime is ~0.03 ms.  This script:

  1. converts the 22-D binary gate and the 16-D threat-typing forest;
  2. compares ONNX probabilities against joblib on real feature matrices and on
     random vectors;
  3. writes a parity report used by the latency section of the paper.

The ONNX artifacts are byte-for-byte derived from the shipped joblib models;
no retraining happens here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

AI = C.AI_ROOT
OUT = C.ARTIFACTS / "models"
OUT.mkdir(parents=True, exist_ok=True)

GATE_JOBLIB = AI / "models" / "csic_binary_22d" / "threat_classifier.joblib"
THREAT_JOBLIB = AI / "models" / "v2.0" / "threat_classifier.joblib"


def convert(model, n_features: int, path: Path) -> None:
    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType

    onnx_model = convert_sklearn(
        model,
        initial_types=[("input", FloatTensorType([None, n_features]))],
        target_opset=15,
        options={id(model): {"zipmap": False}},
    )
    path.write_bytes(onnx_model.SerializeToString())


def session(path: Path):
    import onnxruntime as ort

    return ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])


def probabilities(sess, X):
    return sess.run(None, {"input": np.asarray(X, dtype=np.float32)})[1]


def main() -> None:
    import joblib

    gate = joblib.load(GATE_JOBLIB)
    threat = joblib.load(THREAT_JOBLIB)
    convert(gate, 22, OUT / "gate_22d.onnx")
    convert(threat, 16, OUT / "threat_16d.onnx")
    print("converted", (OUT / "gate_22d.onnx").stat().st_size,
          (OUT / "threat_16d.onnx").stat().st_size)

    # Real matrices: CSIC, SR-BH and the OpenAppSec corpus.
    records, _ = C.csic_unique()
    X_csic, _ = C.extract_matrix(records, dtype=np.float32)
    z = np.load(C.PROCESSED / "srbh" / "srbh_features.npz", allow_pickle=True)
    X_srbh = z["X"]
    w = np.load(C.PROCESSED / "openappsec" / "wcp_features.npz", allow_pickle=True)
    X_wcp = w["X"]

    rng = np.random.default_rng(42)
    samples = {
        "csic": X_csic,
        "srbh": X_srbh[rng.choice(len(X_srbh), 20000, replace=False)],
        "wcp": X_wcp[rng.choice(len(X_wcp), 20000, replace=False)],
        "random": rng.random((5000, 22), dtype=np.float32),
    }

    gate_sess = session(OUT / "gate_22d.onnx")
    max_diff = 0.0
    disagreements = 0
    non_tie_disagreements = 0
    checked = 0
    per_corpus = {}
    for name, matrix in samples.items():
        ref = gate.predict_proba(matrix)[:, 1]
        got = probabilities(gate_sess, matrix)[:, 1]
        diff = float(np.max(np.abs(ref - got)))
        disagree_mask = (ref >= 0.5) != (got >= 0.5)
        disagree = int(np.sum(disagree_mask))
        non_tie = int(np.sum(disagree_mask & (np.abs(ref - 0.5) > 1e-6)))
        per_corpus[name] = {"records": int(len(matrix)), "max_abs_diff": diff,
                            "label_disagreements": disagree,
                            "non_tie_disagreements": non_tie}
        max_diff = max(max_diff, diff)
        disagreements += disagree
        non_tie_disagreements += non_tie
        checked += len(matrix)

    threat_sess = session(OUT / "threat_16d.onnx")
    X16 = X_csic[:, :16]
    ref_label = threat.predict(X16)
    got_probs = probabilities(threat_sess, X16)
    classes = list(threat.classes_)
    got_label = np.asarray(classes)[np.argmax(got_probs, axis=1)]
    ref_probs = threat.predict_proba(X16)
    label_mismatch = int(np.sum(ref_label != got_label))
    # A mismatch is only meaningful if the two top classes are not tied.
    sorted_ref = np.sort(ref_probs, axis=1)
    top_gap = sorted_ref[:, -1] - sorted_ref[:, -2]
    non_tie_mismatch = int(np.sum((ref_label != got_label) & (top_gap > 1e-6)))
    type_max_diff = float(np.max(np.abs(ref_probs - got_probs)))

    report = {
        "gate_joblib": str(GATE_JOBLIB.relative_to(C.ROOT.parent)),
        "gate_onnx": str((OUT / "gate_22d.onnx").relative_to(C.ROOT)),
        "threat_joblib": str(THREAT_JOBLIB.relative_to(C.ROOT.parent)),
        "threat_onnx": str((OUT / "threat_16d.onnx").relative_to(C.ROOT)),
        "records_checked": checked,
        "gate_max_abs_probability_diff": max_diff,
        "gate_label_disagreements": disagreements,
        "gate_non_tie_disagreements": non_tie_disagreements,
        "gate_per_corpus": per_corpus,
        "threat_label_mismatches": label_mismatch,
        "threat_non_tie_mismatches": non_tie_mismatch,
        "threat_max_abs_probability_diff": type_max_diff,
        "pass": bool(
            max_diff < 1e-5
            and non_tie_disagreements == 0
            and non_tie_mismatch == 0
        ),
    }
    C.write_json(OUT / "onnx_parity.json", report)
    print(json.dumps(report, indent=2))
    if not report["pass"]:
        raise SystemExit("ONNX parity check failed")


if __name__ == "__main__":
    main()
