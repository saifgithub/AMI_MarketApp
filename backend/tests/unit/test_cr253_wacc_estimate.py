"""CR253 lane B(b) — the CAPM WACC estimate beside ROIC.

CR252's CFA checklist makes "ROIC > WACC?" a mandatory read; the sheet has
carried ROIC since CR247 Phase 1B with the comparison left to the reader.
This lane emits `wacc_estimate_pct` — risk-free 4.2% + live beta × ERP 4.6%,
every input stated on the line, computed in code (CR179 Leg 4) — so the
spread is a sheet question. It is a cost-of-equity PROXY: no debt weighting
is applied and the line says so, because the weights are not sourced and a
half-built WACC wearing a whole one's label is a fabrication (CR040).

The rules pinned here:

**Only when inputs exist.** No live beta → no estimate; the ROIC line's
tail states the absence ("no WACC is sourced on this sheet"), never a made-
up hurdle.

**Every input is on the line.** Risk-free constant, beta, ERP constant —
the figure is only as checkable as its inputs.

**The flag gates the render only.** The estimate is computed on the profile
regardless; `room_wacc_enabled` is the kill switch, the parity-test
convention every other overlay follows.
"""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.schemas.agents import AgentId
from app.services import room_prompts, room_runner
from app.services.fundamentals import roic_line, wacc_estimate_line
from app.services.wacc import (
    EQUITY_RISK_PREMIUM_PCT,
    RISK_FREE_RATE_PCT,
    estimate_wacc_pct,
)

_ROIC_ARGS = dict(
    operating_income=100_000,
    tax_rate_pct=15.6,
    nopat=84_400,
    invested_capital=96_600,
    roic_pct=87.4,
    period_end="2025-09-27",
)


class TestTheEstimate:
    def test_the_capm_arithmetic_is_pinned(self):
        # 4.2 + 1.0 × 4.6 = 8.8
        assert estimate_wacc_pct(1.0) == 8.8
        # AAPL-shaped: 4.2 + 1.24 × 4.6 = 9.904 → 9.9
        assert estimate_wacc_pct(1.24) == 9.9

    def test_bad_beta_is_absent_not_fiction(self):
        assert estimate_wacc_pct(None) is None
        assert estimate_wacc_pct(0.0) is None
        assert estimate_wacc_pct(-1.2) is None
        assert estimate_wacc_pct(float("nan")) is None
        assert estimate_wacc_pct(float("inf")) is None

    def test_the_constants_are_documented_in_code(self):
        """The risk-free and ERP constants are the figure's whole provenance
        besides beta — they stay module-level, named, and stated on the
        rendered line, never inlined where a reader cannot find them."""
        assert RISK_FREE_RATE_PCT == 4.2
        assert EQUITY_RISK_PREMIUM_PCT == 4.6


class TestTheLines:
    def test_the_wacc_line_states_every_input_and_the_proxy(self):
        line = wacc_estimate_line(9.9, 1.24)
        assert line is not None
        assert "WACC estimate (LIVE)" in line
        assert "9.9%" in line
        assert "risk-free 4.2% + beta 1.24 × equity risk premium 4.6%" in line
        assert "no debt weighting" in line

    def test_no_inputs_no_line(self):
        assert wacc_estimate_line(None, 1.24) is None
        assert wacc_estimate_line(9.9, None) is None

    def test_roic_points_at_the_estimate_when_it_exists(self):
        line = roic_line(**_ROIC_ARGS, wacc_estimate_pct=9.9)
        assert line is not None
        assert "The CAPM WACC estimate beside this line is AMI's own" in line
        assert "no WACC is sourced on this sheet" not in line

    def test_roic_states_the_absence_when_the_estimate_does_not(self):
        """The honest-absence contract: ROIC live + WACC absent renders the
        pre-CR253 tail verbatim — the sheet never stays silent about the
        missing hurdle."""
        line = roic_line(**_ROIC_ARGS)
        assert line is not None
        assert "Compare against your own WACC estimate" in line
        assert "no WACC is sourced on this sheet" in line


# ── The overlay ──────────────────────────────────────────────────────────────


def test_the_overlay_emits_the_estimate_from_live_beta() -> None:
    profile = {"beta": 1.24, "field_state": {"beta": "live"}}
    fs = profile["field_state"]
    room_runner._overlay_wacc(profile, fs)
    assert fs["wacc"] == "live"
    assert profile["wacc_estimate_pct"] == 9.9
    assert profile["wacc_beta"] == 1.24


def test_the_overlay_is_absent_without_live_beta() -> None:
    profile = {"field_state": {"beta": "unavailable"}}
    fs = profile["field_state"]
    room_runner._overlay_wacc(profile, fs)
    assert fs["wacc"] == "unavailable"
    assert "wacc_estimate_pct" not in profile


def test_the_overlay_refuses_a_non_positive_beta() -> None:
    profile = {"beta": 0.0, "field_state": {"beta": "live"}}
    fs = profile["field_state"]
    room_runner._overlay_wacc(profile, fs)
    assert fs["wacc"] == "unavailable"


# ── The sheet ────────────────────────────────────────────────────────────────


def _fundamentals_profile(**over) -> dict:
    profile = {
        "ticker": "AAPL",
        "field_state": {
            "roic": "live",
            "wacc": "live",
            "pe": "live",
        },
        "roic_operating_income": 100_000,
        "roic_tax_rate_pct": 15.6,
        "roic_nopat": 84_400,
        "roic_invested_capital": 96_600,
        "roic_pct": 87.4,
        "roic_period_end": "2025-09-27",
        "wacc_estimate_pct": 9.9,
        "wacc_beta": 1.24,
        "pe": "38.8",
    }
    profile.update(over)
    return profile


@pytest.fixture(autouse=True)
def _flags_restored():
    before_wacc = settings.room_wacc_enabled
    before_roic = settings.room_roic_enabled
    yield
    settings.room_wacc_enabled = before_wacc
    settings.room_roic_enabled = before_roic


class TestTheRenderedSheet:
    def test_the_estimate_renders_beside_roic(self):
        sheet = room_prompts._format_profile(
            _fundamentals_profile(), AgentId.FUNDAMENTALS_ANALYST,
        )
        assert "WACC estimate (LIVE)" in sheet
        assert "risk-free 4.2% + beta 1.24 × equity risk premium 4.6%" in sheet
        assert "ROIC 87.4%" in sheet

    def test_roic_present_wacc_absent_states_the_absence(self):
        """The exact CR253 acceptance case: ROIC live, WACC absent (beta not
        live this call) — the sheet must render the absence honestly, not
        stay silent and not fabricate."""
        profile = _fundamentals_profile()
        profile["field_state"]["wacc"] = "unavailable"
        del profile["wacc_estimate_pct"]
        del profile["wacc_beta"]
        sheet = room_prompts._format_profile(profile, AgentId.FUNDAMENTALS_ANALYST)
        assert "WACC estimate (LIVE)" not in sheet
        assert "ROIC 87.4%" in sheet
        assert "no WACC is sourced on this sheet" in sheet

    def test_nothing_renders_with_the_flag_off(self):
        settings.room_wacc_enabled = False
        sheet = room_prompts._format_profile(
            _fundamentals_profile(), AgentId.FUNDAMENTALS_ANALYST,
        )
        assert "WACC estimate (LIVE)" not in sheet

    def test_the_flag_is_on_by_default(self):
        assert settings.room_wacc_enabled is True

    def test_presence_is_not_provenance(self):
        """A hand-built profile carrying the values with no recorded state
        renders nothing — only field_state may authorize the (LIVE) label
        (CR104)."""
        profile = _fundamentals_profile(field_state={"roic": "live", "pe": "live"})
        sheet = room_prompts._format_profile(profile, AgentId.FUNDAMENTALS_ANALYST)
        assert "WACC estimate (LIVE)" not in sheet

    def test_the_estimate_reaches_the_full_sheet_default_render(self):
        """agent_id=None is the union-of-lanes parity surface."""
        sheet = room_prompts._format_profile(_fundamentals_profile())
        assert "WACC estimate (LIVE)" in sheet

    def test_out_of_lane_agents_do_not_see_it(self):
        """The fundamentals lane firewall is untouched: the Market Analyst's
        sheet carries no WACC line."""
        sheet = room_prompts._format_profile(
            _fundamentals_profile(), AgentId.MARKET_ANALYST,
        )
        assert "WACC estimate" not in sheet
