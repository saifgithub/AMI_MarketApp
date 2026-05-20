"""Tests for the anonymous-first auth scaffold."""

from __future__ import annotations

import base64
import json
from uuid import uuid4

import pytest

from app.services.auth_service import AuthService
from app.services.oidc_verifier import OIDCVerificationError


def _apple_jwt(sub: str) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"RS256","kid":"abc"}').rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(json.dumps({"sub": sub}).encode()).rstrip(b"=").decode()
    sig = base64.urlsafe_b64encode(b"sig").rstrip(b"=").decode()
    return f"{header}.{body}.{sig}"


class _FakeAppleVerifier:
    """Test double for OIDCVerifier — reads `sub` from the body, no signature
    or claim verification. Lets the existing Apple sign-in tests focus on the
    claim → user-row glue instead of having to mint real RSA-signed JWTs.
    Real JWKS verification is covered separately in test_oidc_verifier.py.
    """

    def verify(self, identity_token: str) -> dict:
        if not identity_token or identity_token.count(".") != 2:
            raise OIDCVerificationError("malformed identity token")
        try:
            _hdr, body, _sig = identity_token.split(".")
            padding = "=" * (-len(body) % 4)
            payload = json.loads(base64.urlsafe_b64decode(body + padding).decode())
        except Exception as e:
            raise OIDCVerificationError(f"undecodable body: {e}") from e
        return payload


def test_anon_session_reuses_device_user_id_only_with_matching_bearer():
    """A2 (adversarial audit 2026-05-18): device_user_id alone is no longer
    proof of possession. Cold rebootstrap without a valid bearer always
    mints a fresh user. The same user is only reused when the caller
    presents a Bearer whose parsed user_id matches device_user_id.
    """
    auth = AuthService()
    user1, token1, is_new1 = auth.ensure_anonymous(device_user_id=None)
    # Re-bootstrap WITHOUT the matching bearer — should mint fresh, ignore device_id.
    user2, _, _ = auth.ensure_anonymous(device_user_id=user1.id)
    assert user2.id != user1.id, "device_user_id alone must not reuse the row"
    # Re-bootstrap WITH the matching bearer — should reuse the original row.
    user3, token3, is_new3 = auth.ensure_anonymous(
        device_user_id=user1.id,
        authenticated_user_id=user1.id,
    )
    assert user3.id == user1.id
    assert token3 == token1
    assert is_new1 is True
    assert is_new3 is False
    assert user1.is_anonymous is True


def test_anon_session_creates_new_id_if_unset():
    auth = AuthService()
    user, token, is_new = auth.ensure_anonymous(device_user_id=None)
    assert is_new is True
    assert user.is_anonymous is True
    assert token.startswith("scaffold:")


def test_magic_link_round_trip():
    auth = AuthService()
    user_id = uuid4()
    # bootstrap anon user first
    auth.ensure_anonymous(device_user_id=user_id)

    code = auth.start_magic_link(email="alpha@example.com", user_id=user_id)
    result = auth.verify_magic_link(
        email="alpha@example.com", code=code, user_id=user_id,
    )
    assert result is not None
    user, token = result
    assert user.id == user_id
    assert user.email == "alpha@example.com"
    assert user.is_anonymous is False
    assert user.claimed_at is not None
    assert token.startswith("scaffold:")


def test_magic_link_wrong_code_fails():
    auth = AuthService()
    auth.start_magic_link(email="beta@example.com", user_id=None)
    assert auth.verify_magic_link(
        email="beta@example.com", code="000000", user_id=None,
    ) is None


def test_magic_link_consumed_once():
    auth = AuthService()
    code = auth.start_magic_link(email="gamma@example.com", user_id=None)
    first = auth.verify_magic_link(email="gamma@example.com", code=code, user_id=None)
    assert first is not None
    second = auth.verify_magic_link(email="gamma@example.com", code=code, user_id=None)
    assert second is None  # consumed


def test_apple_claim_attaches_sub_to_user():
    auth = AuthService(apple_verifier=_FakeAppleVerifier())
    user_id = uuid4()
    auth.ensure_anonymous(device_user_id=user_id)
    user, token = auth.sign_in_with_apple(
        identity_token=_apple_jwt("apple-sub-123"),
        user_id=user_id,
    )
    assert user.id == user_id
    assert user.apple_id == "apple-sub-123"
    assert user.is_anonymous is False
    assert user.claimed_at is not None


def test_apple_rejects_undecodable_jwt():
    auth = AuthService(apple_verifier=_FakeAppleVerifier())
    with pytest.raises(ValueError):
        auth.sign_in_with_apple(identity_token="not-a-jwt", user_id=None)
