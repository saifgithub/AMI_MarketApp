"""Effective-plan resolution (BL11, AT:R33).

Source of truth for what tier the user is *currently* entitled to,
given their persisted plan + trial window. Keeps `users.plan` immutable
between explicit admin/conversion events — automatic trial expiry is
expressed as a virtual downgrade, not a DB mutation.

Used by every pick_tier caller so when a tester's 7-day trial lapses
the LLM routing drops to cheap-tier automatically; without this the
expired-trial user keeps getting mid-tier model calls forever.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from app.db import get_session
from app.db.models import User
from app.schemas.mandate import Plan


_PLAN_RANK: dict[Plan, int] = {
    Plan.FLOOR_PASS: 0,
    Plan.TRIAL_TRADER: 1,
    Plan.TRADER: 2,
    Plan.FLOOR_MANAGER: 3,
}


def is_trial_active(trial_expires_at: datetime | None) -> bool:
    if trial_expires_at is None:
        return False
    # SQLite (test fixtures) returns naive datetimes that drop tzinfo.
    # Postgres returns tz-aware. Normalize so the comparison is safe in both.
    if trial_expires_at.tzinfo is None:
        trial_expires_at = trial_expires_at.replace(tzinfo=timezone.utc)
    return trial_expires_at > datetime.now(timezone.utc)


def effective_plan(plan: Plan, trial_expires_at: datetime | None) -> Plan:
    """Return the plan to use for entitlement decisions.

    Three cases:
      1. Active trial → at least TRIAL_TRADER (never downgrade a paid plan)
      2. Expired trial + plan=TRIAL_TRADER → FLOOR_PASS
      3. Otherwise → plan unchanged

    Covers both trial paths:
      - Auto-claim (plan=FLOOR_PASS, trial set on first claim → AT:R31 BL3)
      - Admin-granted (plan=TRIAL_TRADER, set by /v1/admin/.../trial)
    """
    if is_trial_active(trial_expires_at):
        if _PLAN_RANK[plan] < _PLAN_RANK[Plan.TRIAL_TRADER]:
            return Plan.TRIAL_TRADER
        return plan
    # Trial inactive (expired or never granted)
    if plan == Plan.TRIAL_TRADER:
        return Plan.FLOOR_PASS
    return plan


def effective_plan_for_user(user_id: UUID) -> Plan:
    """DB lookup variant — used at pick_tier call sites that have user_id
    but no User row in hand."""
    with get_session() as s:
        row = s.execute(
            select(User.plan, User.trial_expires_at).where(User.id == user_id)
        ).first()
        if row is None:
            return Plan.FLOOR_PASS
        plan_str, trial_expires = row
        try:
            plan = Plan(plan_str)
        except ValueError:
            plan = Plan.FLOOR_PASS
        return effective_plan(plan, trial_expires)
