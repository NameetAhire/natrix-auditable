"""Add split-quality diagnostics to the path-only P2 results."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
from p2_path_only import load_rows, OUT  # noqa: E402


def main() -> None:
    for corpus in ["csic", "ecml", "srbh20k"]:
        path = OUT / f"p2_path_only_{corpus}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = load_rows(corpus)
        y = rows.label.to_numpy(dtype=int)
        z = np.load(OUT / f"p2_path_only_{corpus}_folds.npz", allow_pickle=True)
        folds = [(z[f"tr_{i}"], z[f"te_{i}"]) for i in range(5)]
        sizes = [int(len(te)) for _, te in folds]
        prev = [float(y[te].mean()) for _, te in folds]
        ratio = max(sizes) / min(sizes)
        prev_range = max(prev) - min(prev)
        balanced = bool(ratio < 2.0 and prev_range < 0.10)
        data["split_quality"] = {
            "test_sizes": sizes,
            "test_attack_prevalence": [round(p, 4) for p in prev],
            "max_min_test_size_ratio": round(ratio, 3),
            "prevalence_range": round(prev_range, 4),
            "balanced": balanced,
        }
        data["ranking_identifiable"] = balanced
        if not balanced:
            data["note"] = (
                "The path-only grouping is degenerate on this corpus: a small "
                "number of normalized paths carry most requests, so a 5-fold "
                "group-disjoint split cannot balance the folds. The detector "
                "numbers are reported for completeness but are not used to "
                "rank detectors."
            )
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(corpus, data["split_quality"], "identifiable:", balanced)


if __name__ == "__main__":
    main()
