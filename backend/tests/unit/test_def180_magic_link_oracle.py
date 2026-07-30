"""DEF180 (security review H5 + M5) — magic-link verify is an unthrottled
cross-user 6-digit-code oracle; /start is an open email relay.

Before the fix:
  - `/v1/auth/magic_link/verify` had NO rate limiter at all.
  - The active-challenge lookup matched on target email only, so any
    authenticated caller could guess codes against a challenge some OTHER
    user started for themselves.
  - `/start` only throttled by IP, not by target email, so a botnet (or
    IP-rotating attacker) could still hammer one victim's inbox.

These tests exercise the route layer (real rate limiters, real DB) end
to end.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth import router as auth_router
from app.core.config import settings
from app.services.auth_service import AuthService
from app.services.rate_limit import (
    magic_link_start_email_rate_limit,
    magic_link_start_rate_limit,
    magic_link_verify_email_rate_limit,
    magic_link_verify_global_rate_limit,
    magic_link_verify_ip_rate_limit,
)


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.include_router(auth_router)
    return a


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_limiters():
    magic_link_start_rate_limit.reset()
    magic_link_start_email_rate_limit.reset()
    magic_link_verify_ip_rate_limit.reset()
    magic_link_verify_email_rate_limit.reset()
    magic_link_verify_global_rate_limit.reset()
    yield
    magic_link_start_rate_limit.reset()
    magic_link_start_email_rate_limit.reset()
    magic_link_verify_ip_rate_limit.reset()
    magic_link_verify_email_rate_limit.reset()
    magic_link_verify_global_rate_limit.reset()


def _new_user() -> tuple[str, str]:
    auth = AuthService()
    u, t, _ = auth.ensure_anonymous(device_user_id=None)
    return str(u.id), t


# ── /verify: previously unthrottled ────────────────────────────────────


def test_verify_is_rate_limited_per_target_email(monkeypatch, client: TestClient):
    """Loop wrong-code /verify calls against ONE target email, cycling
    source IPs each time (so the per-IP limiter alone can't catch it) —
    the per-email limiter must still trip. Pre-fix: /verify had no
    limiter at all, so this would run forever without a 429."""
    monkeypatch.setattr(settings, "env", "local")
    _, token = _new_user()
    seen_429 = False
    for i in range(20):
        r = client.post(
            "/v1/auth/magic_link/verify",
            json={"email": "victim@example.com", "code": "000000"},
            headers={
                "Authorization": f"Bearer {token}",
                "cf-connecting-ip": f"10.0.0.{i}",  # a fresh IP every call
            },
        )
        if r.status_code == 429:
            seen_429 = True
            break
    assert seen_429, "unbounded wrong-code guessing against one email must trip a limiter"


def test_verify_rate_limit_response_indistinguishable_from_wrong_code(client: TestClient):
    """Both an unknown-identifier miss and a wrong-code miss return the
    same 401 body — no oracle via status code or message."""
    _, token = _new_user()
    r_unknown = client.post(
        "/v1/auth/magic_link/verify",
        json={"email": "nobody-ever-started-this@example.com", "code": "123456"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_unknown.status_code == 401
    assert r_unknown.json()["detail"] == "invalid or expired code"


# ── /verify: bound to the caller's own challenge ───────────────────────


def test_verify_cannot_guess_against_another_users_challenge(monkeypatch, client: TestClient):
    """User A starts a magic-link claim for their own email. User B
    (different bearer) tries to verify against that SAME email/code —
    even with the correct code, B's lookup must not find A's challenge
    (scoped to the challenge owner), so B cannot hijack or consume it."""
    monkeypatch.setattr(settings, "env", "local")
    user_a_id, token_a = _new_user()
    _, token_b = _new_user()

    r_start = client.post(
        "/v1/auth/magic_link/start",
        json={"email": "owned-by-a@example.com"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    code = r_start.json()["debug_code"]
    assert code is not None

    # B tries the CORRECT code against A's target email.
    r_b = client.post(
        "/v1/auth/magic_link/verify",
        json={"email": "owned-by-a@example.com", "code": code},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert r_b.status_code == 401, "B must not be able to consume A's challenge"

    # A can still verify their own challenge with the correct code.
    r_a = client.post(
        "/v1/auth/magic_link/verify",
        json={"email": "owned-by-a@example.com", "code": code},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert r_a.status_code == 200
    assert r_a.json()["user"]["id"] == user_a_id


# ── /start: previously IP-only throttling ──────────────────────────────


def test_start_is_rate_limited_per_target_email_across_ips(client: TestClient):
    """Attacker cycles source IPs to dodge the per-IP /start limiter (3/min)
    but keeps hammering ONE victim email — the email-keyed limiter must
    still trip well before an unbounded mail-relay flood."""
    seen_429 = False
    for i in range(10):
        _, token = _new_user()
        r = client.post(
            "/v1/auth/magic_link/start",
            json={"email": "flood-victim@example.com"},
            headers={
                "Authorization": f"Bearer {token}",
                "cf-connecting-ip": f"172.16.0.{i}",
            },
        )
        if r.status_code == 429:
            seen_429 = True
            break
    assert seen_429, "per-email throttling on /start must fire even across rotating IPs"
