"""DEF541 — the open-risk cap counts only the shares a lot still holds.

`_risk_limit_context` summed risk over every `open` BUY row carrying a stop, but a
sold lot's BUY row stays `open` by design (DEF166/DEF316), so a flat book kept
paying risk for stops on shares it no longer held (measured: 0.40% on a flat Bursa
book after buy 100 with a stop + sell 100). It over-blocked BUYs against
`max_open_risk_pct`; it never under-blocked. Same derivation as DEF538's
`open_lot_stops` (`_open_quantity_by_lot`). Also: the Room's stop clause names the
book's own currency.
"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest

from app.core.config import settings
from app.schemas.trade import Side
from app.services import room_runner
from app.services.sim_engine import SimEngine
from app.trading_math.markets import Market
from app.trading_math.risk_limits import position_risk_contribution

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from test_cr282_myr_book import _Pinned, _mandate

KL = "1155.KL"


@pytest.fixture
def sim(monkeypatch):
    monkeypatch.setattr(settings, "market_bursa_enabled", True)
    return SimEngine(provider=_Pinned({KL: 20.0, "F": 12.0, "NVDA": 100.0}))


def _buy(sim, uid, ticker, qty, stop):
    r = sim.submit(user_id=uid, ticker=ticker, side=Side.BUY, quantity=qty,
                   mandate=_mandate(), stop=stop)
    assert r.accepted, r.compliance.violations


def _sell(sim, uid, ticker, qty):
    r = sim.submit(user_id=uid, ticker=ticker, side=Side.SELL, quantity=qty,
                   mandate=_mandate())
    assert r.accepted, r.compliance.violations


def _risk(sim, uid, ticker, market):
    value = sim.total_value(uid, market)
    return sim.risk_limit_context(
        uid, portfolio_value=value, quotes=sim.current_marks([ticker]), market=market,
    )[2]


def test_a_flat_bursa_book_after_buy_with_stop_then_sell_has_no_open_risk(sim):
    uid = uuid4()
    _buy(sim, uid, KL, 100, 18.0)
    assert _risk(sim, uid, KL, Market.MY) > 0.0
    _sell(sim, uid, KL, 100)
    assert sim.ensure_portfolio(uid, market=Market.MY).holdings == []
    assert _risk(sim, uid, KL, Market.MY) == pytest.approx(0.0)


def test_a_flat_us_book_has_no_open_risk_either(sim):
    uid = uuid4()
    _buy(sim, uid, "F", 100, 10.0)
    assert _risk(sim, uid, "F", Market.US) > 0.0
    _sell(sim, uid, "F", 100)
    assert _risk(sim, uid, "F", Market.US) == pytest.approx(0.0)


def test_a_partly_sold_lot_counts_only_its_remaining_shares(sim):
    uid = uuid4()
    _buy(sim, uid, KL, 200, 18.0)
    full = _risk(sim, uid, KL, Market.MY)
    _sell(sim, uid, KL, 100)
    got = _risk(sim, uid, KL, Market.MY)
    entry = sim.list_trades(uid, market=Market.MY)[-1].entry_price
    mark = sim.current_marks([KL])[KL]
    pct = 100 * mark / sim.total_value(uid, Market.MY) * 100
    assert got == pytest.approx(position_risk_contribution(pct, entry, 18.0))
    assert 0.0 < got < full


def test_a_lot_still_held_in_full_is_unchanged(sim):
    uid = uuid4()
    _buy(sim, uid, "F", 100, 10.0)
    entry = sim.list_trades(uid, market=Market.US)[-1].entry_price
    mark = sim.current_marks(["F"])["F"]
    pct = 100 * mark / sim.total_value(uid, Market.US) * 100
    assert _risk(sim, uid, "F", Market.US) == pytest.approx(
        position_risk_contribution(pct, entry, 10.0)
    )


def test_a_sold_lot_does_not_mask_or_inflate_a_live_lot_in_the_same_name(sim):
    uid = uuid4()
    _buy(sim, uid, "F", 100, 10.0)
    _sell(sim, uid, "F", 100)
    _buy(sim, uid, "F", 50, 11.0)
    live = _risk(sim, uid, "F", Market.US)
    entry = [t for t in sim.list_trades(uid, market=Market.US)
             if t.stop == 11.0][0].entry_price
    mark = sim.current_marks(["F"])["F"]
    pct = 50 * mark / sim.total_value(uid, Market.US) * 100
    assert live == pytest.approx(position_risk_contribution(pct, entry, 11.0))


def test_the_rm_stop_clause_reads_rm_and_the_us_one_still_reads_dollars():
    assert room_runner._stop_clause(KL, {KL: {18.5}}, {}, Market.MY) == " — stop RM18.5"
    assert room_runner._stop_clause(
        KL, {KL: {18.0, 19.0}}, {KL: 1}, Market.MY
    ) == " — stops RM18, RM19, and 1 lot with NO stop recorded"
    assert room_runner._stop_clause("F", {"F": {10.0}}, {}) == " — stop $10"
    assert room_runner._stop_clause(
        "F", {"F": {10.0, 11.0}}, {}, Market.US
    ) == " — stops $10, $11"


def test_the_bursa_holdings_block_prints_its_stop_in_rm(sim, monkeypatch):
    monkeypatch.setattr(room_runner, "get_sim_engine", lambda: sim)
    uid = uuid4()
    _buy(sim, uid, KL, 100, 18.0)
    block = room_runner._build_sim_holdings_block(uid, KL)
    assert "stop RM18" in block and "$" not in block
