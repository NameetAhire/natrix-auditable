# Control models and cross-fitted stackers

The generic control is a 17-feature LightGBM over request-shape,
lexical, and method features that are not the NATRIX contract. The
stackers combine out-of-fold scores with a logistic model fitted on the
other four folds; the threshold is selected leave-one-fold-out at
FPR <= 2%. `Lex` is the hashed character n-gram baseline in the stated
view (`full` = path+query+body, `payload` = query+body).

| corpus | protocol | lexical view | detector | accuracy | FPR | recall | F1 |
|---|---|---|---|---:|---:|---:|---:|
| CSIC | P1 | full | NATRIX | 95.55 | 1.93 | 92.60 | 0.9505 |
| CSIC | P1 | full | Lex | 96.57 | 1.96 | 94.84 | 0.9622 |
| CSIC | P1 | full | Generic GBM | 86.90 | 1.97 | 73.90 | 0.8388 |
| CSIC | P1 | full | Stack N+Lex | 98.45 | 1.24 | 98.08 | 0.9831 |
| CSIC | P1 | full | Stack G+Lex | 96.97 | 1.96 | 95.72 | 0.9669 |
| CSIC | P1 | full | Stack N+G+Lex | 98.44 | 1.24 | 98.08 | 0.9831 |
| CSIC | P2 | full | NATRIX | 78.85 | 6.50 | 61.73 | 0.7291 |
| CSIC | P2 | full | Lex | 69.53 | 21.57 | 59.13 | 0.6415 |
| CSIC | P2 | full | Generic GBM | 67.65 | 30.80 | 65.84 | 0.6525 |
| CSIC | P2 | full | Stack N+Lex | 67.55 | 21.35 | 54.57 | 0.6080 |
| CSIC | P2 | full | Stack G+Lex | 64.04 | 21.68 | 47.36 | 0.5485 |
| CSIC | P2 | full | Stack N+G+Lex | 72.71 | 21.07 | 65.43 | 0.6886 |
| CSIC | P2 | payload | NATRIX | 78.85 | 6.50 | 61.73 | 0.7291 |
| CSIC | P2 | payload | Lex | 96.03 | 2.43 | 94.24 | 0.9564 |
| CSIC | P2 | payload | Generic GBM | 67.65 | 30.80 | 65.84 | 0.6525 |
| CSIC | P2 | payload | Stack N+Lex | 95.89 | 2.70 | 94.24 | 0.9548 |
| CSIC | P2 | payload | Stack G+Lex | 96.19 | 2.09 | 94.19 | 0.9580 |
| CSIC | P2 | payload | Stack N+G+Lex | 96.33 | 1.85 | 94.21 | 0.9595 |
| SR-BH 20k | P2 | full | NATRIX | 90.62 | 1.88 | 87.56 | 0.9299 |
| SR-BH 20k | P2 | full | Lex | 94.75 | 2.01 | 93.43 | 0.9619 |
| SR-BH 20k | P2 | full | Generic GBM | 71.96 | 2.00 | 61.30 | 0.7563 |
| SR-BH 20k | P2 | full | Stack N+Lex | 96.21 | 2.00 | 95.48 | 0.9728 |
| SR-BH 20k | P2 | full | Stack G+Lex | 93.61 | 2.53 | 92.02 | 0.9533 |
| SR-BH 20k | P2 | full | Stack N+G+Lex | 96.19 | 2.01 | 95.45 | 0.9726 |
| SR-BH 20k | P2 | payload | NATRIX | 90.62 | 1.88 | 87.56 | 0.9299 |
| SR-BH 20k | P2 | payload | Lex | 36.27 | 1.88 | 10.97 | 0.1964 |
| SR-BH 20k | P2 | payload | Generic GBM | 71.96 | 2.00 | 61.30 | 0.7563 |
| SR-BH 20k | P2 | payload | Stack N+Lex | 91.46 | 1.95 | 88.76 | 0.9365 |
| SR-BH 20k | P2 | payload | Stack G+Lex | 72.74 | 1.00 | 62.00 | 0.7635 |
| SR-BH 20k | P2 | payload | Stack N+G+Lex | 91.64 | 2.00 | 89.04 | 0.9379 |
| ECML | P2 | full | NATRIX | 91.60 | 1.75 | 76.21 | 0.8455 |
| ECML | P2 | full | Lex | 93.76 | 0.51 | 80.47 | 0.8860 |
| ECML | P2 | full | Generic GBM | 90.74 | 1.90 | 73.69 | 0.8275 |
| ECML | P2 | full | Stack N+Lex | 94.02 | 0.35 | 80.99 | 0.8909 |
| ECML | P2 | full | Stack G+Lex | 93.79 | 0.57 | 80.73 | 0.8869 |
| ECML | P2 | full | Stack N+G+Lex | 93.91 | 0.51 | 80.97 | 0.8891 |
| ECML | P2 | payload | NATRIX | 91.60 | 1.75 | 76.21 | 0.8455 |
| ECML | P2 | payload | Lex | 92.70 | 0.44 | 76.81 | 0.8638 |
| ECML | P2 | payload | Generic GBM | 90.74 | 1.90 | 73.69 | 0.8275 |
| ECML | P2 | payload | Stack N+Lex | 93.54 | 0.40 | 79.51 | 0.8813 |
| ECML | P2 | payload | Stack G+Lex | 93.59 | 0.69 | 80.36 | 0.8832 |
| ECML | P2 | payload | Stack N+G+Lex | 93.63 | 0.74 | 80.60 | 0.8841 |

## Paired accuracy deltas (stack minus lexical base)

| corpus | protocol | view | comparison | delta accuracy (pp) | 95% CI | McNemar p |
|---|---|---|---|---:|---|---:|
| CSIC | P1 | full | Stack N+Lex - Lex | +1.88 | [+1.71, +2.04] | 3.03e-113 |
| CSIC | P1 | full | Stack N+G+Lex - Stack G+Lex | +1.47 | [+1.32, +1.62] | 8.46e-87 |
| CSIC | P2 | full | Stack N+Lex - Lex | -1.98 | [-2.17, -1.78] | 7.88e-91 |
| CSIC | P2 | full | Stack N+G+Lex - Stack G+Lex | +3.50 | [+3.28, +3.71] | 5.04e-246 |
| CSIC | P2 | payload | Stack N+Lex - Lex | -0.14 | [-0.24, -0.05] | 0.00311 |
| CSIC | P2 | payload | Stack N+G+Lex - Stack G+Lex | -0.30 | [-0.43, -0.17] | 6.23e-06 |
| SR-BH 20k | P2 | full | Stack N+Lex - Lex | +1.46 | [+1.23, +1.69] | 1.28e-38 |
| SR-BH 20k | P2 | full | Stack N+G+Lex - Stack G+Lex | +2.60 | [+2.34, +2.88] | 1.1e-95 |
| SR-BH 20k | P2 | payload | Stack N+Lex - Lex | +55.18 | [+54.46, +55.90] | 0 |
| SR-BH 20k | P2 | payload | Stack N+G+Lex - Stack G+Lex | +18.72 | [+18.15, +19.30] | 0 |
| ECML | P2 | full | Stack N+Lex - Lex | +0.26 | [+0.20, +0.34] | 7.59e-15 |
| ECML | P2 | full | Stack N+G+Lex - Stack G+Lex | +0.23 | [+0.16, +0.30] | 2.47e-11 |
| ECML | P2 | payload | Stack N+Lex - Lex | +0.85 | [+0.74, +0.95] | 2.96e-59 |
| ECML | P2 | payload | Stack N+G+Lex - Stack G+Lex | -0.05 | [-0.14, +0.05] | 0.313 |
