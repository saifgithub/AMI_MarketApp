"""CR219 R21-DATA — earnings revisions + surprise history.

Unblocks WP04-R21's overlay rewrite: `overlay_generator.py`'s short/medium
fundamentals branch has demanded "earnings revisions, surprise history"
since before this CR, and nothing fetched either half — the demand asked
agents to analyse data they were never given. This ships the field; the
demand-text rewrite is WP04's own follow-up commit, coordinated by this
one landing first (per DECISIONS_2026-09-02.md §1: "field ships first,
demand text aligned after").

Two yfinance properties, both siblings of the already-fetched
`quarterly_income_stmt`/`quarterly_cashflow`/`income_stmt` on the same
`yf.Ticker` object — zero new network endpoints:

- `tk.eps_trend` (revisions direction) — the CURRENT-quarter row (`0q`),
  comparing today's consensus estimate against 90 days ago.
- `tk.earnings_history` (surprise history) — reported vs. estimate per
  quarter, yfinance's own pre-computed surprise. NOT `tk.earnings_dates`:
  that property's scrape path needs `lxml`, confirmed NOT an installed
  dependency in this project by running it live against a real ticker,
  2026-09-03, before choosing the alternative.
"""

from __future__ import annotations

import sys
import types

import pandas as pd
import pytest

import app.services.fundamentals as fmod
from app.services.fundamentals import eps_revisions_line, surprise_history_line
from app.services.room_runner import _FUNDAMENTALS_OPTIONAL_LIVE_ONLY_FIELDS

_QUARTERLY_PERIODS = [
    "2026-04-30", "2026-01-31", "2025-10-31", "2025-07-31", "2025-04-30",
]


class TestEpsRevisionsLine:
    def test_an_up_move_renders_direction_and_magnitude(self):
        line = eps_revisions_line("up", 6.9, 6.95, 90)
        assert "up" in line
        assert "6.9%" in line
        assert "$6.95" in line
        assert "90" in line

    def test_a_down_move_renders_direction(self):
        line = eps_revisions_line("down", 12.0, 5.5, 90)
        assert "down" in line
        assert "12.0%" in line

    def test_unchanged_omits_the_percentage(self):
        """A flat/near-flat move genuinely has nothing meaningful to
        percentage-quantify — the direction word alone is the honest claim."""
        line = eps_revisions_line("unchanged", 0.1, 9.0, 90)
        assert "unchanged" in line
        assert "%" not in line

    def test_no_direction_renders_nothing(self):
        assert eps_revisions_line(None, 6.9, 6.95, 90) is None

    def test_no_current_estimate_renders_nothing(self):
        """A direction with no anchor value is the unlabelled-number defect
        this whole module designs against."""
        assert eps_revisions_line("up", 6.9, None, 90) is None

    def test_no_window_renders_nothing(self):
        assert eps_revisions_line("up", 6.9, 6.95, None) is None

    def test_live_marker_present_by_default(self):
        assert "(LIVE)" in eps_revisions_line("up", 6.9, 6.95, 90)

    def test_live_false_omits_the_marker(self):
        line = eps_revisions_line("up", 6.9, 6.95, 90, live=False)
        assert "(LIVE)" not in line


class TestSurpriseHistoryLine:
    def test_multiple_quarters_render_in_order(self):
        line = surprise_history_line(
            ["2025-09-30", "2025-12-31"], [4.95, 5.16], [4.52, 4.71], [9.5, 9.6],
        )
        assert "2025-09-30" in line
        assert "2025-12-31" in line
        assert line.index("2025-09-30") < line.index("2025-12-31")
        assert "$4.95" in line
        assert "$4.52" in line
        assert "beat by 9.5%" in line

    def test_a_miss_says_missed_not_beat(self):
        line = surprise_history_line(["2025-09-30"], [4.00], [4.50], [-11.1])
        assert "missed by 11.1%" in line
        assert "beat" not in line

    def test_a_quarter_with_no_surprise_pct_still_renders_the_dollars(self):
        """DEF053: the surprise percentage is withheld when yfinance's own
        computation didn't produce one, but the reported/estimate dollars
        are still real and still worth stating."""
        line = surprise_history_line(["2025-09-30"], [4.95], [4.52], [None])
        assert "$4.95" in line
        assert "$4.52" in line
        assert "beat" not in line
        assert "missed" not in line

    def test_fewer_quarters_than_the_usual_four_still_renders(self):
        """Real, measured: SNOA returned 3 of the usual 4 quarters (checked
        live 2026-09-03) — the count is never assumed."""
        line = surprise_history_line(
            ["2025-06-30", "2025-09-30", "2025-12-31"],
            [1.0, 1.1, 1.2], [0.9, 1.0, 1.1], [11.1, 10.0, 9.1],
        )
        assert line.count(":") >= 3  # one "quarter:" clause per entry

    def test_no_quarters_renders_nothing(self):
        assert surprise_history_line(None, [4.95], [4.52], [9.5]) is None
        assert surprise_history_line([], [], [], []) is None

    def test_mismatched_lengths_render_nothing(self):
        """A caller error, not a data gap — the three parallel lists must
        agree in length or nothing is trustworthy to render."""
        assert surprise_history_line(["q1", "q2"], [1.0], [1.0], [1.0]) is None

    def test_live_marker_present_by_default(self):
        line = surprise_history_line(["2025-09-30"], [4.95], [4.52], [9.5])
        assert "(LIVE)" in line

    def test_live_false_omits_the_marker(self):
        line = surprise_history_line(["2025-09-30"], [4.95], [4.52], [9.5], live=False)
        assert "(LIVE)" not in line


class TestProvenanceRegistration:
    @pytest.mark.parametrize(
        "field",
        [
            "eps_revisions_direction", "eps_revisions_pct",
            "eps_revisions_current", "eps_revisions_window_days",
            "surprise_quarters", "surprise_actuals", "surprise_estimates",
            "surprise_pcts",
        ],
    )
    def test_the_new_fields_are_registered_as_optional_live(self, field):
        assert field in _FUNDAMENTALS_OPTIONAL_LIVE_ONLY_FIELDS, (
            f"{field} is computed but unregistered, so the renderer drops it"
        )


class TestBothSurfacesRenderIt:
    def test_both_render_sites_call_both_builders(self):
        import inspect

        from app.services import room_prompts

        for fn_name in ("eps_revisions_line(", "surprise_history_line("):
            assert fn_name in inspect.getsource(fmod), (
                f"the 1-on-1 fact sheet does not render {fn_name}"
            )
            assert fn_name in inspect.getsource(room_prompts), (
                f"the Room fact sheet does not render {fn_name}"
            )


def _fake_ticker(eps_trend=None, earnings_history=None):
    empty_quarterly = pd.DataFrame(
        [[0.0] * 5], index=["Total Revenue"], columns=_QUARTERLY_PERIODS,
    )
    empty_annual = pd.DataFrame(
        [[float("nan")] * 5], index=["EBITDA"],
        columns=["2025-12-31", "2024-12-31", "2023-12-31", "2022-12-31", "2021-12-31"],
    )

    class _FakeTicker:
        quarterly_income_stmt = empty_quarterly
        quarterly_cashflow = empty_quarterly
        income_stmt = empty_annual

    tk = _FakeTicker()
    if eps_trend is not None:
        tk.eps_trend = eps_trend
    if earnings_history is not None:
        tk.earnings_history = earnings_history
    return tk


class TestTheFetcherEpsTrend:
    """`_fetch_statement_facts_uncached` — the `0q` row, current vs. 90 days
    ago, direction thresholded at 0.5%."""

    def _run(self, eps_trend):
        tk = _fake_ticker(eps_trend=eps_trend)
        sys.modules["yfinance"] = types.SimpleNamespace(Ticker=lambda t: tk)
        try:
            return fmod._fetch_statement_facts_uncached("TEST")
        finally:
            del sys.modules["yfinance"]

    def test_a_clear_rise_is_up(self):
        et = pd.DataFrame(
            {"current": [6.95], "90daysAgo": [6.50]}, index=["0q"],
        )
        out = self._run(et)
        assert out is not None
        assert out["eps_revisions_direction"] == "up"
        assert out["eps_revisions_pct"] == pytest.approx(6.9, abs=0.05)
        assert out["eps_revisions_current"] == 6.95
        assert out["eps_revisions_window_days"] == 90

    def test_a_clear_fall_is_down(self):
        et = pd.DataFrame(
            {"current": [6.00], "90daysAgo": [6.50]}, index=["0q"],
        )
        out = self._run(et)
        assert out["eps_revisions_direction"] == "down"

    def test_a_tiny_move_is_unchanged(self):
        """Under the 0.5% threshold — matches `window_trend_phrase`'s own
        "flat" band for price moves, scaled for an EPS estimate."""
        et = pd.DataFrame(
            {"current": [6.501], "90daysAgo": [6.500]}, index=["0q"],
        )
        out = self._run(et)
        assert out["eps_revisions_direction"] == "unchanged"

    def test_no_0q_row_produces_nothing(self):
        et = pd.DataFrame({"current": [6.95], "90daysAgo": [6.50]}, index=["+1q"])
        out = self._run(et)
        assert (out or {}).get("eps_revisions_direction") is None

    def test_a_zero_90_days_ago_estimate_produces_nothing(self):
        """Division-by-zero guard — a real if unusual case (a name with a
        just-initiated, near-zero estimate 90 days ago)."""
        et = pd.DataFrame({"current": [6.95], "90daysAgo": [0.0]}, index=["0q"])
        out = self._run(et)
        assert (out or {}).get("eps_revisions_direction") is None

    def test_fetch_error_produces_nothing_and_does_not_raise(self):
        class _RaisingTk:
            quarterly_income_stmt = pd.DataFrame(
                [[0.0] * 5], index=["Total Revenue"], columns=_QUARTERLY_PERIODS,
            )
            quarterly_cashflow = quarterly_income_stmt
            income_stmt = pd.DataFrame(
                [[float("nan")] * 5], index=["EBITDA"],
                columns=["a", "b", "c", "d", "e"],
            )

            @property
            def eps_trend(self):
                raise RuntimeError("boom")

        sys.modules["yfinance"] = types.SimpleNamespace(Ticker=lambda t: _RaisingTk())
        try:
            out = fmod._fetch_statement_facts_uncached("TEST")
        finally:
            del sys.modules["yfinance"]
        assert (out or {}).get("eps_revisions_direction") is None


class TestTheFetcherEarningsHistory:
    """`_fetch_statement_facts_uncached` — reported/estimate/surprise, per
    quarter, off `tk.earnings_history`."""

    def _run(self, earnings_history):
        tk = _fake_ticker(earnings_history=earnings_history)
        sys.modules["yfinance"] = types.SimpleNamespace(Ticker=lambda t: tk)
        try:
            return fmod._fetch_statement_facts_uncached("TEST")
        finally:
            del sys.modules["yfinance"]

    def test_two_quarters_produce_four_parallel_lists_in_order(self):
        eh = pd.DataFrame(
            {
                "epsActual": [4.95, 5.16], "epsEstimate": [4.52, 4.71],
                "epsDifference": [0.43, 0.45], "surprisePercent": [0.0951, 0.0955],
            },
            index=pd.to_datetime(["2025-09-30", "2025-12-31"]),
        )
        out = self._run(eh)
        assert out is not None
        assert out["surprise_quarters"] == ["2025-09-30", "2025-12-31"]
        assert out["surprise_actuals"] == [4.95, 5.16]
        assert out["surprise_estimates"] == [4.52, 4.71]
        assert out["surprise_pcts"] == [9.5, 9.6]

    def test_fewer_than_four_quarters_still_produces_what_exists(self):
        """SNOA-shaped: real yfinance returned 3 rows for this ticker
        (checked live, 2026-09-03) — the fetcher must not require 4."""
        eh = pd.DataFrame(
            {
                "epsActual": [1.0, 1.1, 1.2], "epsEstimate": [0.9, 1.0, 1.1],
                "epsDifference": [0.1, 0.1, 0.1],
                "surprisePercent": [0.111, 0.100, 0.091],
            },
            index=pd.to_datetime(["2025-06-30", "2025-09-30", "2025-12-31"]),
        )
        out = self._run(eh)
        assert len(out["surprise_quarters"]) == 3

    def test_empty_frame_produces_nothing(self):
        eh = pd.DataFrame(
            {"epsActual": [], "epsEstimate": [], "epsDifference": [], "surprisePercent": []},
        )
        out = self._run(eh)
        assert (out or {}).get("surprise_quarters") is None

    def test_a_row_missing_actual_or_estimate_is_dropped_from_all_four_lists(self):
        """Absent, not zero — matches the buyback/dividend/capex row-drop
        convention elsewhere in this fetcher."""
        eh = pd.DataFrame(
            {
                "epsActual": [4.95, float("nan")], "epsEstimate": [4.52, 4.71],
                "epsDifference": [0.43, float("nan")],
                "surprisePercent": [0.0951, float("nan")],
            },
            index=pd.to_datetime(["2025-09-30", "2025-12-31"]),
        )
        out = self._run(eh)
        assert out["surprise_quarters"] == ["2025-09-30"]
        assert len(out["surprise_actuals"]) == 1

    def test_fetch_error_produces_nothing_and_does_not_raise(self):
        class _RaisingTk:
            quarterly_income_stmt = pd.DataFrame(
                [[0.0] * 5], index=["Total Revenue"], columns=_QUARTERLY_PERIODS,
            )
            quarterly_cashflow = quarterly_income_stmt
            income_stmt = pd.DataFrame(
                [[float("nan")] * 5], index=["EBITDA"],
                columns=["a", "b", "c", "d", "e"],
            )

            @property
            def earnings_history(self):
                raise RuntimeError("boom")

        sys.modules["yfinance"] = types.SimpleNamespace(Ticker=lambda t: _RaisingTk())
        try:
            out = fmod._fetch_statement_facts_uncached("TEST")
        finally:
            del sys.modules["yfinance"]
        assert (out or {}).get("surprise_quarters") is None
