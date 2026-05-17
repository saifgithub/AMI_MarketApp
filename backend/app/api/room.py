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
from app.services.room_runner import RoomRunner, get_room_runner


router = APIRouter(prefix="/v1/room", tags=["room"])


def _build_journal_entry(run: RoomRun, user_id: UUID) -> JournalEntryCreate:
    """Build a JournalEntryCreate from a finished (or failed) RoomRun.

    Completed runs: title = "Room on {ticker} — APPROVE/REJECT"
    Failed/incomplete runs: title = "Room on {ticker} — {status}", summary
    describes how many agents completed and what error occurred (if any).
    Exposed at module level so it can be unit-tested directly.
    """
    if run.verdict is not None:
        title = f"Room on {run.ticker} — {run.verdict.action}"
        summary = f"{run.verdict.action} — {run.verdict.reason}"
    else:
        status = run.status if isinstance(run.status, str) else run.status.value
        agents_done = len(run.transcript)
        error_detail = (
            f" — {run.error_message[:80]}" if run.error_message else ""
        )
        title = f"Room on {run.ticker} — {status}"
        summary = (
            f"Run stopped after {agents_done} of 12 agents "
            f"without reaching a verdict{error_detail}"
        )
    return JournalEntryCreate(
        user_id=user_id,
        entry_type=EntryType.ROOM_RUN,
        reference_id=run.id,
        title=title,
        summary=summary[:240],
        ticker=run.ticker,
        agents_involved=[
            m.agent_id if isinstance(m.agent_id, str) else m.agent_id.value
            for m in run.transcript
        ],
        mandate_version=run.mandate_version,
        tags=["room"],
        outcome=Outcome.PENDING,
        payload={
            "verdict": (
                run.verdict.model_dump(mode="json") if run.verdict else None
            ),
            "model_tier": run.model_tier,
            "transcript": [
                {
                    "agent_id": (
                        m.agent_id if isinstance(m.agent_id, str)
                        else m.agent_id.value
                    ),
                    "content": m.content,
                } for m in run.transcript
            ],
        },
    )


class RoomStartRequest(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    user_id: UUID
    ticker: str
    mandate_override: dict | None = None
    locale: str = "en"
    portfolio_value: float = 100_000.0
    current_drawdown_pct: float = 0.0


@router.post("/stream")
async def stream_room(
    req: RoomStartRequest,
    runner: RoomRunner = Depends(get_room_runner),
) -> StreamingResponse:
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
    # off the background task. Dedup: if this user already has a running run
    # for this ticker, returns the existing run_id instead.
    run_id = await runner.start_run(
        user_id=req.user_id,
        ticker=ticker,
        mandate=mandate,
        portfolio_value=req.portfolio_value,
        current_drawdown_pct=req.current_drawdown_pct,
        on_complete=_finalise_to_journal,
    )

    async def event_stream():
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
        yield f"event: done\ndata: {json.dumps({'run_id': str(run_id)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"X-Room-Run-Id": str(run_id)},
    )


@router.get("/{run_id}", response_model=RoomRun)
async def get_room(
    run_id: UUID,
    runner: RoomRunner = Depends(get_room_runner),
) -> RoomRun:
    run = runner.get_run(run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "room run not found")
    return run


@router.get("/user/{user_id}", response_model=list[RoomRun])
async def list_user_rooms(
    user_id: UUID,
    limit: int = 50,
    runner: RoomRunner = Depends(get_room_runner),
) -> list[RoomRun]:
    return runner.list_runs_for_user(user_id, limit=limit)
