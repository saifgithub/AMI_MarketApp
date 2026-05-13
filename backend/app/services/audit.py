"""Audit-logging write helpers.

AT:R16 — comprehensive alpha-era logging. Every write here is best-effort:
any exception in audit code MUST NOT break the request that triggered it.
Wrap callers in try/except logging.exception and continue.

Retention policy: unbounded for now. Before scaling testers past a few
dozen, add a nightly trim job (eg. DELETE WHERE created_at < now() - 90 days)
or partition the tables monthly. TODO once tester count grows.
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from app.core.logging import logger
from app.db.models import HTTPAuditRow, LLMAuditRow, OneOnOneMessageRow
from app.db.session import get_session


# Body capture limits — bigger than typical, smaller than catastrophic. SSE
# response bodies skip capture (handled at the middleware level).
MAX_BODY_BYTES = 64 * 1024
MAX_PROMPT_CHARS = 200_000
MAX_RESPONSE_CHARS = 200_000


def record_llm_call(
    *,
    user_id: Optional[UUID],
    agent_id: Optional[str],
    flow: Optional[str],
    tier: str,
    provider: str,
    locale: Optional[str],
    system_prompt: str,
    messages: list[dict[str, Any]],
    response_text: Optional[str],
    latency_ms: Optional[int],
    error: Optional[str],
) -> None:
    """Persist one LLM gateway call. Safe to call from any code path."""
    try:
        with get_session() as session:
            row = LLMAuditRow(
                user_id=user_id,
                agent_id=agent_id,
                flow=flow,
                tier=tier,
                provider=provider,
                locale=locale,
                system_prompt=(system_prompt or "")[:MAX_PROMPT_CHARS],
                messages=messages,
                response_text=(response_text or "")[:MAX_RESPONSE_CHARS] if response_text is not None else None,
                latency_ms=latency_ms,
                error=(error or None) and error[:500],
            )
            session.add(row)
            session.commit()
    except Exception:
        logger.exception("audit_llm_write_failed")


def record_http(
    *,
    method: str,
    path: str,
    query: Optional[str],
    user_id: Optional[UUID],
    client_ip: Optional[str],
    status_code: int,
    request_body: Optional[bytes],
    response_body: Optional[bytes],
    response_truncated: bool,
    is_streaming: bool,
    latency_ms: int,
) -> None:
    """Persist one HTTP request. Safe to call from any code path."""
    try:
        with get_session() as session:
            row = HTTPAuditRow(
                method=method,
                path=path,
                query=query,
                user_id=user_id,
                client_ip=client_ip,
                status_code=status_code,
                request_body=_decode_body(request_body),
                response_body=_decode_body(response_body),
                response_truncated=response_truncated,
                is_streaming=is_streaming,
                latency_ms=latency_ms,
            )
            session.add(row)
            session.commit()
    except Exception:
        logger.exception("audit_http_write_failed", path=path)


def record_one_on_one_message(
    *,
    session_id: UUID,
    user_id: UUID,
    agent_id: str,
    role: str,
    content: str,
) -> None:
    """Persist one chat turn. Role is 'user' or 'assistant'."""
    try:
        with get_session() as session:
            row = OneOnOneMessageRow(
                session_id=session_id,
                user_id=user_id,
                agent_id=agent_id,
                role=role,
                content=content,
            )
            session.add(row)
            session.commit()
    except Exception:
        logger.exception("audit_one_on_one_write_failed", session_id=str(session_id))


def _decode_body(body: Optional[bytes]) -> Optional[str]:
    if body is None:
        return None
    if len(body) == 0:
        return ""
    truncated = body[:MAX_BODY_BYTES]
    try:
        return truncated.decode("utf-8", errors="replace")
    except Exception:
        return f"<binary {len(body)} bytes>"
