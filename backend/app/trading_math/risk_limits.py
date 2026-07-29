"""CR101-BE2 — the four risk limits that did not exist in any form pre-CR101.

Pure functions, no DB/DateTime.now() calls — every check takes `now` and
whatever trade history it needs as explicit arguments, so `agents/safety_floor.py`
stays deterministic and every caller's clock is one it controls (CR101-BE2
acceptance 7). Centralised here (not inlined in safety_floor.py) so the same
math is available to a future caller without a second re-derivation — the
CR046/DEF153 lesson `trading_math/sizing.py` already applies to the two
existing caps.

Day/week boundaries are pinned to a FIXED UTC basis (calendar day, ISO week
starting Monday 00:00 UTC) — NOT `Mandate.timezone`. Per-user timezone
boundaries would need the user's zone threaded through every trade-history
caller for a brake whose whole point is "don't overtrade today"; UTC-midnight
is close enough for that purpose and is what a test can pin unambiguously
without a zoneinfo dependency. Disclosed judgment call — see the CR101-BE2
hand-off bridge.
"""

from __future__ import annotations

from datetime import datetime, timedelta


def cooldown_lifts_at(
    last_loss_closed_at: datetime | None, cooldown_hours: float | None
) -> datetime | None:
    """When the post-loss cooldown lifts, or None if no cooldown is pending."""
    if last_loss_closed_at is None or cooldown_hours is None:
        return None
    return last_loss_closed_at + timedelta(hours=cooldown_hours)


def in_cooldown(
    now: datetime, last_loss_closed_at: datetime | None, cooldown_hours: float | None
) -> bool:
    lifts_at = cooldown_lifts_at(last_loss_closed_at, cooldown_hours)
    return lifts_at is not None and now < lifts_at


def utc_day_start(now: datetime) -> datetime:
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def utc_week_start(now: datetime) -> datetime:
    """Monday 00:00 UTC of `now`'s ISO week."""
    day_start = utc_day_start(now)
    return day_start - timedelta(days=day_start.weekday())


def trades_since(timestamps: list[datetime], boundary: datetime) -> int:
    return sum(1 for t in timestamps if t >= boundary)


def stop_distance_pct(entry_price: float, stop: float) -> float:
    """How far the stop sits below (or above, for a short) entry, as a % of
    entry price. Never raises on a zero/negative entry — returns 0 (nothing to
    price), same "unpriceable = no contribution, not a crash" contract as the
    single-name cap's own unpriced-proposal guard."""
    if entry_price <= 0:
        return 0.0
    return abs(entry_price - stop) / entry_price * 100.0


def position_risk_contribution(position_pct: float, entry_price: float, stop: float) -> float:
    """A single position's contribution (percentage points) to the total
    open-risk sum: position size (% of portfolio) x stop distance (% of
    entry), scaled by /100 so 5% size x 20% stop = 1.0 pt, matching the
    overlay's own size% x stop-distance% drawdown-contribution framing."""
    return position_pct * stop_distance_pct(entry_price, stop) / 100.0
