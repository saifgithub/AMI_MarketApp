"""Decision Journal endpoints.

GET    /v1/journal/{user_id}                 list entries (filter + search + paginate)
GET    /v1/journal/{user_id}/entry/{id}      single entry detail
POST   /v1/journal/{user_id}/entry/{id}/note attach a user note + tags + outcome
DELETE /v1/journal/{user_id}/entry/{id}      soft-delete (sets deleted_at; not destroyed)
POST   /v1/journal                           DELETED (DEF371) — see the note below
                                              hooks and free-form notes)
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.admin import get_admin
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
from app.services.journal_store import (
    JournalStore,
    RestoreOutcome,
    get_journal_store,
)
from app.services.reputation_service import get_reputation_service
from pydantic import BaseModel, Field


# The Dart client switches on this string; it lives here rather than inline so a
# rename fails a parity test rather than a user's undo (DEF210).
RESTORE_SUPERSEDED_CODE = "journal_restore_superseded"

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
    outcome = store.restore_with_reason(user_id, entry_id)
    if outcome is RestoreOutcome.SUPERSEDED:
        # The entry exists and is this caller's; it is refused because a newer
        # live row holds its dedupe key — delete today's Finding, regenerate,
        # then undo. Reporting that as "entry not found" would describe a real,
        # owned, restorable-looking row as missing (CR136-M07 audit r3, m4).
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "code": RESTORE_SUPERSEDED_CODE,
                "message": (
                    "A newer entry has already taken this one's place. "
                    "Undo is no longer available for it."
                ),
            },
        )
    if outcome is not RestoreOutcome.RESTORED:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "entry not found")


# DEF371 (security review M11) — `POST /v1/journal` was DELETED, not gated.
#
# The finding: `_activity_days` counts `JournalEntryRow.created_at` from any
# source, and this route accepted an arbitrary entry from any authenticated
# user. One throwaway POST a day walked the 7/30/100/365 streak ladder for
# **630 real credits** while doing nothing the streak exists to reward.
#
# The review's suggested fix was "only system-generated entry types qualify".
# That does not work as stated: EVERY value of `EntryType` is
# system-generated — room_run, sim_trade, lesson_complete, all of them are
# written by internal capture. There is no user-authored type to exclude, so a
# type filter excludes nothing. The vector was the route.
#
# Gating it behind `get_admin` was tried first and does not work either: this
# router already carries `dependencies=[Depends(get_current_user)]`, and both
# gates read the same `Authorization` header, so a caller presenting the admin
# secret cannot also present a user bearer. The route would have been
# satisfiable by nobody — an outage with good intentions.
#
# Deleting it costs nothing, which is why it is the right answer:
#   * the app never called it — `api_client.dart` uses `/v1/journal/{user}`
#     (read), `/entry/{id}`, `/note`, `/restore`, `/trash`, never the bare POST;
#   * internal capture (`sim_trade_effects`, `room_runner`, `daily_challenge`,
#     …) calls `get_journal_store().append(...)` in Python and never crosses
#     HTTP;
#   * a repo-wide search for callers returned only this defect's own test.
#
# No caller, one abuser — the same shape as C2's unauthenticated LLM proxy.
# If an operator path is ever genuinely needed, it belongs on the admin router
# with its own auth, not on the user-facing journal router.
