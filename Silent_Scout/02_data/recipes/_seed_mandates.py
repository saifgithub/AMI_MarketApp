"""Seed mandates used by recipes and evals.

Five canonical Mandate shapes that exercise the overlay generator and
safety floor: default-conservative, halal-strict, ESG-strict,
aggressive-active, and long-only-long-horizon.

Recipes use one per example (round-robin or sampled) so the LoRA
sees mandate diversity during training. Evals use the full set to
measure mandate sensitivity.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.schemas import (  # noqa: E402
    Compliance,
    Horizon,
    LearningStyle,
    Mandate,
    Path as MandatePath,
    Plan,
    PrimaryGoal,
    RiskComponents,
    TargetOutcome,
)

_NOW = datetime.now(tz=UTC)


def _base(**overrides) -> Mandate:
    defaults = dict(
        user_id=uuid4(),
        display_name="Sample User",
        locale="en",
        timezone="UTC",
        primary_goal=PrimaryGoal.LONG_TERM_WEALTH,
        horizon=Horizon.LONG,
        target_outcome=TargetOutcome(amount=250_000, currency="USD", by_year=2036),
        path=MandatePath.LONG_HORIZON,
        risk_score=3,
        risk_components=RiskComponents(
            drawdown_response=3, regret_asymmetry=0, concentration_tolerance=3,
        ),
        max_drawdown_pct=20,
        compliance=Compliance(),
        learning_style=LearningStyle.QUICK,
        plan=Plan.TRADER,
        created_at=_NOW,
        updated_at=_NOW,
    )
    defaults.update(overrides)
    return Mandate(**defaults)


def default_conservative() -> Mandate:
    return _base()


def halal_strict() -> Mandate:
    return _base(
        compliance=Compliance(
            halal=True, long_only=True, liquid_only=True, no_tobacco_alcohol_gambling=True,
        ),
        learning_style=LearningStyle.STORY,
    )


def esg_strict() -> Mandate:
    return _base(
        compliance=Compliance(
            esg_lite=True, no_fossil_fuels=True, no_tobacco_alcohol_gambling=True,
            long_only=True,
        ),
    )


def aggressive_active() -> Mandate:
    return _base(
        primary_goal=PrimaryGoal.LEARNING_TO_TRADE,
        horizon=Horizon.SHORT,
        path=MandatePath.ACTIVE,
        risk_score=5,
        risk_components=RiskComponents(
            drawdown_response=5, regret_asymmetry=1, concentration_tolerance=5,
        ),
        max_drawdown_pct=50,
        compliance=Compliance(long_only=False, liquid_only=True),
        learning_style=LearningStyle.HANDS_ON,
    )


def long_only_long_horizon() -> Mandate:
    return _base(
        primary_goal=PrimaryGoal.RETIREMENT,
        horizon=Horizon.VERY_LONG,
        path=MandatePath.LONG_HORIZON,
        risk_score=2,
        risk_components=RiskComponents(
            drawdown_response=2, regret_asymmetry=-1, concentration_tolerance=2,
        ),
        max_drawdown_pct=10,
        compliance=Compliance(long_only=True, liquid_only=True),
        learning_style=LearningStyle.VISUAL,
    )


ALL = [
    default_conservative,
    halal_strict,
    esg_strict,
    aggressive_active,
    long_only_long_horizon,
]


def all_mandates() -> list[Mandate]:
    return [fn() for fn in ALL]
