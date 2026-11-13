# Reviewer-response matrix

Status: working document, 2026-11-05.  This is the experiment plan that turns
the review into evidence.  It is deliberately separate from the manuscript:
nothing here is a claim until the artifact exists under `experiments/results/`.

The reviewer's summary is accepted: the current paper is strong on
reproducibility and honesty, and weak on novelty, baselines, deployment
evidence, and the gap between the nine-role diagram and what was measured.
The response is therefore not "add more discussion"; it is a set of
falsifiable experiments and, where an experiment cannot be run, an explicit
scope reduction.

## 1. Matrix

| # | Reviewer weakness | Why it matters | Experiment / change | Artifact | Status |
|---|---|---|---|---|---|
| R1 | Headline contribution is a null result; v4 equals v3 because the dropped features are constant on CSIC. | A four-condition rule that removes constants is ceremony, and dropping on CSIC alone may be unsafe elsewhere. | (a) Report v4 as an audit artifact, not an accuracy gain. (b) Measure v3 vs v4 on ECML and SR-BH, where `html_tag_density` is not constant. (c) Report the dropped-feature distribution per corpus. | `experiments/results/v3_v4/corpora_v3_v4.*` | Done: ECML null; SR-BH +0.009 pp, negligible |
| R2 | The 95% target looks tuned; the FPR<=2% policy was added post hoc. | The favourable number is not the pre-registered one. | (a) Make the fully nested result the primary endpoint and state that it misses 95%. (b) Keep cross-fitted calibration as a labelled sensitivity analysis. (c) Compare all methods at matched FPR, not at a post-hoc accuracy target. | `paper/manuscript.md`; baseline CSVs | Evidence done; manuscript rewrite pending |
| R3 | CSIC 2010 is artifact-laden; the P1/P2 gap suggests endpoint priors. | The headline may measure endpoint memorisation. | (a) Add an endpoint-only lexical baseline (method + path, no query/body). (b) Add a payload-only baseline. (c) Keep P2 as the generalisation bound. (d) Add a post-2020 labelled corpus. | `experiments/results/baselines/lexical_*_endpoint.json`; `wcp_endpoint_subset.*` | Done: endpoint prior small on CSIC/ECML; WCP is endpoint-confounded and reported as a limitation |
| R4 | Transfer AUCs are below chance; the model may not learn attacks at all. | The negative result needs a mechanism, not only a number. | (a) Harmonise ECML and SR-BH attack families to a common ontology. (b) Recompute direction with family-balanced weights. (c) Test within-family sign replication. (d) Report whether reversal survives. | `experiments/results/feature_audit/label_harmonisation.*` | Done: 13/9 overall, 12/10 family-balanced |
| R5 | "Multi-agent" is thin: only the ML gate is evaluated. | The title promises nine roles; the evidence covers one. | (a) Evaluate gate + a real signature/TI channel (ModSecurity CRS decisions) as an ensemble. (b) Measure the delta over gate-only at matched FPR. (c) Report the remaining roles as specified-but-not-evaluated, or implement one more role. | `experiments/results/baselines/fusion_*` | Done: CRS adds little at 2% FPR |
| R6 | CPPP is not in the running proxy; the verified model is small. | Formal verification of an undeployed protocol is weak systems evidence. | (a) Implement CPPP as a sidecar with the same transition relation. (b) Measure promotion/rollback latency and audit-record completeness. (c) Do not claim the shipped proxy uses CPPP until it does. | `experiments/scripts/cppp_sidecar.*` | Done: 700 records, chain OK, 108/108 |
| R7 | No ModSecurity/CRS baseline and no published ML baseline. | "95.55%" has no reference point. | (a) Replay all corpora through the official OWASP CRS nginx image at PL1 and PL2. (b) Add a standard char n-gram linear learner. (c) Report accuracy, FPR, recall, F1, and latency under the same deduplication and P1 folds. | `experiments/results/baselines/crs_pl1_*`; `lexical_*_full` | Done: CRS CSIC/ECML/SR-BH; WCP endpoint subset pending CRS; published-model citation pending |
| R8 | ONNX parity excludes the JavaScript extractor. | The deployed extractor is the untested part. | Cross-language parity on 2,000 class-balanced CSIC/ECML requests, all 22 features, exact comparison. | `experiments/results/parity/extractor_parity.json` | Done: 2,000/2,000 exact, max delta 0.0 |
| R9 | Title/abstract overclaim a "verified multi-agent detection architecture". | The evidence supports an auditable selection/promotion protocol, not universal detection. | Retitle and rewrite the abstract after the evidence is stable. Candidate: "NATRIX: An Auditable Feature-Selection and Promotion Protocol for Inline HTTP Attack Detection". | `paper/manuscript.md` | Planned |
| R10 | No adversarial evaluation. | A WAF that only sees its training distribution is not deployment evidence. | Add a bounded evasion check on real payloads: encoding/case/comment mutations applied to held-out attacks, with the same mutation budget for NATRIX and CRS. Report the recall drop; do not claim robustness beyond the tested transformations. | `experiments/results/adversarial/` | Done: NATRIX evasion 17.86% of blocked; CRS 2.94%; complementary weak spots |

## 2. Baseline protocol (frozen before the baseline numbers are inspected)

The baseline comparison uses the same deduplicated records and the same P1
folds as the NATRIX headline.  No baseline is tuned on the test fold.

### ModSecurity CRS

- Engine: official `owasp/modsecurity-crs` 4.25.2 nginx image.
- Configuration: default CRS, paranoia level 1, inbound anomaly threshold 5,
  request-body inspection on, response-body inspection off.
- Origin: a local server that returns 200 for every request, so a 403 is the
  WAF decision.
- Replay: the original method, path, query, body, user agent and content type
  are sent as HTTP; no NATRIX feature extraction is involved.
- Decision: 403 = block; 200 = allow.  Other statuses are recorded separately.
- Secondary operating points: paranoia level 2 and anomaly thresholds 10/20,
  to show the recall/FPR trade-off rather than a single point.

### Lexical linear baseline

- Representation: hashed character 2-4 grams (`char_wb`, 2^18 dimensions,
  L2-normalised).
- Learner: logistic-loss SGD, L2, fixed alpha, 30 epochs, no hyper-parameter
  search.
- Views: `endpoint` (method + path only), `payload` (query + body only),
  `full` (path + query + body).
- Protocol: the same 5-fold P1 split; threshold 0.5 and a leave-one-fold-out
  FPR<=2% threshold.

### Fusion

The gate + CRS fusion is a deterministic OR: block when the gate probability is
at its calibrated threshold or CRS returns 403.  This is the architecture's
Threat Intelligence/signature channel, not an external IP-reputation feed.
The comparison reports the change in recall and FPR over gate-only at the same
gate threshold.  A second, more conservative rule (gate AND CRS) is reported as
a precision-oriented point.

## 3. Evidence log (2026-11-04)

Every number below is in `experiments/results/`; this section is a reading aid,
not a second results file.

### 3.1 Baselines at a 2% FPR budget

Cross-fitted thresholds, same rows and folds.  The lexical baseline is a hashed
character 2-4 gram SGD over the full request (`path query body`).  SR-BH uses
the 20,000-request stratified sample that the CRS and lexical replays share.

| Corpus | Detector | Accuracy | FPR | Recall | F1 |
|---|---|---:|---:|---:|---:|
| CSIC | NATRIX v3 | 95.55% | 1.93% | 92.60% | 95.05% |
| CSIC | lexical full | 96.57% | 1.96% | 94.84% | 96.22% |
| CSIC | CRS PL1 | 66.24% | 0.03% | 26.84% | 42.30% |
| ECML | NATRIX v3 | 91.96% | 1.67% | 77.19% | 85.27% |
| ECML | lexical full | 93.93% | 0.43% | 80.85% | 88.93% |
| ECML | CRS PL1 (decisions only) | 78.64% | 20.13% | 75.70% | 67.52% |
| SR-BH 20k | NATRIX v3 | 90.79% | 1.96% | 87.83% | 93.12% |
| SR-BH 20k | lexical full | 95.41% | 1.98% | 94.34% | 96.68% |
| SR-BH 20k | CRS PL1 (decisions only) | 44.29% | 25.80% | 32.00% | 44.88% |
| WCP 20k | NATRIX v3 | 99.79% | 0.11% | 99.58% | 99.69% |
| WCP 20k | lexical full | 99.97% | 0.01% | 99.91% | 99.95% |
| WCP 20k | CRS PL1 (decisions only) | 91.75% | 6.66% | 88.80% | 88.30% |

WCP is endpoint-confounded: every malicious row has path `/`, so the
random-split rows are a sanity check, not a generalisation claim.  Section 3.6
reports the endpoint-matched subset instead.

CRS is a single frozen operating point, not a detector tuned to a 2% FPR
budget.  On ECML, 583 of 50,116 requests (1.16%) were rejected by nginx with
HTTP 400 before ModSecurity evaluated them; on SR-BH, 377 (1.89%) were 400 and
24 (0.12%) were 405 (TRACE).  The table excludes those non-decisions.  Counting
edge rejections as blocks raises ECML recall to 76.64% at the same 20.13% FPR
and SR-BH recall to 33.45% at 27.04% FPR.  The full-set conservative treatment
(only 403 is a block) is in `crs_decisions_*.json`.

The lexical baseline wins at the 2% operating point on all four corpora.  On
CSIC the ROC curves cross: NATRIX catches up at a 5% FPR budget (95.69% vs
95.79% recall), so the honest statement is "competitive at loose FPR, behind at
the deployment-relevant 2% point", not "better".  CRS is not competitive at
this FPR budget on any corpus: it is precise but low-recall on CSIC, and
high-recall but far above the FPR budget on ECML and SR-BH.

The prior-work FPR of roughly 3.45% is below both NATRIX and the lexical
baseline at their 2% operating points, but the protocols differ.  The paper
must not present this as a like-for-like win.

### 3.2 Fusion

CRS + gate on CSIC (OR): 14 extra attacks caught (recall +0.09 pp) for 6 extra
clean false positives (FPR +0.03 pp).  The CRS true positives are almost a
subset of the gate's, so the signature channel is redundant on this corpus.
AND fusion is much worse (recall 26.75%).

The picture is worse on the other corpora.  On ECML, OR adds 1,483 attacks
(recall +9.81 pp) but also 6,835 clean false positives (FPR +19.53 pp); AND
keeps FPR at 0.61% but drops recall to 62.96%.  On SR-BH 20k, OR adds 653
attacks (+4.60 pp recall) for 1,463 clean false positives (+25.19 pp FPR); AND
drops recall to 26.71% at 0.17% FPR.  On WCP 20k, OR adds 22 attacks
(+0.32 pp recall) for 860 clean false positives (+6.61 pp FPR); AND drops
recall to 88.48% at 0.01% FPR.  At a 2% FPR budget the signature channel is
therefore not a useful second agent: it either adds almost nothing (CSIC) or
buys recall at three to twenty-five times the FPR budget.  This is a negative
result for the gate + TI claim and is reported as such.

A two-score stacker (NATRIX + lexical, cross-fitted) is the positive result:

| Corpus | Accuracy | FPR | Recall | F1 |
|---|---:|---:|---:|---:|
| CSIC | 98.45% | 1.24% | 98.08% | 98.31% |
| ECML | 94.04% | 0.34% | 81.02% | 89.13% |
| SR-BH 20k | 96.81% | 1.98% | 96.31% | 97.72% |
| WCP 20k | 99.95% | 0.05% | 99.94% | 99.93% |

On WCP the stacker is not better than the lexical baseline alone (accuracy
-0.015 pp, McNemar p=0.581); the corpus is too easy for fusion to add
anything.  This is offline headroom, not a deployed agent.  The cross-fitted stacker has
the D13 leakage caveat, so the CSIC result was repeated with a fully nested
protocol: outer 5-fold, inner 4-fold base out-of-fold scores, stacker and
threshold fitted only inside the outer training folds.  The nested result is
98.24% accuracy, 1.32% FPR, 97.72% recall, F1 98.08, i.e. the gain survives
nesting almost intact (cross-fitted: 98.45% / 1.24% / 98.08%).  The SR-BH and
ECML stacker numbers remain cross-fitted only.

### 3.3 CPPP sidecar

The TLA+ transition relation is implemented behind HTTP with a hash-chained,
fsync'ed audit log.  100 promotion/rollback cycles plus a 32-rule concurrent
burst produced 700 records, no chain error, 108 promotions and 108 retirements,
and all six invariants true.

| Path | p50 | p95 |
|---|---:|---:|
| promote, no fsync | 2.42 ms | 3.63 ms |
| rollback, no fsync | 2.28 ms | 3.33 ms |
| promote, fsync | 32.20 ms | 34.18 ms |
| rollback, fsync | 32.19 ms | 34.44 ms |

The fsync numbers are the durable-audit cost on this host; the no-fsync numbers
are the protocol cost.  Report both, and do not call the sidecar "deployed in
the proxy".

### 3.4 Adversarial check

Bounded mutations (at most three applicable operators, 90.0% of attacks
covered) on CSIC attacks, same mutated request for both detectors.  NATRIX
recall falls from 92.60% to 82.47%; 17.86% of originally blocked attacks are
evaded.  Dilution (appending an ignored benign parameter) is the main driver
(-11.27 pp); double encoding costs -2.86 pp; case changes and SQL comments are
neutral on this set.  This is a real weakness of aggregate ratio features and
must be reported as such.

The same 15,953 mutated requests were replayed through CRS PL1.  CRS recall
falls from 26.84% to 26.05% (-0.79 pp); only 2.94% of attacks that CRS blocked
before mutation are evaded.  That is much more robust than NATRIX, but it
starts from a far lower recall: the absolute number of detected attacks falls
by 126 (4,281 to 4,155), while NATRIX loses 2,639.  The operator breakdown
shows a genuine complementarity: dilution costs NATRIX 11.27 pp but CRS only
0.84 pp, and double encoding costs NATRIX 2.86 pp but CRS 0.82 pp.  In the
other direction, SQL-comment insertion evades 44 of 44 originally blocked CRS
attacks in that small subgroup (n=72; CRS recall 61.11% -> 0%) while NATRIX is
unaffected, and case changes cost CRS 4.51 pp but NATRIX 0.64 pp.  CRS is
harder to evade per blocked attack, NATRIX detects far more attacks before and
after mutation, and each is weak where the other is strong.  Neither dominates;
the paper must report both axes.

### 3.5 Other completed evidence

- Extractor parity: 2,000 class-balanced CSIC/ECML cases, 22 features, max
  absolute delta 0.0, zero mismatches.
- v3 vs v4 on ECML: accuracy delta -0.006 pp at 0.5 (McNemar p=0.836) and
  +0.016 pp at the 2% FPR point (p=0.516).  v4 is an audit artifact.
- v3 vs v4 on full SR-BH (422,054 rows): v4 is +0.009 pp at 0.5 (95.997% vs
  95.988%, p=0.039) and +0.009 pp at the 2% FPR point (95.705% vs 95.696%,
  p=0.048).  The direction is opposite to the old CSIC claim and the effect
  size is negligible; report v4 as an audit/parsimony artifact, not as an
  accuracy gain.
- Label harmonisation ECML vs SR-BH: 13 same / 9 reversed overall, 12 / 10
  family-balanced; within SQLi 14 / 8, traversal 11 / 11, cmdi 12 / 10.  The
  reversal is not merely attack-family composition.
- Endpoint-only lexical baseline: CSIC 60.85% accuracy, 0.15% FPR, 15.28%
  recall; ECML 72.17%, 1.31% FPR, 10.72% recall.  The headline is not an
  endpoint prior.
- CSIC lexical payload baseline: 96.26% accuracy, 0.75% FPR, 92.77% recall at
  0.5; 96.90% / 1.88% / 95.47% at the 2% point.

### 3.6 Newer corpus: WCP 2024

The OpenAppSec WCP corpus is the newest labelled HTTP set used here: 137,820
legitimate requests from 692 sites and 73,924 malicious requests across seven
families.  On the shared 20k stratified sample, NATRIX reaches 99.785%
accuracy at 0.5 (0.138% FPR, 99.64% recall) and the lexical full-request
baseline reaches 99.97% (0% FPR, 99.91% recall).  The stacker does not improve
on the lexical baseline (accuracy -0.015 pp, p=0.581).

That near-ceiling result is not a detector achievement.  Every malicious
request in the corpus has path `/`; the 137,820 legitimate requests span
thousands of paths.  An endpoint-only lexical model therefore reaches 100%
recall at 1.31% FPR on the 20k sample: it learns that `/` is malicious.  The
random-split WCP number is endpoint-confounded and must not be reported as a
payload-detection result.

Restricting to requests whose path is exactly `/` leaves 170 clean and 6,982
attack rows in the sample.  In that endpoint-matched subset, path is constant,
so any separation comes from method, query, body, and headers.  NATRIX at 0.5
reaches 99.65% accuracy, 0% FPR (0/170; Wilson 95% upper bound 2.21%), 99.64%
recall; lexical full reaches 99.92%, 0% FPR, 99.91% recall.  The endpoint-only
model collapses (all 170 clean rows blocked).  This shows the full-request
models are not using the endpoint alone, but the payloads are still easy and
the clean subset is small.  WCP is reported as an out-of-corpus sanity check
and a dataset-limitation example, not as a generalisation claim.

CRS on the full 20k sample reaches 91.75% accuracy, 6.66% FPR, 88.80% recall,
F1 88.30 (77 HTTP 400 and 4 HTTP 414 are nginx non-decisions).  On the
endpoint-matched subset it reaches 88.49% accuracy, 24.12% FPR (41/170),
88.80% recall.  Gate+CRS OR adds 22 attacks for 860 clean false positives
(+6.61 pp FPR), the same unfavourable trade seen on ECML and SR-BH.  CRS is
better on WCP than on ECML/SR-BH, but still not usable at a 2% FPR budget.
Per-family CRS recall is 99.93% XSS, 71.07% traversal, 85.14% SQLi, 97.93%
command execution; the remaining families have fewer than 20 sampled rows.
NATRIX misses 4 of 16 log4shell rows in this sample, which the lexical
baseline catches; the sample is too small to treat that as a stable family
effect.

### 3.7 Still running / pending

- 583 ECML and 377 SR-BH requests remain HTTP 400 after re-encoding; they are
  malformed or traversal paths that nginx rejects before ModSecurity.  They
  are reported as non-decisions, not as CRS allows or blocks.
- 24 SR-BH requests use TRACE and receive 405 from nginx; also non-decisions.
- 77 WCP requests remain HTTP 400 and 4 are HTTP 414 (URI too long); also
  nginx non-decisions.
- A specific published ML baseline citation still has to be fixed.  The
  lexical baseline is a standard hashed character n-gram learner, not a
  reproduction of a named system.

## 4. What the response will not do

- It will not claim that CSIC, ECML, SR-BH, or WCP is a real production
  network.
- It will not report the random-split WCP result as a payload-detection or
  generalisation result; every WCP attack shares path `/`.
- It will not call a local replay a "real-network deployment".
- It will not tune a baseline on the test fold or choose a baseline
  configuration after seeing its test score.
- It will not present the cross-fitted threshold as fully nested.
- It will not claim CPPP is deployed until the sidecar is actually running and
  measured.
- It will not use the fabricated 99.20%/0.08%/4.12 ms figures from the old
  `NATRIX_MASTER_RESEARCH_PAPER_V3.docx`.

## 5. Real-network validation: scope decision

A true live-network shadow deployment needs a host, a protected application,
traffic, and an approval to observe it.  That is an operational task, not an
offline experiment.  The minimum credible version is:

1. A canary host running the NATRIX proxy in shadow mode in front of a
   non-production web application.
2. A labelled window of real requests from that host, or an agreed replay of
   production access logs with labels supplied by the application owner.
3. A pre-registered observation window, a data-retention rule, and an
   incident/rollback procedure.
4. The same metrics as the offline evaluation, reported separately and not
   pooled with the corpus numbers.

Without those four items the paper must say "offline corpora only" and treat
the live test as future work.  This is a scope decision for the authors, not
something the code can decide.

## 6. Newer dataset: adopted with a caveat

WCP 2024 (OpenAppSec WAF Comparison Project) is adopted as the post-2020
corpus.  It has 137,820 legitimate requests from 692 sites and 73,924 labelled
malicious requests across seven families.  Provenance and raw request text are
available, and the unit of analysis matches NATRIX.

The caveat is structural: every malicious request is stored with path `/`,
while legitimate traffic spans thousands of endpoints.  The random-split
result is therefore endpoint-confounded, and the endpoint-only lexical model
exploits it.  The paper will report the endpoint-matched subset (`path == /`)
as the WCP result and state that WCP cannot test site- or endpoint-disjoint
generalisation.  It will not present the random-split WCP number as a payload
detection result.

A flow-level corpus such as CIC-IDS2017 is still excluded: it changes the unit
of analysis and cannot be compared with NATRIX's payload features.
