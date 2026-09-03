"""CR221 §7 secondary endpoint — was the new line USED, and by whom?

Demand extinction says the Room stopped asking. It does not say the Room read
the answer, and those are different claims: an agent that drops a request
because the sheet grew longer looks identical, in the ask count, to one that
read the figure and was satisfied.

So this counts CITATIONS — a turn that puts one of the line's own figures into
its argument — against two denominators, because only one of them is fair:

  * all twelve agents, which is the number that gets quoted, and
  * **the agents that asked for the item** in the CR219 corpus, which is the
    number that means something. A maturity ladder ignored by the Social Media
    Analyst is not a failure of the ladder.

The precedent this is read against is CR219's own: margin STRUCTURE was cited
by 95.5% of turns and margin TREND by 24.2% off the same sheet, so a low rate
is a real signal about a line, not an artefact of the method.

One warning the first run earned. Citation rate is not value. Measured on CAT,
`.info`'s WRONG free cash flow was cited by 7-8 of 12 agents while the correct
figure that replaced it was cited by 3 — because 200% of free cash flow is
alarming and 112% is unremarkable, and agents cite what argues. A line that
lowers citation by removing a false alarm has done its job.

    backend/.venv/bin/python <this>/citations.py --stamp 20260903T123617Z
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_CR = os.path.abspath(os.path.join(_HERE, ".."))
sys.path.insert(0, os.path.join(_CR, "evidence"))

import inventory  # noqa: E402
import items  # noqa: E402

RESULTS = os.path.join(_HERE, "results")

# One entry per shipped item: the arm that renders it, and the figures its own
# render puts on the CAT sheet. Fingerprints are the RENDERED strings, not
# concepts — "did this line reach the argument", not "did the agent discuss
# debt". Measured from `_format_profile` on the round-1 profile pickle.
SHIPPED = {
    "A1": ("debt", [r"7,120", r"8,920", r"7,747", r"3,112", r"1,261", r"9,656",
                    r"maturity ladder"]),
    "A3": ("debt", [r"5\.1%", r"1,842", r"36,210", r"cost of debt"]),
    "C3": ("cash", [r"13,569", r"4,575", r"8,994", r"cash-flow bridge"]),
    "C4": ("cash", [r"5,001", r"2,391", r"2,957", r"3,368"]),
}

# DEF400 is not a new line — it MOVES one — so it is counted both ways.
DEF400_STALE = [r"5,049", r"\b200% of"]
DEF400_FILED = [r"8,994", r"\b112% of"]


def _asking_agents() -> dict[str, set[str]]:
    """Who asked for each item in the banked 127-line corpus."""
    out: dict[str, set[str]] = collections.defaultdict(set)
    for _, agent, text in inventory.load_requests():
        for item in items.claims(text):
            out[item.id].add(agent)
    return out


def _cited(turns: list[dict], patterns: list[str]) -> set[str]:
    hit = set()
    for turn in turns:
        # The addendum is the instrument, not the turn. A figure quoted only
        # inside `DATA I LACKED:` is the agent naming what it wanted, which is
        # the opposite of a citation.
        body = (turn.get("answer") or "").split("DATA I LACKED")[0]
        if any(re.search(p, body, re.I) for p in patterns):
            hit.add(turn["agent"])
    return hit


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stamp", required=True)
    ap.add_argument("--ticker", default="CAT")
    ap.add_argument("--mandates", nargs="+", default=["short", "medium", "long"])
    ap.add_argument("--results", default=RESULTS)
    args = ap.parse_args()

    asked_by = _asking_agents()
    loaded: dict[tuple[str, str], list[dict]] = {}
    for mandate in args.mandates:
        for arm in ("off", "debt", "cash", "history"):
            path = os.path.join(
                args.results, f"{args.stamp}_{args.ticker}_{mandate}_{arm}.json")
            if os.path.exists(path):
                with open(path) as fh:
                    loaded[(mandate, arm)] = json.load(fh)["turns"]
    if not loaded:
        print("!! no convenes found for that stamp")
        return 1

    print("=" * 92)
    print(f"CITATION — {args.ticker}, {len(loaded)} convenes")
    print("=" * 92)
    print(f"{'item':5s} {'arm':8s} {'cited/12':>9s} {'cited/askers':>13s}  askers")
    print("-" * 92)
    for item_id, (arm, patterns) in SHIPPED.items():
        turns, agents = [], 0
        for (mandate, label), rows in loaded.items():
            if label == arm:
                turns += rows
                agents += len({r["agent"] for r in rows})
        if not turns:
            continue
        cited = _cited(turns, patterns)
        askers = asked_by.get(item_id, set())
        overlap = cited & askers
        print(f"{item_id:5s} {arm:8s} {len(cited):>4d}/{agents:<4d} "
              f"{len(overlap):>6d}/{len(askers):<6d}  "
              f"{','.join(sorted(a[:12] for a in askers)) or '-'}")

    print("\n" + "-" * 92)
    print("DEF400 — the same figure, before and after the fix")
    for label, patterns in (("stale $5,049M / 200%", DEF400_STALE),
                            ("filed $8,994M / 112%", DEF400_FILED)):
        for arm in ("off", "debt", "cash"):
            turns = [t for (m, a), rows in loaded.items() if a == arm for t in rows]
            if not turns:
                continue
            cited = _cited(turns, patterns)
            n = len({t["agent"] for t in turns})
            print(f"  {label:24s} {arm:8s} cited by {len(cited):2d} of {n} agents")
    return 0


if __name__ == "__main__":
    sys.exit(main())
