# NATRIX Q1 — Pre-registered analysis plan

Status: **frozen before any v4 selection was run.**
Frozen on: 2026-10-30.
Any deviation must be recorded in `protocol/deviations.md` with the reason and the
effect on the reported numbers.

## 1. Questions

- **RQ1.** Which of the 22 v3 features carry measurable, non-redundant decision
  value for inline HTTP attack detection, and what is the evidence for each?
- **RQ2.** Can a statistically selected feature set (v4) match or beat v3 on
  accuracy and false-positive rate at lower or equal decision latency?
- **RQ3.** Does the NATRIX decision path generalise across independent HTTP
  corpora, and how large is the domain-shift penalty?
- **RQ4.** Do the trust-decay and CPPP mechanisms satisfy their stated safety
  invariants, and what are the measured promotion/rollback properties?

## 2. Data

| Corpus | Role | Labels used |
|---|---|---|
| CSIC 2010 | Primary benchmark, in-distribution | normal / anomalous |
| SR-BH 2020 | Independent modern corpus, in-distribution + transfer target | normal / anomalous (13 CAPEC labels retained for typing) |
| ECML/PKDD 2007 train | Classic benchmark, in-distribution + transfer target | Valid / Attack (7 attack types) |
| OpenAppSec WCP | Real-world legitimate traffic (FPR) + malicious payloads | legitimate / malicious |

Exclusions: DNS logs, Zeus PE JSON, incident text and unlabelled `http.log` are
never used for training or accuracy claims.

### 2.1 Leakage controls

1. Exact duplicates are removed before splitting. Duplicate keys are
   `(method, path, query, body, user_agent)`.
2. Records whose duplicate key appears with two different labels are dropped and
   counted.
3. Two split protocols are reported for every in-distribution result:
   - **P1 deployment-like**: stratified over unique requests. Same endpoints may
     appear in train and test, no identical request does.
   - **P2 endpoint-disjoint**: groups are
     `(method, normalised path, query keys, body keys)` and a group is wholly
     assigned to one fold.
4. P1 is the headline protocol because it matches how a WAF is operated and how
   the prior CSIC literature reports. P2 is reported as a generalisation bound
   and as evidence about endpoint confounding. **No result is reported from P2
   alone, and P1 is never described as unseen-endpoint performance.**
5. All selection, threshold tuning and calibration happen inside the training
   fold. Test folds are scored once.

## 3. Feature audit (RQ1)

Computed on CSIC unique records (P1 folds) and repeated on SR-BH and ECML.

Per feature:

- Distribution summary by class (median, IQR, zero fraction).
- Mann–Whitney U (continuous), chi-square (binary), with Benjamini–Hochberg
  correction across the 22 tests.
- Effect size: Cliff's delta and Cohen's d.
- Mutual information with the label (training folds only).
- Permutation importance on the held-out fold, 30 repeats.
- SHAP mean |value| on a stratified sample of 5,000 training-fold records.
- Variance inflation factor and Spearman correlation against the other 21.
- Bootstrap selection frequency (200 resamples) under L1-logistic selection.
- Leave-one-feature-out ablation: retrain without the feature, report
  Δaccuracy, ΔFPR, ΔFNR, ΔF1 and Δlatency with paired bootstrap CIs.

**Decision rule for dropping a feature.** A feature is dropped from v4 only if
all four hold:

1. BH-adjusted p ≥ 0.05 **and** |Cliff's delta| < 0.10, or it is near-constant
   (zero fraction ≥ 0.99 in both classes);
2. permutation importance is in the bottom quartile **and** its 95% CI contains 0;
3. LOO ablation shows no degradation larger than the smallest practically
   important effect (Δaccuracy ≤ 0.2 pp, ΔFPR ≤ 0.10 pp) with the CI excluding a
   harmful drop;
4. it is not a safety feature retained by design (documented exception list).

Every dropped feature gets a row in `artifacts/feature_selection/drop_evidence.csv`
and a short written justification in the Phase-2 appendix. Nothing is dropped
silently.

## 4. v4 candidate pool (RQ2)

Pre-registered in `protocol/feature_candidates.md`. Candidates come from the
literature survey and from the runtime's own observable request fields, not from
peeking at CSIC label correlations. Screening uses the same nested CV as the
audit. v4 is accepted only if it is non-inferior to v3 on accuracy (non-inferiority
margin 0.5 pp) and FPR, and no slower.

## 5. Model and evaluation

- Primary learner: Random Forest, 200 trees, `random_state=42`, matching the
  shipped gate. Secondary: histogram gradient boosting and regularised logistic
  regression, to show the feature set is not tuned to one learner.
- Outer 5-fold × 3 seeds; inner 5-fold for hyper-parameters and threshold.
- Threshold policy: maximise F1 inside the training fold; report a second
  operating point at FPR ≤ 1%.
- Metrics: accuracy, balanced accuracy, precision, recall, F1, FPR, FNR, ROC-AUC,
  PR-AUC. 95% bootstrap CIs (2,000 resamples), McNemar tests, BH correction.
- Comparisons are made at equal FPR as well as at the F1-optimal threshold.

## 6. Latency (RQ2, SLO)

The SLO is the **full inline decision**, p95 < 5 ms:

```
request -> Node extraction -> gate inference -> threat typing -> policy verdict
```

Measured on the real proxy with the real model artifacts, at least 10,000
requests, reported as p50/p95/p99 and throughput. Python HTTP round-trip is
measured separately and counted in the inline path unless the architecture is
changed and the change is documented.

## 7. Formal and empirical security properties (RQ4)

No simulation stands in for evidence.

- **Trust decay**: definitions and proofs (boundedness, monotone decay without
  evidence, recovery under positive evidence, half-life, convergence under
  stationary evidence) checked mechanically where the statement is finite, and
  by exhaustive enumeration over the discrete state space.
- **CPPP**: the automaton is implemented in code and model-checked in TLA+ with
  an explicit invariant set; the same invariants are asserted as property-based
  tests against the implementation. A claim appears in the paper only if the
  model checker or the property test actually passes.
- **Agent authority**: invariants encoded as executable tests against the real
  policy module.

## 8. Reporting rules

- Every number in the paper traces to a file under `experiments/results/`.
- Negative and null results are reported.
- No accuracy claim is made on unlabelled data.
- Cross-dataset transfer is reported separately from in-distribution accuracy.
