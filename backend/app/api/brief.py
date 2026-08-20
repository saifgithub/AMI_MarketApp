"""Brief Your Agent endpoints (was Coach Your Agent — renamed AT:R27).

Routes:
  POST   /v1/brief/start
  POST   /v1/brief/message     (SSE stream)
  POST   /v1/brief/propose     (synchronous — returns BriefProposal)
  POST   /v1/brief/accept      (returns UserOverlay or BriefRefusal)
  POST   /v1/brief/reject      (returns {ok})
  POST   /v1/brief/rollback    (returns UserOverlay)
  GET    /v1/brief/history/{user_id}/{agent_id}
"""

from __future__ import annotations

import json

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.schemas import (
    AgentId,
    agent_display_name,
    BriefHistoryResponse,
    BriefProposal,
    BriefRefusal,
    BriefSession,
    UserOverlay,
)
from app.schemas.brief import (
    BriefAcceptRequest,
    BriefMessageRequest,
    BriefProposeRequest,
    BriefRejectRequest,
    BriefRollbackRequest,
    BriefStartRequest,
    BriefStartResponse,
)
from app.schemas.journal import EntryType, JournalEntryCreate
from app.schemas.mandate import Plan
from app.services.brief_engine import (
    BriefEngine,
    get_brief_engine,
    hydrate_brief_mandate,
)
from app.services.journal_store import get_journal_store
from app.services.mandate_store import resolve_mandate
from app.services.overlay_store import (
    LIFETIME_EDIT_CAP_BY_PLAN,
    OverlayStore,
    get_overlay_store,
)
from app.api.dependencies import get_current_user
from app.api.sse import sse_json, sse_text
from app.db.models import User
from app.services.rate_limit import agent_stream_concurrency_limit, brief_message_rate_limit


router = APIRouter(
    prefix="/v1/brief",
    tags=["brief"],
    dependencies=[Depends(get_current_user)],
)


def _own_body(current_user: User, body_user_id: UUID) -> None:
    """Body-level ownership: the body's user_id must match the bearer."""
    if current_user.id != body_user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "access denied")


def _own_session(current_user: User, session) -> None:
    """Session-level ownership: load the session, compare its user_id."""
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "brief session not found")
    if session.user_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "access denied")


@router.post("/start", response_model=BriefStartResponse, status_code=status.HTTP_201_CREATED)
async def brief_start(
    req: BriefStartRequest,
    current_user: User = Depends(get_current_user),
    engine: BriefEngine = Depends(get_brief_engine),
) -> BriefStartResponse:
    _own_body(current_user, req.user_id)
    mandate = resolve_mandate(req.user_id, req.mandate_override, locale=req.locale)
    session, current, opener = engine.open_session(
        user_id=req.user_id,
        agent_id=req.agent_id,
        mode=req.mode,
        mandate=mandate,
    )
    return BriefStartResponse(
        session=session,
        current_overlay=current,
        opening_message=opener,
    )


@router.post("/message")
async def brief_message(
    req: BriefMessageRequest,
    current_user: User = Depends(get_current_user),
    engine: BriefEngine = Depends(get_brief_engine),
) -> StreamingResponse:
    # DEF186 (security review H6): Brief turns spent zero credits and had
    # NO rate limiter at all — one free anon token bought unlimited LLM
    # turns. Per-user (bearer-derived, not IP — an anon user can rotate
    # devices/IPs trivially but the bearer identifies the same billed
    # user), 12/min. Checked here rather than as a router-level Depends
    # so the deprecated /v1/coach/* shim (which calls this same function
    # directly) inherits the same protection instead of needing its own
    # copy.
    brief_message_rate_limit.check(f"user:{current_user.id}")
    session = engine.get_session(req.session_id)
    _own_session(current_user, session)

    # DEF201: shared cap with one_on_one.py's send_message — same LLM
    # compute budget regardless of which surface it's spent through.
    concurrency_key = f"user:{current_user.id}"
    agent_stream_concurrency_limit.acquire(concurrency_key)

    async def event_stream():
        total = 0
        try:
            async for chunk in engine.stream_chat(
                session=session,
                history=req.history,
                user_message=req.user_message,
            ):
                total += len(chunk)
                yield sse_text("token", chunk)
        except Exception as e:  # pragma: no cover — surfaced to client
            # DEF127: framed, not interpolated. A pydantic ValidationError's
            # message is always multi-line, which used to truncate this event
            # at its first line — and a blank line in it forged a new event.
            yield sse_text("error", str(e)[:300])
        finally:
            # DEF201: release on every exit — success, in-stream error, or
            # client disconnect.
            agent_stream_concurrency_limit.release(concurrency_key)
            yield sse_json("done", json.dumps({"chars": total}))

    try:
        return StreamingResponse(event_stream(), media_type="text/event-stream")
    except BaseException:
        # DEF201 round 2 (audit M2, symmetry). The auditor scoped M2 to
        # one_on_one.py, where `spend()` gives the acquire→generator window a
        # real trigger. Brief has no spend, so this window is far narrower —
        # only StreamingResponse construction itself — but the leak class is
        # identical and a leaked slot here wedges the SAME shared counter.
        # Fixing the reported instance and knowingly leaving its twin is how
        # a class becomes a recurrence.
        agent_stream_concurrency_limit.release(concurrency_key)
        raise


@router.post("/propose", response_model=BriefProposal)
async def brief_propose(
    req: BriefProposeRequest,
    current_user: User = Depends(get_current_user),
    engine: BriefEngine = Depends(get_brief_engine),
) -> BriefProposal:
    session = engine.get_session(req.session_id)
    _own_session(current_user, session)
    return await engine.propose(session=session, history=req.history)


@router.post("/accept")
async def brief_accept(
    req: BriefAcceptRequest,
    current_user: User = Depends(get_current_user),
    engine: BriefEngine = Depends(get_brief_engine),
) -> dict:
    session = engine.get_session(req.session_id)
    _own_session(current_user, session)
    result = engine.accept(session=session, proposal_id=req.proposal_id)
    if isinstance(result, BriefRefusal):
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
            title=f"Briefed {agent_display_name(agent_id_str)} → v{result.version}",
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
async def brief_reject(
    req: BriefRejectRequest,
    current_user: User = Depends(get_current_user),
    engine: BriefEngine = Depends(get_brief_engine),
) -> dict:
    session = engine.get_session(req.session_id)
    _own_session(current_user, session)
    ok = engine.reject(session=session, proposal_id=req.proposal_id)
    return {"ok": ok}


@router.post("/rollback", response_model=UserOverlay)
async def brief_rollback(
    req: BriefRollbackRequest,
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
    response_model=BriefHistoryResponse,
)
async def brief_history(
    user_id: UUID,
    agent_id: AgentId,
    plan: str = "trial_trader",
    current_user: User = Depends(get_current_user),
    store: OverlayStore = Depends(get_overlay_store),
) -> BriefHistoryResponse:
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
    return BriefHistoryResponse(
        user_id=user_id,
        agent_id=agent_id,
        versions=versions,
        active_version=active_v,
        edit_count=edits,
        edits_remaining=remaining,
    )
