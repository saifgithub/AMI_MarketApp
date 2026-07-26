"""Tests for CR029 per-lot cost-basis / FIFO reconstruction.

Three layers:
  * pure `compute_lots_fifo` — the deterministic FIFO reconstruction math,
    including the CR029 acceptance case and the self-closed-buy reconciliation;
  * `SimEngine.holding_lots` — the DB read + delegation;
  * GET /v1/sim/lots/{user_id}/{ticker} — the authenticated route contract
    the mobile per-lot cards mirror.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.api.sim import router as sim_router
from app.services import market_data as _md
from app.services.coach_engine import hydrate_coach_mandate
from app.services.cost_basis_lots import Lot, compute_lots_fifo
from app.services.sim_engine import SimEngine, get_sim_engine
from app.schemas.trade import Side

_BASE = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)


@dataclass
class _Trade:
    """Duck-typed stand-in for sim_engine.SimTrade (only the read fields)."""

    side: str
    quantity: float
    entry_price: float
    opened_at: datetime
    id: str = ""
    status: str = "open"
    realised_pnl: float = 0.0


def _t(side: str, qty: float, price: float, minute: int, **kw) -> _Trade:
    return _Trade(
        side=side,
        quantity=qty,
        entry_price=price,
        opened_at=_BASE + timedelta(minutes=minute),
        id=kw.pop("id", f"t{minute}"),
        **kw,
    )


# ── Pure reconstruction ─────────────────────────────────────────────────────


def test_acceptance_case_partial_close_splits_pnl():
    """CR029 acceptance: buy 100@150, buy 50@155, sell 60@160 → lot 1
    partially closed with the correct realised-P&L split."""
    trades = [
        _t("buy", 100, 150, 0, id="b1"),
        _t("buy", 50, 155, 1, id="b2"),
        _t("sell", 60, 160, 2, id="s1"),
    ]
    lots = compute_lots_fifo(trades, current_price=160.0)
    assert len(lots) == 2

    lot1, lot2 = lots
    assert lot1.entry_trade_id == "b1"
    assert lot1.entry_price == 150
    assert lot1.quantity == 100
    assert lot1.quantity_closed == 60
    assert lot1.quantity_open == 40
    assert lot1.realised_pnl == 600.0  # (160-150)*60
    assert lot1.unrealised_pnl == 400.0  # (160-150)*40
    assert lot1.status == "partially_closed"

    assert lot2.entry_trade_id == "b2"
    assert lot2.quantity_open == 50
    assert lot2.quantity_closed == 0
    assert lot2.realised_pnl == 0.0
    assert lot2.unrealised_pnl == 250.0  # (160-155)*50
    assert lot2.status == "open"


def test_empty_history_returns_no_lots():
    assert compute_lots_fifo([], current_price=100.0) == []


def test_single_open_buy_marks_unrealised():
    lots = compute_lots_fifo([_t("buy", 10, 100, 0)], current_price=110.0)
    assert len(lots) == 1
    assert lots[0].status == "open"
    assert lots[0].quantity_open == 10
    assert lots[0].realised_pnl == 0.0
    assert lots[0].unrealised_pnl == 100.0  # (110-100)*10


def test_no_current_price_leaves_unrealised_none():
    lots = compute_lots_fifo([_t("buy", 10, 100, 0)], current_price=None)
    assert lots[0].unrealised_pnl is None


def test_self_closed_buy_uses_recorded_pnl_and_never_enters_queue():
    """A stop/target/manual-closed buy row carries its own realised_pnl and is
    a fully-closed lot; a *later* sell must not draw down its shares."""
    trades = [
        _t("buy", 10, 100, 0, id="won", status="won", realised_pnl=320.0),
        _t("buy", 5, 200, 1, id="open"),
        _t("sell", 5, 210, 2, id="sell"),
    ]
    lots = compute_lots_fifo(trades, current_price=210.0)
    won, still_open = lots

    # Self-closed lot: fully closed, recorded P&L, no unrealised even with price.
    assert won.status == "closed"
    assert won.quantity_open == 0
    assert won.quantity_closed == 10
    assert won.realised_pnl == 320.0
    assert won.unrealised_pnl is None

    # The sell drew from the *open* lot, not the already-closed one.
    assert still_open.entry_trade_id == "open"
    assert still_open.quantity_closed == 5
    assert still_open.quantity_open == 0
    assert still_open.realised_pnl == 50.0  # (210-200)*5


def test_oversell_closes_all_available_without_crashing():
    """Selling more than is held closes everything available; the shortfall is
    logged (degrade loudly), not raised."""
    lots = compute_lots_fifo(
        [_t("buy", 10, 100, 0), _t("sell", 15, 120, 1)], current_price=120.0
    )
    assert len(lots) == 1
    assert lots[0].quantity_open == 0
    assert lots[0].quantity_closed == 10
    assert lots[0].realised_pnl == 200.0  # (120-100)*10
    assert lots[0].status == "closed"


def test_multiple_sells_thread_through_the_same_lot():
    trades = [
        _t("buy", 100, 150, 0),
        _t("sell", 30, 160, 1),
        _t("sell", 30, 170, 2),
    ]
    lots = compute_lots_fifo(trades, current_price=170.0)
    assert len(lots) == 1
    lot = lots[0]
    assert lot.quantity_closed == 60
    assert lot.quantity_open == 40
    # 30*(160-150) + 30*(170-150) = 300 + 600
    assert lot.realised_pnl == 900.0


def test_sell_spills_across_lot_boundary():
    """A sell larger than the oldest lot closes it and spills into the next."""
    trades = [
        _t("buy", 40, 150, 0, id="b1"),
        _t("buy", 40, 155, 1, id="b2"),
        _t("sell", 60, 160, 2),
    ]
    lots = compute_lots_fifo(trades, current_price=160.0)
    lot1, lot2 = lots
    assert lot1.quantity_open == 0 and lot1.quantity_closed == 40
    assert lot1.realised_pnl == 400.0  # 40*(160-150)
    assert lot2.quantity_open == 20 and lot2.quantity_closed == 20
    assert lot2.realised_pnl == 100.0  # 20*(160-155)
    assert lot1.status == "closed"
    assert lot2.status == "partially_closed"


def test_out_of_order_input_is_sorted_chronologically():
    trades = [
        _t("sell", 60, 160, 2),
        _t("buy", 100, 150, 0, id="b1"),
        _t("buy", 50, 155, 1, id="b2"),
    ]
    lots = compute_lots_fifo(trades, current_price=160.0)
    assert [lot.entry_trade_id for lot in lots] == ["b1", "b2"]
    assert lots[0].realised_pnl == 600.0


def test_side_enum_is_accepted_like_a_string():
    """compute_lots_fifo normalises a Side enum the same as a raw string."""
    trades = [
        _Trade(side=Side.BUY, quantity=10, entry_price=100, opened_at=_BASE, id="b"),
        _Trade(
            side=Side.SELL, quantity=4, entry_price=110,
            opened_at=_BASE + timedelta(minutes=1), id="s",
        ),
    ]
    lots = compute_lots_fifo(trades, current_price=110.0)
    assert lots[0].quantity_closed == 4
    assert lots[0].realised_pnl == 40.0


def test_lot_is_json_serialisable_shape():
    lot = compute_lots_fifo([_t("buy", 10, 100, 0)], current_price=110.0)[0]
    d = lot._asdict()
    assert set(d.keys()) == {
        "entry_trade_id", "entry_date", "entry_price", "quantity",
        "quantity_open", "quantity_closed", "realised_pnl",
        "unrealised_pnl", "status",
    }
    assert isinstance(d["entry_date"], str) and d["entry_date"]


# ── Engine + endpoint ───────────────────────────────────────────────────────


class _ConstProvider:
    """Provider stub that fills and marks every ticker at a fixed price."""

    name = "fake"

    def __init__(self, price: float = 100.0) -> None:
        self.price = price

    def quote(self, ticker: str):
        return _md.Quote(price=self.price, source=self.name)

    def get_price(self, ticker: str):
        return self.price

    def history(self, ticker: str, period: str):
        return None

    def news(self, ticker: str, limit: int = 5):
        return None

    def earnings(self, ticker: str):
        return None


def _engine_with_buy(user_id: UUID, qty: float, price: float) -> SimEngine:
    sim = SimEngine(provider=_ConstProvider(price))
    mandate = hydrate_coach_mandate({"plan": "trader"})
    result = sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=qty, mandate=mandate,
    )
    assert result.accepted, result.compliance.violations
    return sim


def test_holding_lots_reconstructs_from_the_trade_ledger():
    user_id = uuid4()
    sim = _engine_with_buy(user_id, qty=8, price=100.0)
    lots = sim.holding_lots(user_id, "AAPL", current_price=100.0)
    assert len(lots) == 1
    assert isinstance(lots[0], Lot)
    assert lots[0].quantity_open == 8
    assert lots[0].status == "open"
    # A ticker the user never traded reconstructs to no lots.
    assert sim.holding_lots(user_id, "MSFT", current_price=100.0) == []


def test_lots_endpoint_returns_contract_and_enforces_ownership():
    user_id = uuid4()
    sim = _engine_with_buy(user_id, qty=8, price=100.0)

    @dataclass
    class _U:
        id: UUID

    app = FastAPI()
    app.include_router(sim_router)
    app.dependency_overrides[get_sim_engine] = lambda: sim
    app.dependency_overrides[get_current_user] = lambda: _U(id=user_id)
    client = TestClient(app, raise_server_exceptions=False)

    r = client.get(f"/v1/sim/lots/{user_id}/AAPL")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ticker"] == "AAPL"
    assert body["current_price"] == 100.0
    assert body["price_source"] == "fake"
    assert set(body["totals"].keys()) == {
        "realised_pnl", "unrealised_pnl", "quantity_open",
    }
    assert len(body["lots"]) == 1
    assert body["lots"][0]["quantity_open"] == 8
    assert body["totals"]["quantity_open"] == 8

    # Another user cannot read this user's lots.
    app.dependency_overrides[get_current_user] = lambda: _U(id=uuid4())
    r = client.get(f"/v1/sim/lots/{user_id}/AAPL")
    assert r.status_code == 403
