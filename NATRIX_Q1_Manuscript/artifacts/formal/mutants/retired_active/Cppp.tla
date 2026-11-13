---------------------------- MODULE Cppp ----------------------------
\* Candidate Policy Promotion Protocol.
\*
\* Models the concurrent behaviour of an agent mesh: any agent may validate a
\* candidate rule, only the policy agent may promote, trust decays on every
\* scheduler tick, and a promoted rule whose trust falls below Tau is retired in
\* the same tick (so a promoted rule is never observably under-trusted).
\*
\* TLC exhaustively explores every interleaving.  The invariants below are the
\* properties claimed in the paper.

EXTENDS Naturals, FiniteSets, TLC

CONSTANTS Agents, PolicyAgent, Rules, K, Tau, MaxTrust

VARIABLES state, votes, trust, canaryPassed, activePolicy, audit

vars == <<state, votes, trust, canaryPassed, activePolicy, audit>>

Lifecycle == {"observed", "canary", "promoted", "retired", "rejected"}

TypeOK ==
  /\ state \in [Rules -> Lifecycle]
  /\ votes \in [Rules -> SUBSET Agents]
  /\ trust \in [Rules -> 0..MaxTrust]
  /\ canaryPassed \in [Rules -> BOOLEAN]
  /\ activePolicy \subseteq Rules
  /\ audit \subseteq Rules

Init ==
  /\ state = [r \in Rules |-> "observed"]
  /\ votes = [r \in Rules |-> {}]
  /\ trust = [r \in Rules |-> 0]
  /\ canaryPassed = [r \in Rules |-> FALSE]
  /\ activePolicy = {}
  /\ audit = {}

\* Any agent may contribute evidence.  Duplicate votes from the same agent do
\* not increase the quorum because votes are a set.
Validate(a, r) ==
  /\ a \in Agents
  /\ r \in Rules
  /\ state[r] \in {"observed", "canary"}
  /\ votes' = [votes EXCEPT ![r] = @ \cup {a}]
  /\ trust' = [trust EXCEPT ![r] = IF @ < MaxTrust THEN @ + 1 ELSE @]
  /\ UNCHANGED <<state, canaryPassed, activePolicy, audit>>

\* Trust is a property of the rule, not a function of the current vote count.
\* A rule can inherit trust from a prior version or from an operator's
\* reputation record.  Seeding trust does not create a vote, which is why the
\* quorum guard below is a separate condition rather than a corollary of trust.
SeedTrust(r) ==
  /\ state[r] = "observed"
  /\ trust[r] < Tau
  /\ trust' = [trust EXCEPT ![r] = Tau]
  /\ UNCHANGED <<state, votes, canaryPassed, activePolicy, audit>>

\* Canary may start only with an independent quorum and sufficient trust.
StartCanary(r) ==
  /\ state[r] = "observed"
  /\ Cardinality(votes[r]) >= K
  /\ trust[r] >= Tau
  /\ state' = [state EXCEPT ![r] = "canary"]
  /\ UNCHANGED <<votes, trust, canaryPassed, activePolicy, audit>>

PassCanary(r) ==
  /\ state[r] = "canary"
  /\ Cardinality(votes[r]) >= K
  /\ trust[r] >= Tau
  /\ canaryPassed' = [canaryPassed EXCEPT ![r] = TRUE]
  /\ UNCHANGED <<state, votes, trust, activePolicy, audit>>

\* Only the policy agent holds the write capability.
Promote(a, r) ==
  /\ a = PolicyAgent
  /\ state[r] = "canary"
  /\ canaryPassed[r]
  /\ Cardinality(votes[r]) >= K
  /\ trust[r] >= Tau
  /\ state' = [state EXCEPT ![r] = "promoted"]
  /\ activePolicy' = activePolicy \cup {r}
  /\ audit' = audit \cup {r}
  /\ UNCHANGED <<votes, trust, canaryPassed>>

Retire(r) ==
  /\ state[r] \in {"canary", "promoted"}
  /\ state' = [state EXCEPT ![r] = "retired"]
  /\ activePolicy' = activePolicy
  /\ UNCHANGED <<votes, trust, canaryPassed, audit>>

Reject(r) ==
  /\ state[r] = "observed"
  /\ state' = [state EXCEPT ![r] = "rejected"]
  /\ UNCHANGED <<votes, trust, canaryPassed, activePolicy, audit>>

\* One scheduler tick: trust decays by one level, and any promoted rule that
\* falls below Tau is retired atomically, so no reachable state exposes a
\* promoted rule with trust < Tau.
Tick ==
  /\ trust' = [r \in Rules |->
        IF state[r] = "promoted" /\ trust[r] <= Tau
        THEN 0
        ELSE IF trust[r] > 0 THEN trust[r] - 1 ELSE 0]
  /\ state' = [r \in Rules |->
        IF state[r] = "promoted" /\ trust[r] <= Tau
        THEN "retired"
        ELSE state[r]]
  /\ activePolicy' = {r \in activePolicy : ~(state[r] = "promoted" /\ trust[r] <= Tau)}
  /\ UNCHANGED <<votes, canaryPassed, audit>>

Next ==
  \/ \E a \in Agents, r \in Rules : Validate(a, r)
  \/ \E a \in Agents, r \in Rules : Promote(a, r)
  \/ \E r \in Rules : SeedTrust(r) \/ StartCanary(r) \/ PassCanary(r) \/ Retire(r) \/ Reject(r)
  \/ Tick

Spec == Init /\ [][Next]_vars

\* ------------------------------------------------------------------
\* Safety properties
\* ------------------------------------------------------------------

NoPromotionWithoutCanary ==
  \A r \in Rules : state[r] = "promoted" => canaryPassed[r]

NoPromotionWithoutQuorum ==
  \A r \in Rules : state[r] = "promoted" => Cardinality(votes[r]) >= K

NoPromotionWithoutTrust ==
  \A r \in Rules : state[r] = "promoted" => trust[r] >= Tau

ActiveImpliesAudited ==
  activePolicy \subseteq audit

RetiredNotActive ==
  \A r \in Rules : state[r] = "retired" => r \notin activePolicy

\* A rule that never entered canary cannot be active.
NoDirectPromotion ==
  \A r \in Rules : r \in activePolicy => canaryPassed[r]

=============================================================================
