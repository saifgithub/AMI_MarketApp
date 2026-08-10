"""Admin-only backtest trigger (CR164) — the ONLY surface that can start an
as-of Room run.

`POST /v1/admin/backtest/room-run` starts one Room convene in historical mode
(`AsOfContext` → the data layer serves only facts knowable on `as_of`; see
`app/services/asof_context.py`). Deliberately separate from the public
`/v1/room/stream`, whose request model never grows a backtest field — a real
client structurally cannot reach as-of mode. Auth is the existing static
ADMIN_SECRET bearer (`admin.get_admin`).

No SSE and no journal write: the sweep driver polls `GET /v1/room/{run_id}`
to terminal state, and scoring reads `room_runs ⋈ backtest_run_index` — a
backtest verdict is measurement data, not a user's decision history.

The scoreable-window refusal (as-of dates before the model-cutoff probe's
`window_start`) lives in the sweep driver and the report, not here — this
endpoint stays free of probe-result constants; the driver is the single
place that knows the current window.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from app.api.admin import get_admin
from app.core.logging import logger
from app.db import get_session
from app.services.asof_context import AsOfContext
from app.services.credit_service import InsufficientCredits
from app.services.mandate_store import resolve_mandate
from app.services.room_runner import RoomRunner, get_room_runner
from app.services.ticker_reference import (
    TickerNotFoundError,
    require_ticker_exists,
    ticker_not_found_detail,
)

router = APIRouter(
    prefix="/v1/admin/backtest",
    tags=["admin"],
    dependencies=[Depends(get_admin)],
)


class BacktestRoomRunRequest(BaseModel):
    user_id: UUID
    ticker: str
    as_of: date
    batch_id: str = Field(min_length=1, max_length=120)
    arm: str = "pit_v1"
    mandate_override: dict | None = None
    locale: str = "en"


@router.post("/room-run", status_code=status.HTTP_202_ACCEPTED)
async def start_backtest_room_run(
    req: BacktestRoomRunRequest,
    runner: RoomRunner = Depends(get_room_runner),
) -> dict:
    ticker = req.ticker.upper().strip()
    if not ticker:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ticker required")
    try:
        with get_session() as session:
            require_ticker_exists(session, ticker)
    except TickerNotFoundError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail=ticker_not_found_detail(exc)
        ) from exc

    mandate = resolve_mandate(req.user_id, req.mandate_override, locale=req.locale)
    ctx = AsOfContext(as_of=req.as_of, batch_id=req.batch_id, arm=req.arm)
    try:
        run_id = await runner.start_run(
            user_id=req.user_id,
            ticker=ticker,
            mandate=mandate,
            backtest=ctx,
        )
    except IntegrityError:
        # The uq_backtest_run idempotency gate: this (batch, ticker, as_of)
        # already ran. 409 so a resuming driver logs-and-skips, loudly.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"backtest pair already indexed: {req.batch_id}/{ticker}/{req.as_of}",
        ) from None
    except InsufficientCredits as e:
        # Same 402 shape as /v1/room/stream, so the driver's existing
        # top-up-on-402 logic works against this endpoint unchanged.
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, str(e)) from e
    logger.info(
        "backtest_room_run_accepted",
        run_id=str(run_id),
        ticker=ticker,
        as_of=req.as_of.isoformat(),
        batch_id=req.batch_id,
        arm=req.arm,
    )
    return {"run_id": str(run_id)}
