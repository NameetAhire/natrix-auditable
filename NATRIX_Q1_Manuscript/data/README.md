# Data provenance

All results in this project are computed from real, labelled HTTP request
corpora. Every file below is recorded in `manifest.json` with its source URL,
license, retrieval date, byte size and SHA-256.

## Included corpora

### 1. CSIC 2010 — primary benchmark

- **What:** HTTP requests to a simulated e-commerce application; SQLi, XSS,
  path traversal, CRLF injection, SSI, parameter tampering, buffer overflow,
  information gathering.
- **Raw:** 97,065 records across three files.
- **Unique:** 34,593 after exact deduplication (18,640 clean / 15,953 attack);
  0 label-conflicting duplicates.
- **Source used:** <https://github.com/msudol/Web-Application-Attack-Datasets>
  (`OriginalDataSets/csic_2010/dataset_cisc_train_test.tar.gz`).
- **Original:** `http://www.isi.csic.es/dataset/` (currently unreachable).
  IMPACT record: <https://www.impactcybertrust.org/dataset_view?idDataset=940>.
- **Citation:** Torrano-Giménez, Pérez-Villegas & Álvarez, *HTTP data set
  CSIC 2010* (2010); see `paper/refs.bib`.
- **Verification:** the three local files are SHA-256 identical to the mirror
  archive.
- **Known label noise:** some requests labelled anomalous are “unintentional
  illegal” inputs rather than attacks. Reported as a sensitivity analysis, not
  silently relabelled.

### 2. SR-BH 2020 — independent modern corpus

- **What:** 12 days of real traffic to a WordPress server behind ModSecurity
  CRS in detection-only mode; 24 request/response fields; 13 raw CAPEC labels,
  grouped into 11 families for reporting.
- **Raw:** 907,815 parsed rows.
- **Unique:** 422,054 after exact deduplication (122,546 clean / 299,508 attack);
  485,237 duplicates and 524 label-conflict rows removed.
- **Source:** <https://doi.org/10.7910/DVN/OGOIXX> (Harvard Dataverse,
  file 6319496).
- **License:** CC0 1.0.
- **Paper:** Sureda Riera et al., *Computers & Security* 120 (2022) 102788.

### 3. ECML/PKDD 2007 — classic benchmark

- **What:** HTTP requests with a declared class: Valid, XSS, SqlInjection,
  LdapInjection, XPathInjection, PathTransversal, OsCommanding, SSI.
- **Total:** 50,116 requests (35,006 Valid / 15,110 attack), matching the
  official training-set counts exactly.
- **Composition used:** `xml_train.txt` (24,504 Valid) + `xml_test.txt`
  (10,502 Valid + 15,110 attack). The official test labels are not public; no
  claim is made on them.
- **Source:** same GitHub mirror, `OriginalDataSets/ecml_pkdd/`.

### 4. OpenAppSec WAF Comparison Project — real-world FPR and robustness

- **Legitimate:** 692 site files in the published archive. Sampled
  deterministically: up to 200 requests per site → **137,820 requests across
  692 site files**. Apache 2.0.
- **Malicious:** **73,924 payloads** across 7 families (XSS 41,888, traversal
  28,314, cmdexe 2,468, sqli 916, log4shell 220, xxe 70, shellshock 48). Mixed
  licenses, mostly MIT (MGM WAF Payload Collection).
- **Source:** <https://github.com/openappsec/waf-comparison-project> and
  `downloads.openappsec.io`.
- **Use:** FPR measured on legitimate traffic never used in training or model
  selection. Malicious payloads used for robustness, not headline accuracy.

## Excluded data

| Data | Reason |
|---|---|
| DNS logs | not HTTP; different task |
| Zeus PE JSON | host/binary telemetry, not HTTP requests |
| Incident text | unlabelled narrative |
| `http.log` | unlabelled; used only as an unsupervised domain-shift check, never for accuracy |

## Rebuilding the caches

```
python experiments/scripts/build_srbh_cache.py      # ~1 min, 422k rows
python experiments/scripts/build_openappsec.py      # ~2 min, 212k rows
python experiments/scripts/make_manifest.py         # checksums
```

The CSIC cache is built on demand from the published parser in
`Ai-Agent/ml_engine/csic_evaluation.py`; feature extraction always comes from
`Ai-Agent/ml_engine/feature_registry.py`, the same code the proxy serves.
