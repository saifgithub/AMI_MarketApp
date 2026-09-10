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

    backend/.venv/bin/python <this>/citations.py --stamp 20260903T123617Z 20260903T180639Z
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
    # Slot 4, measured from `_format_profile` on the round-3 pickle (the
    # figures are the filing's, so they do not move between pickles).
    # The $B forms are here because the first short-mandate read scored A2 at
    # 0/12 while three agents were arguing from "$32.6B captive finance debt is
    # funded lending, not distress" — qwen rounds the sheet's $M to $B. The
    # earlier rows' markers carry the same blind spot and are left as measured.
    "A2": ("dims", [r"10,713", r"32,617", r"10\.7\s?B", r"32\.6\s?B", r"captive finance \$"]),
    "D1": ("dims", [r"27,143", r"24,800", r"12,185", r"4,220", r"27\.1\s?B", r"24\.8\s?B",
                    r"12\.2\s?B", r"Power Energy", r"Construction Industries", r"Resource Industries"]),
    "D2": ("dims", [r"36,609", r"12,793", r"11,199", r"6,988", r"36\.6\s?B", r"12\.8\s?B",
                    r"11\.2\s?B", r"North America \$", r"EMEA", r"Asia Pacific", r"Latin America"]),
}

# DEF400 is not a new line — it MOVES one — so it is counted both ways.
DEF400_STALE = [r"5,049", r"\b200% of"]
DEF400_FILED = [r"8,994", r"\b112% of"]

# Every arm the shipped table names, plus the baseline — derived, so a new arm
# cannot be scored for demand (replay.py) and silently skipped for citation here.
ARMS = ("off",) + tuple(sorted({arm for arm, _ in SHIPPED.values()}))


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
    ap.add_argument("--stamp", nargs="+", required=True)
    ap.add_argument("--ticker", default="CAT")
    ap.add_argument("--mandates", nargs="+", default=["short", "medium", "long"])
    ap.add_argument("--results", default=RESULTS)
    args = ap.parse_args()

    asked_by = _asking_agents()
    # Newest stamp wins per (mandate, arm): a re-run replaces the cell it re-ran,
    # it does not add a second copy of it. Same rule as replay.py's `_banked`.
    loaded: dict[tuple[str, str], list[dict]] = {}
    for stamp in sorted(args.stamp):
        for mandate in args.mandates:
            for arm in ARMS:
                path = os.path.join(
                    args.results, f"{stamp}_{args.ticker}_{mandate}_{arm}.json")
                if os.path.exists(path):
                    with open(path) as fh:
                        loaded[(mandate, arm)] = json.load(fh)["turns"]
    if not loaded:
        print("!! no convenes found for that stamp")
        return 1

    per_arm = collections.Counter(arm for _, arm in loaded)
    if len(set(per_arm.values())) > 1:
        print(f"!! unequal convene counts per arm {dict(per_arm)} — a citation rate "
              "compared across arms of different size is not a comparison")
        return 1

    print("=" * 92)
    print(f"CITATION — {args.ticker}, {len(loaded)} convenes")
    print("=" * 92)
    print(f"{'item':5s} {'arm':8s} {'cited/turns':>12s} {'cited/askers':>13s}  askers")
    print("-" * 92)
    for item_id, (arm, patterns) in SHIPPED.items():
        turns = [t for (m, label), rows in loaded.items() if label == arm for t in rows]
        agents = len(turns)
        if not turns:
            continue
        cited = _cited(turns, patterns)
        askers = asked_by.get(item_id, set())
        overlap = cited & askers
        print(f"{item_id:5s} {arm:8s} {len(cited):>6d}/{agents:<5d} "
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
            print(f"  {label:24s} {arm:8s} cited by {len(cited):2d} of the {n} "
                  f"distinct agents ({len(turns)} turns)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
