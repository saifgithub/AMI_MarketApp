"""POST /waitlist — public endpoint, no auth required.

Called exclusively by the marketing website's sign-up form.
"""

from __future__ import annotations

import re

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from app.db.session import get_session
from app.models import WaitlistEntry

router = APIRouter()

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class WaitlistRequest(BaseModel):
    email: str
    source: str | None = None


class WaitlistResponse(BaseModel):
    ok: bool
    new: bool


@router.post("/waitlist", response_model=WaitlistResponse)
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
