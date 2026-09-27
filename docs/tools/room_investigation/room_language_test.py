#!/usr/bin/env python3
"""Run N full Room convenes with a non-English response instruction injected
into EVERY agent's system_prompt, on any provider — CR240's language-support
check (Saiful, 2026-09-26/27: "We need Malay and Arabic in addition to
English" / "do 5 rooms on both ami-llm and glm5.3").

## Why prompt-injection, not a room_prompts.py change

RES009 doc 14 checked first: `mandate.locale` is metadata-only inside the
English system prompt today (`f"- locale: {mandate.locale}\\n"`), never an
instruction, and no pre-translated prompt infrastructure exists anywhere in
this codebase. The only mechanism that currently exists — and the one
Saiful asked to test — is "English prompt + an appended respond-in-X
instruction." This script tests that mechanism across a FULL Room convene
(every one of the 12 agents), not just one isolated agent replay the way
doc 14's first pass did.

**Nothing here touches production code.** The injection happens by
monkey-patching `LLMGateway.stream_chat` in-process, in THIS throwaway
script's process only, to append the instruction to `system_prompt` before
delegating to the real implementation — `room_prompts.py`/`room_runner.py`
are never modified. This is the same "run RoomRunner.run() directly, in a
throwaway process" pattern every other script in this toolkit uses
(room_kimi_gateway.py's docstring has the full rationale).

## Usage (from backend/, with the venv that already has app deps installed)

    export DATABASE_URL=...          # melehost's Postgres, via SSH tunnel
    export USE_REAL_MARKET_DATA=true # see room_ticker_batch.py's docstring — backend/.env
                                      # does not exist, export explicitly or this silently
                                      # degrades to mock_walk data
    export DEEPINFR_API_KEY=...      # deepinfra only
    export VLLM_BASE_URL=...         # vllm only, e.g. http://192.168.20.74:8000

    # Consistency depth: one ticker, N draws
    .venv/bin/python3 ../docs/tools/room_investigation/room_language_test.py \\
        --ticker SO --provider vllm --language arabic --repeats 5 \\
        --out-dir ../docs/tools/room_investigation/out

    # Variety: a spread of tickers, one draw each (--tickers-file instead of --ticker)
    .venv/bin/python3 ../docs/tools/room_investigation/room_language_test.py \\
        --tickers-file tickers.txt --provider vllm --language arabic \\
        --out-dir ../docs/tools/room_investigation/out
"""
from __future__ import annotations

import argparse
import asyncio
import functools
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent))
from room_kimi_gateway import base_mandate, force_gateway, run_one_ticker, snapshot_price  # noqa: E402

LANGUAGE_INSTRUCTIONS = {
    "arabic": (
        "\n\nIMPORTANT: Respond ENTIRELY in Modern Standard Arabic (فصحى). "
        "Keep any [STANCE: .../CONVICTION: .../HEADLINE: ...] or Side:/other "
        "required tag format EXACTLY as specified elsewhere in this prompt "
        "(tag keywords and structure unchanged), but translate the tag "
        "VALUES and all narrative text into Arabic."
    ),
    "malay": (
        "\n\nIMPORTANT: Respond ENTIRELY in Bahasa Malaysia (Malay). "
        "Keep any [STANCE: .../CONVICTION: .../HEADLINE: ...] or Side:/other "
        "required tag format EXACTLY as specified elsewhere in this prompt "
        "(tag keywords and structure unchanged), but translate the tag "
        "VALUES and all narrative text into Malay."
    ),
}


def _patch_gateway_for_language(gateway, instruction: str) -> None:
    """Wrap LLMGateway.stream_chat on this ONE instance so every agent call
    in this process gets the language instruction appended to its
    system_prompt. AsyncIterator-returning method — patch by wrapping the
    async generator itself, not by mutating shared state.
    """
    original_stream_chat = gateway.stream_chat

    @functools.wraps(original_stream_chat)
    async def patched_stream_chat(*, system_prompt: str, **kwargs):
        async for chunk in original_stream_chat(system_prompt=system_prompt + instruction, **kwargs):
            yield chunk

    gateway.stream_chat = patched_stream_chat


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def main_async(args: argparse.Namespace) -> int:
    from app.services.mandate_store import resolve_mandate
    from app.services.room_runner import RoomRunner
    from app.core.config import settings

    if not args.allow_mock_market_data and not settings.use_real_market_data:
        raise SystemExit(
            "settings.use_real_market_data is False — this run would silently "
            "use mock_walk data. Export USE_REAL_MARKET_DATA=true, or pass "
            "--allow-mock-market-data if a mock-data run is genuinely wanted."
        )

    gateway_kwargs = {"model": args.deepinfra_model} if args.provider == "deepinfra" else {}
    gateway = force_gateway(args.provider, **gateway_kwargs)
    _patch_gateway_for_language(gateway, LANGUAGE_INSTRUCTIONS[args.language])
    runner = RoomRunner(llm=gateway)

    args.out_dir.mkdir(parents=True, exist_ok=True)

    # --tickers-file: one draw each, across a spread of tickers (variety).
    # --ticker: the same ticker repeated --repeats times (consistency depth).
    # Mutually exclusive — argparse group below enforces exactly one is given.
    if args.tickers_file:
        tickers = [
            t.strip().upper()
            for t in args.tickers_file.read_text().splitlines()
            if t.strip() and not t.strip().startswith("#")
        ]
        plan = [(t, 1) for t in tickers]  # (ticker, draw_number) — always draw 1 here
        tag = f"{args.provider}_{args.language}_multiticker"
    else:
        plan = [(args.ticker, i + 1) for i in range(args.repeats)]
        tag = f"{args.provider}_{args.language}_{args.ticker.lower()}"

    out_path = args.out_dir / f"language_test_{tag}.jsonl"

    results = []
    for idx, (ticker, draw_num) in enumerate(plan):
        user_id = uuid4()  # fresh synthetic user per draw
        mandate = resolve_mandate(user_id, base_mandate(
            risk_score=args.risk_score,
            display_name=f"CR240 language test ({args.language}, {args.provider}, {ticker})",
        ))
        print(f"[{idx + 1}/{len(plan)}] {ticker} draw {draw_num} ({args.language}, {args.provider}): starting…", flush=True)
        result = await run_one_ticker(runner, user_id, ticker, mandate)
        record = {
            "draw": draw_num,
            "ticker": ticker,
            "provider": args.provider,
            "language": args.language,
            "user_id": str(user_id),
            "triggered_at": _now_iso(),
            **result,
        }
        record["spot_price"] = snapshot_price(ticker)
        with out_path.open("a") as f:
            f.write(json.dumps(record, default=str) + "\n")
        v = record.get("verdict") or {}
        reason_preview = (v.get("reason") or "")[:120].replace("\n", " ")
        print(
            f"    → {record.get('status')} action={v.get('action')} "
            f"votes={v.get('approve_votes')}/{v.get('samples')} "
            f"duration_ms={record.get('duration_ms')}\n"
            f"    reason preview: {reason_preview}",
            flush=True,
        )
        results.append(record)
        if args.post_spacing:
            await asyncio.sleep(args.post_spacing)

    print(f"\ndone: wrote {len(results)} records → {out_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run N full Room convenes with a non-English response instruction injected into every agent's system_prompt.")
    ticker_group = parser.add_mutually_exclusive_group(required=True)
    ticker_group.add_argument("--ticker", help="single ticker, repeated --repeats times (consistency depth)")
    ticker_group.add_argument("--tickers-file", type=Path, help="list of tickers, one draw each (variety)")
    parser.add_argument("--provider", choices=["kimi", "vllm", "deepinfra"], required=True)
    parser.add_argument("--language", choices=list(LANGUAGE_INSTRUCTIONS.keys()), required=True)
    parser.add_argument("--deepinfra-model", default=None,
                         help="deepinfra only — defaults to room_kimi_gateway.DEEPINFRA_DEFAULT_MODEL")
    parser.add_argument("--risk-score", type=int, default=3)
    parser.add_argument("--repeats", type=int, default=5, help="--ticker only; ignored with --tickers-file")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--post-spacing", type=float, default=15.0)
    parser.add_argument("--allow-mock-market-data", action="store_true")
    args = parser.parse_args()
    if args.deepinfra_model is None:
        from room_kimi_gateway import DEEPINFRA_DEFAULT_MODEL
        args.deepinfra_model = DEEPINFRA_DEFAULT_MODEL
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
