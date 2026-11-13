# Score-level fusion of NATRIX and the lexical baseline

| Corpus | Detector | Accuracy | FPR | Recall | F1 |
|---|---|---|---|---|---|
| CSIC | NATRIX | 95.55 | 1.93 | 92.60 | 95.05 |
| CSIC | Lex-full | 96.57 | 1.96 | 94.84 | 96.22 |
| CSIC | Stack | 98.45 | 1.24 | 98.08 | 98.31 |
| CSIC | Nested | 98.24 | 1.32 | 97.72 | 98.08 |
| ECML | NATRIX | 91.96 | 1.67 | 77.19 | 85.27 |
| ECML | Lex-full | 93.93 | 0.43 | 80.85 | 88.93 |
| ECML | Stack | 94.04 | 0.34 | 81.02 | 89.13 |
| SR-BH | NATRIX | 90.79 | 1.96 | 87.82 | 93.12 |
| SR-BH | Lex-full | 95.41 | 1.98 | 94.34 | 96.68 |
| SR-BH | Stack | 96.81 | 1.98 | 96.31 | 97.72 |
| WCP$^\dagger$ | NATRIX | 99.79 | 0.11 | 99.58 | 99.69 |
| WCP$^\dagger$ | Lex-full | 99.97 | 0.01 | 99.91 | 99.95 |
| WCP$^\dagger$ | Stack | 99.95 | 0.05 | 99.94 | 99.93 |

$^\dagger$ Endpoint-confounded random split. The stacker is not better than the lexical baseline on WCP (accuracy $\Delta = -0.015$ pp, McNemar $p=0.581$).

The nested CSIC row uses an outer five-fold split, inner four-fold base out-of-fold scores, and a stacker and threshold fitted only inside the outer training folds. It is the fully nested check that the CSIC gain is not a threshold-selection artifact.
