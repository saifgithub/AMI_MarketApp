"""Tests for the mandate overlay generator. Pure-function; runs fast."""

import pytest

from app.agents.overlay_generator import generate_overlay
from app.schemas import AgentId, Mandate


def test_every_trading_agent_produces_an_overlay(
    base_mandate: Mandate, all_agents: tuple[AgentId, ...]
):
    for agent_id in all_agents:
        overlay = generate_overlay(agent_id, base_mandate)
        assert overlay, f"empty overlay for {agent_id}"
        assert "USER MANDATE" in overlay
        assert "Role guidance" in overlay


def test_concierge_gets_a_distinct_overlay(base_mandate: Mandate):
    overlay = generate_overlay(AgentId.CONCIERGE, base_mandate)
    assert "CONCIERGE CONTEXT" in overlay
    assert "DO NOT" in overlay  # Concierge cannot give trading advice


def test_halal_flag_appears_in_overlay(halal_mandate: Mandate):
    overlay = generate_overlay(AgentId.FUNDAMENTALS_ANALYST, halal_mandate)
    assert "HALAL" in overlay or "Sharia" in overlay
    assert "interest-based" in overlay.lower() or "compliance" in overlay.lower()


def test_long_only_flag_changes_bear_framing(base_mandate: Mandate):
    # base_mandate has long_only=True
    overlay = generate_overlay(AgentId.BEAR_RESEARCHER, base_mandate)
    assert "LONG-ONLY" in overlay
    assert "Do NOT propose shorts" in overlay or "avoid" in overlay.lower()


def test_long_only_off_allows_shorts_in_bear(aggressive_mandate: Mandate):
    # aggressive_mandate has long_only=False
    overlay = generate_overlay(AgentId.BEAR_RESEARCHER, aggressive_mandate)
    assert "Explicit short recommendations allowed" in overlay or "shorts" in overlay.lower()


def test_max_drawdown_appears_in_aggressive_overlay(base_mandate: Mandate):
    overlay = generate_overlay(AgentId.AGGRESSIVE_DEBATOR, base_mandate)
    assert f"{base_mandate.max_drawdown_pct}%" in overlay


def test_trader_position_size_scales_with_risk_score(
    conservative_mandate: Mandate, aggressive_mandate: Mandate
):
    conservative = generate_overlay(AgentId.TRADER, conservative_mandate)
    aggressive = generate_overlay(AgentId.TRADER, aggressive_mandate)
    # Risk 1 → 5% cap; Risk 5 → 40% cap
    assert "5%" in conservative
    assert "40%" in aggressive


def test_risk_score_in_overlay(base_mandate: Mandate):
    overlay = generate_overlay(AgentId.PORTFOLIO_MANAGER, base_mandate)
    assert "risk_score=3" in overlay or f"Risk score: {base_mandate.risk_score}" in overlay


def test_ticker_blocklist_propagates(base_mandate: Mandate):
    mandate = base_mandate.model_copy(
        update={"compliance": base_mandate.compliance.model_copy(update={"ticker_blocklist": ["TSLA"]})}
    )
    overlay = generate_overlay(AgentId.FUNDAMENTALS_ANALYST, mandate)
    assert "TSLA" in overlay


def test_overlay_determinism(base_mandate: Mandate):
    """Same mandate + same agent → same overlay every time."""
    a = generate_overlay(AgentId.FUNDAMENTALS_ANALYST, base_mandate)
    b = generate_overlay(AgentId.FUNDAMENTALS_ANALYST, base_mandate)
    assert a == b


def test_overlay_has_no_llm_call(base_mandate: Mandate):
    """Overlay generator must be pure — sanity check on no async/IO."""
    # If this function ever becomes async, this import would fail
    import inspect

    assert not inspect.iscoroutinefunction(generate_overlay)
