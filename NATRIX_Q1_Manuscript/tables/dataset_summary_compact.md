# Labelled HTTP corpora

| corpus | role | records | clean / attack | groups | notes |
|---|---|---:|---:|---:|---|
| CSIC 2010 | primary benchmark | 34,593 | 18,640 / 15,953 | endpoint signatures | 97,065 raw; exact dedupe; 0 label conflicts |
| ECML 2007 | in-distribution | 50,116 | 35,006 / 15,110 | endpoint signatures | official training set |
| SR-BH 2020 | in-distribution | 422,054 | 122,546 / 299,508 | 338,640 | 907,815 parsed; 485,237 duplicates; 524 conflicts removed |
| WCP 2024 | diagnostic only | 211,744 | 137,820 / 73,924 | 692 site files | all malicious paths `/`; random split endpoint-confounded; never trained or selected |
