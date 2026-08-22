#!/usr/bin/env python3
"""recipe12_bear_critique.py — CR196 §2c.4 recipe 12: the Bear Researcher's job.

Trains the role contract `content/agents/bear_researcher.md` actually states:

  - lead with the risk thesis in one paragraph
  - identify the **2–3 most dangerous** risks, "not 10 minor ones"
  - quantify downside from the fact sheet's OWN numbers — "if X happens, price
    tests $LEVEL — that is N% below the last close"
  - "never carry a figure over from this instruction"
  - emit the `[STANCE: …]` envelope as the very first line (DEF251 measured 20%
    of debator turns emitting no envelope at all)

## Why the label is verifiable

Companies are SELECTED, not fabricated: only tickers whose real filings make at
least two of `factsheet.py`'s checks fire are used, so a genuine bear case exists
before a word is written. The target is then rendered FROM those computed
findings, which gives two properties for free:

  completeness  — every risk named is one the numbers actually show
  no fabrication — no risk can be named that the numbers do not show, because the
                   renderer has nothing else to draw on

`assert_grounded()` re-checks the finished text: every $ figure and every
percentage must be a token the generator itself computed. It raises on drift.

The risks are ranked by `SEVERITY` and truncated to 3 — training the "2–3 most
dangerous, not 10 minor ones" discipline structurally rather than by asking for it.

Usage: python3 recipe12_bear_critique.py --out out/recipe12.jsonl [--limit N]
Needs: yfinance, pandas (use backend/.venv/bin/python)
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common import load_train_universe, pick, write_jsonl, yf_backoff  # noqa: E402
from factsheet import all_tokens, build_factsheet_cached, cached_tickers  # noqa: E402
from role_common import (assert_grounded, load_role_prompt, stance_format,  # noqa: E402
                         stance_line)

# Ranked by how directly each finding threatens the equity story. Margin
# compression and a persistent accrual gap outrank a working-capital build:
# one is the earnings themselves, the other is a timing signal about them.
SEVERITY = {"margin": 0, "accrual": 1, "revenue_trend": 2, "receivables": 3, "inventory": 4}

THESIS_OPENERS = [
    "The case against taking this position rests on what the statements show rather "
    "than on sentiment:",
    "The reason to avoid this name is visible in its own filings:",
    "The risk here is not a narrative — it is in the numbers on this sheet:",
]

DOWNSIDE_FRAMES = [
    "If these pressures carry into the next reporting period, the level that matters "
    "is the 52-week low at {lo} — that is {dn}% below the last close of {last}, and "
    "nothing in the trajectory above argues the low is unreachable.",
    "Downside is not hypothetical: a retest of the 52-week low at {lo} is {dn}% from "
    "the last close of {last}, and the deterioration above is exactly what takes a "
    "name back to its lows.",
]

CLOSERS = [
    "None of this requires a macro shock. It requires only that the trend already "
    "in the filings continues.",
    "The bull case has to argue these reverse. That argument is not in this sheet.",
]


def build_example(fs: dict, system_prompt: str, fmt: str) -> dict | None:
    ws = sorted(fs["weaknesses"], key=lambda w: SEVERITY.get(w["kind"], 9))[:3]
    if len(ws) < 2:
        return None

    tk = fs["ticker"]
    conviction = "high" if len(ws) >= 3 else "medium"
    headline = ws[0]["headline"]

    body = [pick(THESIS_OPENERS, tk, "open") + " " + ws[0]["text"] + "."]
    if len(ws) > 1:
        body.append("Two further pressures compound it. " if len(ws) > 2
                    else "A second pressure compounds it. ")
        rest = "; ".join(w["text"] for w in ws[1:])
        # NOT str.capitalize(): it lowercases the tail, which turns "$2.71B" into
        # "$2.71b" and silently corrupts every money token after the first word.
        body[-1] += rest[:1].upper() + rest[1:] + "."
    body.append(pick(DOWNSIDE_FRAMES, tk, "down").format(
        lo=f"${fs['lo52']:,.2f}", dn=f"{fs['downside_pct'] * 100:+.1f}",
        last=f"${fs['last']:,.2f}"))
    body.append(pick(CLOSERS, tk, "close"))

    answer = stance_line("against", conviction, headline) + "\n" + "\n\n".join(body)
    assert_grounded(answer, all_tokens(fs, ws), f"recipe12:{tk}")

    user = (fs["sheet"] + "\n\n" +
            "Build the strongest case AGAINST taking this position, from this sheet alone.")
    return {
        "messages": [
            {"role": "system", "content": system_prompt + fmt},
            {"role": "user", "content": user},
            {"role": "assistant", "content": answer},
        ],
        "_meta": {"recipe": "recipe12_bear_critique", "ticker": tk,
                  "risks_named": [w["kind"] for w in ws], "conviction": conviction,
                  "y0_date": fs["y0_date"]},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "out", "recipe12.jsonl"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--cached-only", action="store_true",
                    help="restrict to tickers already in the fact-sheet cache — "
                         "renders fully offline, no Yahoo call at all")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    tickers = load_train_universe()
    if args.cached_only:
        have = cached_tickers()
        tickers = [t for t in tickers if t in have]
        print(f"[cached-only] {len(tickers)} tickers with a fact sheet on disk")
    if args.limit:
        tickers = tickers[: args.limit]

    system_prompt = load_role_prompt("bear_researcher")
    fmt = stance_format(with_size=False)

    rows, skipped = [], {"too_few_weaknesses": 0, "unusable_sheet": 0, "error": 0}
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(build_factsheet_cached, t): t for t in tickers}
        for fut in cf.as_completed(futs):
            try:
                fs = fut.result()
            except Exception:
                skipped["error"] += 1
                continue
            if fs.get("status") != "ok":
                skipped["unusable_sheet"] += 1
                continue
            ex_row = build_example(fs, system_prompt, fmt)
            if ex_row is None:
                skipped["too_few_weaknesses"] += 1
                continue
            rows.append(ex_row)

    n = write_jsonl(args.out, rows)
    kinds = {}
    for r in rows:
        for k in r["_meta"]["risks_named"]:
            kinds[k] = kinds.get(k, 0) + 1
    print(f"wrote {n} examples → {args.out}")
    print(f"risk kinds: {kinds}")
    print(f"skipped: {skipped}")


if __name__ == "__main__":
    main()
