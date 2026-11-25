"""DEF547 follow-up + DEF548 (device lab AMI-DL-33, 1155.KL Rooms of 2026-11-25).

DEF547's first fix removed the sign, "11.5x" and multi-year-average false corrections,
but the next 1155.KL Rooms still carried them, from other causes, each read off the
stored transcript against the stored sheet:

  1. a PERCENTAGE was paired with the FCF amount label: "FCF conversion currently
     -152%" (the sheet's `fcf_conversion_pct[0]`) was "corrected" to -RM15,433M; "6.11%
     yield despite negative FCF" and "0.0% insider ownership" the same;
  2. the digits of a period were read as a figure: "FY2024 FCF was +RM27,986M" was
     "corrected" on "2024", a "(1)" list marker on "1";
  3. the "forward" that disambiguates a P/E was cut in half by the numeral window, so a
     forward P/E's multiple (11.1x, and the 12.6x median beside it) was held to the
     trailing 11.5;
  4. the Risk Officer's `[AMI: unverifiable]` tag landed on "-RM15,433M" - the sheet's
     own TTM FCF - because its corroboration compared an unsigned claim in full units
     with raw signed millions.

DEF548: a desk turn printed "RM-14,077M". Desk text is model output, so the sign is
moved before the symbol structurally (`normalize_money_sign`), on every turn.

Every fix is paired with a case showing the control still fires on a genuinely wrong
figure.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path as _FsPath

import pytest

from app.schemas import AgentId
from app.services import room_runner
from app.services.numeric_quotation import find_sheet_mismatches
from app.services.risk_officer import _quotation_check
from app.services.room_market import normalize_money_sign

_THIS_DIR = _FsPath(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

# The 1155.KL sheet (the fields these checkers read), as stored by the 2026-11-25 Room.
_KL = {
    "market": "MY",
    "pe": "11.5",
    "forward_pe": "11.1",
    "fcf_yield": -12.6,
    "free_cash_flow": -15433,
    "free_cash_flow_ttm": -15433,
    "operating_cash_flow_ttm": -14077,
    "fcf_conversion_pct": [-152, 277, 9, 104],
    "fcf_history": [-16023, 27986, 873, 8257],
    "net_cash": -3728,
    "market_cap": 122891,
    "total_debt": 124174,
    "total_cash": 120446,
    "eps_revisions_pct": -6.6,
    "held_pct_insiders": 0.0,
    "dividend_yield": 6.11,
    "rev_growth": 2,
}


def _fields(text, profile=_KL):
    return [m.field_name for m in find_sheet_mismatches(text, profile)]


# ── 1. a percentage never pairs with an amount (and an amount never with a percent) ──


@pytest.mark.parametrize("text", [
    "FCF conversion was **-152%** in FY2025 vs a **277%** peak in FY2024",
    "A confirmed return to positive FCF conversion (currently -152%) in the next cycle",
    "the **6.11%** yield despite negative FCF",
    "the negative FCF and **0.0%** insider ownership cannot erase it",
    "free cash flow margin of 12%",
])
def test_a_ratio_beside_the_fcf_label_is_not_the_fcf(text):
    assert _fields(text) == []


@pytest.mark.parametrize("text", [
    "TTM FCF of -RM15,000M",
    "TTM FCF of RM15,433M",  # sign dropped, no "negative"
    "free cash flow of -$99,999M",
])
def test_a_wrong_fcf_amount_is_still_corrected(text):
    assert _fields(text) == ["free_cash_flow"]


def test_a_right_fcf_amount_beside_a_ratio_is_not_corrected():
    assert _fields("FCF conversion -152%, trailing FCF is -RM15,433M") == []


def test_a_wrong_fcf_yield_is_still_corrected_and_an_amount_never_binds_it():
    assert _fields("FCF yield of -8.0%") == ["fcf_yield"]
    assert _fields("FCF yield RM8,000M") == []


def test_unit_compat_covers_the_other_amount_and_percent_fields():
    assert _fields("market cap of 12%") == []
    assert _fields("revenue growth of RM5M") == []
    assert _fields("market cap RM1,000M") == ["market_cap"]
    assert _fields("revenue growth of 9%") == ["rev_growth"]


# ── 2. a period or a list marker is not a figure ──


@pytest.mark.parametrize("text", [
    "the **FY2024 FCF was +RM27,986M** against a similar business model",
    "FCF in 2024 was RM27,986M",
    "(1) FCF remains -RM15,433M TTM",
    "Q3 2026 FCF was strong",
])
def test_a_period_label_or_list_marker_is_not_a_sheet_claim(text):
    assert _fields(text) == []


def test_a_bare_fcf_figure_after_a_year_word_is_still_checked():
    assert _fields("FCF of RM5,273M") == ["free_cash_flow"]


# ── 3. the P/E disambiguator survives the numeral window ──


@pytest.mark.parametrize("text", [
    "Trading at **11.1x forward P/E** against a **12.6x** own-history median",
    "The **11.1x** forward P/E is below the **12.6x** historical median",
    "P/E 11.1x (forward) vs 12.6x (4-year median)",
])
def test_a_forward_pe_and_its_median_are_not_held_to_the_trailing_pe(text):
    assert _fields(text) == []


def test_a_wrong_trailing_or_forward_pe_is_still_corrected():
    assert _fields("The trailing P/E is 25.0x") == ["pe_trailing"]
    assert _fields("Trading at 30x forward P/E") == ["pe_forward"]
    assert "pe_trailing" in _fields("Trailing P/E is 45.0x, and forward P/E of 11.1x")


# ── 4. the Risk Officer's quotation check reads sign and units ──


@pytest.mark.parametrize("claim", [
    "-RM15,433M",
    "FCF -RM15,433M",
    "TTM FCF of -RM14,077M",
    "FCF yield -12.6%",
    "consensus EPS estimate down 6.6%",
    "RM124,174M",  # gross debt, millions
    "RM3,987M",
])
def test_the_risk_officer_corroborates_the_sheets_signed_and_millions_figures(claim):
    prof = dict(_KL, capital_return_ttm=3987)
    assert _quotation_check(claim, prof, []) is True


@pytest.mark.parametrize("claim", [
    "RM15,433M",  # the sheet's FCF is negative; a dropped sign is not a quotation
    "-RM15,000M",
    "RM99,999M",
    "6.6%",  # sign dropped, no direction word
])
def test_the_risk_officer_still_marks_a_figure_the_sheet_does_not_carry(claim):
    assert _quotation_check(claim, _KL, []) is False


def test_raw_dollar_profile_values_still_corroborate():
    """The pinned CR219 R59-F2 behaviour: a profile holding full-unit dollars."""
    assert _quotation_check("$1.2B", {"market_cap": 1_200_000_000.0}, []) is True


# ── DEF548: the sign goes before the symbol ──


@pytest.mark.parametrize("raw, fixed", [
    ("RM-14,077M", "-RM14,077M"),
    ("operating cash flow is **RM-14,077M** TTM", "operating cash flow is **-RM14,077M** TTM"),
    ("RM -1,234", "-RM1,234"),
    ("MYR-5.5M", "-MYR5.5M"),
    ("$-12.00", "-$12.00"),
    ("US$-5", "-US$5"),
    ("S$ -2.5M", "-S$2.5M"),
    ("£-3", "-£3"),
    ("RM−4M", "−RM4M"),
])
def test_money_sign_is_moved_before_the_symbol(raw, fixed):
    assert normalize_money_sign(raw) == fixed


@pytest.mark.parametrize("untouched", [
    "RM1-2",
    "a range of RM9.78–RM10.30",
    "$10-$20",
    "the 2025-09-30 close",
    "-RM15,433M and -$12.00",
    "XRM-5",
    "a bare $- placeholder",
    "AAPL-2 and KO-3",
    "",
])
def test_ranges_dates_tickers_and_already_correct_amounts_are_left_alone(untouched):
    assert normalize_money_sign(untouched) == untouched


def test_the_normaliser_is_idempotent():
    once = normalize_money_sign("RM-14,077M and $-12.00")
    assert normalize_money_sign(once) == once


def _turn(agent: AgentId, reply: str, profile: dict, ticker: str) -> str:
    import test_cr266_room_gate as R

    ctx, _, _ = R._ctx()
    ctx.ticker = ticker
    ctx.profile = profile
    text, *_ = asyncio.run(room_runner._compute_agent_text(
        agent_id=agent, ctx=ctx, profile=profile, formatter={}, transcript=[],
        gateway=R._GateGateway([reply]), live=True, agent_timeout_s=30.0,
    ))
    return text


@pytest.mark.parametrize("ticker, profile, wrong, right", [
    ("1155.KL", {"market": "MY", "field_state": {}}, "RM-14,077M", "-RM14,077M"),
    ("AAPL", {"field_state": {}}, "$-14,077M", "-$14,077M"),
])
def test_a_live_desk_turn_reaches_the_user_with_the_sign_first(ticker, profile, wrong, right):
    reply = (
        "[STANCE: against | CONVICTION: high | HEADLINE: cash is negative]\n"
        f"Operating cash flow is {wrong} TTM."
    )
    text = _turn(AgentId.BEAR_RESEARCHER, reply, profile, ticker)
    assert right in text and wrong not in text


def test_the_sign_is_normalised_before_the_fact_check_reads_it():
    """A wrong sign position must not be read as an unsigned figure and "corrected"."""
    profile = dict(_KL, field_state={})
    reply = (
        "[STANCE: against | CONVICTION: high | HEADLINE: cash is negative]\n"
        "TTM free cash flow is RM-15,433M."
    )
    text = _turn(AgentId.BEAR_RESEARCHER, reply, profile, "1155.KL")
    assert "-RM15,433M" in text and "AMI checked" not in text
