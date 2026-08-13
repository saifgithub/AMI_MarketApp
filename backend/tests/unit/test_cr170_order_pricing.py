"""CR170 acceptance 6, 7 and 8 — the two rules and the session-anchored expiry.

Rules 1 and 2 are the whole feature; §Design calls everything else "plumbing
around these". Tested here against the pure modules, and again through
`SimEngine` in `test_cr170_resting_orders.py` — the pure test says the arithmetic
is right, the engine test says the arithmetic is the one that runs.

The boundary cases are the point. `is_triggered` is **inclusive** so it agrees
with `evaluate_outcomes`' existing `price <= stop` / `price >= target`, and both
now fire from the same sweep: a user watching a stop-loss and a sell-stop order
at the same number must not see one fire and the other not.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.schemas.trade import OrderType, Side
from app.trading_math.market_hours import session_close_on_or_after
from app.trading_math.order_pricing import (
    can_rest,
    fill_price_for,
    is_triggered,
    named_price_for,
    rests_below,
    stop_limit_becomes_limit,
)

ET = ZoneInfo("America/New_York")


def _et(y, m, d, hh, mm=0) -> datetime:
    return datetime(y, m, d, hh, mm, tzinfo=ET).astimezone(timezone.utc)


# ── Rule 1: which side of the market ────────────────────────────────────────


@pytest.mark.parametrize(
    "side,order_type,below",
    [
        (Side.BUY, OrderType.LIMIT, True),        # buy the dip
        (Side.BUY, OrderType.STOP, False),        # breakout entry
        (Side.BUY, OrderType.STOP_LIMIT, False),
        (Side.SELL, OrderType.STOP, True),        # stop-loss
        (Side.SELL, OrderType.STOP_LIMIT, True),
        (Side.SELL, OrderType.LIMIT, False),      # take profit
    ],
)
def test_all_four_directions(side, order_type, below):
    assert rests_below(side=side, order_type=order_type) is below


def test_the_diagonal_is_real():
    """A buy limit and a sell stop are the SAME comparison, as are a buy stop
    and a sell limit. Two predicates, four orders — the reason the helper
    returns a direction instead of switching on four cases."""
    assert rests_below(side=Side.BUY, order_type=OrderType.LIMIT) == rests_below(
        side=Side.SELL, order_type=OrderType.STOP
    )
    assert rests_below(side=Side.BUY, order_type=OrderType.STOP) == rests_below(
        side=Side.SELL, order_type=OrderType.LIMIT
    )


def test_wire_strings_work_too():
    assert rests_below(side="buy", order_type="limit") is True
    assert rests_below(side="sell", order_type="stop_limit") is True


# ── Rule 1: the trigger, including the exact touch ──────────────────────────


@pytest.mark.parametrize(
    "side,order_type,named,mark,fires",
    [
        # Buy limit $190 — rests below, fires when price falls to it.
        (Side.BUY, OrderType.LIMIT, 190.0, 190.01, False),
        (Side.BUY, OrderType.LIMIT, 190.0, 190.0, True),    # the exact touch
        (Side.BUY, OrderType.LIMIT, 190.0, 189.99, True),
        # Sell stop $90 — rests below.
        (Side.SELL, OrderType.STOP, 90.0, 90.01, False),
        (Side.SELL, OrderType.STOP, 90.0, 90.0, True),
        (Side.SELL, OrderType.STOP, 90.0, 85.0, True),
        # Buy stop $110 — rests above.
        (Side.BUY, OrderType.STOP, 110.0, 109.99, False),
        (Side.BUY, OrderType.STOP, 110.0, 110.0, True),
        (Side.BUY, OrderType.STOP, 110.0, 115.0, True),
        # Sell limit $210 — rests above.
        (Side.SELL, OrderType.LIMIT, 210.0, 209.99, False),
        (Side.SELL, OrderType.LIMIT, 210.0, 210.0, True),
        (Side.SELL, OrderType.LIMIT, 210.0, 214.0, True),
    ],
)
def test_trigger_including_the_exact_boundary(side, order_type, named, mark, fires):
    assert is_triggered(side=side, order_type=order_type, named=named, mark=mark) is fires


def test_the_boundary_is_inclusive_on_both_sides():
    """Pinned separately from the table above, because this is the property
    that has to agree with `evaluate_outcomes` and a table row is easy to edit
    without noticing what it was for."""
    assert is_triggered(side=Side.BUY, order_type=OrderType.LIMIT, named=50.0, mark=50.0)
    assert is_triggered(side=Side.BUY, order_type=OrderType.STOP, named=50.0, mark=50.0)


# ── Rule 1: which price names the order ─────────────────────────────────────


def test_named_price_by_type():
    assert named_price_for(OrderType.LIMIT, limit_price=190.0, trigger_price=1.0) == 190.0
    assert named_price_for(OrderType.STOP, limit_price=1.0, trigger_price=90.0) == 90.0
    assert named_price_for(
        OrderType.STOP_LIMIT, limit_price=88.0, trigger_price=90.0
    ) == 90.0
    assert named_price_for(OrderType.MARKET, limit_price=5.0, trigger_price=5.0) is None


def test_market_never_rests():
    assert can_rest(OrderType.MARKET) is False
    for ot in (OrderType.LIMIT, OrderType.STOP, OrderType.STOP_LIMIT):
        assert can_rest(ot) is True


# ── Rule 2: the fill price ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "label,side,named,mark,books_at",
    [
        ("buy limit — you pay what you asked", Side.BUY, 190.0, 187.40, 190.0),
        ("sell limit — you get what you asked", Side.SELL, 210.0, 214.0, 210.0),
        ("sell stop — SLIPPAGE, below the trigger", Side.SELL, 90.0, 85.0, 85.0),
        ("buy stop — SLIPPAGE, above the trigger", Side.BUY, 110.0, 115.0, 115.0),
    ],
)
def test_rule_2_all_four_cases(label, side, named, mark, books_at):
    assert fill_price_for(side=side, named=named, mark=mark) == pytest.approx(books_at)


def test_the_user_never_gets_the_better_side_of_the_gap():
    """The whole reason Rule 2 is worse-of rather than the observed mark: our
    mark is a 15-minute-delayed sample of a price that already traded through,
    so a mark-priced fill would hand the user that gap systematically — and it
    is farmable by resting a buy limit a fraction under the market."""
    for mark in (150.0, 175.0, 199.99):
        assert fill_price_for(side=Side.BUY, named=200.0, mark=mark) >= 200.0
    for mark in (250.0, 225.0, 200.01):
        assert fill_price_for(side=Side.SELL, named=200.0, mark=mark) <= 200.0


# ── Stop-limit is two-phase ─────────────────────────────────────────────────


def test_stop_limit_that_gaps_through_its_limit_never_fills():
    """The classic stop-limit failure, reproduced rather than smoothed.
    Sell stop-limit, trigger $90, limit $88."""
    assert stop_limit_becomes_limit(OrderType.STOP_LIMIT) is True

    # Eases to $89: triggers, then evaluates as a sell limit at $88 → fills.
    assert is_triggered(side=Side.SELL, order_type=OrderType.STOP_LIMIT, named=90.0, mark=89.0)
    assert is_triggered(side=Side.SELL, order_type=OrderType.LIMIT, named=88.0, mark=89.0)

    # Gaps to $85: triggers, then the sell limit at $88 is UNMARKETABLE → rests.
    assert is_triggered(side=Side.SELL, order_type=OrderType.STOP_LIMIT, named=90.0, mark=85.0)
    assert not is_triggered(side=Side.SELL, order_type=OrderType.LIMIT, named=88.0, mark=85.0)


# ── Acceptance 8: session-anchored expiry ───────────────────────────────────


def test_saturday_day_order_expires_monday_16_et():
    # Saturday 2026-08-15 is a Saturday; 2026-08-17 is the Monday.
    placed = _et(2026, 8, 15, 11, 0)
    expires = session_close_on_or_after(placed).astimezone(ET)
    assert (expires.year, expires.month, expires.day) == (2026, 8, 17)
    assert (expires.hour, expires.minute) == (16, 0)


def test_inside_a_live_session_expires_the_same_day():
    placed = _et(2026, 8, 18, 11, 0)   # Tuesday, mid-session
    expires = session_close_on_or_after(placed).astimezone(ET)
    assert (expires.month, expires.day, expires.hour) == (8, 18, 16)


def test_after_the_close_rolls_to_the_next_session():
    placed = _et(2026, 8, 18, 21, 0)   # Tuesday 21:00 ET, after the close
    expires = session_close_on_or_after(placed).astimezone(ET)
    assert (expires.month, expires.day, expires.hour) == (8, 19, 16)


def test_before_the_open_expires_the_same_day():
    placed = _et(2026, 8, 18, 8, 0)
    expires = session_close_on_or_after(placed).astimezone(ET)
    assert (expires.month, expires.day, expires.hour) == (8, 18, 16)


def test_no_tif_ever_lands_on_a_local_calendar_boundary():
    """Acceptance 8's second half. Sweep a full year of placements at every hour
    and assert every expiry is a 16:00 ET session close on a weekday — never
    midnight, never a Saturday or Sunday, and never anchored to the placer's own
    clock."""
    start = _et(2026, 1, 1, 0, 0)
    for hours in range(0, 366 * 24, 7):
        expires = session_close_on_or_after(start + timedelta(hours=hours)).astimezone(ET)
        assert (expires.hour, expires.minute, expires.second) == (16, 0, 0)
        assert expires.weekday() < 5


def test_gtd_uses_the_same_rule_from_a_shifted_anchor():
    """GTD_30 needs no separate implementation — it is the same function applied
    to `placed_at + N days`, which is why "the trading day on or after" is not a
    second code path."""
    placed = _et(2026, 8, 18, 11, 0)
    expires = session_close_on_or_after(placed + timedelta(days=30)).astimezone(ET)
    assert (expires.hour, expires.minute) == (16, 0)
    assert expires.weekday() < 5
    assert expires > placed + timedelta(days=29)
