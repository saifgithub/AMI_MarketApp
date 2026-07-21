"""POST /contact — general-inquiry contact form (public).

Flow (store-first, tolerant intake — a message is never lost to a soft failure):
  1. Turnstile + rate-limit + validation.
  2. Store the message (status=received).
  3. Try an AI FAQ auto-answer (deterministic escalation floor in faq_answer):
       - answerable → email the answer, mark 'answered'.
       - not answerable / advice / account / legal → ack the sender + notify the
         team, mark 'escalated'.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.core.net import client_ip
from app.db.session import get_session
from app.models import ContactMessage
from app.services import email_service
from app.services.faq_answer import answer_for_email
from app.services.rate_limit import contact_rate_limit
from app.services.turnstile import verify_turnstile

router = APIRouter()

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ContactRequest(BaseModel):
    email: str = Field(max_length=254)
    subject: str | None = Field(default=None, max_length=200)
    message: str = Field(min_length=1, max_length=4000)
    turnstile_token: str | None = None


class ContactResponse(BaseModel):
    ok: bool
    answered: bool  # True → an AI answer was emailed; False → a human will follow up


@router.post("/contact", response_model=ContactResponse, dependencies=[Depends(contact_rate_limit)])
async def submit_contact(req: ContactRequest, request: Request) -> ContactResponse:
    if not verify_turnstile(req.turnstile_token, remote_ip=client_ip(request)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="verification_failed")

    email = req.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="invalid_email")

    subject = (req.subject or "").strip() or None
    body = req.message.strip()

    # 1. Store first — never lose the message.
    row = ContactMessage(email=email, subject=subject, body=body, status="received")
    with get_session() as s:
        s.add(row)
        s.flush()
        row_id = row.id

    # 2. Attempt an auto-answer.
    handled, answer = await answer_for_email(body)

    if handled and answer:
        email_service.send_contact_answer(to=email, question=body, answer=answer)
        _update_status(row_id, "answered", ai_answer=answer)
        return ContactResponse(ok=True, answered=True)

    # 3. Escalate to a human.
    email_service.send_contact_ack(to=email)
    email_service.notify_team(
        subject=f"[AMI contact] {subject or 'New message'}",
        lines=[f"From: {email}", f"Subject: {subject or '(none)'}", "", body],
    )
    _update_status(row_id, "escalated")
    return ContactResponse(ok=True, answered=False)


def _update_status(row_id: str, new_status: str, *, ai_answer: str | None = None) -> None:
    with get_session() as s:
        row = s.get(ContactMessage, row_id)
        if row is not None:
            row.status = new_status
            if ai_answer is not None:
                row.ai_answer = ai_answer
