#!/usr/bin/env python3
"""CR228 consistency check: BAC, risk_score=2, repeated N times against Kimi
(thinking disabled) — the BAC risk_score sweep (1,2,4,5) found risk_score=2
reversed to a unanimous 0/5 PASS, breaking what was otherwise a clean
unanimous-APPROVE pattern at risk_score=1 (5/5) and risk_score=3 (5/5 across
6 draws, already confirmed stable by run_local_kimi_bac_repeat.py). Since the
deterministic vote-threshold mechanism (_approve_vote_threshold,
room_runner.py:7945) cannot turn a unanimous 5/5 into a unanimous 0/5 — no
threshold in [1,5] flips a unanimous vote either direction — this reversal
must be coming from the model's actual per-agent/PM judgment differing
substantively at risk_score=2, not from the vote-counting rule. This checks
whether THAT holds up across repeated draws or was itself a single-draw
artifact (the same question already asked and answered for risk_score=3).

Reuses run_local_kimi.py's gateway/runner setup verbatim. Fresh synthetic
user per draw (mandate resolution is per-user, and RoomRunner may cache
per-user state across calls otherwise).

Usage (from backend/, with the venv that already has app deps installed):
    export KIMI_API_KEY=...
    export DB_PASSWORD=...
    .venv/bin/python3 ../docs/forward_planning/CR228_risk_appetite_differentiation/run_local_kimi_bac_repeat_r2.py [N]
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

TICKER = "BAC"
RISK_SCORE = 2
DEFAULT_N = 5

OUT_PATH = Path(__file__).resolve().parent / "results" / "bac_repeat_r2_kimi_nothink_20260926.jsonl"


def _mandate_r3() -> dict:
    return {
        "display_name": "CR228 R2 (Kimi BAC repeat r2)",
        "primary_goal": "long_term_wealth",
        "horizon": "long",
        "path": "long_horizon",
        "risk_score": RISK_SCORE,
        "drawdown_response": RISK_SCORE,
        "regret_asymmetry": 0,
        "concentration_tolerance": RISK_SCORE,
        "max_drawdown_pct": 30,
        "compliance": {},
    }


async def main_async(n: int) -> int:
    from app.services.mandate_store import resolve_mandate
    from app.services.room_runner import RoomRunner
    import run_local_kimi as m

    gateway = m._force_kimi_gateway()
    runner = RoomRunner(llm=gateway)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    results = []
    for i in range(n):
        user_id = uuid4()
        mandate = resolve_mandate(user_id, _mandate_r3())
        print(f"[draw {i + 1}/{n}] {TICKER}: starting…", flush=True)
        result = await m._run_one_ticker(runner, user_id, TICKER, mandate)
        record = {"draw": i + 1, "ticker": TICKER, "risk_score": RISK_SCORE, "user_id": str(user_id), **result}
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

    actions = [((r.get("verdict") or {}).get("action")) for r in results]
    print(f"\ndone: {n} draws → {OUT_PATH}")
    print(f"actions: {actions}")
    from collections import Counter
    print(f"distribution: {dict(Counter(actions))}")
    return 0


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_N
    sys.exit(asyncio.run(main_async(n)))
