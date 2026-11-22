# Evidence readiness summary — 2026-11-05

Historical planning note, kept for provenance and superseded by
`paper/manuscript_short.md`; the IEEE condensation was withdrawn and is not
submitted.  Every number is backed by an artifact under
`experiments/results/`.  The old `NATRIX_MASTER_RESEARCH_PAPER_V3.docx`
figures (99.20% accuracy, 0.08% FPR, 4.12 ms) are not used anywhere.

## 1. Corpora

| Corpus | Rows used | Clean | Attack | Notes |
|---|---:|---:|---:|---|
| CSIC 2010 | 34,593 | 18,640 | 15,953 | Deduplicated; P1 protocol |
| ECML 2007 | 50,116 | 35,006 | 15,110 | Full labelled set |
| SR-BH 2020 | 20,000 | 5,807 | 14,193 | Shared stratified sample for CRS/lexical/NATRIX |
| SR-BH 2020 | 422,054 | — | — | Full-corpus headline for v3/v4 only |
| WCP 2024 | 20,000 | 13,018 | 6,982 | Endpoint-confounded; see §6 |
| WCP 2024 (endpoint subset) | 7,152 | 170 | 6,982 | `path == /`; diagnostic only |

## 2. Matched operating points (cross-fitted FPR <= 2%)

| Corpus | Detector | Accuracy | FPR | Recall | F1 |
|---|---|---:|---:|---:|---:|
| CSIC | NATRIX v3 | 95.55% | 1.93% | 92.60% | 95.05% |
| CSIC | lexical full | 96.57% | 1.96% | 94.84% | 96.22% |
| CSIC | CRS PL1 | 66.24% | 0.03% | 26.84% | 42.30% |
| CSIC | NATRIX+lexical stack | 98.45% | 1.24% | 98.08% | 98.31% |
| ECML | NATRIX v3 | 91.96% | 1.67% | 77.19% | 85.27% |
| ECML | lexical full | 93.93% | 0.43% | 80.85% | 88.93% |
| ECML | CRS PL1 | 78.64% | 20.13% | 75.70% | 67.52% |
| ECML | NATRIX+lexical stack | 94.04% | 0.34% | 81.02% | 89.13% |
| SR-BH 20k | NATRIX v3 | 90.79% | 1.96% | 87.83% | 93.12% |
| SR-BH 20k | lexical full | 95.41% | 1.98% | 94.34% | 96.68% |
| SR-BH 20k | CRS PL1 | 44.29% | 25.80% | 32.00% | 44.88% |
| SR-BH 20k | NATRIX+lexical stack | 96.81% | 1.98% | 96.31% | 97.72% |
| WCP 20k | NATRIX v3 | 99.79% | 0.11% | 99.58% | 99.69% |
| WCP 20k | lexical full | 99.97% | 0.01% | 99.91% | 99.95% |
| WCP 20k | CRS PL1 | 91.75% | 6.66% | 88.80% | 88.30% |
| WCP 20k | NATRIX+lexical stack | 99.95% | 0.05% | 99.94% | 99.93% |

The lexical full-request baseline wins at the 2% FPR point on every corpus.
NATRIX is competitive at looser FPR (CSIC ROC crossing at 5%: 95.69% vs
95.79% recall) but is not the best single detector.  The stacker recovers the
gap on CSIC/ECML/SR-BH; on WCP it does not beat lexical alone (p=0.581).

CRS non-decisions: ECML 583 HTTP 400 (1.16%); SR-BH 377 HTTP 400 (1.89%) and
24 HTTP 405 (0.12%); WCP 77 HTTP 400 and 4 HTTP 414.  These never reached
ModSecurity and are reported separately.  Counting edge rejections as blocks
raises ECML recall to 76.64% at 20.13% FPR and SR-BH to 33.45% at 27.04% FPR.

## 3. Gate + CRS fusion

| Corpus | Policy | Accuracy | FPR | Recall | F1 |
|---|---|---:|---:|---:|---:|
| CSIC | OR | — | +0.03 pp | +0.09 pp | — |
| ECML | OR | 81.28% | 21.19% | 87.00% | 73.70% |
| ECML | AND | 88.41% | 0.61% | 62.96% | 76.61% |
| SR-BH 20k | OR | 86.74% | 27.16% | 92.43% | 90.82% |
| SR-BH 20k | AND | 47.94% | 0.17% | 26.71% | 42.14% |
| WCP 20k | OR | 95.60% | 6.71% | 99.90% | 94.06% |
| WCP 20k | AND | 95.98% | 0.01% | 88.48% | 93.88% |

OR adds 14/1,483/653/22 attacks on CSIC/ECML/SR-BH/WCP for 6/6,835/1,463/860
clean false positives.  At a 2% FPR budget the signature channel is not a
useful second agent.  This is a negative result for the gate + TI claim.

## 4. Adversarial check (CSIC, same 15,953 mutated requests)

| Detector | Clean recall | Mutated recall | Delta | Evasion among blocked |
|---|---:|---:|---:|---:|
| NATRIX v3 | 92.60% | 82.47% | -10.13 pp | 17.86% (2,639/14,773) |
| CRS PL1 | 26.84% | 26.05% | -0.79 pp | 2.94% (126/4,281) |

NATRIX is weakest under dilution (-11.27 pp) and double encoding (-2.86 pp);
case and SQL comments are neutral.  CRS is weakest under SQL-comment insertion
(44/44 blocked attacks evaded) and case changes (-4.51 pp), but robust to
dilution (-0.84 pp).  Neither dominates: CRS is harder to evade per blocked
attack, NATRIX detects far more attacks before and after mutation.

## 5. Architecture and systems evidence

- **CPPP sidecar:** 700 audit records, hash chain OK, 108 promotions = 108
  retirements (8 auto-retired), all invariants true.  Promote p95 3.63 ms
  (no fsync) / 34.18 ms (fsync); rollback p95 3.33 / 34.44 ms.  This is a
  sidecar, not the shipped proxy.
- **Extractor parity:** 2,000 class-balanced CSIC/ECML cases, all 22 features
  exact, max absolute delta 0.0.
- **Latency:** 9,700 measured requests, 0 failures.  Total p50 2.86 ms,
  p95 3.78 ms, p99 5.69 ms.  Extraction p95 0.197 ms; score p95 0.0038 ms;
  HTTP hop p95 3.61 ms.
- **v3 vs v4:** ECML null (p=0.836 at 0.5; p=0.516 at FPR2).  Full SR-BH v4
  +0.009 pp at 0.5 (p=0.039) and +0.009 pp at FPR2 (p=0.048), negligible.
  v4 is an audit/parsimony artifact, not an accuracy gain.
- **Label harmonisation ECML vs SR-BH:** 13 same / 9 reversed overall;
  12 / 10 family-balanced; SQLi 14/8, traversal 11/11, cmdi 12/10.  The
  reversal is not merely attack-family composition.
- **Nested CSIC stacker:** 98.24% accuracy, 1.32% FPR, 97.72% recall, F1
  98.08.  NATRIX 94.28/1.06/88.83; lexical 96.49/1.85/94.56.  The fusion gain
  survives full nesting.

## 6. WCP 2024 caveat

Every malicious request in WCP has path `/`; the 137,820 legitimate requests
span thousands of paths.  An endpoint-only lexical model reaches 100% recall
at 1.31% FPR on the 20k sample, so the random-split WCP result is
endpoint-confounded.  The endpoint-matched subset (`path == /`) has 170 clean
and 6,982 attack rows; there, NATRIX reaches 99.65% accuracy at 0% FPR
(0/170; Wilson 95% upper bound 2.21%) and 99.64% recall, lexical full 99.92%
at 0% FPR and 99.91% recall, CRS 88.49% at 24.12% FPR and 88.80% recall.  WCP
is an out-of-corpus sanity check and a dataset-limitation example, not a
generalisation claim.

## 7. Open decisions (as of 2026-11-05; resolved later)

1. **Real-network validation:** no host, protected application, traffic, or
   approval has been defined.  Without them the paper says "offline corpora
   only" and treats live validation as future work.
2. **Published ML baseline:** WADBERT (arXiv 2601.21893) reports F1 99.64 on
   CSIC and 99.59 on SR-BH, but no code/model was released and the protocol is
   not reproduced here.  The lexical char n-gram learner is a strong standard
   baseline, not a named published system.  Choose: cite WADBERT as reported
   literature with a protocol caveat, or implement a reproducible published
   method.
3. **Paper framing:** the evidence supports an auditable feature-selection and
   promotion protocol, not a state-of-the-art detector.  Candidate title:
   "NATRIX: An Auditable Feature-Selection and Promotion Protocol for Inline
   HTTP Attack Detection".
4. **WCP:** include as a limitation/diagnostic, or drop it from the IEEE
   version to save space.
5. **IEEE 7–8 page build:** only after decisions 1–3 are settled.

## 8. Artifact map

- `experiments/results/baselines/` — CRS, lexical, matched-FPR, fusion,
  ROC/family, WCP outputs.
- `experiments/results/adversarial/` — mutated CSIC parquet, NATRIX and CRS
  evasion JSON/CSV.
- `experiments/results/cppp/` — sidecar bench, cycles, audit logs.
- `experiments/results/v3_v4/` — corpus v3/v4 results.
- `experiments/results/latency/latency_report.json` — latency.
- `experiments/results/parity/extractor_parity.json` — extractor parity.
- `experiments/results/feature_audit/label_harmonisation.*` — harmonisation.
