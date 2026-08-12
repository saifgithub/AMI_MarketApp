"""DEF273 — the queue accepted orders the run could never pay for.

Saiful, on the shipped build: *"I have 10,003.29 committed to 8 queued orders,
0.00 available."* The queue path did no affordability check at all. A player
could commit several times their book overnight, and the first they heard of
it was the FIFO drain cancelling the losers with `rejected at fill time` —
hours later, on a screen they were not looking at.

The FIFO drain decided WHICH orders survived, which is the right rule and was
itself a fix. Nothing told the player that some would not. That is the gap.

Two things this must NOT do, and both have tests, because each would be a
worse defect than the one being fixed:

  * refuse a SELL or a COVER. Those return cash and are exactly the orders a
    player most needs to place from an empty balance — refusing them is the
    one-way book DEF259 had to fix, and Amendment G ruling 5 makes the cover
    case explicit.
  * refuse on a price it could not obtain. A refusal built on a guessed number
    is the CR040 fabrication class; with no price the check stands down and
    says so, leaving the drain as the authority it already was.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import GameEntryRow, GameFieldRow, GameQueuedOrderRow
from app.schemas.trade import Side
from app.services import games_service as games
from app.services import market_data as _md
from app.services.sim_engine import SimEngine

# Sunday 23:00 ET — market closed, so every order queues.
_CLOSED = datetime(2026, 8, 10, 3, 0, tzinfo=timezone.utc)
_OPEN = datetime(2026, 8, 10, 15, 0, tzinfo=timezone.utc)


class _ConstProvider:
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


def _use(price: float = 100.0) -> SimEngine:
    """Install a fixed-price engine as THE singleton.

    `games.submit_trade` resolves the engine through `get_sim_engine()`, and
    conftest nulls that singleton per test — so merely constructing a
    `SimEngine` here would leave the code under test on a mock-walk price and
    the assertions measuring nothing. (The first version of this file did
    exactly that: every expected number was off by a random walk.)
    """
    from app.services import sim_engine as _sim

    engine = SimEngine(provider=_ConstProvider(price))
    _sim._engine = engine
    return engine


def _live_entry(user_id):
    entry = games.enter_field(user_id, now=_CLOSED)
    with get_session() as s:
        field = s.execute(
            select(GameFieldRow).where(GameFieldRow.id == entry.field_id)
        ).scalar_one()
        field.state = "live"
    return entry


def _queued_count(run_id):
    with get_session() as s:
        return len(
            s.execute(
                select(GameQueuedOrderRow).where(
                    GameQueuedOrderRow.run_id == run_id,
                    GameQueuedOrderRow.state == "queued",
                )
            ).scalars().all()
        )


def _queue(user_id, run_id, *, ticker="AAPL", side=Side.BUY, qty=10.0):
    return games.submit_trade(
        user_id, run_id, ticker=ticker, side=side, quantity=qty, now=_CLOSED,
    )


# ── The refusal ──────────────────────────────────────────────────────────


def test_an_order_beyond_the_stake_is_refused_at_queue_time():
    """The whole point: refused NOW, not silently cancelled at the open."""
    _use(100.0)
    user_id = uuid4()
    entry = _live_entry(user_id)

    # 10,000 stake at $100 → 100 shares is the whole book; 200 is not.
    result = _queue(user_id, entry.run_id, qty=200)

    assert result["queued"] is False
    assert result["filled"] is False
    assert "left to commit" in result["reason"]
    assert _queued_count(entry.run_id) == 0


def test_an_affordable_order_still_queues():
    """The mutation guard: a check that refused everything passes the test
    above and breaks the feature."""
    _use(100.0)
    user_id = uuid4()
    entry = _live_entry(user_id)

    result = _queue(user_id, entry.run_id, qty=10)

    assert result["queued"] is True
    assert _queued_count(entry.run_id) == 1


def test_the_second_order_is_measured_against_what_the_first_already_committed():
    """Saiful's actual sequence. Each order is affordable ALONE; together
    they are not, and the old queue took both."""
    _use(100.0)
    user_id = uuid4()
    entry = _live_entry(user_id)

    first = _queue(user_id, entry.run_id, ticker="AAPL", qty=60)
    assert first["queued"] is True

    second = _queue(user_id, entry.run_id, ticker="MSFT", qty=60)
    assert second["queued"] is False
    assert "already committed" in second["reason"]
    assert _queued_count(entry.run_id) == 1


def test_the_refusal_names_both_numbers():
    """A refusal that does not say what the order needed and what was left
    teaches nothing — the player cannot tell how much smaller to go."""
    _use(100.0)
    user_id = uuid4()
    entry = _live_entry(user_id)

    reason = _queue(user_id, entry.run_id, qty=500)["reason"]

    # 500 x $100 = 50,000 notional, PLUS the 10bps fee the order would also
    # have to cover. Quoting the bare notional would understate what the
    # order actually needs, which is how a player retries at a size that is
    # still one fee too big.
    assert "$50,050.00" in reason      # what it needed, fee included
    assert "$10,000.00" in reason      # what was available


# ── What it must never refuse ────────────────────────────────────────────


def test_a_sell_is_never_refused_by_this_check():
    """A sell RETURNS cash and is the order a player most needs from an empty
    balance. Refusing it is the one-way book DEF259 had to fix."""
    _use(100.0)
    user_id = uuid4()
    entry = _live_entry(user_id)

    result = _queue(user_id, entry.run_id, side=Side.SELL, qty=10_000)

    assert result["queued"] is True


def test_a_cover_is_never_refused_by_this_check():
    """Amendment G ruling 5: the cash to buy back was posted at open, and a
    cover blocked for cash traps a player in the one position whose loss is
    unbounded. A buy on a shorted name IS a cover."""
    sim = _use(100.0)
    user_id = uuid4()
    entry = _live_entry(user_id)
    # Open a short during market hours so there is a standing position.
    opened = sim.submit_game_trade(
        user_id=user_id, run_id=entry.run_id, ticker="TSLA",
        side=Side.SELL, quantity=90,
    )
    assert opened.accepted, opened.reason

    # Cash is now nearly all posted as collateral — a plain buy would refuse.
    blocked = _queue(user_id, entry.run_id, ticker="AAPL", qty=90)
    assert blocked["queued"] is False

    # The cover on the shorted name is not.
    cover = _queue(user_id, entry.run_id, ticker="TSLA", qty=90)
    assert cover["queued"] is True


def test_an_unpriceable_ticker_stands_the_check_down_rather_than_guessing():
    """A refusal built on a price we could not obtain is the CR040
    fabrication class. With no price the check declines to decide and the
    drain remains the authority it already was."""

    # Zero is the "no usable price" condition `quote_trade` already refuses
    # on — asserted through the same door the production check uses, rather
    # than through an exception the engine's defensive floor would swallow
    # before this code ever saw it.
    _use(0.0)
    user_id = uuid4()
    entry = _live_entry(user_id)

    result = _queue(user_id, entry.run_id, qty=999_999)

    assert result["queued"] is True, (
        "the check guessed at a price instead of standing down"
    )


def test_the_check_does_not_run_during_market_hours():
    """In hours an order FILLS, and the fill path does its own affordability
    check against the real price. Two checks on one action would refuse with
    two different numbers."""
    _use(100.0)
    user_id = uuid4()
    entry = _live_entry(user_id)

    result = games.submit_trade(
        user_id, entry.run_id, ticker="AAPL", side=Side.BUY, quantity=200,
        now=_OPEN,
    )

    assert result["queued"] is False
    assert result["filled"] is False
    # Refused by the FILL path, which names cash rather than commitment.
    assert "left to commit" not in (result.get("reason") or "")
