"""LLM status + translate endpoints — operator-side helpers.

`/status` surfaces which provider the gateway will use (no provider call).
`/translate` is the convenience non-streaming pass-through that
`scripts/translate_arb.py` uses to localise the Flutter ARB files via
the on-prem vLLM Gemma 4. It accumulates the SSE stream into a single
string and returns it. Not used by the mobile app; intended for the
translation tooling pipeline only.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.llm_gateway import ChatMessage, get_llm_gateway

router = APIRouter(prefix="/v1/llm", tags=["llm"])


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
