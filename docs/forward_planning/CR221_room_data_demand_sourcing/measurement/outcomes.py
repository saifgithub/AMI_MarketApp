"""CR221 §7.4 — the verdict, RECORDED and not attributed, and what the data cost.

§7.1 rules the verdict out as an endpoint on measured grounds: `risk_officer.py:32`
records 19.7% of convenes splitting across byte-identical inputs, so a verdict
that moves after a field lands cannot be told from a coin at any n this can
afford. It is recorded anyway, because "we did not measure it" and "we did not
look" are different statements and only the first is defensible.

The cost side is not noisy and is worth stating plainly: every new line is
prompt tokens on twelve turns plus the PM's draws, on every convene, forever.

    backend/.venv/bin/python <this>/outcomes.py --stamp 20260903T123617Z ...
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(_HERE, "results")
ARMS = ("off", "debt", "cash", "history")


def _load(results: str, stamps: list[str], ticker: str, mandate: str, arm: str):
    for stamp in sorted(stamps, reverse=True):
        path = os.path.join(results, f"{stamp}_{ticker}_{mandate}_{arm}.json")
        if os.path.exists(path):
            with open(path) as fh:
                return json.load(fh)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stamp", nargs="+", required=True)
    ap.add_argument("--ticker", default="CAT")
    ap.add_argument("--mandates", nargs="+", default=["short", "medium", "long"])
    ap.add_argument("--results", default=RESULTS)
    args = ap.parse_args()

    print("=" * 96)
    print("VERDICTS — recorded, NOT attributed (§7.1: 19.7% split on identical inputs)")
    print("=" * 96)
    print(f"{'cell':16s} {'action':9s} {'approve':>8s} {'agreement':>10s}  one-line reason")
    cost: dict[str, list[tuple[int, int]]] = collections.defaultdict(list)
    actions: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for mandate in args.mandates:
        for arm in ARMS:
            convene = _load(args.results, args.stamp, args.ticker, mandate, arm)
            if convene is None:
                continue
            pm = convene.get("pm") or {}
            verdict = pm.get("verdict") or {}
            draws = pm.get("draws") or []
            prompt = (sum(t.get("tok_prompt") or 0 for t in convene["turns"])
                      + sum(d.get("tok_prompt") or 0 for d in draws))
            out = (sum(t.get("tok_out") or 0 for t in convene["turns"])
                   + sum(d.get("tok_out") or 0 for d in draws))
            cost[arm].append((prompt, out))
            action = str(verdict.get("action"))
            actions[arm][action] += 1
            reason = " ".join(str(verdict.get("reason") or "").split())[:60]
            print(f"{mandate + '/' + arm:16s} {action:9s} "
                  f"{str(pm.get('approve_votes')):>8s} {str(pm.get('agreement')):>10s}  {reason}")

    print("\n" + "=" * 96)
    print("COST — prompt tokens are what a longer fact sheet actually buys and costs")
    print("=" * 96)
    baseline = None
    print(f"{'arm':10s} {'convenes':>9s} {'prompt tok':>12s} {'out tok':>10s} "
          f"{'vs off':>8s}  verdicts")
    for arm in ARMS:
        if not cost[arm]:
            continue
        prompt = sum(p for p, _ in cost[arm]) / len(cost[arm])
        out = sum(o for _, o in cost[arm]) / len(cost[arm])
        if arm == "off":
            baseline = prompt
        delta = f"{(prompt / baseline - 1) * 100:+.1f}%" if baseline else "—"
        print(f"{arm:10s} {len(cost[arm]):>9d} {prompt:>12,.0f} {out:>10,.0f} "
              f"{delta:>8s}  {dict(actions[arm])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
