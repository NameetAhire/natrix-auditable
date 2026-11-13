# Cross-fitted corpus operating points (22-D gate)

Threshold for fold $k$ is selected on the OOF predictions of the other
four folds (D13). P1 is deployment-like; P2 is endpoint-disjoint and is
reported as a generalisation bound, not a headline result.

| corpus | protocol | policy | threshold | accuracy | FPR | FNR | F1 |
|---|---|---|---:|---:|---:|---:|---:|
| csic | P1 | f1 | 0.42 | 95.69 | 4.09 | 4.58 | 0.9533 |
| csic | P1 | fpr1 | 0.60 | 94.06 | 1.02 | 11.70 | 0.9320 |
| csic | P1 | fpr2 | 0.51 | 95.55 | 1.93 | 7.40 | 0.9505 |
| csic | P2 | f1 | 0.48 | 81.33 | 27.19 | 8.72 | 0.8185 |
| csic | P2 | fpr1 | 0.99 | 78.85 | 6.50 | 38.27 | 0.7291 |
| csic | P2 | fpr2 | 0.99 | 78.85 | 6.50 | 38.27 | 0.7291 |
| ecml | P1 | f1 | 0.48 | 91.96 | 1.67 | 22.81 | 0.8527 |
| ecml | P1 | fpr1 | 0.57 | 92.00 | 1.01 | 24.20 | 0.8510 |
| ecml | P1 | fpr2 | 0.48 | 91.96 | 1.67 | 22.81 | 0.8527 |
| ecml | P2 | f1 | 0.44 | 91.54 | 2.12 | 23.16 | 0.8455 |
| ecml | P2 | fpr1 | 0.57 | 91.68 | 0.99 | 25.29 | 0.8442 |
| ecml | P2 | fpr2 | 0.47 | 91.60 | 1.75 | 23.79 | 0.8455 |
| srbh | P1 | f1 | 0.45 | 96.05 | 8.78 | 1.97 | 0.9724 |
| srbh | P1 | fpr1 | 0.88 | 95.17 | 0.98 | 6.40 | 0.9649 |
| srbh | P1 | fpr2 | 0.76 | 95.70 | 1.96 | 5.25 | 0.9690 |
| srbh | P2 | f1 | 0.64 | 94.09 | 9.42 | 4.48 | 0.9582 |
| srbh | P2 | fpr1 | 0.94 | 93.38 | 2.42 | 8.34 | 0.9516 |
| srbh | P2 | fpr2 | 0.90 | 94.01 | 2.77 | 7.30 | 0.9565 |

**Acceptance check (FPR $\leq$ 2% policy).**

| corpus/protocol | accuracy | FPR | meets accuracy > 95% and FPR < 2.03% |
|---|---:|---:|:--:|
| csic_P1 | 95.55 | 1.93 | yes |
| csic_P2 | 78.85 | 6.50 | no |
| ecml_P1 | 91.96 | 1.67 | no |
| ecml_P2 | 91.60 | 1.75 | no |
| srbh_P1 | 95.70 | 1.96 | yes |
| srbh_P2 | 94.01 | 2.77 | no |
