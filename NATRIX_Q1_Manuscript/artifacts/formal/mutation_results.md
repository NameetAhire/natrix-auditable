# TLA+ mutation test

Each mutant removes one guard from the checked-in `Cppp.tla`. A mutant is
killed when TLC reports the expected invariant violation.

| mutant | expected invariant | killed | violated |
|---|---|:--:|---|
| `no_quorum` | `NoPromotionWithoutQuorum` | yes | NoPromotionWithoutQuorum |
| `no_canary` | `NoPromotionWithoutCanary` | yes | NoPromotionWithoutCanary |
| `no_trust` | `NoPromotionWithoutTrust` | yes | NoPromotionWithoutTrust |
| `no_audit` | `ActiveImpliesAudited` | yes | ActiveImpliesAudited |
| `direct_promote` | `NoDirectPromotion` | yes | NoDirectPromotion |
| `retired_active` | `RetiredNotActive` | yes | RetiredNotActive |
| `canary_hit` | `NoPromotionWithCanaryHit` | yes | NoPromotionWithCanaryHit |
| `no_observations` | `NoPromotionWithoutObservations` | yes | NoPromotionWithoutObservations |

Killed 8/8 mutants; all expected: True.
