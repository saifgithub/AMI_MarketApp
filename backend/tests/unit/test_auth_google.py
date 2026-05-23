"""Tests for Google Sign-In claim flow (AT:R36, D-057).

Mirrors test_auth_service.py's Apple tests. Uses a `_FakeGoogleVerifier`
that reads claims from the JWT body without signature verification —
real JWKS verification is covered separately in `test_oidc_verifier.py`.

The Google-side wrinkles vs Apple covered here:
  - `email_verified=false` claim → email dropped on the floor
  - `name` (Google's display name) persists into `users.display_name`
    on first sight, never overwrites
  - `email` ships on every token (not first-only like Apple) but the
    don't-overwrite-existing rule still applies
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.services.auth_service import AuthService
from app.services.oidc_verifier import OIDCVerificationError


def _google_jwt(
    sub: str,
    *,
    email: str | None = None,
    email_verified: bool = True,
    name: str | None = None,
) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"RS256","kid":"abc"}').rstrip(b"=").decode()
    payload: dict = {"sub": sub, "email_verified": email_verified}
    if email is not None:
        payload["email"] = email
    if name is not None:
        payload["name"] = name
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    sig = base64.urlsafe_b64encode(b"sig").rstrip(b"=").decode()
    return f"{header}.{body}.{sig}"


class _FakeGoogleVerifier:
    """Body-only Google ID-token reader. No signature / iss / aud checks."""

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


def _auth() -> AuthService:
    return AuthService(google_verifier=_FakeGoogleVerifier())


# ── Happy path ────────────────────────────────────────────────────────────


def test_google_claim_attaches_sub_to_user():
    auth = _auth()
    user_id = uuid4()
    auth.ensure_anonymous(device_user_id=user_id)
    user, token = auth.sign_in_with_google(
        identity_token=_google_jwt("google-sub-123"),
        user_id=user_id,
    )
    assert user.id == user_id
    assert user.google_id == "google-sub-123"
    assert user.is_anonymous is False
    assert user.claimed_at is not None
    assert token.startswith("scaffold:")


def test_google_first_auth_persists_email_and_name():
    auth = _auth()
    user_id = uuid4()
    auth.ensure_anonymous(device_user_id=user_id)
    user, _ = auth.sign_in_with_google(
        identity_token=_google_jwt(
            "google-sub-named",
            email="named@example.com",
            name="Named Person",
        ),
        user_id=user_id,
    )
    assert user.email == "named@example.com"
    assert user.display_name == "Named Person"


# ── Rejection ─────────────────────────────────────────────────────────────


def test_google_rejects_undecodable_jwt():
    auth = _auth()
    with pytest.raises(ValueError):
        auth.sign_in_with_google(identity_token="not-a-jwt", user_id=None)


def test_google_rejects_missing_sub():
    """Token signed by Google would always have `sub`, but defensively
    reject any token whose body lacks one."""
    auth = _auth()
    header = base64.urlsafe_b64encode(b'{"alg":"RS256","kid":"abc"}').rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(b'{"email":"x@y"}').rstrip(b"=").decode()
    sig = base64.urlsafe_b64encode(b"sig").rstrip(b"=").decode()
    with pytest.raises(ValueError, match="sub"):
        auth.sign_in_with_google(identity_token=f"{header}.{body}.{sig}", user_id=None)


# ── email_verified guard ──────────────────────────────────────────────────


def test_google_drops_unverified_email():
    """If Google says email_verified=false, we don't persist the email — it
    might belong to someone else who never confirmed."""
    auth = _auth()
    user_id = uuid4()
    auth.ensure_anonymous(device_user_id=user_id)
    user, _ = auth.sign_in_with_google(
        identity_token=_google_jwt(
            "google-sub-unverified",
            email="unverified@example.com",
            email_verified=False,
            name="Skeptic",
        ),
        user_id=user_id,
    )
    assert user.google_id == "google-sub-unverified"
    assert user.email is None
    # Name still persists — it's not security-sensitive.
    assert user.display_name == "Skeptic"


# ── Don't-overwrite rules (parallel to Apple) ─────────────────────────────


def test_google_does_not_overwrite_existing_email():
    """If a row already has a real email (from magic-link), a later Google
    sign-in with a relay/different email must not mutate it."""
    auth = _auth()
    user_id = uuid4()
    auth.ensure_anonymous(device_user_id=user_id)
    # First claim — magic-link with a real email.
    code = auth.start_magic_link(email="primary@example.com", user_id=user_id)
    auth.verify_magic_link(email="primary@example.com", code=code, user_id=user_id)
    # Then a separate Google account with a different verified email.
    user, _ = auth.sign_in_with_google(
        identity_token=_google_jwt(
            "google-sub-other",
            email="other@example.com",
            name="Other Person",
        ),
        user_id=user_id,
    )
    # account-linking sees no match on google-sub-other, but the user_id is
    # already claimed (not anon), so we promote-by-user_id. The original
    # email survives.
    assert user.email == "primary@example.com"
    assert user.google_id == "google-sub-other"


def test_google_does_not_overwrite_existing_display_name():
    auth = _auth()
    user_id = uuid4()
    auth.ensure_anonymous(device_user_id=user_id)
    auth.sign_in_with_google(
        identity_token=_google_jwt(
            "google-sub-d", email="d@example.com", name="First Name"
        ),
        user_id=user_id,
    )
    # Re-auth with a different name (user changed it in their Google account).
    user, _ = auth.sign_in_with_google(
        identity_token=_google_jwt(
            "google-sub-d", email="d@example.com", name="Different Name"
        ),
        user_id=user_id,
    )
    assert user.display_name == "First Name"


def test_google_empty_name_does_not_clobber():
    auth = _auth()
    user_id = uuid4()
    auth.ensure_anonymous(device_user_id=user_id)
    auth.sign_in_with_google(
        identity_token=_google_jwt(
            "google-sub-e", email="e@example.com", name="Initial Name"
        ),
        user_id=user_id,
    )
    user, _ = auth.sign_in_with_google(
        identity_token=_google_jwt(
            "google-sub-e", email="e@example.com", name="   "
        ),
        user_id=user_id,
    )
    assert user.display_name == "Initial Name"


# ── Trial activation (D-039 / BL3) ────────────────────────────────────────


def test_google_first_claim_sets_trial_dates():
    auth = _auth()
    user_id = uuid4()
    auth.ensure_anonymous(device_user_id=user_id)
    user, _ = auth.sign_in_with_google(
        identity_token=_google_jwt("google-sub-trial", email="trial@example.com"),
        user_id=user_id,
    )
    # AuthUser doesn't expose trial fields directly — query the DB row.
    from app.db import get_session
    from app.db.models import User
    from sqlalchemy import select
    with get_session() as s:
        row = s.execute(select(User).where(User.id == user.id)).scalar_one()
        assert row.trial_started_at is not None
        assert row.trial_expires_at is not None
        # 7-day window per D-039.
        delta = row.trial_expires_at - row.trial_started_at
        assert 6 * 86400 < delta.total_seconds() < 8 * 86400


def test_google_reauth_does_not_reset_existing_trial():
    auth = _auth()
    user_id = uuid4()
    auth.ensure_anonymous(device_user_id=user_id)
    user, _ = auth.sign_in_with_google(
        identity_token=_google_jwt("google-sub-trial2", email="trial2@example.com"),
        user_id=user_id,
    )
    from app.db import get_session
    from app.db.models import User
    from sqlalchemy import select
    with get_session() as s:
        row = s.execute(select(User).where(User.id == user.id)).scalar_one()
        original_started = row.trial_started_at
        original_expires = row.trial_expires_at
    # Re-auth — should not bump trial dates.
    auth.sign_in_with_google(
        identity_token=_google_jwt("google-sub-trial2", email="trial2@example.com"),
        user_id=user_id,
    )
    with get_session() as s:
        row = s.execute(select(User).where(User.id == user.id)).scalar_one()
        assert row.trial_started_at == original_started
        assert row.trial_expires_at == original_expires


# ── Account-linking Phase 1 (D-057 mirror of Apple) ───────────────────────


def test_google_links_to_existing_magic_link_user_by_email():
    """Magic-link claim first, then Google Sign-In with the same email →
    attach google_sub to the existing row, not create a parallel one."""
    auth = _auth()
    # Magic-link claim on device A.
    user_id_a = uuid4()
    auth.ensure_anonymous(device_user_id=user_id_a)
    code = auth.start_magic_link(email="link@example.com", user_id=user_id_a)
    auth.verify_magic_link(email="link@example.com", code=code, user_id=user_id_a)
    # Device B — fresh anon, then Google sign-in with same email.
    user_id_b = uuid4()
    auth.ensure_anonymous(device_user_id=user_id_b)
    user, _ = auth.sign_in_with_google(
        identity_token=_google_jwt(
            "google-sub-link",
            email="link@example.com",
            name="Linked Person",
        ),
        user_id=user_id_b,
    )
    assert user.id == user_id_a
    assert user.google_id == "google-sub-link"
    assert user.email == "link@example.com"


def test_google_creates_user_when_sub_and_email_unknown():
    """No google_id match, no email match → fall through to user_id-promote."""
    auth = _auth()
    user_id = uuid4()
    auth.ensure_anonymous(device_user_id=user_id)
    user, _ = auth.sign_in_with_google(
        identity_token=_google_jwt(
            "google-sub-fresh", email="fresh-g@example.com", name="Fresh"
        ),
        user_id=user_id,
    )
    assert user.id == user_id
    assert user.google_id == "google-sub-fresh"
    assert user.email == "fresh-g@example.com"


def test_google_reauth_returns_same_user():
    auth = _auth()
    user_id = uuid4()
    auth.ensure_anonymous(device_user_id=user_id)
    first, _ = auth.sign_in_with_google(
        identity_token=_google_jwt("google-sub-repeat", email="repeat@example.com"),
        user_id=user_id,
    )
    second, _ = auth.sign_in_with_google(
        identity_token=_google_jwt("google-sub-repeat", email="repeat@example.com"),
        user_id=user_id,
    )
    assert first.id == second.id
    assert second.is_anonymous is False
