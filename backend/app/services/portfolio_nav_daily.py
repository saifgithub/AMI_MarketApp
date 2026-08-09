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
from app.db.models import PortfolioNavDailyRow, SimPortfolioRow
from app.trading_math.twr import NavPoint, time_weighted_return

_MOCK_MARKER = "mock"


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
        user_ids = [
            row.user_id
            for row in session.execute(select(SimPortfolioRow)).scalars().all()
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
                        price_source=_normalize_price_source(source),
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
