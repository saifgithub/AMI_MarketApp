"""CR200-R002 — Room LLM call viewer: joins a Room run to its captured
`llm_audit` rows so an operator can see the exact request (system prompt +
message list) and response text each of the 12 agents received/sent.

`llm_audit` (`LLMAuditRow`) already captures every gateway call's full
`system_prompt`/`messages`/`response_text` (`record_llm_call`,
`app/services/audit.py`) — this module adds no new capture, only a read
path. There is no `room_run_id` FK on `llm_audit`: a run's calls are found
by `(user_id, created_at ∈ [triggered_at, finished_at])`, since a user has
at most one Room running at a time (`room_runner._find_active_run`). A run
with no `finished_at` (still running, or a crash left it stuck) windows to
"now" instead of silently returning nothing — CR040 degrade-loudly, same
discipline `ticker_interest.py` and `admin_analytics.py` already follow.

`admin_prompt_replay` rows (an operator's edited resend, see
`api/admin_room.py`) are excluded from a run's own call list — a replay is
a sandbox call the operator made later, not a turn the Room actually took,
and showing it inline would misrepresent what the run itself did.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.db.models import LLMAuditRow, RoomRunRow

# Small grace window past `finished_at` — the terminal PM call's
# `record_llm_call` write can land a beat after the run row's own
# `finished_at` timestamp is set (the audit write happens inside
# `stream_chat`, after the caller has already moved on to persist the run).
_WINDOW_GRACE = timedelta(seconds=30)

REPLAY_FLOW = "admin_prompt_replay"


def _serialize(row: LLMAuditRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "created_at": row.created_at,
        "agent_id": row.agent_id,
        "flow": row.flow,
        "tier": row.tier,
        "provider": row.provider,
        "locale": row.locale,
        "system_prompt": row.system_prompt,
        "messages": row.messages,
        "response_text": row.response_text,
        "latency_ms": row.latency_ms,
        "error": row.error,
        "input_tokens": row.input_tokens,
        "output_tokens": row.output_tokens,
        "cache_read_tokens": row.cache_read_tokens,
        "cache_write_tokens": row.cache_write_tokens,
        "prompt_version": row.prompt_version,
        "constraint_status": row.constraint_status,
    }


def list_calls_for_run(
    *, s, user_id: UUID, triggered_at: datetime, finished_at: datetime | None,
) -> dict[str, Any]:
    """The LLM calls that fall inside one Room run's time window.

    Returns `{"calls": [...], "window_open": bool}` — `window_open` is True
    when `finished_at` was None and the window was capped at "now" instead
    (an in-progress or stuck run), so the caller can say so rather than
    imply the list is final.
    """
    window_open = finished_at is None
    end = (finished_at or datetime.now(timezone.utc)) + _WINDOW_GRACE
    rows = s.execute(
        select(LLMAuditRow)
        .where(
            LLMAuditRow.user_id == user_id,
            LLMAuditRow.created_at >= triggered_at,
            LLMAuditRow.created_at <= end,
            LLMAuditRow.flow != REPLAY_FLOW,
        )
        .order_by(LLMAuditRow.created_at.asc())
    ).scalars().all()
    return {
        "calls": [_serialize(r) for r in rows],
        "window_open": window_open,
    }


def get_call(*, s, call_id: UUID) -> LLMAuditRow | None:
    return s.execute(
        select(LLMAuditRow).where(LLMAuditRow.id == call_id)
    ).scalar_one_or_none()


def find_replay_row(
    *, s, agent_id: str | None, since: datetime,
) -> LLMAuditRow | None:
    """Best-effort lookup of the `llm_audit` row `record_llm_call` just wrote
    for a resend (`api/admin_room.py`'s `resend_call`). `stream_chat()`
    writes that row itself, inside the gateway call, and hands back no id —
    it is a fire-and-forget audit write by design (never allowed to fail the
    request it's auditing). This re-queries for the newest
    `admin_prompt_replay` row for the same agent created at/after the call
    started, which is unambiguous for this tool's own (low, operator-driven)
    concurrency. Returns None rather than guessing when nothing matches —
    the caller must never report a wrong id as the right one (CR040)."""
    return s.execute(
        select(LLMAuditRow)
        .where(
            LLMAuditRow.flow == REPLAY_FLOW,
            LLMAuditRow.agent_id == agent_id,
            LLMAuditRow.created_at >= since,
        )
        .order_by(LLMAuditRow.created_at.desc())
        .limit(1)
    ).scalars().first()


def list_recent_runs(
    *,
    s,
    ticker: str | None = None,
    user_id: UUID | None = None,
    days: int = 7,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Recent Room runs for the operator to pick from. Deliberately not
    filtered to "real users" (unlike `ticker_interest.py`'s analytics) —
    an operator debugging a prompt needs their own test/synthetic runs to
    be findable just as much as a real user's.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    q = select(RoomRunRow).where(RoomRunRow.triggered_at >= since)
    if ticker:
        q = q.where(RoomRunRow.ticker == ticker.upper())
    if user_id:
        q = q.where(RoomRunRow.user_id == user_id)
    rows = s.execute(
        q.order_by(RoomRunRow.triggered_at.desc()).limit(limit)
    ).scalars().all()
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "ticker": r.ticker,
            "status": r.status,
            "triggered_at": r.triggered_at,
            "finished_at": r.finished_at,
            "credit_cost": r.credit_cost,
            "model_tier": r.model_tier,
        }
        for r in rows
    ]
