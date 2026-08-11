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
from datetime import date, datetime, timezone
from typing import Any

from app.core.config import settings
from app.core.logging import logger
from app.core.time import relative_day_phrase
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
      industry, analyst_target_price, analyst_rating

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
    free_cash_flow = _num("freeCashflow")
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
    today = datetime.now(timezone.utc).date()
    # DEF124/D2/D3: same run-date anchor as the Room's `_format_profile` —
    # a bare absolute date below (next-earnings) has no "today" for the
    # model to subtract from otherwise. D4: UTC calendar date, same basis
    # the Room uses, so the two surfaces can't disagree on "how many days".
    lines = [
        f"─── LIVE MARKET DATA — {sym} — as of {today.isoformat()} (UTC) ───"
    ]
    if "base_price" in data:
        lines.append(f"Price: ${data['base_price']}")
    if "pe" in data or "forward_pe" in data:
        lines.append(pe_line(data.get("pe"), data.get("forward_pe")))
    if "rev_growth" in data:
        lines.append(f"TTM revenue growth: {data['rev_growth']}%")
    if "profit_margin" in data:
        lines.append(f"Profit margin: {data['profit_margin']}%")
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
    if size_parts:
        lines.append("Company size: " + ", ".join(size_parts))
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
    peg = peg_part(data.get("peg_ratio"), data.get("peg_basis"))
    if peg:
        multiples.append(peg)
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
