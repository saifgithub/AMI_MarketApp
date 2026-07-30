"""Auth endpoints — anonymous bootstrap + magic-link / Apple / Google claim.

Endpoint map:

  POST /v1/auth/anon                  Bootstrap or re-bootstrap an anon session
  POST /v1/auth/magic_link/start      Begin email magic-link claim
  POST /v1/auth/magic_link/verify     Complete email magic-link claim
  POST /v1/auth/apple                 Claim via Apple Sign-In identity token (iOS)
  POST /v1/auth/google                Claim via Google Sign-In identity token (Android; D-057)
  GET  /v1/auth/me                    Read the current user (by token)

The token format in scaffold mode is `scaffold:<user_id_hex>:<hmac_sig>`
(post AT:R25 Phase 1.5). We accept it via the `Authorization: Bearer <token>`
header or as `?token=...` for mobile WebView callbacks. The legacy
unsigned format `scaffold:<hex>` is still accepted when `env=local` for
offline developer convenience, and rejected everywhere else.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.db import get_session
from app.db.models import SubscriptionEventRow, User
from app.schemas.auth import (
    AnonSessionRequest,
    AnonSessionResponse,
    AppleSignInRequest,
    AuthUser,
    AuthVerifyResponse,
    GoogleSignInRequest,
    MagicLinkStartRequest,
    MagicLinkStartResponse,
    MagicLinkVerifyRequest,
    MergeAccountRequest,
    MergePreview,
    MergeResult,
)
from app.api.dependencies import get_current_user
from app.schemas import Mandate
from app.services.auth_service import AuthService, _is_dev_env, get_auth_service, parse_scaffold_token
from app.services.concierge_engine import session_to_mandate_dict
from app.services.mandate_store import get_mandate_store
from app.services.merge_service import MergeError, MergeService, get_merge_service
from app.services.rate_limit import (
    anon_rate_limit,
    magic_link_start_email_rate_limit,
    magic_link_start_rate_limit,
    magic_link_verify_email_rate_limit,
    magic_link_verify_global_rate_limit,
    magic_link_verify_ip_rate_limit,
)
from app.services.session_store import get_session_store


async def _bind_onboarding_session(session_id: UUID | None, user_id: UUID) -> None:
    """BL13 (AT:R32): if the client supplies the OnboardingSession that
    produced this user, stamp `claimed_user_id` on it. Idempotent — re-binding
    the same pair is a no-op. Silently skips if the session expired or was
    never created (the user could have claimed without going through Concierge
    via the Apple direct path, for instance).

    DEF060 (AT:R59): the Concierge interview builds a real mandate
    (`session_to_mandate_dict`) but historically it was only ever returned as
    a preview to the client and discarded — nothing persisted it, so every
    claimed user got the generic default mandate regardless of what they told
    the Concierge. First-time binding (guarded by the idempotency check above)
    now hydrates the real mandate from the completed session's answers. Skips
    if a mandate row already exists for this user — never clobber a mandate
    that may have been edited since claim (e.g. a re-auth replaying the same
    onboarding_session_id)."""
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

    if session.completed and get_mandate_store().get(user_id) is None:
        mandate_dict = session_to_mandate_dict(session, user_id=user_id)
        get_mandate_store().upsert(user_id, Mandate.model_validate(mandate_dict))


router = APIRouter(prefix="/v1/auth", tags=["auth"])


def _user_id_from_token(token: str | None) -> UUID | None:
    if not token:
        return None
    return parse_scaffold_token(token)


@router.post(
    "/anon",
    response_model=AnonSessionResponse,
    dependencies=[Depends(anon_rate_limit)],
)
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
        device_install_id=req.device_install_id,
    )
    return AnonSessionResponse(user=user, token=token, is_new=is_new)


@router.post(
    "/magic_link/start",
    response_model=MagicLinkStartResponse,
    dependencies=[Depends(magic_link_start_rate_limit)],
)
def magic_link_start(
    req: MagicLinkStartRequest,
    current_user: User = Depends(get_current_user),
    auth: AuthService = Depends(get_auth_service),
) -> MagicLinkStartResponse:
    # Adversarial audit (2026-05-18) finding A3: the challenge row is bound to
    # the caller's authenticated user_id from the Bearer token. Body-supplied
    # user_id is no longer accepted (the field is removed from the schema).
    # DEF180 (security review H5 + M5): per-IP throttling alone didn't stop
    # an attacker (or botnet) hammering ONE target email — throttle by the
    # target email too, on top of the existing per-IP limiter dependency.
    magic_link_start_email_rate_limit.check(f"email:{req.email.lower().strip()}")
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
    request: Request,
    current_user: User = Depends(get_current_user),
    auth: AuthService = Depends(get_auth_service),
) -> AuthVerifyResponse:
    # Adversarial audit (2026-05-18) finding A3: the claim binds to the
    # caller's authenticated user_id. Body-supplied user_id is no longer
    # accepted.
    # DEF180 (security review H5): /verify previously had NO rate limiter
    # at all. Three layers per lane acceptance #3 ("per identifier AND
    # globally"): per-IP, per-target-email (the tight one — this is what
    # actually bounds the brute-force budget against one victim), and a
    # global cap across every key (bounds distributed guessing spread
    # across many emails/IPs).
    magic_link_verify_ip_rate_limit.check(magic_link_verify_ip_rate_limit.resolve_ip_key(request))
    magic_link_verify_email_rate_limit.check(f"email:{req.email.lower().strip()}")
    magic_link_verify_global_rate_limit.check("global")
    # DEF180: the active-challenge lookup used to match on email alone, so
    # ANY authenticated caller could guess codes against a challenge some
    # OTHER user started (e.g. the real owner's own claim-my-email flow).
    # Binding to the caller's own user_id means a caller can only ever
    # guess against challenges they themselves created.
    result = auth.verify_magic_link(
        email=req.email, code=req.code, user_id=current_user.id,
        challenge_owner_id=current_user.id,
    )
    if result is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "invalid or expired code",
        )
    user, token, adopted_from = result
    await _bind_onboarding_session(req.onboarding_session_id, user.id)
    return AuthVerifyResponse(
        user=user, token=token, claimed=True,
        adopted_from_user_id=adopted_from,
    )


@router.post("/apple", response_model=AuthVerifyResponse)
async def sign_in_with_apple(
    req: AppleSignInRequest,
    current_user: User = Depends(get_current_user),
    auth: AuthService = Depends(get_auth_service),
) -> AuthVerifyResponse:
    # Phase 3 (AT:R29) closed audit finding A4. The endpoint now verifies
    # the identity token against Apple's JWKS (signature + iss + aud +
    # exp) via OIDCVerifier. Any failure surfaces as 400.
    # DEF176 (security review C1): the pre-claim anon row is bound to the
    # caller's Bearer-authenticated user_id, not a body-supplied value —
    # otherwise an attacker with their own valid identity_token could pass
    # a victim's user_id and take over that account.
    # DEF183 (security review N2): sign_in_with_apple does a synchronous
    # JWKS fetch (httpx.Client) inside this `async def` handler. An
    # unknown-kid token forces two 5s fetches on the single uvicorn
    # worker's event loop, stalling every other request. run_in_threadpool
    # moves the blocking call off the loop.
    try:
        user, token, adopted_from = await run_in_threadpool(
            auth.sign_in_with_apple,
            identity_token=req.identity_token,
            user_id=current_user.id,
            full_name=req.full_name,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    await _bind_onboarding_session(req.onboarding_session_id, user.id)
    return AuthVerifyResponse(
        user=user, token=token, claimed=True,
        adopted_from_user_id=adopted_from,
    )


@router.post("/google", response_model=AuthVerifyResponse)
async def sign_in_with_google(
    req: GoogleSignInRequest,
    current_user: User = Depends(get_current_user),
    auth: AuthService = Depends(get_auth_service),
) -> AuthVerifyResponse:
    # D-057 (AT:R36). Mirrors the Apple route. Verifies the identity token
    # against Google's JWKS (signature + iss + aud + exp + email_verified)
    # via OIDCVerifier. Any failure surfaces as 400.
    # DEF176: see sign_in_with_apple — bind to the caller's Bearer, not a
    # body-supplied user_id. DEF183: see sign_in_with_apple — offload the
    # blocking JWKS fetch to the threadpool.
    try:
        user, token, adopted_from = await run_in_threadpool(
            auth.sign_in_with_google,
            identity_token=req.identity_token,
            user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    await _bind_onboarding_session(req.onboarding_session_id, user.id)
    return AuthVerifyResponse(
        user=user, token=token, claimed=True,
        adopted_from_user_id=adopted_from,
    )


def _assert_adopter(s, *, caller_id: UUID, from_user_id: UUID) -> None:
    """BL16 (AT:R38) authorisation gate: the caller can only preview/execute
    a merge from `from_user_id` if AuthService earlier logged an
    `account_adoption` event with from_value=from_user_id, to_value=caller.
    Anything else is 403."""
    proof = s.execute(
        select(SubscriptionEventRow.id).where(
            SubscriptionEventRow.event_type == "account_adoption",
            SubscriptionEventRow.from_value == str(from_user_id),
            SubscriptionEventRow.to_value == str(caller_id),
        ).limit(1)
    ).scalar_one_or_none()
    if proof is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "no recorded adoption from this user_id to the caller",
        )


@router.get("/merge/preview/{from_user_id}", response_model=MergePreview)
def merge_preview(
    from_user_id: UUID,
    current_user: User = Depends(get_current_user),
    merge: MergeService = Depends(get_merge_service),
) -> MergePreview:
    """BL16 (AT:R38): show what would be moved off the orphan into the
    adopting user. Caller's Bearer must be the adopting user, and an
    `account_adoption` event with this exact pair must exist."""
    with get_session() as s:
        _assert_adopter(s, caller_id=current_user.id, from_user_id=from_user_id)
        orphan = s.execute(
            select(User).where(User.id == from_user_id)
        ).scalar_one_or_none()
        if orphan is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "orphan user not found (already merged?)",
            )
    try:
        counts = merge.preview(
            from_user_id=from_user_id, to_user_id=current_user.id,
        )
    except MergeError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    return MergePreview(
        from_user_id=from_user_id,
        to_user_id=current_user.id,
        journal_entries=counts.journal_entries,
        sim_trades=counts.sim_trades,
        sim_holdings=counts.sim_holdings,
        sim_watchlists=counts.sim_watchlists,
        lessons_progress=counts.lessons_progress,
        agent_activations=counts.agent_activations,
        one_on_one_messages=counts.one_on_one_messages,
        room_runs=counts.room_runs,
        user_overlays=counts.user_overlays,
        bug_reports=counts.bug_reports,
        mandate_conflict=counts.mandate_conflict,
    )


@router.post("/merge", response_model=MergeResult)
def merge_execute(
    req: MergeAccountRequest,
    current_user: User = Depends(get_current_user),
    merge: MergeService = Depends(get_merge_service),
) -> MergeResult:
    """BL16 (AT:R38): re-key every per-user row from the orphan into the
    adopting user. Single transaction. Idempotent after orphan is gone."""
    with get_session() as s:
        _assert_adopter(s, caller_id=current_user.id, from_user_id=req.from_user_id)
        orphan = s.execute(
            select(User).where(User.id == req.from_user_id)
        ).scalar_one_or_none()
        if orphan is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "orphan user not found (already merged?)",
            )
    try:
        counts, mandate_kept, overlays_deactivated = merge.execute(
            from_user_id=req.from_user_id, to_user_id=current_user.id,
        )
    except MergeError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    return MergeResult(
        from_user_id=req.from_user_id,
        to_user_id=current_user.id,
        counts=counts,
        mandate_kept=mandate_kept,
        overlays_deactivated=overlays_deactivated,
    )


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
) -> AuthUser:
    # DEF181 (security review H4): the `?token=` query-param variant is
    # dropped — a bearer in the URL gets logged verbatim by proxies, CDN
    # access logs, and (pre-fix) this app's own http_audit query-string
    # capture, and stateless HMAC tokens have no exp/revocation, so a
    # single log read yields permanent access. The Flutter client has
    # always used the header; grep confirms no caller anywhere uses the
    # query form.
    raw = None
    if authorization and authorization.lower().startswith("bearer "):
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
            google_id=row.google_id,
            display_name=row.display_name,
            is_anonymous=row.is_anonymous,
            claimed_at=row.claimed_at,
            created_at=row.created_at,
        )
