"""POST /waitlist — public endpoint, no auth required.

Called exclusively by the marketing website's sign-up form. CR267 WP-51 added
the optional profile fields (name, country, platform), the required consent
flag and a honeypot; the batch-invite export lives in `admin_waitlist.py`.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from sqlalchemy import select
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
    name: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=64)
    platform: Literal["ios", "android"] | None = None
    consent: bool = False
    # Honeypot: hidden in the form, so only a bot fills it.
    website: str | None = Field(default=None, max_length=256)

    @field_validator("name", "country", "platform", mode="before")
    @classmethod
    def _blank_is_none(cls, v):
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v


class WaitlistResponse(BaseModel):
    ok: bool
    new: bool


@router.post(
    "/waitlist",
    response_model=WaitlistResponse,
    dependencies=[Depends(waitlist_rate_limit)],
)
def join_waitlist(req: WaitlistRequest) -> WaitlistResponse:
    if req.website:
        # Bot: report success so it learns nothing, store nothing.
        return WaitlistResponse(ok=True, new=False)

    email = req.email.strip().lower()
    if not _EMAIL_RE.match(email):
        return WaitlistResponse(ok=False, new=False)

    if not req.consent:
        raise HTTPException(status_code=422, detail="consent_required")

    now = datetime.now(timezone.utc)
    try:
        with get_session() as s:
            existing = s.scalar(select(WaitlistEntry).where(WaitlistEntry.email == email))
            if existing is None:
                s.add(
                    WaitlistEntry(
                        email=email,
                        source=req.source,
                        name=req.name,
                        country=req.country,
                        platform=req.platform,
                        consent_at=now,
                    )
                )
                return WaitlistResponse(ok=True, new=True)
            if existing.consent_at is None:
                # Row predates the consent box: record it now, never overwrite data.
                existing.consent_at = now
                existing.name = existing.name or req.name
                existing.country = existing.country or req.country
                existing.platform = existing.platform or req.platform
            return WaitlistResponse(ok=True, new=False)
    except IntegrityError:
        return WaitlistResponse(ok=True, new=False)
