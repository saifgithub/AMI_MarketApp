#!/usr/bin/env python3
"""CR256 card pilot — parse CLAIMS/OBJECTIONS blocks from room turns, compute
the direction-signed card composite per room, and score rep-to-rep test-retest.

Post-hoc over Alpha's llm_audit (same fetch pattern as jev_score_runs.py) —
the pilot changes PROMPTS only, zero room_runner surgery. Tolerant parser in
the CR143 family: a missing block marks the desk `cards_absent`; a malformed
card line counts toward `card_malformed` and is dropped, never silently.

Composite (pilot shape, weights provisional — the gate is STABILITY, not the
weights): net_support = mean over all cards of grade_value x direction sign,
signed by each card's OWN direction (never desk membership). evidence_score =
net_support - 0.1 x unanswered, where unanswered = objections at severity
high/medium whose target item has no card graded well by any desk.

Gate: test-retest r of evidence_score across reps >= 0.85 (per spec §6).

Usage (from backend/, pg tunnel + env up):
  python3 ../docs/tools/room_investigation_V2/tools/cards_run.py \
      --runs ../docs/tools/room_investigation_V2/out/cr256-cards/r4/runs_<name>.jsonl \
      --out-dir ../docs/tools/room_investigation_V2/out/cr256-cards/analysis
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import re
import statistics as st
from pathlib import Path

sys_path = Path(__file__).resolve().parent
import sys
sys.path.insert(0, str(sys_path))

# v3 (smoke-measured): only the four evidence desks carry cards. The CFA
# item registry is fundamentals-lane; forcing it on the flow analysts
# produced systematic skips/junk (smoke v1+v2, 2026-10-14). Composite is
# direction-signed across THESE desks' cards.
DESKS = ["fundamentals_analyst", "bull_researcher", "bear_researcher",
         "research_manager"]
OBJ_DESKS = {"bear_researcher", "research_manager"}
ITEMS = ("eq", "vc", "vh", "bs", "moat")
GRADE = {"well": 1.0, "partial": 0.5, "unsupported": 0.0}
DIR = {"support": 1, "oppose": -1, "neutral": 0}

CLAIMS_BLOCK = re.compile(r"\[CLAIMS\](.*?)\[/CLAIMS\]", re.S | re.I)
OBJ_BLOCK = re.compile(r"\[OBJECTIONS\](.*?)\[/OBJECTIONS\]", re.S | re.I)
CARD_LINE = re.compile(
    r"item=(\S+)\s+dir=(\S+)\s+grade=(\S+)\s+data=(\S+)\s+claim=(.+?)"
    r"(?:\s+nums=(.*))?$", re.I)
OBJ_LINE = re.compile(
    r"target=(\S+)\s+severity=(\S+)\s+objection=(.+)$", re.I)


def fetch_turns(dsn: str, arm: dict) -> list[dict]:
    from sqlalchemy import create_engine, text

    eng = create_engine(dsn)
    with eng.connect() as conn:
        rows = conn.execute(text(
            """
            SELECT agent_id, created_at::text AS created_at, response_text
            FROM llm_audit
            WHERE user_id = :uid AND flow = 'room' AND error IS NULL
              AND response_text IS NOT NULL
              AND created_at >= :after AND created_at <= :before
            ORDER BY created_at ASC
            """
        ), {"uid": arm["user_id"], "after": arm["triggered_at"],
            "before": arm["finished_at"]}).mappings().all()
    return [dict(r) for r in rows if r["agent_id"] in DESKS]


def parse_room(turns: list[dict]) -> dict:
    cards, objections = [], []
    flags = collections.Counter()
    for t in turns:
        a = t["agent_id"]
        text = t.get("response_text") or ""
        m = CLAIMS_BLOCK.search(text)
        if not m:
            flags[f"{a}:absent"] += 1
        else:
            for line in m.group(1).strip().splitlines():
                line = line.strip().lstrip("-*").strip()
                if not line:
                    continue
                cm = CARD_LINE.match(line)
                if not cm or cm.group(1).lower() not in ITEMS \
                        or cm.group(2).lower() not in DIR \
                        or cm.group(3).lower() not in GRADE:
                    flags["card_malformed"] += 1
                    continue
                cards.append({
                    "desk": a, "item": cm.group(1).lower(),
                    "dir": cm.group(2).lower(),
                    "grade": cm.group(3).lower(),
                    "data": cm.group(4).lower(),
                    "claim": cm.group(5).strip()[:400],
                    "nums": (cm.group(6) or "").strip()[:200],
                })
        if a in OBJ_DESKS:
            om = OBJ_BLOCK.search(text)
            if om:
                for line in om.group(1).strip().splitlines():
                    line = line.strip().lstrip("-*").strip()
                    if not line:
                        continue
                    o = OBJ_LINE.match(line)
                    if not o or o.group(1).lower() not in ITEMS:
                        flags["objection_malformed"] += 1
                        continue
                    objections.append({
                        "desk": a, "target": o.group(1).lower(),
                        "severity": o.group(2).lower(),
                        "objection": o.group(3).strip()[:400],
                    })
    # Composite
    net = (st.mean(GRADE[c["grade"]] * DIR[c["dir"]] for c in cards)
           if cards else None)
    well_items = {c["item"] for c in cards if c["grade"] == "well"}
    unanswered = sum(1 for o in objections
                     if o["severity"] in ("high", "medium")
                     and o["target"] not in well_items)
    score = (net - 0.1 * unanswered) if net is not None else None
    data_absent = collections.Counter(c["item"] for c in cards
                                      if c["data"] == "no")
    return {"cards": cards, "objections": objections, "flags": dict(flags),
            "net_support": net, "unanswered": unanswered,
            "evidence_score": score,
            "data_absent": dict(data_absent),
            "card_count": len(cards), "objection_count": len(objections)}


def pearson(x, y):
    n = len(x)
    if n < 3:
        return float("nan")
    mx, my = sum(x) / n, sum(y) / n
    c = sum((a - mx) * (b - my) for a, b in zip(x, y))
    vx = sum((a - mx) ** 2 for a in x)
    vy = sum((b - my) ** 2 for b in y)
    return c / math.sqrt(vx * vy) if vx and vy else float("nan")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--dsn", default=None,
                    help="DATABASE_URL default (fallback: env)")
    args = ap.parse_args()

    import os
    dsn = args.dsn or os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit("DATABASE_URL not set")

    arms = [json.loads(l) for l in open(args.runs)]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rooms, absent_rooms = {}, 0
    for arm in arms:
        key = (arm["arm_key"], int(arm["risk_score"]))
        if arm.get("status") != "completed":
            continue
        turns = fetch_turns(dsn, arm)
        if not turns:
            absent_rooms += 1
            continue
        pr = parse_room(turns)
        pr["ticker"], pr["rep"] = arm["arm_key"].rsplit("-rep", 1)
        pr["verdict"] = (arm.get("verdict") or {}).get("action")
        rooms[key] = pr

    # Test-retest across reps (pooled pairs + per-ticker)
    by_ticker = collections.defaultdict(dict)
    for pr in rooms.values():
        by_ticker[pr["ticker"]][pr["rep"]] = pr["evidence_score"]
    pairs, per_ticker = [], {}
    for t, reps in by_ticker.items():
        vals = {r: v for r, v in reps.items() if v is not None}
        keys = sorted(vals)
        ps = [(vals[keys[i]], vals[keys[j]])
              for i in range(len(keys)) for j in range(i + 1, len(keys))]
        per_ticker[t] = {"n": len(vals), "scores": vals,
                         "pair_r": pearson([p[0] for p in ps], [p[1] for p in ps]) if len(keys) >= 3 else None}
        pairs.extend(ps)
    trt = pearson([p[0] for p in pairs], [p[1] for p in pairs])

    n_cards = sum(r["card_count"] for r in rooms.values())
    n_malformed = sum(r["flags"].get("card_malformed", 0) for r in rooms.values())
    n_absent = sum(sum(v for k, v in r["flags"].items() if k.endswith(":absent"))
                   for r in rooms.values())
    desk_turns = len(DESKS) * len(rooms)

    report = {
        "rooms_parsed": len(rooms), "rooms_no_turns": absent_rooms,
        "desk_turns": desk_turns,
        "cards_filed": n_cards, "cards_per_room": round(n_cards / max(len(rooms), 1), 2),
        "card_malformed": n_malformed,
        "malformed_rate": round(n_malformed / max(n_cards + n_malformed, 1), 4),
        "desk_absent_blocks": n_absent,
        "absent_rate": round(n_absent / max(desk_turns, 1), 4),
        "test_retest_r": round(trt, 3),
        "gate_r_required": 0.85,
        "gate_pass": bool(trt >= 0.85),
        "per_ticker": per_ticker,
        "rooms": {f"{k[0]}|{k[1]}": {kk: vv for kk, vv in r.items()
                                    if kk not in ("cards", "objections")}
                  for k, r in rooms.items()},
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, default=str))
    L = ["# CR256 card pilot report", "",
         f"rooms: {len(rooms)} (no turns: {absent_rooms}) | "
         f"cards/room: {report['cards_per_room']} | "
         f"malformed: {n_malformed} ({100*report['malformed_rate']:.1f}%) | "
         f"desks without CLAIMS block: {n_absent} ({100*report['absent_rate']:.1f}%)",
         "",
         f"**test-retest r = {trt:+.3f}** (gate >= 0.85) → "
         f"{'PASS' if report['gate_pass'] else 'FAIL'}", ""]
    L.append("| ticker | n | rep scores | pair r |")
    L.append("|---|---|---|---|")
    for t, d in sorted(per_ticker.items()):
        sc = ", ".join(f"r{r}={v:+.3f}" for r, v in sorted(d["scores"].items()))
        L.append(f"| {t} | {d['n']} | {sc} | {d['pair_r']} |")
    (out_dir / "report.md").write_text("\n".join(L))
    print("\n".join(L[:7]))
    print(f"\nwritten: {out_dir}/report.md + report.json")


if __name__ == "__main__":
    main()
