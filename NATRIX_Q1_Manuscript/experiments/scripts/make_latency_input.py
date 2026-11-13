"""Build the payload sample used by the end-to-end latency benchmark.

10,000 requests sampled from three corpora with different payload shapes:

  CSIC  5,000  (2,500 clean / 2,500 attack)
  ECML  3,000  (1,500 valid / 1,500 attack)
  WCP   2,000  (1,000 legitimate / 1,000 malicious)

The sample is frozen to disk so the Node benchmark and the Python component
measurements score exactly the same requests.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
from redact import redact_item  # noqa: E402

OUT = C.RESULTS / "latency"
OUT.mkdir(parents=True, exist_ok=True)


def sample_records(records, n_per_class, seed=C.SEED):
    rng = np.random.default_rng(seed)
    chosen = []
    labels = np.asarray([r.label for r in records])
    for label in (0, 1):
        pool = [r for r, lab in zip(records, labels) if lab == label]
        take = min(n_per_class, len(pool))
        idx = rng.choice(len(pool), take, replace=False)
        chosen.extend(pool[i] for i in idx)
    return chosen


def main() -> None:
    items = []

    records, _ = C.csic_unique()
    for rec in sample_records(records, 2500, seed=42):
        items.append({
            "corpus": "csic",
            "method": rec.method,
            "url": rec.path + (("?" + rec.query) if rec.query else ""),
            "userAgent": rec.user_agent,
            "body": rec.body,
            "label": rec.label,
        })

    ecml = C.load_ecml_records()
    for rec in sample_records(ecml, 1500, seed=43):
        items.append({
            "corpus": "ecml",
            "method": rec.method,
            "url": rec.path + (("?" + rec.query) if rec.query else ""),
            "userAgent": rec.user_agent,
            "body": rec.body,
            "label": rec.label,
        })

    import pandas as pd

    frame = pd.read_parquet(C.PROCESSED / "openappsec" / "wcp_requests.parquet")
    rng = np.random.default_rng(44)
    for label in (0, 1):
        pool = frame[frame.label == label]
        take = pool.sample(n=min(1000, len(pool)), random_state=int(rng.integers(1 << 30)))
        for row in take.itertuples(index=False):
            items.append({
                "corpus": "wcp",
                "method": row.method,
                "url": row.path + (("?" + row.query) if row.query else ""),
                "userAgent": row.user_agent,
                "body": row.body,
                "label": int(row.label),
            })

    items = [redact_item(item) for item in items]

    path = OUT / "latency_inputs.json"
    path.write_text(json.dumps(items), encoding="utf-8")
    print(f"wrote {len(items):,} requests to {path} ({path.stat().st_size / 1048576:.1f} MB)")
    print("corpora:", {c: sum(1 for i in items if i["corpus"] == c) for c in ("csic", "ecml", "wcp")})


if __name__ == "__main__":
    main()
