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
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select

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
    )


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
        limit: int = 100,
    ) -> tuple[list[JournalEntry], int, int | None]:
        retention = _retention_days_for_plan(plan)
        with get_session() as s:
            stmt = select(JournalEntryRow).where(JournalEntryRow.user_id == user_id)
            if retention is not None:
                cutoff = datetime.now(timezone.utc) - timedelta(days=retention)
                stmt = stmt.where(JournalEntryRow.created_at >= cutoff)
            if entry_type is not None:
                et = entry_type if isinstance(entry_type, EntryType) else EntryType(entry_type)
                stmt = stmt.where(JournalEntryRow.entry_type == et.value)
            if ticker is not None:
                t = ticker.upper().strip()
                stmt = stmt.where(JournalEntryRow.ticker == t)
            stmt = stmt.order_by(JournalEntryRow.created_at.desc())
            rows = s.execute(stmt).scalars().all()
            entries = [_row_to_entry(r) for r in rows]
            return entries[:limit], len(entries), retention

    def get(self, user_id: UUID, entry_id: UUID) -> JournalEntry | None:
        with get_session() as s:
            row = s.execute(
                select(JournalEntryRow).where(
                    JournalEntryRow.user_id == user_id,
                    JournalEntryRow.id == entry_id,
                )
            ).scalar_one_or_none()
            return _row_to_entry(row) if row else None

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
        """Test-only — shift an entry's created_at to exercise retention rules.

        Lives here (not in tests) so we don't depend on a SQLAlchemy session
        in the test module. Production code never calls this.
        """
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


_store: JournalStore | None = None


def get_journal_store() -> JournalStore:
    global _store
    if _store is None:
        _store = JournalStore()
    return _store
