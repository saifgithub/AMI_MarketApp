"""POST /waitlist — public endpoint, no auth required.

Called exclusively by the marketing website's sign-up form.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from sqlalchemy.exc import IntegrityError

from app.db.session import get_session
from app.models import WaitlistEntry
from app.services.rate_limit import waitlist_rate_limit

router = APIRouter()

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class WaitlistRequest(BaseModel):
    # DEF372 (security review M7) — both fields were unbounded. `email` is
    # regex-checked below but that ran AFTER an arbitrarily large body had
    # been parsed, and `source` was never checked at all and goes straight to
    # a DB column. 320 is the RFC-permitted maximum for an address (64 local +
    # @ + 255 domain); `source` is a short campaign tag.
    email: str = Field(max_length=320)
    source: str | None = Field(default=None, max_length=64)


class WaitlistResponse(BaseModel):
    ok: bool
    new: bool


@router.post(
    "/waitlist",
    response_model=WaitlistResponse,
    dependencies=[Depends(waitlist_rate_limit)],
)
def join_waitlist(req: WaitlistRequest) -> WaitlistResponse:
    email = req.email.strip().lower()
    if not _EMAIL_RE.match(email):
        return WaitlistResponse(ok=False, new=False)

    try:
        with get_session() as s:
            s.add(WaitlistEntry(email=email, source=req.source))
        return WaitlistResponse(ok=True, new=True)
    except IntegrityError:
        return WaitlistResponse(ok=True, new=False)
