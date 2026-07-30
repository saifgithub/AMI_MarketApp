"""Day Trader preset — CR129.

Saiful: *"i expect a day trader may also try to learn from using the app...
I am now wondering if we can have a 'day trader' preset, that takes off all
the safeguard."* Writes explicit permissive overrides into the seven risk
limits a user controls. It is NOT `risk_score = 6` (the field is `ge=1, le=5`
and feeds `risk_tier_cap` at 12+ overlay sites) and there is NO bypass flag —
`safety_floor.py`'s deterministic check still runs on every trade, it simply
evaluates these permissive numbers. Compliance, locale, halal, and the
allow/blocklist family (`safety_floor.py`'s "not the user's to relax" side)
are untouched by this preset — see docs/forward_planning/
CR129_risk_limits_from_risk_tolerance/README.md, "The 'Day Trader' preset".
"""

from __future__ import annotations

# "Positions and trade counts set high" (README) — a large-but-finite ceiling
# rather than an unbounded sentinel, since these are plain `int` fields with
# no None-means-infinity contract.
_DAY_TRADER_HIGH_COUNT = 999_999

DAY_TRADER_PRESET_OVERRIDES: dict[str, float | int] = {
    "sector_cap_pct": 100.0,
    "single_name_cap_pct": 100.0,
    "post_loss_cooldown_hours": 0.0,
    "max_open_positions": _DAY_TRADER_HIGH_COUNT,
    "max_trades_per_day": _DAY_TRADER_HIGH_COUNT,
    "max_trades_per_week": _DAY_TRADER_HIGH_COUNT,
    "max_open_risk_pct": 100.0,
}

# Disclosed at selection time (CR040 — a silent 100% is exactly what "degrade
# loudly" exists to stop), not a block: L3 draws no ceiling on what a user may
# set. The two published baselines this CR is already grounded in.
DAY_TRADER_DISCLOSURE = (
    "Day Trader preset removes every risk limit you control: sector and "
    "single-name concentration caps, the post-loss cooldown, max open "
    "positions, trade-pace limits, and total open risk all go permissive. "
    "Compliance, locale, and halal/allow-blocklist rules still apply — this "
    "preset cannot touch them.\n\n"
    "What the evidence says happens: Barber & Odean (66,465 US households, "
    "1991-1996) found the most-active traders earned 11.4%/yr against 18.5%/yr "
    "for the least-active. In Taiwan's day-trading population, under 1% were "
    "reliably profitable and over 80% lost money in a typical six-month "
    "window. This is a training simulator — the outcome is the lesson."
)


def is_day_trader_preset(updates: dict) -> bool:
    """True when a PATCH payload applies the Day Trader preset verbatim — every
    override present with the exact preset value. Used only to give the
    mandate-edit journal entry a distinct, readable summary (CR040); it does
    not change how the PATCH is validated or enforced."""
    return all(updates.get(k) == v for k, v in DAY_TRADER_PRESET_OVERRIDES.items())
