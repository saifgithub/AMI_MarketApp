#!/usr/bin/env python3
"""recipe3_trends.py — CR196 §2 recipe 3: trend reasoning over quarterly revenue.

Renders the last 4-6 reported quarters of Total Revenue (and Net Income, when the row
is present) from yf.Ticker.quarterly_income_stmt, asks "what changed, is it
accelerating or decelerating", and writes a target answer that:
  - computes each quarter-over-quarter (QoQ) dollar and percent delta explicitly
  - states the latest year-over-year (YoY) change when a quarter ~12 months before the
    latest one is present in the series (needs 5+ usable quarters)
  - calls acceleration/deceleration/roughly-stable from comparing the LAST TWO QoQ
    growth rates against each other — never from a single delta, never judged
  - explicitly notes these are point observations, not a forecast

Tickers with fewer than 4 usable quarters (after dropping any quarter with a missing/NaN
Total Revenue cell) are skipped — there is not enough series to reason about a trend.

Usage: python3 recipe3_trends.py --out out/recipe3.jsonl --limit 50 [--workers 6]
Needs: pip install yfinance pandas
"""
import argparse, concurrent.futures as cf, datetime, json, os, sys

import pandas as pd
import yfinance as yf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import fmt_b, load_agent_prompt, load_train_universe, pick, write_jsonl

REVENUE = ["Total Revenue"]
NET_INCOME = ["Net Income", "Net Income Common Stockholders",
              "Net Income Continuous Operations", "Net Income Including Noncontrolling Interests"]
MAX_QUARTERS = 6
MIN_QUARTERS = 4
YOY_LOW_DAYS, YOY_HIGH_DAYS = 330, 400


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


def compute(tk):
    r = {"ticker": tk}
    t = yf.Ticker(tk)
    q = t.quarterly_income_stmt
    if q is None or q.empty or "Total Revenue" not in q.index:
        return {**r, "status": "no_statements"}

    cols = sorted(q.columns, key=lambda c: pd.Timestamp(c))[-MAX_QUARTERS:]
    quarters = []
    for c in cols:
        rev = get_row(q, REVENUE, c)
        if rev is None:
            continue
        ni = get_row(q, NET_INCOME, c)
        quarters.append({"date": str(pd.Timestamp(c).date()), "ts": pd.Timestamp(c),
                          "revenue": rev, "net_income": ni})
    if len(quarters) < MIN_QUARTERS:
        return {**r, "status": "too_few_quarters", "n": len(quarters)}

    qoq = []
    for i in range(1, len(quarters)):
        prev, cur = quarters[i - 1], quarters[i]
        if prev["revenue"] == 0:
            qoq.append(None)
            continue
        qoq.append((cur["revenue"] - prev["revenue"]) / prev["revenue"])

    yoy = None
    latest = quarters[-1]
    for cand in quarters[:-1]:
        delta_days = (latest["ts"] - cand["ts"]).days
        if YOY_LOW_DAYS <= delta_days <= YOY_HIGH_DAYS and cand["revenue"]:
            yoy = {"prior_date": cand["date"], "prior_revenue": cand["revenue"],
                   "latest_date": latest["date"], "latest_revenue": latest["revenue"],
                   "value": (latest["revenue"] - cand["revenue"]) / cand["revenue"]}
            break

    direction = None
    valid_qoq = [(i, g) for i, g in enumerate(qoq) if g is not None]
    if len(valid_qoq) >= 2:
        (_, g_prev), (_, g_last) = valid_qoq[-2], valid_qoq[-1]
        gap = g_last - g_prev
        if gap > 0.01:
            direction = "accelerating"
        elif gap < -0.01:
            direction = "decelerating"
        else:
            direction = "roughly stable"

    r.update(quarters=quarters, qoq=qoq, yoy=yoy, direction=direction, status="ok")
    return r


DIRECTION_TEXT = {
    "accelerating": ["Growth is accelerating — the most recent quarter's growth rate is "
                      "higher than the quarter before it.",
                      "The sequence is accelerating: each of the last two quarters grew "
                      "faster than the one before it."],
    "decelerating": ["Growth is decelerating — the most recent quarter's growth rate is "
                      "lower than the quarter before it.",
                      "The sequence is decelerating: the growth rate has slowed "
                      "quarter over quarter."],
    "roughly stable": ["The growth rate is roughly stable quarter to quarter — no clear "
                        "acceleration or deceleration in the last two readings.",
                        "The last two quarters show a similar growth rate — roughly "
                        "stable, not clearly turning either way."],
}


def render_user(r):
    tk = r["ticker"]
    lines = [f"Fundamentals brief — {tk}", "", "Quarterly revenue (Total Revenue):"]
    for qtr in r["quarters"]:
        line = f"  {qtr['date']}: {fmt_b(qtr['revenue'])}"
        if qtr["net_income"] is not None:
            line += f"  (Net Income {fmt_b(qtr['net_income'])})"
        lines.append(line)
    lines += ["", "What changed across these quarters — is growth accelerating or "
              "decelerating?"]
    return "\n".join(lines)


def render_answer(r):
    tk = r["ticker"]
    quarters, qoq = r["quarters"], r["qoq"]
    parts = []
    for i in range(1, len(quarters)):
        prev, cur = quarters[i - 1], quarters[i]
        g = qoq[i - 1]
        if g is None:
            parts.append(f"{prev['date']} to {cur['date']}: revenue base was zero, "
                         f"QoQ growth not computable.")
            continue
        delta = cur["revenue"] - prev["revenue"]
        sign = "+" if delta >= 0 else "-"
        parts.append(f"{prev['date']} to {cur['date']}: {fmt_b(prev['revenue'])} to "
                     f"{fmt_b(cur['revenue'])}, a {sign}{fmt_b(abs(delta))} change "
                     f"({g * 100:+.1f}% QoQ).")
    if r["yoy"] is not None:
        y = r["yoy"]
        parts.append(f"Year-over-year, {y['latest_date']} versus {y['prior_date']}: "
                     f"{fmt_b(y['prior_revenue'])} to {fmt_b(y['latest_revenue'])} "
                     f"({y['value'] * 100:+.1f}% YoY).")
    if r["direction"]:
        parts.append(pick(DIRECTION_TEXT[r["direction"]], tk, "dir"))
    else:
        parts.append("Only one QoQ reading is available, so acceleration or "
                     "deceleration cannot be called from this series alone.")
    parts.append("These are point observations from the reported quarters, not a "
                 "forecast of what comes next.")
    return " ".join(parts)


def build_example(r, system_prompt):
    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": render_user(r)},
            {"role": "assistant", "content": render_answer(r)},
        ],
        "_meta": {"recipe": "recipe3_trends", "ticker": r["ticker"],
                  "n_quarters": len(r["quarters"]), "quarter_dates": [q["date"] for q in r["quarters"]],
                  "qoq": r["qoq"], "yoy": r["yoy"]["value"] if r["yoy"] else None,
                  "direction": r["direction"]},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "out", "recipe3.jsonl"))
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
    rows, skipped = [], {"no_statements": 0, "too_few_quarters": 0, "error": 0}
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(compute, t): t for t in tickers}
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
    directions = {}
    for e in rows:
        d = e["_meta"]["direction"] or "single_reading"
        directions[d] = directions.get(d, 0) + 1
    print(f"wrote {n} examples → {args.out}")
    print(f"directions: {json.dumps(directions, indent=2)}")
    print(f"skipped: {skipped}")


if __name__ == "__main__":
    main()
