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

## Concurrency (`--max-concurrent-rooms`)

Tickers run through an `asyncio.Semaphore`-bounded pool, not a bare
sequential loop — Saiful, 2026-09-28: "the deepinfra should be able to
handle multiple sessions... look into improving the toolkit to be able to
send multiple concurrent rooms at a time." Verified safe before adding this
(2026-09-28 investigation): `RoomRunner.run()` builds everything it touches
as local variables per call and never mutates `self` state that `run()`
reads (the dedup dicts `_active_queues`/`_active_by_key` are `start_run()`-
only, never touched by the direct `run()` path this toolkit uses); DB access
goes through `get_session()`, a fresh pooled connection per call; the
`Mandate` built once before the loop is read-only and safely shared by
reference. `LLMGateway`/`OpenAICompatibleProvider` already serve concurrent
traffic in production (12 agents fan out per single convene through one
provider instance) — `OutputConstraint`'s own docstring says frozen
specifically "because providers are shared singletons serving concurrent
runs." The toolkit's OWN `_append_jsonl` was the one unsafe part (unguarded
concurrent file writes) — fixed here with an `asyncio.Lock`.

**That check missed a real one: concurrent tickers sharing ONE `user_id`
race `SimEngine.ensure_portfolio`.** Found live the first time this toolkit
ran ≥2 convenes truly in parallel — `room_sim_holdings_failed`/
`room_sector_context_holdings_failed` (`"Multiple rows were found when one
or none was required"`) fired on nearly every ticker, and the resulting
convenes came back corrupted (`REJECT` verdicts — a value the PM should
never emit — on tickers unanimous `APPROVE` in every other arm/provider
tested, e.g. MA). Root cause (confirmed by reading the actual code, not
guessed): `ensure_portfolio` (`backend/app/services/sim_engine.py:961-984`)
does an unlocked SELECT-then-INSERT, and `SimPortfolioRow`'s
`UniqueConstraint(user_id, kind, run_id)` (`backend/app/db/models.py`) is
**silently ineffective** for every training portfolio, because `run_id IS
NULL` for all of them and NULL never equals NULL in a SQL unique
constraint — CR109 slice 2 widened this constraint and, in doing so,
removed the real protection a plain `UNIQUE(user_id)` used to provide. N
concurrent callers for the same `user_id` can all see "no row" and all
INSERT. **This is a real production defect, not a toolkit-only artifact**
— filed as **CR246**, since ordinary concurrent widget loads (sector-watch
+ portfolio-health + a Room card, all independent Riverpod providers) can
plausibly hit the same race for a real brand-new user's first app open.

**Fixed HERE by minting a distinct `user_id` per ticker** (`uuid5`, seeded
from the batch's base user_id + ticker — deterministic across resumes, not
random) instead of sharing one `user_id` across the whole batch. Confirmed
this costs nothing for this toolkit's own measurements: `run_one_ticker`
never calls `sim.submit()`, so nothing accumulates across tickers for one
user — every convene reads the same blank starting portfolio regardless.
Re-smoke-tested after the fix on the exact 4 tickers that corrupted before
(MA/BAC/MO/APD, `--max-concurrent-rooms 4`): zero `holdings_failed`
warnings, MA correctly back to `APPROVE(5)`. **This toolkit fix does NOT
close CR246** — the underlying production race is still live for real
users and needs its own fix (a partial unique index on `(user_id, kind)
WHERE run_id IS NULL`, or row-level locking around the check-then-insert).

**`--max-concurrent-rooms` default is a conservative GUESS, not a measured
limit.** No DeepInfra rate limit (RPS, concurrent connections, quota) is
documented anywhere in this repo — the only existing precedent
(RES009 doc 13) is a researcher's precaution ("run sequentially... to avoid
overlapping API load"), not a measured number. Kimi's 429 behavior IS
documented (RES009/CR228), but that's the Moonshot Open Platform, a
different provider with different limits — do not assume it transfers.
Start low (default 3) and watch for 429s / `room_agent_scripted_fallback
reason=stream_error` spiking before raising it; there is no live evidence
yet for what DeepInfra's real ceiling is.

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
from uuid import UUID, uuid4, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parent))
from room_kimi_gateway import base_mandate, force_gateway, run_one_ticker, snapshot_price  # noqa: E402

POST_SPACING_S = 15.0  # matches run_local_kimi.py / room_benchmark.py's pacing between tickers
DEFAULT_MAX_CONCURRENT_ROOMS = 3  # a guess, not a measured provider limit — see module docstring


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


async def _append_jsonl(lock: asyncio.Lock, path: Path, record: dict) -> None:
    # Concurrent tickers all append to the SAME file — `open(..., "a")` +
    # `write()` is not guaranteed atomic against interleaved writers on every
    # platform/size, so every writer serializes through this one lock rather
    # than relying on OS-level append semantics.
    async with lock:
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
        base_user_id = uuid4()
        users[args.batch_id] = {"user_id": str(base_user_id), "created_at": _now_iso()}
        users_path.write_text(json.dumps(users, indent=2) + "\n")
    else:
        base_user_id = UUID(users[args.batch_id]["user_id"])
    print(f"batch base user: {base_user_id} (local synthetic — not minted via "
          f"/v1/auth/anon, never touches melehost's user table)")

    # One DISTINCT user_id per ticker, not one shared user_id for the whole
    # batch — fixes a real race (2026-09-28): concurrent tickers sharing one
    # user_id all call SimEngine.ensure_portfolio(user_id) (room_runner.py's
    # _build_sim_holdings_block/_build_room_sector_context) at once, which
    # does an unlocked SELECT-then-INSERT with no real uniqueness protection
    # for the training-portfolio row (SimPortfolioRow's UniqueConstraint(
    # user_id, kind, run_id) is silently ineffective when run_id IS NULL,
    # the only shape any Room convene ever uses — NULL never equals NULL in
    # a SQL unique constraint). N concurrent callers for the same user_id can
    # all see "no row" and all INSERT, raising MultipleResultsFound on the
    # next read and corrupting that convene's portfolio/sector-context block
    # (observed live: REJECT verdicts — a value the PM should never emit —
    # on tickers unanimous APPROVE in every other arm). This is filed as its
    # own production defect (CR246 names the root cause), but this toolkit
    # doesn't need to wait for that fix: nothing in this batch shape
    # accumulates across tickers for one user (run_one_ticker never calls
    # sim.submit(), every convene reads the same blank starting portfolio),
    # so a distinct user_id per ticker changes nothing about what's being
    # measured and makes the race structurally impossible — each ticker is
    # the sole caller for its own never-shared user_id.
    #
    # Deterministic (uuid5), not random per run: reproducible across
    # resumes/re-runs with the same --batch-id, and traceable back to the
    # batch's base_user_id in users.json rather than an opaque random value.
    def _user_id_for(ticker: str) -> UUID:
        return uuid5(base_user_id, ticker)

    mandates = {
        t: resolve_mandate(_user_id_for(t), base_mandate(
            risk_score=args.risk_score, display_name=f"{args.batch_id} R{args.risk_score} ({args.provider})",
        ))
        for t in tickers
    }

    to_run = [t for t in tickers if not (latest.get(t) and latest[t].get("status") == "completed")]
    for t in tickers:
        if t not in to_run:
            print(f"{t}: already completed, skip")

    write_lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(args.max_concurrent_rooms)
    failures: list[str] = []
    completed_count = 0
    total = len(to_run)

    async def _run_one(ticker: str) -> None:
        nonlocal completed_count
        async with semaphore:
            ticker_user_id = _user_id_for(ticker)
            print(f"[{ticker}] starting… (slot acquired, user={ticker_user_id})", flush=True)
            triggered_at = _now_iso()
            record = {
                "batch_id": args.batch_id,
                "ticker": ticker,
                "user_id": str(ticker_user_id),
                "ablation": False,
                "triggered_at": triggered_at,
            }
            result = await run_one_ticker(runner, ticker_user_id, ticker, mandates[ticker])
            record.update(result)
            record["spot_price"] = snapshot_price(ticker)
            record["finished_at"] = _now_iso()
            await _append_jsonl(write_lock, runs_path, record)
            completed_count += 1
            verdict = record.get("verdict") or {}
            print(
                f"[{ticker}] ({completed_count}/{total}) → {record.get('status')} "
                f"action={verdict.get('action')} "
                f"votes={verdict.get('approve_votes')}/{verdict.get('samples')} "
                f"spot={record.get('spot_price')} duration_ms={record.get('duration_ms')}",
                flush=True,
            )
            if record.get("status") != "completed":
                failures.append(ticker)
            # Post-spacing now means "hold this slot open a bit longer before
            # freeing it for the next ticker" — keeps SOME pacing even under
            # concurrency, rather than firing every ticker at once.
            await asyncio.sleep(args.post_spacing)

    if to_run:
        print(
            f"running {total} ticker(s), up to {args.max_concurrent_rooms} concurrent "
            f"(--max-concurrent-rooms) …",
            flush=True,
        )
        await asyncio.gather(*(_run_one(t) for t in to_run))

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
    parser.add_argument("--post-spacing", type=float, default=POST_SPACING_S,
                         help="seconds to hold a concurrency slot open after a ticker finishes, "
                              "before freeing it for the next queued ticker")
    parser.add_argument("--max-concurrent-rooms", type=int, default=DEFAULT_MAX_CONCURRENT_ROOMS,
                         help="max Room convenes in flight at once (asyncio.Semaphore-bounded). "
                              f"Default {DEFAULT_MAX_CONCURRENT_ROOMS} is a conservative GUESS, not "
                              "a measured provider limit — see module docstring's Concurrency "
                              "section. --max-concurrent-rooms 1 reproduces the old strictly-"
                              "sequential behavior.")
    parser.add_argument("--allow-mock-market-data", action="store_true",
                         help="skip the settings.use_real_market_data guard (see module docstring)")
    args = parser.parse_args()
    if args.deepinfra_model is None:
        from room_kimi_gateway import DEEPINFRA_DEFAULT_MODEL
        args.deepinfra_model = DEEPINFRA_DEFAULT_MODEL
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
