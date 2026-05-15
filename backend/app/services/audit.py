"""Audit-logging write helpers + nightly retention trim.

AT:R16 — comprehensive alpha-era logging. Every write here is best-effort:
any exception in audit code MUST NOT break the request that triggered it.
Wrap callers in try/except logging.exception and continue.

Retention: 90-day rolling window on all three audit tables. The nightly
`trim_audit_tables()` is called from the lifespan background task in main.py.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import delete, update

from app.core.logging import logger
from app.db.models import HTTPAuditRow, LLMAuditRow, OneOnOneMessageRow, RoomRunRow
from app.db.session import get_session

AUDIT_RETENTION_DAYS = 90


def trim_audit_tables(days: int = AUDIT_RETENTION_DAYS) -> dict[str, int]:
    """Delete rows older than `days` from all three audit tables.

    Returns a dict of {table: rows_deleted} for logging. Raises on DB errors
    (caller decides whether to swallow).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    counts: dict[str, int] = {}
    with get_session() as s:
        for model, label in (
            (LLMAuditRow, "llm_audit"),
            (HTTPAuditRow, "http_audit"),
            (OneOnOneMessageRow, "one_on_one_messages"),
        ):
            result = s.execute(
                delete(model).where(model.created_at < cutoff)
            )
            counts[label] = result.rowcount

        # Mark room_runs rows stuck in 'running' for > 30 min as aborted.
        # These arise when the api-alpha container restarts mid-run; the
        # runner is killed but the DB row never transitions out of 'running'.
        stale_room_cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
        result = s.execute(
            update(RoomRunRow)
            .where(RoomRunRow.status == "running")
            .where(RoomRunRow.triggered_at < stale_room_cutoff)
            .values(status="aborted")
        )
        counts["room_runs_aborted"] = result.rowcount

        s.commit()
    return counts


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
