"""Render the v3-D positive-control gate table."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


def main() -> None:
    data = json.loads((C.RESULTS / "feature_audit" / "v3d_path_gate.json").read_text(encoding="utf-8"))
    import pandas as pd

    frame = pd.read_csv(C.RESULTS / "feature_audit" / "v3d_path_gate.csv")
    lines = [
        "# Positive control: the v3-D path block under the three gates",
        "",
        "The nine v3-D features form two operational blocks. Gate C rejects the",
        "five value features (0.35 ms p95 on the real CSIC distribution against",
        "the 0.15 ms envelope) and accepts the four path features (0.085 ms).",
        "Gate B is then applied to the path block. The full model is the 22-D v3",
        "contract plus the four path features (26-D).",
        "",
        f"Full 26-D: {data['full_26d']['accuracy']*100:.2f}% accuracy, "
        f"{data['full_26d']['fpr']*100:.2f}% FPR, "
        f"{data['full_26d']['recall']*100:.2f}% recall.",
        "",
        "| feature | BH p | Cliff delta | perm. imp. | ablation delta acc. (95% CI) | C1/C2/C3 |",
        "|---|---:|---:|---:|---|---|",
    ]
    for row in frame.itertuples(index=False):
        lines.append(
            f"| `{row.feature}` | {row.p_bh:.2g} | {row.cliffs_delta:+.3f} | "
            f"{row.perm_importance_mean:+.4f} | {row.ablation_delta_accuracy*100:+.2f}pp "
            f"[{row.ablation_delta_accuracy_ci_lo*100:+.2f},"
            f"{row.ablation_delta_accuracy_ci_hi*100:+.2f}] | "
            f"{'yes' if row.c1_univariate else 'no'}/"
            f"{'yes' if row.c2_importance else 'no'}/"
            f"{'yes' if row.c3_ablation else 'no'} |"
        )
    lines += [
        "",
        f"Gate C path-block p95: {data['gate_c']['p95_ms']:.3f} ms (budget 0.15 ms).",
        "All four path features are admitted. The joint accuracy change on CSIC",
        "is +0.02 percentage points (95.57% versus 95.55%), so the admission is",
        "a procedural positive control, not a claim of practical gain. The",
        "exercise is post-freeze and does not change v4; it demonstrates that",
        "the gate is not a reject-only procedure. The path signal matters on",
        "SR-BH, where the view ablation shows that removing the path costs most",
        "of the recall.",
        "",
    ]
    out = C.ROOT / "tables" / "v3d_gate.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
