"""Decision Journal store. In-memory; Postgres at W7.

Floor Pass retention: 30 days, enforced on read (we keep all entries in
memory so a tier upgrade restores history).

Entries are appended by capture hooks across the codebase:
  - one_on_one.send_message — appends an entry on conversation end
  - coach.accept — appends an entry on overlay save
  - lesson_complete — appends on quiz pass
  - mandate_edit — appends on Settings → My Mandate save
  - sim_trade — appended in W6
  - room_run — appended in W6
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from threading import RLock
from uuid import UUID

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


class JournalStore:
    def __init__(self) -> None:
        # user_id → list[JournalEntry] (newest at the end)
        self._entries: dict[UUID, list[JournalEntry]] = defaultdict(list)
        self._lock = RLock()

    def append(self, draft: JournalEntryCreate) -> JournalEntry:
        with self._lock:
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
            self._entries[draft.user_id].append(entry)
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
        with self._lock:
            entries = list(self._entries.get(user_id, []))

        retention = _retention_days_for_plan(plan)
        if retention is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=retention)
            entries = [e for e in entries if e.created_at >= cutoff]

        if entry_type is not None:
            et = entry_type if isinstance(entry_type, EntryType) else EntryType(entry_type)
            entries = [e for e in entries if e.entry_type == et.value]

        if ticker is not None:
            t = ticker.upper().strip()
            entries = [e for e in entries if (e.ticker or "").upper() == t]

        entries.sort(key=lambda e: e.created_at, reverse=True)
        total = len(entries)
        return entries[:limit], total, retention

    def get(self, user_id: UUID, entry_id: UUID) -> JournalEntry | None:
        with self._lock:
            for e in self._entries.get(user_id, []):
                if e.id == entry_id:
                    return e
        return None

    def annotate(
        self,
        user_id: UUID,
        entry_id: UUID,
        *,
        note: str | None = None,
        tags: list[str] | None = None,
        outcome: Outcome | str | None = None,
    ) -> JournalEntry | None:
        with self._lock:
            entries = self._entries.get(user_id, [])
            for i, e in enumerate(entries):
                if e.id == entry_id:
                    updated = e.model_copy(
                        update={
                            "user_note": note if note is not None else e.user_note,
                            "tags": tags if tags is not None else e.tags,
                            "outcome": (
                                Outcome(outcome) if isinstance(outcome, str) and outcome
                                else outcome if outcome is not None
                                else e.outcome
                            ),
                        }
                    )
                    entries[i] = updated
                    return updated
        return None

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


_store: JournalStore | None = None


def get_journal_store() -> JournalStore:
    global _store
    if _store is None:
        _store = JournalStore()
    return _store
