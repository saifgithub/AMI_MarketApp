#!/usr/bin/env python3
"""Run ONE ticker across a set of risk_score mandate values, against Kimi
(thinking disabled) OR vLLM, via a direct RoomRunner call — generalizes the
CR228-specific `run_local_kimi_aapl_sweep.py` / `run_local_kimi_bac_sweep.py`
(2026-09) into a reusable tool: pass the ticker, risk_scores, and provider on
the command line instead of hardcoding them.

Use this to answer: "does changing risk_score actually change this Room's
verdict for this ticker, right now?" Two findings from the CR228 investigation
this generalizes:
  - AAPL, risk_score 1-5: unanimous 0/5 PASS at every level (no threshold
    effect — the vote was never close enough for the vote-bar change to
    matter).
  - BAC, risk_score 1-5: APPROVE at 1/3/4/5, PASS at 2 — later found (via
    room_agent_trader_replay.py + room_llm_audit_trace.py) to trace to the
    live news feed refreshing between draws, not model instability per se.
    See docs/Research/RES009_room_llm_consistency/07_cr228_bac_risk_score_instability.md.

Usage (from backend/, with the venv that already has app deps installed):
    export KIMI_API_KEY=...   # Mac's Open Platform key (Kimi)
    export VLLM_BASE_URL=...  # e.g. http://192.168.20.74:8000, LAN-direct (vLLM)
    export DATABASE_URL=...   # melehost's Postgres, via SSH tunnel
    .venv/bin/python3 ../docs/tools/room_investigation/room_risk_score_sweep.py \\
        --ticker BAC --risk-scores 1,2,3,4,5 --provider kimi \\
        --out-dir ../docs/tools/room_investigation/out
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent))
from room_kimi_gateway import base_mandate, force_gateway, run_one_ticker, snapshot_price  # noqa: E402


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def main_async(args: argparse.Namespace) -> int:
    from app.services.mandate_store import resolve_mandate
    from app.services.room_runner import RoomRunner

    gateway = force_gateway(args.provider)
    runner = RoomRunner(llm=gateway)

    risk_scores = [int(x) for x in args.risk_scores.split(",")]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / f"{args.ticker.lower()}_risk_sweep_{args.tag}.jsonl"

    results = []
    for risk_score in risk_scores:
        user_id = uuid4()  # fresh synthetic user per arm — mandate resolution is per-user
        mandate = resolve_mandate(user_id, base_mandate(
            risk_score=risk_score, display_name=f"{args.tag} R{risk_score} sweep ({args.ticker})"
        ))
        print(f"[risk_score={risk_score}] {args.ticker}: starting…", flush=True)
        result = await run_one_ticker(runner, user_id, args.ticker, mandate)
        record = {
            "ticker": args.ticker, "risk_score": risk_score, "user_id": str(user_id),
            "triggered_at": _now_iso(), **result,
        }
        record["spot_price"] = snapshot_price(args.ticker)
        with out_path.open("a") as f:
            f.write(json.dumps(record, default=str) + "\n")
        v = record.get("verdict") or {}
        print(
            f"    → {record.get('status')} action={v.get('action')} "
            f"votes={v.get('approve_votes')}/{v.get('samples')} "
            f"duration_ms={record.get('duration_ms')}",
            flush=True,
        )
        results.append(record)
        if args.post_spacing:
            await asyncio.sleep(args.post_spacing)

    print(f"\ndone: wrote {len(results)} records → {out_path}")
    print(f"\n{'risk_score':>10s}  {'action':8s}  votes")
    for r in results:
        v = r.get("verdict") or {}
        print(f"{r['risk_score']:>10d}  {str(v.get('action')):8s}  {v.get('approve_votes')}/{v.get('samples')}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sweep one ticker across risk_score values against Kimi.")
    parser.add_argument("--ticker", required=True, help="e.g. AAPL")
    parser.add_argument("--risk-scores", default="1,2,3,4,5", help="comma-separated, e.g. 1,2,4,5")
    parser.add_argument("--provider", choices=["kimi", "vllm"], default="kimi")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--tag", default=None, help="filename tag, e.g. a date stamp (defaults to the provider name)")
    parser.add_argument("--post-spacing", type=float, default=5.0)
    args = parser.parse_args()
    if args.tag is None:
        args.tag = args.provider
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
