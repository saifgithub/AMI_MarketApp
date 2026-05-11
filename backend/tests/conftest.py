"""Shared pytest fixtures."""

from datetime import datetime
from uuid import uuid4

import pytest

from app.schemas import (
    AgentId,
    Compliance,
    DailyBriefing,
    Horizon,
    LearningStyle,
    Mandate,
    Path,
    Plan,
    PrimaryGoal,
    RiskComponents,
)
from app.schemas.trade import OrderType, ProposedTrade, Side


@pytest.fixture
def base_mandate() -> Mandate:
    """A vanilla 'risk_score=3, long-only, US English' mandate."""
    return Mandate(
        user_id=uuid4(),
        version=1,
        display_name="Test User",
        locale="en",
        timezone="UTC",
        primary_goal=PrimaryGoal.LONG_TERM_WEALTH,
        horizon=Horizon.LONG,
        target_outcome=None,
        path=Path.LONG_HORIZON,
        risk_score=3,
        risk_components=RiskComponents(
            drawdown_response=3, regret_asymmetry=0, concentration_tolerance=3
        ),
        risk_quotes=[],
        max_drawdown_pct=30,
        compliance=Compliance(long_only=True, liquid_only=True),
        learning_style=LearningStyle.QUICK,
        daily_briefing=DailyBriefing(enabled=False),
        plan=Plan.TRADER,
        trial_expires_at=None,
        credit_balance=150,
        created_at=datetime(2026, 5, 11),
        updated_at=datetime(2026, 5, 11),
    )


@pytest.fixture
def halal_mandate(base_mandate: Mandate) -> Mandate:
    """A halal-compliant mandate (otherwise identical to base)."""
    return base_mandate.model_copy(
        update={
            "compliance": Compliance(
                halal=True, no_tobacco_alcohol_gambling=True, long_only=True, liquid_only=True
            ),
            "locale": "ar",
            "timezone": "Asia/Riyadh",
        }
    )


@pytest.fixture
def conservative_mandate(base_mandate: Mandate) -> Mandate:
    """risk_score=1, max_drawdown=10%."""
    return base_mandate.model_copy(
        update={
            "risk_score": 1,
            "max_drawdown_pct": 10,
            "risk_components": RiskComponents(
                drawdown_response=1, regret_asymmetry=-1, concentration_tolerance=1
            ),
        }
    )


@pytest.fixture
def aggressive_mandate(base_mandate: Mandate) -> Mandate:
    """risk_score=5, max_drawdown=50%, NOT long-only."""
    return base_mandate.model_copy(
        update={
            "risk_score": 5,
            "max_drawdown_pct": 50,
            "risk_components": RiskComponents(
                drawdown_response=5, regret_asymmetry=1, concentration_tolerance=5
            ),
            "compliance": Compliance(long_only=False, liquid_only=False),
            "path": Path.ACTIVE,
        }
    )


@pytest.fixture
def proposed_buy_nvda() -> ProposedTrade:
    return ProposedTrade(
        ticker="NVDA",
        side=Side.BUY,
        quantity=10,
        order_type=OrderType.LIMIT,
        limit_price=152.0,
    )


@pytest.fixture
def all_agents() -> tuple[AgentId, ...]:
    return tuple(a for a in AgentId if a != AgentId.CONCIERGE)
