"""CR219 R34 — capital expenditure, stated explicitly.

The sheet already renders `free_cash_flow` (a single pre-computed yfinance
`.info` figure, not `operating_cash_flow - capex` computed anywhere in this
codebase), so before this field an agent could only infer capex by ALSO
knowing operating cash flow — a number the sheet never carried either. R20's
global derivation policy ("agents never do arithmetic on sheet figures") now
forbids the inference outright; this field makes the number explicit instead
of implicit.
"""

from __future__ import annotations

import pytest

from app.services.fundamentals import capex_line
from app.services.room_runner import _FUNDAMENTALS_OPTIONAL_LIVE_ONLY_FIELDS


class TestTheLineItself:
    def test_a_value_renders(self):
        line = capex_line(6543)
        assert "$6,543M" in line
        assert "trailing 4 quarters" in line
        assert "Capital expenditure" in line

    def test_no_value_renders_nothing(self):
        """DEF053's shape: never a header over an absence."""
        assert capex_line(None) is None

    def test_live_marker_present_by_default(self):
        assert "(LIVE)" in capex_line(6543)

    def test_live_false_omits_the_marker(self):
        """The 1-on-1 surface renders every fundamentals line with
        `live=False` (presence-only gating, matching every other line in
        that block)."""
        line = capex_line(6543, live=False)
        assert "(LIVE)" not in line


class TestProvenanceRegistration:
    """CR104: a field with no recorded provenance renders as nothing at all.

    Computing this and forgetting to register it would be the CR040
    silent-dark shape — the arithmetic runs on every convene and reaches no
    agent.
    """

    def test_the_new_field_is_registered_as_optional_live(self):
        assert "capex_ttm" in _FUNDAMENTALS_OPTIONAL_LIVE_ONLY_FIELDS, (
            "capex_ttm is computed but unregistered, so the renderer drops it"
        )


class TestBothSurfacesRenderIt:
    """The 1-on-1 sheet and the Room sheet must not disagree about one
    company — the CR166 Tier B / CR179 Leg 3 / CR218 parity rule.
    """

    def test_both_render_sites_call_the_builder(self):
        import inspect

        from app.services import fundamentals, room_prompts

        assert "capex_line(" in inspect.getsource(fundamentals), (
            "the 1-on-1 fact sheet does not render the line"
        )
        assert "capex_line(" in inspect.getsource(room_prompts), (
            "the Room fact sheet does not render the line"
        )


class TestTheFetcher:
    """`_fetch_statement_facts_uncached` — |sum of trailing 4 quarters' capex|,
    in $M, off the same `.quarterly_cashflow` call the buyback/dividend rows
    already read."""

    def _run(self, cashflow_index, cashflow_rows):
        import sys
        import types

        import pandas as pd

        import app.services.fundamentals as fmod

        periods = ["2026-04-30", "2026-01-31", "2025-10-31", "2025-07-31", "2025-04-30"]
        cashflow = pd.DataFrame(cashflow_rows, index=cashflow_index, columns=periods)
        income = pd.DataFrame(
            [[1000.0] * 5], index=["Total Revenue"], columns=periods,
        )

        class _FakeTicker:
            quarterly_income_stmt = income
            quarterly_cashflow = cashflow

        sys.modules["yfinance"] = types.SimpleNamespace(Ticker=lambda t: _FakeTicker())
        try:
            return fmod._fetch_statement_facts_uncached("TEST")
        finally:
            del sys.modules["yfinance"]

    def test_computes_ttm_capex_from_the_trailing_four_quarters(self):
        out = self._run(
            ["Capital Expenditure"],
            [[-2e9, -1.5e9, -1.8e9, -1.243e9, -9e8]],
        )
        assert out is not None
        assert out["capex_ttm"] == 6543

    def test_the_fifth_oldest_column_is_excluded_from_the_sum(self):
        """Proves the `[:4]` slice, not just the arithmetic — an oldest-column
        value large enough to change the sum if included must NOT move the
        result."""
        out = self._run(
            ["Capital Expenditure"],
            [[-2e9, -1.5e9, -1.8e9, -1.243e9, -999e9]],
        )
        assert out["capex_ttm"] == 6543

    def test_no_capex_row_produces_no_field(self):
        """Absent, not zero — matches the buyback/dividend/interest-expense
        absent-row convention this same function already follows."""
        out = self._run(
            ["Repurchase Of Capital Stock"],
            [[0.0] * 5],
        )
        assert (out or {}).get("capex_ttm") is None

    def test_fewer_than_four_reported_quarters_produces_no_field(self):
        """A newly-listed filer with fewer than four quarterly columns of
        capex history is a different claim from one that spent nothing —
        matches the buyback fetcher's own `len(recent) == 4` gate."""
        out = self._run(
            ["Capital Expenditure"],
            [[-2e9, -1.5e9, None, None, None]],
        )
        assert (out or {}).get("capex_ttm") is None

    def test_a_label_variant_is_matched(self):
        """Row-name variance is real and measured elsewhere in this module
        (the buyback/dividend rows both carry alternate spellings) — capex
        gets the same defensive multi-alias match."""
        out = self._run(
            ["Purchase Of PPE"],
            [[-2e9, -1.5e9, -1.8e9, -1.243e9, -9e8]],
        )
        assert out["capex_ttm"] == 6543
