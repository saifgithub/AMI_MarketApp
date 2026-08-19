"""LLM status + translate endpoints — operator-side helpers.

`/status` surfaces which provider the gateway will use (no provider call).
`/translate` is the convenience non-streaming pass-through that
`scripts/translate_arb.py` uses to localise the Flutter ARB files via
the on-prem vLLM Gemma 4. It accumulates the SSE stream into a single
string and returns it. Not used by the mobile app; intended for the
translation tooling pipeline only.

DEF177 (security review C2): both routes were unauthenticated and
internet-reachable — `/translate` is an arbitrary-prompt LLM proxy (free
compute / cash on Anthropic fallback) and `/status` discloses provider
config to anonymous callers. Gated behind the same static ADMIN_SECRET
bearer as `/v1/admin/*` — this router is operator tooling only, and
`get_admin` already 503s loudly if ADMIN_SECRET is unset rather than
failing open.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.admin import get_admin
from app.services.llm_gateway import ChatMessage, get_llm_gateway

router = APIRouter(prefix="/v1/llm", tags=["llm"], dependencies=[Depends(get_admin)])


class TranslateRequest(BaseModel):
    system_prompt: str = Field(..., description="System role text.")
    user_message: str = Field(..., description="The single user-turn prompt.")
    max_tokens: int = Field(default=2048, ge=1, le=16384)


class TranslateResponse(BaseModel):
    text: str
    provider: str


@router.get("/status")
async def llm_status() -> dict[str, object]:
    return get_llm_gateway().status()


@router.post("/translate", response_model=TranslateResponse)
async def llm_translate(req: TranslateRequest) -> TranslateResponse:
    gateway = get_llm_gateway()
    chunks: list[str] = []
    async for chunk in gateway.stream_chat(
        system_prompt=req.system_prompt,
        messages=[ChatMessage(role="user", content=req.user_message)],
        model_tier="cheap",
        locale="en",
        max_tokens=req.max_tokens,
        audit_flow="translate",
    ):
        chunks.append(chunk)
    status = gateway.status()
    return TranslateResponse(
        text="".join(chunks),
        provider=str(status.get("active_provider", "")),
    )


@router.get("/cache_rate")
async def llm_cache_rate(limit: int = 2) -> dict[str, object]:
    """The vLLM prefix-cache hit rate over the most recent window (CR192).

    This lives here rather than beside a per-call figure because there is no
    per-call figure to sit beside: `usage.prompt_tokens_details.cached_tokens`
    is None on every vLLM response (upstream V1-engine bug), so
    `llm_audit.cache_read_tokens` is permanently NULL for the provider serving
    all of Alpha. The rate exists only as a difference between two readings of
    the server's own lifetime counters.

    `rate` is null whenever `status` is not `ok`, and the statuses are not
    interchangeable with zero:

      `reset`                 the counters descended, so vLLM restarted inside
                              the window. Not a cache collapse — no measurement.
      `no_queries_in_window`  no traffic. Not a 0% hit rate — nothing was asked.
      `insufficient_samples`  fewer than two readings stored yet.

    A caller that renders `rate ?? 0` defeats the entire point (CR040).
    """
    from app.services.vllm_metrics import windowed_rate

    w = windowed_rate(limit=limit)
    return {
        "status": w.status,
        "rate": w.rate,
        "queries_delta": w.queries_delta,
        "hits_delta": w.hits_delta,
        "window_start": w.window_start.isoformat() if w.window_start else None,
        "window_end": w.window_end.isoformat() if w.window_end else None,
    }
