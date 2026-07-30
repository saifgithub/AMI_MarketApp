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

from datetime import datetime, timedelta, timezone

from app.trading_math.sizing import _nearest_tier

# CR129 — preset tables for the five CR101-BE2 limits, keyed on `risk_score`
# (1-5), same nearest-key-snap contract as `trading_math.sizing`'s tables.
# Sourced in docs/forward_planning/CR129_risk_limits_from_risk_tolerance/README.md
# ("Preset tables" + "Sourcing, per column") — not re-derived here.
#
# `None` on the matching Mandate field now means "follow my risk profile" (this
# preset), not "off" — the CR101-BE2 inversion CR129 authorises. "Off" stays
# expressible as an explicit override (cooldown 0h, a very high count, or a
# 100% open-risk cap), never as a fifth magic preset value.
DEFAULT_MAX_OPEN_POSITIONS: dict[int, int] = {1: 65, 2: 65, 3: 35, 4: 30, 5: 30}
# Never below 30 for any profile (the "nobody is forced to concentrate" floor —
# see the CR129 README's `max_open_positions` design/guard).
DIVERSIFICATION_FLOOR = 30
DEFAULT_POST_LOSS_COOLDOWN_HOURS: dict[int, float] = {1: 4.0, 2: 2.0, 3: 1.0, 4: 1.0, 5: 0.5}
DEFAULT_MAX_TRADES_PER_DAY: dict[int, int] = {1: 2, 2: 3, 3: 4, 4: 5, 5: 6}
DEFAULT_MAX_TRADES_PER_WEEK: dict[int, int] = {1: 6, 2: 9, 3: 12, 4: 15, 5: 20}
# Total open-risk cap is a FRACTION of the user's own `max_drawdown_pct` (not a
# flat percentage) — consistent with lesson 017's teaching that N correlated
# 1%-risk positions carry N% of real risk against the user's own stated ceiling.
DEFAULT_MAX_OPEN_RISK_FRACTION_OF_DRAWDOWN: dict[int, float] = {
    1: 0.25, 2: 0.30, 3: 0.35, 4: 0.45, 5: 0.50,
}


def resolved_max_open_positions(
    risk_score: int, override: int | None = None, *, table: dict[int, int] | None = None
) -> int:
    """Max distinct tickers concurrently held: the explicit per-user override
    when set, else the risk-tier preset (CR129)."""
    if override is not None:
        return int(override)
    t = DEFAULT_MAX_OPEN_POSITIONS if table is None else table
    return int(_nearest_tier(t, int(risk_score)))


def resolved_post_loss_cooldown_hours(
    risk_score: int, override: float | None = None, *, table: dict[int, float] | None = None
) -> float:
    """Hours after a stop-out before the next BUY: explicit override when set,
    else the risk-tier preset (CR129)."""
    if override is not None:
        return float(override)
    t = DEFAULT_POST_LOSS_COOLDOWN_HOURS if table is None else table
    return _nearest_tier(t, int(risk_score))


def resolved_max_trades_per_day(
    risk_score: int, override: int | None = None, *, table: dict[int, int] | None = None
) -> int:
    """Over-trading brake, per UTC calendar day: explicit override when set,
    else the risk-tier preset (CR129)."""
    if override is not None:
        return int(override)
    t = DEFAULT_MAX_TRADES_PER_DAY if table is None else table
    return int(_nearest_tier(t, int(risk_score)))


def resolved_max_trades_per_week(
    risk_score: int, override: int | None = None, *, table: dict[int, int] | None = None
) -> int:
    """Over-trading brake, per ISO week: explicit override when set, else the
    risk-tier preset (CR129)."""
    if override is not None:
        return int(override)
    t = DEFAULT_MAX_TRADES_PER_WEEK if table is None else table
    return int(_nearest_tier(t, int(risk_score)))


def resolved_max_open_risk_pct(
    risk_score: int,
    max_drawdown_pct: float,
    override: float | None = None,
    *,
    table: dict[int, float] | None = None,
) -> float:
    """Total open-risk cap (percentage points): explicit override when set,
    else a risk-tier fraction of THIS user's own `max_drawdown_pct` (CR129) —
    per-user, not a constant, since it is derived from a value the user
    already chose."""
    if override is not None:
        return float(override)
    t = DEFAULT_MAX_OPEN_RISK_FRACTION_OF_DRAWDOWN if table is None else table
    fraction = _nearest_tier(t, int(risk_score))
    return round(fraction * float(max_drawdown_pct), 4)


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
    if lifts_at is None:
        return False
    return _as_aware_utc(now) < _as_aware_utc(lifts_at)


def _as_aware_utc(dt: datetime) -> datetime:
    """Treat a naive datetime as already-UTC. SQLite (this suite's fixture DB)
    drops tzinfo on round-trip; Postgres (Alpha/prod) does not — the column is
    `DateTime(timezone=True)` throughout. CR129 made the over-trading brake
    always active (not opt-in), so every `sim.submit()`/`sim.preview()` call
    now compares real trade history against `now` on every trade, not only
    when a user had explicitly set the limit — this normalization is what
    keeps that comparison environment-agnostic rather than a test-suite-only
    TypeError."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def utc_day_start(now: datetime) -> datetime:
    return _as_aware_utc(now).replace(hour=0, minute=0, second=0, microsecond=0)


def utc_week_start(now: datetime) -> datetime:
    """Monday 00:00 UTC of `now`'s ISO week."""
    day_start = utc_day_start(now)
    return day_start - timedelta(days=day_start.weekday())


def trades_since(timestamps: list[datetime], boundary: datetime) -> int:
    boundary = _as_aware_utc(boundary)
    return sum(1 for t in timestamps if _as_aware_utc(t) >= boundary)


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
