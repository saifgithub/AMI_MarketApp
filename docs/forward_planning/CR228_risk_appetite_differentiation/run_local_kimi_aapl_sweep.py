#!/usr/bin/env python3
"""CR228 quick longitudinal: AAPL only, risk_score in {1,2,4,5} (3 already run
separately as part of the full 30-ticker batch), against Kimi with thinking
disabled — reuses run_local_kimi.py's gateway/runner setup verbatim.

Purpose: fast read on whether the risk_score dial actually differentiates
Room verdicts at all, without waiting on the full 5-arm x 30-ticker batches.
One ticker, one provider, four mandate variants, run sequentially.

Usage (from backend/, with the venv that already has app deps installed):
    export KIMI_API_KEY=...   # the Mac's Open Platform key
    export DB_PASSWORD=...    # melehost's POSTGRES_PASSWORD
    .venv/bin/python3 ../docs/forward_planning/CR228_risk_appetite_differentiation/run_local_kimi_aapl_sweep.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

TICKER = "AAPL"
RISK_SCORES = [1, 2, 4, 5]  # 3 already covered by the full-batch run

OUT_PATH = Path(__file__).resolve().parent / "results" / "aapl_risk_sweep_kimi_nothink_20260926.jsonl"


def _mandate_for(risk_score: int) -> dict:
    # Same shape as run_pilot.sh's base_mandate(): risk_score, drawdown_response,
    # and concentration_tolerance all track the same arm value (CR228's own
    # convention, not introduced here) — max_drawdown_pct pinned at 30 regardless.
    return {
        "display_name": f"CR228 R{risk_score} (Kimi AAPL sweep)",
        "primary_goal": "long_term_wealth",
        "horizon": "long",
        "path": "long_horizon",
        "risk_score": risk_score,
        "drawdown_response": risk_score,
        "regret_asymmetry": 0,
        "concentration_tolerance": risk_score,
        "max_drawdown_pct": 30,
        "compliance": {},
    }


async def main_async() -> int:
    from app.services.mandate_store import resolve_mandate
    from app.services.room_runner import RoomRunner
    import run_local_kimi as m

    gateway = m._force_kimi_gateway()
    runner = RoomRunner(llm=gateway)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    results = []
    for risk_score in RISK_SCORES:
        user_id = uuid4()  # fresh synthetic user per arm, same convention as run_local_kimi.py
        mandate = resolve_mandate(user_id, _mandate_for(risk_score))
        print(f"[risk_score={risk_score}] {TICKER}: starting…", flush=True)
        result = await m._run_one_ticker(runner, user_id, TICKER, mandate)
        record = {
            "ticker": TICKER,
            "risk_score": risk_score,
            "user_id": str(user_id),
            **result,
        }
        with OUT_PATH.open("a") as f:
            f.write(json.dumps(record, default=str) + "\n")
        v = record.get("verdict") or {}
        print(
            f"    → {record.get('status')} action={v.get('action')} "
            f"votes={v.get('approve_votes')}/{v.get('total_votes')} "
            f"duration_ms={record.get('duration_ms')}",
            flush=True,
        )
        results.append(record)

    print(f"\ndone: wrote {len(results)} records → {OUT_PATH}")
    print("\nsummary:")
    print(f"{'risk_score':>10s}  {'action':8s}  votes")
    for r in results:
        v = r.get("verdict") or {}
        print(f"{r['risk_score']:>10d}  {str(v.get('action')):8s}  {v.get('approve_votes')}/{v.get('total_votes')}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main_async()))
