#!/usr/bin/env python3
"""recipe2_ratios.py — CR196 §2 recipe 2: ratio computation + interpretation.

Renders the raw annual statement lines (income_stmt, balance_sheet, cashflow) a
fundamentals analyst would pull for a quick ratio read, asks the model to compute
2-4 named ratios, and writes a target answer that shows the arithmetic explicitly
(e.g. "$97.0B / $391.0B = 24.8%") before interpreting — per CR196 the model must
compute-then-interpret, never assert a number without showing the division that
produced it.

Ratio set (computed only when every input is present and the denominator is sane):
  net margin        = Net Income / Total Revenue
  gross margin       = Gross Profit / Total Revenue
  ROE                = Net Income / Stockholders Equity
  debt/equity         = Total Debt / Stockholders Equity
  FCF conversion      = Free Cash Flow / Net Income

Interpretation is template-driven off the COMPUTED value (threshold buckets), never
judged — same discipline as recipe1: labels are arithmetic, not opinion. yfinance row
labels vary by ticker (e.g. "Net Income" vs "Net Income Common Stockholders"), so every
lookup goes through get_row(), which tries a fixed candidate list and returns None
rather than raising — a ticker missing too many inputs is SKIPPED, never fabricated.

Usage: python3 recipe2_ratios.py --out out/recipe2.jsonl --limit 50 [--workers 6]
Needs: pip install yfinance pandas
"""
import argparse, concurrent.futures as cf, json, os, sys

import pandas as pd
import yfinance as yf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import fmt_b, load_agent_prompt, load_train_universe, pick, write_jsonl, yf_backoff

REVENUE = ["Total Revenue"]
NET_INCOME = ["Net Income", "Net Income Common Stockholders",
              "Net Income Continuous Operations", "Net Income Including Noncontrolling Interests"]
GROSS_PROFIT = ["Gross Profit"]
EQUITY = ["Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"]
DEBT = ["Total Debt"]
FCF = ["Free Cash Flow"]

# fixed priority order — which ratios get included first when more than 4 qualify
RATIO_ORDER = ["net_margin", "gross_margin", "roe", "debt_equity", "fcf_conversion"]


def get_row(df, candidates, col):
    """Try each candidate row label in order; None if none present/usable."""
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


def bucket(value, hi, lo):
    if value >= hi:
        return "hi"
    if value <= lo:
        return "lo"
    return "mid"


NET_MARGIN_TEXT = {
    "hi": ["an unusually rich margin profile — well above typical operating averages.",
           "a rich margin profile, the kind that invites scrutiny on how it is sustained.",
           "an unusually high net margin for a business at this scale."],
    "lo": ["a thin margin — small swings in costs or pricing move the bottom line a lot.",
           "a thin margin profile; the business runs close to its cost base.",
           "a thin net margin, leaving little cushion against cost inflation."],
    "mid": ["a moderate, unremarkable margin for the sector.",
            "a middle-of-the-road margin — nothing alarming, nothing standout.",
            "an ordinary margin profile."],
}
GROSS_MARGIN_TEXT = {
    "hi": ["a high gross margin, consistent with strong pricing power or an asset-light cost base.",
           "a high gross margin — most of each revenue dollar survives cost of goods sold."],
    "lo": ["a low gross margin typical of a capital- or input-intensive business.",
           "a low gross margin — cost of goods sold consumes most of revenue."],
    "mid": ["a moderate gross margin, in line with a mixed-cost business model.",
            "a middling gross margin, neither asset-light nor commodity-thin."],
}
ROE_TEXT = {
    "hi": ["a high return on equity — worth checking how much of that is leverage versus "
           "operating efficiency before crediting it entirely to the business.",
           "a high return on shareholder capital; confirm it is not mostly a leverage effect."],
    "lo": ["a weak return on shareholder capital.",
           "a soft return on equity — capital is not being put to particularly efficient use."],
    "mid": ["a moderate return on equity, unremarkable either way.",
            "an ordinary return on shareholder capital."],
}
DEBT_EQUITY_TEXT = {
    "hi": ["a leveraged balance sheet — debt is more than double shareholder equity.",
           "a heavily leveraged balance sheet relative to the equity base."],
    "lo": ["a conservatively financed balance sheet — debt is a small fraction of equity.",
           "a lightly leveraged balance sheet."],
    "mid": ["a moderate leverage level, neither conservative nor stretched.",
            "an unremarkable debt load relative to equity."],
}
FCF_CONV_TEXT = {
    "hi": ["cash generation running ahead of reported earnings — often non-cash charges or a "
           "working-capital tailwind explain the gap.",
           "free cash flow outrunning net income; worth checking what non-cash items or "
           "working-capital swings are behind it."],
    "lo": ["cash conversion lagging reported earnings — worth checking receivables and "
           "accruals before taking the earnings figure at face value.",
           "earnings not fully converting to cash; the accrual side of the statements is "
           "worth a closer look."],
    "mid": ["reasonable, in-line cash conversion — earnings and cash generation broadly agree.",
            "cash conversion tracking earnings closely, nothing to flag."],
}


def compute(tk):
    r = {"ticker": tk}
    t = yf.Ticker(tk)
    inc, bs, cff = t.income_stmt, t.balance_sheet, t.cashflow
    if inc is None or inc.empty or bs is None or bs.empty:
        return {**r, "status": "no_statements"}
    inc_col = inc.columns[0]
    bs_col = bs.columns[0]
    cf_col = cff.columns[0] if cff is not None and not cff.empty else None
    r["statement_date"] = str(inc_col)[:10]

    rev = get_row(inc, REVENUE, inc_col)
    ni = get_row(inc, NET_INCOME, inc_col)
    gp = get_row(inc, GROSS_PROFIT, inc_col)
    eq = get_row(bs, EQUITY, bs_col)
    debt = get_row(bs, DEBT, bs_col)
    fcf = get_row(cff, FCF, cf_col) if cf_col is not None else None

    lines, ratios = [], {}

    if rev and rev > 0 and ni is not None:
        v = ni / rev
        lines.append(("Net Income", ni, "Total Revenue", rev))
        ratios["net_margin"] = {"value": v, "num": ni, "num_label": "Net Income",
                                 "den": rev, "den_label": "Total Revenue", "kind": "pct",
                                 "bucket": bucket(v, 0.20, 0.05), "text": NET_MARGIN_TEXT}
    if rev and rev > 0 and gp is not None:
        v = gp / rev
        lines.append(("Gross Profit", gp, "Total Revenue", rev))
        ratios["gross_margin"] = {"value": v, "num": gp, "num_label": "Gross Profit",
                                   "den": rev, "den_label": "Total Revenue", "kind": "pct",
                                   "bucket": bucket(v, 0.60, 0.30), "text": GROSS_MARGIN_TEXT}
    if eq and eq > 0 and ni is not None:
        v = ni / eq
        lines.append(("Net Income", ni, "Stockholders Equity", eq))
        ratios["roe"] = {"value": v, "num": ni, "num_label": "Net Income",
                          "den": eq, "den_label": "Stockholders Equity", "kind": "pct",
                          "bucket": bucket(v, 0.20, 0.05), "text": ROE_TEXT}
    if eq and eq > 0 and debt is not None:
        v = debt / eq
        lines.append(("Total Debt", debt, "Stockholders Equity", eq))
        ratios["debt_equity"] = {"value": v, "num": debt, "num_label": "Total Debt",
                                  "den": eq, "den_label": "Stockholders Equity", "kind": "x",
                                  "bucket": bucket(v, 2.0, 0.5), "text": DEBT_EQUITY_TEXT}
    if ni and ni > 0 and fcf is not None:
        v = fcf / ni
        lines.append(("Free Cash Flow", fcf, "Net Income", ni))
        ratios["fcf_conversion"] = {"value": v, "num": fcf, "num_label": "Free Cash Flow",
                                     "den": ni, "den_label": "Net Income", "kind": "pct",
                                     "bucket": bucket(v, 1.10, 0.70), "text": FCF_CONV_TEXT}

    if len(ratios) < 2:
        return {**r, "status": "missing_fields"}

    # fixed priority order, capped at 4
    chosen = [k for k in RATIO_ORDER if k in ratios][:4]
    r["ratios"] = {k: ratios[k] for k in chosen}
    r["lines"] = lines
    r["status"] = "ok"
    return r


def fmt_ratio(v, kind):
    return f"{v * 100:.1f}%" if kind == "pct" else f"{v:.2f}x"


def render_user(r):
    tk = r["ticker"]
    names = {"net_margin": "net margin", "gross_margin": "gross margin", "roe": "ROE",
              "debt_equity": "debt/equity", "fcf_conversion": "FCF conversion"}
    seen = set()
    stmt_lines = []
    for k, ratio in r["ratios"].items():
        for label, val in ((ratio["num_label"], ratio["num"]), (ratio["den_label"], ratio["den"])):
            if label not in seen:
                seen.add(label)
                stmt_lines.append(f"  {label}: {fmt_b(val)}")
    ask = ", ".join(names[k] for k in r["ratios"])
    lines = [f"Fundamentals brief — {tk}", "", f"Annual statement lines (FY {r['statement_date']}):"]
    lines += stmt_lines
    lines += ["", f"Compute and interpret: {ask}."]
    return "\n".join(lines)


def render_answer(r):
    tk = r["ticker"]
    parts = []
    for k, ratio in r["ratios"].items():
        computation = f"{fmt_b(ratio['num'])} / {fmt_b(ratio['den'])} = {fmt_ratio(ratio['value'], ratio['kind'])}"
        interp = pick(ratio["text"][ratio["bucket"]], tk, k)
        label = {"net_margin": "Net margin", "gross_margin": "Gross margin", "roe": "ROE",
                 "debt_equity": "Debt/equity", "fcf_conversion": "FCF conversion"}[k]
        parts.append(f"{label}: {computation}. That is {interp}")
    return " ".join(parts)


def build_example(r, system_prompt):
    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": render_user(r)},
            {"role": "assistant", "content": render_answer(r)},
        ],
        "_meta": {"recipe": "recipe2_ratios", "ticker": r["ticker"],
                  "statement_date": r["statement_date"],
                  "ratios": {k: v["value"] for k, v in r["ratios"].items()}},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "out", "recipe2.jsonl"))
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
    rows, skipped = [], {"no_statements": 0, "missing_fields": 0, "error": 0}
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(yf_backoff, compute, t): t for t in tickers}
        for fut in cf.as_completed(futs):
            try:
                r = fut.result()
            except Exception:
                skipped["error"] += 1
                continue
            if r.get("status") != "ok":
                key = r.get("status") if r.get("status") in skipped else "no_statements"
                skipped[key] += 1
                continue
            rows.append(build_example(r, system_prompt))

    n = write_jsonl(args.out, rows)
    ratio_counts, bucket_counts = {}, {}
    for e in rows:
        nk = len(e["_meta"]["ratios"])
        ratio_counts[nk] = ratio_counts.get(nk, 0) + 1
        for k in e["_meta"]["ratios"]:
            bucket_counts[k] = bucket_counts.get(k, 0) + 1
    print(f"wrote {n} examples → {args.out}")
    print(f"ratios-per-example distribution: {json.dumps(ratio_counts, indent=2)}")
    print(f"ratio inclusion counts: {json.dumps(bucket_counts, indent=2)}")
    print(f"skipped: {skipped}")


if __name__ == "__main__":
    main()
