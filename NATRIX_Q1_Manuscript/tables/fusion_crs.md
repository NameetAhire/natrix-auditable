# Gate plus CRS fusion

| Corpus | Policy | Accuracy | FPR | Recall | F1 |
|---|---|---|---|---|---|
| CSIC | gate | 95.55 | 1.93 | 92.60 | 95.05 |
| CSIC | OR | 95.57 | 1.96 | 92.69 | 95.07 |
| CSIC | AND | 66.22 | 0.00 | 26.75 | 42.21 |
| ECML | gate | 91.96 | 1.67 | 77.19 | 85.27 |
| ECML | OR | 81.28 | 21.19 | 87.00 | 73.70 |
| ECML | AND | 88.41 | 0.61 | 62.96 | 76.61 |
| SR-BH | gate | 90.79 | 1.96 | 87.82 | 93.12 |
| SR-BH | OR | 86.74 | 27.16 | 92.43 | 90.82 |
| SR-BH | AND | 47.94 | 0.17 | 26.71 | 42.14 |
| WCP$^\dagger$ | gate | 99.79 | 0.11 | 99.58 | 99.69 |
| WCP$^\dagger$ | OR | 95.60 | 6.71 | 99.90 | 94.06 |
| WCP$^\dagger$ | AND | 95.98 | 0.01 | 88.48 | 93.88 |

$^\dagger$ Endpoint-confounded random split; shown for completeness only.

OR adds 14 attacks for 6 clean false positives on CSIC, 1,483 attacks for 6,835 clean false positives on ECML, 653 attacks for 1,463 clean false positives on SR-BH, and 22 attacks for 860 clean false positives on WCP.
