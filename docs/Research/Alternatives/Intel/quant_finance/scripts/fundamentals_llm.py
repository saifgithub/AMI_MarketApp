#!/usr/bin/env python3
"""
Fundamentals -> LLM interpretation pipeline.

Fetches a company's fundamental data, formats it into a structured analyst
brief, and sends it to the local vLLM fleet for interpretation.

This is DATA + INTERPRETATION, not prediction. No forecasting model is
involved -- the earlier experiments established that price prediction from
this data does not work; interpreting the financial position of a business
is a different and far more tractable task.

Usage:
    python3 fundamentals_llm.py AAPL
    python3 fundamentals_llm.py AAPL MSFT NVDA        # peer comparison
    python3 fundamentals_llm.py AAPL --raw            # print data, skip LLM
    python3 fundamentals_llm.py AAPL --think          # enable reasoning mode
"""
import argparse
import json
import sys

import pandas as pd
import requests
import yfinance as yf

LLM_URL = "http://localhost:8000/v1/chat/completions"
LLM_MODEL = "ami-llm"          # Qwen3.6-35B-A3B-NVFP4 on the local fleet
TIMEOUT = 600

# metric -> (label, kind) ; kind drives formatting
METRICS = {
    "valuation": [
        ("trailingPE", "Trailing P/E", "x"),
        ("forwardPE", "Forward P/E", "x"),
        ("pegRatio", "PEG ratio", "x"),
        ("priceToBook", "Price / Book", "x"),
        ("enterpriseToEbitda", "EV / EBITDA", "x"),
        ("priceToSalesTrailing12Months", "Price / Sales", "x"),
    ],
    "profitability": [
        ("grossMargins", "Gross margin", "pct"),
        ("operatingMargins", "Operating margin", "pct"),
        ("profitMargins", "Net margin", "pct"),
        ("returnOnEquity", "Return on equity (ROE)", "pct"),
        ("returnOnAssets", "Return on assets (ROA)", "pct"),
    ],
    "growth": [
        ("revenueGrowth", "Revenue growth (YoY)", "pct"),
        ("earningsGrowth", "Earnings growth (YoY)", "pct"),
        ("earningsQuarterlyGrowth", "Earnings growth (QoQ)", "pct"),
    ],
    "leverage_liquidity": [
        ("debtToEquity", "Debt / Equity", "raw"),
        ("currentRatio", "Current ratio", "x"),
        ("quickRatio", "Quick ratio", "x"),
        ("totalDebt", "Total debt", "money"),
        ("totalCash", "Total cash", "money"),
    ],
    "cash_flow": [
        ("freeCashflow", "Free cash flow", "money"),
        ("operatingCashflow", "Operating cash flow", "money"),
        ("ebitda", "EBITDA", "money"),
    ],
    "scale_market": [
        ("marketCap", "Market cap", "money"),
        ("enterpriseValue", "Enterprise value", "money"),
        ("totalRevenue", "Revenue (TTM)", "money"),
        ("beta", "Beta", "x"),
        ("dividendYield", "Dividend yield", "pct_raw"),
    ],
}


def fmt(val, kind):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "n/a"
    try:
        if kind == "money":
            v = float(val)
            for unit, div in (("T", 1e12), ("B", 1e9), ("M", 1e6)):
                if abs(v) >= div:
                    return f"${v/div:,.2f}{unit}"
            return f"${v:,.0f}"
        if kind == "pct":
            return f"{float(val)*100:.2f}%"
        if kind == "pct_raw":
            return f"{float(val):.2f}%"
        if kind == "x":
            return f"{float(val):.2f}"
        return f"{float(val):,.2f}"
    except (TypeError, ValueError):
        return str(val)


def get_fundamentals(ticker):
    t = yf.Ticker(ticker)
    info = t.info
    if not info or info.get("marketCap") is None:
        raise ValueError(f"no fundamental data returned for {ticker}")

    out = {
        "ticker": ticker,
        "name": info.get("longName", ticker),
        "sector": info.get("sector", "n/a"),
        "industry": info.get("industry", "n/a"),
        "country": info.get("country", "n/a"),
        "employees": info.get("fullTimeEmployees"),
        "summary": (info.get("longBusinessSummary") or "")[:900],
        "metrics": {},
        "_raw": info,
    }
    for group, items in METRICS.items():
        out["metrics"][group] = [
            (label, fmt(info.get(key), kind)) for key, label, kind in items
        ]

    # multi-period statement trends (what changed, not just today's snapshot)
    out["trends"] = {}
    for name, attr in (("income", "financials"),
                       ("balance", "balance_sheet"),
                       ("cashflow", "cashflow")):
        try:
            df = getattr(t, attr)
            if df is not None and not df.empty:
                out["trends"][name] = df.iloc[:, :4]   # 4 most recent periods
        except Exception:
            pass
    return out


ROWS_OF_INTEREST = {
    "income": ["Total Revenue", "Gross Profit", "Operating Income",
               "Net Income", "Diluted EPS", "Research And Development"],
    "balance": ["Total Assets", "Total Debt", "Stockholders Equity",
                "Cash And Cash Equivalents", "Total Liabilities Net Minority Interest"],
    "cashflow": ["Operating Cash Flow", "Free Cash Flow", "Capital Expenditure",
                 "Repurchase Of Capital Stock"],
}


def render_trends(trends):
    lines = []
    for name, df in trends.items():
        wanted = [r for r in ROWS_OF_INTEREST.get(name, []) if r in df.index]
        if not wanted:
            continue
        sub = df.loc[wanted]
        cols = [c.strftime("%Y-%m-%d") if hasattr(c, "strftime") else str(c)
                for c in sub.columns]
        lines.append(f"\n{name.upper()} STATEMENT (most recent {len(cols)} periods)")
        lines.append("  " + " " * 42 + "  ".join(f"{c:>14s}" for c in cols))
        for row in wanted:
            vals = "  ".join(f"{fmt(v,'money'):>14s}" for v in sub.loc[row])
            lines.append(f"  {row:<42s}{vals}")
    return "\n".join(lines)


def build_brief(datas):
    """Render one or more companies into a single analyst brief."""
    parts = []
    for d in datas:
        parts.append("=" * 78)
        parts.append(f"{d['name']}  ({d['ticker']})")
        parts.append(f"Sector: {d['sector']}  |  Industry: {d['industry']}"
                     f"  |  Country: {d['country']}")
        if d.get("employees"):
            parts.append(f"Employees: {d['employees']:,}")
        parts.append("=" * 78)
        if d["summary"]:
            parts.append(f"\nBUSINESS\n{d['summary']}")
        for group, items in d["metrics"].items():
            parts.append(f"\n{group.replace('_',' ').upper()}")
            for label, val in items:
                parts.append(f"  {label:<32s} {val:>18s}")
        if d["trends"]:
            parts.append(render_trends(d["trends"]))
        parts.append("")
    return "\n".join(parts)


SYSTEM = (
    "You are an experienced equity research analyst. You interpret financial "
    "statement data rigorously and plainly. Ground every claim in the numbers "
    "provided; when a figure is missing or looks anomalous, say so rather than "
    "inventing it. Do not predict share prices or give investment advice - "
    "assess the financial condition and quality of the business."
)

PROMPT_SINGLE = """Analyse the fundamental data below.

Cover:
1. **Financial health** - leverage, liquidity, and cash generation. Is the balance sheet sound?
2. **Profitability & quality** - margins and returns on capital. Is this a high-quality business, and are the returns durable?
3. **Growth** - what the revenue/earnings trend shows across the periods given.
4. **Valuation** - what the multiples imply about embedded expectations. Expensive or cheap relative to the fundamentals shown, and why?
5. **Red flags / watch items** - anything in the data that warrants scrutiny (declining margins, rising debt, cash flow diverging from earnings, unusual ratios).
6. **Bottom line** - 3-4 sentence summary of the financial picture.

Be specific and cite the actual figures. Flag anything that looks internally inconsistent.

{brief}"""

PROMPT_PEER = """Compare the companies below on their fundamentals.

Cover:
1. **Head-to-head table** - key differences in valuation, margins, returns, leverage.
2. **Who is the highest-quality business** on the numbers, and why.
3. **Who is most attractively valued** relative to the fundamentals, and why.
4. **Key risks** visible in each company's data.
5. **Bottom line** - a short ranked verdict with reasoning.

Cite actual figures throughout. Note where a comparison is unfair (different
business models, sectors, or accounting treatments).

{brief}"""


def ask_llm(brief, peer=False, think=False, max_tokens=4000):
    tmpl = PROMPT_PEER if peer else PROMPT_SINGLE
    content = tmpl.format(brief=brief)
    # Qwen3.6 runs markedly faster with reasoning disabled and is accurate
    # for structured analytical tasks in this mode.
    if not think:
        content += "\n/no_think"

    payload = {
        "model": LLM_MODEL,
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": content}],
        "temperature": 0.3,
        "max_tokens": max_tokens,
    }
    r = requests.post(LLM_URL, json=payload, timeout=TIMEOUT)
    r.raise_for_status()
    msg = r.json()["choices"][0]["message"]
    reasoning = msg.get("reasoning") or msg.get("reasoning_content")
    return msg.get("content", ""), reasoning


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--raw", action="store_true", help="print data only, no LLM")
    ap.add_argument("--think", action="store_true", help="enable reasoning mode")
    ap.add_argument("--max-tokens", type=int, default=4000)
    args = ap.parse_args()

    datas = []
    for t in args.tickers:
        try:
            datas.append(get_fundamentals(t.upper()))
            print(f"[fetched] {t.upper()}", file=sys.stderr)
        except Exception as e:
            print(f"[FAILED]  {t.upper()}: {e}", file=sys.stderr)
    if not datas:
        sys.exit("no data fetched")

    brief = build_brief(datas)
    if args.raw:
        print(brief)
        return

    print(f"[sending {len(brief):,} chars to {LLM_MODEL}]", file=sys.stderr)
    answer, reasoning = ask_llm(brief, peer=len(datas) > 1,
                                think=args.think, max_tokens=args.max_tokens)
    if reasoning:
        print("--- reasoning ---", file=sys.stderr)
        print(reasoning[:2000], file=sys.stderr)
    print(answer)


if __name__ == "__main__":
    main()
