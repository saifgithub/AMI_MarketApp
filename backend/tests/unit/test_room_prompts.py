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
    assert "Reference position" not in prompt


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
        assert "Reference position" not in system_prompt


def test_recent_range_floor_is_technical_support_not_52w_low(base_mandate):
    """DEF074 — the Room fact-sheet must render the computed technical support
    (profile['support']) as the recent-range floor, matching the value the 1-on-1
    technicals block already shows, and must not drop it in favour of the 52-week
    low (profile['low']). The 52-week range stays as explicit context."""
    profile = {
        "support": 273.75,   # technical 50-day support (compute_technicals)
        "breakout": 334.99,  # technical 50-day breakout
        "low": 201.5,        # 52-week low (fundamentals)
        "high": 334.99,      # 52-week high
        "field_state": {"technicals": "live", "week52": "live"},
    }
    sp, _ = build_room_messages(
        agent_id=AgentId.MARKET_ANALYST, mandate=base_mandate, user_id=None,
        ticker="AAPL", profile=profile, transcript=[],
    )
    # Floor is the technical support, not the 52-week low.
    assert "Recent range: $273.75" in sp
    # The 52-week low survives, but as its own, separately-sourced line (CR104).
    assert "52-week range: $201.5" in sp
    # Regression guard: the 52-week low must never be the recent-range floor again.
    assert "Recent range: $201.5" not in sp


def test_run_date_anchors_the_fact_sheet_header(base_mandate):
    """DEF124/D2/D5 — the run date is stated ONCE, in the header, and assert
    on the exact rendered string (not a helper's return value)."""
    profile = {"run_date": "2026-07-27", "field_state": {"run_date": "live"}}
    sp, _ = build_room_messages(
        agent_id=AgentId.FUNDAMENTALS_ANALYST, mandate=base_mandate, user_id=None,
        ticker="AAPL", profile=profile, transcript=[],
    )
    assert "Fact sheet as of 2026-07-27 (UTC)" in sp
    # Once, not once per line of the disclosure header.
    assert sp.count("Fact sheet as of") == 1


def test_run_date_anchor_absent_without_recorded_provenance(base_mandate):
    """DEF124/D2 — matches every other field's refuse-by-default: presence of
    `run_date` alone (no `field_state` entry) does not earn the anchor line."""
    profile = {"run_date": "2026-07-27", "field_state": {}}
    sp, _ = build_room_messages(
        agent_id=AgentId.FUNDAMENTALS_ANALYST, mandate=base_mandate, user_id=None,
        ticker="AAPL", profile=profile, transcript=[],
    )
    assert "Fact sheet as of" not in sp


def test_earnings_line_renders_interval_alongside_the_absolute_date(base_mandate):
    """DEF124/D1/D5 — the interval rides ALONGSIDE the date, not instead of
    it; assert the exact rendered string."""
    profile = {
        "next_earnings_date": "2026-07-30", "next_earnings_quarter": "Q3",
        "next_earnings_interval": "in 3 days",
        "field_state": {"next_earnings": "live"},
    }
    sp, _ = build_room_messages(
        agent_id=AgentId.FUNDAMENTALS_ANALYST, mandate=base_mandate, user_id=None,
        ticker="AAPL", profile=profile, transcript=[],
    )
    assert "Next earnings (LIVE): 2026-07-30 (Q3) — in 3 days" in sp


def test_earnings_line_omitted_when_interval_not_computed(base_mandate):
    """DEF124 acceptance 6 — a live earnings date with no computed interval
    is an unanchored absolute date. The line is refused entirely, matching
    every other field's incomplete-provenance handling, rather than
    partially rendering the bare date."""
    profile = {
        "next_earnings_date": "2026-07-30", "next_earnings_quarter": "Q3",
        "field_state": {"next_earnings": "live"},
    }
    sp, _ = build_room_messages(
        agent_id=AgentId.FUNDAMENTALS_ANALYST, mandate=base_mandate, user_id=None,
        ticker="AAPL", profile=profile, transcript=[],
    )
    assert "Next earnings" not in sp


# ── DEF124 acceptance 6 — the invariant, not the one line ────────────────

_ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_ANCHOR_RE = re.compile(r"\bas of\b|\btoday\b|\bin \d+ days?\b|\b\d+ days? ago\b")


def _assert_every_date_is_anchored(prompt: str) -> None:
    """Any absolute (ISO) date rendered anywhere in a Room prompt must carry
    a relative anchor on the same line — either it IS the anchor line itself
    ("...as of..."), or it sits beside a computed "today" / "in N days" /
    "N days ago" phrase. A future date rendered without one fails here even
    if no test hardcodes that specific field/string (DEF124's whole point)."""
    for line in prompt.splitlines():
        for date_str in _ISO_DATE_RE.findall(line):
            assert _ANCHOR_RE.search(line), (
                f"unanchored absolute date {date_str!r} in line: {line!r}"
            )


@pytest.mark.parametrize("profile", [
    {  # run date + earnings, both live and fully anchored
        "run_date": "2026-07-27", "next_earnings_date": "2026-07-30",
        "next_earnings_quarter": "Q3", "next_earnings_interval": "in 3 days",
        "field_state": {"run_date": "live", "next_earnings": "live"},
    },
    {  # run date live, no earnings data at all
        "run_date": "2026-07-27", "field_state": {"run_date": "live"},
    },
    {  # nothing live — no provenance recorded anywhere
        "data_source": "synthetic",
    },
    {  # earnings date present but its interval never got computed — the
       # renderer must refuse the whole line, not emit a bare date (guards a
       # future edit that drops the interval computation upstream)
        "next_earnings_date": "2026-07-30", "next_earnings_quarter": "Q3",
        "field_state": {"next_earnings": "live"},
    },
    {  # earnings today — the same-day edge of the anchor phrase regex
        "run_date": "2026-07-27", "next_earnings_date": "2026-07-27",
        "next_earnings_quarter": "Q3", "next_earnings_interval": "today",
        "field_state": {"run_date": "live", "next_earnings": "live"},
    },
], ids=["anchored", "run-date-only", "nothing-live", "interval-missing", "same-day"])
def test_no_unanchored_absolute_date_anywhere_in_room_prompt(base_mandate, profile):
    for agent_id in _PHASE_FOR_AGENT:
        sp, _ = build_room_messages(
            agent_id=agent_id, mandate=base_mandate, user_id=None,
            ticker="AAPL", profile=profile, transcript=[],
        )
        _assert_every_date_is_anchored(sp)


def test_derived_line_only_for_trade_judging_phases(base_mandate):
    """RISK debators and the PM see the derived proposal figure; analysts and
    researchers (who speak before any proposal exists) do not."""
    def has_proposal(agent_id) -> bool:
        return "Reference position" in _pm_prompt_for(agent_id, base_mandate)

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
