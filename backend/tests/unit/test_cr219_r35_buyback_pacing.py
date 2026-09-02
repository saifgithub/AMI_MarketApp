"""CR219 R35 — buyback pacing: the four-quarter repurchase series, dated,
plus a precomputed accelerating/steady/paused label.

`buyback_line` already states the trailing-4-quarter TOTAL. A total alone
cannot distinguish a company ramping its programme from one that has quietly
stopped it — two companies can share an identical total while in opposite
phases, the same "one number hides two stories" shape `capital_return_line`
already makes about buybacks-vs-dividends, one level down. Nothing new is
fetched: the four per-quarter magnitudes existed inside the same
`Repurchase Of Capital Stock` row `buyback_ttm` sums and discards.
"""

from __future__ import annotations

import pytest

from app.services.fundamentals import _buyback_pace, buyback_pacing_line
from app.services.room_runner import _FUNDAMENTALS_OPTIONAL_LIVE_ONLY_FIELDS


class TestThePaceClassifier:
    """`_buyback_pace` — a pure threshold bucket, same house style as
    `rsi_tone`. Latest quarter vs. the prior-3-quarter average, 20% either
    side."""

    def test_a_clear_ramp_is_accelerating(self):
        # latest 4000 against a prior-3 average of 1000 is a 4x ratio,
        # unambiguous.
        assert _buyback_pace([4000.0, 1000.0, 1000.0, 1000.0]) == "accelerating"

    def test_a_near_stop_is_paused(self):
        assert _buyback_pace([100.0, 2000.0, 2000.0, 2000.0]) == "paused"

    def test_ordinary_noise_is_steady(self):
        assert _buyback_pace([2100.0, 2000.0, 1900.0, 2000.0]) == "steady"

    def test_exactly_at_the_1_2_threshold_is_accelerating(self):
        """1200 / ((1000+1000+1000)/3) == 1.2 exactly — the >= boundary."""
        assert _buyback_pace([1200.0, 1000.0, 1000.0, 1000.0]) == "accelerating"

    def test_exactly_at_the_0_2_threshold_is_paused(self):
        """200 / ((1000+1000+1000)/3) == 0.2 exactly — the <= boundary."""
        assert _buyback_pace([200.0, 1000.0, 1000.0, 1000.0]) == "paused"

    def test_just_above_the_0_2_threshold_is_steady(self):
        assert _buyback_pace([201.0, 1000.0, 1000.0, 1000.0]) == "steady"

    def test_just_below_the_1_2_threshold_is_steady(self):
        assert _buyback_pace([1199.0, 1000.0, 1000.0, 1000.0]) == "steady"

    def test_no_prior_activity_at_all_returns_none(self):
        """A brand-new programme has no base to classify pace against —
        calling a first repurchase "accelerating" against zero is a
        manufactured comparison, not a measured one."""
        assert _buyback_pace([500.0, 0.0, 0.0, 0.0]) is None

    def test_fewer_than_four_quarters_returns_none(self):
        assert _buyback_pace([1000.0, 1000.0, 1000.0]) is None

    def test_more_than_four_quarters_returns_none(self):
        assert _buyback_pace([1000.0, 1000.0, 1000.0, 1000.0, 1000.0]) is None


class TestTheLineItself:
    def test_renders_all_four_quarters_oldest_first(self):
        line = buyback_pacing_line(
            [3000, 2000, 1654, 1000],
            ["2026-04-30", "2026-01-31", "2025-10-31", "2025-07-31"],
            "steady",
        )
        # Newest-first input, rendered oldest-first: the earliest date and
        # its figure must appear before the latest date and its figure.
        oldest_pos = line.index("2025-07-31")
        newest_pos = line.index("2026-04-30")
        assert oldest_pos < newest_pos
        assert "$1,000M" in line
        assert "$3,000M" in line
        assert "steady" in line

    def test_no_pace_still_renders_the_series(self):
        """A brand-new programme (no prior base) still has four real
        figures to state — the honest shape is dollars with no label, not a
        withheld line."""
        line = buyback_pacing_line(
            [500, 0, 0, 0],
            ["2026-04-30", "2026-01-31", "2025-10-31", "2025-07-31"],
            None,
        )
        assert line is not None
        assert "$500M" in line

    def test_no_series_renders_nothing(self):
        assert buyback_pacing_line(None, None, "steady") is None

    def test_no_basis_renders_nothing(self):
        """A series with no dated basis is the same unlabelled-number defect
        `margin_trend_line`'s docstring designs against."""
        assert buyback_pacing_line([3000, 2000, 1654, 1000], None, "steady") is None

    def test_wrong_length_series_renders_nothing(self):
        assert buyback_pacing_line([3000, 2000, 1654], ["a", "b", "c"], "steady") is None

    def test_live_marker_present_by_default(self):
        line = buyback_pacing_line(
            [3000, 2000, 1654, 1000],
            ["2026-04-30", "2026-01-31", "2025-10-31", "2025-07-31"],
            "steady",
        )
        assert "(LIVE)" in line

    def test_live_false_omits_the_marker(self):
        line = buyback_pacing_line(
            [3000, 2000, 1654, 1000],
            ["2026-04-30", "2026-01-31", "2025-10-31", "2025-07-31"],
            "steady",
            live=False,
        )
        assert "(LIVE)" not in line


class TestProvenanceRegistration:
    """CR104: a field with no recorded provenance renders as nothing at all."""

    @pytest.mark.parametrize(
        "field", ["buyback_quarterly", "buyback_quarterly_basis", "buyback_pace"],
    )
    def test_the_new_fields_are_registered_as_optional_live(self, field):
        assert field in _FUNDAMENTALS_OPTIONAL_LIVE_ONLY_FIELDS, (
            f"{field} is computed but unregistered, so the renderer drops it"
        )


class TestBothSurfacesRenderIt:
    def test_both_render_sites_call_the_builder(self):
        import inspect

        from app.services import fundamentals, room_prompts

        assert "buyback_pacing_line(" in inspect.getsource(fundamentals), (
            "the 1-on-1 fact sheet does not render the line"
        )
        assert "buyback_pacing_line(" in inspect.getsource(room_prompts), (
            "the Room fact sheet does not render the line"
        )


class TestTheFetcher:
    """`_fetch_statement_facts_uncached` — the per-quarter series, its dated
    basis, and the pace, off the SAME `Repurchase Of Capital Stock` row
    `buyback_ttm` already reads. Nothing new fetched."""

    def _run(self, repurchase_values):
        import sys
        import types

        import pandas as pd

        import app.services.fundamentals as fmod

        periods = ["2026-04-30", "2026-01-31", "2025-10-31", "2025-07-31", "2025-04-30"]
        cashflow = pd.DataFrame(
            [repurchase_values],
            index=["Repurchase Of Capital Stock"],
            columns=periods,
        )
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

    def test_produces_the_series_basis_and_pace_together(self):
        out = self._run([-4e9, -1e9, -1e9, -1e9, -1e9])
        assert out is not None
        assert out["buyback_quarterly"] == [4000, 1000, 1000, 1000]
        assert out["buyback_quarterly_basis"] == [
            "2026-04-30", "2026-01-31", "2025-10-31", "2025-07-31",
        ]
        assert out["buyback_pace"] == "accelerating"

    def test_the_ttm_sum_and_the_series_sum_agree(self):
        """The series is derived from the exact same four values the TTM
        total sums — the two must never disagree about the underlying
        magnitudes, only about whether they're collapsed to one number."""
        out = self._run([-2e9, -3e9, -1e9, -1.654e9, -5e8])
        assert out["buyback_ttm"] == round(sum(out["buyback_quarterly"]))

    def test_no_repurchase_row_produces_none_of_the_three(self):
        import sys
        import types

        import pandas as pd

        import app.services.fundamentals as fmod

        periods = ["2026-04-30", "2026-01-31", "2025-10-31", "2025-07-31", "2025-04-30"]
        cashflow = pd.DataFrame(
            [[0.0] * 5], index=["Cash Dividends Paid"], columns=periods,
        )
        income = pd.DataFrame(
            [[1000.0] * 5], index=["Total Revenue"], columns=periods,
        )

        class _FakeTicker:
            quarterly_income_stmt = income
            quarterly_cashflow = cashflow

        sys.modules["yfinance"] = types.SimpleNamespace(Ticker=lambda t: _FakeTicker())
        try:
            out = fmod._fetch_statement_facts_uncached("TEST")
        finally:
            del sys.modules["yfinance"]

        out = out or {}
        assert "buyback_quarterly" not in out
        assert "buyback_quarterly_basis" not in out
        assert "buyback_pace" not in out

    def test_no_prior_activity_omits_pace_but_keeps_the_series(self):
        """The series and basis still ship (real, dated figures); only the
        pace label is withheld when there is no base to classify against."""
        out = self._run([-5e8, 0.0, 0.0, 0.0, -1e9])
        assert out["buyback_quarterly"] == [500, 0, 0, 0]
        assert "buyback_pace" not in out
