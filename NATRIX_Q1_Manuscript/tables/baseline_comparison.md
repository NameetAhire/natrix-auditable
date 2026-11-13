# Matched-FPR comparison

| Corpus | Detector | Accuracy | FPR | Recall | F1 |
|---|---|---|---|---|---|
| CSIC | NATRIX | 95.55 | 1.93 | 92.60 | 95.05 |
| CSIC | Lex-payload | 96.90 | 1.88 | 95.47 | 96.60 |
| CSIC | Lex-full | 96.57 | 1.96 | 94.84 | 96.22 |
| CSIC | CRS | 66.24 | 0.03 | 26.84 | 42.30 |
| ECML | NATRIX | 91.96 | 1.67 | 77.19 | 85.27 |
| ECML | Lex-payload | 92.66 | 0.54 | 76.90 | 86.33 |
| ECML | Lex-full | 93.93 | 0.43 | 80.85 | 88.93 |
| ECML | CRS | 78.64 | 20.13 | 75.70 | 67.52 |
| SR-BH | NATRIX | 90.79 | 1.96 | 87.82 | 93.12 |
| SR-BH | Lex-payload | 36.20 | 2.00 | 10.91 | 19.54 |
| SR-BH | Lex-full | 95.41 | 1.98 | 94.34 | 96.68 |
| SR-BH | CRS | 44.29 | 25.80 | 32.00 | 44.88 |
| WCP$^\dagger$ | NATRIX | 99.79 | 0.11 | 99.58 | 99.69 |
| WCP$^\dagger$ | Lex-payload | 99.94 | 0.04 | 99.89 | 99.91 |
| WCP$^\dagger$ | Lex-full | 99.97 | 0.01 | 99.91 | 99.95 |
| WCP$^\dagger$ | CRS | 91.75 | 6.66 | 88.80 | 88.30 |

CRS non-decisions are excluded from the CRS rows: 583 ECML HTTP 400 (1.16%), 377 SR-BH HTTP 400 (1.89%), 24 SR-BH HTTP 405 (0.12%), 77 WCP HTTP 400, and 4 WCP HTTP 414. These requests were rejected by nginx before ModSecurity evaluated them. Counting edge rejections as blocks raises ECML recall to 76.64% at 20.13% FPR and SR-BH recall to 33.45% at 27.04% FPR; it does not change the conclusion.
