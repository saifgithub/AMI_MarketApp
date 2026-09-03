"""Is the sheet's interest expense the filer's interest expense? (DEF399, CR221 A3)

CR221 §4 ruled item A3 (cost of debt) IN HAND — "divides the `Interest Expense`
R33 already reads". This script tested that premise before building on it, and
the premise is false for one cohort.

`fundamentals.py:385` reads yfinance's `Interest Expense` /
`Interest Expense Non Operating` rows. For most filers that IS consolidated
interest expense. For an issuer whose captive-finance arm books its interest
inside operating costs, it is only the leftover non-operating line — and the
shipped `interest_coverage` field divides EBIT by that stub, overstating
coverage in the reassuring direction.

Two populations are measured, because the answer differs sharply between them:

  * a 25-name spread across the CR035 benchmark universe (every 6th ticker) —
    the base rate, and it is low;
  * the captive-finance cohort — where the failure actually lives.

The reference figure is the filer's own annual number from SEC `companyfacts`:
`InterestExpense` where tagged, else `InterestPaid`/`InterestPaidNet` from the
cash-flow supplemental. Caterpillar tags NO income-statement interest concept
at all — its two interest lines are dimensional (Machinery & Energy vs
Financial Products), and companyfacts serves the consolidated non-dimensional
fact only, which is CR221 §6's finding arriving a second time.

Read-only. Network: yfinance + one companyfacts GET per ticker, rate-limited.

    backend/.venv/bin/python docs/forward_planning/CR221_room_data_demand_sourcing/evidence/interest_expense_check.py [--cohort|--sample]
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend"))

import yfinance as yf  # noqa: E402

from app.services.fundamentals import _stmt_series  # noqa: E402

UA = "AMI Trade research (saiful.mazli@gmail.com)"
TICKERS_FILE = (
    Path(__file__).resolve().parents[3]
    / "docs/forward_planning/CR035_room_benchmark/tickers_150.txt"
)
# Issuers with a captive-finance arm, plus Deere and Textron as the controls
# that tag consolidated interest and therefore read correctly.
COHORT = ("CAT", "DE", "F", "GM", "PCAR", "HOG", "TXT", "AGCO", "CNH", "TSLA")
UNDERSTATED_BELOW = 0.70

# BOTH are printed, never one silently preferred. They disagree by 10x on
# Harley-Davidson (`InterestExpense` 31M vs `InterestPaidNet` 331M) because the
# income-statement tag there is itself only the non-finance line — the same
# dimensional split that defeats the yfinance read. A ticker whose two
# references disagree is reported AMBIGUOUS rather than scored.
_ACCRUAL_TAGS = ("InterestExpense",)
_CASH_TAGS = ("InterestPaidNet", "InterestPaid")
AMBIGUOUS_ABOVE = 2.0


def _cik_map() -> dict[str, int]:
    req = urllib.request.Request(
        "https://www.sec.gov/files/company_tickers.json", headers={"User-Agent": UA}
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return {v["ticker"]: v["cik_str"] for v in json.load(r).values()}


def edgar_annual_interest(
    ticker: str, cik: dict[str, int]
) -> dict[str, tuple[str, float]]:
    """`{"accrual": (tag, value), "cash": (tag, value)}` — whichever resolve."""
    if ticker not in cik:
        return {}
    req = urllib.request.Request(
        f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik[ticker]:010d}.json",
        headers={"User-Agent": UA},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            us_gaap = json.load(r)["facts"].get("us-gaap", {})
    except Exception:
        return {}

    def first(tags: tuple[str, ...]) -> tuple[str, float] | None:
        for tag in tags:
            for series in us_gaap.get(tag, {}).get("units", {}).values():
                annual = [
                    p for p in series
                    if p.get("start")
                    and (dt.date.fromisoformat(p["end"])
                         - dt.date.fromisoformat(p["start"])).days > 330
                ]
                if annual:
                    newest = max(annual, key=lambda p: (p["end"], p["filed"]))
                    return tag, newest["val"]
        return None

    out = {}
    for key, tags in (("accrual", _ACCRUAL_TAGS), ("cash", _CASH_TAGS)):
        found = first(tags)
        if found:
            out[key] = found
    return out


def yfinance_view(ticker: str) -> tuple[float | None, float | None]:
    """(TTM interest expense, the shipped `interest_coverage`) as the sheet sees them."""
    try:
        income = yf.Ticker(ticker).quarterly_income_stmt
        interest = _stmt_series(income, "Interest Expense", "Interest Expense Non Operating")
        ebit = _stmt_series(income, "Operating Income", "Total Operating Income As Reported")
    except Exception:
        return None, None
    ttm = (
        None
        if not interest or len(interest) < 4 or any(v is None for v in interest[:4])
        else abs(sum(interest[:4]))
    )
    coverage = (
        round(ebit[0] / abs(interest[0]), 1)
        if ebit and interest and ebit[0] is not None and interest[0]
        else None
    )
    return ttm, coverage


def run(tickers: tuple[str, ...], label: str) -> int:
    cik = _cik_map()
    print(f"\n=== {label} ({len(tickers)} tickers) ===")
    print(f"{'tkr':6s} {'yf TTM int':>12s} {'InterestExpense':>16s} "
          f"{'InterestPaid*':>14s} {'ratio':>7s} {'shipped cov':>12s}")
    understated = comparable = ambiguous = 0
    for ticker in tickers:
        found = edgar_annual_interest(ticker, cik)
        time.sleep(0.15)
        ttm, coverage = yfinance_view(ticker)
        accrual = abs(found["accrual"][1]) if "accrual" in found else None
        cash = abs(found["cash"][1]) if "cash" in found else None

        note, ratio = "", None
        if accrual and cash and max(accrual, cash) / min(accrual, cash) > AMBIGUOUS_ABOVE:
            ambiguous += 1
            note = "   <-- AMBIGUOUS reference, not scored"
        elif ttm and (accrual or cash):
            comparable += 1
            ratio = ttm / (accrual or cash)
            if ratio < UNDERSTATED_BELOW:
                understated += 1
                note = "   <-- UNDERSTATED"
        print(
            f"{ticker:6s} {('-' if ttm is None else f'{ttm/1e6:,.0f}M'):>12s} "
            f"{('-' if accrual is None else f'{accrual/1e6:,.0f}M'):>16s} "
            f"{('-' if cash is None else f'{cash/1e6:,.0f}M'):>14s} "
            f"{('-' if ratio is None else f'{ratio:.2f}x'):>7s} "
            f"{('-' if coverage is None else f'{coverage}x'):>12s}{note}"
        )
    print(f"\nscored: {comparable}   understated below {UNDERSTATED_BELOW:.2f}x: "
          f"{understated}   ambiguous reference: {ambiguous}")
    return understated


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "--both"
    if which in ("--cohort", "--both"):
        run(COHORT, "captive-finance cohort")
    if which in ("--sample", "--both"):
        universe = [
            line.strip()
            for line in TICKERS_FILE.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]
        run(tuple(universe[::6][:25]), "CR035 universe, every 6th name")
    return 0


if __name__ == "__main__":
    sys.exit(main())
