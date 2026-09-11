"""CR221 slot 5 — C8 dividend growth and C7 implied buyback price.

Every structural rule here was derived from a case measured on the live feeds
on 2026-09-11, and each has a test named after the case that produced it. The
figures below are those measurements, not fixtures invented to pass:

  - CAT dividends: 2021-2025 declared rate 1.11 / 1.20 / 1.30 / 1.41 / 1.51,
    8.00% CAGR, four payments a year.
  - COST: the same shape plus a $15.00 special on 2023-12-27 (and $10.00 on
    2020-12-01) that must not enter either basis.
  - O (Realty Income): monthly, and the 2024 May ex-date slipped to 2024-06-03,
    so 2024 holds 11 payments and 2025 holds 13. Calendar-year SUMS therefore
    fall 3.062 -> 2.872 then jump to 3.490 — a phantom cut and surge in a
    series whose declared rate rose every month. Sum basis 5.90% CAGR against
    the rate basis's true 2.25%.
  - DIS: paid nothing at all in 2020, 2021 and 2022.
  - CAT buybacks: the dollar tag and the share tag share 25 discrete quarters,
    but the newest four they BOTH carry are Q1 of 2023, 2024, 2025 and 2026 —
    the same calendar quarter four years running, which sums to a $518.82
    "trailing-twelve-month" price spanning three and a quarter years. The true
    contiguous window is 2025-07-01..2026-06-30: $7,224M over 10,869,082
    shares = $664.64, which sits inside CAT's own $386.02-$1,062.93 close
    range for that year (mean $632.74).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest

from app.core.config import settings
from app.schemas.agents import AgentId
from app.services import room_prompts
from app.services.buyback_price import MAX_PRICE, MIN_SHARES, resolve_buyback_price
from app.services.dividend_growth import MIN_YEARS, resolve_dividend_growth
from app.services.fundamentals import buyback_price_line, dividend_growth_line
from app.services.market_data import DividendPayment

_TODAY = date(2026, 9, 11)


@pytest.fixture(autouse=True)
def _flags_restored():
    before = (settings.room_dividend_growth_enabled, settings.room_buyback_price_enabled)
    yield
    (settings.room_dividend_growth_enabled,
     settings.room_buyback_price_enabled) = before


def _pays(spec: dict[int, list[tuple[str, float]]]) -> list[DividendPayment]:
    out = []
    for year, items in sorted(spec.items()):
        for when, amount in items:
            month, day = (int(x) for x in when.split("-"))
            out.append(DividendPayment(
                ex_date=date(year, month, day), amount_per_share=amount, source="test"))
    return sorted(out, key=lambda p: p.ex_date)


def _quarterly(year_rates: dict[int, list[float]], month_days=(("02-15"), ("05-15"), ("08-15"), ("11-15"))):
    return _pays({y: [(m, r) for m, r in zip(month_days, rates)] for y, rates in year_rates.items()})


_CAT = _quarterly({
    2021: [1.03, 1.03, 1.11, 1.11], 2022: [1.11, 1.11, 1.20, 1.20],
    2023: [1.20, 1.20, 1.30, 1.30], 2024: [1.30, 1.30, 1.41, 1.41],
    2025: [1.41, 1.41, 1.51, 1.51], 2026: [1.51, 1.51, 1.63],
})


# ── C8: the basis, and why it is not the calendar-year sum ───────────────────


def test_cats_measured_series_reproduces_its_measured_cagr() -> None:
    g = resolve_dividend_growth(_CAT, _TODAY)
    assert g is not None
    assert (g.first_year, g.last_year) == (2021, 2025)
    assert [round(r, 4) for _, r in g.rate_by_year] == [1.11, 1.20, 1.30, 1.41, 1.51]
    assert round(g.cagr_pct, 2) == 8.00
    assert (g.raised_years, g.comparisons) == (4, 4)
    assert g.partial_year == 2026 and not g.truncated_by_gap
    assert {n for _, n in g.payments_per_year} == {4}


def test_a_slipped_ex_date_does_not_print_a_cut_the_company_never_made() -> None:
    """Realty Income 2024/2025, the case the rate basis exists for.

    Eleven payments in 2024 and thirteen in 2025 because one ex-date crossed a
    year boundary. The declared rate rises monotonically; the calendar sums do
    not. If this test fails, the sheet is about to tell an analyst that a
    monthly payer cut its dividend when it did not.
    """
    o = _pays({
        2021: [(f"{m:02d}-01", 0.2470) for m in range(1, 13)],
        2022: [(f"{m:02d}-01", 0.2490) for m in range(1, 13)],
        2023: [(f"{m:02d}-01", 0.2570) for m in range(1, 13)],
        # 2024: May slips to June 3 — eleven ex-dates land in the year.
        2024: [(f"{m:02d}-01", 0.2640) for m in (1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12)],
        2025: [(f"{m:02d}-01", 0.2700) for m in range(1, 13)] + [("12-31", 0.2700)],
        2026: [(f"{m:02d}-01", 0.2710) for m in range(1, 9)],
    })
    g = resolve_dividend_growth(o, _TODAY)
    assert g is not None
    rates = [r for _, r in g.rate_by_year]
    assert rates == sorted(rates), "the declared rate never fell; the series must not say it did"
    assert g.raised_years == g.comparisons

    totals = dict(g.total_by_year)
    assert totals[2024] < totals[2023], "the SUM basis does fall here — that is the whole point"
    sum_cagr = ((totals[2025] / totals[2021]) ** (1 / 4) - 1) * 100
    assert sum_cagr - g.cagr_pct > 2.0, (
        "the two bases must diverge materially on this series, or the test is "
        f"not reproducing the measured case (rate {g.cagr_pct:.2f}% vs sum {sum_cagr:.2f}%)")
    # The uneven cadence is disclosed rather than smoothed away.
    assert dict(g.payments_per_year)[2024] == 11
    line = dividend_growth_line(g)
    assert "payments per year" in line and "2024 11" in line


def test_a_special_dividend_is_excluded_from_both_bases_and_named() -> None:
    """Costco's $15.00 of 2023-12-27. A naive calendar sum reads 18.96 for
    2023 and prints a 79% collapse in 2024."""
    cost = _quarterly({
        2021: [0.70, 0.79, 0.79, 0.79], 2022: [0.79, 0.90, 0.90, 0.90],
        2023: [0.90, 1.02, 1.02, 1.02], 2024: [1.02, 1.16, 1.16, 1.16],
        2025: [1.16, 1.30, 1.30, 1.30], 2026: [1.30, 1.47, 1.47],
    })
    cost = sorted(cost + _pays({2023: [("12-27", 15.00)]}), key=lambda p: p.ex_date)
    g = resolve_dividend_growth(cost, _TODAY)
    assert g is not None
    assert dict(g.total_by_year)[2023] == pytest.approx(3.96)
    assert [r for _, r in g.rate_by_year] == [0.79, 0.90, 1.02, 1.16, 1.30]
    assert round(g.cagr_pct, 2) == 13.26
    assert g.specials == ((date(2023, 12, 27), 15.00),)
    assert dict(g.payments_per_year)[2023] == 4
    assert "special dividend excluded" in dividend_growth_line(g)


def test_a_rate_renders_in_cents_and_a_sub_cent_rate_keeps_its_digits() -> None:
    """A dividend rate is read as money, so it must render as money.

    `:,.4g` drops trailing zeros: the $1.20 declared rate printed as "$1.2" and
    the $5.00 annual total as "$5", which on a dividend series reads as a
    different figure. Plain two decimals is wrong the other way — GE's rate was
    $0.0498 and rounds away to $0.05, losing the precision the raise is measured
    on. Both shapes are pinned here because no other test looks at the digits.
    """
    line = dividend_growth_line(resolve_dividend_growth(_CAT, _TODAY))
    assert "2022 $1.20" in line and "2023 $1.30" in line
    assert "2023 $5.00" in line, "the annual total must not render as $5"
    assert "$1.2 " not in line and "$5 " not in line

    ge = _quarterly({
        2021: [0.0498] * 4, 2022: [0.0498] * 4, 2023: [0.0638] * 4,
        2024: [0.28] * 4, 2025: [0.36] * 4, 2026: [0.47, 0.47],
    })
    small = dividend_growth_line(resolve_dividend_growth(ge, _TODAY))
    assert "$0.0498" in small and "$0.0638" in small, "a sub-dime rate keeps four decimals"
    assert "2024 $0.28" in small, "and an ordinary one still renders in cents"


def test_a_real_trebling_is_a_raise_not_a_special() -> None:
    """The special filter must not eat a genuine step-up. GE's rate went
    0.0638 -> 0.28 in 2024 (4.4x) and that is a raise."""
    ge = _quarterly({
        2021: [0.0498] * 4, 2022: [0.0498] * 4, 2023: [0.0638] * 4,
        2024: [0.28] * 4, 2025: [0.36] * 4, 2026: [0.47, 0.47],
    })
    g = resolve_dividend_growth(ge, _TODAY)
    assert g is not None and g.specials == ()
    assert [r for _, r in g.rate_by_year] == [0.0498, 0.0498, 0.0638, 0.28, 0.36]


# ── C8: the window ───────────────────────────────────────────────────────────


def test_a_suspension_truncates_the_window_and_says_so() -> None:
    """Disney paid nothing in 2020-2022. A five-year window would bridge the
    suspension and call the recovery steady growth."""
    dis = _pays({
        2018: [("01-11", 0.84), ("07-06", 0.88)],
        2019: [("01-10", 0.88), ("07-08", 0.88)],
        2023: [("12-11", 0.30)],
        2024: [("07-08", 0.45), ("12-12", 0.50)],
        2025: [("07-08", 0.50), ("12-11", 0.75)],
        2026: [("07-08", 0.75)],
    })
    g = resolve_dividend_growth(dis, _TODAY)
    assert g is not None
    assert (g.first_year, g.last_year) == (2023, 2025)
    assert g.truncated_by_gap is True
    line = dividend_growth_line(g)
    assert "paid" in line and "no dividend in the year before it" in line
    assert "not a five-year series" in line


def test_the_partial_current_year_is_never_in_the_series() -> None:
    g = resolve_dividend_growth(_CAT, _TODAY)
    assert g is not None
    assert 2026 not in dict(g.rate_by_year)
    assert g.partial_year == 2026
    assert "2026 excluded as a partial year" in dividend_growth_line(g)


def test_too_short_a_history_is_absent_not_a_growth_rate() -> None:
    short = _quarterly({2024: [0.10] * 4, 2025: [0.12] * 4, 2026: [0.13] * 2})
    assert resolve_dividend_growth(short, _TODAY) is None
    assert MIN_YEARS == 3


@pytest.mark.parametrize("payments", [None, []])
def test_no_feed_and_never_paid_are_both_absent(payments) -> None:
    assert resolve_dividend_growth(payments, _TODAY) is None
    assert dividend_growth_line(None) is None


# ── C7: the two legs, and the window they must share ─────────────────────────


@dataclass(frozen=True)
class _Fact:
    tag: str
    value: float
    period_start: date | None
    period_end: date
    filed: date


def _q(tag: str, start: str, end: str, value: float) -> _Fact:
    s, e = date.fromisoformat(start), date.fromisoformat(end)
    return _Fact(tag=tag, value=value, period_start=s, period_end=e, filed=e)


_CAT_TTM = [
    ("2025-07-01", "2025-09-30", 1_560_000_000, 2_411_000),
    ("2025-10-01", "2025-12-31", 1_712_000_000, 2_460_000),
    ("2026-01-01", "2026-03-31", 2_500_000_000, 3_400_000),
    ("2026-04-01", "2026-06-30", 1_452_000_000, 2_598_082),
]


def _facts(rows, *, dollars=True, shares=True) -> list[_Fact]:
    out = []
    for start, end, usd, sh in rows:
        if dollars:
            out.append(_q("PaymentsForRepurchaseOfCommonStock", start, end, usd))
        if shares:
            out.append(_q("TreasuryStockSharesAcquired", start, end, sh))
    return out


def test_four_consecutive_paired_quarters_give_the_implied_price() -> None:
    r = resolve_buyback_price(_facts(_CAT_TTM), _TODAY)
    assert r is not None
    assert r.dollars == 7_224_000_000 and r.shares == 10_869_082
    assert round(r.avg_price, 2) == 664.64
    assert (r.period_start, r.period_end) == (date(2025, 7, 1), date(2026, 6, 30))
    assert r.quarters == 4


def test_the_same_quarter_four_years_running_is_refused() -> None:
    """The measured CAT failure: both tags carry Q1 of 2023, 2024, 2025 and
    2026, and nothing else in common. Summing them labels a 3.25-year total
    trailing-twelve-month and reads $518.82 — `ttm()`'s documented hazard
    arriving through a second series."""
    rows = [
        ("2023-01-01", "2023-03-31", 400_000_000, 1_701_760),
        ("2024-01-01", "2024-03-31", 4_455_000_000, 11_328_487),
        ("2025-01-01", "2025-03-31", 3_660_000_000, 7_515_281),
        ("2026-01-01", "2026-03-31", 5_028_000_000, 5_557_798),
    ]
    assert resolve_buyback_price(_facts(rows), _TODAY) is None


def test_an_unpaired_leg_is_absent_rather_than_divided_by_too_few_shares() -> None:
    """Deere tags no share count at all; a filer that tags one leg for only
    some quarters must not have its dollars divided by a short share total —
    that overstates the price paid, the reassuring direction (DEF399)."""
    facts = _facts(_CAT_TTM)
    facts = [f for f in facts
             if not (f.tag == "TreasuryStockSharesAcquired"
                     and f.period_end == date(2026, 6, 30))]
    assert resolve_buyback_price(facts, _TODAY) is None
    assert resolve_buyback_price(_facts(_CAT_TTM, shares=False), _TODAY) is None
    assert resolve_buyback_price([], _TODAY) is None


def test_a_residual_share_count_is_not_an_average_price() -> None:
    rows = [(s, e, usd, 10.0) for s, e, usd, _ in _CAT_TTM]
    assert resolve_buyback_price(_facts(rows), _TODAY) is None
    assert MIN_SHARES == 1_000.0


def test_the_share_floor_refuses_a_residual_the_price_ceiling_would_wave_through() -> None:
    """The floor must be the check that fires, not MAX_PRICE standing in for it.

    A plan true-up of 999 shares against $1.5M of dollars quotients to $1,501
    per share — a perfectly plausible-looking price, well under the ceiling and
    inside the range of real US listings. Only the share floor rejects it. If
    this passes with `shares < MIN_SHARES` weakened to `shares <= 0`, the sheet
    prints a four-figure average price off a rounding residual.
    """
    rows = [(start, end, 375_000.0, 249.75) for start, end, _, _ in _CAT_TTM]
    assert sum(row[2] for row in rows) / sum(row[3] for row in rows) < MAX_PRICE
    assert resolve_buyback_price(_facts(rows), _TODAY) is None
    # One share more per quarter than the floor allows, and the same shape resolves.
    ok = [(start, end, 375_000.0, 250.25) for start, end, _, _ in _CAT_TTM]
    resolved = resolve_buyback_price(_facts(ok), _TODAY)
    assert resolved is not None and resolved.shares == 1_001.0


def test_a_gap_in_the_middle_is_refused_by_contiguity_alone() -> None:
    """The contiguity guard, isolated from the span guard.

    A whole missing quarter would push the outer span past 400 days, so the span
    guard would catch that case too and it would prove nothing about contiguity.
    The hole here is a month instead: the four periods run Aug-Oct 2025, Dec 2025
    to Feb 2026, Mar-May 2026 and Jun-Aug 2026, spanning 395 days, which the span
    guard accepts. Only contiguity refuses them. This is the shape `ttm()`
    documents as its hazard and the shape CAT presented on 2026-09-11.
    """
    rows = [
        ("2025-08-01", "2025-10-31", 1_560_000_000, 2_411_000),
        ("2025-12-01", "2026-02-28", 1_712_000_000, 2_460_000),
        ("2026-03-01", "2026-05-31", 2_500_000_000, 3_400_000),
        ("2026-06-01", "2026-08-31", 1_452_000_000, 2_598_082),
    ]
    span = (date(2026, 8, 31) - date(2025, 8, 1)).days
    assert 330 <= span <= 400, (
        f"the span guard must ACCEPT this window ({span}d) or the test is not isolating contiguity")
    assert resolve_buyback_price(_facts(rows), date(2026, 11, 1)) is None


def test_four_contiguous_quarters_that_are_not_a_year_are_refused_by_span_alone() -> None:
    """The span guard, isolated from the contiguity guard.

    The first draft of this test used half-year periods, and it passed for the
    wrong reason: `edgar_pit.quarterly_series` keeps only spans of 70 to 100
    days, so half-years never reach this resolver at all and the series came
    back empty. Mutating the span check away left that test green.

    Reachable instead: four periods of 71 days each, abutting exactly. Every one
    survives the upstream quarter filter and contiguity is satisfied, but together
    they span 287 days. Only the span check refuses to label that total
    trailing-twelve-month. The window the filter admits runs from about 256 to
    418 days, so both ends of the year check are reachable and neither is
    decoration.
    """
    rows = [
        ("2025-10-01", "2025-12-11", 1_560_000_000, 2_411_000),
        ("2025-12-12", "2026-02-21", 1_712_000_000, 2_460_000),
        ("2026-02-22", "2026-05-04", 2_500_000_000, 3_400_000),
        ("2026-05-05", "2026-07-15", 1_452_000_000, 2_598_082),
    ]
    for start, end, _, _ in rows:
        length = (date.fromisoformat(end) - date.fromisoformat(start)).days
        assert 70 <= length <= 100, (
            f"a {length}d period is dropped upstream, so this test would never reach the span guard")
    for earlier, later in zip(rows, rows[1:]):
        gap = (date.fromisoformat(later[0]) - date.fromisoformat(earlier[1])).days
        assert abs(gap) <= 7, "the contiguity guard must ACCEPT this window or the test is not isolating span"
    span = (date.fromisoformat(rows[-1][1]) - date.fromisoformat(rows[0][0])).days
    assert span < 330, f"the span guard must be the check that fires ({span}d)"
    assert resolve_buyback_price(_facts(rows), _TODAY) is None


def test_three_paired_quarters_are_too_few_to_be_a_trailing_year() -> None:
    """Three paired quarters are absent, and the span guard is why.

    The `len(paired) < 4` check cannot be isolated, and the arithmetic says so
    rather than the test working around it: upstream keeps only periods of 70 to
    100 days, so three contiguous ones span at most 314 days, and the span guard
    requires at least 330. Every three-quarter window the resolver can ever see
    is already refused by span. Relaxing the count to three therefore changes no
    outcome — it is a redundant check, kept because it names the condition in the
    log the span message would not, and mutation-proofing it is impossible by
    construction, not by omission.

    What this test pins is the OUTCOME: three quarters never produce a price.
    """
    rows = [
        ("2025-07-01", "2025-09-30", 1_560_000_000, 2_411_000),
        ("2025-10-01", "2025-12-31", 1_712_000_000, 2_460_000),
        ("2026-01-01", "2026-03-31", 2_500_000_000, 3_400_000),
    ]
    span = (date(2026, 3, 31) - date(2025, 7, 1)).days
    assert 3 * 100 + 2 * 7 < 330, (
        "three periods that pass the 70-100d upstream filter cannot span a year; if this "
        "ever becomes false, the four-quarter minimum becomes reachable and needs its own case")
    assert span == 273
    assert resolve_buyback_price(_facts(rows), _TODAY) is None


def test_a_restated_quarter_with_a_different_start_is_not_paired_across() -> None:
    """Pairing is on BOTH period ends, not the closing date alone.

    A filer can carry two facts ending the same day over different starts — a
    discrete quarter and a differenced one from a restatement chain. Matching on
    `period_end` alone pairs a quarter's dollars with another window's share
    count. Here the share leg's third period ends 2026-03-31 like the dollar
    leg's, but starts two weeks later.

    The shifted period is 75 days, deliberately: the first draft shifted it to
    2026-02-01, which is 58 days, and the upstream 70-to-100-day filter dropped
    the row entirely — the unpaired-legs check fired and the pairing key was
    never exercised. At 75 days the row survives upstream and reaches the
    pairing, so only the two-part key refuses it.
    """
    dollars = [_q("PaymentsForRepurchaseOfCommonStock", start, end, usd)
               for start, end, usd, _ in _CAT_TTM]
    shares = []
    for start, end, _, sh in _CAT_TTM:
        if end == "2026-03-31":
            start = "2026-01-15"
            assert 70 <= (date.fromisoformat(end) - date.fromisoformat(start)).days <= 100
        shares.append(_q("TreasuryStockSharesAcquired", start, end, sh))
    assert resolve_buyback_price(dollars + shares, _TODAY) is None


def test_a_future_quarter_is_not_read_before_its_time() -> None:
    assert resolve_buyback_price(_facts(_CAT_TTM), date(2026, 3, 1)) is None


# ── The render seam ──────────────────────────────────────────────────────────


def _profile() -> tuple[dict, dict]:
    profile = {
        "ticker": "CAT",
        "dividend_growth": resolve_dividend_growth(_CAT, _TODAY),
        "buyback_price": resolve_buyback_price(_facts(_CAT_TTM), _TODAY),
    }
    profile["field_state"] = {"dividend_growth": "live", "buyback_price": "live"}
    return profile, profile["field_state"]


def test_both_flags_are_off_by_default_and_the_same_profile_renders_nothing() -> None:
    assert settings.room_dividend_growth_enabled is False
    assert settings.room_buyback_price_enabled is False
    profile, _ = _profile()
    sheet = room_prompts._format_profile(profile, AgentId.FUNDAMENTALS_ANALYST)
    assert "Dividend growth" not in sheet and "Buyback average price" not in sheet

    settings.room_dividend_growth_enabled = True
    settings.room_buyback_price_enabled = True
    sheet = room_prompts._format_profile(profile, AgentId.FUNDAMENTALS_ANALYST)
    assert "Dividend growth (declared rate, by year) (LIVE)" in sheet
    assert "Buyback average price (implied) (LIVE)" in sheet
    assert "$664.64 per share" in sheet and "+8.0% CAGR" in sheet


def test_presence_in_the_profile_is_not_provenance() -> None:
    """A resolved figure with a non-live field state renders nothing: the
    state key is the gate, not the key's presence."""
    settings.room_dividend_growth_enabled = True
    settings.room_buyback_price_enabled = True
    profile, state = _profile()
    state["dividend_growth"] = "unavailable"
    state["buyback_price"] = "unavailable"
    sheet = room_prompts._format_profile(profile, AgentId.FUNDAMENTALS_ANALYST)
    assert "Dividend growth" not in sheet and "Buyback average price" not in sheet


def test_the_buyback_line_never_claims_to_be_the_companys_own_figure() -> None:
    r = resolve_buyback_price(_facts(_CAT_TTM), _TODAY)
    line = buyback_price_line(r)
    assert "AMI's own quotient of two filed figures" in line
    assert "not a company-reported average price" in line
    assert "as filed" in line and "2025-07-01 to 2026-06-30" in line


def test_the_growth_line_states_which_basis_it_used() -> None:
    line = dividend_growth_line(resolve_dividend_growth(_CAT, _TODAY))
    assert "declared rate" in line and "cash paid per share by year" in line
    assert "AMI's own reading of the payments' ex-dates" in line
