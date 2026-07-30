"""DEF110 backfill — the repair for state the old `evaluate_outcomes` wrote.

The code fix stops new phantoms; it cannot clean the ones already on disk.
`backend/scripts/def110_backfill.py` does that, and it moves real money
(`current_cash`), so its two dangerous properties are pinned here:

  1. It credits proceeds at each closed trade's OWN `closed_price`, not
     today's mark, and it does NOT touch `realised_pnl` — that was already
     stamped correctly at close time. Re-realising it would double-count.
  2. It is idempotent. A second run must be a no-op. The naive shape ("for
     each won/lost trade, credit its proceeds") double-credits instead, which
     on a money column is the worse failure of the two.

`_phantom_state` reproduces the pre-fix bug faithfully: flip the trade to
won/lost and stamp the close, leaving the holding and cash untouched — which
is exactly what the old code did.
"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from app.db.models import SimHoldingRow, SimPortfolioRow, SimTradeRow  # noqa: E402
from app.db.session import get_sessionmaker  # noqa: E402
from app.schemas.trade import OrderType, Side  # noqa: E402
from app.services.coach_engine import hydrate_coach_mandate  # noqa: E402
from app.services.market_data import Quote  # noqa: E402
from app.services.sim_engine import SimEngine  # noqa: E402

from def110_backfill import _plan_and_apply  # noqa: E402


class _FixedPrice:
    name = "fixed"

    def __init__(self, price: float) -> None:
        self.price = price

    def quote(self, ticker: str) -> Quote:
        return Quote(price=self.price, source="fixed")

    def get_price(self, ticker: str) -> float:
        return self.price


def _phantom_state(sim, user_id, ticker, qty, entry, close_price, status="lost"):
    """Buy, then close the trade the way the DEF110 bug did — label only."""
    result = sim.submit(
        user_id=user_id, ticker=ticker, side=Side.BUY, quantity=qty,
        mandate=hydrate_coach_mandate({"plan": "trader", "single_name_cap_pct": 100.0}),
        order_type=OrderType.MARKET, stop=entry * 0.9, target=entry * 1.1,
        horizon_days=30, verdict_ref=uuid4(),
    )
    assert result.accepted, result.compliance.violations
    s = get_sessionmaker()()
    try:
        row = s.execute(
            select(SimTradeRow).where(SimTradeRow.id == result.trade.id)
        ).scalar_one()
        row.status = status
        row.closed_price = close_price
        row.realised_pnl = round((close_price - entry) * qty, 2)
        s.commit()
    finally:
        s.close()
    return result.trade.id


def _run_backfill():
    s = get_sessionmaker()()
    try:
        out = _plan_and_apply(s, SimEngine())
        s.commit()
        return out
    finally:
        s.close()


def _portfolio(user_id):
    s = get_sessionmaker()()
    try:
        p = s.execute(
            select(SimPortfolioRow).where(SimPortfolioRow.user_id == user_id)
        ).scalar_one()
        holdings = s.execute(
            select(SimHoldingRow).where(SimHoldingRow.portfolio_id == p.id)
        ).scalars().all()
        return float(p.current_cash), {h.ticker: float(h.quantity) for h in holdings}
    finally:
        s.close()


def test_backfill_removes_the_phantom_and_credits_the_close_price():
    sim = SimEngine(provider=_FixedPrice(100.0))
    user_id = uuid4()
    _phantom_state(sim, user_id, "AMD", 10, 100.0, close_price=90.0)

    cash, holdings = _portfolio(user_id)
    assert holdings == {"AMD": 10.0}, "precondition: the bug left the shares"
    assert cash == 9_000.0

    _, shares, credited, unattributed = _run_backfill()

    assert unattributed == 0
    assert shares == 10.0
    assert credited == 900.0  # 10 * 90 — the CLOSE price, not the 100 mark
    cash, holdings = _portfolio(user_id)
    assert holdings == {}
    assert cash == 9_900.0


def test_backfill_is_idempotent():
    """The property that matters most: this touches a money column."""
    sim = SimEngine(provider=_FixedPrice(100.0))
    user_id = uuid4()
    _phantom_state(sim, user_id, "AMD", 10, 100.0, close_price=90.0)

    _run_backfill()
    after_first = _portfolio(user_id)

    _, shares, credited, unattributed = _run_backfill()

    assert (shares, credited, unattributed) == (0.0, 0.0, 0)
    assert _portfolio(user_id) == after_first, "second run moved shares or cash"


def test_backfill_leaves_realised_pnl_alone():
    sim = SimEngine(provider=_FixedPrice(100.0))
    user_id = uuid4()
    trade_id = _phantom_state(sim, user_id, "AMD", 10, 100.0, close_price=90.0)

    _run_backfill()

    s = get_sessionmaker()()
    try:
        row = s.execute(
            select(SimTradeRow).where(SimTradeRow.id == trade_id)
        ).scalar_one()
        assert float(row.realised_pnl) == -100.0  # (90 - 100) * 10, unchanged
        assert row.status == "lost"
        assert float(row.closed_price) == 90.0
    finally:
        s.close()


def test_backfill_spares_a_genuinely_open_position():
    """The live `abc5e232` case: 3 TSLA held, 2 open, 1 phantom."""
    sim = SimEngine(provider=_FixedPrice(100.0))
    user_id = uuid4()
    _phantom_state(sim, user_id, "TSLA", 1, 100.0, close_price=120.0, status="won")
    open_buy = sim.submit(
        user_id=user_id, ticker="TSLA", side=Side.BUY, quantity=2,
        mandate=hydrate_coach_mandate({"plan": "trader", "single_name_cap_pct": 100.0}),
        order_type=OrderType.MARKET, verdict_ref=uuid4(),
    )
    assert open_buy.accepted

    cash_before, holdings = _portfolio(user_id)
    assert holdings == {"TSLA": 3.0}

    _, shares, credited, unattributed = _run_backfill()

    assert (shares, credited, unattributed) == (1.0, 120.0, 0)
    cash, holdings = _portfolio(user_id)
    assert holdings == {"TSLA": 2.0}, "the open position must survive"
    assert cash == cash_before + 120.0


def test_backfill_does_nothing_to_a_clean_portfolio():
    sim = SimEngine(provider=_FixedPrice(100.0))
    user_id = uuid4()
    sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=3,
        mandate=hydrate_coach_mandate({"plan": "trader", "single_name_cap_pct": 100.0}),
        order_type=OrderType.MARKET, verdict_ref=uuid4(),
    )
    before = _portfolio(user_id)

    lines, shares, credited, unattributed = _run_backfill()

    assert (lines, shares, credited, unattributed) == ([], 0.0, 0.0, 0)
    assert _portfolio(user_id) == before


def test_backfill_refuses_to_price_a_close_with_no_closed_price():
    """Degrade loudly: unattributable drift is left in place and reported."""
    sim = SimEngine(provider=_FixedPrice(100.0))
    user_id = uuid4()
    trade_id = _phantom_state(sim, user_id, "AMD", 10, 100.0, close_price=90.0)
    s = get_sessionmaker()()
    try:
        row = s.execute(
            select(SimTradeRow).where(SimTradeRow.id == trade_id)
        ).scalar_one()
        row.closed_price = None
        s.commit()
    finally:
        s.close()
    before = _portfolio(user_id)

    lines, shares, credited, unattributed = _run_backfill()

    assert unattributed == 1
    assert (shares, credited) == (0.0, 0.0)
    assert _portfolio(user_id) == before, "shares moved without pricing the sale"
    assert any("no closed_price" in line for line in lines)
    assert any("LEFT IN PLACE" in line for line in lines)


def test_sell_trade_rows_stay_open_forever():
    """DEF166 coupling guard.

    `_plan_and_apply`'s `expected()` formula (above) subtracts Σ quantity
    over status='open' SELL trades to derive what a holding SHOULD be. That
    only holds if a SELL trade row never transitions off "open" — nothing
    in the engine currently closes one; `evaluate_outcomes` only watches BUY
    rows against stop/target. If a future change ever flips a sell row's
    status, this formula silently drifts and the backfill's phantom-share
    detection goes wrong without a code change anywhere near it. Pin the
    invariant here so that change has to touch this test.
    """
    provider = _FixedPrice(100.0)
    sim = SimEngine(provider=provider)
    user_id = uuid4()
    sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=5,
        mandate=hydrate_coach_mandate({"plan": "trader", "single_name_cap_pct": 100.0}),
        order_type=OrderType.MARKET, stop=50.0, target=500.0,
        horizon_days=30, verdict_ref=uuid4(),
    )
    sold = sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.SELL, quantity=2,
        mandate=hydrate_coach_mandate({"plan": "trader", "single_name_cap_pct": 100.0}),
        order_type=OrderType.MARKET,
    )
    assert sold.accepted
    sell_trade_id = sold.trade.id

    # A price move that would flip a BUY (stop/target) does nothing to a
    # SELL row — `evaluate_outcomes` never inspects Side.SELL trades.
    provider.price = 1_000.0
    sim.evaluate_outcomes(user_id)

    s = get_sessionmaker()()
    try:
        row = s.execute(
            select(SimTradeRow).where(SimTradeRow.id == sell_trade_id)
        ).scalar_one()
        assert row.status == "open", (
            "a sell trade row moved off 'open' — def110_backfill.py's "
            "expected() formula must be updated in the same change"
        )
    finally:
        s.close()


def test_backfill_after_the_fix_finds_nothing():
    """End-to-end: the fixed engine liquidates, so the backfill is a no-op."""
    provider = _FixedPrice(100.0)
    sim = SimEngine(provider=provider)
    user_id = uuid4()
    sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=5,
        mandate=hydrate_coach_mandate({"plan": "trader", "single_name_cap_pct": 100.0}),
        order_type=OrderType.MARKET, stop=90.0, target=110.0,
        horizon_days=30, verdict_ref=uuid4(),
    )
    provider.price = 110.0
    assert len(sim.evaluate_outcomes(user_id)) == 1
    after_fix = _portfolio(user_id)

    _, shares, credited, unattributed = _run_backfill()

    assert (shares, credited, unattributed) == (0.0, 0.0, 0)
    assert _portfolio(user_id) == after_fix
