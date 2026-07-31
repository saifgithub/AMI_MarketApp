"""DEF201 (H6 follow-up to DEF186) — per-user CONCURRENCY cap on 1-on-1 +
Brief SSE streams, shared across both surfaces.

DEF186 rate-limited these routes to 12/min/user, which bounds pace, not how
many turns one account can have in flight AT ONCE — nothing stopped a
scripted client opening many simultaneous streams, each burning a full LLM
turn's worth of compute for the run's duration, all comfortably under the
per-minute ceiling. `ConcurrencyLimiter` (app/services/rate_limit.py) closes
that: acquire before the stream starts, release in a `finally` covering
success, in-stream error, and (via DEF113's existing except path)
insufficient-credits — a leaked acquire on any of those would permanently
steal one of the user's slots.

Three layers, per this project's own conventions for a shared primitive:
  1. `ConcurrencyLimiter`'s own contract, in isolation.
  2. Each route (`one_on_one.py`, `brief.py`) actually calls it.
  3. Both routes share ONE instance/keyspace — filling it via a direct
     acquire on the imported object blocks either route for that user.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.brief import router as brief_router
from app.api.one_on_one import router as one_on_one_router
from app.api.dependencies import get_current_user
from app.db.models import User
from app.services.auth_service import AuthService
from app.services.rate_limit import (
    ConcurrencyLimiter,
    agent_stream_concurrency_limit,
    brief_message_rate_limit,
    one_on_one_message_rate_limit,
)


@pytest.fixture(autouse=True)
def _reset_all():
    agent_stream_concurrency_limit.reset()
    one_on_one_message_rate_limit.reset()
    brief_message_rate_limit.reset()
    yield
    agent_stream_concurrency_limit.reset()
    one_on_one_message_rate_limit.reset()
    brief_message_rate_limit.reset()


# ── 1. ConcurrencyLimiter's own contract ─────────────────────────────────


def test_allows_up_to_the_cap_then_429s():
    lim = ConcurrencyLimiter(name="t1", max_concurrent=2)
    lim.acquire("k")
    lim.acquire("k")
    with pytest.raises(Exception) as exc:
        lim.acquire("k")
    assert "429" in str(exc.value) or "concurrency_limit_exceeded" in str(exc.value)


def test_release_frees_a_slot_for_reacquire():
    lim = ConcurrencyLimiter(name="t2", max_concurrent=1)
    lim.acquire("k")
    with pytest.raises(Exception):
        lim.acquire("k")
    lim.release("k")
    lim.acquire("k")  # must not raise — the release freed the slot


def test_keys_are_independent():
    lim = ConcurrencyLimiter(name="t3", max_concurrent=1)
    lim.acquire("a")
    lim.acquire("b")  # different key — must not raise


def test_over_release_is_a_safe_no_op():
    lim = ConcurrencyLimiter(name="t4", max_concurrent=1)
    lim.release("never-acquired")  # must not raise
    lim.acquire("k")
    lim.release("k")
    lim.release("k")  # second release of the same key — still must not raise
    lim.acquire("k")  # and the count must not have gone negative/wrapped


def test_reset_clears_all_keys():
    lim = ConcurrencyLimiter(name="t5", max_concurrent=1)
    lim.acquire("k")
    lim.reset()
    lim.acquire("k")  # must not raise post-reset


# ── 2 + 3. Real routes, real wiring, shared instance ─────────────────────


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.include_router(one_on_one_router)
    a.include_router(brief_router)
    return a


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def _new_real_user() -> tuple[str, dict]:
    """A real persisted user — one_on_one.py's spend() does `s.get(User,
    user_id)` and raises LookupError on a fake/unpersisted id, so the
    lightweight dependency-override fakes used elsewhere in this suite
    don't reach this route's concurrency-check line."""
    auth = AuthService()
    user, token, _ = auth.ensure_anonymous(device_user_id=None)
    return user.id, {"Authorization": f"Bearer {token}"}


def _open_one_on_one(client: TestClient, headers: dict) -> str:
    r = client.post(
        "/v1/agents/one_on_one/start",
        json={"agent_id": "concierge"},  # always free — DEF179's lock gate
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_one_on_one_message_is_blocked_at_the_concurrency_cap(client, monkeypatch):
    monkeypatch.setattr(agent_stream_concurrency_limit, "max_concurrent", 2)

    user_id, headers = _new_real_user()
    session_id = _open_one_on_one(client, headers)
    key = f"user:{user_id}"
    # Pre-load the shared limiter to its cap directly — the honest way to
    # simulate "already has streams open" without needing two real
    # concurrent HTTP connections against a synchronous TestClient.
    agent_stream_concurrency_limit.acquire(key)
    agent_stream_concurrency_limit.acquire(key)

    r = client.post(
        "/v1/agents/one_on_one/message",
        json={"session_id": session_id, "user_message": "hi"},
        headers=headers,
    )
    assert r.status_code == 429
    assert "concurrency_limit_exceeded" in r.json()["detail"]


def test_one_on_one_message_succeeds_once_a_slot_is_released(client, monkeypatch):
    monkeypatch.setattr(agent_stream_concurrency_limit, "max_concurrent", 1)

    user_id, headers = _new_real_user()
    session_id = _open_one_on_one(client, headers)
    key = f"user:{user_id}"
    agent_stream_concurrency_limit.acquire(key)
    assert client.post(
        "/v1/agents/one_on_one/message",
        json={"session_id": session_id, "user_message": "hi"},
        headers=headers,
    ).status_code == 429

    agent_stream_concurrency_limit.release(key)
    r = client.post(
        "/v1/agents/one_on_one/message",
        json={"session_id": session_id, "user_message": "hi"},
        headers=headers,
    )
    assert r.status_code == 200, r.text


def test_one_on_one_sequential_requests_never_leak_a_slot(client, monkeypatch):
    """DEF201 mutation guard: if the `finally` release were ever dropped, a
    single slot at cap=1 would only ever serve ONE request before every
    subsequent one 429s. Five sequential requests all succeeding proves
    each one releases before the next starts."""
    monkeypatch.setattr(agent_stream_concurrency_limit, "max_concurrent", 1)

    _, headers = _new_real_user()
    session_id = _open_one_on_one(client, headers)
    for _ in range(5):
        r = client.post(
            "/v1/agents/one_on_one/message",
            json={"session_id": session_id, "user_message": "hi"},
            headers=headers,
        )
        assert r.status_code == 200, r.text


def test_402_insufficient_credits_releases_the_slot_rather_than_leaking_it(
    client, monkeypatch,
):
    """The generator (whose `finally` normally releases) never runs on a
    402 — spend() raises before the StreamingResponse is even constructed.
    DEF201 added an explicit release on that except path; this proves it,
    not just that a 402 happens (test_def113 already covers that)."""
    from app.core import config as config_mod
    from app.db import get_session

    monkeypatch.setattr(agent_stream_concurrency_limit, "max_concurrent", 1)
    monkeypatch.setattr(config_mod.settings, "one_on_one_credit_cost", 3)

    user_id, headers = _new_real_user()
    from app.services.credit_service import balance_for
    balance_for(user_id)  # establish the allowance window
    with get_session() as s:
        s.get(User, user_id).credit_balance = 0
    session_id = _open_one_on_one(client, headers)

    r = client.post(
        "/v1/agents/one_on_one/message",
        json={"session_id": session_id, "user_message": "hi"},
        headers=headers,
    )
    assert r.status_code == 402

    # If the 402 path leaked its acquire, this would 429 at cap=1.
    monkeypatch.setattr(config_mod.settings, "one_on_one_credit_cost", 0)
    r2 = client.post(
        "/v1/agents/one_on_one/message",
        json={"session_id": session_id, "user_message": "hi"},
        headers=headers,
    )
    assert r2.status_code == 200, r2.text


def test_a_non_402_spend_failure_releases_the_slot_rather_than_leaking_it(
    client, monkeypatch,
):
    """AUDIT M2 (round 1). `spend()` opens a session, loads the user and
    commits, so it can raise anything the DB can raise. An OperationalError is
    NOT an InsufficientCredits: pre-fix it escaped that handler, the generator
    (whose finally releases) was never created, and the slot leaked with no
    TTL and no eviction — two of them wedge the user at 429 permanently,
    surviving the DB's own recovery.

    Distinct from the 402 test above: that path had an explicit release from
    the start. This one is the fourth path the round-1 audit found."""
    import app.api.one_on_one as one_on_one_mod

    monkeypatch.setattr(agent_stream_concurrency_limit, "max_concurrent", 1)

    _, headers = _new_real_user()
    session_id = _open_one_on_one(client, headers)

    real_spend = one_on_one_mod.spend

    def _boom(*a, **kw):
        raise RuntimeError("simulated DB failure inside spend()")

    one_on_one_mod.spend = _boom
    try:
        # The `client` fixture is raise_server_exceptions=False, so the
        # RuntimeError surfaces as a 500 rather than propagating — which is
        # also what a real deployment does. Either way the route raised, and
        # the generator was never created.
        boom = client.post(
            "/v1/agents/one_on_one/message",
            json={"session_id": session_id, "user_message": "hi"},
            headers=headers,
        )
        assert boom.status_code == 500, boom.text
    finally:
        one_on_one_mod.spend = real_spend

    # Asserted through the CONTRACT, not the private counter: at cap=1, a
    # leaked slot from the failure above makes the very next request 429
    # forever. A 200 here is the proof the slot came back.
    r = client.post(
        "/v1/agents/one_on_one/message",
        json={"session_id": session_id, "user_message": "hi"},
        headers=headers,
    )
    assert r.status_code != 429, (
        "the failed spend leaked its concurrency slot — this user is now "
        "permanently capped at 429 until the process restarts"
    )
    assert r.status_code == 200, r.text


class _Sess:
    def __init__(self, uid):
        self.user_id = uid
        self.id = uuid4()


class _FakeUser:
    def __init__(self, uid):
        self.id = uid


class _FakeBriefEngine:
    """Mirrors DEF127's `_RaisingEngine` shape — brief_message() never
    touches credit_service, so this route doesn't need a real DB user the
    way one_on_one.py's does."""

    def __init__(self, sess):
        self._sess = sess

    def get_session(self, _sid):
        return self._sess

    async def stream_chat(self, *, session, history, user_message):
        yield "hi"


def _brief_client(uid) -> tuple[TestClient, str]:
    from app.services.brief_engine import get_brief_engine

    sess = _Sess(uid)
    app = FastAPI()
    app.include_router(brief_router)
    app.dependency_overrides[get_current_user] = lambda: _FakeUser(uid)
    app.dependency_overrides[get_brief_engine] = lambda: _FakeBriefEngine(sess)
    return TestClient(app, raise_server_exceptions=False), str(sess.id)


def test_brief_message_is_blocked_at_the_concurrency_cap(monkeypatch):
    monkeypatch.setattr(agent_stream_concurrency_limit, "max_concurrent", 1)

    uid = uuid4()
    client, session_id = _brief_client(uid)
    agent_stream_concurrency_limit.acquire(f"user:{uid}")

    r = client.post(
        "/v1/brief/message",
        json={"session_id": session_id, "user_message": "hi"},
    )
    assert r.status_code == 429
    assert "concurrency_limit_exceeded" in r.json()["detail"]


def test_brief_message_releases_its_slot_after_streaming(monkeypatch):
    monkeypatch.setattr(agent_stream_concurrency_limit, "max_concurrent", 1)

    uid = uuid4()
    client, session_id = _brief_client(uid)
    for _ in range(3):
        r = client.post(
            "/v1/brief/message",
            json={"session_id": session_id, "user_message": "hi"},
        )
        assert r.status_code == 200, r.text


def test_the_cap_is_shared_between_one_on_one_and_brief_for_the_same_user(
    client, monkeypatch,
):
    """Not two independent caps that together allow 2x the streams — one
    shared budget per user, regardless of which surface it's spent on."""
    monkeypatch.setattr(agent_stream_concurrency_limit, "max_concurrent", 1)

    user_id, headers = _new_real_user()
    session_id = _open_one_on_one(client, headers)

    # A brief-surface acquire for THIS SAME user_id key must block the
    # one_on_one route too — proving both files check the one shared
    # module-level instance, not two independently-capped counters.
    agent_stream_concurrency_limit.acquire(f"user:{user_id}")
    r = client.post(
        "/v1/agents/one_on_one/message",
        json={"session_id": session_id, "user_message": "hi"},
        headers=headers,
    )
    assert r.status_code == 429
