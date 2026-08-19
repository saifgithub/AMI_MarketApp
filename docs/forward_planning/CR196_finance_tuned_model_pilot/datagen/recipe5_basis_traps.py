#!/usr/bin/env python3
"""recipe5_basis_traps.py — CR196 §2 recipe 5: basis-trap generalization.

recipe1 taught period/definitional basis traps on the balance-sheet cross-verification
block specifically. This recipe teaches the SAME underlying skill — reconcile-before-
panicking — on three different bases the model will meet elsewhere in a fundamentals
brief, all sourced from yf.Ticker().info + income_stmt:

  EPS leg      trailingEps (TTM, per the quote) vs Net Income/diluted shares computed
               from the latest FY annual filing — a TTM-vs-FY basis gap
  P/E leg      trailingPE (priced off realized TTM earnings) vs forwardPE (priced off
               forward consensus estimates) — a trailing-measured vs forward-forecast gap
  Revenue leg  info.totalRevenue (TTM) vs income_stmt Total Revenue (last FY) — the same
               TTM-vs-FY gap as the EPS leg, on the top line

The user brief renders each leg's two figures side by side under a "MISMATCH FLAGGED"
tag, WITHOUT stating which basis either figure reflects — that omission is the trap,
mirroring recipe1's DATA CROSS-VERIFICATION shape. A leg is included only when the two
figures diverge by more than 5%; legs that agree within tolerance, or whose inputs are
missing, are dropped silently. A ticker with zero divergent legs is skipped — there is
no trap to teach.

The target answer names each figure's basis, states which one answers the question at
hand, and says explicitly that this is not a data conflict.

Usage: python3 recipe5_basis_traps.py --out out/recipe5.jsonl --limit 50 [--workers 6]
Needs: pip install yfinance pandas
"""
import argparse, concurrent.futures as cf, json, os, sys

import pandas as pd
import yfinance as yf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import fmt_b, load_agent_prompt, load_train_universe, pick, write_jsonl, yf_backoff

NET_INCOME = ["Net Income", "Net Income Common Stockholders",
              "Net Income Continuous Operations", "Net Income Including Noncontrolling Interests"]
REVENUE = ["Total Revenue"]
TOL = 0.05


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


def diff_pct(a, b):
    if a is None or b is None or (a == 0 and b == 0):
        return None
    return abs(a - b) / max(abs(a), abs(b), 1e-9)


def compute(tk):
    r = {"ticker": tk}
    t = yf.Ticker(tk)
    info = t.info
    inc = t.income_stmt
    if not info or inc is None or inc.empty:
        return {**r, "status": "no_data"}
    fy_col = inc.columns[0]
    r["fy_date"] = str(pd.Timestamp(fy_col).date())

    legs = []

    ni = get_row(inc, NET_INCOME, fy_col)
    das = get_row(inc, ["Diluted Average Shares"], fy_col)
    trailing_eps = info.get("trailingEps")
    if ni is not None and das and trailing_eps is not None:
        fy_eps = ni / das
        d = diff_pct(trailing_eps, fy_eps)
        if d is not None and d > TOL:
            legs.append({"name": "eps", "field": "EPS per share",
                         "a": trailing_eps, "b": round(fy_eps, 2), "diff_pct": d,
                         "basis_a": f"trailing twelve-month EPS as of the current quote "
                                    f"(TTM, per the quote)",
                         "basis_b": f"FY {r['fy_date']} diluted EPS computed from the annual "
                                    f"filing: {fmt_b(ni)} net income / {das:,.0f} diluted shares",
                         "guidance": "Use the TTM figure for a trailing-performance or "
                                     "current-valuation read; use the FY-filed figure when "
                                     "comparing directly to that fiscal year's reported results."})

    trailing_pe, forward_pe = info.get("trailingPE"), info.get("forwardPE")
    d = diff_pct(trailing_pe, forward_pe)
    if d is not None and d > TOL:
        legs.append({"name": "pe", "field": "P/E ratio",
                     "a": round(trailing_pe, 2), "b": round(forward_pe, 2), "diff_pct": d,
                     "basis_a": "trailing P/E — price divided by realized TTM earnings",
                     "basis_b": "forward P/E — price divided by analyst-consensus estimated "
                                "earnings for the next fiscal year",
                     "guidance": "Use trailing P/E for a historical valuation read; use "
                                 "forward P/E when the question is about a growth-adjusted "
                                 "or forward-looking valuation."})

    fy_rev = get_row(inc, REVENUE, fy_col)
    ttm_rev = info.get("totalRevenue")
    d = diff_pct(fy_rev, ttm_rev)
    if d is not None and d > TOL:
        legs.append({"name": "revenue", "field": "Total revenue",
                     "a": ttm_rev, "b": fy_rev, "diff_pct": d,
                     "basis_a": "trailing-twelve-month revenue (sum of the last four "
                                "reported quarters, per the quote)",
                     "basis_b": f"FY {r['fy_date']} revenue — the completed fiscal year total "
                                f"from the annual filing",
                     "guidance": "Use TTM for a current run-rate read; use the FY figure for "
                                 "year-over-year comparability against prior annual filings."})

    if not legs:
        return {**r, "status": "no_divergent_legs"}
    r["legs"] = legs
    r["status"] = "ok"
    return r


def leg_strs(leg):
    if leg["name"] == "revenue":
        return fmt_b(leg["a"]), fmt_b(leg["b"])
    return f"{leg['a']:.2f}", f"{leg['b']:.2f}"


def render_user(r):
    tk = r["ticker"]
    lines = [f"Fundamentals brief — {tk}", "", "DATA CROSS-VERIFICATION"]
    for leg in r["legs"]:
        a_str, b_str = leg_strs(leg)
        lines.append(f"  {leg['field']}:  {a_str}  vs  {b_str}  — MISMATCH FLAGGED")
    lines += ["", "The figures above appear to disagree. Reconcile before using either: "
              "is this a data-quality conflict, and which figure should the analysis "
              "rely on?"]
    return "\n".join(lines)


OPENERS = [
    "This is not a data conflict — the two figures are measuring different things.",
    "Before treating this as a vendor disagreement: check what each figure is actually measuring.",
    "The mismatch flag is right that the numbers differ, but wrong to call it a conflict.",
]


def render_answer(r):
    tk = r["ticker"]
    parts = [pick(OPENERS, tk, "open")]
    for leg in r["legs"]:
        a_str, b_str = leg_strs(leg)
        parts.append(f"{leg['field']}: {a_str} is {leg['basis_a']}; {b_str} is "
                     f"{leg['basis_b']} — a {leg['diff_pct'] * 100:.1f}% gap driven entirely "
                     f"by basis, not by a data-quality problem. {leg['guidance']}")
    parts.append("Neither figure is wrong; they answer different questions.")
    return " ".join(parts)


def build_example(r, system_prompt):
    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": render_user(r)},
            {"role": "assistant", "content": render_answer(r)},
        ],
        "_meta": {"recipe": "recipe5_basis_traps", "ticker": r["ticker"], "fy_date": r["fy_date"],
                  "legs": [{"name": leg["name"], "a": leg["a"], "b": leg["b"],
                            "diff_pct": leg["diff_pct"]} for leg in r["legs"]]},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "out", "recipe5.jsonl"))
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
    rows, skipped = [], {"no_data": 0, "no_divergent_legs": 0, "error": 0}
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(yf_backoff, compute, t): t for t in tickers}
        for fut in cf.as_completed(futs):
            try:
                r = fut.result()
            except Exception:
                skipped["error"] += 1
                continue
            if r.get("status") != "ok":
                key = r.get("status") if r.get("status") in skipped else "no_data"
                skipped[key] += 1
                continue
            rows.append(build_example(r, system_prompt))

    n = write_jsonl(args.out, rows)
    leg_counts, n_legs_dist = {}, {}
    for e in rows:
        n_legs_dist[len(e["_meta"]["legs"])] = n_legs_dist.get(len(e["_meta"]["legs"]), 0) + 1
        for leg in e["_meta"]["legs"]:
            leg_counts[leg["name"]] = leg_counts.get(leg["name"], 0) + 1
    print(f"wrote {n} examples → {args.out}")
    print(f"leg inclusion counts: {json.dumps(leg_counts, indent=2)}")
    print(f"legs-per-example distribution: {json.dumps(n_legs_dist, indent=2)}")
    print(f"skipped: {skipped}")


if __name__ == "__main__":
    main()
