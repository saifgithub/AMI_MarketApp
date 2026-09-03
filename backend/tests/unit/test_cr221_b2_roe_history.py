"""CR221 B2 — return on equity across the cycle, and why the median matters.

The Research Manager asked for *"full cycle (10-year) historical median
valuation multiples (P/E, EV/EBITDA) and median ROE"*. R37 shipped the
multiples; this is the clause after the "and".

It exists to make a figure the sheet ALREADY carries readable. Caterpillar's
current 41.7% is a weak year against a 47.6% four-year median and an
exceptional one against a 20% median, and a point-in-time ratio cannot say
which — the same reason margin TREND had to join margin LEVEL (CR145 Tier A).

Two rules with measured failures behind them:

**The join is by period, never by index.** ExxonMobil returns four balance-sheet
columns against five income-statement columns (measured 2026-09-03), so zipping
positionally pairs each year's profit with the previous year's equity and every
ROE in the series is silently wrong.

**One definition of one ratio per sheet.** Year-end equity, matching the
`return_on_equity` already rendered — not average equity, which is equally
defensible in isolation and would put two different numbers called ROE on one
page.
"""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.schemas.agents import AgentId
from app.services import fundamentals, room_prompts
from app.services.fundamentals import roe_history_line

# Caterpillar, measured 2026-09-03.
_YEARS = ["2025", "2024", "2023", "2022"]
_ROE = [41.7, 55.4, 53.0, 42.3]
_MEDIAN = 47.6


@pytest.fixture(autouse=True)
def _flag_restored():
    before = settings.room_roe_history_enabled
    yield
    settings.room_roe_history_enabled = before


def test_the_line_carries_the_series_the_median_and_the_basis() -> None:
    line = roe_history_line(_YEARS, _ROE, _MEDIAN, 41.7)
    assert "FY2025 41.7% · FY2024 55.4% · FY2023 53.0% · FY2022 42.3%" in line
    assert "4-year median 47.6%" in line
    assert "currently 41.7%" in line
    assert "each year net income over year-end equity" in line


def test_the_median_still_renders_without_a_current_figure() -> None:
    line = roe_history_line(_YEARS, _ROE, _MEDIAN, None)
    assert "4-year median 47.6%" in line
    assert "currently" not in line


def test_a_divergent_vendor_roe_is_named_not_labelled_with_the_series_basis() -> None:
    """The measured CAT case: 57.0% vendor against FY2025's filed 41.7%.

    The first version of this line appended `currently 57%` and then closed
    with "net income over year-end equity", which is the series' basis and not
    the vendor figure's — DEF400's shape on a second field. It survived because
    THIS fixture used to pass 41.7 for both, so the divergent case never ran.
    """
    line = roe_history_line(_YEARS, _ROE, _MEDIAN, 57.0)
    assert "currently 57.0%" not in line
    assert "vendor TTM ratio on an undisclosed equity basis" in line
    assert "FY2025's 41.7% is what the filed statements support" in line


def test_a_current_figure_inside_the_band_still_reads_as_agreement() -> None:
    """1.5 points is drift, not a different basis — do not cry divergence."""
    line = roe_history_line(_YEARS, _ROE, _MEDIAN, 43.2)
    assert "currently 43.2%" in line
    assert "vendor TTM ratio" not in line


def test_two_years_is_not_a_cycle() -> None:
    assert roe_history_line(_YEARS[:2], _ROE[:2], 48.5, 41.7) is None


def test_a_missing_median_withholds_the_line() -> None:
    """The median IS the ask; a bare series without it answers a different one."""
    assert roe_history_line(_YEARS, _ROE, None, 41.7) is None


# ── The fetcher ──────────────────────────────────────────────────────────


class _Ticker:
    def __init__(self, balance, income):
        import pandas as pd

        self.balance_sheet = balance
        self.income_stmt = income
        self.cashflow = pd.DataFrame()
        self.quarterly_income_stmt = pd.DataFrame()
        self.quarterly_cashflow = pd.DataFrame()
        self.eps_trend = None
        self.earnings_history = None


def _fetch(monkeypatch, equity, equity_periods, net_income, income_periods) -> dict:
    import sys
    import types

    import pandas as pd

    balance = pd.DataFrame([equity], index=["Stockholders Equity"],
                           columns=equity_periods)
    income = pd.DataFrame(
        [net_income, [1.0] * len(income_periods)],
        index=["Net Income", "Diluted EPS"], columns=income_periods,
    )
    module = types.ModuleType("yfinance")
    module.Ticker = lambda symbol: _Ticker(balance, income)
    module.__version__ = "0.2.0"
    monkeypatch.setitem(sys.modules, "yfinance", module)
    fundamentals._statements_cache.clear()
    return fundamentals._fetch_statement_facts_uncached("CAT") or {}


_FY = ["2025-12-31", "2024-12-31", "2023-12-31", "2022-12-31"]
_EQUITY = [21.318e9, 19.491e9, 19.494e9, 15.869e9]
_NET_INCOME = [8.884e9, 10.792e9, 10.335e9, 6.705e9]


def test_the_fetcher_reproduces_the_measured_series(monkeypatch) -> None:
    out = _fetch(monkeypatch, _EQUITY, _FY, _NET_INCOME, _FY)
    assert out["roe_history_years"] == _YEARS
    assert out["roe_history_pct"] == _ROE
    assert out["roe_median_pct"] == _MEDIAN


def test_frames_of_different_lengths_join_on_the_period_not_the_index(
    monkeypatch,
) -> None:
    """XOM's shape. A positional zip would pair FY2025 profit with FY2024 equity."""
    out = _fetch(
        monkeypatch,
        _EQUITY[1:], _FY[1:],            # balance sheet is one year shorter
        _NET_INCOME, _FY,
    )
    assert out["roe_history_years"] == ["2024", "2023", "2022"]
    assert out["roe_history_pct"] == [55.4, 53.0, 42.3]


def test_a_year_with_negative_equity_is_dropped(monkeypatch) -> None:
    """ROE over negative equity has a sign but no meaning."""
    out = _fetch(monkeypatch, [-1.0e9, *_EQUITY[1:]], _FY, _NET_INCOME, _FY)
    assert out["roe_history_years"] == ["2024", "2023", "2022"]


def test_fewer_than_three_usable_years_produces_nothing(monkeypatch) -> None:
    out = _fetch(monkeypatch, _EQUITY[:2], _FY[:2], _NET_INCOME[:2], _FY[:2])
    assert "roe_history_pct" not in out
    assert "roe_median_pct" not in out


# ── The render seam ──────────────────────────────────────────────────────


def _profile() -> dict:
    return {
        "field_state": {k: "live" for k in (
            "roe_history_years", "roe_history_pct", "roe_median_pct",
            "return_on_equity")},
        "roe_history_years": _YEARS,
        "roe_history_pct": _ROE,
        "roe_median_pct": _MEDIAN,
        "return_on_equity": 41.7,
    }


def test_the_flag_is_off_by_default() -> None:
    assert settings.room_roe_history_enabled is False


def test_nothing_renders_with_the_flag_off() -> None:
    settings.room_roe_history_enabled = False
    assert "Return on equity history" not in room_prompts._format_profile(
        _profile(), AgentId.FUNDAMENTALS_ANALYST)


def test_the_line_appears_with_the_flag_on() -> None:
    settings.room_roe_history_enabled = True
    sheet = room_prompts._format_profile(_profile(), AgentId.FUNDAMENTALS_ANALYST)
    assert "Return on equity history (LIVE)" in sheet
    assert "4-year median 47.6%" in sheet


def test_presence_is_not_provenance() -> None:
    settings.room_roe_history_enabled = True
    profile = _profile()
    profile["field_state"] = {}
    assert "Return on equity history" not in room_prompts._format_profile(
        profile, AgentId.FUNDAMENTALS_ANALYST)
