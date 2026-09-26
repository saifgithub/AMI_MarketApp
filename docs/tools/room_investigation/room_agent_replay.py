#!/usr/bin/env python3
"""Replay ONE agent's EXACT captured prompt (system_prompt + messages,
pulled from llm_audit via a user_id — see room_llm_audit_trace.py) N times
direct to Kimi or vLLM, and report how many times each answer recurs —
generalizes `trader_replay_bac_r2_pass.py` (CR228, 2026-09) and RES009's
`ibm_run_a_t1_repeat10.py` (vLLM temperature-cascade repeat) into one tool.

## What this isolates

RES009 established that single-agent LLM calls are unstable on unpinned
sampling (docs/Research/RES009_room_llm_consistency/01-06). This tool asks a
narrower, useful follow-up: is a SPECIFIC observed disagreement (e.g. "why did
`trader` say WAIT in this run but BUY in that one") because the agent itself
is noisy on that input, or because the two runs actually gave it different
inputs upstream?

Concretely, in the BAC risk_score=2 investigation, this tool replayed both
PASS runs' exact `trader` prompts 5x each and got 5/5 WAIT and 5/5 BUY
respectively — PERFECTLY stable on each fixed input. That ruled out "trader
is noisy" and pointed the investigation at the upstream agent chain instead
(the news feed's ~5min cache had genuinely rolled over between the two
draws — see docs/Research/RES009_room_llm_consistency/07_cr228_bac_risk_score_instability.md).
Always run this BEFORE concluding an agent itself is unstable.

## Extracting a decision field from free-text output

Different agents put their decision in different shapes (`trader` has
`Side: BUY/WAIT/SELL`; `research_manager`/others have a `[STANCE: for/against/
neutral | CONVICTION: ...]` tag). Pass --extract-pattern with one capture
group if the built-in `Side:`/`STANCE:` patterns don't match your agent;
otherwise the tool tries both and reports whichever one matches.

## Usage

Kimi (thinking disabled), the default:
    export KIMI_API_KEY=...
    python3 room_agent_replay.py \\
        --system-prompt-file /tmp/trader_sysprompt_PASS_1.txt \\
        --messages-file /tmp/trader_messages_PASS_1.txt \\
        --repeats 5 --label "PASS_1 trader"

vLLM, optionally pinning temperature (RES009's temperature-cascade pattern —
start at 1.0, step down only if draws don't already agree):
    export VLLM_BASE_URL=http://192.168.20.74:8000   # LAN-direct from the Mac
    python3 room_agent_replay.py --provider vllm --temperature 0.6 \\
        --system-prompt-file ... --messages-file ... --repeats 10

Pull the prompt files first with room_llm_audit_trace.py:
    python3 room_llm_audit_trace.py get --user-id <uuid> --agent-id trader --field system_prompt > sysprompt.txt
    python3 room_llm_audit_trace.py get --user-id <uuid> --agent-id trader --field messages > messages.txt
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

import httpx

KIMI_BASE_URL = "https://api.moonshot.ai"
KIMI_MODEL = "kimi-k3"
_REASONING_TOKEN_TOLERANCE = 2  # RES009: kimi-k2.6 leaves ~1 residual even with thinking disabled

_SIDE_PATTERN = re.compile(r"Side:\s*([A-Z]+)")
_STANCE_PATTERN = re.compile(r"\[STANCE:\s*([^\|]+?)\s*\|", re.IGNORECASE)


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
    if reasoning_tokens and reasoning_tokens > _REASONING_TOKEN_TOLERANCE:
        raise RuntimeError(f"thinking not disabled: reasoning_tokens={reasoning_tokens}")
    return {"content": msg.get("content", ""), "reasoning_content": msg.get("reasoning_content")}


def _call_vllm(base_url: str, model: str, system_prompt: str, messages: list[dict], temperature: float | None) -> dict:
    """RES009 (01-06) established temperature/seed are otherwise unset
    everywhere in this codebase — pinning it here is deliberate and only for
    this replay tool, not a change to production request shape.
    """
    body: dict = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}, *messages],
        "max_tokens": 2000,
    }
    if temperature is not None:
        body["temperature"] = temperature
    resp = httpx.post(f"{base_url.rstrip('/')}/v1/chat/completions", json=body, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    msg = data["choices"][0]["message"]
    return {"content": msg.get("content", ""), "reasoning_content": None}


def _extract(text: str, pattern: re.Pattern | None) -> str | None:
    if pattern:
        m = pattern.search(text)
        return m.group(1).strip() if m else None
    m = _SIDE_PATTERN.search(text)
    if m:
        return m.group(1)
    m = _STANCE_PATTERN.search(text)
    if m:
        return m.group(1).strip()
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay an exact captured agent prompt N times, report answer distribution.")
    parser.add_argument("--provider", choices=["kimi", "vllm"], default="kimi")
    parser.add_argument("--system-prompt-file", type=Path, required=True)
    parser.add_argument("--messages-file", type=Path, required=True, help="JSON list of {role, content}")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--label", default="replay")
    parser.add_argument("--extract-pattern", default=None, help="regex with one capture group; default tries Side:/STANCE:")
    parser.add_argument("--out-file", type=Path, default=None)
    parser.add_argument("--temperature", type=float, default=None,
                         help="vLLM only — RES009: temperature/seed are otherwise unset everywhere in this codebase; "
                              "pinning here is deliberate, cascade from 1.0 down only if draws disagree")
    parser.add_argument("--vllm-base-url", default=os.environ.get("VLLM_BASE_URL", ""),
                         help="e.g. http://192.168.20.74:8000 (LAN-direct from the Mac)")
    parser.add_argument("--vllm-model", default=os.environ.get("VLLM_MODEL", "ami-llm"))
    args = parser.parse_args()

    if args.provider == "kimi":
        api_key = os.environ.get("KIMI_API_KEY")
        if not api_key:
            print("KIMI_API_KEY not set", file=sys.stderr)
            return 1
    else:
        if not args.vllm_base_url:
            print("--vllm-base-url or VLLM_BASE_URL not set", file=sys.stderr)
            return 1

    system_prompt = args.system_prompt_file.read_text()
    messages = json.loads(args.messages_file.read_text())
    pattern = re.compile(args.extract_pattern) if args.extract_pattern else None

    temp_note = f", T={args.temperature}" if args.provider == "vllm" and args.temperature is not None else ""
    print(f"=== {args.label} [{args.provider}{temp_note}] ({len(system_prompt)} char system_prompt) ===")
    draws = []
    for i in range(args.repeats):
        if args.provider == "kimi":
            out = _call_kimi(api_key, system_prompt, messages)
        else:
            out = _call_vllm(args.vllm_base_url, args.vllm_model, system_prompt, messages, args.temperature)
        extracted = _extract(out["content"], pattern)
        print(f"  draw {i + 1}/{args.repeats}: {extracted}")
        draws.append({"draw": i + 1, "extracted": extracted, "full_text": out["content"]})

    dist = Counter(d["extracted"] for d in draws)
    print(f"  distribution: {dict(dist)}")

    if args.out_file:
        args.out_file.parent.mkdir(parents=True, exist_ok=True)
        args.out_file.write_text(json.dumps({"label": args.label, "provider": args.provider, "draws": draws}, indent=2))
        print(f"  wrote {args.out_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
