"""LLM status endpoint — surfaces which provider the gateway will use.

Lives so Saiful can `curl /v1/llm/status` after dropping ANTHROPIC_API_KEY
into backend/.env and instantly see whether the live flip took effect.

This endpoint does NOT call any provider — it only inspects the gateway's
in-process state. Safe to call cheaply and often.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.services.llm_gateway import get_llm_gateway

router = APIRouter(prefix="/v1/llm", tags=["llm"])


@router.get("/status")
async def llm_status() -> dict[str, object]:
    return get_llm_gateway().status()
