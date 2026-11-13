# Bounded adversarial mutation on CSIC 2010

| Detector | Scope | n | Orig. | Mut. | $\Delta$ pp | Evaded | Ev./blocked |
|---|---|---|---|---|---|---|---|
| NATRIX | all | 15,953 | 92.60 | 82.47 | -10.13 | 2,639 | 17.86 |
| CRS | all | 15,953 | 26.84 | 26.05 | -0.79 | 126 | 2.94 |
| NATRIX | case | 621 | 97.91 | 97.26 | -0.64 | 16 | 2.63 |
| NATRIX | SQL cmt. | 72 | 100.00 | 100.00 | 0.00 | 0 | 0.00 |
| NATRIX | double enc. | 12,602 | 92.13 | 89.27 | -2.86 | 1,325 | 11.41 |
| NATRIX | dilution | 14,338 | 91.82 | 80.55 | -11.27 | 2,639 | 20.04 |
| CRS | case | 621 | 79.39 | 74.88 | -4.51 | 28 | 5.68 |
| CRS | SQL cmt. | 72 | 61.11 | 0.00 | -61.11 | 44 | 100.00 |
| CRS | double enc. | 12,602 | 24.23 | 23.42 | -0.82 | 103 | 3.37 |
| CRS | dilution | 14,338 | 22.05 | 21.21 | -0.84 | 121 | 3.83 |

Orig./Mut. = recall on original/mutated requests; Ev./blocked = evaded as a fraction of originally blocked attacks; SQL cmt. = SQL-comment insertion.
