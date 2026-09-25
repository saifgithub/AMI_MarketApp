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


@pytest.fixture
def _real_vllm_gateway(monkeypatch):
    """Register a real VLLMProvider (`vllm > anthropic > kimi > mock`), then
    hand back a function that swaps its transport for an `httpx.MockTransport`
    driven by the given handler. Rewires BOTH `agent_runner.get_agent_runner`
    and `brief_engine.get_brief_engine` to the same gateway instance so a
    single fixture covers both surfaces under test.
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

    def _wire(handler):
        provider = gateway._providers["vllm"]
        provider._client = _httpx.AsyncClient(
            base_url="http://fake-vllm:8000",
            transport=_httpx.MockTransport(handler),
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
    """The sibling shape DEF424's own row text calls out as ALREADY correct:
    a reachable host answering a real HTTP 503 hits `OpenAICompatibleProvider
    .stream_chat`'s existing non-200 branch, which sets `meta["stream_error"]`
    and yields its own `[AMI error: HTTP 503 …]` sentinel — never a raw
    transport string, and (per RETRO-SECURITY MAJOR-2) already refunded. This
    is the CONTROL that the DEF424 fix (a try/except around the whole call)
    does not change that pre-existing, working behaviour for the non-Concierge
    branch."""
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
    assert "AMI error" in r.text

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
    """Control, mirroring the 1-on-1 sibling: a real HTTP 503 was already
    handled correctly by the gateway's own in-band sentinel + refund
    (RETRO-SECURITY MAJOR-2 round 2) — this fix's try/except must not change
    that."""
    from app.core import config as config_mod
    monkeypatch.setattr(config_mod.settings, "brief_credit_cost", 3)

    _real_vllm_gateway(_http_503_handler)

    user_id, headers = _new_user()
    before = balance_for(user_id)[0]
    session_id = _open_brief(brief_client, user_id, headers, agent_id="market_analyst")

    r = _send_brief(brief_client, headers, session_id)
    assert r.status_code == 200, r.text
    assert "upstream unavailable" not in r.text.lower()
    assert "AMI error" in r.text

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
