"""POST /data-request — privacy data-rights intake (public).

Access / deletion / correction requests (GDPR erasure, CCPA, app-store account
deletion). Logged and human-actioned within 30 days — NEVER AI-answered. Sends
the requester an acknowledgement and notifies the team.

Fronted on the site by the /ami-trade/sad-to-see-you-go page.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from app.core.net import client_ip
from app.db.session import get_session
from app.models import DataRequest
from app.services import email_service
from app.services.rate_limit import data_request_rate_limit
from app.services.turnstile import verify_turnstile

router = APIRouter()

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_VALID_TYPES = {"deletion", "access", "correction", "other"}


class DataRequestBody(BaseModel):
    email: str = Field(max_length=254)
    request_type: str
    details: str | None = Field(default=None, max_length=2000)
    turnstile_token: str | None = None

    @field_validator("request_type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in _VALID_TYPES:
            raise ValueError("invalid_request_type")
        return v


class DataRequestResponse(BaseModel):
    ok: bool


@router.post(
    "/data-request",
    response_model=DataRequestResponse,
    dependencies=[Depends(data_request_rate_limit)],
)
async def submit_data_request(req: DataRequestBody, request: Request) -> DataRequestResponse:
    if not verify_turnstile(req.turnstile_token, remote_ip=client_ip(request)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="verification_failed")

    email = req.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="invalid_email")

    details = (req.details or "").strip() or None

    row = DataRequest(
        email=email, request_type=req.request_type, details=details, status="received"
    )
    with get_session() as s:
        s.add(row)
        s.flush()
        due = row.due_at

    email_service.send_data_request_ack(to=email, request_type=req.request_type)
    email_service.notify_team(
        subject=f"[AMI data request] {req.request_type} — {email}",
        lines=[
            f"Type: {req.request_type}",
            f"Email: {email}",
            f"Due by: {due:%Y-%m-%d}",
            "",
            details or "(no details provided)",
        ],
    )
    return DataRequestResponse(ok=True)
