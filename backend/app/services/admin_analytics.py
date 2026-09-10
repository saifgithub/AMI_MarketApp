"""CR200 — live console analytics: the daily_report.py KPIs as queries.

Portable SQLAlchemy only (runs on melehost Postgres AND the sqlite unit
fixture); day bucketing happens in Python because Alpha-scale volumes are
tiny and `AT TIME ZONE` isn't portable. The nightly CR051 report keeps its
PG-only SQL — this module is the live subset the HEALTH/ANALYTICS tabs need.

Real-human counts by default: user counts apply the deterministic exclusion
filter from the standing alpha-report rule (13 CR035 room-benchmark
synthetics by `last_app_version='room-benchmark'`, 10 seed fixtures by the
2026-05-24 05:10 burst shape, and the CR125/DEF227-229 probe users by id).
Activity/room-run counts are NOT filtered — those probes' room_runs are real
LLM verdicts; it is only the *user* counts they distort.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, not_, select

from app.db import get_session
from app.db.models import (
    JournalEntryRow,
    LessonProgressRow,
    OneOnOneMessageRow,
    RevenueCatEventRow,
    RoomRunRow,
    SimTradeRow,
    SubscriptionEventRow,
    User,
)

# Probe users excluded BY ID (shape-indistinguishable from real bare
# sessions): 2 CR125 promotion probes + 10 DEF227/228/229 live-verification
# convene users (2026-08-07).
_EXCLUDED_USER_IDS = [UUID(x) for x in (
    "ea99a8bc-e612-4569-928d-6ed4d1a0d708",
    "8735d3f2-3cff-43e5-a670-ecd5677226b7",
    "8f45cd0e-565d-4c7d-b621-a956a4f99339",
    "f16d093d-dd9b-41a9-8315-e18e205c09ec",
    "d7edc328-aa28-41d3-9828-795f145b9879",
    "4ae1436a-3aa8-45c0-a502-f4151c8879b6",
    "5d6a5550-895e-45e5-92ca-56891609e7fd",
    "1a6be9ff-6d35-468e-855e-bbaeb187a242",
    "1c5bb79c-920e-4152-a29a-e6a2d41adcbb",
    "fa724aab-83fb-4bbb-a84e-0774f6721226",
    "0310202b-e2ac-42ff-b44e-8d25b8d0e36c",
    "92518daf-b2f7-49dd-857c-60060e2ceef1",
)]

_SEED_BURST_START = datetime(2026, 5, 24, 5, 10, 0, tzinfo=timezone.utc)
_SEED_BURST_END = datetime(2026, 5, 24, 5, 11, 0, tzinfo=timezone.utc)


def _real_users_clause():
    return and_(
        func.coalesce(User.last_app_version, "") != "room-benchmark",
        not_(and_(
            User.created_at >= _SEED_BURST_START,
            User.created_at < _SEED_BURST_END,
            User.device_model.is_(None),
            User.last_app_version.is_(None),
        )),
        User.id.notin_(_EXCLUDED_USER_IDS),
    )


def real_users_where_sql() -> str:
    """`_real_users_clause()` compiled to a literal Postgres boolean expression.

    DEF403 — the CR051 lineage (`scripts/analytics/daily_report.py`,
    `scripts/users.sh`, `backend/scripts/weekly_room_retro.py`) needs this
    rule outside the ORM: `daily_report.py` and `users.sh` run raw SQL over
    SSH from a host with no `app` import path, so they cannot call
    `_real_users_clause()` directly. This is the one place the rule is
    written down; every other site asks for its SQL rather than restating
    it. Compiles offline (`literal_binds=True`) — no DB connection needed,
    only the Postgres dialect's rendering of the same clause the ORM
    filters use. Column names are bare (`users.id` → `id`) so the fragment
    drops into a raw `WHERE` clause unqualified; callers that alias the
    table must not need to, since every existing raw-SQL site queries
    `users` directly.
    """
    from sqlalchemy.dialects import postgresql

    compiled = _real_users_clause().compile(
        dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
    )
    return str(compiled).replace("users.", "")


def is_real_user(user: User) -> bool:
    """`_real_users_clause()`, evaluated in Python against one loaded `User`.

    For callers that already hold `User` rows in memory rather than
    building a query — `inbox_store.py`'s audience resolution being the
    motivating case (DEF403) — and would otherwise re-derive the same three
    checks by hand. Kept semantically identical to `_real_users_clause()`
    on purpose: same three conjuncts, same constants, just evaluated
    client-side instead of compiled to SQL.
    """
    if (user.last_app_version or "") == "room-benchmark":
        return False
    created = user.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    if (
        _SEED_BURST_START <= created < _SEED_BURST_END
        and user.device_model is None
        and user.last_app_version is None
    ):
        return False
    if user.id in _EXCLUDED_USER_IDS:
        return False
    return True


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    # sqlite returns naive datetimes; every writer in this codebase stamps UTC.
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


# (model, timestamp column) — every table whose rows mean "this user did
# something in the app". The union drives DAU/WAU/MAU and the active series.
_ACTIVITY_SOURCES = (
    (RoomRunRow, RoomRunRow.started_at),
    (SimTradeRow, SimTradeRow.opened_at),
    (JournalEntryRow, JournalEntryRow.created_at),
    (OneOnOneMessageRow, OneOnOneMessageRow.created_at),
    (LessonProgressRow, LessonProgressRow.started_at),
)


def _activity_events(s, since: datetime) -> list[tuple[UUID, datetime]]:
    out: list[tuple[UUID, datetime]] = []
    for model, ts_col in _ACTIVITY_SOURCES:
        rows = s.execute(
            select(model.user_id, ts_col).where(ts_col >= since)
        ).all()
        out.extend((uid, _as_utc(ts)) for uid, ts in rows if ts is not None)
    return out


def summary() -> dict[str, Any]:
    now = _utcnow()
    with get_session() as s:
        real = _real_users_clause()
        total = s.execute(
            select(func.count()).select_from(User).where(real)
        ).scalar_one()
        claimed = s.execute(
            select(func.count()).select_from(User)
            .where(real, User.is_anonymous.is_(False))
        ).scalar_one()
        suspended = s.execute(
            select(func.count()).select_from(User)
            .where(real, User.suspended_at.isnot(None))
        ).scalar_one()
        in_trial = s.execute(
            select(func.count()).select_from(User)
            .where(real, User.trial_expires_at > now)
        ).scalar_one()
        by_plan = {
            plan: n for plan, n in s.execute(
                select(User.plan, func.count()).where(real).group_by(User.plan)
            )
        }
        credit_sum = s.execute(
            select(func.coalesce(func.sum(User.credit_balance), 0)).where(real)
        ).scalar_one()
        # CR203: how many users report a linked Alpaca paper account. Device-
        # reported and therefore a floor, not a census — see `User.alpaca_linked_at`.
        alpaca_linked = s.execute(
            select(func.count()).select_from(User)
            .where(real, User.alpaca_linked_at.isnot(None))
        ).scalar_one()

        events = _activity_events(s, now - timedelta(days=30))
        def _active(days: int) -> int:
            cutoff = now - timedelta(days=days)
            return len({uid for uid, ts in events if ts >= cutoff})

        return {
            "users": {
                "total": total,
                "claimed": claimed,
                "anonymous": total - claimed,
                "suspended": suspended,
                "in_trial": in_trial,
                "by_plan": by_plan,
                "credit_balance_sum": int(credit_sum),
                "alpaca_linked": alpaca_linked,
            },
            "active": {
                "dau": _active(1),
                "wau": _active(7),
                "mau": _active(30),
            },
        }


def timeseries(days: int = 30) -> dict[str, Any]:
    """Per-UTC-day series, oldest → newest, zero-filled."""
    now = _utcnow()
    start_day = (now - timedelta(days=days - 1)).date()
    day_keys = [
        (start_day + timedelta(days=i)).isoformat() for i in range(days)
    ]

    def _bucket(pairs: list[datetime]) -> dict[str, int]:
        out = {k: 0 for k in day_keys}
        for ts in pairs:
            k = _as_utc(ts).date().isoformat()
            if k in out:
                out[k] += 1
        return out

    since = datetime.combine(start_day, datetime.min.time(), tzinfo=timezone.utc)
    with get_session() as s:
        signups = [
            _as_utc(ts) for (ts,) in s.execute(
                select(User.created_at)
                .where(_real_users_clause(), User.created_at >= since)
            )
        ]
        rooms = [
            _as_utc(ts) for (ts,) in s.execute(
                select(RoomRunRow.started_at)
                .where(RoomRunRow.started_at >= since)
            ) if ts is not None
        ]
        events = _activity_events(s, since)
        active_by_day: dict[str, set] = {k: set() for k in day_keys}
        for uid, ts in events:
            k = ts.date().isoformat()
            if k in active_by_day:
                active_by_day[k].add(uid)
        spent_rows = s.execute(
            select(SubscriptionEventRow.created_at,
                   SubscriptionEventRow.from_value,
                   SubscriptionEventRow.to_value)
            .where(
                SubscriptionEventRow.event_type == "credits_spent",
                SubscriptionEventRow.created_at >= since,
            )
        ).all()

    credits_spent = {k: 0 for k in day_keys}
    for ts, from_v, to_v in spent_rows:
        k = _as_utc(ts).date().isoformat()
        if k not in credits_spent:
            continue
        try:
            credits_spent[k] += max(0, int(from_v) - int(to_v))
        except (TypeError, ValueError):
            credits_spent[k] += 0

    return {
        "days": day_keys,
        "signups": [_bucket(signups)[k] for k in day_keys],
        "active_users": [len(active_by_day[k]) for k in day_keys],
        "room_runs": [_bucket(rooms)[k] for k in day_keys],
        "credits_spent": [credits_spent[k] for k in day_keys],
    }


def revenuecat(days: int = 30) -> dict[str, Any]:
    since = _utcnow() - timedelta(days=days)
    with get_session() as s:
        counts = {
            et: n for et, n in s.execute(
                select(RevenueCatEventRow.event_type, func.count())
                .where(RevenueCatEventRow.received_at >= since)
                .group_by(RevenueCatEventRow.event_type)
            )
        }
        recent = s.execute(
            select(
                RevenueCatEventRow.event_type,
                RevenueCatEventRow.received_at,
            )
            .where(RevenueCatEventRow.received_at >= since)
            .order_by(RevenueCatEventRow.received_at.desc())
            .limit(50)
        ).all()
    return {
        "counts": counts,
        "recent": [
            {"event_type": et, "received_at": _as_utc(ts).isoformat()}
            for et, ts in recent
        ],
    }


def _cli() -> int:
    """`python3 -m app.services.admin_analytics` — prints the CR051
    real-users WHERE fragment (DEF403).

    Callable from inside `ami_api_alpha` (the only place `app` is on
    PYTHONPATH) so a host-level script — `scripts/analytics/daily_report.py`,
    `scripts/users.sh` — can fetch the canonical rule via
    `docker exec ami_api_alpha python3 -m app.services.admin_analytics`
    instead of hand-copying it. No DB connection required: the clause is
    compiled offline.
    """
    print(real_users_where_sql())
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
