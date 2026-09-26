#!/usr/bin/env python3
"""CR228 risk_score=3 arm, run against Kimi instead of vLLM — driven from the
Mac, in-process, deliberately NOT through melehost's shared `ami_api_alpha`
container.

Why not the normal `room_benchmark.py` + `LLM_FORCE_PROVIDER=kimi` recipe:
`LLM_FORCE_PROVIDER` is a process-global env var read once at `Settings()`
construction (backend/app/core/config.py) and consulted by every LLM call on
that container — flipping it on melehost's shared `ami_api_alpha` would
redirect ALL live users' Room/Coach/Brief/Concierge traffic to Kimi for the
whole run, not just this benchmark's calls (confirmed live, no per-request or
per-user provider override exists anywhere in the stack). CR035's arms B/C
took exactly this hit and explicitly call it out as degrading live Alpha.

This script avoids that entirely: it runs `RoomRunner.run()` directly, in this
one Python process on the Mac, with its own `LLMGateway` instance configured
so `_active_provider_name()` resolves to "kimi" for THIS PROCESS ONLY
(`Settings` is a per-process singleton — setting `settings.llm_force_provider`
here has zero effect on melehost's separate `ami_api_alpha` process). vLLM and
Anthropic are still registered (their env vars are present in the Mac's own
.env too) but never called, because the forced provider wins in
`_active_provider_name()` before `_PREFERENCE` is ever consulted.

Reads the real captured mandate/portfolio state via melehost's Postgres over
an SSH tunnel (`ssh -f -N -L 5434:127.0.0.1:5434 melehost`) — this is a
read/write to the SAME production DB `room_benchmark.py` would use (a fresh
synthetic user is minted per the same convention, its row landing in the real
`users`/`room_runs` tables), but the LLM traffic itself never touches
melehost's process.

Output schema matches `backend/scripts/room_benchmark.py`'s JSONL exactly
(batch_id, ticker, user_id, ablation, triggered_at, run_id, cached, status,
verdict, model_tier, duration_ms, error_message, spot_price, finished_at) so
CR228's existing `score_pilot.py`/`score_dial.py` can read this file directly
alongside the vLLM arm's output with no format translation.

Usage (from backend/, with the venv that already has app deps installed):
    export KIMI_API_KEY=...   # the Mac's Open Platform key, NOT melehost's Coding Plan key
    export DB_PASSWORD=...    # melehost's POSTGRES_PASSWORD
    .venv/bin/python3 ../docs/forward_planning/CR228_risk_appetite_differentiation/run_local_kimi.py \\
        --tickers-file ../docs/forward_planning/CR228_risk_appetite_differentiation/tickers_30.txt \\
        --batch-id cr228-r3-kimi-<date> \\
        --out-dir ../docs/forward_planning/CR228_risk_appetite_differentiation/results
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

# CR228's own mandate shape, risk_score fixed at 3 (matches run_pilot.sh's
# base_mandate() and room_benchmark.py's NEUTRAL_MANDATE_OVERRIDE — both
# already default to risk_score=3, so this is not a new mandate design).
MANDATE_R3 = {
    "display_name": "CR228 R3 (Kimi)",
    "primary_goal": "long_term_wealth",
    "horizon": "long",
    "path": "long_horizon",
    "risk_score": 3,
    "drawdown_response": 3,
    "regret_asymmetry": 0,
    "concentration_tolerance": 3,
    "max_drawdown_pct": 30,
    "compliance": {},
}

POST_SPACING_S = 15.0  # matches room_benchmark.py's pacing between tickers


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _snapshot_price(ticker: str) -> float | None:
    try:
        import yfinance as yf

        price = yf.Ticker(ticker).fast_info["last_price"]
        return round(float(price), 4) if price else None
    except Exception:  # noqa: BLE001 — a spot-price miss must not sink the run
        return None


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


# RES009 (docs/Research/RES009_room_llm_consistency/05_kimi_cross_check.md)
# established these live: the app's DEFAULT kimi_base_url/kimi_model
# (settings.py) point at api.kimi.com/coding — the Kimi CODING PLAN product,
# a different key scope from the Mac's Moonshot Open Platform key. Pointing
# this run at the app's defaults with an Open Platform key 401s outright
# (confirmed live, this run's own first smoke test). kimi-k3 is the one Open
# Platform model that genuinely zeroes reasoning when thinking is disabled;
# kimi-k2.7-code* 400s on this key (Coding Plan namespace); kimi-k2.6 leaves
# a documented ~1-token residual.
KIMI_OPEN_PLATFORM_BASE_URL = "https://api.moonshot.ai"
KIMI_OPEN_PLATFORM_MODEL = "kimi-k3"

# Saiful, 2026-09-26: "Turn off reasoning for Kimi" — the first full batch
# (cr228-r3-kimi-20260926, no thinking-disable) ran thinking-ENABLED, at
# ~1-3min/agent-call and ~18min/ticker (measured live on this run's own smoke
# test before the full batch), projecting 9-12h for all 30 tickers. That batch
# was stopped, its partial JSONL discarded (not scored — different config from
# the batch this run produces), and this run replaces it end to end.
#
# RES009 (05_kimi_cross_check.md, "Turning thinking off") already tested 4
# candidate request-body shapes live against this same Moonshot Open Platform
# endpoint/key and found only one that actually works — the other three are
# silently ignored (200 OK, reasoning_tokens still nonzero) or 400:
#   {"no_thinking": true}              -> 200 OK, reasoning_tokens: 18 (ignored)
#   {"enable_thinking": false}         -> 200 OK, reasoning_tokens: 27 (ignored)
#   {"thinking": false}                -> 400 Bad Request
#   {"thinking": {"type": "disabled"}} -> 200 OK, reasoning_tokens: None (works)
# This is NOT the OpenAI/Qwen-style `enable_thinking` flag already wired
# in llm_gateway.py (line ~1073) for the Qwen provider — Moonshot doesn't
# honor that shape, hence the dict-shaped `thinking` key instead.
KIMI_EXTRA_BODY = {"thinking": {"type": "disabled"}}


def _force_kimi_gateway():
    """Build an LLMGateway that resolves to Kimi — at the Moonshot Open
    Platform endpoint/model, not the app's Coding-Plan-shaped defaults, with
    reasoning/thinking disabled — for every call, in THIS process only.
    `settings` is imported fresh here (module-level singleton, constructed
    once at import time) — mutating its fields here has no effect on any
    other process, including melehost's.

    LLMGateway.__init__'s own Kimi-registration branch (llm_gateway.py,
    ~line 1024) does not accept an extra_body override — that constructor
    param only reaches the gateway's Qwen branch today. Rather than fork
    LLMGateway's registration logic, build the gateway normally (so every
    other provider registers exactly as production would) and then replace
    just the "kimi" entry with a manually-constructed OpenAICompatibleProvider
    that adds extra_body=KIMI_EXTRA_BODY — same base_url/model/api_key/
    max_tokens_floor as the gateway would have used, so CR130's reasoning-
    token headroom fix stays in effect even with thinking disabled.
    """
    from app.core.config import settings
    from app.services.llm_gateway import LLMGateway, OpenAICompatibleProvider

    if not settings.kimi_api_key:
        raise SystemExit(
            "KIMI_API_KEY not set (needs the Mac's Open Platform key, not "
            "melehost's Coding Plan key) — refusing to run with Kimi "
            "unregistered, which would silently fall through to vLLM"
        )
    settings.llm_force_provider = "kimi"
    settings.kimi_base_url = KIMI_OPEN_PLATFORM_BASE_URL
    settings.kimi_model = KIMI_OPEN_PLATFORM_MODEL
    gateway = LLMGateway()
    gateway._providers["kimi"] = OpenAICompatibleProvider(  # noqa: SLF001 — see docstring
        name="kimi",
        base_url=KIMI_OPEN_PLATFORM_BASE_URL,
        model_name=KIMI_OPEN_PLATFORM_MODEL,
        api_key=settings.kimi_api_key,
        max_tokens_floor=settings.kimi_max_tokens_floor,
        extra_body=KIMI_EXTRA_BODY,
    )
    active = gateway._active_provider_name()  # noqa: SLF001 — verifying the force actually took
    if active != "kimi":
        raise SystemExit(
            f"LLM_FORCE_PROVIDER=kimi did not take effect — active provider "
            f"resolved to {active!r} instead. Refusing to run: this would "
            f"silently score vLLM against itself under a Kimi label."
        )
    print(f"LLM gateway forced to: {active} ({KIMI_OPEN_PLATFORM_BASE_URL}, "
          f"{KIMI_OPEN_PLATFORM_MODEL}, thinking disabled)")
    return gateway


async def _run_one_ticker(runner, user_id: UUID, ticker: str, mandate) -> dict:
    """Drive one real Room convene via RoomRunner.run(), return a
    room_benchmark.py-shaped result dict (verdict, model_tier, duration_ms,
    status) — everything the JSONL record needs besides the batch/ticker
    bookkeeping fields the caller already has.
    """
    run_id = uuid4()
    started = time.monotonic()
    verdict = None
    model_tier = None
    status = "completed"
    error_message = None
    try:
        async for ev in runner.run(
            run_id=run_id, user_id=user_id, ticker=ticker, mandate=mandate,
            # With thinking disabled (KIMI_EXTRA_BODY), Kimi calls should be
            # back in vLLM's own ballpark — the 180s default scripted-fallback
            # timeout that thinking-ENABLED Kimi blew through (bull_researcher
            # ~2.5min, conservative_debator timed out) was a symptom of
            # reasoning overhead, not a Kimi-vs-vLLM latency gap on its own.
            # Kept at 300s rather than reverting all the way to the 180s
            # default: still a different network path (internet, not LAN) and
            # a different provider than vLLM was tuned against, so some
            # margin stays deliberate rather than assumed away.
            agent_timeout_s=300.0,
        ):
            if ev.kind == "verdict" and ev.verdict is not None:
                verdict = ev.verdict.model_dump() if hasattr(ev.verdict, "model_dump") else ev.verdict
            if getattr(ev, "phase", None) and model_tier is None:
                # RoomEvent doesn't carry model_tier directly on every event;
                # PLAN_TO_TIER resolution happens per-agent inside the runner.
                # Left None here deliberately if never observed — matching
                # room_benchmark.py's own field, which is populated from the
                # persisted run row, not fabricated when absent.
                pass
        if verdict is None:
            status = "no_verdict"
    except Exception as exc:  # noqa: BLE001 — record and continue the batch
        status = "script_error"
        error_message = repr(exc)[:300]
    duration_ms = int((time.monotonic() - started) * 1000)
    return {
        "run_id": str(run_id),
        "cached": False,
        "status": status,
        "verdict": verdict,
        "model_tier": model_tier,
        "duration_ms": duration_ms,
        "error_message": error_message,
    }


async def main_async(args: argparse.Namespace) -> int:
    from app.services.mandate_store import resolve_mandate
    from app.services.room_runner import RoomRunner

    gateway = _force_kimi_gateway()

    tickers = [
        t.strip().upper()
        for t in args.tickers_file.read_text().splitlines()
        if t.strip() and not t.strip().startswith("#")
    ]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    runs_path = args.out_dir / f"runs_{args.batch_id}.jsonl"
    users_path = args.out_dir / "users_kimi.json"
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

    mandate = resolve_mandate(user_id, MANDATE_R3)
    runner = RoomRunner(llm=gateway)

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
        result = await _run_one_ticker(runner, user_id, ticker, mandate)
        record.update(result)
        record["spot_price"] = _snapshot_price(ticker)
        record["finished_at"] = _now_iso()
        _append_jsonl(runs_path, record)
        verdict = record.get("verdict") or {}
        print(
            f"    → {record.get('status')} action={verdict.get('action')} "
            f"spot={record.get('spot_price')} duration_ms={record.get('duration_ms')}",
            flush=True,
        )
        if record.get("status") != "completed":
            failures.append(ticker)
        await asyncio.sleep(args.post_spacing)

    print(f"\ndone: {len(tickers) - len(failures)}/{len(tickers)} completed → {runs_path}")
    if failures:
        print(f"failures ({len(failures)}): {', '.join(failures)} — re-run to retry")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="CR228 risk_score=3, Kimi provider, local (Mac) driver.")
    parser.add_argument("--tickers-file", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--fresh-user", action="store_true")
    parser.add_argument("--post-spacing", type=float, default=POST_SPACING_S)
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
