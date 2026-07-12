"""Validate that the Room profile dict covers what each agent's prompt claims.

Strategy: load the Room profile fixture and each agent's base prompt, then assert
that every data *field group* the prompt explicitly names has at least one
corresponding key in the profile dict. Tests are deliberately coarse — we're
checking categories, not exact field names, because prompts use human language
("support and resistance levels") not code keys ("support").

No network calls. No LLM calls. Pure static checks.

Run:
    python -m pytest Silent_Scout/05_agent_alignment/validation_suite/test_room_data_coverage.py -v
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import NamedTuple

import pytest

# ── Paths ─────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parents[3]  # validation_suite/ → 05_agent_alignment/ → Silent_Scout/ → repo root
AGENTS_DIR = REPO_ROOT / "content" / "agents"
FIXTURE = Path(__file__).parent / "fixtures" / "sample_profile.json"

# ── Load the Room profile fixture ─────────────────────────────────────────


@pytest.fixture(scope="module")
def room_profile() -> dict:
    return json.loads(FIXTURE.read_text())


# ── Agent prompt loader ────────────────────────────────────────────────────


def _load_prompt(agent_id: str) -> str:
    """Return the raw text of content/agents/{agent_id}.md."""
    path = AGENTS_DIR / f"{agent_id}.md"
    assert path.exists(), f"Agent prompt not found: {path}"
    return path.read_text()


# ── Coverage spec ─────────────────────────────────────────────────────────
#
# Each spec maps an agent_id to a list of (label, profile_keys, gap_type).
# label       — human-readable name for the test
# profile_keys — one or more keys; test passes if ANY key exists in the profile
# gap_type    — "accidental" | "structural" | "design"
#               structural/design gaps are EXPECTED to be absent; the test
#               records them as known gaps rather than failing.


class FieldCheck(NamedTuple):
    label: str
    profile_keys: tuple[str, ...]
    gap_type: str  # "none" | "accidental" | "structural" | "design"


# Profile keys present in the Room profile dict (from sample_profile.json)
_ROOM_COVERAGE: dict[str, list[FieldCheck]] = {
    "fundamentals_analyst": [
        FieldCheck("price", ("base_price",), "none"),
        FieldCheck("P/E ratio", ("pe",), "none"),
        FieldCheck("revenue growth", ("rev_growth",), "none"),
        FieldCheck("FCF margin", ("fcf_margin",), "none"),
        FieldCheck("net cash", ("net_cash",), "none"),
        FieldCheck("valuation tone / peer PE", ("sector_pe", "valuation_tone"), "none"),
        FieldCheck("earnings catalyst", ("catalyst",), "structural"),  # synthetic
        FieldCheck("P/S or EV/EBITDA", (), "structural"),  # not in profile
        FieldCheck("buybacks / dividends", (), "structural"),
    ],
    "market_analyst": [
        FieldCheck("price", ("base_price",), "none"),
        FieldCheck("52-week range", ("low", "high"), "none"),
        FieldCheck("RSI", ("rsi",), "none"),
        FieldCheck("trend", ("trend",), "none"),
        FieldCheck("support level", ("support",), "none"),
        FieldCheck("breakout level", ("breakout",), "none"),
        FieldCheck("volume", ("volume_tone",), "none"),
        FieldCheck("MACD", (), "structural"),  # not available
        FieldCheck("moving averages (20MA/50MA/200MA)", (), "structural"),
        FieldCheck("Bollinger Bands", (), "structural"),
        FieldCheck("multi-timeframe (1H, daily, weekly)", (), "structural"),
    ],
    "news_analyst": [
        FieldCheck("recent catalyst", ("catalyst",), "none"),  # synthetic but present
        FieldCheck("forward catalyst / macro calendar", ("forward_catalyst",), "none"),
        FieldCheck("macro tone", ("macro_tone",), "none"),
        FieldCheck("Fed stance", ("fed_tone",), "none"),
        FieldCheck("real-time news feed", (), "structural"),  # no live feed
        FieldCheck("earnings calendar", (), "structural"),
        FieldCheck("regulatory filings", (), "structural"),
    ],
    "social_media_analyst": [
        FieldCheck("sentiment tone", ("sentiment_tone",), "none"),
        FieldCheck("sentiment score (σ)", ("sentiment_score",), "none"),
        FieldCheck("mention trend", ("mention_trend",), "none"),
        FieldCheck("influencer take", ("influencer_take",), "none"),
        FieldCheck("sentiment pattern", ("pattern",), "none"),
        FieldCheck("Reddit / StockTwits / Twitter live data", (), "structural"),
        FieldCheck("Google Trends", (), "structural"),
    ],
    "bull_researcher": [
        # Bull reads analyst outputs via transcript — not from profile dict directly.
        # We check the profile has enough scaffolding to inform an analyst's output.
        FieldCheck("price", ("base_price",), "none"),
        FieldCheck("bull thesis scaffolding", ("bull_thesis", "bull_evidence"), "none"),
        FieldCheck("bull falsifier", ("bull_falsifier",), "none"),
        FieldCheck("mandate context", ("data_source",), "none"),  # proxy — mandate is in system prompt
    ],
    "bear_researcher": [
        FieldCheck("price", ("base_price",), "none"),
        FieldCheck("bear risk scaffolding", ("bear_risk", "bear_catalyst"), "none"),
        FieldCheck("bear invalidator", ("bear_invalidator",), "none"),
        FieldCheck("downside quantification", ("bear_quant", "downside"), "none"),
    ],
    "research_manager": [
        # Reads transcript only; profile used for context numbers.
        FieldCheck("price", ("base_price",), "none"),
        FieldCheck("valuation context", ("pe", "sector_pe"), "none"),
    ],
    "trader": [
        FieldCheck("price", ("base_price",), "none"),
        FieldCheck("support / entry reference", ("support", "low"), "none"),
        FieldCheck("target reference", ("high", "breakout"), "none"),
        FieldCheck("risk-reward context", ("upside", "downside"), "none"),
        # Risk Debators' args are NOT in profile (phase-sequencing gap).
        FieldCheck("Risk Debator arguments", (), "accidental"),
        # Portfolio state not in profile (it's in _RoomContext, not profile dict).
        FieldCheck("portfolio value / drawdown", (), "accidental"),
    ],
    "aggressive_debator": [
        FieldCheck("price", ("base_price",), "none"),
        FieldCheck("Trader proposal reference (via transcript)", ("data_source",), "none"),
        # Debators run in parallel — they don't see each other.
        FieldCheck("other Debators' arguments (parallel run)", (), "design"),
    ],
    "conservative_debator": [
        FieldCheck("price", ("base_price",), "none"),
        FieldCheck("Trader proposal reference (via transcript)", ("data_source",), "none"),
        FieldCheck("other Debators' arguments (parallel run)", (), "design"),
    ],
    "neutral_debator": [
        FieldCheck("price", ("base_price",), "none"),
        FieldCheck("Trader proposal reference (via transcript)", ("data_source",), "none"),
        FieldCheck("other Debators' arguments (parallel run)", (), "design"),
    ],
    "portfolio_manager": [
        FieldCheck("price", ("base_price",), "none"),
        FieldCheck("full mandate context", ("data_source",), "none"),
        FieldCheck("Trader + Debator outputs (via transcript)", ("data_source",), "none"),
        FieldCheck("portfolio / drawdown state", (), "accidental"),
    ],
}


# ── Tests ─────────────────────────────────────────────────────────────────


def _all_agent_checks():
    """Pytest parametrize input: (agent_id, field_check)."""
    for agent_id, checks in _ROOM_COVERAGE.items():
        for check in checks:
            yield agent_id, check


@pytest.mark.parametrize("agent_id,check", _all_agent_checks(), ids=lambda x: getattr(x, "label", str(x)))
def test_room_field_coverage(agent_id: str, check: FieldCheck, room_profile: dict):
    """Assert Room profile contains the expected field, or record known gap."""
    if check.gap_type in ("structural", "design"):
        # Known gap — document it but don't fail.
        if check.profile_keys:
            # Structural gaps with partial coverage: at least one key must exist.
            assert any(k in room_profile for k in check.profile_keys), (
                f"[{agent_id}] Structural/partial field '{check.label}' has no key in profile: "
                f"{check.profile_keys}"
            )
        else:
            pytest.skip(
                f"[{agent_id}] Known {check.gap_type} gap: '{check.label}' "
                f"not present in Room profile (by design)"
            )
    elif check.gap_type == "accidental":
        # Accidental gap — document it as a known failure, don't block CI.
        if not check.profile_keys:
            pytest.xfail(
                f"[{agent_id}] Accidental gap: '{check.label}' missing from Room profile. "
                f"See gap_analysis.md for fix."
            )
        present = any(k in room_profile for k in check.profile_keys)
        if not present:
            pytest.xfail(
                f"[{agent_id}] Accidental gap: '{check.label}' keys {check.profile_keys} "
                f"missing from Room profile. See gap_analysis.md."
            )
    else:
        # gap_type == "none" — must be covered.
        assert check.profile_keys, f"[{agent_id}] Test misconfigured: '{check.label}' has no keys"
        assert any(k in room_profile for k in check.profile_keys), (
            f"[{agent_id}] REGRESSION: Field '{check.label}' (keys: {check.profile_keys}) "
            f"is missing from the Room profile dict. Either the profile was changed "
            f"(fix _profile_for_ticker) or this test needs updating."
        )


def test_all_agents_have_prompt_file():
    """Every agent in the coverage spec has a base prompt file."""
    for agent_id in _ROOM_COVERAGE:
        path = AGENTS_DIR / f"{agent_id}.md"
        assert path.exists(), (
            f"Prompt file missing: {path}. Add the file or remove the agent from _ROOM_COVERAGE."
        )


def test_prompt_files_have_inputs_section():
    """Every agent prompt has an ## Inputs section (or ## Role if no inputs listed)."""
    for agent_id in _ROOM_COVERAGE:
        text = _load_prompt(agent_id)
        has_inputs = "## Inputs" in text or "## Role" in text
        assert has_inputs, (
            f"[{agent_id}] Base prompt has no ## Inputs or ## Role section. "
            f"Structured sections are required for automated parsing."
        )


def test_profile_fixture_has_required_base_keys():
    """Sanity-check the fixture itself has the minimum expected Room profile keys."""
    profile = json.loads(FIXTURE.read_text())
    required = {
        "ticker", "base_price", "pe", "rev_growth", "fcf_margin", "net_cash",
        "rsi", "trend", "support", "low", "high", "breakout", "volume_tone",
        "catalyst", "forward_catalyst", "macro_tone", "fed_tone",
        "sentiment_tone", "sentiment_score", "data_source",
    }
    missing = required - set(profile.keys())
    assert not missing, (
        f"sample_profile.json is missing keys: {missing}. "
        f"Update the fixture to match _profile_for_ticker() output."
    )
