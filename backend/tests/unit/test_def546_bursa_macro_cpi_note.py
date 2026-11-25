"""DEF546 — a Bursa Macro & Events turn always carries the CPI reading, month and source.

On a 1155.KL Room the desk wrote "Malaysia CPI at +1.9% YoY" with no reference month
and no OpenDOSM attribution, although the sheet it was handed had both. A prompt ask is
not a control (CR038), so the runner appends the coded CPI note, built from the same
read as the sheet line. US turns and US sheets stay byte-for-byte unchanged.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date
from pathlib import Path as _FsPath

import pytest

from app.schemas import AgentId
from app.services import opendosm_cpi, room_runner
from app.services.opendosm_cpi import CpiRead
from app.services.room_market import my_desk_footer

_THIS_DIR = _FsPath(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

KL = "1155.KL"
_REPLY = "[STANCE: for | CONVICTION: high | HEADLINE: the read holds]\nMalaysia CPI at +1.9% YoY."
_LIVE = CpiRead(1.9, date(2026, 10, 1), 137.7, 135.1)
_DARK = CpiRead(None, None, None, None, "the OpenDOSM CPI feed could not be read")


def _profile(read: CpiRead) -> dict:
    return {
        "market": "MY",
        "macro_cpi_line": opendosm_cpi.cpi_line(read),
        "macro_cpi_note": opendosm_cpi.cpi_note(read),
    }


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


def test_the_cpi_note_states_reading_month_and_source():
    note = opendosm_cpi.cpi_note(_LIVE)
    assert "+1.9%" in note and "Oct 2026" in note and "OpenDOSM" in note
    assert note.startswith("[AMI note: ") and note.endswith("]")


def test_the_cpi_note_says_so_when_there_is_no_reading():
    note = opendosm_cpi.cpi_note(_DARK)
    assert "not available this call" in note and "could not be read" in note
    assert "%" not in note
    assert "from memory" not in note


def test_a_bursa_macro_turn_ends_with_the_cpi_note_even_when_the_desk_omits_month_and_source():
    text = _turn(AgentId.NEWS_ANALYST, _profile(_LIVE), KL)
    paragraphs = text.split("\n\n")
    assert "Oct 2026" not in paragraphs[0] and "OpenDOSM" not in paragraphs[0]
    assert paragraphs[-1] == opendosm_cpi.cpi_note(_LIVE)
    assert paragraphs[-2].startswith("[AMI note: ")
    assert "not available for this market" in paragraphs[-2]


def test_a_bursa_macro_turn_says_cpi_is_unavailable_when_the_feed_is_dark():
    text = _turn(AgentId.NEWS_ANALYST, _profile(_DARK), KL)
    assert text.endswith(opendosm_cpi.cpi_note(_DARK))


def test_the_cpi_note_sits_before_the_malay_mail_note():
    profile = _profile(_LIVE) | {"my_news_rss": "live"}
    paragraphs = my_desk_footer(AgentId.NEWS_ANALYST, profile).split("\n\n")
    assert [("CPI" in p, "Malay Mail" in p) for p in paragraphs] == [
        (False, False), (True, False), (False, True),
    ]


def test_only_macro_and_events_carries_the_cpi_note():
    profile = _profile(_LIVE)
    for agent in (
        AgentId.MARKET_ANALYST, AgentId.FUNDAMENTALS_ANALYST, AgentId.SOCIAL_MEDIA_ANALYST,
    ):
        assert "CPI" not in (my_desk_footer(agent, profile) or "")


def test_a_us_macro_turn_is_byte_for_byte_the_model_text():
    text = _turn(AgentId.NEWS_ANALYST, {"field_state": {}}, "NVDA")
    assert "[AMI note" not in text
    assert my_desk_footer(AgentId.NEWS_ANALYST, {"macro_cpi_note": "[x]"}) is None


@pytest.mark.parametrize("enabled", [True, False])
def test_the_runner_stamps_the_note_beside_the_sheet_line(monkeypatch, enabled):
    read = _LIVE if enabled else _DARK
    monkeypatch.setattr(opendosm_cpi, "fetch_cpi", lambda: read)
    profile: dict = {}
    room_runner._stamp_my_macro(profile, {}, date(2026, 11, 24))
    assert profile["macro_cpi_note"] == opendosm_cpi.cpi_note(read)
    assert profile["macro_cpi_line"] == opendosm_cpi.cpi_line(read)
