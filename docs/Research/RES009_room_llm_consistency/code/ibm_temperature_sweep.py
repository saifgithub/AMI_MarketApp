#!/usr/bin/env python3
"""Temperature sweep on the two captured 2026-09-25 IBM Room prompts.

Follow-up to `ibm_room_divergence_probe.py`. That script showed the two IBM
runs' divergence is mostly explained by per-user context (mandate, portfolio)
plus unpinned sampling — a same-prompt replay of Run A's fundamentals_analyst
call flipped STANCE from "for" to "neutral" with zero temperature control.

This script quantifies that: for each of Run A's and Run B's captured
(system_prompt, messages) for a given agent, it re-sends the SAME prompt to
vLLM once per temperature in {0.2, 0.4, 0.6, 0.8, 1.0}, so the impact of
temperature itself (not prompt content) is visible directly.

vLLM's OpenAI-compatible endpoint accepts `temperature` in the request body;
production's `OpenAICompatibleProvider.stream_chat` (llm_gateway.py) never
sets it, so this script is the first place in this codebase that does.

Must run where `DATABASE_URL` points at melehost's Postgres (see
ibm_room_divergence_probe.py's docstring for why).

Usage:
    python3 -m scripts.ibm_temperature_sweep \\
        --user-a 8f1e288a-b288-4b9e-942f-2003b88ba555 \\
        --user-b d00000f5-c311-4f4e-b94f-cc1b56cdedbc \\
        --since 2026-09-25T17:02:00+00:00 \\
        --until 2026-09-25T17:10:00+00:00 \\
        --agent-needle fundamentals_analyst \\
        --out /tmp/ibm_temperature_sweep.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx  # noqa: E402

TEMPERATURES = [0.2, 0.4, 0.6, 0.8, 1.0]


def _from_db(user_a: str, user_b: str, since: str, until: str, agent_needle: str) -> dict:
    from sqlalchemy import select

    from app.db.models import LLMAuditRow
    from app.db.session import get_session

    out = {}
    with get_session() as s:
        for label, uid in (("A", user_a), ("B", user_b)):
            q = (
                select(LLMAuditRow)
                .where(LLMAuditRow.user_id == uid)
                .where(LLMAuditRow.created_at >= since)
                .where(LLMAuditRow.created_at <= until)
                .where(LLMAuditRow.agent_id.ilike(f"%{agent_needle}%"))
                .order_by(LLMAuditRow.created_at)
            )
            row = s.execute(q).scalars().first()
            if row is None:
                out[label] = None
                continue
            out[label] = {
                "id": str(row.id), "agent_id": row.agent_id, "tier": row.tier,
                "created_at": str(row.created_at),
                "system_prompt": row.system_prompt, "messages": row.messages,
                "original_response": row.response_text,
            }
    return out


def _extract_stance(text: str | None) -> str | None:
    if not text:
        return None
    m = re.search(r"STANCE:\s*([a-zA-Z]+)", text)
    return m.group(1).upper() if m else None


async def _call(base_url: str, model: str, system_prompt: str, messages: list,
                 temperature: float, max_tokens: int = 1500) -> str:
    openai_messages = [{"role": "system", "content": system_prompt}]
    for m in messages or []:
        openai_messages.append({"role": m.get("role", "user"), "content": m.get("content", "")})
    body = {
        "model": model,
        "messages": openai_messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }
    async with httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=120.0) as client:
        resp = await client.post("/v1/chat/completions", json=body)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user-a", required=True)
    ap.add_argument("--user-b", required=True)
    ap.add_argument("--since", required=True)
    ap.add_argument("--until", required=True)
    ap.add_argument("--agent-needle", default="fundamentals_analyst")
    ap.add_argument("--repeats", type=int, default=1,
                     help="completions per temperature per run, for variance within a temperature")
    ap.add_argument("--vllm-base-url", default=os.environ.get("VLLM_BASE_URL", "http://192.168.20.74:8000"))
    ap.add_argument("--vllm-model", default=os.environ.get("VLLM_MODEL", "ami-llm"))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    captured = _from_db(args.user_a, args.user_b, args.since, args.until, args.agent_needle)

    result = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "agent_needle": args.agent_needle,
        "temperatures": TEMPERATURES,
        "repeats": args.repeats,
        "runs": {},
    }

    for label in ("A", "B"):
        row = captured[label]
        if row is None:
            result["runs"][label] = {"error": f"no captured row found for user {label}"}
            continue

        original_stance = _extract_stance(row["original_response"])
        sweep = []
        for temp in TEMPERATURES:
            completions = await asyncio.gather(*[
                _call(args.vllm_base_url, args.vllm_model, row["system_prompt"], row["messages"], temp)
                for _ in range(args.repeats)
            ])
            sweep.append({
                "temperature": temp,
                "completions": [
                    {"text": c, "stance": _extract_stance(c)} for c in completions
                ],
            })
            print(f"Run {label} @ T={temp}: stances = "
                  f"{[_extract_stance(c) for c in completions]}")

        result["runs"][label] = {
            "audit_row_id": row["id"], "tier": row["tier"], "created_at": row["created_at"],
            "original_stance": original_stance,
            "original_response": row["original_response"],
            "sweep": sweep,
        }

    with open(args.out, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    asyncio.run(main())
