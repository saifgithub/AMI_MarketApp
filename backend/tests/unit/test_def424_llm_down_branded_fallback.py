"""DEF424 (E5-D1) — LLM-down degradation leaks a raw transport error on Brief
Your Agent and on any non-Concierge 1-on-1 agent.

Found running CR004's A3 drill 1 (LLM down) against live Alpha
(`alpha-2026-09-25-4`) with `VLLM_BASE_URL` pointed at a dead port: a Brief
`POST /v1/brief/message` turn streamed `event: error` / `data: All connection
attempts failed` verbatim — a raw httpx connection-pool string, not AMI-
branded copy. Root cause: `LLMGateway.stream_chat` picks exactly one provider
per call and re-raises any exception uncaught (no runtime fallback in the
gateway); `BriefEngine.stream_chat` and the non-Concierge branch of
`AgentRunner.stream_one_on_one_message` had no `try`/`except` around their own
`self._llm.stream_chat` call, so the raised exception propagated straight
through the generator to `brief.py` / `one_on_one.py`'s own
`except Exception as e: yield sse_text("error", str(e)[:300])` — the
exception's OWN text, unbranded, on the wire. Only `_stream_concierge`
(RETRO-SECURITY MAJOR-2 round 3) already caught this shape.

These tests drive the REAL `LLMGateway` + a REAL `VLLMProvider` (the
live-preference provider), with only the HTTP transport faked via
`httpx.MockTransport` — the same shape
`test_def113_one_on_one_credit_gate.py`'s round-3 Concierge tests already use,
extended to a non-Concierge agent and to Brief (which had no such coverage at
all).

Acceptance:
  - A ConnectError (fully unreachable host) and an HTTP 503 (reachable host,
    non-200) both yield ONLY branded AMI copy — no raw exception text, no
    `[AMI error: ...]` sentinel leaking to a surface that has its own fallback
    now — and charge 0 net credits (spent then refunded).
  - A genuinely successful reply still bills normally (control — this fix
    must not turn every real reply into a false refund).

DEF424 post-COMPLETE minors (round 1 audit, both MINOR):
  - MINOR-1 — the HTTP-503 in-band sentinel (`[AMI error: HTTP 503 from the
    upstream provider (vllm). Check backend logs.]`) is the SAME outage seen
    from the other side of the pre-existing branch DEF424 deliberately left
    alone. It never raised, so the round-1 fix's try/except never caught it;
    it still leaked the provider name, an HTTP status and an operator
    instruction straight to Brief and 1-on-1. Now routed through the same
    `canned_agent_fallback` branded copy — the two `test_*_http_503_*` tests
    below are UPDATED (not just added-to) from round 1's version, which
    asserted the raw sentinel WAS present as the then-correct control.
  - MINOR-2 — a stream that fails AFTER yielding some real content (`buf`
    non-empty) used to stop silently: `if not buf` correctly avoided
    concatenating branded fallback copy after partial real content, but left
    the user with no signal the reply was cut off or that the turn wasn't
    charged. Now appends one short branded line; refund still fires off the
    same `stream_error` key, unchanged.
"""

from __future__ import annotations

import httpx as _httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.brief import router as brief_router
from app.api.one_on_one import router as one_on_one_router
from app.db import get_session
from app.db.models import SubscriptionEventRow, User
from app.services.auth_service import AuthService
from app.services.credit_service import balance_for
from app.services.llm_gateway import MockProvider
from app.services.rate_limit import (
    agent_stream_concurrency_limit,
    brief_message_rate_limit,
    one_on_one_message_rate_limit,
)


# ── shared fixtures ──────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_limiters():
    brief_message_rate_limit.reset()
    one_on_one_message_rate_limit.reset()
    agent_stream_concurrency_limit.reset()
    yield
    brief_message_rate_limit.reset()
    one_on_one_message_rate_limit.reset()
    agent_stream_concurrency_limit.reset()


def _new_user(plan: str = "trader") -> tuple[str, dict]:
    """A paid-plan user — `trader` unlocks every agent (DEF179's Floor Pass
    gate only applies to `floor_pass`), which matters here because the
    non-Concierge 1-on-1 test needs an agent that ISN'T free-by-default like
    Concierge is."""
    auth = AuthService()
    user, token, _ = auth.ensure_anonymous(device_user_id=None)
    with get_session() as s:
        s.get(User, user.id).plan = plan
    return user.id, {"Authorization": f"Bearer {token}"}


def _ledger(user_id) -> list[SubscriptionEventRow]:
    with get_session() as s:
        return list(s.execute(
            select(SubscriptionEventRow).where(
                SubscriptionEventRow.user_id == user_id
            )
        ).scalars())


def _http_503_handler(request):
    return _httpx.Response(503, text="upstream unavailable")


def _connect_error_handler(request):
    raise _httpx.ConnectError("connection refused", request=request)


def _ok_handler(request):
    body = (
        b'data: {"choices":[{"delta":{"content":"hello from a real reply"}}]}\n\n'
        b'data: [DONE]\n\n'
    )
    return _httpx.Response(
        200, content=body, headers={"content-type": "text/event-stream"},
    )


class _PartialThenDropTransport(_httpx.AsyncBaseTransport):
    """MINOR-2 repro: the provider streams SOME real content, then the
    connection dies mid-response — an `httpx.ReadError` raised out of
    `aiter_lines()` partway through, not a clean non-200 or an immediate
    `ConnectError`. `httpx.MockTransport` can't express "raise partway
    through a stream body" (its handler returns one complete `Response`
    up front), so this is a small custom transport instead.
    """

    async def handle_async_request(self, request):
        async def _body():
            yield b'data: {"choices":[{"delta":{"content":"partial real "}}]}\n\n'
            yield b'data: {"choices":[{"delta":{"content":"content before "}}]}\n\n'
            raise _httpx.ReadError("connection dropped mid-stream", request=request)

        return _httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=_AsyncIterStream(_body()),
        )


class _AsyncIterStream(_httpx.AsyncByteStream):
    def __init__(self, gen):
        self._gen = gen

    async def __aiter__(self):
        async for chunk in self._gen:
            yield chunk

    async def aclose(self) -> None:
        pass


@pytest.fixture
def _real_vllm_gateway(monkeypatch):
    """Register a real VLLMProvider (`vllm > anthropic > kimi > mock`), then
    hand back a function that swaps its transport for either an
    `httpx.MockTransport` driven by a plain handler function, or (MINOR-2's
    partial-then-drop repro, which a single up-front `Response` can't
    express) an already-built `httpx.AsyncBaseTransport` passed straight
    through. Rewires BOTH `agent_runner.get_agent_runner` and
    `brief_engine.get_brief_engine` to the same gateway instance so a single
    fixture covers both surfaces under test.
    """
    from app.core import config as config_mod
    from app.services import agent_runner as agent_runner_mod
    from app.services import brief_engine as brief_engine_mod
    from app.services import llm_gateway as gw_mod

    monkeypatch.setattr(config_mod.settings, "vllm_base_url", "http://fake-vllm:8000")
    monkeypatch.setattr(config_mod.settings, "vllm_model", "test-model")
    monkeypatch.setattr(config_mod.settings, "vllm_api_key", "")

    gateway = gw_mod.LLMGateway()
    assert "vllm" in gateway._providers
    assert gateway._active_provider_name() == "vllm"

    def _wire(handler_or_transport):
        provider = gateway._providers["vllm"]
        transport = (
            handler_or_transport
            if isinstance(handler_or_transport, _httpx.AsyncBaseTransport)
            else _httpx.MockTransport(handler_or_transport)
        )
        provider._client = _httpx.AsyncClient(
            base_url="http://fake-vllm:8000",
            transport=transport,
        )
        return gateway

    monkeypatch.setattr(gw_mod, "_gateway", None)
    monkeypatch.setattr(gw_mod, "get_llm_gateway", lambda: gateway)

    monkeypatch.setattr(agent_runner_mod, "_runner", None)
    monkeypatch.setattr(
        agent_runner_mod, "get_agent_runner",
        lambda: agent_runner_mod.AgentRunner(gateway),
    )

    from app.services.overlay_store import get_overlay_store
    monkeypatch.setattr(brief_engine_mod, "_engine", None)
    monkeypatch.setattr(
        brief_engine_mod, "get_brief_engine",
        lambda: brief_engine_mod.BriefEngine(gateway, get_overlay_store()),
    )

    return _wire


# ── 1-on-1, non-Concierge agent ──────────────────────────────────────────


@pytest.fixture
def one_on_one_client() -> TestClient:
    a = FastAPI()
    a.include_router(one_on_one_router)
    return TestClient(a, raise_server_exceptions=False)


def _open_one_on_one(client: TestClient, headers: dict, agent_id: str) -> str:
    r = client.post(
        "/v1/agents/one_on_one/start",
        json={"agent_id": agent_id},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _send_one_on_one(client: TestClient, headers: dict, session_id: str):
    return client.post(
        "/v1/agents/one_on_one/message",
        json={"session_id": session_id, "user_message": "what do you think of AAPL"},
        headers=headers,
    )


def test_one_on_one_non_concierge_connect_error_yields_branded_copy_no_charge(
    one_on_one_client, monkeypatch, _real_vllm_gateway,
):
    """DEF424's own reproduction shape: a fully unreachable host raises a bare
    transport exception (`httpx.ConnectError`) — no HTTP status, no in-band
    frame, nothing for the gateway's existing `[AMI error: HTTP …]` sentinel
    to key off. Before this fix, `LLMGateway.stream_chat` re-raised it
    straight through `AgentRunner.stream_one_on_one_message`'s non-Concierge
    branch to `one_on_one.py`'s catch-all, which put the exception's OWN text
    on the wire verbatim."""
    from app.core import config as config_mod
    monkeypatch.setattr(config_mod.settings, "one_on_one_credit_cost", 3)

    _real_vllm_gateway(_connect_error_handler)

    user_id, headers = _new_user()
    before = balance_for(user_id)[0]
    session_id = _open_one_on_one(one_on_one_client, headers, agent_id="trader")

    r = _send_one_on_one(one_on_one_client, headers, session_id)
    assert r.status_code == 200, r.text

    # No raw transport text on the wire.
    assert "connection refused" not in r.text.lower()
    assert "ConnectError" not in r.text
    # Branded AMI copy instead — MockProvider's own canned Trader line.
    assert "AMI" in r.text
    assert MockProvider._CANNED["trader"][:40] in r.text.replace("\\n", "\n")

    assert balance_for(user_id)[0] == before, (
        "an LLM-down turn must net to zero credits (spent then refunded)"
    )
    kinds = [e.event_type for e in _ledger(user_id)]
    assert kinds.count("credits_spent") == 1
    assert kinds.count("credits_refunded") == 1


def test_one_on_one_non_concierge_http_503_is_refunded_no_raw_text(
    one_on_one_client, monkeypatch, _real_vllm_gateway,
):
    """DEF424 post-COMPLETE MINOR-1: a reachable host answering a real HTTP
    503 hits `OpenAICompatibleProvider.stream_chat`'s existing non-200
    branch, which sets `meta["stream_error"]` and used to yield its own
    `[AMI error: HTTP 503 from the upstream provider (vllm). Check backend
    logs.]` sentinel straight to the user — never the raw httpx response
    body, but still an internal provider name, an HTTP status and an
    operator instruction. Round 1 filed this as the ALREADY-correct control;
    round-1 audit MINOR-1 found the leak and this round routes it through
    the same `canned_agent_fallback` branded copy `_stream_error`-driven
    Concierge/ConnectError shapes already use. The refund (RETRO-SECURITY
    MAJOR-2) is unchanged — same `stream_error` key, still net 0 credits."""
    from app.core import config as config_mod
    monkeypatch.setattr(config_mod.settings, "one_on_one_credit_cost", 3)

    _real_vllm_gateway(_http_503_handler)

    user_id, headers = _new_user()
    before = balance_for(user_id)[0]
    session_id = _open_one_on_one(one_on_one_client, headers, agent_id="trader")

    r = _send_one_on_one(one_on_one_client, headers, session_id)
    assert r.status_code == 200, r.text
    assert "upstream unavailable" not in r.text.lower(), (
        "the raw httpx response body must never reach the client"
    )
    lower = r.text.lower()
    assert "vllm" not in lower
    assert "503" not in r.text
    assert "backend logs" not in lower
    assert "AMI error" not in r.text
    assert "AMI" in r.text
    assert MockProvider._CANNED["trader"][:40] in r.text.replace("\\n", "\n")

    assert balance_for(user_id)[0] == before, (
        "an HTTP-503 turn must net to zero credits (spent then refunded)"
    )
    kinds = [e.event_type for e in _ledger(user_id)]
    assert kinds.count("credits_spent") == 1
    assert kinds.count("credits_refunded") == 1


def test_one_on_one_non_concierge_success_still_bills_normally(
    one_on_one_client, monkeypatch, _real_vllm_gateway,
):
    """Control — threading the try/except through must not turn a real,
    successful reply into a false refund."""
    from app.core import config as config_mod
    monkeypatch.setattr(config_mod.settings, "one_on_one_credit_cost", 3)

    _real_vllm_gateway(_ok_handler)

    user_id, headers = _new_user()
    before = balance_for(user_id)[0]
    session_id = _open_one_on_one(one_on_one_client, headers, agent_id="trader")

    r = _send_one_on_one(one_on_one_client, headers, session_id)
    assert r.status_code == 200, r.text
    assert "hello from a real reply" in r.text
    assert balance_for(user_id)[0] == before - 3
    kinds = [e.event_type for e in _ledger(user_id)]
    assert kinds.count("credits_spent") == 1
    assert kinds.count("credits_refunded") == 0


# ── Brief Your Agent ──────────────────────────────────────────────────────


@pytest.fixture
def brief_client() -> TestClient:
    a = FastAPI()
    a.include_router(brief_router)
    return TestClient(a, raise_server_exceptions=False)


def _open_brief(client: TestClient, user_id, headers: dict, agent_id: str) -> str:
    r = client.post(
        "/v1/brief/start",
        json={"agent_id": agent_id, "user_id": str(user_id)},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["session"]["id"]


def _send_brief(client: TestClient, headers: dict, session_id: str):
    return client.post(
        "/v1/brief/message",
        json={"session_id": session_id, "user_message": "focus more on momentum"},
        headers=headers,
    )


def test_brief_connect_error_yields_branded_copy_no_charge(
    brief_client, monkeypatch, _real_vllm_gateway,
):
    """DEF424's own reproduction shape, on Brief: a fully unreachable host
    raises `httpx.ConnectError`. Before this fix, `BriefEngine.stream_chat`
    had no try/except at all, so the exception reached `brief.py`'s
    catch-all `except Exception as e: yield sse_text("error", str(e)[:300])`
    — the exact `data: All connection attempts failed` leak the live drill
    reproduced."""
    from app.core import config as config_mod
    monkeypatch.setattr(config_mod.settings, "brief_credit_cost", 3)

    _real_vllm_gateway(_connect_error_handler)

    user_id, headers = _new_user()
    before = balance_for(user_id)[0]
    session_id = _open_brief(brief_client, user_id, headers, agent_id="market_analyst")

    r = _send_brief(brief_client, headers, session_id)
    assert r.status_code == 200, r.text

    assert "connection refused" not in r.text.lower()
    assert "ConnectError" not in r.text
    assert "AMI" in r.text
    assert MockProvider._CANNED["market_analyst"][:40] in r.text.replace("\\n", "\n")

    assert balance_for(user_id)[0] == before, (
        "a Brief turn on an LLM-down provider must net to zero credits"
    )
    kinds = [e.event_type for e in _ledger(user_id)]
    assert kinds.count("credits_spent") == 1
    assert kinds.count("credits_refunded") == 1


def test_brief_http_503_is_refunded_no_raw_text(
    brief_client, monkeypatch, _real_vllm_gateway,
):
    """DEF424 post-COMPLETE MINOR-1, Brief sibling: a real HTTP 503 hit the
    gateway's own in-band sentinel + refund (RETRO-SECURITY MAJOR-2 round 2)
    but the sentinel TEXT itself — provider name, HTTP status, "Check backend
    logs" — used to reach the user verbatim. Now swapped for branded
    `canned_agent_fallback` copy; the refund is unchanged."""
    from app.core import config as config_mod
    monkeypatch.setattr(config_mod.settings, "brief_credit_cost", 3)

    _real_vllm_gateway(_http_503_handler)

    user_id, headers = _new_user()
    before = balance_for(user_id)[0]
    session_id = _open_brief(brief_client, user_id, headers, agent_id="market_analyst")

    r = _send_brief(brief_client, headers, session_id)
    assert r.status_code == 200, r.text
    assert "upstream unavailable" not in r.text.lower()
    lower = r.text.lower()
    assert "vllm" not in lower
    assert "503" not in r.text
    assert "backend logs" not in lower
    assert "AMI error" not in r.text
    assert "AMI" in r.text
    assert MockProvider._CANNED["market_analyst"][:40] in r.text.replace("\\n", "\n")

    assert balance_for(user_id)[0] == before, (
        "an HTTP-503 Brief turn must net to zero credits (spent then refunded)"
    )
    kinds = [e.event_type for e in _ledger(user_id)]
    assert kinds.count("credits_spent") == 1
    assert kinds.count("credits_refunded") == 1


def test_brief_success_still_bills_normally(
    brief_client, monkeypatch, _real_vllm_gateway,
):
    from app.core import config as config_mod
    monkeypatch.setattr(config_mod.settings, "brief_credit_cost", 3)

    _real_vllm_gateway(_ok_handler)

    user_id, headers = _new_user()
    before = balance_for(user_id)[0]
    session_id = _open_brief(brief_client, user_id, headers, agent_id="market_analyst")

    r = _send_brief(brief_client, headers, session_id)
    assert r.status_code == 200, r.text
    assert "hello from a real reply" in r.text
    assert balance_for(user_id)[0] == before - 3
    kinds = [e.event_type for e in _ledger(user_id)]
    assert kinds.count("credits_spent") == 1
    assert kinds.count("credits_refunded") == 0


# ── DEF424 post-COMPLETE MINOR-2: mid-stream drop after partial content ──


def test_one_on_one_non_concierge_partial_stream_then_drop_appends_cutoff_notice(
    one_on_one_client, monkeypatch, _real_vllm_gateway,
):
    """MINOR-2: the provider yields some REAL content, then the connection
    drops mid-reply (`if not buf` correctly skips branded fallback copy here
    — concatenating it after real content would read as nonsense — but the
    user used to get no signal at all that the reply was cut off or that the
    turn wasn't charged). Now: the partial real text is kept, one short
    branded line is appended, and the refund still fires."""
    from app.core import config as config_mod
    monkeypatch.setattr(config_mod.settings, "one_on_one_credit_cost", 3)

    _real_vllm_gateway(_PartialThenDropTransport())

    user_id, headers = _new_user()
    before = balance_for(user_id)[0]
    session_id = _open_one_on_one(one_on_one_client, headers, agent_id="trader")

    r = _send_one_on_one(one_on_one_client, headers, session_id)
    assert r.status_code == 200, r.text

    assert "partial real " in r.text
    assert "content before " in r.text
    assert "wasn't charged" in r.text.replace("\\'", "'")
    assert "ReadError" not in r.text
    assert "connection dropped mid-stream" not in r.text

    assert balance_for(user_id)[0] == before, (
        "a mid-stream drop after partial content must still net to zero credits"
    )
    kinds = [e.event_type for e in _ledger(user_id)]
    assert kinds.count("credits_spent") == 1
    assert kinds.count("credits_refunded") == 1


def test_brief_partial_stream_then_drop_appends_cutoff_notice(
    brief_client, monkeypatch, _real_vllm_gateway,
):
    """MINOR-2, Brief sibling — same shape as the 1-on-1 test above."""
    from app.core import config as config_mod
    monkeypatch.setattr(config_mod.settings, "brief_credit_cost", 3)

    _real_vllm_gateway(_PartialThenDropTransport())

    user_id, headers = _new_user()
    before = balance_for(user_id)[0]
    session_id = _open_brief(brief_client, user_id, headers, agent_id="market_analyst")

    r = _send_brief(brief_client, headers, session_id)
    assert r.status_code == 200, r.text

    assert "partial real " in r.text
    assert "content before " in r.text
    assert "wasn't charged" in r.text.replace("\\'", "'")
    assert "ReadError" not in r.text
    assert "connection dropped mid-stream" not in r.text

    assert balance_for(user_id)[0] == before, (
        "a mid-stream drop after partial content must still net to zero credits"
    )
    kinds = [e.event_type for e in _ledger(user_id)]
    assert kinds.count("credits_spent") == 1
    assert kinds.count("credits_refunded") == 1


# ── unit-level: canned_agent_fallback helper ─────────────────────────────


def test_canned_agent_fallback_matches_mock_provider_per_agent():
    from app.schemas import AgentId
    from app.services.llm_gateway import canned_agent_fallback

    assert canned_agent_fallback(AgentId.TRADER) == MockProvider._CANNED["trader"]
    assert canned_agent_fallback("market_analyst") == MockProvider._CANNED["market_analyst"]


def test_canned_agent_fallback_defaults_for_an_agent_with_no_canned_entry():
    from app.schemas import AgentId
    from app.services.llm_gateway import canned_agent_fallback

    # research_manager has no dedicated _CANNED entry — must still be
    # branded AMI copy, never a KeyError and never empty text.
    assert AgentId.RESEARCH_MANAGER.value not in MockProvider._CANNED
    text = canned_agent_fallback(AgentId.RESEARCH_MANAGER)
    assert text == MockProvider._DEFAULT
    assert "AMI" in text
