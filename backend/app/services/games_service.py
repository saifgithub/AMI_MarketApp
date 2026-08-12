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
from app.db.models import (
    GameEntryRow,
    GameFieldRow,
    GameQueuedOrderRow,
    GameShortPositionRow,
    SimPortfolioRow,
    SimTradeRow,
    User,
)
from app.schemas.trade import OrderType, Side
from app.services import games_duels
from app.services.games_scoring import short_open_fee, trade_fee
from app.services.portfolio_nav_daily import nav_history, twr_pct_for_window
from app.services.sim_engine import get_sim_engine
from app.trading_math.market_hours import is_us_market_open, next_us_market_open
from app.trading_math.shorts import nav_floor, short_buyin_trigger_price
from app.trading_math.shorts import short_cover_proceeds as _short_cover_proceeds
from app.trading_math.shorts import short_needs_buyin
from app.trading_math.shorts import short_unrealised_pnl as _short_unrealised_pnl

WEEKLY_CADENCE = "week"
MONTHLY_CADENCE = "month"
QUARTERLY_CADENCE = "quarter"
HALF_CADENCE = "half"
ANNUAL_CADENCE = "year"

# CR109 slice 6. Saiful, playing the shipped build: *"How do I join the
# monthly, quarterly, etc games?"* — the answer was that you couldn't, because
# this tuple held one entry.
#
# All five are CALENDAR-ANCHORED: a period's field starts on the first day of
# that period and everyone in it starts the same day, which is the property
# §6.2 chose placement scoring for. Demand-gated ROLLING starts for the long
# cadences (so a new player never waits three months to begin a quarterly run)
# are a different feature and belong to slice 4 — they need the thin-field
# thresholds set against a measured entry rate, which does not exist yet.
_SUPPORTED_CADENCES = (
    WEEKLY_CADENCE, MONTHLY_CADENCE, QUARTERLY_CADENCE, HALF_CADENCE, ANNUAL_CADENCE,
)
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


def _add_months(d: date, months: int) -> date:
    """Month arithmetic on the FIRST of a month — every cadence longer than a
    week anchors there, so there is no end-of-month clamping to get wrong."""
    total = (d.year * 12 + d.month - 1) + months
    return date(total // 12, total % 12 + 1, 1)


def period_start(cadence: str, d: date) -> date:
    """The first day of the `cadence` period containing `d`.

    Calendar-anchored on purpose: everyone in a field starts the same day, so
    everyone in it faced the same market — the property §6.2 chose placement
    scoring for, and the one thing merging cohorts across start dates would
    destroy.
    """
    if cadence == WEEKLY_CADENCE:
        return _week_monday(d)
    if cadence == MONTHLY_CADENCE:
        return date(d.year, d.month, 1)
    if cadence == QUARTERLY_CADENCE:
        return date(d.year, ((d.month - 1) // 3) * 3 + 1, 1)
    if cadence == HALF_CADENCE:
        return date(d.year, 1 if d.month <= 6 else 7, 1)
    if cadence == ANNUAL_CADENCE:
        return date(d.year, 1, 1)
    raise UnsupportedCadenceError(f"unknown cadence {cadence!r}")


def next_period_start(cadence: str, start: date) -> date:
    if cadence == WEEKLY_CADENCE:
        return start + timedelta(days=7)
    return _add_months(start, {
        MONTHLY_CADENCE: 1, QUARTERLY_CADENCE: 3, HALF_CADENCE: 6, ANNUAL_CADENCE: 12,
    }[cadence])


def previous_period_start(cadence: str, start: date) -> date:
    if cadence == WEEKLY_CADENCE:
        return start - timedelta(days=7)
    return _add_months(start, -{
        MONTHLY_CADENCE: 1, QUARTERLY_CADENCE: 3, HALF_CADENCE: 6, ANNUAL_CADENCE: 12,
    }[cadence])


def period_end(cadence: str, start: date) -> date:
    """The run's last day.

    Weekly ends on the Friday — `_RUN_DAYS` after the Monday — rather than on
    the Sunday, because a run that "ends" on a day the market never opened has
    two dead days at the end of it. Every longer cadence ends on the last
    calendar day of its period, which is the last day the NAV tick can write.
    """
    if cadence == WEEKLY_CADENCE:
        return start + timedelta(days=_RUN_DAYS)
    return next_period_start(cadence, start) - timedelta(days=1)


def _cadence_window(
    cadence: str, start: date,
) -> tuple[datetime, datetime, datetime, date]:
    """(entry_opens_at, locks_at, market_open, ends_on) for the `cadence`
    field starting on `start`.

    `entry_opens_at` is exactly when the PRIOR period's field locks, so one
    field's entry window opens the instant the previous one's closes — never a
    gap, never an overlap. That invariant is what makes "at any time there is
    exactly one entry-accepting field per cadence" true, which is in turn what
    `enter_field`'s one-live-run-per-cadence check relies on.
    """
    market_open = _market_open_et(start)
    locks_at = market_open - _LOCK_BUFFER
    entry_opens_at = (
        _market_open_et(previous_period_start(cadence, start)) - _LOCK_BUFFER
    )
    return entry_opens_at, locks_at, market_open, period_end(cadence, start)


def _weekly_window(monday: date) -> tuple[datetime, datetime, datetime, date]:
    """Back-compat shim for slice 2's callers and tests."""
    return _cadence_window(WEEKLY_CADENCE, monday)


def _as_utc(value: datetime) -> datetime:
    """SQLite round-trips `DateTime(timezone=True)` as NAIVE, so a stored
    `locks_at` compares as tz-naive against a tz-aware `now` and raises. Same
    normalisation `portfolio_nav_daily._as_utc` already applies for the same
    reason."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


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


def ensure_field(
    session, cadence: str = WEEKLY_CADENCE, *, now: datetime | None = None,
) -> GameFieldRow:
    """Idempotent create-or-fetch of the `open` field of `cadence` currently
    accepting entries (or, if none is entry-accepting at this instant — e.g.
    queried mid-period after this period's field already locked — the NEXT
    one). Updates `state` in place on every call so a field's state column
    never drifts stale between rolls.

    NOTE for callers outside the entry path: the state refresh applies to the
    field this call TARGETS, which mid-period is the next one. A field that is
    currently locked or live can therefore hold a stale `state`, so anything
    that needs to find such a field must derive its state from the row's own
    timestamps (see `games_desks.fields_in_lock_window`).
    """
    now = now or datetime.now(timezone.utc)
    now_et = now.astimezone(_ET)
    this_start = period_start(cadence, now_et.date())
    _, this_locks_at, _, _ = _cadence_window(cadence, this_start)
    target_start = (
        this_start if now < this_locks_at else next_period_start(cadence, this_start)
    )

    entry_opens_at, locks_at, market_open, ends_on = _cadence_window(
        cadence, target_start,
    )
    row = session.execute(
        select(GameFieldRow).where(
            GameFieldRow.cadence == cadence,
            GameFieldRow.kind == "open",
            GameFieldRow.starts_on == target_start,
        )
    ).scalar_one_or_none()
    new_state = _resolve_state(now, entry_opens_at, locks_at, market_open)
    if row is None:
        row = GameFieldRow(
            cadence=cadence,
            state=new_state,
            entry_opens_at=entry_opens_at,
            locks_at=locks_at,
            starts_on=target_start,
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


def ensure_weekly_field(session, *, now: datetime | None = None) -> GameFieldRow:
    """Back-compat shim — slice 2 shipped this name and several callers and
    tests use it. Weekly is just one cadence now."""
    return ensure_field(session, WEEKLY_CADENCE, now=now)


# ── Reads ────────────────────────────────────────────────────────────────


def list_cadences(user_id: UUID, *, now: datetime | None = None) -> list[dict]:
    """`GET /v1/games/cadences` — one entry per cadence the game supports.

    Every number carries what produced it (CR040): `queue_count` is the
    field's own denormalised `entrant_count`, `deadline` is `locks_at`.

    `already_held` is per-cadence, which is the whole point of §4.1: a player
    may hold one Weekly AND one Monthly AND one Quarterly AND one Half AND one
    Annual — five books — but never two of a kind. Two of a kind is a farm:
    career points pay +100 for a win and only −40 for a loss, so parallel
    entries in the SAME cadence are strictly +EV.
    """
    now = now or datetime.now(timezone.utc)
    out: list[dict] = []
    with get_session() as s:
        for cadence in _SUPPORTED_CADENCES:
            field = ensure_field(s, cadence, now=now)
            held = s.execute(
                select(GameEntryRow.id)
                .join(GameFieldRow, GameEntryRow.field_id == GameFieldRow.id)
                .where(
                    GameFieldRow.kind == "open",
                    GameFieldRow.cadence == cadence,
                    GameEntryRow.user_id == user_id,
                    GameEntryRow.state.in_(("entered", "active")),
                )
                .limit(1)
            ).first() is not None
            out.append({
                "cadence": cadence,
                "field_id": str(field.id),
                "state": field.state,
                "entry_opens_at": field.entry_opens_at.isoformat(),
                "locks_at": field.locks_at.isoformat(),
                "starts_on": field.starts_on.isoformat(),
                "ends_on": field.ends_on.isoformat(),
                "queue_count": field.entrant_count,
                "deadline": field.locks_at.isoformat(),
                "already_held": held,
            })
    return out


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
    # CR109 Amendment I — the same floor the NAV row is written under, so the
    # live screen and the stored series cannot disagree about whether a book
    # is worth less than nothing. `nav_shortfall` carries the part the floor
    # hides; the Close is where it gets said in words.
    floored_value, live_shortfall = nav_floor(float(total_value))
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
        "total_value": round(floored_value, 2),
        "nav_shortfall": round(live_shortfall, 2) if live_shortfall > 0 else None,
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
        # CR109 slice 3b — the live duel, or null when this run has no
        # opponent this period (an ordinary state, not a degraded one).
        "duel": games_duels.duel_view_for_run(user_id, run_id),
        # CR109 Amendment G. A separate list, not a holding with a negative
        # quantity: the client renders the two differently (a short's P&L
        # runs the other way and its loss is unbounded), and a sign flip
        # buried inside a shared row is exactly the thing a reader misses.
        # `unrealised_pnl` is signed and POSITIVE when the mark is below
        # entry — sent computed rather than left to the client, so the run
        # screen and the score cannot disagree about which way a short is.
        "shorts": [
            {
                "id": str(sp.id),
                "ticker": sp.ticker,
                "quantity": sp.quantity,
                "entry_price": sp.entry_price,
                "cash_posted": sp.cash_posted,
                "mark": marks.get(sp.ticker, sp.entry_price),
                "unrealised_pnl": round(
                    _short_unrealised_pnl(
                        sp.quantity, sp.entry_price,
                        marks.get(sp.ticker, sp.entry_price),
                    ),
                    2,
                ),
            }
            for sp in portfolio.shorts
        ],
    }


# ── Entry ────────────────────────────────────────────────────────────────


def enter_field(
    user_id: UUID,
    *,
    cadence: str = WEEKLY_CADENCE,
    intent: str | None = None,
    now: datetime | None = None,
    as_desk: bool = False,
    field_id: UUID | None = None,
) -> GameEntryRow:
    """`POST /v1/games/enter`. Entry is FREE — never charge here; an entry
    fee is legal consideration and would break CR109 §15 (design doc).
    Raises `AlreadyEnteredError` (-> 409) if the user already holds a live
    run for this cadence.

    `as_desk` widens the accepted field states by exactly one — `locked` —
    because a house desk (CR109 slice 3c) enters AFTER human entries close,
    which is what lets it taper against the final human count (design §11.2
    "fill to a target field size, never a fixed count"). It is not a
    skip-the-check flag: it is verified against `users.is_desk` below, so a
    human user id passed with `as_desk=True` is refused. That verification is
    the difference between a widened rule and a bypass — CLAUDE.md's
    "prompt instructions are not controls" applied to our own code.

    `field_id` targets ONE field explicitly instead of asking
    `ensure_weekly_field` which field is currently accepting entries. The two
    answers differ precisely in the desk-fill window: past this Monday's
    `locks_at`, `ensure_weekly_field` correctly rolls forward to NEXT Monday's
    field, so a desk filling *this* week's locked field would otherwise have
    entered next week's — sized against a taper computed for a different
    field. Humans never pass it; the roll is the right answer for them.
    """
    if cadence not in _SUPPORTED_CADENCES:
        raise UnsupportedCadenceError(
            f"cadence must be one of {_SUPPORTED_CADENCES}, got {cadence!r}"
        )
    if intent is not None and intent not in INTENTS:
        raise ValueError(f"intent must be one of {INTENTS}, got {intent!r}")
    now = now or datetime.now(timezone.utc)

    accepted_states = ("announced", "entry_open")
    if as_desk:
        with get_session() as s:
            really_a_desk = s.execute(
                select(User.is_desk).where(User.id == user_id)
            ).scalar_one_or_none()
        if not really_a_desk:
            raise FieldNotOpenError(
                f"user {user_id} is not a house desk; as_desk entry refused"
            )
        accepted_states = ("announced", "entry_open", "locked")

    try:
        with get_session() as s:
            if field_id is None:
                field = ensure_field(s, cadence, now=now)
            else:
                field = s.execute(
                    select(GameFieldRow).where(GameFieldRow.id == field_id)
                ).scalar_one_or_none()
                if field is None:
                    raise FieldNotOpenError(f"no field {field_id}")
                # Resolve from the row's OWN timestamps. `state` is only
                # refreshed on the field `ensure_weekly_field` happens to
                # target, so a field outside that roll can hold a stale value.
                field.state = _resolve_state(
                    now,
                    _as_utc(field.entry_opens_at),
                    _as_utc(field.locks_at),
                    _market_open_et(field.starts_on),
                )
            if field.state not in accepted_states:
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
                entered_at=now,
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

    # A desk re-enters every single week by construction, so letting it emit
    # `game_close_to_reentry` would make Gate 1's re-entry rate a measure of
    # the cron rather than of players (§11.2: a desk must never inflate a
    # number Saiful makes decisions on).
    if not as_desk:
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
    # CR109 Amendment G — which queued sells are SHORTS matters here, not
    # just at the fill. A short ties up its full notional exactly as a buy
    # does (no leverage), so treating every queued sell as cash-releasing
    # would let a player queue shorts all night against a balance the app
    # keeps reporting as untouched — the same over-commitment §13.3's
    # `cash_committed` was added to stop, reintroduced through the one side
    # it did not have to consider before.
    # Read straight from the tables rather than through the engine: this
    # needs two ticker sets and nothing else, and going through
    # `ensure_portfolio` would both create a row this read has no business
    # creating and drag the whole market-data fan-out in behind it.
    held_by_ticker: dict[str, float] = {}
    shorted: set[str] = set()
    with get_session() as s:
        p_row = s.execute(
            select(SimPortfolioRow).where(
                SimPortfolioRow.user_id == user_id,
                SimPortfolioRow.kind == "game",
                SimPortfolioRow.run_id == run_id,
            )
        ).scalars().first()
        if p_row is not None:
            held_by_ticker = {h.ticker: float(h.quantity) for h in p_row.holdings}
            shorted = {
                t for (t,) in s.execute(
                    select(GameShortPositionRow.ticker).where(
                        GameShortPositionRow.portfolio_id == p_row.id,
                        GameShortPositionRow.state == "open",
                    )
                ).all()
            }

    for spec in specs:
        quote = sim.current_quote(spec["ticker"])
        est_notional = round(quote.price * spec["quantity"], 2)
        opens_short = (
            spec["side"] == "sell"
            and spec["ticker"] not in shorted
            and held_by_ticker.get(spec["ticker"], 0.0) <= 1e-6
        )
        est_fee = round(
            short_open_fee(est_notional) if opens_short
            else trade_fee(est_notional),
            2,
        )
        # A sell that CLOSES releases cash rather than committing it; a buy
        # and a sell that OPENS a short both tie up the stake. The fee is
        # owed either way.
        commits = (
            est_notional + est_fee
            if (spec["side"] == "buy" or opens_short)
            else est_fee
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
    portfolio, _marks, total_value, _drawdown_pct, _source = (
        sim.portfolio_marks_snapshot(user_id, kind="game", run_id=run_id)
    )
    book_pct = round((notional / total_value) * 100, 2) if total_value > 0 else 0.0
    side_str = side.value if hasattr(side, "value") else str(side)

    # CR109 Amendment G — the ticket has to know WHICH leg this is before
    # the player confirms, because a short open costs 0.3% and everything
    # else costs 0.1%, and because the confirm button says a different word.
    # The inference repeats `SimEngine._route_game_short`'s rules rather than
    # calling it, since that one commits; what matters is that both read the
    # same two facts — held quantity and standing short — so they cannot
    # disagree about what the order is.
    held = next((h for h in portfolio.holdings if h.ticker == ticker), None)
    held_qty = float(held.quantity) if held is not None else 0.0
    standing = next((s for s in portfolio.shorts if s.ticker == ticker), None)
    opens_short = (
        side_str == "sell" and standing is None and held_qty <= 1e-6
    )
    covers_short = side_str == "buy" and standing is not None

    fee = short_open_fee(notional) if opens_short else trade_fee(notional)
    # What the CASH line will actually do. A short OPEN ties up cash exactly
    # as a buy does (no leverage — see `trading_math/shorts.py`), so it is a
    # debit; showing it as a credit would tell the player they are being PAID
    # to open a short, which is what the real mechanic looks like and what
    # this design deliberately does not do. A COVER is the mirror: the posted
    # cash comes back adjusted for the move, so it is a credit even though
    # the side is `buy` — which is why this cannot be derived from the side
    # alone.
    if opens_short:
        estimated_total = round(notional + fee, 2)
    elif covers_short:
        estimated_total = round(
            _short_cover_proceeds(
                standing.cash_posted, standing.quantity,
                standing.entry_price, quote.price,
            ) - fee,
            2,
        )
    elif side_str == "buy":
        estimated_total = round(notional + fee, 2)
    else:
        estimated_total = round(notional - fee, 2)
    return {
        "ticker": ticker,
        "side": side_str,
        "quantity": quantity,
        "price": quote.price,
        "price_source": quote.source,
        "notional": round(notional, 2),
        "estimated_fee": fee,
        "estimated_total": estimated_total,
        "book_percentage": book_pct,
        "market_open": is_us_market_open(datetime.now(timezone.utc)),
        "opens_short": opens_short,
        "covers_short": covers_short,
        "short_quantity_held": standing.quantity if standing is not None else None,
        # CR109 Amendment I — the price at which this short would be bought
        # in, sent from the server rather than re-derived on the client.
        # Amendment G's ticket copy asserted "there is no floor", which this
        # amendment made false; a client that computed 1.9x itself would be a
        # second copy of the constant, free to drift from the one the sweep
        # actually fires on. Null unless this quote opens a short.
        "buyin_trigger_price": (
            round(short_buyin_trigger_price(quote.price), 2) if opens_short else None
        ),
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
        refusal = _refuse_overcommitted_queue(
            user_id, run_id, ticker=ticker, side_str=side_str, quantity=quantity,
        )
        if refusal is not None:
            return refusal
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
        # CR109 Amendment G — a short open/cover writes no `sim_trades` row,
        # so `trade` is null on those. Without this the client would see
        # `filled: true, trade: null` and have nothing to show for it, which
        # is the "the order simply VANISHED" shape §13.3 already had to fix
        # once. Null on an ordinary long fill.
        "short_action": result.short_action,
        "short_ticker": result.short_ticker,
        "short_quantity": result.short_quantity,
        "short_realised_pnl": result.short_realised_pnl,
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


# ── Amendment I — forced buy-in, so an account cannot go negative ─────────


def sweep_forced_buyins(*, now: datetime | None = None, sim=None) -> dict:
    """Buy in every short that has eaten through all but the maintenance
    floor of its collateral (CR109 Amendment I).

    Saiful: *"how do we keep the account from going negative?"* This is the
    first of the two answers — the orderly one. `short_needs_buyin` fires at
    `leg <= 10% of collateral` (equivalently `mark >= 1.9x entry`), which
    caps a short's loss at the collateral posted and so makes its worst case
    equal to a long's. The second answer, for gaps this cannot catch, is the
    NAV floor in `trading_math/shorts.nav_floor`.

    **Runs on the queue-drain tick, immediately AFTER the drain, never as an
    independent task.** Same reasoning Amendment H used for duel pairing: a
    queued sell can OPEN a short in this very tick, and two tasks would race
    that ordering every five minutes with a silent failure mode (a position
    that should have been bought in simply is not, and nothing says so).

    **A no-op outside market hours, deliberately.** A forced cover needs a
    real price, and filling one at the last close is precisely the stale-fill
    §5.1 forbids for user orders — a rule the house must not exempt itself
    from. Waiting for the open is where the gap risk lives, and the gap risk
    is what `nav_floor` exists for.

    `sim` is injectable for the same reason `run_scoring_pass`'s is: the
    marks come from a provider that is a singleton in production, and a test
    that cannot move the price cannot exercise the trigger at all.
    """
    now = now or datetime.now(timezone.utc)
    if not is_us_market_open(now):
        return {"checked": 0, "bought_in": 0}

    sim = sim or get_sim_engine()
    with get_session() as s:
        # Only shorts on runs still being played. A settled run's shorts are
        # closed by settlement, and buying one in here would move a NAV the
        # Close has already scored.
        rows = s.execute(
            select(GameShortPositionRow)
            .join(
                GameEntryRow,
                GameEntryRow.run_id == GameShortPositionRow.run_id,
            )
            .where(
                GameShortPositionRow.state == "open",
                GameEntryRow.state.in_(("entered", "active")),
            )
        ).scalars().all()
        targets = [
            {
                "user_id": r.user_id,
                "run_id": r.run_id,
                "ticker": r.ticker,
                "quantity": float(r.quantity),
                "entry_price": float(r.entry_price),
                "cash_posted": float(r.cash_posted),
            }
            for r in rows
        ]

    bought_in = 0
    for t in targets:
        try:
            quote = sim.current_quote(t["ticker"])
            mark = float(quote.price)
            if not short_needs_buyin(
                t["cash_posted"], t["quantity"], t["entry_price"], mark,
            ):
                continue
            # Routed through the ordinary cover path, at the ordinary fee.
            # A house-exempt fill is a tuned result by the back door — the
            # same objection slice 3c makes about fee-exempt desks.
            result = sim.submit_game_trade(
                user_id=t["user_id"],
                run_id=t["run_id"],
                ticker=t["ticker"],
                side=Side.BUY,
                quantity=t["quantity"],
            )
            if not result.accepted:
                logger.warn(
                    "game_short_buyin_refused",
                    user_id=str(t["user_id"]), run_id=str(t["run_id"]),
                    ticker=t["ticker"], reason=result.reason,
                )
                continue
            _record_fill(t["user_id"], t["run_id"], fee=result.fee)
            bought_in += 1
            logger.info(
                "game_short_bought_in",
                user_id=str(t["user_id"]), run_id=str(t["run_id"]),
                ticker=t["ticker"], qty=t["quantity"],
                entry=t["entry_price"], mark=mark,
                trigger=short_buyin_trigger_price(t["entry_price"]),
            )
        except Exception:
            logger.exception(
                "game_short_buyin_failed",
                run_id=str(t["run_id"]), ticker=t["ticker"],
            )

    return {"checked": len(targets), "bought_in": bought_in}


def _refuse_overcommitted_queue(
    user_id: UUID, run_id: UUID, *, ticker: str, side_str: str, quantity: float,
) -> dict | None:
    """Refuse a queued order the run cannot pay for — at QUEUE time.

    Until now the queue accepted anything. A player could queue eight orders
    against a book that covered three, and the first they heard of it was the
    drain cancelling five with `rejected at fill time` — hours later, on a
    screen they were not looking at. Saiful hit exactly this: *"I have
    10,003.29 committed to 8 queued orders, 0.00 available."* The FIFO drain
    (DEF-era fix) decided WHICH survived; nothing told him some would not.

    **Only cash-consuming orders are checked.** A sell closes a long and a
    cover closes a short — both RETURN cash, and both are the orders a player
    most needs to place from an empty balance. Refusing either is the one-way
    book DEF259 already had to fix, and Amendment G ruling 5 makes the cover
    case explicit.

    **Pricing here does not breach the market-hours fence**, on exactly the
    grounds `_queued_orders_priced` already states: the fence exists so an
    order never FILLS at a stale price. This is an estimate used to REFUSE,
    never to fill — the order still fills at the next open's price, and
    nothing about the estimate is stored. An estimate can be wrong by a
    weekend's drift, which is why the refusal names both numbers and why the
    drain keeps its own check: this makes the common case honest, it does not
    replace the authority at fill time.
    """
    if side_str not in ("buy",):
        return None

    sim = get_sim_engine()
    portfolio = sim.ensure_portfolio(user_id, kind="game", run_id=run_id)

    # A buy on a name already shorted is a COVER — it returns cash. Same
    # exemption as the sell above, decided by the same fact the fill path
    # uses so the two cannot disagree about what this order is.
    if any(sp.ticker == ticker for sp in portfolio.shorts):
        return None

    _queued, committed = _queued_orders_priced(user_id, run_id)
    available = round(float(portfolio.current_cash) - committed, 2)
    try:
        price = float(sim.current_quote(ticker).price)
    except Exception:
        price = 0.0
    if price <= 0:
        # No usable price, no honest estimate — and a refusal built on a
        # number we could not obtain is the CR040 fabrication class. Stand
        # down loudly and leave the drain as the authority it already was.
        # Same "no usable price" condition `quote_trade` already refuses on,
        # so the two cannot disagree about what an unpriceable ticker is.
        logger.warn(
            "game_queue_affordability_unpriced",
            run_id=str(run_id), ticker=ticker,
            reason="no usable price for the estimate; queue-time check skipped",
        )
        return None
    estimate = price * quantity
    estimate = round(estimate + trade_fee(estimate), 2)

    if estimate <= available + 1e-6:
        return None

    logger.info(
        "game_queue_refused_overcommitted",
        user_id=str(user_id), run_id=str(run_id), ticker=ticker,
        estimate=estimate, available=available, committed=committed,
    )
    return {
        "queued": False,
        "filled": False,
        "fee": None,
        "reason": (
            f"that order needs about ${estimate:,.2f} and this run has "
            f"${available:,.2f} left to commit"
            + (
                f" — ${committed:,.2f} is already committed to orders waiting "
                f"on the next open"
                if committed > 0
                else ""
            )
        ),
    }


# ── Amendment I — settlement: a closed run holds nothing ─────────────────


def settle_run_positions(
    user_id: UUID, run_id: UUID, *, sim=None, now: datetime | None = None,
) -> dict:
    """Close every position a finished run still holds — CR109 Amendment I.

    Saiful: *"when the game ends, all positions must be closed."* This
    reverses Amendment G's *"no forced cover at the close"* and narrows §5.2's
    mark-don't-liquidate rule to the DAILY mark, which is what it was always
    about; the run boundary now settles.

    **Free, and that is a decision rather than an omission.** An exit fee here
    would move the score for the act of the run ending — a charge for a
    non-decision — which is Amendment G ruling 3's objection ("a position that
    books a profit for the act of being entered scores the contest on an
    artefact") pointed the other way. Nothing about a settlement was chosen by
    the player, so nothing about it may cost them.

    **Not a trade, either.** `_record_fill` is deliberately NOT called: a
    settlement must not bump `trade_count` (which gates the finish stipend on
    ">= 1 executed trade" — a player who never traded must not be handed one
    by the close itself) and must not add to `fees_paid`.

    **It does write an ordinary sell row, and that is also deliberate.**
    `scripts/def110_backfill.py` walks EVERY portfolio and rebuilds holdings
    from `Σ open buys − Σ open sells`; a settlement that deleted holdings
    silently would leave that formula expecting shares nobody holds, and the
    repair script — running with every good intention — would recreate the
    positions this function just closed. Writing the sell keeps its invariant
    exactly true with no change to it. The turnover that row would add is
    harmless because phase 4 runs AFTER scoring: `wildness_index` was computed
    from a phase-1 read snapshot taken before this row existed.

    **The price.** The current mark, fetched fresh. `run_scoring_pass` fires
    once `ends_on < today_et`, i.e. from midnight ET on the day after the run
    ends, on a 30-minute tick — so in the ordinary case the "current" mark IS
    the run's final close, and the settled cash agrees with the final NAV. A
    settlement delayed past the next open uses that day's price instead, which
    is honest (it is when the book actually converted) and cannot disturb the
    SCORE either way, since the score is read from the NAV series and was
    already written in phase 2.

    Idempotent: a run with nothing open settles nothing and reports zero.
    """
    from app.services.games_shorts import cover_short, find_open_short

    now = now or datetime.now(timezone.utc)
    sim = sim or get_sim_engine()

    portfolio = sim.ensure_portfolio(user_id, kind="game", run_id=run_id)
    longs = [(h.ticker, float(h.quantity)) for h in portfolio.holdings]
    shorts = [(s.ticker, float(s.quantity)) for s in portfolio.shorts]
    if not longs and not shorts:
        return {"positions_closed": 0, "shorts_covered": 0}

    closed = covered = 0
    with get_session() as s:
        p_row = sim._load_portfolio_row(s, user_id, kind="game", run_id=run_id)
        if p_row is None:
            return {"positions_closed": 0, "shorts_covered": 0}

        for ticker, qty in longs:
            mark = float(sim.current_price(ticker))
            sold = sim._apply_sell_row(s, p_row, ticker, qty, mark)
            if sold <= 0:
                continue
            s.add(SimTradeRow(
                id=uuid4(),
                user_id=user_id,
                portfolio_id=p_row.id,
                ticker=ticker,
                side="sell",
                quantity=sold,
                entry_price=mark,
                opened_at=now,
                # 'open' like every other sell row — DEF166/DEF110 make that
                # permanent-open state load-bearing for the backfill formula
                # this row exists to satisfy.
                status="open",
                realised_pnl=0,
            ))
            closed += 1

        for ticker, qty in shorts:
            mark = float(sim.current_price(ticker))
            short_row = find_open_short(s, p_row.id, ticker)
            if short_row is None:
                continue
            cover_short(
                s, portfolio_row=p_row, short_row=short_row,
                close_price=mark, fee=0.0, reason="settlement", now=now,
            )
            covered += 1
            closed += 1

    logger.info(
        "game_run_settled",
        user_id=str(user_id), run_id=str(run_id),
        positions_closed=closed, shorts_covered=covered,
    )
    return {"positions_closed": closed, "shorts_covered": covered}


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
