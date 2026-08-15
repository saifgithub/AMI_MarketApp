"""DEF311 — a resting sell must not outlive the shares it was selling.

Nothing connected the two. `SimRestingOrderRow` was touched in five places in
`sim_engine` — reset, placement, list, cancel, `clear()` — and neither
`manual_close` nor `_apply_sell_row` was one of them. So a stop-loss survived the
position it protected, and the three-case sell rule then read `held == 0` and
**opened a short**: unbounded loss, in an account the user believes is flat, and
with CR187 shipping, a push reading *"Sold 10 NVDA at $90.00"* that looks exactly
like the stop working.

The fix sits in `_apply_sell_row` rather than in `manual_close`, and the first
test is why: three different paths reduce a holding, and a fix in any one of them
leaves the other two.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select

from app.db import get_session
from app.db.models import SimRestingOrderRow, SimShortPositionRow
from app.schemas.trade import OrderType, Side
from app.services.coach_engine import hydrate_coach_mandate
from app.services.market_data import Quote
from app.services.sim_engine import SimEngine
from app.services.sim_resting_orders import sweep_resting_orders


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


def _mandate(**over):
    base = {"plan": "trader", "single_name_cap_pct": 100.0, "max_open_risk_pct": 100.0}
    base.update(over)
    return hydrate_coach_mandate(base)


def _row(order_id) -> SimRestingOrderRow:
    with get_session() as s:
        return s.get(SimRestingOrderRow, order_id)


def _shorts(user_id):
    with get_session() as s:
        return list(s.execute(
            select(SimShortPositionRow).where(
                SimShortPositionRow.user_id == user_id,
            )
        ).scalars().all())


def _session_now(order_id) -> datetime:
    exp = _row(order_id).expires_at
    exp = exp if exp.tzinfo else exp.replace(tzinfo=timezone.utc)
    return exp - timedelta(hours=1)


def _buy(sim, user_id, ticker, qty):
    r = sim.submit(user_id=user_id, ticker=ticker, side=Side.BUY, quantity=qty,
                   mandate=_mandate(), order_type=OrderType.MARKET)
    assert r.accepted and r.trade is not None
    return r.trade


def _rest_sell_stop(sim, user_id, *, ticker, quantity, trigger):
    r = sim.submit(
        user_id=user_id, ticker=ticker, side=Side.SELL, quantity=quantity,
        mandate=_mandate(), order_type=OrderType.STOP, trigger_price=trigger,
    )
    assert r.accepted and r.resting, "precondition: the order must have rested"
    return r.resting_order.id


# ── The three paths that reduce a holding ──────────────────────────────────


def test_manual_close_retires_the_stop_that_was_protecting_the_position():
    """The reported sequence. Before the fix this order stayed `working`, and the
    next time the price reached $90 it opened a short."""
    prov = _Pinned({"NVDA": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    trade = _buy(sim, user_id, "NVDA", 10)
    order_id = _rest_sell_stop(sim, user_id, ticker="NVDA", quantity=10, trigger=90.0)

    sim.manual_close(user_id, trade.id)

    row = _row(order_id)
    assert row.state == "cancelled"
    # Non-NULL reason: the SYSTEM did this, which is the invariant the client's
    # copy distinguishes "you cancelled it" from "it was taken away" on.
    assert row.cancel_reason is not None
    assert "NVDA" in row.cancel_reason


def test_a_market_sell_of_the_whole_holding_retires_it_too():
    prov = _Pinned({"NVDA": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    _buy(sim, user_id, "NVDA", 10)
    order_id = _rest_sell_stop(sim, user_id, ticker="NVDA", quantity=10, trigger=90.0)

    r = sim.submit(user_id=user_id, ticker="NVDA", side=Side.SELL, quantity=10,
                   mandate=_mandate(), order_type=OrderType.MARKET)
    assert r.accepted

    assert _row(order_id).state == "cancelled"


def test_a_bracket_stop_out_retires_it_too():
    """`evaluate_outcomes` is the third path, and the one the user never
    triggers by hand — so it is the one a fix in `manual_close` would miss."""
    prov = _Pinned({"NVDA": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    r = sim.submit(user_id=user_id, ticker="NVDA", side=Side.BUY, quantity=10,
                   mandate=_mandate(), order_type=OrderType.MARKET, stop=95.0)
    assert r.accepted
    order_id = _rest_sell_stop(sim, user_id, ticker="NVDA", quantity=10, trigger=90.0)

    prov.prices["NVDA"] = 94.0  # through the bracket stop
    sim.evaluate_outcomes(user_id)

    assert _row(order_id).state == "cancelled"


# ── The outcome the defect actually produced ───────────────────────────────


def test_the_stop_loss_no_longer_becomes_a_short():
    """End to end, through the real sweep. This is the failure stated as a test:
    close the position, let the price reach the stop, and confirm no short was
    opened and no fill happened."""
    prov = _Pinned({"NVDA": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    trade = _buy(sim, user_id, "NVDA", 10)
    order_id = _rest_sell_stop(sim, user_id, ticker="NVDA", quantity=10, trigger=90.0)

    sim.manual_close(user_id, trade.id)
    prov.prices["NVDA"] = 85.0
    sweep_resting_orders(user_id=user_id, now=_session_now(order_id), engine=sim)

    assert _shorts(user_id) == [], "a stop-loss must never open a short"
    assert _row(order_id).fill_price is None


# ── Partials, and what must NOT be retired ─────────────────────────────────


def test_a_partial_sell_retires_an_order_that_can_no_longer_be_covered():
    """Sell 6 of 10 and a resting sell for 10 can never fill — it would hit the
    cross-zero refusal at trigger. Retiring it now says so while the user is
    still looking, instead of hours later."""
    prov = _Pinned({"NVDA": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    _buy(sim, user_id, "NVDA", 10)
    order_id = _rest_sell_stop(sim, user_id, ticker="NVDA", quantity=10, trigger=90.0)

    sim.submit(user_id=user_id, ticker="NVDA", side=Side.SELL, quantity=6,
               mandate=_mandate(), order_type=OrderType.MARKET)

    row = _row(order_id)
    assert row.state == "cancelled"
    assert "4" in row.cancel_reason


def test_a_partial_sell_leaves_an_order_it_can_still_cover():
    """Non-vacuity. Sell 6 of 10, and a resting sell for 4 is still good — the
    fix must not retire every order on the ticker."""
    prov = _Pinned({"NVDA": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    _buy(sim, user_id, "NVDA", 10)
    order_id = _rest_sell_stop(sim, user_id, ticker="NVDA", quantity=4, trigger=90.0)

    sim.submit(user_id=user_id, ticker="NVDA", side=Side.SELL, quantity=6,
               mandate=_mandate(), order_type=OrderType.MARKET)

    assert _row(order_id).state == "working"


def test_a_sell_on_one_ticker_leaves_another_ticker_alone():
    prov = _Pinned({"NVDA": 100.0, "AAPL": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    _buy(sim, user_id, "NVDA", 10)
    _buy(sim, user_id, "AAPL", 10)
    aapl_order = _rest_sell_stop(sim, user_id, ticker="AAPL", quantity=10, trigger=90.0)

    sim.submit(user_id=user_id, ticker="NVDA", side=Side.SELL, quantity=10,
               mandate=_mandate(), order_type=OrderType.MARKET)

    assert _row(aapl_order).state == "working"


def test_a_resting_BUY_is_never_retired_by_a_sell():
    """A buy is not covered by shares and has nothing to orphan."""
    prov = _Pinned({"NVDA": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    _buy(sim, user_id, "NVDA", 10)
    r = sim.submit(user_id=user_id, ticker="NVDA", side=Side.BUY, quantity=2,
                   mandate=_mandate(), order_type=OrderType.LIMIT, limit_price=80.0)
    assert r.accepted and r.resting
    buy_order = r.resting_order.id

    sim.submit(user_id=user_id, ticker="NVDA", side=Side.SELL, quantity=10,
               mandate=_mandate(), order_type=OrderType.MARKET)

    assert _row(buy_order).state == "working"
