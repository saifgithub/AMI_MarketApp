#!/usr/bin/env python3
"""
Market-analyst data layer: the inputs a market analyst actually works from.

This is a SEPARATE LENS from the fundamentals brief, deliberately. A
fundamental analyst asks "what is this business worth"; a market analyst asks
"what is the tape saying and what is the regime". Keeping the two briefs apart
means the two views can be compared on the same name instead of being blended
into one muddy answer.

Coverage relative to the categories a market analyst normally uses:

  price & volume ............ yes  (OHLCV, 1y-2y daily)
  derived technicals ........ yes  (MA stack, RSI, Bollinger, ATR, drawdown)
  relative strength ......... yes  (vs SPY and vs the name's own sector ETF)
  cross-asset / intermarket . yes  (SPY, VIX, 10Y, dollar, credit, oil, gold)
  market breadth ............ yes  (computed across the full 503-name universe)
  positioning ............... partial (short interest, insider/institutional)
  options / implied vol ..... partial (ATM IV + put/call open interest)
  macro releases ............ NO   (needs FRED; not wired up)
  microstructure ............ NO   (needs paid tick/order-book data)

Everything here is free via yfinance. The expensive call is breadth (~14s for
503 names), so the regime block is fetched ONCE per run and shared across every
ticker rather than re-fetched per name.

IMPORTANT CONTEXT, kept out of the prompt on purpose: Phase 1 of this project
tested price-derived technical features for predictive power and found none
(see Docs/lgbm_results.md). Telling the model that up front would just make it
hedge, so the prompt asks for its genuine read. The caveat belongs in the
write-up of the results, not in the question.
"""
import warnings

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

# GICS sector -> the sector ETF a market analyst would benchmark against.
SECTOR_ETF = {
    "Information Technology": "XLK", "Health Care": "XLV",
    "Financials": "XLF", "Consumer Discretionary": "XLY",
    "Communication Services": "XLC", "Industrials": "XLI",
    "Consumer Staples": "XLP", "Energy": "XLE",
    "Utilities": "XLU", "Real Estate": "XLRE", "Materials": "XLB",
}

# Cross-asset series. Each says something distinct about the backdrop:
#   SPY  = equity trend        VIX  = fear / implied vol
#   ^TNX = 10y yield           ^FVX = 5y (curve shape vs 10y)
#   DX-Y.NYB = dollar          HYG/LQD = credit risk appetite
#   CL=F = oil (inflation)     GC=F = gold (real rates / haven)
CROSS_ASSET = {
    "SPY": "S&P 500 (SPY)", "^VIX": "VIX", "^TNX": "US 10y yield",
    "^FVX": "US 5y yield", "DX-Y.NYB": "US dollar index",
    "HYG": "High-yield credit (HYG)", "LQD": "IG credit (LQD)",
    "CL=F": "Crude oil", "GC=F": "Gold",
}


# --------------------------------------------------------------------------
# indicators
# --------------------------------------------------------------------------
def rsi(s, n=14):
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def _ret(c, n):
    return c.iloc[-1] / c.iloc[-n - 1] - 1 if len(c) > n else None


def technicals(hist):
    """Per-ticker technical state from a daily OHLCV frame."""
    if hist is None or hist.empty or len(hist) < 60:
        return None
    c, v = hist["Close"], hist["Volume"]
    r = c.pct_change()
    last = c.iloc[-1]
    out = {"last": last}

    for lbl, n in (("1w", 5), ("1m", 21), ("3m", 63), ("6m", 126), ("12m", 252)):
        out[f"ret_{lbl}"] = _ret(c, n)

    for w in (20, 50, 200):
        if len(c) >= w:
            ma = c.rolling(w).mean().iloc[-1]
            out[f"px_vs_ma{w}"] = last / ma - 1
            out[f"ma{w}"] = ma
    # Trend structure: the classic stacked-MA read.
    if all(f"ma{w}" in out for w in (20, 50, 200)):
        out["ma_stack"] = ("bullish (20>50>200)"
                           if out["ma20"] > out["ma50"] > out["ma200"]
                           else "bearish (20<50<200)"
                           if out["ma20"] < out["ma50"] < out["ma200"]
                           else "mixed / transitioning")

    out["rsi_14"] = rsi(c, 14).iloc[-1]
    m20, s20 = c.rolling(20).mean(), c.rolling(20).std()
    if not pd.isna(s20.iloc[-1]) and s20.iloc[-1] > 0:
        out["bollinger_z"] = (last - m20.iloc[-1]) / s20.iloc[-1]

    out["vol_20d_ann"] = r.rolling(20).std().iloc[-1] * np.sqrt(252)
    out["vol_60d_ann"] = r.rolling(60).std().iloc[-1] * np.sqrt(252)
    if out["vol_60d_ann"]:
        out["vol_regime"] = out["vol_20d_ann"] / out["vol_60d_ann"]

    win = min(252, len(c))
    hi, lo = c.rolling(win).max().iloc[-1], c.rolling(win).min().iloc[-1]
    out["off_52w_high"] = last / hi - 1
    out["off_52w_low"] = last / lo - 1
    out["max_drawdown_1y"] = (c.tail(win) / c.tail(win).cummax() - 1).min()

    out["vol_vs_avg"] = (v.iloc[-5:].mean() / v.rolling(60).mean().iloc[-1] - 1
                         if v.rolling(60).mean().iloc[-1] else None)

    # Support / resistance from recent swing extremes -- the levels a market
    # analyst would actually quote.
    tail = c.tail(126)
    out["support"] = tail.min()
    out["resistance"] = tail.max()
    return out


def relative_strength(hist, bench):
    """Ratio-line performance vs a benchmark over several windows."""
    if hist is None or bench is None or hist.empty or bench.empty:
        return {}
    a = hist["Close"] if isinstance(hist, pd.DataFrame) else hist
    b = bench["Close"] if isinstance(bench, pd.DataFrame) else bench
    # Ticker.history() returns a tz-AWARE index; yf.download() returns a
    # tz-NAIVE one. Joining them directly matches zero rows and silently
    # renders every relative-strength figure as n/a. Normalise to plain dates.
    a, b = a.copy(), b.copy()
    for s in (a, b):
        if getattr(s.index, "tz", None) is not None:
            s.index = s.index.tz_localize(None)
        s.index = s.index.normalize()
    j = pd.concat([a, b], axis=1, join="inner").dropna()
    if len(j) < 30:
        return {}
    x, y = j.iloc[:, 0], j.iloc[:, 1]
    out = {}
    for lbl, n in (("1m", 21), ("3m", 63), ("6m", 126), ("12m", 252)):
        if len(j) > n:
            out[f"rs_{lbl}"] = (x.iloc[-1] / x.iloc[-n - 1]) / \
                               (y.iloc[-1] / y.iloc[-n - 1]) - 1
    return out


# --------------------------------------------------------------------------
# regime (fetched ONCE per run, shared across tickers)
# --------------------------------------------------------------------------
def fetch_regime(universe_csv="data/sp500_universe.csv"):
    out = {"cross": {}, "breadth": {}, "series": {}}

    # 2y, not 1y: a 12-month return needs 253 rows and "1y" returns ~251,
    # which silently rendered every 12m column as n/a.
    px = yf.download(list(CROSS_ASSET), period="2y", interval="1d",
                     auto_adjust=True, progress=False, threads=True)["Close"]
    for sym, label in CROSS_ASSET.items():
        if sym not in px.columns:
            continue
        s = px[sym].dropna()
        if s.empty:
            continue
        out["series"][sym] = s
        d = {"label": label, "last": s.iloc[-1],
             "chg_1m": _ret(s, 21), "chg_3m": _ret(s, 63),
             "chg_12m": _ret(s, 252)}
        if len(s) >= 200:
            d["vs_ma200"] = s.iloc[-1] / s.rolling(200).mean().iloc[-1] - 1
        # Percentile rank locates the level in its own 1y range, which is how
        # a VIX or yield reading is normally judged.
        # Percentile is over the trailing year only, even though 2y is fetched.
        s1y = s.tail(252)
        d["pctile_1y"] = float((s1y < s.iloc[-1]).mean())
        out["cross"][sym] = d

    # Derived intermarket reads.
    if "HYG" in out["series"] and "LQD" in out["series"]:
        j = pd.concat([out["series"]["HYG"], out["series"]["LQD"]],
                      axis=1, join="inner").dropna()
        ratio = j.iloc[:, 0] / j.iloc[:, 1]
        out["cross"]["_credit_appetite"] = {
            "label": "Credit appetite (HYG/LQD ratio)",
            "last": ratio.iloc[-1], "chg_1m": _ret(ratio, 21),
            "chg_3m": _ret(ratio, 63), "pctile_1y": float(
                (ratio < ratio.iloc[-1]).mean())}
    if "^TNX" in out["series"] and "^FVX" in out["series"]:
        j = pd.concat([out["series"]["^TNX"], out["series"]["^FVX"]],
                      axis=1, join="inner").dropna()
        sp = j.iloc[:, 0] - j.iloc[:, 1]
        out["cross"]["_curve"] = {
            "label": "Yield curve 10y-5y (bp)",
            "last": sp.iloc[-1] * 100, "chg_1m": None, "chg_3m": None,
            "pctile_1y": float((sp < sp.iloc[-1]).mean())}

    # Breadth across the full index -- the single most useful "is the tape
    # healthy" input, and impossible to see from one ticker's chart.
    try:
        u = pd.read_csv(universe_csv)
        up = yf.download(u.ticker.tolist(), period="2y", interval="1d",
                         auto_adjust=True, progress=False,
                         threads=True)["Close"].dropna(axis=1, how="all")
        last = up.iloc[-1]
        out["breadth"] = {
            "n": int(up.shape[1]),
            "pct_above_200dma": float((last > up.rolling(200).mean().iloc[-1]).mean()),
            "pct_above_50dma": float((last > up.rolling(50).mean().iloc[-1]).mean()),
            "pct_up_1m": float((up.iloc[-1] / up.iloc[-22] - 1 > 0).mean()),
            "pct_up_3m": float((up.iloc[-1] / up.iloc[-64] - 1 > 0).mean()),
            "new_52w_highs": int((last >= up.rolling(252).max().iloc[-1] * 0.999).sum()),
            "new_52w_lows": int((last <= up.rolling(252).min().iloc[-1] * 1.001).sum()),
        }
    except Exception as e:
        out["breadth"] = {"error": str(e)[:120]}

    # Sector ETFs for relative strength.
    try:
        se = yf.download(list(set(SECTOR_ETF.values())), period="2y",
                         interval="1d", auto_adjust=True, progress=False,
                         threads=True)["Close"]
        out["sector_px"] = se
        spy = out["series"].get("SPY")
        if spy is not None:
            perf = {}
            for etf in se.columns:
                s = se[etf].dropna()
                if len(s) > 63:
                    perf[etf] = (s.iloc[-1] / s.iloc[-64] - 1) - \
                                (spy.iloc[-1] / spy.iloc[-64] - 1)
            out["sector_rs_3m"] = dict(sorted(perf.items(),
                                              key=lambda kv: -kv[1]))
    except Exception:
        out["sector_px"] = None
    return out


# --------------------------------------------------------------------------
# options (positioning / implied vol)
# --------------------------------------------------------------------------
def options_snapshot(ticker, spot):
    """Nearest-expiry ATM implied vol and put/call open interest."""
    try:
        t = yf.Ticker(ticker)
        exps = t.options
        if not exps:
            return {}
        ch = t.option_chain(exps[0])
        calls, puts = ch.calls, ch.puts
        if calls.empty or puts.empty:
            return {}
        atm_c = calls.iloc[(calls.strike - spot).abs().argsort()[:1]]
        atm_p = puts.iloc[(puts.strike - spot).abs().argsort()[:1]]
        iv_c = float(atm_c.impliedVolatility.iloc[0])
        iv_p = float(atm_p.impliedVolatility.iloc[0])
        oi_c, oi_p = calls.openInterest.sum(), puts.openInterest.sum()
        return {"expiry": exps[0], "atm_iv_call": iv_c, "atm_iv_put": iv_p,
                "iv_skew_put_minus_call": iv_p - iv_c,
                "put_call_oi": (float(oi_p / oi_c) if oi_c else None)}
    except Exception:
        return {}


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------
def _p(v, dp=1):
    return "n/a" if v is None or (isinstance(v, float) and pd.isna(v)) \
        else f"{v*100:.{dp}f}%"


def _n(v, dp=2):
    return "n/a" if v is None or (isinstance(v, float) and pd.isna(v)) \
        else f"{v:,.{dp}f}"


def render_regime(reg):
    """The shared market backdrop -- identical text for every ticker in a run."""
    L = ["=" * 88, "MARKET REGIME (as of this run -- shared across all names)",
         "=" * 88, "", "CROSS-ASSET",
         f"  {'series':<32s}{'last':>12s}{'1m':>10s}{'3m':>10s}"
         f"{'12m':>10s}{'1y %ile':>10s}"]
    for _, d in reg.get("cross", {}).items():
        L.append(f"  {d['label']:<32s}{_n(d.get('last')):>12s}"
                 f"{_p(d.get('chg_1m')):>10s}{_p(d.get('chg_3m')):>10s}"
                 f"{_p(d.get('chg_12m')):>10s}"
                 f"{_p(d.get('pctile_1y'),0):>10s}")
    b = reg.get("breadth", {})
    if b and "error" not in b:
        L += ["", f"BREADTH (across {b['n']} S&P 500 constituents)",
              f"  % above 200d MA                {_p(b['pct_above_200dma'])}",
              f"  % above 50d MA                 {_p(b['pct_above_50dma'])}",
              f"  % up over 1 month              {_p(b['pct_up_1m'])}",
              f"  % up over 3 months             {_p(b['pct_up_3m'])}",
              f"  new 52w highs / lows           {b['new_52w_highs']} / {b['new_52w_lows']}"]
    rs = reg.get("sector_rs_3m")
    if rs:
        L += ["", "SECTOR RELATIVE STRENGTH, 3m vs SPY (leaders first)"]
        L.append("  " + "  ".join(f"{k} {v*100:+.1f}%" for k, v in rs.items()))
    return "\n".join(L)


def build_market_brief(d):
    """Per-ticker market-analyst brief. `regime` is rendered separately once."""
    t, tech = d["ticker"], d["tech"]
    info, rs_spy, rs_sec = d.get("info", {}), d.get("rs_spy", {}), d.get("rs_sector", {})
    opt, sector = d.get("options", {}), d.get("sector", "n/a")
    L = ["=" * 88,
         f"{info.get('longName', t)}  ({t})",
         f"Sector: {sector}   Benchmark ETF: {SECTOR_ETF.get(sector,'n/a')}"
         f"   Beta: {_n(info.get('beta'))}",
         "=" * 88, "", "PRICE & TREND",
         f"  Last close                     ${_n(tech.get('last'))}",
         f"  Return 1w / 1m / 3m            {_p(tech.get('ret_1w'))} / "
         f"{_p(tech.get('ret_1m'))} / {_p(tech.get('ret_3m'))}",
         f"  Return 6m / 12m                {_p(tech.get('ret_6m'))} / "
         f"{_p(tech.get('ret_12m'))}",
         f"  Price vs 20d / 50d / 200d MA   {_p(tech.get('px_vs_ma20'))} / "
         f"{_p(tech.get('px_vs_ma50'))} / {_p(tech.get('px_vs_ma200'))}",
         f"  MA structure                   {tech.get('ma_stack','n/a')}",
         f"  Support / resistance (6m)      ${_n(tech.get('support'))} / "
         f"${_n(tech.get('resistance'))}",
         "", "MOMENTUM & EXTENSION",
         f"  RSI(14)                        {_n(tech.get('rsi_14'))}",
         f"  Bollinger z-score (20d)        {_n(tech.get('bollinger_z'))}",
         f"  Below 52w high                 {_p(tech.get('off_52w_high'))}",
         f"  Above 52w low                  {_p(tech.get('off_52w_low'))}",
         f"  Max drawdown (1y)              {_p(tech.get('max_drawdown_1y'))}",
         "", "VOLATILITY & VOLUME",
         f"  Realised vol 20d / 60d (ann)   {_p(tech.get('vol_20d_ann'))} / "
         f"{_p(tech.get('vol_60d_ann'))}",
         f"  Vol regime (20d/60d)           {_n(tech.get('vol_regime'))}x"
         f"  ({'expanding' if (tech.get('vol_regime') or 1) > 1.15 else 'contracting' if (tech.get('vol_regime') or 1) < 0.85 else 'stable'})",
         f"  5d volume vs 60d average       {_p(tech.get('vol_vs_avg'))}",
         "", "RELATIVE STRENGTH"]
    L.append("  vs SPY    1m/3m/6m/12m       " + " / ".join(
        _p(rs_spy.get(f"rs_{k}")) for k in ("1m", "3m", "6m", "12m")))
    L.append("  vs sector 1m/3m/6m/12m       " + " / ".join(
        _p(rs_sec.get(f"rs_{k}")) for k in ("1m", "3m", "6m", "12m")))

    L += ["", "POSITIONING",
          f"  Short % of float               {_p(info.get('shortPercentOfFloat'))}",
          f"  Short ratio (days to cover)    {_n(info.get('shortRatio'))}",
          f"  Held by institutions           {_p(info.get('heldPercentInstitutions'))}",
          f"  Held by insiders               {_p(info.get('heldPercentInsiders'))}"]
    if opt:
        L += ["", f"OPTIONS (nearest expiry {opt.get('expiry','n/a')})",
              f"  ATM implied vol call / put     {_p(opt.get('atm_iv_call'))} / "
              f"{_p(opt.get('atm_iv_put'))}",
              f"  Put-minus-call IV skew         {_p(opt.get('iv_skew_put_minus_call'))}",
              f"  Put/call open interest         {_n(opt.get('put_call_oi'))}"]
        iv, rv = opt.get("atm_iv_call"), tech.get("vol_20d_ann")
        if iv and rv:
            L.append(f"  Implied vs realised (20d)      {_n(iv/rv)}x "
                     f"({'implied rich' if iv/rv > 1.1 else 'implied cheap' if iv/rv < 0.9 else 'fair'})")
    return "\n".join(L)


MARKET_SYSTEM = (
    "You are an experienced market analyst. You read price action, trend "
    "structure, relative strength, volatility, positioning and the "
    "cross-asset backdrop, and you commit to a view. You are NOT valuing the "
    "business -- you have deliberately not been given financial statements. "
    "Ground every claim in the figures provided and cite them. If a figure is "
    "missing or internally inconsistent, say so rather than inventing one. "
    "Distinguish clearly between what the tape shows and what you infer from "
    "it. State your conclusions directly -- do not hedge into uselessness."
)

MARKET_SINGLE = """Give a market-analyst read on the name below.

You have NOT been given fundamentals. Do not speculate about valuation,
earnings quality or fair value from business logic -- work from the tape,
the regime and positioning only.

1. **Trend & structure** - where price sits against its moving-average stack, and what that says about the prevailing trend.
2. **Momentum & extension** - RSI, Bollinger position, distance from the 52w high/low. Is this extended, washed out, or mid-range?
3. **Volatility regime** - is volatility expanding or contracting, and what does that imply for risk?
4. **Relative strength** - performance against SPY and against its own sector. Is this a leader or a laggard, and is that changing?
5. **Market regime & breadth** - given the shared regime block, is the broad tape supportive or hostile? Does breadth confirm or diverge from the index?
6. **Cross-asset backdrop** - what rates, the dollar, credit appetite and commodities imply for THIS name specifically, given its sector.
7. **Positioning & options** - short interest, implied vs realised volatility, skew. Is positioning crowded or clean?
8. **Key levels** - the specific support and resistance that matter, and what a break of each would signal.

9. **VERDICT** - commit to a call. State clearly, each on its own line:
   - **Rating: BUY / HOLD / SELL**
   - **Conviction: HIGH / MEDIUM / LOW**
   - **Confidence: NN%** - integer 0-100, the probability your rating is the
     right call over your stated time frame. Use the FULL range and make it
     mean something; 50% is a coin flip, 90% should be rare. Do not default
     to 70-80%.
   - **Data confidence: NN%** - separate integer for how much you trust the
     inputs themselves, independent of your view.
   - **Primary uncertainty:** one short phrase.
   - **Time frame** your view applies over. A market view is normally shorter
     than a fundamental one - think weeks to a few months, and say which.
   - **The 2-3 things that most drive the call**, citing figures.
   - **What would change your mind** - the specific level or signal that flips it.

10. **SCENARIOS** - a probability-weighted distribution over your time frame.
   Exactly three lines in this format, with a dollar price target for each:

   - **Bear case: NN% probability, target $NNN** - one line on what drives it.
   - **Base case: NN% probability, target $NNN** - one line on what drives it.
   - **Bull case: NN% probability, target $NNN** - one line on what drives it.

   - **Fair value: $NNN** - the level you think price gravitates to on this
     technical/regime picture. (This is a tape-based estimate, not a valuation.)

   The three probabilities MUST sum to exactly 100. Targets must be absolute
   per-share dollar prices, anchored to the last close given above. Do NOT
   compute a weighted average or expected value yourself - just give the three
   probability/target pairs; the arithmetic is done downstream.

{brief}"""
