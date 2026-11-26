"""DEF552 (AT:B1) - a buy that SELL orders have fully taken reads CLOSED in History.

Android build 137: two 6888.KL round trips (buy 100, sell 100) left positions at 0
and the Journal correct, but every History row read OPEN and the header "0 CLOSED,
WON 0, LOST 0". Since CR188 a sell order is the only manual exit and the buy row it
consumes keeps `status='open'` by design (DEF316), so a History keyed on `status`
could never see a hand-closed trade, in either book. `GET /v1/sim/trades` now adds
`lot_close` (net of fees, DEF542) to exactly those rows; the ledger's own `status`
and `realised_pnl` are untouched.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.sim import get_sim_engine, router
from app.core.config import settings
from app.schemas.trade import Side
from app.services.auth_service import AuthService
from app.services.coach_engine import hydrate_coach_mandate
from app.services.cost_basis_lots import hand_closed_lots
from app.services.market_data import Quote
from app.services.sim_engine import SimEngine


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


@pytest.fixture(autouse=True)
def _bursa_on(monkeypatch):
    monkeypatch.setattr(settings, "market_bursa_enabled", True)


def _mandate():
    return hydrate_coach_mandate(
        {"plan": "trader", "single_name_cap_pct": 100.0, "max_open_risk_pct": 100.0}
    )


def _setup(prices):
    sim = SimEngine(provider=_Pinned(prices))
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_sim_engine] = lambda: sim
    user, token, _ = AuthService().ensure_anonymous(device_user_id=None)
    return sim, TestClient(app, raise_server_exceptions=False), user, {
        "Authorization": f"Bearer {token}"
    }


def _fill(sim, uid, ticker, side, qty):
    r = sim.submit(user_id=uid, ticker=ticker, side=side, quantity=qty, mandate=_mandate())
    assert r.accepted, r.compliance.violations
    return r


def _rows(c, user, h, **params):
    r = c.get(f"/v1/sim/trades/{user.id}", params=params, headers=h)
    assert r.status_code == 200, r.text
    return r.json()["trades"]


def test_bursa_hand_closed_buy_carries_net_lot_close():
    sim, c, user, h = _setup({"6888.KL": 1.58})
    _fill(sim, user.id, "6888.KL", Side.BUY, 100)
    _fill(sim, user.id, "6888.KL", Side.SELL, 100)

    rows = _rows(c, user, h, market="MY")
    buy = next(r for r in rows if r["side"] == "buy")
    sell = next(r for r in rows if r["side"] == "sell")
    # the ledger keeps its by-design truth
    assert buy["status"] == "open" and buy["realised_pnl"] == 0.0
    # ... and the row says what happened: break-even on price, -RM16.42 of fees
    lc = buy["lot_close"]
    assert lc["realised_pnl"] == -16.42
    assert lc["fees"] == 16.42
    assert lc["closed_price"] == 1.58
    assert lc["closed_at"] is not None
    assert "lot_close" not in sell


def test_partly_sold_buy_is_not_closed():
    sim, c, user, h = _setup({"6888.KL": 1.58})
    _fill(sim, user.id, "6888.KL", Side.BUY, 200)
    _fill(sim, user.id, "6888.KL", Side.SELL, 100)
    buy = next(r for r in _rows(c, user, h, market="MY") if r["side"] == "buy")
    assert "lot_close" not in buy


def test_us_round_trip_is_closed_too_and_untouched_rows_keep_their_shape():
    sim, c, user, h = _setup({"AAPL": 100.0, "MSFT": 100.0})
    _fill(sim, user.id, "AAPL", Side.BUY, 5)
    _fill(sim, user.id, "AAPL", Side.SELL, 5)
    _fill(sim, user.id, "MSFT", Side.BUY, 5)
    rows = _rows(c, user, h)
    aapl = next(r for r in rows if r["ticker"] == "AAPL" and r["side"] == "buy")
    msft = next(r for r in rows if r["ticker"] == "MSFT")
    assert aapl["lot_close"]["realised_pnl"] == 0.0 and aapl["lot_close"]["fees"] == 0.0
    assert "lot_close" not in msft  # a still-held buy: exact pre-DEF552 key set


def test_page_of_the_ledger_still_sees_earlier_buys_for_fifo():
    sim, c, user, h = _setup({"6888.KL": 1.58})
    _fill(sim, user.id, "6888.KL", Side.BUY, 100)
    _fill(sim, user.id, "6888.KL", Side.SELL, 100)
    # limit=1 returns only the newest row (the sell): nothing to annotate, no error
    rows = _rows(c, user, h, market="MY", limit=1)
    assert [r["side"] for r in rows] == ["sell"]
    # limit=2 returns both; the buy's lot needs the sell that is also on the page
    rows = _rows(c, user, h, market="MY", limit=2)
    assert any("lot_close" in r for r in rows if r["side"] == "buy")


class _T:
    def __init__(self, id, side, qty, price, at, fee=None, status="open"):
        from datetime import datetime, timedelta, timezone

        self.id, self.side, self.quantity, self.entry_price = id, side, qty, price
        self.opened_at = datetime(2026, 11, 26, 3, 0, tzinfo=timezone.utc) + timedelta(minutes=at)
        self.toll_charged, self.status = fee, status
        self.realised_pnl, self.closed_at = 0.0, None


def test_two_sells_close_one_lot_and_fees_follow_the_shares():
    out = hand_closed_lots([
        _T("b", "buy", 200, 1.0, 0, fee=8.42),
        _T("s1", "sell", 100, 1.2, 1, fee=8.21),
        _T("s2", "sell", 100, 1.4, 2, fee=8.21),
    ])
    lc = out["b"]
    assert lc.closed_price == 1.3
    # gross +60.00 (20 + 40); fees 8.42 + 8.21 + 8.21
    assert lc.fees == 24.84
    assert lc.realised_pnl == round(60.0 - 24.84, 2)


def test_self_closed_buy_is_not_repeated():
    out = hand_closed_lots([_T("b", "buy", 10, 1.0, 0, status="lost")])
    assert out == {}
