"""Build the OpenAppSec WAF-comparison corpus.

The full legitimate archive is 1.15 GB compressed / 7 GB uncompressed across
692 site files.  We stream the zip and take a deterministic stratified sample
per site, which is what the FPR experiment needs: many independent benign
traffic distributions, not one giant site.

Malicious payloads (73,924) are taken in full.  Both sets are converted with the
production v3 extractor and cached.
"""

from __future__ import annotations

import hashlib
import io
import json
import random
import sys
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import candidate_features as CF  # noqa: E402

OUT = C.PROCESSED / "openappsec"
OUT.mkdir(parents=True, exist_ok=True)

LEGIT_ZIP = C.OPENAPPSEC_DIR / "legitimate.zip"
MAL_ZIP = C.OPENAPPSEC_DIR / "malicious.zip"
PER_SITE = 200
SEED = 42


def _iter_json_array(zf: zipfile.ZipFile, name: str):
    with zf.open(name) as handle:
        return json.load(io.TextIOWrapper(handle, encoding="utf-8", errors="replace"))


def _record(method, url, headers, data, label, group, family):
    ua = ""
    for key, value in (headers or {}).items():
        if key.lower() == "user-agent":
            ua = value
            break
    path, query = C.split_target(url or "/")
    return {
        "group": group,
        "family": family,
        "label": label,
        "method": (method or "GET").upper(),
        "path": path,
        "query": query,
        "body": data or "",
        "user_agent": ua,
    }


def main() -> None:
    started = time.time()
    rows = []

    legit_names = [
        n for n in zipfile.ZipFile(LEGIT_ZIP).namelist() if n.lower().endswith(".json")
    ]
    print(f"legitimate files: {len(legit_names)}", flush=True)

    with zipfile.ZipFile(LEGIT_ZIP) as zf:
        for i, name in enumerate(legit_names):
            site = Path(name).stem
            try:
                items = _iter_json_array(zf, name)
            except Exception as exc:  # noqa: BLE001
                print(f"  skip {name}: {exc}", flush=True)
                continue
            if not isinstance(items, list):
                continue
            rng = random.Random(SEED + int(hashlib.blake2b(name.encode(), digest_size=4).hexdigest(), 16))
            take = items if len(items) <= PER_SITE else rng.sample(items, PER_SITE)
            for item in take:
                if not isinstance(item, dict):
                    continue
                rows.append(
                    _record(
                        item.get("method"),
                        item.get("url"),
                        item.get("headers"),
                        item.get("data"),
                        0,
                        site,
                        "legitimate",
                    )
                )
            if i % 50 == 0:
                print(f"  {i:>3}/{len(legit_names)} {site:<40} total={len(rows):>7,}", flush=True)

    legit_count = len(rows)
    print(f"legitimate sampled: {legit_count:,}", flush=True)

    with zipfile.ZipFile(MAL_ZIP) as zf:
        for name in zf.namelist():
            if not name.lower().endswith(".json"):
                continue
            family = Path(name).stem
            items = _iter_json_array(zf, name)
            for item in items:
                if not isinstance(item, dict):
                    continue
                rows.append(
                    _record(
                        item.get("method"),
                        item.get("url"),
                        item.get("headers"),
                        item.get("data"),
                        1,
                        family,
                        family,
                    )
                )
            print(f"  malicious {family:<12} {len(items):>7,}", flush=True)

    frame = pd.DataFrame.from_records(rows)
    frame.to_parquet(OUT / "wcp_requests.parquet", index=False)

    X = np.zeros((len(frame), C.N_FEATURES), dtype=np.float32)
    Cmat = np.zeros((len(frame), len(CF.CANDIDATE_NAMES)), dtype=np.float32)
    for i, row in enumerate(frame.itertuples(index=False)):
        rec = C.make_request(
            rid=str(i),
            source="wcp",
            label=int(row.label),
            method=row.method,
            target=(row.path + ("?" + row.query if row.query else "")),
            body=row.body,
            user_agent=row.user_agent,
        )
        feats = C.registry.extract_features(
            rec.payload, user_agent=row.user_agent, method=row.method, version="v3"
        )
        X[i] = C.registry.feature_dict_to_vector(feats, version="v3")
        Cmat[i] = CF.extract(rec)

    np.savez_compressed(
        OUT / "wcp_features.npz",
        X=X,
        C=Cmat,
        y=frame["label"].to_numpy(dtype=np.int8),
        groups=frame["group"].to_numpy(),
        families=frame["family"].to_numpy(),
    )

    summary = {
        "legitimate_sampled": int(legit_count),
        "legitimate_sites": int(frame.loc[frame.label == 0, "group"].nunique()),
        "per_site_cap": PER_SITE,
        "malicious": int((frame.label == 1).sum()),
        "malicious_families": frame.loc[frame.label == 1, "family"].value_counts().to_dict(),
        "elapsed_seconds": round(time.time() - started, 1),
        "features": C.FEATURES,
        "candidates": CF.CANDIDATE_NAMES,
    }
    C.write_json(OUT / "wcp_summary.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
