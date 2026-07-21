"""Position-size caps — the one place the per-risk-tier cap is defined.

CR046 M03: three modules used to answer "how big a position?" three different,
mutually-inconsistent ways — the Trader agent was TOLD up to 40% per name
(overlay_generator), the Portfolio Manager silently CLAMPED to 4.5%
(room_runner), and compliance allowed a flat 50% (safety_floor). A risk-5 user's
agent proposed 40% and the system enforced ~4.5%. The invariant this fixes: the
number an agent is shown must equal the number the system enforces. So the cap
lives here and every call site reads it.

`DEFAULT_RISK_TIER_CAPS` is AMI's live enforced policy (exactly the values the PM
already clamped to — adopting them here changes no enforced behaviour, only the
Trader's now-truthful narration). Another project reuses the mechanism by passing
its own `caps` table; the numbers are product policy, not universal math.
"""

from __future__ import annotations

from typing import NamedTuple

# AMI's enforced per-risk-tier single-name cap (% of portfolio).
DEFAULT_RISK_TIER_CAPS: dict[int, float] = {1: 1.5, 2: 1.5, 3: 3.0, 4: 4.5, 5: 4.5}

# Absolute single-name ceiling, independent of risk tier. Every tier cap is <= this;
# it is the deterministic backstop the compliance floor enforces regardless of mandate.
SINGLE_NAME_ABSOLUTE_CAP_PCT: float = 50.0


def risk_tier_cap(risk_score: int, caps: dict[int, float] | None = None) -> float:
    """The single-name position-size cap (%) for a risk tier.

    Total for any non-empty table: a risk_score without an exact key snaps to the
    nearest key present (ties round down to the lower tier), so neither an
    out-of-range score nor a *sparse* custom `caps` table can raise (CR046 O1).
    An empty table is the one unsupported input — a caller error, not a score one.
    """
    table = DEFAULT_RISK_TIER_CAPS if caps is None else caps
    score = int(risk_score)
    if score in table:
        return table[score]
    return table[min(table, key=lambda k: (abs(k - score), k))]


def clamp_size(proposed_pct: float, cap_pct: float) -> float:
    """Clamp a proposed position size (%) down to its cap. Never raises."""
    return min(float(proposed_pct), float(cap_pct))


class DebatorSizes(NamedTuple):
    """The three Risk Debators' sizing positions, spread around the Trader's size."""

    aggressive: float  # push up (bounded by the absolute backstop)
    conservative: float  # trim down (floored at a token 0.5%)
    neutral: float  # hold at the Trader's size


def risk_debator_sizes(
    trader_size: float, backstop: float = SINGLE_NAME_ABSOLUTE_CAP_PCT
) -> DebatorSizes:
    """The Aggressive/Conservative/Neutral sizing spread around `trader_size`.

    A deterministic debate spread — +2 pts (Aggressive, capped at the absolute
    backstop), −1.5 pts (Conservative, floored at 0.5%), and the Trader's own size
    (Neutral). These are debate *positions*, not enforced sizes: the PM's own clamp
    (`risk_tier_cap`) and the safety floor remain the enforcement. Centralised here
    so the offsets live next to the caps they orbit instead of as inline magic
    numbers in the Room runner.
    """
    return DebatorSizes(
        aggressive=round(min(backstop, trader_size + 2), 1),
        conservative=round(max(0.5, trader_size - 1.5), 1),
        neutral=round(trader_size, 1),
    )
