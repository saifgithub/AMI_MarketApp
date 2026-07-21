"""ORM models for the website API database (ami_website).

Completely separate from the main app's ami_trade database.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Uuid


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _due_in_30d() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=30)


class WaitlistEntry(Base):
    """Marketing site email waitlist.

    One row per unique email. Duplicate submissions are silently ignored
    (the endpoint returns ok=True, new=False).
    """

    __tablename__ = "waitlist"
    __table_args__ = (UniqueConstraint("email", name="uq_waitlist_email"),)

    id: Mapped[str] = mapped_column(Uuid(), primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String, index=True, nullable=False)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class ContactMessage(Base):
    """General-inquiry contact-form submissions (CR049).

    status: received → answered (AI FAQ auto-answer sent) | escalated (human to reply).
    Store-first, tolerant intake — a message is never lost to a soft email/LLM failure.
    """

    __tablename__ = "contact_messages"

    id: Mapped[str] = mapped_column(Uuid(), primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String, index=True, nullable=False)
    subject: Mapped[str | None] = mapped_column(String, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, default="received", nullable=False)
    ai_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class DataRequest(Base):
    """Privacy data-rights requests — access / deletion (CR049).

    GDPR erasure / CCPA / app-store account-deletion. Human-actioned within the
    legal SLA (due_at = created + 30d). Never AI-answered.
    """

    __tablename__ = "data_requests"

    id: Mapped[str] = mapped_column(Uuid(), primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String, index=True, nullable=False)
    request_type: Mapped[str] = mapped_column(String, nullable=False)  # deletion|access|correction|other
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default="received", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    due_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_due_in_30d, nullable=False
    )
