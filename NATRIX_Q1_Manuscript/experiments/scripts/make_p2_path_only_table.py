"""Render the P2 path-only grouping sensitivity table."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

ENDPOINT = {
    "ecml": {
        "natrix": (91.60, 1.75, 76.21),
        "lexical_full": (93.76, 0.51, 80.47),
        "lexical_payload": (92.70, 0.44, 76.81),
    },
    "srbh20k": {
        "natrix": (90.62, 1.88, 87.56),
        "lexical_full": (94.75, 2.01, 93.43),
        "lexical_payload": (36.27, 1.88, 10.97),
    },
}
LABEL = {"natrix": "NATRIX", "lexical_full": "Lex-full", "lexical_payload": "Lex-payload"}
CORPUS = {"csic": "CSIC", "ecml": "ECML", "srbh20k": "SR-BH 20k"}


def main() -> None:
    lines = [
        "# P2 sensitivity: path-only grouping",
        "",
        "The main P2 protocol groups by method + normalized path + sorted",
        "query/body parameter names. The path-only check groups by method +",
        "normalized path only, so requests to the same path with different",
        "parameter names stay in one fold. This is stricter.",
        "",
        "| corpus | grouping | groups | median size | p95 size | max size | mixed groups | rows in mixed groups |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    data = {}
    for corpus in ["csic", "ecml", "srbh20k"]:
        path = C.RESULTS / "baselines" / f"p2_path_only_{corpus}.json"
        if not path.exists():
            continue
        d = json.loads(path.read_text(encoding="utf-8"))
        data[corpus] = d
        for key, label in [("endpoint_grouping", "endpoint+params"), ("path_grouping", "path-only")]:
            g = d[key]
            lines.append(
                f"| {CORPUS[corpus]} | {label} | {g['n_groups']:,} | "
                f"{g['median_group_size']:.0f} | {g['p95_group_size']:.0f} | "
                f"{g['max_group_size']:,} | {g['n_mixed_groups']} | "
                f"{g['pct_rows_in_mixed_groups']:.1f}% |"
            )
    lines += ["", "## Split quality", "",
              "| corpus | test sizes | attack prevalence | max/min | balanced |",
              "|---|---|---|---:|---|"]
    for corpus, d in data.items():
        q = d["split_quality"]
        sizes = "/".join(f"{s:,}" for s in q["test_sizes"])
        prev = "/".join(f"{p:.2f}" for p in q["test_attack_prevalence"])
        lines.append(
            f"| {CORPUS[corpus]} | {sizes} | {prev} | "
            f"{q['max_min_test_size_ratio']:.2f} | {'yes' if q['balanced'] else 'no'} |"
        )
    lines += [
        "",
        "CSIC is not identifiable under path-only grouping: 10 normalized paths",
        "carry 93% of the 34,593 requests, so one fold receives 668 test requests",
        "and another 14,087, with attack prevalence from 0.43 to 0.98. The",
        "detector numbers for CSIC are therefore not used to rank detectors.",
        "",
        "## Detector comparison where the split is balanced",
        "",
        "| corpus | detector | path-only accuracy | path-only FPR | path-only recall | endpoint P2 accuracy | endpoint P2 FPR | endpoint P2 recall | delta accuracy |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for corpus in ["ecml", "srbh20k"]:
        d = data.get(corpus)
        if not d or not d["ranking_identifiable"]:
            continue
        for det in d["detectors"]:
            view = det["view"]
            m = det["metrics"]
            e = ENDPOINT[corpus][view]
            lines.append(
                f"| {CORPUS[corpus]} | {LABEL[view]} | {m['accuracy']*100:.2f} | "
                f"{m['fpr']*100:.2f} | {m['recall']*100:.2f} | {e[0]:.2f} | "
                f"{e[1]:.2f} | {e[2]:.2f} | {(m['accuracy']*100)-e[0]:+.2f} |"
            )
    lines += [
        "",
        "On ECML and SR-BH the ranking is unchanged and the accuracy deltas are",
        "within one point. The path-only grouping is therefore a robustness check",
        "that supports the endpoint+parameter grouping used in the main protocol;",
        "it does not change the paper's conclusion.",
        "",
    ]
    out = C.ROOT / "tables" / "p2_path_only.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
