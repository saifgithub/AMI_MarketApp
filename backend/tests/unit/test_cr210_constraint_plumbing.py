"""CR210 — the per-call decoding-grammar channel, from `OutputConstraint` to the wire.

The taxonomy and the capability gate live in `test_cr210_outcome_taxonomy.py`;
this file is only about the type and the request body.

Why the request body is pinned BY KEY NAME: `ChatCompletionRequest` on the live
server declares `additionalProperties: true`, so a field it does not implement is
accepted with HTTP 200 and silently ignored. `guided_json` was verified doing
exactly that on 2026-08-25 — dropped, and the model answered in prose. There is
therefore no error to catch and no status code to check: a rename, a wrong nesting
level, or a stale spelling would ship a grammar that never takes effect while every
layer above reads the reply as enforced. Only a test that names the key catches it,
which is the same reason `test_config_compose_parity` pins `ADANOS_API_KEY`.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import pytest

from app.services.llm_gateway import (
    ChatMessage,
    OutputConstraint,
    OpenAICompatibleProvider,
    VLLMProvider,
    _constraint_request_fields,
)

LADDER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"recommended": {"type": "number", "enum": [1.5, 3.0, 4.5]}},
    "required": ["recommended"],
    "additionalProperties": False,
}
MONEY_REGEX = r"Side: +(?:BUY|HOLD|WAIT)\n"

# Every spelling that this server accepts-and-ignores, or that an older vLLM
# honoured. None of them may ever appear in an outbound body.
FORBIDDEN_KEYS = ("guided_json", "guided_regex", "guided_choice", "guided_grammar")


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
    def __init__(self, captured: dict):
        self._captured = captured

    @asynccontextmanager
    async def stream(self, method: str, url: str, json: dict):
        self._captured["json"] = json
        yield _FakeSSEResponse(['data: {"choices":[{"delta":{"content":"x"}}]}',
                                "data: [DONE]"])

    async def aclose(self) -> None:
        pass


async def _body(provider, constraint) -> dict:
    captured: dict = {}
    provider._client = _FakeClient(captured)  # type: ignore[assignment]
    async for _ in provider.stream_chat(
        system_prompt="sys",
        messages=[ChatMessage(role="user", content="hi")],
        max_tokens=64,
        constraint=constraint,
    ):
        pass
    return captured["json"]


# ── the type ──────────────────────────────────────────────────────────────


def test_exactly_one_grammar_is_required():
    with pytest.raises(ValueError, match="exactly one"):
        OutputConstraint(name="x")
    with pytest.raises(ValueError, match="exactly one"):
        OutputConstraint(name="x", json_schema=LADDER_SCHEMA, regex=MONEY_REGEX)


def test_a_constraint_must_be_named():
    """The name is the audit label. An unnamed grammar makes every log line and
    the `constraint_status` column unable to say WHICH grammar was in force."""
    with pytest.raises(ValueError, match="audit label"):
        OutputConstraint(name="", json_schema=LADDER_SCHEMA)


def test_kind_reports_the_grammar_that_was_given():
    assert OutputConstraint(name="a", json_schema=LADDER_SCHEMA).kind == "json_schema"
    assert OutputConstraint(name="b", regex=MONEY_REGEX).kind == "regex"


# ── the field mapping ─────────────────────────────────────────────────────


def test_json_maps_to_the_openai_standard_response_format():
    fields = _constraint_request_fields(
        OutputConstraint(name="risk_ladder", json_schema=LADDER_SCHEMA)
    )
    assert set(fields) == {"response_format"}
    rf = fields["response_format"]
    assert rf["type"] == "json_schema"
    assert rf["json_schema"]["name"] == "risk_ladder"
    assert rf["json_schema"]["schema"] is LADDER_SCHEMA
    assert rf["json_schema"]["strict"] is True


def test_regex_maps_to_structured_outputs():
    """`structured_outputs.regex` is a first-class field on this build (verified
    from its own /openapi.json, 2026-08-25). It has no OpenAI-standard
    equivalent, which is why the regex path is vLLM-only."""
    fields = _constraint_request_fields(
        OutputConstraint(name="trader_block", regex=MONEY_REGEX)
    )
    assert fields == {"structured_outputs": {"regex": MONEY_REGEX}}


@pytest.mark.parametrize("constraint", [
    OutputConstraint(name="a", json_schema=LADDER_SCHEMA),
    OutputConstraint(name="b", regex=MONEY_REGEX),
])
def test_no_silently_ignored_spelling_is_ever_emitted(constraint):
    """The load-bearing one. These keys do not exist on this server's request
    model, and `additionalProperties: true` means sending one is a no-op that
    reports success."""
    fields = _constraint_request_fields(constraint)
    for key in FORBIDDEN_KEYS:
        assert key not in fields
    # Nor nested one level down, where a plausible-looking mistake would hide.
    for value in fields.values():
        if isinstance(value, dict):
            for key in FORBIDDEN_KEYS:
                assert key not in value


# ── the wire ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_constraint_reaches_the_request_body_undisturbed():
    p = VLLMProvider(base_url="http://lan:8000", model_name="ami-llm")
    body = await _body(p, OutputConstraint(name="pm_verdict", json_schema=LADDER_SCHEMA))

    assert body["response_format"]["json_schema"]["name"] == "pm_verdict"
    # CR141/DEF125 machinery must survive alongside it.
    assert body["model"] == "ami-llm"
    assert body["stream"] is True
    assert body["stream_options"] == {"include_usage": True}
    assert body["max_tokens"] == 64
    assert body["messages"][0]["role"] == "system"
    for key in FORBIDDEN_KEYS:
        assert key not in body


@pytest.mark.asyncio
async def test_an_unconstrained_call_sends_no_grammar_field_at_all():
    """Anti-vacuity for the pin above: absent, not present-and-empty. A
    `response_format: null` would be a field the server has to interpret."""
    p = VLLMProvider(base_url="http://lan:8000", model_name="ami-llm")
    body = await _body(p, None)
    assert "response_format" not in body
    assert "structured_outputs" not in body


@pytest.mark.asyncio
async def test_a_per_call_constraint_wins_over_a_provider_level_extra_body():
    """The spread-ordering pin.

    `extra_body` is a constructor-time, per-PROVIDER dict merged with
    `**self._extra_body`. If the constraint were applied BEFORE that spread, a
    provider configured with a `response_format` of its own would silence every
    schema on that provider — with no error anywhere, which is this CR's own
    failure mode turned inward. Ordering is behaviour, so it gets a test.
    """
    p = OpenAICompatibleProvider(
        name="vllm", base_url="http://lan:8000", model_name="ami-llm",
        extra_body={"response_format": {"type": "text"}, "enable_thinking": False},
        supported_constraints=frozenset({"json_schema"}),
    )
    body = await _body(p, OutputConstraint(name="pm_verdict", json_schema=LADDER_SCHEMA))

    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["name"] == "pm_verdict"
    # …and the unrelated provider quirk is untouched.
    assert body["enable_thinking"] is False


# ── capability declarations ───────────────────────────────────────────────


def test_only_vllm_declares_it_can_enforce():
    """A claim about a SERVER. Every other endpoint defaults to the empty set,
    so a provider added later is unconstrained until someone verifies it —
    failing closed rather than assuming an OpenAI-compatible URL implies
    OpenAI-compatible enforcement."""
    assert VLLMProvider(
        base_url="http://lan:8000", model_name="ami-llm"
    ).supported_constraints == frozenset({"json_schema", "regex"})

    for name in ("kimi", "deepseek", "qwen", "gemini"):
        p = OpenAICompatibleProvider(
            name=name, base_url="http://x", model_name="m",
        )
        assert p.supported_constraints == frozenset(), name
