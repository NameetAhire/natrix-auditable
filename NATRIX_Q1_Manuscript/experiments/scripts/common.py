"""Shared paths, dataset loaders and feature extraction for the NATRIX Q1 work.

Design rule: feature values are produced by the *production* FeatureRegistry and
CSIC records are parsed by the *published* evaluation module.  Nothing here
reimplements a formula, so the audit cannot silently measure a different feature
set from the one the proxy serves.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.parse
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
ARTIFACTS = ROOT / "artifacts"
RESULTS = ROOT / "experiments" / "results"
FIGURES = ROOT / "figures"
TABLES = ROOT / "tables"

AI_ROOT = ROOT.parent / "Ai-Agent"
ML_ENGINE = AI_ROOT / "ml_engine"
if str(ML_ENGINE) not in sys.path:
    sys.path.insert(0, str(ML_ENGINE))

from feature_registry import registry  # noqa: E402
import csic_evaluation as ce  # noqa: E402

FEATURES = registry.get_feature_names("v3")
N_FEATURES = len(FEATURES)
SEED = 42

CSIC_FILES = RAW / "csic" / "mirror"
ECML_TRAIN = RAW / "ecml" / "extracted" / "xml_train.txt"
ECML_TEST = RAW / "ecml" / "extracted" / "xml_test.txt"
SRBH_CSV = RAW / "srbh" / "srbh_2020.csv"
OPENAPPSEC_DIR = RAW / "openappsec"

# SR-BH columns we actually need.
SRBH_USE = [
    "request_http_method",
    "request_http_request",
    "request_body",
    "request_user_agent",
    "request_content_type",
    "request_http_protocol",
]
SRBH_LABEL_COLS = [
    "000 - Normal",
    "272 - Protocol Manipulation",
    "242 - Code Injection",
    "88 - OS Command Injection",
    "126 - Path Traversal",
    "66 - SQL Injection",
    "16 - Dictionary-based Password Attack",
    "310 - Scanning for Vulnerable Software",
    "153 - Input Data Manipulation",
    "248 - Command Injection",
    "274 - HTTP Verb Tampering",
    "194 - Fake the Source of Data",
    "34 - HTTP Response Splitting",
    "33 - HTTP Request Smuggling",
]


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, default=str)


def read_json(path: Path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def split_target(target: str) -> tuple[str, str]:
    """Return (path, query) from a request target, tolerating absolute URIs."""
    if not target:
        return "/", ""
    if "://" in target:
        parsed = urllib.parse.urlsplit(target)
        return parsed.path or "/", parsed.query
    if target.startswith("/"):
        path, _, query = target.partition("?")
        return path or "/", query
    # authority-form (CONNECT) or asterisk-form
    if target == "*":
        return "*", ""
    path, _, query = target.partition("?")
    return path or "/", query


def make_request(
    *,
    rid: str,
    source: str,
    label: int,
    method: str,
    target: str,
    body: str = "",
    user_agent: str = "",
    headers: dict | None = None,
    declared_class: str = "",
) -> ce.Request:
    path, query = split_target(target)
    body = (body or "").strip()
    if body.lower() == "null":
        body = ""
    payload = path
    if query:
        payload += "?" + query
    if body:
        payload += " " + body
    return ce.Request(
        rid=rid,
        source=source,
        declared_class=declared_class,
        label=label,
        method=(method or "GET").upper(),
        url=target,
        path=path,
        query=query,
        body=body,
        user_agent=user_agent or "",
        headers=headers or {},
        payload=payload,
    )


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------


def extract_matrix(records, dtype=np.float64) -> tuple[np.ndarray, np.ndarray]:
    """Extract the 22-D v3 matrix and the static-asset pre-filter flags."""
    rows = []
    statics = []
    for rec in records:
        features = registry.extract_features(
            rec.payload, user_agent=rec.user_agent, method=rec.method, version="v3"
        )
        rows.append(registry.feature_dict_to_vector(features, version="v3"))
        statics.append(ce.static_asset_flag(rec))
    matrix = np.asarray(rows, dtype=dtype)
    assert matrix.shape[1] == N_FEATURES
    return matrix, np.asarray(statics, dtype=np.int8)


# ---------------------------------------------------------------------------
# CSIC 2010
# ---------------------------------------------------------------------------


def load_csic_records(verbose: bool = False) -> list:
    """Parse the three published CSIC files, byte-identical to the mirror."""
    records = []
    for filename, source, label in ce.FILES:
        path = CSIC_FILES / filename
        if not path.exists():
            # Fall back to the copy already used by the published evaluation.
            path = Path(ce.DATASET_DIR) / filename
        if not path.exists():
            raise FileNotFoundError(path)
        parsed = ce.parse_file(str(path), source, label)
        if verbose:
            print(f"  {filename}: {len(parsed):,}")
        records.extend(parsed)
    return records


def csic_unique(records=None):
    """Deduplicate exactly as the published evaluation does."""
    if records is None:
        records = load_csic_records()
    unique, ambiguous = ce.dedupe_records(records)
    return unique, ambiguous


# ---------------------------------------------------------------------------
# ECML/PKDD 2007
# ---------------------------------------------------------------------------

ECML_LABEL_MAP = {
    "Valid": 0,
    "XSS": 1,
    "SqlInjection": 1,
    "LdapInjection": 1,
    "XPathInjection": 1,
    "PathTransversal": 1,
    "OsCommanding": 1,
    "SSI": 1,
}


def parse_ecml_file(path: Path, source: str) -> list:
    """Parse the ECML block format, keeping the declared attack family."""
    records = []
    state = 0
    rid = declared = request_line = ""
    headers: dict[str, str] = {}
    body_lines: list[str] = []

    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\r\n")
            if line.startswith("Start - Id:"):
                rid = line.split(":", 1)[1].strip()
                declared = request_line = ""
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
                    parts = request_line.split()
                    if len(parts) >= 2 and declared in ECML_LABEL_MAP:
                        records.append(
                            make_request(
                                rid=rid,
                                source=source,
                                label=ECML_LABEL_MAP[declared],
                                method=parts[0],
                                target=parts[1],
                                body="\n".join(body_lines),
                                user_agent=headers.get("user-agent", ""),
                                headers=headers,
                                declared_class=declared,
                            )
                        )
                    state = 0
                else:
                    body_lines.append(line)

    return records


def load_ecml_records() -> list:
    """The two mirror files together reconstitute the official training set."""
    records = parse_ecml_file(ECML_TRAIN, "ecml_train")
    records.extend(parse_ecml_file(ECML_TEST, "ecml_test"))
    return records


# ---------------------------------------------------------------------------
# SR-BH 2020 (streamed; 436 MB, 8 GB machine)
# ---------------------------------------------------------------------------


def srbh_available() -> bool:
    return SRBH_CSV.exists() and SRBH_CSV.stat().st_size > 100 * 1024 * 1024


def iter_srbh(chunksize: int = 40_000):
    """Yield (chunk, labels) with the label columns decoded to int8 arrays."""
    import pandas as pd

    usecols = SRBH_USE + SRBH_LABEL_COLS
    for chunk in pd.read_csv(
        SRBH_CSV,
        usecols=usecols,
        chunksize=chunksize,
        dtype=str,
        keep_default_na=False,
        encoding="utf-8",
        on_bad_lines="skip",
    ):
        labels = chunk[SRBH_LABEL_COLS].apply(pd.to_numeric, errors="coerce").fillna(0)
        yield chunk[SRBH_USE], labels.astype(np.int8).to_numpy()


def srbh_attack_family(label_row: np.ndarray) -> str:
    """First active CAPEC family, or 'normal'."""
    if label_row[0] == 1:
        return "normal"
    for name, value in zip(SRBH_LABEL_COLS[1:], label_row[1:]):
        if value == 1:
            return name
    return "unlabelled_anomaly"


# ---------------------------------------------------------------------------
# Dataset fingerprints
# ---------------------------------------------------------------------------


def dataset_fingerprint() -> dict:
    """Cheap, deterministic description of the inputs each result depends on."""
    out = {}
    for name, path in [
        ("csic_normal_train", CSIC_FILES / "cisc_normalTraffic_train.txt"),
        ("csic_normal_test", CSIC_FILES / "cisc_normalTraffic_test.txt"),
        ("csic_anomalous_test", CSIC_FILES / "cisc_anomalousTraffic_test.txt"),
        ("ecml_xml_train", ECML_TRAIN),
        ("ecml_xml_test", ECML_TEST),
        ("srbh_csv", SRBH_CSV),
    ]:
        if path.exists():
            stat = path.stat()
            out[name] = {
                "path": str(path.relative_to(ROOT)) if ROOT in path.parents else str(path),
                "bytes": stat.st_size,
                "sha256": sha256_file(path) if stat.st_size < 60 * 1024 * 1024 else None,
            }
    return out


# ---------------------------------------------------------------------------
# Split helpers
# ---------------------------------------------------------------------------


def group_signature(rec: ce.Request) -> str:
    return rec.group_signature


def label_array(records) -> np.ndarray:
    return np.asarray([r.label for r in records], dtype=np.int8)


def make_rf(**overrides):
    """The shipped gate configuration, exactly.

    `max_features=None` is essential: sklearn's classifier default is 'sqrt',
    which is *not* the configuration of the deployed artifact and changes CSIC
    accuracy by ~5 percentage points.  Every experiment goes through this
    factory so the ablation, the audit and the headline comparison all score
    the same learner.
    """
    from sklearn.ensemble import RandomForestClassifier

    params = dict(
        n_estimators=200,
        max_depth=None,
        min_samples_leaf=1,
        max_features=None,
        class_weight=None,
        random_state=SEED,
        n_jobs=6,
    )
    params.update(overrides)
    return RandomForestClassifier(**params)

