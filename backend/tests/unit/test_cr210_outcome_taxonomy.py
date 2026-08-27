"""CR210 — the capability gate and the five outcomes a constrained call can have.

Structured output is config-gated per provider, and only the on-prem vLLM enforces
it. Without a recorded outcome, "the PM verdict parsed" means two different things
depending on who answered: a decoder guarantee on vLLM, and CR143's tolerant parser
doing the work everywhere else. That is the shape that shipped dark twice already
(DEF038, DEF063), so each state gets its own value and its own severity.

    NULL          no grammar was REQUESTED           — no log
    enforced      on the wire, stream ended normally — no log
    truncated     on the wire, max_tokens ended it   — WARNING (llm_call_length_stop)
    rejected      the server refused the grammar     — ERROR   (llm_constraint_rejected)
    unsupported   requested, provider cannot enforce — WARNING (llm_constraint_unsupported)

NULL vs 'unsupported' is the distinction the column exists for and is asserted
below: one says nobody asked, the other says we asked and ran unguarded anyway.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from uuid import uuid4

import pytest
import structlog
from sqlalchemy import select

from app.db.models import LLMAuditRow
from app.db.session import get_session
from app.services.llm_gateway import (
    ChatMessage,
    LLMGateway,
    LLMProvider,
    OpenAICompatibleProvider,
    OutputConstraint,
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"recommended": {"type": "number", "enum": [1.5, 3.0, 4.5]}},
    "required": ["recommended"],
    "additionalProperties": False,
}
LADDER = OutputConstraint(name="risk_ladder", json_schema=SCHEMA)


class _FakeSSEResponse:
    def __init__(self, lines: list[str]):
        self.status_code = 200
        self._lines = lines

    async def aiter_lines(self) -> AsyncIterator[str]:
        for line in self._lines:
            yield line

    async def aread(self) -> bytes:
        return b""


class _FakeClient:
    def __init__(self, lines: list[str], captured: dict | None = None):
        self._lines = lines
        self._captured = captured if captured is not None else {}

    @asynccontextmanager
    async def stream(self, method: str, url: str, json: dict):
        self._captured["json"] = json
        yield _FakeSSEResponse(self._lines)

    async def aclose(self) -> None:
        pass


CLEAN = [
    'data: {"choices":[{"delta":{"content":"{\\"recommended\\": 1.5}"}}]}',
    'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}',
    "data: [DONE]",
]
STARVED = [
    'data: {"choices":[{"delta":{"content":"{\\"recomm"}}]}',
    'data: {"choices":[{"delta":{},"finish_reason":"length"}]}',
    "data: [DONE]",
]
REFUSED = [
    'data: {"error": {"message": "Grammar error: Invalid type: obDJECT", '
    '"type": "BadRequestError", "code": 400}}',
    "data: [DONE]",
]


def _vllm_gateway(lines: list[str], captured: dict | None = None) -> LLMGateway:
    gw = LLMGateway()
    p = OpenAICompatibleProvider(
        name="vllm", base_url="http://lan:8000", model_name="ami-llm",
        supported_constraints=frozenset({"json_schema", "regex"}),
    )
    p._client = _FakeClient(lines, captured)  # type: ignore[assignment]
    gw._providers["vllm"] = p  # type: ignore[attr-defined]
    return gw


async def _run(gw: LLMGateway, constraint, user_id, meta=None):
    async for _ in gw.stream_chat(
        system_prompt="sys", messages=[ChatMessage(role="user", content="hi")],
        audit_user_id=user_id, audit_agent_id="risk_officer",
        audit_flow="room_risk_officer", meta=meta, constraint=constraint,
    ):
        pass


def _row(user_id) -> LLMAuditRow:
    with get_session() as s:
        return s.execute(
            select(LLMAuditRow).where(LLMAuditRow.user_id == user_id)
        ).scalar_one()


# ── the five states ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_not_requested_records_null_not_unsupported():
    """The CR040 distinction the whole column exists for. Every pre-CR210 row and
    every unconstrained flow is NULL; collapsing it into 'unsupported' would
    claim we asked for a guarantee on calls where we never did."""
    uid = uuid4()
    meta: dict[str, Any] = {}
    with structlog.testing.capture_logs() as logs:
        await _run(_vllm_gateway(CLEAN), None, uid, meta)

    assert _row(uid).constraint_status is None
    assert "constraint" not in meta
    assert not [r for r in logs if r["event"].startswith("llm_constraint_")]


@pytest.mark.asyncio
async def test_enforced_is_recorded_and_says_nothing():
    """No log on the clean path — llm_audit already carries one row per call, and
    a per-call INFO would double the Room's log volume to say nothing happened."""
    uid = uuid4()
    meta: dict[str, Any] = {}
    with structlog.testing.capture_logs() as logs:
        await _run(_vllm_gateway(CLEAN), LADDER, uid, meta)

    assert _row(uid).constraint_status == "enforced"
    assert meta["constraint"] == {
        "name": "risk_ladder", "kind": "json_schema",
        "provider": "vllm", "status": "enforced",
    }
    assert not [r for r in logs if r["event"].startswith("llm_constraint_")]


@pytest.mark.asyncio
async def test_a_constrained_call_that_hits_the_ceiling_is_truncated_not_success():
    """The grammar guaranteed a shape the budget then made unreachable, so the
    reply is unparseable rather than merely short. Reported through the EXISTING
    length-stop event with added fields, not a sibling event — it is the same
    physical event, and two names for one makes "how often do we truncate" a
    two-query question with one of the two forgotten."""
    uid = uuid4()
    with structlog.testing.capture_logs() as logs:
        await _run(_vllm_gateway(STARVED), LADDER, uid)

    assert _row(uid).constraint_status == "truncated"
    stops = [r for r in logs if r["event"] == "llm_call_length_stop"]
    assert len(stops) == 1
    assert stops[0]["constrained"] is True
    assert stops[0]["constraint"] == "risk_ladder"


@pytest.mark.asyncio
async def test_an_unconstrained_length_stop_still_reports_itself_as_unconstrained():
    """Anti-vacuity for the fields above: they must discriminate, not decorate."""
    uid = uuid4()
    with structlog.testing.capture_logs() as logs:
        await _run(_vllm_gateway(STARVED), None, uid)

    assert _row(uid).constraint_status is None
    stops = [r for r in logs if r["event"] == "llm_call_length_stop"]
    assert len(stops) == 1
    assert stops[0]["constrained"] is False
    assert stops[0]["constraint"] is None


@pytest.mark.asyncio
async def test_a_refused_grammar_is_an_error_not_a_runtime_condition():
    """ERROR, because a human must change code: the server will not compile the
    schema we shipped, so every call on that surface returns nothing until the
    schema is edited. Detected from DEF376's `stream_error` plus the fact that a
    grammar was on the wire — never by string-matching "Grammar error:", which
    would be a contract with a log line rather than a contract."""
    uid = uuid4()
    with structlog.testing.capture_logs() as logs:
        await _run(_vllm_gateway(REFUSED), LADDER, uid)

    assert _row(uid).constraint_status == "rejected"
    errs = [r for r in logs if r["event"] == "llm_constraint_rejected"]
    assert len(errs) == 1
    assert errs[0]["log_level"] == "error"
    assert errs[0]["constraint"] == "risk_ladder"
    assert "Grammar error" in errs[0]["error"]
    # DEF376 still records the transport fact on the same row.
    assert "Grammar error" in (_row(uid).error or "")


# ── the capability gate ───────────────────────────────────────────────────


class _RecordingProvider(LLMProvider):
    """Declares no capability, and remembers what it was actually handed."""

    name = "mock"

    def __init__(self) -> None:
        self.seen: list[Any] = []

    async def stream_chat(self, *, system_prompt, messages, model_tier="cheap",
                          max_tokens=1024, meta=None, constraint=None):
        self.seen.append(constraint)
        yield "prose, obviously"


@pytest.mark.asyncio
async def test_a_provider_that_cannot_enforce_is_never_sent_the_grammar():
    """It is not enough to record the failure: the field must not go out. A
    server that accepts and ignores it returns HTTP 200 with a prose answer,
    which is indistinguishable from enforcement at every layer above — the
    `guided_json` failure, verified live."""
    gw = LLMGateway()
    provider = _RecordingProvider()
    gw._providers["mock"] = provider  # type: ignore[attr-defined]

    uid = uuid4()
    meta: dict[str, Any] = {}
    with structlog.testing.capture_logs() as logs:
        await _run(gw, LADDER, uid, meta)

    assert provider.seen == [None]
    assert _row(uid).constraint_status == "unsupported"
    assert meta["constraint"]["status"] == "unsupported"
    assert meta["constraint"]["provider"] == "mock"

    warns = [r for r in logs if r["event"] == "llm_constraint_unsupported"]
    assert len(warns) == 1
    assert warns[0]["log_level"] == "warning"
    assert warns[0]["provider"] == "mock"
    assert warns[0]["constraint"] == "risk_ladder"
    # The operational point, said in the log rather than left to be inferred.
    assert "UNCONSTRAINED" in warns[0]["detail"]


@pytest.mark.asyncio
async def test_a_regex_on_a_json_only_provider_is_unsupported():
    """Capability is per KIND, not per provider. An endpoint that honours
    `response_format` says nothing about `structured_outputs.regex`, which is a
    vLLM extension."""
    gw = LLMGateway()
    p = OpenAICompatibleProvider(
        name="vllm", base_url="http://lan:8000", model_name="ami-llm",
        supported_constraints=frozenset({"json_schema"}),
    )
    captured: dict = {}
    p._client = _FakeClient(CLEAN, captured)  # type: ignore[assignment]
    gw._providers["vllm"] = p  # type: ignore[attr-defined]

    uid = uuid4()
    await _run(gw, OutputConstraint(name="trader_block", regex=r"Side: +BUY\n"), uid)

    assert _row(uid).constraint_status == "unsupported"
    assert "structured_outputs" not in captured["json"]
