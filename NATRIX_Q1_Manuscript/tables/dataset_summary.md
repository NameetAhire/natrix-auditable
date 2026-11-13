# Labelled HTTP corpora

| corpus | role | records used | clean / attack | groups | notes |
|---|---|---:|---:|---:|---|
| CSIC 2010 | primary in-distribution benchmark | 34,593 unique | 18,640 / 15,953 | endpoint signatures | 97,065 raw; exact dedupe; 0 label conflicts |
| ECML/PKDD 2007 | classic in-distribution + transfer target | 50,116 | 35,006 / 15,110 | endpoint signatures | official training set (`xml_train` + `xml_test`) |
| SR-BH 2020 | modern in-distribution + transfer target | 422,054 unique | 122,546 / 299,508 | 338,640 | 907,815 parsed; 485,237 duplicates and 524 label-conflict rows removed |
| OpenAppSec WCP | diagnostic only: endpoint-matched subset | 137,820 legitimate + 73,924 malicious | 137,820 / 73,924 | 692 site files | all malicious rows have path `/`; random split is endpoint-confounded; never used for training or selection |

## SR-BH attack families (unique records)

| family | records |
|---|---:|
| SQL Injection | 190,994 |
| Fake the Source of Data | 46,168 |
| HTTP Response Splitting | 18,882 |
| Path Traversal | 12,383 |
| Code Injection | 12,043 |
| OS Command Injection | 6,080 |
| Protocol Manipulation | 4,290 |
| HTTP Verb Tampering | 4,055 |
| Scanning for Vulnerable Software | 2,372 |
| Input Data Manipulation | 1,123 |
| Dictionary-based Password Attack | 1,118 |

## ECML/PKDD 2007 declared classes

| class | records |
|---|---:|
| Valid | 35,006 |
| OsCommanding | 2,302 |
| PathTransversal | 2,295 |
| XPathInjection | 2,279 |
| LdapInjection | 2,279 |
| SqlInjection | 2,274 |
| SSI | 1,856 |
| XSS | 1,825 |

## OpenAppSec malicious families
| family | payloads |
|---|---:|
| XSS | 41,888 |
| traversal | 28,314 |
| cmdexe | 2,468 |
| sqli | 916 |
| log4shell | 220 |
| xxe | 70 |
| shellshock | 48 |

## Split protocols

- **P1 deployment-like**: stratified 5-fold over unique requests; no identical
  request crosses the split, but the same endpoint may appear in train and test.
  This is the headline protocol and matches how a WAF is operated.
- **P2 endpoint-disjoint**: groups are `(method, normalised path, query keys,
  body keys)`; a group is assigned wholly to one fold. Reported as a
  generalisation bound, never as the headline number.

Sources and checksums: `data/manifest.json`. Counts: `data/processed/*/*_summary.json`,
`data/README.md`.
