"""Coach Your Agent endpoints.

Routes:
  POST   /v1/coach/start
  POST   /v1/coach/message     (SSE stream)
  POST   /v1/coach/propose     (synchronous — returns CoachProposal)
  POST   /v1/coach/accept      (returns UserOverlay or CoachRefusal)
  POST   /v1/coach/reject      (returns {ok})
  POST   /v1/coach/rollback    (returns UserOverlay)
  GET    /v1/coach/history/{user_id}/{agent_id}
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.schemas import (
    AgentId,
    CoachHistoryResponse,
    CoachProposal,
    CoachRefusal,
    CoachSession,
    UserOverlay,
)
from app.schemas.coach import (
    CoachAcceptRequest,
    CoachMessageRequest,
    CoachProposeRequest,
    CoachRejectRequest,
    CoachRollbackRequest,
    CoachStartRequest,
    CoachStartResponse,
)
from app.services.coach_engine import (
    CoachEngine,
    get_coach_engine,
    hydrate_coach_mandate,
)
from app.services.overlay_store import (
    LIFETIME_EDIT_CAP_BY_PLAN,
    OverlayStore,
    get_overlay_store,
)
from app.schemas.mandate import Plan


router = APIRouter(prefix="/v1/coach", tags=["coach"])


@router.post("/start", response_model=CoachStartResponse, status_code=status.HTTP_201_CREATED)
async def coach_start(
    req: CoachStartRequest,
    engine: CoachEngine = Depends(get_coach_engine),
) -> CoachStartResponse:
    mandate = hydrate_coach_mandate(req.mandate_override)
    mandate = mandate.model_copy(update={"locale": req.locale, "user_id": req.user_id})
    session, current, opener = engine.open_session(
        user_id=req.user_id,
        agent_id=req.agent_id,
        mode=req.mode,
        mandate=mandate,
    )
    return CoachStartResponse(
        session=session,
        current_overlay=current,
        opening_message=opener,
    )


@router.post("/message")
async def coach_message(
    req: CoachMessageRequest,
    engine: CoachEngine = Depends(get_coach_engine),
) -> StreamingResponse:
    session = engine.get_session(req.session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "coach session not found")

    async def event_stream():
        total = 0
        try:
            async for chunk in engine.stream_chat(
                session=session,
                history=req.history,
                user_message=req.user_message,
            ):
                total += len(chunk)
                safe = chunk.replace("\\", "\\\\").replace("\n", "\\n")
                yield f"event: token\ndata: {safe}\n\n"
        except Exception as e:  # pragma: no cover — surfaced to client
            yield f"event: error\ndata: {str(e)[:300]}\n\n"
        finally:
            yield f"event: done\ndata: {{\"chars\": {total}}}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/propose", response_model=CoachProposal)
async def coach_propose(
    req: CoachProposeRequest,
    engine: CoachEngine = Depends(get_coach_engine),
) -> CoachProposal:
    session = engine.get_session(req.session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "coach session not found")
    return await engine.propose(session=session, history=req.history)


@router.post("/accept")
async def coach_accept(
    req: CoachAcceptRequest,
    engine: CoachEngine = Depends(get_coach_engine),
) -> dict:
    session = engine.get_session(req.session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "coach session not found")
    result = engine.accept(session=session, proposal_id=req.proposal_id)
    if isinstance(result, CoachRefusal):
        return {"ok": False, "refusal": result.model_dump(mode="json")}
    assert isinstance(result, UserOverlay)
    return {"ok": True, "overlay": result.model_dump(mode="json")}


@router.post("/reject")
async def coach_reject(
    req: CoachRejectRequest,
    engine: CoachEngine = Depends(get_coach_engine),
) -> dict:
    session = engine.get_session(req.session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "coach session not found")
    ok = engine.reject(session=session, proposal_id=req.proposal_id)
    return {"ok": ok}


@router.post("/rollback", response_model=UserOverlay)
async def coach_rollback(
    req: CoachRollbackRequest,
    store: OverlayStore = Depends(get_overlay_store),
) -> UserOverlay:
    try:
        return store.rollback_to(req.user_id, req.agent_id, req.to_version)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


@router.get(
    "/history/{user_id}/{agent_id}",
    response_model=CoachHistoryResponse,
)
async def coach_history(
    user_id: UUID,
    agent_id: AgentId,
    plan: str = "trial_trader",
    store: OverlayStore = Depends(get_overlay_store),
) -> CoachHistoryResponse:
    try:
        plan_enum = Plan(plan)
    except ValueError:
        plan_enum = Plan.TRIAL_TRADER
    versions = store.list_versions(user_id, agent_id)
    active_v = store.active_version(user_id, agent_id)
    edits = store.edit_count(user_id, agent_id)
    cap = LIFETIME_EDIT_CAP_BY_PLAN.get(plan_enum)
    remaining: int | None = None if cap is None else max(0, cap - edits)
    return CoachHistoryResponse(
        user_id=user_id,
        agent_id=agent_id,
        versions=versions,
        active_version=active_v,
        edit_count=edits,
        edits_remaining=remaining,
    )
