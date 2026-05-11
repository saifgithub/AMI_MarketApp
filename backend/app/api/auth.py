"""Auth endpoints — anonymous bootstrap + magic-link / Apple claim.

Endpoint map:

  POST /v1/auth/anon                  Bootstrap or re-bootstrap an anon session
  POST /v1/auth/magic_link/start      Begin email magic-link claim
  POST /v1/auth/magic_link/verify     Complete email magic-link claim
  POST /v1/auth/apple                 Claim via Apple Sign-In identity token
  GET  /v1/auth/me                    Read the current user (by token)

The token format in scaffold mode is `scaffold:<user_id_hex>`. We accept
it via the `Authorization: Bearer <token>` header or as `?token=...` for
mobile WebView callbacks.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select

from app.core.config import settings
from app.db import get_session
from app.db.models import User
from app.schemas.auth import (
    AnonSessionRequest,
    AnonSessionResponse,
    AppleSignInRequest,
    AuthUser,
    AuthVerifyResponse,
    MagicLinkStartRequest,
    MagicLinkStartResponse,
    MagicLinkVerifyRequest,
)
from app.services.auth_service import AuthService, _is_dev_env, get_auth_service


router = APIRouter(prefix="/v1/auth", tags=["auth"])


def _user_id_from_token(token: str | None) -> UUID | None:
    if not token:
        return None
    if token.startswith("scaffold:"):
        try:
            return UUID(token.split(":", 1)[1])
        except ValueError:
            return None
    return None


@router.post("/anon", response_model=AnonSessionResponse)
def anon_session(
    req: AnonSessionRequest,
    auth: AuthService = Depends(get_auth_service),
) -> AnonSessionResponse:
    user, token, is_new = auth.ensure_anonymous(
        device_user_id=req.device_user_id,
        locale=req.locale,
        timezone_str=req.timezone,
    )
    return AnonSessionResponse(user=user, token=token, is_new=is_new)


@router.post("/magic_link/start", response_model=MagicLinkStartResponse)
def magic_link_start(
    req: MagicLinkStartRequest,
    auth: AuthService = Depends(get_auth_service),
) -> MagicLinkStartResponse:
    code = auth.start_magic_link(email=req.email, user_id=req.user_id)
    # Dev convenience: surface the code so the iPhone client can copy it
    # without an actual email send. Real prod (env=prod) never returns it.
    return MagicLinkStartResponse(
        sent=True,
        debug_code=code if _is_dev_env() else None,
    )


@router.post("/magic_link/verify", response_model=AuthVerifyResponse)
def magic_link_verify(
    req: MagicLinkVerifyRequest,
    auth: AuthService = Depends(get_auth_service),
) -> AuthVerifyResponse:
    result = auth.verify_magic_link(
        email=req.email, code=req.code, user_id=req.user_id,
    )
    if result is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "invalid or expired code",
        )
    user, token = result
    return AuthVerifyResponse(user=user, token=token, claimed=True)


@router.post("/apple", response_model=AuthVerifyResponse)
def sign_in_with_apple(
    req: AppleSignInRequest,
    auth: AuthService = Depends(get_auth_service),
) -> AuthVerifyResponse:
    try:
        user, token = auth.sign_in_with_apple(
            identity_token=req.identity_token,
            user_id=req.user_id,
            full_name=req.full_name,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    return AuthVerifyResponse(user=user, token=token, claimed=True)


@router.get("/me", response_model=AuthUser)
def whoami(
    authorization: str | None = Header(default=None),
    token: str | None = Query(default=None),
) -> AuthUser:
    raw = token
    if raw is None and authorization and authorization.lower().startswith("bearer "):
        raw = authorization.split(" ", 1)[1]
    user_id = _user_id_from_token(raw)
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing or invalid token")
    with get_session() as s:
        row = s.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
        return AuthUser(
            id=row.id,
            email=row.email,
            apple_id=row.apple_id,
            is_anonymous=row.is_anonymous,
            claimed_at=row.claimed_at,
            created_at=row.created_at,
        )
