"""DEF538 — a Room's "YOUR SIMULATED PORTFOLIO" block must state only the position the
user actually holds, in the book the Room's ticker belongs to.

Device report (AMI-DL-27, build 133): a 1155.KL Room's CIO cited an "existing 8.1%
position" on a Bursa book that was empty (RM49,962.76 cash). The user had bought and
then sold 100 1155.KL. The block was built from the open TRADE ROWS summed per name,
and a sell leaves its BUY row `open` AND adds its own permanently-`open` SELL row
(DEF166/DEF110), so a round trip read as 200 shares held. The fix reads the book's
holdings, the same rows the portfolio screen and the compliance check read.
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

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from test_cr282_myr_book import _Pinned, _mandate

KL = "1155.KL"


@pytest.fixture
def sim(monkeypatch):
    monkeypatch.setattr(settings, "market_bursa_enabled", True)
    eng = SimEngine(provider=_Pinned({KL: 20.0, "F": 12.0, "NVDA": 100.0}))
    monkeypatch.setattr(room_runner, "get_sim_engine", lambda: eng)
    return eng


def _trade(sim, uid, ticker, side, qty):
    r = sim.submit(user_id=uid, ticker=ticker, side=side, quantity=qty, mandate=_mandate())
    assert r.accepted, r.compliance.violations
    return r


def test_a_us_position_and_an_empty_myr_book_shows_no_bursa_position(sim):
    uid = uuid4()
    _trade(sim, uid, "F", Side.BUY, 100)
    block = room_runner._build_sim_holdings_block(uid, KL)
    assert "RM" in block and "F ×" not in block
    assert f"You hold 0% of {KL}" in block
    assert "Open positions: none" in block
    assert room_runner._build_room_sector_context(uid, Market.MY)[0] == []


def test_a_bought_then_sold_bursa_name_reads_as_flat(sim):
    uid = uuid4()
    _trade(sim, uid, KL, Side.BUY, 100)
    _trade(sim, uid, KL, Side.SELL, 100)
    assert sim.ensure_portfolio(uid, market=Market.MY).holdings == []
    block = room_runner._build_sim_holdings_block(uid, KL)
    assert f"You hold 0% of {KL}" in block
    assert "Open positions: none" in block
    assert "You currently hold" not in block


def test_a_partly_sold_bursa_name_shows_the_remaining_shares_only(sim):
    uid = uuid4()
    _trade(sim, uid, KL, Side.BUY, 200)
    _trade(sim, uid, KL, Side.SELL, 100)
    block = room_runner._build_sim_holdings_block(uid, KL)
    total = sim.total_value(uid, Market.MY)
    assert f"{KL} ×100 " in block
    assert f"You currently hold {100 * 20.0 / total * 100:.1f}% of {KL}" in block


def test_a_us_room_is_unchanged_by_a_bursa_position(sim):
    uid = uuid4()
    _trade(sim, uid, KL, Side.BUY, 100)
    _trade(sim, uid, "F", Side.BUY, 50)
    _trade(sim, uid, "F", Side.BUY, 10)
    _trade(sim, uid, "F", Side.SELL, 20)
    block = room_runner._build_sim_holdings_block(uid, "F")
    total = sim.total_value(uid)
    assert "$" in block and KL not in block
    assert "F ×40 " in block
    assert f"You currently hold {40 * 12.0 / total * 100:.1f}% of F" in block


def test_the_trade_count_and_open_risk_a_kl_room_sees_are_the_myr_books_only(sim):
    uid = uuid4()
    for _ in range(3):
        r = sim.submit(user_id=uid, ticker="F", side=Side.BUY, quantity=1,
                       mandate=_mandate(), stop=10.0)
        assert r.accepted
    _, stamps_my, risk_my = room_runner._build_room_risk_limit_context(
        uid, portfolio_value=50_000.0, quotes={}, market=Market.MY,
    )
    assert stamps_my == [] and risk_my == 0.0
    _, stamps_us, risk_us = room_runner._build_room_risk_limit_context(
        uid, portfolio_value=10_000.0, quotes={},
    )
    assert len(stamps_us) == 3 and risk_us > 0.0
