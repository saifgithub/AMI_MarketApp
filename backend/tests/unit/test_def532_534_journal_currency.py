"""DEF532 / DEF534 — journal text in the book's own currency, a sell that closes a
position journals as a CLOSED trade, bracket closes of the MYR book reach the
Journal, and money in server copy carries thousands separators.

No network. The engine runs against a pinned quote provider.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.core.config import settings
from app.schemas.journal import EntryType
from app.schemas.trade import Side
from app.services.coach_engine import hydrate_coach_mandate
from app.services.journal_store import get_journal_store
from app.services.market_data import Quote
from app.services.sim_engine import SimEngine
from app.services.sim_resting_orders import sweep_resting_orders
from app.services.sim_trade_effects import apply_post_fill_effects
from app.trading_math.markets import Market, format_money

KL = ZoneInfo("Asia/Kuala_Lumpur")


class _Pinned:
    name = "pinned"

    def __init__(self, prices: dict[str, float]):
        self.prices = {k.upper(): v for k, v in prices.items()}

    def set(self, ticker: str, price: float) -> None:
        self.prices[ticker.upper()] = price

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


@pytest.fixture
def bursa_on(monkeypatch):
    monkeypatch.setattr(settings, "market_bursa_enabled", True)


def _fill(sim, uid, ticker, side, qty, **kw):
    r = sim.submit(user_id=uid, ticker=ticker, side=side, quantity=qty, mandate=_mandate(), **kw)
    assert r.accepted, r.compliance.violations
    apply_post_fill_effects(user_id=uid, trade=r.trade)
    return r


def _entries(uid):
    entries, _, _ = get_journal_store().list_for_user(uid, entry_type=EntryType.SIM_TRADE)
    return sorted(entries, key=lambda e: e.created_at)


@pytest.mark.parametrize(
    "amount,market,signed,expected",
    [
        (11620.0, Market.US, False, "$11,620.00"),
        (-8.08, Market.US, True, "-$8.08"),
        (11.0, Market.US, True, "+$11.00"),
        (-8.08, Market.US, False, "-$8.08"),
        (11.0, Market.MY, True, "+RM11.00"),
        (-1234.5, Market.MY, True, "-RM1,234.50"),
        (0.0, Market.US, True, "+$0.00"),
        (-0.001, Market.US, True, "+$0.00"),
        (-0.0, Market.US, False, "$0.00"),
    ],
)
def test_format_money_is_the_house_format(amount, market, signed, expected):
    assert format_money(amount, market, signed=signed) == expected


def test_cash_refusal_has_thousands_separators_def534(bursa_on):
    sim = SimEngine(provider=_Pinned({"AAPL": 400.0, "MSFT": 400.0}))
    uid = uuid4()
    _fill(sim, uid, "AAPL", Side.BUY, 24)  # $9,600 of the $10,000 book
    r = sim.submit(user_id=uid, ticker="MSFT", side=Side.BUY, quantity=20, mandate=_mandate())
    assert not r.accepted
    msg = r.compliance.violations[0]
    assert msg == "insufficient cash: need $8,000.00, have $400.00", msg


def test_bursa_buy_is_journaled_in_ringgit_def532(bursa_on):
    sim = SimEngine(provider=_Pinned({"1155.KL": 10.10}))
    uid = uuid4()
    _fill(sim, uid, "1155.KL", Side.BUY, 100, stop=9.00, target=12.00)
    (e,) = _entries(uid)
    assert e.title == "BUY 100 1155.KL @ RM10.10"
    assert e.summary == "Opened at RM10.10. Stop RM9.00. Target RM12.00."
    assert "$" not in e.title + e.summary


def test_bursa_sell_of_the_whole_position_journals_a_closed_entry_in_ringgit(bursa_on):
    prov = _Pinned({"1155.KL": 10.00})
    sim = SimEngine(provider=prov)
    uid = uuid4()
    _fill(sim, uid, "1155.KL", Side.BUY, 100)
    prov.set("1155.KL", 11.00)
    sell = _fill(sim, uid, "1155.KL", Side.SELL, 100)
    opened, closed = _entries(uid)
    assert opened.title == "BUY 100 1155.KL @ RM10.00"
    assert closed.title == "Closed 1155.KL (MANUAL) — +RM100.00"
    assert closed.summary == "Sold 100 at RM11.00."
    assert closed.reference_id == sell.trade.id
    assert closed.outcome == "win"
    t = closed.payload["trade"]
    assert t["status"] == "closed"
    assert t["closed_price"] == 11.0
    assert t["realised_pnl"] == 100.0
    assert closed.payload["outcome"]["realised_pnl"] == 100.0


def test_us_sell_journals_a_closed_entry_with_a_leading_minus_def532(bursa_on):
    prov = _Pinned({"AAPL": 100.0})
    sim = SimEngine(provider=prov)
    uid = uuid4()
    _fill(sim, uid, "AAPL", Side.BUY, 10)
    prov.set("AAPL", 91.92)
    _fill(sim, uid, "AAPL", Side.SELL, 10)
    _, closed = _entries(uid)
    assert closed.title == "Closed AAPL (MANUAL) — -$80.80"
    assert closed.outcome == "loss"


def test_partial_sell_says_what_is_still_held(bursa_on):
    prov = _Pinned({"1155.KL": 10.00})
    sim = SimEngine(provider=prov)
    uid = uuid4()
    _fill(sim, uid, "1155.KL", Side.BUY, 300)
    prov.set("1155.KL", 10.50)
    _fill(sim, uid, "1155.KL", Side.SELL, 100)
    _, closed = _entries(uid)
    assert closed.summary == "Sold 100 at RM10.50. 200 still held."
    assert closed.title == "Closed 1155.KL (MANUAL) — +RM50.00"


def test_a_sell_the_ledger_cannot_place_keeps_its_opened_entry():
    """No stored row / no lots to draw from: nothing was closed, so the entry
    must not claim a realised P&L it cannot compute."""
    from datetime import timezone

    from app.services.sim_engine import SimTrade

    uid = uuid4()
    sell = SimTrade(
        id=uuid4(), user_id=uid, portfolio_id=uuid4(), ticker="AAPL", side=Side.SELL,
        quantity=5, entry_price=100.0, stop=None, target=None, horizon_days=None,
        opened_at=datetime.now(timezone.utc),
    )
    apply_post_fill_effects(user_id=uid, trade=sell)
    (e,) = _entries(uid)
    assert e.title == "SELL 5 AAPL @ $100.00"
    assert "closed" not in e.tags


def test_manual_close_title_has_house_sign_format(bursa_on):
    from app.services.sim_trade_effects import journal_manual_close

    prov = _Pinned({"AAPL": 100.0})
    sim = SimEngine(provider=prov)
    uid = uuid4()
    r = _fill(sim, uid, "AAPL", Side.BUY, 10)
    prov.set("AAPL", 111.0)
    closed = sim.manual_close(uid, r.trade.id)
    journal_manual_close(uid, closed)
    last = _entries(uid)[-1]
    assert last.title == "Closed AAPL (MANUAL) — +$110.00"
    assert last.summary == "Closed at $111.00."


def test_my_bracket_close_by_the_sweep_is_journaled_in_ringgit(bursa_on):
    prov = _Pinned({"1155.KL": 10.00})
    sim = SimEngine(provider=prov)
    uid = uuid4()
    _fill(sim, uid, "1155.KL", Side.BUY, 100, stop=9.00)
    prov.set("1155.KL", 8.50)
    session = datetime(2026, 12, 1, 15, 0, tzinfo=KL)
    assert sweep_resting_orders(user_id=uid, now=session, engine=sim)["brackets_closed"] == 1
    closed = [e for e in _entries(uid) if "closed" in e.tags]
    assert len(closed) == 1
    e = closed[0]
    assert e.title == "Closed 1155.KL (LOST) — -RM150.00"
    assert e.summary == "Stop hit at RM8.50."
    assert e.payload["trade"]["realised_pnl"] == -150.0
