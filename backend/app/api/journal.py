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

from app.schemas import Plan
from app.schemas.journal import (
    EntryType,
    JournalEntry,
    JournalEntryCreate,
    JournalListResponse,
    Outcome,
)
from app.services.journal_store import JournalStore, get_journal_store
from pydantic import BaseModel, Field


router = APIRouter(prefix="/v1/journal", tags=["journal"])


class AnnotateRequest(BaseModel):
    note: str | None = None
    tags: list[str] | None = None
    outcome: Outcome | None = None


@router.get("/{user_id}", response_model=JournalListResponse)
async def list_entries(
    user_id: UUID,
    plan: str = "trial_trader",
    entry_type: str | None = None,
    ticker: str | None = None,
    q: str | None = None,
    limit: int = 100,
    store: JournalStore = Depends(get_journal_store),
) -> JournalListResponse:
    try:
        plan_enum = Plan(plan)
    except ValueError:
        plan_enum = Plan.TRIAL_TRADER
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


@router.get("/{user_id}/entry/{entry_id}", response_model=JournalEntry)
async def get_entry(
    user_id: UUID,
    entry_id: UUID,
    store: JournalStore = Depends(get_journal_store),
) -> JournalEntry:
    entry = store.get(user_id, entry_id)
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "entry not found")
    return entry


@router.post("/{user_id}/entry/{entry_id}/note", response_model=JournalEntry)
async def annotate_entry(
    user_id: UUID,
    entry_id: UUID,
    req: AnnotateRequest,
    store: JournalStore = Depends(get_journal_store),
) -> JournalEntry:
    updated = store.annotate(
        user_id, entry_id,
        note=req.note, tags=req.tags, outcome=req.outcome,
    )
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "entry not found")
    return updated


@router.delete(
    "/{user_id}/entry/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_entry(
    user_id: UUID,
    entry_id: UUID,
    store: JournalStore = Depends(get_journal_store),
) -> None:
    found = store.soft_delete(user_id, entry_id)
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "entry not found")


@router.post("", response_model=JournalEntry, status_code=status.HTTP_201_CREATED)
async def append_entry(
    draft: JournalEntryCreate,
    store: JournalStore = Depends(get_journal_store),
) -> JournalEntry:
    return store.append(draft)
