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
     /v1/auth/apple — decodes the JWT body without verification (scaffold
     only), reads the `sub` claim, marks the user row claimed with
     apple_id=sub.

`SessionToken` in scaffold mode is just `user_id.hex`. When Supabase
plugs in, the real access JWT replaces it and `kind` becomes `supabase`.
"""

from __future__ import annotations

import base64
import hashlib
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


MAGIC_LINK_TTL_MIN = 15
APPLE_CHALLENGE_TTL_MIN = 60


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _row_to_user(row: User) -> AuthUser:
    return AuthUser(
        id=row.id,
        email=row.email,
        apple_id=row.apple_id,
        is_anonymous=row.is_anonymous,
        claimed_at=row.claimed_at,
        created_at=row.created_at,
    )


def _scaffold_token(user_id: UUID) -> str:
    return f"scaffold:{user_id.hex}"


def _b64url_decode(seg: str) -> bytes:
    padding = "=" * (-len(seg) % 4)
    return base64.urlsafe_b64decode(seg + padding)


def _decode_apple_sub(identity_token: str) -> str:
    """Read the `sub` claim from an Apple JWT body without signature check.

    Real prod: validate JWK + audience + nonce. This scaffold trusts the
    client because we do not yet have Apple production keys plumbed in.
    """
    try:
        _hdr, body, _sig = identity_token.split(".")
        payload = json.loads(_b64url_decode(body).decode("utf-8"))
        sub = payload.get("sub")
        if not sub:
            raise ValueError("apple jwt missing 'sub'")
        return str(sub)
    except Exception as e:
        raise ValueError(f"apple jwt undecodable: {e}") from e


class AuthService:
    """All auth flows. Sync API, opens its own DB session per call."""

    def __init__(self) -> None:
        init_schema()

    # ── Anonymous bootstrap ────────────────────────────────────────────

    def ensure_anonymous(
        self,
        *,
        device_user_id: UUID | None,
        locale: str = "en",
        timezone_str: str = "UTC",
    ) -> tuple[AuthUser, str, bool]:
        """Return (user, token, is_new).

        If `device_user_id` is given and an existing row matches, reuse
        it. Otherwise create a fresh row.
        """
        with get_session() as s:
            row: User | None = None
            if device_user_id is not None:
                row = s.execute(
                    select(User).where(User.device_user_id == device_user_id)
                ).scalar_one_or_none()
                if row is None:
                    # The client-supplied id is the user_id directly. This
                    # is the property that lets data survive claim: the
                    # primary key never changes.
                    row = s.execute(
                        select(User).where(User.id == device_user_id)
                    ).scalar_one_or_none()
            is_new = row is None
            if row is None:
                user_id = device_user_id or uuid4()
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
        apple_sub = _decode_apple_sub(identity_token)
        with get_session() as s:
            # Prefer matching an existing apple_id row.
            row = s.execute(
                select(User).where(User.apple_id == apple_sub)
            ).scalar_one_or_none()
            if row is None and user_id is not None:
                row = s.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
            if row is None:
                row = User(
                    id=user_id or uuid4(),
                    device_user_id=user_id,
                    apple_id=apple_sub,
                    is_anonymous=False,
                    claimed_at=datetime.now(timezone.utc),
                )
                s.add(row)
                s.flush()
            else:
                row.apple_id = apple_sub
                if row.is_anonymous:
                    row.is_anonymous = False
                    row.claimed_at = datetime.now(timezone.utc)
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
            row = User(
                id=user_id or uuid4(),
                device_user_id=user_id,
                email=email,
                is_anonymous=False,
                claimed_at=datetime.now(timezone.utc),
            )
            s.add(row)
            s.flush()
            return row
        row.email = email
        if row.is_anonymous:
            row.is_anonymous = False
            row.claimed_at = datetime.now(timezone.utc)
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
    return settings.env in ("local", "dev")
