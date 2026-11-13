# Cross-fitted threshold calibration (CSIC 2010, P1, 3 seeds)

For each outer fold, the threshold is selected on the outer OOF
predictions of the other four folds (D13). Values are mean over seeds;
`min`/`max` are over seeds.

| feature set | policy | threshold | accuracy | min acc | FPR | max FPR | FNR | F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| v3 | f1 | 0.44 | 95.83 | 95.71 | 3.40 | 4.07 | 5.06 | 0.9546 |
| v3 | fpr1 | 0.60 | 93.96 | 93.89 | 0.99 | 0.99 | 11.94 | 0.9308 |
| v3 | fpr2 | 0.51 | 95.55 | 95.43 | 1.94 | 1.95 | 7.38 | 0.9505 |
| v4 | f1 | 0.44 | 95.92 | 95.76 | 3.26 | 3.63 | 5.04 | 0.9555 |
| v4 | fpr1 | 0.60 | 94.05 | 93.94 | 0.98 | 1.00 | 11.76 | 0.9318 |
| v4 | fpr2 | 0.51 | 95.55 | 95.38 | 1.96 | 2.00 | 7.35 | 0.9505 |

**Acceptance check (all seeds, FPR<=2% policy).**

- `v3`: accuracy mean 95.55 (min 95.43), FPR mean 1.94 (max 1.95); both targets met on every seed: **True**.
- `v4`: accuracy mean 95.55 (min 95.38), FPR mean 1.96 (max 2.00); both targets met on every seed: **True**.

Paired $\Delta$accuracy (v4 $-$ v3, seed 42, FPR<=2%): -0.01 pp [-0.07, +0.06]; McNemar $p=0.8624$.
