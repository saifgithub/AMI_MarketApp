"""On-prem model streaming client — ported from the app backend's VLLMProvider.

Deliberately a *copy*, not an import: the website stack keeps zero shared code
with `backend/` (WEBSITE.md security decision). This is the self-contained
OpenAI-compatible SSE streamer only — no tier policy, no audit DB, no per-user
context. It calls the same on-prem vLLM server the backend uses, directly over
the LAN (`VLLM_BASE_URL`), so no Cloudflare hop is involved.

If `VLLM_BASE_URL` is unset the client reports unavailable and callers fall back
to scripted KB replies (degrade loudly, CR040 — never a dead "offline" bot).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal

import httpx

from app.core.config import settings
from app.core.logging import logger


@dataclass
class ChatMessage:
    role: Literal["system", "user", "assistant"]
    content: str


class LLMClient:
    """Streams chat completions from the on-prem vLLM server (OpenAI schema)."""

    def __init__(self) -> None:
        self._base_url = settings.vllm_base_url.rstrip("/")
        self._model = settings.vllm_model
        self._api_key = settings.vllm_api_key or None
        self._client: httpx.AsyncClient | None = None
        if self._base_url:
            headers = {"Content-Type": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            self._client = httpx.AsyncClient(
                base_url=self._base_url, headers=headers, timeout=45.0
            )
            logger.info("llm_client_ready", base_url=self._base_url, model=self._model)
        else:
            logger.info("llm_client_disabled", reason="no VLLM_BASE_URL")

    def available(self) -> bool:
        return self._client is not None

    async def stream_chat(
        self,
        *,
        system_prompt: str,
        messages: list[ChatMessage],
        max_tokens: int = 512,
    ) -> AsyncIterator[str]:
        """Yield content chunks as they arrive. Raises if the client is disabled."""
        if self._client is None:
            raise RuntimeError("llm_client_disabled")

        openai_messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt}
        ]
        for m in messages:
            openai_messages.append({"role": m.role, "content": m.content})

        body = {
            "model": self._model,
            "messages": openai_messages,
            "max_tokens": max_tokens,
            "stream": True,
        }

        async with self._client.stream(
            "POST", "/v1/chat/completions", json=body
        ) as resp:
            if resp.status_code != 200:
                err_body = await resp.aread()
                logger.error(
                    "llm_error", status=resp.status_code, body=err_body.decode()[:300]
                )
                raise RuntimeError(f"llm_http_{resp.status_code}")

            async for line in resp.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data = line[len("data: ") :].strip()
                if data == "[DONE]":
                    return
                try:
                    obj = json.loads(data)
                    choices = obj.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    content = delta.get("content")
                    if content:
                        yield content
                except Exception as e:
                    logger.warn("llm_chunk_parse_failed", error=str(e))

    async def complete(
        self, *, system_prompt: str, messages: list[ChatMessage], max_tokens: int = 512
    ) -> str:
        """Collapse the stream into a single string (used by the email auto-answer)."""
        parts: list[str] = []
        async for chunk in self.stream_chat(
            system_prompt=system_prompt, messages=messages, max_tokens=max_tokens
        ):
            parts.append(chunk)
        return "".join(parts).strip()


_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
