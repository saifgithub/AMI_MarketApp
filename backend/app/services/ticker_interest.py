"""CR200-R001 — ticker interest analytics: what tickers/tickets users research and
trade, and their order fulfilment, aggregated per symbol.

Portable SQLAlchemy, same convention as `admin_analytics.py` (runs on melehost
Postgres and the sqlite unit fixture). Reuses `admin_analytics._real_users_clause()`
so counts exclude the same CR035 room-benchmark synthetics, seed-burst rows,
and CR125/DEF227-229 probe users already excluded from every other admin
metric — a per-ticker breakdown built on an unfiltered user set would just be
those same distortions cut a different way.

No raw ticker-lookup/view telemetry exists (no `research_events` table) — the
interest signals available are Room runs (`room_runs`), trades (`sim_trades`),
resting orders (`sim_resting_orders`), and watchlist adds (`sim_watchlists`).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select

from app.db import get_session
from app.db.models import RoomRunRow, SimRestingOrderRow, SimTradeRow, SimWatchlistRow, User
from app.services.admin_analytics import _real_users_clause
from app.services.sim_engine import OPEN_RESTING_STATES, TERMINAL_RESTING_STATES

# CR200-R001 audit MINOR-1: these were hand-restated string literals with no
# tie to the model's declared vocabulary, so an 8th state (added to
# sim_engine.py's RestingOrderState/TERMINAL_RESTING_STATES) would silently
# fall through every bucket below. Derived from sim_engine.py's own tuples
# instead — the canonical source `SimRestingOrderRow`'s docstring (models.py)
# describes — so this file changes automatically when that one does.
_PENDING_STATES = OPEN_RESTING_STATES
_TERMINAL_NOT_FILLED_STATES = tuple(s for s in TERMINAL_RESTING_STATES if s != "filled")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def top_tickers(days: int = 30, limit: int = 25) -> dict[str, Any]:
    """Room runs grouped by ticker, real users only."""
    since = _utcnow() - timedelta(days=days)
    with get_session() as s:
        rows = s.execute(
            select(
                RoomRunRow.ticker,
                func.count().label("runs"),
                func.count(func.distinct(RoomRunRow.user_id)).label("researchers"),
                func.sum(func.coalesce(RoomRunRow.credit_cost, 0)).label("credits"),
            )
            .select_from(RoomRunRow)
            .join(User, User.id == RoomRunRow.user_id)
            .where(_real_users_clause(), RoomRunRow.triggered_at >= since)
            .group_by(RoomRunRow.ticker)
            .order_by(func.count().desc())
            .limit(limit)
        ).all()
        status_rows = s.execute(
            select(RoomRunRow.ticker, RoomRunRow.status, func.count())
            .select_from(RoomRunRow)
            .join(User, User.id == RoomRunRow.user_id)
            .where(_real_users_clause(), RoomRunRow.triggered_at >= since)
            .group_by(RoomRunRow.ticker, RoomRunRow.status)
        ).all()

    by_status: dict[str, dict[str, int]] = {}
    for ticker, status, n in status_rows:
        by_status.setdefault(ticker, {})[status] = n

    return {
        "days": days,
        "tickers": [
            {
                "ticker": ticker,
                "runs": runs,
                "researchers": researchers,
                "credits_spent": int(credits or 0),
                "by_status": by_status.get(ticker, {}),
            }
            for ticker, runs, researchers, credits in rows
        ],
    }


def ticker_orders(days: int = 30, limit: int = 25) -> dict[str, Any]:
    """Orders grouped by ticker: filled vs. pending vs. terminal-not-filled."""
    since = _utcnow() - timedelta(days=days)
    with get_session() as s:
        filled_rows = s.execute(
            select(SimTradeRow.ticker, func.count())
            .select_from(SimTradeRow)
            .join(User, User.id == SimTradeRow.user_id)
            .where(_real_users_clause(), SimTradeRow.opened_at >= since)
            .group_by(SimTradeRow.ticker)
        ).all()
        order_rows = s.execute(
            select(SimRestingOrderRow.ticker, SimRestingOrderRow.state, func.count())
            .select_from(SimRestingOrderRow)
            .join(User, User.id == SimRestingOrderRow.user_id)
            .where(_real_users_clause(), SimRestingOrderRow.placed_at >= since)
            .group_by(SimRestingOrderRow.ticker, SimRestingOrderRow.state)
        ).all()

    def _blank() -> dict[str, int]:
        return {"filled": 0, "pending": 0, "not_filled": 0, "other": 0}

    by_ticker: dict[str, dict[str, int]] = {}
    for ticker, n in filled_rows:
        by_ticker.setdefault(ticker, _blank())
        by_ticker[ticker]["filled"] += n
    for ticker, state, n in order_rows:
        by_ticker.setdefault(ticker, _blank())
        if state == "filled":
            by_ticker[ticker]["filled"] += n
        elif state in _PENDING_STATES:
            by_ticker[ticker]["pending"] += n
        elif state in _TERMINAL_NOT_FILLED_STATES:
            by_ticker[ticker]["not_filled"] += n
        else:
            # CR200-R001 audit MINOR-1: a state outside the documented seven
            # (models.py SimRestingOrderRow) must never vanish silently — an
            # admin reading "12 filled, 3 pending, 1 not filled" has no way
            # to know a row was dropped. Degrade loudly (CR040) instead:
            # count it, don't drop it. test_all_states_are_bucketed pins the
            # vocabulary so an eighth state fails the suite, not this branch.
            by_ticker[ticker]["other"] += n

    ranked = sorted(
        by_ticker.items(),
        key=lambda kv: sum(kv[1].values()),
        reverse=True,
    )[:limit]

    return {
        "days": days,
        "tickers": [{"ticker": t, **counts} for t, counts in ranked],
    }


def watchlist_interest(days: int = 30, limit: int = 25) -> dict[str, Any]:
    """Most-watchlisted tickers, real users only."""
    since = _utcnow() - timedelta(days=days)
    with get_session() as s:
        rows = s.execute(
            select(SimWatchlistRow.ticker, func.count())
            .select_from(SimWatchlistRow)
            .join(User, User.id == SimWatchlistRow.user_id)
            .where(_real_users_clause(), SimWatchlistRow.added_at >= since)
            .group_by(SimWatchlistRow.ticker)
            .order_by(func.count().desc())
            .limit(limit)
        ).all()
    return {
        "days": days,
        "tickers": [{"ticker": ticker, "watchlist_adds": n} for ticker, n in rows],
    }


def ticker_detail(ticker: str, days: int = 90) -> dict[str, Any]:
    """One symbol's full interest history, real users only."""
    since = _utcnow() - timedelta(days=days)
    with get_session() as s:
        runs = s.execute(
            select(RoomRunRow.id, RoomRunRow.user_id, RoomRunRow.status,
                   RoomRunRow.triggered_at, RoomRunRow.credit_cost)
            .select_from(RoomRunRow)
            .join(User, User.id == RoomRunRow.user_id)
            .where(_real_users_clause(), RoomRunRow.ticker == ticker,
                   RoomRunRow.triggered_at >= since)
            .order_by(RoomRunRow.triggered_at.desc())
        ).all()
        trades = s.execute(
            select(SimTradeRow.id, SimTradeRow.user_id, SimTradeRow.side,
                   SimTradeRow.quantity, SimTradeRow.status, SimTradeRow.opened_at)
            .select_from(SimTradeRow)
            .join(User, User.id == SimTradeRow.user_id)
            .where(_real_users_clause(), SimTradeRow.ticker == ticker,
                   SimTradeRow.opened_at >= since)
            .order_by(SimTradeRow.opened_at.desc())
        ).all()
        orders = s.execute(
            select(SimRestingOrderRow.id, SimRestingOrderRow.user_id,
                   SimRestingOrderRow.side, SimRestingOrderRow.state,
                   SimRestingOrderRow.placed_at)
            .select_from(SimRestingOrderRow)
            .join(User, User.id == SimRestingOrderRow.user_id)
            .where(_real_users_clause(), SimRestingOrderRow.ticker == ticker,
                   SimRestingOrderRow.placed_at >= since)
            .order_by(SimRestingOrderRow.placed_at.desc())
        ).all()
        watchlist_adds = s.execute(
            select(func.count())
            .select_from(SimWatchlistRow)
            .join(User, User.id == SimWatchlistRow.user_id)
            .where(_real_users_clause(), SimWatchlistRow.ticker == ticker)
        ).scalar_one()

    return {
        "ticker": ticker,
        "days": days,
        "room_runs": [
            {
                "id": str(rid), "user_id": str(uid), "status": status,
                "triggered_at": ts.isoformat() if ts else None,
                "credit_cost": cost,
            }
            for rid, uid, status, ts, cost in runs
        ],
        "trades": [
            {
                "id": str(tid), "user_id": str(uid), "side": side,
                "quantity": float(qty), "status": status,
                "opened_at": ts.isoformat() if ts else None,
            }
            for tid, uid, side, qty, status, ts in trades
        ],
        "resting_orders": [
            {
                "id": str(oid), "user_id": str(uid), "side": side, "state": state,
                "placed_at": ts.isoformat() if ts else None,
            }
            for oid, uid, side, state, ts in orders
        ],
        "watchlist_adds": watchlist_adds,
    }
