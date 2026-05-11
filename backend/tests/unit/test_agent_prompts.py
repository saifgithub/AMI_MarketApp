"""Tests for the base-prompt loader + full-prompt composition."""

import pytest

from app.schemas import AgentId, Mandate
from app.services.agent_prompts import (
    build_agent_prompt,
    clear_prompt_cache,
    load_base_prompt,
)


def test_every_agent_has_a_base_prompt():
    for agent_id in AgentId:
        text = load_base_prompt(agent_id)
        assert text, f"{agent_id} base prompt empty"
        # Frontmatter should be stripped
        assert not text.startswith("---")
        # Should contain a "Role" section per our template
        assert "## Role" in text or "Role" in text


def test_base_prompt_frontmatter_stripped():
    text = load_base_prompt(AgentId.FUNDAMENTALS_ANALYST)
    assert "agent_id:" not in text  # frontmatter key, must be stripped
    assert "You are the Fundamentals Analyst" in text


def test_concierge_prompt_distinct():
    concierge = load_base_prompt(AgentId.CONCIERGE)
    fundamentals = load_base_prompt(AgentId.FUNDAMENTALS_ANALYST)
    assert concierge != fundamentals
    assert "Concierge" in concierge
    assert "Personal assistant" in concierge or "personal assistant" in concierge


def test_build_agent_prompt_concatenates_layers(base_mandate: Mandate):
    full = build_agent_prompt(AgentId.BEAR_RESEARCHER, base_mandate)
    # Base prompt content
    assert "Bear Researcher" in full
    # Mandate overlay content
    assert "USER MANDATE" in full
    # No safety floor for non-PM
    assert "SAFETY FLOOR" not in full


def test_portfolio_manager_includes_safety_floor(base_mandate: Mandate):
    full = build_agent_prompt(AgentId.PORTFOLIO_MANAGER, base_mandate)
    assert "Portfolio Manager" in full
    assert "USER MANDATE" in full
    assert "SAFETY FLOOR" in full


def test_prompt_cache_can_be_cleared():
    text1 = load_base_prompt(AgentId.TRADER)
    clear_prompt_cache()
    text2 = load_base_prompt(AgentId.TRADER)
    assert text1 == text2  # same content; just exercising the cache-clear path
