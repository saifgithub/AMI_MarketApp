"""Waitlist request/response schemas — marketing site lead capture."""

from __future__ import annotations

import re

from fastapi import HTTPException, status
from pydantic import BaseModel, field_validator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class WaitlistRequest(BaseModel):
    email: str
    source: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid email address",
            )
        return v


class WaitlistResponse(BaseModel):
    ok: bool
    already_registered: bool = False
