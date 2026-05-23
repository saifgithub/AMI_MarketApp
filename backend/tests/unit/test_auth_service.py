"""Tests for the anonymous-first auth scaffold."""

from __future__ import annotations

import base64
import json
from uuid import uuid4

import pytest

from app.services.auth_service import AuthService
from app.services.oidc_verifier import OIDCVerificationError


def _apple_jwt(sub: str, *, email: str | None = None) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"RS256","kid":"abc"}').rstrip(b"=").decode()
    payload: dict = {"sub": sub}
    if email is not None:
        payload["email"] = email
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
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
    user, token, adopted = result
    assert user.id == user_id
    assert user.email == "alpha@example.com"
    assert adopted is None  # caller's anon promoted in place, not adopted
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


# ── B-tier audit: brute-force lockout (AT:R37) ──────────────────────────


def test_magic_link_locks_out_after_max_attempts():
    """Five wrong attempts force-consume the active challenge — even the
    correct code can't unlock it after that."""
    from app.services.auth_service import MAX_MAGIC_LINK_ATTEMPTS

    auth = AuthService()
    correct = auth.start_magic_link(
        email="lockout@example.com", user_id=None,
    )
    # Burn the budget on wrong codes.
    for _ in range(MAX_MAGIC_LINK_ATTEMPTS):
        assert auth.verify_magic_link(
            email="lockout@example.com", code="000000", user_id=None,
        ) is None
    # The correct code is now locked out — challenge was force-consumed
    # on the 5th miss.
    assert auth.verify_magic_link(
        email="lockout@example.com", code=correct, user_id=None,
    ) is None


def test_magic_link_attempts_counter_resets_with_new_challenge():
    """Requesting a fresh code mints a new auth_challenges row, so the
    counter starts at zero again. A user who got locked out can always
    recover."""
    from app.services.auth_service import MAX_MAGIC_LINK_ATTEMPTS

    auth = AuthService()
    auth.start_magic_link(email="reset@example.com", user_id=None)
    # Burn the original challenge.
    for _ in range(MAX_MAGIC_LINK_ATTEMPTS):
        auth.verify_magic_link(
            email="reset@example.com", code="000000", user_id=None,
        )
    # Mint a fresh challenge and verify with its code — should succeed.
    new_code = auth.start_magic_link(email="reset@example.com", user_id=None)
    result = auth.verify_magic_link(
        email="reset@example.com", code=new_code, user_id=None,
    )
    assert result is not None
    user, _token, _adopted = result
    assert user.email == "reset@example.com"


def test_magic_link_correct_code_within_budget_still_works():
    """Mistype, then submit the right code — should still succeed."""
    auth = AuthService()
    correct = auth.start_magic_link(
        email="mistype@example.com", user_id=None,
    )
    # Two wrong attempts (well below the 5-attempt cap).
    assert auth.verify_magic_link(
        email="mistype@example.com", code="000000", user_id=None,
    ) is None
    assert auth.verify_magic_link(
        email="mistype@example.com", code="111111", user_id=None,
    ) is None
    result = auth.verify_magic_link(
        email="mistype@example.com", code=correct, user_id=None,
    )
    assert result is not None


def test_apple_claim_attaches_sub_to_user():
    auth = AuthService(apple_verifier=_FakeAppleVerifier())
    user_id = uuid4()
    auth.ensure_anonymous(device_user_id=user_id)
    user, token, _ = auth.sign_in_with_apple(
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


def test_apple_first_auth_persists_email_claim():
    """Apple ships the email claim only on first auth; we persist it."""
    auth = AuthService(apple_verifier=_FakeAppleVerifier())
    user_id = uuid4()
    auth.ensure_anonymous(device_user_id=user_id)
    user, _, _ = auth.sign_in_with_apple(
        identity_token=_apple_jwt("apple-sub-with-email", email="alpha@example.com"),
        user_id=user_id,
    )
    assert user.email == "alpha@example.com"
    assert user.apple_id == "apple-sub-with-email"


def test_apple_subsequent_auth_without_email_keeps_existing():
    """Subsequent Apple sign-ins don't ship the email claim. Existing
    row's email must be preserved, not blanked out."""
    auth = AuthService(apple_verifier=_FakeAppleVerifier())
    user_id = uuid4()
    auth.ensure_anonymous(device_user_id=user_id)
    # First auth — email present.
    auth.sign_in_with_apple(
        identity_token=_apple_jwt("apple-sub-1", email="first@example.com"),
        user_id=user_id,
    )
    # Second auth — Apple's contract: no email claim. Mobile sends the
    # same identity_token shape but the JWT body has no email key.
    user, _, _ = auth.sign_in_with_apple(
        identity_token=_apple_jwt("apple-sub-1"),  # no email
        user_id=user_id,
    )
    assert user.email == "first@example.com"  # preserved


def test_apple_first_auth_persists_full_name():
    """full_name from the iOS SDK is captured into users.display_name on
    first auth (the only time Apple ships it)."""
    auth = AuthService(apple_verifier=_FakeAppleVerifier())
    user_id = uuid4()
    auth.ensure_anonymous(device_user_id=user_id)
    user, _, _ = auth.sign_in_with_apple(
        identity_token=_apple_jwt("apple-sub-named"),
        user_id=user_id,
        full_name="Alpha Tester",
    )
    assert user.display_name == "Alpha Tester"


def test_apple_subsequent_auth_without_full_name_keeps_existing():
    """Subsequent sign-ins don't ship a name — display_name preserved."""
    auth = AuthService(apple_verifier=_FakeAppleVerifier())
    user_id = uuid4()
    auth.ensure_anonymous(device_user_id=user_id)
    auth.sign_in_with_apple(
        identity_token=_apple_jwt("apple-sub-1"),
        user_id=user_id,
        full_name="Alpha Tester",
    )
    # Second auth — mobile sends no full_name.
    user, _, _ = auth.sign_in_with_apple(
        identity_token=_apple_jwt("apple-sub-1"),
        user_id=user_id,
        full_name=None,
    )
    assert user.display_name == "Alpha Tester"


def test_apple_does_not_overwrite_existing_display_name():
    """If display_name already populated (e.g. set by an earlier auth or
    a different provider), don't overwrite even if a new name arrives."""
    auth = AuthService(apple_verifier=_FakeAppleVerifier())
    user_id = uuid4()
    auth.ensure_anonymous(device_user_id=user_id)
    auth.sign_in_with_apple(
        identity_token=_apple_jwt("apple-sub-1"),
        user_id=user_id,
        full_name="Original Name",
    )
    # A buggy/malicious second call with a different name should not
    # rewrite the original.
    user, _, _ = auth.sign_in_with_apple(
        identity_token=_apple_jwt("apple-sub-1"),
        user_id=user_id,
        full_name="Different Name",
    )
    assert user.display_name == "Original Name"


def test_apple_empty_full_name_does_not_clobber():
    """Empty/whitespace full_name is treated as None — no clobber."""
    auth = AuthService(apple_verifier=_FakeAppleVerifier())
    user_id = uuid4()
    auth.ensure_anonymous(device_user_id=user_id)
    auth.sign_in_with_apple(
        identity_token=_apple_jwt("apple-sub-1"),
        user_id=user_id,
        full_name="Real Name",
    )
    # Apple sometimes sends an empty PersonNameComponents — treat as no name.
    user, _, _ = auth.sign_in_with_apple(
        identity_token=_apple_jwt("apple-sub-1"),
        user_id=user_id,
        full_name="   ",
    )
    assert user.display_name == "Real Name"


def test_apple_does_not_overwrite_existing_email():
    """If a user claimed via magic-link first (real email), then linked
    Apple later (might be a `@privaterelay.appleid.com` relay), keep the
    real email — never overwrite a populated email field."""
    auth = AuthService(apple_verifier=_FakeAppleVerifier())
    user_id = uuid4()
    auth.ensure_anonymous(device_user_id=user_id)
    # Magic-link claim first → user.email = real email.
    code = auth.start_magic_link(email="real@example.com", user_id=user_id)
    auth.verify_magic_link(email="real@example.com", code=code, user_id=user_id)
    # Then Apple sign-in with a relay address.
    user, _, _ = auth.sign_in_with_apple(
        identity_token=_apple_jwt(
            "apple-sub-relay", email="abc123@privaterelay.appleid.com"
        ),
        user_id=user_id,
    )
    assert user.email == "real@example.com"  # NOT overwritten
    assert user.apple_id == "apple-sub-relay"


def test_claim_sets_trial_dates():
    """First Apple claim populates trial_started_at + trial_expires_at on the user row (BL3 / D-039)."""
    from datetime import timedelta
    from app.db import get_session
    from app.db.models import User as UserModel
    from sqlalchemy import select as _select
    auth = AuthService(apple_verifier=_FakeAppleVerifier())
    user_id = uuid4()
    user, _, _ = auth.sign_in_with_apple(
        identity_token=_apple_jwt("apple-sub-trial", email="trial@example.com"),
        user_id=user_id,
    )
    with get_session() as s:
        row = s.execute(_select(UserModel).where(UserModel.id == user.id)).scalar_one()
        assert row.trial_started_at is not None
        assert row.trial_expires_at is not None
        assert row.trial_expires_at - row.trial_started_at == timedelta(days=7)


def test_reauth_does_not_reset_existing_trial():
    """A second Apple sign-in must not slide the trial window forward."""
    from app.db import get_session
    from app.db.models import User as UserModel
    from sqlalchemy import select as _select
    auth = AuthService(apple_verifier=_FakeAppleVerifier())
    user_id = uuid4()
    user, _, _ = auth.sign_in_with_apple(
        identity_token=_apple_jwt("apple-sub-reauth"),
        user_id=user_id,
    )
    with get_session() as s:
        original_expiry = s.execute(
            _select(UserModel).where(UserModel.id == user.id)
        ).scalar_one().trial_expires_at
    # Re-auth (same apple_sub).
    auth.sign_in_with_apple(
        identity_token=_apple_jwt("apple-sub-reauth"),
        user_id=user_id,
    )
    with get_session() as s:
        row = s.execute(_select(UserModel).where(UserModel.id == user.id)).scalar_one()
        assert row.trial_expires_at == original_expiry  # window preserved


# ── Account linking — Phase 1 (AT:R32) ─────────────────────────────────────


def test_magic_link_adopts_existing_email_user_on_new_device():
    """Same email + a fresh anon on a new device → adopt the existing user,
    not create a parallel row. Resolves the multi-device fragmentation in
    AT:R32 (3-rows-per-human bug)."""
    auth = AuthService()
    # Original device claims first.
    original_user_id = uuid4()
    auth.ensure_anonymous(device_user_id=original_user_id)
    code = auth.start_magic_link(email="shared@example.com", user_id=original_user_id)
    first_result = auth.verify_magic_link(
        email="shared@example.com", code=code, user_id=original_user_id,
    )
    assert first_result is not None
    first_user, _, _ = first_result

    # New device — fresh anon, then magic-link with the same email.
    new_device_uid = uuid4()
    auth.ensure_anonymous(device_user_id=new_device_uid)
    code2 = auth.start_magic_link(email="shared@example.com", user_id=new_device_uid)
    second_result = auth.verify_magic_link(
        email="shared@example.com", code=code2, user_id=new_device_uid,
    )
    assert second_result is not None
    second_user, _, adopted = second_result

    # Same row, not a parallel one.
    assert second_user.id == first_user.id
    assert second_user.id != new_device_uid
    # BL16 (AT:R38): adoption signal points back at the new device's anon.
    assert adopted == new_device_uid


def test_magic_link_creates_user_when_email_unknown():
    """No existing identity match → fall through to the user_id-promote path
    and claim the fresh anon row (the original AT:R26 magic-link flow)."""
    auth = AuthService()
    user_id = uuid4()
    auth.ensure_anonymous(device_user_id=user_id)
    code = auth.start_magic_link(email="brand-new@example.com", user_id=user_id)
    result = auth.verify_magic_link(
        email="brand-new@example.com", code=code, user_id=user_id,
    )
    assert result is not None
    user, _, adopted = result
    assert user.id == user_id  # the anon row got promoted, not a new row
    assert user.email == "brand-new@example.com"
    assert adopted is None


def test_apple_links_to_existing_email_user():
    """Magic-link first, then Apple Sign-In ships the same email → attach
    apple_sub to the magic-link user instead of creating a parallel row."""
    auth = AuthService(apple_verifier=_FakeAppleVerifier())
    # Magic-link claim on device A.
    user_id_a = uuid4()
    auth.ensure_anonymous(device_user_id=user_id_a)
    code = auth.start_magic_link(email="link@example.com", user_id=user_id_a)
    auth.verify_magic_link(email="link@example.com", code=code, user_id=user_id_a)

    # Device B — fresh anon, then Apple Sign-In whose token carries the same
    # email (Apple's first-auth-only email claim).
    user_id_b = uuid4()
    auth.ensure_anonymous(device_user_id=user_id_b)
    user, _, _ = auth.sign_in_with_apple(
        identity_token=_apple_jwt("apple-sub-link", email="link@example.com"),
        user_id=user_id_b,
    )
    assert user.id == user_id_a  # adopted the magic-link row
    assert user.apple_id == "apple-sub-link"
    assert user.email == "link@example.com"


def test_apple_creates_user_when_sub_and_email_unknown():
    """No apple_id match, no email match → fall through to the user_id-promote
    path (the original AT:R29 first-Apple-auth flow)."""
    auth = AuthService(apple_verifier=_FakeAppleVerifier())
    user_id = uuid4()
    auth.ensure_anonymous(device_user_id=user_id)
    user, _, _ = auth.sign_in_with_apple(
        identity_token=_apple_jwt("apple-sub-fresh", email="fresh@example.com"),
        user_id=user_id,
    )
    assert user.id == user_id
    assert user.apple_id == "apple-sub-fresh"
    assert user.email == "fresh@example.com"
