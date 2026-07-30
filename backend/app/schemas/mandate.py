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


# DEF179: these Mandate fields describe entitlement state that actually lives
# on `users` (see `Mandate.plan` docstring below) and is resolved server-side
# via `effective_plan_for_user()` / `balance_for()`. A client-supplied value
# for any of them — via `PATCH /v1/mandate/{user_id}` or a Brief/1-on-1
# `mandate_override` body — is dropped rather than honoured, silently: the
# server always re-stamps the real value on read (`_with_plan_state`), so a
# stored/overridden client value would be invisible on the next GET anyway.
CLIENT_UNWRITABLE_MANDATE_FIELDS = frozenset({
    "plan",
    "credit_balance",
    "credit_allowance",
    "trial_expires_at",
    "trial_started_at",
})


class TargetOutcome(BaseModel):
    amount: float
    currency: str = "USD"
    by_year: int


class RiskComponents(BaseModel):
    drawdown_response: int = Field(..., ge=1, le=5)
    regret_asymmetry: int = Field(..., ge=-1, le=1)
    concentration_tolerance: int = Field(..., ge=1, le=5)


class ResolvedCaps(BaseModel):
    """DEF193: the ENFORCED value of each preset-backed cap, server-resolved.

    `Mandate.sector_cap_pct` / `single_name_cap_pct` are `None` until a user
    explicitly overrides them, but a real, binding preset still applies —
    `GET /v1/portfolio/sector-allocation/{id}`'s `max_allowed` has shown that
    resolved number for months. Stamping the SAME resolution
    (`app.trading_math.sizing.resolved_sector_cap_pct` /
    `resolved_single_name_cap_pct` — the one place each cap is computed, per
    CR046) onto the mandate GET response closes the gap where a client had to
    choose between fabricating a number or hiding one. Same percentage-point
    units as the field each resolves; never null."""

    sector_cap_pct: float
    single_name_cap_pct: float


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

    # CR101-BE1: the two ALREADY-enforced risk caps (sector concentration, single-name
    # position size), made explicit and settable. `None` = not explicitly set — the
    # enforcement/overlay/disclosure resolvers (`sector_allocation.sector_concentration_cap`,
    # `safety_floor.single_name_cap_pct`) fall back to the preset table keyed by
    # `risk_components.concentration_tolerance` / `risk_score`, i.e. the SAME computation
    # this replaces. An existing stored mandate snapshot has no such key at all (same as
    # `None`), so it enforces IDENTICALLY post-migration. Percentage points (e.g. 40.0 =
    # 40%), matching `max_drawdown_pct`'s units. Once a PATCH sets either field it is
    # sticky — it no longer moves if risk_score/concentration_tolerance later change.
    sector_cap_pct: float | None = None
    single_name_cap_pct: float | None = None

    # CR101-BE2: four risk limits that did not exist in ANY form pre-CR101 — no
    # legacy value to migrate, so `None` simply means "off / not enforced", not
    # "fall back to a preset" (unlike sector_cap_pct/single_name_cap_pct above).
    # Each is enforced deterministically in `agents/safety_floor.py`, disclosed
    # in its own units in `agents/overlay_generator.py`, and settable via PATCH.
    # Round 2: enforced at EVERY `check_mandate_compliance` call site — the
    # direct trade-ticket path AND the Room (both the scripted path and the
    # LLM-override wrapper) — not just the ticket path round 1 shipped it on;
    # a fifth call site omitting the context now fails loudly rather than
    # silently, per the CR101-BE2 round-2 architect/auditor findings.
    # No ceiling is imposed on what a user may set (L3) — loud disclosure at
    # set-time is a mobile concern (CR101-MOBILE), out of scope here.
    #
    # Hours after a stop-out (a trade closed with a realised loss) before the
    # next BUY is allowed. Evaluated against the most recent lost trade's
    # `closed_at`.
    post_loss_cooldown_hours: float | None = None
    # Ceiling on distinct tickers concurrently held. A BUY that would open a
    # NEW position (a ticker not already held) is blocked once the count is
    # already at/above this; adding to an existing holding is unaffected.
    max_open_positions: int | None = None
    # Over-trading brake — a ceiling on trades submitted (any side) within the
    # current UTC calendar day / ISO week (Monday 00:00 UTC boundary). Fixed
    # UTC basis, not `Mandate.timezone` — see `agents/safety_floor.py` for why.
    max_trades_per_day: int | None = None
    max_trades_per_week: int | None = None
    # Sum of (position size % of portfolio) x (stop distance % below entry) /
    # 100 across open positions, in percentage points. Caps the portfolio's
    # total capital-at-risk-to-stops, not any single position. Requires a
    # stop on the proposed trade to price its own contribution; an open
    # position with no stop contributes 0 (nothing to sum).
    max_open_risk_pct: float | None = None

    # Constraints — hard rules
    compliance: Compliance = Field(default_factory=Compliance)

    # Preferences
    learning_style: LearningStyle = LearningStyle.QUICK

    # DEF129 removed `daily_briefing: DailyBriefing`. It was collected at
    # onboarding, persisted, and echoed back as a settled arrangement, while
    # nothing in the backend could schedule or deliver it. Existing mandate
    # snapshots in the `mandates` JSONB column still carry the key; Pydantic
    # ignores unknown fields, so they load unchanged and no migration is owed.

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
    # CR047 "The Winzip": when set and in the future, the next Room convene is
    # in cooldown — the client shows the countdown card instead of firing a
    # doomed request. NULL / past = no cooldown pending.
    room_cooldown_until: datetime | None = None

    # DEF193: stamped by the mandate API's read path (`_with_plan_state`),
    # same as `plan`/`credit_balance` above — never persisted on the row.
    resolved: ResolvedCaps | None = None

    created_at: datetime
    updated_at: datetime
