"""Admin back-office API — /v1/admin/* (AT:R27).

All routes require the static ADMIN_SECRET bearer (Alpha). Beta will layer in
admin_users table + short-lived JWT; the get_admin dependency will accept both.

Endpoint map:
  GET    /v1/admin/users                       Search by email or device_user_id
  GET    /v1/admin/users/{user_id}             Full detail + last 20 events
  PATCH  /v1/admin/users/{user_id}/plan        Change plan tier
  POST   /v1/admin/users/{user_id}/trial       Grant trial (trial_trader, N days)
  PATCH  /v1/admin/users/{user_id}/trial       Extend or revoke trial
  POST   /v1/admin/users/{user_id}/credits     Add or deduct credits
  POST   /v1/admin/users/{user_id}/suspend     Suspend account
  POST   /v1/admin/users/{user_id}/reinstate   Lift suspension
  GET    /v1/admin/users/{user_id}/events      Paginated subscription_events
  POST   /v1/admin/release-floor               Raise the client version floor (CR121)
"""

from __future__ import annotations

import hmac
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import func, select

from app.core.config import Settings, settings
from app.db import get_session
from app.db.models import SubscriptionEventRow, User, UserDeviceRow
from app.schemas.client_release_floor import (
    AdminReleaseFloorOut,
    AdminReleaseFloorRequest,
)
from app.services.client_release_floor import (
    ReleaseFloorDuplicateError,
    ReleaseFloorFootgunError,
    create_floor_raise,
    get_active_floor,
)
from app.schemas.admin import (
    AdminConfigCheckResponse,
    AdminCreditsRequest,
    AdminEventsResponse,
    AdminNoteRequest,
    AdminPlanChangeRequest,
    AdminTrialGrantRequest,
    AdminTrialUpdateRequest,
    AdminUserDetail,
    AdminUserDevice,
    AdminUserSummary,
    FeatureGate,
    SettingsFieldState,
    SubscriptionEventOut,
)


router = APIRouter(prefix="/v1/admin", tags=["admin"])

_VALID_PLANS = {"floor_pass", "trader", "floor_manager", "trial_trader"}


# ── Auth dependency ───────────────────────────────────────────────────────────

def get_admin(authorization: str | None = Header(default=None)) -> None:
    """Verify the static ADMIN_SECRET bearer. Raises 403 on any mismatch."""
    if not settings.admin_secret:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "admin back-office not configured — set ADMIN_SECRET",
        )
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
    if not hmac.compare_digest(token.encode(), settings.admin_secret.encode()):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "invalid admin secret")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _record_event(
    session,
    *,
    user_id: UUID,
    event_type: str,
    from_value: str | None,
    to_value: str | None,
    source: str = "admin_override",
    note: str | None = None,
) -> None:
    row = SubscriptionEventRow(
        id=uuid4(),
        user_id=user_id,
        event_type=event_type,
        from_value=from_value,
        to_value=to_value,
        source=source,
        admin_id=None,
        note=note,
        created_at=_utcnow(),
    )
    session.add(row)


def _get_user_or_404(session, user_id: UUID) -> User:
    row = session.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    return row


def _event_out(row: SubscriptionEventRow) -> SubscriptionEventOut:
    return SubscriptionEventOut(
        id=row.id,
        user_id=row.user_id,
        event_type=row.event_type,
        from_value=row.from_value,
        to_value=row.to_value,
        source=row.source,
        admin_id=row.admin_id,
        note=row.note,
        created_at=row.created_at,
    )


def _user_summary(row: User) -> AdminUserSummary:
    return AdminUserSummary(
        id=row.id,
        email=row.email,
        plan=row.plan,
        credit_balance=row.credit_balance,
        is_anonymous=row.is_anonymous,
        suspended_at=row.suspended_at,
        trial_expires_at=row.trial_expires_at,
        created_at=row.created_at,
    )


def _load_devices(s, user_id: UUID) -> list[UserDeviceRow]:
    """BL2: per-user device list ordered most-recently-seen first."""
    return list(
        s.execute(
            select(UserDeviceRow)
            .where(UserDeviceRow.user_id == user_id)
            .order_by(UserDeviceRow.last_seen_at.desc())
        ).scalars()
    )


def _user_detail(
    row: User,
    events: list[SubscriptionEventRow],
    devices: list[UserDeviceRow] | None = None,
) -> AdminUserDetail:
    # BL11 (AT:R33): compute effective_plan from persisted plan + trial.
    from app.schemas.mandate import Plan
    from app.services.entitlements import effective_plan, is_trial_active
    try:
        _persisted = Plan(row.plan)
    except ValueError:
        _persisted = Plan.FLOOR_PASS
    _effective = effective_plan(_persisted, row.trial_expires_at)
    return AdminUserDetail(
        id=row.id,
        email=row.email,
        phone=row.phone,
        apple_id=row.apple_id,
        google_id=row.google_id,
        plan=row.plan,
        credit_balance=row.credit_balance,
        locale=row.locale,
        timezone=row.timezone,
        is_anonymous=row.is_anonymous,
        device_user_id=row.device_user_id,
        device_model=row.device_model,
        os_version=row.os_version,
        last_app_version=row.last_app_version,
        devices=[
            AdminUserDevice(
                device_install_id=d.device_install_id,
                device_model=d.device_model,
                os_version=d.os_version,
                app_version=d.app_version,
                first_seen_at=d.first_seen_at,
                last_seen_at=d.last_seen_at,
            )
            for d in (devices or [])
        ],
        effective_plan=_effective.value,
        trial_active=is_trial_active(row.trial_expires_at),
        suspended_at=row.suspended_at,
        trial_started_at=row.trial_started_at,
        trial_expires_at=row.trial_expires_at,
        claimed_at=row.claimed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        recent_events=[_event_out(e) for e in events],
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

# CR040: every feature that silently falls back when its config is missing.
# DEF038 and DEF063 both shipped dark for want of one compose line, and nothing
# anywhere could answer "is this actually on in Alpha?" without a shell on the
# box. Adding a feature that degrades silently? Add it here too.
#   (setting attr, human name, what happens when it's NOT configured)
_FEATURE_GATES: list[tuple[str, str, str]] = [
    ("adanos_api_key", "Social Analyst — live Reddit sentiment (CR024)",
     "Social Analyst invents illustrative sentiment (CR037)"),
    ("alpha_vantage_api_key", "News Analyst — Alpha Vantage sentiment merge (CR023)",
     "Yahoo-only headlines; news_source still reads 'live' so the gap is invisible"),
    ("vllm_base_url", "LLM — on-prem vLLM provider",
     "gateway falls back to anthropic/mock"),
    ("kimi_api_key", "LLM — Kimi (Moonshot) provider, candidate B7 (CR126)",
     "LLM_FORCE_PROVIDER=kimi silently falls through to vllm/anthropic/mock"),
    ("use_real_market_data", "Market data — real Yahoo quotes",
     "deterministic mock random-walk prices"),
    ("admin_secret", "Admin back-office auth",
     "admin API returns 503"),
    ("resend_api_key", "Transactional email (magic links)",
     "email send is a no-op"),
    ("sentry_dsn", "Sentry error reporting", "errors are local-log only"),
    ("posthog_api_key", "PostHog analytics", "no product analytics"),
]


def _settings_coverage() -> list[SettingsFieldState]:
    """Every `Settings` field, configured-or-not, derived not listed (CR175 F3).

    `_FEATURE_GATES` above is the right shape for a human reading the output
    and the wrong shape for a guard: it is hand-maintained, and nothing fails
    when it is incomplete. Measured 2026-08-12 it covered **9 of 98 fields** —
    including, notably, not `adanos_api_key_secondary`, which had been wired
    that same week precisely because 250 paid calls/month sat idle undetected.
    The check built to catch silently-absent keys could not see the newest
    silently-absent key.

    Deriving from `Settings.model_fields` is what makes the coverage
    self-maintaining. `test_cr175_config_coverage.py` fails when a field is
    neither annotated above nor excused there, so the annotation stays a
    deliberate act rather than something that rots quietly.

    Booleans only. `bool(value)` on a str/int/list is a presence test; `bool`
    fields are passed through so `USE_REAL_MARKET_DATA=false` reports False
    rather than the truthiness of the string.
    """
    annotated = {attr for attr, _name, _effect in _FEATURE_GATES}
    out: list[SettingsFieldState] = []
    for attr in sorted(Settings.model_fields):
        value = getattr(settings, attr, None)
        configured = value if isinstance(value, bool) else bool(value)
        out.append(SettingsFieldState(
            setting=attr.upper(),
            configured=configured,
            annotated=attr in annotated,
        ))
    return out


@router.get("/config-check", response_model=AdminConfigCheckResponse)
def config_check(_: None = Depends(get_admin)) -> AdminConfigCheckResponse:
    """Report which config-gated features are live in THIS container (CR040).

    Booleans only — never echoes a secret. `dark_count` is the number of
    features silently running on their fallback path; a promotion gate can
    diff this against what infra/alpha.env intends to have enabled.
    """
    gates: list[FeatureGate] = []
    for attr, name, effect in _FEATURE_GATES:
        value = getattr(settings, attr, None)
        configured = bool(value) if not isinstance(value, bool) else value
        gates.append(FeatureGate(
            name=name,
            setting=attr.upper(),
            configured=configured,
            effect_when_unconfigured=effect,
        ))
    # CR121 — surface the version-gate's live state here too. Not a
    # FeatureGate (those are Settings presence checks); this is DB-derived
    # runtime state, same shape as portfolio_health_gate_mode above. This is
    # also the "surfaced in the admin config check" half of the mobile
    # gate's fail-open contract: an operator can always see whether a floor
    # is even configured, independent of whether any one client's fetch
    # happened to succeed.
    with get_session() as session:
        active_floor = get_active_floor(session)

    coverage = _settings_coverage()
    return AdminConfigCheckResponse(
        env=settings.env,
        gates=gates,
        dark_count=sum(1 for g in gates if not g.configured),
        settings_coverage=coverage,
        settings_total=len(coverage),
        one_on_one_credit_cost=settings.one_on_one_credit_cost,
        portfolio_health_gate_mode=settings.portfolio_health_gate_mode,
        client_release_floor_configured=active_floor is not None,
        client_release_floor_min_build=(
            active_floor.min_build if active_floor is not None else None
        ),
    )


@router.post("/release-floor", response_model=AdminReleaseFloorOut)
def raise_release_floor(
    req: AdminReleaseFloorRequest, _: None = Depends(get_admin),
) -> AdminReleaseFloorOut:
    """CR121 — raise the client version floor. One API call, no deploy, no
    container recreate — the entire point of an append-only DB table over an
    env var. Refuses `min_build` above the highest build the server has ever
    observed in `users.last_app_version` / `user_devices.app_version` unless
    `force=true` is passed: raising the floor above what TestFlight has
    actually approved bricks every iOS tester with nowhere to go.
    """
    with get_session() as session:
        try:
            row, highest = create_floor_raise(
                session,
                min_build=req.min_build,
                recommended_build=req.recommended_build,
                headline=req.headline,
                body_en=req.body_en,
                body_ar=req.body_ar,
                body_ms=req.body_ms,
                created_by=req.created_by,
                force=req.force,
            )
        except ReleaseFloorFootgunError as exc:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail={
                    "error": "min_build_exceeds_highest_observed",
                    "min_build": exc.min_build,
                    "highest_observed_build": exc.highest_observed,
                    "hint": "pass force=true to override",
                },
            ) from exc
        except ReleaseFloorDuplicateError as exc:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail={
                    "error": "min_build_already_exists",
                    "min_build": exc.min_build,
                },
            ) from exc
        return AdminReleaseFloorOut(
            id=row.id,
            min_build=row.min_build,
            recommended_build=row.recommended_build,
            headline=row.headline,
            body_en=row.body_en,
            body_ar=row.body_ar,
            body_ms=row.body_ms,
            created_at=row.created_at,
            created_by=row.created_by,
            active=row.active,
            highest_observed_build=highest,
        )


@router.get("/users", response_model=list[AdminUserSummary])
def search_users(
    email: str | None = Query(default=None),
    device_user_id: UUID | None = Query(default=None),
    _: None = Depends(get_admin),
) -> list[AdminUserSummary]:
    if not email and not device_user_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "provide email or device_user_id to search",
        )
    with get_session() as s:
        q = select(User)
        if email:
            q = q.where(User.email == email)
        if device_user_id:
            q = q.where(User.device_user_id == device_user_id)
        rows = s.execute(q.limit(20)).scalars().all()
        return [_user_summary(r) for r in rows]


@router.get("/users/{user_id}", response_model=AdminUserDetail)
def get_user(
    user_id: UUID,
    _: None = Depends(get_admin),
) -> AdminUserDetail:
    with get_session() as s:
        user = _get_user_or_404(s, user_id)
        events = (
            s.execute(
                select(SubscriptionEventRow)
                .where(SubscriptionEventRow.user_id == user_id)
                .order_by(SubscriptionEventRow.created_at.desc())
                .limit(20)
            )
            .scalars()
            .all()
        )
        return _user_detail(user, events, _load_devices(s, user_id))


@router.patch("/users/{user_id}/plan", response_model=AdminUserDetail)
def change_plan(
    user_id: UUID,
    req: AdminPlanChangeRequest,
    _: None = Depends(get_admin),
) -> AdminUserDetail:
    if req.plan not in _VALID_PLANS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"unknown plan '{req.plan}'; valid: {sorted(_VALID_PLANS)}",
        )
    with get_session() as s:
        user = _get_user_or_404(s, user_id)
        old_plan = user.plan
        user.plan = req.plan
        user.updated_at = _utcnow()
        _record_event(
            s,
            user_id=user_id,
            event_type="plan_changed",
            from_value=old_plan,
            to_value=req.plan,
            note=req.note,
        )
        s.flush()
        events = (
            s.execute(
                select(SubscriptionEventRow)
                .where(SubscriptionEventRow.user_id == user_id)
                .order_by(SubscriptionEventRow.created_at.desc())
                .limit(20)
            )
            .scalars()
            .all()
        )
        return _user_detail(user, events, _load_devices(s, user_id))


@router.post("/users/{user_id}/trial", response_model=AdminUserDetail)
def grant_trial(
    user_id: UUID,
    req: AdminTrialGrantRequest,
    _: None = Depends(get_admin),
) -> AdminUserDetail:
    with get_session() as s:
        user = _get_user_or_404(s, user_id)
        old_plan = user.plan
        now = _utcnow()
        user.plan = "trial_trader"
        user.trial_started_at = now
        user.trial_expires_at = now + timedelta(days=req.days)
        user.updated_at = now
        _record_event(
            s,
            user_id=user_id,
            event_type="trial_granted",
            from_value=old_plan,
            to_value=f"trial_trader:{req.days}d",
            note=req.note,
        )
        s.flush()
        events = (
            s.execute(
                select(SubscriptionEventRow)
                .where(SubscriptionEventRow.user_id == user_id)
                .order_by(SubscriptionEventRow.created_at.desc())
                .limit(20)
            )
            .scalars()
            .all()
        )
        return _user_detail(user, events, _load_devices(s, user_id))


@router.patch("/users/{user_id}/trial", response_model=AdminUserDetail)
def update_trial(
    user_id: UUID,
    req: AdminTrialUpdateRequest,
    _: None = Depends(get_admin),
) -> AdminUserDetail:
    with get_session() as s:
        user = _get_user_or_404(s, user_id)
        now = _utcnow()

        if req.action == "extend":
            if not req.days:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST, "days required for action=extend"
                )
            current_expires = user.trial_expires_at or now
            old_val = current_expires.isoformat()
            new_expires = current_expires + timedelta(days=req.days)
            user.trial_expires_at = new_expires
            user.updated_at = now
            _record_event(
                s,
                user_id=user_id,
                event_type="trial_extended",
                from_value=old_val,
                to_value=new_expires.isoformat(),
                note=req.note,
            )

        else:  # revoke
            old_plan = user.plan
            user.plan = "floor_pass"
            user.trial_started_at = None
            user.trial_expires_at = None
            user.updated_at = now
            _record_event(
                s,
                user_id=user_id,
                event_type="trial_revoked",
                from_value=old_plan,
                to_value="floor_pass",
                note=req.note,
            )

        s.flush()
        events = (
            s.execute(
                select(SubscriptionEventRow)
                .where(SubscriptionEventRow.user_id == user_id)
                .order_by(SubscriptionEventRow.created_at.desc())
                .limit(20)
            )
            .scalars()
            .all()
        )
        return _user_detail(user, events, _load_devices(s, user_id))


@router.post("/users/{user_id}/credits", response_model=AdminUserDetail)
def adjust_credits(
    user_id: UUID,
    req: AdminCreditsRequest,
    _: None = Depends(get_admin),
) -> AdminUserDetail:
    if req.delta == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "delta must be non-zero")
    with get_session() as s:
        user = _get_user_or_404(s, user_id)
        old_balance = user.credit_balance
        new_balance = max(0, old_balance + req.delta)
        user.credit_balance = new_balance
        user.updated_at = _utcnow()
        event_type = "credits_added" if req.delta > 0 else "credits_deducted"
        _record_event(
            s,
            user_id=user_id,
            event_type=event_type,
            from_value=str(old_balance),
            to_value=str(new_balance),
            note=req.note,
        )
        s.flush()
        events = (
            s.execute(
                select(SubscriptionEventRow)
                .where(SubscriptionEventRow.user_id == user_id)
                .order_by(SubscriptionEventRow.created_at.desc())
                .limit(20)
            )
            .scalars()
            .all()
        )
        return _user_detail(user, events, _load_devices(s, user_id))


@router.post("/users/{user_id}/suspend", response_model=AdminUserDetail)
def suspend_user(
    user_id: UUID,
    req: AdminNoteRequest,
    _: None = Depends(get_admin),
) -> AdminUserDetail:
    with get_session() as s:
        user = _get_user_or_404(s, user_id)
        if user.suspended_at is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "user is already suspended")
        now = _utcnow()
        user.suspended_at = now
        user.updated_at = now
        _record_event(
            s,
            user_id=user_id,
            event_type="user_suspended",
            from_value="active",
            to_value="suspended",
            note=req.note,
        )
        s.flush()
        events = (
            s.execute(
                select(SubscriptionEventRow)
                .where(SubscriptionEventRow.user_id == user_id)
                .order_by(SubscriptionEventRow.created_at.desc())
                .limit(20)
            )
            .scalars()
            .all()
        )
        return _user_detail(user, events, _load_devices(s, user_id))


@router.post("/users/{user_id}/reinstate", response_model=AdminUserDetail)
def reinstate_user(
    user_id: UUID,
    req: AdminNoteRequest,
    _: None = Depends(get_admin),
) -> AdminUserDetail:
    with get_session() as s:
        user = _get_user_or_404(s, user_id)
        if user.suspended_at is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "user is not suspended")
        now = _utcnow()
        user.suspended_at = None
        user.updated_at = now
        _record_event(
            s,
            user_id=user_id,
            event_type="user_reinstated",
            from_value="suspended",
            to_value="active",
            note=req.note,
        )
        s.flush()
        events = (
            s.execute(
                select(SubscriptionEventRow)
                .where(SubscriptionEventRow.user_id == user_id)
                .order_by(SubscriptionEventRow.created_at.desc())
                .limit(20)
            )
            .scalars()
            .all()
        )
        return _user_detail(user, events, _load_devices(s, user_id))


@router.get("/users/{user_id}/events", response_model=AdminEventsResponse)
def list_events(
    user_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: None = Depends(get_admin),
) -> AdminEventsResponse:
    with get_session() as s:
        _get_user_or_404(s, user_id)
        total = s.execute(
            select(func.count()).where(SubscriptionEventRow.user_id == user_id)
        ).scalar_one()
        rows = (
            s.execute(
                select(SubscriptionEventRow)
                .where(SubscriptionEventRow.user_id == user_id)
                .order_by(SubscriptionEventRow.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            .scalars()
            .all()
        )
        return AdminEventsResponse(
            events=[_event_out(r) for r in rows],
            total=total,
            limit=limit,
            offset=offset,
        )
