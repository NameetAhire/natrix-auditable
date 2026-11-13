# Runtime promotion path and the gap that CPPP closes

This note records what the shipped proxy actually does, so the manuscript does
not describe a protocol that is not there.

## Observed promotion path

`Ai-Agent/proxy/server.js`, `learnSignature()`:

- a new signature is inserted with `status = 'candidate'` and `hitCount = 1`;
- on the next observation `hitCount` is incremented;
- the candidate is promoted to `status = 'active'` when
  `hitCount >= 2` **or** the source string contains `PCAP` or `Dataset`;
- promotion writes an evolution-log entry and increments a generation counter;
- there is no canary stage, no independent-agent quorum, no trust value, and no
  automatic decay;
- rollback exists only as the manual endpoint `POST /api/agent-rollback`.

The `PCAP`/`Dataset` disjunct is a direct-promotion shortcut: a single
observation from an import path is enough to activate a rule. That is precisely
the transition CPPP forbids.

## What CPPP adds

1. **Quorum.** A candidate can start a canary only after at least `K`
   independent agents have voted for it. Repeated votes from the same agent do
   not count twice.
2. **Canary.** Promotion requires a canary stage that passes. There is no direct
   `observed -> promoted` transition.
3. **Authority.** Only the policy agent may promote. Other agents may submit
   evidence, but cannot activate a rule.
4. **Trust floor and decay.** Every scheduler tick decays trust; a promoted rule
   whose trust reaches the floor is retired atomically, so no observable state
   contains a promoted rule below `tau`. Reactivation requires the full
   quorum/canary path again.
5. **Audit.** Every promotion is written to the audit log, and the invariant
   `ActiveImpliesAudited` is checked.

## Evidence status

- `artifacts/formal/Cppp.tla` is model-checked by TLC; the two-rule
  configuration generated 104,245 states (21,316 distinct) with no invariant
  violation.
- `artifacts/formal/cppp.py` is an executable reference implementation of the
  same transition relation.
- `experiments/tests/test_formal.py` checks the invariants by property-based
  testing and by breadth-first enumeration of bounded reachable states.

The shipped JavaScript path is the integration point, not a verified
implementation of CPPP. The manuscript therefore describes CPPP as the proposed
policy lifecycle, reports the verified reference implementation and model, and
lists the replacement of the `hitCount >= 2` / import-shortcut path as the
deployment step. No claim is made that the current proxy already enforces the
CPPP invariants.
