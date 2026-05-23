"""Tests for OIDCVerifier — Apple's JWKS-backed identity-token verifier.

Mints a real RSA keypair per test, signs a JWT with python-jose, seeds the
verifier's JWKS cache with the public half, then verifies the token end-to-
end. Covers: happy path, expired token, wrong audience, wrong issuer,
unknown kid (key rotation), tampered signature, malformed token.

The JWKS HTTP fetch is bypassed via OIDCVerifier._seed_jwks_for_test —
real key rotation behaviour (cache miss → refresh) is covered by patching
httpx in a dedicated test.
"""

from __future__ import annotations

import base64
import json
import time
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwk, jwt

from app.services.oidc_verifier import OIDCVerificationError, OIDCVerifier


# ── helpers ──────────────────────────────────────────────────────────────


def _gen_rsa() -> tuple[rsa.RSAPrivateKey, dict]:
    """Return (private_key, jwk_dict_with_kid). jwk_dict carries only the
    public components needed to populate a JWKS endpoint."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    public_jwk = jwk.construct(public_pem.decode(), algorithm="RS256").to_dict()
    # Some jose versions return bytes for n/e; normalize to str so json
    # serialization works the same as the real Apple JWKS endpoint.
    for k, v in list(public_jwk.items()):
        if isinstance(v, bytes):
            public_jwk[k] = v.decode()
    public_jwk["kid"] = "test-kid-1"
    public_jwk["alg"] = "RS256"
    public_jwk["use"] = "sig"
    return private_key, public_jwk


def _sign(private_key: rsa.RSAPrivateKey, claims: dict, kid: str = "test-kid-1") -> str:
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    return jwt.encode(claims, pem, algorithm="RS256", headers={"kid": kid})


def _fresh_verifier(audiences: list[str] | None = None) -> tuple[OIDCVerifier, rsa.RSAPrivateKey, dict]:
    private_key, public_jwk = _gen_rsa()
    verifier = OIDCVerifier(
        jwks_uri="https://example.invalid/jwks",  # never hit in seeded tests
        issuers=["https://appleid.apple.com"],
        audiences=audiences or ["ai.agenticmarketintel.amiTrade"],
    )
    verifier._seed_jwks_for_test({public_jwk["kid"]: public_jwk})
    return verifier, private_key, public_jwk


# ── happy path + claim extraction ────────────────────────────────────────


def test_verify_happy_path_returns_claims():
    verifier, priv, _ = _fresh_verifier()
    token = _sign(
        priv,
        {
            "iss": "https://appleid.apple.com",
            "aud": "ai.agenticmarketintel.amiTrade",
            "sub": "apple-sub-abc",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
        },
    )
    claims = verifier.verify(token)
    assert claims["sub"] == "apple-sub-abc"


def test_verify_accepts_multiple_audiences():
    """Audience list is configurable for the future Web Services ID case."""
    verifier, priv, _ = _fresh_verifier(
        audiences=["ai.agenticmarketintel.amiTrade", "ai.agenticmarketintel.web"],
    )
    token = _sign(
        priv,
        {
            "iss": "https://appleid.apple.com",
            "aud": "ai.agenticmarketintel.web",
            "sub": "apple-sub-web",
            "exp": int(time.time()) + 3600,
        },
    )
    claims = verifier.verify(token)
    assert claims["sub"] == "apple-sub-web"


# ── rejection cases ──────────────────────────────────────────────────────


def test_verify_rejects_expired_token():
    verifier, priv, _ = _fresh_verifier()
    token = _sign(
        priv,
        {
            "iss": "https://appleid.apple.com",
            "aud": "ai.agenticmarketintel.amiTrade",
            "sub": "apple-sub-abc",
            "exp": int(time.time()) - 60,  # expired 60s ago
        },
    )
    with pytest.raises(OIDCVerificationError, match="expired"):
        verifier.verify(token)


def test_verify_rejects_wrong_audience():
    verifier, priv, _ = _fresh_verifier()
    token = _sign(
        priv,
        {
            "iss": "https://appleid.apple.com",
            "aud": "com.someoneelse.app",
            "sub": "apple-sub-abc",
            "exp": int(time.time()) + 3600,
        },
    )
    with pytest.raises(OIDCVerificationError):
        verifier.verify(token)


def test_verify_rejects_wrong_issuer():
    verifier, priv, _ = _fresh_verifier()
    token = _sign(
        priv,
        {
            "iss": "https://evil.example.com",
            "aud": "ai.agenticmarketintel.amiTrade",
            "sub": "apple-sub-abc",
            "exp": int(time.time()) + 3600,
        },
    )
    with pytest.raises(OIDCVerificationError):
        verifier.verify(token)


def test_verify_rejects_unknown_kid_after_refresh():
    """When `kid` isn't in cache and refresh-on-miss still doesn't find it,
    verification must fail rather than fall back to no-signature-check."""
    verifier, priv, _ = _fresh_verifier()
    # Sign with a different kid than what's seeded.
    token = _sign(priv, {"sub": "x", "exp": int(time.time()) + 60}, kid="unknown-kid")

    # Mock the refresh path: return an empty JWKS, mimicking Apple returning
    # a set that doesn't include `unknown-kid`. The verifier must not silently
    # accept the token.
    with patch("app.services.oidc_verifier.httpx.Client") as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value.json.return_value = {
            "keys": []
        }
        mock_client.return_value.__enter__.return_value.get.return_value.raise_for_status.return_value = None
        with pytest.raises(OIDCVerificationError, match="no matching JWK"):
            verifier.verify(token)


def test_verify_rejects_tampered_signature():
    verifier, priv, _ = _fresh_verifier()
    token = _sign(
        priv,
        {
            "iss": "https://appleid.apple.com",
            "aud": "ai.agenticmarketintel.amiTrade",
            "sub": "apple-sub-abc",
            "exp": int(time.time()) + 3600,
        },
    )
    # Flip a char in the middle of the signature segment. (The last
    # base64url char can carry fewer than 6 significant bits, so flipping
    # it is sometimes a no-op — flipping mid-segment always changes the
    # decoded bytes.)
    head, body, sig = token.split(".")
    mid = len(sig) // 2
    flipped = "B" if sig[mid] != "B" else "C"
    tampered = f"{head}.{body}.{sig[:mid]}{flipped}{sig[mid + 1:]}"
    with pytest.raises(OIDCVerificationError):
        verifier.verify(tampered)


def test_verify_rejects_malformed_token():
    verifier, _, _ = _fresh_verifier()
    for bogus in ["", "abc", "abc.def", "not.a.jwt.at.all"]:
        with pytest.raises(OIDCVerificationError):
            verifier.verify(bogus)


def test_verify_rejects_header_missing_kid():
    """A token signed without a `kid` header can't be looked up in JWKS — Apple
    always emits a kid so any token without one is suspect."""
    verifier, priv, _ = _fresh_verifier()
    # Mint a token via low-level encode that omits kid.
    pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    token = jwt.encode({"sub": "x"}, pem, algorithm="RS256")  # no headers kw → no kid
    with pytest.raises(OIDCVerificationError, match="kid"):
        verifier.verify(token)


# ── JWKS cache behaviour ─────────────────────────────────────────────────


def test_jwks_cache_refreshes_on_kid_miss():
    """When a new kid appears (Apple key rotation), the verifier should
    refresh JWKS once before failing — gives us automatic rotation handling."""
    private_key, public_jwk = _gen_rsa()
    public_jwk["kid"] = "rotated-kid"

    verifier = OIDCVerifier(
        jwks_uri="https://example.invalid/jwks",
        issuers=["https://appleid.apple.com"],
        audiences=["ai.agenticmarketintel.amiTrade"],
    )
    # Seed with the OLD key (different kid). The verifier should refresh on
    # miss and find the new one.
    verifier._seed_jwks_for_test({"old-kid": {"kid": "old-kid"}})

    token = _sign(
        private_key,
        {
            "iss": "https://appleid.apple.com",
            "aud": "ai.agenticmarketintel.amiTrade",
            "sub": "rotated-sub",
            "exp": int(time.time()) + 3600,
        },
        kid="rotated-kid",
    )

    fake_jwks = {"keys": [public_jwk]}
    with patch("app.services.oidc_verifier.httpx.Client") as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value.json.return_value = fake_jwks
        mock_client.return_value.__enter__.return_value.get.return_value.raise_for_status.return_value = None
        claims = verifier.verify(token)
        assert claims["sub"] == "rotated-sub"
        # The mock should have been hit (refresh happened).
        assert mock_client.called
