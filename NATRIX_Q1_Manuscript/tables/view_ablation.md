# View ablation: which request fields carry the signal?

| corpus | protocol | view | accuracy | FPR | recall | F1 |
|---|---|---|---:|---:|---:|---:|
| SR-BH 20k | P1 | full | 90.79 | 1.96 | 87.82 | 0.9312 |
| SR-BH 20k | P1 | no_path | 37.52 | 1.93 | 12.74 | 0.2244 |
| SR-BH 20k | P1 | path_only | 89.16 | 1.98 | 85.53 | 0.9180 |
| SR-BH 20k | P1 | query_only | 36.35 | 1.91 | 11.10 | 0.1984 |
| SR-BH 20k | P1 | body_only | 35.38 | 1.55 | 9.58 | 0.1739 |
| SR-BH 20k | P2 | full | 90.62 | 1.88 | 87.56 | 0.9299 |
| SR-BH 20k | P2 | no_path | 37.29 | 2.08 | 12.49 | 0.2203 |
| SR-BH 20k | P2 | path_only | 89.05 | 1.83 | 85.31 | 0.9170 |
| SR-BH 20k | P2 | query_only | 34.03 | 1.55 | 7.68 | 0.1418 |
| SR-BH 20k | P2 | body_only | 35.24 | 1.86 | 9.50 | 0.1724 |
| CSIC | P1 | full | 95.55 | 1.93 | 92.60 | 0.9505 |
| CSIC | P1 | no_path | 95.34 | 2.01 | 92.24 | 0.9481 |
| CSIC | P1 | path_only | 60.87 | 0.09 | 15.26 | 0.2645 |
| CSIC | P1 | query_only | 73.26 | 1.98 | 44.34 | 0.6047 |
| CSIC | P1 | body_only | 68.77 | 2.00 | 34.62 | 0.5056 |
| CSIC | P2 | full | 78.85 | 6.50 | 61.73 | 0.7291 |
| CSIC | P2 | no_path | 75.07 | 4.26 | 50.92 | 0.6532 |
| CSIC | P2 | path_only | 34.47 | 99.92 | 74.64 | 0.5123 |
| CSIC | P2 | query_only | 51.02 | 27.27 | 25.66 | 0.3258 |
| CSIC | P2 | body_only | 50.45 | 28.06 | 25.34 | 0.3205 |
