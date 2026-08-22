#!/usr/bin/env python3
"""recipe10_longform_report.py — CR196 §2 recipe 10: the long-form analyst report.

## Why this recipe exists

Run 1 trained on 25,695 examples whose median assistant target was 331 characters,
of which 3.53% reached 5,000. Asked for the production nine-section brief the
merged model returned 45-244 tokens where the untrained base returned ~1,200
(CR196 §9, guards-register P27). The corpus audit that followed found the real
hole: **not one Tier-A example in the entire mix reached 5,000 characters.** Every
long-form row in run 1 came from the UltraChat replay slice — generic chat. The
model was taught finance exclusively in short answers and never once saw the
deliverable it exists to produce.

This recipe is that missing shape: the exact production brief in, a full
nine-section report out. It is the only source in the mix that teaches the job the
way production asks for it.

## Where the targets come from — and where they must not

Targets are SELF-DISTILLED from **vanilla Fastino**, which CR196 §2 recipe 10
blesses by name ("DeepSeek-R1 / self-distilled Fastino"). **Claude outputs are
barred outright** — Anthropic's terms prohibit training a competing model on them,
and the old Silent_Scout "Opus distillation ladder" is retired for this purpose.
Nothing in this file may ever be pointed at an Anthropic endpoint.

## Why self-distilling from the base is not circular

Copying the teacher verbatim would teach the student to be the teacher, which is
pointless when the teacher is the base we are training. The value is entirely in
the FILTER: the base writes a report of roughly the right shape most of the time,
and this recipe keeps only the runs that survive checks the base itself does not
enforce —

  clean stop        not truncated at the token budget (a cut-off report teaches
                    the model to stop mid-sentence)
  structure         every field the backend actually parses is present: Rating,
                    Conviction, Confidence, Data confidence, three scenario lines,
                    Fair value
  arithmetic        the three scenario probabilities sum to exactly 100 — the one
                    place the report makes a checkable claim about itself
  grounding         figures >= $1M that the report states AS DATA must trace to a
                    figure in the brief. This is what stops hallucinated numbers
                    being trained in. It is deliberately not absolute: measured
                    against 44 real reports, a flat "every figure must appear in
                    the brief" rule rejected 34 of them, and reading the rejects
                    showed almost all were legitimate ANALYSIS -- "implied net
                    debt of -$110B", "if FCF drops below $800M", "a 100bps hike
                    could add ~$100M". Those are what section 9's "what would
                    change your mind" asks for; rejecting them would train the
                    model not to reason. So derived figures (hedged or
                    conditional by context) are exempt, values are deduped, the
                    tolerance allows re-rounding, and a small budget of
                    unexplained figures is permitted before the report is cut
  basis             a report that calls the cross-verification block a genuine
                    source conflict when the computed class is period-only is
                    rejected — so recipe 10 cannot regress what §1 measured.
                    Qualified by basis_level: the scorer's source-conflict
                    pattern matches the substring inside a NEGATED phrase too
                    ("these are not two sources disagreeing"), which is a
                    perfectly good way to reconcile. A report that reached
                    level 2/3 has demonstrably matched the periods, so the
                    string is a negation or a quotation of the brief's framing,
                    not a misreading. Audited on the 44 real reports in
                    eval/basis/responses/: all 12 source-conflict matches were
                    asserted rather than negated, and all 7 false-conflict
                    flags sat at level 0-1 — so this qualifier changes nothing
                    there and only stops the false positive on a correct
                    negated reconciliation. NOTE: the blind spot is in the
                    vendored scorer, which is left BYTE-IDENTICAL to the lane's
                    so it keeps reproducing §1 exactly. It is qualified here,
                    at the point of use, not patched there
  no retreat        "consult a financial advisor" and friends are rejected; the
                    prompt explicitly forbids that exit

Every one of those is deterministic. No model scores a model here (CR038: prompt
instructions are not controls, and that applies to graders too).

With --n > 1 the surviving candidates are RANKED and the best kept: candidates that
reconcile the basis mismatch (score_basis level 2/3) win over ones that merely
raise it (level 1), ties broken by length. That is the "best-of-n" §2 specifies,
and it is how this recipe pushes L2/L3 behaviour without ever touching an eval
ticker.

## The brief is rebuilt, not borrowed

The eval set is frozen bytes lifted from the pilot's results.db (see
`eval/basis/extract_frozen_set.py`). Those are the 44 EVAL tickers and are
off-limits as training data. Here the same brief LAYOUT is rebuilt from live
yfinance over the frozen TRAIN universe. Two consequences worth being explicit
about:

- The "OpenBB" statement columns and the OpenBB side of the cross-verification
  block are **yfinance-derived** — the annual filed statements, compared against
  the `.info` TTM/MRQ snapshot. This reproduces the trap faithfully because the
  trap IS one vendor on two bases (that is the finding the rubric grades), and it
  is the same substitution `recipe1_basis.py` already makes. It is recorded in
  `_meta.openbb_source` so no reader has to infer it.
- Figures are live at generation time, so a brief is only ever paired with the
  teacher report generated from it. `_meta.as_of` stamps both.

## Stages, and why they are separate

  --stage briefs     train tickers -> out/recipe10_briefs.jsonl   (local, CPU, yfinance)
  --stage assemble   briefs + teacher completions -> out/recipe10.jsonl  (local, CPU)

Generation sits between them and runs on a GPU box via `distill_teacher.py`. The
split exists because the GPU is not this machine and may not be ours; briefs and
verification stay here where they are cheap and reviewable.

Usage:
  python3 recipe10_longform_report.py --stage briefs --limit 2500 [--workers 6]
  # ... distill_teacher.py on the GPU box ...
  python3 recipe10_longform_report.py --stage assemble \
      --briefs out/recipe10_briefs.jsonl --completions out/recipe10_completions.jsonl

Needs: pip install yfinance pandas
"""
import argparse
import concurrent.futures as cf
import json
import os
import re
import sys
from collections import Counter

import pandas as pd
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "ami_finetune_kit", "eval", "basis"))
from common import fmt_b, load_train_universe, write_jsonl, yf_backoff  # noqa: E402
from recipe1_basis import cell, classify  # noqa: E402
import score_basis  # noqa: E402

# The system + user prompt production actually sends. Imported, never retyped: a
# wording drift between the eval prompt and the training prompt would train the
# model on a brief it is never asked to answer.
from extract_frozen_set import NO_THINK, SINGLE, SYSTEM  # noqa: E402

W_SUMMARY = 56      # summary rows pad to this width (measured off the frozen briefs)
W_DERIVED = 62
W_LABEL = 40        # statement tables: label field, then 4 columns of 16
W_COL = 16

MIN_TARGET_CHARS = 3500     # below this it is not a report, whatever else it passes
GROUNDING_FLOOR = 1e6       # only audit figures >= $1M; per-share targets are not claims
GROUNDING_TOL = 0.03        # re-rounding: "$94B" for $91.45B is not a fabrication
GROUNDING_BUDGET = 2        # unexplained figures tolerated before the report is cut
HEDGE_WINDOW = 70           # chars before a figure searched for derivation language

# A figure introduced by any of these is the report DERIVING a number, not quoting
# one -- a threshold, an implied value, a run-rate, a scenario. Measured off the 44
# real reports in eval/basis/responses/: this is where the ungrounded figures live.
P_HEDGE = re.compile(
    r"(implie\w*|imply|implied|if\s|would|could|should|approx\w*|roughly|about\s|"
    r"~|below|above|exceed\w*|assum\w*|target\w*|scenario|run[- ]rate|annuali[sz]\w*|"
    r"per\s+year|per\s+quarter|toward|towards|at\s+least|more\s+than|less\s+than|"
    r"drop\w*|fall\w*|rise\w*|reach\w*|sustain\w*|trigger\w*)", re.I)

P_RETREAT = re.compile(r"(consult\s+(a|your|with)\s+(financial|investment|qualified)|"
                       r"financial\s+advisor|not\s+(financial|investment)\s+advice|"
                       r"i\s+(cannot|can't|am\s+not\s+able\s+to)\s+provide)", re.I)
P_RATING = re.compile(r"rating\s*[:*\s]*\s*(BUY|HOLD|SELL)", re.I)
P_CONVICTION = re.compile(r"conviction\s*[:*\s]*\s*(HIGH|MEDIUM|LOW)", re.I)
P_CONFIDENCE = re.compile(r"(?<!data\s)confidence\s*[:*\s]*\s*(\d{1,3})\s*%", re.I)
P_DATA_CONF = re.compile(r"data\s+confidence\s*[:*\s]*\s*(\d{1,3})\s*%", re.I)
P_FAIR_VALUE = re.compile(r"fair\s+value\s*[:*\s]*\s*\$\s*([\d,]+(?:\.\d+)?)", re.I)
P_SCENARIO = re.compile(
    r"(bear|base|bull)\s+case\s*[:*\s]*.{0,40}?(\d{1,3})\s*%\s*probability.{0,60}?"
    r"target\s*\$\s*([\d,]+(?:\.\d+)?)", re.I | re.S)
P_MONEY = re.compile(r"\$\s?(-?[\d,]+(?:\.\d+)?)\s*([TBM])\b")


def _pad(label, value, width):
    return ("  " + label).ljust(width - len(value)) + value


def _fmt_num(v, suffix="", dp=2):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "n/a"
    return f"{float(v):.{dp}f}{suffix}"


def _pct(v, dp=2):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "n/a"
    return f"{float(v) * 100:.{dp}f}%"


def _table(df, rows, cols):
    out = []
    out.append(" " * (W_LABEL + 2)
               + "".join(f"{str(pd.Timestamp(c).date()):>{W_COL}}" for c in cols))
    for label, key in rows:
        vals = []
        for c in cols:
            v = cell(df, key, c)
            vals.append(fmt_b(v) if v is not None else "n/a")
        if all(v == "n/a" for v in vals):
            continue
        out.append(f"  {label:<{W_LABEL}}" + "".join(f"{v:>{W_COL}}" for v in vals))
    return out


INCOME_ROWS = [("total_revenue", "Total Revenue"), ("gross_profit", "Gross Profit"),
               ("operating_income", "Operating Income"),
               ("research_and_development_expense", "Research And Development"),
               ("net_income", "Net Income"),
               ("diluted_earnings_per_share", "Diluted EPS")]
BALANCE_ROWS = [("total_assets", "Total Assets"),
                ("total_liabilities_net_minority_interest",
                 "Total Liabilities Net Minority Interest"),
                ("common_stock_equity", "Common Stock Equity"),
                ("total_debt", "Total Debt"),
                ("net_debt", "Net Debt"),
                ("cash_and_cash_equivalents", "Cash And Cash Equivalents")]
CASH_ROWS = [("capital_expenditure", "Capital Expenditure"),
             ("free_cash_flow", "Free Cash Flow"),
             ("repurchase_of_capital_stock", "Repurchase Of Capital Stock")]


def build_brief(tk):
    """Rebuild the production fundamentals brief for one TRAIN ticker."""
    t = yf.Ticker(tk)
    info = yf_backoff(lambda: t.info)
    inc, bs, cff = t.income_stmt, t.balance_sheet, t.cashflow
    if inc is None or inc.empty or bs is None or bs.empty:
        return {"ticker": tk, "status": "no_statements"}
    if not info.get("longName") or info.get("marketCap") is None:
        return {"ticker": tk, "status": "no_info"}

    cls = classify(tk)
    if cls.get("status") != "ok":
        return {"ticker": tk, "status": cls.get("status", "classify_failed")}

    cols = sorted(inc.columns, key=lambda c: pd.Timestamp(c), reverse=True)[:4]
    bcols = sorted(bs.columns, key=lambda c: pd.Timestamp(c), reverse=True)[:4]
    ccols = (sorted(cff.columns, key=lambda c: pd.Timestamp(c), reverse=True)[:4]
             if cff is not None and not cff.empty else [])
    ann = bcols[0]

    L = ["=" * 88,
         f"{info.get('longName')}  ({tk})",
         f"Sector: {info.get('sector', 'n/a')}  |  Industry: "
         f"{info.get('industry', 'n/a')}  |  Country: {info.get('country', 'n/a')}"]
    if info.get("fullTimeEmployees"):
        L.append(f"Employees: {int(info['fullTimeEmployees']):,}")
    L += ["=" * 88, "", "BUSINESS", (info.get("longBusinessSummary") or "n/a")[:1000], ""]

    L.append("VALUATION  [basis: current price / TTM or forward earnings]")
    for lab, key, kind in [("Trailing P/E", "trailingPE", "n"),
                           ("Forward P/E", "forwardPE", "n"),
                           ("PEG ratio", "trailingPegRatio", "n"),
                           ("Price / Book", "priceToBook", "n"),
                           ("EV / EBITDA", "enterpriseToEbitda", "n"),
                           ("Price / Sales", "priceToSalesTrailing12Months", "n")]:
        L.append(_pad(lab, _fmt_num(info.get(key)), W_SUMMARY))
    L.append("")

    L.append("PROFITABILITY  [basis: TTM]")
    for lab, key in [("Gross margin", "grossMargins"),
                     ("Operating margin", "operatingMargins"),
                     ("Net margin", "profitMargins"),
                     ("Return on equity", "returnOnEquity"),
                     ("Return on assets", "returnOnAssets"),
                     ("EBITDA margin (OpenBB)", "ebitdaMargins")]:
        L.append(_pad(lab, _pct(info.get(key)), W_SUMMARY))
    L.append("")

    L.append("GROWTH")
    for lab, key in [("Revenue growth (YoY)", "revenueGrowth"),
                     ("Earnings growth (YoY)", "earningsGrowth"),
                     ("Earnings growth (QoQ)", "earningsQuarterlyGrowth")]:
        L.append(_pad(lab, _pct(info.get(key)), W_SUMMARY))
    L.append("")

    L.append("LEVERAGE & LIQUIDITY  [basis: most recent quarter (MRQ)]")
    L.append(_pad("Debt / Equity (MRQ, % form)", _fmt_num(info.get("debtToEquity")),
                  W_SUMMARY))
    L.append(_pad("Current ratio", _fmt_num(info.get("currentRatio")), W_SUMMARY))
    L.append(_pad("Quick ratio", _fmt_num(info.get("quickRatio")), W_SUMMARY))
    L.append(_pad("Total debt", fmt_b(info.get("totalDebt")), W_SUMMARY))
    L.append(_pad("Total cash", fmt_b(info.get("totalCash")), W_SUMMARY))
    L.append("")

    L.append("CASH FLOW & SCALE  [basis: TTM]")
    for lab, key in [("Free cash flow", "freeCashflow"),
                     ("Operating cash flow", "operatingCashflow"),
                     ("EBITDA", "ebitda"), ("Revenue (TTM)", "totalRevenue"),
                     ("Market cap", "marketCap"),
                     ("Enterprise value", "enterpriseValue")]:
        L.append(_pad(lab, fmt_b(info.get(key)), W_SUMMARY))
    L.append(_pad("Beta", _fmt_num(info.get("beta")), W_SUMMARY))
    # dividendYield is ALREADY a percentage in current yfinance (ACN: 3.52, which is
    # dividendRate 6.52 / price 185.28). The margin and growth fields on either side
    # of it are fractions, so passing this one through _pct too renders 352% -- caught
    # when the teacher's very first report said "the dividend yield of 352% is a data
    # error". Nothing in the brief flagged it; the number just sat there looking like
    # data. Hence the guard below.
    div = info.get("dividendYield") or 0
    L.append(_pad("Dividend yield", _fmt_num(div, "%"), W_SUMMARY))
    L.append("")

    L.append(f"INCOME STATEMENT (OpenBB, {len(cols)} periods)")
    L += _table(inc, INCOME_ROWS, cols) + [""]
    L.append(f"BALANCE STATEMENT (OpenBB, {len(bcols)} periods)")
    L += _table(bs, BALANCE_ROWS, bcols) + [""]
    if ccols:
        L.append(f"CASH STATEMENT (OpenBB, {len(ccols)} periods)")
        L += _table(cff, CASH_ROWS, ccols) + [""]

    eq = cell(bs, "Common Stock Equity", ann)
    debt = cell(bs, "Total Debt", ann)
    cash = cell(bs, "Cash And Cash Equivalents", ann)
    assets = cell(bs, "Total Assets", ann)
    liab = cell(bs, "Total Liabilities Net Minority Interest", ann)
    L.append("DERIVED FROM FILED BALANCE SHEET (annual, period ending "
             f"{str(pd.Timestamp(ann).date())})")
    L += ["  These are computed from the statement above. The ratios in the",
          "  summary sections are TTM / most-recent-quarter and are therefore",
          "  on a DIFFERENT basis -- do not treat a gap as an error by itself."]
    if eq:
        L.append(_pad("Shareholders' equity", fmt_b(eq), W_DERIVED))
    if eq and debt:
        L.append(_pad("Debt / Equity (annual)", f"{debt / eq:.2f}x", W_DERIVED)
                 + f"  ({debt / eq * 100:.1f}%)")
    if debt is not None and cash is not None:
        L.append(_pad("Net debt (debt - cash)", fmt_b(debt - cash), W_DERIVED))
    if assets and liab:
        L.append(_pad("Liabilities / Assets", f"{liab / assets:.2f}x", W_DERIVED))
    if assets and eq:
        L.append(_pad("Equity / Assets", f"{eq / assets:.2f}x", W_DERIVED))
    L.append("")

    mismatches = []
    if cls["debt_class"] not in ("no_conflict", "missing"):
        mismatches.append(("Total debt (vs balance sheet)",
                           cls["info_total_debt"], cls["a_debt_at_annual"]))
    if cls["cash_class"] not in ("no_conflict", "missing"):
        mismatches.append(("Total cash (vs balance sheet)",
                           cls["info_total_cash"], cls["a_cash_eq_at_annual"]))
    L.append("DATA CROSS-VERIFICATION (yfinance vs OpenBB)")
    L.append(f"  {12 - len(mismatches)} metric(s) agree across both sources.")
    if mismatches:
        L.append(f"  !! {len(mismatches)} DISAGREEMENT(S) -- treat these with caution:")
        for lab, a, b in mismatches:
            L.append(f"     {lab}  yfinance={a:.4f} OpenBB={b:.4f}")
    L.append("")

    hist = yf_backoff(lambda: t.history(period="1y"))
    # No price => no brief. Section 9 requires scenario targets "anchored to the
    # current share price given in the data"; a brief that renders MARKET CONTEXT as
    # n/a still LOOKS fine and would train unanchored price targets. Degrade loudly
    # (CR040) — drop the ticker rather than emit a brief that is quietly unanswerable.
    if hist is None or hist.empty or "Close" not in hist or hist["Close"].empty:
        return {"ticker": tk, "status": "no_price"}
    L.append("MARKET CONTEXT (descriptive background only -- NOT predictive)")
    if True:
        px = hist["Close"]
        last = float(px.iloc[-1])
        L.append(_pad("Last close", f"${last:,.0f}" if last >= 100
                      else f"${last:,.2f}", W_SUMMARY))
        for lab, back in [("Return 1M", 21), ("Return 3M", 63), ("Return 12M", 250)]:
            if len(px) > back:
                L.append(_pad(lab, f"{(last / float(px.iloc[-back]) - 1) * 100:.2f}%",
                              W_SUMMARY))
        vol = float(px.pct_change().std() * (252 ** 0.5) * 100)
        L.append(_pad("Annualised volatility", f"{vol:.2f}%", W_SUMMARY))
        hi, lo = float(px.max()), float(px.min())
        L.append(_pad("Below 52w high", f"{(last / hi - 1) * 100:.2f}%", W_SUMMARY))
        L.append(_pad("Above 52w low", f"{(last / lo - 1) * 100:.2f}%", W_SUMMARY))
        if len(px) >= 200:
            ma = float(px.iloc[-200:].mean())
            L.append(_pad("Price vs 200d MA", f"{(last / ma - 1) * 100:.2f}%", W_SUMMARY))

    # Units guard. A units bug is off by 100x, so it fails a plausibility band that
    # no real S&P 1500 constituent does. Degrade loudly (CR040): drop the ticker
    # rather than emit a brief whose figures quietly teach nonsense.
    if div and float(div) > 25:
        return {"ticker": tk, "status": f"implausible_dividend_yield:{div}"}

    brief = "\n".join(L)
    return {"ticker": tk, "status": "ok", "brief": brief,
            "debt_class": cls["debt_class"], "cash_class": cls["cash_class"],
            "mrq_date": cls["mrq_date"], "annual_date": cls["annual_date"],
            "last_close": last,
            "system": SYSTEM, "user": SINGLE.format(brief=brief) + NO_THINK}


# --- verification -----------------------------------------------------------

MULT = {"T": 1e12, "B": 1e9, "M": 1e6}


def money_values(text, with_context=False):
    """Every figure >= $1M the text states, as floats. Per-share prices are below
    the floor by construction, so price targets and fair value are not audited.
    With with_context, each value is paired with the text just before it so the
    caller can tell a quoted figure from a derived one."""
    out = []
    for m in P_MONEY.finditer(text):
        try:
            v = abs(float(m.group(1).replace(",", "")) * MULT[m.group(2)])
        except ValueError:
            continue
        if v < GROUNDING_FLOOR:
            continue
        out.append((v, text[max(0, m.start() - HEDGE_WINDOW):m.start()])
                   if with_context else v)
    return out


def verify(target, rec):
    """Deterministic gate. Returns (ok, reasons, meta) — never raises on content."""
    reasons = []
    meta = {}

    if len(target) < MIN_TARGET_CHARS:
        reasons.append(f"too_short:{len(target)}")
    if P_RETREAT.search(target):
        reasons.append("advisor_retreat")

    for name, pat in [("rating", P_RATING), ("conviction", P_CONVICTION),
                      ("confidence", P_CONFIDENCE), ("data_confidence", P_DATA_CONF),
                      ("fair_value", P_FAIR_VALUE)]:
        if not pat.search(target):
            reasons.append(f"missing:{name}")

    scen = {m[0].lower(): (int(m[1]), float(m[2].replace(",", "")))
            for m in P_SCENARIO.findall(target)}
    meta["scenarios"] = scen
    if set(scen) != {"bear", "base", "bull"}:
        reasons.append(f"scenarios:{sorted(scen)}")
    else:
        total = sum(p for p, _ in scen.values())
        meta["prob_sum"] = total
        if total != 100:
            reasons.append(f"prob_sum:{total}")

    brief_vals = money_values(rec["brief"])
    ungrounded, derived, seen = set(), 0, set()
    for v, ctx in money_values(target, with_context=True):
        key = round(v, -3)               # one claim, however often it is repeated
        if key in seen:
            continue
        seen.add(key)
        if any(abs(v - b) <= GROUNDING_TOL * max(v, b) for b in brief_vals):
            continue
        if P_HEDGE.search(ctx):
            derived += 1                 # analysis, not a data claim
            continue
        ungrounded.add(key)
    meta["ungrounded"], meta["derived"] = len(ungrounded), derived
    if len(ungrounded) > GROUNDING_BUDGET:
        reasons.append(f"ungrounded:{len(ungrounded)}")

    ev = score_basis.score_text(target, rec["debt_class"], rec["cash_class"])
    meta["basis_level"] = ev["level"]
    if ev["false_conflict"] and ev["level"] < 2:
        reasons.append("false_conflict")
    if ev["overclaim"]:
        reasons.append("basis_overclaim")

    return (not reasons), reasons, meta


def rank_key(target, meta):
    """Best-of-n ordering: reconciling the basis beats merely raising it; length
    breaks ties. Deterministic — no judge, no sampling."""
    return (meta.get("basis_level", 0), len(target))


# --- stages -----------------------------------------------------------------

def stage_briefs(args):
    """Append-as-you-go and resumable. Yahoo rate-limits a sweep this size hard
    (recipe1's first full run lost 758 of 1,437 tickers to YFRateLimitError), so a
    build-everything-then-write pass would throw away hours on one late failure."""
    tickers = load_train_universe()
    if args.limit:
        tickers = tickers[args.offset:args.offset + args.limit]
    else:
        tickers = tickers[args.offset:]

    seen = set()
    if os.path.exists(args.out_briefs) and not args.restart:
        failed = 0
        for line in open(args.out_briefs):
            try:
                r = json.loads(line)
            except Exception:
                continue
            # Only a SUCCEEDED ticker is done. Errors are retried, because the
            # dominant failure here is a transient Yahoo rate limit, not a broken
            # ticker — recipe1 lost 758/1,437 that way and the retried tail then
            # completed with 0 errors.
            if r.get("status") == "ok":
                seen.add(r["ticker"])
            else:
                failed += 1
        print(f"[resume] {len(seen)} ok on disk, {failed} earlier failures will retry")
    todo = [t for t in tickers if t not in seen]
    print(f"[briefs] {len(todo)} to do of {len(tickers)}, {args.workers} workers")
    if not todo:
        print("[briefs] nothing missing")
        return

    stats = Counter()
    lock = __import__("threading").Lock()
    os.makedirs(os.path.dirname(args.out_briefs), exist_ok=True)
    out_f = open(args.out_briefs, "w" if args.restart else "a")

    def one(tk):
        try:
            r = build_brief(tk)
        except Exception as e:
            r = {"ticker": tk, "status": f"error:{type(e).__name__}"}
        with lock:
            out_f.write(json.dumps(r, ensure_ascii=False) + "\n")
            out_f.flush()
            stats[r["status"]] += 1
            n = sum(stats.values())
            if n % 25 == 0:
                print(f"  {n}/{len(todo)}  ok={stats['ok']}", flush=True)
        return r

    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        rows = [r for r in ex.map(one, todo) if r["status"] == "ok"]
    out_f.close()

    print(f"[briefs] appended {len(rows)} ok -> {args.out_briefs}")
    print(f"[briefs] status: {dict(stats)}")
    if rows:
        cl = Counter((r["debt_class"], r["cash_class"]) for r in rows)
        print(f"[briefs] class pairs (debt,cash): {dict(cl.most_common(8))}")
        bl = sorted(len(r["brief"]) for r in rows)
        print(f"[briefs] brief chars: min={bl[0]} med={bl[len(bl)//2]} max={bl[-1]}")


def stage_assemble(args):
    briefs = {}
    for line in open(args.briefs):
        r = json.loads(line)
        if r.get("status") == "ok":
            briefs[r["ticker"]] = r
    print(f"[assemble] {len(briefs)} briefs")

    cands = {}
    n_comp = 0
    for line in open(args.completions):
        c = json.loads(line)
        n_comp += 1
        tk = c["ticker"]
        if tk not in briefs:
            continue
        cands.setdefault(tk, []).append(c)
    print(f"[assemble] {n_comp} completions over {len(cands)} tickers")

    kept, stats, lens = [], Counter(), []
    for tk, cs in sorted(cands.items()):
        rec = briefs[tk]
        best = None
        for c in cs:
            stats["candidates"] += 1
            if c.get("finish_reason") not in (None, "stop", "eos"):
                stats[f"reject:finish_{c.get('finish_reason')}"] += 1
                continue
            target = (c.get("text") or "").strip()
            ok, reasons, meta = verify(target, rec)
            if not ok:
                for r in reasons:
                    stats["reject:" + r.split(":")[0]] += 1
                continue
            k = rank_key(target, meta)
            if best is None or k > best[0]:
                best = (k, target, meta)
        if best is None:
            stats["ticker_dropped"] += 1
            continue
        _, target, meta = best
        lens.append(len(target))
        stats["kept"] += 1
        stats[f"level_{meta['basis_level']}"] += 1
        kept.append({
            "messages": [{"role": "system", "content": rec["system"]},
                         {"role": "user", "content": rec["user"]},
                         {"role": "assistant", "content": target}],
            "_meta": {"recipe": "recipe10_longform", "ticker": tk,
                      "teacher": args.teacher, "openbb_source": "yfinance-annual",
                      "debt_class": rec["debt_class"], "cash_class": rec["cash_class"],
                      "basis_level": meta["basis_level"],
                      "prob_sum": meta.get("prob_sum"),
                      "target_chars": len(target)},
        })

    write_jsonl(args.out, kept)
    print(f"[assemble] kept {len(kept)} -> {args.out}")
    for k in sorted(stats):
        print(f"  {k:34s} {stats[k]}")
    if lens:
        lens.sort()
        n = len(lens)
        print(f"[assemble] target chars: min={lens[0]} med={lens[n // 2]} "
              f"p90={lens[int(.9 * n)]} max={lens[-1]}")
        for thr in (3500, 4000, 5000, 6000):
            k = sum(1 for x in lens if x >= thr)
            print(f"  >= {thr}: {k} ({k / n:.1%})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=["briefs", "assemble"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--out-briefs", default=os.path.join(HERE, "out",
                                                         "recipe10_briefs.jsonl"))
    ap.add_argument("--briefs", default=os.path.join(HERE, "out",
                                                     "recipe10_briefs.jsonl"))
    ap.add_argument("--completions", default=os.path.join(HERE, "out",
                                                          "recipe10_completions.jsonl"))
    ap.add_argument("--out", default=os.path.join(HERE, "out", "recipe10.jsonl"))
    ap.add_argument("--teacher", default="fastino-finance-bf16 (vanilla)")
    ap.add_argument("--restart", action="store_true",
                    help="discard an existing brief file instead of resuming it")
    args = ap.parse_args()
    (stage_briefs if args.stage == "briefs" else stage_assemble)(args)


if __name__ == "__main__":
    main()
