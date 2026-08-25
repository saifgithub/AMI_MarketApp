"""1-on-1 chat endpoints. POST to start, POST to send messages (SSE stream back)."""

import json

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.schemas import AgentId, agent_display_name
from app.schemas.journal import EntryType, JournalEntryCreate
from app.schemas.mandate import Plan
from app.schemas.one_on_one import (
    OneOnOneMessageRequest,
    OneOnOneSession,
    OneOnOneStartRequest,
)
from app.services.agent_runner import AgentRunner, get_agent_runner
from app.services.alpaca_service import render_snapshot
from app.services.credit_service import InsufficientCredits, one_on_one_cost, refund, spend
from app.services.entitlements import effective_plan_for_user
from app.services.journal_store import get_journal_store
from app.services.lessons_service import get_lessons_service
from app.services.mandate_store import resolve_mandate
from app.api.dependencies import get_current_user
from app.api.sse import sse_json, sse_text
from app.db.models import User
from app.services.rate_limit import (
    agent_stream_concurrency_limit,
    one_on_one_message_rate_limit,
)

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


def _agent_id_str(session: OneOnOneSession) -> str:
    return (
        session.agent_id.value
        if isinstance(session.agent_id, AgentId)
        else str(session.agent_id)
    )


@router.post(
    "/one_on_one/start",
    response_model=OneOnOneSession,
    status_code=status.HTTP_201_CREATED,
)
def start_one_on_one(
    req: OneOnOneStartRequest,
    current_user: User = Depends(get_current_user),
    runner: AgentRunner = Depends(get_agent_runner),
) -> OneOnOneSession:
    # L-1 cleanup (AT:R32): user identity comes from the Bearer token, not the
    # body. Removed the `_own_body(current_user, req.user_id)` check + the
    # `req.user_id is None` fallback branch — both are unreachable now that
    # `current_user.id` is always populated by the `Depends(get_current_user)`
    # guard at the router level.
    user_id = current_user.id
    mandate = resolve_mandate(
        user_id, req.mandate_override, locale=req.locale,
    )

    # Gate: Floor Pass users must earn agents. Paid tiers (trader / floor
    # manager / trial_trader) skip-path everything. Concierge is always free.
    # DEF179: reads `users.plan` via `effective_plan_for_user`, not
    # `mandate.plan` — the mandate's plan field is client-influenced (a
    # PATCH's stripped-but-formerly-writable field, or a `mandate_override`
    # body) and is not the entitlement source of truth.
    plan = effective_plan_for_user(user_id)
    if plan == Plan.FLOOR_PASS and req.agent_id != AgentId.CONCIERGE:
        unlocked = {a.agent_id for a in get_lessons_service().list_activations(user_id)}
        # `OneOnOneStartRequest` has `use_enum_values=True`, so `req.agent_id`
        # is already the raw string value here, not an `AgentId` member —
        # `.value` on it raised `AttributeError` (masked as a 500) on every
        # locked-agent request; found while adding DEF179 coverage for this
        # exact gate, fixed in the same touch.
        if req.agent_id not in unlocked:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail={
                    "reason": "agent_locked",
                    "message": "This agent is locked. Earn it by completing the related lessons, or upgrade to skip.",
                    "agent_id": req.agent_id,
                },
            )

    return runner.open_one_on_one(
        agent_id=req.agent_id, mandate=mandate, user_id=user_id
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
    # DEF186 (security review H6): messages spent zero credits and had NO
    # rate limiter at all. Per-user, 12/min — see brief.py's brief_message
    # for the same rationale (bearer-keyed, not IP).
    one_on_one_message_rate_limit.check(f"user:{current_user.id}")
    session = runner.get_session(req.session_id)
    _own_session(current_user, session)

    # DEF201: claim a concurrency slot before spending — a request bounced
    # for holding too many streams already open must never be charged.
    # Released in event_stream()'s finally, shared with brief.py (same
    # LLM compute budget regardless of surface).
    concurrency_key = f"user:{current_user.id}"
    agent_stream_concurrency_limit.acquire(concurrency_key)

    # DEF113: debit before the stream is on the wire — once the SSE status is
    # sent a refusal can only be an in-band error event, which the client
    # renders as a crash, not a paywall (same reasoning as room.py's 402).
    # `spend()` always runs the full path (ledger row written, balance
    # arithmetic executed) even at Alpha's configured price of 0 — a charge of
    # zero, never a skipped charge, so flipping the price later needs no new
    # code path.
    cost = one_on_one_cost()
    try:
        spend(current_user.id, cost, reason=f"one_on_one:{_agent_id_str(session)}")
    except InsufficientCredits as e:
        # DEF201: the generator (which would otherwise release the slot in
        # its finally) never runs on this path — release here or a 402
        # permanently steals one of this user's concurrency slots.
        agent_stream_concurrency_limit.release(concurrency_key)
        detail = {
            "code": "insufficient_credits",
            "balance": e.balance,
            "cost": e.cost,
            "plan": e.plan.value,
            "resets_at": e.resets_at.isoformat(),
        }
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, detail=detail) from e
    except BaseException:
        # DEF201 round 2 (audit M2). `spend()` opens a session, loads the user
        # and commits, so it can raise anything the DB can raise — an
        # OperationalError is not an InsufficientCredits, escapes the handler
        # above, and the generator's finally never runs because the generator
        # was never created. The slot then leaks with no TTL and no eviction:
        # two such failures wedge this user's 1-on-1 at 429 until the process
        # restarts, surviving the DB's own recovery.
        #
        # BaseException, not Exception: a CancelledError here (client hung up
        # mid-spend) leaks the slot exactly the same way, and asyncio's
        # CancelledError descends from BaseException.
        agent_stream_concurrency_limit.release(concurrency_key)
        raise

    async def event_stream():
        total_chars = 0
        buffer: list[str] = []
        failed = False
        try:
            async for chunk in runner.stream_one_on_one_message(
                session=session,
                history=req.history,
                user_message=req.user_message,
                alpaca_snapshot=render_snapshot(req.alpaca),
            ):
                total_chars += len(chunk)
                buffer.append(chunk)
                yield sse_text("token", chunk)
        except Exception as e:
            # DEF127: framed, not interpolated — see app/api/sse.py.
            failed = True
            yield sse_text("error", str(e)[:300])
        finally:
            # DEF201: release the concurrency slot on every exit — success,
            # in-stream error, or client disconnect (an `async for` broken
            # by cancellation still runs this finally).
            agent_stream_concurrency_limit.release(concurrency_key)
            # DEF113: charged-then-failed is a real user-visible wrong on a
            # money path even at price 0 (the ledger row persists regardless).
            # Refund before the journal write, mirroring room_runner's
            # failed-run refund — never let a provider blip silently eat a
            # turn the user never got.
            if failed and cost > 0:
                try:
                    refund(current_user.id, cost, reason=f"one_on_one_failed:{session.id}")
                except Exception:  # pragma: no cover
                    pass
            # Capture to Decision Journal — best-effort, never fail the stream
            try:
                if session.user_id is not None:
                    reply = "".join(buffer)
                    summary = reply[:240].rstrip() + ("…" if len(reply) > 240 else "")
                    agent_id_str = _agent_id_str(session)
                    get_journal_store().append(JournalEntryCreate(
                        user_id=session.user_id,
                        entry_type=EntryType.ONE_ON_ONE,
                        reference_id=session.id,
                        title=f"1-on-1 — {agent_display_name(agent_id_str)}",
                        summary=summary or req.user_message[:240],
                        agents_involved=[agent_id_str],
                        payload={
                            "user_message": req.user_message,
                            "assistant_reply": reply,
                        },
                    ))
            except Exception:  # pragma: no cover
                pass
            yield sse_json("done", json.dumps({"chars": total_chars}))

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/one_on_one/{session_id}", response_model=OneOnOneSession)
def get_one_on_one(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    runner: AgentRunner = Depends(get_agent_runner),
) -> OneOnOneSession:
    session = runner.get_session(session_id)
    _own_session(current_user, session)
    return session
