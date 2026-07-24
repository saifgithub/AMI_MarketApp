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
from typing import Any

from app.core.config import settings
from app.core.logging import logger
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

_yf_convention_checked = False


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


def fetch_live_fundamentals(ticker: str) -> dict[str, Any] | None:
    """Fetch real fundamentals via yfinance. Returns None on any error.

    Returned dict keys (all optional — missing fields mean yfinance
    didn't have them for this ticker):
      base_price, pe, rev_growth, profit_margin, net_cash, low, high,
      week52_range_live, support, breakout, price_to_sales, ev_to_ebitda,
      peg_ratio, fcf_yield, dividend_yield, sector, industry,
      analyst_target_price, analyst_rating

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
    peg_ratio = _num("trailingPegRatio")
    if peg_ratio is None:
        peg_ratio = _num("pegRatio")
    if peg_ratio is not None:
        out["peg_ratio"] = f"{peg_ratio:.2f}"
    free_cash_flow = _num("freeCashflow")
    market_cap = _num("marketCap")
    fcf_yield = fcf_yield_pct(free_cash_flow, market_cap)
    if fcf_yield is not None:
        out["fcf_yield"] = fcf_yield

    # Real capital allocation (dividends only — buybacks/M&A have no
    # yfinance field and stay undisclosed rather than fabricated).
    dividend_yield = _num("dividendYield")
    if dividend_yield is not None:
        out["dividend_yield"] = dividend_yield_pct(dividend_yield)

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

    # Real analyst consensus — the closest honest proxy for "forward
    # guidance" available (a company's own guidance figures aren't
    # exposed by yfinance; this is the Street's view, labeled as such).
    # CR035: suppressible for ablation benchmarks — omitting the keys here
    # drops the consensus line from both the Room profile and the 1-on-1
    # data block (_analyst_line returns None when the keys are absent).
    if not settings.suppress_analyst_consensus:
        analyst_target = _num("targetMeanPrice")
        if analyst_target is not None:
            out["analyst_target_price"] = round(analyst_target, 2)
        rating = info.get("recommendationKey")
        if rating and rating != "none":
            out["analyst_rating"] = str(rating).replace("_", " ")

    return out


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


def build_live_data_block(ticker: str) -> str | None:
    """Compose a system-prompt-ready block of live numeric fundamentals.

    Returns None when:
      - use_real_market_data is disabled (tests, dev),
      - yfinance errored / had no data for this ticker.

    The caller appends this to the agent's system prompt. The Room
    surface uses a richer profile via `_format_profile`; this is the
    lean version for 1-on-1 chat where the agent doesn't have a full
    Room scenario built around the ticker.
    """
    if not settings.use_real_market_data:
        return None
    data = fetch_live_fundamentals(ticker)
    if not data:
        return None
    sym = ticker.upper()
    lines = [f"─── LIVE MARKET DATA — {sym} ───"]
    if "base_price" in data:
        lines.append(f"Price: ${data['base_price']}")
    if "pe" in data:
        lines.append(f"P/E: {data['pe']}")
    if "rev_growth" in data:
        lines.append(f"TTM revenue growth: {data['rev_growth']}%")
    if "profit_margin" in data:
        lines.append(f"Profit margin: {data['profit_margin']}%")
    if "net_cash" in data:
        phrase = net_position_phrase(data["net_cash"])  # "net cash $X M" / "net debt $Y M"
        lines.append(phrase[:1].upper() + phrase[1:])
    if "low" in data and "high" in data:
        if data.get("week52_range_live"):
            lines.append(f"52-week range: ${data['low']}–${data['high']}")
        else:
            lines.append(
                f"Recent range (±5% placeholder — real 52-week range unavailable): "
                f"${data['low']}–${data['high']}"
            )
    multiples = []
    if "price_to_sales" in data:
        multiples.append(f"P/S {data['price_to_sales']}x")
    if "ev_to_ebitda" in data:
        multiples.append(f"EV/EBITDA {data['ev_to_ebitda']}x")
    if "peg_ratio" in data:
        multiples.append(f"PEG {data['peg_ratio']}")
    if "fcf_yield" in data:
        multiples.append(f"FCF yield {data['fcf_yield']}%")
    if multiples:
        lines.append("Valuation: " + ", ".join(multiples))
    if "dividend_yield" in data:
        lines.append(f"Dividend yield: {data['dividend_yield']}%")
    if "sector" in data or "industry" in data:
        lines.append(f"Sector/industry: {data.get('sector', '—')} / {data.get('industry', '—')}")
    if "analyst_target_price" in data or "analyst_rating" in data:
        lines.append(
            f"Analyst consensus: {data.get('analyst_rating', '—')}, "
            f"target ${data.get('analyst_target_price', '—')} "
            f"(Street view, not company guidance)"
        )
    # Real next-earnings window (DEF098) — date + quarter + consensus EPS, so the
    # 1-on-1 fundamentals block reaches parity with the Room's `_format_profile`,
    # which has surfaced this since DEF053. Same wording as the Room line.
    earnings = fetch_next_earnings(ticker)
    if earnings and earnings.earnings_date:
        line = f"Next earnings (LIVE): {earnings.earnings_date}"
        if earnings.quarter:
            line += f" ({earnings.quarter})"
        if earnings.eps_estimate is not None:
            line += f", consensus EPS est. ${earnings.eps_estimate}"
        lines.append(line)
    lines.append(
        f"(yfinance live snapshot for {sym}. Use these numbers when "
        f"discussing {sym}. Do NOT cite figures from training memory; "
        f"if a number isn't above, qualify your claim or omit it.)"
    )
    return "\n".join(lines)
