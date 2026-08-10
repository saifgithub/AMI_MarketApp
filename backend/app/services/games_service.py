"""CR109 slice 2 — "the run": weekly field roll, entry, the game trade
path's orchestration (market-hours queue-or-fill), and restart/forfeit.

A game "run" is not its own table — it is the pairing of one `GameEntryRow`
(`docs/forward_planning/CR109_pnl_game_ami_cash/implementation_plan.md`
§4.4) with one `SimPortfolioRow(kind="game")` sharing the same `run_id`.
This module owns the field state machine and entry lifecycle; the actual
fill mechanics live in `SimEngine.submit_game_trade` (§7.1 — the game path
never touches the training submit path or its safety floor), and the
trading-cost constant lives in `games_scoring.py`.

Weekly cadence ONLY, fixed calendar starts (implementation_plan.md §2
slice 2). A weekly field runs Monday-Friday US market dates; entry for a
given Monday opens the moment the PRIOR week's field locks, and locks
`_LOCK_BUFFER` before that Monday's market open — so at any given time
there is exactly one `open`-kind weekly field accepting entries. State
machine: `announced -> entry_open -> locked -> live` (slice 2 never writes
past `live` — settling/closing is slice 3).

Entry is FREE, always — an entry fee is legal consideration and would
break CR109 §15's simulation-only legal position (design doc). Restart
sets the entry to `forfeit`; there is no career-points ledger yet (slice
3), so there is nothing to debit.
"""

from __future__ import annotations

from datetime import date, datetime, time as dt_time, timedelta, timezone
from typing import Optional
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.core.logging import logger
from app.db import get_session
from app.db.models import GameEntryRow, GameFieldRow, GameQueuedOrderRow
from app.schemas.trade import OrderType, Side
from app.services.games_scoring import trade_fee
from app.services.portfolio_nav_daily import nav_history, twr_pct_for_window
from app.services.sim_engine import get_sim_engine
from app.trading_math.market_hours import is_us_market_open, next_us_market_open

WEEKLY_CADENCE = "week"
_SUPPORTED_CADENCES = (WEEKLY_CADENCE,)
INTENTS = ("wild", "thesis", "disciplined")

_ET = ZoneInfo("America/New_York")
_MARKET_OPEN = dt_time(9, 30)
# Entries close (and the field state flips entry_open -> locked) this long
# before the run's own market open. Big enough that "locked" is an
# observable state rather than an instant collapsed into "live".
_LOCK_BUFFER = timedelta(minutes=30)
_RUN_DAYS = 4  # Monday .. Friday inclusive


class GamesServiceError(Exception):
    """Base for every games_service error — routes translate these to
    the right HTTP status in `api/games.py`."""


class AlreadyEnteredError(GamesServiceError):
    """The user already holds a live entry for this cadence (409)."""


class FieldNotOpenError(GamesServiceError):
    """The target field is not accepting entries right now."""


class UnsupportedCadenceError(GamesServiceError):
    """Slice 2 supports `week` only."""


class RunNotFoundError(GamesServiceError):
    """No entry exists for this (user, run_id) pair."""


class RunNotLiveError(GamesServiceError):
    """The entry exists but is not `entered`/`active` (already forfeited,
    finished, or void)."""


# ── Pure date/time helpers ────────────────────────────────────────────────


def _week_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _market_open_et(d: date) -> datetime:
    return datetime.combine(d, _MARKET_OPEN, tzinfo=_ET)


def _weekly_window(monday: date) -> tuple[datetime, datetime, datetime, date]:
    """(entry_opens_at, locks_at, market_open, ends_on) for the weekly
    field starting `monday`. `entry_opens_at` is set to exactly when the
    PRIOR week's field locks, so the entry-accepting window for one field
    starts the instant the previous one's ends — there is never a gap
    (nor an overlap) between two weekly fields' entry windows.
    """
    ends_on = monday + timedelta(days=_RUN_DAYS)
    market_open = _market_open_et(monday)
    locks_at = market_open - _LOCK_BUFFER
    entry_opens_at = _market_open_et(monday - timedelta(days=7)) - _LOCK_BUFFER
    return entry_opens_at, locks_at, market_open, ends_on


def _resolve_state(
    now: datetime, entry_opens_at: datetime, locks_at: datetime, market_open: datetime,
) -> str:
    if now < entry_opens_at:
        return "announced"
    if now < locks_at:
        return "entry_open"
    if now < market_open:
        return "locked"
    # Slice 2 never advances past `live` — settling/closing is slice 3.
    return "live"


# ── Field roll ───────────────────────────────────────────────────────────


def ensure_weekly_field(session, *, now: datetime | None = None) -> GameFieldRow:
    """Idempotent create-or-fetch of the weekly `open` field currently
    accepting entries (or, if none is entry-accepting at this instant —
    e.g. queried mid-week after this week's field already locked — the
    NEXT one). Updates `state` in place on every call so a field's state
    column never drifts stale between rolls.
    """
    now = now or datetime.now(timezone.utc)
    now_et = now.astimezone(_ET)
    this_monday = _week_monday(now_et.date())
    _, this_locks_at, _, _ = _weekly_window(this_monday)
    target_monday = (
        this_monday if now < this_locks_at else this_monday + timedelta(days=7)
    )

    entry_opens_at, locks_at, market_open, ends_on = _weekly_window(target_monday)
    row = session.execute(
        select(GameFieldRow).where(
            GameFieldRow.cadence == WEEKLY_CADENCE,
            GameFieldRow.kind == "open",
            GameFieldRow.starts_on == target_monday,
        )
    ).scalar_one_or_none()
    new_state = _resolve_state(now, entry_opens_at, locks_at, market_open)
    if row is None:
        row = GameFieldRow(
            cadence=WEEKLY_CADENCE,
            state=new_state,
            entry_opens_at=entry_opens_at,
            locks_at=locks_at,
            starts_on=target_monday,
            ends_on=ends_on,
            min_entrants=None,
            max_wait_days=None,
            scoring_basis=None,
            benchmark_ticker="SPY",
            entrant_count=0,
            kind="open",
            points_policy="full",
        )
        session.add(row)
        session.flush()
    elif row.state != new_state:
        row.state = new_state
        session.flush()
    return row


# ── Reads ────────────────────────────────────────────────────────────────


def list_cadences(user_id: UUID, *, now: datetime | None = None) -> list[dict]:
    """`GET /v1/games/cadences` — slice 2 has exactly one cadence (weekly).
    Every number carries what produced it (CR040): `queue_count` is the
    field's own denormalised `entrant_count`, `deadline` is `locks_at`.
    """
    now = now or datetime.now(timezone.utc)
    with get_session() as s:
        field = ensure_weekly_field(s, now=now)
        held = s.execute(
            select(GameEntryRow.id)
            .join(GameFieldRow, GameEntryRow.field_id == GameFieldRow.id)
            .where(
                GameFieldRow.kind == "open",
                GameFieldRow.cadence == WEEKLY_CADENCE,
                GameEntryRow.user_id == user_id,
                GameEntryRow.state.in_(("entered", "active")),
            )
            .limit(1)
        ).first() is not None
        return [{
            "cadence": WEEKLY_CADENCE,
            "field_id": str(field.id),
            "state": field.state,
            "entry_opens_at": field.entry_opens_at.isoformat(),
            "locks_at": field.locks_at.isoformat(),
            "starts_on": field.starts_on.isoformat(),
            "ends_on": field.ends_on.isoformat(),
            "queue_count": field.entrant_count,
            "deadline": field.locks_at.isoformat(),
            "already_held": held,
        }]


def list_live_runs(user_id: UUID) -> list[dict]:
    """`GET /v1/games/runs` — the caller's OWN live runs only."""
    today = datetime.now(timezone.utc).date()
    with get_session() as s:
        rows = s.execute(
            select(GameEntryRow, GameFieldRow)
            .join(GameFieldRow, GameEntryRow.field_id == GameFieldRow.id)
            .where(
                GameEntryRow.user_id == user_id,
                GameEntryRow.state.in_(("entered", "active")),
            )
        ).all()
    out = []
    for entry, field in rows:
        nav_rows = nav_history(user_id, run_id=entry.run_id)
        out.append({
            "run_id": str(entry.run_id),
            "field_id": str(field.id),
            "cadence": field.cadence,
            "state": entry.state,
            "intent": entry.intent,
            "twr_pct": twr_pct_for_window(nav_rows),
            "days_left": max((field.ends_on - today).days, 0),
            "starts_on": field.starts_on.isoformat(),
            "ends_on": field.ends_on.isoformat(),
            "fees_paid": float(entry.fees_paid),
            "trade_count": entry.trade_count,
        })
    return out


def _find_entry(user_id: UUID, run_id: UUID) -> Optional[GameEntryRow]:
    with get_session() as s:
        return s.execute(
            select(GameEntryRow).where(
                GameEntryRow.user_id == user_id, GameEntryRow.run_id == run_id,
            )
        ).scalar_one_or_none()


def get_run_detail(user_id: UUID, run_id: UUID) -> dict | None:
    """`GET /v1/games/runs/{run_id}` — detail + NAV series for the curve.
    `None` if this run doesn't belong to `user_id` — never leaks whether
    it belongs to someone else."""
    with get_session() as s:
        row = s.execute(
            select(GameEntryRow, GameFieldRow)
            .join(GameFieldRow, GameEntryRow.field_id == GameFieldRow.id)
            .where(GameEntryRow.user_id == user_id, GameEntryRow.run_id == run_id)
        ).first()
        if row is None:
            return None
        entry, field = row
        entry_state, intent, fees_paid, trade_count = (
            entry.state, entry.intent, float(entry.fees_paid), entry.trade_count,
        )
        cadence, starts_on, ends_on = field.cadence, field.starts_on, field.ends_on

    nav_rows = nav_history(user_id, run_id=run_id)
    portfolio, marks, total_value, _drawdown_pct, source = (
        get_sim_engine().portfolio_marks_snapshot(user_id, kind="game", run_id=run_id)
    )
    _queued, _committed = _queued_orders_priced(user_id, run_id)
    return {
        "run_id": str(run_id),
        "cadence": cadence,
        "state": entry_state,
        "intent": intent,
        "starts_on": starts_on.isoformat(),
        "ends_on": ends_on.isoformat(),
        "current_cash": float(portfolio.current_cash),
        # §13.3's Queued-orders surface requires `cash committed`. Without
        # it the ticket offered the whole stake no matter how much was
        # already queued against it, so a player could commit several times
        # their book. `cash_available` is what the ticket must size against.
        "cash_committed": _committed,
        "cash_available": round(float(portfolio.current_cash) - _committed, 2),
        "queued_order_count": len(_queued),
        "total_value": round(float(total_value), 2),
        "price_source": source,
        "fees_paid": fees_paid,
        "trade_count": trade_count,
        "twr_pct": twr_pct_for_window(nav_rows),
        "nav_series": [
            {
                "as_of_date": r.as_of_date.isoformat(),
                "nav": float(r.nav),
                "cash": float(r.cash),
                "price_source": r.price_source,
                "capital_event": r.capital_event,
            }
            for r in nav_rows
        ],
        "holdings": [
            {
                "ticker": h.ticker,
                "quantity": h.quantity,
                "avg_cost": h.avg_cost,
                "mark": marks.get(h.ticker, h.avg_cost),
            }
            for h in portfolio.holdings
        ],
    }


# ── Entry ────────────────────────────────────────────────────────────────


def enter_field(
    user_id: UUID,
    *,
    cadence: str = WEEKLY_CADENCE,
    intent: str | None = None,
    now: datetime | None = None,
) -> GameEntryRow:
    """`POST /v1/games/enter`. Entry is FREE — never charge here; an entry
    fee is legal consideration and would break CR109 §15 (design doc).
    Raises `AlreadyEnteredError` (-> 409) if the user already holds a live
    run for this cadence.
    """
    if cadence not in _SUPPORTED_CADENCES:
        raise UnsupportedCadenceError(
            f"only {_SUPPORTED_CADENCES} supported in slice 2, got {cadence!r}"
        )
    if intent is not None and intent not in INTENTS:
        raise ValueError(f"intent must be one of {INTENTS}, got {intent!r}")
    now = now or datetime.now(timezone.utc)

    try:
        with get_session() as s:
            field = ensure_weekly_field(s, now=now)
            if field.state not in ("announced", "entry_open"):
                raise FieldNotOpenError(
                    f"field {field.id} is {field.state}, not accepting entries"
                )
            already = s.execute(
                select(GameEntryRow.id)
                .join(GameFieldRow, GameEntryRow.field_id == GameFieldRow.id)
                .where(
                    GameFieldRow.kind == "open",
                    GameFieldRow.cadence == cadence,
                    GameEntryRow.user_id == user_id,
                    GameEntryRow.state.in_(("entered", "active")),
                )
                .limit(1)
            ).first()
            if already is not None:
                raise AlreadyEnteredError(
                    f"user {user_id} already holds a live {cadence} run"
                )

            run_id = uuid4()
            entry = GameEntryRow(
                field_id=field.id,
                user_id=user_id,
                run_id=run_id,
                state="entered",
                intent=intent,
                fees_paid=0,
                trade_count=0,
            )
            s.add(entry)
            field.entrant_count = (field.entrant_count or 0) + 1
            s.flush()
            entry_id = entry.id
    except IntegrityError as exc:
        # The DB-level UniqueConstraint(field_id, user_id) is the backstop
        # behind the pre-check above — a concurrent second /enter losing
        # this race lands here rather than corrupting the table.
        raise AlreadyEnteredError(
            f"user {user_id} already holds a live {cadence} run"
        ) from exc

    # Lazily create the game portfolio NOW (not deferred to first trade) so
    # GET /v1/games/runs/{run_id} works immediately after entry.
    get_sim_engine().ensure_portfolio(user_id, kind="game", run_id=run_id)

    _log_close_to_reentry_if_any(user_id, entry_id, now=now)

    with get_session() as s:
        return s.execute(
            select(GameEntryRow).where(GameEntryRow.id == entry_id)
        ).scalar_one()


def _log_close_to_reentry_if_any(user_id: UUID, new_entry_id, *, now: datetime) -> None:
    """CR109 slice 3 — `close -> re-entry` is one of the two numbers Gate 1
    runs on (implementation_plan.md §9 / design §10.3), instrumented from
    day one via a structured log line rather than a new table — the same
    footprint `sim_trade_filled` / `account_merge_executed` already use
    elsewhere in this codebase. A no-op (logs nothing) the first time a
    user ever enters, since there is no prior close to measure a gap from.
    """
    with get_session() as s:
        prior = s.execute(
            select(GameEntryRow)
            .where(
                GameEntryRow.user_id == user_id,
                GameEntryRow.state.in_(("finished", "void")),
                GameEntryRow.scored_at.isnot(None),
            )
            .order_by(GameEntryRow.scored_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if prior is None:
            return
        prior_entry_id, prior_scored_at, prior_run_id = (
            prior.id, prior.scored_at, prior.run_id,
        )
    # SQLite round-trips DateTime(timezone=True) as naive — the same
    # normalisation `portfolio_nav_daily.py`'s `_as_utc` already applies.
    if prior_scored_at.tzinfo is None:
        prior_scored_at = prior_scored_at.replace(tzinfo=timezone.utc)
    gap = (now - prior_scored_at).total_seconds()
    logger.info(
        "game_close_to_reentry",
        user_id=str(user_id), new_entry_id=str(new_entry_id),
        prior_entry_id=str(prior_entry_id), prior_run_id=str(prior_run_id),
        reentry_gap_seconds=gap,
    )


# ── The trade path's orchestration ──────────────────────────────────────


def _require_live_entry(user_id: UUID, run_id: UUID) -> None:
    entry = _find_entry(user_id, run_id)
    if entry is None:
        raise RunNotFoundError(f"no run {run_id} for user {user_id}")
    if entry.state not in ("entered", "active"):
        raise RunNotLiveError(f"run {run_id} is {entry.state}, not live")


def _record_fill(user_id: UUID, run_id: UUID, *, fee: float) -> None:
    """Post-fill bookkeeping on `game_entries` — `fees_paid` (denormalised
    total for the Close's cost line, slice 3) and `trade_count` (the
    stipend's `>= 1 executed trade` guard, slice 3). Deliberately a
    SEPARATE transaction from the fill itself: `SimEngine._execute_fill`
    knows nothing about `game_entries` (it is a portfolio-mechanics module,
    not a games-domain one), so this is where the two meet.
    """
    with get_session() as s:
        entry = s.execute(
            select(GameEntryRow).where(
                GameEntryRow.user_id == user_id, GameEntryRow.run_id == run_id,
            )
        ).scalar_one_or_none()
        if entry is None:
            return
        entry.fees_paid = round(float(entry.fees_paid or 0) + fee, 2)
        entry.trade_count = (entry.trade_count or 0) + 1
        if entry.state == "entered":
            entry.state = "active"


def _queued_orders_priced(
    user_id: UUID, run_id: UUID,
) -> tuple[list[dict], float]:
    """Every still-queued order for a run, priced AT READ TIME, plus the total
    AMI Cash they commit.

    Pricing here does not breach the market-hours fence. That fence exists so
    a queued order never FILLS at a stale price (§5.1's hindsight exploit);
    this is a display estimate, recomputed on every read and never written
    anywhere, and the fill still happens at the next open's price. The queue
    path itself is untouched and still stores no price at all.

    Why this exists: without it the ticket showed the full stake as
    "available" no matter how many orders were already queued against it, so
    a player could commit 250% of their book and the app would keep offering
    them 100%. Saiful, on build 74: *"This was the second order placed. But it
    is still showing I have 10K."* §13.3's Queued-orders surface names
    `cash committed` as a required field.
    """
    sim = get_sim_engine()
    rows_out: list[dict] = []
    committed = 0.0
    with get_session() as s:
        rows = s.execute(
            select(GameQueuedOrderRow).where(
                GameQueuedOrderRow.run_id == run_id,
                GameQueuedOrderRow.user_id == user_id,
                GameQueuedOrderRow.state == "queued",
            ).order_by(GameQueuedOrderRow.queued_at.desc())
        ).scalars().all()
        specs = [
            {
                "id": str(r.id),
                "ticker": r.ticker,
                "side": r.side,
                "quantity": float(r.quantity),
                "queued_at": r.queued_at.isoformat(),
            }
            for r in rows
        ]
    for spec in specs:
        quote = sim.current_quote(spec["ticker"])
        est_notional = round(quote.price * spec["quantity"], 2)
        est_fee = round(trade_fee(est_notional), 2)
        # A SELL releases cash rather than committing it; only a BUY ties up
        # the stake. The fee is owed either way.
        commits = (
            est_notional + est_fee if spec["side"] == "buy" else est_fee
        )
        committed += commits
        rows_out.append({
            **spec,
            # Explicit, because this list now carries refused orders too and
            # the client must never have to infer which is which.
            "state": "queued",
            "est_price": quote.price,
            "price_source": quote.source,
            "est_notional": est_notional,
            "est_fee": est_fee,
            "est_total": round(est_notional + est_fee, 2),
        })
    return rows_out, round(committed, 2)


def list_queued_orders(user_id: UUID, run_id: UUID) -> list[dict]:
    """`GET /v1/games/runs/{run_id}/orders` — §13.3's Queued-orders surface,
    which that table calls "the most-seen state in the product" for GCC/SEA
    players. Every estimate carries `price_source` (CR040 on the wire).

    Returns still-queued orders AND any order the open REFUSED in the last
    24h, each carrying `state` and `cancel_reason`.

    The refusals are the point. A queued order that cannot be afforded at the
    open is cancelled with a perfectly good reason — "insufficient cash: need
    $X, have $Y" — and this list used to filter to `state == "queued"`, so
    from the player's side the order simply VANISHED overnight. They would
    find some orders filled, some gone, and nothing anywhere saying which or
    why. Silence is not a result; CR040 asks that a thing which fails says so.

    24h because that is one open. Older refusals belong to a settled day and
    would just accumulate.
    """
    _require_live_entry(user_id, run_id)
    orders, _committed = _queued_orders_priced(user_id, run_id)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    with get_session() as s:
        refused = s.execute(
            select(GameQueuedOrderRow).where(
                GameQueuedOrderRow.run_id == run_id,
                GameQueuedOrderRow.user_id == user_id,
                GameQueuedOrderRow.state == "cancelled",
                GameQueuedOrderRow.cancel_reason.is_not(None),
                GameQueuedOrderRow.queued_at >= cutoff,
            ).order_by(GameQueuedOrderRow.queued_at.desc())
        ).scalars().all()
        # A player's own cancel writes no reason (see `cancel_queued_order`),
        # so `cancel_reason IS NOT NULL` is exactly "the system refused this" —
        # the only kind worth reporting back. Nobody needs telling about the
        # order they cancelled themselves.
        orders.extend({
            "id": str(r.id),
            "ticker": r.ticker,
            "side": r.side,
            "quantity": float(r.quantity),
            "queued_at": r.queued_at.isoformat(),
            "state": "refused",
            "cancel_reason": r.cancel_reason,
        } for r in refused)
    return orders


def cancel_queued_order(user_id: UUID, run_id: UUID, order_id: UUID) -> dict:
    """`POST /v1/games/runs/{run_id}/orders/{order_id}/cancel`.

    The ticket's own copy promises "free to cancel any time before it fills"
    (§5.1). Until this existed the app made that promise and had no way to
    keep it.
    """
    _require_live_entry(user_id, run_id)
    with get_session() as s:
        row = s.execute(
            select(GameQueuedOrderRow).where(
                GameQueuedOrderRow.id == order_id,
                GameQueuedOrderRow.run_id == run_id,
                GameQueuedOrderRow.user_id == user_id,
            )
        ).scalar_one_or_none()
        if row is None:
            raise RunNotFoundError(f"no queued order {order_id} on run {run_id}")
        if row.state != "queued":
            # Already filled or already cancelled. Not an error to the player,
            # but never report it as a cancellation that happened.
            return {"cancelled": False, "state": row.state, "order_id": str(order_id)}
        row.state = "cancelled"
        s.add(row)
    return {"cancelled": True, "state": "cancelled", "order_id": str(order_id)}


def quote_trade(
    user_id: UUID,
    run_id: UUID,
    *,
    ticker: str,
    side: Side,
    quantity: float | None = None,
    notional: float | None = None,
) -> dict:
    """`POST /v1/games/runs/{run_id}/trade/quote` — the ticket's pre-
    confirm card. Rides the market-data provider's own 60s cache; no
    separate TTL of its own.

    Sized by SHARES or by DOLLARS, exactly one. The 3-tap ticket sizes by
    percentage of book, which is a notional, and only this side has the price
    to turn that into a share count — so `notional` resolves here and the
    returned `quantity` is what the client then sends to `/trade`. That
    round-trip is deliberate: it keeps `submit_trade`'s queue path free of any
    price fetch, which is the stale-price fence.
    """
    if (quantity is None) == (notional is None):
        raise ValueError(
            "quote_trade needs exactly one of quantity or notional"
        )
    _require_live_entry(user_id, run_id)
    sim = get_sim_engine()
    ticker = ticker.upper().strip()
    quote = sim.current_quote(ticker)
    if quantity is None:
        if quote.price <= 0:
            raise ValueError(f"cannot size {ticker} by notional: no usable price")
        # 4dp matches `game_queued_orders.quantity`'s Numeric(12, 4), so the
        # number quoted is exactly the number that can be stored and filled.
        quantity = round(notional / quote.price, 4)
    notional = quote.price * quantity
    fee = trade_fee(notional)
    _portfolio, _marks, total_value, _drawdown_pct, _source = (
        sim.portfolio_marks_snapshot(user_id, kind="game", run_id=run_id)
    )
    book_pct = round((notional / total_value) * 100, 2) if total_value > 0 else 0.0
    side_str = side.value if hasattr(side, "value") else str(side)
    return {
        "ticker": ticker,
        "side": side_str,
        "quantity": quantity,
        "price": quote.price,
        "price_source": quote.source,
        "notional": round(notional, 2),
        "estimated_fee": fee,
        "estimated_total": round(
            notional + fee if side_str == "buy" else notional - fee, 2,
        ),
        "book_percentage": book_pct,
        "market_open": is_us_market_open(datetime.now(timezone.utc)),
    }


def submit_trade(
    user_id: UUID,
    run_id: UUID,
    *,
    ticker: str,
    side: Side,
    quantity: float,
    order_type: OrderType = OrderType.MARKET,
    limit_price: float | None = None,
    stop: float | None = None,
    target: float | None = None,
    horizon_days: int | None = None,
    now: datetime | None = None,
) -> dict:
    """`POST /v1/games/runs/{run_id}/trade` — the game trade path's
    orchestration. Market-hours rule: outside the US regular session this
    QUEUES the order (never touches `current_price` — see
    `GameQueuedOrderRow`'s docstring for why that is what keeps a queued
    order off a stale price) instead of calling
    `SimEngine.submit_game_trade`.
    """
    now = now or datetime.now(timezone.utc)
    _require_live_entry(user_id, run_id)
    ticker = ticker.upper().strip()
    side_str = side.value if hasattr(side, "value") else str(side)
    order_type_str = order_type.value if hasattr(order_type, "value") else str(order_type)

    if not is_us_market_open(now):
        with get_session() as s:
            s.add(GameQueuedOrderRow(
                run_id=run_id,
                user_id=user_id,
                ticker=ticker,
                side=side_str,
                quantity=quantity,
                order_type=order_type_str,
                limit_price=limit_price,
                stop=stop,
                target=target,
                horizon_days=horizon_days,
                state="queued",
                queued_at=now,
            ))
        return {
            "queued": True,
            "filled": False,
            "fee": None,
            "next_open_at": next_us_market_open(now).isoformat(),
        }

    result = get_sim_engine().submit_game_trade(
        user_id=user_id,
        run_id=run_id,
        ticker=ticker,
        side=side,
        quantity=quantity,
        order_type=order_type,
        limit_price=limit_price,
        stop=stop,
        target=target,
        horizon_days=horizon_days,
    )
    if result.accepted:
        _record_fill(user_id, run_id, fee=result.fee)
    return {
        "queued": False,
        "filled": result.accepted,
        "trade": result.trade.to_json() if result.trade else None,
        "fee": result.fee if result.accepted else None,
        "reason": result.reason,
    }


def process_queued_orders(*, now: datetime | None = None) -> dict:
    """The queue-drain sweep — called on a background tick
    (`main.py`'s `_game_queue_fill_tick`). Fetches a FRESH price for every
    still-queued order at drain time (via `SimEngine.submit_game_trade`,
    never a price captured when the order was placed); a no-op outside
    market hours.

    A queued order whose run is no longer live (forfeited since it was
    placed) is cancelled here rather than filled into a closed book.
    """
    now = now or datetime.now(timezone.utc)
    if not is_us_market_open(now):
        return {"checked": 0, "filled": 0, "cancelled": 0}

    with get_session() as s:
        queued = s.execute(
            # FIFO — oldest first, explicitly.
            #
            # This had no ORDER BY, so when a run's queued orders cost more
            # than its cash (routine: prices move overnight, and nothing stops
            # a player queueing past their balance), WHICH orders filled and
            # which were refused came down to whatever order Postgres happened
            # to return rows in. Undefined behaviour deciding a scored result.
            #
            # Oldest first is the only rule a player can reason about while
            # placing the orders: the ones you committed to first are the ones
            # that survive. It is also the rule every real venue uses, and the
            # only one that does not reward re-queueing.
            select(GameQueuedOrderRow)
            .where(GameQueuedOrderRow.state == "queued")
            .order_by(GameQueuedOrderRow.queued_at.asc())
        ).scalars().all()
        targets = [
            {
                "id": q.id, "run_id": q.run_id, "user_id": q.user_id,
                "ticker": q.ticker, "side": q.side, "quantity": float(q.quantity),
                "order_type": q.order_type,
                "limit_price": float(q.limit_price) if q.limit_price is not None else None,
                "stop": float(q.stop) if q.stop is not None else None,
                "target": float(q.target) if q.target is not None else None,
                "horizon_days": q.horizon_days,
            }
            for q in queued
        ]

    filled = 0
    cancelled = 0
    for t in targets:
        try:
            entry = _find_entry(t["user_id"], t["run_id"])
            if entry is None or entry.state not in ("entered", "active"):
                with get_session() as s:
                    row = s.execute(
                        select(GameQueuedOrderRow).where(GameQueuedOrderRow.id == t["id"])
                    ).scalar_one_or_none()
                    if row is not None and row.state == "queued":
                        row.state = "cancelled"
                        row.cancel_reason = "run no longer live"
                        cancelled += 1
                continue

            result = get_sim_engine().submit_game_trade(
                user_id=t["user_id"],
                run_id=t["run_id"],
                ticker=t["ticker"],
                side=Side(t["side"]),
                quantity=t["quantity"],
                order_type=OrderType(t["order_type"]),
                limit_price=t["limit_price"],
                stop=t["stop"],
                target=t["target"],
                horizon_days=t["horizon_days"],
            )
            with get_session() as s:
                row = s.execute(
                    select(GameQueuedOrderRow).where(GameQueuedOrderRow.id == t["id"])
                ).scalar_one_or_none()
                if row is None or row.state != "queued":
                    continue
                if result.accepted:
                    row.state = "filled"
                    row.filled_at = now
                    row.filled_trade_id = result.trade.id if result.trade else None
                else:
                    row.state = "cancelled"
                    row.cancel_reason = result.reason or "rejected at fill time"
            if result.accepted:
                _record_fill(t["user_id"], t["run_id"], fee=result.fee)
                filled += 1
            else:
                cancelled += 1
        except Exception:
            logger.exception("game_queue_fill_failed", order_id=str(t["id"]))

    return {"checked": len(targets), "filled": filled, "cancelled": cancelled}


# ── Restart / forfeit ────────────────────────────────────────────────────


def preview_restart(user_id: UUID, run_id: UUID) -> dict:
    """`POST /v1/games/runs/{run_id}/restart` preview half — no career-
    points ledger exists yet (slice 3), so there is nothing to debit."""
    entry = _find_entry(user_id, run_id)
    if entry is None:
        raise RunNotFoundError(f"no run {run_id} for user {user_id}")
    if entry.state not in ("entered", "active"):
        raise RunNotLiveError(f"run {run_id} is {entry.state}, cannot restart")
    return {
        "run_id": str(run_id),
        "career_points_debit": 0,
        "reason": (
            "no career-points ledger exists yet (slice 3) — forfeiting "
            "this run costs nothing today"
        ),
    }


def commit_restart(user_id: UUID, run_id: UUID, *, now: datetime | None = None) -> dict:
    """Forfeits the run (`state -> "forfeit"`) and cancels any orders still
    queued against it — a forfeited run's book is closed, so nothing
    should fill into it afterward."""
    now = now or datetime.now(timezone.utc)
    with get_session() as s:
        entry = s.execute(
            select(GameEntryRow).where(
                GameEntryRow.user_id == user_id, GameEntryRow.run_id == run_id,
            )
        ).scalar_one_or_none()
        if entry is None:
            raise RunNotFoundError(f"no run {run_id} for user {user_id}")
        if entry.state not in ("entered", "active"):
            raise RunNotLiveError(f"run {run_id} is {entry.state}, cannot restart")
        entry.state = "forfeit"
        result = s.execute(
            update(GameQueuedOrderRow)
            .where(
                GameQueuedOrderRow.run_id == run_id,
                GameQueuedOrderRow.state == "queued",
            )
            .values(state="cancelled", cancel_reason="run forfeited")
        )
        cancelled_count = int(result.rowcount or 0)
    return {
        "run_id": str(run_id),
        "state": "forfeit",
        "career_points_debit": 0,
        "queued_orders_cancelled": cancelled_count,
    }
