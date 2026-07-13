"""Convene the Room endpoints.

POST /v1/room/start    Open a session for a ticker (validates plan + access).
POST /v1/room/stream   Begin the run and stream agent contributions via SSE.
GET  /v1/room/{id}     Final snapshot (transcript + verdict).
GET  /v1/room/user/{user_id}  List recent runs for a user.

The stream wire format mirrors the 1-on-1 SSE pattern but adds richer event
types so the Flutter console can colour-code by phase + agent.

  event: phase
  data: {"label": "ANALYSTS"}

  event: agent_token
  data: {"agent_id": "fundamentals_analyst", "text": "Q"}

  event: agent_done
  data: {"agent_id": "fundamentals_analyst"}

  event: verdict
  data: {<Verdict JSON>}

  event: done
  data: {"run_id": "..."}

  event: error
  data: <error string>
"""

from __future__ import annotations

import asyncio
import json
import structlog
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict

logger = structlog.get_logger(__name__)

from app.schemas.journal import EntryType, JournalEntryCreate, Outcome
from app.schemas.room import RoomRun, Verdict
from app.services.journal_store import get_journal_store
from app.services.mandate_store import resolve_mandate
from app.services.room_runner import (
    RoomRunner,
    build_journal_entry_for_run,
    get_room_runner,
)
from app.api.dependencies import get_current_user
from app.db import get_session
from app.db.models import User
from app.services.rate_limit import room_stream_rate_limit
from app.services.reputation_service import get_reputation_service
from app.services.sim_engine import SimEngine, get_sim_engine


router = APIRouter(
    prefix="/v1/room",
    tags=["room"],
    dependencies=[Depends(get_current_user)],
)


# _build_journal_entry moved to services/room_runner.py as
# `build_journal_entry_for_run` so the runner's retry path (AT:R34,
# eeeb866f) can re-fire the journal write after a container restart
# without an upward import from services → api.
_build_journal_entry = build_journal_entry_for_run


class RoomStartRequest(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    user_id: UUID
    ticker: str
    mandate_override: dict | None = None
    locale: str = "en"


@router.post("/stream", dependencies=[Depends(room_stream_rate_limit)])
async def stream_room(
    req: RoomStartRequest,
    current_user: User = Depends(get_current_user),
    runner: RoomRunner = Depends(get_room_runner),
    sim: SimEngine = Depends(get_sim_engine),
) -> StreamingResponse:
    # Adversarial audit (2026-05-18) finding A6: body-level ownership.
    # Without this, an authenticated user can trigger a Room run under
    # another user's identity, polluting their journal and burning credits.
    if current_user.id != req.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "access denied")
    """Run a Room session and stream events via SSE.

    The run executes as a background task independent of the SSE connection —
    a client disconnect (phone sleep, LTE handoff, Cloudflare timeout) does
    NOT cancel the run. The run_id is returned in the X-Room-Run-Id response
    header before any SSE body arrives, so the client can store it and poll
    GET /v1/room/{run_id} on reconnect.

    Journal write and push notification hook fire via on_complete, which the
    background task calls on terminal state regardless of SSE connectivity.
    """
    mandate = resolve_mandate(req.user_id, req.mandate_override, locale=req.locale)
    ticker = req.ticker.upper().strip()
    if not ticker:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ticker required")

    async def _finalise_to_journal(run_id: UUID) -> None:
        """Write the Decision Journal entry. Retries 3× with exponential backoff
        so a transient DB hiccup doesn't silently drop the entry."""
        if run_id is None:
            return
        run = runner.get_run(run_id)
        if run is None:
            return
        for attempt in range(3):
            try:
                get_journal_store().append(_build_journal_entry(run, req.user_id))
                logger.info(
                    "room_push_stub",
                    run_id=str(run_id),
                    user_id=str(req.user_id),
                    action=run.verdict.action if run.verdict else "no_verdict",
                    note="TODO B1: fire APNs push notification here",
                )
                # Reputation (CR004): run-id ref dedup + the ROOM_DEDUP_*
                # windows prevent farming verdicts for points.
                if run.verdict is not None:
                    try:
                        with get_session() as s:
                            get_reputation_service().award(
                                s, user_id=req.user_id,
                                event_type="room_verdict", ref_id=str(run_id),
                            )
                    except Exception:  # pragma: no cover
                        pass
                return
            except Exception as exc:
                if attempt == 2:
                    logger.error(
                        "room_journal_all_retries_failed",
                        run_id=str(run_id),
                        error=str(exc)[:200],
                    )
                else:
                    await asyncio.sleep(2 ** attempt)  # 1 s, then 2 s

    # start_run() pre-allocates run_id, creates the event queue, and kicks
    # off the background task. Dedup tiers (in start_run):
    #   1. attached to in-flight run → events stream from current position
    #   2. attached to recently completed run → no events to stream; we
    #      replay the persisted transcript + verdict below so the client
    #      sees a full state instead of "no verdict" on the empty stream.
    # DEF051: resolve the user's real sim-portfolio state server-side — never
    # trust a client-suppliable override for a compliance-check input.
    portfolio_value = sim.total_value(req.user_id)
    current_drawdown_pct = sim.current_drawdown_pct(req.user_id)
    run_id = await runner.start_run(
        user_id=req.user_id,
        ticker=ticker,
        mandate=mandate,
        portfolio_value=portfolio_value,
        current_drawdown_pct=current_drawdown_pct,
        on_complete=_finalise_to_journal,
    )
    cached = not runner.is_active(run_id)

    async def event_stream():
        if cached:
            # Dedup hit on a completed run — replay the persisted snapshot
            # as a compressed SSE stream so the client renders the prior
            # verdict instead of falling through to "Room ended without a
            # verdict." Each agent's full content lands in one agent_token
            # event (the client concatenates into transcript[agent_id]).
            persisted = runner.get_run(run_id)
            if persisted is not None:
                yield f"event: started\ndata: {json.dumps({'run_id': str(run_id)})}\n\n"
                for msg in persisted.transcript:
                    aid = msg.agent_id if isinstance(msg.agent_id, str) else msg.agent_id.value
                    safe = (msg.content or "").replace("\\", "\\\\").replace("\n", "\\n")
                    yield f"event: agent_token\ndata: {json.dumps({'agent_id': aid, 'text': safe})}\n\n"
                    yield f"event: agent_done\ndata: {json.dumps({'agent_id': aid})}\n\n"
                if persisted.verdict is not None:
                    yield f"event: phase\ndata: {json.dumps({'label': 'VERDICT'})}\n\n"
                    yield f"event: verdict\ndata: {persisted.verdict.model_dump_json()}\n\n"
        else:
            async for ev in runner.subscribe(run_id):
                if ev.kind == "started":
                    payload = json.dumps({"run_id": str(ev.run_id)})
                    yield f"event: started\ndata: {payload}\n\n"
                elif ev.kind == "phase":
                    payload = json.dumps({"label": ev.phase})
                    yield f"event: phase\ndata: {payload}\n\n"
                elif ev.kind == "agent_token":
                    safe = (ev.text or "").replace("\\", "\\\\").replace("\n", "\\n")
                    payload = json.dumps({
                        "agent_id": ev.agent_id.value if ev.agent_id else None,
                        "text": safe,
                    })
                    yield f"event: agent_token\ndata: {payload}\n\n"
                elif ev.kind == "agent_done":
                    payload = json.dumps({
                        "agent_id": ev.agent_id.value if ev.agent_id else None,
                    })
                    yield f"event: agent_done\ndata: {payload}\n\n"
                elif ev.kind == "verdict":
                    if ev.verdict is not None:
                        yield f"event: verdict\ndata: {ev.verdict.model_dump_json()}\n\n"
                elif ev.kind == "error":
                    yield f"event: error\ndata: {ev.text or 'unknown'}\n\n"
        # on_complete callback (journal + push stub) fires from the background
        # task's finally block, not here — so it runs even on disconnect.
        # For cached replays there's no _pump task, hence no on_complete; the
        # original journal entry from the first run is the canonical record.
        yield f"event: done\ndata: {json.dumps({'run_id': str(run_id)})}\n\n"

    headers = {"X-Room-Run-Id": str(run_id)}
    if cached:
        # Lets the client UI surface "cached analysis from earlier today"
        # if it wants to differentiate a dedup hit from a fresh run.
        headers["X-Room-Cached"] = "true"
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=headers,
    )


@router.get("/{run_id}", response_model=RoomRun)
async def get_room(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    runner: RoomRunner = Depends(get_room_runner),
) -> RoomRun:
    run = runner.get_run(run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "room run not found")
    # Adversarial audit (2026-05-18) finding A6: prevent reading another
    # user's transcript / verdict by guessing or harvesting their run_id.
    if run.user_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "access denied")
    return run


@router.get("/user/{user_id}", response_model=list[RoomRun])
async def list_user_rooms(
    user_id: UUID,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    runner: RoomRunner = Depends(get_room_runner),
) -> list[RoomRun]:
    if current_user.id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "access denied")
    return runner.list_runs_for_user(user_id, limit=limit)
