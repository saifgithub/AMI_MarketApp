"""CR109 Amendment G — short selling in the game, at 0.3%.

Saiful, 2026-08-11: *"the game does not allow 'short' selling? we will need
to add a 'fee' for short selling. lets set it at 0.3% for now."*

The invariants under test, in the order they matter:

1. **Opening a short does not change total value.** Everything the Close
   scores on — NAV, drawdown, the TWR chain — is derived from
   `Portfolio.total_value`. If opening a position moves that number, a
   player books a profit or a loss for the act of entering, and the contest
   is scored on an artefact.
2. **No leverage.** A $5,000 short ties up $5,000, exactly as a $5,000 buy
   would. CR109 §5.1's "Leverage / margin: None, ever" is what fixes
   shorting's one free parameter, and without it gross exposure is
   unbounded and the whole board is unscoreable.
3. **A sell never crosses zero**, and its buy-side mirror.
4. **The training lane is untouched** — no negative `sim_holdings.quantity`
   anywhere, and `def110_backfill`'s phantom-share formula reads exactly
   what it read before.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import (
    GameQueuedOrderRow,
    GameShortPositionRow,
    SimHoldingRow,
    SimTradeRow,
)
from app.schemas.trade import Side
from app.services import market_data as _md
from app.services.games_scoring import (
    FEE_BPS,
    FEE_MIN,
    SHORT_FEE_BPS,
    short_open_fee,
    trade_fee,
)
from app.services.sim_engine import SimEngine
from app.trading_math.shorts import short_leg


class _MutableProvider:
    """A fixed price that the test can move, to mark a short."""

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


def _short(sim, user_id, run_id, ticker="AAPL", qty=10.0):
    return sim.submit_game_trade(
        user_id=user_id, run_id=run_id, ticker=ticker,
        side=Side.SELL, quantity=qty,
    )


def _cover(sim, user_id, run_id, ticker="AAPL", qty=10.0):
    return sim.submit_game_trade(
        user_id=user_id, run_id=run_id, ticker=ticker,
        side=Side.BUY, quantity=qty,
    )


def _game(sim, user_id, run_id):
    return sim.ensure_portfolio(user_id, kind="game", run_id=run_id)


# ── The fee Saiful set ──────────────────────────────────────────────────


def test_short_fee_is_30bps_three_times_the_ordinary_trade_fee():
    """A retune is a one-line change here that fails until updated."""
    assert SHORT_FEE_BPS == 30.0
    assert SHORT_FEE_BPS == 3 * FEE_BPS
    assert short_open_fee(10_000.0) == 30.00   # 0.3% of 10,000
    assert short_open_fee(100.0) == FEE_MIN    # 0.3% of 100 = 0.30, floored


def test_opening_a_short_charges_the_short_fee_and_the_cover_charges_the_ordinary_one():
    """The split Saiful was given a rate for but not a leg. Stated here so
    it is a decision on the record rather than an accident of the code."""
    sim = SimEngine(provider=_MutableProvider(100.0))
    user_id, run_id = uuid4(), uuid4()

    opened = _short(sim, user_id, run_id, qty=10)     # 1,000 notional
    assert opened.accepted, opened.reason
    assert opened.fee == 3.00                        # 30bps of 1,000

    covered = _cover(sim, user_id, run_id, qty=10)
    assert covered.accepted, covered.reason
    assert covered.fee == 1.00                       # 10bps of 1,000


# ── Invariant 1: value is continuous across open and close ──────────────


def test_opening_a_short_does_not_change_total_value_beyond_the_fee():
    """The load-bearing one. At an unchanged mark, the only movement is the
    fee — the same as opening a long."""
    sim = SimEngine(provider=_MutableProvider(100.0))
    user_id, run_id = uuid4(), uuid4()
    before = _game(sim, user_id, run_id).total_value({"AAPL": 100.0})

    opened = _short(sim, user_id, run_id, qty=10)
    assert opened.accepted, opened.reason

    after = _game(sim, user_id, run_id).total_value({"AAPL": 100.0})
    assert after == pytest.approx(before - opened.fee)


def test_covering_at_the_entry_price_returns_exactly_what_was_posted():
    sim = SimEngine(provider=_MutableProvider(100.0))
    user_id, run_id = uuid4(), uuid4()
    _short(sim, user_id, run_id, qty=10)
    cash_while_short = _game(sim, user_id, run_id).current_cash

    covered = _cover(sim, user_id, run_id, qty=10)
    assert covered.accepted, covered.reason
    assert covered.short_realised_pnl == pytest.approx(0.0)

    cash_after = _game(sim, user_id, run_id).current_cash
    assert cash_after == pytest.approx(cash_while_short + 1_000.00 - covered.fee)


# ── Invariant 2: no leverage ────────────────────────────────────────────


def test_a_short_ties_up_the_full_notional_exactly_as_a_buy_would():
    """No leverage. A real short posts ~50% and is 2:1 levered; here the
    cash cost of shorting $1,000 equals the cash cost of buying $1,000."""
    sim = SimEngine(provider=_MutableProvider(100.0))
    user_id, short_run, long_run = uuid4(), uuid4(), uuid4()

    _short(sim, user_id, short_run, ticker="AAPL", qty=10)
    sim.submit_game_trade(
        user_id=user_id, run_id=long_run, ticker="AAPL",
        side=Side.BUY, quantity=10,
    )

    short_cash = _game(sim, user_id, short_run).current_cash
    long_cash = _game(sim, user_id, long_run).current_cash
    # Same notional out of cash; the fee differs (30bps vs 10bps) and that
    # difference is the entire difference.
    assert short_cash == pytest.approx(long_cash - 2.00)


def test_a_short_beyond_the_stake_is_refused_not_silently_levered():
    sim = SimEngine(provider=_MutableProvider(100.0))
    user_id, run_id = uuid4(), uuid4()

    result = _short(sim, user_id, run_id, qty=200)   # 20,000 on a 10,000 stake
    assert not result.accepted
    assert "insufficient cash" in (result.reason or "")
    assert _game(sim, user_id, run_id).shorts == []


def test_a_short_that_moves_against_the_player_reduces_total_value():
    """And it is unbounded below — the lesson the position exists to teach."""
    sim = SimEngine(provider=_MutableProvider(100.0))
    user_id, run_id = uuid4(), uuid4()
    _short(sim, user_id, run_id, qty=10)
    at_entry = _game(sim, user_id, run_id).total_value({"AAPL": 100.0})

    # Price doubles against the short.
    against = _game(sim, user_id, run_id).total_value({"AAPL": 200.0})
    assert against == pytest.approx(at_entry - 1_000.00)

    # And in the player's favour.
    favour = _game(sim, user_id, run_id).total_value({"AAPL": 90.0})
    assert favour == pytest.approx(at_entry + 100.00)


def test_a_winning_short_is_realised_into_cash_on_the_cover():
    sim = SimEngine(provider=_MutableProvider(100.0))
    user_id, run_id = uuid4(), uuid4()
    _short(sim, user_id, run_id, qty=10)
    cash_while_short = _game(sim, user_id, run_id).current_cash

    sim._provider = _MutableProvider(90.0)
    covered = _cover(sim, user_id, run_id, qty=10)
    assert covered.accepted, covered.reason
    assert covered.short_realised_pnl == pytest.approx(100.00)

    cash_after = _game(sim, user_id, run_id).current_cash
    assert cash_after == pytest.approx(cash_while_short + 1_100.00 - covered.fee)
    assert _game(sim, user_id, run_id).shorts == []


def test_a_losing_cover_is_never_refused_for_want_of_cash():
    """The posted cash IS the money to buy back with. A cover that could be
    blocked by a low balance would trap a player in the one position whose
    loss is unbounded."""
    sim = SimEngine(provider=_MutableProvider(100.0))
    user_id, run_id = uuid4(), uuid4()
    _short(sim, user_id, run_id, qty=10)
    # Spend every remaining cent on something else.
    game = _game(sim, user_id, run_id)
    sim.submit_game_trade(
        user_id=user_id, run_id=run_id, ticker="MSFT", side=Side.BUY,
        quantity=(game.current_cash - 10.0) / 100.0,
    )
    assert _game(sim, user_id, run_id).current_cash < 15.0

    sim._provider = _MutableProvider(150.0)
    covered = _cover(sim, user_id, run_id, ticker="AAPL", qty=10)
    assert covered.accepted, covered.reason
    assert covered.short_realised_pnl == pytest.approx(-500.00)


# ── Invariant 3: a sell never crosses zero ──────────────────────────────


def test_a_sell_larger_than_the_holding_is_refused_naming_both_numbers():
    sim = SimEngine(provider=_MutableProvider(100.0))
    user_id, run_id = uuid4(), uuid4()
    sim.submit_game_trade(
        user_id=user_id, run_id=run_id, ticker="AAPL", side=Side.BUY, quantity=5,
    )

    result = _short(sim, user_id, run_id, qty=8)
    assert not result.accepted
    assert "8" in (result.reason or "") and "5" in (result.reason or "")
    assert _game(sim, user_id, run_id).shorts == []
    assert [h.quantity for h in _game(sim, user_id, run_id).holdings] == [5.0]


def test_a_sell_that_closes_a_long_still_closes_it_and_opens_no_short():
    sim = SimEngine(provider=_MutableProvider(100.0))
    user_id, run_id = uuid4(), uuid4()
    sim.submit_game_trade(
        user_id=user_id, run_id=run_id, ticker="AAPL", side=Side.BUY, quantity=5,
    )
    result = sim.submit_game_trade(
        user_id=user_id, run_id=run_id, ticker="AAPL", side=Side.SELL, quantity=5,
    )
    assert result.accepted, result.reason
    assert result.short_action is None
    assert _game(sim, user_id, run_id).shorts == []
    assert _game(sim, user_id, run_id).holdings == []


def test_a_second_short_in_the_same_name_is_refused():
    """Extending would blend two entry prices into one position, with no
    `avg_cost` column to hold the blend honestly."""
    sim = SimEngine(provider=_MutableProvider(100.0))
    user_id, run_id = uuid4(), uuid4()
    assert _short(sim, user_id, run_id, qty=10).accepted

    again = _short(sim, user_id, run_id, qty=5)
    assert not again.accepted
    assert "already short" in (again.reason or "")
    assert len(_game(sim, user_id, run_id).shorts) == 1


def test_a_partial_cover_is_refused_naming_both_numbers():
    sim = SimEngine(provider=_MutableProvider(100.0))
    user_id, run_id = uuid4(), uuid4()
    assert _short(sim, user_id, run_id, qty=10).accepted

    partial = _cover(sim, user_id, run_id, qty=4)
    assert not partial.accepted
    assert "10" in (partial.reason or "") and "4" in (partial.reason or "")
    assert len(_game(sim, user_id, run_id).shorts) == 1


def test_a_buy_in_an_unshorted_name_is_an_ordinary_buy():
    sim = SimEngine(provider=_MutableProvider(100.0))
    user_id, run_id = uuid4(), uuid4()
    assert _short(sim, user_id, run_id, ticker="AAPL", qty=10).accepted

    result = sim.submit_game_trade(
        user_id=user_id, run_id=run_id, ticker="MSFT", side=Side.BUY, quantity=5,
    )
    assert result.accepted, result.reason
    assert result.short_action is None
    assert result.fee == 1.00
    assert [h.ticker for h in _game(sim, user_id, run_id).holdings] == ["MSFT"]


# ── Invariant 4: the training lane and DEF110 are untouched ─────────────


def test_a_short_writes_no_sim_holdings_row_and_no_negative_quantity():
    sim = SimEngine(provider=_MutableProvider(100.0))
    user_id, run_id = uuid4(), uuid4()
    assert _short(sim, user_id, run_id, qty=10).accepted

    with get_session() as s:
        quantities = [
            float(q) for q in s.execute(select(SimHoldingRow.quantity)).scalars().all()
        ]
    assert all(q >= 0 for q in quantities), "a negative holding quantity exists"
    assert _game(sim, user_id, run_id).holdings == []


def test_a_short_writes_no_sim_trades_row():
    """`def110_backfill.py::expected()` subtracts Σ quantity over open SELL
    rows to detect phantom shares. A short's sell leg is permanently open by
    design, so a `sim_trades` row for it would make every real phantom share
    in that portfolio look accounted for."""
    sim = SimEngine(provider=_MutableProvider(100.0))
    user_id, run_id = uuid4(), uuid4()
    assert _short(sim, user_id, run_id, qty=10).accepted

    with get_session() as s:
        rows = s.execute(
            select(SimTradeRow).where(SimTradeRow.user_id == user_id)
        ).scalars().all()
    assert rows == []


def test_the_training_portfolio_never_carries_a_short_leg():
    sim = SimEngine(provider=_MutableProvider(100.0))
    user_id, run_id = uuid4(), uuid4()
    assert _short(sim, user_id, run_id, qty=10).accepted

    assert sim.ensure_portfolio(user_id).shorts == []
    assert sim.ensure_portfolio(user_id).total_value({"AAPL": 500.0}) == pytest.approx(
        10_000.0
    )


# ── The row itself ──────────────────────────────────────────────────────


def test_the_settled_row_records_how_and_why_it_closed():
    sim = SimEngine(provider=_MutableProvider(100.0))
    user_id, run_id = uuid4(), uuid4()
    _short(sim, user_id, run_id, qty=10)
    sim._provider = _MutableProvider(80.0)
    _cover(sim, user_id, run_id, qty=10)

    with get_session() as s:
        row = s.execute(
            select(GameShortPositionRow).where(GameShortPositionRow.run_id == run_id)
        ).scalars().one()
        assert row.state == "closed"
        assert row.close_reason == "user"
        assert float(row.close_price) == pytest.approx(80.0)
        assert float(row.realised_pnl) == pytest.approx(200.0)
        assert float(row.cash_posted) == pytest.approx(1_000.0)
        assert float(row.fee_paid) == pytest.approx(3.00)


def test_short_leg_arithmetic_is_the_identity_the_design_claims():
    """The pure function, pinned independently of the engine."""
    assert short_leg(1_000.0, 10, 100.0, 100.0) == pytest.approx(1_000.0)
    assert short_leg(1_000.0, 10, 100.0, 90.0) == pytest.approx(1_100.0)
    assert short_leg(1_000.0, 10, 100.0, 110.0) == pytest.approx(900.0)
    # Unbounded below: a name that triples costs more than was posted.
    assert short_leg(1_000.0, 10, 100.0, 300.0) == pytest.approx(-1_000.0)


# ── Two places a short could have been forgotten ────────────────────────


def test_a_queued_short_commits_its_full_notional():
    """§13.3's `cash_committed` exists because the ticket offered the whole
    stake no matter how much was already queued against it. A short is a
    SELL, and every sell used to release cash rather than commit it — so
    without this a player could queue shorts all night against a balance the
    app kept reporting as untouched."""
    from app.services import games_service

    sim = SimEngine(provider=_MutableProvider(100.0))
    user_id, run_id = uuid4(), uuid4()
    sim.ensure_portfolio(user_id, kind="game", run_id=run_id)

    with get_session() as s:
        s.add(GameQueuedOrderRow(
            run_id=run_id, user_id=user_id, ticker="AAPL", side="sell",
            quantity=10, order_type="market", state="queued",
            queued_at=datetime(2026, 8, 11, 2, 0, tzinfo=timezone.utc),
        ))

    rows, committed = games_service._queued_orders_priced(user_id, run_id)
    # Asserted against the row's OWN estimate rather than a literal: this
    # function prices through the process-global engine (the mock walk), not
    # through the provider this test constructed, so the price is whatever
    # that provider says. What must hold is the SHAPE — the notional is
    # committed, not just the fee.
    (row,) = rows
    assert committed == pytest.approx(row["est_notional"] + row["est_fee"])
    assert committed > row["est_fee"]
    # And it is the SHORT fee that was quoted, not the ordinary one.
    assert row["est_fee"] == pytest.approx(short_open_fee(row["est_notional"]))


def test_a_queued_sell_that_closes_a_long_still_commits_only_the_fee():
    """The mutation guard for the test above: the fix must not turn every
    queued sell into a commitment, or a player closing a position overnight
    would watch their available cash fall for doing it."""
    from app.services import games_service

    sim = SimEngine(provider=_MutableProvider(100.0))
    user_id, run_id = uuid4(), uuid4()
    sim.submit_game_trade(
        user_id=user_id, run_id=run_id, ticker="AAPL", side=Side.BUY, quantity=10,
    )

    with get_session() as s:
        s.add(GameQueuedOrderRow(
            run_id=run_id, user_id=user_id, ticker="AAPL", side="sell",
            quantity=10, order_type="market", state="queued",
            queued_at=datetime(2026, 8, 11, 2, 0, tzinfo=timezone.utc),
        ))

    rows, committed = games_service._queued_orders_priced(user_id, run_id)
    (row,) = rows
    # The fee alone — a sell that closes RELEASES the notional.
    assert committed == pytest.approx(row["est_fee"])
    assert row["est_fee"] == pytest.approx(trade_fee(row["est_notional"]))


def test_a_split_divides_a_short_the_same_way_it_divides_a_long():
    """The market price halves on a 2:1. A short whose quantity and entry
    price were left alone would mark at half its entry and show a 50% gain
    that is pure arithmetic — a fabricated profit, in a scored contest, from
    a corporate action that changed nothing."""
    sim = SimEngine(provider=_MutableProvider(100.0))
    user_id, run_id = uuid4(), uuid4()
    _short(sim, user_id, run_id, ticker="AAPL", qty=10)
    before = _game(sim, user_id, run_id).total_value({"AAPL": 100.0})

    sim.apply_split(user_id, "AAPL", 2.0, kind="game", run_id=run_id)

    (leg,) = _game(sim, user_id, run_id).shorts
    assert leg.quantity == pytest.approx(20.0)
    assert leg.entry_price == pytest.approx(50.0)
    # The posted cash is `old_entry * old_quantity`, which is unchanged by
    # the division — and value is continuous once the mark halves too.
    assert leg.cash_posted == pytest.approx(1_000.0)
    after = _game(sim, user_id, run_id).total_value({"AAPL": 50.0})
    assert after == pytest.approx(before)
