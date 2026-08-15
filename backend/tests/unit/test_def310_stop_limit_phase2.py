"""DEF310 — a triggered stop-limit is a LIMIT, on every sweep after the first.

`_fill_triggered` read `order.named_price` unconditionally, which returns the
**trigger** for a stop-limit. That is right on the first sweep, while the order
is `working`. It is wrong on every sweep after, because the phase-1 block only
runs `if state == "working"` — so a `triggered` stop-limit fell straight through
to a trigger comparison, matched, claimed and filled, with its limit price never
consulted.

The case it broke is CR170's own worked example, and acceptance 6's second half:

    sell stop-limit, trigger $90, limit $88, price gaps to $85
      sweep 1  triggers, correctly declines to fill
      sweep 2  fills at $85 — three dollars below the floor the user set

That is the classic stop-limit failure the CR says the type is in the curriculum
to teach, so filling it is not a rounding error; it is the simulator teaching the
opposite of the lesson.

**Why it survived.** The only test of the two-phase rule ran over the pure
function in `test_cr170_order_pricing.py`. The sweep's own test file opens by
warning about exactly this gap — *"that file proves the arithmetic; this one
proves the arithmetic is the one that runs"* — and acceptance 6's stop-limit
clause was never given a test there. Every test below sweeps at least twice,
because one sweep is what the defect looks correct under.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.db import get_session
from app.db.models import SimRestingOrderRow, SimTradeRow
from app.schemas.trade import OrderType, Side
from app.services.coach_engine import hydrate_coach_mandate
from app.services.market_data import Quote
from app.services.sim_engine import SimEngine
from app.services.sim_resting_orders import sweep_resting_orders
from sqlalchemy import select


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


def _session_now(order_id) -> datetime:
    exp = _row(order_id).expires_at
    exp = exp if exp.tzinfo else exp.replace(tzinfo=timezone.utc)
    return exp - timedelta(hours=1)


def _trades(user_id):
    with get_session() as s:
        return list(s.execute(
            select(SimTradeRow).where(SimTradeRow.user_id == user_id)
        ).scalars().all())


def _hold(sim, user_id, ticker, qty):
    r = sim.submit(user_id=user_id, ticker=ticker, side=Side.BUY, quantity=qty,
                   mandate=_mandate(), order_type=OrderType.MARKET)
    assert r.accepted and r.trade is not None
    return r


def _rest_stop_limit(sim, user_id, *, ticker, side, quantity, trigger, limit):
    r = sim.submit(
        user_id=user_id, ticker=ticker, side=side, quantity=quantity,
        mandate=_mandate(), order_type=OrderType.STOP_LIMIT,
        trigger_price=trigger, limit_price=limit,
    )
    assert r.accepted and r.resting, "precondition: the order must have rested"
    return r.resting_order.id


def test_a_sell_stop_limit_that_gaps_through_its_limit_never_fills():
    """The defect, as CR170's own worked example.

    Trigger $90, limit $88, price gaps to $85. The order triggers and must then
    rest forever: $85 is below the floor the user named, and a sell limit at $88
    does not fill at $85.
    """
    prov = _Pinned({"NVDA": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    _hold(sim, user_id, "NVDA", 5)
    order_id = _rest_stop_limit(
        sim, user_id, ticker="NVDA", side=Side.SELL, quantity=5,
        trigger=90.0, limit=88.0,
    )
    prov.prices["NVDA"] = 85.0
    at = _session_now(order_id)

    sweep_resting_orders(user_id=user_id, now=at, engine=sim)
    assert _row(order_id).state == "triggered", "sweep 1 was already correct"

    # The sweep the defect lived on.
    for _ in range(3):
        sweep_resting_orders(user_id=user_id, now=at, engine=sim)

    assert _row(order_id).state == "triggered"
    assert _row(order_id).fill_price is None
    # Only the opening market buy exists — no exit was booked.
    assert [t.side for t in _trades(user_id)] == ["buy"]


def test_a_sell_stop_limit_fills_at_its_limit_when_the_price_comes_back():
    """Non-vacuity, and the other half of the mechanic.

    The same order must still fill once the market returns to the limit — the
    fix must not be "a triggered stop-limit never fills".
    """
    prov = _Pinned({"NVDA": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    _hold(sim, user_id, "NVDA", 5)
    order_id = _rest_stop_limit(
        sim, user_id, ticker="NVDA", side=Side.SELL, quantity=5,
        trigger=90.0, limit=88.0,
    )
    at = _session_now(order_id)

    prov.prices["NVDA"] = 85.0
    sweep_resting_orders(user_id=user_id, now=at, engine=sim)
    assert _row(order_id).state == "triggered"

    prov.prices["NVDA"] = 89.0  # back above the limit
    sweep_resting_orders(user_id=user_id, now=at, engine=sim)

    row = _row(order_id)
    assert row.state == "filled"
    # Rule 2 for a sell: the worse of named and observed. min(88, 89) = 88.
    assert float(row.fill_price) == 88.0


def test_a_buy_stop_limit_that_gaps_above_its_limit_never_fills():
    """The mirror. Buy stop-limit, trigger $110, limit $112, price gaps to $120:
    triggers, then rests, because a buy limit at $112 does not fill at $120."""
    prov = _Pinned({"AAPL": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    order_id = _rest_stop_limit(
        sim, user_id, ticker="AAPL", side=Side.BUY, quantity=2,
        trigger=110.0, limit=112.0,
    )
    prov.prices["AAPL"] = 120.0
    at = _session_now(order_id)

    sweep_resting_orders(user_id=user_id, now=at, engine=sim)
    sweep_resting_orders(user_id=user_id, now=at, engine=sim)
    sweep_resting_orders(user_id=user_id, now=at, engine=sim)

    assert _row(order_id).state == "triggered"
    assert _trades(user_id) == []


def test_a_plain_stop_is_untouched_by_the_fix():
    """A STOP has one phase and must still fill on the trigger, with slippage.

    The fix branches on `state == "triggered"` for STOP_LIMIT only; this pins
    that a plain stop did not get caught in it.
    """
    prov = _Pinned({"AAPL": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    r = sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=2,
        mandate=_mandate(), order_type=OrderType.STOP, trigger_price=110.0,
    )
    assert r.accepted and r.resting
    order_id = r.resting_order.id

    prov.prices["AAPL"] = 115.0
    sweep_resting_orders(user_id=user_id, now=_session_now(order_id), engine=sim)

    row = _row(order_id)
    assert row.state == "filled"
    # Rule 2 for a buy: the worse of named and observed. max(110, 115) = 115 —
    # slippage, which is what a stop exists to teach.
    assert float(row.fill_price) == 115.0
