#!/usr/bin/env python3
"""CR256 card pilot — mechanical enforcement: post-hoc CLAIMS repair.

Voluntary filing was measured dead (six prompt variants, compliance wobbles
0-100% with the same LLM — salience noise, not disobedience). This tool is
the harness-side enforcement: for every desk turn missing a valid CLAIMS
block, one direct call re-asks the model — from its OWN stored turn and the
actual payload it saw (llm_audit system_prompt) — to output only the block.
The repaired turn is written to a turns file that cards_run.py consumes, so
the composite and the ICC gate always run over a complete census.

The repair call is identical for every desk: same re-ask shape, same model
the room ran on. That is the point — enforcement uniform by construction,
no per-room salience lottery.

Usage (from backend/, pg tunnel + env up):
  python3 ../docs/tools/room_investigation_V2/tools/cards_repair.py \
      --runs ../docs/tools/room_investigation_V2/out/cr256-cards-pilot/a/runs_*.jsonl \
      --out ../docs/tools/room_investigation_V2/out/cr256-cards-pilot/repaired.jsonl \
      --provider deepinfra --model deepseek-ai/DeepSeek-V4-Flash
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "library"))

from cards_run import CLAIMS_BLOCK, CARD_LINE, DESKS, ITEMS, fetch_turns  # noqa: E402

REPAIR_ASK = (
    "{original}\n\n---\nYour turn above is missing its CLAIMS block. Output "
    "ONLY the [CLAIMS] block for all five items (eq, vc, vh, bs, moat), one "
    "line per item, in exactly the shape your instructions specify. Do not "
    "rewrite your analysis, do not comment. Output nothing except the block."
)


def has_valid_block(text: str) -> bool:
    m = CLAIMS_BLOCK.search(text or "")
    if not m:
        return False
    for line in m.group(1).strip().splitlines():
        line = line.strip().lstrip("-*").strip()
        if not line:
            continue
        cm = CARD_LINE.match(line)
        if cm and cm.group(1).lower() in ITEMS:
            return True
    return False


def parse_repair_reply(text: str) -> str | None:
    m = CLAIMS_BLOCK.search(text or "")
    if not m:
        return None
    valid = 0
    for line in m.group(1).strip().splitlines():
        line = line.strip().lstrip("-*").strip()
        if not line:
            continue
        cm = CARD_LINE.match(line)
        if cm and cm.group(1).lower() in ITEMS:
            valid += 1
    return m.group(0) if valid >= 3 else None


async def repair_turn(provider: str, model: str, t: dict) -> str | None:
    from provider_gateway import direct_call

    system = (t.get("system_prompt") or "")[:24000]
    ask = REPAIR_ASK.format(original=(t.get("response_text") or "")[:6000])
    r = await direct_call(
        provider,
        system_prompt=system,
        messages=[{"role": "user", "content": ask}],
        model=model,
        max_tokens=1500,
    )
    return parse_repair_reply(r.get("text") or "")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--provider", default="deepinfra")
    ap.add_argument("--model", required=True)
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()

    import os
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit("DATABASE_URL not set (pg tunnel + export first)")

    arms = []
    for path in args.runs:
        arms.extend(json.loads(l) for l in open(path))
    arms = [a for a in arms if a.get("status") == "completed"]
    print(f"{len(arms)} completed rooms across {len(args.runs)} run file(s)")

    sem = asyncio.Semaphore(args.workers)
    out_records = []
    n_missing = n_repaired = n_failed = 0

    async def process_arm(arm):
        nonlocal n_missing, n_repaired, n_failed
        turns = fetch_turns(dsn, arm)
        if not turns:
            return
        jobs = []
        for i, t in enumerate(turns):
            if t["agent_id"] in DESKS and not has_valid_block(t.get("response_text")):
                jobs.append((i, t))
        async with sem:
            for i, t in jobs:
                n_missing += 1
                try:
                    block = await repair_turn(args.provider, args.model, t)
                except Exception as exc:  # noqa: BLE001 — record and continue
                    block = None
                    print(f"  repair error {arm['arm_key']}/{t['agent_id']}: {str(exc)[:120]}")
                if block:
                    turns[i] = dict(t)
                    turns[i]["response_text"] = (t.get("response_text") or "").rstrip() \
                        + "\n\n" + block
                    turns[i]["repaired"] = True
                    n_repaired += 1
                else:
                    n_failed += 1
        ticker, rep = arm["arm_key"].rsplit("-rep", 1)
        out_records.append({
            "arm_key": arm["arm_key"], "risk_score": int(arm["risk_score"]),
            "user_id": arm["user_id"], "ticker": ticker, "rep": rep,
            "verdict": (arm.get("verdict") or {}).get("action"),
            "turns": turns,
        })

    await asyncio.gather(*(process_arm(a) for a in arms))
    with open(args.out, "w") as fh:
        for rec in out_records:
            fh.write(json.dumps(rec) + "\n")
    print(f"missing blocks: {n_missing} | repaired: {n_repaired} | "
          f"unrepairable: {n_failed} → {args.out}")


if __name__ == "__main__":
    asyncio.run(main())
