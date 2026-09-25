"""DEF205 — Brief Your Agent turns cost credits, same flat price as 1-on-1.

Until 2026-08-24 `credit_service.spend()` was reachable only from
`room_runner`. Both conversational surfaces therefore burned real vLLM (and,
on a vLLM outage, real Anthropic) compute for free, bounded only by DEF186's
12/min per-user limit — **720 unpriced turns per user per hour** — and by
DEF201's concurrency cap. Both buy time; neither prices anything.

Saiful ruled 2026-08-24: *"1 credit per turn, Brief the same."* DEF113 had
already built the spine for 1-on-1 and left it priced at 0; this is the other
surface plus the flip, and these tests mirror
`test_def113_one_on_one_credit_gate.py` deliberately — the two surfaces share
a concurrency cap and now a price, so their guards should be comparable
side by side.

The guard worth naming: `test_a_402_does_not_leak_a_concurrency_slot`. The
generator that releases the slot in its `finally` never runs on the refusal
path, so without an explicit release a user who hits their credit wall
permanently loses one of the slots they share with 1-on-1 — DEF201's exact
shape, arriving through the new door this change opens.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.brief import router as brief_router
from app.db import get_session
from app.db.models import SubscriptionEventRow
from app.services.auth_service import AuthService
from app.services.credit_service import balance_for, brief_cost
from app.services.rate_limit import (
    agent_stream_concurrency_limit,
    brief_message_rate_limit,
)


@pytest.fixture
def client() -> TestClient:
    a = FastAPI()
    a.include_router(brief_router)
    return TestClient(a, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _reset_limiters():
    brief_message_rate_limit.reset()
    yield
    brief_message_rate_limit.reset()


def _new_user() -> tuple[str, dict]:
    auth = AuthService()
    user, token, _ = auth.ensure_anonymous(device_user_id=None)
    return user.id, {"Authorization": f"Bearer {token}"}


def _open(client: TestClient, user_id, headers: dict) -> str:
    r = client.post(
        "/v1/brief/start",
        json={"agent_id": "concierge", "user_id": str(user_id)},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["session"]["id"]


def _send(client: TestClient, headers: dict, session_id: str):
    return client.post(
        "/v1/brief/message",
        json={"session_id": session_id, "user_message": "hi"},
        headers=headers,
    )


def _ledger(user_id) -> list[SubscriptionEventRow]:
    with get_session() as s:
        return list(s.execute(
            select(SubscriptionEventRow).where(
                SubscriptionEventRow.user_id == user_id
            )
        ).scalars())


def test_the_default_brief_price_matches_one_on_one():
    from app.core.config import settings
    from app.services.credit_service import one_on_one_cost

    assert brief_cost() == 1
    assert brief_cost() == one_on_one_cost(), "Saiful: 'Brief the same'"
    assert settings.brief_credit_cost == 1


def test_a_brief_turn_debits_through_spend(client, monkeypatch):
    """The test that FAILS against pre-DEF205 code, which never called
    spend() from brief.py at all."""
    from app.core import config as config_mod
    monkeypatch.setattr(config_mod.settings, "brief_credit_cost", 3)

    user_id, headers = _new_user()
    before = balance_for(user_id)[0]
    session_id = _open(client, user_id, headers)

    r = _send(client, headers, session_id)
    assert r.status_code == 200, r.text
    assert balance_for(user_id)[0] == before - 3

    spent = [e for e in _ledger(user_id) if e.event_type == "credits_spent"]
    assert len(spent) == 1
    assert spent[0].note.startswith("brief:")


def test_the_default_price_actually_debits(client):
    user_id, headers = _new_user()
    before = balance_for(user_id)[0]
    session_id = _open(client, user_id, headers)

    assert _send(client, headers, session_id).status_code == 200
    assert balance_for(user_id)[0] == before - 1


def test_an_exhausted_balance_gets_a_402_not_a_free_turn(client, monkeypatch):
    from app.core import config as config_mod
    monkeypatch.setattr(config_mod.settings, "brief_credit_cost", 10**9)

    user_id, headers = _new_user()
    session_id = _open(client, user_id, headers)

    r = _send(client, headers, session_id)
    assert r.status_code == 402, r.text
    assert r.json()["detail"]["code"] == "insufficient_credits"


def test_a_402_does_not_leak_a_concurrency_slot(client, monkeypatch):
    """DEF201's shape through DEF205's new door: the generator that releases
    the slot never runs on the refusal path. A leaked slot is permanent and
    is shared with 1-on-1, so the user loses capacity on BOTH surfaces."""
    from app.core import config as config_mod
    monkeypatch.setattr(config_mod.settings, "brief_credit_cost", 10**9)

    user_id, headers = _new_user()
    session_id = _open(client, user_id, headers)
    key = f"user:{user_id}"

    for _ in range(6):
        assert _send(client, headers, session_id).status_code == 402

    # If slots leaked, this acquire raises rather than succeeding.
    agent_stream_concurrency_limit.acquire(key)
    agent_stream_concurrency_limit.release(key)


# ── RETRO-SECURITY MAJOR-2 (round 2): charged-then-failed is refunded ─────
#
# Mirrors test_def113_one_on_one_credit_gate.py's
# `test_llm_failure_after_spend_refunds_at_a_non_zero_price` — until round 2,
# `brief.py` had no twin: a failed Brief turn was charged and never refunded.
# These also cover the auditor's SECOND finding on the same MAJOR: a reply
# that is really the provider's own "[AMI error: HTTP 503 …]" sentinel,
# rendered as an ordinary token chunk, must be detected the same way a raised
# exception is — via `llm_gateway.py`'s structural `stream_error` channel,
# never by matching the sentinel text.

class _FakeGatewayRaises:
    """A raised exception during the stream — DEF113's exact shape, ported."""

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(self, **_kwargs):
        yield "partial "
        raise RuntimeError("simulated provider failure")


class _FakeGatewayHttpErrorSentinel:
    """The auditor's probe: a non-200 transport response never raises — the
    OpenAI-compatible provider yields the `[AMI error: HTTP 503 …]` sentinel
    as an ordinary chunk and returns cleanly. Structural detection means
    writing `meta["stream_error"]`, exactly as `llm_gateway.py` now does on
    this path (RETRO-SECURITY MAJOR-2 round 2) — this fake reproduces that
    same contract rather than the sentinel text alone, so the test proves the
    route reads the key and not the prose."""

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(self, *, meta=None, **_kwargs):
        if meta is not None:
            meta["stream_error"] = "HTTP 503: vLLM host unreachable"
        yield "[AMI error: HTTP 503 from the upstream provider (vllm). Check backend logs.]"


def _engine_with(fake_gateway) -> "BriefEngine":
    from app.services.brief_engine import BriefEngine
    from app.services.overlay_store import get_overlay_store

    return BriefEngine(fake_gateway, get_overlay_store())


def test_a_raised_provider_failure_after_spend_is_refunded(monkeypatch):
    from app.api.brief import router as brief_router
    from app.services.brief_engine import get_brief_engine
    from app.core import config as config_mod

    monkeypatch.setattr(config_mod.settings, "brief_credit_cost", 3)

    engine = _engine_with(_FakeGatewayRaises())
    a = FastAPI()
    a.include_router(brief_router)
    a.dependency_overrides[get_brief_engine] = lambda: engine
    client = TestClient(a, raise_server_exceptions=False)

    user_id, headers = _new_user()
    before = balance_for(user_id)[0]
    session_id = _open(client, user_id, headers)

    r = _send(client, headers, session_id)
    assert r.status_code == 200  # the error is an in-band SSE event
    assert balance_for(user_id)[0] == before, "charged-then-failed must be refunded"

    kinds = [e.event_type for e in _ledger(user_id)]
    assert kinds.count("credits_spent") == 1
    assert kinds.count("credits_refunded") == 1


def test_an_http_error_sentinel_reply_is_refunded_not_billed(monkeypatch):
    """The auditor's exact probe (round 1 run report): a non-200 transport
    reply never raises, so BEFORE round 2's fix the route's only "did this
    fail" signal was absent and the turn was billed for an error message
    rendered as the answer.

    DEF424 post-COMPLETE MINOR-1 (round-1 audit): round 2 only fixed the
    BILLING half — the raw `[AMI error: HTTP 503 …]` sentinel text itself
    (provider name, HTTP status, "Check backend logs") still reached the
    user verbatim. `BriefEngine.stream_chat` now detects the `stream_error`
    key going from unset to set on this exact chunk and swaps it for
    `canned_agent_fallback(agent_id)` — this session is `agent_id=concierge`
    (see `_open` above), so the branded copy is `MockProvider._CANNED
    ["concierge"]`. The refund assertion below is unchanged from round 2."""
    from app.api.brief import router as brief_router
    from app.services.brief_engine import get_brief_engine
    from app.core import config as config_mod
    from app.services.llm_gateway import MockProvider

    monkeypatch.setattr(config_mod.settings, "brief_credit_cost", 3)

    engine = _engine_with(_FakeGatewayHttpErrorSentinel())
    a = FastAPI()
    a.include_router(brief_router)
    a.dependency_overrides[get_brief_engine] = lambda: engine
    client = TestClient(a, raise_server_exceptions=False)

    user_id, headers = _new_user()
    before = balance_for(user_id)[0]
    session_id = _open(client, user_id, headers)

    r = _send(client, headers, session_id)
    assert r.status_code == 200
    assert "AMI error" not in r.text
    lower = r.text.lower()
    assert "vllm" not in lower
    assert "503" not in r.text
    assert "backend logs" not in lower
    assert MockProvider._CANNED["concierge"][:40] in r.text.replace("\\n", "\n")
    assert balance_for(user_id)[0] == before, (
        "an HTTP-error-sentinel reply must be refunded, not billed as a "
        "successful turn"
    )

    kinds = [e.event_type for e in _ledger(user_id)]
    assert kinds.count("credits_spent") == 1
    assert kinds.count("credits_refunded") == 1


def test_a_zero_price_turn_is_still_a_charge(client, monkeypatch):
    """Same property DEF113 pins for 1-on-1: at price 0 the full spend() path
    must still run, so moving the price stays a config change."""
    from app.core import config as config_mod
    monkeypatch.setattr(config_mod.settings, "brief_credit_cost", 0)

    user_id, headers = _new_user()
    before = balance_for(user_id)[0]
    session_id = _open(client, user_id, headers)

    assert _send(client, headers, session_id).status_code == 200
    assert balance_for(user_id)[0] == before
    spent = [e for e in _ledger(user_id) if e.event_type == "credits_spent"]
    assert len(spent) == 1, "spend() must run even at price 0"
