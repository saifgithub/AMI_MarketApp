"""WaitlistStore — write-only store for marketing site email captures.

Upserts on email so repeat submissions are idempotent. Source tag records
which surface (marketing_site, referral, etc.) drove the signup.
"""

from __future__ import annotations

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError

from app.db import get_session, init_schema
from app.db.models import WaitlistRow
from app.schemas.waitlist import WaitlistRequest, WaitlistResponse


class WaitlistStore:
    def __init__(self) -> None:
        init_schema()

    def register(self, req: WaitlistRequest) -> WaitlistResponse:
        try:
            with get_session() as s:
                row = WaitlistRow(email=req.email.lower(), source=req.source)
                s.add(row)
                s.flush()
            return WaitlistResponse(ok=True, already_registered=False)
        except IntegrityError:
            # Duplicate email — idempotent, still a success from the caller's view
            return WaitlistResponse(ok=True, already_registered=True)


_store: WaitlistStore | None = None


def get_waitlist_store() -> WaitlistStore:
    global _store
    if _store is None:
        _store = WaitlistStore()
    return _store
