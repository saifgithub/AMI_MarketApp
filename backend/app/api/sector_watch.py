"""Sector Watch endpoint (CR183) — the Floor's card 3 data.

GET /v1/sector-watch/{user_id} — one composing read answering "what's moving
where I look?": the top-moving GICS sector among the user's TOUCHED tickers
(watchlist + sim holdings), that sector's leader, and the leader's top
yfinance headline.

Definitions (CR183, locked at build):
  - touched tickers  = watchlist ∪ training-portfolio holdings.
  - sector move      = mean day `change_pct` over the user's LIVE-sourced
    touched tickers in the leading sector (mock_walk / unavailable quotes are
    EXCLUDED — a mock quote's change_pct is fabricated by construction).
  - leading sector   = largest absolute mean mover; Other/Cash buckets never
    lead (they aren't sectors).
  - leader           = largest absolute mover inside that sector.

Degrades loudly (CR040): `state` is "ok" | "empty" | "unavailable" — empty
(nothing touched yet; the card teaches) is a different fact from unavailable
(feed can't be read honestly: no live quotes, nothing classified, or no news
for the leader) and neither ever renders a fabricated 0.0% move. The endpoint
never 500s — composition failures degrade to `state=unavailable` with a
logged warning (`_build_room_sector_context` precedent).
"""

from __future__ import annotations

import asyncio
from statistics import fmean
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.core.logging import logger
from app.db.models import User
from app.services.sector_allocation import NON_SECTOR_BUCKETS, default_sector_map
from app.services.sim_engine import SimEngine, get_sim_engine
from app.services.watchlist_store import get_watchlist_store

router = APIRouter(
    prefix="/v1/sector-watch",
    tags=["sector-watch"],
    dependencies=[Depends(get_current_user)],
)

# Quote sources that must never feed the sector move: mock_walk fabricates
# change_pct and "unavailable" is the defensive floor (client convention in
# sim.dart's isLivePrice, mirrored server-side here).
_NON_LIVE_SOURCES = frozenset({"mock_walk", "unavailable"})


def _own(current_user: User, user_id: UUID) -> None:
    # 404, not 403 (CR183 decision): another user's sector watch should not
    # even confirm the user id exists.
    if current_user.id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")


def _resp(
    state: str,
    *,
    reason: str | None = None,
    sector: str | None = None,
    move_pct: float | None = None,
    leader: str | None = None,
    leader_change_pct: float | None = None,
    tickers_considered: int = 0,
    headline: dict | None = None,
    quote_source: str | None = None,
    news_source: str | None = None,
) -> dict:
    return {
        "state": state,
        "reason": reason,
        "sector": sector,
        "move_pct": move_pct,
        "leader": leader,
        "leader_change_pct": leader_change_pct,
        "tickers_considered": tickers_considered,
        "headline": headline,
        "quote_source": quote_source,
        "news_source": news_source,
    }


def _compose(user_id: UUID, sim: SimEngine) -> dict:
    watch = [e.ticker for e in get_watchlist_store().list_for_user(user_id)]
    holdings = [h.ticker for h in sim.ensure_portfolio(user_id).holdings]
    touched = sorted({str(t).upper().strip() for t in watch + holdings if t})
    if not touched:
        return _resp("empty")

    smap = default_sector_map()
    quotes = sim.current_marks_with_source(touched)
    by_sector: dict[str, list[tuple[str, float]]] = {}
    for ticker, q in quotes.items():
        if q.source in _NON_LIVE_SOURCES:
            continue
        sector = smap.sector(ticker)
        if sector in NON_SECTOR_BUCKETS:
            continue
        by_sector.setdefault(sector, []).append((ticker, q.change_pct))

    considered = sum(len(v) for v in by_sector.values())
    if not by_sector:
        return _resp("unavailable", reason="no_live_quotes")

    sector, movers = max(
        by_sector.items(), key=lambda kv: abs(fmean(c for _, c in kv[1])),
    )
    move_pct = fmean(c for _, c in movers)
    leader, leader_change_pct = max(movers, key=lambda tc: abs(tc[1]))

    articles, news_source = sim.current_news(leader, 1)
    if not articles:
        return _resp(
            "unavailable", reason="no_news",
            tickers_considered=considered, news_source=news_source,
        )
    top = articles[0]
    return _resp(
        "ok",
        sector=sector,
        move_pct=move_pct,
        leader=leader,
        leader_change_pct=leader_change_pct,
        tickers_considered=considered,
        headline={
            "title": top.title,
            "publisher": top.publisher,
            "published_at": top.published_at,
        },
        quote_source=quotes[leader].source,
        news_source=news_source,
    )


@router.get("/{user_id}")
async def sector_watch(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    sim: SimEngine = Depends(get_sim_engine),
) -> dict:
    _own(current_user, user_id)
    try:
        return await asyncio.to_thread(_compose, user_id, sim)
    except Exception as exc:  # noqa: BLE001 — degrade loudly, never 500 the Floor
        logger.warning(
            "sector_watch_failed", user_id=str(user_id), error=str(exc)[:200],
        )
        return _resp("unavailable", reason="error")
