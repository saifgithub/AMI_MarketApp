"""CR181 — persona telemetry: idempotent ingest + the four deterministic segments.

The segments are Research 08 §8.4's, as predicates over recorded events —
no LLM anywhere (CR038), no guessing:

  bounce  — opened the app (>=1 app_open) and took NO engagement action.
            Engagement = the §8.1 core actions (room / 1-on-1 / lesson /
            trade / challenge / brief) plus firm_open: someone who opened
            the firm screen explored, so they are depth, not a bounce.
  convene — ran the Room at least once (room_convene).
  depth   — opened a 1-on-1, the firm screen, or a lesson (CR181 §3).
  locale  — the app locale in force: the latest event's non-null locale,
            ordered by (occurred_at, received_at). A setting, not a
            location — no PII beyond the user id (CR181 §4).

Ingest is idempotent per (user_id, event_id) via the table's unique
constraint and dialect-native INSERT .. ON CONFLICT DO NOTHING — the DB
decides who wins, not deployment topology (CR095 lesson). Duplicates are
counted and reported to the caller, never silently absorbed (CR040), and
`client_drop` marker rows keep the emitter's discards countable.

Retention — decided at file time per CR181 §3: raw rows live
RETENTION_DAYS (400 — long enough for a year-over-year window read),
swept for the posting user on each ingest. No scheduler, no cron: the
sweep rides the same write path it protects, so it cannot ship dark.

Window semantics everywhere: [since, until) on `occurred_at`, normalized
to UTC. Naive datetimes are taken as UTC — sqlite stores wall-clock
digits, so every bound value must be UTC before it hits the driver.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.db import get_session, init_schema
from app.db.models import PersonaEventRow
from app.schemas.telemetry import TelemetryEventIn

APP_OPEN = "app_open"
CLIENT_DROP = "client_drop"
CONVENE_TYPES = frozenset({"room_convene"})
DEPTH_TYPES = frozenset({"one_on_one_open", "firm_open", "lesson_open"})
CORE_ACTION_TYPES = frozenset({
    "room_convene", "one_on_one_open", "lesson_open",
    "trade_place", "challenge_attempt", "brief_edit",
})
ENGAGEMENT_TYPES = CORE_ACTION_TYPES | DEPTH_TYPES

RETENTION_DAYS = 400


@dataclass(frozen=True)
class PersonaSegments:
    bounce: bool
    convene: bool
    depth: bool
    locale: Optional[str]


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _insert_ignoring_duplicates(session, values: dict) -> bool:
    """True when the row landed; False when (user_id, event_id) already had one.

    Dialect-native upsert so a concurrent duplicate is settled by the
    database, race-free. An unrecognized dialect raises instead of falling
    back to a non-idempotent plain INSERT (degrade loudly, CR040).
    """
    dialect = session.get_bind().dialect.name
    table = PersonaEventRow.__table__
    if dialect == "postgresql":
        stmt = pg_insert(table).values(**values).on_conflict_do_nothing(
            index_elements=["user_id", "event_id"],
        )
    elif dialect == "sqlite":
        stmt = sqlite_insert(table).values(**values).on_conflict_do_nothing(
            index_elements=["user_id", "event_id"],
        )
    else:
        raise RuntimeError(
            f"persona telemetry has no idempotent insert for dialect {dialect!r}"
        )
    return session.execute(stmt).rowcount == 1


def ingest_events(
    user_id: UUID, events: Sequence[TelemetryEventIn],
) -> tuple[int, int]:
    """Store a batch for the token's user. Returns (accepted, duplicates)."""
    init_schema()
    accepted = 0
    duplicates = 0
    now = datetime.now(timezone.utc)
    with get_session() as s:
        for ev in events:
            landed = _insert_ignoring_duplicates(s, {
                "id": uuid4(),
                "user_id": user_id,
                "event_id": ev.event_id,
                "event_type": ev.event_type,
                "occurred_at": _as_utc(ev.occurred_at),
                "received_at": now,
                "locale": ev.locale,
                "count": ev.count,
            })
            if landed:
                accepted += 1
            else:
                duplicates += 1
        cutoff = now - timedelta(days=RETENTION_DAYS)
        s.execute(
            delete(PersonaEventRow).where(
                PersonaEventRow.user_id == user_id,
                PersonaEventRow.occurred_at < cutoff,
            )
        )
    return accepted, duplicates


def _segments_from_rows(
    rows: Sequence[tuple[str, Optional[str]]],
) -> PersonaSegments:
    """The four predicates, over one user's (event_type, locale) rows in
    (occurred_at, received_at) order. Pure — this is the single
    implementation both the per-user read and the counts query go through,
    so the two can never diverge."""
    opened = False
    engaged = False
    convene = False
    depth = False
    locale: Optional[str] = None
    for event_type, row_locale in rows:
        if event_type == APP_OPEN:
            opened = True
        if event_type in ENGAGEMENT_TYPES:
            engaged = True
        if event_type in CONVENE_TYPES:
            convene = True
        if event_type in DEPTH_TYPES:
            depth = True
        if row_locale is not None:
            locale = row_locale
    return PersonaSegments(
        bounce=opened and not engaged,
        convene=convene,
        depth=depth,
        locale=locale,
    )


def derive_segments(
    user_id: UUID, since: datetime, until: datetime,
) -> PersonaSegments:
    """One user's segments over [since, until)."""
    init_schema()
    since, until = _as_utc(since), _as_utc(until)
    with get_session() as s:
        rows = s.execute(
            select(PersonaEventRow.event_type, PersonaEventRow.locale)
            .where(
                PersonaEventRow.user_id == user_id,
                PersonaEventRow.occurred_at >= since,
                PersonaEventRow.occurred_at < until,
            )
            .order_by(PersonaEventRow.occurred_at, PersonaEventRow.received_at)
        ).all()
    return _segments_from_rows([(r.event_type, r.locale) for r in rows])


def segment_counts(since: datetime, until: datetime) -> dict:
    """The CR181 §2 answering query: cohort counts over [since, until).

    Run it for a pre-window and a post-window and compare — that is 'did
    Floor v0.2 move the persona numbers' without a manual archaeology
    pass. Aggregates per user through the same `_segments_from_rows`
    predicates the per-user read uses."""
    init_schema()
    since, until = _as_utc(since), _as_utc(until)
    with get_session() as s:
        rows = s.execute(
            select(
                PersonaEventRow.user_id,
                PersonaEventRow.event_type,
                PersonaEventRow.locale,
                PersonaEventRow.count,
            )
            .where(
                PersonaEventRow.occurred_at >= since,
                PersonaEventRow.occurred_at < until,
            )
            .order_by(PersonaEventRow.occurred_at, PersonaEventRow.received_at)
        ).all()

    per_user: dict[UUID, list[tuple[str, Optional[str]]]] = {}
    dropped_events = 0
    for r in rows:
        per_user.setdefault(r.user_id, []).append((r.event_type, r.locale))
        if r.event_type == CLIENT_DROP:
            dropped_events += r.count

    bounce = convene = depth = 0
    locales: dict[str, int] = {}
    for user_rows in per_user.values():
        seg = _segments_from_rows(user_rows)
        bounce += seg.bounce
        convene += seg.convene
        depth += seg.depth
        if seg.locale is not None:
            locales[seg.locale] = locales.get(seg.locale, 0) + 1

    return {
        "since": since,
        "until": until,
        "users": len(per_user),
        "bounce": bounce,
        "convene": convene,
        "depth": depth,
        "locales": locales,
        "dropped_events": dropped_events,
    }
