#!/usr/bin/env python3
"""Viability screen for ATRDF 2023 as a P1/P2 corpus.

ATRDF is the only public API corpus with labelled endpoint structure, so it is
the natural candidate for a modern replication. This script measures the two
properties the protocol needs: class overlap across endpoints, and whether the
path alone separates the classes.

Download the training subsets from
https://github.com/ArielCyber/Cisco_Ariel_Uni_API_security_challenge/tree/main/Datasets
extract the .7z files, and pass the directory holding the JSON files.

    python atrdf_viability.py --data-dir /path/to/atrdf

Writes results/atrdf_viability.json.
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

FILES = ("dataset_1_train.json", "dataset_2_train.json")
BENIGN = {"", "benign"}


def normalise(path: str) -> str:
    parts = []
    for segment in path.split("/"):
        if re.fullmatch(r"\d+", segment):
            parts.append("{int}")
        elif re.fullmatch(r"[0-9a-fA-F]{16,}", segment):
            parts.append("{hex}")
        else:
            parts.append(segment)
    return "/".join(parts)


def load(path: Path):
    rows = []
    posts = bodies = 0
    for record in json.loads(path.read_text(encoding="utf-8")):
        request = record["request"]
        tag = (request.get("Attack_Tag") or "").strip()
        label = "benign" if tag.lower() in BENIGN else tag
        path_only = normalise(urlsplit(request.get("url") or "").path)
        rows.append((label, path_only))
        if request.get("method") == "POST":
            posts += 1
        if (request.get("body") or "").strip():
            bodies += 1
    return rows, posts, bodies


def summarise(rows):
    labels = Counter(label for label, _ in rows)
    benign_paths = {path for label, path in rows if label == "benign"}
    attacks = [(label, path) for label, path in rows if label != "benign"]
    hidden = sum(1 for _, path in attacks if path not in benign_paths)

    by_path = {}
    for label, path in rows:
        by_path.setdefault(path, Counter())[label] += 1
    majority = sum(max(counts.values()) for counts in by_path.values())

    return {
        "records": len(rows),
        "benign": labels.get("benign", 0),
        "attack": len(attacks),
        "benign_share_pct": round(100 * labels.get("benign", 0) / len(rows), 2),
        "distinct_paths": len(by_path),
        "benign_paths": len(benign_paths),
        "attack_classes": sorted(k for k in labels if k != "benign"),
        "attack_on_benign_invisible_path": hidden,
        "attack_on_benign_invisible_path_pct": round(100 * hidden / len(attacks), 1),
        "path_only_majority_accuracy_pct": round(100 * majority / len(rows), 2),
        "class_pure_paths": sum(1 for c in by_path.values() if len(c) == 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    per_file, combined, posts, bodies = {}, [], 0, 0
    for name in FILES:
        path = args.data_dir / name
        if not path.is_file():
            raise SystemExit(f"missing {path}")
        rows, file_posts, file_bodies = load(path)
        posts += file_posts
        bodies += file_bodies
        per_file[name] = summarise(rows)
        combined.extend(rows)

    result = {
        "corpus": "ATRDF 2023",
        "source": "https://github.com/ArielCyber/Cisco_Ariel_Uni_API_security_challenge",
        "files": list(FILES),
        "posts": posts,
        "requests_with_body": bodies,
        "per_file": per_file,
        "combined": summarise(combined),
    }
    out = args.out or Path(__file__).resolve().parents[1] / "results" / "atrdf_viability.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["combined"], indent=2))
    print(f"POSTs {posts}, requests with body {bodies}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
