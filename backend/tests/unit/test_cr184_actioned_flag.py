"""CR184 — `actioned` flag on journal entries.

list_for_user must stamp `actioned` on ROOM_RUN entries via ONE batch query
against sim_trades.verdict_ref, scoped to the user's TRAINING ledger
(training_trade_scope, DEF269). Semantics under test:

  - actioned=True  when a training-portfolio trade carries the entry's
    reference_id as verdict_ref (any status, per _existing_trade_for_verdict).
  - actioned=False when the room run has a verdict but no such trade —
    including when SOMEONE ELSE traded that verdict (scope isolation) or the
    trade sits in a game portfolio (DEF269).
  - actioned=None  on non-ROOM_RUN entries and verdict-less room runs —
    N/A is never rendered as False (CR040).
  - Exactly ONE extra query regardless of how many room entries are listed.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import event

from sqlalchemy import select

from app.db import get_session
from app.db.models import SimHoldingRow, SimPortfolioRow, SimTradeRow
from app.db.session import get_engine
from app.schemas import Plan
from app.schemas.journal import EntryType, JournalEntryCreate
from app.services.journal_store import JournalStore


def _room_entry(user_id: UUID, run_id: UUID, *, title: str = "convene",
                with_verdict: bool = True) -> JournalEntryCreate:
    payload = {"verdict": {"action": "APPROVE"}} if with_verdict else {"verdict": None}
    return JournalEntryCreate(
        user_id=user_id,
        entry_type=EntryType.ROOM_RUN,
        reference_id=run_id,
        title=title,
        ticker="NVDA",
        payload=payload,
    )


def _make_portfolio(user_id: UUID, *, kind: str = "training",
                    run_id: UUID | None = None) -> UUID:
    with get_session() as s:
        port = SimPortfolioRow(
            user_id=user_id, kind=kind, run_id=run_id,
            starting_capital=10000, current_cash=9000,
        )
        s.add(port)
        s.flush()
        return port.id


def _make_trade(user_id: UUID, portfolio_id: UUID, verdict_ref: UUID) -> None:
    """Open buy + matching holding — the conftest ledger/holdings drift guard
    requires every engine-shaped open trade to be backed by held shares."""
    with get_session() as s:
        s.add(SimTradeRow(
            user_id=user_id, portfolio_id=portfolio_id,
            ticker="NVDA", side="buy", quantity=10, entry_price=150,
            verdict_ref=verdict_ref,
        ))
        holding = s.execute(
            select(SimHoldingRow)
            .where(SimHoldingRow.portfolio_id == portfolio_id)
            .where(SimHoldingRow.ticker == "NVDA")
        ).scalar_one_or_none()
        if holding is not None:
            holding.quantity = float(holding.quantity) + 10
        else:
            s.add(SimHoldingRow(
                portfolio_id=portfolio_id, ticker="NVDA",
                quantity=10, avg_cost=150,
            ))


def test_two_convenes_one_actioned():
    store = JournalStore()
    user_id = uuid4()
    run_a, run_b = uuid4(), uuid4()
    store.append(_room_entry(user_id, run_a, title="actioned one"))
    store.append(_room_entry(user_id, run_b, title="ignored one"))
    port = _make_portfolio(user_id)
    _make_trade(user_id, port, run_a)

    entries, total, _ = store.list_for_user(user_id, plan=Plan.TRADER)
    assert total == 2
    by_title = {e.title: e.actioned for e in entries}
    assert by_title == {"actioned one": True, "ignored one": False}


def test_scope_isolation_other_users_trade_does_not_action_mine():
    store = JournalStore()
    me, stranger = uuid4(), uuid4()
    run_id = uuid4()
    store.append(_room_entry(me, run_id))
    # The stranger executes a trade against the SAME verdict_ref in their own
    # training portfolio — my entry must stay unactioned.
    stranger_port = _make_portfolio(stranger)
    _make_trade(stranger, stranger_port, run_id)

    entries, _, _ = store.list_for_user(me, plan=Plan.TRADER)
    assert len(entries) == 1
    assert entries[0].actioned is False


def test_game_portfolio_trade_does_not_action():
    store = JournalStore()
    user_id = uuid4()
    run_id = uuid4()
    store.append(_room_entry(user_id, run_id))
    game_port = _make_portfolio(user_id, kind="game", run_id=uuid4())
    _make_trade(user_id, game_port, run_id)

    entries, _, _ = store.list_for_user(user_id, plan=Plan.TRADER)
    assert entries[0].actioned is False


def test_none_on_non_room_and_verdictless_entries():
    store = JournalStore()
    user_id = uuid4()
    store.append(JournalEntryCreate(
        user_id=user_id, entry_type=EntryType.ONE_ON_ONE, title="chat",
    ))
    store.append(_room_entry(user_id, uuid4(), title="no verdict",
                             with_verdict=False))
    entries, _, _ = store.list_for_user(user_id, plan=Plan.TRADER)
    assert all(e.actioned is None for e in entries)


def test_closed_trade_still_counts_as_actioned():
    store = JournalStore()
    user_id = uuid4()
    run_id = uuid4()
    store.append(_room_entry(user_id, run_id))
    port = _make_portfolio(user_id)
    with get_session() as s:
        s.add(SimTradeRow(
            user_id=user_id, portfolio_id=port,
            ticker="NVDA", side="buy", quantity=10, entry_price=150,
            verdict_ref=run_id, status="closed", closed_price=160,
        ))
    entries, _, _ = store.list_for_user(user_id, plan=Plan.TRADER)
    assert entries[0].actioned is True


def test_one_batch_query_not_n():
    store = JournalStore()
    user_id = uuid4()
    port = _make_portfolio(user_id)
    for i in range(5):
        run_id = uuid4()
        store.append(_room_entry(user_id, run_id, title=f"convene {i}"))
        if i % 2 == 0:
            _make_trade(user_id, port, run_id)

    engine = get_engine()
    statements: list[str] = []

    def _capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", _capture)
    try:
        entries, _, _ = store.list_for_user(user_id, plan=Plan.TRADER)
    finally:
        event.remove(engine, "before_cursor_execute", _capture)

    assert len(entries) == 5
    sim_trade_selects = [
        st for st in statements
        if "sim_trades" in st and st.lstrip().upper().startswith("SELECT")
    ]
    assert len(sim_trade_selects) == 1, statements
