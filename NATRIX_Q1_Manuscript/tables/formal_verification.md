# Formal verification evidence

| configuration | constants | states generated | distinct | depth | result |
|---|---|---:|---:|---:|---|
| one rule (`Cppp_small.cfg`) | `Agents=a1,a2,a3`, `Rules=r1`, `K=2`, `Tau=2`, `MaxTrust=3` | 459 | 150 | 11 | no error |
| two rules (`Cppp_two.cfg`) | same agents, `Rules=r1,r2` | 114,901 | 22,500 | 18 | no error |

Invariants: `TypeOK`, `NoPromotionWithoutCanary`,
`NoPromotionWithoutQuorum`, `NoPromotionWithoutTrust`,
`ActiveImpliesAudited`, `RetiredNotActive`, `NoDirectPromotion`.
Logs: `artifacts/formal/tlc_one_rule.log`,
`artifacts/formal/tlc_two_rules.log`.

| check | result |
|---|---|
| property tests (`experiments/tests/test_formal.py`) | 10 passed |
| exhaustive BFS, depth 9 | 13,278 reachable states, 62,263 transitions |
| BFS invariant violations | none |
| TLA+ mutation test | 6/6 mutants killed, all expected |

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
