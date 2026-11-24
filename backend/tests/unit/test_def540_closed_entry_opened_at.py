"""DEF540 (AT:B1) — a closed journal entry's `opened_at` is when the POSITION was
opened (the buy), never when the SELL filled.

UAT-JRNL-012 (build 133): Bursa buy 5:35 PM, manual sell 5:36 PM, and the closed
entry's detail read OPENED AT 5:36 PM. `_journal_sell_close` built the closed
trade JSON from the SELL row, whose own `opened_at` is the fill time of the sell.
Covers Bursa and US, and a sell that spans lots.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.core.config import settings
from app.schemas.journal import EntryType
from app.schemas.trade import Side
from app.services.coach_engine import hydrate_coach_mandate
from app.services.journal_store import get_journal_store
from app.services.market_data import Quote
from app.services.sim_engine import SimEngine
from app.services.sim_trade_effects import apply_post_fill_effects
from app.trading_math.markets import Market


class _Pinned:
    name = "pinned"

    def __init__(self, prices: dict[str, float]):
        self.prices = {k.upper(): v for k, v in prices.items()}

    def quote(self, ticker: str) -> Quote | None:
        return Quote(price=self.prices.get(ticker.upper(), 100.0), source="yfinance", change_pct=0.0)

    def history(self, *a, **k):  # pragma: no cover
        return []

    def news(self, *a, **k):  # pragma: no cover
        return []

    def earnings(self, *a, **k):  # pragma: no cover
        return None


def _mandate():
    return hydrate_coach_mandate(
        {"plan": "trader", "single_name_cap_pct": 100.0, "max_open_risk_pct": 100.0}
    )


@pytest.fixture(autouse=True)
def _bursa_on(monkeypatch):
    monkeypatch.setattr(settings, "market_bursa_enabled", True)


def _fill(sim, uid, ticker, side, qty):
    r = sim.submit(user_id=uid, ticker=ticker, side=side, quantity=qty, mandate=_mandate())
    assert r.accepted, r.compliance.violations
    apply_post_fill_effects(user_id=uid, trade=r.trade)
    return r


def _closed_entries(uid):
    entries, _, _ = get_journal_store().list_for_user(uid, entry_type=EntryType.SIM_TRADE)
    return [e for e in sorted(entries, key=lambda e: e.created_at) if "closed" in e.tags]


def _utc(value) -> datetime:
    dt = value if isinstance(value, datetime) else datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _stored_opened_at(sim, uid, trade_id) -> datetime:
    for market in (Market.US, Market.MY):
        for t in sim.list_trades(uid, market=market):
            if t.id == trade_id:
                return _utc(t.opened_at)
    raise AssertionError("trade not in ledger")


@pytest.mark.parametrize("ticker,qty", [("1155.KL", 100), ("AAPL", 10)])
def test_closed_entry_opened_at_is_the_buy_not_the_close(ticker, qty):
    sim = SimEngine(provider=_Pinned({ticker: 10.0}))
    uid = uuid4()
    buy = _fill(sim, uid, ticker, Side.BUY, qty)
    sell = _fill(sim, uid, ticker, Side.SELL, qty)
    (closed,) = _closed_entries(uid)
    t = closed.payload["trade"]
    assert _utc(t["opened_at"]) == _stored_opened_at(sim, uid, buy.trade.id)
    assert _utc(t["closed_at"]) == _stored_opened_at(sim, uid, sell.trade.id)
    assert _utc(t["opened_at"]) < _utc(t["closed_at"])
    # tz-aware on the wire: a naive string reads as local time on the client
    assert datetime.fromisoformat(t["opened_at"]).tzinfo is not None


def test_a_sell_spanning_two_lots_reports_the_earliest_lot_opened_at():
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    uid = uuid4()
    first = _fill(sim, uid, "AAPL", Side.BUY, 5)
    _fill(sim, uid, "AAPL", Side.BUY, 5)
    _fill(sim, uid, "AAPL", Side.SELL, 8)
    (closed,) = _closed_entries(uid)
    assert _utc(closed.payload["trade"]["opened_at"]) == _stored_opened_at(sim, uid, first.trade.id)


def test_a_sell_drawing_only_a_later_lot_reports_that_lots_opened_at():
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    uid = uuid4()
    first = _fill(sim, uid, "AAPL", Side.BUY, 5)
    _fill(sim, uid, "AAPL", Side.SELL, 5)  # FIFO consumes the first lot entirely
    second = _fill(sim, uid, "AAPL", Side.BUY, 5)
    _fill(sim, uid, "AAPL", Side.SELL, 5)
    _, closed = _closed_entries(uid)
    opened = _utc(closed.payload["trade"]["opened_at"])
    assert opened == _stored_opened_at(sim, uid, second.trade.id)
    assert opened != _stored_opened_at(sim, uid, first.trade.id)
