"""DEF399 — interest coverage is withdrawn when its numerator is a stub.

`fundamentals.py` divides EBIT by yfinance's `Interest Expense` row. For most
filers that IS consolidated interest expense. For an issuer whose captive
finance arm books its interest inside cost of revenue it is the LEFTOVER
non-operating line, and the shipped ratio overstates coverage 5-6x — always in
the reassuring direction. Caterpillar's FY2025 10-K carries $1,359M of
Financial Products interest plus $502M excluding it, $1,861M consolidated,
against four yfinance quarters summing to $529M: the sheet read 31.8x where
operating profit over real interest is ~6x. CAT is the ticker the entire CR219
corpus runs on, and the field was added BECAUSE of a solvency argument about
it.

These tests pin the three properties of the gate.

**It withdraws, it does not correct.** A3's EDGAR numerator is annual and the
coverage ratio is one quarter's EBIT; rebuilding the quarterly ratio from an
annual figure assumes an even spread, which is an assumption wearing a
measurement's clothes. The honest output is the declared absence the sheet
already renders for a filer that breaks out no interest line.

**It is silent without evidence.** No EDGAR interest figure is not evidence the
row is wrong, and withdrawing on absence would blank the field for every filer
whose facts have not been ingested.

**A filer that reads correctly keeps its figure.** 7 of the 10-name
captive-finance cohort corroborate, and across a 25-name spread of the CR035
universe only 1 of 21 comparable names was materially understated. The gate is
cohort-specific by construction, not a blanket distrust of the vendor row.

Fixture values are live measured facts (CAT's FY2025 10-K `R3.htm` and GM/DE
companyfacts, read 2026-09-03), in millions of USD.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.services import room_runner
from app.services.interest_cost import InterestCost
from app.services.room_runner import LiveDataState, _gate_interest_coverage

_PERIOD_END = date(2025, 12, 31)


def _cost(annual_interest_millions: float) -> InterestCost:
    """An A3 result carrying `annual_interest` in dollars, as the real one does."""
    return InterestCost(
        annual_interest=annual_interest_millions * 1_000_000,
        basis="cash interest paid, fiscal year",
        period_end=_PERIOD_END,
        gross_debt=36_210 * 1_000_000,
        cost_of_debt_pct=5.1,
    )


def _profile(ratio: float | None, quarterly_interest: float | None) -> dict:
    out: dict = {}
    if ratio is not None:
        out["interest_coverage"] = ratio
        out["interest_coverage_quarter"] = "2025-12-31"
    if quarterly_interest is not None:
        out["interest_expense_quarter_usd_m"] = quarterly_interest
    return out


class TestTheStubIsWithdrawn:
    def test_caterpillar_loses_its_coverage_figure(self):
        """CAT: $529M of annualised row against $1,861M filed, 3.5x apart."""
        profile = _profile(31.8, 132.25)
        state: dict[str, str] = {}

        _gate_interest_coverage(profile, state, "CAT", _cost(1_861))

        assert "interest_coverage" not in profile, (
            "a numerator 3.5x below the filed consolidated figure must not "
            "render a coverage ratio"
        )
        assert "interest_coverage_quarter" not in profile
        assert state["interest_coverage"] == LiveDataState.UNAVAILABLE.value
        assert state["interest_coverage_quarter"] == LiveDataState.UNAVAILABLE.value

    def test_general_motors_loses_its_coverage_figure(self):
        """GM: $685M read against $4,121M of `us-gaap:InterestExpense`."""
        profile = _profile(9.7, 171.25)
        state: dict[str, str] = {}

        _gate_interest_coverage(profile, state, "GM", _cost(4_121))

        assert "interest_coverage" not in profile
        assert state["interest_coverage"] == LiveDataState.UNAVAILABLE.value

    def test_it_withdraws_rather_than_substituting_a_corrected_ratio(self):
        """No re-derived figure appears in the withdrawn field's place.

        An annual numerator cannot rebuild a quarterly ratio without assuming
        an even spread. Absence is the honest output; a corrected-looking
        number would be the same defect with a different value.
        """
        profile = _profile(31.8, 132.25)

        _gate_interest_coverage(profile, {}, "CAT", _cost(1_861))

        assert profile.get("interest_coverage") is None
        assert not any(
            "coverage" in key and profile[key] is not None for key in profile
        ), f"a replacement coverage figure was written: {profile}"


class TestTheCorroboratedFigureSurvives:
    def test_a_filer_whose_row_agrees_keeps_its_ratio(self):
        """DE reads 0.94x against its own tag — inside the limit, untouched."""
        profile = _profile(4.2, 470.0)
        state: dict[str, str] = {}

        _gate_interest_coverage(profile, state, "DE", _cost(1_880))

        assert profile["interest_coverage"] == 4.2
        assert profile["interest_coverage_quarter"] == "2025-12-31"
        assert "interest_coverage" not in state

    @pytest.mark.parametrize("consolidated", [530.0, 1_050.0])
    def test_the_limit_is_not_a_hair_trigger(self, consolidated):
        """Seasonal borrowing annualises imperfectly; under 2x is not a defect.

        The ×4 bridge from one quarter is itself lossy, which is why the limit
        is loose rather than tight. A filer inside it keeps its figure.
        """
        profile = _profile(8.0, 132.25)

        _gate_interest_coverage(profile, {}, "SEASONAL", _cost(consolidated))

        assert profile["interest_coverage"] == 8.0


class TestSilentWithoutEvidence:
    def test_no_edgar_figure_leaves_the_ratio_alone(self):
        """Absence of corroboration is not evidence of a stub."""
        profile = _profile(31.8, 132.25)
        state: dict[str, str] = {}

        _gate_interest_coverage(profile, state, "CAT", None)

        assert profile["interest_coverage"] == 31.8, (
            "an un-ingested fact store must not blank a field for every filer"
        )
        assert state == {}

    def test_no_carried_numerator_leaves_the_ratio_alone(self):
        """A profile built before the numerator was carried still renders.

        The quotient alone cannot support the comparison: 31.8x is equally
        consistent with a stub numerator and with an unlevered filer.
        """
        profile = _profile(31.8, None)

        _gate_interest_coverage(profile, {}, "CAT", _cost(1_861))

        assert profile["interest_coverage"] == 31.8

    def test_no_ratio_is_a_no_op(self):
        profile: dict = {"interest_expense_quarter_usd_m": 132.25}
        state: dict[str, str] = {}

        _gate_interest_coverage(profile, state, "CAT", _cost(1_861))

        assert state == {}

    @pytest.mark.parametrize("bad", [0, 0.0])
    def test_a_zero_numerator_cannot_divide(self, bad):
        """Guards the ZeroDivisionError the ratio arithmetic would otherwise hit."""
        profile = _profile(31.8, bad)

        _gate_interest_coverage(profile, {}, "CAT", _cost(1_861))

        assert profile["interest_coverage"] == 31.8


class TestTheNumeratorIsCarriedButNeverRendered:
    def test_the_field_is_declared_on_the_profile_key_list(self):
        """It rides the same fetch, so it must share its live/absent state."""
        assert (
            "interest_expense_quarter_usd_m"
            in room_runner._FUNDAMENTALS_OPTIONAL_LIVE_ONLY_FIELDS
        ), (
            "a carried field absent from the key list gets no state and can "
            "pair a live figure with a stale label"
        )

    def test_it_reaches_no_render_function(self):
        """DEF399's numerator is evidence, not a line on the sheet."""
        import inspect

        from app.services import room_prompts

        assert "interest_expense_quarter_usd_m" not in inspect.getsource(room_prompts), (
            "the corroboration numerator must not be rendered — it is a "
            "quarterly stub for exactly the filers the gate exists for"
        )
