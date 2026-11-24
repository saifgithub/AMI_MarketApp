"""DEF535 — every Bursa desk that has a market-specific fact carries it as a CODED note.

On a 1155.KL Room the Technical Strategist wrote "+11.4pp ahead of the index" with the
FBM KLCI never named, and Macro & Events / Flow & Positioning described the missing
Bursa inputs in their own words. DEF533 had coded the note for Fundamentals only; a
prompt instruction is not a control (CR038), so the runner now appends one line per
desk, by code. US turns and US sheets must stay byte-for-byte unchanged.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path as _FsPath

import pytest

from app.schemas import AgentId
from app.services import room_bank, room_runner
from app.services.fundamentals import relative_strength_line
from app.services.room_market import (
    NOT_AVAILABLE_FOR_MARKET,
    NOT_AVAILABLE_NO_BURSA_POSITIONING,
    my_dark_lines,
    my_desk_footer,
)

_THIS_DIR = _FsPath(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

KL = "1155.KL"
_REPLY = "[STANCE: for | CONVICTION: high | HEADLINE: the read holds]\nThe read is steady."
_MY = {"market": "MY", "field_state": {"relative_strength_52w_pct": "live"}}
_US = {"field_state": {"relative_strength_52w_pct": "live"}}


def _turn(agent: AgentId, profile: dict, ticker: str) -> str:
    import test_cr266_room_gate as R

    ctx, _, _ = R._ctx()
    ctx.ticker = ticker
    ctx.profile = profile
    text, *_ = asyncio.run(room_runner._compute_agent_text(
        agent_id=agent, ctx=ctx, profile=profile, formatter={}, transcript=[],
        gateway=R._GateGateway([_REPLY]), live=True, agent_timeout_s=30.0,
    ))
    return text


def test_technical_strategist_turn_names_the_fbm_klci():
    text = _turn(AgentId.MARKET_ANALYST, _MY, KL)
    assert text.endswith(
        "[AMI note: the 52-week relative strength on this sheet is measured against "
        "the FBM KLCI, Bursa Malaysia's index, not the S&P 500.]"
    )


def test_technical_strategist_note_is_honest_when_the_klci_legs_are_absent():
    note = my_desk_footer(AgentId.MARKET_ANALYST, {"market": "MY", "field_state": {}})
    assert "FBM KLCI" in note and "not available this call" in note
    assert "measured against" not in note


def test_macro_and_events_turn_lists_exactly_its_dark_inputs():
    text = _turn(AgentId.NEWS_ANALYST, _MY, KL)
    note = text.split("\n\n")[-1]
    assert note.startswith("[AMI note: ") and NOT_AVAILABLE_FOR_MARKET in note
    # derived from what the desk's own sheet marks dark, so the two cannot drift
    dark_labels = [
        ln.split(":", 1)[0]
        for ln in my_dark_lines(news=True, fundamentals=False, social=False)
    ]
    assert dark_labels
    for label in dark_labels:
        assert label in note, label
    assert "put/call" not in note.lower()


def test_flow_and_positioning_turn_names_put_call_as_a_data_gap():
    text = _turn(AgentId.SOCIAL_MEDIA_ANALYST, _MY, KL)
    assert text.endswith(
        "[AMI note: the put/call ratio is not available for this market "
        "(no Bursa options or positioning feed is ingested); this read does not include it.]"
    )
    assert "filings" not in text.split("\n\n")[-1]
    assert NOT_AVAILABLE_NO_BURSA_POSITIONING in text


def test_the_fundamentals_note_is_unchanged():
    text = _turn(AgentId.FUNDAMENTALS_ANALYST, _MY, KL)
    assert text.endswith(
        "[AMI note: peer comparison, filed-statement detail and the filings index are "
        f"{NOT_AVAILABLE_FOR_MARKET}; this read does not include them.]"
    )


@pytest.mark.parametrize("agent", [
    AgentId.MARKET_ANALYST, AgentId.NEWS_ANALYST, AgentId.SOCIAL_MEDIA_ANALYST,
    AgentId.FUNDAMENTALS_ANALYST, AgentId.TRADER, AgentId.PORTFOLIO_MANAGER,
])
def test_a_us_turn_is_byte_for_byte_the_model_text(agent):
    text = _turn(agent, _US, "NVDA")
    assert "[AMI note" not in text
    assert my_desk_footer(agent, _US) is None
    assert my_desk_footer(agent, None) is None


@pytest.mark.parametrize("agent", [
    AgentId.TRADER, AgentId.PORTFOLIO_MANAGER, AgentId.BULL_RESEARCHER,
])
def test_a_bursa_desk_with_nothing_market_specific_gets_no_note(agent):
    assert my_desk_footer(agent, _MY) is None


def test_the_relative_strength_line_names_the_klci_in_the_spread_too():
    line = relative_strength_line(19.1, 7.7, 11.4, index_name="FBM KLCI")
    assert "vs FBM KLCI +7.7%" in line and "11.4pp ahead of the FBM KLCI" in line
    assert "the index" not in line


def test_the_us_relative_strength_line_is_unchanged():
    assert relative_strength_line(23.0, 20.0, 3.0).endswith("3.0pp ahead of the index")
    assert "S&P 500 +20.0%" in relative_strength_line(23.0, 20.0, 3.0)


def test_the_bursa_bank_variant_is_revision_four_and_us_is_untouched():
    my = room_bank.sheet_variant(
        news_state="live", social_state="live", market_withheld=False, ticker=KL,
    )
    assert my.endswith("|my_rev=4")
    us = room_bank.sheet_variant(
        news_state="live", social_state="live", market_withheld=False, ticker="NVDA",
    )
    assert "my_rev" not in us
    assert us == room_bank.sheet_variant(
        news_state="live", social_state="live", market_withheld=False,
    )
