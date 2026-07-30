"""CR129 backfill disclosure — the loud half of the coalesce-at-read backfill.

The backfill itself is STRUCTURAL, not a migration (README: "Do not write an
UPDATE over `mandates`") — every mandate with an unset field already resolves
to the new risk-tier preset the instant this deploys, via
`trading_math.sizing`/`trading_math.risk_limits`'s `resolved_*` functions.
Nothing here writes a new mandate version or changes a stored field.

What this module produces is the CR040 "degrade loudly" half: a plain-English
description of exactly what changed for a user whose mandate has one or more
of these fields unset, for a one-time `MANDATE_EDIT` journal entry
(`scripts/cr129_backfill_journal.py`) so the 13 live alpha users see WHY a
limit they never set is suddenly active, rather than discovering it silently
at the first blocked trade.
"""

from __future__ import annotations

from app.schemas import Mandate
from app.trading_math.risk_limits import (
    resolved_max_open_positions,
    resolved_max_open_risk_pct,
    resolved_max_trades_per_day,
    resolved_max_trades_per_week,
    resolved_post_loss_cooldown_hours,
)
from app.trading_math.sizing import resolved_single_name_cap_pct

# The pre-CR129 enforced value for an unset single-name cap — the flat
# backstop `safety_floor.single_name_cap_pct` fell back to before DEF187's
# unification. Sourcing the "was" side of the disclosure line; NOT read from
# `SINGLE_NAME_ABSOLUTE_CAP_PCT` at call time so a future change to that
# constant can't silently rewrite this backfill's own historical record.
_PRE_CR129_SINGLE_NAME_CAP_PCT = 50.0


def backfill_disclosure_lines(mandate: Mandate) -> list[str]:
    """Plain-English lines describing every limit this mandate's own PATCH
    history left unset and that CR129 now resolves to a real, enforced value.
    Empty when every one of the six was already explicitly set (nothing
    changes for that user — their overrides always won and still do)."""
    lines: list[str] = []

    if mandate.single_name_cap_pct is None:
        new = resolved_single_name_cap_pct(mandate.risk_score, None)
        lines.append(
            f"single-name cap {_PRE_CR129_SINGLE_NAME_CAP_PCT}% (old flat backstop) "
            f"→ {new}% (your risk profile, DEF187)"
        )
    if mandate.post_loss_cooldown_hours is None:
        new = resolved_post_loss_cooldown_hours(mandate.risk_score, None)
        lines.append(f"post-loss cooldown off → {new}h (your risk profile)")
    if mandate.max_open_positions is None:
        new = resolved_max_open_positions(mandate.risk_score, None)
        lines.append(f"max open positions off → {new} (your risk profile)")
    if mandate.max_trades_per_day is None:
        new = resolved_max_trades_per_day(mandate.risk_score, None)
        lines.append(f"max trades/day off → {new} (your risk profile)")
    if mandate.max_trades_per_week is None:
        new = resolved_max_trades_per_week(mandate.risk_score, None)
        lines.append(f"max trades/week off → {new} (your risk profile)")
    if mandate.max_open_risk_pct is None:
        new = resolved_max_open_risk_pct(mandate.risk_score, mandate.max_drawdown_pct, None)
        lines.append(f"total open-risk cap off → {new}% (your risk profile)")

    return lines


def backfill_disclosure_summary(mandate: Mandate) -> str | None:
    """One journalable summary string, or None if this mandate has nothing to
    disclose (every one of the six fields was already explicitly set)."""
    lines = backfill_disclosure_lines(mandate)
    if not lines:
        return None
    return (
        "CR129 — your risk limits now follow your risk profile (risk score "
        f"{mandate.risk_score}/5): " + "; ".join(lines)
    )
