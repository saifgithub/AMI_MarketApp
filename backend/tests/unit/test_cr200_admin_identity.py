"""CR200 — admin identity resolution: CF Access JWT path + bearer fallback.

Covers:
  - resolve_admin_identity: bearer match/mismatch, CF email claim, CF
    service-token common_name claim, invalid CF JWT falling through to
    bearer, half-configured CF settings disabling the CF path
  - get_admin endpoint behaviour through a real route: CF header accepted,
    503 only when NEITHER auth path is configured
"""

from __future__ import annotations

import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwk, jwt

from app.api.admin import router as admin_router
from app.core.config import settings
from app.services import cf_access
from app.services.cf_access import build_cf_access_verifier, resolve_admin_identity

_TEAM = "https://testteam.cloudflareaccess.com"
_AUD = "aud-tag-cr200"
_SECRET = "test-admin-secret-abc123"


def _gen_rsa() -> tuple[rsa.RSAPrivateKey, dict]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    public_jwk = jwk.construct(public_pem.decode(), algorithm="RS256").to_dict()
    for k, v in list(public_jwk.items()):
        if isinstance(v, bytes):
            public_jwk[k] = v.decode()
    public_jwk["kid"] = "cf-kid-1"
    public_jwk["alg"] = "RS256"
    public_jwk["use"] = "sig"
    return private_key, public_jwk


def _sign(private_key: rsa.RSAPrivateKey, claims: dict) -> str:
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    return jwt.encode(claims, pem, algorithm="RS256", headers={"kid": "cf-kid-1"})


@pytest.fixture
def cf_configured(monkeypatch: pytest.MonkeyPatch):
    """CF settings set + a seeded verifier; yields the signing key."""
    monkeypatch.setattr(settings, "cf_access_team_domain", _TEAM)
    monkeypatch.setattr(settings, "cf_access_aud", _AUD)
    monkeypatch.setattr(settings, "admin_secret", _SECRET)
    private_key, public_jwk = _gen_rsa()
    verifier = build_cf_access_verifier(_TEAM, _AUD)
    verifier._seed_jwks_for_test({public_jwk["kid"]: public_jwk})
    monkeypatch.setattr(cf_access, "_cached_verifier", lambda: verifier)
    return private_key


def _cf_claims(**extra) -> dict:
    return {
        "iss": _TEAM,
        "aud": _AUD,
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
        **extra,
    }


# ── resolve_admin_identity ───────────────────────────────────────────────


def test_bearer_match(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_secret", _SECRET)
    identity = resolve_admin_identity(None, f"Bearer {_SECRET}")
    assert identity is not None
    assert identity.kind == "static_bearer"
    assert identity.operator == "static_bearer"


def test_bearer_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_secret", _SECRET)
    assert resolve_admin_identity(None, "Bearer wrong") is None


def test_cf_email_claim(cf_configured) -> None:
    token = _sign(cf_configured, _cf_claims(email="saiful@example.com"))
    identity = resolve_admin_identity(token, None)
    assert identity is not None
    assert identity.kind == "cf_email"
    assert identity.operator == "saiful@example.com"


def test_cf_service_token_common_name(cf_configured) -> None:
    token = _sign(cf_configured, _cf_claims(common_name="claude-agents"))
    identity = resolve_admin_identity(token, None)
    assert identity is not None
    assert identity.kind == "cf_service"
    assert identity.operator == "claude-agents"


def test_invalid_cf_jwt_falls_through_to_bearer(cf_configured) -> None:
    token = _sign(cf_configured, _cf_claims(email="x@y.com", aud="wrong-aud"))
    identity = resolve_admin_identity(token, f"Bearer {_SECRET}")
    assert identity is not None
    assert identity.kind == "static_bearer"


def test_invalid_cf_jwt_alone_is_rejected(cf_configured) -> None:
    token = _sign(cf_configured, _cf_claims(email="x@y.com", aud="wrong-aud"))
    assert resolve_admin_identity(token, None) is None


def test_half_configured_disables_cf_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "cf_access_team_domain", _TEAM)
    monkeypatch.setattr(settings, "cf_access_aud", "")
    cf_access.reset_cf_access_verifier_cache()
    try:
        assert cf_access._cached_verifier() is None
    finally:
        cf_access.reset_cf_access_verifier_cache()


# ── get_admin through a real route ───────────────────────────────────────


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(admin_router)
    return TestClient(app, raise_server_exceptions=False)


def test_route_accepts_cf_header(cf_configured, client: TestClient) -> None:
    token = _sign(cf_configured, _cf_claims(email="saiful@example.com"))
    r = client.get(
        "/v1/admin/users?email=nobody@example.com",
        headers={"Cf-Access-Jwt-Assertion": token},
    )
    assert r.status_code == 200


def test_route_503_only_when_nothing_configured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "admin_secret", "")
    monkeypatch.setattr(settings, "cf_access_team_domain", "")
    monkeypatch.setattr(settings, "cf_access_aud", "")
    r = client.get("/v1/admin/users?email=x@y.com")
    assert r.status_code == 503
