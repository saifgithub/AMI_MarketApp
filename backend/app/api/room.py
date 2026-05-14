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
    """Run a Room session and stream events. Final 'done' event includes the
    run_id; clients then GET /v1/room/{id} for the persisted snapshot."""

    mandate = resolve_mandate(req.user_id, req.mandate_override, locale=req.locale)
    ticker = req.ticker.upper().strip()
    if not ticker:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ticker required")

    # Single async generator from the runner — shared between the SSE
    # consumer (this request) and the detached completion task (if the
    # client disconnects mid-stream).
    run_iter = runner.run(
        user_id=req.user_id,
        ticker=ticker,
        mandate=mandate,
        portfolio_value=req.portfolio_value,
        current_drawdown_pct=req.current_drawdown_pct,
    )

    async def _finalise_to_journal(run_id: UUID) -> None:
        """Append the ROOM_RUN journal entry from the persisted snapshot.

        Called once the runner has terminated — either through normal
        completion (in event_stream) or after disconnect-recovery (in
        _drain_to_completion).
        """
        if run_id is None:
            return
        run = runner.get_run(run_id)
        if run is None:
            return
        try:
            verdict_text = (
                f"{run.verdict.action} — "
                f"{run.verdict.reason}" if run.verdict else "no verdict"
            )
            get_journal_store().append(JournalEntryCreate(
                user_id=req.user_id,
                entry_type=EntryType.ROOM_RUN,
                reference_id=run.id,
                title=f"Room on {run.ticker} — {run.verdict.action if run.verdict else 'incomplete'}",
                summary=verdict_text[:240],
                ticker=run.ticker,
                agents_involved=[
                    m.agent_id if isinstance(m.agent_id, str)
                    else m.agent_id.value
                    for m in run.transcript
                ],
                mandate_version=run.mandate_version,
                tags=["room"],
                outcome=Outcome.PENDING,
                payload={
                    "verdict": (
                        run.verdict.model_dump(mode="json")
                        if run.verdict else None
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
            ))
        except Exception:  # pragma: no cover
            pass

    async def _drain_to_completion(run_id: UUID | None) -> None:
        """Keep pulling events from the runner so it persists the final
        state to the room_runs table, even though no client is watching.

        Triggered when the SSE generator is cancelled (client disconnect /
        phone sleep). The runner's internal _persist_run + verdict
        assembly happens during its async-generator execution, so we
        just need someone to keep iterating.
        """
        try:
            async for _ in run_iter:
                pass  # events go to /dev/null
        except Exception as e:
            logger.warning("room_drain_failed", run_id=str(run_id), error=str(e)[:200])
        else:
            logger.info("room_drained_after_disconnect", run_id=str(run_id))
        # Journal capture for the recovered completion.
        if run_id is not None:
            await _finalise_to_journal(run_id)

    async def event_stream():
        run_id: UUID | None = None
        disconnect_handed_off = False
        try:
            async for ev in run_iter:
                run_id = ev.run_id or run_id
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
                        yield (
                            f"event: verdict\n"
                            f"data: {ev.verdict.model_dump_json()}\n\n"
                        )
                elif ev.kind == "error":
                    yield f"event: error\ndata: {ev.text or 'unknown'}\n\n"
        except (asyncio.CancelledError, GeneratorExit):
            # Client gone — hand the generator off to a detached task so
            # the runner reaches its verdict + persists, and the user can
            # come back later and fetch GET /v1/room/{run_id}.
            asyncio.create_task(_drain_to_completion(run_id))
            disconnect_handed_off = True
            raise
        except Exception as e:  # pragma: no cover
            yield f"event: error\ndata: {str(e)[:300]}\n\n"
        finally:
            if not disconnect_handed_off:
                # Normal completion path: journal + done event.
                if run_id is not None:
                    await _finalise_to_journal(run_id)
                yield (
                    f"event: done\n"
                    f"data: {json.dumps({'run_id': str(run_id) if run_id else None})}\n\n"
                )

    return StreamingResponse(event_stream(), media_type="text/event-stream")


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
