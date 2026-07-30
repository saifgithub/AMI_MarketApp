"""Decision Journal endpoints.

GET    /v1/journal/{user_id}                 list entries (filter + search + paginate)
GET    /v1/journal/{user_id}/entry/{id}      single entry detail
POST   /v1/journal/{user_id}/entry/{id}/note attach a user note + tags + outcome
DELETE /v1/journal/{user_id}/entry/{id}      soft-delete (sets deleted_at; not destroyed)
POST   /v1/journal                           append (used by internal capture
                                              hooks and free-form notes)
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.dependencies import get_current_user
from app.db import get_session
from app.db.models import SimTradeRow, User
from app.schemas.journal import (
    EntryType,
    JournalEntry,
    JournalEntryCreate,
    JournalListResponse,
    Outcome,
)
from app.services.entitlements import effective_plan_for_user
from app.services.journal_store import JournalStore, get_journal_store
from app.services.reputation_service import get_reputation_service
from pydantic import BaseModel, Field


router = APIRouter(
    prefix="/v1/journal",
    tags=["journal"],
    dependencies=[Depends(get_current_user)],
)


def _own(current_user: User, user_id: UUID) -> None:
    if current_user.id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "access denied")


class AnnotateRequest(BaseModel):
    note: str | None = None
    tags: list[str] | None = None
    outcome: Outcome | None = None


@router.get("/{user_id}", response_model=JournalListResponse)
async def list_entries(
    user_id: UUID,
    entry_type: str | None = None,
    ticker: str | None = None,
    q: str | None = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    store: JournalStore = Depends(get_journal_store),
) -> JournalListResponse:
    _own(current_user, user_id)
    # DEF202: retention is entitlement-bearing, so it is derived from the
    # authenticated user via `effective_plan_for_user`, not a client-supplied
    # `plan` query param — the same correction DEF179 applies to one_on_one.py
    # and brief_engine.py. A caller could otherwise ask for `floor_manager`
    # retention, or omit the param and silently get `trial_trader`'s.
    plan_enum = effective_plan_for_user(user_id)
    et: EntryType | None = None
    if entry_type:
        try:
            et = EntryType(entry_type)
        except ValueError:
            et = None

    entries, total, retention = store.list_for_user(
        user_id,
        plan=plan_enum,
        entry_type=et,
        ticker=ticker,
        q=q or None,
        limit=limit,
    )
    return JournalListResponse(entries=entries, total=total, retention_days=retention)


@router.get("/{user_id}/trash", response_model=JournalListResponse)
async def list_trash(
    user_id: UUID,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    store: JournalStore = Depends(get_journal_store),
) -> JournalListResponse:
    _own(current_user, user_id)
    """Soft-deleted entries from the last 30 days.

    Rows older than the window stay in the DB (recoverable via the
    restore endpoint or psql) but never surface here — keeps the
    in-app Trash view to a bounded fetch.
    """
    entries, total = store.list_deleted(user_id, limit=limit)
    return JournalListResponse(entries=entries, total=total, retention_days=None)


@router.get("/{user_id}/entry/{entry_id}", response_model=JournalEntry)
async def get_entry(
    user_id: UUID,
    entry_id: UUID,
    current_user: User = Depends(get_current_user),
    store: JournalStore = Depends(get_journal_store),
) -> JournalEntry:
    _own(current_user, user_id)
    entry = store.get(user_id, entry_id)
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "entry not found")
    return entry


@router.post("/{user_id}/entry/{entry_id}/note", response_model=JournalEntry)
async def annotate_entry(
    user_id: UUID,
    entry_id: UUID,
    req: AnnotateRequest,
    current_user: User = Depends(get_current_user),
    store: JournalStore = Depends(get_journal_store),
) -> JournalEntry:
    _own(current_user, user_id)
    updated = store.annotate(
        user_id, entry_id,
        note=req.note, tags=req.tags, outcome=req.outcome,
    )
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "entry not found")

    # Reputation (CR004): reviewing a CLOSED trade (outcome or note on its
    # journal entry) is the reflective habit the app teaches — award it.
    # Entry-id ref dedup + the ≤3/day per-type limit keep it un-farmable.
    if (
        updated.entry_type == EntryType.SIM_TRADE
        and (req.outcome is not None or req.note)
        and updated.reference_id is not None
    ):
        try:
            with get_session() as s:
                trade = s.execute(
                    select(SimTradeRow).where(SimTradeRow.id == updated.reference_id)
                ).scalar_one_or_none()
                if trade is not None and trade.status != "open":
                    get_reputation_service().award(
                        s, user_id=user_id,
                        event_type="trade_reviewed", ref_id=str(entry_id),
                    )
        except Exception:  # pragma: no cover
            pass
    return updated


@router.delete(
    "/{user_id}/entry/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_entry(
    user_id: UUID,
    entry_id: UUID,
    current_user: User = Depends(get_current_user),
    store: JournalStore = Depends(get_journal_store),
) -> None:
    _own(current_user, user_id)
    found = store.soft_delete(user_id, entry_id)
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "entry not found")


@router.post(
    "/{user_id}/entry/{entry_id}/restore",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def restore_entry(
    user_id: UUID,
    entry_id: UUID,
    current_user: User = Depends(get_current_user),
    store: JournalStore = Depends(get_journal_store),
) -> None:
    """Undo a soft-delete — clears deleted_at on the entry.

    Used by the in-app UNDO snackbar after swipe-to-delete. The entry
    row was never actually destroyed, just hidden by `deleted_at`.
    """
    _own(current_user, user_id)
    restored = store.restore(user_id, entry_id)
    if not restored:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "entry not found")


@router.post("", response_model=JournalEntry, status_code=status.HTTP_201_CREATED)
async def append_entry(
    draft: JournalEntryCreate,
    current_user: User = Depends(get_current_user),
    store: JournalStore = Depends(get_journal_store),
) -> JournalEntry:
    if current_user.id != draft.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "access denied")
    return store.append(draft)
