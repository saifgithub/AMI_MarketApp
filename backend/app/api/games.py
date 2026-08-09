"""CR109 slice 2 — "the run": the game's backend API.

GET  /v1/games/cadences                  next field, entry state, queue count + deadline
POST /v1/games/enter                     enter the current weekly field (free, 409 if already held)
GET  /v1/games/runs                      caller's OWN live runs, with TWR + days left
GET  /v1/games/runs/{run_id}             detail + NAV series for the curve
POST /v1/games/runs/{run_id}/trade       the game trade path (no mandate; market-hours queue)
POST /v1/games/runs/{run_id}/trade/quote pre-confirm card: shares, est. fee, book-percentage
POST /v1/games/runs/{run_id}/restart     forfeit preview + commit

**THE DARK-LAUNCH REQUIREMENT.** This router is registered in `main.py`
with `include_in_schema=False` — `test_cr109_games_dark_launch.py` asserts
no `/v1/games` path ever appears in `app.openapi()`. Do not remove that
kwarg; `settings.env != "prod"` still serves `/docs` + the default
`/openapi.json` on Alpha, so without it this whole surface is published
while it is meant to be dark.

Follows `api/league.py`'s conventions: no `user_id` path param, every
route acts on `current_user.id` — there is no cross-user surface in slice 2
(no board, no Close), so nothing here ever needs to render another
player's data, let alone their AMI Cash.

Every response carrying a number carries its basis (CR040 on the wire):
`price_source`, `twr_pct`'s two-point floor, `capital_event`, `fee` vs
`estimated_fee`. Zero compliance surface — the game path never touches the
training safety floor.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from app.api.dependencies import get_current_user
from app.db.models import User
from app.schemas.trade import OrderType, Side
from app.services import games_service as games
from app.services.ticker_reference import (
    TickerNotFoundError,
    require_ticker_exists,
    ticker_not_found_detail,
)
from app.db import get_session

router = APIRouter(prefix="/v1/games", tags=["games"], include_in_schema=False)


def _require_ticker_or_422(ticker: str) -> None:
    try:
        with get_session() as session:
            require_ticker_exists(session, ticker)
    except TickerNotFoundError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail=ticker_not_found_detail(exc)
        ) from exc


def _translate(exc: games.GamesServiceError) -> HTTPException:
    if isinstance(exc, games.AlreadyEnteredError):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    if isinstance(exc, games.FieldNotOpenError):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    if isinstance(exc, games.RunNotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    if isinstance(exc, games.RunNotLiveError):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    if isinstance(exc, games.UnsupportedCadenceError):
        return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    return HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))  # pragma: no cover


class EnterGameRequest(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    cadence: str = games.WEEKLY_CADENCE
    # One tap at entry: going wild / testing a thesis / playing it
    # disciplined (design §10.4). Optional — a player may skip the tap.
    intent: str | None = None


class GameTradeRequest(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    ticker: str
    side: Side = Side.BUY
    quantity: float
    order_type: OrderType = OrderType.MARKET
    limit_price: float | None = None
    stop: float | None = None
    target: float | None = None
    horizon_days: int | None = None


class GameQuoteRequest(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    ticker: str
    side: Side = Side.BUY
    quantity: float


@router.get("/cadences")
async def cadences(current_user: User = Depends(get_current_user)) -> list[dict]:
    return await asyncio.to_thread(games.list_cadences, current_user.id)


@router.post("/enter")
async def enter(
    req: EnterGameRequest, current_user: User = Depends(get_current_user),
) -> dict:
    try:
        entry = await asyncio.to_thread(
            games.enter_field,
            current_user.id, cadence=req.cadence, intent=req.intent,
        )
    except games.GamesServiceError as exc:
        raise _translate(exc) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return {
        "run_id": str(entry.run_id),
        "field_id": str(entry.field_id),
        "state": entry.state,
        "intent": entry.intent,
    }


@router.get("/runs")
async def runs(current_user: User = Depends(get_current_user)) -> list[dict]:
    return await asyncio.to_thread(games.list_live_runs, current_user.id)


@router.get("/runs/{run_id}")
async def run_detail(
    run_id: UUID, current_user: User = Depends(get_current_user),
) -> dict:
    detail = await asyncio.to_thread(games.get_run_detail, current_user.id, run_id)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
    return detail


@router.post("/runs/{run_id}/trade/quote")
async def trade_quote(
    run_id: UUID, req: GameQuoteRequest, current_user: User = Depends(get_current_user),
) -> dict:
    _require_ticker_or_422(req.ticker)
    side = req.side if isinstance(req.side, Side) else Side(req.side)
    try:
        return await asyncio.to_thread(
            games.quote_trade,
            current_user.id, run_id,
            ticker=req.ticker, side=side, quantity=req.quantity,
        )
    except games.GamesServiceError as exc:
        raise _translate(exc) from exc


@router.post("/runs/{run_id}/trade")
async def trade(
    run_id: UUID, req: GameTradeRequest, current_user: User = Depends(get_current_user),
) -> dict:
    _require_ticker_or_422(req.ticker)
    side = req.side if isinstance(req.side, Side) else Side(req.side)
    order_type = (
        req.order_type if isinstance(req.order_type, OrderType)
        else OrderType(req.order_type)
    )
    try:
        return await asyncio.to_thread(
            games.submit_trade,
            current_user.id, run_id,
            ticker=req.ticker, side=side, quantity=req.quantity,
            order_type=order_type, limit_price=req.limit_price,
            stop=req.stop, target=req.target, horizon_days=req.horizon_days,
        )
    except games.GamesServiceError as exc:
        raise _translate(exc) from exc


@router.post("/runs/{run_id}/restart")
async def restart(
    run_id: UUID,
    commit: bool = False,
    current_user: User = Depends(get_current_user),
) -> dict:
    """`commit=false` (default) previews the forfeit; `commit=true` commits
    it. Two calls, one endpoint — matches "forfeit preview + commit" from
    implementation_plan.md §6 without inventing a second route."""
    try:
        if commit:
            return await asyncio.to_thread(games.commit_restart, current_user.id, run_id)
        return await asyncio.to_thread(games.preview_restart, current_user.id, run_id)
    except games.GamesServiceError as exc:
        raise _translate(exc) from exc
