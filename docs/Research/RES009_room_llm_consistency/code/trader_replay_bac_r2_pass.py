#!/usr/bin/env python3
"""Replay the `trader` agent's EXACT captured prompt from each of the two
risk_score=2 BAC PASS runs, 5x each, direct to Kimi (kimi-k3, thinking
disabled) — no Room, no RoomRunner, just the raw system_prompt + messages
already captured in llm_audit, resent verbatim.

Purpose: isolate whether `trader` itself is unstable on a FIXED input, same
question RES009's 05/06 already asked of a single agent call, applied here
to the specific prompts that produced this session's two anomalous PASS
draws (docs/Research/RES009_room_llm_consistency/07_cr228_bac_risk_score_instability.md).

Usage:
    export KIMI_API_KEY=...   # Mac's Open Platform key
    python3 trader_replay_bac_r2_pass.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

import httpx

KIMI_BASE_URL = "https://api.moonshot.ai"
KIMI_MODEL = "kimi-k3"
N_REPEATS = 5

PROMPT_DIR = Path("/tmp/bac_pattern")  # captured system_prompt/messages, this session
OUT_PATH = Path(__file__).resolve().parents[1] / "out" / "09_trader_replay_bac_r2_pass.json"


def _load(label: str) -> tuple[str, list[dict]]:
    sys_prompt = (PROMPT_DIR / f"trader_sysprompt_{label}.txt").read_text()
    messages = json.loads((PROMPT_DIR / f"trader_messages_{label}.txt").read_text())
    return sys_prompt, messages


def _call_kimi(api_key: str, system_prompt: str, messages: list[dict]) -> dict:
    resp = httpx.post(
        f"{KIMI_BASE_URL}/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": KIMI_MODEL,
            "messages": [{"role": "system", "content": system_prompt}, *messages],
            "max_tokens": 2000,
            "thinking": {"type": "disabled"},
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    usage = data.get("usage", {})
    reasoning_tokens = usage.get("completion_tokens_details", {}).get("reasoning_tokens")
    msg = data["choices"][0]["message"]
    if reasoning_tokens and reasoning_tokens > 2:  # RES009's _REASONING_TOKEN_TOLERANCE
        raise RuntimeError(f"thinking not disabled: reasoning_tokens={reasoning_tokens}")
    return {"content": msg.get("content", ""), "reasoning_content": msg.get("reasoning_content")}


def _extract_side(text: str) -> str | None:
    m = re.search(r"Side:\s*([A-Z]+)", text)
    return m.group(1) if m else None


def main() -> int:
    api_key = os.environ.get("KIMI_API_KEY")
    if not api_key:
        print("KIMI_API_KEY not set", file=sys.stderr)
        return 1

    results: dict[str, list[dict]] = {}
    for label in ("PASS_1", "PASS_2"):
        sys_prompt, messages = _load(label)
        print(f"=== {label} ({len(sys_prompt)} char system_prompt) ===")
        draws = []
        for i in range(N_REPEATS):
            out = _call_kimi(api_key, sys_prompt, messages)
            side = _extract_side(out["content"])
            print(f"  draw {i + 1}/{N_REPEATS}: Side={side}")
            draws.append({"draw": i + 1, "side": side, "full_text": out["content"]})
        results[label] = draws
        dist = Counter(d["side"] for d in draws)
        print(f"  distribution: {dict(dist)}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(results, indent=2))
    print(f"\nwrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
