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
      base_price, pe, rev_growth, fcf_margin, net_cash, low, high,
      support, breakout, price_to_sales, ev_to_ebitda, peg_ratio,
      fcf_yield, dividend_yield, sector, industry, analyst_target_price,
      analyst_rating

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
    if pe is not None:
        out["pe"] = f"{pe:.1f}"
    rev_growth = _num("revenueGrowth")
    if rev_growth is not None:
        # yfinance reports growth as a decimal (0.05 = 5%).
        out["rev_growth"] = round(rev_growth * 100)
    profit_margin = _num("profitMargins")
    if profit_margin is not None:
        out["fcf_margin"] = round(profit_margin * 100)
    # totalCash / totalDebt are dollars; net cash in millions for the prompt.
    total_cash = _num("totalCash")
    total_debt = _num("totalDebt")
    if total_cash is not None and total_debt is not None:
        out["net_cash"] = round((total_cash - total_debt) / 1_000_000)

    # Real valuation multiples beyond P/E (DEF053) — closes the "P/S,
    # EV/EBITDA, FCF yield" overclaim without a second provider.
    price_to_sales = _num("priceToSalesTrailing12Months")
    if price_to_sales is not None:
        out["price_to_sales"] = f"{price_to_sales:.1f}"
    ev_to_ebitda = _num("enterpriseToEbitda")
    if ev_to_ebitda is not None:
        out["ev_to_ebitda"] = f"{ev_to_ebitda:.1f}"
    peg_ratio = _num("pegRatio")
    if peg_ratio is not None:
        out["peg_ratio"] = f"{peg_ratio:.2f}"
    free_cash_flow = _num("freeCashflow")
    market_cap = _num("marketCap")
    if free_cash_flow is not None and market_cap is not None and market_cap > 0:
        out["fcf_yield"] = round(free_cash_flow / market_cap * 100, 1)

    # Real capital allocation (dividends only — buybacks/M&A have no
    # yfinance field and stay undisclosed rather than fabricated).
    dividend_yield = _num("dividendYield")
    if dividend_yield is not None:
        out["dividend_yield"] = round(dividend_yield, 2)

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
    if "fcf_margin" in data:
        lines.append(f"Profit margin: {data['fcf_margin']}%")
    if "net_cash" in data:
        lines.append(f"Net cash: ${data['net_cash']}M")
    if "low" in data and "high" in data:
        lines.append(f"52-week range: ${data['low']}–${data['high']}")
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
    lines.append(
        f"(yfinance live snapshot for {sym}. Use these numbers when "
        f"discussing {sym}. Do NOT cite figures from training memory; "
        f"if a number isn't above, qualify your claim or omit it.)"
    )
    return "\n".join(lines)
