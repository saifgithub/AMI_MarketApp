"""CR273 (D-084) — the 18+ confirmation gate and its persistence.

Onboarding needs exactly one explicit "I am 18 or older" confirmation. What is
kept is the moment it was given (`OnboardingSession.age_confirmed_at`, copied
to `users.age_confirmed_at`); a birth date or age is never asked for or stored.

The gate is server-side because a prompt or a screen is not a control: any
client that skips the confirmation screen is refused by the routes that call
`require_age_confirmed`.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import structlog
from fastapi import HTTPException, status

from app.core.config import settings
from app.core.time import now_utc
from app.db import get_session
from app.db.models import User
from app.schemas.onboarding import OnboardingSession

logger = structlog.get_logger(__name__)

AGE_CONFIRMATION_REQUIRED = "age_confirmation_required"


def require_age_confirmed(session: OnboardingSession) -> None:
    """403 with a typed `age_confirmation_required` code if the session has no confirmation."""
    if session.age_confirmed_at is None:
        if not settings.onboarding_age_gate_enforced:
            logger.warning(
                "onboarding_age_gate_not_enforced",
                session_id=str(session.id),
                detail="session has no 18+ confirmation; ONBOARDING_AGE_GATE_ENFORCED=false",
            )
            return
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={
                "code": AGE_CONFIRMATION_REQUIRED,
                "message": "Confirm you are 18 or older before continuing.",
            },
        )


def stamp_session(session: OnboardingSession) -> None:
    session.age_confirmed_at = now_utc()


def stamp_user(user_id: UUID, confirmed_at: datetime | None) -> None:
    """Copy the session's confirmation onto the user row. Never overwrites an existing stamp."""
    if confirmed_at is None:
        return
    with get_session() as s:
        row = s.get(User, user_id)
        if row is None or row.age_confirmed_at is not None:
            return
        row.age_confirmed_at = confirmed_at
        s.commit()
