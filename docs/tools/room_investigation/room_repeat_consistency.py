#!/usr/bin/env python3
"""Run ONE ticker + ONE risk_score N times (fresh synthetic user each draw)
— a full 12-agent Room convene each time, not a single agent call — against
Kimi (thinking disabled) OR vLLM, via a direct RoomRunner call, and report
the action distribution. Generalizes `run_local_kimi_bac_repeat.py` /
`run_local_kimi_bac_repeat_r2.py` (CR228, 2026-09) into a reusable tool.

This is the FULL-ROOM consistency check. For a single agent's consistency on
a FIXED, already-captured prompt (cheaper, isolates one pipeline stage),
use `room_agent_replay.py` instead — both take `--provider kimi|vllm`.

Use this to answer: "is this ticker/risk_score's verdict a stable, repeatable
result, or did I just see one draw of an unstable distribution?" This is the
FIRST thing to run whenever a single Room draw looks surprising, before
concluding anything from it — RES009 and CR228 both found single draws are
not reliable on their own (see docs/Research/RES009_room_llm_consistency/,
especially 07_cr228_bac_risk_score_instability.md, where a risk_score=2 BAC
draw's single PASS turned out to be 1 of 6, the other 5 split 4 APPROVE/1
PASS).

Usage (from backend/, with the venv that already has app deps installed):
    export KIMI_API_KEY=...   # Kimi
    export VLLM_BASE_URL=...  # vLLM, e.g. http://192.168.20.74:8000, LAN-direct
    export DATABASE_URL=...
    .venv/bin/python3 ../docs/tools/room_investigation/room_repeat_consistency.py \\
        --ticker BAC --risk-score 3 --repeats 5 --provider kimi \\
        --out-dir ../docs/tools/room_investigation/out

## Reproducing a REAL user's exact mandate, not the synthetic default

`base_mandate()` (risk_score-only, everything else default — single_name_cap
resolves from risk_score, max_drawdown_pct pinned at 30) is NOT the same
compliance envelope as any real account's stored mandate. Hit this live
2026-09-26: a real user's V room (mandate_version=5, risk_score=3) landed
PASS, but their mandate had single_name_cap_pct=100.0 and sector_cap_pct=100.0
(effectively uncapped) and max_drawdown_pct=50 — materially looser than this
tool's synthetic risk_score=3 default — so it wasn't a clean comparison to
this toolkit's other risk_score=3 runs. Pull the exact `mandates.snapshot`
JSON for their user_id (see `room_llm_audit_trace.py`'s docstring for the
psql/ssh pattern) to a file, then pass `--mandate-file` to reproduce it
verbatim instead of `--risk-score`'s synthetic mandate:
    ssh melehost "docker exec ami_postgres psql -U postgres -d ami_trade -t -A \\
        -c \\"SELECT snapshot FROM mandates WHERE user_id='<uuid>' AND version=<n>;\\"" \\
        > /tmp/their_mandate.json
    .venv/bin/python3 ../docs/tools/room_investigation/room_repeat_consistency.py \\
        --ticker V --mandate-file /tmp/their_mandate.json --repeats 5 \\
        --provider kimi --out-dir ../docs/tools/room_investigation/out
`--risk-score` is still required for the output filename/labeling even when
`--mandate-file` is given — pass the mandate's own `risk_score` field so the
filename/log line stays accurate; the mandate CONTENT sent to the Room comes
entirely from the file, --risk-score does not additionally override it.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent))
from room_kimi_gateway import base_mandate, force_gateway, run_one_ticker  # noqa: E402


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def main_async(args: argparse.Namespace) -> int:
    from app.services.mandate_store import resolve_mandate
    from app.services.room_runner import RoomRunner

    gateway = force_gateway(args.provider)
    runner = RoomRunner(llm=gateway)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / f"{args.ticker.lower()}_repeat_r{args.risk_score}_{args.tag}.jsonl"

    if args.mandate_file:
        mandate_override = json.loads(args.mandate_file.read_text())
        print(f"Using mandate snapshot from {args.mandate_file} (risk_score={mandate_override.get('risk_score')}, "
              f"single_name_cap_pct={mandate_override.get('single_name_cap_pct')}, "
              f"sector_cap_pct={mandate_override.get('sector_cap_pct')}, "
              f"max_drawdown_pct={mandate_override.get('max_drawdown_pct')})")
    else:
        mandate_override = None

    results = []
    for i in range(args.repeats):
        user_id = uuid4()
        mandate = resolve_mandate(user_id, mandate_override if mandate_override is not None else base_mandate(
            risk_score=args.risk_score,
            display_name=f"{args.tag} R{args.risk_score} repeat ({args.ticker})",
        ))
        print(f"[draw {i + 1}/{args.repeats}] {args.ticker}: starting…", flush=True)
        result = await run_one_ticker(runner, user_id, args.ticker, mandate)
        record = {
            "draw": i + 1, "ticker": args.ticker, "risk_score": args.risk_score,
            "user_id": str(user_id), "triggered_at": _now_iso(), **result,
        }
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

    actions = [(r.get("verdict") or {}).get("action") for r in results]
    print(f"\ndone: {args.repeats} draws → {out_path}")
    print(f"actions: {actions}")
    print(f"distribution: {dict(Counter(actions))}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Repeat one ticker+risk_score N times against Kimi, report distribution.")
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--risk-score", type=int, required=True, help="used for the output filename/log line; the actual mandate content sent to the Room is --mandate-file's, when given, not re-derived from this")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--provider", choices=["kimi", "vllm"], default="kimi")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--tag", default=None, help="filename tag (defaults to the provider name)")
    parser.add_argument("--post-spacing", type=float, default=5.0)
    parser.add_argument("--mandate-file", type=Path, default=None, help="JSON mandate snapshot (e.g. a real user's mandates.snapshot column) to use verbatim instead of the synthetic base_mandate()")
    args = parser.parse_args()
    if args.tag is None:
        args.tag = args.provider
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
