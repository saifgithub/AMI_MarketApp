"""User-facing inbox API — /v1/messages (CR102 in-app tester messaging).

The tester's view of broadcasts + their own replies. Auth is
get_current_user (401s bad tokens, blocks suspended users). Every
per-row route 404s on another user's row — indistinguishable from a
nonexistent id, so ids can't be probed (same pattern as feedback ack).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.db.models import User
from app.schemas.messages import InboxMessageOut, ReplyOut, ReplyRequest
from app.services.inbox_store import get_inbox_store

router = APIRouter(prefix="/v1/messages", tags=["messages"])


@router.get("", response_model=list[InboxMessageOut])
def list_inbox(
    current_user: User = Depends(get_current_user),
) -> list[InboxMessageOut]:
    """The caller's inbox, newest-first, both directions.

    Each row carries read_at — the client derives the unread count —
    and priority + toasted_at for the high-priority cold-start toast.
    """
    return get_inbox_store().list_inbox(current_user.id)


@router.post("/{message_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_read(
    message_id: UUID,
    current_user: User = Depends(get_current_user),
) -> None:
    if not get_inbox_store().mark_read(current_user.id, message_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.post("/{message_id}/reply", response_model=ReplyOut)
def reply(
    message_id: UUID,
    req: ReplyRequest,
    current_user: User = Depends(get_current_user),
) -> ReplyOut:
    out = get_inbox_store().reply(current_user.id, message_id, req.body)
    if out is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return out


@router.post("/{message_id}/toasted", status_code=status.HTTP_204_NO_CONTENT)
def mark_toasted(
    message_id: UUID,
    current_user: User = Depends(get_current_user),
) -> None:
    """Server-side once-only stamp for the priority=high cold-start toast."""
    if not get_inbox_store().mark_toasted(current_user.id, message_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
