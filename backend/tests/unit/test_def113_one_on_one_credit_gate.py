"""DEF113 (AT:R65) — 1-on-1 chat gets a charging spine, priced 0 in Alpha.

Before this, `credit_service.spend()` had exactly one call site in the whole
backend (Room). `backend/app/api/one_on_one.py` never touched credits/402 at
all — unlimited free 1-on-1s on every plan, including Floor Pass, even though
credits.md:18 prices a 1-on-1 turn at 1 credit and sizes the whole Floor Pass
allowance against it.

Saiful ruled (2026-07-30): wire the full spend()/ledger/402 spine now, but
keep `settings.one_on_one_credit_cost` at 0 in Alpha so no existing tester
hits a paywall they've never seen mid-test. The dangerous part is the 0 —
these tests pin that it is a genuine charge-of-zero (full path executes,
ledger row written, balance arithmetic runs), not a silently-skipped charge,
and that the 402 wall is proven at a non-zero price so the spine isn't
untested until someone flips the price.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.one_on_one import router as one_on_one_router
from app.db import get_session
from app.db.models import SubscriptionEventRow, User
from app.schemas import AgentId
from app.services.auth_service import AuthService
from app.services.credit_service import balance_for, one_on_one_cost
from app.services.rate_limit import one_on_one_message_rate_limit


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.include_router(one_on_one_router)
    return a


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _reset_limiter():
    one_on_one_message_rate_limit.reset()
    yield
    one_on_one_message_rate_limit.reset()


def _new_user() -> tuple[str, dict]:
    auth = AuthService()
    user, token, _ = auth.ensure_anonymous(device_user_id=None)
    return user.id, {"Authorization": f"Bearer {token}"}


def _open_session(client: TestClient, headers: dict, agent_id: str = "concierge") -> str:
    """Concierge is always free (no lesson-unlock gate) — keeps these tests
    about billing, not the agent-lock gate DEF179 already covers."""
    r = client.post(
        "/v1/agents/one_on_one/start",
        json={"agent_id": agent_id},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _send(client: TestClient, headers: dict, session_id: str, msg: str = "hi"):
    return client.post(
        "/v1/agents/one_on_one/message",
        json={"session_id": session_id, "user_message": msg},
        headers=headers,
    )


def _ledger(user_id) -> list[SubscriptionEventRow]:
    with get_session() as s:
        return list(s.execute(
            select(SubscriptionEventRow)
            .where(SubscriptionEventRow.user_id == user_id)
            .order_by(SubscriptionEventRow.created_at)
        ).scalars())


# ── Acceptance 1: a turn debits through spend() ──────────────────────────

def test_message_debits_through_spend_at_a_non_zero_price(client, monkeypatch):
    """Proves the charge really happens on the wire, not just in unit-tested
    isolation — this is the test that FAILED against pre-DEF113 code (which
    never called spend() from one_on_one.py at all)."""
    from app.core import config as config_mod
    monkeypatch.setattr(config_mod.settings, "one_on_one_credit_cost", 3)

    user_id, headers = _new_user()
    before = balance_for(user_id)[0]
    session_id = _open_session(client, headers)

    r = _send(client, headers, session_id)
    assert r.status_code == 200, r.text
    assert balance_for(user_id)[0] == before - 3

    spent = [e for e in _ledger(user_id) if e.event_type == "credits_spent"]
    assert len(spent) == 1
    assert spent[0].note == "one_on_one:concierge"


# ── Acceptance 2: the 402 path, proven at a non-zero price ──────────────

def test_insufficient_credits_returns_402_at_a_non_zero_price(client, monkeypatch):
    from app.core import config as config_mod
    monkeypatch.setattr(config_mod.settings, "one_on_one_credit_cost", 3)

    user_id, headers = _new_user()
    balance_for(user_id)  # establish the allowance window (grants 13) first
    with get_session() as s:
        s.get(User, user_id).credit_balance = 2  # below the 3-credit cost
    session_id = _open_session(client, headers)

    r = _send(client, headers, session_id)
    assert r.status_code == 402
    detail = r.json()["detail"]
    assert detail["code"] == "insufficient_credits"
    assert detail["balance"] == 2
    assert detail["cost"] == 3
    assert detail["plan"] == "floor_pass"
    # The wall must not nibble — a refused spend leaves the balance untouched.
    assert balance_for(user_id)[0] == 2


def test_402_does_not_stream_or_journal_the_turn(client, monkeypatch):
    """A refused spend must not still run the LLM call or write a journal
    entry — the 402 has to land before any of that."""
    from app.core import config as config_mod
    from app.services.journal_store import get_journal_store
    monkeypatch.setattr(config_mod.settings, "one_on_one_credit_cost", 3)

    user_id, headers = _new_user()
    balance_for(user_id)  # establish the allowance window (grants 13) first
    with get_session() as s:
        s.get(User, user_id).credit_balance = 0
    session_id = _open_session(client, headers)

    before_entries = get_journal_store().list_for_user(user_id)[1]
    r = _send(client, headers, session_id)
    assert r.status_code == 402
    assert get_journal_store().list_for_user(user_id)[1] == before_entries


# ── Acceptance 3: Alpha's price of 0 is a genuine charge-of-zero ─────────

def test_the_default_price_is_the_spec_price():
    """SUPERSEDED 2026-08-24 (DEF205). This asserted 0 — correct under the
    2026-07-30 ruling, which held the price at zero so no tester met an
    unfamiliar paywall mid-test. Saiful re-ruled *"1 credit per turn, Brief
    the same"* after the risk was measured away: every Alpha account holds
    116+ credits, i.e. 116+ turns before a 402 is reachable. credits.md:18
    has priced a 1-on-1 turn at 1 throughout; the default now matches it."""
    from app.core.config import settings
    assert settings.one_on_one_credit_cost == 1
    assert one_on_one_cost() == 1


def test_a_zero_price_turn_is_still_a_charge_and_not_a_skipped_charge(client, monkeypatch):
    """The property this lane actually protects, kept and now pinned
    independently of the default. A price of 0 must still run spend()'s full
    path — ledger row written, balance arithmetic executed — so that moving
    the price is a config change and never a new code path. It survived the
    flip to 1 precisely because it was never about the number."""
    from app.core import config as config_mod
    monkeypatch.setattr(config_mod.settings, "one_on_one_credit_cost", 0)

    user_id, headers = _new_user()
    before = balance_for(user_id)[0]
    session_id = _open_session(client, headers)

    r = _send(client, headers, session_id)
    assert r.status_code == 200, r.text
    assert balance_for(user_id)[0] == before  # unchanged: charged 0, not skipped

    spent = [e for e in _ledger(user_id) if e.event_type == "credits_spent"]
    assert len(spent) == 1, "spend() must be called even at price 0"
    assert spent[0].from_value == spent[0].to_value == str(before)
    assert spent[0].note == "one_on_one:concierge"


def test_the_default_price_actually_debits(client):
    """DEF205 — the flip is only real if a turn at the default price moves
    the balance. Asserts the charge without monkeypatching anything, which is
    the one thing the old zero-price test could not do."""
    user_id, headers = _new_user()
    before = balance_for(user_id)[0]
    session_id = _open_session(client, headers)

    r = _send(client, headers, session_id)
    assert r.status_code == 200, r.text
    assert balance_for(user_id)[0] == before - 1


# ── Ownership precedes billing ───────────────────────────────────────────

def test_ownership_403_precedes_any_billing(client, monkeypatch):
    from app.core import config as config_mod
    monkeypatch.setattr(config_mod.settings, "one_on_one_credit_cost", 3)

    owner_id, owner_headers = _new_user()
    _, attacker_headers = _new_user()
    session_id = _open_session(client, owner_headers)

    before = balance_for(owner_id)[0]
    r = _send(client, attacker_headers, session_id)
    assert r.status_code == 403
    assert balance_for(owner_id)[0] == before


# ── Acceptance 4: charged-then-failed is refunded ────────────────────────

def test_llm_failure_after_spend_refunds_at_a_non_zero_price(client, monkeypatch):
    from app.core import config as config_mod
    from app.services import agent_runner as agent_runner_mod
    monkeypatch.setattr(config_mod.settings, "one_on_one_credit_cost", 3)

    async def _boom(**_kwargs):
        raise RuntimeError("simulated provider failure")
        yield  # pragma: no cover — makes this an async generator

    monkeypatch.setattr(
        agent_runner_mod.AgentRunner, "stream_one_on_one_message", _boom
    )

    user_id, headers = _new_user()
    before = balance_for(user_id)[0]
    session_id = _open_session(client, headers)

    r = _send(client, headers, session_id)
    assert r.status_code == 200  # the error is an in-band SSE event, not an HTTP failure
    assert balance_for(user_id)[0] == before, "charged-then-failed must be refunded"

    kinds = [e.event_type for e in _ledger(user_id)]
    assert kinds.count("credits_spent") == 1
    assert kinds.count("credits_refunded") == 1


# ── RETRO-SECURITY MAJOR-2 (round 2) — the auditor's second finding on the
# same MAJOR: a non-200 transport reply never raises, so a route that only
# refunds on a raised exception still bills for it. `agent_runner.py` now
# threads a caller-supplied `meta` dict into `LLMGateway.stream_chat`'s own
# `meta=`, and `llm_gateway.py` writes `stream_error` into it on this exact
# shape (RETRO-SECURITY MAJOR-2 round 2) — this test drives that contract
# through the real route with a fake `stream_one_on_one_message` that
# reproduces it, rather than asserting on the sentinel's own wording.

def test_an_http_error_sentinel_reply_is_refunded_not_billed(client, monkeypatch):
    from app.core import config as config_mod
    from app.services import agent_runner as agent_runner_mod
    monkeypatch.setattr(config_mod.settings, "one_on_one_credit_cost", 3)

    async def _sentinel_no_raise(self, *, meta=None, **_kwargs):
        if meta is not None:
            meta["stream_error"] = "HTTP 503: vLLM host unreachable"
        yield "[AMI error: HTTP 503 from the upstream provider (vllm). Check backend logs.]"

    monkeypatch.setattr(
        agent_runner_mod.AgentRunner, "stream_one_on_one_message", _sentinel_no_raise
    )

    user_id, headers = _new_user()
    before = balance_for(user_id)[0]
    session_id = _open_session(client, headers)

    r = _send(client, headers, session_id)
    assert r.status_code == 200
    assert "AMI error" in r.text
    assert balance_for(user_id)[0] == before, (
        "an HTTP-error-sentinel reply must be refunded, not billed as a "
        "successful turn"
    )

    kinds = [e.event_type for e in _ledger(user_id)]
    assert kinds.count("credits_spent") == 1
    assert kinds.count("credits_refunded") == 1


# ── Config-check reports the configured price ────────────────────────────

def test_config_check_reports_the_one_on_one_price(monkeypatch):
    from app.api.admin import router as admin_router
    from app.core.config import settings as _settings

    monkeypatch.setattr(_settings, "admin_secret", "test-secret")
    monkeypatch.setattr(_settings, "one_on_one_credit_cost", 7)

    a = FastAPI()
    a.include_router(admin_router)
    c = TestClient(a)
    r = c.get(
        "/v1/admin/config-check",
        headers={"Authorization": "Bearer test-secret"},
    )
    assert r.status_code == 200
    assert r.json()["one_on_one_credit_cost"] == 7


def test_negative_price_fails_boot_loudly():
    """CR040 degrade-loudly, same shape as the CR098 pull-back validator."""
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(one_on_one_credit_cost=-1, _env_file=None)


# ── RETRO-SECURITY MAJOR-2 (round 3) — the Concierge 1-on-1, real gateway ───
#
# Round 2's `test_an_http_error_sentinel_reply_is_refunded_not_billed` above
# monkeypatches the whole `stream_one_on_one_message` method — exactly what
# the round-2 auditor flagged: it never exercises `_stream_concierge`'s own
# `self._llm.stream_chat` call, so it could not have caught that `meta` never
# reached that call, or that the ConnectError branch swallowed the failure
# with no signal at all. These drive the REAL `LLMGateway` + a REAL
# `OpenAICompatibleProvider` (as `VLLMProvider`, the live-preference
# provider), with only the HTTP transport faked via `httpx.MockTransport` —
# the auditor's own probe shape, reproduced through the route.

@pytest.fixture
def _real_vllm_gateway(monkeypatch):
    """Register a real VLLMProvider so `_active_provider_name()` picks
    "vllm" (the live preference, `vllm > anthropic > mock`), then hand back
    a function that swaps its transport for an `httpx.MockTransport` driven
    by the given handler — the provider object, request building, SSE
    parsing and `meta["stream_error"]` writes are all the real code."""
    import httpx as _httpx

    from app.core import config as config_mod
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

    from app.services import agent_runner as agent_runner_mod
    monkeypatch.setattr(agent_runner_mod, "_runner", None)
    monkeypatch.setattr(
        agent_runner_mod, "get_agent_runner",
        lambda: agent_runner_mod.AgentRunner(gateway),
    )

    return _wire


def _http_503_handler(request):
    import httpx as _httpx
    return _httpx.Response(503, text="upstream unavailable")


def _connect_error_handler(request):
    import httpx as _httpx
    raise _httpx.ConnectError("connection refused", request=request)


def test_concierge_real_provider_http_503_is_refunded_not_billed(
    client, monkeypatch, _real_vllm_gateway
):
    """Auditor round-2 probe: `PROBE 1on1 agent=concierge http503 charged=1`.
    The gateway's own `stream_chat` writes `meta["stream_error"]` on a
    non-200 reply (`llm_gateway.py`'s `OpenAICompatibleProvider.stream_chat`)
    — round 3's fix threads that same `meta` into `_stream_concierge`, which
    round 2 never did."""
    from app.core import config as config_mod
    monkeypatch.setattr(config_mod.settings, "one_on_one_credit_cost", 3)

    _real_vllm_gateway(_http_503_handler)

    user_id, headers = _new_user()
    before = balance_for(user_id)[0]
    session_id = _open_session(client, headers, agent_id="concierge")

    r = _send(client, headers, session_id)
    assert r.status_code == 200, r.text
    assert "AMI error" in r.text
    assert balance_for(user_id)[0] == before, (
        "Concierge must not bill for an HTTP-error-sentinel reply"
    )
    kinds = [e.event_type for e in _ledger(user_id)]
    assert kinds.count("credits_spent") == 1
    assert kinds.count("credits_refunded") == 1


def test_concierge_real_provider_connect_error_is_refunded_not_billed(
    client, monkeypatch, _real_vllm_gateway
):
    """Auditor round-2 probe: `PROBE 1on1 agent=concierge connect_error
    charged=1  tail: a scripted Concierge reply`. Before round 3,
    `_stream_concierge`'s `except Exception` swallowed the transport error
    and yielded a scripted fallback with no `stream_error` signal at all —
    so the caller billed a real turn for a fallback the user never chose."""
    from app.core import config as config_mod
    monkeypatch.setattr(config_mod.settings, "one_on_one_credit_cost", 3)

    _real_vllm_gateway(_connect_error_handler)

    user_id, headers = _new_user()
    before = balance_for(user_id)[0]
    session_id = _open_session(client, headers, agent_id="concierge")

    r = _send(client, headers, session_id)
    assert r.status_code == 200, r.text
    assert balance_for(user_id)[0] == before, (
        "Concierge must not bill for a provider outage answered by the "
        "scripted fallback reply"
    )
    kinds = [e.event_type for e in _ledger(user_id)]
    assert kinds.count("credits_spent") == 1
    assert kinds.count("credits_refunded") == 1


def test_concierge_real_provider_success_still_bills_normally(
    client, monkeypatch, _real_vllm_gateway
):
    """Control: threading `meta` through must not turn a real, successful
    Concierge reply into a false refund."""
    from app.core import config as config_mod
    monkeypatch.setattr(config_mod.settings, "one_on_one_credit_cost", 3)

    def _ok_handler(request):
        import httpx as _httpx
        body = (
            b'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n'
            b'data: [DONE]\n\n'
        )
        return _httpx.Response(
            200, content=body,
            headers={"content-type": "text/event-stream"},
        )

    _real_vllm_gateway(_ok_handler)

    user_id, headers = _new_user()
    before = balance_for(user_id)[0]
    session_id = _open_session(client, headers, agent_id="concierge")

    r = _send(client, headers, session_id)
    assert r.status_code == 200, r.text
    assert balance_for(user_id)[0] == before - 3
    kinds = [e.event_type for e in _ledger(user_id)]
    assert kinds.count("credits_spent") == 1
    assert kinds.count("credits_refunded") == 0
