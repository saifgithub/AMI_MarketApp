"""LLM smoke test — pings each tier with a trivial prompt and prints the reply.

Use after dropping ANTHROPIC_API_KEY into backend/.env to confirm the live
flip worked end-to-end before exercising the app. Exits non-zero if any
tier fails so it can be wired into a deploy gate.

Usage (from backend/):
    .venv/bin/python -m scripts.llm_smoke              # ping all three tiers
    .venv/bin/python -m scripts.llm_smoke cheap        # ping just one tier
    .venv/bin/python -m scripts.llm_smoke --quiet      # one-line PASS/FAIL

Designed to be safe to run repeatedly — uses max_tokens=64 so each ping
costs a fraction of a cent.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.services.llm_gateway import ChatMessage, ModelTier, get_llm_gateway

_PING_SYSTEM = (
    "You are a one-word smoke test. Reply with the single word PONG. "
    "Do not add punctuation, emoji, or explanation."
)
_PING_USER = "ping"


async def _ping(tier: ModelTier) -> tuple[bool, str]:
    gateway = get_llm_gateway()
    buf: list[str] = []
    try:
        async for chunk in gateway.stream_chat(
            system_prompt=_PING_SYSTEM,
            messages=[ChatMessage(role="user", content=_PING_USER)],
            model_tier=tier,
            max_tokens=64,
        ):
            buf.append(chunk)
    except Exception as exc:  # noqa: BLE001 — surface everything to the user
        return False, f"exception: {exc!r}"
    text = "".join(buf).strip()
    if not text:
        return False, "empty response"
    return True, text


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Ping each LLM tier.")
    parser.add_argument(
        "tier",
        nargs="?",
        choices=["cheap", "mid", "premium", "all"],
        default="all",
        help="Which tier(s) to ping. Default: all.",
    )
    parser.add_argument("--quiet", action="store_true", help="One-line PASS/FAIL only.")
    args = parser.parse_args()

    gateway = get_llm_gateway()
    status = gateway.status()
    tiers: list[ModelTier] = (
        ["cheap", "mid", "premium"] if args.tier == "all" else [args.tier]
    )

    if not args.quiet:
        print(f"active provider: {status['active_provider']}")
        print(f"tier_to_model:   {status['tier_to_model']}")
        if not status["has_real_provider"]:
            print("note: no real provider registered — pinging the mock.")
        print()

    failures: list[str] = []
    for tier in tiers:
        ok, body = await _ping(tier)
        flag = "PASS" if ok else "FAIL"
        line = f"  [{flag}] tier={tier:7s} model={status['tier_to_model'][tier]:25s} reply={body[:80]!r}"
        if not args.quiet:
            print(line)
        if not ok:
            failures.append(tier)

    if args.quiet:
        if failures:
            print(f"FAIL ({','.join(failures)})")
        else:
            print(f"PASS ({','.join(tiers)})")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
