"""POST /concierge/message — public website chatbot, SSE stream.

Streams the AMI Concierge's answer token-by-token (same wire protocol the mobile
app uses: `event: token` / `event: error` / `event: done`). Read-only, no side
effects, no user data. Grounded strictly in the FAQ knowledge base with a
deterministic advice/account/legal escalation floor (see faq_answer).

Security: rate-limited (5/min/IP) + hard input caps. Turnstile is verified when a
token is supplied (defense in depth) but not required — a chat is multi-turn and
Turnstile tokens are single-use, so the rate limiter + caps are the primary control
here; the email-triggering forms (/contact, /data-request) hard-require Turnstile.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.net import client_ip
from app.services.faq_answer import stream_answer
from app.services.rate_limit import concierge_rate_limit
from app.services.turnstile import verify_turnstile

router = APIRouter()


class Turn(BaseModel):
    role: str
    content: str = Field(max_length=2000)


class ConciergeRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[Turn] = Field(default_factory=list, max_length=8)
    turnstile_token: str | None = None


def _sse_escape(chunk: str) -> str:
    return chunk.replace("\\", "\\\\").replace("\n", "\\n")


@router.post("/concierge/message", dependencies=[Depends(concierge_rate_limit)])
async def concierge_message(req: ConciergeRequest, request: Request) -> StreamingResponse:
    # Defense in depth: if a token is present, it must be valid; absence is allowed.
    if req.turnstile_token is not None:
        if not await verify_turnstile(req.turnstile_token, remote_ip=client_ip(request)):
            async def _rejected():
                yield "event: error\ndata: verification_failed\n\n"
            return StreamingResponse(_rejected(), media_type="text/event-stream")

    history = [{"role": t.role, "content": t.content} for t in req.history]

    async def event_stream():
        total = 0
        try:
            async for chunk in stream_answer(req.message, history):
                total += len(chunk)
                yield f"event: token\ndata: {_sse_escape(chunk)}\n\n"
        except Exception:
            yield "event: error\ndata: concierge_unavailable\n\n"
            return
        yield f'event: done\ndata: {{"chars": {total}}}\n\n'

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
