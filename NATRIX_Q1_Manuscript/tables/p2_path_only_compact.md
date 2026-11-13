# P2 grouping sensitivity: path-only groups

| corpus | grouping | groups | max group | rows in mixed groups | balanced 5-fold? |
|---|---|---:|---:|---:|---|
| CSIC | endpoint + params | 1,734 | 2,923 | 81.7% | yes |
| CSIC | path-only | 1,648 | 3,364 | 94.5% | no |
| ECML | path-only | 48,723 | 68 | 0.0% | yes |
| SR-BH 20k | path-only | 17,021 | 220 | 8.6% | yes |

CSIC is not identifiable under path-only grouping: ten normalized paths
carry 93% of the requests, so the five test folds range from 668 to
14,087 requests and from 0.43 to 0.98 attack prevalence. The CSIC
path-only detector numbers are therefore not used for ranking.

| corpus | detector | path-only accuracy | endpoint P2 accuracy | delta |
|---|---|---:|---:|---:|
| ECML | NATRIX | 91.48 | 91.60 | -0.12 |
| ECML | Lex-full | 93.74 | 93.76 | -0.02 |
| ECML | Lex-payload | 92.67 | 92.70 | -0.03 |
| SR-BH 20k | NATRIX | 89.66 | 90.62 | -0.97 |
| SR-BH 20k | Lex-full | 94.16 | 94.75 | -0.59 |
| SR-BH 20k | Lex-payload | 36.06 | 36.27 | -0.21 |

Where the split is balanced, the ranking is unchanged and every accuracy
delta is within one point. The endpoint+parameter grouping used in the
main protocol is therefore not doing hidden work for the ranking.
