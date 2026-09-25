"""Admin Room LLM call viewer + replay API — /v1/admin/room/* (CR200-R002).

The raw request (system prompt + message list) and raw response text for
every LLM call inside a convened Room, plus a "resend" sandbox to edit a
captured prompt and replay it — for testing prompt-wording changes before
they ship. Sub-CR of CR200 — own console tab.

Endpoint map:
  GET  /v1/admin/room/runs?ticker=&user_id=&days=7&limit=50   Recent runs to pick from
  GET  /v1/admin/room/runs/{run_id}                            Run detail (RoomRun)
  GET  /v1/admin/room/runs/{run_id}/llm-calls                  This run's captured LLM calls
  POST /v1/admin/room/llm-calls/{call_id}/resend               Edit + replay one call

`resend` is an ISOLATED raw LLM call — `gateway.stream_chat()` directly,
same no-side-effect shape as `POST /v1/llm/translate`
(`app/api/llm.py`), generalized to a full message list and an
overridable tier. It never re-enters `room_runner`: no verdict parsing, no
safety-floor pass, no credit spend, no Decision Journal write, and no
`room_runs` row is created or mutated. The replay's own gateway call is
still recorded to `llm_audit` (`audit_flow="admin_prompt_replay"`), so it
carries the same traceability every other LLM call does, and
`room_llm_calls.list_calls_for_run` excludes that flow so a replay is never
mistaken for a turn the Room itself took.

Gating follows every other admin route: `Depends(get_admin)`.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.api.admin import get_admin
from app.db import get_session
from app.schemas.room import RoomRun
from app.services import room_llm_calls
from app.services.admin_audit import record_admin_action
from app.services.cf_access import AdminIdentity
from app.services.llm_gateway import ChatMessage, ModelTier, get_llm_gateway
from app.services.room_runner import RoomRunner, get_room_runner

router = APIRouter(
    prefix="/v1/admin/room",
    tags=["admin"],
    dependencies=[Depends(get_admin)],
)


@router.get("/runs")
def list_runs(
    ticker: str | None = Query(default=None),
    user_id: UUID | None = Query(default=None),
    days: int = Query(default=7, ge=1, le=365),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    with get_session() as s:
        runs = room_llm_calls.list_recent_runs(
            s=s, ticker=ticker, user_id=user_id, days=days, limit=limit,
        )
    return {"runs": runs}


@router.get("/runs/{run_id}", response_model=RoomRun)
def get_run(
    run_id: UUID, runner: RoomRunner = Depends(get_room_runner),
) -> RoomRun:
    run = runner.get_run(run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "room run not found")
    return run


@router.get("/runs/{run_id}/llm-calls")
def get_run_llm_calls(
    run_id: UUID, runner: RoomRunner = Depends(get_room_runner),
) -> dict[str, Any]:
    run = runner.get_run(run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "room run not found")
    with get_session() as s:
        return room_llm_calls.list_calls_for_run(
            s=s,
            user_id=run.user_id,
            triggered_at=run.triggered_at,
            finished_at=run.finished_at,
        )


class ResendRequest(BaseModel):
    system_prompt: str | None = None
    messages: list[ChatMessage] | None = None
    model_tier: ModelTier | None = None
    max_tokens: int | None = None


class ResendResponse(BaseModel):
    response_text: str
    provider: str
    latency_ms: int
    # None when the just-written llm_audit row couldn't be confidently
    # re-identified afterward (see `find_replay_row`'s docstring) — never a
    # guessed id standing in for it.
    llm_audit_id: UUID | None


def _load_original_call(call_id: UUID) -> dict[str, Any]:
    """Sync DB read, run off the event loop via `run_in_threadpool` (DEF200:
    a bare `async def` handler doing this inline blocks the single uvicorn
    worker for every other request and every open SSE stream). Returns
    plain values, not the ORM row — the row is detached once its session
    closes, same reasoning as `resend_call`'s old inline comment."""
    with get_session() as s:
        original = room_llm_calls.get_call(s=s, call_id=call_id)
        if original is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "llm call not found")
        return {
            "system_prompt": original.system_prompt,
            "messages": original.messages,
            "tier": original.tier,
            "locale": original.locale,
            "agent_id": original.agent_id,
        }


def _finalize_resend(
    *, admin: AdminIdentity, call_id: UUID, agent_id: str | None,
    model_tier: ModelTier, req: ResendRequest, started_at: datetime,
) -> Any:
    """Sync DB write, likewise threadpooled. Re-finds the replay's own
    `llm_audit` row for the response and writes the `admin_audit` row in
    the same session/commit."""
    with get_session() as s:
        replay_row = room_llm_calls.find_replay_row(
            s=s, agent_id=agent_id, since=started_at,
        )
        record_admin_action(
            s, admin, "room_llm_call_resent",
            target=str(call_id),
            payload={
                "original_call_id": str(call_id),
                "agent_id": agent_id,
                "model_tier": model_tier,
                "edited_system_prompt": req.system_prompt is not None,
                "edited_messages": req.messages is not None,
                "replay_llm_audit_id": str(replay_row.id) if replay_row else None,
            },
        )
        s.commit()
        return replay_row.id if replay_row else None


@router.post("/llm-calls/{call_id}/resend", response_model=ResendResponse)
async def resend_call(
    call_id: UUID,
    req: ResendRequest,
    admin: AdminIdentity = Depends(get_admin),
) -> ResendResponse:
    original = await run_in_threadpool(_load_original_call, call_id)

    system_prompt = req.system_prompt if req.system_prompt is not None else original["system_prompt"]
    messages = req.messages if req.messages is not None else [
        ChatMessage(role=m["role"], content=m["content"]) for m in original["messages"]
    ]
    model_tier: ModelTier = req.model_tier or original["tier"]
    max_tokens = req.max_tokens or 2048
    original_agent_id = original["agent_id"]

    gateway = get_llm_gateway()
    started_at = datetime.now(timezone.utc)
    started = time.monotonic()
    chunks: list[str] = []
    async for chunk in gateway.stream_chat(
        system_prompt=system_prompt,
        messages=messages,
        model_tier=model_tier,
        locale=original["locale"] or "en",
        max_tokens=max_tokens,
        audit_agent_id=original_agent_id,
        audit_flow=room_llm_calls.REPLAY_FLOW,
    ):
        chunks.append(chunk)
    latency_ms = int((time.monotonic() - started) * 1000)
    status_info = gateway.status()

    llm_audit_id = await run_in_threadpool(
        _finalize_resend,
        admin=admin, call_id=call_id, agent_id=original_agent_id,
        model_tier=model_tier, req=req, started_at=started_at,
    )

    return ResendResponse(
        response_text="".join(chunks),
        provider=str(status_info.get("active_provider", "")),
        latency_ms=latency_ms,
        llm_audit_id=llm_audit_id,
    )
