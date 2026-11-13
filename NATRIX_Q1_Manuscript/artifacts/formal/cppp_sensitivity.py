"""Sensitivity of CPPP quorum and trust-decay parameters.

Two exact calculations, no simulation:

Quorum
------
With N agents, quorum K, c compromised agents that always vote, and honest
agents that validate independently with probability p, the probability that a
candidate receives at least K votes is the binomial tail over the honest
agents.  This makes the trade-off between K and the compromised fraction
explicit.

Trust decay
-----------
For the discrete map tick(T) = reinforce(decay(T)), the half-life, fixed point,
1% settling time, and no-evidence retirement time are computed with exact
rational arithmetic for a grid of rho and alpha.

Outputs
-------
artifacts/formal/cppp_sensitivity.json
tables/cppp_sensitivity.md
"""

from __future__ import annotations

import json
import math
from fractions import Fraction
from pathlib import Path

FORMAL = Path(__file__).resolve().parent
ROOT = FORMAL.parents[1]
OUT = ROOT / "tables"
OUT.mkdir(parents=True, exist_ok=True)


def quorum_probability(n: int, k: int, p: float, compromised: int = 0) -> float:
    """P(at least k votes) with `compromised` automatic votes."""
    honest = n - compromised
    need = max(0, k - compromised)
    if need > honest:
        return 0.0
    return sum(
        math.comb(honest, h) * (p ** h) * ((1 - p) ** (honest - h))
        for h in range(need, honest + 1)
    )


def half_life(rho: Fraction) -> int:
    value = Fraction(1)
    n = 0
    while value > Fraction(1, 2):
        value *= rho
        n += 1
    return n


def fixed_point(rho: Fraction, alpha: Fraction) -> Fraction:
    return alpha / (1 - (1 - alpha) * rho)


def settle_ticks(rho: Fraction, alpha: Fraction, tol: Fraction = Fraction(1, 100)) -> int:
    star = fixed_point(rho, alpha)
    value = Fraction(0)
    n = 0
    while abs(value - star) > tol and n < 10_000:
        value = rho * value
        value = value + alpha * (1 - value)
        n += 1
    return n


def retire_ticks(rho: Fraction, start: Fraction, tau: Fraction) -> int:
    """Ticks of no evidence until trust falls below tau."""
    value = start
    n = 0
    while value >= tau and n < 10_000:
        value *= rho
        n += 1
    return n


def main() -> None:
    n_agents = 5
    quorum_rows = []
    for compromised in (0, 1, 2):
        for k in (2, 3, 4):
            for p in (0.2, 0.4, 0.6, 0.8):
                quorum_rows.append(
                    {
                        "agents": n_agents,
                        "quorum": k,
                        "compromised": compromised,
                        "honest_validate_p": p,
                        "promotion_probability": round(
                            quorum_probability(n_agents, k, p, compromised), 6
                        ),
                    }
                )

    trust_rows = []
    for rho in (Fraction(1, 2), Fraction(3, 4), Fraction(9, 10), Fraction(19, 20)):
        for alpha in (Fraction(1, 10), Fraction(1, 4), Fraction(1, 2), Fraction(1)):
            star = fixed_point(rho, alpha)
            trust_rows.append(
                {
                    "rho": float(rho),
                    "alpha": float(alpha),
                    "half_life_ticks": half_life(rho),
                    "fixed_point": round(float(star), 6),
                    "settle_1pct_ticks": settle_ticks(rho, alpha),
                    "retire_from_075_at_tau_050": retire_ticks(
                        rho, Fraction(3, 4), Fraction(1, 2)
                    ),
                }
            )

    result = {
        "quorum": {
            "agents": n_agents,
            "rows": quorum_rows,
            "note": "Exact binomial tail; compromised agents vote automatically.",
        },
        "trust_decay": {
            "rows": trust_rows,
            "note": "Exact rational iteration of tick(T)=reinforce(decay(T)).",
        },
    }
    (FORMAL / "cppp_sensitivity.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    lines = [
        "# CPPP parameter sensitivity",
        "",
        "## Quorum: exact binomial promotion probability (N = 5 agents)",
        "",
        "| compromised agents | K | honest p=0.2 | p=0.4 | p=0.6 | p=0.8 |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for compromised in (0, 1, 2):
        for k in (2, 3, 4):
            vals = [
                row["promotion_probability"]
                for row in quorum_rows
                if row["compromised"] == compromised and row["quorum"] == k
            ]
            lines.append(
                f"| {compromised} | {k} | " + " | ".join(f"{v:.3f}" for v in vals) + " |"
            )
    lines += [
        "",
        "## Trust decay: exact rational iteration",
        "",
        "| rho | alpha | half-life (ticks) | fixed point | 1% settling (ticks) | retire 0.75->0.50 (ticks) |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for row in trust_rows:
        lines.append(
            f"| {row['rho']:.2f} | {row['alpha']:.2f} | {row['half_life_ticks']} | "
            f"{row['fixed_point']:.3f} | {row['settle_1pct_ticks']} | "
            f"{row['retire_from_075_at_tau_050']} |"
        )
    lines.append("")
    (OUT / "cppp_sensitivity.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
