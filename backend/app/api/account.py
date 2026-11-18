"""Account closure and data export (CR276, CR267 WP-30).

  GET  /v1/account/policy   What the post-grace step does, in words the app can
                            show before the user commits (public, no secrets).
  POST /v1/account/close    Deactivate the account, revoke every session at once,
                            start the restore window. Authenticated; the body must
                            carry `confirm: true` so a stray call cannot close it.
  GET  /v1/account/export   The user's own data as a downloadable JSON file.

**Restore has no route of its own.** After closure the bearer token is dead
(that is the point), and an anonymous account has no credential to prove
ownership with, so a restore endpoint would have nothing to authenticate. The
restore path is sign-in: an Apple / Google / magic-link sign-in that matches the
closed account inside its window is answered `409 account_pending_deletion`
(with the date), and the same call repeated with `restore_account: true` restores
it. Identity is proved by the provider token, and the restore is explicit.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.db.models import User
from app.services import account_erasure, account_export
from app.services.rate_limit import account_export_rate_limit

router = APIRouter(prefix="/v1/account", tags=["account"])


class CloseAccountRequest(BaseModel):
    confirm: bool = False


class CloseAccountResponse(BaseModel):
    closed: bool
    closure_requested_at: str
    restorable_until: str
    grace_days: int
    mode: str


@router.get("/policy")
def account_policy() -> dict:
    return account_erasure.policy()


@router.post("/close", response_model=CloseAccountResponse)
def close_account(
    req: CloseAccountRequest,
    current_user: User = Depends(get_current_user),
) -> CloseAccountResponse:
    if not req.confirm:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "confirm_required")
    try:
        result = account_erasure.request_closure(current_user.id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    return CloseAccountResponse(
        closed=True,
        closure_requested_at=result.closure_requested_at.isoformat(),
        restorable_until=result.erase_after.isoformat(),
        grace_days=settings.account_closure_grace_days,
        mode=settings.account_erasure_mode,
    )


@router.get("/export")
def export_account(current_user: User = Depends(get_current_user)) -> Response:
    account_export_rate_limit.check(f"user:{current_user.id}")
    doc = account_export.build_export(current_user.id)
    stamp = doc["exported_at"][:10]
    return Response(
        content=json.dumps(doc, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="ami-data-export-{stamp}.json"',
            "Cache-Control": "no-store",
        },
    )
