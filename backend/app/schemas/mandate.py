"""Mandate schema — the user's financial profile injected into every agent's prompt.

See docs/initial_specs/03_onboarding/mandate_schema.md for the full spec.
"""

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PrimaryGoal(str, Enum):
    RETIREMENT = "retirement"
    LONG_TERM_WEALTH = "long_term_wealth"
    INCOME_NOW = "income_now"
    SPECIFIC_GOAL = "specific_goal"
    LEARNING_TO_TRADE = "learning_to_trade"
    EXPLORING = "exploring"


class Horizon(str, Enum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"
    VERY_LONG = "very_long"


class Path(str, Enum):
    ACTIVE = "active"
    LONG_HORIZON = "long_horizon"
    BOTH = "both"


class LearningStyle(str, Enum):
    QUICK = "quick"
    STORY = "story"
    VISUAL = "visual"
    HANDS_ON = "hands_on"


class Plan(str, Enum):
    FLOOR_PASS = "floor_pass"
    TRADER = "trader"
    FLOOR_MANAGER = "floor_manager"
    TRIAL_TRADER = "trial_trader"


class TargetOutcome(BaseModel):
    amount: float
    currency: str = "USD"
    by_year: int


class RiskComponents(BaseModel):
    drawdown_response: int = Field(..., ge=1, le=5)
    regret_asymmetry: int = Field(..., ge=-1, le=1)
    concentration_tolerance: int = Field(..., ge=1, le=5)


class Compliance(BaseModel):
    halal: bool = False
    esg_lite: bool = False
    no_tobacco_alcohol_gambling: bool = False
    no_fossil_fuels: bool = False
    long_only: bool = True
    liquid_only: bool = True
    ticker_blocklist: list[str] = Field(default_factory=list)
    ticker_allowlist: list[str] | None = None
    custom_constraints: list[str] = Field(default_factory=list)


class DailyBriefing(BaseModel):
    enabled: bool = False
    time_local: str = "07:00"
    timezone: str = "UTC"
    voice_id: str | None = None
    delivery_channels: list[Literal["push", "in_app", "email"]] = Field(
        default_factory=lambda: ["in_app"]
    )
    language: str = "en"


class Mandate(BaseModel):
    """Versioned user mandate. Injected into every agent's prompt as an overlay."""

    model_config = ConfigDict(use_enum_values=True)

    user_id: UUID
    version: int = 1

    # Identity
    display_name: str
    locale: str = "en"
    timezone: str = "UTC"

    # Goal & horizon
    primary_goal: PrimaryGoal
    horizon: Horizon
    target_outcome: TargetOutcome | None = None
    path: Path

    # Risk
    risk_score: int = Field(..., ge=1, le=5)
    risk_components: RiskComponents
    risk_quotes: list[str] = Field(default_factory=list)
    max_drawdown_pct: Literal[10, 20, 30, 50, 100]

    # Constraints — hard rules
    compliance: Compliance = Field(default_factory=Compliance)

    # Preferences
    learning_style: LearningStyle = LearningStyle.QUICK

    # Delivery
    daily_briefing: DailyBriefing = Field(default_factory=DailyBriefing)

    # Plan. Not persisted on the mandate row — these live on `users` and are
    # stamped onto the response by the mandate API (CR039). Until then they
    # were schema defaults that nothing ever populated, so every client read
    # `floor_pass` / 0 credits regardless of the user's actual state.
    plan: Plan = Plan.FLOOR_PASS
    trial_expires_at: datetime | None = None
    credit_balance: int = 0
    credit_allowance: int = 0
    credits_reset_at: datetime | None = None
    room_cost: int = 0

    created_at: datetime
    updated_at: datetime
