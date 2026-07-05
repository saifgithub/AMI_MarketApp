# Mandate Schema

The structured object that captures the user's financial mandate. Versioned. Injected into every agent's system prompt. The single most important data structure in the product.

## TypeScript / TS-style definition

```typescript
type Mandate = {
  // Identity
  user_id: string;              // uuid, links to User
  version: number;              // auto-increment on edit

  // Identity (for personalisation)
  display_name: string;
  locale: "en" | "ar" | "ms" | string;  // pluggable; ISO-style codes
  timezone: string;             // IANA, e.g. "Asia/Riyadh"

  // Goal & horizon
  primary_goal:
    | "retirement"
    | "long_term_wealth"
    | "income_now"
    | "specific_goal"
    | "learning_to_trade"
    | "exploring";
  horizon: "short" | "medium" | "long" | "very_long";  // <1y / 1-3y / 3-10y / 10y+
  target_outcome: { amount: number; currency: string; by_year: number } | null;
  path: "active" | "long_horizon" | "both";

  // Risk (used everywhere)
  risk_score: 1 | 2 | 3 | 4 | 5;
  risk_components: {
    drawdown_response: 1 | 2 | 3 | 4 | 5;   // from Scenario 1
    regret_asymmetry: -1 | 0 | 1;            // from Scenario 2
    concentration_tolerance: 1 | 2 | 3 | 4 | 5;  // from Scenario 3
  };
  risk_quotes: string[];        // verbatim user words during risk scenarios
  max_drawdown_pct: 10 | 20 | 30 | 50 | 100;  // hard floor enforced by PM

  // Constraints — HARD RULES (compliance, enforced by PM safety floor)
  compliance: {
    halal: boolean;
    esg_lite: boolean;
    no_tobacco_alcohol_gambling: boolean;
    no_fossil_fuels: boolean;
    long_only: boolean;
    liquid_only: boolean;
    ticker_blocklist: string[];
    ticker_allowlist: string[] | null;  // null = no allowlist (= all permitted)
    custom_constraints: string[];        // freeform user constraints, used as agent hints
  };

  // Learning preferences (used by AI-tutor + Concierge)
  learning_style: "quick" | "story" | "visual" | "hands_on";

  // Delivery
  daily_briefing: {
    enabled: boolean;
    time_local: string;          // "HH:MM"
    timezone: string;            // IANA (mirrors user.timezone)
    voice_id: string | null;     // TTS voice; null = text-only briefing
    delivery_channels: Array<"push" | "in_app" | "email">;
    language: string;            // override locale for briefing language
  };

  // Plan / commerce
  plan: "floor_pass" | "trader" | "floor_manager" | "trial_trader";
  trial_expires_at: Date | null;
  credit_balance: number;

  // Meta
  created_at: Date;
  updated_at: Date;
};
```

## Python / Pydantic definition

Excerpted from `backend/app/schemas/mandate.py` (Pydantic v2; full file is the authoritative source):

```python
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

    display_name: str
    locale: str = "en"
    timezone: str = "UTC"

    primary_goal: PrimaryGoal
    horizon: Horizon
    target_outcome: TargetOutcome | None = None
    path: Path

    risk_score: int = Field(..., ge=1, le=5)
    risk_components: RiskComponents
    risk_quotes: list[str] = Field(default_factory=list)
    max_drawdown_pct: Literal[10, 20, 30, 50, 100]

    compliance: Compliance = Field(default_factory=Compliance)
    learning_style: LearningStyle = LearningStyle.QUICK
    daily_briefing: DailyBriefing = Field(default_factory=DailyBriefing)

    plan: Plan = Plan.FLOOR_PASS
    trial_expires_at: datetime | None = None
    credit_balance: int = 0

    created_at: datetime
    updated_at: datetime
```

Notes:
- Pydantic v2 throughout — `model_config = ConfigDict(...)`, not the legacy `class Config`.
- `user_id` is `UUID`, not `str`.
- Several fields have safe defaults that earlier docs didn't show (`compliance`, `learning_style`, `daily_briefing`) — concierge can produce a valid mandate without explicitly composing every nested object.

## Database table

```sql
CREATE TABLE mandates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,

    -- Identity
    display_name TEXT NOT NULL,
    locale TEXT NOT NULL,
    timezone TEXT NOT NULL,

    -- Goal & horizon
    primary_goal TEXT NOT NULL,
    horizon TEXT NOT NULL,
    target_outcome JSONB,
    path TEXT NOT NULL,

    -- Risk
    risk_score SMALLINT NOT NULL CHECK (risk_score BETWEEN 1 AND 5),
    risk_components JSONB NOT NULL,
    risk_quotes JSONB DEFAULT '[]'::jsonb,
    max_drawdown_pct SMALLINT NOT NULL,

    -- Compliance
    compliance JSONB NOT NULL,

    -- Preferences
    learning_style TEXT NOT NULL,
    daily_briefing JSONB NOT NULL,

    -- Plan
    plan TEXT NOT NULL DEFAULT 'floor_pass',
    trial_expires_at TIMESTAMPTZ,
    credit_balance INTEGER NOT NULL DEFAULT 0,

    -- Meta
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (user_id, version)
);

CREATE INDEX idx_mandates_user_current ON mandates(user_id) WHERE is_current = TRUE;
CREATE INDEX idx_mandates_user_version ON mandates(user_id, version DESC);

-- Row-level security: users only see their own mandates
ALTER TABLE mandates ENABLE ROW LEVEL SECURITY;
CREATE POLICY mandates_user_only ON mandates
    USING (user_id = auth.uid());
```

**Versioning model.** Every edit creates a new row with `version = max(version) + 1`. Old rows have `is_current = FALSE`. The current mandate is the one with `is_current = TRUE` (exactly one per user).

## Example mandate (Saudi halal user)

```json
{
  "user_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "version": 1,
  "display_name": "Saiful",
  "locale": "ar-SA",
  "timezone": "Asia/Riyadh",
  "primary_goal": "retirement",
  "horizon": "very_long",
  "target_outcome": {
    "amount": 5000000,
    "currency": "SAR",
    "by_year": 2050
  },
  "path": "long_horizon",
  "risk_score": 3,
  "risk_components": {
    "drawdown_response": 3,
    "regret_asymmetry": 0,
    "concentration_tolerance": 3
  },
  "risk_quotes": [
    "I'd probably hold and wait if it dropped 30%",
    "Losing feels worse than missing out, but only a bit",
    "30% is the most I'd put in one name — anything can happen"
  ],
  "max_drawdown_pct": 30,
  "compliance": {
    "halal": true,
    "esg_lite": false,
    "no_tobacco_alcohol_gambling": true,
    "no_fossil_fuels": false,
    "long_only": true,
    "liquid_only": true,
    "ticker_blocklist": [],
    "ticker_allowlist": null,
    "custom_constraints": []
  },
  "learning_style": "hands_on",
  "daily_briefing": {
    "enabled": true,
    "time_local": "07:00",
    "timezone": "Asia/Riyadh",
    "voice_id": "azure-ar-SA-Hamed",
    "delivery_channels": ["push", "in_app"],
    "language": "ar-SA"
  },
  "plan": "trial_trader",
  "trial_expires_at": "2026-05-18T07:00:00Z",
  "credit_balance": 75,
  "created_at": "2026-05-11T07:00:00Z",
  "updated_at": "2026-05-11T07:00:00Z"
}
```

## Cross-references

- How this gets used per agent: [`docs/initial_specs/02_agents/mandate_overlays.md`](../02_agents/mandate_overlays.md)
- The safety floor that enforces it: [`docs/initial_specs/02_agents/safety_floor.md`](../02_agents/safety_floor.md)
- Lifecycle (edit, audit, drift): [`lifecycle.md`](lifecycle.md)
- DB row-level security & auth context: [`docs/initial_specs/08_tech/data_model.md`](../08_tech/data_model.md)
