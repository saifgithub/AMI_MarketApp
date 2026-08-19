#!/usr/bin/env python3
"""recipe6_asof_discipline.py — CR196 §2 recipe 6: as-of-date discipline.

Builds a brief "as of <date D>" where D is a historical calendar quarter-end picked
deterministically 6-12 months back from the freshest date in the ticker's own price
history, then renders ONLY prices and statement figures dated on or before D — nothing
from after D ever reaches the brief, so there is nothing for the model to leak.

Two example types per ticker, built independently — each only when its own inputs allow:

  (a) refusal              user asks "how has the stock performed since D?" — a question
                            about the period AFTER the brief's evidence horizon. The
                            target answer declines to project past D, states the horizon
                            explicitly, and gives what CAN be said from data up to D (the
                            trailing move INTO D, if a point ~6 months earlier exists).
                            Built whenever a price point at/before D exists.

  (b) staleness flag        user asks an ordinary question the brief's newest statement
                            CAN answer, but that statement is >2 quarters (>~182 days)
                            older than D. The target answer answers normally from the
                            newest figures on file AND explicitly flags the gap, naming
                            both dates. Built only when that staleness condition holds —
                            for well-covered large-cap quarterly filers this is often
                            zero, since the newest quarter <= D is usually within one
                            reporting cycle of D; the check still fires correctly for any
                            ticker with a real filing gap in the window.

Price source: yf.Ticker.history(period="2y"), resampled to monthly closes. Statement
source: quarterly_income_stmt (Total Revenue required, Net Income when present). A
ticker with no quarter-end candidate in the 6-12-month window, or no price/statement
data at or before the chosen D, is skipped.

Usage: python3 recipe6_asof_discipline.py --out out/recipe6.jsonl --limit 50 [--workers 6]
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
WINDOW_LOW_DAYS, WINDOW_HIGH_DAYS = 183, 365
TRAIL_BACK_DAYS = 182
STALE_GAP_DAYS = 182  # >2 quarters


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
    hist = t.history(period="2y")
    if hist is None or hist.empty or "Close" not in hist.columns:
        return {**r, "status": "no_price_history"}
    monthly = hist["Close"].resample("ME").last().dropna()
    if monthly.index.tz is not None:
        monthly.index = monthly.index.tz_localize(None)
    if monthly.empty:
        return {**r, "status": "no_price_history"}
    now = monthly.index.max()

    q = t.quarterly_income_stmt
    if q is None or q.empty or "Total Revenue" not in q.index:
        return {**r, "status": "no_statements"}

    candidates = [d for d in pd.date_range(end=now, periods=8, freq="QE")
                  if WINDOW_LOW_DAYS <= (now - d).days <= WINDOW_HIGH_DAYS]
    if not candidates:
        return {**r, "status": "no_asof_candidate"}
    candidates_iso = sorted(d.strftime("%Y-%m-%d") for d in candidates)
    D = pd.Timestamp(pick(candidates_iso, tk, "asof"))
    r["as_of_date"] = str(D.date())

    price_upto = monthly[monthly.index <= D]
    if price_upto.empty:
        return {**r, "status": "no_price_at_asof"}
    r["price_asof"] = float(price_upto.iloc[-1])
    r["price_asof_date"] = str(price_upto.index[-1].date())

    trail_target = D - pd.Timedelta(days=TRAIL_BACK_DAYS)
    trail_series = monthly[monthly.index <= trail_target]
    if not trail_series.empty:
        r["price_trail"] = float(trail_series.iloc[-1])
        r["price_trail_date"] = str(trail_series.index[-1].date())
    else:
        r["price_trail"] = r["price_trail_date"] = None

    q_cols = [c for c in q.columns if pd.Timestamp(c) <= D]
    if not q_cols:
        return {**r, "status": "no_statement_at_asof"}
    newest_col = max(q_cols, key=lambda c: pd.Timestamp(c))
    rev = get_row(q, REVENUE, newest_col)
    if rev is None:
        return {**r, "status": "no_statement_at_asof"}
    ni = get_row(q, NET_INCOME, newest_col)
    newest_dt = pd.Timestamp(newest_col)
    r["newest_data_date"] = str(newest_dt.date())
    r["newest_revenue"] = rev
    r["newest_net_income"] = ni
    gap_days = (D - newest_dt).days
    r["gap_days"] = gap_days
    r["is_stale"] = gap_days > STALE_GAP_DAYS
    r["status"] = "ok"
    return r


def build_refusal_example(r, system_prompt):
    tk, D = r["ticker"], r["as_of_date"]
    lines = [f"Fundamentals brief — {tk}, as of {D}", "",
             "Prices (monthly close, through the as-of date):"]
    if r["price_trail_date"]:
        lines.append(f"  {r['price_trail_date']}: ${r['price_trail']:.2f}")
    lines.append(f"  {r['price_asof_date']}: ${r['price_asof']:.2f}")
    lines.append("")
    stmt_line = f"Most recent statement on file ({r['newest_data_date']}): " \
                f"Total Revenue {fmt_b(r['newest_revenue'])}"
    if r["newest_net_income"] is not None:
        stmt_line += f", Net Income {fmt_b(r['newest_net_income'])}"
    lines += [stmt_line, "", f"How has {tk} performed since {D}?"]
    user = "\n".join(lines)

    parts = [f"This brief's evidence horizon ends at {D} — the last price point on file "
            f"is {r['price_asof_date']} (${r['price_asof']:.2f}) and the newest statement "
            f"is {r['newest_data_date']}. There is no data here for anything after {D}, so "
            f"how the stock has performed SINCE that date is not something this brief can "
            f"answer — stating it would mean asserting facts outside the evidence."]
    if r["price_trail_date"]:
        chg = (r["price_asof"] - r["price_trail"]) / r["price_trail"]
        parts.append(f"What the brief CAN say: from {r['price_trail_date']} "
                     f"(${r['price_trail']:.2f}) to {r['price_asof_date']} "
                     f"(${r['price_asof']:.2f}), the trailing move INTO the as-of date was "
                     f"{chg * 100:+.1f}%. That is a statement about the period up to {D}, "
                     f"not since it.")
    else:
        parts.append(f"The only price point on file at or before {D} is "
                     f"{r['price_asof_date']} (${r['price_asof']:.2f}) — no earlier point "
                     f"is available to describe a trailing move up to that date either.")
    assistant = " ".join(parts)

    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ],
        "_meta": {"recipe": "recipe6_asof_discipline", "ticker": tk, "example_type": "refusal",
                  "as_of_date": D, "newest_data_date": r["newest_data_date"],
                  "price_asof_date": r["price_asof_date"]},
    }


def build_stale_example(r, system_prompt):
    tk, D = r["ticker"], r["as_of_date"]
    stmt_line = f"  {r['newest_data_date']}: Total Revenue {fmt_b(r['newest_revenue'])}"
    if r["newest_net_income"] is not None:
        stmt_line += f", Net Income {fmt_b(r['newest_net_income'])}"
    user = "\n".join([f"Fundamentals brief — {tk}, as of {D}", "",
                      "Most recent statement on file:", stmt_line, "",
                      f"What does the most recent statement on file say about {tk}'s revenue?"])

    gap_quarters = r["gap_days"] / 91.0
    ni_clause = f" and net income of {fmt_b(r['newest_net_income'])}" if r["newest_net_income"] is not None else ""
    assistant = (f"The most recent statement on file is {r['newest_data_date']}, reporting "
                f"revenue of {fmt_b(r['newest_revenue'])}{ni_clause}. Flag on freshness: this "
                f"brief is as of {D}, and {r['newest_data_date']} is {r['gap_days']} days "
                f"(roughly {gap_quarters:.1f} quarters) older than that as-of date — more "
                f"than two reporting cycles behind. Treat this figure as dated for anything "
                f"tied to the current period; a more recent filing may exist that this brief "
                f"does not carry.")

    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ],
        "_meta": {"recipe": "recipe6_asof_discipline", "ticker": tk, "example_type": "stale_flag",
                  "as_of_date": D, "newest_data_date": r["newest_data_date"],
                  "gap_days": r["gap_days"]},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "out", "recipe6.jsonl"))
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
    rows, skipped = [], {"no_price_history": 0, "no_statements": 0, "no_asof_candidate": 0,
                         "no_price_at_asof": 0, "no_statement_at_asof": 0, "error": 0}
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(compute, t): t for t in tickers}
        for fut in cf.as_completed(futs):
            try:
                r = fut.result()
            except Exception:
                skipped["error"] += 1
                continue
            if r.get("status") != "ok":
                key = r.get("status") if r.get("status") in skipped else "no_price_history"
                skipped[key] += 1
                continue
            rows.append(build_refusal_example(r, system_prompt))
            if r["is_stale"]:
                rows.append(build_stale_example(r, system_prompt))

    n = write_jsonl(args.out, rows)
    types = {}
    for e in rows:
        k = e["_meta"]["example_type"]
        types[k] = types.get(k, 0) + 1
    print(f"wrote {n} examples → {args.out}")
    print(f"example types: {json.dumps(types, indent=2)}")
    print(f"skipped: {skipped}")


if __name__ == "__main__":
    main()
