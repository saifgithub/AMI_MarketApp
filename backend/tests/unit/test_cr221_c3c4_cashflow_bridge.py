"""CR221 C3/C4 + DEF400 — the cash-flow bridge, and the FCF it is allowed to state.

Nine request lines from six agents asked for one thing: *"a detailed free cash
flow reconciliation showing changes in working capital versus CapEx"*. Every
operand was already on the `.quarterly_cashflow` frame `fetch_statement_facts`
pulls; only the capex leg survived the function.

Three properties are load-bearing here, and each is a measured failure, not a
hypothetical.

**The parts must add up.** CAT's three named working-capital drivers sum to
-$4,435M against a reported -$1,067M total. Printing the three next to the
total, with nothing said, is a sheet that visibly fails arithmetic — so the
render carries the remainder as `other` and the sum always closes.

**A partial year may not wear a TTM label.** `_ttm_millions` refuses anything
short of four quarters, the same absent-is-not-zero rule the buyback and
dividend rows above it already follow.

**DEF400: `.info`'s `freeCashflow` reconciles to nothing.** Measured
2026-09-03, CAT $5,049M against $13,569M - $4,575M = $8,994M, which the same
frame's own `Free Cash Flow` row confirms to the dollar. It was right when
CR218 shipped (that comment records $8,961M), so this is provider drift on a
rendered number, and the number it drifted into is the one the Room reasons
from: the capital-return line reads **200% of TTM FCF** on the stale figure
against **112%** on the filed one, and "the 200% FCF payout" is verbatim what
the Portfolio Manager built its structural-deficit case on in the CR219 corpus.
"""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.schemas.agents import AgentId
from app.services import fundamentals, room_prompts
from app.services.fundamentals import cashflow_bridge_line

# Caterpillar, measured 2026-09-03, $M. The drivers deliberately do not sum to
# the total — that is the filing, not a fixture convenience.
_CAT = dict(
    operating_cash_flow=13_569, capex=4_575, free_cash_flow=8_994,
    basis="2025-09-30 to 2026-06-30",
    wc_change=-1_067, wc_receivables=-5_001, wc_inventory=-2_391, wc_payables=2_957,
)


def _line(**overrides) -> str | None:
    args = {**_CAT, **overrides}
    return cashflow_bridge_line(
        args["operating_cash_flow"], args["capex"], args["free_cash_flow"],
        args["basis"], args["wc_change"], args["wc_receivables"],
        args["wc_inventory"], args["wc_payables"],
        args.get("sheet_free_cash_flow"),
    )


def _profile() -> dict:
    return {
        "field_state": {
            k: "live" for k in (
                "operating_cash_flow_ttm", "capex_ttm", "free_cash_flow_ttm",
                "cashflow_ttm_basis", "wc_change_ttm", "wc_receivables_ttm",
                "wc_inventory_ttm", "wc_payables_ttm", "free_cash_flow",
            )
        },
        "operating_cash_flow_ttm": _CAT["operating_cash_flow"],
        "capex_ttm": _CAT["capex"],
        "free_cash_flow_ttm": _CAT["free_cash_flow"],
        "cashflow_ttm_basis": _CAT["basis"],
        "wc_change_ttm": _CAT["wc_change"],
        "wc_receivables_ttm": _CAT["wc_receivables"],
        "wc_inventory_ttm": _CAT["wc_inventory"],
        "wc_payables_ttm": _CAT["wc_payables"],
        "free_cash_flow": 5_049,
    }


@pytest.fixture(autouse=True)
def _flags_restored():
    before = (settings.room_cashflow_bridge_enabled,
              settings.fundamentals_fcf_from_statements_enabled)
    yield
    (settings.room_cashflow_bridge_enabled,
     settings.fundamentals_fcf_from_statements_enabled) = before


# ── The subtraction ──────────────────────────────────────────────────────


def test_the_bridge_states_every_operand_not_just_the_result() -> None:
    line = _line()
    assert "operating cash flow $13,569M" in line
    assert "capex $4,575M" in line
    assert "free cash flow $8,994M" in line
    assert "2025-09-30 to 2026-06-30" in line


def test_a_missing_operand_withholds_the_whole_bridge() -> None:
    """Half a subtraction is not a partial answer, it is a wrong one."""
    assert _line(operating_cash_flow=None) is None
    assert _line(capex=None) is None
    assert _line(free_cash_flow=None) is None


def test_the_bridge_survives_a_filer_that_reports_no_working_capital_rows() -> None:
    """XOM, measured: the frame carries no `Change In ...` rows at all."""
    line = _line(wc_change=None, wc_receivables=None, wc_inventory=None,
                 wc_payables=None)
    assert "free cash flow $8,994M" in line
    assert "working capital" not in line


# ── The working-capital detail ───────────────────────────────────────────


def test_the_named_drivers_and_the_remainder_sum_to_the_stated_total() -> None:
    line = _line()
    assert "working capital consumed $1,067M" in line
    assert "receivables -$5,001M" in line
    assert "inventory -$2,391M" in line
    assert "payables +$2,957M" in line
    # -5,001 - 2,391 + 2,957 = -4,435; -1,067 - (-4,435) = +3,368.
    assert "other +$3,368M" in line


def test_no_remainder_is_printed_when_the_named_drivers_already_close() -> None:
    line = _line(wc_change=-4_435)
    assert "other" not in line


def test_a_positive_change_is_released_not_consumed() -> None:
    """The sign is the statement's own; inverting it inverts the finding."""
    assert "working capital released $1,067M" in _line(wc_change=1_067)


def test_a_driver_the_filer_omits_is_absorbed_by_the_remainder() -> None:
    line = _line(wc_inventory=None)
    assert "inventory" not in line
    assert "other +$977M" in line  # -1,067 - (-5,001 + 2,957)


# ── DEF400's tripwire ────────────────────────────────────────────────────


def test_a_diverging_sheet_figure_is_named_in_the_line() -> None:
    line = _line(sheet_free_cash_flow=5_049)
    assert "$5,049M stated above" in line
    assert "does not reconcile" in line
    assert "$8,994M is what the filed statements support" in line


def test_an_agreeing_sheet_figure_says_nothing() -> None:
    """Silence is correct here — there is no contradiction to warn about."""
    assert "does not reconcile" not in _line(sheet_free_cash_flow=8_994)
    assert "does not reconcile" not in _line(sheet_free_cash_flow=8_900)  # 1.0%


# ── The four-quarter rule ────────────────────────────────────────────────


@pytest.mark.parametrize("series", [
    None,
    [1.0, 2.0, 3.0],                 # three quarters
    [1.0, 2.0, None, 4.0],           # a hole in the middle
    [None, 2.0, 3.0, 4.0],           # the newest quarter unreported
])
def test_an_incomplete_year_yields_no_ttm_figure(series) -> None:
    assert fundamentals._ttm_millions(series) is None


def test_only_the_trailing_four_quarters_are_summed() -> None:
    """A fifth column is history, not part of the trailing year."""
    assert fundamentals._ttm_millions([1e6, 2e6, 3e6, 4e6, 99e6]) == 10


# ── The render seam ──────────────────────────────────────────────────────


def _sheet() -> str:
    return room_prompts._format_profile(_profile(), AgentId.FUNDAMENTALS_ANALYST)


def test_the_flag_is_off_by_default() -> None:
    assert settings.room_cashflow_bridge_enabled is False
    assert settings.fundamentals_fcf_from_statements_enabled is False


def test_the_same_profile_renders_nothing_with_the_flag_off() -> None:
    settings.room_cashflow_bridge_enabled = False
    assert "Cash-flow bridge" not in _sheet()


def test_the_bridge_appears_on_the_room_sheet_with_the_flag_on() -> None:
    settings.room_cashflow_bridge_enabled = True
    sheet = _sheet()
    assert "Cash-flow bridge (LIVE)" in sheet
    assert "operating cash flow $13,569M - capex $4,575M = free cash flow $8,994M" in sheet
    assert "other +$3,368M" in sheet
    assert "$5,049M stated above" in sheet, (
        "the sheet's own FCF still comes from `.info` while DEF400's fix is off, "
        "so the bridge must name the contradiction rather than sit beside it"
    )


def test_a_profile_whose_fields_are_not_live_renders_no_bridge() -> None:
    """CR104/D8 — presence is not provenance, on this line like every other."""
    settings.room_cashflow_bridge_enabled = True
    profile = _profile()
    profile["field_state"] = {}
    assert "Cash-flow bridge" not in room_prompts._format_profile(
        profile, AgentId.FUNDAMENTALS_ANALYST)


# ── DEF400's substitution ────────────────────────────────────────────────

_INFO = {
    # `currentPrice`/`trailingPE` only because `fetch_live_fundamentals`
    # treats a ticker missing BOTH as unknown to yfinance and returns None.
    "currentPrice": 771.39,
    "trailingPE": 34.0,
    "freeCashflow": 5_049_000_000,      # `.info`, measured 2026-09-03
    "marketCap": 364_191_000_000,
}
_STATEMENTS = {
    "free_cash_flow_ttm": 8_994,        # OCF - capex, off the same provider
    "buyback_ttm": 7_302,
    "dividends_paid_ttm": 2_812,
}


def _fake_yfinance(info: dict):
    """Only `.info` — `fetch_statement_facts` is patched separately below."""
    import types

    class _Ticker:
        def __init__(self, symbol): self.info = dict(info)

    module = types.ModuleType("yfinance")
    module.Ticker = _Ticker
    module.__version__ = "0.2.0"
    return module


def _fundamentals(monkeypatch, *, derived: bool, statements=None) -> dict:
    import sys

    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(settings, "fundamentals_fcf_from_statements_enabled", derived)
    monkeypatch.setitem(sys.modules, "yfinance", _fake_yfinance(_INFO))
    monkeypatch.setattr(
        fundamentals, "fetch_statement_facts",
        lambda t: dict(_STATEMENTS if statements is None else statements),
    )
    monkeypatch.setattr(fundamentals, "_warn_if_yfinance_convention_stale", lambda m: None)
    return fundamentals.fetch_live_fundamentals("CAT") or {}


def test_def400_off_leaves_the_shipped_numbers_exactly_where_they_were() -> None:
    assert settings.fundamentals_fcf_from_statements_enabled is False


def test_def400_off_renders_the_vendor_figure(monkeypatch) -> None:
    out = _fundamentals(monkeypatch, derived=False)
    assert out["free_cash_flow"] == 5_049
    assert out["fcf_yield"] == 1.4
    assert out["capital_return_pct_fcf"] == 200


def test_def400_on_moves_the_fcf_and_everything_derived_from_it(monkeypatch) -> None:
    """Not the FCF alone: the yield and CR218's payout share ride on it too.

    200% of free cash flow is a company funding its dividend out of the balance
    sheet; 112% is a normal cyclical year. The Room drew the first conclusion
    from a figure that was never the subtraction it claimed to be.
    """
    out = _fundamentals(monkeypatch, derived=True)
    assert out["free_cash_flow"] == 8_994
    assert out["fcf_yield"] == 2.5
    assert out["capital_return_pct_fcf"] == 112


def test_def400_falls_back_rather_than_blanking_when_the_quarters_are_short(
    monkeypatch,
) -> None:
    """A filer with three reported quarters keeps the figure it always had."""
    short = {k: v for k, v in _STATEMENTS.items() if k != "free_cash_flow_ttm"}
    out = _fundamentals(monkeypatch, derived=True, statements=short)
    assert out["free_cash_flow"] == 5_049
    assert out["capital_return_pct_fcf"] == 200
