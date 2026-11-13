from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import math
import os
import glob
from feature_registry import registry

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_ROOT = os.path.join(REPO_ROOT, "models")

# Optional 22-D gate.  This is the model that was actually measured on CSIC
# 2010 (95.55% unique-request CV, 95.38% external holdout at threshold 0.5).
BINARY_GATE_PATHS = (
    os.path.join(MODELS_ROOT, "csic_binary_22d", "threat_classifier.joblib"),
    os.path.join(MODELS_ROOT, "csic_binary", "threat_classifier.joblib"),
)

# Global state for ML Model & Pipeline
CLF_MODEL = None
ISO_MODEL = None
BINARY_GATE = None
BINARY_GATE_THRESHOLD = 0.5
BINARY_GATE_FEATURES = 0
BINARY_GATE_PATH = None
THREAT_MODEL_FEATURES = 0
ACTIVE_MODEL_VERSION = "deterministic-fallback"
ACTIVE_SCHEMA_VERSION = "v3"  # Defaults to the 22-D contract
ACTIVE_FEATURE_COUNT = 22
ACTIVE_FEATURE_NAMES = registry.get_feature_names("v3")


def _coerce_number(value, name):
    """Reject NaN/Infinity and non-numeric values before they reach sklearn."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"Feature '{name}' must be numeric")
    if not math.isfinite(number):
        raise ValueError(f"Feature '{name}' must be finite")
    return number


def _features_from_request(data):
    """
    Accept either a precomputed vector from the Node proxy or a raw payload.

    Two shapes are supported:
      {"features": [22 numbers], "featureNames": [...]}
      {"features": {"payload_length": 42, ...}, "featureNames": [...]}

    Older callers may still send 10 or 16 values.  Any active-model feature the
    caller did not provide is re-extracted from the payload instead of feeding a
    short vector to sklearn.
    """
    incoming = data.get("features")
    incoming_names = data.get("featureNames")
    requested_version = data.get("version") or ACTIVE_SCHEMA_VERSION
    payload = data.get("payload", "")
    user_agent = data.get("userAgent", "")
    method = data.get("method", "GET")

    required_names = registry.get_feature_names(ACTIVE_SCHEMA_VERSION)
    provided = None

    if isinstance(incoming, dict):
        provided = {str(name): _coerce_number(value, str(name)) for name, value in incoming.items()}
    elif isinstance(incoming, (list, tuple)):
        names = incoming_names or registry.get_feature_names(requested_version)
        if not isinstance(names, (list, tuple)) or len(names) != len(incoming):
            raise ValueError("featureNames must be a list with the same length as features")
        if len(names) > 64:
            raise ValueError("Too many feature names")
        provided = {
            str(name): _coerce_number(value, str(name))
            for name, value in zip(names, incoming)
        }
    elif incoming is not None:
        raise ValueError("features must be an array or an object")

    missing = [name for name in required_names if not provided or name not in provided]
    if provided is None or missing:
        features = registry.extract_features(
            payload,
            user_agent=user_agent,
            method=method,
            version=ACTIVE_SCHEMA_VERSION,
        )
        source = "extracted"
    else:
        features = {name: provided[name] for name in required_names}
        source = "precomputed"

    vector = [features[name] for name in required_names]
    if len(vector) != ACTIVE_FEATURE_COUNT:
        raise ValueError(
            f"Active model {ACTIVE_MODEL_VERSION} expects {ACTIVE_FEATURE_COUNT} features, got {len(vector)}"
        )

    return features, vector, requested_version, source


def _model_feature_count(model):
    count = getattr(model, "n_features_in_", None)
    return int(count) if count is not None else None


def _load_binary_gate():
    """Load the measured 22-D CSIC gate if it is present."""
    global BINARY_GATE, BINARY_GATE_THRESHOLD, BINARY_GATE_FEATURES, BINARY_GATE_PATH
    try:
        import joblib
    except Exception as exc:  # pragma: no cover - joblib ships with sklearn
        print(f"[ML Model Service] joblib unavailable; binary gate disabled ({exc})")
        return

    for path in BINARY_GATE_PATHS:
        if not os.path.exists(path):
            continue
        model = joblib.load(path)
        features = _model_feature_count(model)
        if features not in (16, 22):
            print(f"[ML Model Service] Ignoring binary gate {path}: unsupported {features} features")
            continue
        threshold = 0.5
        metadata_path = os.path.join(os.path.dirname(path), "metadata.json")
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, "r", encoding="utf-8") as handle:
                    threshold = float(json.load(handle).get("decision_threshold", 0.5))
            except Exception:
                threshold = 0.5
        BINARY_GATE = model
        BINARY_GATE_FEATURES = features
        BINARY_GATE_THRESHOLD = threshold
        BINARY_GATE_PATH = os.path.relpath(path, REPO_ROOT)
        print(f"[ML Model Service] Loaded binary attack gate {BINARY_GATE_PATH} "
              f"({features} features, threshold {threshold})")
        return

    print("[ML Model Service] No CSIC binary gate found; using threat-type model only")


def load_latest_models():
    """
    Load the threat-type classifier and the measured binary gate.

    The threat classifier (v2.0) is a 16-D 7-class model trained on the small
    curated NATRIX corpus; it supplies the threat label.  The binary gate is the
    22-D CSIC model whose held-out accuracy is reported in
    ml_engine/CSIC_EVALUATION_REPORT.md and is authoritative for is_attack.
    """
    global CLF_MODEL, ISO_MODEL, ACTIVE_MODEL_VERSION, ACTIVE_SCHEMA_VERSION
    global ACTIVE_FEATURE_COUNT, ACTIVE_FEATURE_NAMES, THREAT_MODEL_FEATURES
    global BINARY_GATE, BINARY_GATE_FEATURES, BINARY_GATE_THRESHOLD, BINARY_GATE_PATH
    try:
        import joblib
        candidate_dirs = sorted(glob.glob(os.path.join(MODELS_ROOT, "v*")), reverse=True)
        clf_loaded = False
        CLF_MODEL = None
        ISO_MODEL = None

        # Check versioned directories first (e.g., models/v2.0, models/v1.0)
        for v_dir in candidate_dirs:
            clf_path = os.path.join(v_dir, "threat_classifier.joblib")
            iso_path = os.path.join(v_dir, "anomaly_detector.joblib")
            if os.path.exists(clf_path):
                CLF_MODEL = joblib.load(clf_path)
                ACTIVE_MODEL_VERSION = os.path.basename(v_dir)
                clf_loaded = True
                print(f"[ML Model Service] Loaded threat-type model from {clf_path} "
                      f"(Version: {ACTIVE_MODEL_VERSION})")
                if os.path.exists(iso_path):
                    ISO_MODEL = joblib.load(iso_path)
                break

        # Fallback to root models directory
        if not clf_loaded and os.path.exists(os.path.join(MODELS_ROOT, "threat_classifier.joblib")):
            CLF_MODEL = joblib.load(os.path.join(MODELS_ROOT, "threat_classifier.joblib"))
            ACTIVE_MODEL_VERSION = "v1.0-legacy"
            clf_loaded = True
            print("[ML Model Service] Loaded classifier model from models/threat_classifier.joblib")

        THREAT_MODEL_FEATURES = _model_feature_count(CLF_MODEL) or 16

        _load_binary_gate()

        # The runtime contract is v3 (22-D) whenever the gate needs 22 features.
        # A 16-D gate can be sliced from the same v3 vector.
        ACTIVE_SCHEMA_VERSION = "v3"
        ACTIVE_FEATURE_COUNT = 22
        if BINARY_GATE is None and THREAT_MODEL_FEATURES == 10:
            ACTIVE_SCHEMA_VERSION = "v1"
            ACTIVE_FEATURE_COUNT = 10
        elif BINARY_GATE is None and THREAT_MODEL_FEATURES == 16:
            ACTIVE_SCHEMA_VERSION = "v2"
            ACTIVE_FEATURE_COUNT = 16

        ACTIVE_FEATURE_NAMES = registry.get_feature_names(ACTIVE_SCHEMA_VERSION)
        print(f"[ML Model Service] Active pipeline schema: {ACTIVE_SCHEMA_VERSION} "
              f"({ACTIVE_FEATURE_COUNT} features); threat model expects "
              f"{THREAT_MODEL_FEATURES}, gate expects {BINARY_GATE_FEATURES or 0}")
        return True, ACTIVE_MODEL_VERSION, ACTIVE_FEATURE_COUNT
    except Exception as e:
        print(f"[ML Model Service] Note: Running in deterministic ML feature evaluator mode ({e})")
        CLF_MODEL = None
        ISO_MODEL = None
        BINARY_GATE = None
        THREAT_MODEL_FEATURES = 0
        BINARY_GATE_FEATURES = 0
        ACTIVE_MODEL_VERSION = "deterministic-fallback"
        ACTIVE_SCHEMA_VERSION = "v3"
        ACTIVE_FEATURE_COUNT = 22
        ACTIVE_FEATURE_NAMES = registry.get_feature_names("v3")
        return False, str(e), 22


# Initial load on startup
load_latest_models()


def _predict_threat_type(features, vector):
    """Return (threat_type, confidence, anomaly_score, gate_info)."""
    gate_info = None
    gate_probability = None
    gate_attack = False

    if BINARY_GATE is not None and BINARY_GATE_FEATURES:
        gate_vector = vector[:BINARY_GATE_FEATURES]
        try:
            probabilities = BINARY_GATE.predict_proba([gate_vector])[0]
            classes = list(getattr(BINARY_GATE, "classes_", [0, 1]))
            attack_index = classes.index(1) if 1 in classes else len(classes) - 1
            gate_probability = float(probabilities[attack_index])
            gate_attack = gate_probability >= BINARY_GATE_THRESHOLD
            gate_info = {
                "model": BINARY_GATE_PATH,
                "features": BINARY_GATE_FEATURES,
                "threshold": BINARY_GATE_THRESHOLD,
                "probability": round(gate_probability, 6),
                "is_attack": bool(gate_attack),
            }
        except Exception as exc:
            gate_info = {"model": BINARY_GATE_PATH, "error": str(exc)}

    threat_type = "CLEAN"
    confidence = 98.0
    if CLF_MODEL is not None and hasattr(CLF_MODEL, "predict"):
        threat_vector = vector[:THREAT_MODEL_FEATURES]
        predicted = str(CLF_MODEL.predict([threat_vector])[0])
        type_confidence = 98.0
        if hasattr(CLF_MODEL, "predict_proba"):
            probabilities = CLF_MODEL.predict_proba([threat_vector])[0]
            type_confidence = round(float(max(probabilities)) * 100, 2)
        if gate_info is not None:
            # The measured gate decides whether this is an attack.  The 7-class
            # model only names it; if it says CLEAN while the gate fires, use a
            # generic label rather than pretending a sub-type was identified.
            if gate_attack:
                threat_type = predicted if predicted.upper() != "CLEAN" else "Suspicious HTTP Request"
                confidence = max(type_confidence, round(gate_probability * 100, 2))
            else:
                threat_type = "CLEAN"
                confidence = round((1.0 - gate_probability) * 100, 2)
        else:
            threat_type = predicted
            confidence = type_confidence
    elif gate_info is not None:
        threat_type = "Suspicious HTTP Request" if gate_attack else "CLEAN"
        confidence = round((gate_probability if gate_attack else 1.0 - gate_probability) * 100, 2)

    if gate_info is not None and gate_probability is not None:
        anomaly_score = round(gate_probability, 6)
    elif threat_type.upper() != "CLEAN":
        anomaly_score = 0.95
    else:
        anomaly_score = 0.05
    return threat_type, confidence, anomaly_score, gate_info


class MLSafetyHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/predict':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body.decode('utf-8'))
                if not isinstance(data, dict):
                    raise ValueError("Request body must be a JSON object")

                # 1. Features: precomputed 22-D vector from the proxy, or payload fallback
                features, vec, requested_version, source = _features_from_request(data)

                # 2. Prediction
                if CLF_MODEL is not None or BINARY_GATE is not None:
                    threat_type, confidence, anomaly_score, gate_info = _predict_threat_type(features, vec)
                    is_anomaly = bool(gate_info and gate_info.get("is_attack"))
                    if gate_info is None:
                        is_anomaly = threat_type.upper() != "CLEAN"
                else:
                    # Statistical Feature Weights Fallback (Zero-Dependency High Performance)
                    threat_type = "CLEAN"
                    confidence = 98.0
                    anomaly_score = 0.05
                    gate_info = None
                    if features.get("command_injection_score", 0) > 0:
                        threat_type = "Command Injection"
                        confidence = 95.0
                        anomaly_score = 0.93
                    elif features.get("null_byte_score", 0) > 0:
                        threat_type = "Path Traversal"
                        confidence = 92.0
                        anomaly_score = 0.85
                    elif features.get("sql_keyword_score", 0) > 0:
                        threat_type = "SQL Injection"
                        confidence = 96.5
                        anomaly_score = 0.92
                    elif features.get("xss_keyword_score", 0) > 0 or features.get("html_tag_density", 0) > 0.5:
                        threat_type = "Cross-Site Scripting (XSS)"
                        confidence = 94.0
                        anomaly_score = 0.88
                    elif features.get("path_traversal_score", 0) > 0:
                        threat_type = "Path Traversal"
                        confidence = 92.0
                        anomaly_score = 0.85
                    elif features.get("user_agent_anomaly", 0) == 1:
                        threat_type = "Reconnaissance"
                        confidence = 95.0
                        anomaly_score = 0.80
                    elif features.get("request_method_risk", 0) >= 0.8:
                        threat_type = "Reconnaissance"
                        confidence = 90.0
                        anomaly_score = 0.70
                    is_anomaly = anomaly_score > 0.6

                response = {
                    "status": "success",
                    "threatType": threat_type,
                    "confidence": confidence,
                    "anomalyScore": anomaly_score,
                    "isAnomaly": is_anomaly,
                    "pipeline_version": ACTIVE_MODEL_VERSION,
                    "schema_version": ACTIVE_SCHEMA_VERSION,
                    "requested_schema_version": requested_version,
                    "feature_count": len(vec),
                    "feature_names": ACTIVE_FEATURE_NAMES,
                    "features": features,
                    "feature_vector": vec,
                    "feature_source": source,
                    "binary_gate": gate_info,
                }

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode('utf-8'))
                return

            except Exception as e:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
                return

        elif self.path == '/reload_model':
            # Zero-delay dynamic hot-reload endpoint
            success, msg, feats = load_latest_models()
            res = {
                "status": "reloaded" if success else "fallback",
                "message": f"Pipeline updated to {ACTIVE_MODEL_VERSION}",
                "model_version": ACTIVE_MODEL_VERSION,
                "schema_version": ACTIVE_SCHEMA_VERSION,
                "features_count": feats,
                "binary_gate": {
                    "model": BINARY_GATE_PATH,
                    "features": BINARY_GATE_FEATURES,
                    "threshold": BINARY_GATE_THRESHOLD,
                } if BINARY_GATE is not None else None,
                "feature_names": registry.get_feature_names(ACTIVE_SCHEMA_VERSION)
            }
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(res).encode('utf-8'))
            return

        self.send_response(404)
        self.end_headers()

    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            info = {
                "status": "ML Detection Engine Online",
                "modelLoaded": CLF_MODEL is not None,
                "model_version": ACTIVE_MODEL_VERSION,
                "active_schema": ACTIVE_SCHEMA_VERSION,
                "features_count": ACTIVE_FEATURE_COUNT,
                "binary_gate_loaded": BINARY_GATE is not None,
                "binary_gate_model": BINARY_GATE_PATH,
                "binary_gate_features": BINARY_GATE_FEATURES,
                "binary_gate_threshold": BINARY_GATE_THRESHOLD,
                "active_features": registry.get_feature_names(ACTIVE_SCHEMA_VERSION)
            }
            self.wfile.write(json.dumps(info).encode('utf-8'))
            return
        elif self.path == '/features':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            manifest = {
                "v1_10_features": registry.get_feature_names("v1"),
                "v2_16_features": registry.get_feature_names("v2"),
                "v3_22_features": registry.get_feature_names("v3"),
                "groups": registry.get_feature_groups(),
                "descriptions": registry.get_feature_descriptions(),
                "current_active": ACTIVE_SCHEMA_VERSION
            }
            self.wfile.write(json.dumps(manifest).encode('utf-8'))
            return

        self.send_response(404)
        self.end_headers()


def run(port=5001):
    server_address = ('', port)
    httpd = HTTPServer(server_address, MLSafetyHandler)
    print(f"[ML Engine] Server running on port {port} (Active schema: {ACTIVE_SCHEMA_VERSION}, Features: {ACTIVE_FEATURE_COUNT})...")
    httpd.serve_forever()

if __name__ == '__main__':
    run()
