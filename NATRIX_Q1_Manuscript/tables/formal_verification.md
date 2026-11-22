# Formal verification evidence

| configuration | constants | states generated | distinct | depth | result |
|---|---|---:|---:|---:|---|
| one rule (`Cppp_small.cfg`) | `Agents=a1,a2,a3`, `Rules=r1`, `K=2`, `Tau=2`, `MaxTrust=3`, `CanaryObs=2` | 939 | 278 | 12 | no error |
| two rules (`Cppp_two.cfg`) | same agents, `Rules=r1,r2` | 444,245 | 77,284 | 23 | no error |

Invariants: `TypeOK`, `NoPromotionWithoutCanary`,
`NoPromotionWithoutQuorum`, `NoPromotionWithoutTrust`,
`NoPromotionWithoutObservations`, `NoPromotionWithCanaryHit`,
`ActiveImpliesAudited`, `RetiredNotActive`, `NoDirectPromotion`.
Logs: `artifacts/formal/tlc_one_rule.log`,
`artifacts/formal/tlc_two_rules.log`.

| check | result |
|---|---|
| property tests (`experiments/tests/test_formal.py`) | 13 passed |
| exhaustive BFS, depth 9 | 20,678 reachable states, 97,870 transitions |
| BFS invariant violations | none |
| TLA+ mutation test | 8/8 mutants killed, all expected |

| trust-decay check | result |
|---|---|
| exhaustive rational enumeration | 81,484 cases, 0 violations |
| symbolic identities (SymPy) | 9/9 pass |

Identities: initial value, limit at infinity, monotone decreasing,
bounded above, half-life, recovery non-decreasing, recovery upper
bound, gap contraction, contraction identity. Source:
`artifacts/formal/trust_decay_verification.json`,
`artifacts/formal/trust_decay.py`.

## Mutation test

| mutant | expected invariant | killed |
|---|---|:--:|
| `no_quorum` | `NoPromotionWithoutQuorum` | yes |
| `no_canary` | `NoPromotionWithoutCanary` | yes |
| `no_trust` | `NoPromotionWithoutTrust` | yes |
| `no_audit` | `ActiveImpliesAudited` | yes |
| `direct_promote` | `NoDirectPromotion` | yes |
| `retired_active` | `RetiredNotActive` | yes |
| `canary_hit` | `NoPromotionWithCanaryHit` | yes |
| `no_observations` | `NoPromotionWithoutObservations` | yes |

## Sidecar

| check | result |
|---|---|
| audit records | 916, hash chain verified |
| promotions matched by retirements | 108 / 108 (8 automatic) |
| runtime invariants | 8/8 hold |
| promotion p95, no fsync / fsync | 5.15 ms / 53.57 ms |
| retirement p95, no fsync / fsync | 4.76 ms / 48.04 ms |
| full cycle p95 | 33.75 ms |
| validate p95 / p99, 32 parallel rules | 45.82 ms / 522.41 ms |
