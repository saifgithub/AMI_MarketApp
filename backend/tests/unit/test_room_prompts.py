"""DEF066 — the Room's drawdown snapshot must give agents a usable figure.

The CR035 benchmark found 16 of 64 Street-Buy/Room-PASS names refusing on a unit
error: a single position's stop *distance* was compared directly against the
portfolio max-drawdown cap, overstating the risk ~20x. The fix labels the cap as
portfolio-level everywhere and, for the agents that judge the proposed trade,
injects the *derived* contribution (size% × stop-distance%) so no agent has to do
the arithmetic. These tests pin both halves.
"""

from __future__ import annotations

import re

import pytest

from app.schemas import AgentId
from app.services.room_prompts import _PHASE_FOR_AGENT, build_room_messages

_AAPL_PROFILE = {"data_source": "synthetic"}

# entry 100, stop 81 → stop 19% below entry; at 5% size the contribution is
# 5 × 19 / 100 = 0.95 pt of a 30 pt cap — the exact AMD case from the report.
_PROPOSAL = {"size_pct": 5.0, "entry": 100.0, "stop": 81.0}


def _pm_prompt(base_mandate, trade_proposal=None) -> str:
    system_prompt, _ = build_room_messages(
        agent_id=AgentId.PORTFOLIO_MANAGER, mandate=base_mandate, user_id=None,
        ticker="AAPL", profile=_AAPL_PROFILE, transcript=[],
        trade_proposal=trade_proposal,
    )
    return system_prompt


def test_pm_prompt_carries_derived_drawdown_contribution(base_mandate):
    prompt = _pm_prompt(base_mandate, _PROPOSAL)
    # The finished figure, not just the formula.
    assert "0.95 pt" in prompt
    assert "19.0% below entry" in prompt
    assert re.search(r"contribution\s*≈\s*0\.95\s*pt", prompt)
    # And the anti-conflation instruction.
    assert "not the raw stop distance" in prompt.lower()


def test_pm_prompt_states_cap_is_portfolio_level_even_without_proposal(base_mandate):
    prompt = _pm_prompt(base_mandate, trade_proposal=None)
    assert "PORTFOLIO-level cap" in prompt
    assert "not a per-trade stop budget" in prompt.lower()
    # No proposal → no invented contribution figure.
    assert "Trader's proposal:" not in prompt


@pytest.mark.parametrize("agent_id", list(_PHASE_FOR_AGENT))
def test_no_room_prompt_emits_a_bare_max_drawdown_line(base_mandate, agent_id):
    """Every agent, every phase: the drawdown figure must never appear as a
    bare 'max_drawdown_pct: N' with no portfolio-level qualifier — that bare
    form is what agents mis-read as a per-trade budget."""
    system_prompt, _ = build_room_messages(
        agent_id=agent_id, mandate=base_mandate, user_id=None, ticker="AAPL",
        profile=_AAPL_PROFILE, transcript=[], trade_proposal=_PROPOSAL,
    )
    # The snapshot line always carries the clarification.
    assert "PORTFOLIO-level cap" in system_prompt
    # A pre-trade phase must not show a concrete proposal it hasn't heard yet.
    if _PHASE_FOR_AGENT[agent_id] not in ("RISK", "VERDICT"):
        assert "Trader's proposal:" not in system_prompt


def test_recent_range_floor_is_technical_support_not_52w_low(base_mandate):
    """DEF074 — the Room fact-sheet must render the computed technical support
    (profile['support']) as the recent-range floor, matching the value the 1-on-1
    technicals block already shows, and must not drop it in favour of the 52-week
    low (profile['low']). The 52-week range stays as explicit context."""
    profile = {
        "data_source": "live",
        "support": 273.75,   # technical 50-day support (compute_technicals)
        "breakout": 334.99,  # technical 50-day breakout
        "low": 201.5,        # 52-week low (fundamentals)
        "high": 334.99,      # 52-week high
    }
    sp, _ = build_room_messages(
        agent_id=AgentId.MARKET_ANALYST, mandate=base_mandate, user_id=None,
        ticker="AAPL", profile=profile, transcript=[],
    )
    # Floor is the technical support, not the 52-week low.
    assert "Recent range: $273.75" in sp
    # The 52-week low survives, but labelled as 52-week context.
    assert "52-week: $201.5" in sp
    # Regression guard: the 52-week low must never be the recent-range floor again.
    assert "Recent range: $201.5" not in sp


def test_derived_line_only_for_trade_judging_phases(base_mandate):
    """RISK debators and the PM see the derived proposal figure; analysts and
    researchers (who speak before any proposal exists) do not."""
    def has_proposal(agent_id) -> bool:
        return "Trader's proposal:" in _pm_prompt_for(agent_id, base_mandate)

    def _pm_prompt_for(agent_id, mandate):
        sp, _ = build_room_messages(
            agent_id=agent_id, mandate=mandate, user_id=None, ticker="AAPL",
            profile=_AAPL_PROFILE, transcript=[], trade_proposal=_PROPOSAL,
        )
        return sp

    assert has_proposal(AgentId.PORTFOLIO_MANAGER)
    assert has_proposal(AgentId.CONSERVATIVE_DEBATOR)
    assert not has_proposal(AgentId.FUNDAMENTALS_ANALYST)
    assert not has_proposal(AgentId.BULL_RESEARCHER)
