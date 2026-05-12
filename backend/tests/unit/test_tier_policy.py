"""Tier policy: which model tier each (plan, agent) runs at."""

import pytest

from app.schemas import AgentId
from app.schemas.mandate import Plan
from app.services.tier_policy import pick_tier


@pytest.mark.parametrize("plan,agent,expected", [
    (Plan.FLOOR_PASS, AgentId.CONCIERGE, "cheap"),
    (Plan.FLOOR_MANAGER, AgentId.CONCIERGE, "mid"),
    (Plan.FLOOR_PASS, AgentId.PORTFOLIO_MANAGER, "mid"),
    (Plan.TRADER, AgentId.PORTFOLIO_MANAGER, "premium"),
    (Plan.FLOOR_MANAGER, AgentId.PORTFOLIO_MANAGER, "premium"),
    (Plan.FLOOR_PASS, AgentId.TRADER, "cheap"),
    (Plan.TRADER, AgentId.TRADER, "mid"),
    (Plan.FLOOR_MANAGER, AgentId.TRADER, "premium"),
    (Plan.FLOOR_PASS, AgentId.MARKET_ANALYST, "cheap"),
    (Plan.TRIAL_TRADER, AgentId.BULL_RESEARCHER, "mid"),
    (Plan.FLOOR_MANAGER, AgentId.NEWS_ANALYST, "premium"),
])
def test_pick_tier(plan, agent, expected):
    assert pick_tier(plan, agent) == expected
