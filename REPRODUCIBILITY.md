# Reproducibility guide

This document describes how the offline-corpus results in the manuscript were
produced, how to regenerate them, and what cannot be reproduced from this
package. It is written for a reader who has the package but not the original
authoring workspace.

## 1. Scope and status

The evidence is from four public, labelled HTTP corpora, local replay, and a fixed-probe audit of the deployed gateway. There is no shadow-mode observation window and no live adversary. The package reproduces the **offline evaluation** and the **fixed-probe deployment audit**, not a generalisation estimate.

The submission version is the Elsevier manuscript for the *Journal of
Information Security and Applications*:
`paper/manuscript_jisa.md` -> `paper/NATRIX_jisa.pdf`. The earlier
`paper/manuscript_short.md` -> `paper/NATRIX_manuscript_short.pdf` build is the
retired *Computers & Security* variant and is kept only for history.

## 2. Reference environment

The measured numbers were produced on:

| Component | Value |
|---|---|
| Operating system | Windows 11 Home Single Language (build 10.0.26200) |
| CPU | AMD Ryzen 5 4600H with Radeon Graphics |
| RAM | 7.37 GB usable |
| Python | 3.11.8 |
| Node.js | 22.21.0 |
| Pandoc | 3.10 (via `pypandoc`) |
| Tectonic | 0.17.0 |
| Java | Temurin 17.0.20.1 (for TLA+) |
| PyTorch | 2.9.1+cpu |
| ONNX Runtime | 1.31.1 |

`requirements.txt` pins the Python packages used for the reported results.
Timings are machine-specific. The latency section reports the observed
distribution on this machine; a different CPU, Python build, ONNX Runtime
version, or background load will move the percentiles. Accuracy and FPR should
be stable to rounding, but exact tree-model probabilities can differ slightly
across library versions.

## 3. Package layout

```text
NATRIX_reproducibility_v1.0.3/
  README.md
  REPRODUCIBILITY.md
  MANIFEST.md
  MANIFEST.csv
  SHA256SUMS.txt
  CITATION.cff
  requirements.txt
  LICENSE.md
  NATRIX_Q1_Manuscript/
    experiments/scripts/        evaluation and table/figure code
    experiments/tests/          formal-model tests
    experiments/results/        measured outputs (no parquet caches)
    experiments/run_all.ps1     main queue
    protocol/                   frozen plan, candidates, deviations
    tables/                     generated tables
    figures/                    generated figures
    artifacts/formal/           TLA+ model, mutants, Python models
    artifacts/models/           ONNX gate and typing models
    artifacts/feature_selection/ frozen v4 definitions
    paper/                      manuscript sources and compiled PDFs
    data/                       provenance only (no raw corpora)
  Ai-Agent/
    ml_engine/feature_registry.py
    ml_engine/csic_evaluation.py
    ml_engine/model_service.py
    proxy/feature_extractor.js
    models/feature_schema.json
    models/metadata.json
    models/v2.0/threat_classifier.joblib
    models/v2.0/anomaly_detector.joblib
```

`experiments/scripts/common.py` resolves `ROOT` as
`NATRIX_Q1_Manuscript/` and imports the production modules from
`../Ai-Agent/ml_engine/`. Keep the two top-level directories as siblings.

## 4. Data

Raw corpora are **not** redistributed. Download them from the sources recorded
in `NATRIX_Q1_Manuscript/data/README.md` and verify the SHA-256 values in
`NATRIX_Q1_Manuscript/data/manifest.json`.

| Corpus | Role | Unique requests used | Source |
|---|---|---:|---|
| CSIC 2010 | Primary in-distribution benchmark | 34,593 (18,640 clean / 15,953 attack) | GitHub mirror `msudol/Web-Application-Attack-Datasets`; original ISI CSIC page is unreachable |
| ECML/PKDD 2007 | Classic in-distribution and transfer target | 50,116 (35,006 clean / 15,110 attack) | Same mirror, `OriginalDataSets/ecml_pkdd/` |
| SR-BH 2020 | Modern in-distribution and transfer target | 422,054 (122,546 clean / 299,508 attack) | Harvard Dataverse, doi:10.7910/DVN/OGOIXX |
| OpenAppSec WCP 2024 | Diagnostic only: endpoint-matched FPR and robustness | 137,820 legitimate + 73,924 malicious payloads | `openappsec/waf-comparison-project` |

The expected local paths are:

```text
data/raw/csic/mirror/cisc_normalTraffic_train.txt
data/raw/csic/mirror/cisc_normalTraffic_test.txt
data/raw/csic/mirror/cisc_anomalousTraffic_test.txt
data/raw/ecml/extracted/xml_train.txt
data/raw/ecml/extracted/xml_test.txt
data/raw/srbh/srbh_2020.csv
data/raw/openappsec/...
```

Deduplication is exact on `(method, path, query, body, user_agent)`; records
whose duplicate key appears with two labels are removed and counted. The
counts in the manuscript are the post-deduplication counts.

WCP is never used for training or threshold selection. Every malicious WCP row
has path `/`, so a random split leaks the endpoint; WCP is reported only as a
diagnostic.

## 5. Splits and operating points

- **P1 (deployment-like).** Stratified five-fold over unique requests. No
  identical request crosses the split, but the same endpoint may appear in
  training and test. This matches a WAF that already knows the endpoint.
- **P2 (endpoint-disjoint).** Groups are
  `(method, normalised path, sorted query parameter names, sorted body
  parameter names)`. A group is wholly assigned to one fold, so the test
  endpoint is unseen.
- **P2 path-only sensitivity.** Groups are `(method, normalised path)` only.
  This is stricter. On CSIC the grouping is degenerate: ten normalised paths
  carry 93% of requests, fold sizes range from 668 to 14,087, and prevalence
  ranges from 0.43 to 0.98. CSIC path-only detector numbers are reported for
  completeness but are **not** used to rank detectors. ECML and SR-BH path-only
  splits are balanced; their ranking is unchanged.
- **Threshold policy.** All score-based detectors use leave-one-fold-out
  thresholds at FPR <= 2%. The threshold for each outer fold is selected on the
  out-of-fold predictions of the other folds. CRS is a frozen replay and is not
  tuned to the 2% budget.
- **Seeds.** Fold seed 42. The v3/v4 comparison uses seeds 42, 123 and 2026.
  The char-CNN uses seed 42 and the same folds.
- **Nested policy.** The v3/v4 table also reports a fully nested threshold
  policy; it reaches 94.67% and misses the 95% target. This is a negative
  result and is reported as such.

## 6. Experiment sequence

All commands are run from `NATRIX_Q1_Manuscript/` after activating the Python
environment. PowerShell is assumed; on Linux or macOS run the same commands
individually.

### 6.1 Main queue

```powershell
.\experiments\run_all.ps1
```

The queue runs, in order:

1. `audit_univariate.py`, `audit_model.py` - C1/C2 statistics.
2. `evaluate_featuresets.py --out ablation_csic` - leave-one-feature-out
   ablation at a fixed 0.5 threshold.
3. `merge_drop_evidence.py`, `write_drop_appendix.py` - merge the drop
   evidence.
4. `screen_candidates.py` - v4 candidate screening.
5. `measure_candidate_cost.py`, `finalize_v4.py` - Gate C costs and v4
   definition.
6. `compare_v3_v4.py`, `calibrate_thresholds.py` - headline v3/v4 comparison
   and nested threshold sensitivity.
7. `evaluate_corpora.py --corpora csic ecml srbh --protocols P1 P2` -
   in-distribution P1/P2 at threshold 0.5.
8. `calibrate_corpora.py` - cross-fitted FPR <= 2% policy.
9. `evaluate_transfer.py` - cross-corpus transfer and WCP family recall.
10. `audit_shap.py` - SHAP audit.
11. `evaluate_learners.py` - secondary learners.
12. `audit_cross_corpus.py` - cross-corpus feature-direction replication.
13. `pytest experiments/tests/test_formal.py -v` - CPPP and trust-decay
    properties.
14. `node experiments/scripts/latency_bench.js` - end-to-end latency; the ONNX
    service must be running on port 5001.
15. `make_result_tables.py` - result tables.
16. `make_figures.py`, `make_architecture_figure.py` - figures.

### 6.2 Additional runs not in the main queue

These produce the Gate C, positive-control, grouping-sensitivity, scale,
control/stacker and independent-learner evidence.

```powershell
# Gate C: per-candidate costs and the set-level budget
python experiments\scripts\measure_candidate_cost.py
python experiments\scripts\make_candidate_cost_table.py

# v3-D positive control: split into value and path blocks, then apply Gate B/C
python experiments\scripts\measure_v3d_cost.py
python experiments\scripts\gate_v3d.py
python experiments\scripts\make_v3d_gate_table.py

# P2 path-only grouping sensitivity
python experiments\scripts\p2_path_only.py --corpus csic --views full payload
python experiments\scripts\p2_path_only.py --corpus ecml --views full payload
python experiments\scripts\p2_path_only.py --corpus srbh20k --views full payload
python experiments\scripts\finalize_p2_path_only.py
python experiments\scripts\make_p2_path_only_table.py

# SR-BH full-versus-20k scale sensitivity
python experiments\scripts\srbh_sample_gap.py

# Generic control and stackers
python experiments\scripts\control_stack.py --corpus csic --protocol P1 --lexical-view full
python experiments\scripts\control_stack.py --corpus csic --protocol P2 --lexical-view full
python experiments\scripts\control_stack.py --corpus csic --protocol P2 --lexical-view payload
python experiments\scripts\control_stack.py --corpus srbh20k --protocol P2 --lexical-view full
python experiments\scripts\control_stack.py --corpus srbh20k --protocol P2 --lexical-view payload
python experiments\scripts\control_stack.py --corpus ecml --protocol P2 --lexical-view full
python experiments\scripts\control_stack.py --corpus ecml --protocol P2 --lexical-view payload

# Independent char-CNN, seven settings
python experiments\scripts\learned_detector.py --corpus csic --protocol P1 --views full payload
python experiments\scripts\learned_detector.py --corpus csic --protocol P2 --views full payload
python experiments\scripts\learned_detector.py --corpus srbh20k --protocol P1 --views full payload
python experiments\scripts\learned_detector.py --corpus srbh20k --protocol P2 --views full payload

# Short-version Table 4 (adds the eight char-CNN rows)
python experiments\scripts\make_short_detector_table.py

# Revision tables and figures
python experiments\scripts\make_revision_tables.py
python experiments\scripts\make_revision_figures.py
```

The char-CNN runs are CPU-only and take roughly one hour in total on the
reference machine. They write `experiments/results/baselines/learned_*.json`
and `*_oof.npz`.

### 6.3 CRS replay

CRS is replayed through the official `owasp/modsecurity-crs` 4.25.2 nginx
image, with the inbound anomaly threshold at 5, request-body inspection on, and
response-body inspection off. The origin returns HTTP 200 for every request, so
a 403 is the WAF decision. The exact image digest used for the reported run
should be recorded before re-running; the checked-in JSON files identify the
engine and paranoia level but not the digest.

```powershell
# Start the CRS reverse proxy on host port 8088.
docker run --rm -d --name natrix-crs -p 8088:8080 `
  -e PARANOIA=1 -e ANOMALY_INBOUND=5 owasp/modsecurity-crs:4.25.2-nginx

python experiments\scripts\crs_baseline.py --corpus csic --paranoia-level 1 --tag crs_pl1 --workers 24
python experiments\scripts\crs_baseline.py --corpus csic --paranoia-level 2 --tag crs_pl2 --workers 24
python experiments\scripts\crs_baseline.py --corpus csic --paranoia-level 3 --tag crs_pl3 --workers 24
python experiments\scripts\crs_baseline.py --corpus ecml --paranoia-level 1 --tag crs_pl1 --workers 24
python experiments\scripts\crs_baseline.py --corpus srbh --paranoia-level 1 --tag crs_pl1 --workers 24
python experiments\scripts\crs_baseline.py --corpus wcp --paranoia-level 1 --tag crs_pl1 --workers 24

docker stop natrix-crs
```

The reported CRS table uses **decisions only**: statuses 400, 405, 413 and 414
are nginx rejections that occur before ModSecurity evaluates the request and are
reported as non-decisions. `crs_decisions.py` recomputes the decision-only
confusion matrix from the replay parquet.

### 6.4 Latency benchmark

```powershell
# Build the frozen 10,000-request input sample (5,000 CSIC, 3,000 ECML,
# 2,000 WCP) from the raw corpora.
python experiments\scripts\make_latency_input.py

# Start the ONNX serving adapter.
python experiments\scripts\serve_gate.py --port 5001

# In another terminal:
node experiments\scripts\latency_bench.js `
  experiments\results\latency\latency_inputs.json `
  experiments\results\latency\latency_report.json
```

The harness measures the real Node extraction path, the HTTP hop, and ONNX
inference. The reported p95 is 3.78 ms and p99 is 5.69 ms over 9,700 measured
requests after 300 warm-up requests. A p95 is not a hard bound; the 8 KiB
adversarial extraction case is a tail stress test at 6.68 ms p95, not the
admission measurement.

The public `latency_inputs.json` is sanitized by
`experiments/scripts/redact.py`: credential-like URL, form and JSON values are
replaced with same-length `~` placeholders. Request count, structure and field
lengths are preserved; the reported timings were measured on the original
corpus.

### 6.5 Formal verification

The Python property and exhaustive tests do not need Java:

```powershell
python -m pytest experiments\tests\test_formal.py -v
```

The TLA+ mutation test needs Java 17 and `tla2tools.jar`. The script expects
`tools/tla2tools.jar` and a JRE under `tools/jre17/` relative to
`NATRIX_Q1_Manuscript/`; those binaries are not in this package.

```powershell
# Download TLA+ tools and a Java 17 runtime, then:
python artifacts\formal\mutation_test.py
```

The checked-in `artifacts/formal/mutation_results.json` and
`mutation_results.md` record 8/8 mutants killed. The Python trust-decay
verification covers 81,484 exact-rational cases.

### 6.6 Deployment audit

The fixed-probe audit reads the deployed gateway through its public route. It is
a policy check, not a load test and not shadow-mode observation.

```powershell
python experiments\scripts\live_attack_suite.py `
  --url https://natrix-security-engine.onrender.com/p/nameetahire-vercel-app `
  --out experiments\results\live_gate\live_suite_run1
# repeat with run2 and run3
python experiments\scripts\aggregate_live_suite.py
```

The per-run files are `results/live_gate/live_suite_run{1,2,3}.json`, the pooled
confusion matrix is `results/live_gate/aggregate.json`, and the raw gate ledger
is `results/live_gate/gate_decisions_export.jsonl` (95 decisions, 2026-11-15 to
2026-11-16 UTC). `experiments/scripts/deployment_boundary.py` replays
`gateHasLexicalSignal` offline and writes
`results/deployment_boundary/deployment_boundary.json`, the source for Table 13.

### 6.7 Manuscript build

```powershell
python paper\build_manuscript.py --source paper\manuscript_short.md `
  --stem NATRIX_manuscript_short --template paper\elsarticle_template.tex
tectonic -X compile paper\NATRIX_manuscript_short.tex
```

`build_manuscript.py` resolves `{{table:name}}` directives from `tables/` and
citations from `paper/refs.bib`. The compiled PDF is included under `paper/`.

## 7. Claim-to-artifact map

Table numbers refer to the 41-page Elsevier version.

| Manuscript item | Generator | Primary inputs |
|---|---|---|
| Table 1, Gate C per-candidate cost | `make_candidate_cost_table.py` | `results/latency/candidate_cost.json`, `results/v4_screening/candidate_screening.csv` |
| Table 2, v3-D positive control | `make_v3d_gate_table.py` | `results/feature_audit/v3d_path_gate.json`, `v3d_path_gate.csv`, `results/latency/v3d_cost.json` |
| Table 3, corpora and splits | static compact derivative of `dataset_summary.md`, from `data/README.md` and `data/manifest.json` | `data/manifest.json` |
| Table 4, matched operating points | `make_revision_tables.py` + `make_short_detector_table.py` | `results/corpora/corpora_calibrated.csv`, `results/baselines/*.json`, `results/baselines/learned_*.json` |
| Table 5, view ablation | `make_revision_tables.py` | `results/baselines/natrix_views_*.json` |
| Table 6, generic control and stackers | `make_revision_tables.py` | `results/baselines/control_*.json` |
| Table 7, P2 path-only sensitivity | `make_p2_path_only_table.py` | `results/baselines/p2_path_only_*.json` |
| Table 8, SR-BH scale sensitivity | `make_revision_tables.py` | `results/corpora/srbh_sample_gap.json` |
| Table 9, v3 versus v4 | `make_result_tables.py` | `results/v3_v4/comparison_metrics.csv`, `comparison_summary.json` |
| Table 10, inline latency | `make_result_tables.py` | `results/latency/latency_report.json` |
| Table 11, CRS paranoia levels | `make_revision_tables.py` | `results/baselines/crs_pl{1,2,3}_csic.json` |
| Table 12, dilution-resistant variant | `make_revision_tables.py` | `results/adversarial/dilution_resistant.json` |
| Table 13, deployed enforcement boundary | `deployment_boundary.py` | `results/deployment_boundary/deployment_boundary.json` |
| Live probe suite (Section 9) | `live_suite.py` + `aggregate_live_suite.py` | `results/live_gate/live_suite_run{1,2,3}.json`, `aggregate.json`, `gate_decisions_export.jsonl` |
| Figure 1, architecture | `make_architecture_figure.py` | static |
| Figure 2, protocol sensitivity | `make_revision_figures.py` | `tables/detector_comparison.md` |
| Figure 3, view ablation | `make_revision_figures.py` | `tables/view_ablation.md` |
| Figure 4, SR-BH learning curve | `make_revision_figures.py` | `tables/srbh_sample_gap.md` |
| Figure 5, latency ECDF | `make_figures.py` | `results/latency/latency_report.json` |

Key result files:

- `results/corpora/corpora_calibrated.csv` - NATRIX P1/P2 at the cross-fitted
  FPR <= 2% policy.
- `results/baselines/lexical_*.json` - lexical full, payload and endpoint
  views.
- `results/baselines/learned_*.json` - independent char-CNN, seven settings.
- `results/baselines/control_*.json` - generic LightGBM and stackers.
- `results/baselines/crs_pl*.json` - CRS replay.
- `results/baselines/p2_path_only_*.json` - path-only grouping sensitivity.
- `results/feature_audit/v3d_path_gate.json` - Gate B/C decisions for the four
  path features.
- `results/adversarial/dilution_resistant.json` - bounded and targeted
  dilution.
- `results/latency/latency_report.json` - end-to-end latency.
- `results/latency/candidate_cost.json` - per-candidate Gate C costs.
- `results/latency/v3d_cost.json` - v3-D block costs.

## 8. What is excluded and why

| Excluded path | Reason | How to regenerate |
|---|---|---|
| `data/raw/**`, `data/processed/**` | Raw corpora are third-party data with their own licences; redistribution is not assumed | Download from `data/README.md` |
| `experiments/results/**/*.parquet` | Request-level caches contain raw request text; large | `crs_baseline.py`, `crs_decisions.py` |
| `experiments/results/nj*.npy` | Stray numerical-Jacobian intermediates not used by any manuscript table | Re-run the relevant audit if needed |
| `tools/**` | Tectonic, JRE and `tla2tools.jar` are third-party binaries, not authored here | Install Tectonic; install Java 17 and TLA+ tools |
| `backups/**`, `states/**`, `.hypothesis/**`, `.pytest_cache/**` | Editor/agent state and caches | None |
| `paper/build/**`, `paper/*.docx`, `paper/*.log`, `paper/*.blg` | Generated build intermediates | `build_manuscript.py` |
| `paper/manuscript.md`, `paper/manuscript_revision.md` | Earlier manuscript drafts, superseded by `paper/manuscript_short.md` | Archived in `paper/_archive/2026-11-17/` |
| `artifacts/formal/**/*.st`, `*.fp`, `*.log`, `*TTrace*.tla` | TLC state dumps and trace files | Re-run TLC |
| `submission/dist/**` | The archive itself | `make_package.py` |

The `.npz` out-of-fold prediction files are included. They are small enough to
ship and are needed to recompute paired tests and figures without re-training.

## 9. Determinism, seeds and known variability

- Fold generation uses seed 42. The v3/v4 comparison uses 42, 123 and 2026.
- The char-CNN uses seed 42, a 32-dimensional byte embedding, two convolutional
  layers, max-pooling, five epochs, and the same leave-one-fold-out FPR <= 2%
  calibration.
- The lexical baseline is a hashed character 2--4 gram representation
  (2^18 dimensions, L2-normalised) with an L2-regularised logistic-loss SGD
  classifier at alpha = 1e-5, 30 epochs, and averaging.
- The generic control is a 17-feature LightGBM over request-shape descriptors
  with no security keywords and no NATRIX feature.
- The stackers are cross-fitted logistic combinations of out-of-fold scores.
- TLA+ model checking is exhaustive within the small configuration; the
  Python trust-decay check is exhaustive over the recorded grid.
- Exact float values can move in the last digit across BLAS, LightGBM, PyTorch
  or ONNX Runtime versions. The manuscript reports two decimal places for
  percentages and four for F1; differences at that scale are not claimed to be
  meaningful.

## 10. Integrity and protocol deviations

`protocol/analysis_plan.md` was frozen before any v4 selection. Every change
after freezing is recorded in `protocol/deviations.md` (D1--D14), including:

- D1: header-coherence candidates deferred; the pool is payload-derived.
- D2: SR-BH has 907,815 parsed rows, one more than the published count, due to
  a quoted newline inside a request body.
- D3: ablation uses a fixed 0.5 threshold.
- D4: MI and L1 stability use an 8,000-row training-fold subsample.
- D5: the learner configuration was corrected to the shipped gate
  (`max_features=None`).
- D8 and D13 were added after the initial freeze: D8 fixes the FPR <= 2%
  operating point; D13 adds cross-fitted threshold calibration alongside nested
  selection. The manuscript states this explicitly.
- D14 re-measured Gate C with batch timing.

`INTEGRITY_NOTES.md` records numbers that must not enter the paper. In
particular, the Phase 1 values 99.20% accuracy, 0.08% FPR and 4.12 ms are
hardcoded artefacts, not measurements, and are not used. The manuscript's
measured values are 95.55% CSIC P1 accuracy, 1.93% FPR, and 3.78 ms p95.

## 11. Release checklist

- [x] Set the public repository URL in `CITATION.cff` and in both manuscripts.
- [x] Set the licence: MIT for authored code; CC BY 4.0 for documentation,
      tables, figures and manuscript source.
- [x] Publish the Zenodo deposit and cite the concept DOI
      (10.5281/zenodo.24435601) in the manuscript and \CITATION.cff\.
- [ ] Confirm the author list, affiliations and corresponding author.
- [ ] Confirm that the raw-corpus licences permit the intended redistribution
      (the package does not redistribute them).
- [ ] Record the CRS image digest used for the reported replay.
- [x] Rebuild the archive with `python submission/make_package.py`.
- [x] Verify `SHA256SUMS.txt` and the archive size.
- [x] Push the repository and confirm that the manuscript URL resolves before
      submission.
- [x] Do not submit a conference version while the *Journal of Information
      Security and Applications* submission is active; the IEEE build is
      archived and withdrawn.
