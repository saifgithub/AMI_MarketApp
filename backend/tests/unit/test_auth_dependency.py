"""Tests for the get_current_user dependency + route-level auth guards.

Covers the three core auth outcomes on a protected route:
  401 — no token, malformed token, forged HMAC, unknown user
  403 — valid token but caller_id != path user_id (ownership)
  200 — valid token and caller owns the resource

Uses the live mandate router as the smoke route since it has the simplest
shape (single user_id path param, both GET and PATCH).
"""

from __future__ import annotations

import hmac as _hmac
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.mandate import router as mandate_router
from app.core.config import settings
from app.services.auth_service import AuthService, _scaffold_token, parse_scaffold_token


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(mandate_router)
    return TestClient(app)


def _make_user() -> tuple[UUID, str]:
    """Create an anonymous user in the DB and return (user_id, bearer_token).

    Post adversarial-audit A2: a cold call to `ensure_anonymous` without a
    valid bearer token always mints a fresh user, so the returned user_id
    is the one the service created (not the device_user_id we passed in).
    """
    auth = AuthService()
    user, token, _ = auth.ensure_anonymous(device_user_id=None)
    return user.id, token


# ── parse_scaffold_token ─────────────────────────────────────────────────


def test_parse_scaffold_token_round_trip():
    user_id = uuid4()
    token = _scaffold_token(user_id, token_version=1)
    parsed = parse_scaffold_token(token)
    assert parsed is not None
    assert parsed.user_id == user_id
    assert parsed.token_version == 1


def test_parse_scaffold_token_rejects_forged_hmac():
    """A well-formed CR125 token (4 parts) with a tampered signature."""
    user_id = uuid4()
    exp = int(datetime.now(timezone.utc).timestamp()) + 86400
    forged = f"scaffold:{user_id.hex}:{exp}:1:" + ("0" * 64)
    assert parse_scaffold_token(forged) is None


def test_parse_scaffold_token_rejects_tampered_exp():
    """Rewriting `exp` upward without re-signing must fail — the HMAC covers
    exp, not just the user_id hex."""
    user_id = uuid4()
    token = _scaffold_token(user_id, token_version=1)
    hex_id, exp, ver, sig = token.removeprefix("scaffold:").split(":")
    tampered = f"scaffold:{hex_id}:{int(exp) + 999999}:{ver}:{sig}"
    assert parse_scaffold_token(tampered) is None


def test_parse_scaffold_token_rejects_tampered_version():
    """Rewriting `ver` without re-signing must fail — a stolen token can't be
    replayed against a bumped token_version by just editing the field."""
    user_id = uuid4()
    token = _scaffold_token(user_id, token_version=1)
    hex_id, exp, ver, sig = token.removeprefix("scaffold:").split(":")
    tampered = f"scaffold:{hex_id}:{exp}:{int(ver) + 1}:{sig}"
    assert parse_scaffold_token(tampered) is None


def test_parse_scaffold_token_rejects_expired():
    user_id = uuid4()
    token = _scaffold_token(user_id, token_version=1, ttl_days=-1)
    assert parse_scaffold_token(token) is None


def test_parse_scaffold_token_rejects_old_3part_signed_format():
    """CR040 degrade-loudly: the pre-CR125 signed format (no exp/version)
    is rejected outright, not silently accepted. A stale token 401s."""
    user_id = uuid4()
    sig = _hmac.new(
        settings.secret_key.encode("utf-8"),
        user_id.hex.encode("utf-8"),
        "sha256",
    ).hexdigest()
    old_format = f"scaffold:{user_id.hex}:{sig}"
    assert parse_scaffold_token(old_format) is None


def test_parse_scaffold_token_rejects_malformed():
    assert parse_scaffold_token("") is None
    assert parse_scaffold_token("garbage") is None
    assert parse_scaffold_token("scaffold:") is None
    assert parse_scaffold_token("scaffold:not-a-uuid:sig") is None


def test_parse_scaffold_token_accepts_legacy_in_dev():
    """During the migration window dev env accepts the old `scaffold:<hex>` form.

    Tests run with env=local by default (Settings default), so legacy works.
    No version field exists in this format — token_version comes back None.
    """
    user_id = uuid4()
    legacy = f"scaffold:{user_id.hex}"
    parsed = parse_scaffold_token(legacy)
    assert parsed is not None
    assert parsed.user_id == user_id
    assert parsed.token_version is None


# ── route guard: 401 paths ───────────────────────────────────────────────


def test_no_token_returns_401(client: TestClient):
    user_id = uuid4()
    r = client.get(f"/v1/mandate/{user_id}")
    assert r.status_code == 401
    assert "authentication required" in r.json()["detail"]


def test_invalid_token_returns_401(client: TestClient):
    user_id = uuid4()
    r = client.get(
        f"/v1/mandate/{user_id}",
        headers={"Authorization": "Bearer garbage"},
    )
    assert r.status_code == 401


def test_forged_hmac_returns_401(client: TestClient):
    user_id = uuid4()
    forged = f"scaffold:{user_id.hex}:" + ("0" * 64)
    r = client.get(
        f"/v1/mandate/{user_id}",
        headers={"Authorization": f"Bearer {forged}"},
    )
    assert r.status_code == 401


def test_token_for_nonexistent_user_returns_401(client: TestClient):
    """Valid HMAC but no user row in DB."""
    ghost_id = uuid4()
    token = _scaffold_token(ghost_id, token_version=1)
    r = client.get(
        f"/v1/mandate/{ghost_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 401


# ── route guard: 403 (ownership) ─────────────────────────────────────────


def test_wrong_user_returns_403(client: TestClient):
    """Caller is authenticated as user A but asks for user B's mandate."""
    user_a, token_a = _make_user()
    user_b, _ = _make_user()
    r = client.get(
        f"/v1/mandate/{user_b}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert r.status_code == 403
    assert "access denied" in r.json()["detail"]


def test_wrong_user_patch_returns_403(client: TestClient):
    user_a, token_a = _make_user()
    user_b, _ = _make_user()
    r = client.patch(
        f"/v1/mandate/{user_b}",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"max_drawdown_pct": 5.0},
    )
    assert r.status_code == 403


# ── route guard: 200 (happy path) ────────────────────────────────────────


def test_correct_user_returns_200(client: TestClient):
    user_id, token = _make_user()
    r = client.get(
        f"/v1/mandate/{user_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "max_drawdown_pct" in body


def test_correct_user_patch_returns_200(client: TestClient):
    user_id, token = _make_user()
    r = client.patch(
        f"/v1/mandate/{user_id}",
        headers={"Authorization": f"Bearer {token}"},
        # DEF062: must be one of the schema's Literal[10,20,30,50,100] values —
        # 8.0 (the prior value here) only ever "worked" because the route had
        # no validation and would have silently persisted it.
        json={"max_drawdown_pct": 20},
    )
    assert r.status_code == 200
    assert r.json()["max_drawdown_pct"] == 20
