"""Property-based and exhaustive tests for CPPP and trust decay.

Run:  python -m pytest experiments/tests/test_formal.py -q
"""

from __future__ import annotations

import sys
from collections import deque
from fractions import Fraction
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

FORMAL = Path(__file__).resolve().parents[2] / "artifacts" / "formal"
sys.path.insert(0, str(FORMAL))

import cppp as cppp_mod  # noqa: E402
import trust_decay as td  # noqa: E402
from cppp import CPPP, Lifecycle, ProtocolError  # noqa: E402

AGENTS = ("a1", "a2", "a3")
POLICY = "a1"
RULES = ("r1", "r2")
QUORUM = 2
TAU = 2
MAX_TRUST = 3
CANARY_OBS = 2


def fresh() -> CPPP:
    return CPPP(AGENTS, POLICY, RULES, QUORUM, TAU, MAX_TRUST, CANARY_OBS)


def apply_action(system: CPPP, action) -> bool:
    kind = action[0]
    try:
        if kind == "validate":
            system.validate(action[1], action[2])
        elif kind == "seed":
            system.seed_trust(action[1])
        elif kind == "start":
            system.start_canary(action[1])
        elif kind == "observe":
            system.observe_canary(action[1], action[2])
        elif kind == "pass":
            system.pass_canary(action[1])
        elif kind == "promote":
            system.promote(action[1], action[2])
        elif kind == "retire":
            system.retire(action[1])
        elif kind == "reject":
            system.reject(action[1])
        elif kind == "tick":
            system.tick()
        else:  # pragma: no cover - guarded by the strategy
            raise AssertionError(kind)
        return True
    except ProtocolError:
        return False


ACTIONS = (
    [("validate", a, r) for a in AGENTS for r in RULES]
    + [("seed", r) for r in RULES]
    + [("start", r) for r in RULES]
    + [("observe", r, hit) for r in RULES for hit in (False, True)]
    + [("pass", r) for r in RULES]
    + [("promote", a, r) for a in AGENTS for r in RULES]
    + [("retire", r) for r in RULES]
    + [("reject", r) for r in RULES]
    + [("tick",)]
)


@settings(max_examples=400, deadline=None)
@given(st.lists(st.sampled_from(ACTIONS), max_size=40))
def test_invariants_hold_after_every_action(actions):
    system = fresh()
    system.check()
    for action in actions:
        apply_action(system, action)
        system.check()


@settings(max_examples=200, deadline=None)
@given(st.lists(st.sampled_from(ACTIONS), max_size=25))
def test_promotion_requires_policy_agent(actions):
    system = fresh()
    for action in actions:
        before = set(system.active_policy)
        apply_action(system, action)
        if action[0] == "promote" and action[1] != POLICY:
            assert set(system.active_policy) == before


def _key(system: CPPP):
    return (
        tuple(
            sorted(
                (
                    rule,
                    state.state.value,
                    tuple(sorted(state.votes)),
                    state.trust,
                    state.canary_passed,
                    state.canary_seen,
                    state.canary_hit,
                )
                for rule, state in system.rules.items()
            )
        ),
        tuple(sorted(system.audit)),
        tuple(sorted(system.active_policy)),
    )


def test_exhaustive_bounded_reachability():
    """Breadth-first enumeration of every reachable state up to depth 9."""
    start = fresh()
    start.check()
    seen = {_key(start)}
    frontier = deque([(start, 0)])
    states = 1
    transitions = 0
    while frontier:
        system, depth = frontier.popleft()
        if depth >= 9:
            continue
        for action in ACTIONS:
            clone = fresh()
            clone.__dict__.update(
                {
                    "rules": {
                        r: cppp_mod.RuleState(
                            state=s.state,
                            votes=set(s.votes),
                            trust=s.trust,
                            canary_passed=s.canary_passed,
                            canary_seen=s.canary_seen,
                            canary_hit=s.canary_hit,
                            promoted_tick=s.promoted_tick,
                            retired_tick=s.retired_tick,
                        )
                        for r, s in system.rules.items()
                    },
                    "audit": set(system.audit),
                    "tick_no": system.tick_no,
                    "history": list(system.history),
                }
            )
            before = _key(clone)
            if not apply_action(clone, action):
                continue
            transitions += 1
            clone.check()
            key = _key(clone)
            if key not in seen:
                seen.add(key)
                states += 1
                frontier.append((clone, depth + 1))
    assert states > 100, f"reachable state space suspiciously small: {states}"
    print(f"reachable states={states} transitions={transitions}")


def test_atomic_retirement():
    system = fresh()
    for agent in ("a1", "a2"):
        system.validate(agent, "r1")
    system.start_canary("r1")
    system.observe_canary("r1", hit=False)
    system.observe_canary("r1", hit=False)
    system.pass_canary("r1")
    system.promote(POLICY, "r1")
    assert system.rules["r1"].trust == TAU
    system.tick()
    assert system.rules["r1"].state is Lifecycle.RETIRED
    assert system.rules["r1"].trust == 0
    assert "r1" not in system.active_policy
    system.check()


def test_seed_trust_does_not_create_vote():
    system = fresh()
    system.seed_trust("r1")
    assert system.rules["r1"].trust == TAU
    assert system.rules["r1"].votes == set()
    with pytest.raises(ProtocolError):
        system.start_canary("r1")
    for agent in ("a1", "a2"):
        system.validate(agent, "r1")
    system.start_canary("r1")
    system.check()


def test_duplicate_votes_do_not_increase_quorum():
    system = fresh()
    system.validate("a1", "r1")
    system.validate("a1", "r1")
    assert system.rules["r1"].votes == {"a1"}
    with pytest.raises(ProtocolError):
        system.start_canary("r1")


def test_direct_promotion_rejected():
    system = fresh()
    for agent in ("a1", "a2"):
        system.validate(agent, "r1")
    with pytest.raises(ProtocolError):
        system.promote(POLICY, "r1")
    assert "r1" not in system.active_policy


def test_canary_requires_clean_observations():
    system = fresh()
    for agent in ("a1", "a2"):
        system.validate(agent, "r1")
    system.start_canary("r1")
    with pytest.raises(ProtocolError):
        system.pass_canary("r1")
    system.observe_canary("r1", hit=True)
    system.observe_canary("r1", hit=False)
    assert system.rules["r1"].canary_seen == CANARY_OBS
    with pytest.raises(ProtocolError):
        system.pass_canary("r1")
    with pytest.raises(ProtocolError):
        system.promote(POLICY, "r1")
    system.check()


def test_canary_hit_is_permanent():
    system = fresh()
    for agent in ("a1", "a2"):
        system.validate(agent, "r1")
    system.start_canary("r1")
    system.observe_canary("r1", hit=True)
    system.observe_canary("r1", hit=False)
    assert system.rules["r1"].canary_hit is True
    with pytest.raises(ProtocolError):
        system.pass_canary("r1")


def test_canary_clean_path_promotes():
    system = fresh()
    for agent in ("a1", "a2"):
        system.validate(agent, "r1")
    system.start_canary("r1")
    for _ in range(CANARY_OBS):
        system.observe_canary("r1", hit=False)
    system.pass_canary("r1")
    system.promote(POLICY, "r1")
    assert system.rules["r1"].state is Lifecycle.PROMOTED
    system.check()


def test_trust_decay_exhaustive_verification():
    result = td.verify_discrete()
    assert result["violations"] == []
    assert result["cases"] > 10_000


def test_trust_decay_symbolic_verification():
    result = td.verify_continuous()
    assert result["available"] is True
    assert result["all_pass"] is True


@settings(max_examples=300, deadline=None)
@given(
    trust=st.fractions(0, 1, max_denominator=32),
    rho=st.sampled_from([Fraction(1, 2), Fraction(3, 4), Fraction(9, 10)]),
    alpha=st.sampled_from([Fraction(1, 10), Fraction(1, 4), Fraction(1, 2), Fraction(1)]),
)
def test_decay_bounds(trust, rho, alpha):
    value = td.iterate(trust, rho, alpha, 500)
    assert 0 <= value <= 1
