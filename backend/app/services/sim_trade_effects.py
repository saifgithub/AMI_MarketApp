"""CR170 §7 — the three things that follow a fill, in one place. CR177 adds
the record of the opposite event: the safety floor refusing one.

Both live here for the same reason: each is a property of a training-path
submit EVENT, not of the route that carried it, and each has two call sites
that must not diverge — a fill happens at the ticket and at the resting-order
sweep, and so does a mandate block (the sweep re-runs the floor at fill time
precisely so a resting order cannot become a time-delayed bypass).



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

from datetime import datetime, timezone
from uuid import UUID

from app.core.logging import logger
from app.db import get_session
from app.schemas.journal import EntryType, JournalEntryCreate, Outcome
from app.schemas.trade import Side
from app.services.journal_store import get_journal_store
from app.services.sim_engine import SimTrade, get_sim_engine
from app.trading_math.markets import Market, format_money, market_for
from app.services.watchlist_store import get_watchlist_store


#: CR222 §3 — the payload key the registered thesis/invalidation/horizon live
#: under on a SIM_TRADE journal entry, and the key the close paths read them
#: back from. One constant, because a writer and a reader that each spell the
#: key themselves are the CR131 drift the audit proved exploitable.
PREREGISTRATION_PAYLOAD_KEY = "preregistration"


def apply_post_fill_effects(
    *,
    user_id: UUID,
    trade: SimTrade,
    thesis: str | None = None,
    invalidation: str | None = None,
    mandate_version: int | None = None,
) -> None:
    """Watchlist and journal for one filled training trade.

    Reads the **trade**, never a request: `trade.stop`/`trade.target` are the
    values `_execute_fill` actually wrote. CR109 slice 7 removed the third
    effect, the `trade_disciplined` reputation award.

    CR222 §3 — `thesis`/`invalidation`/`mandate_version` are the exception, and
    they have to be: neither free-text field is on the trade row (they are a
    record of a decision, not a term of a fill), and the row carries no mandate
    version at all. `trade.horizon_days` IS on the row and is read from there,
    so the one field that has a home keeps it. All three default to None, which
    is what the resting-order sweep passes — an order placed before the flag
    was on carries no registration, and a fabricated one would be worse than
    none (CR040).
    """
    _add_to_watchlist(user_id, trade)
    _append_journal(
        user_id,
        trade,
        thesis=thesis,
        invalidation=invalidation,
        mandate_version=mandate_version,
    )


def _add_to_watchlist(user_id: UUID, trade: SimTrade) -> None:
    """Auto-add the traded ticker so it shows up in the ticker tape.
    Idempotent on (user_id, ticker)."""
    try:
        get_watchlist_store().add(user_id, trade.ticker)
    except Exception:  # pragma: no cover
        pass


def _append_journal(
    user_id: UUID,
    trade: SimTrade,
    *,
    thesis: str | None = None,
    invalidation: str | None = None,
    mandate_version: int | None = None,
) -> None:
    try:
        side_label = (
            trade.side.value if hasattr(trade.side, "value")
            else str(trade.side)
        ).upper()
        if side_label == "SELL":
            try:
                if _journal_sell_close(user_id, trade):
                    return
            except Exception:
                logger.exception("journal_sell_close_failed", user_id=str(user_id))
        market = market_for(trade.ticker)
        stop_str = format_money(trade.stop, market) if trade.stop is not None else "—"
        target_str = format_money(trade.target, market) if trade.target is not None else "—"
        payload: dict = {"trade": trade.to_json()}
        prereg = preregistration_record(
            thesis=thesis,
            invalidation=invalidation,
            horizon_days=trade.horizon_days,
        )
        if prereg is not None:
            payload[PREREGISTRATION_PAYLOAD_KEY] = prereg
        draft = JournalEntryCreate(
            user_id=user_id,
            entry_type=EntryType.SIM_TRADE,
            reference_id=trade.id,
            title=(
                f"{side_label} {trade.quantity:g} {trade.ticker} "
                f"@ {format_money(trade.entry_price, market)}"
            ),
            summary=(
                f"Opened at {format_money(trade.entry_price, market)}. "
                f"Stop {stop_str}. Target {target_str}."
            ),
            ticker=trade.ticker,
            tags=["sim_trade"],
            outcome=Outcome.PENDING,
            payload=payload,
        )
        # Only when the caller actually knows it. `mandate_version` defaults to
        # 1 on the schema, and 1 is a real version — passing None through would
        # stamp "v1" on an entry whose mandate version was never read, which is
        # a fabricated fact rather than a missing one.
        if mandate_version is not None:
            draft = draft.model_copy(update={"mandate_version": mandate_version})
        get_journal_store().append(draft)
    except Exception:  # pragma: no cover
        pass


def _as_utc_iso(iso: str | None) -> str | None:
    """A ledger timestamp as a tz-aware ISO string. Lot dates come off stored rows
    and can be naive (SQLite); a naive string reads as LOCAL time on the client,
    so a UTC instant would show hours off. Naive means UTC here, as everywhere in
    this ledger."""
    if iso is None:
        return None
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _journal_sell_close(user_id: UUID, sell: SimTrade) -> bool:
    """DEF532 — a SELL that closes shares writes a CLOSED entry, not an "Opened
    at" one. Since CR188 a sell order is the app's only manual exit, and the SELL
    row stays `open` forever by design (DEF166), so the opened-entry text read
    "SELL 100 X … Opened at" for what the user did to END a position and no entry
    ever carried the realised P&L. True when the closed entry was written; False
    (nothing written) for a sell that closed nothing, which is a short open and
    keeps its opened entry."""
    effect = get_sim_engine().sell_close_effect(user_id, sell)
    if effect is None:
        return False
    closed_qty, realised, still_held, position_opened_at = effect
    market = market_for(sell.ticker)
    price = sell.entry_price
    closed_at = sell.opened_at.isoformat()
    trade_json = {
        **sell.to_json(),
        # DEF540: `sell.opened_at` is when the SELL filled, i.e. the close time.
        # The entry's "opened_at" is when the position was opened — the buy lot
        # the sell drew from. If the ledger cannot say, leave it absent so the
        # detail screen omits the row rather than showing the close time.
        "opened_at": _as_utc_iso(position_opened_at),
        "status": "closed",
        "closed_at": closed_at,
        "closed_price": price,
        "realised_pnl": realised,
    }
    summary = f"Sold {closed_qty:g} at {format_money(price, market)}."
    if still_held > 1e-6:
        summary += f" {still_held:g} still held."
    get_journal_store().append(JournalEntryCreate(
        user_id=user_id,
        entry_type=EntryType.SIM_TRADE,
        reference_id=sell.id,
        title=(
            f"Closed {sell.ticker} (MANUAL) — "
            f"{format_money(realised, market, signed=True)}"
        ),
        summary=summary,
        ticker=sell.ticker,
        tags=["sim_trade", "closed", "manual"],
        outcome=Outcome.WIN if realised >= 0 else Outcome.LOSS,
        payload={
            "trade": trade_json,
            "outcome": {
                "status": "manual",
                "closed_price": price,
                "realised_pnl": realised,
            },
        },
    ))
    return True


def closed_trade_payload(
    *,
    user_id: UUID,
    trade,
    closed_price: float | None,
    realised_pnl: float,
    status: str,
) -> dict:
    """CR222 §3 — the close entry's payload: the trade, the realised outcome,
    and the registration the position was opened with.

    ONE builder for every close path (the bracket sweep and the manual exit)
    because they are the same event to a reader: the position ended and here is
    how against what was expected. Two builders would diverge on the first
    change, which is the DEF098 shape this codebase keeps meeting.

    `outcome` is a fresh block rather than fields merged into `trade`: the
    trade JSON is a shipped shape the client parses, and adding keys to it
    would put a new fact where an old parser will not look for it.
    """
    payload: dict = {
        "trade": trade.to_json(),
        "outcome": {
            "status": status,
            "closed_price": closed_price,
            "realised_pnl": realised_pnl,
        },
    }
    registered = registered_preregistration(user_id, trade.id)
    if registered is not None:
        payload[PREREGISTRATION_PAYLOAD_KEY] = registered
    return payload


def journal_bracket_closes(
    user_id: UUID, updates: list, market: Market = Market.US,
) -> None:
    """One Journal entry per bracket-closed trade (blocking DB I/O).

    Shared by the evaluate route and the resting-order sweep so a stop that
    fires while the user is away is journaled exactly like one that fires on
    app open (CR282: the Bursa sweep used to discard its closes). Each update is
    returned by `evaluate_outcomes` once, so the two callers cannot double-write.
    """
    if not updates:
        return
    store = get_journal_store()
    trades_by_id = {
        t.id: t for t in get_sim_engine().list_trades(user_id, market=market)
    }
    for u in updates:
        t = trades_by_id.get(u.trade_id)
        if not t:
            continue
        try:
            won = u.new_status == "won"
            store.append(JournalEntryCreate(
                user_id=user_id,
                entry_type=EntryType.SIM_TRADE,
                reference_id=t.id,
                title=(
                    f"Closed {t.ticker} ({u.new_status.upper()}) — "
                    f"{format_money(u.realised_pnl, market, signed=True)}"
                ),
                summary=(
                    f"{'Target hit' if won else 'Stop hit'} "
                    f"at {format_money(u.closed_price, market)}."
                ),
                ticker=t.ticker,
                tags=["sim_trade", "closed", u.new_status],
                outcome=Outcome.WIN if won else Outcome.LOSS,
                # CR222 §3 — the realised outcome sits beside what was
                # registered on the way in, so a review reads thesis →
                # invalidation → what happened without a join.
                payload=closed_trade_payload(
                    user_id=user_id,
                    trade=t,
                    closed_price=u.closed_price,
                    realised_pnl=u.realised_pnl,
                    status=u.new_status,
                ),
            ))
        except Exception:  # pragma: no cover
            logger.exception("journal_bracket_close_failed", user_id=str(user_id))


def journal_manual_close(user_id: UUID, closed: SimTrade) -> None:
    """Write the Journal entry for a manual close (blocking DB I/O). Best-effort:
    a failed write never fails the close."""
    try:
        market = market_for(closed.ticker)
        get_journal_store().append(JournalEntryCreate(
            user_id=user_id,
            entry_type=EntryType.SIM_TRADE,
            reference_id=closed.id,
            title=(
                f"Closed {closed.ticker} (MANUAL) — "
                f"{format_money(closed.realised_pnl, market, signed=True)}"
            ),
            summary=f"Closed at {format_money(closed.closed_price, market)}.",
            ticker=closed.ticker,
            tags=["sim_trade", "closed", "manual"],
            outcome=Outcome.WIN if closed.realised_pnl >= 0 else Outcome.LOSS,
            payload=closed_trade_payload(
                user_id=user_id,
                trade=closed,
                closed_price=closed.closed_price,
                realised_pnl=closed.realised_pnl,
                status="manual",
            ),
        ))
    except Exception:  # pragma: no cover
        logger.exception("journal_manual_close_failed", user_id=str(user_id))


def preregistration_record(
    *,
    thesis: str | None,
    invalidation: str | None,
    horizon_days: int | None,
) -> dict | None:
    """CR222 §3 — the registered decision, or None when nothing was registered.

    None rather than a dict of nulls: an entry with no registration and an
    entry that registered three empty fields are different facts, and a review
    that reads thesis → invalidation → outcome has to be able to tell them
    apart. A partial registration IS recorded (with its own nulls) — the floor
    only permits one when the requirement was off, and hiding what the user did
    write would lose it.
    """
    if thesis is None and invalidation is None and horizon_days is None:
        return None
    return {
        "thesis": thesis,
        "invalidation": invalidation,
        "horizon_days": horizon_days,
    }


def registered_preregistration(user_id: UUID, trade_id: UUID) -> dict | None:
    """CR222 §3 — what this position was registered with when it was opened.

    Read back off the OPENING journal entry so a close entry can carry it
    beside the realised outcome, which is the whole point of the feature: a
    review reads thesis → invalidation → what actually happened, in one row,
    without a join the reader has to know to make.

    Best-effort in the same sense as everything else in this module — the
    position is already closed and the cash already moved by the time this
    runs. A failed read costs the close entry its registration block, not the
    entry, and it is logged rather than swallowed: a close that silently loses
    the thesis makes the feature look like it never worked.
    """
    try:
        entry = get_journal_store().first_for_reference(
            user_id, EntryType.SIM_TRADE, trade_id,
        )
    except Exception:
        logger.exception(
            "preregistration_readback_failed",
            user_id=str(user_id),
            trade_id=str(trade_id),
        )
        return None
    if entry is None:
        return None
    record = entry.payload.get(PREREGISTRATION_PAYLOAD_KEY)
    return dict(record) if isinstance(record, dict) else None


def record_compliance_block(
    *,
    user_id: UUID,
    ticker: str,
    side,
    quantity: float,
    order_type,
    compliance,
    source: str,
    reference_id: UUID | None = None,
) -> None:
    """CR177 — one durable journal entry for a trade the safety floor refused.

    The discriminator lives HERE, not at the call sites, so the two paths
    cannot diverge on it: only a refusal that names its rule
    (``compliance.blocked_by``) is a safety-floor block. Mechanical refusals —
    insufficient cash, a wrong-side bracket — carry ``blocked_by=None`` and
    are not a mandate decision, so they stay unjournaled (the same fence that
    keeps the game path out: a cash refusal is not the floor firing).

    Every identical repeat is written. Twenty taps against one cap are twenty
    rows because the repetition IS the teaching signal (spec §5.2) — the
    Journal reader aggregates; the data stays honest. `dedupe_key` stays NULL
    deliberately: collapsing repeats at write time is the position §5.2
    rejects.

    Best-effort like every other effect in this module — the block already
    protected the user and the response already told them; a failing journal
    write must not turn "AMI stopped you" into a 500 the user reads as "did
    my trade happen?". Unlike the fill effects it logs the failure loudly:
    losing this row silently would recreate the exact invisibility this CR
    exists to remove (CR040).

    ``source`` is ``"ticket"`` or ``"resting_order"`` — with no request in
    the sweep's call stack, the entry itself must say which path refused.
    """
    blocked_by = getattr(compliance, "blocked_by", None)
    if not blocked_by:
        return
    try:
        side_label = (
            side.value if hasattr(side, "value") else str(side)
        ).upper()
        order_type_label = (
            order_type.value if hasattr(order_type, "value")
            else (str(order_type) if order_type is not None else None)
        )
        violations = list(getattr(compliance, "violations", []) or [])
        sharia = getattr(compliance, "sharia_verdict", None)
        get_journal_store().append(JournalEntryCreate(
            user_id=user_id,
            entry_type=EntryType.COMPLIANCE_BLOCK,
            reference_id=reference_id,
            title=f"BLOCKED: {side_label} {quantity:g} {ticker}",
            summary=(
                violations[0] if violations else f"Blocked by {blocked_by}."
            ),
            ticker=ticker,
            tags=["compliance_block", source],
            # A block has no win/loss and must never render as either —
            # None, not PENDING: nothing is pending, the decision is final.
            outcome=None,
            payload={
                "blocked_by": blocked_by,
                "violations": violations,
                "request": {
                    "ticker": ticker,
                    "side": side_label,
                    "quantity": quantity,
                    "order_type": order_type_label,
                },
                "sharia_verdict": (
                    sharia.model_dump(mode="json") if sharia is not None
                    else None
                ),
                "classification_verdicts": [
                    v.model_dump(mode="json")
                    for v in getattr(compliance, "classification_verdicts", [])
                ],
                "advisories": list(
                    getattr(compliance, "advisories", []) or []
                ),
                "source": source,
            },
        ))
    except Exception:
        logger.exception(
            "compliance_block_journal_write_failed",
            user_id=str(user_id),
            ticker=ticker,
            blocked_by=blocked_by,
            source=source,
        )


# CR109 slice 7 — `_award_disciplined` stood here: a buy carrying both a stop
# and a target, having cleared the mandate check, scored `trade_disciplined`.
# It scored for the league Amendment A retired, so it is gone with it. The
# discipline it rewarded is still enforced — the mandate check and the bracket
# rules are unchanged; only the points are gone.
