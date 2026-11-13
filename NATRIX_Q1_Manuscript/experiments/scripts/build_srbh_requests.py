"""Build a deduplicated raw-request cache for SR-BH 2020.

The feature cache intentionally discards request text.  A WAF baseline needs the
text, so this script applies the *same* duplicate and label-conflict rules as
``build_srbh_cache.py`` and writes the surviving requests to parquet.  No
feature extraction and no model selection happen here.
"""

from __future__ import annotations

import hashlib
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

OUT = C.PROCESSED / "srbh"
OUT.mkdir(parents=True, exist_ok=True)

USE = [
    "timestamp",
    "src_ip",
    "src_port",
    "dst_ip",
    "dst_port",
    "request_http_method",
    "request_http_request",
    "request_http_protocol",
    "request_user_agent",
    "request_referer",
    "request_host",
    "request_origin",
    "request_cookie",
    "request_content_type",
    "request_accept",
    "request_accept_language",
    "request_accept_encoding",
    "request_connection",
    "request_body",
]


def key_hash(method: str, path: str, query: str, body: str, ua: str) -> bytes:
    blob = "\x1f".join((method, path, query, body, ua)).encode("utf-8", "replace")
    return hashlib.blake2b(blob, digest_size=16).digest()


def main() -> None:
    started = time.time()
    rows: list[dict] = []
    seen: dict[bytes, tuple[int, int]] = {}
    conflicts: set[int] = set()
    dropped = 0
    raw = 0

    # Stream once, retaining both the model fields and the provenance fields.
    for chunk_no, chunk in enumerate(
        pd.read_csv(
            C.SRBH_CSV,
            usecols=USE + C.SRBH_LABEL_COLS,
            chunksize=40_000,
            dtype=str,
            keep_default_na=False,
            encoding="utf-8",
            on_bad_lines="skip",
        )
    ):
        labels = chunk[C.SRBH_LABEL_COLS].apply(pd.to_numeric, errors="coerce").fillna(0)
        label_values = labels.astype("int8").to_numpy()
        for i in range(len(chunk)):
            raw += 1
            row = chunk.iloc[i]
            method = str(row["request_http_method"] or "GET").upper()
            target = str(row["request_http_request"] or "/")
            body = str(row["request_body"] or "")
            ua = str(row["request_user_agent"] or "")
            path, query = C.split_target(target)
            digest = key_hash(method, path, query, body, ua)
            label = 0 if label_values[i][0] == 1 else 1

            prior = seen.get(digest)
            if prior is not None:
                dropped += 1
                if prior[0] != label:
                    conflicts.add(prior[1])
                continue

            index = len(rows)
            seen[digest] = (label, index)
            rows.append(
                {
                    "method": method,
                    "path": path,
                    "query": query,
                    "body": body,
                    "user_agent": ua,
                    "label": label,
                    "src_ip": str(row["src_ip"] or ""),
                    "host": str(row["request_host"] or ""),
                    "referer": str(row["request_referer"] or ""),
                    "cookie": str(row["request_cookie"] or ""),
                    "content_type": str(row["request_content_type"] or ""),
                    "family": C.srbh_attack_family(label_values[i]),
                }
            )
        if chunk_no % 5 == 0:
            print(
                f"chunk {chunk_no:>3} raw={raw:>7,} kept={len(rows):>7,} "
                f"dupes={dropped:>7,} conflict={len(conflicts):>5,} "
                f"{time.time() - started:6.1f}s",
                flush=True,
            )

    frame = pd.DataFrame.from_records(rows)
    if conflicts:
        frame = frame.drop(index=sorted(conflicts)).reset_index(drop=True)
    frame.to_parquet(OUT / "srbh_requests.parquet", index=False)
    summary = {
        "raw_rows": raw,
        "kept_rows": int(len(frame)),
        "dropped_duplicates": dropped,
        "label_conflict_rows_dropped": len(conflicts),
        "labels": {"clean": int((frame.label == 0).sum()), "attack": int((frame.label == 1).sum())},
        "elapsed_seconds": round(time.time() - started, 1),
    }
    C.write_json(OUT / "srbh_requests_summary.json", summary)
    print(summary)


if __name__ == "__main__":
    main()
