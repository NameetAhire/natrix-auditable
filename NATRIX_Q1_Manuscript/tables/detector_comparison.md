# Matched operating points: deployment-like (P1) and endpoint-disjoint (P2)

All score-based detectors use leave-one-fold-out thresholds at FPR <= 2%.
CRS is a frozen ModSecurity CRS 4.25.2 PL1 replay; it is not tuned to a
2% budget. SR-BH rows use the shared 20,000-request sample. The generic
control is a 17-feature LightGBM trained on the same folds; the stacks
are cross-fitted logistic combinations of the listed base scores.

## Panel A: P1 (deployment-like, endpoint may recur)

| corpus | detector | accuracy | FPR | recall | F1 |
|---|---|---:|---:|---:|---:|
| CSIC | NATRIX | 95.55 | 1.93 | 92.60 | 0.9505 |
| CSIC | Lex-full | 96.57 | 1.96 | 94.84 | 0.9622 |
| CSIC | Lex-payload | 96.90 | 1.88 | 95.47 | 0.9660 |
| CSIC | Lex-endpt | 60.85 | 0.14 | 15.26 | 0.2645 |
| CSIC | CRS PL1 | 66.24 | 0.03 | 26.84 | 0.4230 |
| CSIC | Generic GBM | 86.90 | 1.97 | 73.90 | 0.8388 |
| CSIC | Stack NATRIX+Lex | 98.45 | 1.24 | 98.08 | 0.9831 |
| CSIC | Stack N+G+Lex | 98.44 | 1.24 | 98.08 | 0.9831 |
| ECML | NATRIX | 91.96 | 1.67 | 77.19 | 0.8527 |
| ECML | Lex-full | 93.93 | 0.43 | 80.85 | 0.8893 |
| ECML | Lex-payload | 92.66 | 0.54 | 76.90 | 0.8633 |
| ECML | Lex-endpt | 71.94 | 1.80 | 11.11 | 0.1927 |
| ECML | CRS PL1 | 78.64 | 20.13 | 75.70 | 0.6752 |
| SR-BH | NATRIX (20k) | 90.79 | 1.96 | 87.82 | 0.9312 |
| SR-BH | Lex-full | 95.41 | 1.98 | 94.34 | 0.9668 |
| SR-BH | Lex-payload | 36.20 | 2.00 | 10.91 | 0.1954 |
| SR-BH | CRS PL1 | 44.29 | 25.80 | 32.00 | 0.4488 |

## Panel B: P2 (endpoint-disjoint, unseen endpoint groups)

| corpus | detector | accuracy | FPR | recall | F1 |
|---|---|---:|---:|---:|---:|
| CSIC | NATRIX | 78.85 | 6.50 | 61.73 | 0.7291 |
| CSIC | Lex-full | 69.53 | 21.57 | 59.13 | 0.6415 |
| CSIC | Lex-payload | 96.03 | 2.43 | 94.24 | 0.9564 |
| CSIC | Lex-endpt | 51.55 | 21.50 | 20.05 | 0.2763 |
| CSIC | Generic GBM | 67.65 | 30.80 | 65.84 | 0.6525 |
| CSIC | Stack NATRIX+Lex | 67.55 | 21.35 | 54.57 | 0.6080 |
| CSIC | Stack N+G+Lex | 72.71 | 21.07 | 65.43 | 0.6886 |
| ECML | NATRIX | 91.60 | 1.75 | 76.21 | 0.8455 |
| ECML | Lex-full | 93.76 | 0.51 | 80.47 | 0.8860 |
| ECML | Lex-payload | 92.70 | 0.44 | 76.81 | 0.8638 |
| ECML | Lex-endpt | 71.79 | 1.97 | 11.00 | 0.1904 |
| ECML | Generic GBM | 90.74 | 1.90 | 73.69 | 0.8275 |
| ECML | Stack NATRIX+Lex | 94.02 | 0.35 | 80.99 | 0.8909 |
| ECML | Stack N+G+Lex | 93.91 | 0.51 | 80.97 | 0.8891 |
| SR-BH | NATRIX (20k) | 90.62 | 1.88 | 87.56 | 0.9299 |
| SR-BH | Lex-full | 94.75 | 2.01 | 93.43 | 0.9619 |
| SR-BH | Lex-payload | 36.27 | 1.88 | 10.97 | 0.1964 |
| SR-BH | Lex-endpt | 93.08 | 2.08 | 91.11 | 0.9492 |
