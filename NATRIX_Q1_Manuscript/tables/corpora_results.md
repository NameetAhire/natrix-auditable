# In-distribution results (22-D v3 gate)

P1 = deployment-like stratified; P2 = endpoint-disjoint bound.
Threshold 0.5 unless a policy column says otherwise.

| corpus | protocol | policy | n | accuracy | FPR | FNR | F1 | ROC-AUC |
|---|---|---|---:|---:|---:|---:|---:|---:|
| csic | P1 | threshold_0.5 | 34,593 | 95.63 | 2.07 | 7.06 | 0.9515 | 0.9910 |
| csic | P2 | threshold_0.5 | 34,593 | 82.21 | 24.30 | 10.18 | 0.8232 | 0.8992 |
| ecml | P1 | threshold_0.5 | 50,116 | 92.00 | 1.50 | 23.04 | 0.8530 | 0.9087 |
| ecml | P2 | threshold_0.5 | 50,116 | 91.65 | 1.50 | 24.24 | 0.8454 | 0.9082 |
| srbh | P1 | threshold_0.5 | 422,054 | 95.99 | 7.56 | 2.55 | 0.9718 | 0.9942 |
| srbh | P2 | threshold_0.5 | 422,054 | 94.21 | 11.98 | 3.25 | 0.9596 | 0.9886 |
