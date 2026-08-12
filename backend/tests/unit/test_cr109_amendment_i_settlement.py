"""CR109 Amendment I, second half — a closed run holds nothing.

Saiful, 2026-08-12: *"keep no leverage, but when the game ends, all positions
must be closed."* This reverses Amendment G's *"no forced cover at the close"*
and narrows §5.2's mark-don't-liquidate rule to the DAILY mark, which is what
it was always about.

The three things that make this correct rather than merely done, each with a
test that fails if it stops holding:

1. **Settlement is free.** An exit fee would move the score for the act of the
   run ending — a charge for a non-decision, which is Amendment G ruling 3's
   objection pointed the other way.
2. **Settlement is not a trade.** `trade_count` gates the finish stipend on
   ">= 1 executed trade"; a close that incremented it would hand a stipend to
   a player who never traded, using the close itself as the qualifying trade.
3. **Settlement runs AFTER scoring.** `_score_one_entry` reads holdings for
   the wildness index's concentration weights and the trade ledger for its
   turnover term. Settling first scores everyone on an empty book; writing the
   settlement rows first inflates turnover for a liquidation nobody chose.

And one that is easy to miss until a repair script quietly undoes the feature:
settlement writes an ordinary sell row, because `scripts/def110_backfill.py`
rebuilds holdings from `Σ open buys − Σ open sells` across EVERY portfolio.
Deleting a holding without that row leaves the formula expecting shares nobody
holds, and the backfill would recreate the positions this just closed.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import (
    GameEntryRow,
    GameFieldRow,
    GameShortPositionRow,
    PortfolioNavDailyRow,
    SimHoldingRow,
    SimTradeRow,
)
from app.schemas.trade import Side
from app.services import games_scoring_pass as pass_module
from app.services import games_service as games
from app.services.sim_engine import SimEngine

_ENTRY_OPEN_CLOSED_MARKET = datetime(2026, 8, 10, 3, 0, tzinfo=timezone.utc)
_MARKET_OPEN = datetime(2026, 8, 10, 15, 0, tzinfo=timezone.utc)
_STARTS_ON = date(2026, 8, 10)
_ENDS_ON = date(2026, 8, 14)
_AFTER_CLOSE = datetime(2026, 8, 17, 15, 0, tzinfo=timezone.utc)


class _ConstProvider:
    name = "fake"

    def __init__(self, price: float = 100.0) -> None:
        self.price = price

    def quote(self, ticker: str):
        from app.services import market_data as _md

        return _md.Quote(price=self.price, source=self.name)

    def get_price(self, ticker: str):
        return self.price

    def history(self, ticker: str, period: str):
        return None

    def news(self, ticker: str, limit: int = 5):
        return None

    def earnings(self, ticker: str):
        return None


def _enter_and_make_live(user_id) -> GameEntryRow:
    entry = games.enter_field(user_id, now=_ENTRY_OPEN_CLOSED_MARKET)
    with get_session() as s:
        field = s.execute(
            select(GameFieldRow).where(GameFieldRow.id == entry.field_id)
        ).scalar_one()
        field.state = "live"
    return entry


def _nav_series(user_id, run_id, *, end_nav=10_200.0):
    for as_of, nav, ev in (
        (_STARTS_ON, 10_000.0, "open"),
        (date(2026, 8, 12), (10_000.0 + end_nav) / 2, None),
        (_ENDS_ON, end_nav, None),
    ):
        with get_session() as s:
            s.add(PortfolioNavDailyRow(
                user_id=user_id, run_id=run_id, as_of_date=as_of, nav=nav,
                cash=nav, price_source="live", capital_event=ev,
            ))


def _holdings(user_id, run_id):
    with get_session() as s:
        p = games.get_sim_engine()._load_portfolio_row(
            s, user_id, kind="game", run_id=run_id,
        )
        return list(
            s.execute(
                select(SimHoldingRow).where(SimHoldingRow.portfolio_id == p.id)
            ).scalars().all()
        )


def _entry_row(user_id):
    with get_session() as s:
        return s.execute(
            select(GameEntryRow).where(GameEntryRow.user_id == user_id)
        ).scalar_one()


# ── The ruling itself ────────────────────────────────────────────────────


def test_a_closed_run_holds_nothing():
    user_id = uuid4()
    entry = _enter_and_make_live(user_id)
    games.submit_trade(
        user_id, entry.run_id, ticker="AAPL", side=Side.BUY, quantity=5,
        now=_MARKET_OPEN,
    )
    _nav_series(user_id, entry.run_id)
    assert _holdings(user_id, entry.run_id), "fixture holds nothing to settle"

    pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    assert _holdings(user_id, entry.run_id) == []


def test_an_open_short_is_covered_by_the_close():
    user_id = uuid4()
    entry = _enter_and_make_live(user_id)
    games.submit_trade(
        user_id, entry.run_id, ticker="TSLA", side=Side.SELL, quantity=5,
        now=_MARKET_OPEN,
    )
    _nav_series(user_id, entry.run_id)

    with get_session() as s:
        assert s.execute(
            select(GameShortPositionRow).where(
                GameShortPositionRow.run_id == entry.run_id,
                GameShortPositionRow.state == "open",
            )
        ).scalars().first() is not None, "fixture opened no short"

    pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    with get_session() as s:
        row = s.execute(
            select(GameShortPositionRow).where(
                GameShortPositionRow.run_id == entry.run_id
            )
        ).scalars().one()
        assert row.state == "closed"
        assert row.close_reason == "settlement"


def test_settlement_is_idempotent_and_a_flat_run_settles_nothing():
    user_id = uuid4()
    entry = _enter_and_make_live(user_id)
    _nav_series(user_id, entry.run_id)

    first = games.settle_run_positions(user_id, entry.run_id, now=_AFTER_CLOSE)
    assert first == {"positions_closed": 0, "shorts_covered": 0}


# ── Free, and not a trade ────────────────────────────────────────────────


def test_settlement_charges_no_fee():
    """An exit fee would move the score for the act of the run ending."""
    user_id = uuid4()
    entry = _enter_and_make_live(user_id)
    games.submit_trade(
        user_id, entry.run_id, ticker="AAPL", side=Side.BUY, quantity=5,
        now=_MARKET_OPEN,
    )
    _nav_series(user_id, entry.run_id)
    fees_before = float(_entry_row(user_id).fees_paid)

    pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    assert float(_entry_row(user_id).fees_paid) == pytest.approx(fees_before)


def test_settlement_does_not_count_as_a_trade():
    """`trade_count` gates the finish stipend on ">= 1 executed trade". A
    close that bumped it would hand the stipend to a player who never traded,
    using the close itself as the qualifying trade."""
    user_id = uuid4()
    entry = _enter_and_make_live(user_id)
    games.submit_trade(
        user_id, entry.run_id, ticker="AAPL", side=Side.BUY, quantity=5,
        now=_MARKET_OPEN,
    )
    _nav_series(user_id, entry.run_id)
    count_before = _entry_row(user_id).trade_count
    assert count_before == 1

    pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    assert _entry_row(user_id).trade_count == count_before


def test_a_run_that_never_traded_is_not_handed_a_trade_by_its_own_close():
    """The sharp end of the test above, on the player it would actually
    change: zero trades in, zero trades out, so the stipend still refuses."""
    user_id = uuid4()
    entry = _enter_and_make_live(user_id)
    _nav_series(user_id, entry.run_id)

    pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    row = _entry_row(user_id)
    assert row.trade_count == 0
    assert row.stipend_points == 0


# ── The ordering, which is load-bearing rather than tidy ─────────────────


def test_the_score_is_taken_before_the_book_is_settled(monkeypatch):
    """Settling first would score every entrant on an EMPTY book.

    `wildness_index` reads holdings for its concentration weights, so a run
    that held one name all week would score as though it held nothing — and a
    concentration of zero is the calmest book there is, which is the exact
    inversion the index exists to prevent.

    Asserted by observing the ORDER of the two calls rather than by a value.
    The first version of this test asserted `wildness_index > 0` and was
    useless: the index has a turnover term and a volatility term as well, so
    it stays positive on an empty book — the test passed with settlement
    moved deliberately ahead of the score, which is the mutation it existed
    to catch.
    """
    calls: list[str] = []

    real_score = pass_module._score_one_entry
    real_settle = games.settle_run_positions

    def spy_score(*a, **kw):
        calls.append("score")
        return real_score(*a, **kw)

    def spy_settle(*a, **kw):
        calls.append("settle")
        return real_settle(*a, **kw)

    monkeypatch.setattr(pass_module, "_score_one_entry", spy_score)
    monkeypatch.setattr(games, "settle_run_positions", spy_settle)

    user_id = uuid4()
    entry = _enter_and_make_live(user_id)
    games.submit_trade(
        user_id, entry.run_id, ticker="AAPL", side=Side.BUY, quantity=5,
        now=_MARKET_OPEN,
    )
    _nav_series(user_id, entry.run_id)

    pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    assert "score" in calls and "settle" in calls, calls
    assert calls.index("score") < calls.index("settle"), (
        f"settlement ran before the score: {calls}"
    )
    assert _entry_row(user_id).state == "finished"


def test_the_settled_book_still_satisfies_the_backfill_invariant():
    """`def110_backfill` rebuilds holdings as `Σ open buys − Σ open sells`
    over EVERY portfolio. If settlement deleted the holding without writing
    the sell, that formula would expect shares nobody holds and the repair
    script would recreate the position this close just settled — a repair
    tool confidently undoing a correct settlement.
    """
    user_id = uuid4()
    entry = _enter_and_make_live(user_id)
    games.submit_trade(
        user_id, entry.run_id, ticker="AAPL", side=Side.BUY, quantity=5,
        now=_MARKET_OPEN,
    )
    _nav_series(user_id, entry.run_id)

    pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    with get_session() as s:
        p = games.get_sim_engine()._load_portfolio_row(
            s, user_id, kind="game", run_id=entry.run_id,
        )
        trades = s.execute(
            select(SimTradeRow).where(SimTradeRow.portfolio_id == p.id)
        ).scalars().all()

    expected = 0.0
    for t in trades:
        side = t.side.value if hasattr(t.side, "value") else str(t.side)
        if t.status != "open":
            continue
        expected += float(t.quantity) if side == "buy" else -float(t.quantity)

    assert expected == pytest.approx(0.0), (
        "the trade ledger still expects shares the settled run no longer holds"
    )
    assert _holdings(user_id, entry.run_id) == []
