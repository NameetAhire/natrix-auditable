"""Build the SR-BH 2020 feature cache.

436 MB CSV, 907,814 rows, 8 GB machine.  Streamed in chunks; exact duplicates
removed on the same key the CSIC pipeline uses; features come from the
production registry.  Output is a compact npz plus a summary, so later
experiments never re-parse the CSV.
"""

from __future__ import annotations

import hashlib
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import candidate_features as CF  # noqa: E402

OUT = C.PROCESSED / "srbh"
OUT.mkdir(parents=True, exist_ok=True)


def key_hash(method: str, path: str, query: str, body: str, ua: str) -> bytes:
    blob = "\x1f".join((method, path, query, body, ua)).encode("utf-8", "replace")
    return hashlib.blake2b(blob, digest_size=16).digest()


def main() -> None:
    if not C.srbh_available():
        raise SystemExit(f"SR-BH CSV missing or incomplete: {C.SRBH_CSV}")

    xs: list[np.ndarray] = []
    cs: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    groups: list[np.ndarray] = []
    families: list[np.ndarray] = []
    family_names: list[str] = []
    family_index: dict[str, int] = {}
    group_index: dict[str, int] = {}

    # digest -> (label, retained_row_index)
    seen: dict[bytes, tuple[int, int]] = {}
    conflict_rows: set[int] = set()
    dropped_dupes = 0
    raw_rows = 0
    kept_rows = 0
    started = time.time()

    for chunk_no, (frame, labels) in enumerate(C.iter_srbh()):
        rows_x = []
        rows_c = []
        rows_y = []
        rows_g = []
        rows_f = []

        cols = {name: frame[name].to_numpy() for name in C.SRBH_USE}
        for i in range(len(frame)):
            raw_rows += 1
            method = str(cols["request_http_method"][i] or "GET").upper()
            target = str(cols["request_http_request"][i] or "/")
            body = str(cols["request_body"][i] or "")
            ua = str(cols["request_user_agent"][i] or "")
            path, query = C.split_target(target)

            digest = key_hash(method, path, query, body, ua)
            label_row = labels[i]
            label = 0 if label_row[0] == 1 else 1

            prior = seen.get(digest)
            if prior is not None:
                dropped_dupes += 1
                if prior[0] != label:
                    conflict_rows.add(prior[1])
                continue

            index = kept_rows
            seen[digest] = (label, index)

            rec = C.make_request(
                rid=str(raw_rows),
                source="srbh",
                label=label,
                method=method,
                target=target,
                body=body,
                user_agent=ua,
            )
            group = rec.group_signature
            gid = group_index.get(group)
            if gid is None:
                gid = len(group_index)
                group_index[group] = gid

            family = C.srbh_attack_family(label_row)
            fid = family_index.get(family)
            if fid is None:
                fid = len(family_names)
                family_index[family] = fid
                family_names.append(family)

            feats = C.registry.extract_features(
                rec.payload, user_agent=ua, method=method, version="v3"
            )
            rows_x.append(C.registry.feature_dict_to_vector(feats, version="v3"))
            rows_c.append(CF.extract(rec))
            rows_y.append(label)
            rows_g.append(gid)
            rows_f.append(fid)
            kept_rows += 1

        if rows_x:
            xs.append(np.asarray(rows_x, dtype=np.float32))
            cs.append(np.asarray(rows_c, dtype=np.float32))
            ys.append(np.asarray(rows_y, dtype=np.int8))
            groups.append(np.asarray(rows_g, dtype=np.int32))
            families.append(np.asarray(rows_f, dtype=np.int16))

        elapsed = time.time() - started
        print(
            f"chunk {chunk_no:>3}  raw={raw_rows:>7,}  kept={kept_rows:>7,}  "
            f"dupes={dropped_dupes:>7,}  conflict={len(conflict_rows):>5,}  {elapsed:6.1f}s",
            flush=True,
        )

    X = np.vstack(xs)
    Cmat = np.vstack(cs)
    y = np.concatenate(ys)
    group_ids = np.concatenate(groups)
    family_ids = np.concatenate(families)

    if conflict_rows:
        keep = np.ones(len(y), dtype=bool)
        keep[np.fromiter(conflict_rows, dtype=np.int64, count=len(conflict_rows))] = False
        X, y = X[keep], y[keep]
        Cmat = Cmat[keep]
        group_ids, family_ids = group_ids[keep], family_ids[keep]

    np.savez_compressed(
        OUT / "srbh_features.npz",
        X=X,
        C=Cmat,
        y=y,
        group_ids=group_ids,
        family_ids=family_ids,
        family_names=np.asarray(family_names, dtype=object),
    )

    summary = {
        "raw_rows": raw_rows,
        "kept_rows": int(len(y)),
        "dropped_duplicates": dropped_dupes,
        "label_conflict_rows_dropped": len(conflict_rows),
        "groups": len(group_index),
        "families": {name: int((family_ids == i).sum()) for i, name in enumerate(family_names)},
        "labels": {"clean": int((y == 0).sum()), "attack": int((y == 1).sum())},
        "elapsed_seconds": round(time.time() - started, 1),
        "features": C.FEATURES,
        "candidates": CF.CANDIDATE_NAMES,
    }
    C.write_json(OUT / "srbh_summary.json", summary)
    print(C.json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
