"""DEF547 — the sheet-figure fact-check must not "correct" a figure the desk got right.

On a 1155.KL Room (device lab AMI-DL-32) AMI told the reader, under the Fundamentals
Analyst's own correct text: "the sheet's own figure is -12.6, not 12.6%", "... is
-RM15,433M, not 5,273M" and "... is 11.5, not 11". Three separate causes:

  1. the numeral regex carried no sign, so "-12.6%" and "-RM15,433M" were read as
     positive and then "corrected" to the sheet's own negative figure;
  2. "11.5x" backtracked to the integer "11" (the "x" blocked the fraction);
  3. "4-year average FCF of RM5,273M" (the mean of the sheet's own fcf_history) was
     paired with the TTM FCF, a different statistic.

The check is a control against fabricated figures, so every fix is paired with a test
that a genuinely wrong figure is still corrected. The cases are not Bursa-specific:
the US checker had the same three faults.
"""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.services.numeric_quotation import annotate_sheet_mismatches, find_sheet_mismatches

_KL = {
    "market": "MY",
    "pe": "11.5",
    "forward_pe": "11.0",
    "fcf_yield": -12.6,
    "free_cash_flow": -15433,
    "fcf_history": [-16023, 27986, 873, 8257],
    "historical_pe_median": 12.6,
    "rsi": 45,
    "rev_growth": -2,
}

_DESK_TEXT = (
    "a **negative FCF yield of -12.6%**; this contrasts sharply with the multi-year "
    "average FCF of **RM5,273M**, making the current period an outlier. The trailing "
    "P/E of **11.5x** sits below the 4-year median of **12.6x**. TTM free cash flow at "
    "**-RM15,433M**."
)


def _fields(text, profile=_KL):
    return [m.field_name for m in find_sheet_mismatches(text, profile)]


def test_the_real_room_text_draws_no_correction():
    assert find_sheet_mismatches(_DESK_TEXT, _KL) == []
    assert annotate_sheet_mismatches(_DESK_TEXT, _KL) == _DESK_TEXT


@pytest.mark.parametrize("text", [
    "FCF yield of -12.6%",
    "a negative FCF yield of 12.6%",
    "FCF yield (-12.6%)",
    "FCF at -RM15,433M",
    "free cash flow of -$15,433M",
    "TTM free cash flow of negative RM15,433M",
])
def test_a_negative_figure_quoted_with_its_sign_is_not_corrected(text):
    assert _fields(text) == []


@pytest.mark.parametrize("text, field", [
    ("FCF yield of -8.0%", "fcf_yield"),
    ("FCF yield of 12.6%", "fcf_yield"),
    ("FCF at -RM9,000M", "free_cash_flow"),
    ("FCF of RM15,433M", "free_cash_flow"),
    ("revenue growth of 2%", "rev_growth"),
])
def test_a_wrong_figure_or_a_dropped_sign_is_still_corrected(text, field):
    assert _fields(text) == [field]


def test_the_correction_quotes_the_sign_the_desk_wrote(monkeypatch):
    monkeypatch.setattr(settings, "room_factcheck_notes", "annotate")
    note = annotate_sheet_mismatches("FCF at -RM9,000M", _KL)
    assert "“-9,000M”" in note and "-RM15,433M" in note


def test_the_word_negative_never_manufactures_a_mismatch():
    assert _fields("a negative read on the RSI of 45") == []
    assert _fields("a negative read on the RSI of 61") == ["rsi"]


def test_a_hyphen_in_a_range_or_date_is_not_a_minus_sign():
    assert _fields("RSI 45-50 range") == []
    assert _fields("RSI of 45 as of 2025-09-30") == []
    assert _fields("revenue growth of 2%-3%") == ["rev_growth"]


@pytest.mark.parametrize("text", [
    "the trailing P/E of 11.5x",
    "forward P/E of 11.0x",
    "forward P/E of 11x",
    "P/E is 11.5×",
])
def test_a_multiple_with_an_x_is_read_whole(text):
    assert _fields(text) == []


def test_a_wrong_multiple_with_an_x_is_still_corrected():
    assert _fields("the trailing P/E of 14.2x") == ["pe_trailing"]


def test_a_decimal_followed_by_a_unit_word_is_not_truncated_into_an_integer():
    assert _fields("RSI of 45.6pp") == []


@pytest.mark.parametrize("text", [
    "the 4-year average FCF of RM5,273M",
    "multi-year average FCF of RM5,273M",
    "median FCF of RM5,273M",
    "FCF averaged RM5,273M over the period",
    "historical free cash flow of RM5,273M",
])
def test_a_statistic_of_the_history_is_not_paired_with_the_ttm_scalar(text):
    assert _fields(text) == []


def test_the_same_figure_without_a_qualifier_is_still_corrected():
    assert _fields("TTM FCF of RM5,273M") == ["free_cash_flow"]
    assert _fields("FCF of RM5,273M") == ["free_cash_flow"]


def test_a_qualifier_in_another_clause_does_not_unbind_the_label():
    assert _fields("The average analyst is cautious, but FCF of RM5,273M") == ["free_cash_flow"]
    assert _fields("4-year median P/E 12.6x vs trailing P/E of 14.2x") == ["pe_trailing"]


def test_a_label_in_the_next_sentence_does_not_bind_to_the_previous_sentences_figure():
    assert _fields("The 4-year median of 12.6x. TTM free cash flow at -RM15,433M.") == []
    assert _fields("The 4-year median of 12.6x. TTM free cash flow at -RM9,000M.") == [
        "free_cash_flow"
    ]


def test_a_us_sheet_gets_the_same_treatment():
    us = {"pe": "24.6", "free_cash_flow": -3200, "rev_growth": 8}
    assert find_sheet_mismatches("trailing P/E of 24.6x and FCF at -$3,200M", us) == []
    assert _fields("trailing P/E of 31.0x", us) == ["pe_trailing"]
