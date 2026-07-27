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

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from app.core.config import settings
from app.db import get_session
from app.db.models import User
from app.schemas import AgentId
from app.schemas.mandate import Plan


_PLAN_RANK: dict[Plan, int] = {
    Plan.FLOOR_PASS: 0,
    Plan.TRIAL_TRADER: 1,
    Plan.TRADER: 2,
    Plan.FLOOR_MANAGER: 3,
}


def plan_rank(plan: Plan) -> int:
    """Entitlement ordering — higher = more entitled.

    Exposes the private `_PLAN_RANK` so the account-merge conflict rule
    (DEF099) can pick the higher of two plans on claim without ever
    downgrading the surviving account. Unknown plans are treated as the
    floor (rank 0) rather than raising — a merge must never fail on a stray
    plan string.
    """
    return _PLAN_RANK.get(plan, 0)


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


# ── Room analyst roster (CR098) ────────────────────────────────────────────
#
# Tenure-drip pull-back: a FLOOR_PASS user loses Social/News/Market voices as
# their account ages, on three independently-configured `.env` day thresholds.
# Fundamentals is hard-capped out of the withholdable set here in CODE — no
# threshold setting exists for it — so no `.env` value can ever empty the Room.

_WITHHOLDABLE_ORDER: tuple[AgentId, ...] = (
    AgentId.SOCIAL_MEDIA_ANALYST,
    AgentId.NEWS_ANALYST,
    AgentId.MARKET_ANALYST,
)


def _pullback_thresholds() -> dict[AgentId, int]:
    """`.env`-sourced day thresholds, keyed by the three withholdable analysts.

    `0` = never withheld. Negative values are rejected at Settings-construction
    time (config.py field_validator) — this function never sees one; it exists
    so the resolver isn't gluing three `settings.room_pullback_days_*` reads
    inline everywhere it's called.
    """
    return {
        AgentId.SOCIAL_MEDIA_ANALYST: settings.room_pullback_days_social,
        AgentId.NEWS_ANALYST: settings.room_pullback_days_news,
        AgentId.MARKET_ANALYST: settings.room_pullback_days_market,
    }


@dataclass(frozen=True)
class AnalystRoster:
    """The resolved (plan, account_age_days) → analyst roster for one Room run.

    `present` / `withheld` partition the four analysts. `next_step` is the
    single nearest upcoming withhold event for a user who still has some
    analysts left to lose — `(agent, days_until)` or `None` once every
    withholdable analyst is already gone (or none is scheduled to leave).
    """

    present: tuple[AgentId, ...]
    withheld: tuple[AgentId, ...]
    next_step: tuple[AgentId, int] | None


def resolve_analyst_roster(
    plan: Plan,
    account_age_days: int,
    *,
    now: datetime | None = None,  # noqa: ARG001 — clock injected for signature
    # parity with other resolvers/tests (D5 acceptance #3 says "clock
    # injected"); age is passed pre-computed by the caller, so `now` isn't
    # actually consulted here — kept for interface symmetry and future use.
) -> AnalystRoster:
    """Resolve which of the four Room analysts run for this (plan, tenure).

    Only `FLOOR_PASS` (post `effective_plan`) is ever degraded — `TRIAL_TRADER`
    and every paid plan always get all four (CR098 locked decision). Thresholds
    are independent, not ordered steps: any combination of the three `.env`
    ints is legal, so an operator can withhold Market before News if they want
    to — the resolver just evaluates each threshold on its own.

    Fundamentals is never in `withheld` — it has no threshold in
    `_pullback_thresholds()` and is unconditionally prepended to `present`.
    """
    if plan != Plan.FLOOR_PASS:
        return AnalystRoster(
            present=(
                AgentId.FUNDAMENTALS_ANALYST,
                AgentId.MARKET_ANALYST,
                AgentId.NEWS_ANALYST,
                AgentId.SOCIAL_MEDIA_ANALYST,
            ),
            withheld=(),
            next_step=None,
        )

    thresholds = _pullback_thresholds()
    withheld: list[AgentId] = []
    present: list[AgentId] = [AgentId.FUNDAMENTALS_ANALYST]
    upcoming: list[tuple[AgentId, int]] = []
    for agent_id in _WITHHOLDABLE_ORDER:
        threshold = thresholds[agent_id]
        if threshold >= 1 and account_age_days >= threshold:
            withheld.append(agent_id)
        else:
            present.append(agent_id)
            if threshold >= 1:
                upcoming.append((agent_id, threshold - account_age_days))

    next_step: tuple[AgentId, int] | None = None
    if upcoming:
        upcoming.sort(key=lambda pair: pair[1])
        next_step = upcoming[0]

    return AnalystRoster(
        present=tuple(present), withheld=tuple(withheld), next_step=next_step
    )


def account_age_days(created_at: datetime, *, now: datetime | None = None) -> int:
    """Whole days since `created_at` — the resolver's tenure clock.

    Same naive/aware normalization as `is_trial_active` (SQLite test fixtures
    drop tzinfo; Postgres keeps it).
    """
    now = now or datetime.now(timezone.utc)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return max(0, (now - created_at).days)


def resolve_roster_for_user(user_id: UUID, *, now: datetime | None = None) -> AnalystRoster:
    """DB lookup variant of `resolve_analyst_roster` — the Room runner's single
    call site. Missing user (respawn/direct-call path with no row) degrades to
    the full roster rather than guessing a tenure — never withholds on absent
    data (CR040)."""
    with get_session() as s:
        row = s.execute(
            select(User.plan, User.trial_expires_at, User.created_at)
            .where(User.id == user_id)
        ).first()
        if row is None:
            return AnalystRoster(
                present=(
                    AgentId.FUNDAMENTALS_ANALYST, AgentId.MARKET_ANALYST,
                    AgentId.NEWS_ANALYST, AgentId.SOCIAL_MEDIA_ANALYST,
                ),
                withheld=(), next_step=None,
            )
        plan_str, trial_expires, created_at = row
        try:
            plan = Plan(plan_str)
        except ValueError:
            plan = Plan.FLOOR_PASS
        plan = effective_plan(plan, trial_expires)
        age = account_age_days(created_at, now=now)
        return resolve_analyst_roster(plan, age, now=now)
