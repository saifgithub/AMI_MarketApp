"""CR247 Phase 1B — SBC and the SBC-adjusted free cash flow.

Every FCF figure the sheet carries is gross of stock-based compensation:
operating cash flow adds the share-based expense back as non-cash, so the
bridge, the history and the yield all count compensation paid in shares as
if it cost nothing. This line nets it out.

Three rules are pinned here, each with a measured failure class behind it.

**The subtraction happens in code, once.** TTM FCF minus TTM SBC is two
numbers plus an instruction, and CR179 Leg 4 is the record of what that
becomes in a model's hands (DEF066 → DEF235 → DEF241). The line renders the
result with both operands named; when the FCF operand is not live the SBC
still renders but the adjustment is NOT computed and the line says so.

**The two operands come from different stores and the line says which is
which.** The FCF is the yfinance-statements bridge figure; the SBC is the
filed XBRL tag (`ShareBasedCompensation`, verified live against AAPL
2026-09-29: 180 USD duration rows, cumulative year-to-date — the shape
`edgar_pit.quarterly_series` differences). The SBC window is named on the
line so the two bases can never blur.

**The tag set is new to the ingest.** A store last ingested before this
phase holds nothing under it, which at the sheet is indistinguishable from a
filer that discloses no SBC — so the overlay warns `edgar_sbc_roic_tags_not_
ingested`, the same loud-degrade shape A1 shipped after finding exactly that
state on Alpha.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.core.config import settings
from app.db import get_session
from app.db.models import EdgarFactRow
from app.schemas.agents import AgentId
from app.services import edgar_pit, edgar_tags, room_prompts, room_runner
from app.services.fundamentals import sbc_adjusted_fcf_line
from app.services.sbc import fetch_sbc_ttm, resolve_sbc_ttm

_TAG = edgar_tags.SHARE_BASED_COMPENSATION[0]
_FY25_START = date(2024, 9, 29)
_FY26_START = date(2025, 9, 28)
# Cumulative YTD, the way filers actually tag it: FY2025 builds to 4,000M over
# four quarters of 1,000M; FY2026 has three quarters of 1,100M so far.
_YTD = [
    (_FY25_START, date(2024, 12, 28), 1.0e9, date(2025, 2, 1)),
    (_FY25_START, date(2025, 3, 29), 2.0e9, date(2025, 5, 1)),
    (_FY25_START, date(2025, 6, 28), 3.0e9, date(2025, 8, 1)),
    (_FY25_START, date(2025, 9, 27), 4.0e9, date(2025, 10, 31)),
    (_FY26_START, date(2025, 12, 27), 1.1e9, date(2026, 1, 30)),
    (_FY26_START, date(2026, 3, 28), 2.2e9, date(2026, 5, 1)),
    (_FY26_START, date(2026, 6, 27), 3.3e9, date(2026, 7, 31)),
]
_AS_OF = date(2026, 9, 29)


def _facts(rows=_YTD):
    return [
        edgar_pit._FactView(
            tag=_TAG, value=value, period_start=start, period_end=end, filed=filed,
        )
        for start, end, value, filed in rows
    ]


# ── The resolver ─────────────────────────────────────────────────────────


def test_ytd_durations_difference_into_a_trailing_four_quarters() -> None:
    out = resolve_sbc_ttm(_facts(), _AS_OF)
    assert out is not None
    # Q4-25 1,000 + Q1-26 1,100 + Q2-26 1,100 + Q3-26 1,100 = 4,300 ($)
    assert out.ttm == pytest.approx(4.3e9)
    assert out.period_start == date(2025, 6, 29)
    assert out.period_end == date(2026, 6, 27)


def test_fewer_than_four_quarters_is_absent_not_partial() -> None:
    assert resolve_sbc_ttm(_facts(_YTD[-2:]), _AS_OF) is None


def test_a_stale_newest_quarter_ages_out() -> None:
    assert resolve_sbc_ttm(_facts(), date(2027, 6, 1)) is None


def test_a_restatement_supersedes_the_original_filing() -> None:
    """Per period the latest-filed value wins, and it wins BEFORE the YTD
    differencing — so restating the third-quarter cumulative figure re-prices
    that quarter alone. (Restating an EARLIER YTD row instead moves the
    differenced quarters on both sides and leaves the TTM invariant.)"""
    rows = _YTD + [(_FY26_START, date(2026, 6, 27), 3.8e9, date(2026, 8, 15))]
    out = resolve_sbc_ttm(_facts(rows), _AS_OF)
    # Q3-26 is now 3,800 − 2,200 = 1,600: total 1,000 + 1,100 + 1,100 + 1,600
    assert out is not None and out.ttm == pytest.approx(4.8e9)


def test_a_negative_trailing_sum_is_refused() -> None:
    rows = [(s, e, -v, f) for s, e, v, f in _YTD]
    assert resolve_sbc_ttm(_facts(rows), _AS_OF) is None


# ── The line ─────────────────────────────────────────────────────────────


def test_the_line_states_both_operands_and_the_result() -> None:
    line = sbc_adjusted_fcf_line(108550, 13706, "2025-06-29", "2026-06-27")
    assert "SBC-adjusted free cash flow (LIVE)" in line
    assert "TTM FCF $108,550M − TTM stock-based compensation $13,706M = $94,844M" in line
    assert "AMI's own arithmetic" in line
    assert "4 quarters 2025-06-29 to 2026-06-27" in line


def test_a_missing_fcf_renders_the_sbc_without_the_adjustment() -> None:
    """The filed SBC is real either way; the subtraction is not."""
    line = sbc_adjusted_fcf_line(None, 13706, "2025-06-29", "2026-06-27")
    assert "TTM stock-based compensation $13,706M as filed" in line
    assert "NOT computed" in line
    assert "do not compute it yourself" in line
    assert "=" not in line.split(";")[0]


def test_no_sbc_means_no_line() -> None:
    assert sbc_adjusted_fcf_line(108550, None, None, None) is None


# ── The overlay (store-backed, like the debt-structure tests) ────────────


@pytest.fixture
def seeded():
    with get_session() as s:
        s.query(EdgarFactRow).filter(EdgarFactRow.ticker == "SBCX").delete()
        for start, end, value, filed in _YTD:
            s.add(EdgarFactRow(
                cik=9, ticker="SBCX", taxonomy="us-gaap", tag=_TAG, unit="USD",
                value=value, period_start=start, period_end=end, filed=filed,
                accession_no=f"acc-{end}",
                ingested_at=datetime(2026, 9, 1, tzinfo=UTC),
            ))
        s.commit()
    yield
    with get_session() as s:
        s.query(EdgarFactRow).filter(EdgarFactRow.ticker == "SBCX").delete()
        s.commit()


def test_the_overlay_converts_edgar_dollars_to_the_sheets_millions(seeded) -> None:
    profile: dict = {}
    field_state: dict[str, str] = {}
    room_runner._overlay_sbc_and_roic(profile, field_state, "SBCX", _AS_OF)
    assert field_state["sbc"] == "live"
    assert profile["sbc_ttm"] == 4_300
    assert profile["sbc_period_start"] == "2025-06-29"
    assert profile["sbc_period_end"] == "2026-06-27"
    # No tax/debt tags seeded — ROIC is absent on its OWN state, not SBC's.
    assert field_state["roic"] == "unavailable"


def test_an_un_ingested_store_is_logged_not_silently_absent(monkeypatch) -> None:
    warned: list[str] = []
    monkeypatch.setattr(room_runner.logger, "warn",
                        lambda event, **kw: warned.append(event))
    field_state: dict[str, str] = {}
    room_runner._overlay_sbc_and_roic({}, field_state, "NOSUCH", _AS_OF)
    assert field_state["sbc"] == "unavailable"
    assert "edgar_sbc_roic_tags_not_ingested" in warned


def test_an_unreachable_store_costs_the_block_not_the_convene(monkeypatch) -> None:
    def boom(*_a, **_k):
        raise RuntimeError("no such table: edgar_facts")

    warned: list[str] = []
    monkeypatch.setattr(room_runner.sbc, "fetch_sbc_ttm", boom)
    monkeypatch.setattr(room_runner.logger, "warn",
                        lambda event, **kw: warned.append(event))
    field_state: dict[str, str] = {}
    room_runner._overlay_sbc_and_roic({}, field_state, "ANY", _AS_OF)
    assert field_state == {"sbc": "unavailable", "roic": "unavailable"}
    assert "edgar_sbc_roic_unreadable" in warned


def test_fetch_sbc_ttm_reads_the_store(seeded) -> None:
    out = fetch_sbc_ttm("SBCX", _AS_OF)
    assert out is not None and out.ttm == pytest.approx(4.3e9)


# ── The render seam ──────────────────────────────────────────────────────


def _profile() -> dict:
    return {
        "field_state": {"sbc": "live", "free_cash_flow_ttm": "live"},
        "free_cash_flow_ttm": 108550,
        "sbc_ttm": 13706,
        "sbc_period_start": "2025-06-29",
        "sbc_period_end": "2026-06-27",
    }


def _sheet(**flags) -> str:
    for name, value in flags.items():
        setattr(settings, name, value)
    return room_prompts._format_profile(_profile(), AgentId.FUNDAMENTALS_ANALYST)


@pytest.fixture(autouse=True)
def _flag_restored():
    before = settings.room_sbc_enabled
    yield
    settings.room_sbc_enabled = before


def test_nothing_renders_with_the_flag_off() -> None:
    settings.room_sbc_enabled = False
    assert "SBC-adjusted free cash flow" not in _sheet()


def test_the_flag_is_on_by_default() -> None:
    """Flipped ON 2026-09-29 (CR247 Phase 1B — unit suite + the live AAPL
    render probe). The env var stays as the kill switch; the flag-off render
    is pinned above."""
    assert settings.room_sbc_enabled is True


def test_the_line_appears_with_the_flag_on() -> None:
    settings.room_sbc_enabled = True
    sheet = _sheet(room_sbc_enabled=True)
    assert "SBC-adjusted free cash flow (LIVE)" in sheet
    assert "$94,844M" in sheet


def test_presence_is_not_provenance() -> None:
    """CR104/D8 — the block state, not the keys, decides."""
    settings.room_sbc_enabled = True
    profile = _profile()
    profile["field_state"] = {}
    assert "SBC-adjusted free cash flow" not in room_prompts._format_profile(
        profile, AgentId.FUNDAMENTALS_ANALYST)


def test_the_sbc_survives_an_absent_fcf_operand() -> None:
    settings.room_sbc_enabled = True
    profile = _profile()
    profile["field_state"] = {"sbc": "live"}  # FCF operand not live
    sheet = room_prompts._format_profile(profile, AgentId.FUNDAMENTALS_ANALYST)
    assert "TTM stock-based compensation $13,706M as filed" in sheet
    assert "NOT computed" in sheet


def test_out_of_lane_agents_do_not_see_the_line() -> None:
    settings.room_sbc_enabled = True
    sheet = room_prompts._format_profile(_profile(), AgentId.MARKET_ANALYST)
    assert "SBC-adjusted free cash flow" not in sheet
