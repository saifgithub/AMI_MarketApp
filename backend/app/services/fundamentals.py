"""Live ticker fundamentals — shared between Room and 1-on-1 agent paths.

Both surfaces need the same data shape: numeric facts (P/E, growth, FCF,
profit margin, net cash, 52-week range) the LLM is otherwise prone to
hallucinate from training memory.

  - The Room runner pulls this once per Convene and injects it into
    every agent's system prompt.
  - The 1-on-1 runner pulls per-message: it extracts plausible tickers
    from the user's text and appends a live-data block for each.

Gated on `settings.use_real_market_data` so tests stay deterministic
and yfinance outages don't break either surface.
"""

from __future__ import annotations

import math
import re
import statistics
import time
from datetime import date, datetime, timezone
from threading import RLock
from typing import Any

from app.core.config import settings
from app.core.logging import logger
from app.core.time import relative_day_phrase
from app.schemas import AgentId
from app.services import edgar_tags
from app.services.market_data import get_market_data_provider
from app.trading_math.valuation import (
    dividend_yield_pct,
    fcf_yield_pct,
    net_cash_millions,
    net_position_phrase,
    ratio_to_pct,
)


# Common English words / acronyms that look like tickers in caps. The
# blocklist is intentionally conservative — false positives cost an
# extra yfinance call that returns None; false negatives mean a real
# ticker silently misses the live-data overlay.
_TICKER_BLOCKLIST: frozenset[str] = frozenset({
    "I", "A", "AN", "THE", "AND", "OR", "BUT", "IF", "TO", "OF", "IN",
    "ON", "FOR", "WITH", "AS", "AT", "BY", "FROM", "IS", "IT", "BE",
    "ARE", "WAS", "WERE", "DO", "DOES", "DID", "HAS", "HAVE", "HAD",
    "WILL", "WOULD", "CAN", "COULD", "SHOULD", "MAY", "MIGHT", "MUST",
    "NOT", "NO", "YES", "OK", "OKAY", "SO", "HOW", "WHY", "WHAT",
    "WHEN", "WHERE", "WHO", "MY", "ME", "WE", "US", "YOU",
    "USA", "UK", "EU", "PM", "AM", "CEO", "CFO", "COO", "CTO", "VP",
    "IPO", "ETF", "API", "URL", "USD", "GBP", "EUR", "JPY", "CNY",
    "YOY", "QOQ", "YTD", "MTD", "WTD", "EPS", "PE", "FCF", "ESG",
    "AI", "LLM", "ML", "ROI", "GDP", "CPI", "PPI", "FED", "FOMC",
    "AAOIFI", "GAAP", "IFRS", "SEC", "FDA", "FTC", "DOJ",
    "TLDR", "FYI", "BTW", "IMO", "IIRC", "PS",
})

_TICKER_RE = re.compile(r"\$?([A-Z]{1,5})\b")

# CR168 (folded into CR166) — yfinance's `exchange` is a venue CODE, not a name:
# AAPL returns "NMS", not "NASDAQ". `Exchange: NMS` is jargon to the model, so an
# unmapped code is DROPPED rather than rendered — the same "absent beats
# meaningless" rule DEF053 applies to numerics. Adding a venue here is the only
# way to make it reachable, which keeps the mapping auditable instead of letting
# an unrecognised code leak through as fact.
_EXCHANGE_NAMES: dict[str, str] = {
    "NMS": "NASDAQ",   # Global Select
    "NGM": "NASDAQ",   # Global Market
    "NCM": "NASDAQ",   # Capital Market
    "NAS": "NASDAQ",
    "NYQ": "NYSE",
    "NYS": "NYSE",
    "ASE": "NYSE American",
    "AMX": "NYSE American",
    "PCX": "NYSE Arca",
    "BTS": "Cboe BZX",
}

_yf_convention_checked = False


# ── CR145 Tier D — the quarterly statements, and the cache that pays for them ──
#
# Tier D's row makes the cache a precondition rather than a nicety: *"a TTL
# fundamentals cache ships in this tier or the tier does not ship."* Two things
# were measured before choosing where to put one.
#
# **What is actually expensive.** The Room calls `fetch_live_fundamentals` ONCE
# per convene (`room_runner.py:521`), so a cache on `.info` saves nothing there;
# the 1-on-1 path calls it per message, which is real but small. What Tier D
# ADDS is two more network calls per ticker — `.quarterly_income_stmt` and
# `.quarterly_cashflow`, measured at 0.27–0.99s each against NVDA/GRAB/SNOA/
# NBIS/KTOS — and those are the ones worth not repeating.
#
# **Why `.info` is deliberately NOT cached here.** It carries a live price:
# `base_price` comes from `currentPrice`, and `low`/`high`/`support`/`breakout`
# are derived from it. A long TTL would freeze the Room's reference price while
# `last_close` (60s TTL, `CachingProvider`) kept moving, and
# `_reference_price_line` would then narrate a growing divergence between two
# figures that are supposed to be the same instrument — a fabricated
# disagreement manufactured by a cache. Caching the slow half and leaving the
# live half live is the only split that does not trade a real cost for a
# misleading number.
#
# 6 hours, matching `CachingProvider`'s earnings TTL rather than inventing a
# number. Quarterly statements change when a company files — four times a year
# — so the TTL is bounded by staleness we could tolerate at 30 days and chosen
# for consistency with the neighbouring cache instead.
_STATEMENTS_TTL_S = 21600.0

_statements_cache: dict[str, tuple[dict[str, Any] | None, float]] = {}
_statements_lock = RLock()


def clear_statement_cache() -> None:
    """Drop every cached statement fact. Test seam, and the operational escape
    hatch if a filing lands inside the TTL window."""
    with _statements_lock:
        _statements_cache.clear()


def _stmt_series(frame: Any, *row_names: str) -> list[float | None] | None:
    """One row of a yfinance statement frame as plain floats, newest first.

    Defensive at every step on purpose: these frames are pandas objects whose
    row labels are yfinance's own normalisation of a filing, and a label that
    exists for one company is routinely absent for another — measured, not
    assumed: NBIS and KTOS carry no `Repurchase Of Capital Stock` row at all
    while SNOA, a microcap, does. `None` means "this company does not report
    it", which is what DEF053 says to render as absent rather than as zero.
    """
    try:
        labels = [str(i) for i in frame.index]
    except Exception:
        return None
    for name in row_names:
        if name not in labels:
            continue
        try:
            raw = list(frame.loc[name].values)
        except Exception:
            return None
        out: list[float | None] = []
        for v in raw:
            try:
                f = float(v)
            except (TypeError, ValueError):
                out.append(None)
                continue
            out.append(f if math.isfinite(f) else None)
        return out
    return None


def _ttm_millions(series: list[float | None] | None) -> int | None:
    """The trailing four quarters of a statement row, in whole $M, signed.

    None unless all four are present. Three quarters summed and labelled TTM
    is a wrong number with a right-sounding name, which is the failure class
    the whole module's absent-is-not-zero rule exists to prevent.
    """
    if series is None or len(series) < 4:
        return None
    recent = series[:4]
    if any(v is None for v in recent):
        return None
    return round(sum(recent) / 1_000_000)


def _margin_bps(num: list[float | None] | None, den: list[float | None] | None,
                latest: int, prior: int) -> int | None:
    """Change in a margin between two quarters, in basis points.

    Computed here rather than handed to an agent as two ratios: CR179 Leg 4's
    rule is that every derived figure is precomputed, because four recurrences
    (DEF066 → DEF235 → DEF241 → CR166 Tier D) have shown a prompt instruction
    not to calculate is not a control.
    """
    if not num or not den or len(num) <= prior or len(den) <= prior:
        return None
    a_n, a_d = num[latest], den[latest]
    b_n, b_d = num[prior], den[prior]
    if None in (a_n, a_d, b_n, b_d) or not a_d or not b_d:
        return None
    return round(((a_n / a_d) - (b_n / b_d)) * 10_000)


def _buyback_pace(quarters: list[float]) -> str | None:
    """CR219 R35 — accelerating / steady / paused, off the four per-quarter
    magnitudes (already-absolute, oldest-to-newest).

    A pure threshold classifier, same house style as `rsi_tone`
    (`trading_math/indicators.py`) — a deterministic bucket, never an LLM
    judgment call, so the label on the sheet is reproducible from the same
    four numbers every time. The latest quarter is compared against the
    prior three quarters' average, at a symmetric 20% threshold:

    - **paused**: latest is 20% or less of the prior average — comfortably
      below what a merely quieter quarter would show, so a company still
      repurchasing a residual amount (an option-dilution offset, say) does
      not get called "paused" by accident.
    - **accelerating**: latest is 20% or more ABOVE the prior average.
    - **steady**: everything between the two thresholds — deliberately wide,
      because a buyback programme (which management explicitly varies with
      price and opportunity, unlike a dividend) has real quarter-to-quarter
      noise that is not a change of pace.

    Requires exactly 4 non-None quarters — the same `len(recent) == 4` gate
    the TTM sum uses, so the two never disagree about whether the company
    has enough history to speak about at all.
    """
    if len(quarters) != 4:
        return None
    latest = quarters[0]
    prior_avg = sum(quarters[1:]) / 3
    if prior_avg <= 0:
        # No repurchase activity in the prior three quarters at all — a
        # brand-new programme has no "pace" yet to classify against, and
        # calling it "accelerating" against a zero base is a manufactured
        # comparison, not a measured one.
        return None
    ratio = latest / prior_avg
    if ratio <= 0.2:
        return "paused"
    if ratio >= 1.2:
        return "accelerating"
    return "steady"


def fetch_statement_facts(ticker: str) -> dict[str, Any] | None:
    """Margin TREND and buyback activity from the quarterly statements.

    Two facts the fact sheet has never carried, both named in the Fundamentals
    Analyst's own job description (*"durable margins … capital allocation"*)
    and both previously disclosed as unavailable in this very module.

    - **Margin trend.** The sheet already renders three margin LEVELS from
      `.info`; what it could not say was which way any of them was moving, so
      `fundamentals_analyst.md` had to have the ask removed (CR145 Tier A)
      rather than answered. Year-over-year, latest quarter against the same
      quarter a year earlier — not quarter-on-quarter, which for any seasonal
      business measures the season rather than the business.
    - **Buybacks.** Trailing four quarters of `Repurchase Of Capital Stock`,
      and the same figure as a percentage of market cap, because the absolute
      is unreadable without a denominator — $40B is a rounding error at one
      market cap and a recapitalisation at another.

    Returns None on any error, and omits any individual key the filings do not
    support. Never raises: a statements outage must degrade the two new lines
    to CR104 UNAVAILABLE, not take the whole fact sheet down with it.
    """
    key = ticker.upper().strip()
    now = time.time()
    with _statements_lock:
        hit = _statements_cache.get(key)
        if hit is not None and hit[1] > now:
            return hit[0]
    out = _fetch_statement_facts_uncached(key)
    with _statements_lock:
        # A None result is cached too. A ticker with no filings yfinance can
        # parse is a stable fact, and re-asking every convene would make the
        # failure case the expensive one — which is how a degraded provider
        # turns into a latency incident.
        _statements_cache[key] = (out, now + _STATEMENTS_TTL_S)
    return out


def _fetch_statement_facts_uncached(ticker: str) -> dict[str, Any] | None:
    try:
        import yfinance as yf
        tk = yf.Ticker(ticker)
        income = tk.quarterly_income_stmt
        cashflow = tk.quarterly_cashflow
    except Exception as exc:
        logger.warn("yfinance_statements_error", ticker=ticker, error=str(exc)[:200])
        return None

    out: dict[str, Any] = {}

    # ── Margin trend, YoY ────────────────────────────────────────────────
    # Columns arrive newest-first, so index 0 is the latest quarter and index
    # 4 is the same quarter a year ago. Fewer than five columns means the YoY
    # comparison does not exist for this company; nothing is rendered rather
    # than falling back to a quarter-on-quarter delta wearing a YoY label.
    try:
        periods = [str(c)[:10] for c in income.columns]
    except Exception:
        periods = []
    if len(periods) >= 5:
        revenue = _stmt_series(income, "Total Revenue")
        deltas = {
            "gross_margin_trend_bps": _stmt_series(income, "Gross Profit"),
            "operating_margin_trend_bps": _stmt_series(
                income, "Operating Income", "Total Operating Income As Reported"
            ),
            "net_margin_trend_bps": _stmt_series(
                income, "Net Income", "Net Income Common Stockholders"
            ),
        }
        for field, numerator in deltas.items():
            bps = _margin_bps(numerator, revenue, latest=0, prior=4)
            if bps is not None:
                out[field] = bps
        if any(f in out for f in deltas):
            out["margin_trend_basis"] = f"{periods[0]} vs {periods[4]}"

    # ── Buybacks, trailing four quarters ─────────────────────────────────
    # The row is signed as a cash OUTflow, so the reported figure is negative
    # and the magnitude is what was returned to shareholders. An absent row is
    # absent, never zero: a company that reports no repurchase line and one
    # that reports a repurchase of 0.0 are different claims, and only the
    # second is ours to make.
    repurchase = _stmt_series(cashflow, "Repurchase Of Capital Stock")
    if repurchase is not None:
        recent = [v for v in repurchase[:4] if v is not None]
        if len(recent) == 4:
            out["buyback_ttm"] = round(abs(sum(recent)) / 1_000_000)
            # CR219 R35 — the four individual quarters, and the pace they
            # describe, rather than just their sum. The magnitudes existed
            # right here and were discarded the moment they were summed;
            # nothing new is fetched. Rounded to whole $M, newest-first, same
            # order `periods`/`_stmt_series` already use throughout this
            # function. Gated on `periods` carrying at least 4 dates too — a
            # series with no dated basis is the same "number with no basis"
            # defect `margin_trend_line`'s docstring designs against, so all
            # three keys below ship together or not at all.
            if len(periods) >= 4:
                out["buyback_quarterly"] = [
                    round(abs(v) / 1_000_000) for v in recent
                ]
                out["buyback_quarterly_basis"] = periods[:4]
                pace = _buyback_pace([abs(v) for v in recent])
                if pace is not None:
                    out["buyback_pace"] = pace

    # ── Dividends paid, trailing four quarters ───────────────────────────
    # CR218. The sheet already carried a dividend YIELD, and an analyst that
    # wants the capital-allocation picture has to turn that back into dollars
    # against the market cap to add it to buybacks. Observed GLM-5.3 doing
    # exactly that arithmetic in its reasoning, and landing on $2,707M for CAT
    # against the statement's actual $2,812M — a 3.9% error, because a TRAILING
    # yield times a CURRENT market cap is not the trailing payment.
    #
    # The exact figure is on the cash-flow statement this function already
    # fetches for buybacks, so it costs no additional call. Same signed-outflow
    # and absent-is-not-zero rules as the repurchase row above.
    dividends = _stmt_series(
        cashflow, "Cash Dividends Paid", "Common Stock Dividend Paid"
    )
    if dividends is not None:
        recent = [v for v in dividends[:4] if v is not None]
        if len(recent) == 4:
            out["dividends_paid_ttm"] = round(abs(sum(recent)) / 1_000_000)

    # ── Capital expenditure, trailing four quarters (CR219 R34) ──────────
    # The sheet already renders `free_cash_flow` (from `.info`'s
    # `freeCashflow`, a single pre-computed figure — not derived here from
    # operating cash flow minus capex), so capex was only ever IMPLICIT: an
    # agent could see FCF move and infer capex changed without ever being
    # told by how much, which is exactly the arithmetic R20's global
    # derivation policy now forbids doing on sheet figures. This makes the
    # number explicit instead of inferable. Same signed-outflow and
    # absent-is-not-zero rules as the buyback/dividend rows above; row-label
    # variants matched the same way `edgar_tags.CAPEX`'s PIT resolver already
    # has to (measured there: filers spell this several ways).
    capex = _stmt_series(
        cashflow,
        "Capital Expenditure", "Purchase Of PPE",
        "Payments To Acquire Property Plant And Equipment",
    )
    if capex is not None:
        recent = [v for v in capex[:4] if v is not None]
        if len(recent) == 4:
            out["capex_ttm"] = round(abs(sum(recent)) / 1_000_000)

    # ── The cash-flow bridge: OCF - capex = FCF (CR221 C3/C4, DEF400) ─────
    # Two things at once, because they are one disclosure.
    #
    # C3/C4 is what six agents asked for in nine request lines — *"a detailed
    # free cash flow reconciliation showing changes in working capital versus
    # CapEx"*. Every operand is already on the frame fetched above; only the
    # capex leg survived the function, so the bridge could not be stated.
    #
    # DEF400 is why it must be derived rather than read. `.info`'s
    # `freeCashflow` is a single pre-computed figure that reconciles to
    # nothing: measured 2026-09-03, CAT's is $5,049M against $13,569M of
    # operating cash flow less $4,575M of capex = $8,994M, and the frame's own
    # `Free Cash Flow` row agrees with the subtraction to the dollar (MSFT
    # likewise: $16,546M stated, $66,987M derived). It was right when CR218
    # was written — that comment records $8,961M — so this is provider drift
    # on a shipped number, not a basis we mis-read. The subtraction is
    # checkable against a row on the same frame; the `.info` scalar is not.
    #
    # Absent is absent: an incomplete quarter set yields no bridge rather than
    # a partial-year figure wearing a TTM label.
    ocf = _stmt_series(
        cashflow, "Operating Cash Flow",
        "Cash Flow From Continuing Operating Activities",
        "Total Cash From Operating Activities",
    )
    ocf_ttm = _ttm_millions(ocf)
    if ocf_ttm is not None and len(periods) >= 4:
        out["operating_cash_flow_ttm"] = ocf_ttm
        out["cashflow_ttm_basis"] = f"{periods[3]} to {periods[0]}"
        if "capex_ttm" in out:
            # `capex_ttm` is stored as a magnitude, so this is a subtraction
            # even though the underlying row is a signed outflow.
            out["free_cash_flow_ttm"] = ocf_ttm - out["capex_ttm"]

    # Working-capital detail. The total and its three named drivers, each an
    # independent 4-quarter series — a driver that does not report all four
    # quarters is dropped rather than back-filled, and the render carries the
    # remainder as `other` so the parts always sum to the stated total. The
    # sign is the statement's own: negative consumed cash.
    if out.get("cashflow_ttm_basis"):
        wc_total = _ttm_millions(_stmt_series(cashflow, "Change In Working Capital"))
        components = {
            "wc_receivables_ttm": ("Change In Receivables", "Changes In Receivables"),
            "wc_inventory_ttm": ("Change In Inventory", "Changes In Inventories"),
            "wc_payables_ttm": (
                "Change In Payables And Accrued Expense", "Change In Payable",
            ),
        }
        found = {
            field: value
            for field, rows in components.items()
            if (value := _ttm_millions(_stmt_series(cashflow, *rows))) is not None
        }
        if wc_total is not None and found:
            out["wc_change_ttm"] = wc_total
            out.update(found)

    # ── Interest coverage, latest quarter (CR219 R33) ────────────────────
    # The #1 arm request across the CR219 measurement — 21 mentions from 9 of
    # 12 agents — and the CAT insolvency-risk narrative that motivated it was
    # built with no coverage figure on the sheet at all. EBIT is Operating
    # Income: this module already fetches it for the margin-trend delta above,
    # and it is the standard EBIT proxy (income before interest and tax) —
    # reusing it costs nothing and keeps one number meaning one thing across
    # the sheet rather than a second, slightly different "EBIT" appearing here.
    #
    # Interest expense is signed as a cost in some filers' statements and as a
    # magnitude in others (measured across yfinance's own row-label variants);
    # `abs()` at the point of division is deliberate — a coverage ratio is
    # never negative because the borrower paid interest, only because EBIT
    # itself is negative, and that sign must survive.
    #
    # Quarterly, not TTM: `.quarterly_income_stmt`'s newest column IS the
    # latest reported quarter, and stating which one is the label rule this
    # whole module follows (`margin_trend_basis`, `next_earnings_quarter`) —
    # never a number with no date attached.
    ebit_series = _stmt_series(
        income, "Operating Income", "Total Operating Income As Reported"
    )
    interest_series = _stmt_series(
        income, "Interest Expense", "Interest Expense Non Operating"
    )
    if ebit_series and interest_series and ebit_series[0] is not None and interest_series[0]:
        out["interest_coverage"] = round(ebit_series[0] / abs(interest_series[0]), 1)
        out["interest_coverage_quarter"] = periods[0] if periods else None

    # ── Own-history annual EPS/EBITDA, for R37's median multiples ─────────
    # A SEPARATE try/except from the quarterly fetch above: `tk.income_stmt`
    # (annual — distinct from `tk.quarterly_income_stmt`, already held as
    # `income`) is a different yfinance property that can fail independently,
    # and a failure here must not cost the quarterly-derived fields above it
    # (margin trend, buybacks, capex, interest coverage) — same "one outage
    # degrades only its own lines" contract `fetch_statement_facts`'s own
    # docstring states for the module as a whole.
    #
    # Verified against real yfinance (CAT/NVDA/KTOS/SNOA, 2026-09-03) before
    # writing this: `income_stmt` carries a literal "EBITDA" row (no
    # Operating-Income-plus-D&A reconstruction needed, unlike the PIT/
    # backtest path in edgar_pit.py, which has no such row and must build
    # it) and a "Diluted EPS" row, both keyed to fiscal-year-end columns.
    # Every ticker tested returned exactly 5 columns, but the OLDEST column
    # was NaN for CAT specifically — so "5 columns" and "5 USABLE years" are
    # different claims, and only the second is safe to state. The window is
    # measured per-ticker below (`len(usable)`), never assumed to be 4 or 5.
    try:
        annual_income = tk.income_stmt
        annual_periods = [str(c)[:10] for c in annual_income.columns]
    except Exception as exc:
        logger.warn("yfinance_annual_statement_error", ticker=ticker, error=str(exc)[:200])
        annual_income = None
        annual_periods = []
    if annual_income is not None and annual_periods:
        ebitda_series = _stmt_series(annual_income, "EBITDA")
        eps_series = _stmt_series(annual_income, "Diluted EPS")
        if ebitda_series is not None:
            usable = [
                (period, v) for period, v in zip(annual_periods, ebitda_series)
                if v is not None and v > 0
            ]
            if usable:
                out["ebitda_history"] = [v for _, v in usable]
                out["ebitda_history_years"] = [p[:4] for p, _ in usable]
        if eps_series is not None:
            usable = [
                (period, v) for period, v in zip(annual_periods, eps_series)
                if v is not None and v > 0
            ]
            if usable:
                out["eps_history"] = [v for _, v in usable]
                out["eps_history_years"] = [p[:4] for p, _ in usable]

    # ── Multi-year FCF, capex and conversion (CR221 C2/C5) ────────────────
    # Five request lines from four agents, all wanting the same series and
    # none of them satisfiable from a single TTM figure: *"historical
    # multi-year averages for free cash flow and capital expenditure"*,
    # *"free cash flow conversion rate history over the past 5 years"*,
    # *"FCF as a percentage of net income over time"*.
    #
    # `tk.cashflow` is the ANNUAL sibling of the `quarterly_cashflow` frame
    # this function already holds — the same "one more property on the same
    # Ticker, no new endpoint" shape as `income_stmt` above, with its own
    # try/except for the same reason.
    #
    # FCF is DERIVED here, never read from the frame's `Free Cash Flow` row,
    # for DEF400's reason: the two agree on every filer measured, and where a
    # vendor figure and a subtraction disagree the subtraction is the one that
    # can be checked. Conversion is withheld for any year whose net income is
    # not positive — FCF over a loss is a number with no meaning, and printing
    # -340% next to four honest percentages invites exactly the misreading the
    # series was added to prevent.
    try:
        annual_cash = tk.cashflow
        cash_periods = [str(c)[:10] for c in annual_cash.columns]
    except Exception as exc:
        logger.warn("yfinance_annual_cashflow_error", ticker=ticker, error=str(exc)[:200])
        annual_cash = None
        cash_periods = []
    if annual_cash is not None and cash_periods:
        annual_ocf = _stmt_series(annual_cash, "Operating Cash Flow",
                                  "Cash Flow From Continuing Operating Activities")
        annual_capex = _stmt_series(annual_cash, "Capital Expenditure",
                                    "Purchase Of PPE")
        if annual_ocf and annual_capex:
            years = [
                (period, round((ocf + capex) / 1_000_000), round(abs(capex) / 1_000_000))
                for period, ocf, capex in zip(cash_periods, annual_ocf, annual_capex)
                if ocf is not None and capex is not None
            ]
            # Three is the floor for calling something a history. Two points
            # are a comparison, and an average of two is just their midpoint
            # wearing a longer word.
            if len(years) >= 3:
                out["fcf_history_years"] = [p[:4] for p, _, _ in years]
                out["fcf_history"] = [fcf for _, fcf, _ in years]
                out["capex_history"] = [capex for _, _, capex in years]
                net_income = _stmt_series(
                    annual_income, "Net Income", "Net Income Common Stockholders",
                ) if annual_income is not None else None
                if net_income:
                    by_period = dict(zip(annual_periods, net_income))
                    # `fcf` is already whole $M; the income frame is raw
                    # dollars, so the denominator is scaled to match.
                    conversion = [
                        round(fcf / (by_period[period] / 1_000_000) * 100)
                        if by_period.get(period) and by_period[period] > 0 else None
                        for period, fcf, _ in years
                    ]
                    if sum(c is not None for c in conversion) >= 3:
                        out["fcf_conversion_pct"] = conversion

    # ── Earnings revisions direction (CR219 R21-DATA) ──────────────────────
    # This unblocks WP04-R21's overlay rewrite: the short/medium fundamentals
    # branch demands "earnings revisions, surprise history" and, until this
    # field, nothing fetched either — the demand was asking agents to
    # analyse data they were never given.
    #
    # `tk.eps_trend` — yet ANOTHER yfinance property, its own try/except for
    # the same "one outage costs only its own lines" reason as the annual
    # statement block above. Verified live (CAT, 2026-09-03): four rows
    # (0q/+1q/0y/+1y — current quarter, next quarter, current year, next
    # year), each with `current`/`7daysAgo`/`30daysAgo`/`60daysAgo`/
    # `90daysAgo` consensus EPS estimates. The CURRENT-QUARTER row (`0q`) is
    # used — the nearest, most decision-relevant estimate — comparing
    # `current` against `90daysAgo` for the widest window this data
    # actually spans (the demand text itself will say "over the stated
    # window" once WP04 rewrites it, and the window stated here is what
    # backs that).
    try:
        eps_trend = tk.eps_trend
    except Exception as exc:
        logger.warn("yfinance_eps_trend_error", ticker=ticker, error=str(exc)[:200])
        eps_trend = None
    if eps_trend is not None and "0q" in eps_trend.index:
        try:
            current = eps_trend.loc["0q", "current"]
            ago_90d = eps_trend.loc["0q", "90daysAgo"]
            current = float(current) if current is not None else None
            ago_90d = float(ago_90d) if ago_90d is not None else None
        except (TypeError, ValueError):
            current = ago_90d = None
        if (
            current is not None and ago_90d is not None
            and math.isfinite(current) and math.isfinite(ago_90d) and ago_90d
        ):
            pct_change = round((current - ago_90d) / abs(ago_90d) * 100, 1)
            # A flat/near-flat band reads as "unchanged" rather than forcing
            # a direction onto noise — matching the house style
            # `window_trend_phrase` already applies to price moves ("flat"
            # under 0.05%), scaled for an estimate that moves in cents, not
            # points: under half a percent of the estimate itself.
            if abs(pct_change) < 0.5:
                direction = "unchanged"
            else:
                direction = "up" if pct_change > 0 else "down"
            out["eps_revisions_direction"] = direction
            out["eps_revisions_pct"] = pct_change
            out["eps_revisions_current"] = round(current, 2)
            out["eps_revisions_window_days"] = 90

    # ── Surprise history (CR219 R21-DATA) ───────────────────────────────────
    # `tk.earnings_history` — reported vs. estimate for the last several
    # quarters, yfinance's own pre-computed surprise. Deliberately NOT
    # `tk.earnings_dates` (also considered): that property's
    # `_get_earnings_dates_using_scrape` path requires `lxml`, which is not
    # an installed dependency in this project (confirmed by running it
    # live, 2026-09-03 — it raised `ImportError` before any network call
    # even completed) — `earnings_history` is a plain API call with no such
    # requirement and returns the same reported/estimate/surprise shape.
    # Adding `lxml` to reach `earnings_dates` instead would be exactly the
    # kind of new dependency this WP's own rule reserves for R38-style
    # design review, for a property that is not actually needed once this
    # one is confirmed to carry the same data.
    try:
        earnings_hist = tk.earnings_history
    except Exception as exc:
        logger.warn("yfinance_earnings_history_error", ticker=ticker, error=str(exc)[:200])
        earnings_hist = None
    if earnings_hist is not None and len(earnings_hist) > 0:
        try:
            quarters = [str(idx)[:10] for idx in earnings_hist.index]
            actuals = [
                float(v) if v is not None and math.isfinite(v) else None
                for v in earnings_hist["epsActual"]
            ]
            estimates = [
                float(v) if v is not None and math.isfinite(v) else None
                for v in earnings_hist["epsEstimate"]
            ]
            surprise_pct = [
                round(float(v) * 100, 1) if v is not None and math.isfinite(v) else None
                for v in earnings_hist["surprisePercent"]
            ]
        except (TypeError, ValueError, KeyError):
            quarters = actuals = estimates = surprise_pct = []
        # Four PARALLEL lists, matching the `buyback_quarterly`/
        # `buyback_quarterly_basis` idiom above rather than a list of dicts
        # — one shape for "a dated numeric series" across this whole
        # module. A row missing quarter/actual/estimate is dropped from all
        # four in lockstep rather than rendered with a gap (DEF053's
        # "absent beats meaningless", applied to a row instead of a
        # scalar). Oldest-first, matching `earnings_hist`'s own
        # chronological index order — unlike the statement frames above,
        # which arrive newest-first.
        usable = [
            (q, a, e, s)
            for q, a, e, s in zip(quarters, actuals, estimates, surprise_pct)
            if q and a is not None and e is not None
        ]
        if usable:
            out["surprise_quarters"] = [q for q, _, _, _ in usable]
            out["surprise_actuals"] = [a for _, a, _, _ in usable]
            out["surprise_estimates"] = [e for _, _, e, _ in usable]
            out["surprise_pcts"] = [s for _, _, _, s in usable]

    return out or None


def _yfinance_major(version: str | None) -> int:
    """Major version number from a yfinance `__version__` string, or -1 if it
    can't be parsed. Isolated so the convention gate below is a pure, testable
    decision rather than string-fiddling inline."""
    try:
        return int((version or "").split(".")[0])
    except (ValueError, IndexError):
        return -1


def _warn_if_yfinance_convention_stale(yf_module: Any) -> None:
    """Degrade loudly (CR040) if the installed yfinance predates the 1.x
    dividend-yield convention CR046 M04 depends on. On 0.2.x, `dividendYield`
    is a decimal fraction, so `dividend_yield_pct`'s pass-through round would
    under-report every payer's yield ~100× — silently. The pin is `>=1.0`; this
    shouts once per process if a build somehow resolves an older major, rather
    than letting a wrong-but-plausible yield reach the analyst."""
    global _yf_convention_checked
    if _yf_convention_checked:
        return
    _yf_convention_checked = True
    installed = getattr(yf_module, "__version__", "") or ""
    if _yfinance_major(installed) < 1:
        logger.error(
            "yfinance_below_dividend_convention_floor",
            installed=installed,
            required=">=1.0",
            impact="dividendYield is a fraction on <1.0 → dividend yield ~100x too low",
        )


def extract_tickers(text: str) -> list[str]:
    """Pull plausible US-equity tickers from free-form text.

    Heuristic: a 1–5 character all-caps token, optionally `$`-prefixed,
    that isn't in the blocklist of common English words / acronyms.
    Returns at most 3 distinct tickers in first-mention order — more
    than that and the prompt becomes a wall of data blocks.
    """
    if not text:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for m in _TICKER_RE.finditer(text):
        sym = m.group(1)
        if sym in _TICKER_BLOCKLIST:
            continue
        if sym in seen:
            continue
        seen.add(sym)
        out.append(sym)
        if len(out) >= 3:
            break
    return out


def fetch_fundamentals(ticker: str, as_of: date | None = None) -> dict[str, Any] | None:
    """One fundamentals fetch, two temporal modes (CR164).

    `as_of=None` → the live yfinance `.info` path below — byte-identical
    behaviour to every pre-CR164 caller. `as_of=date` → point-in-time EDGAR
    resolution (`edgar_pit.fetch_pit_fundamentals`): same dict shape, same
    formatting helpers, only facts `filed <= as_of`. Consensus-derived fields
    (forward_pe, peg, analyst target/rating) simply never appear in the PIT
    dict — their absence flows to the CR104 UNAVAILABLE rendering, which is
    the ablation mechanism, not prompt text.

    One module owns the shape so a future fact-sheet field lands here once
    and both the live Room and the backtest harness exercise it — the CR164
    same-infrastructure rule.
    """
    if as_of is None:
        return fetch_live_fundamentals(ticker)
    from app.services.edgar_pit import fetch_pit_fundamentals  # lazy: avoids cycle

    return fetch_pit_fundamentals(ticker, as_of)


def fetch_live_fundamentals(ticker: str) -> dict[str, Any] | None:
    """Fetch real fundamentals via yfinance. Returns None on any error.

    Returned dict keys (all optional — missing fields mean yfinance
    didn't have them for this ticker):
      base_price, pe, forward_pe, rev_growth, profit_margin, net_cash, low,
      high, week52_range_live, support, breakout, price_to_sales,
      ev_to_ebitda, peg_ratio, peg_basis, fcf_yield, dividend_yield, sector,
      industry, analyst_target_price, analyst_rating,
      long_name, exchange_name,
      gross_margin, operating_margin, trailing_eps,
      revenue_ttm, revenue_per_share, return_on_equity, return_on_assets,
      current_ratio, quick_ratio, debt_to_equity, payout_ratio,
      analyst_opinion_count, analyst_target_high, analyst_target_low,
      analyst_target_median, analyst_rating_score, held_pct_institutions,
      held_pct_insiders, shares_outstanding, float_shares

    Only numeric fields the LLM is likely to misremember. Narrative
    fields stay synthetic at the call site so yfinance gaps don't
    create misleading absence-of-data.

    DEF053 (AT:R58): price_to_sales/ev_to_ebitda/peg_ratio/fcf_yield/
    dividend_yield/sector/industry/analyst_target_price/analyst_rating
    all come free from yfinance's own `info` dict — confirmed live
    against AAPL/MSFT/NVDA/GME before wiring, no Alpha Vantage key
    needed. Full financial statements (income/balance/cash flow) and
    buyback/M&A history remain unavailable — not fabricated, just
    absent from the profile (see fundamentals_analyst.md).
    """
    try:
        import yfinance as yf
        _warn_if_yfinance_convention_stale(yf)
        info = yf.Ticker(ticker.upper()).info
    except Exception as exc:
        logger.warn("yfinance_fundamentals_error", ticker=ticker, error=str(exc)[:200])
        return None
    if not info:
        return None

    def _num(key: str) -> float | None:
        # DEF052's F1 lesson applied proactively: yfinance's own
        # missing-value sentinel is NaN, not always a missing key — a
        # non-finite value must be treated as absent, not passed through
        # to `f"{v:.1f}"` (renders the literal string "nan") or a
        # downstream comparison that would silently misbehave.
        v = info.get(key)
        if v is None:
            return None
        try:
            result = float(v)
        except (TypeError, ValueError):
            return None
        return result if math.isfinite(result) else None

    price = _num("currentPrice") or _num("regularMarketPrice")
    pe = _num("trailingPE")
    # DEF233: the sheet carried ONLY the trailing multiple, so on every growth
    # or cyclical name the Room reasoned about "valuation disconnect" from the
    # one figure that argues against entry. Measured across a 10-name sample,
    # trailing ÷ forward ran 1.6×–6.6× (median ~3.3×) and not one name went the
    # other way — KTOS was rejected live on "357.5x P/E" with a forward P/E of
    # 54.4. Forward P/E is an analyst ESTIMATE, so it is carried BESIDE the
    # trailing figure and labelled as consensus at every render site, never
    # swapped in for it (CR104/DEF123: an estimate must not render with a
    # measurement's authority).
    #
    # A non-positive forward multiple is an artefact of a forecast loss, not a
    # valuation — NBIS returns forwardPE=-86.97 against a real trailing 72.86,
    # and LCID returns -1.41 with no trailing at all. Rendering either as "-87x
    # forward" would be worse than the omission this defect is about, so a
    # non-positive figure is treated as absent and the render sites say so.
    forward_pe_raw = _num("forwardPE")
    forward_pe = forward_pe_raw if forward_pe_raw is not None and forward_pe_raw > 0 else None
    # Anchor on real signals — if price + pe are both missing, the
    # ticker is unknown to yfinance and the caller should fall through.
    if price is None and pe is None:
        return None

    out: dict[str, Any] = {}
    if price is not None:
        out["base_price"] = round(price, 2)
        out["low"] = round(price * 0.95, 2)
        out["high"] = round(price * 1.05, 2)
        out["support"] = round(price * 0.9, 2)
        out["breakout"] = round(price * 1.03, 2)
    fifty_two_low = _num("fiftyTwoWeekLow")
    fifty_two_high = _num("fiftyTwoWeekHigh")
    if fifty_two_low is not None and fifty_two_high is not None:
        out["low"] = round(fifty_two_low, 2)
        out["high"] = round(fifty_two_high, 2)
        # DEF-audit D-c: only the REAL yfinance 52-week range earns the
        # "52-week range" label. When these fields are missing, low/high stay the
        # ±5% placeholder above (kept so the range tracks the live price) but the
        # 1-on-1 block labels it a placeholder rather than claiming 52 weeks.
        out["week52_range_live"] = True
    if pe is not None:
        out["pe"] = f"{pe:.1f}"
    if forward_pe is not None:
        out["forward_pe"] = f"{forward_pe:.1f}"
    # Unit conversions live in trading_math.valuation (CR046 M04).
    rev_growth = _num("revenueGrowth")
    if rev_growth is not None:
        out["rev_growth"] = ratio_to_pct(rev_growth)
    # profitMargins is the NET PROFIT margin — keyed and labeled as such. It was
    # stored as `fcf_margin` and rendered "FCF margin" in the Room, a metric this
    # value is not (CR046 D-b).
    profit_margin = _num("profitMargins")
    if profit_margin is not None:
        out["profit_margin"] = ratio_to_pct(profit_margin)
    # totalCash / totalDebt are dollars; net cash in millions for the prompt.
    total_cash = _num("totalCash")
    total_debt = _num("totalDebt")
    if total_cash is not None and total_debt is not None:
        out["net_cash"] = net_cash_millions(total_cash, total_debt)
    # CR145 Tier A — GROSS debt beside the net figure. A netted number hides
    # leverage: $40B cash against $45B debt and $1B against $6B both render as
    # "net debt $5,000M", and they are not the same balance sheet.
    if total_debt is not None:
        out["total_debt"] = round(total_debt / 1_000_000)
    # CR179 Leg 3 — and gross CASH, which that argument applies to equally and
    # which was left behind. The asymmetry was invisible to both guards: the
    # census counts `totalCash` as consumed (it is read, into `net_cash`), and
    # parity only asks whether a PRODUCED field is rendered — a key read and
    # dropped inside a helper produces nothing to ask about. It surfaced from
    # the Leg 0 perturbation probe: moving `totalDebt` moves two output fields,
    # moving `totalCash` moves one.
    #
    # It is the half of the pair that carries the survivability question. The
    # two balance sheets in the comment above are distinguished by the CASH,
    # and "how long can this company fund itself" is a different question from
    # "how levered is it" — the Bear Researcher's, specifically.
    if total_cash is not None:
        out["total_cash"] = round(total_cash / 1_000_000)

    # Real valuation multiples beyond P/E (DEF053) — closes the "P/S,
    # EV/EBITDA, FCF yield" overclaim without a second provider.
    price_to_sales = _num("priceToSalesTrailing12Months")
    if price_to_sales is not None:
        out["price_to_sales"] = f"{price_to_sales:.1f}"
    ev_to_ebitda = _num("enterpriseToEbitda")
    if ev_to_ebitda is not None:
        out["ev_to_ebitda"] = f"{ev_to_ebitda:.1f}"
    # yfinance renamed pegRatio → trailingPegRatio; try the current key first,
    # fall back to the legacy one, so the PEG line doesn't silently disappear.
    # DEF233: the current key states its own denominator — a PEG built on the
    # same trailing earnings the P/E line now labels explicitly — so the basis
    # is carried through and rendered. The legacy key does NOT declare a basis,
    # so nothing is claimed for it rather than assuming it matches.
    peg_ratio = _num("trailingPegRatio")
    peg_basis: str | None = "trailing"
    if peg_ratio is None:
        peg_ratio = _num("pegRatio")
        peg_basis = None
    if peg_ratio is not None:
        out["peg_ratio"] = f"{peg_ratio:.2f}"
        if peg_basis is not None:
            out["peg_basis"] = peg_basis
    # ── CR179 Leg 3 — the technicals-lane keys `.info` has always returned ──
    #
    # All fetched inside the SAME `yf.Ticker(t).info` call that already serves
    # every field above, exempted in the census as "CR166 stage 3" and never
    # rendered. Measured 6/6 available across NVDA/GRAB/KTOS/SNOA/NBIS/BAC.
    #
    # THREE of the tempting ones are deliberately NOT taken, because "more is
    # better" is bounded by the second half of this build's mandate — a Room
    # that agrees with itself:
    #
    #   - `previousClose` — the sheet already carries a reference price AND a
    #     last close, and `_reference_price_line` exists because one turn read
    #     those two as two facts. A third price is that defect again. The day
    #     MOVE is the actual gap ("the sheet states a price and never says
    #     whether it moved") and a percentage needs no second price to stand.
    #   - `fiftyDayAverage` — we already compute and render `sma_long` from the
    #     history. Two 50-day averages on different bases is the same defect.
    #     The 200-day has no counterpart, so it is pure gain.
    #   - a second volume RATIO — `volume_tone`/`volume_ratio` (CR146 Tier B)
    #     already state the comparison off the history. The absolutes are taken
    #     because they answer a different question: scale. SNOA trades ~75k
    #     shares a day and NVDA ~45M, and the mandate's "Liquid only. Avoid
    #     microcaps" is a sizing constraint that market cap alone cannot settle.
    day_change_pct = _num("regularMarketChangePercent")
    if day_change_pct is not None:
        out["day_change_pct"] = round(day_change_pct, 2)
    # CR104's provenance question applied to a price: a quote carries a
    # different authority at 14:00 than at 03:00, and the sheet never said
    # which. An unrecognised state is dropped rather than passed through, the
    # same rule `_EXCHANGE_NAMES` applies to a venue code.
    market_state = info.get("marketState")
    if market_state in ("REGULAR", "PRE", "POST", "CLOSED", "PREPRE", "POSTPOST"):
        out["market_state"] = str(market_state)
    sma_200 = _num("twoHundredDayAverage")
    if sma_200 is not None:
        out["sma_200"] = round(sma_200, 2)
        # Precomputed, per Leg 4's rule: the distance is the figure an agent
        # reaches for, and handing over two numbers plus an instruction to
        # divide them is what DEF066 → DEF235 → DEF241 → CR166 Tier D is a
        # record of.
        if price is not None and sma_200:
            out["price_vs_sma_200_pct"] = round((price - sma_200) / sma_200 * 100, 1)
    volume_today = _num("volume")
    if volume_today is not None:
        out["volume_today"] = int(volume_today)
    volume_avg = _num("averageVolume")
    if volume_avg is not None:
        out["volume_avg_3m"] = int(volume_avg)

    # Relative strength. `SandP52WeekChange` is the INDEX's own 52-week change
    # — measured identical (0.1979) across all six probe tickers, which is what
    # confirms it is the benchmark and not the ticker. The spread is what the
    # pair is for, so the spread is what gets computed here rather than left as
    # two numbers for an agent to subtract.
    change_52w = _num("52WeekChange")
    change_52w_sp = _num("SandP52WeekChange")
    if change_52w is not None:
        out["change_52w_pct"] = round(change_52w * 100, 1)
    if change_52w_sp is not None:
        out["change_52w_sp500_pct"] = round(change_52w_sp * 100, 1)
    if change_52w is not None and change_52w_sp is not None:
        out["relative_strength_52w_pct"] = round((change_52w - change_52w_sp) * 100, 1)

    # ── CR150 — the Bear Researcher's quantified downside ──────────────────
    beta = _num("beta")
    if beta is not None:
        out["beta"] = round(beta, 2)
    # Short interest, with the as-of date CR150's row requires. It is reported
    # on a lag of roughly two weeks, so an undated short-interest figure
    # presented beside a live price is a freshness claim we cannot support —
    # the CR148 Tier B lesson, on a different feed.
    short_pct_float = _num("shortPercentOfFloat")
    short_ratio = _num("shortRatio")
    short_date = _num("dateShortInterest")
    # A literal ZERO is treated as absent, not as a fact. Measured: BAC comes
    # back with `sharesShort` 3,122 against billions of shares outstanding and
    # `shortPercentOfFloat` 0.0 — which would render as "0.0% of float", i.e. a
    # confident claim that nobody is short a mega-cap bank. That is not a tuned
    # threshold, it is the boundary of the domain: a listed equity does not have
    # zero short interest, so a zero is the provider telling us it does not
    # know. DEF053 — absent beats meaningless.
    if short_pct_float:
        out["short_pct_float"] = round(short_pct_float * 100, 2)
        if short_ratio:
            out["short_days_to_cover"] = round(short_ratio, 1)
        if short_date:
            try:
                out["short_interest_date"] = datetime.fromtimestamp(
                    short_date, tz=timezone.utc
                ).date().isoformat()
            except (OverflowError, OSError, ValueError):
                pass

    free_cash_flow = _num("freeCashflow")
    # DEF400 — `.info`'s `freeCashflow` reconciles to nothing on this same
    # provider's own statements, so prefer the subtraction that does. Reads
    # through the 6h statements cache the merge below already populates, so
    # this costs no extra fetch. Falls back rather than blanking: a filer whose
    # quarters are incomplete keeps the `.info` figure it has always had.
    if settings.fundamentals_fcf_from_statements_enabled:
        derived = (fetch_statement_facts(ticker) or {}).get("free_cash_flow_ttm")
        if derived is not None:
            free_cash_flow = derived * 1_000_000
    market_cap = _num("marketCap")
    fcf_yield = fcf_yield_pct(free_cash_flow, market_cap)
    if fcf_yield is not None:
        out["fcf_yield"] = fcf_yield
    # CR145 Tier A / CR150 A2 — both of these were fetched only to be consumed
    # as the numerator and denominator of the yield above, then discarded.
    #
    # Market cap is the one that matters most: the mandate carries "Liquid only.
    # Avoid microcaps (< $500M market cap)" as a HARD constraint in 17 of 18
    # prompts, while 0 of 18 fact sheets stated a market cap and the same prompt
    # forbids recalling one from training memory. The rule was unfollowable by
    # construction. Rendering this makes it checkable for the first time.
    #
    # FCF in dollars because a yield alone cannot distinguish a company earning
    # $200M on a $5B cap from one earning $2B on a $50B cap, and "FCF
    # consistency" is in the Fundamentals Analyst's own job description.
    if market_cap is not None:
        out["market_cap"] = round(market_cap / 1_000_000)
    if free_cash_flow is not None:
        out["free_cash_flow"] = round(free_cash_flow / 1_000_000)

    # Real capital allocation. CR145 Tier D retires half of what this comment
    # used to say: *"buybacks/M&A have no yfinance field and stay undisclosed
    # rather than fabricated"*. That was true of `.info`, which is the only
    # endpoint this module called — buybacks are on `.quarterly_cashflow`, and
    # the disclosure was really a statement about our own fetch. M&A history
    # genuinely has no yfinance field and stays undisclosed.
    dividend_yield = _num("dividendYield")
    if dividend_yield is not None:
        out["dividend_yield"] = dividend_yield_pct(dividend_yield)

    # Margin trend + buybacks, from the quarterly statements behind a 6h TTL.
    # Merged here rather than fetched at either render site so ONE module owns
    # the fact-sheet shape and both surfaces exercise it — the CR164
    # same-infrastructure rule `fetch_fundamentals` states. A statements
    # failure returns None and simply contributes no keys, which is the CR104
    # UNAVAILABLE path, not a hole in the sheet.
    statements = fetch_statement_facts(ticker)
    if statements:
        out.update(statements)
        # The buyback needs its denominator to be readable, and Leg 4's rule is
        # that we hand over the derived figure rather than the two operands and
        # an instruction. Computed only where market cap is live — a yield
        # against an absent denominator is the fabrication this avoids.
        buyback = statements.get("buyback_ttm")
        if buyback is not None and market_cap:
            out["buyback_yield"] = round(buyback * 1_000_000 / market_cap * 100, 1)

        # CR218 — total capital returned, and what share of free cash flow it
        # consumed. Same Leg 4 rule as the buyback yield beside it: hand over
        # the derived figure, not the operands and an instruction.
        #
        # This is the fact the two components do not carry separately. CAT
        # returned $8,617M against $8,961M of TTM FCF — 96% — while revenue
        # shrank 1% and operating margin fell 360bps. "Buybacks $5,910M" and
        # "yield 1.4%" are both benign on their own; together against FCF they
        # are the capital-allocation finding the role brief asks for, and the
        # incumbent model read the buyback line and never made the connection.
        dividends_paid = statements.get("dividends_paid_ttm")
        components = [v for v in (buyback, dividends_paid) if v is not None]
        if components:
            total = sum(components)
            out["capital_return_ttm"] = total
            # Guarded on POSITIVE free cash flow, not merely present. A payer
            # burning cash returns capital out of the balance sheet or new
            # borrowing, and "213% of FCF" against a small positive number, or
            # a negative percentage against a negative one, both read as
            # precision the figure does not have. The dollars still render; only
            # the ratio is withheld.
            if free_cash_flow and free_cash_flow > 0:
                out["capital_return_pct_fcf"] = round(
                    total * 1_000_000 / free_cash_flow * 100
                )

        # CR219 R37 — historical median multiples: TODAY's price/EV against
        # each of the last several fiscal years' own EPS/EBITDA, median'd.
        #
        # This is NOT a historical-price-based P/E series (that would need a
        # separate multi-year price-history fetch this rule forbids —
        # "everything derives from statements/bars/estimates yfinance
        # already returns via the existing fetch paths"). It answers a
        # related, narrower, and still useful question the evidence corpus
        # actually raised: the PM's own gap report said *"if I had proof
        # that 24.5x was a normal mid-cycle baseline rather than an extreme
        # cyclical peak, I might have approved"* — i.e., is TODAY's
        # denominator (EBITDA/EPS) itself elevated or depressed relative to
        # the company's own recent history. Pricing every past year's
        # earnings at TODAY's price/EV isolates exactly that: if the spread
        # of implied multiples is wide and skewed, the denominator has moved
        # a lot: a genuine "mid-cycle vs. peak" signal, cheaply available
        # from data already on the sheet, worded to make plain it is NOT a
        # reconstructed historical multiple.
        #
        # Window labelled per-ticker from what `_fetch_statement_facts_uncached`
        # actually returned (already filtered to positive, usable years there)
        # — never assumed to be 4 or 5.
        #
        # `ebitda_history`/`ebitda_history_years`/`eps_history`/
        # `eps_history_years` are raw INTERMEDIATE arrays — computation
        # inputs, never a rendered field. `out.update(statements)` above
        # already merged them in with the rest of `statements`' keys;
        # popped here, explicitly, at the point they're consumed, rather
        # than left to leak into `out` as four keys with no render site and
        # no field_state registration — exactly the shape
        # `test_prompt_data_parity.py`'s guard-on-the-guard exists to catch
        # (and did, on the first real run of this code: caught here, not
        # discovered later).
        ebitda_hist = out.pop("ebitda_history", None)
        ebitda_years = out.pop("ebitda_history_years", None)
        eps_hist = out.pop("eps_history", None)
        eps_years = out.pop("eps_history_years", None)
        if ebitda_hist and ebitda_years and market_cap and total_debt is not None and total_cash is not None:
            ev = market_cap + total_debt - total_cash
            if ev > 0:
                implied = [round(ev / e, 1) for e in ebitda_hist]
                out["historical_ev_ebitda_median"] = round(statistics.median(implied), 1)
                out["historical_ev_ebitda_years"] = len(ebitda_hist)
                out["historical_ev_ebitda_window"] = f"{ebitda_years[-1]}-{ebitda_years[0]}"

        if eps_hist and eps_years and price:
            implied = [round(price / e, 1) for e in eps_hist]
            out["historical_pe_median"] = round(statistics.median(implied), 1)
            out["historical_pe_years"] = len(eps_hist)
            out["historical_pe_window"] = f"{eps_years[-1]}-{eps_years[0]}"

    # Real sector/industry classification replaces the old always-fake
    # numeric `sector_pe` — a category, not a fabricated peer-average P/E
    # (yfinance has no peer-basket P/E; computing one would need a peer
    # mapping this app doesn't have).
    sector = info.get("sector")
    if sector:
        out["sector"] = str(sector)
    industry = info.get("industry")
    if industry:
        out["industry"] = str(industry)

    # CR168 (folded into CR166) — resolved instrument identity, from this same
    # dict at zero additional cost. A company NAME reached the model in only
    # 156/216 = 72.2% of production prompts (66.7% after Batch 9's recency
    # floor, and 0% for AMD/AVGO/KTOS), and always incidentally, via the
    # `Catalysts —` headline line rather than as identity: the AAPL corpus
    # names Nvidia, Amazon and OpenAI, and never Apple. Prophylactic rather
    # than a correctness fix — the gate found 0 wrong-company instances in 216
    # turns — so it is rendered as identity and nothing is claimed for it.
    long_name = info.get("longName")
    if long_name:
        out["long_name"] = str(long_name)
    exchange_name = _EXCHANGE_NAMES.get(str(info.get("exchange") or "").upper())
    if exchange_name:
        out["exchange_name"] = exchange_name

    # CR166 Tier B — the margin STRUCTURE. `profitMargins` (net) alone cannot
    # say whether a thin net margin is a pricing problem or a cost problem, and
    # the role brief asks the agent to "prioritise durable margins". All three
    # sit in the dict already fetched. Whole percents to match the net figure
    # already on the sheet — mixed precision across one comparison line reads
    # as a difference in confidence that isn't there.
    gross_margin = _num("grossMargins")
    if gross_margin is not None:
        out["gross_margin"] = ratio_to_pct(gross_margin)
    operating_margin = _num("operatingMargins")
    if operating_margin is not None:
        out["operating_margin"] = ratio_to_pct(operating_margin)
    # `ebitdaMargins` is deliberately NOT fetched. It sits in the same dict, but
    # gross → operating → net is the progression the question is asked in, and
    # EBITDA slots between gross and operating in a way that reads as a fourth
    # step rather than the add-back it is. EV/EBITDA already carries the metric
    # where it earns its place. Fetching a field we would not render is the
    # exact behaviour this CR exists to stop — it would have been number 113.

    # CR166 Tier B — earnings power. The sheet renders a P/E on two bases with
    # no earnings behind either, so nothing lets the agent sanity-check the
    # multiple it is quoting; and it renders revenue GROWTH with no revenue, so
    # "16%" has no base. Revenue in $M, matching net_cash / market_cap / FCF.
    trailing_eps = _num("trailingEps")
    if trailing_eps is not None:
        out["trailing_eps"] = round(trailing_eps, 2)
    revenue_ttm = _num("totalRevenue")
    if revenue_ttm is not None:
        out["revenue_ttm"] = round(revenue_ttm / 1_000_000)
    revenue_per_share = _num("revenuePerShare")
    if revenue_per_share is not None:
        out["revenue_per_share"] = round(revenue_per_share, 2)

    # CR166 Tier B — returns and balance-sheet quality. The role brief asks for
    # "balance sheet strength", served today by two debt figures and nothing on
    # what the business earns against the capital it employs.
    return_on_equity = _num("returnOnEquity")
    if return_on_equity is not None:
        out["return_on_equity"] = ratio_to_pct(return_on_equity)
    return_on_assets = _num("returnOnAssets")
    if return_on_assets is not None:
        out["return_on_assets"] = ratio_to_pct(return_on_assets)
    current_ratio = _num("currentRatio")
    if current_ratio is not None:
        out["current_ratio"] = round(current_ratio, 2)
    quick_ratio = _num("quickRatio")
    if quick_ratio is not None:
        out["quick_ratio"] = round(quick_ratio, 2)
    # yfinance reports debtToEquity as a PERCENT (AAPL: 78.445), not the ratio
    # the name implies — 78.445 is 0.78x, and rendering the raw figure as "78x
    # debt/equity" would describe a solvency crisis at a company with $84B of
    # debt against $107B of equity. Converted here, once, at the fetch site.
    debt_to_equity = _num("debtToEquity")
    if debt_to_equity is not None:
        out["debt_to_equity"] = round(debt_to_equity / 100, 2)

    # CR166 Tier B — dividend COVER. A yield says what the payer yields; the
    # payout ratio says whether it can keep paying it, which is the half
    # "capital allocation" actually turns on.
    payout_ratio = _num("payoutRatio")
    if payout_ratio is not None:
        out["payout_ratio"] = ratio_to_pct(payout_ratio)
    # NOTE — no dividend RATE is fetched here on purpose. CR030 already pulls
    # `dividendRate` onto `EarningsInfo` for the mobile dividend chip, and the
    # Room renders its next-earnings line off that same object; adding a second
    # rate key would put TWO annual dividend rates in the profile on two
    # different bases (`dividendRate` is the forward indicated figure, 1.08 for
    # AAPL; `trailingAnnualDividendRate` is 1.05). One concept, one source — the
    # duplication this census exists to stop. The render site labels the basis,
    # DEF233-style, because the yield beside it is the trailing figure.

    # CR166 Tier B — the ownership base. Market cap (CR145 Tier A) only half
    # serves the mandate's liquidity rule: a large cap with a small float is
    # not liquid, and the float is what a position is actually filled against.
    held_pct_institutions = _num("heldPercentInstitutions")
    if held_pct_institutions is not None:
        out["held_pct_institutions"] = ratio_to_pct(held_pct_institutions, 1)
    held_pct_insiders = _num("heldPercentInsiders")
    if held_pct_insiders is not None:
        out["held_pct_insiders"] = ratio_to_pct(held_pct_insiders, 1)
    shares_outstanding = _num("sharesOutstanding")
    if shares_outstanding is not None:
        out["shares_outstanding"] = round(shares_outstanding / 1_000_000)
    float_shares = _num("floatShares")
    if float_shares is not None:
        out["float_shares"] = round(float_shares / 1_000_000)

    # Real analyst consensus — the closest honest proxy for "forward
    # guidance" available (a company's own guidance figures aren't
    # exposed by yfinance; this is the Street's view, labeled as such).
    # CR035: suppressible for ablation benchmarks — omitting the keys here
    # drops the consensus line from both the Room profile and the 1-on-1
    # data block (_analyst_line returns None when the keys are absent).
    #
    # CR166 Tier B — the DISPERSION rides the same suppression flag as the mean,
    # because it is the same consensus: an ablation arm that stripped the target
    # but left the high/low/median standing would leak the figure it exists to
    # remove. "buy, target $322.82" reads as precision; 41 analysts spanning
    # $215–$400 is the same consensus with its disagreement left in.
    if not settings.suppress_analyst_consensus:
        analyst_target = _num("targetMeanPrice")
        if analyst_target is not None:
            out["analyst_target_price"] = round(analyst_target, 2)
        rating = info.get("recommendationKey")
        if rating and rating != "none":
            out["analyst_rating"] = str(rating).replace("_", " ")
        opinion_count = _num("numberOfAnalystOpinions")
        if opinion_count is not None:
            out["analyst_opinion_count"] = int(opinion_count)
        target_high = _num("targetHighPrice")
        if target_high is not None:
            out["analyst_target_high"] = round(target_high, 2)
        target_low = _num("targetLowPrice")
        if target_low is not None:
            out["analyst_target_low"] = round(target_low, 2)
        target_median = _num("targetMedianPrice")
        if target_median is not None:
            out["analyst_target_median"] = round(target_median, 2)
        # 1 = strong buy … 5 = sell. Carried as the number with its scale named
        # at the render site; `recommendationKey` is a bucketing of this, and a
        # 2.1 and a 2.9 both render as "buy".
        rating_score = _num("recommendationMean")
        if rating_score is not None:
            out["analyst_rating_score"] = round(rating_score, 1)

    return out


def pe_line(trailing: str | None, forward: str | None) -> str:
    """The P/E fact-sheet line, on both bases, labelled (DEF233).

    Lives here rather than in either renderer because the Room
    (`room_prompts._format_profile`) and 1-on-1 (`build_live_data_block`)
    render the same two numbers and drifted apart once already — same reason
    `range_position_pct` sits in `technicals.py` (DEF228). Callers pass a
    figure only once its own provenance is established: the Room gates each
    basis on `field_state`, 1-on-1 on the fetcher having supplied the key.

    The two bases are never merged or averaged, and neither substitutes for
    the other — trailing is a measurement of reported earnings, forward is the
    Street's estimate. An absent basis is stated as absent, never dropped
    silently, so "P/E 357.5x" can no longer read as the whole valuation
    picture.
    """
    trailing_part = (
        f"{trailing} trailing (measured — last 12 months of reported earnings)"
        if trailing
        else "trailing not available"
    )
    forward_part = (
        f"{forward} forward (CONSENSUS ESTIMATE of the next 12 months — "
        "analysts' forecast, not a measurement)"
        if forward
        else "forward not available — do not estimate one"
    )
    if not trailing and not forward:
        return "P/E: not available"
    return f"P/E: {trailing_part} · {forward_part}. Say which basis you mean whenever you cite a P/E."


def historical_multiples_line(
    pe_median: float | None, pe_years: int | None, pe_window: str | None,
    ev_ebitda_median: float | None, ev_ebitda_years: int | None, ev_ebitda_window: str | None,
    *, live: bool = True,
) -> str | None:
    """CR219 R37 — is today's multiple against a normal or an extreme year of
    this company's OWN earnings/EBITDA?

    Explicitly NOT a historical-price-based multiple series — this module
    fetches no multi-year price history (that would be a new network call
    the house rule forbids; "everything derives from statements/bars/
    estimates yfinance already returns via the existing fetch paths"). It is
    TODAY's price/EV divided by EACH of the last several fiscal years' own
    EPS/EBITDA, then the MEDIAN of those implied multiples — which answers a
    narrower, related question from data already on the sheet: is the
    denominator (this year's earnings/EBITDA) itself elevated or depressed
    relative to the company's own recent history. The wording below says so
    explicitly, every time, so the figure can never be mistaken for a
    reconstructed historical P/E series it structurally is not.

    The window is stated per-ticker (`Nyr, {window}`) — yfinance returns
    ~4-5 fiscal years of annual statements, not 10, and not every year
    clears the positive-earnings/EBITDA filter (`_fetch_statement_facts_
    uncached` drops non-positive years before this ever runs), so the
    number of years actually used is a measured fact, never assumed.
    """
    parts = []
    if pe_median is not None and pe_years and pe_window:
        parts.append(
            f"P/E: today's price against each of the last {pe_years} FYs' own "
            f"diluted EPS ({pe_window}), median {pe_median}x"
        )
    if ev_ebitda_median is not None and ev_ebitda_years and ev_ebitda_window:
        parts.append(
            f"EV/EBITDA: today's EV against each of the last {ev_ebitda_years} "
            f"FYs' own EBITDA ({ev_ebitda_window}), median {ev_ebitda_median}x"
        )
    if not parts:
        return None
    line = _labelled("Multiples vs. own history", live, parts)
    return (
        f"{line}. NOT a historical price-based multiple series — today's "
        "price/EV priced against past years' own fundamentals, to show "
        "whether this year's earnings/EBITDA is itself high or low versus "
        "the company's recent history. No peer-basket comparison exists."
    )


def eps_revisions_line(
    direction: str | None, pct: float | None, current: float | None,
    window_days: int | None, *, live: bool = True,
) -> str | None:
    """CR219 R21-DATA — analyst consensus EPS estimate revisions, direction
    and magnitude, over the stated window.

    This is what unblocks WP04-R21: the short/medium overlay branch demands
    "earnings revisions" and nothing fetched them until this field. The
    CURRENT-quarter consensus estimate against the same estimate 90 days
    ago (`tk.eps_trend`'s `0q` row) — the nearest, most decision-relevant
    estimate, and the widest comparison window that data actually carries.
    A near-flat move (under 0.5% of the estimate) reads as "unchanged"
    rather than a manufactured direction on noise.
    """
    if direction is None or current is None or window_days is None:
        return None
    part = f"consensus EPS estimate {direction}"
    if pct is not None and direction != "unchanged":
        part += f" {abs(pct)}%"
    part += f" over the last {window_days} days, now ${current}"
    return _labelled("Earnings revisions", live, [part])


def surprise_history_line(
    quarters: list[str] | None, actuals: list[float] | None,
    estimates: list[float] | None, surprise_pcts: list[float | None] | None,
    *, live: bool = True,
) -> str | None:
    """CR219 R21-DATA — reported vs. estimate, per quarter, the other half
    of WP04-R21's "surprise history" demand.

    `tk.earnings_history`, not `tk.earnings_dates` — the latter's scrape
    path requires `lxml`, not an installed dependency; the former is a
    plain API call carrying the same reported/estimate/surprise shape.
    Renders every quarter actually returned (measured, not assumed to be
    4 — SNOA returned 3 of the usual 4, checked live 2026-09-03), oldest
    first so the record reads as a timeline.
    """
    if not quarters or not actuals or not estimates:
        return None
    if not (len(quarters) == len(actuals) == len(estimates)):
        return None
    surprise_pcts = surprise_pcts or [None] * len(quarters)
    entries = []
    for i, (q, a, e) in enumerate(zip(quarters, actuals, estimates)):
        part = f"{q}: actual ${a} vs. est. ${e}"
        pct = surprise_pcts[i] if i < len(surprise_pcts) else None
        if pct is not None:
            part += f" ({'beat' if pct >= 0 else 'missed'} by {abs(pct)}%)"
        entries.append(part)
    return _labelled("Surprise history", live, ["; ".join(entries)])


# ── CR166 Tier B shared fact-sheet lines ────────────────────────────────────
#
# Same home and same reason as `pe_line` / `peg_part` above: the Room
# (`room_prompts._format_profile`) and 1-on-1 (`build_live_data_block`) render
# the same figures and drifted apart once already. Each builder owns the wording
# and the units; the caller owns PROVENANCE and passes a value only once it has
# established one — the Room gates on `field_state` (CR104), 1-on-1 on the
# fetcher having supplied the key. `live` controls only the liveness marker, so
# neither surface can label a figure the other calls unlabelled.
#
# Every one returns None when it has nothing to say, so an absent group is an
# absent LINE rather than a header over "not available" (DEF053).


def _labelled(name: str, live: bool, parts: list[str]) -> str | None:
    if not parts:
        return None
    marker = " (LIVE)" if live else ""
    return f"{name}{marker}: " + ", ".join(parts)


def margin_structure_line(
    gross: float | None, operating: float | None, net: float | None, *, live: bool = True
) -> str | None:
    """Gross → operating → net, the shape a margin question is actually asked in.

    The sheet carried only `profitMargins` (net), so an agent could not say
    whether a thin net margin was a pricing problem or a cost problem — and
    `fundamentals_analyst.md` was edited to forbid the gross-margin discussion
    (CR145 Batch 6) on the grounds the figure was not computed. It was in the
    dict all along; CR166's census is what found it.
    """
    parts = []
    if gross is not None:
        parts.append(f"gross {gross}%")
    if operating is not None:
        parts.append(f"operating {operating}%")
    if net is not None:
        parts.append(f"net {net}%")
    return _labelled("Margin structure", live, parts)


def margin_trend_line(
    gross_bps: int | None,
    operating_bps: int | None,
    net_bps: int | None,
    basis: str | None,
    *,
    live: bool = True,
) -> str | None:
    """CR145 Tier D — which way the margins are moving, not just where they are.

    **The basis is stated in the line itself, deliberately.** The levels on
    `margin_structure_line` are TTM (that is what yfinance's `.info` margins
    are); this delta is the latest QUARTER against the same quarter a year
    earlier, off `.quarterly_income_stmt`. Two different bases for the same
    word sitting silently on one sheet is precisely the defect
    `_reference_price_line` had to reconcile for price — one turn read a quote
    and a last close as two facts. So the comparison names its own two quarters
    and says it is quarterly, and the reader cannot subtract one line from the
    other by accident.

    A basis of eight quarters would let this be TTM-vs-TTM and remove the
    mismatch entirely; yfinance returns five to seven quarterly columns
    (measured across NVDA/GRAB/KTOS/SNOA/NBIS), so that comparison does not
    exist for most names and inventing it would mean labelling a quarterly
    delta as TTM.
    """
    parts = []
    for label, bps in (
        ("gross", gross_bps), ("operating", operating_bps), ("net", net_bps),
    ):
        if bps is not None:
            # No thousands separator, deliberately. A comma inside a number is
            # the DEF242 hazard in this codebase — `Entry: $1,507.00` parsed as
            # `1.0` — and every prose agent's output is walked by regexes that
            # have been bitten by it twice. A basis-point delta needs no
            # grouping to be readable, so there is nothing to trade away.
            parts.append(f"{label} {bps:+d}bps")
    if not parts or not basis:
        return None
    line = _labelled("Margin trend, YoY", live, parts)
    return f"{line} — quarter ending {basis.replace(' vs ', ' against the quarter ending ')}"


def buyback_line(
    ttm_millions: int | None, yield_pct: float | None, *, live: bool = True
) -> str | None:
    """CR145 Tier D — buybacks, the capital-allocation evidence the prompt asked
    for and this module used to disclose as unavailable.

    The percentage rides beside the absolute because the absolute alone is
    unreadable: NVDA's $45,303M trailing-four-quarter repurchase is 0.8% of its
    market cap, and the same dollar figure would be a recapitalisation at a
    tenth the size. Precomputed rather than left as two operands and an
    instruction — CR179 Leg 4's rule, applied at the point the field is born.
    """
    if ttm_millions is None:
        return None
    part = f"${ttm_millions:,}M repurchased (trailing 4 quarters)"
    if yield_pct is not None:
        part += f", {yield_pct}% of market cap"
    return _labelled("Buybacks", live, [part])


def buyback_pacing_line(
    quarterly_millions: list[int] | None,
    basis: list[str] | None,
    pace: str | None,
    *,
    live: bool = True,
) -> str | None:
    """CR219 R35 — the four-quarter repurchase series, and the pace it
    describes, beside the trailing-4-quarter TOTAL `buyback_line` already
    states. A total alone cannot say whether a programme is ramping,
    steady, or has quietly stopped — the same "one number hides two
    different stories" reasoning `capital_return_line`'s docstring makes
    about buybacks-vs-dividends, one level down: two companies with an
    identical $7,654M trailing-4-quarter total can be in opposite phases of
    the same programme.

    `pace` is the precomputed `_buyback_pace` label (CR179 Leg 4's rule
    again: a classification is handed over, not left for the model to eyeball
    four numbers and characterise). It is genuinely optional even when the
    series renders — `_buyback_pace` withholds a label rather than fabricate
    one against a zero prior-quarters base, and this line must render the
    honest four figures either way.

    Quarters render OLDEST first, matching how the basis dates read left to
    right as a timeline — the newest-first order the raw statement columns
    and `buyback_ttm`'s derivation use internally is reversed here for
    readability, and reversed nowhere else in this module, so the two lists
    passed in (already newest-first from the fetcher) are both flipped at
    the render boundary rather than at the point they were computed.
    """
    if not quarterly_millions or not basis or len(quarterly_millions) != 4 or len(basis) != 4:
        return None
    oldest_first_values = list(reversed(quarterly_millions))
    oldest_first_basis = list(reversed(basis))
    series = ", ".join(
        f"{date}: ${v:,}M" for date, v in zip(oldest_first_basis, oldest_first_values)
    )
    part = f"{series}"
    if pace is not None:
        part += f" — {pace}"
    return _labelled("Buyback pacing", live, [part])


def interest_coverage_line(
    ratio: float | None, quarter: str | None, *, live: bool = True
) -> str | None:
    """CR219 R33 — EBIT / interest expense, the #1 arm request in the CR219
    measurement (21 mentions from 9 of 12 agents) and the figure the CAT
    insolvency-risk narrative was reasoned about without.

    The quarter is stated in the line itself, the same discipline
    `margin_trend_line` and `next_earnings_quarter` already follow: a bare
    ratio with no date invites a reader to treat it as TTM or as "current"
    when it is one reported quarter's EBIT against that same quarter's
    interest expense.
    """
    if ratio is None or not quarter:
        return None
    return _labelled(
        "Interest coverage (EBIT / interest expense)", live,
        [f"{ratio}x — quarter ending {quarter}"],
    )


def debt_maturity_line(
    labels: list[str] | None,
    values: list[float] | None,
    period_end: str | None,
    beyond_five: float | None,
    excluded_short_term: float | None,
    sheet_gross_debt: float | None = None,
    *,
    live: bool = True,
) -> str | None:
    """CR221 A1 — principal repayments by year, on a basis the line states itself.

    Fourteen request lines from six agents asked for this schedule. The basis
    note is not decoration and must not be dropped to save room: Caterpillar's
    five buckets sum to $28,160M while the same sheet reads "gross debt
    $45,146M", because the ladder is long-term principal only. An agent handed
    both figures with nothing to reconcile them reads a $17B gap as a
    contradiction and spends its turn there — the CR219 failure class this
    whole line exists downstream of. So the excluded short-term borrowings and
    the derived beyond-year-five bucket travel WITH the ladder, and a short
    ladder says how many years it actually covers.
    """
    if not labels or not values or len(labels) != len(values) or not period_end:
        return None
    parts = [f"{label} ${value:,.0f}M" for label, value in zip(labels, values)]
    if beyond_five is not None:
        parts.append(f"beyond year 5 ${beyond_five:,.0f}M (derived)")
    tail = f"long-term debt principal as of {period_end}"
    if excluded_short_term is not None:
        tail += f"; excludes short-term borrowings ${excluded_short_term:,.0f}M"
    # A three-bucket ladder rendered without this reads as "nothing matures
    # after year three", which is a conclusion the filer never stated and the
    # flattering one to draw.
    if len(labels) < len(edgar_tags.DEBT_MATURITY_LADDER):
        tail += f"; the filer discloses only these {len(labels)} years"
    # The measured ask is "the maturity schedule for the $45,146M gross debt
    # load" — the sheet's own figure, which the ladder is not on the basis of.
    # Ladder + beyond-five + short-term still lands ~4% under it for CAT, and
    # an agent that adds them up will find that gap whether or not we mention
    # it. Naming it is the difference between a stated basis difference and a
    # contradiction the agent has to spend a turn on.
    accounted = sum(values) + (beyond_five or 0) + (excluded_short_term or 0)
    if sheet_gross_debt and abs(accounted - sheet_gross_debt) / sheet_gross_debt > 0.02:
        tail += (
            f". Does not reconcile to the gross debt ${sheet_gross_debt:,.0f}M "
            f"stated above: that figure is on a different basis, and "
            f"${accounted:,.0f}M is what these filed maturity tags account for"
        )
    return _labelled("Debt maturity ladder", live, [" · ".join(parts), tail])


def cost_of_debt_line(
    pct: float | None,
    basis: str | None,
    annual_interest: float | None,
    gross_debt: float | None,
    period_end: str | None,
    *, live: bool = True,
) -> str | None:
    """CR221 A3 — the implied rate, with both of its inputs and its basis.

    Six request lines from four agents. Every term is shown because the rate
    is a quotient of two figures that can each be read a different way, and
    DEF399 is what happens when one of them is taken on trust: the shipped
    interest-coverage numerator is a non-operating stub for filers whose
    finance arm books interest into cost of revenue, and nothing on the sheet
    said so. Naming the basis (accrued vs cash) and printing the numerator and
    denominator makes a wrong input visible instead of silently priced in.
    """
    if pct is None or not basis or annual_interest is None or gross_debt is None:
        return None
    dated = f" to {period_end}" if period_end else ""
    return _labelled(
        "Implied cost of debt", live,
        [f"{pct}%",
         f"${annual_interest:,.0f}M {basis}{dated} / gross debt ${gross_debt:,.0f}M"],
    )


_FCF_BASIS_DIVERGENCE_PCT = 2.0


def _signed_millions(value: float) -> str:
    return f"{'-' if value < 0 else '+'}${abs(value):,.0f}M"


def cashflow_bridge_line(
    operating_cash_flow: int | None,
    capex: int | None,
    free_cash_flow: int | None,
    basis: str | None,
    wc_change: int | None,
    wc_receivables: int | None,
    wc_inventory: int | None,
    wc_payables: int | None,
    sheet_free_cash_flow: int | None = None,
    *, live: bool = True,
) -> str | None:
    """CR221 C3/C4 — the reconciliation nine request lines from six agents asked for.

    The ask is verbatim *"a detailed free cash flow reconciliation showing
    changes in working capital versus CapEx"*, and the reason it matters is on
    the Portfolio Manager's own follow-up: it wanted to know whether *"the 200%
    FCF payout was a structural deficit or a temporary"* swing, and could not
    tell from a single pre-computed FCF scalar with nothing behind it.

    So this states the subtraction rather than its result, and states what
    working capital did inside it. The working-capital drivers are printed with
    an `other` remainder computed to close the gap, because the three named rows
    do not sum to the reported total for any filer measured (CAT: -$4,435M
    named against -$1,067M reported) and three numbers that visibly fail to add
    up read as an error in the sheet rather than as an incomplete decomposition.

    The last argument is DEF400's tripwire. While that fix is off, the sheet's
    own `free_cash_flow` comes from `.info` and this bridge does not reconcile
    to it — CAT $5,049M against $8,994M. Two contradicting numbers on one sheet
    with nothing said about it is the exact CR219 failure class, so the
    divergence is named in the line rather than left for an agent to trip over.
    """
    if operating_cash_flow is None or capex is None or free_cash_flow is None:
        return None
    dated = f", 4 quarters {basis}" if basis else ""
    parts = [
        f"operating cash flow ${operating_cash_flow:,.0f}M "
        f"- capex ${capex:,.0f}M = free cash flow ${free_cash_flow:,.0f}M{dated}"
    ]

    if wc_change is not None:
        verb = "consumed" if wc_change < 0 else "released"
        drivers = [
            (label, value)
            for label, value in (
                ("receivables", wc_receivables),
                ("inventory", wc_inventory),
                ("payables", wc_payables),
            )
            if value is not None
        ]
        named = sum(value for _, value in drivers)
        detail = [f"{label} {_signed_millions(value)}" for label, value in drivers]
        remainder = wc_change - named
        if round(remainder) != 0:
            detail.append(f"other {_signed_millions(remainder)}")
        parts.append(
            f"working capital {verb} ${abs(wc_change):,.0f}M "
            f"({', '.join(detail)})" if detail
            else f"working capital {verb} ${abs(wc_change):,.0f}M"
        )

    if sheet_free_cash_flow is not None and free_cash_flow:
        drift = abs(sheet_free_cash_flow - free_cash_flow) / abs(free_cash_flow) * 100
        if drift > _FCF_BASIS_DIVERGENCE_PCT:
            parts.append(
                f"the free cash flow ${sheet_free_cash_flow:,.0f}M stated above is a "
                f"vendor-supplied figure that does not reconcile to this subtraction; "
                f"${free_cash_flow:,.0f}M is what the filed statements support"
            )

    return _labelled("Cash-flow bridge", live, parts)


def _series(years: list[str], values: list[int | None], unit: str = "$") -> str:
    return " · ".join(
        f"FY{year} " + (f"${value:,.0f}M" if unit == "$" else f"{value}%")
        for year, value in zip(years, values) if value is not None
    )


def fcf_history_line(
    years: list[str] | None,
    fcf: list[int] | None,
    capex: list[int] | None,
    *, live: bool = True,
) -> str | None:
    """CR221 C2 — the multi-year series, and the averages the ask named.

    *"Historical multi-year averages for free cash flow and capital
    expenditure"* — three request lines from three agents, none answerable
    from the single trailing figure the sheet carried. The averages are
    computed here rather than left to the reader for CR179 Leg 4's reason
    (four recurrences have shown a prompt instruction not to calculate is not
    a control), and the window is stated as the number of years actually
    usable, never as the number of columns the frame returned — CAT's oldest
    column is NaN, so a "5-year average" over it would be a 4-year average
    wearing a longer label.

    Free cash flow here is operating cash flow less capex, said out loud,
    because the sheet's own FCF figure is a vendor scalar on a basis that
    reconciles to nothing (DEF400) and two differently-derived FCFs on one
    sheet must not look like one series.
    """
    if not years or not fcf or len(fcf) < 3:
        return None
    parts = [
        f"{_series(years, fcf)} ({len(fcf)}-year average "
        f"${sum(fcf) / len(fcf):,.0f}M)"
    ]
    if capex and len(capex) == len(fcf):
        parts.append(
            f"capex {_series(years, capex)} (average ${sum(capex) / len(capex):,.0f}M)"
        )
    parts.append("each year operating cash flow less capex")
    return _labelled("Free cash flow history", live, parts)


def fcf_conversion_line(
    years: list[str] | None,
    conversion: list[int | None] | None,
    *, live: bool = True,
) -> str | None:
    """CR221 C5 — free cash flow as a share of net income, year by year.

    *"Historical free cash flow conversion rates (FCF as a percentage of net
    income over time)"*. The trend is the finding, not the level: Microsoft
    converts 84% -> 82% -> 70% -> 50% across its capex build-out (measured
    2026-09-03), which no single year states and no TTM figure can.

    A year whose net income was not positive contributes nothing — the ratio
    has no meaning over a loss, and one impossible percentage beside three
    honest ones is read as a series, not as an exception.
    """
    if not years or not conversion:
        return None
    usable = [(y, c) for y, c in zip(years, conversion) if c is not None]
    if len(usable) < 3:
        return None
    tail = ""
    omitted = len(years) - len(usable)
    if omitted:
        tail = (f"; {omitted} loss-making year"
                f"{'s' if omitted > 1 else ''} omitted")
    return _labelled(
        "FCF conversion", live,
        [f"{_series([y for y, _ in usable], [c for _, c in usable], unit='%')} "
         f"of net income{tail}"],
    )


def capital_return_line(
    total_millions: int | None,
    buyback_millions: int | None,
    dividends_millions: int | None,
    pct_fcf: int | None,
    *,
    live: bool = True,
) -> str | None:
    """CR218 — what the company returned, and what share of FCF that consumed.

    The sheet already stated buybacks in dollars and dividends as a yield. An
    analyst wanting the capital-allocation picture the role brief asks for had
    to convert the yield to dollars against market cap, add it to buybacks, and
    divide by FCF — three steps, none of them in the sheet. GLM-5.3 was observed
    doing precisely that in its reasoning; the incumbent model read the buyback
    line and never made the connection at all. Precomputing it hands both the
    finding for free, which is a better trade than adopting a slower model to
    get it.

    Both components are named beside the total rather than folded into it. A
    company returning $8B entirely through buybacks and one splitting it evenly
    with a dividend are different capital-allocation stories, and the total
    alone cannot tell them apart.

    `pct_fcf` is withheld rather than fabricated when free cash flow is not
    positive — see the fetcher. A line with the dollars and no ratio is the
    honest shape there, not a hole.
    """
    if total_millions is None:
        return None
    split = [
        f"{label} ${v:,}M"
        for label, v in (("buybacks", buyback_millions), ("dividends", dividends_millions))
        if v is not None
    ]
    part = f"${total_millions:,}M (trailing 4 quarters)"
    if split:
        part += " — " + " + ".join(split)
    if pct_fcf is not None:
        part += f", {pct_fcf}% of TTM FCF"
    return _labelled("Capital returned", live, [part])


def capex_line(ttm_millions: int | None, *, live: bool = True) -> str | None:
    """CR219 R34 — capital expenditure, stated explicitly rather than left
    implicit inside the already-rendered free cash flow figure.

    The sheet renders `free_cash_flow` (a single pre-computed yfinance
    figure, not `operating_cash_flow - capex` computed here), so before this
    line an agent could see FCF and infer capex only by ALSO knowing
    operating cash flow — a number the sheet never stated either — which is
    exactly the sheet-figure arithmetic R20's global derivation policy now
    forbids. Reverse-engineering capex from FCF alone was already unsound
    even before R20 named the rule: FCF moves for revenue, margin and
    working-capital reasons that have nothing to do with capex, so the
    inference was never safe, only unexamined.
    """
    if ttm_millions is None:
        return None
    return _labelled(
        "Capital expenditure", live,
        [f"${ttm_millions:,}M (trailing 4 quarters)"],
    )


def day_move_line(
    change_pct: float | None, market_state: str | None, *, live: bool = True
) -> str | None:
    """CR179 Leg 3 — the sheet stated a price and never said whether it moved.

    The market state rides on the same line because the two are one fact: a
    +0.2% day move means something different mid-session than it does after the
    close, and an agent given the number without the state has to guess which
    it is holding. No second price is introduced — see the fetcher's note on
    why `previousClose` is refused.
    """
    if change_pct is None:
        return None
    state = {
        "REGULAR": "market open",
        "PRE": "pre-market",
        "PREPRE": "pre-market",
        "POST": "after hours",
        "POSTPOST": "after hours",
        "CLOSED": "market closed",
    }.get(market_state or "")
    part = f"{change_pct:+.2f}% today"
    if state:
        part += f" ({state})"
    return _labelled("Day move", live, [part])


def primary_trend_line(
    sma_200: float | None, distance_pct: float | None, *, live: bool = True
) -> str | None:
    """CR179 Leg 3 — the 200-day average, and where price sits against it.

    **"200-day" had zero hits anywhere in either register.** No agent could
    discuss the primary trend, and `compute_technicals` cannot derive one:
    `_HISTORY_PERIOD = "3m"` is ~65 bars. The value was in the `.info` dict the
    whole time, exempted as "CR166 stage 3".

    The distance is precomputed and the raw average is carried beside it, since
    a level is what a stop or an invalidation is written against while the
    percentage is what the trend argument is made from.

    DEF302 — the percentage is stated from BOTH ends, because one end was read
    off and re-attached backwards. On the MU run of 2026-08-14 the Neutral wrote
    *"The 200-day average at $895.91 is 70.6% below the current $1528.11 price"*
    against a line that said *"price 70.6% above it"*. The figure was quoted
    correctly and the referent inverted; the average is 41.4% below the price,
    not 70.6%, because the two are measured off different bases. Only one of the
    two readings was ever available to quote, so the other had to be computed,
    and P5 says that is where the error enters. Both are now supplied, which
    also makes the asymmetry visible rather than something to be discovered.
    """
    if sma_200 is None:
        return None
    part = f"200-day average ${sma_200:,}"
    if distance_pct is not None:
        side = "above" if distance_pct >= 0 else "below"
        part += f", price {abs(distance_pct)}% {side} it"
        # The inverse is NOT the same magnitude: +70.6% above maps to -41.4%
        # below, since each is a fraction of a different denominator.
        if distance_pct > -100.0:
            inverse = (100.0 / (1.0 + distance_pct / 100.0)) - 100.0
            other = "below" if inverse < 0 else "above"
            part += (
                f" (equivalently, the average sits {abs(inverse):.1f}% {other} "
                f"the price — the two differ because each is a share of a "
                f"different base)"
            )
    return _labelled("Primary trend", live, [part])


def relative_strength_line(
    ticker_pct: float | None,
    index_pct: float | None,
    spread_pct: float | None,
    *,
    live: bool = True,
) -> str | None:
    """CR179 Leg 3 — 52-week performance against the index, free from `.info`.

    Both legs are rendered as well as the spread, because "up 23%" in a year
    the index rose 20% and "up 23%" in a year it fell 20% are opposite facts,
    and an agent handed only the spread cannot tell whether the name rose or
    the market fell.
    """
    if ticker_pct is None or index_pct is None or spread_pct is None:
        return None
    verb = "ahead of" if spread_pct >= 0 else "behind"
    return _labelled(
        "Relative strength, 52w", live,
        [f"{ticker_pct:+.1f}% vs S&P 500 {index_pct:+.1f}% — "
         f"{abs(spread_pct)}pp {verb} the index"],
    )


def liquidity_line(
    volume_today: int | None, volume_avg_3m: int | None, *, live: bool = True
) -> str | None:
    """CR179 Leg 3 — the OTHER half of the mandate's liquidity constraint.

    *"Liquid only. Avoid microcaps"* was unfollowable until CR145 Tier A
    supplied market cap. Cap alone still cannot settle it: a name can be large
    and barely traded. These are absolutes, not a ratio — `volume_tone` already
    states the comparison off the history, and a second ratio on a second basis
    is the defect this build is closing, not opening.
    """
    parts = []
    if volume_today is not None:
        parts.append(f"{volume_today:,} shares today")
    if volume_avg_3m is not None:
        parts.append(f"{volume_avg_3m:,} 3-month average")
    return _labelled("Volume", live, parts)


def short_interest_line(
    pct_float: float | None,
    days_to_cover: float | None,
    as_of: str | None,
    *,
    live: bool = True,
) -> str | None:
    """CR150 — short interest, with the as-of date its row requires.

    Short interest is reported on roughly a two-week lag. Presented undated
    beside a live price it becomes a freshness claim we cannot support, which
    is what CR148 Tier B had to fix on the social feed — same mistake, different
    provider. So the date is part of the fact, not a footnote, and the line is
    written so the lag is visible rather than inferable.
    """
    if pct_float is None:
        return None
    parts = [f"{pct_float}% of float short"]
    if days_to_cover is not None:
        parts.append(f"{days_to_cover} days to cover")
    line = _labelled("Short interest", live, parts)
    if as_of:
        line += f" — as reported {as_of}, NOT a live figure"
    return line


def risk_profile_line(beta: float | None, *, live: bool = True) -> str | None:
    """CR150 — beta, the Bear Researcher's quantified downside.

    Named at the render site rather than left bare: `beta` is one of the most
    over-loaded words in finance, and the sheet says which one this is so the
    agent is not choosing between three definitions.
    """
    if beta is None:
        return None
    return _labelled(
        "Beta", live, [f"{beta} vs the market (5-year monthly, per the provider)"]
    )


def earnings_power_line(
    eps: float | None,
    revenue_ttm: float | None,
    revenue_per_share: float | None,
    *,
    live: bool = True,
) -> str | None:
    """Trailing EPS and the revenue base the growth figure is a percentage OF.

    The sheet states a P/E on two bases with no earnings behind either, and a
    TTM revenue growth percent with no revenue. Neither figure could be
    sanity-checked from the sheet that carried it.
    """
    parts = []
    if eps is not None:
        parts.append(f"EPS ${eps} trailing (measured, last 12 months)")
    if revenue_ttm is not None:
        parts.append(f"revenue ${revenue_ttm:,}M TTM")
    if revenue_per_share is not None:
        parts.append(f"revenue/share ${revenue_per_share}")
    return _labelled("Earnings power", live, parts)


def returns_line(
    roe: float | None, roa: float | None, *, live: bool = True
) -> str | None:
    """What the business earns on the capital it employs.

    The role brief asks for "balance sheet strength", which the sheet served
    with two debt figures and nothing on returns. ROE is reported against book
    equity, which buybacks shrink — so a high figure is not automatically a
    quality signal, and the label says "on book equity" rather than leaving the
    denominator implied.
    """
    parts = []
    if roe is not None:
        parts.append(f"ROE {roe}% (on book equity)")
    if roa is not None:
        parts.append(f"ROA {roa}%")
    return _labelled("Returns", live, parts)


def balance_sheet_line(
    current_ratio: float | None,
    quick_ratio: float | None,
    debt_to_equity: float | None,
    *,
    live: bool = True,
) -> str | None:
    """Liquidity and leverage, beside the net/gross debt figures already shown.

    `debt_to_equity` arrives here as a RATIO — the fetcher divides yfinance's
    percent-scaled `debtToEquity` by 100 — so it renders as "0.78x", not "78x".
    """
    parts = []
    if current_ratio is not None:
        parts.append(f"current ratio {current_ratio:.2f}")
    if quick_ratio is not None:
        parts.append(f"quick ratio {quick_ratio:.2f}")
    if debt_to_equity is not None:
        parts.append(f"debt/equity {debt_to_equity:.2f}x")
    return _labelled("Balance sheet", live, parts)


def ownership_line(
    institutions: float | None,
    insiders: float | None,
    shares_outstanding: float | None,
    float_shares: float | None,
    *,
    live: bool = True,
) -> str | None:
    """The ownership base behind the mandate's liquidity rule.

    Market cap (CR145 Tier A) only half-serves it: a large cap with a small
    float is not liquid, and the float is what a position actually fills
    against. Insider percentage is carried because a 34.6% insider holding
    (RIVN) and a 1.6% one (AAPL) are different instruments to size in.
    """
    parts = []
    if institutions is not None:
        parts.append(f"institutions {institutions}%")
    if insiders is not None:
        parts.append(f"insiders {insiders}%")
    if shares_outstanding is not None:
        parts.append(f"{shares_outstanding:,}M shares out")
    if float_shares is not None:
        parts.append(f"{float_shares:,}M float")
    return _labelled("Ownership", live, parts)


def dividend_line(
    dividend_yield: float | None,
    dividend_rate: float | None,
    payout_ratio: float | None,
    ex_dividend_date: str | None,
    *,
    today: date | None = None,
    live: bool = True,
) -> str | None:
    """Yield, rate, cover and the next ex-date — "capital allocation" in full.

    A yield says what a payer yields; the PAYOUT RATIO says whether it can keep
    paying it, and that is the half the role brief's "capital allocation" turns
    on. The two figures sit on different bases and say so: the yield is
    yfinance's trailing number, the rate is its forward indicated one (AAPL:
    0.34% trailing against $1.08 indicated). Merging them would be DEF233's
    defect one field over, so both are labelled and neither is derived from the
    other. M&A stays absent and stays disclaimed — no yfinance field backs it.
    Buybacks USED to be disclaimed here and are not any more: CR145 Tier D added
    the `.cashflow` call this docstring anticipated, and CR218 removed the
    disclaimer it left stranded (see the return statement).

    A NON-PAYER gets no line at all. `payoutRatio` is 0.0 for companies that pay
    nothing, so gating on "any part present" rendered *"Dividend: payout 0% of
    earnings"* for NBIS and RIVN — a header over an absence, which is the shape
    DEF053 exists to prevent. The yield or the rate is what makes this a
    dividend; the payout ratio only qualifies one.
    """
    if dividend_yield is None and dividend_rate is None:
        return None
    parts = []
    if dividend_yield is not None:
        parts.append(f"yield {dividend_yield}% (trailing)")
    if dividend_rate is not None:
        parts.append(f"${dividend_rate}/share indicated annual")
    if payout_ratio is not None:
        parts.append(f"payout {payout_ratio}% of earnings")
    if ex_dividend_date:
        # DEF124 — the interval beside the date, computed here rather than left
        # for the model to subtract. yfinance's `exDividendDate` is the most
        # recently DECLARED ex-date, which is routinely in the past, and a bare
        # date reads as upcoming.
        stamp = f"ex-date {ex_dividend_date}"
        if today is not None:
            try:
                stamp += f" ({relative_day_phrase(date.fromisoformat(ex_dividend_date), today)})"
            except ValueError:
                pass
        parts.append(stamp)
    line = _labelled("Dividend", live, parts)
    if line is None:
        return None
    # CR218 — the disclaimer used to read "(buybacks/M&A: not available, not
    # claimed)" and had been wrong since CR145 Tier D, which added the
    # `.quarterly_cashflow` call that backs buybacks. The docstring above even
    # anticipated it ("CR145 Tier D owns the `.cashflow` call that would") and
    # the disclaimer was never updated when Tier D shipped.
    #
    # It mattered because of how hard the rest of this sheet works to police
    # available-vs-not: two lines above, "Buybacks (LIVE): $5,910M repurchased"
    # states the figure, and this line then declared it unavailable. An agent
    # that believed the disclaimer would suppress a real number it had been
    # given — the mirror image of the fabrication the disclaimer exists to stop.
    # M&A genuinely has no yfinance field and stays disclaimed.
    return f"{line} (M&A: not available, not claimed)"


def analyst_consensus_line(
    rating: str | None,
    target_mean: float | None,
    opinion_count: int | None,
    target_high: float | None,
    target_low: float | None,
    target_median: float | None,
    rating_score: float | None,
    *,
    live: bool = True,
) -> str | None:
    """The Street's view WITH its disagreement left in.

    "buy, target $322.82" reads as a precision the consensus does not have: the
    same consensus is 41 analysts spanning $215–$400, and the mean sits below
    the median. `recommendationKey` is a bucketing of `recommendationMean`, so a
    2.1 and a 2.9 both render as "buy" — the score is carried with its scale
    named rather than left to be inferred from a word.

    Still explicitly the Street's view and NOT company guidance, which yfinance
    does not expose. The whole line is suppressed with the mean under CR035's
    ablation flag, at the fetch site: an arm that stripped the target but left
    the high/low standing would leak the figure it exists to remove.
    """
    if not rating and target_mean is None:
        return None
    head = f"{rating or '—'}"
    if rating_score is not None:
        head += f" (mean score {rating_score} on 1=strong buy … 5=sell)"
    if opinion_count is not None:
        head += f", {opinion_count} analysts"
    targets = []
    if target_mean is not None:
        targets.append(f"${target_mean:.2f} mean")
    if target_median is not None:
        targets.append(f"${target_median:.2f} median")
    if target_low is not None and target_high is not None:
        targets.append(f"${target_low:.2f}–${target_high:.2f} range")
    marker = " (LIVE, Street view — NOT company guidance)" if live else " (Street view, not company guidance)"
    line = f"Analyst consensus{marker}: {head}"
    if targets:
        line += ", target " + " / ".join(targets)
    return line


def identity_line(
    long_name: str | None, ticker: str, exchange_name: str | None
) -> str:
    """Which instrument this whole sheet is about (CR168, folded into CR166).

    A company NAME reached the model in 156/216 = 72.2% of production prompts
    and never as identity — always incidentally, through a news headline that
    happened to spell it out. It fell to 66.7% under Batch 9's recency floor and
    to 0% for AMD, AVGO and KTOS; in the AAPL corpus the prompt names Nvidia,
    Amazon and OpenAI, and never Apple. Prophylactic rather than a fix (0
    wrong-company instances in 216 turns), so nothing is claimed for it.

    NOT domain-gated: this is the SUBJECT of the run, not one desk's data, and
    an agent that cannot name the company it is analysing is not firewalled,
    it is lost. An absent name renders as the ticker alone — NBIS returns
    `longName: null` with a live exchange, and that half-populated identity is
    the acceptance fixture.
    """
    head = f"{long_name} ({ticker})" if long_name else ticker
    if exchange_name:
        return f"Instrument: {head} — {exchange_name}"
    return f"Instrument: {head}"


def peg_part(peg_ratio: str | None, peg_basis: str | None) -> str | None:
    """The PEG fragment of the valuation line, carrying its denominator when
    the provider declared one (DEF233).

    Once the P/E line states two bases, an unlabelled PEG beside it is the same
    ambiguity one field over — `trailingPegRatio` divides the *trailing*
    multiple by growth, so it moves with the figure the Room was over-weighting.
    Shared by both renderers for the same reason `pe_line` is.
    """
    if not peg_ratio:
        return None
    if peg_basis:
        return f"PEG {peg_ratio} ({peg_basis} basis)"
    return f"PEG {peg_ratio}"


def fetch_next_earnings(ticker: str):
    """Upcoming-earnings window (date / quarter / consensus EPS) for the 1-on-1
    fundamentals block (DEF098).

    The Room already surfaces next-earnings from
    `get_market_data_provider().earnings()`, but the 1-on-1 fundamentals path
    never fetched it, so the single analyst in a 1-on-1 saw a strictly poorer
    fact-sheet than the same analyst in the Room — the drop the prompt-data
    parity guard exists to forbid. Mirrors `room_runner`'s fetch (same provider,
    same 90-day window, same never-raises contract) rather than inventing a
    second earnings path. Returns None on any error or when nothing is within
    the window.
    """
    try:
        return get_market_data_provider().earnings(ticker.upper().strip())
    except Exception as exc:
        logger.warn("fundamentals_earnings_error", ticker=ticker, error=str(exc)[:200])
        return None


def build_live_data_block(ticker: str, agent_id: AgentId | None = None) -> str | None:
    """Compose a system-prompt-ready block of live numeric fundamentals.

    Returns None when:
      - use_real_market_data is disabled (tests, dev),
      - yfinance errored / had no data for this ticker.

    The caller appends this to the agent's system prompt. The Room
    surface uses a richer profile via `_format_profile`; this is the
    lean version for 1-on-1 chat where the agent doesn't have a full
    Room scenario built around the ticker.

    CR219 R24 — `agent_id=None` renders the FULL, ungated block and is the
    default, for the same reason `_format_profile(profile, agent_id=None)`
    defaults to full (room_prompts.py): non-Room callers and
    `test_prompt_data_parity.py` ask "is this computed field rendered
    anywhere at all", and the lane split must not change that answer. The
    1-on-1 chat runner (`agent_runner.py`) is the one caller that knows a
    real agent id and passes it, which is what actually closes the gap: the
    Room already lane-gates the four analysts via `_AGENT_LANES`
    (room_prompts.py:1790), but this block did not, so a 1-on-1 Fundamentals
    Analyst received the same price/momentum lines its own persona forbids
    it to cite.

    Reuses `_AGENT_LANES` / `_lane_for` from `room_prompts.py` rather than
    forking a second lane table (the WP04 instruction) — imported inside the
    function body because `room_prompts.py` imports THIS module at its own
    top level, so a top-level import back here would be circular. The same
    deferred-import shape already exists at `prompt_version.py:162` for the
    identical reason.
    """
    if not settings.use_real_market_data:
        return None
    data = fetch_live_fundamentals(ticker)
    if not data:
        return None
    # noqa: PLC0415 — breaks an import cycle, see the docstring above.
    from app.services.room_prompts import _ALL_DOMAINS, _DOMAIN_LABELS, _lane_for

    lane = _lane_for(agent_id)

    def _in_lane(domain: str) -> bool:
        return domain in lane

    sym = ticker.upper()
    today = datetime.now(timezone.utc).date()
    # DEF124/D2/D3: same run-date anchor as the Room's `_format_profile` —
    # a bare absolute date below (next-earnings) has no "today" for the
    # model to subtract from otherwise. D4: UTC calendar date, same basis
    # the Room uses, so the two surfaces can't disagree on "how many days".
    lines = [
        f"─── LIVE MARKET DATA — {sym} — as of {today.isoformat()} (UTC) ───"
    ]
    # CR040/CR219 R24 — a withheld lane announces itself instead of silently
    # vanishing, same principle as the Room's `_out_of_lane_line`, worded
    # differently on purpose: the Room can truthfully say "another analyst on
    # this desk holds it", but a 1-on-1 chat has no other analyst in the
    # conversation to point to — that claim would be false here. Omitted
    # entirely when nothing is withheld (agent_id=None, or an agent absent
    # from `_AGENT_LANES`), so every pre-R24 caller's output is unchanged.
    if lane != _ALL_DOMAINS:
        withheld = [_DOMAIN_LABELS[d] for d in ("fundamentals", "technicals", "news", "social")
                    if d not in lane]
        if withheld:
            lines.append(
                "Not shown in this chat: " + "; ".join(withheld) + ". That is a "
                "division of labour on this desk, not missing data — do not "
                "estimate or infer it, and do not tell the user it is unavailable."
            )
    # Identity and the reference quote are core, unconditional — same
    # reasoning as the Room's `_reference_price_line`: every agent needs a
    # price to reason about the portfolio block, and it is not what the
    # lane firewall withholds.
    lines.append(identity_line(data.get("long_name"), sym, data.get("exchange_name")))
    if "base_price" in data:
        lines.append(f"Price: ${data['base_price']}")
    if _in_lane("fundamentals"):
        if "pe" in data or "forward_pe" in data:
            lines.append(pe_line(data.get("pe"), data.get("forward_pe")))
        # CR219 R37 — same builder, same order, same wording as the Room
        # sheet (parity rule above).
        hist_line = historical_multiples_line(
            data.get("historical_pe_median"), data.get("historical_pe_years"),
            data.get("historical_pe_window"),
            data.get("historical_ev_ebitda_median"), data.get("historical_ev_ebitda_years"),
            data.get("historical_ev_ebitda_window"),
            live=False,
        )
        if hist_line:
            lines.append(hist_line)
        # CR219 R21-DATA — same builders, same order, same wording as the
        # Room sheet (parity rule above). Explicitly guarded, same reason
        # `hist_line` is above: this function's own `"\n".join(lines)` at
        # the bottom has no None-filtering.
        revisions_line = eps_revisions_line(
            data.get("eps_revisions_direction"), data.get("eps_revisions_pct"),
            data.get("eps_revisions_current"), data.get("eps_revisions_window_days"),
            live=False,
        )
        if revisions_line:
            lines.append(revisions_line)
        surprise_line = surprise_history_line(
            data.get("surprise_quarters"), data.get("surprise_actuals"),
            data.get("surprise_estimates"), data.get("surprise_pcts"),
            live=False,
        )
        if surprise_line:
            lines.append(surprise_line)
        if "rev_growth" in data:
            lines.append(f"TTM revenue growth: {data['rev_growth']}%")
        # Net margin is no longer stated here — it is the third term of the
        # `Margin structure` line below (CR166 Tier B). Two statements of one figure
        # is the defect `_reference_price_line` had to reconcile for price.
        if "net_cash" in data:
            phrase = net_position_phrase(data["net_cash"])  # "net cash $X M" / "net debt $Y M"
            lines.append(phrase[:1].upper() + phrase[1:])
        # CR145 Tier A — same three fields the Room renders, on the same line shape,
        # so the two surfaces cannot state a different size for the same company.
        size_parts = []
        if "market_cap" in data:
            size_parts.append(f"market cap ${data['market_cap']:,}M")
        if "free_cash_flow" in data:
            size_parts.append(f"FCF ${data['free_cash_flow']:,}M (TTM)")
        if "total_debt" in data:
            size_parts.append(f"gross debt ${data['total_debt']:,}M")
        if "total_cash" in data:
            size_parts.append(f"gross cash ${data['total_cash']:,}M")
        if size_parts:
            lines.append("Company size: " + ", ".join(size_parts))
        # CR166 Tier B — same builders, same order, same wording as the Room sheet.
        for builder in (
            margin_structure_line(
                data.get("gross_margin"), data.get("operating_margin"),
                data.get("profit_margin"), live=False,
            ),
            margin_trend_line(
                data.get("gross_margin_trend_bps"),
                data.get("operating_margin_trend_bps"),
                data.get("net_margin_trend_bps"),
                data.get("margin_trend_basis"), live=False,
            ),
            buyback_line(
                data.get("buyback_ttm"), data.get("buyback_yield"), live=False,
            ),
            # CR219 R35 — same builder, same order, same wording as the Room
            # sheet (parity rule above).
            buyback_pacing_line(
                data.get("buyback_quarterly"), data.get("buyback_quarterly_basis"),
                data.get("buyback_pace"), live=False,
            ),
            capital_return_line(
                data.get("capital_return_ttm"), data.get("buyback_ttm"),
                data.get("dividends_paid_ttm"), data.get("capital_return_pct_fcf"),
                live=False,
            ),
            # CR219 R34 — same builder, same order, same wording as the Room
            # sheet (parity rule above).
            capex_line(data.get("capex_ttm"), live=False),
            # CR221 C3/C4 — same builder, same order, same wording as the
            # Room sheet (parity rule above), behind the same flag.
            cashflow_bridge_line(
                data.get("operating_cash_flow_ttm"), data.get("capex_ttm"),
                data.get("free_cash_flow_ttm"), data.get("cashflow_ttm_basis"),
                data.get("wc_change_ttm"), data.get("wc_receivables_ttm"),
                data.get("wc_inventory_ttm"), data.get("wc_payables_ttm"),
                data.get("free_cash_flow"), live=False,
            ) if settings.room_cashflow_bridge_enabled else None,
            # CR221 C2/C5 — same builders, same order, same wording as the
            # Room sheet (parity rule above), behind the same flags.
            fcf_history_line(
                data.get("fcf_history_years"), data.get("fcf_history"),
                data.get("capex_history"), live=False,
            ) if settings.room_fcf_history_enabled else None,
            fcf_conversion_line(
                data.get("fcf_history_years"), data.get("fcf_conversion_pct"),
                live=False,
            ) if settings.room_fcf_conversion_enabled else None,
            # CR219 R33 — same builder, same order, same wording as the Room
            # sheet (parity rule above).
            interest_coverage_line(
                data.get("interest_coverage"), data.get("interest_coverage_quarter"),
                live=False,
            ),
            earnings_power_line(
                data.get("trailing_eps"), data.get("revenue_ttm"),
                data.get("revenue_per_share"), live=False,
            ),
            returns_line(data.get("return_on_equity"), data.get("return_on_assets"), live=False),
            balance_sheet_line(
                data.get("current_ratio"), data.get("quick_ratio"),
                data.get("debt_to_equity"), live=False,
            ),
            ownership_line(
                data.get("held_pct_institutions"), data.get("held_pct_insiders"),
                data.get("shares_outstanding"), data.get("float_shares"), live=False,
            ),
        ):
            if builder:
                lines.append(builder)
    if _in_lane("technicals"):
        # CR179 Leg 3 — same builders, same order, same wording as the Room
        # sheet. CR219 R24: the Room lane-gates these to the technicals desk
        # (room_prompts.py `_in_lane("technicals")`, same domain as RSI/trend/
        # range below); this block now applies the identical gate, closing
        # the gap where a 1-on-1 Fundamentals Analyst received day-move,
        # 200-day trend, relative strength, volume, beta and short interest —
        # all subject matter its own persona denies having.
        for builder in (
            day_move_line(data.get("day_change_pct"), data.get("market_state"), live=False),
            primary_trend_line(
                data.get("sma_200"), data.get("price_vs_sma_200_pct"), live=False,
            ),
            relative_strength_line(
                data.get("change_52w_pct"), data.get("change_52w_sp500_pct"),
                data.get("relative_strength_52w_pct"), live=False,
            ),
            liquidity_line(
                data.get("volume_today"), data.get("volume_avg_3m"), live=False,
            ),
            risk_profile_line(data.get("beta"), live=False),
            short_interest_line(
                data.get("short_pct_float"), data.get("short_days_to_cover"),
                data.get("short_interest_date"), live=False,
            ),
        ):
            if builder:
                lines.append(builder)
    # 52-week range is dual-lane, same reasoning as the Room's `week52` line
    # (room_prompts.py): a price RANGE is fundamentals-or-technicals subject
    # matter depending on which desk you ask, so either lane keeps it.
    if ("low" in data and "high" in data) and (_in_lane("fundamentals") or _in_lane("technicals")):
        if data.get("week52_range_live"):
            lines.append(f"52-week range: ${data['low']}–${data['high']}")
        else:
            lines.append(
                f"Recent range (±5% placeholder — real 52-week range unavailable): "
                f"${data['low']}–${data['high']}"
            )
    if _in_lane("fundamentals"):
        multiples = []
        if "price_to_sales" in data:
            multiples.append(f"P/S {data['price_to_sales']}x")
        if "ev_to_ebitda" in data:
            multiples.append(f"EV/EBITDA {data['ev_to_ebitda']}x")
        peg = peg_part(data.get("peg_ratio"), data.get("peg_basis"))
        if peg:
            multiples.append(peg)
        if "fcf_yield" in data:
            multiples.append(f"FCF yield {data['fcf_yield']}%")
        if multiples:
            lines.append("Valuation: " + ", ".join(multiples))
    # Fetched BEFORE the dividend line rather than after it (CR166 Tier B): the
    # ex-date and the indicated rate ride this same object (CR030), so the
    # dividend line cannot be composed until it has been called. Fetched
    # unconditionally — `earnings` also backs the dual-lane next-earnings
    # line below, which fundamentals OR news may render.
    earnings = fetch_next_earnings(ticker)
    if _in_lane("fundamentals"):
        dividend = dividend_line(
            data.get("dividend_yield"),
            earnings.dividend_rate if earnings else None,
            data.get("payout_ratio"),
            earnings.ex_dividend_date if earnings else None,
            today=today,
            live=False,
        )
        if dividend:
            lines.append(dividend)
        if "sector" in data or "industry" in data:
            lines.append(
                f"Sector/industry: {data.get('sector', '—')} / {data.get('industry', '—')}"
            )
        consensus = analyst_consensus_line(
            data.get("analyst_rating"),
            data.get("analyst_target_price"),
            data.get("analyst_opinion_count"),
            data.get("analyst_target_high"),
            data.get("analyst_target_low"),
            data.get("analyst_target_median"),
            data.get("analyst_rating_score"),
            live=False,
        )
        if consensus:
            lines.append(consensus)
    # Real next-earnings window (DEF098) — date + quarter + consensus EPS, so the
    # 1-on-1 fundamentals block reaches parity with the Room's `_format_profile`,
    # which has surfaced this since DEF053. Same wording as the Room line.
    # Dual-lane like the Room's `next_earnings` (room_prompts.py): a scheduled
    # earnings date is a forward catalyst as much as a fundamentals fact.
    if earnings and earnings.earnings_date and (_in_lane("fundamentals") or _in_lane("news")):
        # DEF124/D1: interval alongside the date, same pattern (and same
        # shared helper) as the Room line — never asked of the model.
        interval = relative_day_phrase(date.fromisoformat(earnings.earnings_date), today)
        line = f"Next earnings (LIVE): {earnings.earnings_date}"
        if earnings.quarter:
            line += f" ({earnings.quarter})"
        line += f" — {interval}"
        if earnings.eps_estimate is not None:
            line += f", consensus EPS est. ${earnings.eps_estimate}"
        lines.append(line)
    lines.append(
        f"(yfinance live snapshot for {sym}. Use these numbers when "
        f"discussing {sym}. Do NOT cite figures from training memory; "
        f"if a number isn't above, qualify your claim or omit it.)"
    )
    return "\n".join(lines)
