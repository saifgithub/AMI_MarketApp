"""CR219 R37 — is today's multiple against a normal or an extreme year of
this company's OWN earnings/EBITDA?

Explicitly NOT a reconstructed historical-price P/E series (that needs a
multi-year price-history fetch the house rule forbids — "everything derives
from statements/bars/estimates yfinance already returns via the existing
fetch paths"). Today's price/EV divided by EACH of the last several fiscal
years' own EPS/EBITDA, then the MEDIAN of those implied multiples. Answers
the real gap the evidence corpus found: the PM's own gap report on a 24.5x
EV/EBITDA verdict — "if I had proof that 24.5x was a normal mid-cycle
baseline rather than an extreme cyclical peak, I might have approved."

The window is measured per-ticker, not assumed to be 4 or 5: real yfinance
(verified against CAT/NVDA/KTOS/SNOA, 2026-09-03) returns 5 annual columns
for every ticker checked, but CAT's oldest column is NaN on both the EBITDA
and Diluted EPS rows, leaving exactly 4 usable years for that name
specifically — the fixtures below replicate that shape deliberately.
"""

from __future__ import annotations

import sys
import types

import pandas as pd
import pytest

import app.services.fundamentals as fmod
from app.services.fundamentals import historical_multiples_line
from app.services.room_runner import _FUNDAMENTALS_OPTIONAL_LIVE_ONLY_FIELDS

_FY_PERIODS = ["2025-12-31", "2024-12-31", "2023-12-31", "2022-12-31", "2021-12-31"]


def _annual_income_stmt(ebitda, diluted_eps):
    return pd.DataFrame(
        [ebitda, diluted_eps],
        index=["EBITDA", "Diluted EPS"],
        columns=_FY_PERIODS,
    )


class TestTheLineItself:
    def test_both_halves_render(self):
        line = historical_multiples_line(
            15.7, 4, "2025-2022", 11.3, 4, "2025-2022",
        )
        assert "median 15.7x" in line
        assert "median 11.3x" in line
        assert "the last 4 FYs" in line
        assert "2025-2022" in line

    def test_says_explicitly_it_is_not_a_reconstructed_series(self):
        """The self-disclosure that keeps the R7 peer-basket denial (and the
        genuinely-different 'not a historical multiple series' claim) both
        true at once — this line must never be mistaken for what it isn't."""
        line = historical_multiples_line(15.7, 4, "2025-2022", None, None, None)
        assert "NOT a historical price-based multiple series" in line
        assert "No peer-basket comparison exists" in line

    def test_pe_half_alone_renders(self):
        line = historical_multiples_line(15.7, 4, "2025-2022", None, None, None)
        assert "median 15.7x" in line
        assert "EV/EBITDA" not in line

    def test_ev_ebitda_half_alone_renders(self):
        line = historical_multiples_line(None, None, None, 11.3, 4, "2025-2022")
        assert "median 11.3x" in line
        assert "P/E:" not in line

    def test_neither_half_renders_nothing(self):
        assert historical_multiples_line(None, None, None, None, None, None) is None

    def test_a_half_with_a_median_but_no_years_or_window_does_not_render_that_half(self):
        """A live median paired with a missing year-count or window is the
        exact partial-provenance shape the per-field field_state gating
        exists to prevent — this function's own contract must refuse to
        render an unlabelled figure even if a caller supplies one."""
        line = historical_multiples_line(15.7, None, "2025-2022", None, None, None)
        assert line is None
        line2 = historical_multiples_line(15.7, 4, None, None, None, None)
        assert line2 is None

    def test_live_marker_present_by_default(self):
        line = historical_multiples_line(15.7, 4, "2025-2022", None, None, None)
        assert "(LIVE)" in line

    def test_live_false_omits_the_marker(self):
        line = historical_multiples_line(
            15.7, 4, "2025-2022", None, None, None, live=False,
        )
        assert "(LIVE)" not in line


class TestProvenanceRegistration:
    @pytest.mark.parametrize(
        "field",
        [
            "historical_pe_median", "historical_pe_years", "historical_pe_window",
            "historical_ev_ebitda_median", "historical_ev_ebitda_years",
            "historical_ev_ebitda_window",
        ],
    )
    def test_the_new_fields_are_registered_as_optional_live(self, field):
        assert field in _FUNDAMENTALS_OPTIONAL_LIVE_ONLY_FIELDS, (
            f"{field} is computed but unregistered, so the renderer drops it"
        )


class TestBothSurfacesRenderIt:
    def test_both_render_sites_call_the_builder(self):
        import inspect

        from app.services import room_prompts

        assert "historical_multiples_line(" in inspect.getsource(fmod), (
            "the 1-on-1 fact sheet does not render the line"
        )
        assert "historical_multiples_line(" in inspect.getsource(room_prompts), (
            "the Room fact sheet does not render the line"
        )


class TestTheFetcher:
    """`fetch_live_fundamentals` — the median computation, end to end
    through a fake `yf.Ticker` carrying both the quarterly statements (for
    the R33/R34/R35 fields) and the ANNUAL `income_stmt` (for R37).
    """

    def _run(self, ebitda, diluted_eps, *, price=100.0, market_cap=None,
             total_debt=None, total_cash=None):
        # A minimal `.info` dict carrying only what this computation needs;
        # every other numeric key resolves via a deterministic fallback so
        # every OTHER branch of the real fetcher still fires without
        # raising, matching this module's own `_AllKeysInfo`-style fixture
        # discipline in test_prompt_data_parity.py — but self-contained here
        # rather than importing that file's private fixture, so this test's
        # correctness never depends on an unrelated file's internals.
        class _Info(dict):
            def get(self, key, default=None):
                overrides = {
                    "currentPrice": price,
                    "marketCap": market_cap if market_cap is not None else 1_000_000_000.0,
                    "totalDebt": total_debt if total_debt is not None else 0.0,
                    "totalCash": total_cash if total_cash is not None else 0.0,
                    "exchange": "NMS",
                    "marketState": "REGULAR",
                }
                if key in overrides:
                    return overrides[key]
                return None

            def __bool__(self) -> bool:
                # `fetch_live_fundamentals` bails to None on `if not info`,
                # and an empty dict subclass with no real items is falsy by
                # default — matching `_AllKeysInfo`'s own override in
                # test_prompt_data_parity.py, so this fixture's `info` reads
                # as present the same way that one does.
                return True

        empty_quarterly = pd.DataFrame(
            [[0.0] * 5], index=["Total Revenue"],
            columns=["2026-04-30", "2026-01-31", "2025-10-31", "2025-07-31", "2025-04-30"],
        )

        class _FakeTicker:
            info = _Info()
            quarterly_income_stmt = empty_quarterly
            quarterly_cashflow = empty_quarterly
            income_stmt = _annual_income_stmt(ebitda, diluted_eps)

        sys.modules["yfinance"] = types.SimpleNamespace(
            __version__="1.2.3", Ticker=lambda t: _FakeTicker(),
        )
        try:
            return fmod.fetch_live_fundamentals("TEST")
        finally:
            del sys.modules["yfinance"]
            fmod.clear_statement_cache()

    def test_the_cat_shaped_case_uses_exactly_four_years_and_labels_it_so(self):
        """The real, measured CAT shape: 5 columns, oldest NaN on both rows
        -> exactly 4 usable years, window spans the 4 real ones only."""
        out = self._run(
            ebitda=[14305.0, 16038.0, 15705.0, 11414.0, float("nan")],
            diluted_eps=[18.81, 22.05, 20.12, 12.64, float("nan")],
            price=300.0, market_cap=150_000_000_000.0,
            total_debt=30_000_000_000.0, total_cash=5_000_000_000.0,
        )
        assert out is not None
        assert out["historical_ev_ebitda_years"] == 4
        assert out["historical_pe_years"] == 4
        # Chronological order, oldest first — "2022-2025" reads as a normal
        # historical window; the fetcher builds it from
        # `{oldest_usable_year}-{newest_usable_year}`.
        assert out["historical_ev_ebitda_window"] == "2022-2025"
        assert out["historical_pe_window"] == "2022-2025"
        assert "2021" not in out["historical_ev_ebitda_window"]
        assert "2021" not in out["historical_pe_window"]

    def test_the_median_is_the_middle_of_four_implied_multiples(self):
        """EV = market_cap(1000) + debt(0) - cash(0) = 1000 (in whatever
        unit `.info` returns — this fixture keeps it simple: 1000/each
        EBITDA year gives implied multiples [10, 5, 4, 2] sorted; median of
        an even count is the mean of the two middle values: (5+4)/2 = 4.5."""
        out = self._run(
            ebitda=[100.0, 200.0, 250.0, 500.0, float("nan")],
            diluted_eps=[10.0, 20.0, 25.0, 50.0, float("nan")],
            price=100.0, market_cap=1000.0, total_debt=0.0, total_cash=0.0,
        )
        assert out is not None
        # implied EV/EBITDA per year: 1000/100=10, 1000/200=5, 1000/250=4,
        # 1000/500=2 -> sorted [2,4,5,10] -> median (4+5)/2 = 4.5
        assert out["historical_ev_ebitda_median"] == 4.5
        # implied P/E per year: 100/10=10, 100/20=5, 100/25=4, 100/50=2 ->
        # same shape -> median 4.5
        assert out["historical_pe_median"] == 4.5

    def test_no_annual_statement_produces_neither_field(self):
        """A `.income_stmt` fetch failure (or a ticker yfinance has none for)
        must not cost the quarterly-derived fields (R33/R34/R35) — separate
        try/except, verified by checking this call does not raise and simply
        omits the R37 keys."""
        import sys as _sys
        import types as _types

        class _Info(dict):
            def get(self, key, default=None):
                overrides = {"currentPrice": 100.0, "marketCap": 1000.0}
                return overrides.get(key, None)

            def __bool__(self) -> bool:
                return True

        empty_quarterly = pd.DataFrame(
            [[0.0] * 5], index=["Total Revenue"],
            columns=["2026-04-30", "2026-01-31", "2025-10-31", "2025-07-31", "2025-04-30"],
        )

        class _RaisingIncomeStmt:
            @property
            def columns(self):
                raise RuntimeError("boom")

        class _FakeTicker:
            info = _Info()
            quarterly_income_stmt = empty_quarterly
            quarterly_cashflow = empty_quarterly
            income_stmt = _RaisingIncomeStmt()

        _sys.modules["yfinance"] = _types.SimpleNamespace(
            __version__="1.2.3", Ticker=lambda t: _FakeTicker(),
        )
        try:
            out = fmod.fetch_live_fundamentals("TEST")
        finally:
            del _sys.modules["yfinance"]
            fmod.clear_statement_cache()

        assert out is not None  # the whole fetch did not go down
        assert "historical_ev_ebitda_median" not in out
        assert "historical_pe_median" not in out

    def test_only_ebitda_present_produces_only_the_ev_ebitda_half(self):
        """A filer can carry one series without the other — the two halves
        must be independently gated, not all-or-nothing."""
        out = self._run(
            ebitda=[100.0, 200.0, 250.0, 500.0, float("nan")],
            diluted_eps=[float("nan")] * 5,  # no usable EPS year at all
            price=100.0, market_cap=1000.0, total_debt=0.0, total_cash=0.0,
        )
        assert out is not None
        assert "historical_ev_ebitda_median" in out
        assert "historical_pe_median" not in out

    def test_the_raw_intermediate_arrays_never_leak_into_the_returned_dict(self):
        """Regression: caught live during this WP's own development by
        test_prompt_data_parity.py's guard-on-the-guard. `ebitda_history`/
        `eps_history`/their `_years` siblings are computation inputs, never
        a rendered field — they must be popped, not merely consumed."""
        out = self._run(
            ebitda=[100.0, 200.0, 250.0, 500.0, float("nan")],
            diluted_eps=[10.0, 20.0, 25.0, 50.0, float("nan")],
            price=100.0, market_cap=1000.0, total_debt=0.0, total_cash=0.0,
        )
        assert out is not None
        for leaked_key in (
            "ebitda_history", "ebitda_history_years",
            "eps_history", "eps_history_years",
        ):
            assert leaked_key not in out, (
                f"{leaked_key} is a raw computation intermediate and must not "
                "reach the returned fundamentals dict"
            )

    def test_zero_or_negative_ev_withholds_the_ev_ebitda_half_only(self):
        """A net-cash-rich company with debt < cash can have EV <= 0, which
        makes an implied multiple meaningless — withheld, not a crash, and
        the P/E half (which doesn't depend on EV) still renders."""
        out = self._run(
            ebitda=[100.0, 200.0, 250.0, 500.0, float("nan")],
            diluted_eps=[10.0, 20.0, 25.0, 50.0, float("nan")],
            price=100.0, market_cap=1000.0, total_debt=0.0, total_cash=2000.0,
        )
        assert out is not None
        assert "historical_ev_ebitda_median" not in out
        assert "historical_pe_median" in out
