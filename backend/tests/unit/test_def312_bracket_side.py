"""DEF312 — a stop below entry, a target above it. Both directions, every path.

CR171 §5 shipped `short_bracket_is_wrong_side`, called from `_open_short_fill`
alone. `_open_short_fill` is unreachable from a buy, so **the long half of the
rule was never checked anywhere**: not in the safety floor, which only feeds
`proposed_stop` into a risk-sizing figure through an `abs()`, and not on the
client, whose `stopIsWrongSide`/`targetIsWrongSide` take an `isShort` flag,
handle the long case correctly, and are called behind `if intent !=
SellIntent.opensShort: return null`.

That is **P21** — a check present in the source and inert at runtime — on both
sides of the wire at once, which is also why reading either one made it look
covered.

The cost is not cosmetic. `bracket_hit` fires a long stop on `mark <= stop`, so a
buy with its stop above entry is liquidated on the **next** market-hours sweep,
at market, and booked as a stop-out — which then trips the post-stop-out cooldown
that hard-blocks the user's next BUY. One transposed field, an instant
liquidation and a trading ban, with nothing anywhere explaining it.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.db import get_session
from app.db.models import SimRestingOrderRow
from app.schemas.trade import OrderType, Side
from app.services.coach_engine import hydrate_coach_mandate
from app.services.market_data import Quote
from app.services.sim_engine import SimEngine
from app.services.sim_resting_orders import sweep_resting_orders
from app.trading_math.order_pricing import bracket_is_wrong_side


class _Pinned:
    def __init__(self, prices: dict[str, float], source: str = "yfinance"):
        self.prices = {k.upper(): v for k, v in prices.items()}
        self.source = source

    def quote(self, ticker: str) -> Quote | None:
        return Quote(price=self.prices.get(ticker.upper(), 100.0), source=self.source)

    def history(self, *a, **k):  # pragma: no cover
        return []

    def news(self, *a, **k):  # pragma: no cover
        return []

    def earnings(self, *a, **k):  # pragma: no cover
        return None


def _mandate(*, long_only: bool = True, **over):
    """`long_only` lives under `compliance`, not at the top level — passing it
    flat hydrates to the default (`True`), which refuses the short before the
    bracket is ever reached. Lifted from `test_cr171_short_selling.py`, where
    the same trap has its own comment."""
    base = {
        "plan": "trader",
        "single_name_cap_pct": 100.0,
        "max_open_risk_pct": 100.0,
        "compliance": {"long_only": long_only},
    }
    base.update(over)
    return hydrate_coach_mandate(base)


# ── The pure rule, both directions ─────────────────────────────────────────


@pytest.mark.parametrize("stop,target,bad", [
    (90.0, 110.0, False),   # a correct long bracket
    (110.0, 120.0, True),   # stop ABOVE entry
    (100.0, 110.0, True),   # stop AT entry — fires on the first tick
    (90.0, 90.0, True),     # target BELOW entry
    (90.0, 100.0, True),    # target AT entry
    (None, None, False),    # nothing set is not a violation
    (90.0, None, False),
    (None, 110.0, False),
])
def test_the_long_rule(stop, target, bad):
    out = bracket_is_wrong_side(
        is_short=False, entry=100.0, stop=stop, target=target,
    )
    assert (out is not None) is bad


@pytest.mark.parametrize("stop,target,bad", [
    (110.0, 90.0, False),   # a correct short bracket
    (90.0, 80.0, True),     # stop BELOW entry
    (110.0, 110.0, True),   # target ABOVE entry
])
def test_the_short_rule_is_unchanged(stop, target, bad):
    out = bracket_is_wrong_side(
        is_short=True, entry=100.0, stop=stop, target=target,
    )
    assert (out is not None) is bad


def test_the_two_directions_disagree_on_the_same_numbers():
    """Non-vacuity for the whole file: a bracket that is right for a long is
    wrong for a short, so a rule that ignored `is_short` could not pass both."""
    assert bracket_is_wrong_side(
        is_short=False, entry=100.0, stop=90.0, target=110.0) is None
    assert bracket_is_wrong_side(
        is_short=True, entry=100.0, stop=90.0, target=110.0) is not None


# ── Through the engine ─────────────────────────────────────────────────────


def test_a_market_buy_with_a_stop_above_entry_is_refused():
    """The headline case. Accepted before the fix, then liquidated by the very
    next bracket sweep."""
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    r = sim.submit(
        user_id=uuid4(), ticker="AAPL", side=Side.BUY, quantity=2,
        mandate=_mandate(), order_type=OrderType.MARKET, stop=110.0,
    )
    assert not r.accepted
    assert r.trade is None
    assert "BELOW the entry price" in r.compliance.violations[0]


def test_a_market_buy_with_a_target_below_entry_is_refused():
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    r = sim.submit(
        user_id=uuid4(), ticker="AAPL", side=Side.BUY, quantity=2,
        mandate=_mandate(), order_type=OrderType.MARKET, target=90.0,
    )
    assert not r.accepted
    assert "ABOVE the entry price" in r.compliance.violations[0]


def test_a_correct_long_bracket_still_goes_through():
    """Non-vacuity at the engine boundary."""
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    r = sim.submit(
        user_id=uuid4(), ticker="AAPL", side=Side.BUY, quantity=2,
        mandate=_mandate(), order_type=OrderType.MARKET, stop=90.0, target=120.0,
    )
    assert r.accepted and r.trade is not None


def test_a_resting_buy_is_judged_against_its_FILL_price_not_the_mark():
    """Why the check lives in `_execute_fill` and not in `submit`.

    A buy stop at $110 filling into a $115 mark books at $115 (Rule 2, the worse
    of named and observed). A target of $112 is above the named trigger and
    below the actual fill — so judging it at placement would pass an order that
    is inverted by the time it exists.
    """
    prov = _Pinned({"AAPL": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    r = sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=2,
        mandate=_mandate(), order_type=OrderType.STOP, trigger_price=110.0,
        target=112.0,
    )
    assert r.accepted and r.resting
    order_id = r.resting_order.id

    prov.prices["AAPL"] = 115.0
    with get_session() as s:
        exp = s.get(SimRestingOrderRow, order_id).expires_at
    exp = exp if exp.tzinfo else exp.replace(tzinfo=timezone.utc)
    sweep_resting_orders(
        user_id=user_id, now=exp - timedelta(hours=1), engine=sim,
    )

    with get_session() as s:
        row = s.get(SimRestingOrderRow, order_id)
        assert row.state == "rejected"
        assert "ABOVE the entry price" in row.cancel_reason


def test_a_short_with_an_inverted_bracket_is_still_refused():
    """CR171 §5's own guarantee, re-pinned after the check moved out of
    `_open_short_fill` and into the shared chokepoint."""
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    r = sim.submit(
        user_id=uuid4(), ticker="AAPL", side=Side.SELL, quantity=2,
        mandate=_mandate(long_only=False), order_type=OrderType.MARKET, stop=90.0,
    )
    assert not r.accepted
    assert "ABOVE the entry price" in r.compliance.violations[0]


def test_a_sell_that_CLOSES_a_long_is_not_bracket_checked():
    """An exit carries no bracket of its own — its levels are meaningless, which
    is the same reason `bracket_hit` branches on what the POSITION is rather
    than on the row's side. Checking here would refuse ordinary exits."""
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    user_id = uuid4()
    sim.submit(user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=5,
               mandate=_mandate(), order_type=OrderType.MARKET)
    r = sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.SELL, quantity=5,
        mandate=_mandate(), order_type=OrderType.MARKET, stop=90.0, target=80.0,
    )
    assert r.accepted, "an exit must not be judged as if it opened a position"
