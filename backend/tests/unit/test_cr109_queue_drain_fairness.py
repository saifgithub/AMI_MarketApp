"""CR109 — what happens at the open when the queued orders cost more than
the cash behind them.

Saiful, looking at a run with 10,003.29 committed against a 10,000 stake:
*"I have committed more than the 10K allocated AMI Cash... what will happen
when we trade for real [i.e. when the market opens]? 1. Do we adjust? How?
2. Do we decline trade? Which one?"*

The answers the code gives, and which these tests hold in place:

1. **We do not adjust.** There is no partial fill. An order fills whole or
   is refused whole. A partial fill silently changes the position the player
   asked for, and in a scored contest that is worse than a clean refusal.

2. **We decline, oldest first.** `process_queued_orders` had no `ORDER BY`,
   so *which* orders survived came down to whatever order Postgres returned
   rows in — undefined behaviour deciding a scored result. FIFO is the only
   rule a player can reason about while placing the orders, and the only one
   that does not reward re-queueing.

3. **A refusal is reported.** The refused row carries a reason and used to be
   filtered out of the orders list, so the order simply vanished overnight.

Over-commitment cannot be designed away, which is why this path has to be
right rather than merely prevented: a set of orders that fits tonight need
not fit at tomorrow's open, because the prices move in between.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.services import games_service as games


def _order(session, *, run_id, user_id, ticker, quantity, queued_at, state="queued",
           cancel_reason=None):
    from app.db.models import GameQueuedOrderRow

    row = GameQueuedOrderRow(
        run_id=run_id,
        user_id=user_id,
        ticker=ticker,
        side="buy",
        quantity=quantity,
        order_type="market",
        state=state,
        queued_at=queued_at,
        cancel_reason=cancel_reason,
    )
    session.add(row)
    session.flush()
    return row


def test_drain_reads_oldest_first():
    """The refusal rule is only fair if it is deterministic.

    Asserted against the STATEMENT rather than a live drain, because the
    property under test is the ordering the database is asked for — and a
    test that filled real orders would pass just as happily on an unordered
    query whenever Postgres happened to return insertion order, which is
    most of the time. That is precisely how this shipped unordered.
    """
    import inspect

    src = inspect.getsource(games.process_queued_orders)
    assert "order_by" in src, (
        "the drain must impose an explicit order — without one, which orders "
        "survive an over-committed book is undefined behaviour deciding a "
        "scored result"
    )
    assert "queued_at.asc()" in src, (
        "oldest first: the orders committed to first are the ones that "
        "survive, which is the only rule a player can reason about in advance"
    )


def test_no_partial_fill_anywhere_in_the_drain():
    """We decline whole orders; we never quietly shrink one.

    A partial fill hands the player a position they did not choose. The
    guard is that the drain passes the stored quantity straight through.
    """
    import inspect

    src = inspect.getsource(games.process_queued_orders)
    assert 'quantity=t["quantity"]' in src, (
        "the drain must submit the quantity the player queued, untouched — "
        "any scaling here is a partial fill by another name"
    )


@pytest.mark.parametrize("reason", [None, "insufficient cash: need $500.00, have $12.00"])
def test_a_refused_order_is_reported_and_a_self_cancel_is_not(monkeypatch, reason):
    """`cancel_reason IS NOT NULL` is exactly "the system refused this".

    A player's own cancel writes no reason (`cancel_queued_order` sets state
    and nothing else), so nobody is told about the order they cancelled
    themselves — while an order the open refused comes back with `state:
    "refused"` and the cause, instead of vanishing.
    """
    from app.db.session import get_session

    run_id, user_id = uuid4(), uuid4()
    monkeypatch.setattr(games, "_require_live_entry", lambda *a, **k: None)
    monkeypatch.setattr(games, "_queued_orders_priced", lambda *a, **k: ([], 0.0))

    with get_session() as s:
        _order(
            s, run_id=run_id, user_id=user_id, ticker="BAC", quantity=7.5,
            queued_at=datetime.now(timezone.utc) - timedelta(hours=2),
            state="cancelled", cancel_reason=reason,
        )

    out = games.list_queued_orders(user_id, run_id)

    if reason is None:
        assert out == [], "a player's own cancellation is not news to them"
    else:
        assert len(out) == 1, "an order the open refused must not vanish"
        assert out[0]["state"] == "refused"
        assert out[0]["cancel_reason"] == reason
        assert out[0]["ticker"] == "BAC"


def test_refusals_older_than_one_open_are_not_carried_forever(monkeypatch):
    from app.db.session import get_session

    run_id, user_id = uuid4(), uuid4()
    monkeypatch.setattr(games, "_require_live_entry", lambda *a, **k: None)
    monkeypatch.setattr(games, "_queued_orders_priced", lambda *a, **k: ([], 0.0))

    with get_session() as s:
        _order(
            s, run_id=run_id, user_id=user_id, ticker="RXT", quantity=1.0,
            queued_at=datetime.now(timezone.utc) - timedelta(days=3),
            state="cancelled", cancel_reason="insufficient cash",
        )

    assert games.list_queued_orders(user_id, run_id) == [], (
        "a refusal belongs to the open it happened at; three days later it is "
        "clutter on a surface that exists to show what is about to happen"
    )


def test_a_live_queued_order_declares_its_state(monkeypatch):
    """The list is now mixed, so the client must never infer which is which."""
    from app.db.session import get_session

    run_id, user_id = uuid4(), uuid4()
    monkeypatch.setattr(games, "_require_live_entry", lambda *a, **k: None)

    with get_session() as s:
        _order(
            s, run_id=run_id, user_id=user_id, ticker="AAPL", quantity=2.0,
            queued_at=datetime.now(timezone.utc),
        )

    class _Q:
        price = 100.0
        source = "yfinance"

    class _Sim:
        def current_quote(self, _ticker):
            return _Q()

    monkeypatch.setattr(games, "get_sim_engine", lambda: _Sim())

    out = games.list_queued_orders(user_id, run_id)
    assert len(out) == 1
    assert out[0]["state"] == "queued"
