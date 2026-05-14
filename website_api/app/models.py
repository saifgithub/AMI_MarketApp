"""ORM models for the website API database (ami_website).

Completely separate from the main app's ami_trade database.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Uuid


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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
