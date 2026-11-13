# SR-BH scale sensitivity: full corpus versus the 20k comparison sample

| subset | n | accuracy | FPR | recall | F1 |
|---|---:|---:|---:|---:|---:|
| full | 422,054 | 95.70 | 1.95 | 94.74 | 0.9690 |
| sample 20k | 20,000 | 90.79 | 1.96 | 87.82 | 0.9312 |
| nested 10k | 10,000 | 87.86 | 2.07 | 83.74 | 0.9073 |
| nested 20k | 20,000 | 90.31 | 1.89 | 87.13 | 0.9274 |
| nested 50k | 50,000 | 93.43 | 1.90 | 91.52 | 0.9519 |
| nested 100k | 100,000 | 94.09 | 1.91 | 92.46 | 0.9569 |
| nested 200k | 200,000 | 95.00 | 1.92 | 93.73 | 0.9637 |

Class prevalence is 70.96% attack in the full corpus and 70.97% in the 20k
sample. Attack-family shares are stable: SQL injection is 63.77% of full-corpus
attacks and 63.30% of sample attacks; fake-source is 15.41% and 15.51%.
