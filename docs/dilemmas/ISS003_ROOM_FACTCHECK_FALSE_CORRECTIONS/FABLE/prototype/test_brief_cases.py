"""ISS003 / FABLE — every false correction in the brief (DEF547 rounds 1-3), run
through the grounding prototype. Self-contained: no app imports, no database.

    python3 -m pytest docs/dilemmas/ISS003_ROOM_FACTCHECK_FALSE_CORRECTIONS/FABLE/prototype/test_brief_cases.py -q

The sheet lines below are a cut-down 1155.KL sheet carrying the values the brief
quotes. What is asserted is the user-visible outcome: which figures AMI would list
as "not on the fact sheet", and that no sentence ever states what a figure "should" be.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from grounding import Ledger, classify, own_figures, provenance_note  # noqa: E402

SHEET = """\
P/E: 11.5x trailing, 11.1x forward (consensus)
market cap RM120,655M, FCF -RM15,433M (TTM), FCF yield -12.6%
Free cash flow history: FY2025 -RM16,023M, FY2024 RM27,986M, FY2023 RM873M, FY2022 RM8,257M
FCF conversion: FY2025 -152% of net income
Dividend: yield 6.11%, payout 86%
Ownership: insiders 0.0%, institutions 31.2%
ATR(14): RM0.145 (average true range, simple 14-session average)
52-week range: RM9.78–RM12.42
"""
MANDATE = "Single-name cap: 1.0% of portfolio. Max drawdown 30%."


def ledger() -> Ledger:
    led = Ledger()
    led.add_text("sheet", SHEET)
    led.add_text("mandate", MANDATE)
    return led


def own(text: str) -> list[str]:
    return own_figures(text, ledger())


# ── Round 1 ──────────────────────────────────────────────────────────────────
def test_r1_signed_figures_are_figures_of_record():
    assert own("FCF yield is -12.6% and TTM FCF is -RM15,433M.") == []


def test_r1_multiples_are_not_truncated():
    assert own("The stock trades at 11.5x trailing earnings.") == []


def test_r1_average_of_history_is_the_desks_own_figure_and_is_not_corrected():
    text = "The 4-year average FCF of RM5,273M masks the TTM figure of -RM15,433M."
    assert own(text) == ["RM5,273M"]
    note = provenance_note(text, ledger())
    assert "RM5,273M" in note and "15,433" not in note  # never says what it "should" be


# ── Round 2 ──────────────────────────────────────────────────────────────────
def test_r2_ratio_next_to_an_amount_label():
    assert own("FCF conversion currently -152%, a 6.11% yield despite negative FCF, 0.0% insider ownership.") == []


def test_r2_periods_and_list_markers_are_not_figures():
    assert own("FY2024 FCF was +RM27,986M. (1) FCF remains negative.") == []


def test_r2_forward_pe():
    assert own("At 11.1x forward P/E the multiple is undemanding.") == []


# ── Round 3 ──────────────────────────────────────────────────────────────────
def test_r3_mandate_cap_is_a_figure_of_record():
    statuses = {p.fig.raw: p for p in classify("The mandate caps a single name at 1.0%.", ledger())}
    assert statuses["1.0%"].status == "record" and statuses["1.0%"].sources == ("mandate",)


def test_r3_multiple_of_atr():
    text = "The RM9.78 stop is exactly 1.0x ATR(14) (RM0.145) away."
    # RM9.78 and RM0.145 are on the sheet. "1.0x" is the desk's own multiplier:
    # listed as not on the sheet (true), never "corrected" to the ATR.
    assert own(text) == ["1.0x"]
    assert "0.145" not in provenance_note(text, ledger())


def test_r3_sign_in_words_after_the_number():
    assert own("TTM free cash flow is RM15,433M negative.") == []


# ── The protection: invented and altered figures ─────────────────────────────
def test_invented_figure_is_listed():
    assert own("Trailing P/E of 14.2x looks cheap against ROIC of 19.4%.") == ["14.2x", "19.4%"]


def test_altered_figure_is_listed():
    assert own("FCF yield is -21.6% on TTM FCF of -RM15,343M.") == ["-21.6%", "-RM15,343M"]


def test_rounding_and_truncation_are_not_alterations():
    assert own("FCF of -RM15.4B (TTM); market cap RM120.6B; RM120.7 billion; RM15.4bil.") == []


# ── Known misses, pinned so nobody mistakes them for coverage ────────────────
def test_MISS_dropped_sign_is_not_caught():
    assert own("FCF yield is 12.6%.") == []


def test_MISS_right_number_wrong_label_is_not_caught():
    assert own("Trailing P/E is 11.1x.") == []  # 11.1x is the FORWARD multiple


def test_MISS_altered_figure_that_lands_on_another_sheet_figure():
    assert own("Dividend payout is 31.2%.") == []  # 31.2% is institutional ownership


def test_no_sentence_ever_states_a_sheet_value():
    led = ledger()
    for text in (
        "P/E of 25x.", "FCF is RM5,273M.", "ATR is RM0.2.", "Yield 7%.", "Market cap RM99B.",
    ):
        note = provenance_note(text, led) or ""
        for value in ("11.5", "11.1", "15,433", "0.145", "6.11", "120,655"):
            assert value not in note
