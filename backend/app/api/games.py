"""CR109 slices 2+3 — "the run" and "the close": the game's backend API.

GET  /v1/games/cadences                  next field, entry state, queue count + deadline
POST /v1/games/enter                     enter the current weekly field (free, 409 if already held)
GET  /v1/games/runs                      caller's OWN live runs, with TWR + days left
GET  /v1/games/runs/{run_id}             detail + NAV series for the curve
POST /v1/games/runs/{run_id}/trade       the game trade path (no mandate; market-hours queue)
POST /v1/games/runs/{run_id}/trade/quote pre-confirm card: shares, est. fee, book-percentage
POST /v1/games/runs/{run_id}/restart     forfeit preview + commit
GET  /v1/games/runs/{run_id}/close       the Close payload — three beats + the debrief panel
GET  /v1/games/runs/{run_id}/arc         the period arc's live beat (slice 5, design §10)
GET  /v1/games/record                    career points (signed net), forfeit count, run history
GET  /v1/games/record/prs                the PR board — self-competition, works at n=1

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
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.api.dependencies import get_current_user
from app.db import get_session
from app.db.models import User
from app.schemas.trade import OrderType, Side
from app.services import games_arc, games_board, games_desks
from app.services import games_record_service as record_service
from app.services import games_service as games
from app.services.ticker_reference import (
    TickerNotFoundError,
    require_ticker_exists,
    ticker_not_found_detail,
)

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


def _translate_record(exc: record_service.RecordServiceError) -> HTTPException:
    if isinstance(exc, record_service.RunNotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    if isinstance(exc, record_service.RunNotClosedError):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    return HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))  # pragma: no cover


class EnterGameRequest(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    cadence: str = games.WEEKLY_CADENCE
    # One tap at entry: going wild / testing a thesis / playing it
    # disciplined (design §10.4). Optional — a player may skip the tap.
    intent: str | None = None


class GameTradeRequest(BaseModel):
    """Shares only — deliberately NOT notional.

    Outside US market hours this order QUEUES, and `games_service.submit_trade`
    never touches `current_price` on that path: pricing a queued order at
    queue time is precisely the stale-price hindsight exploit §5.1 exists to
    prevent. Accepting dollars here would force a price fetch to convert, and
    the fence would be gone.

    The ticket sizes in dollars, so the client quotes first (which may size by
    notional) and sends the share count the quote returned. The order is then
    filled at the NEXT OPEN's price, which is the honest one.
    """

    model_config = ConfigDict(use_enum_values=True)

    ticker: str
    side: Side = Side.BUY
    # STRICTLY POSITIVE. A zero-share order is not an order — and it is what
    # a sizing bug produces. When the client's cash read 0.0 (it looked for
    # `cash`, the wire says `current_cash`), every percentage sized to zero
    # and this endpoint accepted all of them: five orders sat queued for
    # 0.0000 shares, each reported to the player as placed. Refusing the
    # number here turns a silent no-op into a visible 422 at the moment the
    # arithmetic goes wrong.
    quantity: float = Field(gt=0)
    order_type: OrderType = OrderType.MARKET
    limit_price: float | None = None
    stop: float | None = None
    target: float | None = None
    horizon_days: int | None = None


class GameQuoteRequest(BaseModel):
    """Size a quote by SHARES or by DOLLARS — exactly one.

    The 3-tap ticket sizes by percentage of book (Amendment D), which is
    inherently a notional amount, and the client cannot convert it to shares
    without a price it does not have. So the quote accepts `notional` and
    resolves the share count here, where the price already is.

    Pricing here is safe: a quote is a preview, and it already calls
    `current_quote`. `GameTradeRequest` deliberately does NOT accept notional —
    see its docstring.
    """

    model_config = ConfigDict(use_enum_values=True)

    ticker: str
    side: Side = Side.BUY
    quantity: float | None = Field(default=None, gt=0)
    notional: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _exactly_one_size(self) -> "GameQuoteRequest":
        if (self.quantity is None) == (self.notional is None):
            raise ValueError(
                "provide exactly one of `quantity` (shares) or `notional` "
                "(AMI Cash to deploy)"
            )
        return self


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
            ticker=req.ticker, side=side,
            quantity=req.quantity, notional=req.notional,
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


@router.get("/runs/{run_id}/orders")
async def queued_orders(
    run_id: UUID, current_user: User = Depends(get_current_user),
) -> list[dict]:
    """§13.3's Queued-orders surface — "the most-seen state in the product"
    for GCC/SEA players, who place most orders outside US market hours.
    Every estimate carries `price_source` (CR040 on the wire)."""
    try:
        return await asyncio.to_thread(
            games.list_queued_orders, current_user.id, run_id,
        )
    except games.GamesServiceError as exc:
        raise _translate(exc) from exc


@router.post("/runs/{run_id}/orders/{order_id}/cancel")
async def cancel_queued_order(
    run_id: UUID, order_id: UUID, current_user: User = Depends(get_current_user),
) -> dict:
    """The ticket promises "free to cancel any time before it fills" (§5.1).
    This is what lets the app keep that promise."""
    try:
        return await asyncio.to_thread(
            games.cancel_queued_order, current_user.id, run_id, order_id,
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


@router.get("/runs/{run_id}/close")
async def run_close(
    run_id: UUID, current_user: User = Depends(get_current_user),
) -> dict:
    """The Close payload — COMPLETE without an entitlement (implementation_
    plan.md §6): rank, delta, curve, both counterfactual lines, markers and
    the re-entry CTA, for every plan. The paid post-mortem is a later
    slice and is not built here."""
    try:
        return await asyncio.to_thread(
            record_service.get_close_payload, current_user.id, run_id,
        )
    except record_service.RecordServiceError as exc:
        raise _translate_record(exc) from exc


@router.get("/runs/{run_id}/board")
async def run_board(
    run_id: UUID, current_user: User = Depends(get_current_user),
) -> dict:
    """Where you stand against the rest of the field — Saiful's *"How do I see
    my current standing against the rest of the field?"*

    Ranks on % TWR only (design §6.1's written-down invariant: a board that
    ranks money makes capital tier pay-to-win), moves once per close rather
    than per tick (§10), and carries no mirror and no currency amount for any
    entrant including the caller."""
    try:
        return await asyncio.to_thread(games_board.board_for_run, current_user.id, run_id)
    except games_board.BoardNotAvailable as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/runs/{run_id}/arc")
async def run_arc(
    run_id: UUID, current_user: User = Depends(get_current_user),
) -> dict:
    """CR109 slice 5 — which beat of the period arc this run is in (design
    §10): the entry countdown, the bell, the daily standing, the final
    stretch, the settlement freeze.

    Separate from `GET /runs/{run_id}` on purpose: the run detail is polled
    while the screen is open, and this walks every entrant's NAV series to
    rank the field. Standings move once per close; the attribution line is
    live — `games_arc`'s docstring carries the reasoning for the split."""
    try:
        return await asyncio.to_thread(games_arc.arc_for_run, current_user.id, run_id)
    except games_arc.ArcNotAvailable as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/desks")
async def desks(current_user: User = Depends(get_current_user)) -> list[dict]:
    """The house desks' published rules (design §11.2). Disclosure is the
    feature — a player must be able to reproduce any desk's basket by hand,
    which is what makes studying a desk education rather than signal-chasing."""
    return games_desks.published_roster()


@router.get("/record")
async def record(current_user: User = Depends(get_current_user)) -> dict:
    return await asyncio.to_thread(record_service.get_record, current_user.id)


@router.get("/record/prs")
async def record_prs(current_user: User = Depends(get_current_user)) -> dict:
    """The PR board — self-competition, the only competitive surface that
    works at n=1 (implementation_plan.md §4.4.2 / §8.4 of the design)."""
    return await asyncio.to_thread(record_service.get_personal_records, current_user.id)
