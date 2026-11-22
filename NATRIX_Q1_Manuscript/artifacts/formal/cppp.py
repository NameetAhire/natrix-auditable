"""Reference implementation of the Candidate Policy Promotion Protocol (CPPP).

This is the executable counterpart of `Cppp.tla`.  The TLA+ model is checked by
TLC; this module is checked by property-based tests and by exhaustive
enumeration of bounded action sequences.  The two share the same state
variables and the same guards, so a passing model check and a passing test
suite support the same claim.

States
------
observed -> canary -> promoted -> retired
observed -> rejected          (explicit rejection)

Rules
-----
* any agent may add evidence (vote);
* trust may be seeded from a prior rule version or a reputation record without
  creating a vote, so quorum and trust are separate guards;
* a canary may start only with an independent quorum and trust >= tau;
* passing the canary requires at least ``canary_obs`` observations and zero
  benign hits; a hit is permanent, so the rule cannot be rescued by later
  clean traffic;
* only the policy agent can promote, and only after the canary passed,
  the quorum is still present, and trust >= tau;
* every promotion is written to the audit log;
* on every scheduler tick, trust decays by one level and a promoted rule whose
  trust would fall below tau is retired atomically, so no observable state has
  a promoted rule below tau.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class Lifecycle(str, Enum):
    OBSERVED = "observed"
    CANARY = "canary"
    PROMOTED = "promoted"
    RETIRED = "retired"
    REJECTED = "rejected"


class ProtocolError(RuntimeError):
    """Raised when an action is attempted that the protocol does not allow."""


@dataclass
class RuleState:
    state: Lifecycle = Lifecycle.OBSERVED
    votes: set[str] = field(default_factory=set)
    trust: int = 0
    canary_passed: bool = False
    canary_seen: int = 0
    canary_hit: bool = False
    promoted_tick: int | None = None
    retired_tick: int | None = None


class CPPP:
    """Concurrent candidate policy promotion, single policy agent."""

    def __init__(
        self,
        agents: Iterable[str],
        policy_agent: str,
        rules: Iterable[str],
        quorum: int,
        tau: int,
        max_trust: int,
        canary_obs: int,
    ) -> None:
        self.agents = frozenset(agents)
        self.policy_agent = policy_agent
        self.quorum = int(quorum)
        self.tau = int(tau)
        self.max_trust = int(max_trust)
        self.canary_obs = int(canary_obs)
        if self.policy_agent not in self.agents:
            raise ValueError("policy agent must be an agent")
        if self.quorum < 1 or self.quorum > len(self.agents):
            raise ValueError("quorum must be between 1 and the number of agents")
        if not (0 <= self.tau <= self.max_trust):
            raise ValueError("tau must lie in [0, max_trust]")
        if self.canary_obs < 1:
            raise ValueError("canary_obs must be at least one observation")
        self.rules: dict[str, RuleState] = {r: RuleState() for r in rules}
        self.audit: set[str] = set()
        self.tick_no = 0
        self.history: list[tuple[str, str | None]] = []

    # -- queries ---------------------------------------------------------
    @property
    def active_policy(self) -> set[str]:
        return {r for r, s in self.rules.items() if s.state is Lifecycle.PROMOTED}

    def _require_rule(self, rule: str) -> RuleState:
        if rule not in self.rules:
            raise ProtocolError(f"unknown rule {rule!r}")
        return self.rules[rule]

    # -- actions ---------------------------------------------------------
    def validate(self, agent: str, rule: str) -> None:
        rs = self._require_rule(rule)
        if agent not in self.agents:
            raise ProtocolError(f"unknown agent {agent!r}")
        if rs.state not in (Lifecycle.OBSERVED, Lifecycle.CANARY):
            raise ProtocolError(f"cannot validate a rule in state {rs.state.value}")
        rs.votes.add(agent)
        rs.trust = min(self.max_trust, rs.trust + 1)
        self.history.append(("validate", f"{agent}:{rule}"))

    def seed_trust(self, rule: str) -> None:
        """Seed trust from a prior version or reputation record, not a vote."""
        rs = self._require_rule(rule)
        if rs.state is not Lifecycle.OBSERVED:
            raise ProtocolError("trust may only be seeded on an observed rule")
        if rs.trust >= self.tau:
            raise ProtocolError("trust already at or above tau")
        rs.trust = self.tau
        self.history.append(("seed_trust", rule))

    def start_canary(self, rule: str) -> None:
        rs = self._require_rule(rule)
        if rs.state is not Lifecycle.OBSERVED:
            raise ProtocolError("canary may only start from observed")
        if len(rs.votes) < self.quorum:
            raise ProtocolError("quorum not reached")
        if rs.trust < self.tau:
            raise ProtocolError("trust below tau")
        rs.state = Lifecycle.CANARY
        self.history.append(("start_canary", rule))

    def observe_canary(self, rule: str, hit: bool) -> None:
        """Record one canary observation; ``hit`` means benign traffic fired."""
        rs = self._require_rule(rule)
        if rs.state is not Lifecycle.CANARY:
            raise ProtocolError("no canary is running")
        if rs.canary_seen >= self.canary_obs:
            raise ProtocolError("canary observation budget exhausted")
        rs.canary_seen += 1
        rs.canary_hit = rs.canary_hit or bool(hit)
        self.history.append(("observe_canary", f"{rule}:{'hit' if hit else 'clean'}"))

    def pass_canary(self, rule: str) -> None:
        rs = self._require_rule(rule)
        if rs.state is not Lifecycle.CANARY:
            raise ProtocolError("canary has not started")
        if len(rs.votes) < self.quorum:
            raise ProtocolError("quorum lost")
        if rs.trust < self.tau:
            raise ProtocolError("trust below tau")
        if rs.canary_seen < self.canary_obs:
            raise ProtocolError("insufficient canary observations")
        if rs.canary_hit:
            raise ProtocolError("canary observed a benign hit")
        rs.canary_passed = True
        self.history.append(("pass_canary", rule))

    def promote(self, agent: str, rule: str) -> None:
        rs = self._require_rule(rule)
        if agent != self.policy_agent:
            raise ProtocolError("only the policy agent may promote")
        if rs.state is not Lifecycle.CANARY:
            raise ProtocolError("promotion requires a canary")
        if not rs.canary_passed:
            raise ProtocolError("canary has not passed")
        if len(rs.votes) < self.quorum:
            raise ProtocolError("quorum lost")
        if rs.trust < self.tau:
            raise ProtocolError("trust below tau")
        rs.state = Lifecycle.PROMOTED
        rs.promoted_tick = self.tick_no
        self.audit.add(rule)
        self.history.append(("promote", f"{agent}:{rule}"))

    def retire(self, rule: str) -> None:
        rs = self._require_rule(rule)
        if rs.state not in (Lifecycle.CANARY, Lifecycle.PROMOTED):
            raise ProtocolError("only an active candidate can be retired")
        rs.state = Lifecycle.RETIRED
        rs.retired_tick = self.tick_no
        self.history.append(("retire", rule))

    def reject(self, rule: str) -> None:
        rs = self._require_rule(rule)
        if rs.state is not Lifecycle.OBSERVED:
            raise ProtocolError("only an observed candidate can be rejected")
        rs.state = Lifecycle.REJECTED
        self.history.append(("reject", rule))

    def tick(self) -> None:
        """One scheduler tick: decay, then atomic retirement below tau."""
        self.tick_no += 1
        for rule, rs in self.rules.items():
            if rs.state is Lifecycle.PROMOTED and rs.trust <= self.tau:
                # The rule is at or below the floor: decay to zero and retire
                # in the same atomic step (TLA+ Tick).
                rs.trust = 0
                rs.state = Lifecycle.RETIRED
                rs.retired_tick = self.tick_no
            elif rs.trust > 0:
                rs.trust -= 1
        self.history.append(("tick", str(self.tick_no)))

    # -- invariants ------------------------------------------------------
    def invariants(self) -> dict[str, bool]:
        rules = self.rules
        return {
            "NoPromotionWithoutCanary": all(
                s.state is not Lifecycle.PROMOTED or s.canary_passed for s in rules.values()
            ),
            "NoPromotionWithoutQuorum": all(
                s.state is not Lifecycle.PROMOTED or len(s.votes) >= self.quorum
                for s in rules.values()
            ),
            "NoPromotionWithoutTrust": all(
                s.state is not Lifecycle.PROMOTED or s.trust >= self.tau
                for s in rules.values()
            ),
            "NoPromotionWithoutObservations": all(
                s.state is not Lifecycle.PROMOTED or s.canary_seen >= self.canary_obs
                for s in rules.values()
            ),
            "NoPromotionWithCanaryHit": all(
                s.state is not Lifecycle.PROMOTED or not s.canary_hit
                for s in rules.values()
            ),
            "ActiveImpliesAudited": self.active_policy <= self.audit,
            "RetiredNotActive": all(
                s.state is not Lifecycle.RETIRED or r not in self.active_policy
                for r, s in rules.items()
            ),
            "NoDirectPromotion": all(
                r not in self.active_policy or rules[r].canary_passed
                for r in rules
            ),
            "TrustBounded": all(0 <= s.trust <= self.max_trust for s in rules.values()),
            "AuditMonotone": self.audit <= {r for r in rules},
        }

    def check(self) -> None:
        failed = [name for name, ok in self.invariants().items() if not ok]
        if failed:
            raise AssertionError(f"invariant violation: {failed}")

    # -- introspection ---------------------------------------------------
    def snapshot(self) -> dict:
        return {
            "tick": self.tick_no,
            "rules": {
                r: {
                    "state": s.state.value,
                    "votes": sorted(s.votes),
                    "trust": s.trust,
                    "canary_passed": s.canary_passed,
                    "canary_seen": s.canary_seen,
                    "canary_hit": s.canary_hit,
                }
                for r, s in self.rules.items()
            },
            "active": sorted(self.active_policy),
            "audit": sorted(self.audit),
        }
