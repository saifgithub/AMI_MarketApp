"""Decision Journal store — Postgres-backed.

Floor Pass tier sees 30-day retention enforced on read; paid tiers see all
history. We keep older rows in the DB so a tier upgrade restores history.

Entries are appended by capture hooks across the codebase:
  - one_on_one.send_message     → ONE_ON_ONE on conversation end
  - coach.accept                → AGENT_COACH on overlay save
  - lessons.submit_quiz         → LESSON_COMPLETE / AGENT_UNLOCK on pass
  - mandate.patch               → MANDATE_EDIT
  - sim_trade open/close        → SIM_TRADE
  - room.run                    → ROOM_RUN

Reads return Pydantic JournalEntry objects so callers don't see SQLAlchemy
rows. The public sync API matches the previous in-memory store.

Soft delete: DELETE sets deleted_at; all reads filter deleted_at IS NULL —
EXCEPT the two CR136 Portfolio Health reads at the bottom of this class, which
deliberately count and read soft-deleted rows. Deleting a Finding must not mint
free trial budget, and must not wipe the rule hysteresis state the next Finding
reads back.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import delete, or_, select

from app.db import get_session, init_schema
from app.db.models import JournalEntryRow
from app.schemas import Plan
from app.schemas.journal import (
    EntryType,
    JournalEntry,
    JournalEntryCreate,
    Outcome,
)


FLOOR_PASS_RETENTION_DAYS = 30


def _retention_days_for_plan(plan: Plan | str) -> int | None:
    """Floor Pass: 30 days. Paid tiers: unlimited."""
    p = plan if isinstance(plan, Plan) else Plan(plan)
    if p == Plan.FLOOR_PASS:
        return FLOOR_PASS_RETENTION_DAYS
    return None


def _as_utc(value: datetime) -> datetime:
    """SQLite (test fixtures) drops tzinfo; Postgres keeps it. Comparing the two
    shapes raises, so every stored timestamp is normalised on read — the same
    guard entitlements.py:51-55 already carries."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _row_to_entry(row: JournalEntryRow) -> JournalEntry:
    return JournalEntry(
        id=row.id,
        user_id=row.user_id,
        entry_type=EntryType(row.entry_type),
        reference_id=row.reference_id,
        title=row.title,
        summary=row.summary,
        ticker=row.ticker,
        agents_involved=list(row.agents_involved or []),
        mandate_version=row.mandate_version,
        tags=list(row.tags or []),
        user_note=row.user_note,
        outcome=Outcome(row.outcome) if row.outcome else None,
        payload=dict(row.payload or {}),
        created_at=row.created_at,
        deleted_at=row.deleted_at,
    )


# Trash retention: how far back the in-app Trash view looks. Soft-deleted
# rows older than this stay in the DB (recoverable via direct API call or
# psql) but never appear in `list_deleted` — keeps the Trash list to a
# bounded fetch regardless of how long the user's been using the app.
TRASH_VISIBLE_DAYS = 30


class JournalStore:
    def __init__(self) -> None:
        init_schema()

    def append(self, draft: JournalEntryCreate) -> JournalEntry:
        entry = JournalEntry(
            user_id=draft.user_id,
            entry_type=EntryType(draft.entry_type)
            if isinstance(draft.entry_type, str)
            else draft.entry_type,
            reference_id=draft.reference_id,
            title=draft.title,
            summary=draft.summary,
            ticker=draft.ticker,
            agents_involved=draft.agents_involved,
            mandate_version=draft.mandate_version,
            tags=draft.tags,
            user_note=draft.user_note,
            outcome=draft.outcome,
            payload=draft.payload,
        )
        with get_session() as s:
            s.add(JournalEntryRow(
                id=entry.id,
                user_id=entry.user_id,
                entry_type=entry.entry_type,
                reference_id=entry.reference_id,
                title=entry.title,
                summary=entry.summary,
                ticker=entry.ticker,
                agents_involved=list(entry.agents_involved),
                mandate_version=entry.mandate_version,
                tags=list(entry.tags),
                user_note=entry.user_note,
                outcome=entry.outcome,
                payload=dict(entry.payload),
                created_at=entry.created_at,
            ))
        return entry

    def list_for_user(
        self,
        user_id: UUID,
        *,
        plan: Plan | str = Plan.FLOOR_PASS,
        entry_type: EntryType | str | None = None,
        ticker: str | None = None,
        q: str | None = None,
        limit: int = 100,
    ) -> tuple[list[JournalEntry], int, int | None]:
        retention = _retention_days_for_plan(plan)
        with get_session() as s:
            stmt = (
                select(JournalEntryRow)
                .where(JournalEntryRow.user_id == user_id)
                .where(JournalEntryRow.deleted_at.is_(None))
            )
            if retention is not None:
                cutoff = datetime.now(timezone.utc) - timedelta(days=retention)
                stmt = stmt.where(JournalEntryRow.created_at >= cutoff)
            if entry_type is not None:
                et = entry_type if isinstance(entry_type, EntryType) else EntryType(entry_type)
                stmt = stmt.where(JournalEntryRow.entry_type == et.value)
            if ticker is not None:
                t = ticker.upper().strip()
                stmt = stmt.where(JournalEntryRow.ticker == t)
            if q:
                term = f"%{q.strip()}%"
                stmt = stmt.where(
                    or_(
                        JournalEntryRow.title.ilike(term),
                        JournalEntryRow.summary.ilike(term),
                    )
                )
            stmt = stmt.order_by(JournalEntryRow.created_at.desc())
            rows = s.execute(stmt).scalars().all()
            entries = [_row_to_entry(r) for r in rows]
            return entries[:limit], len(entries), retention

    def list_deleted(
        self,
        user_id: UUID,
        *,
        limit: int = 100,
    ) -> tuple[list[JournalEntry], int]:
        """Soft-deleted entries within the trash-visible window.

        Returns entries with `deleted_at IS NOT NULL` AND
        `deleted_at >= now - TRASH_VISIBLE_DAYS`, ordered by most-recently
        deleted first. Older rows still exist in the DB but are out of
        scope for the user-facing trash list.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=TRASH_VISIBLE_DAYS)
        with get_session() as s:
            stmt = (
                select(JournalEntryRow)
                .where(JournalEntryRow.user_id == user_id)
                .where(JournalEntryRow.deleted_at.is_not(None))
                .where(JournalEntryRow.deleted_at >= cutoff)
                .order_by(JournalEntryRow.deleted_at.desc())
            )
            rows = s.execute(stmt).scalars().all()
            entries = [_row_to_entry(r) for r in rows]
            return entries[:limit], len(entries)

    def get(self, user_id: UUID, entry_id: UUID) -> JournalEntry | None:
        with get_session() as s:
            row = s.execute(
                select(JournalEntryRow).where(
                    JournalEntryRow.user_id == user_id,
                    JournalEntryRow.id == entry_id,
                    JournalEntryRow.deleted_at.is_(None),
                )
            ).scalar_one_or_none()
            return _row_to_entry(row) if row else None

    def soft_delete(self, user_id: UUID, entry_id: UUID) -> bool:
        """Mark an entry as deleted. Returns True if found and deleted."""
        with get_session() as s:
            row = s.execute(
                select(JournalEntryRow).where(
                    JournalEntryRow.user_id == user_id,
                    JournalEntryRow.id == entry_id,
                    JournalEntryRow.deleted_at.is_(None),
                )
            ).scalar_one_or_none()
            if row is None:
                return False
            row.deleted_at = datetime.now(timezone.utc)
            s.flush()
            return True

    def restore(self, user_id: UUID, entry_id: UUID) -> bool:
        """Clear deleted_at on a soft-deleted entry. Returns True if restored."""
        with get_session() as s:
            row = s.execute(
                select(JournalEntryRow).where(
                    JournalEntryRow.user_id == user_id,
                    JournalEntryRow.id == entry_id,
                    JournalEntryRow.deleted_at.is_not(None),
                )
            ).scalar_one_or_none()
            if row is None:
                return False
            row.deleted_at = None
            s.flush()
            return True

    def annotate(
        self,
        user_id: UUID,
        entry_id: UUID,
        *,
        note: str | None = None,
        tags: list[str] | None = None,
        outcome: Outcome | str | None = None,
    ) -> JournalEntry | None:
        with get_session() as s:
            row = s.execute(
                select(JournalEntryRow).where(
                    JournalEntryRow.user_id == user_id,
                    JournalEntryRow.id == entry_id,
                    JournalEntryRow.deleted_at.is_(None),
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            if note is not None:
                row.user_note = note
            if tags is not None:
                row.tags = list(tags)
            if outcome is not None:
                row.outcome = outcome.value if isinstance(outcome, Outcome) else outcome
            s.flush()
            return _row_to_entry(row)

    def _backdate_for_test(self, user_id: UUID, entry_id: UUID, created_at: datetime) -> None:
        """Test-only — shift an entry's created_at to exercise retention rules."""
        with get_session() as s:
            row = s.execute(
                select(JournalEntryRow).where(
                    JournalEntryRow.user_id == user_id,
                    JournalEntryRow.id == entry_id,
                )
            ).scalar_one_or_none()
            if row is not None:
                row.created_at = created_at

    def clear(self) -> None:
        with get_session() as s:
            s.execute(delete(JournalEntryRow))

    # ── CR136 Portfolio Health (M08 owns these; M07 consumes) ───────────────
    #
    # Both deliberately include soft-deleted rows, which is exactly why they
    # exist rather than M07 filtering `list_for_user`: that read excludes
    # soft-deleted AND applies the Floor Pass 30-day retention window, either of
    # which would silently hand a user free Findings — delete yesterday's, get
    # today's budget back — or reset a rule's hysteresis band to cleared because
    # the entry holding its state aged out of a plan's view.

    def latest_portfolio_health_entry(
        self, user_id: UUID, portfolio_id: UUID,
    ) -> JournalEntry | None:
        """Newest Finding for this portfolio, soft-deleted included.

        One read serves both callers, and they read different fields of it: the
        rule hysteresis state is taken unconditionally, while the same-day
        idempotency check consults `deleted_at` first — returning a deleted
        entry to the client would answer "regenerate" with a journal id pointing
        at a row the user cannot open.
        """
        with get_session() as s:
            row = s.execute(
                select(JournalEntryRow)
                .where(JournalEntryRow.user_id == user_id)
                .where(
                    JournalEntryRow.entry_type
                    == EntryType.PORTFOLIO_HEALTH_ANALYSIS.value
                )
                .where(JournalEntryRow.reference_id == portfolio_id)
                .order_by(JournalEntryRow.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            return _row_to_entry(row) if row else None

    def portfolio_health_stats(
        self, user_id: UUID, portfolio_id: UUID, *, now: datetime,
    ) -> tuple[int, datetime | None, int]:
        """`(trial_findings_used, first_finding_at, daily_used)`.

        The trial counters are per USER across every `reference_id`, because
        `reset_portfolio` destroys and recreates the portfolio — a per-portfolio
        trial would reset itself every time a user resets their book. The daily
        counter is per PORTFOLIO, per Rev 4, and its day boundary is UTC.
        """
        day_start = now.astimezone(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )
        with get_session() as s:
            base = (
                select(JournalEntryRow)
                .where(JournalEntryRow.user_id == user_id)
                .where(
                    JournalEntryRow.entry_type
                    == EntryType.PORTFOLIO_HEALTH_ANALYSIS.value
                )
            )
            rows = s.execute(base).scalars().all()
            created = [_as_utc(r.created_at) for r in rows]
            daily = sum(
                1
                for r in rows
                if r.reference_id == portfolio_id
                and _as_utc(r.created_at) >= day_start
            )
            return len(rows), (min(created) if created else None), daily


_store: JournalStore | None = None


def get_journal_store() -> JournalStore:
    global _store
    if _store is None:
        _store = JournalStore()
    return _store
