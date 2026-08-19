#!/usr/bin/env python3
"""recipe4_earnings_quality.py — CR196 §2 recipe 4: earnings-quality flags.

Renders two years of annual statement lines (Net Income, Operating Cash Flow, Total
Revenue, Receivables, Inventory where present) and writes a target answer that runs
three checks — each computed independently, each flagged ONLY when the computed
numbers actually show it, and each SKIPPED (never flagged, never asserted "clean")
when its inputs are missing:

  (a) accrual gap        — Operating Cash Flow persistently (both years) meaningfully
                            below Net Income → accrual-heavy earnings
  (b) receivables vs revenue — receivables YoY growth outgrowing revenue YoY growth by
                            more than 5 points → potential revenue pull-forward
  (c) inventory vs revenue   — inventory YoY growth outgrowing revenue YoY growth by
                            more than 5 points → potential demand problem

Where a check's inputs ARE present but the numbers don't show the pattern, the answer
says that check is clean — it never stays silent on a computable check. Tickers with
fewer than 2 annual columns, or with zero checks computable at all, are skipped.

Usage: python3 recipe4_earnings_quality.py --out out/recipe4.jsonl --limit 50 [--workers 6]
Needs: pip install yfinance pandas
"""
import argparse, concurrent.futures as cf, json, os, sys

import pandas as pd
import yfinance as yf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import fmt_b, load_agent_prompt, load_train_universe, pick, write_jsonl

REVENUE = ["Total Revenue"]
NET_INCOME = ["Net Income", "Net Income Common Stockholders",
              "Net Income Continuous Operations", "Net Income Including Noncontrolling Interests"]
OCF = ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"]
RECEIVABLES = ["Receivables", "Accounts Receivable"]
INVENTORY = ["Inventory"]
GROWTH_FLAG_THRESHOLD = 0.05  # 5 percentage points of growth-rate divergence
ACCRUAL_FLAG_RATIO = 0.90     # OCF below 90% of NI in BOTH years → flag


def get_row(df, candidates, col):
    for name in candidates:
        if name not in df.index:
            continue
        try:
            v = df.loc[name, col]
        except Exception:
            continue
        if v is None:
            continue
        try:
            if pd.isna(v):
                continue
        except (TypeError, ValueError):
            pass
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return None


def yoy(y0, y1):
    """y0 = latest, y1 = prior. None if not computable."""
    if y0 is None or y1 is None or y1 == 0:
        return None
    return (y0 - y1) / abs(y1)


def compute(tk):
    r = {"ticker": tk}
    t = yf.Ticker(tk)
    inc, bs, cff = t.income_stmt, t.balance_sheet, t.cashflow
    if inc is None or inc.empty or len(inc.columns) < 2:
        return {**r, "status": "too_few_years"}

    inc_cols = sorted(inc.columns, key=lambda c: pd.Timestamp(c))[-2:]
    y1_col, y0_col = inc_cols[0], inc_cols[1]  # y1=prior, y0=latest
    r["y0_date"], r["y1_date"] = str(pd.Timestamp(y0_col).date()), str(pd.Timestamp(y1_col).date())

    rev0, rev1 = get_row(inc, REVENUE, y0_col), get_row(inc, REVENUE, y1_col)
    ni0, ni1 = get_row(inc, NET_INCOME, y0_col), get_row(inc, NET_INCOME, y1_col)
    rev_growth = yoy(rev0, rev1)

    checks = {}

    # (a) accrual gap — needs cashflow columns aligned to the same two FYs
    if cff is not None and not cff.empty:
        try:
            ocf0 = get_row(cff, OCF, y0_col) if y0_col in cff.columns else None
            ocf1 = get_row(cff, OCF, y1_col) if y1_col in cff.columns else None
        except Exception:
            ocf0 = ocf1 = None
        if ocf0 is not None and ocf1 is not None and ni0 is not None and ni1 is not None \
                and ni0 > 0 and ni1 > 0:
            below0, below1 = ocf0 < ni0 * ACCRUAL_FLAG_RATIO, ocf1 < ni1 * ACCRUAL_FLAG_RATIO
            checks["accrual"] = {"y0_ocf": ocf0, "y0_ni": ni0, "y1_ocf": ocf1, "y1_ni": ni1,
                                  "flagged": below0 and below1}

    # (b) receivables vs revenue
    if bs is not None and not bs.empty and y0_col in bs.columns and y1_col in bs.columns:
        recv0, recv1 = get_row(bs, RECEIVABLES, y0_col), get_row(bs, RECEIVABLES, y1_col)
        recv_growth = yoy(recv0, recv1)
        if recv_growth is not None and rev_growth is not None:
            checks["receivables"] = {"recv0": recv0, "recv1": recv1, "recv_growth": recv_growth,
                                      "rev_growth": rev_growth,
                                      "flagged": (recv_growth - rev_growth) > GROWTH_FLAG_THRESHOLD}

    # (c) inventory vs revenue
    if bs is not None and not bs.empty and y0_col in bs.columns and y1_col in bs.columns:
        inv0, inv1 = get_row(bs, INVENTORY, y0_col), get_row(bs, INVENTORY, y1_col)
        inv_growth = yoy(inv0, inv1)
        if inv_growth is not None and rev_growth is not None:
            checks["inventory"] = {"inv0": inv0, "inv1": inv1, "inv_growth": inv_growth,
                                    "rev_growth": rev_growth,
                                    "flagged": (inv_growth - rev_growth) > GROWTH_FLAG_THRESHOLD}

    if not checks:
        return {**r, "status": "no_checks"}

    r.update(rev0=rev0, rev1=rev1, ni0=ni0, ni1=ni1, rev_growth=rev_growth,
             checks=checks, status="ok")
    return r


def render_user(r):
    tk = r["ticker"]
    lines = [f"Fundamentals brief — {tk}", "",
             f"Annual statement lines (FY {r['y1_date']} vs FY {r['y0_date']}):",
             f"  Total Revenue: {fmt_b(r['rev1'])} → {fmt_b(r['rev0'])}",
             f"  Net Income: {fmt_b(r['ni1'])} → {fmt_b(r['ni0'])}"]
    if "accrual" in r["checks"]:
        c = r["checks"]["accrual"]
        lines.append(f"  Operating Cash Flow: {fmt_b(c['y1_ocf'])} → {fmt_b(c['y0_ocf'])}")
    if "receivables" in r["checks"]:
        c = r["checks"]["receivables"]
        lines.append(f"  Receivables: {fmt_b(c['recv1'])} → {fmt_b(c['recv0'])}")
    if "inventory" in r["checks"]:
        c = r["checks"]["inventory"]
        lines.append(f"  Inventory: {fmt_b(c['inv1'])} → {fmt_b(c['inv0'])}")
    lines += ["", "Run the earnings-quality checks: does cash generation back up reported "
              "earnings, and are receivables/inventory growing in line with revenue?"]
    return "\n".join(lines)


ACCRUAL_FLAG_TEXT = [
    "Operating cash flow has run meaningfully below net income in both years — "
    "accrual-heavy earnings; a bigger share of reported income is not showing up as cash.",
    "Cash flow from operations trails net income in both years by a wide margin — "
    "the earnings quality here leans accrual-heavy.",
]
ACCRUAL_CLEAN_TEXT = [
    "Operating cash flow tracks or exceeds net income in at least one of the two years — "
    "no persistent accrual gap.",
    "Cash generation is not persistently lagging earnings — this check is clean.",
]
RECV_FLAG_TEXT = [
    "receivables are growing faster than revenue by more than the arithmetic would "
    "explain — a potential sign of revenue pulled forward via looser collection terms.",
    "receivables outgrew revenue by a wide enough margin to flag — worth checking "
    "whether sales are being recognized ahead of cash collection.",
]
RECV_CLEAN_TEXT = [
    "receivables growth roughly tracks revenue growth — clean on this check.",
    "no material divergence between receivables and revenue growth here.",
]
INV_FLAG_TEXT = [
    "inventory is growing faster than revenue by more than the arithmetic would "
    "explain — a potential demand problem if goods are piling up unsold.",
    "inventory outgrew revenue by a wide enough margin to flag — worth checking "
    "whether demand is softening relative to production or purchasing.",
]
INV_CLEAN_TEXT = [
    "inventory growth roughly tracks revenue growth — clean on this check.",
    "no material divergence between inventory and revenue growth here.",
]


def render_answer(r):
    tk = r["ticker"]
    parts = []
    if "accrual" in r["checks"]:
        c = r["checks"]["accrual"]
        gap0 = c["y0_ocf"] - c["y0_ni"]
        gap1 = c["y1_ocf"] - c["y1_ni"]
        parts.append(f"Accrual check: FY{r['y0_date']} OCF {fmt_b(c['y0_ocf'])} vs NI "
                     f"{fmt_b(c['y0_ni'])} ({'+' if gap0 >= 0 else '-'}{fmt_b(abs(gap0))}); "
                     f"FY{r['y1_date']} OCF {fmt_b(c['y1_ocf'])} vs NI {fmt_b(c['y1_ni'])} "
                     f"({'+' if gap1 >= 0 else '-'}{fmt_b(abs(gap1))}). "
                     f"{pick(ACCRUAL_FLAG_TEXT if c['flagged'] else ACCRUAL_CLEAN_TEXT, tk, 'a')}")
    if "receivables" in r["checks"]:
        c = r["checks"]["receivables"]
        parts.append(f"Receivables check: receivables grew {c['recv_growth'] * 100:+.1f}% "
                     f"({fmt_b(c['recv1'])} → {fmt_b(c['recv0'])}) versus revenue growth of "
                     f"{c['rev_growth'] * 100:+.1f}% — a "
                     f"{(c['recv_growth'] - c['rev_growth']) * 100:+.1f}pt gap. "
                     f"{pick(RECV_FLAG_TEXT if c['flagged'] else RECV_CLEAN_TEXT, tk, 'r')}")
    if "inventory" in r["checks"]:
        c = r["checks"]["inventory"]
        parts.append(f"Inventory check: inventory grew {c['inv_growth'] * 100:+.1f}% "
                     f"({fmt_b(c['inv1'])} → {fmt_b(c['inv0'])}) versus revenue growth of "
                     f"{c['rev_growth'] * 100:+.1f}% — a "
                     f"{(c['inv_growth'] - c['rev_growth']) * 100:+.1f}pt gap. "
                     f"{pick(INV_FLAG_TEXT if c['flagged'] else INV_CLEAN_TEXT, tk, 'i')}")
    return " ".join(parts)


def build_example(r, system_prompt):
    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": render_user(r)},
            {"role": "assistant", "content": render_answer(r)},
        ],
        "_meta": {"recipe": "recipe4_earnings_quality", "ticker": r["ticker"],
                  "y0_date": r["y0_date"], "y1_date": r["y1_date"],
                  "checks": {k: v["flagged"] for k, v in r["checks"].items()}},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "out", "recipe4.jsonl"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--tickers", nargs="*", help="explicit list (proof runs only — "
                    "still decontamination-checked)")
    args = ap.parse_args()

    if args.tickers:
        from common import load_eval_tickers
        tickers = [t.upper() for t in args.tickers]
        bad = set(tickers) & load_eval_tickers()
        if bad:
            raise SystemExit(f"DECONTAMINATION VIOLATION: {sorted(bad)}")
    else:
        tickers = load_train_universe()
    if args.limit:
        tickers = tickers[: args.limit]

    system_prompt = load_agent_prompt()
    rows, skipped = [], {"too_few_years": 0, "no_checks": 0, "error": 0}
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(compute, t): t for t in tickers}
        for fut in cf.as_completed(futs):
            try:
                r = fut.result()
            except Exception:
                skipped["error"] += 1
                continue
            if r.get("status") != "ok":
                key = r.get("status") if r.get("status") in skipped else "too_few_years"
                skipped[key] += 1
                continue
            rows.append(build_example(r, system_prompt))

    n = write_jsonl(args.out, rows)
    flag_counts = {"accrual_flagged": 0, "receivables_flagged": 0, "inventory_flagged": 0,
                   "accrual_clean": 0, "receivables_clean": 0, "inventory_clean": 0}
    for e in rows:
        for k, flagged in e["_meta"]["checks"].items():
            flag_counts[f"{k}_{'flagged' if flagged else 'clean'}"] += 1
    print(f"wrote {n} examples → {args.out}")
    print(f"flags: {json.dumps(flag_counts, indent=2)}")
    print(f"skipped: {skipped}")


if __name__ == "__main__":
    main()
