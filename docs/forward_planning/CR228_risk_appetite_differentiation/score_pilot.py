"""CR228 Step 1 scorer — R1 vs R5, paired on ticker.

Reads the two arms' runs_*.jsonl and answers one question: how large is the
risk-appetite difference today, with fail-safe PASSes excluded?

Why the exclusion is not optional. `config.py:138` records ~7% of PM calls being
killed at the old 90s timeout, each degrading to a DEF059 fail-safe PASS. Those
carry no judgement at all, and folding them into a baseline would bake an outage
rate into the number every later step is measured against.

Why mean approve_votes and not the approve rate. CR214 measured the binary
verdict as a ~12-20% coin flip (three byte-identical replays of 136 convenes
disagreed on 26 of 132). `approve_votes` is the 0..5 self-consistency count and
exists precisely so a convene can enter a rank statistic instead
(`schemas/room.py:99-108`). Pairing on ticker removes ticker difficulty as a
variance source, which at n=30 is the dominant one.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from statistics import mean


def load(path: Path) -> dict[str, dict]:
    """Latest record per ticker (the driver appends on resume)."""
    out: dict[str, dict] = {}
    for line in path.read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            out[r["ticker"]] = r
    return out


def classify(rec: dict) -> tuple[str, int | None, float | None]:
    """-> (outcome, approve_votes, size_pct).

    outcome is APPROVE / PASS / REJECT / FAILSAFE / INCOMPLETE. FAILSAFE covers
    both the LLM-outage verdict and a floor override, neither of which is the
    model's own judgement about this trade.
    """
    if rec.get("status") != "completed":
        return "INCOMPLETE", None, None
    v = rec.get("verdict") or {}
    if not v:
        return "INCOMPLETE", None, None
    action = (v.get("action") or "").upper()
    votes = v.get("approve_votes")
    size = v.get("size_pct")
    reason = (v.get("reason") or "").lower()
    if v.get("overridden_from_llm"):
        return "FAILSAFE", votes, size
    if votes is None and action == "PASS" and (
        "unavailable" in reason or "machine-readable" in reason or "not available" in reason
    ):
        return "FAILSAFE", votes, size
    return action or "INCOMPLETE", votes, size


def summarise(name: str, recs: dict[str, dict]) -> dict:
    rows = {t: classify(r) for t, r in recs.items()}
    counts = Counter(o for o, _, _ in rows.values())
    judged = {t: (o, v, s) for t, (o, v, s) in rows.items() if o in ("APPROVE", "PASS", "REJECT")}
    votes = [v for _, v, _ in judged.values() if v is not None]
    sizes = [s for o, _, s in judged.values() if o == "APPROVE" and s is not None]
    appr = sum(1 for o, _, _ in judged.values() if o == "APPROVE")
    print(f"\n=== {name} ===")
    print(f"  records={len(recs)}  {dict(counts)}")
    print(f"  judged (excl. FAILSAFE/INCOMPLETE): {len(judged)}")
    if judged:
        print(f"  approve rate: {appr}/{len(judged)} = {100 * appr / len(judged):.1f}%")
    if votes:
        print(f"  mean approve_votes: {mean(votes):.2f}  (n={len(votes)})")
    if sizes:
        print(f"  mean size_pct on APPROVE: {mean(sizes):.2f}%  (n={len(sizes)})")
    return {"rows": rows, "judged": judged}


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: score_pilot.py <runs_r1.jsonl> <runs_r5.jsonl>")
        return 2
    a, b = Path(argv[1]), Path(argv[2])
    ra, rb = load(a), load(b)
    sa = summarise(f"ARM A risk_score=1  ({a.name})", ra)
    sb = summarise(f"ARM B risk_score=5  ({b.name})", rb)

    both = sorted(set(sa["judged"]) & set(sb["judged"]))
    print(f"\n=== PAIRED (both arms judged): n={len(both)} ===")
    if not both:
        print("  no paired tickers — cannot compare")
        return 0

    va = [sa["judged"][t][1] for t in both]
    vb = [sb["judged"][t][1] for t in both]
    if all(x is not None for x in va + vb):
        da = mean(va)
        db = mean(vb)
        print(f"  mean approve_votes  R1={da:.2f}  R5={db:.2f}  delta={db - da:+.2f}")
        diffs = [y - x for x, y in zip(va, vb)]
        nz = [d for d in diffs if d != 0]
        print(f"  per-ticker vote delta: {sum(1 for d in nz if d > 0)} up, "
              f"{sum(1 for d in nz if d < 0)} down, {len(diffs) - len(nz)} unchanged")

    flips = [(t, sa["judged"][t][0], sb["judged"][t][0]) for t in both
             if sa["judged"][t][0] != sb["judged"][t][0]]
    aa = sum(1 for t in both if sa["judged"][t][0] == "APPROVE")
    ab = sum(1 for t in both if sb["judged"][t][0] == "APPROVE")
    print(f"  approve rate  R1={aa}/{len(both)} ({100 * aa / len(both):.1f}%)  "
          f"R5={ab}/{len(both)} ({100 * ab / len(both):.1f}%)")
    print(f"  verdict flips: {len(flips)}")
    for t, x, y in flips:
        print(f"    {t}: {x} -> {y}")

    # McNemar's exact test on the discordant pairs — the right instrument for a
    # paired binary outcome (CR197 recorded the symmetric flip rate being the
    # WRONG one and giving p=1.0).
    b01 = sum(1 for t in both
              if sa["judged"][t][0] != "APPROVE" and sb["judged"][t][0] == "APPROVE")
    b10 = sum(1 for t in both
              if sa["judged"][t][0] == "APPROVE" and sb["judged"][t][0] != "APPROVE")
    n = b01 + b10
    if n:
        from math import comb
        k = min(b01, b10)
        p = min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / (2 ** n))
        print(f"  McNemar exact: R5-only APPROVE={b01}, R1-only APPROVE={b10}, p={p:.3f}")
    else:
        print("  McNemar: no discordant pairs — the arms agree on every ticker")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
