# Cross-corpus transfer (source-only thresholds)

The threshold is selected on source out-of-fold predictions; the target
corpus is never used for training or threshold selection.

| source | target | policy | threshold | accuracy | FPR | FNR | F1 |
|---|---|---|---:|---:|---:|---:|---:|
| csic | ecml | f1 | 0.41 | 30.02 | 98.66 | 3.53 | 0.4539 |
| csic | ecml | fpr2 | 0.51 | 37.93 | 86.02 | 6.59 | 0.4758 |
| csic | srbh | f1 | 0.41 | 55.03 | 82.44 | 29.63 | 0.6895 |
| csic | srbh | fpr2 | 0.51 | 53.27 | 81.49 | 32.50 | 0.6722 |
| csic | wcp | f1 | 0.41 | 36.45 | 93.58 | 7.56 | 0.5039 |
| csic | wcp | fpr2 | 0.51 | 39.43 | 88.80 | 7.94 | 0.5149 |
| srbh | csic | f1 | 0.45 | 62.47 | 42.47 | 31.76 | 0.6264 |
| srbh | csic | fpr2 | 0.76 | 63.06 | 21.72 | 54.72 | 0.5306 |
| srbh | ecml | f1 | 0.45 | 42.06 | 69.48 | 31.21 | 0.4172 |
| srbh | ecml | fpr2 | 0.76 | 43.07 | 58.00 | 54.45 | 0.3255 |
| srbh | wcp | f1 | 0.45 | 49.19 | 50.48 | 51.42 | 0.4003 |
| srbh | wcp | fpr2 | 0.76 | 62.35 | 25.64 | 60.03 | 0.4257 |

## OpenAppSec WCP per-family recall (FPR $\leq$ 2% policy)

| source | family | n | recall / specificity | FPR |
|---|---|---:|---:|---:|
| csic | cmdexe | 2,468 | 96.92 | 0.00 |
| csic | legitimate | 137,820 | 11.20 | 88.80 |
| csic | log4shell | 220 | 100.00 | 0.00 |
| csic | shellshock | 48 | 100.00 | 0.00 |
| csic | sqli | 916 | 99.34 | 0.00 |
| csic | traversal | 28,314 | 79.57 | 0.00 |
| csic | xss | 41,888 | 100.00 | 0.00 |
| csic | xxe | 70 | 100.00 | 0.00 |
| srbh | cmdexe | 2,468 | 29.86 | 0.00 |
| srbh | legitimate | 137,820 | 74.36 | 25.64 |
| srbh | log4shell | 220 | 45.45 | 0.00 |
| srbh | shellshock | 48 | 58.33 | 0.00 |
| srbh | sqli | 916 | 54.80 | 0.00 |
| srbh | traversal | 28,314 | 55.13 | 0.00 |
| srbh | xss | 41,888 | 29.92 | 0.00 |
| srbh | xxe | 70 | 51.43 | 0.00 |
