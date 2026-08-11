"""CR145 Tier C — the four upstream analysts stop reading each other's data.

`_format_profile(profile)` took no `agent_id`, so all twelve agents received a
BYTE-IDENTICAL fact sheet carrying every domain's numbers. Measured over 18
convenes / 72 analyst turns, they used them: `news_analyst` cited valuation
16/18 and technicals 13/18, `social_media_analyst` cited technicals 13/18,
`fundamentals_analyst` cited technicals 8/18. The four-analyst separation exists
to produce four INDEPENDENT lenses — it is the product's core claim, and it was
leaking.

The matrix is **default-open** (Saiful, 2026-08-11): only the four upstream
analysts are firewalled. Bull, Bear, Research Manager, Trader, PM and the three
Risk Debators keep the full sheet, because their job IS the cross-lane join.

Two things these tests exist to hold, both of which a naive "filter the sheet"
implementation gets wrong:

1. **"Not this agent's lane" is not "dropped."** The lane split must not remove
   a computed field from the Room. `test_prompt_data_parity.py` asks whether a
   fetched field is rendered *anywhere*; the guarantee that keeps its answer
   honest is that the UNION of the twelve agents' sheets is the full sheet, and
   that is asserted here rather than assumed.

2. **A withheld lane announces itself (CR040).** Silently omitting technicals
   from the News Analyst's sheet leaves it to conclude none exist, and the next
   honest thing it does is tell the Room they are unavailable — a fabrication in
   the other direction. The lane line is the difference between a firewall and a
   data gap, so its absence is a failure, not a cosmetic gap.
"""

from __future__ import annotations

import pytest

from app.schemas import AgentId
from app.services.room_prompts import (
    _ALL_DOMAINS,
    _AGENT_LANES,
    _format_profile,
    _lane_for,
)

_FULL_SHEET_AGENTS = [
    AgentId.BULL_RESEARCHER,
    AgentId.BEAR_RESEARCHER,
    AgentId.RESEARCH_MANAGER,
    AgentId.TRADER,
    AgentId.PORTFOLIO_MANAGER,
    AgentId.AGGRESSIVE_DEBATOR,
    AgentId.CONSERVATIVE_DEBATOR,
    AgentId.NEUTRAL_DEBATOR,
]

_FIREWALLED_AGENTS = [
    AgentId.FUNDAMENTALS_ANALYST,
    AgentId.MARKET_ANALYST,
    AgentId.NEWS_ANALYST,
    AgentId.SOCIAL_MEDIA_ANALYST,
]

# One fingerprint per domain — a string that appears on the full sheet and can
# only have come from that domain's renderer.
_DOMAIN_FINGERPRINTS = {
    "fundamentals": ["P/E", "TTM revenue growth", "Valuation (LIVE)",
                     "Sector/industry (LIVE)", "Dividend yield (LIVE)",
                     "Analyst consensus (LIVE"],
    "technicals": ["RSI:", "50-day range:", "Volume:"],
    "news": ["Catalysts — recent:"],
    "social": ["Retail sentiment:", "Mentions:", "Communities:"],
}

# Fields that belong to more than one lane on DOMAIN grounds rather than by
# which fetcher returned them. Kept out of the fingerprint table above (which
# asserts exclusivity) and asserted explicitly below instead.
_DUAL_LANE = {
    "52-week range": {"fundamentals", "technicals"},
    "Next earnings (LIVE)": {"fundamentals", "news"},
}


@pytest.fixture
def profile() -> dict:
    """Every domain live, so a missing line can only be the lane split."""
    return {
        "run_date": "2026-08-11",
        "base_price": 271.83,
        "pe": 48.77,
        "forward_pe": 12.34,
        "rev_growth": 23.61,
        "profit_margin": 41.29,
        "net_cash": 944.0,
        "low": 155.4,
        "high": 402.9,
        "rsi": 61.2,
        "rsi_tone": "neutral",
        "trend": "up",
        "support": 240.11,
        "breakout": 300.55,
        "last_close": 268.40,
        "volume_tone": "above average",
        "catalyst": "Reported Q3 above consensus",
        "news_headlines": [],
        "forward_catalyst": "FOMC decision in 14 days",
        "sentiment_tone": "bullish",
        "sentiment_score": 0.62,
        "mention_trend": "up 40% week on week",
        "pattern": "Buzz 71, 812 bullish vs 190 bearish",
        "influencer_take": "r/stocks, r/investing",
        "price_to_sales": 7.31,
        "ev_to_ebitda": 19.42,
        "peg_ratio": 2.15,
        "peg_basis": "5y",
        "fcf_yield": 3.87,
        "sector": "Technology",
        "industry": "Semiconductors",
        "dividend_yield": 1.63,
        "analyst_target_price": 320.50,
        "analyst_rating": "buy",
        "next_earnings_date": "2026-09-24",
        "next_earnings_quarter": "Q4",
        "next_earnings_interval": "in 44 days",
        "field_state": {
            "run_date": "live", "base_price": "live", "pe": "live",
            "forward_pe": "live", "rev_growth": "live", "profit_margin": "live",
            "net_cash": "live", "week52": "live", "technicals": "live",
            "news": "live", "social": "live", "price_to_sales": "live",
            "ev_to_ebitda": "live", "peg_ratio": "live", "peg_basis": "live",
            "fcf_yield": "live", "sector": "live", "dividend_yield": "live",
            "analyst_target_price": "live", "analyst_rating": "live",
            "next_earnings": "live",
        },
    }


# ── The matrix itself ─────────────────────────────────────────────────────────


def test_the_matrix_is_default_open():
    """An agent absent from `_AGENT_LANES` sees everything. Adding a 13th agent
    must fail OPEN — starving a new agent silently is the failure mode this
    whole CR is about, pointed the other way."""
    assert set(_AGENT_LANES) == set(_FIREWALLED_AGENTS)
    for agent in _FULL_SHEET_AGENTS:
        assert _lane_for(agent) == _ALL_DOMAINS


def test_no_agent_id_renders_the_full_sheet():
    """Non-Room callers and `test_prompt_data_parity.py` pass no agent id. The
    lane split must not change what "rendered at all" means for them."""
    assert _lane_for(None) == _ALL_DOMAINS


# ── The firewall bites ────────────────────────────────────────────────────────


@pytest.mark.parametrize("agent", _FIREWALLED_AGENTS)
def test_a_firewalled_analyst_sees_only_its_own_lane(agent, profile):
    text = _format_profile(profile, agent)
    lane = _lane_for(agent)
    for domain, fingerprints in _DOMAIN_FINGERPRINTS.items():
        for fp in fingerprints:
            if domain in lane:
                assert fp in text, f"{agent.value} lost its OWN lane's {fp!r}"
            else:
                assert fp not in text, (
                    f"{agent.value} can still read {domain}'s {fp!r} — the "
                    "firewall does not bite"
                )


@pytest.mark.parametrize("agent", _FIREWALLED_AGENTS)
def test_dual_lane_fields_reach_both_desks_that_own_them(agent, profile):
    """Lane membership is a judgement about DOMAIN, not about which fetcher
    returned the field. `week52` arrives from `fetch_live_fundamentals`, but a
    52-week high/low is a price range and the Market Analyst already holds the
    50-day one — gating it out would leave the range desk reasoning about ranges
    with less context than the sheet carries. `next_earnings` is the same shape:
    a scheduled date IS a forward catalyst, which is the News Analyst's job.
    (This is also what `test_room_prompts.py`'s DEF074 guard caught, unmodified,
    when `week52` was fundamentals-only.)"""
    text = _format_profile(profile, agent)
    lane = _lane_for(agent)
    for fingerprint, owners in _DUAL_LANE.items():
        if lane & owners:
            assert fingerprint in text, f"{agent.value} lost dual-lane {fingerprint!r}"
        else:
            assert fingerprint not in text, (
                f"{agent.value} sees {fingerprint!r}, which belongs to {owners}"
            )


@pytest.mark.parametrize("agent", _FULL_SHEET_AGENTS)
def test_a_full_sheet_agent_loses_nothing(agent, profile):
    """Their job IS the cross-lane join. A Bull that cannot see technicals
    cannot weigh a thesis against them."""
    full = _format_profile(profile, None)
    assert _format_profile(profile, agent) == full


def test_the_union_of_all_lanes_is_the_full_sheet(profile):
    """"Not this agent's lane" ≠ "dropped". Every line of the full sheet must
    reach at least one agent, or the firewall has quietly deleted data the
    pipeline paid to fetch — which is what `test_prompt_data_parity.py` would
    otherwise stop being able to see."""
    full_lines = set(_format_profile(profile, None).split("\n"))
    seen: set[str] = set()
    for agent in list(AgentId):
        seen |= set(_format_profile(profile, agent).split("\n"))
    unreachable = sorted(line for line in full_lines - seen if line.strip())
    assert not unreachable, (
        "these fact-sheet lines reach NO agent after the lane split: "
        f"{unreachable}"
    )


# ── CR040: the withheld lane announces itself ─────────────────────────────────


@pytest.mark.parametrize("agent", _FIREWALLED_AGENTS)
def test_a_firewalled_analyst_is_told_what_it_is_not_seeing(agent, profile):
    text = _format_profile(profile, agent)
    assert "Not in your lane this call:" in text
    assert "NOT missing data" in text
    assert "do not tell the Room they are unavailable" in text


def test_the_lane_line_names_every_withheld_domain(profile):
    """A generic "some data is withheld" would leave the agent guessing which,
    and guessing is what it does badly."""
    text = _format_profile(profile, AgentId.NEWS_ANALYST)
    for phrase in ("company fundamentals and valuation",
                   "market technicals", "retail sentiment"):
        assert phrase in text
    assert "news and catalysts" not in text  # its own lane is not "withheld"


@pytest.mark.parametrize("agent", _FULL_SHEET_AGENTS)
def test_a_full_sheet_agent_gets_no_lane_line(agent, profile):
    """Nothing is withheld from them, so a line saying so would be false."""
    assert "Not in your lane this call:" not in _format_profile(profile, agent)


def test_an_out_of_lane_domain_is_not_disclosed_as_unavailable(profile):
    """The trap this CR could easily have created: reusing the existing
    "not available this call" disclosure for an out-of-lane domain would tell
    the Market Analyst that news does not exist, when it is live and another
    analyst is about to cite it."""
    text = _format_profile(profile, AgentId.MARKET_ANALYST)
    assert "Recent catalyst/headline: not available" not in text
    assert "Recent catalyst/headline: alpha simulation scaffolding" not in text
    assert "none available live this call" not in text


# ── CR151 Tier A — the asymmetry line ─────────────────────────────────────────


def test_the_asymmetry_line_renders_for_full_sheet_agents(profile):
    text = _format_profile(profile, AgentId.RESEARCH_MANAGER)
    assert "Asymmetry from the last close $268.4" in text
    assert "+19.4%" in text          # (320.50 - 268.40) / 268.40
    assert "-10.5%" in text          # (240.11 - 268.40) / 268.40
    assert "the Street's target is not a trade target" in text


@pytest.mark.parametrize("agent", _FIREWALLED_AGENTS)
def test_the_asymmetry_line_is_not_a_way_back_across_the_firewall(agent, profile):
    """It joins a fundamentals number to a technicals one. Rendering it to a
    firewalled analyst would hand back exactly what the firewall removed —
    the reconciliation CR151 asked CR145's matrix to state explicitly."""
    assert "Asymmetry from" not in _format_profile(profile, agent)


def test_the_asymmetry_line_names_its_own_anchor(profile):
    """DEF228 happened because two rendered prices were joined as if they were
    one. The line must say which price it measured from."""
    text = _format_profile(profile, AgentId.BULL_RESEARCHER)
    assert "Asymmetry from the last close" in text

    no_technicals = dict(profile)
    no_technicals["field_state"] = dict(profile["field_state"], technicals="unavailable")
    fallback = _format_profile(no_technicals, AgentId.BULL_RESEARCHER)
    assert "Asymmetry from the reference price $271.83" in fallback
    assert "50-day range low" not in fallback  # its half is gated off with technicals


def test_each_half_of_the_asymmetry_is_gated_independently(profile):
    """CR104 — a missing analyst target drops the upside clause, not the line."""
    no_target = dict(profile)
    no_target["field_state"] = dict(
        profile["field_state"], analyst_target_price="unavailable"
    )
    text = _format_profile(no_target, AgentId.BULL_RESEARCHER)
    assert "consensus target" not in text
    assert "50-day range low" in text


def test_the_asymmetry_line_is_absent_when_neither_half_is_live(profile):
    """Not a line reading "Asymmetry: not available" — a derived figure with no
    inputs has nothing to disclose, and DEF053's rule is that we do not print a
    label for a number we never had."""
    bare = dict(profile)
    bare["field_state"] = dict(
        profile["field_state"], technicals="unavailable",
        analyst_target_price="unavailable",
    )
    assert "Asymmetry from" not in _format_profile(bare, AgentId.BULL_RESEARCHER)
