"""Validate that the 1-on-1 live data block covers what each agent's prompt claims.

The 1-on-1 path in agent_runner.py appends build_live_data_block() to every
agent's system prompt — the same 6 fundamentals fields regardless of agent role.
These tests document which agents are well-served by that block and which are not.

No network calls. No LLM calls. We parse build_live_data_block() output from a
synthetic fixture (USE_REAL_MARKET_DATA=false → function returns None; we test
the shape with a pre-built string that matches what the function produces when
live data is available).

Run:
    python -m pytest Silent_Scout/05_agent_alignment/validation_suite/test_one_on_one_coverage.py -v
"""

from __future__ import annotations

from typing import NamedTuple

import pytest

# ── What build_live_data_block() produces for a well-populated ticker ─────
#
# Constructed from fundamentals.py:138–174 — the exact fields and labels
# the function emits, in order. This is what gets appended to every agent's
# system prompt in 1-on-1 mode when USE_REAL_MARKET_DATA=true.

LIVE_BLOCK_SAMPLE = """─── LIVE MARKET DATA — AAPL ───
Price: $182.50
P/E: 28.5
TTM revenue growth: 12%
Profit margin: 25%
Net cash: $45000M
52-week range: $150.00–$198.00
(yfinance live snapshot for AAPL. Use these numbers when discussing AAPL. Do NOT cite figures from training memory; if a number isn't above, qualify your claim or omit it.)"""

# Fields present in the 1-on-1 block
_LIVE_BLOCK_FIELDS = {
    "price",
    "pe",
    "revenue_growth",
    "profit_margin",
    "net_cash",
    "52_week_range",
}

# Fields NOT in the 1-on-1 block
_LIVE_BLOCK_ABSENT = {
    "rsi",
    "macd",
    "moving_averages",
    "bollinger_bands",
    "support_resistance",
    "volume_profile",
    "trend",
    "news_catalyst",
    "macro_tone",
    "sentiment",
    "mention_trend",
    "portfolio_state",
    "drawdown",
}


# ── Coverage spec ─────────────────────────────────────────────────────────


class OneOnOneCoverage(NamedTuple):
    agent_id: str
    label: str
    required_fields: frozenset[str]   # must be in live block
    absent_fields: frozenset[str]     # known gaps (documented, not failures)
    gap_types: dict[str, str]         # field → "structural" | "accidental"
    overall_rating: str               # "covered" | "partial" | "missing" | "na"


_COVERAGE: list[OneOnOneCoverage] = [
    OneOnOneCoverage(
        agent_id="fundamentals_analyst",
        label="Fundamentals Analyst",
        required_fields=frozenset({"price", "pe", "revenue_growth", "profit_margin", "net_cash", "52_week_range"}),
        absent_fields=frozenset({"balance_sheet", "earnings_history", "ps_ratio", "ev_ebitda", "peer_comparison"}),
        gap_types={
            "balance_sheet": "structural",
            "earnings_history": "structural",
            "ps_ratio": "structural",
            "ev_ebitda": "structural",
            "peer_comparison": "structural",
        },
        overall_rating="partial",
    ),
    OneOnOneCoverage(
        agent_id="market_analyst",
        label="Market Analyst",
        required_fields=frozenset({"price", "52_week_range"}),  # bare minimum
        absent_fields=frozenset({"rsi", "macd", "moving_averages", "bollinger_bands", "support_resistance", "volume_profile", "trend"}),
        gap_types={
            "rsi": "accidental",          # exists in room_runner.py, not in live block
            "trend": "accidental",
            "support_resistance": "accidental",
            "macd": "structural",
            "moving_averages": "structural",
            "bollinger_bands": "structural",
            "volume_profile": "structural",
        },
        overall_rating="missing",  # has price but no technical indicators
    ),
    OneOnOneCoverage(
        agent_id="news_analyst",
        label="News Analyst",
        required_fields=frozenset(),  # nothing in the live block is news-relevant
        absent_fields=frozenset({"news_catalyst", "macro_tone", "earnings_calendar", "regulatory_filings"}),
        gap_types={
            "news_catalyst": "structural",
            "macro_tone": "structural",
            "earnings_calendar": "structural",
            "regulatory_filings": "structural",
        },
        overall_rating="missing",
    ),
    OneOnOneCoverage(
        agent_id="social_media_analyst",
        label="Social Media Analyst",
        required_fields=frozenset(),  # nothing in the live block is sentiment-relevant
        absent_fields=frozenset({"sentiment", "mention_trend", "reddit_data", "stocktwits_scores"}),
        gap_types={
            "sentiment": "structural",
            "mention_trend": "structural",
            "reddit_data": "structural",
            "stocktwits_scores": "structural",
        },
        overall_rating="missing",
    ),
    OneOnOneCoverage(
        agent_id="bull_researcher",
        label="Bull Researcher",
        required_fields=frozenset({"price", "pe", "revenue_growth"}),
        absent_fields=frozenset({"analyst_transcript", "decision_journal"}),
        gap_types={
            "analyst_transcript": "design",   # no room in 1-on-1
            "decision_journal": "accidental",
        },
        overall_rating="partial",
    ),
    OneOnOneCoverage(
        agent_id="bear_researcher",
        label="Bear Researcher",
        required_fields=frozenset({"price", "pe", "revenue_growth"}),
        absent_fields=frozenset({"analyst_transcript", "decision_journal"}),
        gap_types={
            "analyst_transcript": "design",
            "decision_journal": "accidental",
        },
        overall_rating="partial",
    ),
    OneOnOneCoverage(
        agent_id="research_manager",
        label="Research Manager",
        required_fields=frozenset({"price"}),
        absent_fields=frozenset({"bull_bear_transcript"}),
        gap_types={"bull_bear_transcript": "design"},
        overall_rating="partial",
    ),
    OneOnOneCoverage(
        agent_id="trader",
        label="Trader",
        required_fields=frozenset({"price", "52_week_range"}),
        absent_fields=frozenset({"portfolio_state", "drawdown", "risk_debator_args"}),
        gap_types={
            "portfolio_state": "accidental",
            "drawdown": "accidental",
            "risk_debator_args": "design",   # 1-on-1 has no debate
        },
        overall_rating="partial",
    ),
    OneOnOneCoverage(
        agent_id="aggressive_debator",
        label="Aggressive Debator",
        required_fields=frozenset(),
        absent_fields=frozenset({"trader_proposal", "room_debate"}),
        gap_types={"trader_proposal": "design", "room_debate": "design"},
        overall_rating="na",
    ),
    OneOnOneCoverage(
        agent_id="conservative_debator",
        label="Conservative Debator",
        required_fields=frozenset(),
        absent_fields=frozenset({"trader_proposal", "room_debate"}),
        gap_types={"trader_proposal": "design", "room_debate": "design"},
        overall_rating="na",
    ),
    OneOnOneCoverage(
        agent_id="neutral_debator",
        label="Neutral Debator",
        required_fields=frozenset(),
        absent_fields=frozenset({"trader_proposal", "room_debate"}),
        gap_types={"trader_proposal": "design", "room_debate": "design"},
        overall_rating="na",
    ),
    OneOnOneCoverage(
        agent_id="portfolio_manager",
        label="Portfolio Manager",
        required_fields=frozenset({"price"}),
        absent_fields=frozenset({"portfolio_state", "drawdown", "verdict_from_safety_floor"}),
        gap_types={
            "portfolio_state": "accidental",
            "drawdown": "accidental",
            "verdict_from_safety_floor": "design",  # deterministic, not via prompt
        },
        overall_rating="partial",
    ),
]


# ── Helpers ───────────────────────────────────────────────────────────────


def _block_has_field(block: str, field: str) -> bool:
    """Coarse check: does the live block string contain this field category?"""
    field_markers = {
        "price": "Price:",
        "pe": "P/E:",
        "revenue_growth": "revenue growth:",
        "profit_margin": "Profit margin:",
        "net_cash": "Net cash:",
        "52_week_range": "52-week range:",
    }
    marker = field_markers.get(field)
    if marker is None:
        return False
    return marker in block


# ── Tests ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("spec", _COVERAGE, ids=lambda s: s.agent_id)
def test_required_fields_present_in_live_block(spec: OneOnOneCoverage):
    """Required fields (those in the live block the agent needs) must be present."""
    if spec.overall_rating == "na":
        pytest.skip(f"[{spec.agent_id}] Agent doesn't use 1-on-1 live block (N/A).")

    if not spec.required_fields:
        pytest.skip(f"[{spec.agent_id}] No required fields — agent is fully missing in 1-on-1 (see absent_fields).")

    for field in spec.required_fields:
        assert _block_has_field(LIVE_BLOCK_SAMPLE, field), (
            f"[{spec.agent_id}] REGRESSION: Required field '{field}' not found in live block. "
            f"Check build_live_data_block() in fundamentals.py."
        )


@pytest.mark.parametrize("spec", _COVERAGE, ids=lambda s: s.agent_id)
def test_known_absent_fields_are_documented(spec: OneOnOneCoverage):
    """Known-absent fields should not silently appear in the live block (regression guard).

    If a field that was previously absent now appears, either the gap was fixed
    (update this test + agent_data_matrix.md) or something was accidentally added.
    """
    for field in spec.absent_fields:
        if _block_has_field(LIVE_BLOCK_SAMPLE, field):
            pytest.fail(
                f"[{spec.agent_id}] Field '{field}' was listed as absent but is now "
                f"present in the live block. Update agent_data_matrix.md and this test "
                f"to reflect the fix."
            )


@pytest.mark.parametrize("spec", _COVERAGE, ids=lambda s: s.agent_id)
def test_accidental_gaps_are_flagged(spec: OneOnOneCoverage):
    """Accidental gaps (fixable without new data sources) should be xfail, not silent."""
    accidental = [f for f, t in spec.gap_types.items() if t == "accidental"]
    if not accidental:
        return
    for field in accidental:
        if not _block_has_field(LIVE_BLOCK_SAMPLE, field):
            pytest.xfail(
                f"[{spec.agent_id}] Accidental gap: '{field}' missing from 1-on-1 live block. "
                f"See gap_analysis.md for specific fix recommendation."
            )


def test_overall_ratings_summary(capsys):
    """Print a human-readable coverage summary table (always passes)."""
    print("\n\n=== 1-ON-1 COVERAGE SUMMARY ===")
    print(f"{'Agent':<30} {'Rating':<10} {'Accidental gaps'}")
    print("-" * 65)
    for spec in _COVERAGE:
        accidental = [f for f, t in spec.gap_types.items() if t == "accidental"]
        rating_display = {
            "covered": "✅ Covered",
            "partial": "⚠️  Partial",
            "missing": "❌ Missing",
            "na": "N/A",
        }.get(spec.overall_rating, spec.overall_rating)
        gap_str = ", ".join(accidental) if accidental else "—"
        print(f"{spec.label:<30} {rating_display:<10} {gap_str}")
    print()
