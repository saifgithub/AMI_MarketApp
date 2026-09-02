"""Production-COHERENT mandates for the golden-set matrix.

This file exists because of one bug. `evidence/convene_gemini.py:77` hardcodes
`path=Path.LONG_HORIZON` while `--horizon` varies, so the `h_short` arm ran
`Horizon: short (<1 year)` alongside `Path: long_horizon` / `Primary goal:
long_term_wealth` — a combination onboarding cannot produce. Four of that arm's
twelve contradiction reports are about THAT incoherence, not production's
(`evidence/README.md` §"Three things the record does NOT support", item 3). A
harness that manufactures its own contradictions cannot measure contradictions.

The coherence rule is not invented here; it is read off the production
derivation in `app/services/concierge_engine.py:253-262`, which sets `path`
FROM `primary_goal` and never from horizon:

    RETIREMENT | LONG_TERM_WEALTH  -> Path.LONG_HORIZON
    LEARNING_TO_TRADE              -> Path.ACTIVE
    everything else                -> Path.LONG_HORIZON   (the else branch)

`horizon` is classified independently (`_classify_horizon`, :309), so any
(goal, horizon) pair IS reachable — but `path` is a FUNCTION of the goal and
must never be passed separately. `mandate_for()` therefore takes goal + horizon
and derives path exactly the way onboarding does.

The three-mandate battery below is the WP07 short/medium/long set, each chosen
so its goal is one a user with that horizon actually gives:

  short   -> learning_to_trade (ACTIVE)      risk 4
  medium  -> specific_goal     (LONG_HORIZON) risk 3
  long    -> long_term_wealth  (LONG_HORIZON) risk 3
"""
from datetime import datetime
from uuid import UUID

from app.schemas.mandate import (
    Compliance,
    Horizon,
    LearningStyle,
    Mandate,
    Path,
    Plan,
    PrimaryGoal,
    RiskComponents,
)

# Fixed, not random: the mandate must be the only thing that varies between
# arms, and a user_id that moves would move the Brief-overlay lookup with it.
_HARNESS_USER_ID = UUID("00000000-0000-4219-8000-000000000219")
_FIXED_TS = datetime(2026, 9, 2)


def derive_path(goal: PrimaryGoal) -> Path:
    """The production derivation, single-sourced (concierge_engine.py:253-262)."""
    if goal in (PrimaryGoal.RETIREMENT, PrimaryGoal.LONG_TERM_WEALTH):
        return Path.LONG_HORIZON
    if goal is PrimaryGoal.LEARNING_TO_TRADE:
        return Path.ACTIVE
    return Path.LONG_HORIZON


def mandate_for(
    goal: PrimaryGoal,
    horizon: Horizon,
    *,
    risk_score: int = 3,
    max_drawdown_pct: int = 30,
) -> Mandate:
    """One coherent mandate. `path` is DERIVED — never a parameter (see module
    docstring: making it one is the h_short artifact)."""
    return Mandate(
        user_id=_HARNESS_USER_ID,
        version=1,
        display_name="Harness User",
        locale="en",
        timezone="UTC",
        primary_goal=goal,
        horizon=horizon,
        target_outcome=None,
        path=derive_path(goal),
        risk_score=risk_score,
        risk_components=RiskComponents(
            drawdown_response=risk_score,
            regret_asymmetry=0,
            concentration_tolerance=risk_score,
        ),
        risk_quotes=[],
        max_drawdown_pct=max_drawdown_pct,
        compliance=Compliance(long_only=True, liquid_only=True),
        learning_style=LearningStyle.QUICK,
        plan=Plan.TRADER,
        trial_expires_at=None,
        credit_balance=150,
        created_at=_FIXED_TS,
        updated_at=_FIXED_TS,
    )


# label -> (goal, horizon, risk_score). Labels are what land in filenames and
# in the scored JSON, so they are short and stable.
BATTERY: dict[str, tuple[PrimaryGoal, Horizon, int]] = {
    "short": (PrimaryGoal.LEARNING_TO_TRADE, Horizon.SHORT, 4),
    "medium": (PrimaryGoal.SPECIFIC_GOAL, Horizon.MEDIUM, 3),
    "long": (PrimaryGoal.LONG_TERM_WEALTH, Horizon.LONG, 3),
}


def battery_mandate(label: str) -> Mandate:
    if label not in BATTERY:
        raise KeyError(f"unknown mandate label {label!r}; have {sorted(BATTERY)}")
    goal, horizon, risk = BATTERY[label]
    return mandate_for(goal, horizon, risk_score=risk)
