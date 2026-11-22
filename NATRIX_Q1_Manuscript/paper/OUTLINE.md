# Manuscript outline and evidence map

Target: *Computers & Security* (Elsevier), subscription route.
Title: **NATRIX: A Verifiable Multi-Agent Architecture for Inline HTTP Attack
Detection with Statistically Selected Features and Contract-Governed Agent
Promotion**

Authors: Ahire Nameet Sudam and D. D. Ambawade, Department of Computer
Engineering, Sardar Patel Institute of Technology, Mumbai 400058, India.

Every number in the manuscript resolves to a file in this workspace. This map
is the post-draft checklist: it records what each section claims, which
artifact backs it, and which table or figure carries it. The source of truth is
`paper/manuscript.md`; this file is an index, not a second draft.

## Front matter

- Title, authors, abstract, keywords.
- Abstract reports: 34,593 CSIC requests; 20-D v4; two dropped features; 24
  candidates screened, 12 accepted statistically and none admitted on cost;
  CPPP model-checked with 8/8 mutants killed; CSIC P1 and SR-BH P1 at
  95.55%/1.93% and 95.70%/1.95% under cross-fitted calibration; nested CSIC
  94.67%/1.26%; deployed gateway 30/30 attacks blocked with zero benign
  blocks; inline p95 3.78 ms on 9,700 measured requests.
- The abstract distinguishes the cross-fitted and fully nested operating
  points and does not claim a v4 accuracy gain.

## 1. Introduction

- Problem: inline WAF decisions need auditable feature sets, promotion rules,
  and latency budgets, not only benchmark accuracy.
- Gap: feature choices are reported without drop evidence; agent promotion is
  described but not modelled; latency claims often exclude serialisation and
  the decision service.
- Contributions:
  1. NATRIX architecture: nine roles, five-role synchronous decision path,
     four asynchronous governance roles.
  2. A frozen four-condition feature-drop rule applied to the 22-D contract,
     with written per-feature evidence and a 20-D v4 outcome.
  3. A pre-registered 24-candidate screen that admits zero candidates because
     the measured extraction cost exceeds the 0.15 ms budget (negative result).
  4. Multi-corpus evaluation on CSIC 2010, SR-BH 2020, ECML/PKDD 2007, and
     OpenAppSec WCP, with P1/P2 protocols and source-only transfer.
  5. CPPP model-checked in TLA+ with an executable reference and exhaustive
     enumeration; trust decay verified by exact rational enumeration and
     symbolic identities.
  6. End-to-end Node→Python inline latency measured on real artifacts.
- Evidence: `protocol/analysis_plan.md`, `protocol/runtime_gap.md`,
  `artifacts/formal/`, `experiments/results/`.

## 2. Related work

- Signature and learned HTTP detection: CSIC 2010, ECML/PKDD 2007, SR-BH 2020,
  OWASP CRS, WAF machine learning.
- Evaluation bias and dataset shift: Sommer & Paxson; Arp et al.; Pendlebury
  et al.; domain shift and temporal bias.
- Feature selection and explanation: Breiman; Lundberg & Lee; Fisher et al.;
  Benjamini & Hochberg; Demšar; permutation importance.
- Agent architectures and formal assurance: software-agent systems,
  TLA+/TLC, property-based testing, defence in depth.
- Federated learning is cited as related future work only; no federated result
  is claimed in this paper.
- Evidence: `paper/refs.bib` (43 entries, all cited).

## 3. NATRIX architecture and threat model

- Design constraints: inline decision, bounded payload contract, no generative
  model in the decision path, single-writer policy authority.
- Nine roles: Telemetry Ingestion, Zero-Trust Verifier, Threat Intelligence,
  Risk Scoring, ML Engine, Remediation Orchestrator, Adaptive Memory, Policy,
  Containment.
- Synchronous five-role path: Telemetry, Zero-Trust, Threat Intelligence, ML
  Engine, Orchestrator. Asynchronous/post-decision: Risk Scoring, Adaptive
  Memory, Policy, Containment.
- Request path and verdict semantics: allow, block, challenge, quarantine;
  fail-closed on contract violation.
- Authority separation: no role both observes and promotes; CPPP gives
  promotion authority to the Policy Agent and requires independent evidence.
- Threat model and assumptions: attacker controls request content, not the
  host; model and contract integrity assumed; CPPP addresses policy promotion,
  not Byzantine agents.
- Runtime gap: the shipped runtime has a promotion shortcut; CPPP is proposed
  and model-checked, not claimed deployed.
- Figure 1: architecture.
- Evidence: `D:\Mtech\MAJOR_PROJECT\Ai-Agent\proxy\server.js` (read-only),
  `D:\Mtech\MAJOR_PROJECT\Ai-Agent\agents\`,
  `ml_engine/model_service.py`, `protocol/runtime_gap.md`.

## 4. CPPP and trust decay

- Lifecycle: observed → canary → promoted → retired, with quorum K, trust
  floor τ, canary evidence, and an audit record.
- Invariants: no promotion without canary, quorum, trust, observations, and
  audit; no promotion after a benign canary hit; no direct promotion; retired
  rules are never active; active implies audited.
- TLA+ model: one-rule and two-rule configurations; 939/278/depth 12 and
  444,245/77,284/depth 23 from TLC logs; no invariant violation.
- Executable reference: Python CPPP implementation; exhaustive BFS depth 9 =
  20,678 states / 97,870 transitions.
- Trust decay: discrete rational grid, 81,484 cases, zero violations; nine
  SymPy symbolic identities.
- Mutation test: 8/8 mutants killed with the expected invariant.
- Scope: control-flow safety only; not statistical validity of canary
  outcomes, not agent independence or Sybil resistance.
- Evidence: `artifacts/formal/Cppp.tla`, `artifacts/formal/tlc_*.log`,
  `artifacts/formal/trust_decay_verification.json`,
  `experiments/tests/test_formal.py` (13 passed).
- The formal numbers are reported in Section 9; the TLA+ configuration is
  `artifacts/formal/Cppp.tla`.

## 5. Feature contract and statistical selection

- Contract versions: v1 10-D, v2 16-D, v3 22-D, v4 20-D. v1/v2 remain
  compatible; v3 is the active runtime contract; v4 is the statistically
  selected contract.
- CSIC 2010: 97,065 raw → 34,593 unique (18,640 clean / 15,953 attack), zero
  ambiguous after deduplication.
- Frozen four-condition drop rule C1–C4, fixed before selection; learner
  pinned to the shipped Random Forest (`n_estimators=200`, unlimited depth,
  `min_samples_leaf=1`, `max_features=None`, no class weighting,
  `random_state=42`, D5).
- Drop outcome: exactly two features dropped (`html_tag_density`,
  `param_pollution_count`); 20 retained, including 7 safety-retained features.
- `token_count` caveat: permutation-importance CI entirely negative
  ([-0.00082, -0.00026]), so C2 fails; ablation effect negligible (+0.029 pp).
  Retained by the conservative rule and reported as a limitation.
- Ablation: largest degradation is `shannon_entropy` −1.50 pp, then
  `uppercase_ratio` −1.08, `digit_ratio` −0.89, `hex_encoding_ratio` −0.72.
  Ablation and permutation rankings are not identical.
- Candidate screen: 24 candidates → 16 after constant/correlation filters →
  12 statistically accepted → 0 admitted on cost. The 0.15 ms extraction budget fails: candidate
  pass p95 3.799 ms, combined v3+candidate p95 10.918 ms, v3 worst-case p95
  6.680 ms. Final v4 = 20-D retained core. Five raw-accepted candidates
  (`backslash_count`, `brace_count`, `nonascii_ratio`, `ldap_filter_score`,
  `crlf_sequence_count`) are exactly constant on CSIC; their identical
  +0.046 pp gain is an RNG artifact.
- `param_name_digit_ratio` had the largest raw gain (+4.46 pp F1) but is
  rejected by the cost budget; reported as future work.
- Cross-corpus replication: ECML and SR-BH; descriptive only, no selection.
- Figure 2: ablation. Table 1: safety-retained features. Table 2: candidate
  screen. Tables 14–16 in Appendix A: full drop evidence.
- Evidence: `artifacts/feature_selection/drop_evidence.csv`,
  `artifacts/feature_selection/v4_definition.json`,
  `artifacts/feature_selection/v4_definition_screened.json`,
  `experiments/results/ablation_csic/metrics.csv`,
  `experiments/results/feature_audit/`,
  `experiments/results/v4_screening/`,
  `experiments/results/latency/candidate_cost.json`.

## 6. Evaluation protocol

- Datasets: CSIC 2010 primary; SR-BH 2020 modern corpus; ECML/PKDD 2007
  classic benchmark; OpenAppSec WCP real-world legitimate and malicious
  payloads. Only labelled HTTP requests are used; no DNS, PE, incident text,
  or unlabelled `http.log` enters training or selection.
- Deduplication and label-conflict handling per corpus; SR-BH 907,815 parsed
  → 422,054 unique, 485,237 duplicates and 524 label-conflict rows dropped;
  338,640 endpoint groups.
- P1 deployment-like stratified 5-fold: headline protocol. P2
  endpoint-disjoint: generalisation bound, not a headline result.
- Learners: shipped Random Forest headline; HGB and L2 logistic regression
  as fixed untuned robustness checks (D9).
- Thresholds: F1-optimal, FPR ≤ 1%, FPR ≤ 2% (D8); nested inner-CV for the
  pre-registered result; cross-fitted leave-one-fold-out calibration for the
  deployment operating point (D13), with the non-fully-nested caveat stated.
- Statistics: paired McNemar, paired bootstrap 95% CIs, BH correction,
  Cliff's delta for direction replication.
- Transfer: source-only thresholds; target never used for training or
  threshold selection.
- Latency: full Node extraction → HTTP /predict → ONNX gate → threat typing →
  verdict; 10,000 requests, 300 warm-up, 9,700 measured; side effects excluded
  and disclosed.
- Reproducibility: `experiments/run_all.ps1` covers audit, ablation, drop
  merge, screening, corpus evaluation, calibration, transfer, learners,
  latency, tables, and figures.
- Table 3: dataset summary.
- Evidence: `protocol/analysis_plan.md`, `protocol/deviations.md`,
  `data/manifest.json`, `data/README.md`,
  `experiments/results/corpora/*_folds_seed42.npz`.

## 7. Results

### 7.1 In-distribution accuracy

- 0.5 threshold: CSIC P1 95.63%/2.07%; SR-BH P1 95.99%/7.56%; ECML P1
  92.00%/1.50%; P2 collapses for CSIC (82.21%/24.30%), milder for SR-BH
  (94.21%/11.98%), unchanged for ECML (91.65%/1.50%).
- Cross-fitted FPR ≤ 2%: CSIC P1 95.55%/1.93%; SR-BH P1 95.70%/1.96%; ECML
  P1 91.96%/1.67%; P2 CSIC 78.85%/6.50%, ECML 91.60%/1.75%, SR-BH
  94.01%/2.77%.
- Fully nested CSIC: v3 94.67%/1.26%, v4 94.59%/1.24%; both narrowly miss the
  95% target. The manuscript reports both nested and cross-fitted results.
- Tables 4 and 5.
- Evidence: `experiments/results/corpora/corpora_metrics.csv`,
  `corpora_calibration.json`, `tables/corpora_results.md`,
  `tables/corpora_calibrated.md`.

### 7.2 v3 versus v4

- Nested: v3 F1 95.87%/3.11%, v4 95.91%/3.03%; FPR ≤ 2%: v3 94.67%/1.26%,
  v4 94.59%/1.24%. McNemar seed 42 F1 p=0.1328, Δacc +0.058 pp CI
  [−0.009, +0.130].
- Cross-fitted: both 95.55%, v3 FPR 1.94%, v4 1.96%; McNemar p=0.8624,
  Δacc −0.009 pp CI [−0.072, +0.058].
- v4 is behaviorally inert on CSIC: the two dropped features are constant
  zero, so the forest partition is unchanged; small RF differences are RNG
  tie-breaking. No performance gain is claimed.
- Figures 3 and 4. Tables 6 and 7.
- Evidence: `experiments/results/v3_v4/comparison_metrics.csv`,
  `calibrated_metrics.csv`, `calibration_summary.json`.

### 7.3 Secondary learners

- HGB F1 90.23% (v3) / 90.28% (v4); FPR ≤ 2% 89.12% both.
- Logistic F1 75.48% both; FPR ≤ 2% 76.44% both.
- Seed-42 paired v4−v3: Δaccuracy 0.0, McNemar p=1.0 for both. Across seeds,
  HGB mean 90.28 vs 90.23 (+0.05 pp) and logistic unchanged; attributed to
  tie-breaking, not feature signal.
- Table 8.
- Evidence: `experiments/results/learners/learner_metrics.csv`,
  `learner_summary.json`.

### 7.4 Interpretability

- Permutation top two: `uppercase_ratio` 0.2716, `hex_encoding_ratio` 0.2069;
  third is `digit_ratio` 0.1375. SHAP top three: `uppercase_ratio` 0.1429,
  `hex_encoding_ratio` 0.0838, `sql_keyword_score` 0.0637.
- Six zero-SHAP features: the two dropped plus four safety-retained
  (`command_injection_score`, `path_traversal_score`, `null_byte_score`,
  `user_agent_anomaly`). Safety retention prevents a rare-but-decisive policy
  signal from being discarded.
- Figure 5. Table 9.
- Evidence: `experiments/results/feature_audit/csic_shap_importance.csv`,
  `permutation_importance.csv`, `tables/interpretability.md`.

### 7.5 Cross-corpus transfer and direction reversal

- Ten of 22 features reverse direction on both ECML and SR-BH.
- Source-only thresholds collapse: CSIC→SR-BH AUC 0.4354, SR-BH→ECML AUC
  0.4864, both below chance; transfer accuracy far below in-distribution.
- WCP family recall and legitimate FPR reported by family; WCP never used for
  training or selection.
- The defensible claim is corpus-specific direction and deployment-local
  calibration, not universal generalisation.
- Figure 6. Tables 10 and 11.
- Evidence: `experiments/results/transfer/transfer_metrics.csv`,
  `transfer_summary.json`, `wcp_family_recall.csv`,
  `experiments/results/cross_corpus/cross_corpus_directions.csv`.

### 7.6 Inline latency and ONNX parity

- 10,000 loaded, 300 warm-up, 9,700 measured, 0 failures; p50 2.863 ms,
  p95 3.779 ms, p99 5.692 ms. SLO p95 < 5 ms met; p99 exceeds 5 ms.
- Per corpus p95: CSIC 3.862, ECML 3.540, WCP 3.848 ms.
- Worst-case 8 KiB extraction p95 6.680 ms and combined v3+candidate p95
  10.918 ms exceed 5 ms; these are adversarial/upper-bound measurements, not
  the real-sample headline.
- ONNX parity: 79,593 real requests; gate max probability delta 1.788e-7,
  three label disagreements all ties, zero non-tie; threat max 1.264e-7,
  1,022 mismatches all ties, zero non-tie.
- Side effects excluded: synchronous SQLite/logging/containment; disclosed.
- Figure 7. Table 12.
- Evidence: `experiments/results/latency/latency_report.json`,
  `artifacts/models/onnx_parity.json`,
  `experiments/results/latency/latency_inputs.json`.

## 8. Formal verification

- TLA+ one rule: 939 generated / 278 distinct / depth 12, no error.
- TLA+ two rules: 444,245 generated / 77,284 distinct / depth 23, no error.
- Invariants checked: TypeOK, NoPromotionWithoutCanary,
  NoPromotionWithoutQuorum, NoPromotionWithoutTrust,
  NoPromotionWithoutObservations, NoPromotionWithCanaryHit,
  ActiveImpliesAudited, RetiredNotActive, NoDirectPromotion.
- Executable reference: 13 tests pass; exhaustive BFS depth 9 = 20,678 states /
  97,870 transitions.
- Mutation test: 8/8 mutants killed with the expected invariant.
- Trust decay: 81,484 exact rational cases, zero violations; nine symbolic
  identities pass (initial value, limit at infinity, monotone decreasing,
  bounded above identity, half-life identity, recovery nondecreasing, recovery
  upper bound, recovery contracts gap, contraction identity).
- Scope: control-flow safety and trust arithmetic; not canary statistical
  validity, not agent independence, not Byzantine fault tolerance.
- The formal numbers are reported in Section 9 text; the TLA+ configuration is
  `artifacts/formal/Cppp.tla`.
- Evidence: `artifacts/formal/Cppp.tla`, `artifacts/formal/tlc_*.log`,
  `artifacts/formal/cppp.py`,
  `artifacts/formal/trust_decay_verification.json`,
  `experiments/tests/test_formal.py`.

## 9. Discussion

- What the evidence supports: inline accuracy/FPR on named corpora under a
  stated calibration protocol; defensible feature drops; control-flow
  invariants; measured latency; ONNX parity.
- What it does not support: open-world generalisation, adversarial evasion,
  agent compromise, deployment-scale throughput, economic cost, universal
  feature directions.
- P2 collapse as evidence of endpoint confounding in CSIC.
- The negative screening result and the v4 inertness are treated as evidence
  standards, not failures to hide.
- Design implications: local calibration, safety-retained policy signals,
  CPPP as a promotion gate, latency budget as a selection constraint.

## 10. Limitations and threats to validity

- CSIC age and synthetic traffic; SR-BH attack-dominant; ECML age; WCP
  legitimate sample capped per site.
- Single-workstation measurements; Python service hop included; side effects
  excluded.
- Drop-rule conservatism (`token_count`).
- Screening budget (D6) and bounded permutation/SHAP (D7).
- D13 cross-fitted calibration is not fully nested; disclosed.
- CPPP models protocol control flow, not Byzantine agents.
- No federated deployment result; federated learning is future work.

## 11. Conclusion and future work

- NATRIX contributes an architecture plus an evidence standard, not a new
  classifier.
- v4 is a smaller audited contract, not a performance gain.
- Future work: federated learning across deployments (implemented last, not
  claimed here); header-coherence candidates deferred by D1; online canary
  calibration and drift monitoring; adaptive thresholds per endpoint.
- The isolated `federated/` directory contains a three-seed FedAvg emulation
  on CSIC with three endpoint-disjoint client shards. It is an engineering
  artifact only: it is not cited in the manuscript and changes no paper claim.
  Its README records the protocol, results, and the single-host limits.

## Back matter (unnumbered)

- Data availability, Code availability, Ethics statement, CRediT author
  statement, Declaration of competing interest, Funding, Acknowledgements.

## Appendices

- A. Feature-drop evidence: Table 14 (four-condition evidence), Table 15
  (univariate screen), Table 16 (multivariate and ablation evidence).
- B. Reproducibility: commands, environment (Python 3.11.8, Node 22.21.0,
  Pandoc 3.10, LaTeX not installed), artifact layout.
- C. TLA+ configuration: constants, invariants, TLC commands, log locations.

## Table map

| # | Include | Section | Content |
|---|---|---|---|
| 1 | `safety_features` | 5 | Safety-retained features and runtime role |
| 2 | `screening_results` | 5 | Pre-registered v4 candidate screen |
| 3 | `dataset_summary` | 6 | Corpora, deduplication, splits |
| 4 | `corpora_results` | 7.1 | In-distribution at 0.5 |
| 5 | `corpora_calibrated` | 7.1 | Cross-fitted corpus operating points |
| 6 | `v3_v4_results` | 7.2 | Nested v3 vs v4, three seeds |
| 7 | `calibrated_results` | 7.2 | Cross-fitted v3 vs v4 |
| 8 | `learner_results` | 7.3 | Secondary learners |
| 9 | `interpretability` | 7.4 | Permutation and SHAP |
| 10 | `cross_corpus_directions` | 7.5 | Direction replication |
| 11 | `transfer_results` | 7.5 | Source-only transfer |
| 12 | `latency_results` | 7.6 | End-to-end inline latency |
| 13 | `formal_verification` | 8 | TLC and trust-decay evidence |
| 14 | `drop_evidence` | A | Four-condition drop evidence |
| 15 | `drop_univariate` | A | Univariate screen |
| 16 | `drop_multivariate` | A | Multivariate and ablation evidence |

## Figure map

| # | File | Section | Content |
|---|---|---|---|
| 1 | `architecture.png` | 3 | Nine roles and synchronous/asynchronous split |
| 2 | `ablation_delta.png` | 5 | Leave-one-feature-out ablation |
| 3 | `v3_v4_roc_pr.png` | 7.2 | ROC and PR for v3/v4 |
| 4 | `threshold_tradeoff.png` | 7.2 | Operating-point trade-off |
| 5 | `feature_importance.png` | 7.4 | Permutation importance |
| 6 | `transfer_accuracy.png` | 7.5 | Cross-corpus transfer |
| 7 | `latency_ecdf.png` | 7.6 | Latency ECDF |

## Build and QA checklist

- Source: `paper/manuscript.md`; build: `python paper/build_manuscript.py`.
- Primary artifact: `paper/NATRIX_manuscript.docx` (A4, 2.54 cm margins,
  double-spaced, line numbers, Elsevier Vancouver numeric citations).
- Secondary artifact: `paper/NATRIX_manuscript.tex` (elsarticle, not compiled
  locally because LaTeX is not installed).
- Checks: 43 bibliography entries and all keys cited; 16 numbered table
  captions; 7 figure captions; no unresolved `[@` or `??`; table captions
  adjacent to tables; OMML math present; both authors present; back matter
  unnumbered; Appendix A–C present.
- Known display note: terminal cp1252 may show UTF-8 punctuation as `�`;
  the docx codepoints are correct.
