# WCP 2024 endpoint-matched subset

| Detector | Policy | Accuracy | FPR | Recall | F1 | TP | TN | FP | FN |
|---|---|---|---|---|---|---|---|---|---|
| NATRIX | 0.5 | 99.65 | 0.00 | 99.64 | 99.82 | 6,957 | 170 | 0 | 25 |
| Full | 0.5 | 99.92 | 0.00 | 99.91 | 99.96 | 6,976 | 170 | 0 | 6 |
| Payload | 0.5 | 99.89 | 0.00 | 99.89 | 99.94 | 6,974 | 170 | 0 | 8 |
| CRS | frozen | 88.49 | 24.12 | 88.80 | 93.78 | 6,200 | 129 | 41 | 782 |
| Endpoint | 0.5 | 97.62 | 100.00 | 100.00 | 98.80 | 6,982 | 0 | 170 | 0 |

Full/Payload/Endpoint = lexical full-request, payload-only, and endpoint-only models. CRS uses decisions only. The clean side is 170 rows, so the FPR has a wide Wilson interval.
