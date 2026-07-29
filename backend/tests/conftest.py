"""Shared pytest fixtures.

The `_isolated_db` autouse fixture gives every test a fresh sqlite database
(file under /tmp, wiped between tests). It also clears all the in-memory
store/service singletons so a store doesn't accidentally carry rows or
caches across test cases. Tests that exercise persistence get clean tables;
tests that don't touch persistence pay almost no cost.
"""

import os
import tempfile
from datetime import datetime
from pathlib import Path as _Path
from uuid import uuid4

import pytest

from app.schemas import (
    AgentId,
    Compliance,
    Horizon,
    LearningStyle,
    Mandate,
    Path,
    Plan,
    PrimaryGoal,
    RiskComponents,
)
from app.schemas.trade import OrderType, ProposedTrade, Side


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path: _Path) -> None:
    """Per-test sqlite database + singleton reset for every store/service.

    Runs autouse so every existing test gets a clean slate without changes.
    """
    db_file = tmp_path / "ami_trade_test.db"
    url = f"sqlite:///{db_file}"
    os.environ["AMI_TEST_DATABASE_URL"] = url

    from app.db import reset_for_tests
    reset_for_tests(url)

    # Reset module-level singletons so cached pre-DB instances don't leak.
    from app.services import mandate_store as _ms
    from app.services import overlay_store as _os
    from app.services import journal_store as _js
    from app.services import lessons_service as _ls
    from app.services import sim_engine as _sim
    from app.services import room_runner as _rr
    from app.services import market_data as _md
    from app.services import news_context as _nc
    from app.services import social_context as _sc
    from app.services import watchlist_store as _ws
    from app.services import feedback_store as _fb
    from app.services import daily_challenge_service as _dc
    from app.services import ai_coach_service as _ac
    from app.services import reputation_service as _rep
    from app.services import league_service as _lg
    _lg._service = None
    _ms._store = None
    _os._store = None
    _js._store = None
    _ls._service = None
    _sim._engine = None
    _rr._runner = None
    _ws._store = None
    _fb._store = None
    _dc._service = None
    _ac._service = None
    _rep._service = None
    # CR026: the sector-map provider caches the stored snapshot's ticker→sector map;
    # clear it so a seeded map from one test doesn't leak into the next.
    from app.services import sector_allocation as _sec
    _sec.reset_sector_map_provider(None)
    # Pin tests to the deterministic mock walk regardless of USE_REAL_MARKET_DATA.
    _md.set_market_data_provider(_md.MockWalkProvider())
    _nc.set_alpha_vantage_source(None)
    _sc.set_adanos_source(None)
    # B-tier audit (AT:R37): the rate-limit module holds module-level
    # singletons too; flush their sliding windows between tests so the
    # 4th `/v1/auth/magic_link/start` call in test_auth_phase1_5_audit_fixes
    # doesn't trip the 3/min IP limit.
    from app.services import rate_limit as _rl
    _rl.anon_rate_limit.reset()
    _rl.magic_link_start_rate_limit.reset()
    _rl.room_stream_rate_limit.reset()


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
