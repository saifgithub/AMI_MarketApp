#!/usr/bin/env python3
"""CR210 — what the Room's machine-read surfaces actually do, on real traffic.

Acceptance 1 as originally written ("`_parse_pm_verdict` receives valid JSON on
every turn") is UNFALSIFIABLE: the unconstrained system already returns valid
JSON on 136/136 recorded production convenes, so a constrained run showing 100%
is indistinguishable from the control showing 100%. It can be passed, never
failed.

This script exists so the number is reported with its own base rate beside it.
It measures the same three things in both directions:

  * from a committed CORPUS  — `--corpus <dir>` over CR143's captured
    `llm_audit_*.json` epochs, runnable on the Mac with no database;
  * from the LIVE table      — `--since/--until` inside `ami_api_alpha`, for the
    before/after batches around a flag flip.

It reports PRODUCTION-PARSER truth (does `extract_json_object` succeed, did the
DEF058 reformatter have to fire) alongside the CR196 INSTRUMENT's own checks
(`score_S4` / `score_S6`), so the Room run and the surfaces eval sit on one axis
instead of two.

`room_pm_reformat` count is the direct observable, not a proxy: the reformatter
fires only when `_parse_pm_verdict` returned None.

Usage:
    python3 -m scripts.cr210_room_audit --corpus docs/.../corpus --out baseline.json
    python -m scripts.cr210_room_audit --since 2026-08-28T00:00:00Z --out batch.json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.llm_json import extract_json_object  # noqa: E402

# The frozen CR196 S5 pattern, and a bold-tolerant twin. Reported as two columns
# on purpose: `_PROSE_FORMAT` tells every prose agent to bold its metrics, so the
# Desk writes `*   **Side:** WAIT`, which the frozen pattern misses and
# production's own `_LEVEL_PATTERNS` does not. One number is comparable to
# CR196; the other is closer to what the app can actually read. Collapsing them
# into one would answer a different question than whichever reader assumed.
P_SIDE_FROZEN = re.compile(r"Side:\s*(BUY|HOLD|WAIT|SELL|SHORT)", re.I)
P_SIDE_BOLD = re.compile(r"\*{0,2}Side:?\*{0,2}[:\s]*\*{0,2}(BUY|HOLD|WAIT|SELL|SHORT)", re.I)


def _from_corpus(directory):
    rows = []
    for f in sorted(glob.glob(os.path.join(directory, "llm_audit_*.json"))):
        d = json.load(open(f))
        rs = d if isinstance(d, list) else (d.get("rows") or d.get("records") or [])
        for r in rs:
            r["_src"] = os.path.basename(f)
        rows += rs
    return rows


def _from_db(since, until):
    from sqlalchemy import select

    from app.db.models import LLMAuditRow
    from app.db.session import get_session

    with get_session() as s:
        q = select(LLMAuditRow).where(
            LLMAuditRow.flow.in_(["room", "room_pm", "room_pm_reformat",
                                  "room_risk_officer"])
        )
        if since:
            q = q.where(LLMAuditRow.created_at >= since)
        if until:
            q = q.where(LLMAuditRow.created_at <= until)
        return [
            {"flow": r.flow, "agent_id": r.agent_id, "response_text": r.response_text,
             "error": r.error, "constraint_status": r.constraint_status,
             "created_at": str(r.created_at)}
            for r in s.execute(q).scalars()
        ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus")
    ap.add_argument("--since")
    ap.add_argument("--until")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    if not args.corpus and not (args.since or args.until):
        raise SystemExit("give --corpus or a --since/--until window")
    rows = _from_corpus(args.corpus) if args.corpus else _from_db(args.since, args.until)

    pm = [r for r in rows if r.get("flow") == "room_pm"]
    officer = [r for r in rows if r.get("flow") == "room_risk_officer"]
    trader = [r for r in rows if r.get("agent_id") == "trader"]
    reformat = [r for r in rows if r.get("flow") == "room_pm_reformat"]

    def _parses(rs):
        return sum(1 for r in rs if extract_json_object(r.get("response_text") or ""))

    actions = Counter()
    approve_missing_size = 0
    for r in pm:
        o = extract_json_object(r.get("response_text") or "") or {}
        a = str(o.get("action") or "").upper()
        actions[a] += 1
        if a == "APPROVE" and o.get("size_pct") in (None, ""):
            approve_missing_size += 1

    # The four values the prompt explicitly forbids and the tolerant parser
    # rescues. A grammar makes them unrepresentable, which is the PM schema's
    # only falsifiable claim — the parse rate has nowhere to go from 100%.
    off_contract = {a: n for a, n in actions.items() if a not in ("APPROVE", "PASS", "")}

    out = {
        "source": args.corpus or f"llm_audit[{args.since}..{args.until}]",
        "n_rows": len(rows),
        "pm": {
            "n": len(pm),
            "strict_parse": _parses(pm),
            "actions": dict(actions),
            "off_contract_actions": off_contract,
            "approve_missing_size_pct": approve_missing_size,
            "reformat_calls": len(reformat),
            "constraint_status": dict(Counter(r.get("constraint_status") for r in pm)),
        },
        "risk_officer": {
            "n": len(officer),
            "strict_parse": _parses(officer),
            "constraint_status": dict(Counter(
                r.get("constraint_status") for r in officer)),
        },
        "trader": {
            "n": len(trader),
            "has_side_frozen_pattern": sum(
                1 for r in trader if P_SIDE_FROZEN.search(r.get("response_text") or "")),
            "has_side_bold_tolerant": sum(
                1 for r in trader if P_SIDE_BOLD.search(r.get("response_text") or "")),
            "constraint_status": dict(Counter(
                r.get("constraint_status") for r in trader)),
        },
    }

    with open(args.out, "w") as fh:
        json.dump(out, fh, indent=1)

    def pct(k, n):
        return f"{k}/{n} ({k / n:.0%})" if n else "n/a"

    print(f"source: {out['source']}")
    print(f"  PM verdict   strict-parse {pct(out['pm']['strict_parse'], len(pm))}"
          f"  reformat calls {len(reformat)}"
          f"  APPROVE-without-size {approve_missing_size}")
    print(f"               off-contract actions: {off_contract or 'none'}")
    print(f"  Risk officer strict-parse {pct(out['risk_officer']['strict_parse'], len(officer))}")
    print(f"  Trader block frozen {pct(out['trader']['has_side_frozen_pattern'], len(trader))}"
          f"  bold-tolerant {pct(out['trader']['has_side_bold_tolerant'], len(trader))}")
    print(f"[cr210] wrote {args.out}")


if __name__ == "__main__":
    main()
