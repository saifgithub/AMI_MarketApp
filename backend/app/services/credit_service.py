"""Credit allowance + spend (CR039, AT:R60).

`users.credit_balance` has existed since the initial schema but was write-only:
`reputation_service` granted streak credits into it and nothing anywhere ever
decremented it. This module is the missing half — the meter behind Convene the
Room, and the first paywall axis the user can actually feel.

Two ideas carry the design:

1. **The ledger already exists.** `SubscriptionEventRow` is documented as the
   audit trail for "every app-side credit consumption"; `credit_balance` is the
   denormalized running total in front of it — the same shape as
   `users.reputation` / `reputation_events`. We add the mirror of
   `reputation_service`'s `credits_added`: `credits_spent`, `credits_refunded`,
   `credits_reset`. No new table.

2. **Re-grant on effective-plan change, not just the calendar.** A 7-day trial
   almost always lapses mid-month. If the allowance only refreshed at month
   rollover, an expired trial would keep its 150 credits for up to three more
   weeks and the user would never feel the downgrade — which is the entire
   point of the cliff. So `credits_plan_at_grant` records the *effective* plan
   the balance was granted under, and drift re-grants immediately.

Allowances and costs come from `docs/initial_specs/06_monetization/` —
`tiers_and_pricing.md` (13/150/500 per month) and `credits.md` (a Basic Room
costs 8). Credits reset monthly and do not accumulate (credits.md), so a
re-grant *sets* the balance rather than adding to it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from app.core.config import settings
from app.db import get_session
from app.db.models import SubscriptionEventRow, User, _utcnow
from app.schemas.mandate import Plan
from app.services.entitlements import effective_plan


# tiers_and_pricing.md:12 — included credits/month.
# Floor Pass's 13 is deliberately "1 Room (8) + 5 one-on-ones (5)".
ALLOWANCE: dict[Plan, int] = {
    Plan.FLOOR_PASS: 13,
    Plan.TRIAL_TRADER: 150,
    Plan.TRADER: 150,
    Plan.FLOOR_MANAGER: 500,
}

# credits.md:19-20 — Basic Room 8 ("Floor Pass / Trader, 1 round", ~$0.80
# retail); Premium Room 25 ("Floor Manager, multi-round", ~$2.50).
#
# Keyed off the **plan**, not the PM's model tier. `room_runner` used to derive
# this as `25 if pick_tier(plan, PORTFOLIO_MANAGER) == "premium" else 8`, which
# conflated two different things: `tier_policy` deliberately routes a
# Trader-plan PM to a premium *model* ("a TRADER-plan PM still gets
# premium-class judgment") as a quality override. That says nothing about which
# Room *product* the user bought. The old expression therefore priced a Trader's
# Basic Room at 25 — 3x the spec, and ~6 Rooms a month instead of ~18. It was
# inert while nothing charged; metering makes it real, so it's corrected here.
ROOM_COST_BASIC = 8
ROOM_COST_PREMIUM = 25

_ROOM_COST_BY_PLAN: dict[Plan, int] = {
    Plan.FLOOR_PASS: ROOM_COST_BASIC,
    Plan.TRIAL_TRADER: ROOM_COST_BASIC,
    Plan.TRADER: ROOM_COST_BASIC,
    Plan.FLOOR_MANAGER: ROOM_COST_PREMIUM,
}


def room_cost_for_plan(plan: Plan) -> int:
    return _ROOM_COST_BY_PLAN.get(plan, ROOM_COST_BASIC)


class InsufficientCredits(Exception):
    """Raised by `spend` when the balance won't cover the operation.

    Carries what the client needs to render the wall without a second call.

    Under a GTM funnel (CR047), the wall can be *soft*: `funnel` names the active
    tactic and `cooldown_until` is when the user may convene again. For "winzip"
    the raise is deliberately paired with an immediate +1-Room re-grant inside
    `spend`, so the 402 the client renders is a countdown, not a dead end.
    """

    def __init__(
        self,
        *,
        balance: int,
        cost: int,
        plan: Plan,
        resets_at: datetime,
        funnel: str | None = None,
        cooldown_until: datetime | None = None,
    ) -> None:
        self.balance = balance
        self.cost = cost
        self.plan = plan
        self.resets_at = resets_at
        self.funnel = funnel
        self.cooldown_until = cooldown_until
        super().__init__(f"insufficient credits: have {balance}, need {cost}")


def _plan_of(user: User) -> Plan:
    try:
        return Plan(user.plan)
    except ValueError:
        return Plan.FLOOR_PASS


def _as_utc(dt: datetime | None) -> datetime | None:
    # SQLite (test fixtures) drops tzinfo; Postgres keeps it. Normalize so
    # comparisons are safe in both — same reason entitlements.py does it.
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _month_start(dt: datetime) -> datetime:
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _next_month_start(dt: datetime) -> datetime:
    return (
        _month_start(dt).replace(year=dt.year + 1, month=1)
        if dt.month == 12
        else _month_start(dt).replace(month=dt.month + 1)
    )


def _record(
    session,
    user: User,
    *,
    old_balance: int,
    event_type: str,
    note: str,
) -> None:
    session.add(SubscriptionEventRow(
        id=uuid4(),
        user_id=user.id,
        event_type=event_type,
        from_value=str(old_balance),
        to_value=str(user.credit_balance),
        source="app",
        note=note,
        created_at=_utcnow(),
    ))


def _ensure_period(session, user: User) -> Plan:
    """Re-grant the monthly allowance if the window rolled or the effective
    plan drifted. Returns the effective plan. Caller must be inside a session.

    `credits_period_start` is always stamped to the month it belongs to, so a
    mid-month plan change doesn't shift the window — it only re-grants.
    """
    eff = effective_plan(_plan_of(user), user.trial_expires_at)
    month_start = _month_start(_utcnow())
    period = _as_utc(user.credits_period_start)

    window_rolled = period is None or period < month_start
    plan_drifted = user.credits_plan_at_grant != eff.value
    if not (window_rolled or plan_drifted):
        return eff

    old_balance = user.credit_balance or 0
    user.credit_balance = ALLOWANCE[eff]
    user.credits_period_start = month_start
    user.credits_plan_at_grant = eff.value
    _record(
        session, user,
        old_balance=old_balance,
        event_type="credits_reset",
        note=f"allowance_{eff.value}",
    )
    return eff


def balance_for(user_id: UUID) -> tuple[int, int, datetime]:
    """(balance, allowance, resets_at) — re-granting first if due.

    Read path for the client. It commits, so the post-trial drop becomes
    visible the next time the app reads the mandate, not at month rollover.
    """
    with get_session() as s:
        user = s.get(User, user_id)
        if user is None:
            now = _utcnow()
            return 0, ALLOWANCE[Plan.FLOOR_PASS], _next_month_start(now)
        eff = _ensure_period(s, user)
        return user.credit_balance, ALLOWANCE[eff], _next_month_start(_utcnow())


def spend(user_id: UUID, amount: int | None, *, reason: str) -> tuple[int, int]:
    """Debit credits, returning (new_balance, cost_charged).

    `amount=None` means "the Room price for this user's effective plan" —
    derived inside the same session as the allowance check, so the charge and
    the allowance can never disagree about which plan the user is on. Callers
    with a fixed price (1-on-1, later) pass an int.

    Raises `InsufficientCredits` when the balance won't cover it — deliberately
    *after* the session commits, so a refused spend still persists any allowance
    re-grant `_ensure_period` just made (raising inside the block would roll it
    back and redo the work on every attempt).
    """
    shortfall: InsufficientCredits | None = None
    new_balance = 0
    cost = 0

    with get_session() as s:
        user = s.get(User, user_id)
        if user is None:
            raise LookupError(f"user {user_id} not found")
        eff = _ensure_period(s, user)
        cost = room_cost_for_plan(eff) if amount is None else amount
        old_balance = user.credit_balance or 0
        now = _utcnow()

        # CR047 "The Winzip" — a soft wall for exhausted Floor-Pass Room
        # convenes. Room-only (`amount is None`), Floor-Pass-only, armed by the
        # GTM_FUNNEL flag. The cooldown, not the balance, is the pacing gate:
        # each exhaustion tops the balance up to exactly one Room, so it must be
        # checked *before* the balance test or the just-granted credit would let
        # the very next convene straight through and the wait would never bite.
        winzip = (
            amount is None
            and eff == Plan.FLOOR_PASS
            and settings.gtm_funnel == "winzip"
        )
        cooldown = _as_utc(user.room_cooldown_until)

        if winzip and cooldown is not None and cooldown > now:
            # Still inside the felt cooldown — block regardless of balance and
            # do not re-grant (the +1 Room from the last reset already waits).
            shortfall = InsufficientCredits(
                balance=old_balance, cost=cost, plan=eff,
                resets_at=_next_month_start(now),
                funnel="winzip", cooldown_until=cooldown,
            )
        elif old_balance >= cost:
            user.credit_balance = old_balance - cost
            new_balance = user.credit_balance
            _record(
                session=s, user=user,
                old_balance=old_balance,
                event_type="credits_spent",
                note=reason,
            )
        elif winzip:
            # Floor-Pass exhaustion under Winzip: reset to exactly one Room and
            # start the cooldown. The 402 still fires (the client renders the
            # countdown), but it's soft — the user returns after the cooldown to
            # spend what we just granted, and the loop repeats. One Room per
            # cooldown, unlimited, the user never actually lost.
            cd = now + timedelta(minutes=settings.winzip_cooldown_minutes)
            user.credit_balance = cost
            user.room_cooldown_until = cd
            _record(
                session=s, user=user,
                old_balance=old_balance,
                event_type="credits_added",
                note="winzip_reset",
            )
            shortfall = InsufficientCredits(
                balance=cost, cost=cost, plan=eff,
                resets_at=_next_month_start(now),
                funnel="winzip", cooldown_until=cd,
            )
        else:
            # Legacy CR039 hard wall (GTM_FUNNEL=none, or a non-Floor-Pass plan
            # / non-Room spend hitting its own balance limit).
            shortfall = InsufficientCredits(
                balance=old_balance,
                cost=cost,
                plan=eff,
                resets_at=_next_month_start(now),
            )

    if shortfall is not None:
        raise shortfall
    return new_balance, cost


# ── CR084: RevenueCat-driven grants ───────────────────────────────────────
#
# These reuse THIS module's allowance mechanism (single ledger — no parallel
# store). They follow the reputation_service.award / admin._record_event
# pattern: the caller (the webhook) owns the session and the commit, so the
# dedup insert, the balance mutation, and the audit row all land in ONE
# transaction. They deliberately do NOT write a subscription_events row — the
# webhook writes the single authoritative source="revenuecat" audit row, so
# attribution is correct and there is exactly one transition row per event.


@dataclass
class AllowanceGrant:
    """Outcome of a subscription-driven plan + allowance change."""

    old_plan: str
    new_plan: str
    effective_plan: Plan
    old_balance: int
    new_balance: int
    granted: bool  # True when a fresh allowance was set for the period


def _plan_from_str(value: str | None) -> Plan:
    if value is None:
        return Plan.FLOOR_PASS
    try:
        return Plan(value)
    except ValueError:
        return Plan.FLOOR_PASS


def set_plan_and_grant_allowance(session, user: User, target_plan: Plan) -> AllowanceGrant:
    """Set `users.plan` to a paid tier and grant that tier's monthly allowance
    for the current period (INITIAL_PURCHASE / RENEWAL / PRODUCT_CHANGE).

    Trial double-grant guard: an active `trial_trader` already granted 150
    credits for this calendar period, and paid `trader` is also 150 — so a
    re-grant fires only when the window rolled to a new period OR the paid
    tier's allowance is strictly larger than what was already granted this
    period (an upgrade top-up, e.g. trader→floor_manager). When it does not
    re-grant it still re-tags `credits_plan_at_grant`, so `_ensure_period`'s
    drift detector won't re-grant on the next balance read.
    """
    old_plan = user.plan
    old_balance = user.credit_balance or 0
    user.plan = target_plan.value
    eff = effective_plan(target_plan, user.trial_expires_at)

    now = _utcnow()
    month_start = _month_start(now)
    period = _as_utc(user.credits_period_start)
    window_rolled = period is None or period < month_start
    current_granted = (
        0 if window_rolled
        else ALLOWANCE.get(_plan_from_str(user.credits_plan_at_grant), 0)
    )
    target_allowance = ALLOWANCE[eff]

    granted = window_rolled or target_allowance > current_granted
    if granted:
        user.credit_balance = target_allowance
    # Either way, attribute the current period to the effective plan so a later
    # balance_for()/_ensure_period() read does not spuriously re-grant.
    user.credits_period_start = month_start
    user.credits_plan_at_grant = eff.value

    return AllowanceGrant(
        old_plan=old_plan,
        new_plan=user.plan,
        effective_plan=eff,
        old_balance=old_balance,
        new_balance=user.credit_balance,
        granted=granted,
    )


def add_credit_pack(session, user: User, amount: int) -> tuple[int, int]:
    """Add purchased (consumable) credits on top of the current period's
    balance (NON_RENEWING_PURCHASE). `_ensure_period` first brings the balance
    to the correct baseline (a rolled window resets to the allowance), then the
    pack stacks on top. Per credits.md the single balance still resets monthly
    — packs top up the current month, they do not accumulate across the reset.
    Returns (old_balance, new_balance). No plan change.
    """
    _ensure_period(session, user)
    old_balance = user.credit_balance or 0
    user.credit_balance = old_balance + amount
    return old_balance, user.credit_balance


def revoke_to_base(session, user: User) -> tuple[str, Plan]:
    """A subscription lapsed (CANCELLATION / EXPIRATION / BILLING_ISSUE). Drop
    `users.plan` to the base; `effective_plan` keeps an active trial. Re-grants
    the now-lower allowance immediately via the existing drift mechanism (the
    CR039 downgrade cliff). Returns (old_plan, effective_plan).
    """
    old_plan = user.plan
    user.plan = Plan.FLOOR_PASS.value
    eff = _ensure_period(session, user)
    return old_plan, eff


def refund(user_id: UUID, amount: int, *, reason: str) -> None:
    """Credit `amount` back — for a run that failed after being billed.

    Deliberately does not `_ensure_period`: a refund is for a spend that already
    happened, and re-granting here would let a rollover between spend and
    failure silently swap the user's window mid-refund. The narrow cost is that
    a run spanning midnight-on-the-1st refunds into the new month's balance,
    over-crediting by the run's cost in the user's favour. Rare, and erring
    toward the user on our own failure is the right side to err on.
    """
    with get_session() as s:
        user = s.get(User, user_id)
        if user is None:
            return
        old_balance = user.credit_balance or 0
        user.credit_balance = old_balance + amount
        _record(
            session=s, user=user,
            old_balance=old_balance,
            event_type="credits_refunded",
            note=reason,
        )
