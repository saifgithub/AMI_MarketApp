"""Anonymous-first auth — Supabase-shaped, but works without Supabase.

Three flows for now:

  1. Anonymous session
     POST /v1/auth/anon  with an optional device_user_id from the mobile
     client (shared_preferences). Returns the same id every call, so
     the mandate/journal/portfolio that built up against it survives.

  2. Magic-link claim
     /v1/auth/magic_link/start  → stores a hashed 6-digit code,
     "sends" the email (in dev: returns the code in the response).
     /v1/auth/magic_link/verify → consumes the code, sets email on
     the user row, bumps claimed_at, returns a fresh session token.

  3. Apple Sign-In claim
     /v1/auth/apple — verifies the identity token against Apple's
     JWKS (`OIDCVerifier`), checks `iss`/`aud`/`exp`, reads the `sub`
     claim, marks the user row claimed with apple_id=sub. Phase 3
     verification landed in AT:R29; the earlier "trust the client"
     scaffold was the audit's must-fix-A4 finding.

`SessionToken` in scaffold mode is just `user_id.hex`. When Supabase
plugs in, the real access JWT replaces it and `kind` becomes `supabase`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac as _hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import select

from app.core.config import settings
from app.core.logging import logger
from app.db import get_session, init_schema
from app.db.models import AuthChallengeRow, User
from app.schemas.auth import AuthUser
from app.services.email_service import send_magic_link as _send_magic_link_email
from app.services.oidc_verifier import OIDCVerifier, build_apple_verifier


MAGIC_LINK_TTL_MIN = 15
APPLE_CHALLENGE_TTL_MIN = 60


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _row_to_user(row: User) -> AuthUser:
    return AuthUser(
        id=row.id,
        email=row.email,
        apple_id=row.apple_id,
        display_name=row.display_name,
        is_anonymous=row.is_anonymous,
        claimed_at=row.claimed_at,
        created_at=row.created_at,
    )


def _scaffold_token(user_id: UUID) -> str:
    """Issue a scaffold Bearer token: `scaffold:<user_id_hex>:<hmac_sig>`.

    HMAC prevents offline token forgery. The Beta swap point is a one-line
    change in `parse_scaffold_token()` (verify a Supabase JWT instead).

    The legacy unsigned format `scaffold:<hex>` is still parseable, but
    only when `env == "local"` — see `parse_scaffold_token()`. Adversarial
    audit (2026-05-18) tightened this from "local|dev" because melehost
    runs as `env=dev` and its tunnel is public.
    """
    sig = _hmac.new(
        settings.secret_key.encode("utf-8"),
        user_id.hex.encode("utf-8"),
        "sha256",
    ).hexdigest()
    return f"scaffold:{user_id.hex}:{sig}"


def parse_scaffold_token(token: str) -> UUID | None:
    """Parse and verify a scaffold Bearer token. Returns user_id or None."""
    if not token.startswith("scaffold:"):
        return None
    rest = token[len("scaffold:"):]
    parts = rest.split(":", 1)
    if len(parts) == 2:
        # New signed format: scaffold:<hex>:<sig>
        hex_id, claimed_sig = parts
        try:
            user_id = UUID(hex_id)
        except ValueError:
            return None
        expected_sig = _hmac.new(
            settings.secret_key.encode("utf-8"),
            hex_id.encode("utf-8"),
            "sha256",
        ).hexdigest()
        if not _hmac.compare_digest(claimed_sig, expected_sig):
            return None
        return user_id
    if len(parts) == 1 and settings.env == "local":
        # Legacy unsigned format — accepted only on the developer's local
        # machine. Adversarial audit (2026-05-18) closed dev-env acceptance:
        # melehost is reachable via the public Cloudflare Tunnel.
        try:
            return UUID(parts[0])
        except ValueError:
            return None
    return None


def _b64url_decode(seg: str) -> bytes:
    padding = "=" * (-len(seg) % 4)
    return base64.urlsafe_b64decode(seg + padding)


# `_decode_apple_sub` previously read the JWT body without signature
# verification — the must-fix-A4 finding from the 2026-05-18 audit.
# Replaced in AT:R29 by AuthService._apple_verifier (OIDCVerifier with
# real JWKS fetch). Helper deleted; no callers remain.


class AuthService:
    """All auth flows. Sync API, opens its own DB session per call."""

    def __init__(self, apple_verifier: OIDCVerifier | None = None) -> None:
        init_schema()
        # Apple OIDC verifier (singleton-shaped — one instance owns the
        # JWKS cache). Injectable so tests can pass a fake that trusts
        # body claims without hitting Apple's network.
        self._apple_verifier: OIDCVerifier = (
            apple_verifier
            if apple_verifier is not None
            else build_apple_verifier(settings.apple_audiences)
        )

    # ── Anonymous bootstrap ────────────────────────────────────────────

    def ensure_anonymous(
        self,
        *,
        device_user_id: UUID | None,
        authenticated_user_id: UUID | None = None,
        locale: str = "en",
        timezone_str: str = "UTC",
    ) -> tuple[AuthUser, str, bool]:
        """Return (user, token, is_new).

        `authenticated_user_id` is the user_id parsed from the caller's
        Bearer token (if any). Adversarial audit (2026-05-18) finding A2:
        without this guard the endpoint is a token-minting oracle — anyone
        who knows a victim's UUID could POST {device_user_id: <victim>}
        and receive a valid signed token for them.

        Policy:
          - No `device_user_id` supplied → mint a fresh user (cold start).
          - `device_user_id` matches `authenticated_user_id` → legitimate
            re-bootstrap from the rightful owner. Reuse the row.
          - `device_user_id` supplied but DOESN'T match the bearer (or no
            bearer at all) → ignore the supplied id, mint a fresh user.
            The caller acts as if they were a brand-new install.
        """
        with get_session() as s:
            row: User | None = None
            # Only honour device_user_id when the caller has proved possession
            # via a Bearer token for that same user.
            trust_device_id = (
                device_user_id is not None
                and authenticated_user_id is not None
                and device_user_id == authenticated_user_id
            )
            if trust_device_id:
                row = s.execute(
                    select(User).where(User.device_user_id == device_user_id)
                ).scalar_one_or_none()
                if row is None:
                    row = s.execute(
                        select(User).where(User.id == device_user_id)
                    ).scalar_one_or_none()
            is_new = row is None
            if row is None:
                user_id = uuid4()  # always mint fresh when device_id untrusted
                row = User(
                    id=user_id,
                    device_user_id=user_id,
                    locale=locale,
                    timezone=timezone_str,
                    is_anonymous=True,
                    anonymous_session_started_at=datetime.now(timezone.utc),
                )
                s.add(row)
                s.flush()
            return _row_to_user(row), _scaffold_token(row.id), is_new

    # ── Magic-link ─────────────────────────────────────────────────────

    def start_magic_link(self, *, email: str, user_id: UUID | None) -> str:
        """Returns the 6-digit code; production never returns this in API."""
        code = f"{secrets.randbelow(1_000_000):06d}"
        with get_session() as s:
            s.add(AuthChallengeRow(
                kind="magic_link",
                target=email.lower().strip(),
                code_hash=_hash_code(code),
                user_id=user_id,
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=MAGIC_LINK_TTL_MIN),
            ))
        logger.info("magic_link_started", email=email, user_id=str(user_id))
        _send_magic_link_email(email, code)
        return code

    def verify_magic_link(
        self,
        *,
        email: str,
        code: str,
        user_id: UUID | None,
    ) -> tuple[AuthUser, str] | None:
        target = email.lower().strip()
        with get_session() as s:
            row = s.execute(
                select(AuthChallengeRow).where(
                    AuthChallengeRow.kind == "magic_link",
                    AuthChallengeRow.target == target,
                    AuthChallengeRow.code_hash == _hash_code(code),
                    AuthChallengeRow.consumed_at.is_(None),
                    AuthChallengeRow.expires_at > datetime.now(timezone.utc),
                ).order_by(AuthChallengeRow.created_at.desc()).limit(1)
            ).scalar_one_or_none()
            if row is None:
                return None
            row.consumed_at = datetime.now(timezone.utc)

            # Claim or create the user.
            user = self._claim_or_create(
                s, user_id=user_id or row.user_id, email=target,
            )
            return _row_to_user(user), _scaffold_token(user.id)

    # ── Apple Sign-In ──────────────────────────────────────────────────

    def sign_in_with_apple(
        self,
        *,
        identity_token: str,
        user_id: UUID | None,
        full_name: str | None = None,
    ) -> tuple[AuthUser, str]:
        # Full verification: signature against Apple's JWKS, iss, aud,
        # exp. Raises OIDCVerificationError (subclass of ValueError) on
        # any failure — the route layer translates that to HTTP 400.
        claims = self._apple_verifier.verify(identity_token)
        apple_sub = claims.get("sub")
        if not apple_sub:
            raise ValueError("apple identity_token missing 'sub' claim")
        apple_sub = str(apple_sub)
        # Apple's first-auth-only contract: `email` (real or
        # `@privaterelay.appleid.com` relay) ships only on the very first
        # authorization per Apple-ID/app pair. Subsequent sign-ins omit
        # the claim. So persist on first sight; never overwrite a value
        # already in the row.
        apple_email = claims.get("email")
        apple_email = str(apple_email) if apple_email else None
        # `full_name` is also first-auth-only on the iOS SDK side —
        # Apple only returns it on the initial SignInWithApple consent
        # screen. Persisted into users.display_name on first sight,
        # never overwritten (same rule as email).
        full_name = (full_name or "").strip() or None
        with get_session() as s:
            # Prefer matching an existing apple_id row.
            row = s.execute(
                select(User).where(User.apple_id == apple_sub)
            ).scalar_one_or_none()
            if row is None and user_id is not None:
                row = s.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
            if row is None:
                now = datetime.now(timezone.utc)
                row = User(
                    id=user_id or uuid4(),
                    device_user_id=user_id,
                    apple_id=apple_sub,
                    email=apple_email,
                    display_name=full_name,
                    is_anonymous=False,
                    claimed_at=now,
                    trial_started_at=now,
                    trial_expires_at=now + timedelta(days=7),
                )
                s.add(row)
                s.flush()
            else:
                row.apple_id = apple_sub
                # Never overwrite a populated email — protects against a
                # user who first claimed via magic-link (real email) and
                # later linked Apple (might be the relay address).
                if apple_email and not row.email:
                    row.email = apple_email
                # Same don't-overwrite rule for display_name.
                if full_name and not row.display_name:
                    row.display_name = full_name
                if row.is_anonymous:
                    now = datetime.now(timezone.utc)
                    row.is_anonymous = False
                    row.claimed_at = now
                    if row.trial_started_at is None:
                        row.trial_started_at = now
                        row.trial_expires_at = now + timedelta(days=7)
            return _row_to_user(row), _scaffold_token(row.id)

    # ── Helpers ────────────────────────────────────────────────────────

    def _claim_or_create(
        self,
        s,
        *,
        user_id: UUID | None,
        email: str,
    ) -> User:
        row: User | None = None
        if user_id is not None:
            row = s.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if row is None and email:
            row = s.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if row is None:
            now = datetime.now(timezone.utc)
            row = User(
                id=user_id or uuid4(),
                device_user_id=user_id,
                email=email,
                is_anonymous=False,
                claimed_at=now,
                trial_started_at=now,
                trial_expires_at=now + timedelta(days=7),
            )
            s.add(row)
            s.flush()
            return row
        row.email = email
        if row.is_anonymous:
            now = datetime.now(timezone.utc)
            row.is_anonymous = False
            row.claimed_at = now
            if row.trial_started_at is None:
                row.trial_started_at = now
                row.trial_expires_at = now + timedelta(days=7)
        return row

    # Test helper
    def clear(self) -> None:
        from sqlalchemy import delete as _delete
        with get_session() as s:
            s.execute(_delete(AuthChallengeRow))
            s.execute(_delete(User))


_service: AuthService | None = None


def get_auth_service() -> AuthService:
    global _service
    if _service is None:
        _service = AuthService()
    return _service


def _is_dev_env() -> bool:
    """Returns True only on a developer's local machine.

    Controls debug affordances that must never leak via a public tunnel:
    magic-link code returned in API response, Apple JWT signature skipped.
    Adversarial audit (2026-05-18) tightened this from `local|dev` to `local`
    after melehost was found leaking debug codes via the public hostname.
    """
    return settings.env == "local"
