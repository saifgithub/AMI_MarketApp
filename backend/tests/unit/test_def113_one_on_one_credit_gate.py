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

def test_alpha_default_price_is_zero():
    from app.core.config import settings
    assert settings.one_on_one_credit_cost == 0
    assert one_on_one_cost() == 0


def test_zero_price_turn_still_writes_a_ledger_row_and_returns_200(client):
    """The dangerous part of this lane: a price of 0 must still run spend()'s
    full path — ledger row written, balance arithmetic executed — a charge
    of zero, not a skipped charge. Otherwise flipping the price later is a
    new code path, not a config change."""
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
