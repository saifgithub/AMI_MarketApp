"""1-on-1 chat endpoints. POST to start, POST to send messages (SSE stream back)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.schemas import AgentId
from app.schemas.journal import EntryType, JournalEntryCreate
from app.schemas.mandate import Plan
from app.schemas.one_on_one import (
    OneOnOneMessageRequest,
    OneOnOneSession,
    OneOnOneStartRequest,
)
from app.services.agent_runner import AgentRunner, get_agent_runner, hydrate_mandate
from app.services.journal_store import get_journal_store
from app.services.lessons_service import get_lessons_service
from app.services.mandate_store import resolve_mandate
from app.api.dependencies import get_current_user
from app.db.models import User

router = APIRouter(
    prefix="/v1/agents",
    tags=["agents"],
    dependencies=[Depends(get_current_user)],
)


def _own_body(current_user: User, body_user_id: UUID | None) -> None:
    """Body-level ownership: body's user_id must match the bearer, when set."""
    if body_user_id is not None and current_user.id != body_user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "access denied")


def _own_session(current_user: User, session: OneOnOneSession | None) -> None:
    """Session ownership: load the session, compare its user_id to bearer."""
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found")
    # Strict: a session with no owner cannot be operated on by anyone.
    if session.user_id is None or session.user_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "access denied")


@router.post(
    "/one_on_one/start",
    response_model=OneOnOneSession,
    status_code=status.HTTP_201_CREATED,
)
async def start_one_on_one(
    req: OneOnOneStartRequest,
    current_user: User = Depends(get_current_user),
    runner: AgentRunner = Depends(get_agent_runner),
) -> OneOnOneSession:
    _own_body(current_user, req.user_id)
    # Prefer the user's stored mandate over the inline override
    mandate = resolve_mandate(
        req.user_id, req.mandate_override, locale=req.locale,
    )
    # If we fell through to defaults (no store + no override) keep using
    # hydrate_mandate's broader set of defaults to stay backward-compatible.
    if req.user_id is None and req.mandate_override is None:
        mandate = hydrate_mandate(None)
        mandate = mandate.model_copy(update={"locale": req.locale})

    # Gate: Floor Pass users must earn agents. Paid tiers (trader / floor
    # manager / trial_trader) skip-path everything. Concierge is always free.
    plan = (
        mandate.plan if isinstance(mandate.plan, Plan)
        else Plan(mandate.plan)
    )
    if (
        req.user_id is not None
        and plan == Plan.FLOOR_PASS
        and req.agent_id != AgentId.CONCIERGE
    ):
        unlocked = {a.agent_id for a in get_lessons_service().list_activations(req.user_id)}
        if req.agent_id.value not in unlocked:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail={
                    "reason": "agent_locked",
                    "message": "This agent is locked. Earn it by completing the related lessons, or upgrade to skip.",
                    "agent_id": req.agent_id.value,
                },
            )

    return runner.open_one_on_one(
        agent_id=req.agent_id, mandate=mandate, user_id=req.user_id
    )


@router.post("/one_on_one/message")
async def send_message(
    req: OneOnOneMessageRequest,
    current_user: User = Depends(get_current_user),
    runner: AgentRunner = Depends(get_agent_runner),
) -> StreamingResponse:
    """Send a user message; the response streams back as Server-Sent Events.

    Each event payload is a single content chunk (text). The stream ends with
    `event: done\\ndata: {...}` containing minimal stats.
    """
    session = runner.get_session(req.session_id)
    _own_session(current_user, session)

    async def event_stream():
        total_chars = 0
        buffer: list[str] = []
        try:
            async for chunk in runner.stream_one_on_one_message(
                session=session,
                history=req.history,
                user_message=req.user_message,
            ):
                total_chars += len(chunk)
                buffer.append(chunk)
                # SSE event format
                # Escape backslashes + newlines so the line stays valid
                safe = chunk.replace("\\", "\\\\").replace("\n", "\\n")
                yield f"event: token\ndata: {safe}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {str(e)[:300]}\n\n"
        finally:
            # Capture to Decision Journal — best-effort, never fail the stream
            try:
                if session.user_id is not None:
                    reply = "".join(buffer)
                    summary = reply[:240].rstrip() + ("…" if len(reply) > 240 else "")
                    agent_id_str = (
                        session.agent_id.value
                        if isinstance(session.agent_id, AgentId)
                        else str(session.agent_id)
                    )
                    get_journal_store().append(JournalEntryCreate(
                        user_id=session.user_id,
                        entry_type=EntryType.ONE_ON_ONE,
                        reference_id=session.id,
                        title=f"1-on-1 — {agent_id_str.replace('_', ' ').title()}",
                        summary=summary or req.user_message[:240],
                        agents_involved=[agent_id_str],
                        payload={
                            "user_message": req.user_message,
                            "assistant_reply": reply,
                        },
                    ))
            except Exception:  # pragma: no cover
                pass
            yield f"event: done\ndata: {{\"chars\": {total_chars}}}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/one_on_one/{session_id}", response_model=OneOnOneSession)
async def get_one_on_one(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    runner: AgentRunner = Depends(get_agent_runner),
) -> OneOnOneSession:
    session = runner.get_session(session_id)
    _own_session(current_user, session)
    return session
