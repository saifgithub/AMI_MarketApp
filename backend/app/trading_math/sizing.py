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

# AMI's enforced per-risk-tier single-name cap (% of portfolio).
DEFAULT_RISK_TIER_CAPS: dict[int, float] = {1: 1.5, 2: 1.5, 3: 3.0, 4: 4.5, 5: 4.5}

# Absolute single-name ceiling, independent of risk tier. Every tier cap is <= this;
# it is the deterministic backstop the compliance floor enforces regardless of mandate.
SINGLE_NAME_ABSOLUTE_CAP_PCT: float = 50.0


def risk_tier_cap(risk_score: int, caps: dict[int, float] | None = None) -> float:
    """The single-name position-size cap (%) for a risk tier.

    Table-driven and total: a risk_score outside the table's keys clamps to the
    nearest tier rather than raising, so a malformed score can never crash sizing.
    """
    table = DEFAULT_RISK_TIER_CAPS if caps is None else caps
    key = min(max(int(risk_score), min(table)), max(table))
    return table[key]


def clamp_size(proposed_pct: float, cap_pct: float) -> float:
    """Clamp a proposed position size (%) down to its cap. Never raises."""
    return min(float(proposed_pct), float(cap_pct))
