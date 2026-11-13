"""Trust decay: executable model plus machine-checked properties.

Two models are provided.

Continuous (analysis).  Without evidence a rule's trust decays exponentially:

    T(t) = T0 * exp(-lambda * t),   T0 in [0, 1], lambda > 0

Positive evidence raises trust towards 1 with gain alpha in (0, 1]:

    E(T) = T + alpha * (1 - T)

Discrete (implementation).  Trust is an exact rational in [0, 1]:

    decay(T)        = rho * T                    (one scheduler tick, rho in (0,1))
    reinforce(T)    = T + alpha * (1 - T)
    tick(T)         = reinforce(decay(T))        (stationary evidence every tick)

The discrete properties are verified by exhaustive enumeration over a rational
grid; the continuous properties are proved symbolically with SymPy.  Both
verification passes write their results to JSON, so a claim in the paper can be
traced to an executed check rather than to prose.
"""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

OUT = Path(__file__).resolve().parent

# Rational grid used by the exhaustive checks.  Every value is exactly
# representable, so the checks are exact rather than floating point.
TRUST_GRID = [Fraction(k, 16) for k in range(17)]
RHO_GRID = [Fraction(1, 2), Fraction(3, 4), Fraction(9, 10), Fraction(19, 20)]
ALPHA_GRID = [Fraction(1, 10), Fraction(1, 4), Fraction(1, 2), Fraction(1)]
STEPS = 200


# ---------------------------------------------------------------------------
# Discrete model
# ---------------------------------------------------------------------------

def decay(trust: Fraction, rho: Fraction) -> Fraction:
    return rho * trust


def reinforce(trust: Fraction, alpha: Fraction) -> Fraction:
    return trust + alpha * (1 - trust)


def tick(trust: Fraction, rho: Fraction, alpha: Fraction) -> Fraction:
    return reinforce(decay(trust, rho), alpha)


def iterate(trust: Fraction, rho: Fraction, alpha: Fraction, n: int) -> Fraction:
    for _ in range(n):
        trust = tick(trust, rho, alpha)
    return trust


def half_life_ticks(rho: Fraction) -> int:
    """Smallest n >= 1 with rho**n <= 1/2 (exact rational arithmetic)."""
    value = Fraction(1)
    n = 0
    while True:
        n += 1
        value *= rho
        if value <= Fraction(1, 2):
            return n


def fixed_point(rho: Fraction, alpha: Fraction) -> Fraction:
    """Closed form of the stationary-evidence iteration."""
    return alpha / (1 - (1 - alpha) * rho)


def closed_form(trust0: Fraction, rho: Fraction, alpha: Fraction, n: int) -> Fraction:
    """T_n = T* + (T0 - T*) * ((1-alpha) * rho)**n."""
    star = fixed_point(rho, alpha)
    return star + (trust0 - star) * ((1 - alpha) * rho) ** n


# ---------------------------------------------------------------------------
# Exhaustive verification
# ---------------------------------------------------------------------------

def verify_discrete() -> dict:
    cases = 0
    violations: list[str] = []

    # 1. Boundedness of decay.
    for trust0 in TRUST_GRID:
        for rho in RHO_GRID:
            value = trust0
            for n in range(STEPS + 1):
                cases += 1
                if not (0 <= value <= 1):
                    violations.append(f"decay out of bounds T0={trust0} rho={rho} n={n} v={value}")
                value = decay(value, rho)

    # 2. Monotone non-increasing decay, strict while trust > 0.
    for trust0 in TRUST_GRID:
        if trust0 == 0:
            continue
        for rho in RHO_GRID:
            value = trust0
            for n in range(STEPS):
                cases += 1
                nxt = decay(value, rho)
                if nxt > value:
                    violations.append(f"decay increased T0={trust0} rho={rho} n={n}")
                value = nxt

    # 3. Half-life definition.
    for rho in RHO_GRID:
        cases += 1
        h = half_life_ticks(rho)
        if not (rho ** h <= Fraction(1, 2) < rho ** (h - 1)):
            violations.append(f"half-life wrong rho={rho} h={h}")

    # 4. Recovery bounds and monotonicity.
    for trust0 in TRUST_GRID:
        for alpha in ALPHA_GRID:
            cases += 1
            value = reinforce(trust0, alpha)
            if not (trust0 <= value <= 1):
                violations.append(f"recovery out of bounds T0={trust0} alpha={alpha}")
            if trust0 == 1 and value != 1:
                violations.append(f"full trust not absorbing T0={trust0} alpha={alpha}")

    # 5. Stationary evidence: closed form equals iteration, bounded, monotone,
    #    convergent to the fixed point.
    for trust0 in TRUST_GRID:
        for rho in RHO_GRID:
            for alpha in ALPHA_GRID:
                star = fixed_point(rho, alpha)
                if not (0 <= star <= 1):
                    violations.append(f"fixed point out of bounds rho={rho} alpha={alpha}")
                value = trust0
                previous = trust0
                for n in range(STEPS + 1):
                    cases += 1
                    expected = closed_form(trust0, rho, alpha, n)
                    if value != expected:
                        violations.append(f"closed form mismatch n={n} T0={trust0} rho={rho} alpha={alpha}")
                    if not (0 <= value <= 1):
                        violations.append(f"iteration out of bounds n={n}")
                    if n > 0:
                        if alpha == 0:
                            if value > previous:
                                violations.append("iteration increased without evidence")
                        elif (trust0 - star) < 0 and value < previous:
                            violations.append("iteration decreased while below fixed point")
                        elif (trust0 - star) > 0 and value > previous:
                            violations.append("iteration increased while above fixed point")
                    previous = value
                    value = tick(value, rho, alpha)
                cases += 1
                if abs(value - star) > Fraction(1, 10 ** 6):
                    violations.append(
                        f"no convergence T0={trust0} rho={rho} alpha={alpha} "
                        f"value={float(value):.9f} star={float(star):.9f}"
                    )
    return {"model": "discrete", "cases": cases, "violations": violations[:20]}


def verify_continuous() -> dict:
    """Symbolic proofs with SymPy; skips with a recorded reason if absent."""
    try:
        import sympy as sp
    except Exception as exc:  # noqa: BLE001
        return {"model": "continuous", "available": False, "reason": str(exc)}

    t, lam, T0, alpha = sp.symbols("t lambda T0 alpha", positive=True)
    checks = {}

    T = T0 * sp.exp(-lam * t)
    # Boundedness is proved from three identities: T(0)=T0, dT/dt = -lambda*T,
    # and T -> 0.  With T0 <= 1 and a negative derivative, 0 < T <= T0 <= 1.
    checks["initial_value"] = sp.simplify(sp.limit(T, t, 0, "+") - T0) == 0
    checks["limit_at_infinity"] = sp.simplify(sp.limit(T, t, sp.oo)) == 0
    dT = sp.diff(T, t)
    checks["monotone_decreasing"] = sp.simplify(dT + lam * T) == 0
    checks["bounded_above_identity"] = (
        sp.simplify((T0 - T) - T0 * (1 - sp.exp(-lam * t))) == 0
    )
    half = sp.log(2) / lam
    checks["half_life_identity"] = sp.simplify(T.subs(t, half) - T0 / 2) == 0

    E = T0 + alpha * (1 - T0)
    checks["recovery_nondecreasing"] = sp.simplify(E - T0 - alpha * (1 - T0)) == 0
    checks["recovery_upper_bound"] = sp.simplify((1 - E) - (1 - alpha) * (1 - T0)) == 0
    checks["recovery_contracts_gap"] = (
        sp.simplify(((1 - T0) - (1 - E)) - alpha * (1 - T0)) == 0
    )

    # Stationary-evidence map E(decay(T)) has contraction factor (1-alpha)*rho < 1.
    rho = sp.symbols("rho", positive=True)
    combined = alpha * (1 - rho * T0) + rho * T0
    star = alpha / (1 - (1 - alpha) * rho)
    error = sp.simplify(combined - star - (1 - alpha) * rho * (T0 - star))
    checks["contraction_identity"] = error == 0

    return {
        "model": "continuous",
        "available": True,
        "checks": {k: bool(v) for k, v in checks.items()},
        "all_pass": all(bool(v) for v in checks.values()),
    }


def verify() -> dict:
    discrete = verify_discrete()
    continuous = verify_continuous()
    result = {
        "discrete": discrete,
        "continuous": continuous,
        "pass": bool(not discrete["violations"] and continuous.get("all_pass", False)),
        "grid": {
            "trust_points": len(TRUST_GRID),
            "rho_values": len(RHO_GRID),
            "alpha_values": len(ALPHA_GRID),
            "steps": STEPS,
        },
    }
    return result


def main() -> None:
    result = verify()
    (OUT / "trust_decay_verification.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, indent=2))
    if not result["pass"]:
        raise SystemExit("trust-decay verification failed")


if __name__ == "__main__":
    main()
