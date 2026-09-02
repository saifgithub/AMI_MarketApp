"""DEF376 — an in-band SSE error frame must be an error, not a silent empty answer.

Both streaming providers answer a REFUSED request with HTTP 200 and a single SSE
frame carrying an `error` object, then `[DONE]`. Neither loop had a branch for it:

  - `OpenAICompatibleProvider` reaches `choices = obj.get("choices") or []` /
    `if not choices: continue` — an error frame has no `choices`, so it was
    skipped in silence.
  - `AnthropicProvider` branches on `obj.get("type")`, and `{"type": "error"}`
    matched no branch, so it fell through to the same silence.

Net effect before the fix: nothing yielded, `meta["finish_reason"]` never written,
and `record_llm_call` handed `response_text=None, error=None` — a refusal recorded
as a clean answer the model had nothing to add to. In the Room that reaches
`_parse_pm_verdict` as an empty string and fails safe to PASS with nothing anywhere
to grep for, which is the CR040 shape (DEF038 / DEF063) one layer below where the
guards were looking.

Reproduced live 2026-08-25 against `ami-llm` (vLLM 0.23.1.dev0+g0fc695fc6) by
sending a malformed decoding grammar:

    data: {"error": {"message": "Grammar error: Invalid type: obDJECT",
                     "type": "BadRequestError", "param": null, "code": 400}}
    data: [DONE]

The same request NON-streamed returns a real HTTP 400 — so the existing
`resp.status_code != 200` guard can never fire on the path we actually use.

The four call-site tests at the bottom are the other half of the fix: the sentinel
this yields is NON-empty, so every `"".join(chunks).strip() or <fallback>` idiom in
`room_runner` would take the truthy branch and put transport wreckage where the
designed fallback belongs.
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
from app.schemas.room import VerdictAction
from app.services.coach_engine import hydrate_coach_mandate
from app.services.llm_gateway import (
    AnthropicProvider,
    ChatMessage,
    LLMGateway,
    OpenAICompatibleProvider,
)
from app.services.room_runner import RoomRunner

from tests.unit.test_room_runner import _FakeGateway, _collect


# ── SSE fakes (same shape as test_llm_gateway.py / test_cr141_usage_capture.py) ──


class _FakeSSEResponse:
    def __init__(self, status_code: int, lines: list[str], body: bytes = b""):
        self.status_code = status_code
        self._lines = lines
        self._body = body

    async def aiter_lines(self) -> AsyncIterator[str]:
        for line in self._lines:
            yield line

    async def aread(self) -> bytes:
        return self._body


class _FakeClient:
    def __init__(self, resp: _FakeSSEResponse):
        self._resp = resp

    @asynccontextmanager
    async def stream(self, method: str, url: str, json: dict):
        yield self._resp

    async def aclose(self) -> None:
        pass


def _sse(payload: str) -> str:
    return f"data: {payload}"


GRAMMAR_ERROR_FRAME = _sse(
    '{"error": {"message": "Grammar error: Invalid type: obDJECT", '
    '"type": "BadRequestError", "param": null, "code": 400}}'
)


async def _drain(provider, meta: dict[str, Any] | None = None) -> str:
    chunks: list[str] = []
    async for c in provider.stream_chat(
        system_prompt="x",
        messages=[ChatMessage(role="user", content="ping")],
        meta=meta,
    ):
        chunks.append(c)
    return "".join(chunks)


# ── the OpenAI-compatible half (vLLM, kimi, deepseek, qwen, gemini) ───────


@pytest.mark.asyncio
async def test_openai_compat_in_band_error_frame_is_loud():
    """The five properties that together make the refusal impossible to miss.

    Reverting the DEF376 block in `OpenAICompatibleProvider.stream_chat` fails
    every one of them — the pre-fix behaviour is `text == ""`, `meta == {}`, and
    no log record at all.
    """
    p = OpenAICompatibleProvider(
        name="vllm", base_url="http://lan:8000", model_name="ami-llm"
    )
    p._client = _FakeClient(  # type: ignore[assignment]
        _FakeSSEResponse(200, [GRAMMAR_ERROR_FRAME, "data: [DONE]"])
    )

    meta: dict[str, Any] = {}
    with structlog.testing.capture_logs() as logs:
        text = await _drain(p, meta)

    # 1. the caller gets a sentinel, not silence
    assert "[AMI error:" in text
    assert "vllm" in text
    # 2. the machine channel carries the server's own reason
    assert "Grammar error: Invalid type: obDJECT" in meta["stream_error"]
    # 3. DEF125's channel is untouched — the MODEL never ran, so there is no
    #    stop reason. Four call sites test this with `== "length"`.
    assert "finish_reason" not in meta
    # 4. it is an ERROR, not a warning: a refused request is a code defect
    errs = [r for r in logs if r["event"] == "vllm_stream_error"]
    assert len(errs) == 1
    assert errs[0]["log_level"] == "error"
    assert "Grammar error" in errs[0]["error"]
    # 5. no usage was invented from a frame that carried none
    assert "usage" not in meta


@pytest.mark.asyncio
async def test_openai_compat_error_frame_stops_the_stream():
    """Content queued behind the error frame is not delivered — a refusal is
    terminal, and half an answer is worse than none."""
    p = OpenAICompatibleProvider(
        name="vllm", base_url="http://lan:8000", model_name="ami-llm"
    )
    p._client = _FakeClient(  # type: ignore[assignment]
        _FakeSSEResponse(200, [
            _sse('{"choices":[{"index":0,"delta":{"content":"PO"}}]}'),
            GRAMMAR_ERROR_FRAME,
            _sse('{"choices":[{"index":0,"delta":{"content":"NG"}}]}'),
            "data: [DONE]",
        ])
    )
    meta: dict[str, Any] = {}
    text = await _drain(p, meta)
    assert text.startswith("PO")
    assert "NG" not in text
    assert "stream_error" in meta


@pytest.mark.asyncio
async def test_openai_compat_string_form_error_is_handled():
    """Not every endpoint nests the message: `{"error": "rate_limited"}` is a
    shape in the wild, and `.get("message")` on a str would raise."""
    p = OpenAICompatibleProvider(
        name="kimi", base_url="https://api.kimi.com", model_name="k2"
    )
    p._client = _FakeClient(  # type: ignore[assignment]
        _FakeSSEResponse(200, [_sse('{"error": "rate_limited"}'), "data: [DONE]"])
    )
    meta: dict[str, Any] = {}
    text = await _drain(p, meta)
    assert "[AMI error:" in text
    assert meta["stream_error"] == "rate_limited"


@pytest.mark.asyncio
async def test_a_normal_stream_is_untouched_by_the_error_check():
    """Anti-vacuity: the guard must fire on a refusal and on NOTHING else. The
    terminal usage frame also has empty `choices`, and mistaking it for an error
    would break every call rather than none."""
    p = OpenAICompatibleProvider(
        name="vllm", base_url="http://lan:8000", model_name="ami-llm"
    )
    p._client = _FakeClient(  # type: ignore[assignment]
        _FakeSSEResponse(200, [
            _sse('{"choices":[{"index":0,"delta":{"content":"PO"}}]}'),
            _sse('{"choices":[{"index":0,"delta":{"content":"NG"}}]}'),
            _sse('{"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}'),
            _sse('{"choices":[],"usage":{"prompt_tokens":9,"completion_tokens":2}}'),
            "data: [DONE]",
        ])
    )
    meta: dict[str, Any] = {}
    with structlog.testing.capture_logs() as logs:
        text = await _drain(p, meta)

    assert text == "PONG"
    assert "stream_error" not in meta
    assert meta["finish_reason"] == "stop"
    assert meta["usage"]["input_tokens"] == 9
    assert not [r for r in logs if r["event"].endswith("_stream_error")]


# ── the Anthropic mirror ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_anthropic_in_band_error_frame_is_loud():
    """Fixing one provider and not the other would leave the defect half-open:
    the statement is "in-band error frames are swallowed", not "vLLM's are"."""
    p = AnthropicProvider(api_key="sk-ant-fake")
    p._client = _FakeClient(  # type: ignore[assignment]
        _FakeSSEResponse(200, [
            _sse('{"type":"message_start"}'),
            _sse('{"type":"error","error":{"type":"overloaded_error",'
                 '"message":"Overloaded"}}'),
            _sse('{"type":"content_block_delta","delta":'
                 '{"type":"text_delta","text":"never"}}'),
            "data: [DONE]",
        ])
    )
    meta: dict[str, Any] = {}
    with structlog.testing.capture_logs() as logs:
        text = await _drain(p, meta)

    assert "[AMI error:" in text
    assert "never" not in text
    assert meta["stream_error"] == "Overloaded"
    assert "finish_reason" not in meta
    errs = [r for r in logs if r["event"] == "anthropic_stream_error"]
    assert len(errs) == 1 and errs[0]["log_level"] == "error"


# ── the audit row ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gateway_records_the_refusal_as_an_error():
    """The durable half. Before DEF376 this row read `error=NULL` with an empty
    response — indistinguishable from a model that answered with nothing, which
    is what made the failure survivable for as long as it did."""
    gw = LLMGateway()
    provider = OpenAICompatibleProvider(
        name="vllm", base_url="http://lan:8000", model_name="ami-llm"
    )
    provider._client = _FakeClient(  # type: ignore[assignment]
        _FakeSSEResponse(200, [GRAMMAR_ERROR_FRAME, "data: [DONE]"])
    )
    gw._providers["vllm"] = provider  # type: ignore[attr-defined]

    user_id = uuid4()
    async for _ in gw.stream_chat(
        system_prompt="sys", messages=[ChatMessage(role="user", content="hi")],
        model_tier="cheap", locale="en",
        audit_user_id=user_id, audit_agent_id="portfolio_manager",
        audit_flow="room_pm",
    ):
        pass

    with get_session() as s:
        row = s.execute(
            select(LLMAuditRow).where(LLMAuditRow.user_id == user_id)
        ).scalar_one()
        assert row.error is not None
        assert "Grammar error" in row.error
        assert row.error.startswith("stream_error:")


@pytest.mark.asyncio
async def test_a_real_exception_keeps_priority_over_the_stream_error():
    """`error_str` is only filled in from `stream_error` when the call did not
    already raise — a genuine exception is the more specific fact."""
    gw = LLMGateway()

    class _RaisesAfterErrorFrame(OpenAICompatibleProvider):
        async def stream_chat(self, **kw):  # type: ignore[override]
            meta = kw.get("meta")
            if meta is not None:
                meta["stream_error"] = "in-band thing"
            raise RuntimeError("connect refused")
            yield ""  # pragma: no cover — makes this an async generator

    gw._providers["vllm"] = _RaisesAfterErrorFrame(  # type: ignore[attr-defined]
        name="vllm", base_url="http://lan:8000", model_name="ami-llm"
    )

    user_id = uuid4()
    with pytest.raises(RuntimeError):
        async for _ in gw.stream_chat(
            system_prompt="sys", messages=[ChatMessage(role="user", content="hi")],
            audit_user_id=user_id, audit_flow="room_pm",
        ):
            pass

    with get_session() as s:
        row = s.execute(
            select(LLMAuditRow).where(LLMAuditRow.user_id == user_id)
        ).scalar_one()
        assert row.error is not None
        assert "connect refused" in row.error
        assert not row.error.startswith("stream_error:")


# ── the call sites: the sentinel must never reach a user or a parser ──────


class _RefusingGateway(_FakeGateway):
    """Every call is refused mid-stream, exactly as the provider now reports it:
    `meta["stream_error"]` set and the `[AMI error: …]` sentinel yielded."""

    async def stream_chat(self, *, system_prompt, messages, model_tier,
                          locale="en", max_tokens=1024, **_audit):
        meta = _audit.get("meta")
        if meta is not None:
            meta["stream_error"] = "Grammar error: Invalid type: obDJECT"
        yield (
            "\n\n[AMI error: the upstream provider (vllm) refused this request "
            "mid-stream. Check backend logs.]"
        )


def test_a_refused_run_never_shows_the_sentinel_and_fails_safe_to_pass():
    """The whole point of the call-site half. The sentinel is non-empty, so
    every `or <fallback>` idiom in room_runner would otherwise take the truthy
    branch — putting transport wreckage into the transcript that eleven agents
    and the user both read, and handing `_parse_pm_verdict` a string to find a
    decision in."""
    runner = RoomRunner(llm=_RefusingGateway())  # type: ignore[arg-type]
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    events = _collect(runner.run(
        user_id=uuid4(), ticker="AAPL", mandate=mandate,
        char_delay_min=0.0, char_delay_max=0.0,
    ))

    # No user-visible surface carries the sentinel.
    for e in events:
        assert "[AMI error:" not in (getattr(e, "text", None) or "")

    # And the decision fails safe, never a fabricated APPROVE (DEF059).
    # CR219 R51 (2026-09-03) moved the fail-safe target: a run where every
    # desk fell back to scripted turns now DISCARDS the decision — an explicit
    # NO_VERDICT with the outage disclosed — instead of dressing up as a
    # confident PASS. Same direction (no trade), more honest shape; the
    # sentinel half of this test is unchanged.
    v = next(e.verdict for e in events if e.kind == "verdict")
    assert v.action == VerdictAction.NO_VERDICT.value
    assert v.overridden_from_llm is True
    assert v.scripted_turns == 11 and len(v.scripted_agents) == 11
    assert v.size_pct is None and v.entry is None and v.stop is None
