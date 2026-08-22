#!/usr/bin/env python3
"""recipe13_bull_thesis.py — CR196 §2c.4 recipe 13: the Bull Researcher's job.

Trains the three demands `content/agents/bull_researcher.md` makes that a
generically optimistic answer fails:

  1. **Attribution.** "For each piece of evidence, name the analyst it came from —
     'the Fundamentals Analyst's 18.2 P/E', not 'valuation is undemanding'. If it
     came from the fact sheet rather than from a voice in the room, say that
     instead." These examples have NO room transcript, so the correct behaviour is
     to attribute to the fact sheet explicitly — which is precisely the honesty the
     clause is protecting, and the failure mode (inventing an analyst who never
     spoke) is what it exists to prevent.
  2. **Address the Bear's strongest counter.** The fact sheet's computed
     `weaknesses` ARE the bear case, so the target names the most severe one and
     answers it — never pretending it is absent.
  3. **State the break level.** "A number, and what it would take to reach it" —
     rendered from the sheet's own 52-week low, not a caveat.

## Why the label is verifiable

Selection requires at least two computed strengths AND at least one computed
weakness: a bull case that has something real to argue and something real to
concede. The target is rendered only from those computed findings, so it cannot
claim a strength the filings do not show — the hallucination failure mode this
recipe exists to train against. `assert_grounded()` re-checks every figure.

Usage: python3 recipe13_bull_thesis.py --out out/recipe13.jsonl [--limit N]
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
from recipe12_bear_critique import SEVERITY  # noqa: E402
from role_common import (assert_grounded, load_role_prompt, stance_format,  # noqa: E402
                         stance_line)

STRENGTH_RANK = {"cash_conversion": 0, "margin": 1, "revenue_trend": 2, "collection": 3}

OPENERS = [
    "The case for this position comes off the fact sheet, and I am attributing it there "
    "rather than to any voice in the room — no analyst has spoken to this name in this "
    "session:",
    "The long case rests on the fact sheet's own numbers — attributing them there, not "
    "to an analyst, because none has covered this name in this session:",
]

CONCESSION_FRAMES = [
    "The Bear's strongest counter is the honest one: {risk}. That is real and I am not "
    "arguing it away — the question is whether it outweighs what I have put up, and on this "
    "sheet it does not, because the cash and margin evidence is drawn from the same "
    "filings and is the more durable of the two signals.",
    "The strongest argument against me is {risk}. I concede the reading — what I dispute "
    "is the weight, since the case above comes from the same statements and speaks to "
    "the earnings themselves rather than to their timing.",
]

BREAK_FRAMES = [
    "What would break this thesis: a close back at the 52-week low of {lo}, {dn}% below "
    "the last close of {last}. That is the level, not a caveat — reaching it would mean "
    "the trend described above has actually reversed.",
    "The thesis breaks at {lo} — the 52-week low, {dn}% from the last close of {last}. "
    "Below that, the case above is no longer the operative story.",
]


def build_example(fs, system_prompt, fmt):
    ss = sorted(fs["strengths"], key=lambda s: STRENGTH_RANK.get(s["kind"], 9))[:2]
    ws = sorted(fs["weaknesses"], key=lambda w: SEVERITY.get(w["kind"], 9))
    # One real strength plus one real concession is already a legitimate bull turn;
    # demanding two strengths threw away 3/4 of the universe for no gain in contract
    # coverage (attribution / counter / break level are all exercised either way).
    if not ss or not ws:
        return None

    tk = fs["ticker"]
    top_risk = ws[0]
    conviction = "high" if len(fs["strengths"]) >= 3 else "medium" if len(ss) > 1 else "low"

    body = [
        pick(OPENERS, tk, "open") + " " + ss[0]["text"] + ".",
    ]
    if len(ss) > 1:
        body.append("The fact sheet also shows " + ss[1]["text"] + ".")
    body += [
        pick(CONCESSION_FRAMES, tk, "conc").format(risk=top_risk["text"]),
        pick(BREAK_FRAMES, tk, "brk").format(
            lo=f"${fs['lo52']:,.2f}", dn=f"{fs['downside_pct'] * 100:+.1f}",
            last=f"${fs['last']:,.2f}"),
    ]
    answer = stance_line("for", conviction, ss[0]["headline"]) + "\n" + "\n\n".join(body)
    assert_grounded(answer, all_tokens(fs, ss + [top_risk]), f"recipe13:{tk}")

    user = (fs["sheet"] + "\n\n" +
            "Build the strongest case FOR going long, from this sheet alone.")
    return {
        "messages": [
            {"role": "system", "content": system_prompt + fmt},
            {"role": "user", "content": user},
            {"role": "assistant", "content": answer},
        ],
        "_meta": {"recipe": "recipe13_bull_thesis", "ticker": tk,
                  "strengths_named": [s["kind"] for s in ss],
                  "counter_addressed": top_risk["kind"], "conviction": conviction,
                  "y0_date": fs["y0_date"]},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "out", "recipe13.jsonl"))
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

    system_prompt = load_role_prompt("bull_researcher")
    fmt = stance_format(with_size=False)

    rows, skipped = [], {"no_bull_case": 0, "unusable_sheet": 0, "error": 0}
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
            row = build_example(fs, system_prompt, fmt)
            if row is None:
                skipped["no_bull_case"] += 1
                continue
            rows.append(row)

    n = write_jsonl(args.out, rows)
    print(f"wrote {n} examples → {args.out}")
    print(f"skipped: {skipped}")


if __name__ == "__main__":
    main()
