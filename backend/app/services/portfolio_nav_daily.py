"""Daily NAV snapshot tick + reads — CR109 slice 1, the equity-curve spine.

One `portfolio_nav_daily` row per user per US market date, for the TRAINING
portfolio only (`run_id` stays NULL here; a game run writes its own rows
through the same table in a later slice). Idempotent like
`_sharia_universe_refresh` / `_classification_universe_refresh` in
`main.py`: a tick that finds today's row already stored does nothing, so a
restart cannot miss a boundary.

Unlike CR136 M03's `portfolio_snapshot.py` — which REFUSES to write a
mock-priced day — this tick WRITES it and flags `price_source="mock"`. This
table is the equity-curve spine: a hole in it reads as "nothing happened",
which is a worse lie than a flagged mock day (CR040 degrade-loudly).

`capital_event` is inferred at tick time, not written by `reset_portfolio()`
itself (this slice does not touch that function): the FIRST row this tick
ever writes for a user is `open`; a later row lands on `restart` when the
portfolio's own `created_at` is NEWER than our last recorded observation of
it, which is what `reset_portfolio()`'s destroy-and-recreate produces. That
comparison is a TIMESTAMP one, deliberately not a calendar-date one — `as_of`
is a trading day and can lag the wall clock by a weekend or holiday, so
comparing dates would miss a reset that happens on a day the market didn't
trade. A reset that happens on the same trading day AFTER the tick has
already run for it is not caught until the next trading day's tick — an
accepted daily-granularity limit, the same one CR136 M03 already lives with.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Callable, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.logging import logger
from app.db import get_session
from app.db.models import GameEntryRow, PortfolioNavDailyRow, SimPortfolioRow
from app.trading_math.shorts import nav_floor
from app.trading_math.twr import NavPoint, time_weighted_return

_MOCK_MARKER = "mock"


def _price_source_for_snapshot(raw: str, *, holding_count: int) -> str:
    """`_normalize_price_source`, except a book with NO holdings reads `cash`.

    A zero-holding day needs no price at all: NAV is cash, and cash is exactly
    known. But `SimEngine.aggregate_source` returns `mock_walk` for an empty
    ticker list — correct for its own purpose (the LIVE pill must not light up
    when nothing has been priced), and wrong as an input to scoring, because
    `games_scoring_pass` VOIDs any run whose NAV series contains a `mock` day.

    Chained together those two correct-in-isolation rules VOIDED essentially
    every run. Queue-first is the PRIMARY designed flow — US hours are evening
    in the Gulf and past midnight in Malaysia — so a player enters, queues an
    order that night, and fills at the next open. The day in between has no
    holdings, so it was recorded `mock`, so the run was void before it began.
    The player did everything right and got no score.

    Found on live Alpha during the CR109 end-to-end check, not by the unit
    suite: every scoring fixture already had holdings, so nothing exercised the
    empty book. `cash` states what actually happened, which is what CR040 asks
    for — the day is not a fabricated price and must not be scored as one.
    """
    if holding_count == 0:
        return "cash"
    return _normalize_price_source(raw)


def _normalize_price_source(raw: str) -> str:
    """Collapse the provider stack's leaf source strings ("yahoo",
    "mock_walk", "unavailable", ...) onto the three-value vocabulary
    `portfolio_nav_daily.price_source` promises callers: `live` / `mock` /
    `stale`. `unavailable` (the defensive floor `SimEngine.current_quote`
    falls back to when even the mock provider comes up empty) reads as
    `stale` — SOME price was served, just not one this round actually
    confirmed."""
    lowered = (raw or "").lower()
    if _MOCK_MARKER in lowered:
        return "mock"
    if lowered in ("", "unavailable"):
        return "stale"
    return "live"


def _as_utc(value: datetime) -> datetime:
    """SQLite round-trips `DateTime(timezone=True)` as naive — treat a naive
    stamp as UTC (everything here is written with `datetime.now(timezone.utc)`
    or an injected UTC `now`), the same normalisation `api/sim.py`'s reset
    cooldown already applies to a portfolio row's `created_at`."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _default_trading_day() -> date | None:
    from app.services.price_history import latest_trading_day

    return latest_trading_day()


def run_portfolio_nav_snapshot_tick(
    *,
    now: datetime | None = None,
    trading_day: Callable[[], date | None] | None = None,
) -> dict[str, object]:
    """One sweep: at most one `portfolio_nav_daily` row per user per trading
    day, `run_id` NULL (training portfolio). Idempotent by design — see the
    module docstring.

    The trading day comes from the benchmark's own candle grid
    (`latest_trading_day`, CR136 M01), never from calendar arithmetic —
    consulting a mock database's guessed date would put a hole in the very
    series TWR is meant to measure. If the data layer cannot serve it, this
    is a loud no-op rather than a fabricated date.
    """
    now = now or datetime.now(timezone.utc)
    resolve_day = trading_day or _default_trading_day

    as_of = resolve_day()
    if as_of is None:
        logger.warn(
            "portfolio_nav_snapshot_no_trading_day",
            reason=(
                "no SPY rows in price_history_daily — the history table has "
                "not been warmed yet (cold start), or every stored SPY row "
                "is mock-source while USE_REAL_MARKET_DATA is true. No row "
                "written."
            ),
        )
        return {"as_of": "none", "users": 0, "written": 0, "skipped_existing": 0}

    from app.services.sim_engine import get_sim_engine

    sim = get_sim_engine()
    with get_session() as session:
        # CR109 slice 2: `sim_portfolios` now also holds GAME portfolios
        # (`kind="game"`, one row per run). Scoped to `kind="training"` so
        # this tick keeps writing exactly the training curve it always
        # has — a game user's OWN nav rows come from
        # `run_game_nav_snapshot_tick` below, keyed by their run_id, never
        # by folding into the training (`run_id=None`) series.
        user_ids = [
            row.user_id
            for row in session.execute(
                select(SimPortfolioRow).where(SimPortfolioRow.kind == "training")
            ).scalars().all()
        ]

    written = 0
    skipped = 0
    for user_id in user_ids:
        try:
            with get_session() as session:
                exists_today = session.execute(
                    select(PortfolioNavDailyRow.id).where(
                        PortfolioNavDailyRow.user_id == user_id,
                        PortfolioNavDailyRow.run_id.is_(None),
                        PortfolioNavDailyRow.as_of_date == as_of,
                    )
                ).first()
                if exists_today is not None:
                    skipped += 1
                    continue
                last_row = session.execute(
                    select(PortfolioNavDailyRow)
                    .where(
                        PortfolioNavDailyRow.user_id == user_id,
                        PortfolioNavDailyRow.run_id.is_(None),
                    )
                    .order_by(PortfolioNavDailyRow.created_at.desc())
                    .limit(1)
                ).scalar_one_or_none()
                last_created_at = (
                    _as_utc(last_row.created_at) if last_row is not None else None
                )

            portfolio, _marks, total_value, _drawdown_pct, source = (
                sim.portfolio_marks_snapshot(user_id)
            )
            if last_created_at is None:
                capital_event = "open"
            elif _as_utc(portfolio.created_at) > last_created_at:
                # The portfolio row is newer than our last recorded
                # observation of it — `reset_portfolio()` destroy-and-
                # recreates with a fresh `created_at`, so this is the tick's
                # own evidence a reset happened since it last looked.
                # Comparing TIMESTAMPS rather than calendar dates is
                # deliberate: `as_of` is a TRADING day (from the benchmark's
                # candle grid) and can lag the wall clock by a weekend or a
                # holiday, so a same-calendar-day check would miss resets
                # that happen on a day the market didn't trade.
                capital_event = "restart"
            else:
                capital_event = None

            try:
                with get_session() as session:
                    session.add(PortfolioNavDailyRow(
                        user_id=user_id,
                        run_id=None,
                        as_of_date=as_of,
                        nav=round(float(total_value), 2),
                        cash=round(float(portfolio.current_cash), 2),
                        price_source=_price_source_for_snapshot(
                            source, holding_count=len(portfolio.holdings),
                        ),
                        capital_event=capital_event,
                        created_at=now,
                    ))
                written += 1
            except IntegrityError:
                # The unique constraint is the backstop behind the
                # check-before-insert above; a concurrent tick losing this
                # race is a skip, not a failure.
                skipped += 1
        except Exception:
            logger.exception(
                "portfolio_nav_snapshot_user_failed", user_id=str(user_id),
            )

    return {
        "as_of": as_of.isoformat(),
        "users": len(user_ids),
        "written": written,
        "skipped_existing": skipped,
    }


def _mark_run_bust(
    user_id: UUID, run_id: UUID, *, shortfall: float, now: datetime,
) -> bool:
    """End a run whose book went past zero — CR109 Amendment I.

    Idempotent on `busted_at`: the NAV tick runs daily and a busted run is
    still a row in `sim_portfolios`, so without this the shortfall would be
    rewritten (and the log line re-emitted) every day until the field closes.
    The FIRST measurement is the true one — it is the day the account
    actually broke — and a later one taken after the positions have drifted
    is a different, wrong number.

    Only ever moves a run that is still being played. A `finished`, `void` or
    `forfeit` entry has already been scored, and re-stating it as `bust`
    would change a settled result.
    """
    with get_session() as session:
        entry = session.execute(
            select(GameEntryRow).where(
                GameEntryRow.user_id == user_id, GameEntryRow.run_id == run_id,
            )
        ).scalar_one_or_none()
        if entry is None or entry.busted_at is not None:
            return False
        if entry.state not in ("entered", "active"):
            return False
        entry.state = "bust"
        entry.busted_at = now
        entry.nav_shortfall = round(shortfall, 2)
    logger.warn(
        "game_run_bust",
        user_id=str(user_id), run_id=str(run_id), shortfall=round(shortfall, 2),
        reason=(
            "book value went below zero — a short gapped through its "
            "maintenance floor before the forced buy-in could fill"
        ),
    )
    return True


def run_game_nav_snapshot_tick(
    *,
    now: datetime | None = None,
    trading_day: Callable[[], date | None] | None = None,
    sim=None,
) -> dict[str, object]:
    """CR109 slice 2 — the sibling of `run_portfolio_nav_snapshot_tick` for
    GAME portfolios (`kind="game"`). One `portfolio_nav_daily` row per
    (user, run, trading day), `run_id` = the game run's own id — the run's
    NAV curve (`GET /v1/games/runs/{run_id}`) reads straight off these
    rows, same as the training curve reads off the `run_id IS NULL` rows.

    Idempotent for the same reason as the training tick: a tick that finds
    today's row already stored for a run does nothing.

    A queued (not yet filled) `GameQueuedOrderRow` never appears here — this
    only ever reads the actual portfolio row's holdings/cash via
    `portfolio_marks_snapshot(kind="game", run_id=...)`, and a queued order
    hasn't touched either yet. That is what keeps a queued order out of a
    NAV snapshot before it fills, structurally rather than by a special
    case here.

    `capital_event` is never set to anything but `None` on this path in
    slice 2 — a game run's ONLY capital event is its own entry (there is no
    reset/restart-in-place for a game run; forfeiting ends it, see
    `games_service.py`), and Amendment D's trading fee is explicitly NOT a
    capital event (design §12), so it never appears here either.
    """
    now = now or datetime.now(timezone.utc)
    resolve_day = trading_day or _default_trading_day

    as_of = resolve_day()
    if as_of is None:
        logger.warn(
            "game_nav_snapshot_no_trading_day",
            reason="no SPY rows in price_history_daily — cold start or mock-only.",
        )
        return {"as_of": "none", "runs": 0, "written": 0, "skipped_existing": 0}

    from app.services.sim_engine import get_sim_engine

    # Injectable for the same reason `run_scoring_pass`'s is: the marks come
    # from a provider that is a singleton in production, so a test that cannot
    # set the price cannot exercise this tick's arithmetic — and one that
    # relies on having constructed the singleton last is order-dependent,
    # which is how it passes alone and fails in a full run.
    sim = sim or get_sim_engine()
    with get_session() as session:
        targets = [
            (row.user_id, row.run_id)
            for row in session.execute(
                select(SimPortfolioRow).where(SimPortfolioRow.kind == "game")
            ).scalars().all()
            if row.run_id is not None
        ]

    written = 0
    skipped = 0
    for user_id, run_id in targets:
        try:
            with get_session() as session:
                exists_today = session.execute(
                    select(PortfolioNavDailyRow.id).where(
                        PortfolioNavDailyRow.user_id == user_id,
                        PortfolioNavDailyRow.run_id == run_id,
                        PortfolioNavDailyRow.as_of_date == as_of,
                    )
                ).first()
                if exists_today is not None:
                    skipped += 1
                    continue
                first_row = session.execute(
                    select(PortfolioNavDailyRow.id).where(
                        PortfolioNavDailyRow.user_id == user_id,
                        PortfolioNavDailyRow.run_id == run_id,
                    )
                    .limit(1)
                ).first()

            portfolio, _marks, total_value, _drawdown_pct, source = (
                sim.portfolio_marks_snapshot(user_id, kind="game", run_id=run_id)
            )
            capital_event = "open" if first_row is None else None

            # CR109 Amendment I — a run's NAV never goes below zero.
            #
            # This is the row the TWR chain links across, so it is the exact
            # place the floor has to be applied: TWR is undefined across a
            # sign change, and one negative NAV row would make every link
            # after it arithmetic about nothing — the Close, the board, the
            # drawdown denominator and the career-point delta all read off
            # this series. A wipeout is -100%, which is what a wipeout is.
            nav, shortfall = nav_floor(float(total_value))
            if shortfall > 0:
                _mark_run_bust(user_id, run_id, shortfall=shortfall, now=now)

            try:
                with get_session() as session:
                    session.add(PortfolioNavDailyRow(
                        user_id=user_id,
                        run_id=run_id,
                        as_of_date=as_of,
                        nav=round(nav, 2),
                        cash=round(float(portfolio.current_cash), 2),
                        price_source=_price_source_for_snapshot(
                            source, holding_count=len(portfolio.holdings),
                        ),
                        capital_event=capital_event,
                        created_at=now,
                    ))
                written += 1
            except IntegrityError:
                skipped += 1
        except Exception:
            logger.exception(
                "game_nav_snapshot_run_failed", user_id=str(user_id), run_id=str(run_id),
            )

    return {
        "as_of": as_of.isoformat(),
        "runs": len(targets),
        "written": written,
        "skipped_existing": skipped,
    }


# ── Reads ────────────────────────────────────────────────────────────────


def nav_history(
    user_id: UUID, *, run_id: UUID | None = None, limit: int = 365,
) -> list[PortfolioNavDailyRow]:
    """The trailing `limit` NAV rows for one (user, run), ascending by date.

    `run_id=None` (the default) reads the TRAINING portfolio — the only
    surface CR109 slice 1 writes.
    """
    run_filter = (
        PortfolioNavDailyRow.run_id.is_(None) if run_id is None
        else PortfolioNavDailyRow.run_id == run_id
    )
    with get_session() as session:
        rows = session.execute(
            select(PortfolioNavDailyRow)
            .where(PortfolioNavDailyRow.user_id == user_id, run_filter)
            .order_by(PortfolioNavDailyRow.as_of_date.desc())
            .limit(limit)
        ).scalars().all()
    return list(reversed(rows))


def twr_pct_for_window(rows: Sequence[PortfolioNavDailyRow]) -> float | None:
    """The chain-linked TWR over `rows`, as a rounded percent — `None` below
    two points, matching `time_weighted_return`'s own contract."""
    navs = [
        NavPoint(as_of=r.as_of_date, nav=float(r.nav), capital_event=r.capital_event)
        for r in rows
    ]
    twr = time_weighted_return(navs)
    return round(twr * 100, 2) if twr is not None else None
