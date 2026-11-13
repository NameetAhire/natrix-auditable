# Positive control: the v3-D path block under the three gates

The nine v3-D features form two operational blocks. Gate C rejects the
five value features (0.35 ms p95 on the real CSIC distribution against
the 0.15 ms envelope) and accepts the four path features (0.085 ms).
Gate B is then applied to the path block. The full model is the 22-D v3
contract plus the four path features (26-D).

Full 26-D: 95.57% accuracy, 1.92% FPR, 92.63% recall.

| feature | BH p | Cliff delta | perm. imp. | ablation delta acc. (95% CI) | C1/C2/C3 |
|---|---:|---:|---:|---|---|
| `path_special_char_ratio` | 9.3e-19 | +0.055 | +0.0314 | +0.04pp [-0.11,+0.03] | no/no/yes |
| `path_digit_ratio` | 0.36 | -0.006 | +0.0016 | +0.02pp [-0.09,+0.05] | yes/no/yes |
| `path_uppercase_ratio` | 2e-187 | +0.045 | -0.0000 | +0.04pp [-0.10,+0.02] | no/yes/yes |
| `path_keyword_score` | 7e-05 | +0.001 | +0.0000 | -0.02pp [-0.04,+0.09] | yes/no/yes |

Gate C path-block p95: 0.085 ms (budget 0.15 ms).
All four path features are admitted. The joint accuracy change on CSIC
is +0.02 percentage points (95.57% versus 95.55%), so the admission is
a procedural positive control, not a claim of practical gain. The
exercise is post-freeze and does not change v4; it demonstrates that
the gate is not a reject-only procedure. The path signal matters on
SR-BH, where the view ablation shows that removing the path costs most
of the recall.
