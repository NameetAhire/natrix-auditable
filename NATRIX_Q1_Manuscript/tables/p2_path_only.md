# P2 sensitivity: path-only grouping

The main P2 protocol groups by method + normalized path + sorted
query/body parameter names. The path-only check groups by method +
normalized path only, so requests to the same path with different
parameter names stay in one fold. This is stricter.

| corpus | grouping | groups | median size | p95 size | max size | mixed groups | rows in mixed groups |
|---|---|---:|---:|---:|---:|---:|---:|
| CSIC | endpoint+params | 1,734 | 1 | 30 | 2,923 | 16 | 81.7% |
| CSIC | path-only | 1,648 | 1 | 1 | 3,364 | 16 | 94.5% |
| ECML | endpoint+params | 48,727 | 1 | 1 | 68 | 1 | 0.0% |
| ECML | path-only | 48,723 | 1 | 1 | 68 | 2 | 0.0% |
| SR-BH 20k | endpoint+params | 17,129 | 1 | 1 | 87 | 81 | 7.2% |
| SR-BH 20k | path-only | 17,021 | 1 | 1 | 220 | 75 | 8.6% |

## Split quality

| corpus | test sizes | attack prevalence | max/min | balanced |
|---|---|---|---:|---|
| CSIC | 14,087/668/9,933/6,775/3,130 | 0.43/0.98/0.47/0.42/0.55 | 21.09 | no |
| ECML | 10,006/9,943/10,242/9,928/9,997 | 0.30/0.30/0.32/0.31/0.28 | 1.03 | yes |
| SR-BH 20k | 4,210/3,708/4,522/3,797/3,763 | 0.71/0.70/0.68/0.72/0.74 | 1.22 | yes |

CSIC is not identifiable under path-only grouping: 10 normalized paths
carry 93% of the 34,593 requests, so one fold receives 668 test requests
and another 14,087, with attack prevalence from 0.43 to 0.98. The
detector numbers for CSIC are therefore not used to rank detectors.

## Detector comparison where the split is balanced

| corpus | detector | path-only accuracy | path-only FPR | path-only recall | endpoint P2 accuracy | endpoint P2 FPR | endpoint P2 recall | delta accuracy |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| ECML | NATRIX | 91.48 | 1.79 | 75.88 | 91.60 | 1.75 | 76.21 | -0.12 |
| ECML | Lex-full | 93.74 | 0.55 | 80.52 | 93.76 | 0.51 | 80.47 | -0.02 |
| ECML | Lex-payload | 92.67 | 0.53 | 76.90 | 92.70 | 0.44 | 76.81 | -0.03 |
| SR-BH 20k | NATRIX | 89.66 | 1.88 | 86.19 | 90.62 | 1.88 | 87.56 | -0.97 |
| SR-BH 20k | Lex-full | 94.16 | 1.81 | 92.52 | 94.75 | 2.01 | 93.43 | -0.59 |
| SR-BH 20k | Lex-payload | 36.06 | 2.55 | 10.94 | 36.27 | 1.88 | 10.97 | -0.21 |

On ECML and SR-BH the ranking is unchanged and the accuracy deltas are
within one point. The path-only grouping is therefore a robustness check
that supports the endpoint+parameter grouping used in the main protocol;
it does not change the paper's conclusion.
