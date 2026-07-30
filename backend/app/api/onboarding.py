"""Onboarding API endpoints — anonymous-first conversation."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user_optional
from app.core.time import now_utc
from app.db.models import User
from app.schemas import Mandate
from app.schemas.onboarding import (
    AnswerRequest,
    AnswerResponse,
    Author,
    ConversationStep,
    Message,
    OnboardingSession,
    ReadbackConfirmRequest,
    ReadbackConfirmResponse,
    StartOnboardingRequest,
    StartOnboardingResponse,
)
from app.services.concierge_engine import (
    make_welcome_messages,
    process_answer,
    session_to_mandate_dict,
)
from app.services.mandate_store import get_mandate_store
from app.services.session_store import InMemorySessionStore, get_session_store

router = APIRouter(prefix="/v1/onboarding", tags=["onboarding"])


@router.post(
    "/start",
    response_model=StartOnboardingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_onboarding(
    req: StartOnboardingRequest,
    store: InMemorySessionStore = Depends(get_session_store),
) -> StartOnboardingResponse:
    """Create a new anonymous onboarding session. Returns the welcome + first question."""
    session = OnboardingSession(
        locale=req.locale,
        timezone=req.timezone,
        current_step=ConversationStep.WELCOME,
    )
    welcome, first_q = make_welcome_messages()
    session.messages.append(welcome)
    await store.create(session)

    return StartOnboardingResponse(
        session_id=session.id,
        welcome_message=welcome,
        first_question=first_q,
    )


@router.get("/{session_id}", response_model=OnboardingSession)
async def get_session(
    session_id: UUID,
    store: InMemorySessionStore = Depends(get_session_store),
) -> OnboardingSession:
    session = await store.get(session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found or expired")
    return session


@router.post("/answer", response_model=AnswerResponse)
async def submit_answer(
    req: AnswerRequest,
    store: InMemorySessionStore = Depends(get_session_store),
) -> AnswerResponse:
    """User submits an answer to the current question. Returns the next Concierge message."""
    session = await store.get(req.session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found or expired")

    # Record the user's message in the transcript
    session.messages.append(
        Message(
            author=Author.USER,
            content=req.answer,
            step=req.step,
            timestamp=now_utc(),
        )
    )

    next_step, concierge_reply, readback = process_answer(session, req.step, req.answer)
    session.messages.append(concierge_reply)
    await store.save(session)

    return AnswerResponse(
        next_step=next_step,
        concierge_reply=concierge_reply,
        readback_summary=readback,
    )


@router.post("/readback/confirm", response_model=ReadbackConfirmResponse)
async def confirm_readback(
    req: ReadbackConfirmRequest,
    store: InMemorySessionStore = Depends(get_session_store),
    current_user: User | None = Depends(get_current_user_optional),
) -> ReadbackConfirmResponse:
    """User confirms (or edits) the readback summary. Marks session complete.

    DEF160: onboarding stays anonymous-first — `current_user` is a best-effort
    Bearer read (`get_current_user_optional`), never required, so an anon
    caller with no token still completes the interview exactly as before.
    An already-signed-in user retaking the interview *is* authenticated here
    (unlike the anonymous-then-claim path), so this is the only place that
    can carry an explicit, authorised "replace my mandate" signal. That
    signal is `req.restart` — it must be BOTH true AND paired with a valid
    Bearer token to do anything, so it can't be set by accident from an
    anonymous client. This is a distinct operation from
    `_bind_onboarding_session`'s claim-time bind in auth.py: that guard
    (DEF060) still refuses to clobber a mandate on session_id replay with no
    restart signal, and this path never touches it.
    """
    session = await store.get(req.session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found or expired")

    if req.confirm == "edit":
        # Not implemented yet (no mobile UI calls this path — the readback
        # screen only offers confirm). Fail before touching session state:
        # this used to apply the edits to session.answers and persist them
        # before raising, so a client told "this failed, restart" had
        # actually already had its session mutated underneath it.
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            "edit flow lands W2 day 3 — for now, restart the session",
        )

    # confirm path
    session.completed = True
    session.current_step = ConversationStep.COMPLETE
    await store.save(session)

    if req.restart and current_user is not None:
        # Explicit + authenticated: replace the caller's current mandate
        # outright. upsert() bumps the version and keeps prior rows for
        # history/journal replay.
        mandate_dict = session_to_mandate_dict(session, user_id=current_user.id)
        applied = get_mandate_store().upsert(
            current_user.id, Mandate.model_validate(mandate_dict)
        )
        mandate_preview = applied.model_dump(mode="json")
    else:
        # In a real flow this is where account claim is offered; in V0 we
        # just produce a mandate preview for the next screen.
        mandate_preview = session_to_mandate_dict(session, user_id="anonymous-pending-claim")

    follow_up = Message(
        author=Author.CONCIERGE,
        content=(
            "Your mandate is saved. Your 12 analysts are calibrating to you. "
            "Ready to meet them?"
        ),
        step=ConversationStep.COMPLETE,
    )

    return ReadbackConfirmResponse(
        completed=True,
        final_step=ConversationStep.COMPLETE,
        mandate_preview=mandate_preview,
        follow_up_message=follow_up,
    )
