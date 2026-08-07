"""Shared FastAPI dependencies for the AMI Trade API.

get_current_user — extract and verify the Bearer token from the
  Authorization header, return the live UserRow.

  Token format (scaffold mode): `scaffold:<user_id_hex>:<exp>:<ver>:<hmac_sig>`
  (CR125). `parse_scaffold_token()` verifies signature + `exp`; THIS module
  is the single point that checks `ver` against the live `user.token_version`
  — the DB round-trip `parse_scaffold_token()` deliberately doesn't make.
  At Beta the token becomes a Supabase JWT; only the parse logic in
  parse_scaffold_token() changes — this enforcement point stays identical,
  which is the whole reason it lives here and not inside the parser.
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select

from app.db import get_session
from app.db.models import User
from app.services.auth_service import ParsedToken, parse_scaffold_token


def _extract_token(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1]
    return None


def _version_matches(parsed: ParsedToken, row: User) -> bool:
    # None only on the local-only legacy unsigned format, which carries no
    # version field at all — trust it exactly as far as it was already
    # trusted (env=="local" only; parse_scaffold_token gates that).
    return parsed.token_version is None or parsed.token_version == row.token_version


def get_current_user(
    authorization: str | None = Header(default=None),
) -> User:
    """Require a valid Bearer token; return the live UserRow.

    Raises 401 when the token is missing, invalid, expired, or was issued
    under a `token_version` the user has since revoked (sign-out — CR125).
    Callers that also need ownership validation should check
    `current_user.id == user_id_in_path` and raise 403 on mismatch.
    """
    token = _extract_token(authorization)
    if not token:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    parsed = parse_scaffold_token(token)
    if parsed is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    with get_session() as s:
        row = s.execute(select(User).where(User.id == parsed.user_id)).scalar_one_or_none()
        if row is None:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "user not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not _version_matches(parsed, row):
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if row.suspended_at is not None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "account_suspended")
        return row


def get_current_user_optional(
    authorization: str | None = Header(default=None),
) -> User | None:
    """Best-effort variant for public routes that enrich their response
    when a valid Bearer is present (e.g. /v1/daily_challenge/today gains
    `my_attempt`). Missing/invalid/expired/wrong-version/suspended → None,
    never an error."""
    token = _extract_token(authorization)
    if not token:
        return None
    parsed = parse_scaffold_token(token)
    if parsed is None:
        return None
    with get_session() as s:
        row = s.execute(select(User).where(User.id == parsed.user_id)).scalar_one_or_none()
        if row is None or row.suspended_at is not None:
            return None
        if not _version_matches(parsed, row):
            return None
        return row
