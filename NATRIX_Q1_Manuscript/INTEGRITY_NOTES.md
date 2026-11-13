# Integrity notes — numbers that must not enter the paper

## INT-1 — Phase 1 ablation and metrics CSVs are hardcoded, not measured

`Ai-Agent/experiments/run_ablation.py` does not run an experiment. It writes a
fixed table to `results/ablation.csv`:

```
"Full CPPP Framework (Proposed)", "99.20% ± 0.12%", ...
```

`Ai-Agent/experiments/results/metrics.csv` contains the same values as literals
(Accuracy 0.992, FPR 0.0008). Nothing in the repository produces them.

**Consequence.** The 99.20% accuracy / 0.08% FPR / 4.12 ms figures in the Phase 1
deck are not experimental results and must not appear in the manuscript, the
viva, or any submission.

**Real measured values** from the actual CSIC pipeline are:

| Metric | Measured |
|---|---|
| 22-D unique CV accuracy | 95.55% (95% CI 95.33–95.79) |
| FPR | 2.03% |
| FNR | 7.27% |
| External holdout accuracy | 95.38% |

**Action.** The manuscript's ablation study is rebuilt from real experiments in
`experiments/results/`. The old CSVs are left untouched (per project rule) but
are marked unusable here.

## INT-2 — CPPP and trust decay were described but not implemented

The Phase 1 deck presents CPPP, trust decay and authority separation as
components of NATRIX, but no implementation exists in `Ai-Agent/agents/` (only
two thin JS agents) and no verification exists.

**Action.** This project implements the state machine, trust model and invariant
checks for real, verifies them with TLA+ and property-based tests, and reports
only measured outcomes. The paper will not claim properties that were not
checked.

## INT-3 — first audit/ablation run used the wrong forest configuration

The first feature audit and leave-one-feature-out ablation omitted
`max_features=None`, so scikit-learn silently used `max_features='sqrt'` and
the full-22 baseline scored 90.71% instead of the published 95.63%. The
artifacts are pinned to `max_features=None`. The affected results were deleted
and rerun through `common.make_rf()`; no 90.71%-based number is used anywhere in
the manuscript.
