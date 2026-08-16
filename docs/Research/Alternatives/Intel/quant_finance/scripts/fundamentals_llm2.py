#!/usr/bin/env python3
"""
Fundamentals -> LLM interpretation, v2: BOTH data sources + market context.

Why both sources rather than one:
  * yfinance .info  -- business summary, sector, employees, beta, free cash
                       flow, dividend yield, price/book. Descriptive context.
  * OpenBB          -- 5 periods x 40/70/54 fields of income/balance/cash
                       statements, plus a 35-field metrics block that includes
                       ratios yfinance lacks (e.g. ebitda_margin).
  Neither is a superset. Together they also enable CROSS-VERIFICATION: where
  the two disagree on the same quantity, we surface the conflict explicitly
  instead of silently trusting one. (A real example: yfinance .info reported
  AAPL totalDebt $84.34B while the balance sheet showed $98.66B.)

Market context is included as DESCRIPTIVE background only. Prior testing in
this project established these indicators have no usable predictive power
(see Docs/lgbm_results.md), so the prompt states that explicitly to stop the
model treating them as a forecast.

Usage:
    python3 fundamentals_llm2.py AAPL
    python3 fundamentals_llm2.py AAPL MSFT NVDA
    python3 fundamentals_llm2.py AAPL --raw
    python3 fundamentals_llm2.py AAPL --no-openbb      # yfinance only (fast)
    python3 fundamentals_llm2.py AAPL --no-market      # skip price context
"""
import argparse
import sys
import warnings

import numpy as np
import pandas as pd
import requests
import yfinance as yf

warnings.filterwarnings("ignore")

LLM_URL = "http://localhost:8000/v1/chat/completions"
LLM_MODEL = "ami-llm"
TIMEOUT = 900


# --------------------------------------------------------------------------
# formatting
# --------------------------------------------------------------------------
def money(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "n/a"
    try:
        v = float(v)
    except (TypeError, ValueError):
        return str(v)
    for unit, div in (("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if abs(v) >= div:
            return f"${v/div:,.2f}{unit}"
    return f"${v:,.0f}"


def pct(v, already=False):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "n/a"
    try:
        return f"{float(v) * (1 if already else 100):.2f}%"
    except (TypeError, ValueError):
        return str(v)


def num(v, dp=2):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "n/a"
    try:
        return f"{float(v):,.{dp}f}"
    except (TypeError, ValueError):
        return str(v)


# --------------------------------------------------------------------------
# sources
# --------------------------------------------------------------------------
def from_yfinance(ticker):
    t = yf.Ticker(ticker)
    info = t.info
    if not info or info.get("marketCap") is None:
        raise ValueError("no data")
    hist = t.history(period="1y", auto_adjust=True)
    return {"info": info, "hist": hist}


def from_openbb(ticker):
    """Deep statements + metrics. Returns {} on any failure (optional source)."""
    try:
        from openbb import obb
    except ImportError:
        return {}
    out = {}
    for key, fn in (
        ("metrics", lambda: obb.equity.fundamental.metrics(
            ticker, provider="yfinance")),
        ("income", lambda: obb.equity.fundamental.income(
            ticker, provider="yfinance")),
        ("balance", lambda: obb.equity.fundamental.balance(
            ticker, provider="yfinance")),
        ("cash", lambda: obb.equity.fundamental.cash(
            ticker, provider="yfinance")),
    ):
        try:
            out[key] = fn().to_df()
        except Exception:
            pass
    return out


# --------------------------------------------------------------------------
# cross-verification
# --------------------------------------------------------------------------
# (label, yfinance .info key, OpenBB metrics column, comparison tolerance)
CHECKS = [
    ("Trailing P/E", "trailingPE", "pe_ratio", 0.05),
    ("Forward P/E", "forwardPE", "forward_pe", 0.05),
    ("PEG ratio", "pegRatio", "peg_ratio", 0.10),
    ("Return on equity", "returnOnEquity", "return_on_equity", 0.05),
    ("Return on assets", "returnOnAssets", "return_on_assets", 0.05),
    ("Gross margin", "grossMargins", "gross_margin", 0.05),
    ("Operating margin", "operatingMargins", "operating_margin", 0.05),
    ("Net margin", "profitMargins", "profit_margin", 0.05),
    ("Debt / Equity", "debtToEquity", "debt_to_equity", 0.05),
    ("Current ratio", "currentRatio", "current_ratio", 0.05),
    ("Quick ratio", "quickRatio", "quick_ratio", 0.05),
    ("Market cap", "marketCap", "market_cap", 0.02),
]


# Balance-sheet checks: .info summary figures vs the actual filed statement.
# This is where the real-world disagreements show up -- e.g. AAPL .info
# totalDebt $84.34B vs balance sheet total_debt $98.66B. Comparing .info only
# against OpenBB's metrics block misses these entirely.
BALANCE_CHECKS = [
    ("Total debt (vs balance sheet)", "totalDebt", "total_debt", 0.05),
    ("Total cash (vs balance sheet)", "totalCash",
     "cash_and_cash_equivalents", 0.05),
]


def cross_verify(info, ob):
    """Compare the same quantity across both sources; report disagreements."""
    agree, conflict = [], []

    # --- .info vs the most recent filed balance sheet ---
    bal = ob.get("balance")
    if bal is not None and not bal.empty:
        latest = bal.iloc[-1] if "period_ending" not in bal.columns else \
            bal.sort_values("period_ending").iloc[-1]
        for label, ykey, bkey, tol in BALANCE_CHECKS:
            yv, bv = info.get(ykey), latest.get(bkey)
            if yv is None or bv is None or pd.isna(bv):
                continue
            try:
                yv, bv = float(yv), float(bv)
            except (TypeError, ValueError):
                continue
            denom = max(abs(yv), abs(bv), 1e-9)
            if abs(yv - bv) / denom <= tol:
                agree.append((label, yv, bv, "agree"))
            else:
                conflict.append((label, yv, bv))

    if "metrics" not in ob or ob["metrics"].empty:
        return agree, conflict
    m = ob["metrics"].iloc[0]
    for label, ykey, okey, tol in CHECKS:
        yv, ov = info.get(ykey), m.get(okey)
        if yv is None or ov is None or pd.isna(ov):
            continue
        try:
            yv, ov = float(yv), float(ov)
        except (TypeError, ValueError):
            continue
        # yfinance stores margins as fractions, debtToEquity as a percent-like
        # number; normalise before comparing magnitudes.
        a, b = abs(yv), abs(ov)
        if max(a, b) > 0 and min(a, b) > 0:
            ratio = max(a, b) / min(a, b)
            # tolerate a pure 100x unit difference (fraction vs percent)
            if 95 < ratio < 105:
                agree.append((label, yv, ov, "unit difference (x100)"))
                continue
        denom = max(abs(yv), abs(ov), 1e-9)
        if abs(yv - ov) / denom <= tol:
            agree.append((label, yv, ov, "agree"))
        else:
            conflict.append((label, yv, ov))
    return agree, conflict


# --------------------------------------------------------------------------
# market context (DESCRIPTIVE ONLY -- not predictive, see module docstring)
# --------------------------------------------------------------------------
def market_context(hist):
    if hist is None or hist.empty or len(hist) < 60:
        return None
    c = hist["Close"]
    r = c.pct_change()
    last = c.iloc[-1]
    hi, lo = c.max(), c.min()
    return {
        "last_close": last,
        "ret_1m": c.iloc[-1] / c.iloc[-21] - 1 if len(c) > 21 else None,
        "ret_3m": c.iloc[-1] / c.iloc[-63] - 1 if len(c) > 63 else None,
        "ret_12m": c.iloc[-1] / c.iloc[0] - 1,
        "vol_ann": r.std() * np.sqrt(252),
        "off_52w_high": last / hi - 1,
        "off_52w_low": last / lo - 1,
        "px_vs_ma200": (last / c.rolling(200).mean().iloc[-1] - 1
                        if len(c) >= 200 else None),
    }


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------
# NOTE: these must match OpenBB's actual column names. Earlier versions used
# "total_equity"/"total_liabilities", which do NOT exist in the yfinance
# provider's schema -- they rendered as nothing, leaving the model to guess
# equity. Both local models then mis-derived it (assets - debt instead of
# assets - liabilities) and wrongly declared the D/E ratio impossible.
STATEMENT_ROWS = {
    "income": ["total_revenue", "gross_profit", "operating_income",
               "research_and_development_expense", "net_income",
               "diluted_earnings_per_share"],
    "balance": ["total_assets", "total_liabilities_net_minority_interest",
                "common_stock_equity", "total_debt", "net_debt",
                "cash_and_cash_equivalents"],
    "cash": ["net_cash_from_operating_activities", "capital_expenditure",
             "free_cash_flow", "repurchase_of_capital_stock"],
}


def _period_labels(df):
    """Prefer an explicit period_ending column; fall back to the index."""
    if "period_ending" in df.columns:
        return [str(p)[:10] for p in df["period_ending"]]
    return [str(i)[:10] for i in df.index]


def render_statements(ob):
    lines = []
    for key in ("income", "balance", "cash"):
        df = ob.get(key)
        if df is None or df.empty:
            continue
        cols = [c for c in STATEMENT_ROWS[key] if c in df.columns]
        if not cols:
            cols = [c for c in df.columns if df[c].dtype.kind in "if"][:6]
        labels = _period_labels(df)
        sub = df[cols].copy()
        sub.index = labels
        # drop periods with no data at all for the selected rows
        sub = sub.dropna(how="all")
        if sub.empty:
            continue
        sub = sub.tail(5)
        lines.append(f"\n{key.upper()} STATEMENT (OpenBB, {len(sub)} periods)")
        lines.append(" " * 42 + "".join(f"{p:>16s}" for p in sub.index))
        for c in cols:
            vals = "".join(f"{money(v):>16s}" for v in sub[c])
            lines.append(f"  {c:<40s}{vals}")
    return "\n".join(lines)


def derived_from_statements(ob):
    """Ratios computed straight from the filed balance sheet.

    The summary metrics above are TTM/most-recent-quarter; the statements are
    ANNUAL. Mixing them silently caused both local models to misread the D/E
    ratio, so we compute the annual figures explicitly and label the basis.
    """
    bal = ob.get("balance")
    if bal is None or bal.empty:
        return ""
    b = bal.dropna(subset=["total_assets"]) if "total_assets" in bal.columns \
        else bal.dropna(how="all")
    if b.empty:
        return ""
    r = b.iloc[0] if "period_ending" not in b.columns else \
        b.sort_values("period_ending").iloc[-1]
    period = str(r.get("period_ending", "latest"))[:10]

    assets = r.get("total_assets")
    liab = r.get("total_liabilities_net_minority_interest")
    eq = r.get("common_stock_equity")
    debt = r.get("total_debt")
    cash = r.get("cash_and_cash_equivalents")

    L = [f"\nDERIVED FROM FILED BALANCE SHEET (annual, period ending {period})",
         "  These are computed from the statement above. The ratios in the",
         "  summary sections are TTM / most-recent-quarter and are therefore",
         "  on a DIFFERENT basis -- do not treat a gap as an error by itself."]
    def line(lbl, val):
        L.append(f"  {lbl:<40s}{val:>20s}")
    if eq is not None and not pd.isna(eq):
        line("Shareholders' equity", money(eq))
    if debt is not None and eq:
        line("Debt / Equity (annual)", f"{debt/eq:.2f}x  ({debt/eq*100:.1f}%)")
    if debt is not None and cash is not None:
        line("Net debt (debt - cash)", money(debt - cash))
    if liab is not None and assets:
        line("Liabilities / Assets", f"{liab/assets:.2f}x")
    if eq is not None and assets:
        line("Equity / Assets", f"{eq/assets:.2f}x")
    return "\n".join(L)


def build_brief(d):
    info, ob, mkt = d["info"], d["openbb"], d["market"]
    agree, conflict = d["agree"], d["conflict"]
    L = []
    L.append("=" * 88)
    L.append(f"{info.get('longName', d['ticker'])}  ({d['ticker']})")
    L.append(f"Sector: {info.get('sector','n/a')}  |  Industry: "
             f"{info.get('industry','n/a')}  |  Country: {info.get('country','n/a')}")
    if info.get("fullTimeEmployees"):
        L.append(f"Employees: {info['fullTimeEmployees']:,}")
    L.append("=" * 88)

    if info.get("longBusinessSummary"):
        L.append(f"\nBUSINESS\n{info['longBusinessSummary'][:900]}")

    L.append("\nVALUATION  [basis: current price / TTM or forward earnings]")
    for lbl, k, f in [("Trailing P/E", "trailingPE", num),
                      ("Forward P/E", "forwardPE", num),
                      ("PEG ratio", "pegRatio", num),
                      ("Price / Book", "priceToBook", num),
                      ("EV / EBITDA", "enterpriseToEbitda", num),
                      ("Price / Sales", "priceToSalesTrailing12Months", num)]:
        L.append(f"  {lbl:<34s}{f(info.get(k)):>20s}")

    L.append("\nPROFITABILITY  [basis: TTM]")
    for lbl, k in [("Gross margin", "grossMargins"),
                   ("Operating margin", "operatingMargins"),
                   ("Net margin", "profitMargins"),
                   ("Return on equity", "returnOnEquity"),
                   ("Return on assets", "returnOnAssets")]:
        L.append(f"  {lbl:<34s}{pct(info.get(k)):>20s}")
    if "metrics" in ob and not ob["metrics"].empty:
        eb = ob["metrics"].iloc[0].get("ebitda_margin")
        if eb is not None and not pd.isna(eb):
            L.append(f"  {'EBITDA margin (OpenBB)':<34s}{pct(eb):>20s}")

    L.append("\nGROWTH")
    for lbl, k in [("Revenue growth (YoY)", "revenueGrowth"),
                   ("Earnings growth (YoY)", "earningsGrowth"),
                   ("Earnings growth (QoQ)", "earningsQuarterlyGrowth")]:
        L.append(f"  {lbl:<34s}{pct(info.get(k)):>20s}")

    L.append("\nLEVERAGE & LIQUIDITY  [basis: most recent quarter (MRQ)]")
    L.append(f"  {'Debt / Equity (MRQ, % form)':<34s}"
             f"{num(info.get('debtToEquity')):>20s}")
    for lbl, k in [("Current ratio", "currentRatio"), ("Quick ratio", "quickRatio")]:
        L.append(f"  {lbl:<34s}{num(info.get(k)):>20s}")
    for lbl, k in [("Total debt", "totalDebt"), ("Total cash", "totalCash")]:
        L.append(f"  {lbl:<34s}{money(info.get(k)):>20s}")

    L.append("\nCASH FLOW & SCALE  [basis: TTM]")
    for lbl, k in [("Free cash flow", "freeCashflow"),
                   ("Operating cash flow", "operatingCashflow"),
                   ("EBITDA", "ebitda"), ("Revenue (TTM)", "totalRevenue"),
                   ("Market cap", "marketCap"),
                   ("Enterprise value", "enterpriseValue")]:
        L.append(f"  {lbl:<34s}{money(info.get(k)):>20s}")
    L.append(f"  {'Beta':<34s}{num(info.get('beta')):>20s}")
    L.append(f"  {'Dividend yield':<34s}{pct(info.get('dividendYield'), True):>20s}")

    if ob:
        L.append(render_statements(ob))
        L.append(derived_from_statements(ob))

    # ---- cross-source verification block ----
    if agree or conflict:
        L.append("\nDATA CROSS-VERIFICATION (yfinance vs OpenBB)")
        L.append(f"  {len(agree)} metric(s) agree across both sources.")
        if conflict:
            L.append(f"  !! {len(conflict)} DISAGREEMENT(S) -- treat these with caution:")
            for lbl, yv, ov in conflict:
                L.append(f"     {lbl:<30s} yfinance={yv:<16,.4f} OpenBB={ov:,.4f}")
        else:
            L.append("  No conflicts detected.")

    if mkt:
        L.append("\nMARKET CONTEXT (descriptive background only -- NOT predictive)")
        L.append(f"  {'Last close':<34s}{money(mkt['last_close']):>20s}")
        for lbl, k in [("Return 1M", "ret_1m"), ("Return 3M", "ret_3m"),
                       ("Return 12M", "ret_12m")]:
            L.append(f"  {lbl:<34s}{pct(mkt.get(k)):>20s}")
        L.append(f"  {'Annualised volatility':<34s}{pct(mkt['vol_ann']):>20s}")
        L.append(f"  {'Below 52w high':<34s}{pct(mkt['off_52w_high']):>20s}")
        L.append(f"  {'Above 52w low':<34s}{pct(mkt['off_52w_low']):>20s}")
        if mkt.get("px_vs_ma200") is not None:
            L.append(f"  {'Price vs 200d MA':<34s}{pct(mkt['px_vs_ma200']):>20s}")
    L.append("")
    return "\n".join(L)


# --------------------------------------------------------------------------
# LLM
# --------------------------------------------------------------------------
SYSTEM = (
    "You are an experienced equity research analyst. You interpret financial "
    "statement data rigorously and plainly, and you commit to a view. Ground "
    "every claim in the figures provided and cite them. If a figure is missing, "
    "internally inconsistent, or the two data sources disagree, say so "
    "explicitly rather than smoothing over it or inventing a value. "
    "State your conclusions directly -- do not hedge into uselessness. "
    "Separate what the data shows from what you infer, and be explicit about "
    "which is which."
)

SINGLE = """Analyse the fundamental data below.

1. **Financial health** - leverage, liquidity, cash generation. Is the balance sheet sound?
2. **Profitability & quality** - margins and returns on capital. High-quality business? Durable?
3. **Growth** - what the multi-period statement trend actually shows.
4. **Valuation** - what the multiples imply about embedded expectations, and why.
5. **Data quality** - comment on any cross-source disagreements or internally inconsistent figures flagged below, and state which source you would trust and why.
6. **Red flags / watch items** - anything warranting scrutiny.
7. **Bottom line** - 3-4 sentences.

8. **VERDICT** - commit to a call. State clearly, each on its own line:
   - **Rating: BUY / HOLD / SELL**
   - **Conviction: HIGH / MEDIUM / LOW**
   - **Confidence: NN%** - a single integer 0-100: the probability you would
     assign to your rating being the right call over your stated time frame.
     Use the FULL range and make it mean something. 50% means a coin flip you
     have no real edge on; 90% should be rare and reserved for cases where the
     figures are unambiguous. Do not default to 70-80% out of politeness.
   - **Data confidence: NN%** - a separate integer 0-100 for how much you trust
     the underlying DATA, independent of your analytical view. Lower this when
     figures are missing, the two sources disagree materially, or the bases are
     inconsistent. A confident view built on questionable data should show a
     HIGH confidence and a LOW data confidence - do not blend them into one
     number.
   - **Primary uncertainty:** one short phrase naming the single biggest thing
     you are unsure about.
   - **Time frame** your view applies over.

9. **SCENARIOS** - give a probability-weighted distribution of outcomes over
   your stated time frame. Write these as exactly three lines in this format,
   with a price target in dollars for each:

   - **Bear case: NN% probability, target $NNN** - one line on what drives it.
   - **Base case: NN% probability, target $NNN** - one line on what drives it.
   - **Bull case: NN% probability, target $NNN** - one line on what drives it.

   - **Fair value: $NNN** - your single-point estimate of what the business is
     worth per share today on these fundamentals.

   The three probabilities MUST sum to exactly 100. The targets must be
   absolute per-share prices in dollars, not percentages and not multiples.
   Anchor them to the current share price given in the data. Do NOT compute a
   weighted average or expected value yourself - just give the three
   probability/target pairs and the fair value; the arithmetic is done
   downstream.
   - **The 2-3 things that most drive the call**, citing figures.
   - **What would change your mind** - the specific observable that would flip the rating.
   - **Your view on the current price** relative to what the fundamentals justify.

   Do not refuse to give a rating and do not retreat into "consult a financial
   advisor". Give your actual assessment. Do flag genuine uncertainty through
   the confidence numbers rather than by declining to answer.

{brief}"""

PEER = """Compare the companies below on their fundamentals.

1. **Head-to-head** - key differences in valuation, margins, returns, leverage.
2. **Highest-quality business** on the numbers, and why.
3. **Most attractively valued** relative to fundamentals, and why.
4. **Data quality** - note any cross-source disagreements flagged and how much they affect the comparison.
5. **Key risks** visible in each company's data.
6. **Bottom line** - short ranked verdict. Note where comparison is unfair (different models/sectors).

7. **VERDICT** - for EACH company give:
   - **Rating: BUY / HOLD / SELL** and **Conviction: HIGH / MEDIUM / LOW**
   - **Confidence: NN%** (integer 0-100, probability your rating is the right
     call) and **Data confidence: NN%** (separate integer, how much you trust
     the underlying figures). Keep these two distinct - a strong view on weak
     data is high confidence with low data confidence.
   - One-line rationale citing the figures that drive it.
   Then rank them best-to-worst as investments right now and say which single
   one you would put new money into, and why. Commit to an answer.

{brief}"""


def ask_llm(brief, peer, think, max_tokens):
    content = (PEER if peer else SINGLE).format(brief=brief)
    if not think:
        content += "\n/no_think"
    r = requests.post(LLM_URL, json={
        "model": LLM_MODEL,
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": content}],
        "temperature": 0.3, "max_tokens": max_tokens,
    }, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()["choices"][0]["message"].get("content", "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--raw", action="store_true")
    ap.add_argument("--think", action="store_true")
    ap.add_argument("--no-openbb", action="store_true")
    ap.add_argument("--no-market", action="store_true")
    ap.add_argument("--max-tokens", type=int, default=5000)
    args = ap.parse_args()

    briefs = []
    for tk in args.tickers:
        tk = tk.upper()
        try:
            y = from_yfinance(tk)
        except Exception as e:
            print(f"[FAILED]  {tk}: {e}", file=sys.stderr)
            continue
        ob = {} if args.no_openbb else from_openbb(tk)
        agree, conflict = cross_verify(y["info"], ob)
        mkt = None if args.no_market else market_context(y["hist"])
        briefs.append(build_brief({
            "ticker": tk, "info": y["info"], "openbb": ob,
            "market": mkt, "agree": agree, "conflict": conflict}))
        src = "yfinance" + ("+OpenBB" if ob else "")
        flag = f", {len(conflict)} CONFLICT(S)" if conflict else ""
        print(f"[fetched] {tk:6s} via {src}"
              f" ({len(agree)} metrics cross-checked{flag})", file=sys.stderr)

    if not briefs:
        sys.exit("no data fetched")
    brief = "\n".join(briefs)

    if args.raw:
        print(brief)
        return
    print(f"[sending {len(brief):,} chars to {LLM_MODEL}]", file=sys.stderr)
    print(ask_llm(brief, len(briefs) > 1, args.think, args.max_tokens))


if __name__ == "__main__":
    main()
