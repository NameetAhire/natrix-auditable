# Dilution-resistant feature variant (v3-D)

## Panel A: bounded mutation suite (all 15,953 attacks)

| contract | clean accuracy | clean FPR | clean recall | mutated recall | delta (pp) | evaded |
|---|---:|---:|---:|---:|---:|---:|
| v3 | 95.55 | 1.93 | 92.60 | 82.47 | -10.13 | 2,639 |
| v3-D | 96.79 | 2.08 | 95.46 | 85.51 | -9.95 | 2,222 |

## Panel B: targeted dilution subset

| contract | original recall | mutated recall | delta (pp) | evaded |
|---|---:|---:|---:|---:|
| v3 | 91.83 | 58.51 | -33.32 | 5,197 |
| v3-D | 94.99 | 66.55 | -28.44 | 4,387 |

## Panel C: per-operator loss (bounded suite)

| operator | n | v3 delta (pp) | v3-D delta (pp) | v3 evaded | v3-D evaded |
|---|---:|---:|---:|---:|---:|
| case | 621 | -0.64 | -2.90 | 16 | 22 |
| sql_comment | 72 | +0.00 | -13.89 | 0 | 10 |
| double_encode | 12,602 | -2.86 | -0.37 | 1,325 | 678 |
| dilution | 14,338 | -11.27 | -11.07 | 2,639 | 2,221 |
