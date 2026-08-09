"""CR109 slice 2 — the game's tunable constants and their pure functions.

implementation_plan.md §5: this module is meant to own EVERY tunable
constant the game economy needs, each documented with why that number and
nothing anywhere else hand-copies it — later slices generate §18 of the
design from this module rather than five documents agreeing by hand.

Slice 2 needs exactly one family: the trading cost. Slice 3 adds the
finish stipend, the alpha-to-points curve and the achievable-benchmark
discount — landing here only once there is a scoring pass to test them
against (implementation_plan.md §1: "building them first means building
machinery that cannot run").

Pure — no DB, no network — matching `trading_math/twr.py`'s contract.
"""

from __future__ import annotations

# ── Trading cost (Amendment D) ──────────────────────────────────────────
#
# 10 bps of notional, floored at 1.00 AMI Cash, charged on BOTH sides of a
# fill (buy AND sell) — never on a training-path trade. BURNED: the fee
# reduces the trader's own cash and is credited to nothing. No table, no
# counter, no field total may ever accumulate it (§7.2 fence of the
# implementation plan — a pool of forfeited/farmed fees is a wagered
# stake, and that is the thing that would break CR109 §15's simulation-
# only legal position). `SimEngine._execute_fill()`'s `fee` parameter
# defaults to 0.0 and only `games_service.py`'s game trade path ever
# passes a non-zero value — see `test_games_trading_cost.py`.
FEE_BPS = 10.0
FEE_MIN = 1.00


def trade_fee(notional: float) -> float:
    """FEE_BPS of `notional`, floored at FEE_MIN, rounded to cents.

    `notional` is expected non-negative (fill_price * quantity); `abs()`
    is defensive only — there is no such thing as a free or negative cost,
    so a malformed caller still pays the floor rather than nothing.
    """
    bps_fee = abs(notional) * (FEE_BPS / 10_000.0)
    return round(max(bps_fee, FEE_MIN), 2)
