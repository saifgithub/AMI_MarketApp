"""User identity + plan state."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.mandate import Plan


class User(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: UUID
    email: str | None = None
    phone: str | None = None
    hms_unionid: str | None = None
    apple_id: str | None = None
    google_id: str | None = None

    plan: Plan = Plan.FLOOR_PASS
    trial_started_at: datetime | None = None
    trial_expires_at: datetime | None = None

    credit_balance: int = 0
    free_one_on_ones_used_this_period: int = 0
    free_rooms_used_this_period: int = 0
    period_resets_at: datetime | None = None

    reputation: int = 0

    locale: str = "en"
    timezone: str = "UTC"

    is_anonymous: bool = False
    anonymous_session_started_at: datetime | None = None

    created_at: datetime
    updated_at: datetime
