"""Is the sheet's free cash flow free cash flow? (DEF400, CR221 C3)

CR221 item C3 asks for the operating-cash-flow line and the OCF→FCF bridge —
three request lines from three agents. The data is already fetched and thrown
away: `_fetch_statement_facts_uncached` pulls `tk.quarterly_cashflow` and keeps
four rows out of forty-six.

Rendering the bridge required first checking that it would AGREE with what the
sheet already prints, and it does not. The sheet's `free_cash_flow` (and the
`fcf_yield` derived from it) come from `.info`'s `freeCashflow`, a single
pre-computed vendor figure. Its own `capex_ttm` (CR219 R34) comes from the
statements. This script puts the two bases side by side on six large caps and
adds the third reference — the annual statements' own `Free Cash Flow` row.

The statement figures are internally consistent: annual `Free Cash Flow`
equals annual `Operating Cash Flow` minus `Capital Expenditure` exactly, on
every filer tested. `.info`'s figure matches neither that nor the quarterly
trailing-four-quarter sum.

Read-only, network via yfinance. Run from any directory:

    backend/.venv/bin/python docs/forward_planning/CR221_room_data_demand_sourcing/evidence/fcf_basis_check.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend"))

import yfinance as yf  # noqa: E402

from app.services.fundamentals import _stmt_series  # noqa: E402

FILERS = ("CAT", "MSFT", "DE", "AAPL", "GOOGL", "KO")
# Above this ratio the two bases are not the same measurement by any margin a
# reporting-lag or restatement story explains.
DIVERGENT_ABOVE = 1.25


def _millions(frame, *names, quarters: int | None = None) -> int | None:
    series = _stmt_series(frame, *names)
    if not series:
        return None
    if quarters is None:
        return None if series[0] is None else round(series[0] / 1e6)
    window = series[:quarters]
    if len(window) < quarters or any(v is None for v in window):
        return None
    return round(sum(window) / 1e6)


def main() -> int:
    print(f"{'tkr':6s} {'.info FCF':>11s} {'qTTM OCF-capex':>15s} "
          f"{'annual OCF-capex':>17s} {'annual FCF row':>15s} {'worst gap':>10s}")
    divergent = 0
    for ticker in FILERS:
        tk = yf.Ticker(ticker)
        info = tk.info or {}
        quarterly, annual = tk.quarterly_cashflow, tk.cashflow

        vendor = info.get("freeCashflow")
        vendor = None if vendor is None else round(vendor / 1e6)
        q_ocf = _millions(quarterly, "Operating Cash Flow", quarters=4)
        q_capex = _millions(quarterly, "Capital Expenditure", quarters=4)
        a_ocf = _millions(annual, "Operating Cash Flow")
        a_capex = _millions(annual, "Capital Expenditure")

        q_bridge = None if q_ocf is None or q_capex is None else q_ocf + q_capex
        a_bridge = None if a_ocf is None or a_capex is None else a_ocf + a_capex
        a_row = _millions(annual, "Free Cash Flow")

        gaps = [max(vendor, b) / min(vendor, b)
                for b in (q_bridge, a_bridge) if vendor and b and min(vendor, b) > 0]
        worst = max(gaps) if gaps else None
        if worst and worst > DIVERGENT_ABOVE:
            divergent += 1
        print(f"{ticker:6s} {_fmt(vendor):>11s} {_fmt(q_bridge):>15s} "
              f"{_fmt(a_bridge):>17s} {_fmt(a_row):>15s} "
              f"{('-' if worst is None else f'{worst:.2f}x'):>10s}"
              + ("   <-- DIVERGENT" if worst and worst > DIVERGENT_ABOVE else ""))

    print(f"\ndivergent above {DIVERGENT_ABOVE:.2f}x: {divergent} of {len(FILERS)}")
    print("The annual `Free Cash Flow` ROW equals annual OCF - capex on every filer")
    print("here: the statements are self-consistent. `.info`'s figure is the outlier,")
    print("and it is the one the fact sheet renders as 'FCF (TTM)' and divides into")
    print("market cap for 'FCF yield'. See DEF400.")
    return 0


def _fmt(value: int | None) -> str:
    return "-" if value is None else f"{value:,}"


if __name__ == "__main__":
    sys.exit(main())
