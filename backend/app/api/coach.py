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
from app.schemas.journal import EntryType, JournalEntryCreate
from app.schemas.mandate import Plan
from app.services.coach_engine import (
    CoachEngine,
    get_coach_engine,
    hydrate_coach_mandate,
)
from app.services.journal_store import get_journal_store
from app.services.mandate_store import resolve_mandate
from app.services.overlay_store import (
    LIFETIME_EDIT_CAP_BY_PLAN,
    OverlayStore,
    get_overlay_store,
)
from app.api.dependencies import get_current_user
from app.db.models import User


router = APIRouter(
    prefix="/v1/coach",
    tags=["coach"],
    dependencies=[Depends(get_current_user)],
)


def _own_body(current_user: User, body_user_id: UUID) -> None:
    """Body-level ownership: the body's user_id must match the bearer."""
    if current_user.id != body_user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "access denied")


def _own_session(current_user: User, session) -> None:
    """Session-level ownership: load the session, compare its user_id."""
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "coach session not found")
    if session.user_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "access denied")


@router.post("/start", response_model=CoachStartResponse, status_code=status.HTTP_201_CREATED)
async def coach_start(
    req: CoachStartRequest,
    current_user: User = Depends(get_current_user),
    engine: CoachEngine = Depends(get_coach_engine),
) -> CoachStartResponse:
    _own_body(current_user, req.user_id)
    mandate = resolve_mandate(req.user_id, req.mandate_override, locale=req.locale)
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
    current_user: User = Depends(get_current_user),
    engine: CoachEngine = Depends(get_coach_engine),
) -> StreamingResponse:
    session = engine.get_session(req.session_id)
    _own_session(current_user, session)

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
    current_user: User = Depends(get_current_user),
    engine: CoachEngine = Depends(get_coach_engine),
) -> CoachProposal:
    session = engine.get_session(req.session_id)
    _own_session(current_user, session)
    return await engine.propose(session=session, history=req.history)


@router.post("/accept")
async def coach_accept(
    req: CoachAcceptRequest,
    current_user: User = Depends(get_current_user),
    engine: CoachEngine = Depends(get_coach_engine),
) -> dict:
    session = engine.get_session(req.session_id)
    _own_session(current_user, session)
    result = engine.accept(session=session, proposal_id=req.proposal_id)
    if isinstance(result, CoachRefusal):
        return {"ok": False, "refusal": result.model_dump(mode="json")}
    assert isinstance(result, UserOverlay)
    # Capture to Decision Journal — best-effort
    try:
        agent_id_str = (
            result.agent_id.value if hasattr(result.agent_id, "value")
            else str(result.agent_id)
        )
        get_journal_store().append(JournalEntryCreate(
            user_id=session.user_id,
            entry_type=EntryType.AGENT_COACH,
            reference_id=result.id,
            title=f"Coached {agent_id_str.replace('_', ' ').title()} → v{result.version}",
            summary=result.plain_english,
            agents_involved=[agent_id_str],
            payload={
                "version": result.version,
                "overlay": result.content,
            },
        ))
    except Exception:  # pragma: no cover
        pass
    return {"ok": True, "overlay": result.model_dump(mode="json")}


@router.post("/reject")
async def coach_reject(
    req: CoachRejectRequest,
    current_user: User = Depends(get_current_user),
    engine: CoachEngine = Depends(get_coach_engine),
) -> dict:
    session = engine.get_session(req.session_id)
    _own_session(current_user, session)
    ok = engine.reject(session=session, proposal_id=req.proposal_id)
    return {"ok": ok}


@router.post("/rollback", response_model=UserOverlay)
async def coach_rollback(
    req: CoachRollbackRequest,
    current_user: User = Depends(get_current_user),
    store: OverlayStore = Depends(get_overlay_store),
) -> UserOverlay:
    _own_body(current_user, req.user_id)
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
    current_user: User = Depends(get_current_user),
    store: OverlayStore = Depends(get_overlay_store),
) -> CoachHistoryResponse:
    if current_user.id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "access denied")
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
