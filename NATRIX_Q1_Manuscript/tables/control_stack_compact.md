# Control models and cross-fitted stackers (compact)

| corpus | view | NATRIX | Lex | Generic | N+Lex | N+G+Lex |
|---|---|---:|---:|---:|---:|---:|
| CSIC P1 | full | 95.55/1.93 | 96.57/1.96 | 86.90/1.97 | 98.45/1.24 | 98.44/1.24 |
| CSIC P2 | full | 78.85/6.50 | 69.53/21.57 | 67.65/30.80 | 67.55/21.35 | 72.71/21.07 |
| CSIC P2 | payload | 78.85/6.50 | 96.03/2.43 | 67.65/30.80 | 95.89/2.70 | 96.33/1.85 |
| ECML P2 | full | 91.60/1.75 | 93.76/0.51 | 90.74/1.90 | 94.02/0.35 | 93.91/0.51 |
| ECML P2 | payload | 91.60/1.75 | 92.70/0.44 | 90.74/1.90 | 93.54/0.40 | 93.63/0.74 |
| SR-BH 20k P2 | full | 90.62/1.88 | 94.75/2.01 | 71.96/2.00 | 96.21/2.00 | 96.19/2.01 |
| SR-BH 20k P2 | payload | 90.62/1.88 | 36.27/1.88 | 71.96/2.00 | 91.46/1.95 | 91.64/2.00 |

Cells are accuracy/FPR (%). `Lex` is the hashed character n-gram baseline
in the stated view. The NATRIX score is the same 22-D model in both
payload rows, because the contract always includes the path.
