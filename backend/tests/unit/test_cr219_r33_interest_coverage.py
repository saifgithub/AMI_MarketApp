"""CR219 R33 — interest coverage (EBIT / interest expense).

The #1 request across the CR219 arm measurement: 21 mentions from 9 of 12
agents, and the CAT insolvency-risk narrative in the evidence corpus was
reasoned about with no coverage figure on the sheet at all — the sheet
carried debt/equity and net cash/debt, but nothing that answers "can this
company service its interest cost from operating profit."

EBIT is `Operating Income` — this module already fetches that row for the
margin-trend YoY delta (`_fetch_statement_facts_uncached`), so no new
statement call is made; only a new row read off the same
`.quarterly_income_stmt` this function already holds.
"""

from __future__ import annotations

import pytest

from app.services.fundamentals import interest_coverage_line
from app.services.room_runner import _FUNDAMENTALS_OPTIONAL_LIVE_ONLY_FIELDS


class TestTheLineItself:
    def test_ratio_and_quarter_both_render(self):
        line = interest_coverage_line(9.4, "2026-04-30")
        assert "9.4x" in line
        assert "2026-04-30" in line
        assert "EBIT" in line

    def test_no_ratio_renders_nothing(self):
        """DEF053's shape: never a header over an absence."""
        assert interest_coverage_line(None, "2026-04-30") is None

    def test_no_quarter_renders_nothing(self):
        """A ratio with no date attached is exactly the defect
        `margin_trend_line`'s docstring designs against — never ship a number
        with no basis stated."""
        assert interest_coverage_line(9.4, None) is None

    def test_neither_renders_nothing(self):
        assert interest_coverage_line(None, None) is None

    def test_live_marker_present_by_default(self):
        line = interest_coverage_line(9.4, "2026-04-30")
        assert "(LIVE)" in line

    def test_live_false_omits_the_marker(self):
        """The 1-on-1 surface renders every fundamentals line with `live=False`
        (presence-only gating, matching `capital_return_line`'s own 1-on-1
        call) — the marker itself must be able to turn off."""
        line = interest_coverage_line(9.4, "2026-04-30", live=False)
        assert "(LIVE)" not in line


class TestSignHandling:
    def test_a_negative_ebit_produces_a_negative_ratio(self):
        """Coverage is meaningfully negative when the company is not
        operationally profitable — that sign must survive, unlike the
        interest-expense sign, which is always folded to a cost."""
        line = interest_coverage_line(-2.1, "2026-04-30")
        assert "-2.1x" in line


class TestProvenanceRegistration:
    """CR104: a field with no recorded provenance renders as nothing at all.

    Computing this and forgetting to register it would be the CR040
    silent-dark shape CR218's own comment names — the arithmetic runs on
    every convene and reaches no agent.
    """

    @pytest.mark.parametrize(
        "field", ["interest_coverage", "interest_coverage_quarter"],
    )
    def test_the_new_fields_are_registered_as_optional_live(self, field):
        assert field in _FUNDAMENTALS_OPTIONAL_LIVE_ONLY_FIELDS, (
            f"{field} is computed but unregistered, so the renderer drops it"
        )


class TestBothSurfacesRenderIt:
    """The 1-on-1 sheet and the Room sheet must not disagree about one
    company — the same parity rule CR166 Tier B / CR179 Leg 3 / CR218 state.
    """

    def test_both_render_sites_call_the_builder(self):
        import inspect

        from app.services import fundamentals, room_prompts

        assert "interest_coverage_line(" in inspect.getsource(fundamentals), (
            "the 1-on-1 fact sheet does not render the line"
        )
        assert "interest_coverage_line(" in inspect.getsource(room_prompts), (
            "the Room fact sheet does not render the line"
        )


class TestTheFetcher:
    """`_fetch_statement_facts_uncached` — EBIT / |interest expense|, latest
    quarter, rounded to one decimal."""

    def test_computes_from_the_same_statement_call_as_margin_trend(self):
        import pandas as pd

        from app.services.fundamentals import _fetch_statement_facts_uncached

        periods = ["2026-04-30", "2026-01-31", "2025-10-31", "2025-07-31", "2025-04-30"]
        income = pd.DataFrame(
            [
                [1000.0] * 5,
                [734.5, 700.0, 650.0, 600.0, 500.0],
                [-78.1, -75.0, -71.0, -68.0, -60.0],
            ],
            index=["Total Revenue", "Operating Income", "Interest Expense"],
            columns=periods,
        )
        cashflow = pd.DataFrame(
            [[0.0] * 5], index=["Repurchase Of Capital Stock"], columns=periods,
        )

        class _FakeTicker:
            quarterly_income_stmt = income
            quarterly_cashflow = cashflow

        import sys
        import types

        import app.services.fundamentals as fmod

        fake_yf = types.SimpleNamespace(Ticker=lambda t: _FakeTicker())
        sys.modules["yfinance"] = fake_yf
        try:
            out = fmod._fetch_statement_facts_uncached("TEST")
        finally:
            del sys.modules["yfinance"]

        assert out is not None
        assert out["interest_coverage"] == 9.4
        assert out["interest_coverage_quarter"] == "2026-04-30"

    def test_no_interest_expense_row_produces_no_field(self):
        """Absent, not zero — a filer that does not break out interest expense
        as its own line is not the same claim as one whose coverage is
        infinite. Matches the buyback/dividend "absent row" convention this
        same function already follows."""
        import pandas as pd

        from app.services.fundamentals import _fetch_statement_facts_uncached

        periods = ["2026-04-30", "2026-01-31", "2025-10-31", "2025-07-31", "2025-04-30"]
        income = pd.DataFrame(
            [[1000.0] * 5, [734.5, 700.0, 650.0, 600.0, 500.0]],
            index=["Total Revenue", "Operating Income"],
            columns=periods,
        )
        cashflow = pd.DataFrame(
            [[0.0] * 5], index=["Repurchase Of Capital Stock"], columns=periods,
        )

        class _FakeTicker:
            quarterly_income_stmt = income
            quarterly_cashflow = cashflow

        import sys
        import types

        import app.services.fundamentals as fmod

        sys.modules["yfinance"] = types.SimpleNamespace(Ticker=lambda t: _FakeTicker())
        try:
            out = fmod._fetch_statement_facts_uncached("TEST")
        finally:
            del sys.modules["yfinance"]

        assert (out or {}).get("interest_coverage") is None

    def test_zero_interest_expense_produces_no_field(self):
        """Division-by-zero guard: a filer reporting exactly 0.0 interest
        expense (fully unlevered that quarter) must not render an infinite or
        crashing ratio — withheld, same as a missing row."""
        import pandas as pd

        from app.services.fundamentals import _fetch_statement_facts_uncached

        periods = ["2026-04-30", "2026-01-31", "2025-10-31", "2025-07-31", "2025-04-30"]
        income = pd.DataFrame(
            [
                [1000.0] * 5,
                [734.5, 700.0, 650.0, 600.0, 500.0],
                [0.0, 0.0, 0.0, 0.0, 0.0],
            ],
            index=["Total Revenue", "Operating Income", "Interest Expense"],
            columns=periods,
        )
        cashflow = pd.DataFrame(
            [[0.0] * 5], index=["Repurchase Of Capital Stock"], columns=periods,
        )

        class _FakeTicker:
            quarterly_income_stmt = income
            quarterly_cashflow = cashflow

        import sys
        import types

        import app.services.fundamentals as fmod

        sys.modules["yfinance"] = types.SimpleNamespace(Ticker=lambda t: _FakeTicker())
        try:
            out = fmod._fetch_statement_facts_uncached("TEST")
        finally:
            del sys.modules["yfinance"]

        assert (out or {}).get("interest_coverage") is None
