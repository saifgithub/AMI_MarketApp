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
    # DEF302 widened this from `"19.0% below entry"`. The guard's intent is
    # unchanged and is deliberately not weakened: the stop distance must still
    # arrive finished, and 19.0 is still the asserted value. What changed is
    # that the percentage now names the pair it was measured from on its own
    # clause, because the bare form travelled — a Conservative attached the
    # reference position's "6.0% below entry" to a level of its own 23.1% away.
    # Asserted as a regex over the whole clause rather than loosened to a bare
    # "19.0", so a future edit that drops the binding fails here too.
    assert re.search(r"19\.0% below THAT entry \([\d.]+ from [\d.]+;", prompt)
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
    # Floor is the technical support, not the 52-week low. (The label became
    # "50-day range" in DEF229(b) — "breakout level" named a level as a trade
    # trigger. The guarantee this test exists for is unchanged.)
    assert "50-day range: $273.75" in sp
    # The 52-week low survives, but as its own, separately-sourced line (CR104).
    assert "52-week range: $201.5" in sp
    # Regression guard: the 52-week low must never be the recent-range floor again.
    assert "50-day range: $201.5" not in sp


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

# DEF130: the detector was ISO-only, so `July 30` or `14/03/2026` walked past
# the invariant unseen. Every date this codebase renders goes through
# `isoformat()` or `strftime("%Y-%m-%d")` today, so this is detection
# completeness rather than a live hole — the point is to notice when a future
# renderer introduces a human-formatted date, which is exactly when nobody is
# looking. Widened here rather than by listing known formats at call sites:
# an enumeration at the call site is the allowlist-instead-of-invariant shape
# that produced findings on CR104 r1-2 and DEF120 r1-2.
_MONTH = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t)?(?:ember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)"
)
_ORD = r"(?:st|nd|rd|th)?"
_DATE_RES = (
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),                       # 2026-07-30
    re.compile(r"\b\d{4}/\d{2}/\d{2}\b"),                       # 2026/07/30
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b"),                   # 14/03/2026, 03/14/2026
    re.compile(r"\b\d{1,2}\.\d{1,2}\.\d{4}\b"),                 # 14.03.2026
    re.compile(rf"\b{_MONTH}\.?\s+\d{{1,2}}{_ORD},?\s+\d{{4}}\b"),   # July 30, 2026
    re.compile(rf"\b\d{{1,2}}{_ORD}\s+{_MONTH}\.?,?\s+\d{{4}}\b"),   # 30 July 2026
    # Month + day with no year. Kept because `July 30` is the row's own example
    # of what used to walk past. "May" is excluded from THIS form only: it is
    # the one month name that is also an ordinary English word, so `May 5` in
    # prose would false-positive. `May 5, 2026` still matches the two forms
    # above, so nothing carrying a year escapes.
    re.compile(rf"\b(?!May\b){_MONTH}\.?\s+\d{{1,2}}{_ORD}\b"),
)
_ANCHOR_RE = re.compile(r"\bas of\b|\btoday\b|\bin \d+ days?\b|\b\d+ days? ago\b")


def _dates_in(line: str) -> list[str]:
    return [m for rx in _DATE_RES for m in rx.findall(line)]


def _assert_every_date_is_anchored(prompt: str) -> None:
    """Any absolute date rendered anywhere in a Room prompt must carry a
    relative anchor on the same line — either it IS the anchor line itself
    ("...as of..."), or it sits beside a computed "today" / "in N days" /
    "N days ago" phrase. A future date rendered without one fails here even
    if no test hardcodes that specific field/string (DEF124's whole point),
    and since DEF130 that holds for human-formatted dates too, not just ISO."""
    for line in prompt.splitlines():
        for date_str in _dates_in(line):
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


# ── DEF130 — the detector's own coverage ─────────────────────────────────
#
# The invariant above is only as good as what it can see. Before DEF130 it
# recognised ISO only, and the DEF124 auditor measured that directly: a
# fact-sheet header carrying "Last 10-K filed March 14, 2026" left the suite
# GREEN. These tests pin the detector itself, so widening it cannot silently
# narrow again.

@pytest.mark.parametrize("line", [
    "Last 10-K filed 2026-03-14",
    "Last 10-K filed 2026/03/14",
    "Last 10-K filed 14/03/2026",
    "Last 10-K filed 03/14/2026",
    "Last 10-K filed 14.03.2026",
    "Last 10-K filed March 14, 2026",
    "Last 10-K filed Mar 14 2026",
    "Last 10-K filed Mar. 14th, 2026",
    "Last 10-K filed 14 March 2026",
    "Last 10-K filed 14th March, 2026",
    "Next earnings July 30",
    "Next earnings Jul 30th",
    "Next earnings September 1",
    "Next earnings Sept 1",
    "Next earnings May 5, 2026",
])
def test_detector_sees_a_date_in_every_format_we_might_render(line):
    assert _dates_in(line), f"detector blind to: {line!r}"
    with pytest.raises(AssertionError, match="unanchored absolute date"):
        _assert_every_date_is_anchored(line)


@pytest.mark.parametrize("line", [
    "as of 2026-03-14",
    "Next earnings (LIVE): 2026-07-30 (Q3) — in 3 days",
    "Next earnings: March 14, 2026 — in 3 days",
    "filed 2026-03-14, 5 days ago",
    "Next earnings Jul 30 — in 3 days",
])
def test_an_anchored_date_still_passes_in_every_format(line):
    assert _dates_in(line), f"detector blind to: {line!r}"
    _assert_every_date_is_anchored(line)


@pytest.mark.parametrize("line", [
    "P/E 30 vs sector 22",
    "Conviction 7/10 on this setup",
    "Stop at 182.50, target 195.00",
    "Revenue grew 14% YoY to 94.8B",
    "May 5 analysts covering, 3 rate it a buy",
    "It may 5x from here",
    "Q3 2026 guidance raised",
    "RSI 14 period, MACD 12/26/9",
])
def test_detector_does_not_fire_on_prose_or_numbers_that_are_not_dates(line):
    assert not _dates_in(line), (
        f"false positive — {line!r} is not a date, but the detector matched "
        f"{_dates_in(line)}. A guard that cries wolf gets waived."
    )


def test_detector_sweeps_the_user_message_too_not_only_the_system_prompt(base_mandate):
    """DEF124's own test only ever inspected the system prompt. The user
    message is a rendered surface the agent reads just as directly, so a date
    introduced there would be equally unanchored and equally unseen."""
    profile = {
        "run_date": "2026-07-27", "next_earnings_date": "2026-07-30",
        "next_earnings_quarter": "Q3", "next_earnings_interval": "in 3 days",
        "field_state": {"run_date": "live", "next_earnings": "live"},
    }
    for agent_id in _PHASE_FOR_AGENT:
        sp, um = build_room_messages(
            agent_id=agent_id, mandate=base_mandate, user_id=None,
            ticker="AAPL", profile=profile, transcript=[],
        )
        _assert_every_date_is_anchored(sp)
        for msg in (um or []):
            content = msg.content if hasattr(msg, "content") else str(msg)
            _assert_every_date_is_anchored(content)
