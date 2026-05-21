"""Auth endpoints — anonymous bootstrap + magic-link / Apple claim.

Endpoint map:

  POST /v1/auth/anon                  Bootstrap or re-bootstrap an anon session
  POST /v1/auth/magic_link/start      Begin email magic-link claim
  POST /v1/auth/magic_link/verify     Complete email magic-link claim
  POST /v1/auth/apple                 Claim via Apple Sign-In identity token
  GET  /v1/auth/me                    Read the current user (by token)

The token format in scaffold mode is `scaffold:<user_id_hex>:<hmac_sig>`
(post AT:R25 Phase 1.5). We accept it via the `Authorization: Bearer <token>`
header or as `?token=...` for mobile WebView callbacks. The legacy
unsigned format `scaffold:<hex>` is still accepted when `env=local` for
offline developer convenience, and rejected everywhere else.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select

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
from app.api.dependencies import get_current_user
from app.services.auth_service import AuthService, _is_dev_env, get_auth_service, parse_scaffold_token
from app.services.session_store import get_session_store


async def _bind_onboarding_session(session_id: UUID | None, user_id: UUID) -> None:
    """BL13 (AT:R32): if the client supplies the OnboardingSession that
    produced this user, stamp `claimed_user_id` on it. Idempotent — re-binding
    the same pair is a no-op. Silently skips if the session expired or was
    never created (the user could have claimed without going through Concierge
    via the Apple direct path, for instance)."""
    if session_id is None:
        return
    store = get_session_store()
    session = await store.get(session_id)
    if session is None:
        return
    if session.claimed_user_id == user_id:
        return
    session.claimed_user_id = user_id
    await store.save(session)


router = APIRouter(prefix="/v1/auth", tags=["auth"])


def _user_id_from_token(token: str | None) -> UUID | None:
    if not token:
        return None
    return parse_scaffold_token(token)


@router.post("/anon", response_model=AnonSessionResponse)
def anon_session(
    req: AnonSessionRequest,
    authorization: str | None = Header(default=None),
    auth: AuthService = Depends(get_auth_service),
) -> AnonSessionResponse:
    # Adversarial audit (2026-05-18) finding A2: only honour an existing
    # device_user_id when the caller has proved possession by sending the
    # matching signed token. Otherwise treat the call as a fresh install.
    bearer_user_id: UUID | None = None
    if authorization and authorization.lower().startswith("bearer "):
        bearer_user_id = _user_id_from_token(authorization.split(" ", 1)[1])
    user, token, is_new = auth.ensure_anonymous(
        device_user_id=req.device_user_id,
        authenticated_user_id=bearer_user_id,
        locale=req.locale,
        timezone_str=req.timezone,
        device_model=req.device_model,
        os_version=req.os_version,
        app_version=req.app_version,
    )
    return AnonSessionResponse(user=user, token=token, is_new=is_new)


@router.post("/magic_link/start", response_model=MagicLinkStartResponse)
def magic_link_start(
    req: MagicLinkStartRequest,
    current_user: User = Depends(get_current_user),
    auth: AuthService = Depends(get_auth_service),
) -> MagicLinkStartResponse:
    # Adversarial audit (2026-05-18) finding A3: the challenge row is bound to
    # the caller's authenticated user_id from the Bearer token. Body-supplied
    # user_id is no longer accepted (the field is removed from the schema).
    code = auth.start_magic_link(email=req.email, user_id=current_user.id)
    # Dev affordance: only env=local returns the code in the response so the
    # developer can paste it without an email send. _is_dev_env() now means
    # local-only; melehost (staging) never leaks the code.
    return MagicLinkStartResponse(
        sent=True,
        debug_code=code if _is_dev_env() else None,
    )


@router.post("/magic_link/verify", response_model=AuthVerifyResponse)
async def magic_link_verify(
    req: MagicLinkVerifyRequest,
    current_user: User = Depends(get_current_user),
    auth: AuthService = Depends(get_auth_service),
) -> AuthVerifyResponse:
    # Adversarial audit (2026-05-18) finding A3: the claim binds to the
    # caller's authenticated user_id. Body-supplied user_id is no longer
    # accepted.
    result = auth.verify_magic_link(
        email=req.email, code=req.code, user_id=current_user.id,
    )
    if result is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "invalid or expired code",
        )
    user, token = result
    await _bind_onboarding_session(req.onboarding_session_id, user.id)
    return AuthVerifyResponse(user=user, token=token, claimed=True)


@router.post("/apple", response_model=AuthVerifyResponse)
async def sign_in_with_apple(
    req: AppleSignInRequest,
    auth: AuthService = Depends(get_auth_service),
) -> AuthVerifyResponse:
    # Phase 3 (AT:R29) closed audit finding A4. The endpoint now verifies
    # the identity token against Apple's JWKS (signature + iss + aud +
    # exp) via OIDCVerifier. Any failure surfaces as 400.
    try:
        user, token = auth.sign_in_with_apple(
            identity_token=req.identity_token,
            user_id=req.user_id,
            full_name=req.full_name,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    await _bind_onboarding_session(req.onboarding_session_id, user.id)
    return AuthVerifyResponse(user=user, token=token, claimed=True)


@router.delete("/session", status_code=status.HTTP_200_OK)
def sign_out(
    current_user: User = Depends(get_current_user),
) -> dict[str, bool]:
    # Scaffold tokens are stateless HMAC — there is no server-side session
    # to invalidate. The client clears its token + re-bootstraps an anon
    # session. This endpoint exists as a clean HTTP contract for a future
    # token blocklist (Phase 5+).
    return {"signed_out": True}


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
