#!/usr/bin/env python3
"""Run a LIST of tickers, one full Room convene each, at a fixed mandate,
against Kimi/vLLM/DeepInfra — generalizes the CR228 batch drivers
(`run_local_kimi.py`, `run_local_kimi_bac_sweep.py`, etc.) the same way
`room_risk_score_sweep.py` generalized the risk_score-sweep-on-one-ticker
shape. Use this one when the axis under test is TICKER, not risk_score —
e.g. CR240's "does DeepInfra/GLM-5.3-Flash reach the same verdicts as Kimi
on the tickers Kimi approved" comparison (2026-09-26).

Resumable: skips any ticker already `status=completed` in the output JSONL
(same convention as `run_local_kimi.py`), so a batch interrupted partway
through (provider outage, credit exhaustion — see RES009/CR228's Kimi 429s)
picks up where it left off on re-run with the same --batch-id/--out-dir.

## `backend/.env` does not exist — every setting below must be exported

`Settings.model_config` has `env_file=".env"`, resolved relative to CWD. This
tool's own usage says "run from backend/", but the repo's real `.env` lives
at the repo ROOT, one level up — `backend/.env` has never existed. Pydantic
loads no file at all in that case, silently falls back to `Settings`' class
defaults, and does NOT error — CLAUDE.md's own "degrade loudly" rule
(CR040) is violated by this gap, but fixing `Settings.model_config` itself
is out of scope for this tool. Concretely, this bit CR240's own 2026-09-26
smoke test live: `USE_REAL_MARKET_DATA=true` sits in the root `.env` but
was never seen by the process, so `market_data_provider_registered
stack=mock_walk` fired silently instead of hitting real Yahoo data, and the
resulting fact sheet said "not available" for every field — a confound
against the original Kimi/vLLM batches, which DID get real data (visible
directly in their captured `verdict.reason` text — real prices/RSI/targets).
**Every setting this tool needs must be exported explicitly in the shell,
not left to an `.env` file the process will silently fail to find:**

    export DATABASE_URL=...          # melehost's Postgres, via SSH tunnel
    export USE_REAL_MARKET_DATA=true # or the run silently uses mock_walk data
    export DEEPINFR_API_KEY=...      # (deepinfra only) codebase's own spelling, see .env
    export KIMI_API_KEY=...          # (kimi only) Mac's Open Platform key
    export VLLM_BASE_URL=...         # (vllm only) e.g. http://192.168.20.74:8000, LAN-direct
    .venv/bin/python3 ../docs/tools/room_investigation/room_ticker_batch.py \\
        --tickers-file tickers.txt --provider deepinfra --risk-score 3 \\
        --batch-id cr240-deepinfra-glm53flash-20260926 \\
        --out-dir ../docs/tools/room_investigation/out
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent))
from room_kimi_gateway import base_mandate, force_gateway, run_one_ticker, snapshot_price  # noqa: E402

POST_SPACING_S = 15.0  # matches run_local_kimi.py / room_benchmark.py's pacing between tickers


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_latest_records(runs_path: Path) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    if runs_path.exists():
        for line in runs_path.read_text().splitlines():
            if line.strip():
                rec = json.loads(line)
                latest[rec["ticker"]] = rec
    return latest


def _append_jsonl(path: Path, record: dict) -> None:
    with path.open("a") as f:
        f.write(json.dumps(record, default=str) + "\n")


async def main_async(args: argparse.Namespace) -> int:
    from app.core.config import settings
    from app.services.mandate_store import resolve_mandate
    from app.services.room_runner import RoomRunner

    if not args.allow_mock_market_data and not settings.use_real_market_data:
        raise SystemExit(
            "settings.use_real_market_data is False — this run would silently "
            "use mock_walk data (see this module's docstring: backend/.env "
            "does not exist, so USE_REAL_MARKET_DATA must be exported "
            "explicitly). This bit CR240's own 2026-09-26 smoke test. "
            "Export USE_REAL_MARKET_DATA=true, or pass --allow-mock-market-data "
            "if a mock-data run is genuinely what you want."
        )

    gateway_kwargs = {"model": args.deepinfra_model} if args.provider == "deepinfra" else {}
    gateway = force_gateway(args.provider, **gateway_kwargs)
    runner = RoomRunner(llm=gateway)

    tickers = [
        t.strip().upper()
        for t in args.tickers_file.read_text().splitlines()
        if t.strip() and not t.strip().startswith("#")
    ]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    runs_path = args.out_dir / f"runs_{args.batch_id}.jsonl"
    users_path = args.out_dir / f"users_{args.provider}_{args.batch_id}.json"
    latest = _load_latest_records(runs_path)

    users = json.loads(users_path.read_text()) if users_path.exists() else {}
    if args.fresh_user or args.batch_id not in users:
        user_id = uuid4()
        users[args.batch_id] = {"user_id": str(user_id), "created_at": _now_iso()}
        users_path.write_text(json.dumps(users, indent=2) + "\n")
    else:
        user_id = UUID(users[args.batch_id]["user_id"])
    print(f"batch user: {user_id} (local synthetic — not minted via /v1/auth/anon, "
          f"never touches melehost's user table)")

    mandate = resolve_mandate(user_id, base_mandate(
        risk_score=args.risk_score, display_name=f"{args.batch_id} R{args.risk_score} ({args.provider})",
    ))

    failures: list[str] = []
    for i, ticker in enumerate(tickers):
        prior = latest.get(ticker)
        if prior and prior.get("status") == "completed":
            print(f"[{i + 1}/{len(tickers)}] {ticker}: already completed, skip")
            continue
        print(f"[{i + 1}/{len(tickers)}] {ticker}: starting…", flush=True)
        triggered_at = _now_iso()
        record = {
            "batch_id": args.batch_id,
            "ticker": ticker,
            "user_id": str(user_id),
            "ablation": False,
            "triggered_at": triggered_at,
        }
        result = await run_one_ticker(runner, user_id, ticker, mandate)
        record.update(result)
        record["spot_price"] = snapshot_price(ticker)
        record["finished_at"] = _now_iso()
        _append_jsonl(runs_path, record)
        verdict = record.get("verdict") or {}
        print(
            f"    → {record.get('status')} action={verdict.get('action')} "
            f"votes={verdict.get('approve_votes')}/{verdict.get('samples')} "
            f"spot={record.get('spot_price')} duration_ms={record.get('duration_ms')}",
            flush=True,
        )
        if record.get("status") != "completed":
            failures.append(ticker)
        await asyncio.sleep(args.post_spacing)

    print(f"\ndone: {len(tickers) - len(failures)}/{len(tickers)} completed → {runs_path}")
    if failures:
        print(f"failures ({len(failures)}): {', '.join(failures)} — re-run with the same --batch-id to retry")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a list of tickers, one full Room convene each, fixed mandate.")
    parser.add_argument("--tickers-file", type=Path, required=True)
    parser.add_argument("--provider", choices=["kimi", "vllm", "deepinfra"], default="kimi")
    parser.add_argument("--deepinfra-model", default=None,
                         help="deepinfra only — defaults to room_kimi_gateway.DEEPINFRA_DEFAULT_MODEL")
    parser.add_argument("--risk-score", type=int, default=3)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--fresh-user", action="store_true")
    parser.add_argument("--post-spacing", type=float, default=POST_SPACING_S)
    parser.add_argument("--allow-mock-market-data", action="store_true",
                         help="skip the settings.use_real_market_data guard (see module docstring)")
    args = parser.parse_args()
    if args.deepinfra_model is None:
        from room_kimi_gateway import DEEPINFRA_DEFAULT_MODEL
        args.deepinfra_model = DEEPINFRA_DEFAULT_MODEL
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
