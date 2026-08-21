#!/usr/bin/env python3
"""recipe14_research_manager.py — CR196 §2c.4 recipe 14: adjudication.

The Research Manager's job (`content/agents/research_manager.md`) is the one role
that is explicitly NOT advocacy: "You don't take sides — you weigh evidence." Its
contract is unusually checkable:

  - a fixed 3-part shape — **points of agreement / points of dispute / recommended
    stance** — with the dispute named on a dimension (timeframe, magnitude,
    probability)
  - a stance drawn from *lean long / pass / wait*
  - **never "short"**: "There is no short option: the simulator rejects any sell
    beyond what is held, and the mandate carries long-only. 'Avoid' is how a
    negative view is expressed." This recipe asserts that on every generated
    target — a hard, machine-checked floor, not a hope.

## The one recipe here that CONSTRUCTS rather than selects

Recipes 12/13 select real companies whose filings make real checks fire. This one
needs a *wrong* case for the manager to reject, so it builds one: one side is
rendered from the fact sheet's computed findings, the other asserts things that are
nowhere in the sheet (management guidance, channel checks, a peer re-rating).
The correct adjudication is therefore known by construction — pick the side that
cites the evidence actually in front of the room.

**Which side is the weak one alternates deterministically by ticker hash.** If the
bear were always the grounded case, the model would learn "side with the bear"
instead of "side with the evidence" — an unconditional prior of exactly the kind
§2c.4 exists to prevent. `--report` prints the realised balance so the split is a
measured number, not an assumption.

Usage: python3 recipe14_research_manager.py --out out/recipe14.jsonl [--limit N]
Needs: yfinance, pandas (use backend/.venv/bin/python)
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common import load_train_universe, pick, write_jsonl, yf_backoff  # noqa: E402
from factsheet import all_tokens, build_factsheet  # noqa: E402
from recipe12_bear_critique import SEVERITY  # noqa: E402
from recipe13_bull_thesis import STRENGTH_RANK  # noqa: E402
from role_common import assert_grounded, load_role_prompt  # noqa: E402

# Claims that reference evidence the room does not have. Each names its own
# absent source, so the manager's rejection can cite what is missing.
UNSUPPORTED_CLAIMS = [
    ("management's guidance for next year points the other way",
     "no guidance figures appear on the fact sheet"),
    ("channel checks suggest demand is already turning",
     "no channel-check or third-party demand data is in front of the room"),
    ("the peer group has re-rated and this name should follow",
     "no peer or relative-valuation data appears on the fact sheet"),
    ("the last earnings call flagged a one-off that will not repeat",
     "no transcript or call commentary is in front of the room"),
]

DIMENSIONS = ["magnitude", "timeframe", "probability"]

FORBIDDEN = ("short", "shorting", "go short", "short the")


def _mk_grounded(findings, direction):
    lead = findings[0]
    body = f"{lead['text']}"
    if len(findings) > 1:
        body += f"; and {findings[1]['text']}"
    verb = "argues for the long side" if direction == "bull" else "argues against the position"
    return f"The {direction.title()} {verb} on the sheet's own figures: {body}.", lead


def _mk_unsupported(tk, direction):
    claim, missing = pick(UNSUPPORTED_CLAIMS, tk, "unsupported")
    verb = "argues for the long side" if direction == "bull" else "argues against the position"
    return (f"The {direction.title()} {verb} on the view that {claim}.", missing)


def build_example(fs, system_prompt):
    ws = sorted(fs["weaknesses"], key=lambda w: SEVERITY.get(w["kind"], 9))[:2]
    ss = sorted(fs["strengths"], key=lambda s: STRENGTH_RANK.get(s["kind"], 9))[:2]
    if not ws or not ss:
        return None

    tk = fs["ticker"]
    h = int(hashlib.sha256(f"side|{tk}".encode()).hexdigest(), 16)
    bull_is_grounded = (h % 2 == 0)

    if bull_is_grounded:
        bull_text, lead = _mk_grounded(ss, "bull")
        bear_text, missing = _mk_unsupported(tk, "bear")
        grounded_side, weak_side = "Bull", "Bear"
        grounded_findings = ss
        stance, stance_word = "lean long", "supports taking the position"
    else:
        bear_text, lead = _mk_grounded(ws, "bear")
        bull_text, missing = _mk_unsupported(tk, "bull")
        grounded_side, weak_side = "Bear", "Bull"
        grounded_findings = ws
        stance, stance_word = "avoid", "argues against taking the position"

    dimension = pick(DIMENSIONS, tk, "dim")
    shared = (f"revenue of {fs['sheet_tokens'] and ''}" if False else
              f"both sides accept the sheet's reported figures — neither disputes the "
              f"statements themselves, and neither disputes the last close of "
              f"${fs['last']:,.2f}")

    answer = (
        f"**1. Points of agreement.** On the evidence in front of the room, "
        f"{shared}. The disagreement is not about what the filings say.\n\n"
        f"**2. Points of dispute.** They diverge on {dimension}. The {grounded_side} "
        f"reasons from figures on this sheet: {lead['text']}. The {weak_side} reasons "
        f"from something else entirely — {missing}, so that argument cannot be weighed "
        f"against the {grounded_side}'s on equal footing, however plausible it sounds.\n\n"
        f"**3. Recommended stance.** {stance.title()}. Weighing only what is in front of "
        f"us, the {grounded_side}'s case {stance_word} and rests on the sheet's own "
        f"numbers; the {weak_side}'s rests on evidence the room does not have. If that "
        f"evidence arrives, this reweighs — until then it does not carry. Sizing stays "
        f"inside the mandate either way."
    )

    for bad in FORBIDDEN:
        if bad in answer.lower():
            raise AssertionError(f"recipe14:{tk}: forbidden short-side language {bad!r}")
    assert_grounded(answer, all_tokens(fs, grounded_findings), f"recipe14:{tk}")

    user = (fs["sheet"] + "\n\n"
            "The Room's two researchers have reported.\n\n"
            f"{bull_text}\n\n{bear_text}\n\n"
            "Adjudicate. Write the synthesis.")
    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user},
            {"role": "assistant", "content": answer},
        ],
        "_meta": {"recipe": "recipe14_research_manager", "ticker": tk,
                  "grounded_side": grounded_side, "stance": stance,
                  "dimension": dimension, "y0_date": fs["y0_date"]},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "out", "recipe14.jsonl"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    tickers = load_train_universe()
    if args.limit:
        tickers = tickers[: args.limit]

    system_prompt = load_role_prompt("research_manager")
    rows, skipped = [], {"no_two_sided_case": 0, "unusable_sheet": 0, "error": 0}
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(yf_backoff, build_factsheet, t): t for t in tickers}
        for fut in cf.as_completed(futs):
            try:
                fs = fut.result()
            except Exception:
                skipped["error"] += 1
                continue
            if fs.get("status") != "ok":
                skipped["unusable_sheet"] += 1
                continue
            row = build_example(fs, system_prompt)
            if row is None:
                skipped["no_two_sided_case"] += 1
                continue
            rows.append(row)

    n = write_jsonl(args.out, rows)
    bal = {"Bull": 0, "Bear": 0}
    for r in rows:
        bal[r["_meta"]["grounded_side"]] += 1
    print(f"wrote {n} examples → {args.out}")
    print(f"grounded-side balance (must be near 50/50): {bal}")
    print(f"skipped: {skipped}")


if __name__ == "__main__":
    main()
