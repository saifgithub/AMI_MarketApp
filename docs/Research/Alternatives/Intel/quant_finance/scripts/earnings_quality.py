#!/usr/bin/env python3
"""
Earnings-quality / forensic-accounting lens.

A THIRD lens, and the cheapest of the three: it needs no new data at all --
every input is already in the OpenBB statements the fundamental collector
fetches. It asks a question neither existing lens asks.

  fundamental lens -> "what is this business worth?"
  market lens      -> "what is the tape saying?"
  quality lens     -> "are these earnings REAL?"

That distinction matters because the failure mode it targets is invisible to
the other two. A company can post excellent margins and returns -- which the
fundamental lens rewards -- while net income quietly diverges from cash flow,
receivables balloon relative to sales, or reported profit depends on unusual
items. Accrual-based anomalies are among the most durable documented effects in
accounting research (Sloan 1996), and they are exactly the sort of multi-period
cross-statement pattern a ratio screen misses.

What is computed (all from filed statements, 4-5 annual periods):

  cash backing ....... CFO/NI, FCF/NI, accrual ratio (Sloan), TATA
  working capital .... DSO, DPO, inventory days, and their TRENDS
  Beneish M-score .... full 8-factor model where inputs allow
  quality of profit .. normalized vs reported income, unusual items,
                       stock-based comp as % of revenue and of CFO
  reinvestment ....... capex vs D&A (under-investment inflates near-term FCF)
  balance risk ....... goodwill/assets, interest coverage
  dilution ........... diluted share count trend

Nothing here is a verdict on its own -- a high DSO can be a credit-terms
change, and a low capex/D&A can be a genuinely asset-light shift. The lens
surfaces the pattern and asks the model to weigh it, which is why the prompt
demands alternative innocent explanations before any red flag is called.
"""
import numpy as np
import pandas as pd


def _col(df, *names):
    """First matching column, else None. Schemas vary by company/provider."""
    for n in names:
        if df is not None and n in df.columns:
            return df[n]
    return None


def _ordered(ob, key):
    df = ob.get(key)
    if df is None or df.empty:
        return None
    if "period_ending" in df.columns:
        df = df.sort_values("period_ending")
        # OpenBB commonly returns an OLDEST period that is entirely empty --
        # every numeric field NaN. Keeping it renders a full column of "n/a"
        # and silently costs one of only 4-5 periods of trend. Drop it.
        num = df.select_dtypes(include="number")
        if not num.empty:
            # Threshold, not `.all()`: the stub row usually keeps a handful of
            # non-null fields, so requiring EVERY column to be NaN never fires.
            df = df[num.isna().mean(axis=1) < 0.9]
    return df


def _safe(a, b):
    try:
        if a is None or b is None or pd.isna(a) or pd.isna(b) or b == 0:
            return None
        return float(a) / float(b)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _mul365(v):
    """Ratio -> days, preserving None. Never coerce a missing value to zero."""
    return None if v is None else v * 365


def beneish_m(inc, bal, cash, i):
    """8-factor Beneish M-score comparing period i against i-1.

    M > -1.78 is the conventional flag for 'possible manipulation'. It is a
    SCREEN, not a finding -- false positives are common in fast-growing and
    acquisitive companies, and the prompt is told so explicitly.
    """
    if i < 1:
        return None, {}
    def g(df, *n):
        s = _col(df, *n)
        return (None, None) if s is None else (s.iloc[i], s.iloc[i - 1])

    rec_t, rec_p = g(bal, "accounts_receivable", "net_receivables")
    sal_t, sal_p = g(inc, "total_revenue", "operating_revenue")
    gp_t, gp_p = g(inc, "gross_profit")
    ca_t, ca_p = g(bal, "total_current_assets")
    ppe_t, ppe_p = g(bal, "plant_property_equipment_net")
    ta_t, ta_p = g(bal, "total_assets")
    dep_t, dep_p = g(cash, "depreciation", "depreciation_and_amortization")
    sga_t, sga_p = g(inc, "selling_general_and_admin_expense")
    cl_t, cl_p = g(bal, "current_liabilities")
    ltd_t, ltd_p = g(bal, "long_term_debt")
    ni_t, _ = g(inc, "net_income",
                "net_income_attributable_to_common_shareholders",
                "net_income_continuous_operations",
                "net_income_including_noncontrolling_interests")
    cfo_t, _ = g(cash, "operating_cash_flow")

    f = {}
    f["DSRI"] = _safe(_safe(rec_t, sal_t), _safe(rec_p, sal_p))
    f["GMI"] = _safe(_safe(gp_p, sal_p), _safe(gp_t, sal_t))
    aq_t = None if None in (ca_t, ppe_t, ta_t) else 1 - _safe(
        (ca_t or 0) + (ppe_t or 0), ta_t)
    aq_p = None if None in (ca_p, ppe_p, ta_p) else 1 - _safe(
        (ca_p or 0) + (ppe_p or 0), ta_p)
    f["AQI"] = _safe(aq_t, aq_p)
    f["SGI"] = _safe(sal_t, sal_p)
    f["DEPI"] = _safe(_safe(dep_p, (dep_p or 0) + (ppe_p or 0)),
                      _safe(dep_t, (dep_t or 0) + (ppe_t or 0)))
    f["SGAI"] = _safe(_safe(sga_t, sal_t), _safe(sga_p, sal_p))
    f["TATA"] = _safe((ni_t or 0) - (cfo_t or 0), ta_t)
    lev_t = _safe((cl_t or 0) + (ltd_t or 0), ta_t)
    lev_p = _safe((cl_p or 0) + (ltd_p or 0), ta_p)
    f["LVGI"] = _safe(lev_t, lev_p)

    w = {"DSRI": 0.920, "GMI": 0.528, "AQI": 0.404, "SGI": 0.892,
         "DEPI": 0.115, "SGAI": -0.172, "TATA": 4.679, "LVGI": -0.327}
    if sum(v is not None for v in f.values()) < 6:
        return None, f          # too many gaps for the score to mean anything
    m = -4.84 + sum(w[k] * (f[k] if f[k] is not None else 1.0) for k in w)
    return m, f


def compute(ob):
    """All earnings-quality metrics, most recent period last."""
    inc, bal, cash = (_ordered(ob, k) for k in ("income", "balance", "cash"))
    if inc is None or bal is None or cash is None:
        return None
    n = min(len(inc), len(bal), len(cash))
    if n < 2:
        return None
    inc, bal, cash = inc.iloc[-n:], bal.iloc[-n:], cash.iloc[-n:]

    periods = ([str(p)[:10] for p in inc["period_ending"]]
               if "period_ending" in inc.columns else [str(i) for i in inc.index])
    rows = []
    for i in range(n):
        # OpenBB's income schema VARIES BY COMPANY -- utilities and some
        # health-care names have no plain "net_income" column at all. A narrow
        # lookup rendered net income (and therefore CFO/NI and the accrual
        # ratio) as n/a for those, degrading the brief itself, not just the EV.
        ni = _col(inc, "net_income",
                  "net_income_attributable_to_common_shareholders",
                  "net_income_common_stockholders",
                  "net_income_continuous_operations",
                  "net_income_including_noncontrolling_interests",
                  "net_income_from_continuing_and_discontinued_operation")
        if ni is None:
            ni = _col(cash, "net_income_from_continuing_operations")
        cfo = _col(cash, "operating_cash_flow")
        fcf = _col(cash, "free_cash_flow")
        rev = _col(inc, "total_revenue", "operating_revenue")
        ta = _col(bal, "total_assets")
        rec = _col(bal, "accounts_receivable", "net_receivables")
        # OpenBB names this "inventories" (plural); "inventory" does not exist
        # and silently rendered every inventory-days cell as n/a -- including
        # for a grocer, which should have been the tell.
        inv = _col(bal, "inventories", "inventory")
        ap = _col(bal, "accounts_payable", "payables")
        cogs = _col(inc, "cost_of_revenue")
        dep = _col(cash, "depreciation_and_amortization", "depreciation")
        capex = _col(cash, "capital_expenditure")
        sbc = _col(cash, "stock_based_compensation")
        gw = _col(bal, "goodwill")
        norm = _col(inc, "normalized_income")
        unus = _col(inc, "total_unusual_items")
        ebit = _col(inc, "ebit")
        iexp = _col(inc, "interest_expense")
        sh = _col(inc, "weighted_average_diluted_shares_outstanding")
        defrev = _col(bal, "current_deferred_revenue")

        v = lambda s: (None if s is None else s.iloc[i])
        r = {"period": periods[i],
             "net_income": v(ni), "cfo": v(cfo), "fcf": v(fcf),
             "revenue": v(rev),
             "cfo_over_ni": _safe(v(cfo), v(ni)),
             "fcf_over_ni": _safe(v(fcf), v(ni)),
             # Sloan accrual ratio: the wider (NI - CFO) is relative to the
             # asset base, the more of reported profit is accrual rather than
             # cash. Persistently high values predict weak future earnings.
             "accrual_ratio": _safe((v(ni) or 0) - (v(cfo) or 0), v(ta)),
             # `or 0` would turn a MISSING numerator into a confident 0.0
             # days, which reads as "collects instantly" rather than "unknown".
             "dso_days": _mul365(_safe(v(rec), v(rev))),
             "dpo_days": _mul365(_safe(v(ap), v(cogs))),
             "inv_days": _mul365(_safe(v(inv), v(cogs))),
             "capex_over_da": _safe(abs(v(capex) or 0), v(dep)),
             "sbc_pct_revenue": _safe(v(sbc), v(rev)),
             "sbc_pct_cfo": _safe(v(sbc), v(cfo)),
             "goodwill_pct_assets": _safe(v(gw), v(ta)),
             "normalized_vs_reported": _safe(v(norm), v(ni)),
             "unusual_items": v(unus),
             "interest_coverage": _safe(v(ebit), abs(v(iexp) or 0) or None),
             "diluted_shares": v(sh),
             "deferred_revenue": v(defrev)}
        rows.append(r)

    m, factors = beneish_m(inc, bal, cash, n - 1)
    return {"rows": rows, "beneish_m": m, "beneish_factors": factors}


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------
def _f(v, dp=2, pct=False, x=""):
    if v is None or (isinstance(v, float) and (pd.isna(v) or np.isinf(v))):
        return "n/a"
    return f"{v*100:.{dp}f}%" if pct else f"{v:,.{dp}f}{x}"


def _money(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "n/a"
    for u, d in (("T", 1e12), ("B", 1e9), ("M", 1e6)):
        if abs(v) >= d:
            return f"${v/d:,.2f}{u}"
    return f"${v:,.0f}"


def build_quality_brief(d):
    q, t, info = d["quality"], d["ticker"], d.get("info", {})
    rows = q["rows"]
    hdr = "".join(f"{r['period']:>16s}" for r in rows)
    L = ["=" * 92,
         f"{info.get('longName', t)}  ({t})",
         f"Sector: {d.get('sector','n/a')}   "
         f"EARNINGS QUALITY / FORENSIC REVIEW",
         "=" * 92,
         "",
         "All figures below are from the FILED ANNUAL STATEMENTS "
         f"({len(rows)} periods, oldest first).",
         "", f"{'':<38s}{hdr}"]

    def line(lbl, key, **kw):
        L.append(f"  {lbl:<36s}" + "".join(
            f"{_f(r.get(key), **kw):>16s}" for r in rows))

    def mline(lbl, key):
        L.append(f"  {lbl:<36s}" + "".join(
            f"{_money(r.get(key)):>16s}" for r in rows))

    L.append("\nCASH BACKING OF EARNINGS")
    mline("Net income", "net_income")
    mline("Operating cash flow", "cfo")
    mline("Free cash flow", "fcf")
    line("CFO / net income", "cfo_over_ni", x="x")
    line("FCF / net income", "fcf_over_ni", x="x")
    line("Accrual ratio (NI-CFO)/assets", "accrual_ratio", pct=True)

    L.append("\nWORKING CAPITAL")
    line("Days sales outstanding", "dso_days", dp=1, x="d")
    line("Days payable outstanding", "dpo_days", dp=1, x="d")
    line("Inventory days", "inv_days", dp=1, x="d")
    mline("Deferred revenue (current)", "deferred_revenue")

    L.append("\nQUALITY OF REPORTED PROFIT")
    line("Normalized / reported income", "normalized_vs_reported", x="x")
    mline("Unusual items", "unusual_items")
    line("Stock comp % of revenue", "sbc_pct_revenue", pct=True)
    line("Stock comp % of op cash flow", "sbc_pct_cfo", pct=True)

    L.append("\nREINVESTMENT & BALANCE-SHEET RISK")
    line("Capex / D&A", "capex_over_da", x="x")
    line("Goodwill % of assets", "goodwill_pct_assets", pct=True)
    line("Interest coverage (EBIT/int)", "interest_coverage", dp=1, x="x")
    line("Diluted shares outstanding", "diluted_shares", dp=0)

    if q.get("beneish_m") is not None:
        f = q["beneish_factors"]
        L += ["", "BENEISH M-SCORE (latest period vs prior)",
              f"  M-score                             {q['beneish_m']:.3f}"
              f"   (conventional flag threshold: > -1.78)",
              "  factors: " + "  ".join(
                  f"{k}={_f(v)}" for k, v in f.items() if v is not None),
              "  NOTE: this is a SCREEN, not a finding. It produces false",
              "  positives for fast-growing and acquisitive companies."]
    else:
        L += ["", "BENEISH M-SCORE: not computable (insufficient inputs)"]
    return "\n".join(L)


QUALITY_SYSTEM = (
    "You are a forensic accounting analyst. Your job is to assess whether "
    "reported earnings are backed by cash and whether the accounting is "
    "conservative or aggressive. You are NOT valuing the business and you have "
    "deliberately not been given valuation multiples or price data. Ground "
    "every claim in the figures provided and cite them. For every apparent red "
    "flag, state the innocent explanation as well as the concerning one, and "
    "say which the data actually supports -- accounting anomalies have benign "
    "causes more often than not. If a figure is missing or a metric is not "
    "computable, say so rather than inventing it. State conclusions directly."
)

QUALITY_SINGLE = """Assess the EARNINGS QUALITY of the company below.

You have not been given valuation multiples or share price. Do not opine on
whether the stock is cheap. Judge the accounting only.

1. **Cash backing** - does operating cash flow support reported net income? Read the CFO/NI and FCF/NI trend across periods, not just the latest.
2. **Accruals** - what does the accrual ratio trend imply? Rising accruals with rising profit is the classic warning pattern; say whether that is what you see.
3. **Working capital** - are DSO, DPO or inventory days drifting in a way that flatters reported results? Distinguish a deliberate credit-terms or supply-chain change from deterioration.
4. **Quality of reported profit** - how much depends on unusual items, and how large is stock-based compensation relative to revenue and to operating cash flow?
5. **Reinvestment** - is capex keeping pace with D&A? Sustained under-investment inflates near-term free cash flow at the cost of the future. Note if the business is genuinely asset-light.
6. **Balance-sheet risk** - goodwill as a share of assets (impairment exposure), interest coverage, and share-count trend (is per-share growth real or buyback-driven?).
7. **Beneish M-score** - interpret it if computed, explicitly noting it is a screen with known false positives for fast-growing and acquisitive firms.
8. **The single most important thing** - if you could check one item in the notes to the accounts, what would it be and why?

9. **VERDICT** - commit to a call. State clearly, each on its own line:
   - **Earnings quality: HIGH / ADEQUATE / QUESTIONABLE / POOR**
   - **Rating: BUY / HOLD / SELL** - purely on accounting quality: would you
     own this if you could see nothing but the accounts? Aggressive accounting
     is a SELL even in a good business; conservative accounting in a dull
     business can be a BUY.
   - **Conviction: HIGH / MEDIUM / LOW**
   - **Confidence: NN%** - integer 0-100, probability your quality assessment
     is right. Use the full range; 50% is a coin flip, 90% should be rare.
   - **Data confidence: NN%** - separate integer for how much you trust the
     underlying figures.
   - **Primary uncertainty:** one short phrase.
   - **Time frame** over which your concerns would surface.
   - **The 2-3 figures that most drive the call.**
   - **What would change your mind** - the specific observable.

10. **SCENARIOS** - over your stated time frame, express your view as a
   probability-weighted distribution of what an investor realises relative to
   reported earnings. Exactly three lines, using the LATEST reported net income
   as the $ anchor:

   - **Bear case: NN% probability, target $NNN** - accounting concerns prove real; sustainable earnings are materially below reported.
   - **Base case: NN% probability, target $NNN** - reported earnings are broadly sustainable.
   - **Bull case: NN% probability, target $NNN** - accounting is conservative; true earning power exceeds reported.

   - **Fair value: $NNN** - your estimate of SUSTAINABLE annual net income in
     dollars, given the accounting.

   The three probabilities MUST sum to exactly 100. Targets must be absolute
   dollar amounts of annual net income, not per-share prices and not
   percentages. Do NOT compute a weighted average yourself - give the three
   probability/target pairs only; the arithmetic is done downstream.

{brief}"""
