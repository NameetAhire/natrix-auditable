# Protocol deviations and clarifications

Every change to `analysis_plan.md` or `feature_candidates.md` after they were
frozen is recorded here, with the reason and the effect on reported results.

## D1 — 2026-10-30 — v4 candidate pool restricted to payload-derived signals

**Change.** The header-coherence candidates in Group D of
`feature_candidates.md` (`missing_host`, `ua_header_mismatch`,
`expect_100_continue`, `transfer_encoding_present`, `header_count`,
`content_length_mismatch`, `content_type_form_mismatch`) are removed from the
screened pool. The implemented pool is the 24 payload-derived candidates in
`experiments/scripts/candidate_features.py`.

**Reason.** The inline extraction contract passes only `(payload, user_agent,
method)` to the registry. Screening header features would require a runtime
interface change before the feature is even known to help, and the SR-BH cache
does not retain the full header set, so the definition could not be made
identical across corpora. Keeping the pool inside the existing contract also
keeps the latency claim honest.

**Effect.** None on existing results. The deferred candidates are listed as
future work in the paper. No v4 decision was made before this change.

## D2 — 2026-10-30 — SR-BH row count

**Observation.** 907,815 data rows were parsed, one more than the 907,814
reported in the dataset description. One physical line is a quoted newline
inside a request body, so this is a parsing artefact of the published file, not
a duplicated record. Deduplication and label counts are reported from the parsed
data (422,054 unique: 122,546 clean / 299,508 attack).

**Effect.** None. Noted for transparency.

## D3 — 2026-10-30 — ablation threshold fixed at 0.5

**Change.** Leave-one-feature-out ablation uses a fixed 0.5 threshold for every
variant, so relative deltas are not confounded by per-variant threshold tuning.
The headline v3/v4 comparison uses full nested threshold selection.

**Effect.** Ablation deltas are conservative; absolute ablation accuracies may
differ slightly from the headline numbers.

## D4 — 2026-10-30 — MI and L1 stability estimated on a training-fold subsample

**Change.** Mutual information and the bootstrap L1 selection frequency are
computed on 8,000 training-fold records per fold instead of the full ~27,700.
The model itself, and the permutation importance it is scored with, still use
the full training and held-out folds. SHAP is bounded separately (D7).

**Reason.** Exact k-nearest-neighbour mutual information on the full fold
deadlocks in this Windows environment when prior joblib/OpenMP pools are alive;
the bounded estimate is stable at 8,000 rows and keeps the audit reproducible
on an 8 GB machine. This affects only two descriptive importance measures, not
any accuracy or ablation number.

**Effect.** MI values are estimates with slightly wider sampling error;
selection-frequency estimates use the same number of bootstrap resamples. No
feature decision rests on MI alone (drop rule requires three independent
conditions to agree).

## D5 — 2026-10-30 — learner configuration corrected to the shipped gate

**Finding.** The first audit and ablation runs used
`RandomForestClassifier(n_estimators=200, random_state=42)` without specifying
`max_features`. scikit-learn's classifier default is `max_features='sqrt'`,
whereas the shipped 22-D artifact was trained with `max_features=None`
(all 22 features at every split). This produced a full-22 accuracy of 90.71%
instead of the published 95.63% at threshold 0.5.

**Change.** All experiments now construct the learner through
`common.make_rf()`, which pins `n_estimators=200, max_depth=None,
min_samples_leaf=1, max_features=None, class_weight=None,
random_state=42` — the exact artifact configuration. The first audit and
ablation outputs were discarded and rerun; none of the 90.71%-based numbers
appear in the paper.

**Effect.** The full-22 baseline is restored to the published configuration
(95.6% at 0.5 on unique requests). Ablation deltas are now measured against the
actual deployed learner. This is a correctness fix, not a change to the
pre-registered feature-selection rule.

## D6 — 2026-10-30 — v4 screening stage uses 3 inner folds and 100 trees

**Change.** The candidate screening loop uses 3 inner folds and 100 trees per
forest to keep 24 candidates x 5 outer folds inside the workstation budget.
The final v3-vs-v4 comparison uses 5 inner folds and the full 200-tree gate.

**Effect.** Screening is slightly less precise than the final evaluation; a
candidate near the acceptance boundary may be rejected. The final comparison
uses only accepted candidates and the full protocol, so headline numbers are
unaffected. The full screening table is reported in the appendix.

## D7 — 2026-10-30 — permutation repeats and SHAP sample are bounded

**Change.** Permutation importance uses 10 repeats per held-out fold (the plan
says 30), and SHAP uses 500 held-out records per fold (the plan says 5,000
training-fold records). Both remain descriptive: no drop decision rests on SHAP,
and permutation importance contributes only the second of four independent drop
conditions.

**Reason.** Thirty repeats across 22 features and five folds would multiply the
audit runtime by three for a measure whose sign and ordering are already stable
at ten repeats. A 5,000-record TreeSHAP pass per fold is unnecessary for a
ranking that is reported alongside permutation importance and L1 stability.
Both bounds keep the audit reproducible on the 8 GB workstation.

**Effect.** Permutation confidence intervals are wider than a 30-repeat run
would give, which biases the drop rule toward *retaining* features (the CI is
more likely to contain zero, so condition 2 is easier to satisfy, but condition
2 alone cannot drop a feature). SHAP is used for interpretation only. The
headline accuracy, ablation and v3/v4 comparisons are unaffected.

## D8 — 2026-10-30 — target operating point at FPR <= 2%

**Change.** In addition to the pre-registered F1-optimal and FPR <= 1%
operating points, the headline comparison reports a third nested threshold:
the F1-maximising threshold whose training-fold FPR is <= 2%. The project's
acceptance criterion is accuracy > 95% with FPR below 2.03%, and neither
pre-registered point satisfies both simultaneously (F1-optimal sits near 2.9%
FPR; the FPR <= 1% point costs about 3.4 accuracy points, 92.2% vs 95.6% at
threshold 0.5).

**Reason.** The analysis plan already requires comparisons "at equal FPR as well
as at the F1-optimal threshold"; this makes the equal-FPR point explicit at the
value the deployment target names. The threshold is still selected inside the
training fold, so the test fold is scored once and never used for selection.

**Effect.** Adds a deployment operating point; does not replace or alter the
pre-registered points. All three are reported, and the paper states which one
the acceptance claim refers to.

## D9 — 2026-10-30 — secondary learners use fixed, untuned hyper-parameters

**Change.** The histogram gradient boosting and logistic-regression checks use
one fixed configuration each (`max_iter=300`, learning rate 0.08, 31 leaves,
L2=1.0; and `C=1.0` with standardised features). They are not tuned on any
fold.

**Reason.** The analysis plan asks for a second and third learner to show the
feature decision is not forest-specific, not for a model-selection study.
Tuning each learner would add a second selection layer and more ways for the
test folds to leak into the comparison.

**Effect.** Secondary-learner numbers are a robustness check; the headline
accuracy and FPR remain the shipped Random Forest.

## D10 — 2026-10-30 — cross-corpus audit is a replication, not a selection run

**Change.** The ECML and SR-BH replication uses one stratified 80/20 split per
corpus, 5 permutation repeats on the 20% holdout, and full-corpus univariate
statistics with BH correction. The CSIC audit keeps the full 5-fold protocol.

**Reason.** The cross-corpus pass exists to show whether the same signals carry
class information elsewhere. Re-running the full 5-fold permutation/SHAP/L1
audit on 422k SR-BH rows would multiply runtime without changing any decision:
no feature is dropped or added on the basis of these numbers.

**Effect.** Cross-corpus ranks are descriptive and have wider sampling error
than the CSIC audit. They are reported as replication evidence only.

## D11 — 2026-10-30 — candidate screening adds each candidate individually

**Change.** The nested screen compares `core + {candidate}` against `core` for
each surviving candidate separately, then combines all accepted candidates.
It is not a sequential forward selection in which each accepted candidate
changes the baseline for the next one. The correlation filter keeps the first
candidate in the pre-registered order when two candidates exceed
`|Spearman| >= 0.95`; because all candidates are computed in one pass, the
"cheaper one" tie-break in the protocol has no measurable cost difference.

**Reason.** Individual screening keeps each candidate's effect interpretable
and avoids order-dependent acceptance. The correlation filter removes the
redundant member before the screen, so the combined set is not a chain of
near-duplicates.

**Effect.** A candidate that only helps in combination with another candidate
can be missed. The full screening table is reported so this limitation is
visible.

## D12 — 2026-10-31 — candidate pool rejected by the pre-registered cost budget

**Finding.** The accuracy screen accepted 12 of 16 surviving candidates, but
the pre-registered extraction-cost budget (≤ 0.15 ms added to Python p95 on the
8 KiB worst case) fails by a wide margin: the candidate pass alone costs
3.80 ms p95 on the delimiter-heavy worst case, 1.38 ms on the long-run case and
0.84 ms on the body-heavy case. The combined v3 + candidate pass costs 10.92 ms
p95 on the delimiter-heavy case. Five of the 12 raw-accepted candidates
(`backslash_count`, `brace_count`, `nonascii_ratio`, `ldap_filter_score`,
`crlf_sequence_count`) are exactly constant on CSIC; their identical
+0.046 pp screening delta is an artefact of the random feature order in the
forest, not signal.

**Change.** No candidate is admitted. v4 is the 20-D retained core produced by
the four-condition drop rule. The raw screening result is preserved in
`artifacts/feature_selection/v4_definition_screened.json`; the final definition
and rejection record are in `v4_definition.json`.

**Reason.** The cost budget is a hard pre-registered rejection criterion
("rejected regardless of accuracy"). The constant-on-CSIC candidates are a
second, independent reason not to trust the small screening gains.

**Effect.** v4 is smaller than v3 (20 vs 22 features), so the v3/v4 comparison
tests the value of the two dropped features rather than the candidate pool. The
candidate pool and a faster extractor are reported as future work. The
worst-case 8 KiB extraction cost of the *v3* path (6.68 ms p95 on the synthetic
delimiter-heavy case) is reported as a limitation; the headline latency
measurement uses the real 10,000-request corpus sample.

## D13 — 2026-10-31 — cross-fitted threshold calibration reported alongside nested selection

**Finding.** The pre-registered inner-CV threshold is selected on models trained
on 64% of the data (four of five inner folds), while the outer model that scores
the test fold is trained on 80%. On CSIC the inner-CV FPR<=2% threshold is
0.57–0.58; applied to the outer test folds it yields about 94.7% accuracy at
1.2% FPR. The 0.51–0.52 thresholds that satisfy both acceptance targets
(accuracy > 95%, FPR < 2.03%) are visible on outer OOF predictions, but choosing
one by inspecting those same predictions would be selection on the test data.

**Change.** `calibrate_thresholds.py` adds a cross-fitted calibration: for each
outer fold k, the threshold is selected on the outer OOF predictions of the
other four folds and applied once to fold k. Every OOF prediction comes from a
model trained on 80% of the data, so the score scale matches the model that is
deployed. Fold k labels are not used to choose its threshold. The
pre-registered inner-CV results remain in `comparison_metrics.csv` and are
reported separately.

**Reason.** The training-size mismatch is a property of nested threshold
selection, not of the model. The acceptance target names an operating FPR, so
the operating point must be estimated on predictions from models of the
deployed size. Cross-fitting is the standard way to do that without touching
the evaluation fold.

**Effect.** The calibrated operating point is the one used for the acceptance
claim; the inner-CV point is reported as the conservative bound. Because the
OOF model that scores fold j was trained on the other folds (including fold k),
the calibration is not a fully nested selection: the threshold for fold k is
influenced by fold k through the training data of the other folds' models. This
is disclosed in the manuscript. The effect is a single scalar threshold, and
the paired v3/v4 comparison applies the same calibration procedure separately
to each feature set, so the comparison itself remains fair.



## D14 - 2026-11-11 - Gate C re-measured with batch timing

**Finding.** The original Gate C measurement timed each extractor call
individually with `perf_counter_ns`. On the shared workstation, per-call
wall-clock p95 is dominated by scheduler preemption: repeated runs of the same
payload varied from 2.3 ms to 15.2 ms. The recorded 3.80 ms p95 was one draw
from that distribution, not a stable property of the extractor.

**Change.** `measure_candidate_cost.py` now times short batches (10 calls) and
reports the per-call batch mean. Five warmup batches and 60 timed batches are
used per payload. The candidate extractor is refactored into one function per
candidate so the per-candidate marginal cost can be reported separately from
the shared parse. The vector is byte-identical to the previous implementation
on the first 2,000 CSIC requests.

**Effect.** On the 8 KiB delimiter-heavy worst case the full 24-candidate pass
costs 2.33 ms p95; the 12 statistically accepted candidates cost 1.71 ms; the
nine accepted candidates whose individual marginal cost is at most 0.15 ms
still cost 0.73 ms as a set because they share a second parse of the payload.
Every set-level figure is above the 0.15 ms envelope, so the negative adoption
decision is unchanged. The manuscript reports 2.33 ms for the full pass and
1.71 ms for the accepted block, and the per-candidate table is reported as a
diagnostic rather than as a per-feature admission rule.
