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
"""

from __future__ import annotations

import hmac
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import func, select

from app.core.config import settings
from app.db import get_session
from app.db.models import SubscriptionEventRow, User
from app.schemas.admin import (
    AdminCreditsRequest,
    AdminEventsResponse,
    AdminNoteRequest,
    AdminPlanChangeRequest,
    AdminTrialGrantRequest,
    AdminTrialUpdateRequest,
    AdminUserDetail,
    AdminUserSummary,
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


def _user_detail(row: User, events: list[SubscriptionEventRow]) -> AdminUserDetail:
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
        suspended_at=row.suspended_at,
        trial_started_at=row.trial_started_at,
        trial_expires_at=row.trial_expires_at,
        claimed_at=row.claimed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        recent_events=[_event_out(e) for e in events],
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

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
        return _user_detail(user, events)


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
        return _user_detail(user, events)


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
        return _user_detail(user, events)


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
        return _user_detail(user, events)


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
        return _user_detail(user, events)


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
        return _user_detail(user, events)


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
        return _user_detail(user, events)


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
