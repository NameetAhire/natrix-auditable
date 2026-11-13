# SR-BH scale sensitivity: full corpus versus the 20k comparison sample

The detector, folds, and FPR <= 2% policy are identical; only the
training/test population size changes. The nested subsets are drawn
from the full corpus with the same class prevalence, so the curve
separates a sample-size effect from a class-prior artefact.

| subset | n | accuracy | FPR | recall | F1 |
|---|---:|---:|---:|---:|---:|
| full | 422,054 | 95.70 | 1.95 | 94.74 | 0.9690 |
| sample20k | 20,000 | 90.79 | 1.96 | 87.82 | 0.9312 |
| nested10000 | 10,000 | 87.86 | 2.07 | 83.74 | 0.9073 |
| nested20000 | 20,000 | 90.31 | 1.89 | 87.13 | 0.9274 |
| nested50000 | 50,000 | 93.43 | 1.90 | 91.52 | 0.9519 |
| nested100000 | 100,000 | 94.09 | 1.91 | 92.46 | 0.9569 |
| nested200000 | 200,000 | 95.00 | 1.92 | 93.73 | 0.9637 |

Class prevalence: full corpus 70.96% attack; 20k sample 70.97% attack.

## Attack-family mix

| family | full clean | full attack | 20k clean | 20k attack |
|---|---:|---:|---:|---:|
| 126 - Path Traversal | 0 | 12,383 | 0 | 586 |
| 153 - Input Data Manipulation | 0 | 1,123 | 0 | 45 |
| 16 - Dictionary-based Password Attack | 0 | 1,118 | 0 | 67 |
| 194 - Fake the Source of Data | 0 | 46,168 | 0 | 2,202 |
| 242 - Code Injection | 0 | 12,043 | 0 | 597 |
| 272 - Protocol Manipulation | 0 | 4,290 | 0 | 211 |
| 274 - HTTP Verb Tampering | 0 | 4,055 | 0 | 201 |
| 310 - Scanning for Vulnerable Software | 0 | 2,372 | 0 | 110 |
| 34 - HTTP Response Splitting | 0 | 18,882 | 0 | 879 |
| 66 - SQL Injection | 0 | 190,994 | 0 | 8,984 |
| 88 - OS Command Injection | 0 | 6,080 | 0 | 311 |
| normal | 122,546 | 0 | 5,807 | 0 |
