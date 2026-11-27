"""CR287 — sector-aware metrics: banks' misleading figures are "not applicable", regulated utilities get context.

Maybank (1155.KL) carried free cash flow of -RM15,433M on its sheet, and 16 of 17 Rooms argued
it as if it were cash burn; for a bank, operating cash flow and debt mostly reflect customer
loans and deposits. The control is structural: for a bank (the sheet's own `industry` tag) the
figures are removed from the profile and marked `not_applicable`, so the renderer, the terminal
question's inputs, the debt check, the fact-check and the Risk Officer's corroboration corpus all
lose them together, and one sheet line says why. Behind `ROOM_SECTOR_METRICS_ENABLED`.

Proved here: the table and `family_for`; a US and a Bursa bank sheet carry none of the listed
numbers (checked by value) and carry the one line; the debt check records "not applicable: bank"
and writes no verdict note; the fact-check and the Risk Officer cannot pair or corroborate a
prose figure with a listed field; and with the switch off, or for a non-bank with it on, nothing
changes (the pre-CR287 US golden corpus is reproduced byte for byte).

Regulated utilities (decision B) are a different KIND of row: every figure stays, one coded
context line is added, and the debt check is skipped "not applicable: regulated utility". Renewable,
Diversified and Independent Power Producers are not rows.
"""

from __future__ import annotations

import copy
import re
import sys
from pathlib import Path as _FsPath

import pytest

from app.core.config import settings
from app.schemas import AgentId
from app.services import (
    edgar_filings_feed,
    edgar_pit,
    fundamentals,
    numeric_quotation,
    opendosm_cpi,
    put_call,
    risk_officer,
    room_bank,
    room_market,
    room_runner,
    sector_metrics,
)
from app.services.cio_snapshot_codec import decode_profile, encode_profile
from app.services.room_grader_contract import Answer, build_terminal_inputs
from app.services.room_graders import terminal_materiality as M
from app.services.room_prompts import _format_profile
from app.services.room_runner import _append_debt_check_note
from app.schemas.room import Verdict, VerdictAction

_THIS_DIR = _FsPath(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import test_cr282_room_us_byte_identical as G  # noqa: E402
import test_def553_debt_check_note as D553  # noqa: E402
import test_prompt_data_parity as P  # noqa: E402
from test_cr285_debt_coverage import _inputs, _yes  # noqa: E402

KL = "1155.KL"
LINE = (
    "Free cash flow, net debt, EV/EBITDA, interest coverage: not applicable for banks — "
    "a bank's operating cash flow and debt mostly reflect customer loans and deposits."
)

# What the golden US sheet renders for the listed fields (its own fingerprints).
US_FINGERPRINTS = (
    "$45,678M", "3.87%", "$3,333M", "$9,876M", "$944M", "$8,901M", "$55,221M", "19.42x",
    "9.4x", "COVQUARTERSENT", "CFBASISSENT", "EVWINDOWSENT", "$3,210M", "63% of TTM FCF",
    "$2,100M", "$1,400M", "5.2%", "$612M", "$41,000M",
)

LADDER_AND_FRIENDS = {
    "debt_maturity_labels": ["Within 1 year", "Year 2"],
    "debt_maturity_values": [2100.0, 1400.0],
    "debt_maturity_period_end": "2026-09-30",
    "cost_of_debt_pct": 5.2,
    "cost_of_debt_basis": "accrued",
    "cost_of_debt_interest": 612,
    "cost_of_debt_gross_debt": 41000,
    "cost_of_debt_period_end": "2026-09-30",
    "sbc_ttm": 777,
    "sbc_period_start": "2025-10-01",
    "sbc_period_end": "2026-09-30",
}


@pytest.fixture
def sector_on(monkeypatch):
    monkeypatch.setattr(settings, "room_sector_metrics_enabled", True)


def _us_sheet(*, industry: str = "Banks - Diversified") -> dict:
    """The frozen, production-shaped US golden sheet with the ladder, cost-of-debt and SBC blocks
    added (the golden leaves them dark), tagged with `industry`."""
    sheet = decode_profile(G._load()["sheet"])
    sheet.update(copy.deepcopy(LADDER_AND_FRIENDS))
    sheet["industry"] = industry
    state = sheet["field_state"]
    for key in LADDER_AND_FRIENDS:
        state[key] = "live"
    state["debt_maturity"] = state["cost_of_debt"] = state["sbc"] = "live"
    return sheet


def _enable_blocks(monkeypatch) -> None:
    G.enable_default_off_flags(monkeypatch)
    for flag in ("room_sbc_enabled", "room_debt_maturity_enabled", "room_cost_of_debt_enabled"):
        monkeypatch.setattr(settings, flag, True)


# ── 1. the table and `family_for` ────────────────────────────────────────────


@pytest.mark.parametrize("industry,expected", [
    ("Banks - Regional", "bank"),
    ("Banks - Diversified", "bank"),
    ("banks - regional", "bank"),
    (None, None),
    ("", None),
    ("Insurance - Life", None),
    ("Capital Markets", None),
    ("REIT - Retail", None),
    ("Utilities - Renewable", None),
    ("Semiconductors", None),
])
def test_family_for_reads_the_industry_tag(industry, expected):
    assert sector_metrics.family_for(industry, "Financial Services") == expected


def test_a_sector_alone_is_no_bank_signal():
    assert sector_metrics.family_for(None, "Financial Services") is None


def test_the_bank_rule_lists_the_figures_and_states_the_reason():
    rule = sector_metrics.FAMILY_RULES["bank"]
    assert rule.line == LINE
    assert rule.check_reason == "not applicable: bank"
    for key in (
        "free_cash_flow", "fcf_yield", "free_cash_flow_ttm", "fcf_history", "fcf_conversion_pct",
        "capital_return_pct_fcf", "net_cash", "total_debt", "total_cash", "debt_maturity",
        "ev_to_ebitda", "historical_ev_ebitda_median", "interest_coverage",
        "interest_coverage_quarter", "interest_expense_quarter_usd_m",
    ):
        assert key in rule.fields, key
    for kept in ("pe", "market_cap", "return_on_equity", "dividend_yield", "payout_ratio", "capex_ttm"):
        assert kept not in rule.fields, kept


def test_the_bank_marks_are_read_through_the_one_table(sector_on):
    sheet = _us_sheet()
    assert sector_metrics.not_applicable(sheet) is None
    sector_metrics.apply_to_profile(sheet)
    assert sector_metrics.not_applicable(sheet).family == "bank"
    assert sector_metrics.is_not_applicable("free_cash_flow", sheet)
    assert sector_metrics.is_not_applicable("interest_coverage", sheet)
    assert not sector_metrics.is_not_applicable("pe", sheet)
    assert sector_metrics.is_not_applicable("free_cash_flow", {}) is False


def test_a_bursa_bank_sheet_shape_is_a_bank():
    sheet = {"market": "MY", "industry": "Banks - Regional", "sector": "Financial Services",
             "field_state": {"industry": "live", "sector": "live"}}
    assert sector_metrics.family_for(*sector_metrics._industry_of(sheet)) == "bank"
    unlabelled = {**sheet, "field_state": {"industry": "unavailable"}}
    assert sector_metrics.family_for(*sector_metrics._industry_of(unlabelled)) is None


def test_apply_is_idempotent_and_the_marker_survives_the_frozen_sheet_codec(sector_on):
    sheet = _us_sheet()
    sector_metrics.apply_to_profile(sheet)
    once = copy.deepcopy(sheet)
    sector_metrics.apply_to_profile(sheet)
    assert sheet == once
    assert sector_metrics.not_applicable(decode_profile(encode_profile(sheet))).family == "bank"


# ── 2. the sheet (US and Bursa) ──────────────────────────────────────────────


def test_a_us_bank_sheet_drops_every_listed_number_and_states_why(sector_on, monkeypatch):
    _enable_blocks(monkeypatch)
    before = _us_sheet()
    sheet = copy.deepcopy(before)
    sector_metrics.apply_to_profile(sheet)
    rule = sector_metrics.FAMILY_RULES["bank"]

    for key in rule.fields:
        assert key not in sheet, key
        assert sheet["field_state"][key] == "not_applicable", key

    full_before = _format_profile(before)
    for fp in US_FINGERPRINTS:
        assert fp in full_before, f"non-vacuity: {fp} must render on the un-stripped sheet"
    for agent in [None, *AgentId]:
        text = _format_profile(sheet, agent)
        for fp in US_FINGERPRINTS:
            assert fp not in text, (agent, fp)
        for phrase in ("Cash-flow bridge", "Debt maturity ladder", "Implied cost of debt",
                       "Interest coverage", "FCF yield", "EV/EBITDA", "net cash $", "Net cash $",
                       "Net debt $", "net debt $", "gross debt", "gross cash", "Free cash flow $"):
            assert phrase not in text.replace(LINE, ""), (agent, phrase)
    assert _format_profile(sheet, AgentId.FUNDAMENTALS_ANALYST).count(LINE) == 1
    assert _format_profile(sheet).count(LINE) == 1
    assert "Balance sheet: net cash not available" not in _format_profile(sheet)


def test_the_bank_sheet_keeps_what_does_apply(sector_on, monkeypatch):
    _enable_blocks(monkeypatch)
    sheet = _us_sheet()
    sector_metrics.apply_to_profile(sheet)
    text = _format_profile(sheet)
    for kept in ("market cap $1,234,567M", "P/S 7.31x", "31.55", "1.63", "27.33", "Capital expenditure"):
        assert kept in text, kept


# 1155.KL as it stood, FCF -RM15,433M, -12.5% yield; every other listed figure fingerprinted.
MAYBANK = {
    **P._FUND_SENTINEL,
    "industry": "Banks - Regional",
    "sector": "Financial Services",
    "free_cash_flow": -15433,
    "fcf_yield": -12.5,
    "free_cash_flow_ttm": -15433,
    "net_cash": -83211,
    "total_debt": 91234,
    "total_cash": 8023,
    "ev_to_ebitda": "-6.66",
    "interest_coverage": 0.8,
    "interest_coverage_quarter": "2026-09-30",
}


def _boom(*a, **k):
    raise AssertionError("an SEC/EDGAR/options seam was reached for a Bursa ticker")


@pytest.fixture
def bursa_bank_sheet(monkeypatch):
    """The production `_profile_for_ticker` on 1155.KL, with Maybank's real-shaped figures, the
    switch on. Same seams as `test_cr282_room_my.my_sheet`."""
    monkeypatch.setattr(settings, "market_bursa_enabled", True)
    monkeypatch.setattr(settings, "room_sector_metrics_enabled", True)
    G.install_seams(monkeypatch, ticker=KL)
    monkeypatch.setattr(fundamentals, "fetch_live_fundamentals", lambda t: dict(MAYBANK))
    monkeypatch.setattr(room_runner, "fetch_live_fundamentals", lambda t: dict(MAYBANK))
    monkeypatch.setattr(edgar_filings_feed, "fetch_recent_filings", _boom)
    monkeypatch.setattr(edgar_pit, "load_facts", _boom)
    monkeypatch.setattr(put_call, "fetch_put_call_ratio", _boom)
    for name in (
        "_overlay_debt_structure", "_overlay_filing_dimensions", "_overlay_executive_change",
        "_overlay_capital_returns", "_overlay_recent_filings", "_overlay_sbc_and_roic",
        "_overlay_insider_forensics", "_overlay_edgar_8k_flags", "_overlay_put_call",
        "_overlay_peer_comparison",
    ):
        monkeypatch.setattr(room_runner, name, _boom)
    monkeypatch.setattr(opendosm_cpi, "_fetch_rows", lambda: [
        {"date": "2026-10-01", "index": 137.7, "division": "overall"},
        {"date": "2025-10-01", "index": 135.1, "division": "overall"},
    ])
    monkeypatch.setattr(settings, "opendosm_cpi_enabled", True)
    opendosm_cpi.reset_cache()
    return room_runner._profile_for_ticker(KL)


def test_a_bursa_bank_sheet_has_no_fcf_number_and_the_one_line(bursa_bank_sheet, monkeypatch):
    sheet = bursa_bank_sheet
    assert sheet["market"] == "MY" and sheet["sector_family"] == "bank"
    for agent in [None, *AgentId]:
        text = _format_profile(sheet, agent)
        for needle in ("15,433", "-12.5", "83,211", "91,234", "8,023", "-6.66", "0.8x", "FCF yield",
                       "EV/EBITDA", "gross debt", "gross cash"):
            assert needle not in text.replace(LINE, ""), (agent, needle)
    full = _format_profile(sheet)
    assert full.count(LINE) == 1
    # still there: return on equity, dividend yield and payout ratio, and the other valuation parts
    for kept in ("31.55", "1.63", "27.33", "P/S 7.31x"):
        assert kept in full, kept
    # the coded RM lines stay in ringgit and carry no dollar amount
    assert not re.search(r"\$\d", full)


def test_the_same_bursa_sheet_with_the_switch_off_still_shows_the_numbers(monkeypatch):
    monkeypatch.setattr(settings, "market_bursa_enabled", True)
    G.install_seams(monkeypatch, ticker=KL)
    monkeypatch.setattr(fundamentals, "fetch_live_fundamentals", lambda t: dict(MAYBANK))
    monkeypatch.setattr(room_runner, "fetch_live_fundamentals", lambda t: dict(MAYBANK))
    monkeypatch.setattr(edgar_filings_feed, "fetch_recent_filings", _boom)
    monkeypatch.setattr(edgar_pit, "load_facts", _boom)
    monkeypatch.setattr(put_call, "fetch_put_call_ratio", _boom)
    for name in (
        "_overlay_debt_structure", "_overlay_filing_dimensions", "_overlay_executive_change",
        "_overlay_capital_returns", "_overlay_recent_filings", "_overlay_sbc_and_roic",
        "_overlay_insider_forensics", "_overlay_edgar_8k_flags", "_overlay_put_call",
        "_overlay_peer_comparison",
    ):
        monkeypatch.setattr(room_runner, name, _boom)
    sheet = room_runner._profile_for_ticker(KL)
    assert "sector_family" not in sheet
    text = _format_profile(sheet)
    assert "-RM15,433M" in text and LINE not in text


# ── 3. the debt check ────────────────────────────────────────────────────────


def _bank_inputs(sheet) -> dict:
    return _inputs(
        build_terminal_inputs(sheet, 42, mandate_horizon_months=24, min_coverage=1.0),
        months=24, minimum=1.0,
    )


def test_the_bank_debt_check_records_skipped_not_applicable_and_never_computes(sector_on):
    sheet = _us_sheet()
    sector_metrics.apply_to_profile(sheet)
    inputs = build_terminal_inputs(sheet, 42, mandate_horizon_months=24, min_coverage=1.0)
    assert inputs["not_applicable_family"] == "bank"
    assert inputs["ladder"] is None and inputs["fcf_ttm"] is None and inputs["total_cash"] is None

    out = M.apply_materiality(_yes(), _bank_inputs(sheet))
    check = out.detail["terminal_check"]
    assert check["skipped"] is True
    assert check["reason"].endswith("not applicable: bank")
    assert check["due_in_horizon"] is None and check["coverage"] is None and check["available"] is None
    assert "verdict_note" not in check
    assert out.answer is Answer.NO and "not applicable: bank" in out.detail["terminal_rejected"]


def test_a_skipped_bank_check_adds_no_debt_check_note(sector_on):
    sheet = _us_sheet()
    sector_metrics.apply_to_profile(sheet)
    result = D553._result(_bank_inputs(sheet))
    verdict = Verdict(action=VerdictAction.PASS, reason="CIO says.")
    text, out = _append_debt_check_note("Room.", verdict, result, "BAC")
    assert text == "Room." and out.reason == "CIO says."
    assert "AMI debt check" not in text + out.reason


def test_a_non_bank_debt_check_is_what_it_was(sector_on):
    sheet = _us_sheet(industry="Semiconductors")
    sector_metrics.apply_to_profile(sheet)
    inputs = build_terminal_inputs(sheet, 42, mandate_horizon_months=24, min_coverage=1.0)
    assert "not_applicable_family" not in inputs
    assert set(inputs) == set(build_terminal_inputs(_us_sheet(industry="Semiconductors"), 42))


# ── 4. the fact-check and the Risk Officer ───────────────────────────────────

MAYBANK_PROSE = "Maybank's FCF of -RM15,433M is a cash burn that no desk has answered."


def _maybank_profile(*, switch: bool, monkeypatch) -> dict:
    monkeypatch.setattr(settings, "room_sector_metrics_enabled", switch)
    profile = {
        "industry": "Banks - Regional", "market": "MY", "free_cash_flow": -15433,
        "fcf_history": [-15433, 9000, 8100], "capex_history": [800, 700, 650],
        "net_cash": -83211, "total_debt": 91234, "total_cash": 8023,
        "field_state": {
            "industry": "live", "free_cash_flow": "live", "fcf_history": "live",
            "net_cash": "live", "total_debt": "live", "total_cash": "live",
        },
    }
    sector_metrics.apply_to_profile(profile)
    return profile


def test_the_fact_check_pairs_a_bank_fcf_figure_with_nothing(monkeypatch):
    live = _maybank_profile(switch=False, monkeypatch=monkeypatch)
    off_prose = "Maybank's FCF of -RM9,999M is a cash burn."
    assert [m.field_name for m in numeric_quotation.find_sheet_mismatches(off_prose, live)] == [
        "free_cash_flow"
    ], "non-vacuity: with the field on the sheet a wrong figure is paired and flagged"
    assert numeric_quotation.find_sheet_mismatches(MAYBANK_PROSE, live) == []

    bank = _maybank_profile(switch=True, monkeypatch=monkeypatch)
    assert "free_cash_flow" not in bank
    assert numeric_quotation.find_sheet_mismatches(off_prose, bank) == []
    assert numeric_quotation.find_sheet_mismatches(MAYBANK_PROSE, bank) == []
    assert numeric_quotation.millions_scaled_values(bank) == []


def test_the_risk_officer_cannot_corroborate_against_a_listed_value(monkeypatch):
    live = _maybank_profile(switch=False, monkeypatch=monkeypatch)
    assert risk_officer._quotation_check(MAYBANK_PROSE, live, []) is True, "non-vacuity"

    bank = _maybank_profile(switch=True, monkeypatch=monkeypatch)
    corpus = risk_officer._corroborating_values(bank, [])
    for value in (15433.0, -15433.0, 15433e6, -15433e6, 83211.0, 91234.0, 8023.0, 9000.0):
        assert value not in corpus
    assert risk_officer._quotation_check(MAYBANK_PROSE, bank, []) is False
    assert risk_officer._uncorroborated_numerals(MAYBANK_PROSE, bank, []) != []


# ── 5. switch off and non-banks: nothing changes ─────────────────────────────


def test_switch_off_a_bank_sheet_is_untouched_and_renders_as_before(monkeypatch):
    monkeypatch.setattr(settings, "room_sector_metrics_enabled", False)
    _enable_blocks(monkeypatch)
    sheet = _us_sheet()
    before = copy.deepcopy(sheet)
    assert sector_metrics.apply_to_profile(sheet) is None
    assert sheet == before and "sector_family" not in sheet
    assert _format_profile(sheet) == _format_profile(before)
    assert LINE not in _format_profile(sheet) and "$45,678M" in _format_profile(sheet)
    assert "not_applicable_family" not in build_terminal_inputs(sheet, 42)


def test_a_non_bank_with_the_switch_on_renders_the_pre_cr287_golden_byte_for_byte(sector_on, monkeypatch):
    """The whole US corpus (every desk's sheet, every Room prompt, the Risk Officer prompts)
    from the frozen pre-CR282 golden, after `apply_to_profile` with the switch ON."""
    G.install_seams(monkeypatch)
    G.pin_render_clock(monkeypatch)
    golden = G._load()
    sheet = decode_profile(golden["sheet"])
    assert sector_metrics.apply_to_profile(sheet) is None
    assert G.render_corpus(sheet) == golden["corpus"]


@pytest.mark.parametrize("industry", [
    "Insurance - Life", "REIT - Retail", "Utilities - Renewable", "Capital Markets",
    "Software - Application",
])
def test_other_families_are_out_of_scope_and_unchanged(sector_on, monkeypatch, industry):
    _enable_blocks(monkeypatch)
    sheet = _us_sheet(industry=industry)
    before = copy.deepcopy(sheet)
    assert sector_metrics.apply_to_profile(sheet) is None
    assert sheet == before
    assert _format_profile(sheet) == _format_profile(before)


def test_a_freshly_built_non_bank_sheet_is_identical_with_the_switch_on_or_off(monkeypatch):
    G.install_seams(monkeypatch)
    monkeypatch.setattr(settings, "room_sector_metrics_enabled", False)
    off = G._mask(room_runner._profile_for_ticker(G.TICKER))
    monkeypatch.setattr(settings, "room_sector_metrics_enabled", True)
    on = G._mask(room_runner._profile_for_ticker(G.TICKER))
    assert on == off


def test_the_us_bank_build_path_applies_the_table(sector_on, monkeypatch):
    G.install_seams(monkeypatch, ticker="BAC")
    bank = {**P._FUND_SENTINEL, "industry": "Banks - Diversified", "sector": "Financial Services"}
    monkeypatch.setattr(fundamentals, "fetch_live_fundamentals", lambda t: dict(bank))
    monkeypatch.setattr(room_runner, "fetch_live_fundamentals", lambda t: dict(bank))
    sheet = room_runner._profile_for_ticker("BAC")
    assert sheet["sector_family"] == "bank"
    assert "free_cash_flow" not in sheet and sheet["field_state"]["free_cash_flow"] == "not_applicable"
    assert "$45,678M" not in _format_profile(sheet)


# ── 6. the switch, the frozen-sheet variant ──────────────────────────────────


def test_the_sheet_variant_moves_only_when_the_switch_is_on(monkeypatch):
    kw = dict(news_state="live", social_state="live", market_withheld=False)
    monkeypatch.setattr(settings, "room_sector_metrics_enabled", False)
    off_us = room_bank.sheet_variant(**kw, ticker="BAC")
    off_my = room_bank.sheet_variant(**kw, ticker=KL)
    assert "sector" not in off_us and "sector" not in off_my
    assert off_my.endswith(f"|my_rev={room_bank.MY_SHEET_REVISION}")
    monkeypatch.setattr(settings, "room_sector_metrics_enabled", True)
    assert room_bank.sheet_variant(**kw, ticker="BAC") == off_us + "|sector=1"
    assert room_bank.sheet_variant(**kw, ticker=KL) == off_my + "|sector=1"


def test_the_switch_defaults_off_and_is_classified_not_keyed():
    from app.core.config import Settings

    assert Settings.model_fields["room_sector_metrics_enabled"].default is False
    assert "room_sector_metrics_enabled" in room_bank.ROOM_SETTINGS_NOT_KEYED
    assert "room_sector_metrics_enabled" not in room_bank.ROOM_POLICY_SETTINGS


def test_a_figure_that_stopped_applying_is_not_reported_as_a_change_since_the_last_convene():
    prior = {
        "date": "2026-11-20", "action": "PASS", "reference_price": 10.0,
        "sheet_state": {"free_cash_flow": "live", "pe": "live", "net_cash": "live"},
    }
    this = {
        "last_close": 10.0,
        "field_state": {
            "free_cash_flow": "not_applicable", "pe": "unavailable",
            "net_cash": "not_applicable", "technicals": "live",
        },
    }
    delta = room_runner._build_next_convene_delta(prior, this_profile=this)
    assert [(c.field, c.to_state) for c in delta.changed_fields] == [("pe", "unavailable")]


# ── 7. regulated utilities: a `context` row (nothing removed) ────────────────

UTILITY_LINE = (
    "Context: negative free cash flow from regulated capital spending, and high debt, "
    "are normal for a regulated utility; its returns are set on a regulated asset base."
)


@pytest.mark.parametrize("industry,expected", [
    ("Utilities - Regulated Electric", "regulated_utility"),
    ("Utilities - Regulated Gas", "regulated_utility"),
    ("Utilities - Regulated Water", "regulated_utility"),
    ("Utilities—Regulated Electric", "regulated_utility"),
    ("Utilities–Regulated Gas", "regulated_utility"),
    ("utilities  -  regulated water", "regulated_utility"),
    ("Utilities - Renewable", None),
    ("Utilities—Renewable", None),
    ("Utilities - Diversified", None),
    ("Utilities—Diversified", None),
    ("Utilities - Independent Power Producers", None),
    ("Utilities—Independent Power Producers", None),
    ("Utilities", None),
    ("Banks—Regional", "bank"),
])
def test_family_for_reads_both_dash_forms_and_only_the_three_regulated_tags(industry, expected):
    assert sector_metrics.family_for(industry, "Utilities") == expected


def test_the_two_kinds_are_explicit_and_cannot_be_confused():
    bank = sector_metrics.FAMILY_RULES["bank"]
    util = sector_metrics.FAMILY_RULES["regulated_utility"]
    assert (bank.kind, util.kind) == ("not_applicable", "context")
    assert bank.fields and not util.fields
    assert util.line == UTILITY_LINE
    assert util.check_reason == "not applicable: regulated utility"
    assert "not applicable for" not in util.line


def test_a_regulated_utility_keeps_every_figure_and_gains_one_context_line(sector_on, monkeypatch):
    _enable_blocks(monkeypatch)
    before = _us_sheet(industry="Utilities - Regulated Electric")
    sheet = copy.deepcopy(before)
    rule = sector_metrics.apply_to_profile(sheet)
    assert rule.kind == "context" and sheet["sector_family"] == "regulated_utility"
    assert sector_metrics.not_applicable(sheet) is None
    assert sector_metrics.context_line(sheet) == UTILITY_LINE
    assert not sector_metrics.is_not_applicable("free_cash_flow", sheet)
    without_marker = {k: v for k, v in sheet.items() if k != "sector_family"}
    assert without_marker == before, "a context row changes nothing in the profile but the marker"

    for agent in [None, *AgentId]:
        after_text = _format_profile(sheet, agent)
        before_text = _format_profile(before, agent)
        assert after_text.replace(UTILITY_LINE + "\n", "") == before_text, agent
    full = _format_profile(sheet)
    assert full.count(UTILITY_LINE) == 1
    for fp in US_FINGERPRINTS:
        assert fp in full, fp
    assert "not applicable for" not in full


def test_a_bursa_regulated_electric_sheet_keeps_its_figures_and_states_the_context(monkeypatch):
    monkeypatch.setattr(settings, "market_bursa_enabled", True)
    monkeypatch.setattr(settings, "room_sector_metrics_enabled", True)
    tenaga = {
        **MAYBANK, "industry": "Utilities—Regulated Electric", "sector": "Utilities",
        "free_cash_flow": -4321, "fcf_yield": -3.1,
    }
    G.install_seams(monkeypatch, ticker="5347.KL")
    monkeypatch.setattr(fundamentals, "fetch_live_fundamentals", lambda t: dict(tenaga))
    monkeypatch.setattr(room_runner, "fetch_live_fundamentals", lambda t: dict(tenaga))
    monkeypatch.setattr(edgar_filings_feed, "fetch_recent_filings", _boom)
    monkeypatch.setattr(edgar_pit, "load_facts", _boom)
    monkeypatch.setattr(put_call, "fetch_put_call_ratio", _boom)
    for name in (
        "_overlay_debt_structure", "_overlay_filing_dimensions", "_overlay_executive_change",
        "_overlay_capital_returns", "_overlay_recent_filings", "_overlay_sbc_and_roic",
        "_overlay_insider_forensics", "_overlay_edgar_8k_flags", "_overlay_put_call",
        "_overlay_peer_comparison",
    ):
        monkeypatch.setattr(room_runner, name, _boom)
    sheet = room_runner._profile_for_ticker("5347.KL")
    assert sheet["sector_family"] == "regulated_utility"
    text = _format_profile(sheet)
    assert text.count(UTILITY_LINE) == 1
    for kept in ("-RM4,321M", "-3.1", "RM91,234M", "EV/EBITDA"):
        assert kept in text, kept
    assert "not applicable for" not in text


def test_a_regulated_utility_debt_check_is_skipped_loudly_with_no_note(sector_on):
    sheet = _us_sheet(industry="Utilities - Regulated Electric")
    sector_metrics.apply_to_profile(sheet)
    inputs = _inputs(
        build_terminal_inputs(sheet, 42, mandate_horizon_months=24, min_coverage=1.0),
        months=24, minimum=1.0,
    )
    assert inputs["not_applicable_family"] == "regulated_utility"
    # the figures are still on the sheet's inputs; the check simply does not run
    assert inputs["total_cash"] is not None and inputs["fcf_ttm"] is not None
    out = M.apply_materiality(_yes(), inputs)
    check = out.detail["terminal_check"]
    assert check["skipped"] is True and check["reason"].endswith("not applicable: regulated utility")
    assert check["coverage"] is None and check["due_in_horizon"] is None
    assert "verdict_note" not in check
    verdict = Verdict(action=VerdictAction.PASS, reason="CIO says.")
    text, v = _append_debt_check_note("Room.", verdict, D553._result(inputs), "SO")
    assert text == "Room." and v.reason == "CIO says."


@pytest.mark.parametrize("industry", [
    "Utilities - Renewable", "Utilities—Renewable", "Utilities - Diversified",
    "Utilities - Independent Power Producers",
])
def test_other_utilities_are_unchanged_and_their_debt_check_still_runs(sector_on, monkeypatch, industry):
    _enable_blocks(monkeypatch)
    sheet = _us_sheet(industry=industry)
    before = copy.deepcopy(sheet)
    assert sector_metrics.apply_to_profile(sheet) is None
    assert sheet == before and _format_profile(sheet) == _format_profile(before)
    inputs = build_terminal_inputs(sheet, 42, mandate_horizon_months=24, min_coverage=1.0)
    assert "not_applicable_family" not in inputs
    ladder = {**inputs, "ladder": [["Within 1 year", 5000.0]], "total_cash": 100.0, "fcf_ttm": -50.0}
    check = M.debt_default_check(_inputs(ladder, months=24, minimum=1.0))
    assert not check.get("skipped") and check["due_in_horizon"] == 5000.0
    assert check["verdict_note"].startswith("AMI debt check")


def test_with_the_switch_off_a_regulated_utility_is_untouched(monkeypatch):
    monkeypatch.setattr(settings, "room_sector_metrics_enabled", False)
    sheet = _us_sheet(industry="Utilities - Regulated Electric")
    before = copy.deepcopy(sheet)
    assert sector_metrics.apply_to_profile(sheet) is None
    assert sheet == before and UTILITY_LINE not in _format_profile(sheet)
    assert "not_applicable_family" not in build_terminal_inputs(sheet, 42)


def test_the_fact_check_still_pairs_a_regulated_utilitys_fcf(sector_on):
    profile = {
        "industry": "Utilities - Regulated Electric", "free_cash_flow": -4321,
        "field_state": {"industry": "live", "free_cash_flow": "live"},
    }
    sector_metrics.apply_to_profile(profile)
    found = numeric_quotation.find_sheet_mismatches("The FCF of -RM9,999M is a burn.", profile)
    assert [m.field_name for m in found] == ["free_cash_flow"]


# ── 8. bank sheets do not list the dropped figures as missing data (CR287 follow-up) ─────────

_FILED_DETAIL_BEFORE = (
    "Filed-statement detail: not available for this market (Bursa Malaysia filings are not yet "
    "ingested) (debt maturity ladder, cost of debt, debt split, segment and geographic revenue, "
    "SBC-adjusted free cash flow, ROIC, buyback average price and dividend growth are read from "
    "SEC XBRL filings). Do not supply it from memory."
)


def _filed_detail(sheet) -> list[str]:
    return [
        ln for ln in _format_profile(sheet, AgentId.FUNDAMENTALS_ANALYST).splitlines()
        if ln.startswith("Filed-statement detail")
    ]


def test_a_bursa_bank_sheet_has_no_not_available_line_naming_a_dropped_figure(bursa_bank_sheet):
    for agent in [None, *AgentId]:
        text = _format_profile(bursa_bank_sheet, agent)
        for ln in text.splitlines():
            if ln == LINE or "not available" not in ln.lower():
                continue
            for dropped in ("SBC-adjusted", "debt maturity", "cost of debt", "debt split",
                            "interest coverage", "free cash flow", "net debt", "EV/EBITDA"):
                assert dropped.lower() not in ln.lower(), (agent, dropped, ln)
    full = _format_profile(bursa_bank_sheet)
    assert full.count(LINE) == 1
    assert "SBC-adjusted" not in full
    # what is still genuinely not read from Bursa stays named, in the same line
    (detail,) = _filed_detail(bursa_bank_sheet)
    assert "segment and geographic revenue, ROIC, buyback average price and dividend growth" in detail
    assert "not available for this market" in detail


def test_a_non_bank_bursa_sheet_keeps_its_filed_statement_line_unchanged(bursa_bank_sheet):
    sheet = dict(bursa_bank_sheet)
    sheet.pop("sector_family")
    sheet["industry"] = "Telecom Services"
    assert _filed_detail(sheet) == [_FILED_DETAIL_BEFORE]
    assert room_market.my_dark_lines(news=False, fundamentals=True, social=False) == (
        room_market.my_dark_lines(news=False, fundamentals=True, social=False, profile=sheet)
    )


def test_a_regulated_utility_bursa_sheet_keeps_its_filed_statement_line_unchanged():
    profile = {"sector_family": "regulated_utility", "market": "MY"}
    lines = room_market.my_dark_lines(
        news=False, fundamentals=True, social=False, profile=profile,
    )
    assert _FILED_DETAIL_BEFORE in lines


_BANK_GAPS = [
    "Operating cash flow vs net income", "Interest coverage ratio", "SBC-adjusted FCF",
    "Debt maturity ladder", "5-year historical P/E band", "Net interest margin trend",
]
_KEPT_GAPS = ["5-year historical P/E band", "Net interest margin trend"]


def test_a_bank_desks_data_gaps_drop_the_not_applicable_figures(bursa_bank_sheet):
    assert sector_metrics.drop_not_applicable_gaps(list(_BANK_GAPS), bursa_bank_sheet) == _KEPT_GAPS
    assert sector_metrics.drop_not_applicable_gaps([], bursa_bank_sheet) == []
    assert sector_metrics.drop_not_applicable_gaps(None, bursa_bank_sheet) is None


def test_non_bank_and_switch_off_data_gaps_are_returned_unchanged(bursa_bank_sheet):
    items = list(_BANK_GAPS)
    off = {k: v for k, v in bursa_bank_sheet.items() if k != "sector_family"}
    assert sector_metrics.drop_not_applicable_gaps(items, off) is items
    assert sector_metrics.drop_not_applicable_gaps(items, None) is items
    assert sector_metrics.drop_not_applicable_gaps(items, {"sector_family": "regulated_utility"}) is items
