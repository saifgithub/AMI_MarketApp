"""CR221 C2/C5 — the multi-year cash-flow series behind the trailing figure.

Five request lines from four agents wanted the same thing and none of them
could be answered from one TTM number: *"historical multi-year averages for
free cash flow and capital expenditure"*, *"free cash flow conversion rate
history over the past 5 years"*, *"FCF as a percentage of net income over
time"*. `tk.cashflow` is the annual sibling of the frame the module already
pulls, so this costs no new endpoint — the same "one more property on the same
Ticker" shape `income_stmt` established for R37.

Three rules are pinned here because each one has a measured failure behind it.

**Free cash flow is derived, never read.** The frame carries a `Free Cash Flow`
row that agrees with the subtraction on every filer checked, and a vendor
scalar (`.info.freeCashflow`) that agrees with nothing — DEF400. Where a stated
figure and a checkable one can disagree, the sheet states the checkable one.

**The window is measured, not assumed.** Every filer returns five annual
columns and CAT's oldest is NaN, so "5-year average" over four usable years is
a wrong label on a right number. `len()` of what survived is the only number
allowed to appear.

**A loss year does not get a conversion percentage.** FCF over negative net
income is arithmetic, not a ratio, and one impossible figure beside three
honest ones is read as part of the series.
"""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.schemas.agents import AgentId
from app.services import fundamentals, room_prompts
from app.services.fundamentals import fcf_conversion_line, fcf_history_line

# Caterpillar, measured 2026-09-03 off `tk.cashflow` / `tk.income_stmt`, $M.
_YEARS = ["2025", "2024", "2023", "2022"]
_FCF = [7_453, 8_820, 9_793, 5_167]
_CAPEX = [4_286, 3_215, 3_092, 2_599]
_CONVERSION = [84, 82, 95, 77]


@pytest.fixture(autouse=True)
def _flags_restored():
    before = (settings.room_fcf_history_enabled, settings.room_fcf_conversion_enabled)
    yield
    (settings.room_fcf_history_enabled,
     settings.room_fcf_conversion_enabled) = before


# ── C2: the series and its averages ──────────────────────────────────────


def test_the_series_carries_every_year_and_both_averages() -> None:
    line = fcf_history_line(_YEARS, _FCF, _CAPEX)
    assert "FY2025 $7,453M" in line and "FY2022 $5,167M" in line
    assert "4-year average $7,808M" in line          # 31,233 / 4
    assert "capex FY2025 $4,286M" in line
    assert "average $3,298M" in line                 # 13,192 / 4
    assert "each year operating cash flow less capex" in line


def test_the_window_is_the_years_that_survived_not_the_columns_returned() -> None:
    """CAT returns five columns and four usable years. Only four may be claimed."""
    line = fcf_history_line(_YEARS[:3], _FCF[:3], _CAPEX[:3])
    assert "3-year average" in line
    assert "4-year" not in line and "5-year" not in line


def test_two_years_is_a_comparison_not_a_history() -> None:
    assert fcf_history_line(_YEARS[:2], _FCF[:2], _CAPEX[:2]) is None


def test_the_fcf_series_survives_a_missing_capex_series() -> None:
    line = fcf_history_line(_YEARS, _FCF, None)
    assert "FY2025 $7,453M" in line
    assert "capex" in line, "the basis note names capex even with no capex series"
    assert "average $3,298M" not in line


def test_a_capex_series_of_a_different_length_is_dropped_not_zipped() -> None:
    """Silently zipping unequal series would pair a year with another year's capex."""
    line = fcf_history_line(_YEARS, _FCF, _CAPEX[:2])
    assert "capex FY2025" not in line


# ── C5: conversion ───────────────────────────────────────────────────────


def test_conversion_states_each_year_against_net_income() -> None:
    line = fcf_conversion_line(_YEARS, _CONVERSION)
    assert "FY2025 84% · FY2024 82% · FY2023 95% · FY2022 77% of net income" in line
    assert "omitted" not in line


def test_a_loss_year_is_omitted_and_the_omission_is_stated() -> None:
    line = fcf_conversion_line(_YEARS, [84, None, 95, 77])
    assert "FY2024" not in line
    assert "1 loss-making year omitted" in line


def test_two_loss_years_pluralise() -> None:
    line = fcf_conversion_line(_YEARS + ["2021"], [84, None, 95, 77, None])
    assert "2 loss-making years omitted" in line


def test_fewer_than_three_usable_years_yields_no_conversion() -> None:
    assert fcf_conversion_line(_YEARS, [84, None, None, 77]) is None


# ── The fetcher ──────────────────────────────────────────────────────────


def _frames(ocf, capex, net_income, periods=None):
    import pandas as pd

    periods = periods or ["2025-12-31", "2024-12-31", "2023-12-31", "2022-12-31"]
    cash = pd.DataFrame(
        [ocf, capex], index=["Operating Cash Flow", "Capital Expenditure"],
        columns=periods,
    )
    income = pd.DataFrame(
        [net_income, [1.0] * len(periods)],
        index=["Net Income", "Diluted EPS"], columns=periods,
    )
    return cash, income


class _Ticker:
    def __init__(self, cash, income):
        import pandas as pd

        self.cashflow = cash
        self.income_stmt = income
        self.quarterly_income_stmt = pd.DataFrame()
        self.quarterly_cashflow = pd.DataFrame()
        self.eps_trend = None
        self.earnings_history = None


def _fetch(monkeypatch, ocf, capex, net_income, periods=None) -> dict:
    import sys
    import types

    cash, income = _frames(ocf, capex, net_income, periods)
    module = types.ModuleType("yfinance")
    module.Ticker = lambda symbol: _Ticker(cash, income)
    module.__version__ = "0.2.0"
    monkeypatch.setitem(sys.modules, "yfinance", module)
    fundamentals._statements_cache.clear()
    return fundamentals._fetch_statement_facts_uncached("CAT") or {}


_OCF = [11.739e9, 12.035e9, 12.885e9, 7.766e9]
_CAP = [-4.286e9, -3.215e9, -3.092e9, -2.599e9]
_NI = [8.884e9, 10.792e9, 10.335e9, 6.705e9]


def test_the_fetcher_derives_fcf_and_joins_conversion_on_period(monkeypatch) -> None:
    out = _fetch(monkeypatch, _OCF, _CAP, _NI)
    assert out["fcf_history_years"] == _YEARS
    assert out["fcf_history"] == _FCF
    assert out["capex_history"] == _CAPEX
    assert out["fcf_conversion_pct"] == _CONVERSION


def test_a_year_missing_either_leg_is_dropped_from_every_series(monkeypatch) -> None:
    """A year with no capex has no derivable FCF, so it cannot appear at all."""
    out = _fetch(monkeypatch, _OCF, [_CAP[0], None, _CAP[2], _CAP[3]], _NI)
    assert out["fcf_history_years"] == ["2025", "2023", "2022"]
    assert len(out["fcf_history"]) == len(out["capex_history"]) == 3


def test_fewer_than_three_derivable_years_produces_no_series_at_all(monkeypatch) -> None:
    out = _fetch(monkeypatch, _OCF, [_CAP[0], _CAP[1], None, None], _NI)
    assert "fcf_history" not in out
    assert "capex_history" not in out
    assert "fcf_conversion_pct" not in out


def test_a_loss_year_gets_no_conversion_but_keeps_its_fcf(monkeypatch) -> None:
    out = _fetch(monkeypatch, _OCF, _CAP, [_NI[0], -1.0e9, _NI[2], _NI[3]])
    assert out["fcf_history"] == _FCF, "the series itself is unaffected"
    assert out["fcf_conversion_pct"] == [84, None, 95, 77]


def test_conversion_is_withheld_when_too_few_years_are_profitable(monkeypatch) -> None:
    out = _fetch(monkeypatch, _OCF, _CAP, [_NI[0], -1.0e9, -1.0e9, _NI[3]])
    assert out["fcf_history"] == _FCF
    assert "fcf_conversion_pct" not in out


# ── The render seam ──────────────────────────────────────────────────────


def _profile() -> dict:
    return {
        "field_state": {k: "live" for k in (
            "fcf_history_years", "fcf_history", "capex_history", "fcf_conversion_pct")},
        "fcf_history_years": _YEARS,
        "fcf_history": _FCF,
        "capex_history": _CAPEX,
        "fcf_conversion_pct": _CONVERSION,
    }


def _sheet(**flags) -> str:
    for name, value in flags.items():
        setattr(settings, name, value)
    return room_prompts._format_profile(_profile(), AgentId.FUNDAMENTALS_ANALYST)


def test_both_flags_are_off_by_default() -> None:
    assert settings.room_fcf_history_enabled is False
    assert settings.room_fcf_conversion_enabled is False


def test_neither_line_renders_with_the_flags_off() -> None:
    sheet = _sheet(room_fcf_history_enabled=False, room_fcf_conversion_enabled=False)
    assert "Free cash flow history" not in sheet
    assert "FCF conversion" not in sheet


def test_each_flag_gates_only_its_own_item() -> None:
    """§7 attributes demand extinction per item; one switch for two would not."""
    sheet = _sheet(room_fcf_history_enabled=True, room_fcf_conversion_enabled=False)
    assert "Free cash flow history (LIVE)" in sheet
    assert "FCF conversion" not in sheet

    sheet = _sheet(room_fcf_history_enabled=False, room_fcf_conversion_enabled=True)
    assert "Free cash flow history" not in sheet
    assert "FCF conversion (LIVE)" in sheet


def test_presence_is_not_provenance() -> None:
    """CR104/D8 — on these lines like every other."""
    settings.room_fcf_history_enabled = True
    settings.room_fcf_conversion_enabled = True
    profile = _profile()
    profile["field_state"] = {}
    sheet = room_prompts._format_profile(profile, AgentId.FUNDAMENTALS_ANALYST)
    assert "Free cash flow history" not in sheet
    assert "FCF conversion" not in sheet
