"""Waitlist route — marketing site lead capture.

POST /v1/waitlist  — register an email address for early access
  Body: { "email": "...", "source": "marketing_site" }
  Returns: { "ok": true, "already_registered": false }

No auth required — this is a public endpoint hit from the marketing website.
Upserts on email so repeat submissions are safe.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.schemas.waitlist import WaitlistRequest, WaitlistResponse
from app.services.waitlist_store import get_waitlist_store

router = APIRouter(prefix="/v1/waitlist", tags=["waitlist"])


@router.post("", response_model=WaitlistResponse, status_code=status.HTTP_200_OK)
async def register_waitlist(req: WaitlistRequest) -> WaitlistResponse:
    return get_waitlist_store().register(req)
