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
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError

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


class RestoreOutcome(str, Enum):
    """Why an undo did or did not happen.

    `SUPERSEDED` exists because a refused undo and a missing entry are not the
    same fact and must not become the same status code (audit r3, m4).
    """

    RESTORED = "restored"
    NOT_FOUND = "not_found"
    SUPERSEDED = "superseded"


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
                dedupe_key=draft.dedupe_key,
            ))
        return entry

    def append_unique(self, draft: JournalEntryCreate) -> tuple[JournalEntry, bool]:
        """`(entry, created)` — append, or return the row that won the race.

        The `uq_journal_dedupe` constraint is the only thing that actually
        serialises two concurrent writers; an application re-read cannot,
        because the competing INSERT may land immediately after it. Losing the
        race is not an error — the winner's row is exactly what this caller was
        about to write, so it is returned as `created=False`, the same answer a
        same-day replay gets.
        """
        if not draft.dedupe_key:
            raise ValueError("append_unique needs a dedupe_key to deduplicate on")
        try:
            return self.append(draft), True
        except IntegrityError:
            existing = self.find_by_dedupe_key(draft.user_id, draft.dedupe_key)
            if existing is None:
                raise
            return existing, False

    def find_by_dedupe_key(self, user_id: UUID, dedupe_key: str) -> JournalEntry | None:
        """The LIVE row holding this key, if any.

        Tombstones are excluded (CR136-M07 audit r1, B1). This is the loser's
        half of `append_unique`, so whatever it returns is handed to the client
        as the entry it asked for — and a deleted row answered "regenerate" with
        an id pointing into an empty journal. `latest_portfolio_health_entry`'s
        docstring names that exact failure one call earlier; this is the same
        rule applied one call later.
        """
        with get_session() as s:
            row = s.execute(
                select(JournalEntryRow)
                .where(JournalEntryRow.user_id == user_id)
                .where(JournalEntryRow.dedupe_key == dedupe_key)
                .where(JournalEntryRow.deleted_at.is_(None))
                .limit(1)
            ).scalar_one_or_none()
            return _row_to_entry(row) if row else None

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
        """Clear deleted_at on a soft-deleted entry. Returns True if restored.

        Callers that need to tell the refusals apart want `restore_with_reason`;
        this stays boolean because three of its four outcomes mean the same thing
        to every existing caller.
        """
        return self.restore_with_reason(user_id, entry_id) is RestoreOutcome.RESTORED

    def restore_with_reason(self, user_id: UUID, entry_id: UUID) -> RestoreOutcome:
        """`restore`, with the refusals distinguished.

        Undo is the one operation that can turn a legal state into an illegal
        one, because `deleted_at` became a predicate on `uq_journal_dedupe`
        (CR136-M07 audit r1, B1): delete today's Finding, regenerate, then undo,
        and two live rows claim the same day. Letting it through would be an
        IntegrityError raised out of a route whose contract is a boolean.

        That refusal is NOT "entry not found" — the entry exists and is the
        caller's (audit r3, MINOR m4). Reporting it as a 404 would be the same
        misdescription class B1's own log line was graded on: the loud thing
        described quietly and wrongly.
        """
        with get_session() as s:
            row = s.execute(
                select(JournalEntryRow).where(
                    JournalEntryRow.user_id == user_id,
                    JournalEntryRow.id == entry_id,
                    JournalEntryRow.deleted_at.is_not(None),
                )
            ).scalar_one_or_none()
            if row is None:
                return RestoreOutcome.NOT_FOUND
            if row.dedupe_key is not None:
                taken = s.execute(
                    select(JournalEntryRow.id).where(
                        JournalEntryRow.user_id == user_id,
                        JournalEntryRow.entry_type == row.entry_type,
                        JournalEntryRow.dedupe_key == row.dedupe_key,
                        JournalEntryRow.deleted_at.is_(None),
                    ).limit(1)
                ).scalar_one_or_none()
                if taken is not None:
                    return RestoreOutcome.SUPERSEDED
            row.deleted_at = None
            s.flush()
            return RestoreOutcome.RESTORED

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

    def last_portfolio_health_finding_at(self, user_id: UUID) -> datetime | None:
        """Newest Finding timestamp for this USER, soft-deleted included.

        The CR140 cadence clock. Per user and not per portfolio for the same
        reason `portfolio_health_stats` counts per user: `reset_portfolio`
        mints a fresh `uuid4()`, so a per-portfolio clock restarts every time
        the user resets their book — the exact loophole the daily counter
        closed (CR136-M07 audit, MINOR m1). Soft-deleted rows count because
        deleting yesterday's Finding must not bring the next one forward.
        """
        with get_session() as s:
            last_at = s.execute(
                select(func.max(JournalEntryRow.created_at)).where(
                    JournalEntryRow.user_id == user_id,
                    JournalEntryRow.entry_type
                    == EntryType.PORTFOLIO_HEALTH_ANALYSIS.value,
                )
            ).scalar_one()
            return _as_utc(last_at) if last_at is not None else None

    def portfolio_health_stats(
        self, user_id: UUID, portfolio_id: UUID, *, now: datetime,
    ) -> tuple[int, datetime | None, int]:
        """`(trial_findings_used, first_finding_at, daily_used)`.

        Both counters are per USER across every `reference_id`, and for the same
        reason: `reset_portfolio` destroys the row and `ensure_portfolio` mints a
        fresh `uuid4()`, so anything keyed on `portfolio_id` resets itself every
        time a user resets their book.

        The daily counter was per PORTFOLIO, per Rev 4's wording, until the
        CR136-M07 audit (round 1, MINOR m1) pointed out that it made "the only
        limiter on an entitled user" resettable by the user. Saiful's call
        (2026-08-03) was to count per user: a user has exactly one book, so the
        two readings are identical except across resets, and the reset is the
        loophole. `portfolio_id` is still taken because the caller has it and the
        signature is shared with `latest_portfolio_health_entry`, which does
        legitimately want the book.

        The day boundary is UTC.
        """
        # `_as_utc` first, never a bare `astimezone`: astimezone() reinterprets
        # a NAIVE datetime as LOCAL system time, so a caller passing a naive UTC
        # `now` would silently get a day boundary offset by the server's tz —
        # the daily cap resetting hours early or late depending on where the
        # container runs.
        day_start = _as_utc(now).astimezone(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )
        # DEF214: counted in SQL, not in Python. This read runs on BOTH CR136
        # routes — the tiles GET and the Finding POST — and it used to SELECT
        # whole rows for every Finding the user had ever generated, then take
        # `len()` of them. The row count is bounded only by the daily cap
        # working correctly, and M07's own BLOCKER B1 was a live demonstration
        # that the cap is an assumption rather than a property: with it
        # defeated an ordinary user reached ~7,200 rows in a day, every one of
        # them fetched in full on every subsequent request.
        #
        # The trial leg is deliberately still unbounded by date. `evaluate_gate`
        # gates on `used < budget AND days_elapsed < trial_days`, so the window
        # check already ends the trial regardless of the count — bounding the
        # count would change the number reported to the client without changing
        # a single gate decision, which is a semantic change wearing a
        # performance fix's clothes.
        conditions = (
            JournalEntryRow.user_id == user_id,
            JournalEntryRow.entry_type
            == EntryType.PORTFOLIO_HEALTH_ANALYSIS.value,
        )
        with get_session() as s:
            used = s.execute(
                select(func.count())
                .select_from(JournalEntryRow)
                .where(*conditions)
            ).scalar_one()
            first_at = s.execute(
                select(func.min(JournalEntryRow.created_at)).where(*conditions)
            ).scalar_one()
            daily = s.execute(
                select(func.count())
                .select_from(JournalEntryRow)
                .where(*conditions)
                .where(JournalEntryRow.created_at >= day_start)
            ).scalar_one()
            return (
                int(used),
                _as_utc(first_at) if first_at is not None else None,
                int(daily),
            )


_store: JournalStore | None = None


def get_journal_store() -> JournalStore:
    global _store
    if _store is None:
        _store = JournalStore()
    return _store
