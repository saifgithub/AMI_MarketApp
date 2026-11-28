"""DEF533 — a Room on `.KL` convened through the LIVE path still showed US framing.

CR282 lane E's tests stubbed `fetch_live_fundamentals` with the US sentinel, so the
FBM KLCI relative-strength legs and `benchmark_name` never travelled the real
`fetch_live_fundamentals` -> `_profile_for_ticker` -> frozen sheet -> `_format_profile`
route. Here the REAL `fetch_live_fundamentals` runs against a stubbed yfinance with
realistic `.KL` data (MYR, `^KLSE` history present), the sheet goes through the same
freeze codec (`encode_profile`/`decode_profile`) the live `/v1/room/stream` uses, and
each desk's text is rendered from the decoded sheet.
"""

from __future__ import annotations

import re
import sys
import types
from pathlib import Path as _FsPath

import pandas as pd
import pytest

from app.core.config import settings
from app.schemas import AgentId
from app.services import fundamentals, room_bank, room_runner
from app.services.cio_snapshot_codec import decode_profile, encode_profile
from app.services.numeric_quotation import annotate_sheet_mismatches
from app.services.room_market import NOT_AVAILABLE_FOR_MARKET
from app.services.room_prompts import _format_profile

_THIS_DIR = _FsPath(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import test_cr282_room_us_byte_identical as G  # noqa: E402

KL = "1155.KL"
_REAL_FETCH = fundamentals.fetch_live_fundamentals

_INFO = {
    "currency": "MYR",
    "currentPrice": 10.12,
    "trailingPE": 11.4,
    "fiftyTwoWeekLow": 8.9,
    "fiftyTwoWeekHigh": 10.8,
    "marketCap": 160_000_000_000,
    "freeCashflow": -15_433_000_000,
    "52WeekChange": 0.077,
    "SandP52WeekChange": 0.3,
    "regularMarketChangePercent": 0.4,
    "volume": 5_000_000,
    "averageVolume": 6_000_000,
}


def _history(first: float, last: float) -> pd.DataFrame:
    return pd.DataFrame({"Close": [first, (first + last) / 2, last]})


class _Ticker:
    def __init__(self, sym: str):
        self.sym = sym
        self.info = dict(_INFO) if sym.upper() == KL else {}

    def history(self, period="1y", **kw):
        if self.sym == "^KLSE":
            return _history(1500.0, 1560.0)
        return _history(9.4, 10.12)


@pytest.fixture
def live_sheet(monkeypatch):
    monkeypatch.setattr(settings, "market_bursa_enabled", True)
    G.install_seams(monkeypatch, ticker=KL)
    fake_yf = types.SimpleNamespace(Ticker=_Ticker, __version__="1.0.0")
    monkeypatch.setitem(sys.modules, "yfinance", fake_yf)
    monkeypatch.setattr(fundamentals, "fetch_statement_facts", lambda t: None)
    monkeypatch.setattr(fundamentals, "fetch_live_fundamentals", _REAL_FETCH)
    monkeypatch.setattr(room_runner, "fetch_live_fundamentals", _REAL_FETCH)
    sheet = room_runner._profile_for_ticker(KL)
    return decode_profile(encode_profile(sheet))


def test_the_live_klci_legs_carry_their_benchmark_name_onto_the_sheet(live_sheet):
    assert live_sheet["benchmark_name"] == "FBM KLCI"
    assert live_sheet["change_52w_sp500_pct"] == 4.0


def test_technical_strategist_relative_strength_names_the_klci_never_the_sp500(live_sheet):
    text = _format_profile(live_sheet, AgentId.MARKET_ANALYST)
    rs = [ln for ln in text.splitlines() if "Relative strength" in ln]
    assert rs and "vs FBM KLCI" in rs[0]
    for agent in list(AgentId) + [None]:
        assert "S&P" not in _format_profile(live_sheet, agent), agent


def test_without_klci_legs_the_line_is_dropped_not_sp500(live_sheet, monkeypatch):
    sheet = dict(live_sheet)
    for key in ("benchmark_name", "change_52w_pct", "change_52w_sp500_pct", "relative_strength_52w_pct"):
        sheet.pop(key, None)
    text = _format_profile(sheet, AgentId.MARKET_ANALYST)
    assert "Relative strength" not in text and "S&P" not in text


def test_a_benchmark_name_with_no_matching_state_never_reaches_an_s_and_p_label(live_sheet):
    """A frozen sheet from before the fix has the legs but no `benchmark_name`: it must
    never render as S&P 500."""
    sheet = dict(live_sheet)
    sheet.pop("benchmark_name")
    text = _format_profile(sheet, AgentId.MARKET_ANALYST)
    assert "S&P" not in text
    assert "vs FBM KLCI" in text


def test_the_fundamentals_desk_names_every_sec_dark_input(live_sheet):
    text = _format_profile(live_sheet, AgentId.FUNDAMENTALS_ANALYST)
    for label in ("Peer comparison", "Filed-statement detail"):
        assert re.search(rf"{label}: {re.escape(NOT_AVAILABLE_FOR_MARKET)}", text), label
    assert NOT_AVAILABLE_FOR_MARKET in text


def test_a_negative_amount_reads_with_the_sign_before_the_symbol(live_sheet):
    for agent in list(AgentId) + [None]:
        text = _format_profile(live_sheet, agent)
        assert "$-" not in text and "$" not in re.sub(r"\$[A-Z]{1,5}\b", "", text), agent
    full = _format_profile(live_sheet)
    assert "-RM15,433M" in full


def test_the_fact_check_footnote_is_in_ringgit_with_sign_first(live_sheet, monkeypatch):
    monkeypatch.setattr(settings, "room_factcheck_notes", "annotate")
    out = annotate_sheet_mismatches("TTM FCF is RM9,999M.", live_sheet)
    assert "-RM15,433M" in out and "$" not in out


def test_the_us_footnote_keeps_dollars(monkeypatch):
    monkeypatch.setattr(settings, "room_factcheck_notes", "annotate")
    out = annotate_sheet_mismatches("TTM FCF is $9,999M.", {"free_cash_flow": 12_000})
    assert "$12,000M" in out and "RM" not in out


def test_bursa_sheets_frozen_before_the_fix_do_not_serve_the_old_text():
    us = room_bank.sheet_variant(news_state="live", social_state="live", market_withheld=False)
    my = room_bank.sheet_variant(news_state="live", social_state="live", market_withheld=False, ticker=KL)
    assert my != us
    assert room_bank.sheet_variant(
        news_state="live", social_state="live", market_withheld=False, ticker="NVDA",
    ) == us


def _fundamentals_turn(profile: dict, ticker: str, reply: str) -> str:
    import asyncio

    import test_cr266_room_gate as R

    ctx, _, _ = R._ctx()
    ctx.ticker = ticker
    ctx.profile = profile
    text, *_ = asyncio.run(room_runner._compute_agent_text(
        agent_id=AgentId.FUNDAMENTALS_ANALYST, ctx=ctx, profile=profile,
        formatter={}, transcript=[], gateway=R._GateGateway([reply]), live=True,
        agent_timeout_s=30.0,
    ))
    return text


_REPLY = "[STANCE: for | CONVICTION: high | HEADLINE: earnings quality holds]\nThe margins are steady."


def test_a_bursa_fundamentals_turn_always_names_what_is_dark_for_the_market(live_sheet):
    text = _fundamentals_turn(live_sheet, KL, _REPLY)
    assert NOT_AVAILABLE_FOR_MARKET in text
    for what in ("peer comparison", "filed-statement detail", "filings index"):
        assert what in text


def test_a_us_fundamentals_turn_is_not_touched():
    profile = {"field_state": {}}
    text = _fundamentals_turn(profile, "NVDA", _REPLY)
    assert NOT_AVAILABLE_FOR_MARKET not in text and "[AMI note" not in text
