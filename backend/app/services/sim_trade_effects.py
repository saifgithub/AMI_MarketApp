"""CR170 §7 — the three things that follow a fill, in one place.

Extracted verbatim from `api/sim.py::submit_trade`, where the watchlist add,
the journal entry and the `trade_disciplined` award have lived since they were
each written. They were never properties of *the submit route*; they are
properties of **a fill**, and CR170 is about to add a second fill site (the
resting-order sweep, which reaches `SimEngine.fill_resting_order` with no HTTP
request anywhere in the call stack). Left in the route, a resting BUY with a
stop and a target would fill without a journal entry, without the ticker
appearing on the tape, and without the reputation award it earns via the
ticket — three silent divergences between two paths a user cannot tell apart.

This commit is deliberately behaviour-neutral: the route now calls this, the
body is the same code, and the existing route tests pin it. The sweep wires in
afterwards.

**Every effect is best-effort and swallows its own exception.** That is
inherited, not invented, and it is right: the money has already moved and the
trade row is committed by the time this runs. A watchlist write that fails must
not turn a completed fill into an error the user reads as "the trade did not
happen". Each block therefore fails alone — a raising journal store cannot cost
the user their reputation award.

Dedup stays `ref_id=str(trade.id)`, which is what keeps the award un-farmable
regardless of which path produced the fill.
"""

from __future__ import annotations

from uuid import UUID

from app.db import get_session
from app.schemas.journal import EntryType, JournalEntryCreate, Outcome
from app.schemas.trade import Side
from app.services.journal_store import get_journal_store
from app.services.reputation_service import get_reputation_service
from app.services.sim_engine import SimTrade
from app.services.watchlist_store import get_watchlist_store


def apply_post_fill_effects(*, user_id: UUID, trade: SimTrade) -> None:
    """Watchlist, journal and reputation for one filled training trade.

    Reads the **trade**, never a request: `trade.stop`/`trade.target` are the
    values `_execute_fill` actually wrote, so a resting order that carried its
    bracket from placement earns the same award as one typed at the ticket.
    """
    _add_to_watchlist(user_id, trade)
    _append_journal(user_id, trade)
    _award_disciplined(user_id, trade)


def _add_to_watchlist(user_id: UUID, trade: SimTrade) -> None:
    """Auto-add the traded ticker so it shows up in the ticker tape.
    Idempotent on (user_id, ticker)."""
    try:
        get_watchlist_store().add(user_id, trade.ticker)
    except Exception:  # pragma: no cover
        pass


def _append_journal(user_id: UUID, trade: SimTrade) -> None:
    try:
        side_label = (
            trade.side.value if hasattr(trade.side, "value")
            else str(trade.side)
        ).upper()
        stop_str = f"${trade.stop:.2f}" if trade.stop is not None else "—"
        target_str = f"${trade.target:.2f}" if trade.target is not None else "—"
        get_journal_store().append(JournalEntryCreate(
            user_id=user_id,
            entry_type=EntryType.SIM_TRADE,
            reference_id=trade.id,
            title=(
                f"{side_label} {trade.quantity:g} {trade.ticker} "
                f"@ ${trade.entry_price:.2f}"
            ),
            summary=(
                f"Opened at ${trade.entry_price:.2f}. "
                f"Stop {stop_str}. Target {target_str}."
            ),
            ticker=trade.ticker,
            tags=["sim_trade"],
            outcome=Outcome.PENDING,
            payload={"trade": trade.to_json()},
        ))
    except Exception:  # pragma: no cover
        pass


def _award_disciplined(user_id: UUID, trade: SimTrade) -> None:
    """Reputation (CR004): a buy with both stop AND target that cleared the
    mandate check is a disciplined trade. Trade-id ref dedup + the ≤3/day
    per-type limit keep it un-farmable."""
    side = trade.side if isinstance(trade.side, Side) else Side(trade.side)
    if side != Side.BUY or trade.stop is None or trade.target is None:
        return
    try:
        with get_session() as s:
            get_reputation_service().award(
                s, user_id=user_id,
                event_type="trade_disciplined", ref_id=str(trade.id),
            )
    except Exception:  # pragma: no cover
        pass
