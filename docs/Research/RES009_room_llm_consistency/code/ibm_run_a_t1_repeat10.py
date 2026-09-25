#!/usr/bin/env python3
"""A captured (Run A's or Run B's) fundamentals_analyst prompt, sent 10 times at
one explicit temperature (default 1.0, override via SWEEP_TEMPERATURE env var).

Follow-up to `ibm_room_divergence_probe.py` and `ibm_temperature_sweep.py`. Those
showed a single same-prompt replay at unset (vLLM default) temperature flipped
STANCE from "for" to "neutral". This isolates one temperature at a time and asks
the direct question: at that sampling setting, how much does the SAME prompt
actually vary across repeated draws? Intended to be run in a temperature
cascade per run (1.0, 0.8, 0.6, 0.4, 0.2 — stop once all 10 draws agree), once
per user (Run A, Run B), so the two runs' stability can be compared directly.

Must run where `DATABASE_URL` points at melehost's Postgres.

Usage:
    SWEEP_TEMPERATURE=0.6 python3 -m scripts.ibm_run_a_t1_repeat10 \\
        --user-id 8f1e288a-b288-4b9e-942f-2003b88ba555 \\
        --since 2026-09-25T17:02:00+00:00 \\
        --until 2026-09-25T17:10:00+00:00 \\
        --out /tmp/ibm_run_a_t06_repeat10.json
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

TEMPERATURE = float(os.environ.get("SWEEP_TEMPERATURE", "1.0"))
N_REPEATS = 10


def _from_db(user_a: str, since: str, until: str, agent_needle: str) -> dict | None:
    from sqlalchemy import select

    from app.db.models import LLMAuditRow
    from app.db.session import get_session

    with get_session() as s:
        q = (
            select(LLMAuditRow)
            .where(LLMAuditRow.user_id == user_a)
            .where(LLMAuditRow.created_at >= since)
            .where(LLMAuditRow.created_at <= until)
            .where(LLMAuditRow.agent_id.ilike(f"%{agent_needle}%"))
            .order_by(LLMAuditRow.created_at)
        )
        row = s.execute(q).scalars().first()
        if row is None:
            return None
        return {
            "id": str(row.id), "agent_id": row.agent_id, "tier": row.tier,
            "created_at": str(row.created_at),
            "system_prompt": row.system_prompt, "messages": row.messages,
            "original_response": row.response_text,
        }


def _extract_stance(text: str | None) -> str | None:
    if not text:
        return None
    m = re.search(r"STANCE:\s*([a-zA-Z]+)", text)
    return m.group(1).upper() if m else None


def _extract_conviction(text: str | None) -> str | None:
    if not text:
        return None
    m = re.search(r"CONVICTION:\s*([a-zA-Z]+)", text)
    return m.group(1).upper() if m else None


def _extract_headline(text: str | None) -> str | None:
    if not text:
        return None
    m = re.search(r"HEADLINE:\s*([^\]]+)\]", text)
    return m.group(1).strip() if m else None


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
    ap.add_argument("--user-id", required=True, help="Run A's or Run B's user_id")
    ap.add_argument("--since", required=True)
    ap.add_argument("--until", required=True)
    ap.add_argument("--agent-needle", default="fundamentals_analyst")
    ap.add_argument("--vllm-base-url", default=os.environ.get("VLLM_BASE_URL", "http://192.168.20.74:8000"))
    ap.add_argument("--vllm-model", default=os.environ.get("VLLM_MODEL", "ami-llm"))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    row = _from_db(args.user_id, args.since, args.until, args.agent_needle)
    if row is None:
        raise SystemExit(f"no captured row found for user {args.user_id}")

    print(f"Captured row: {row['id']} tier={row['tier']} at {row['created_at']}")
    print(f"Original: STANCE={_extract_stance(row['original_response'])} "
          f"CONVICTION={_extract_conviction(row['original_response'])} "
          f"HEADLINE={_extract_headline(row['original_response'])}")
    print(f"Sending {N_REPEATS} completions at T={TEMPERATURE}...")

    completions = await asyncio.gather(*[
        _call(args.vllm_base_url, args.vllm_model, row["system_prompt"], row["messages"], TEMPERATURE)
        for _ in range(N_REPEATS)
    ])

    results = []
    for i, text in enumerate(completions):
        stance = _extract_stance(text)
        conviction = _extract_conviction(text)
        headline = _extract_headline(text)
        results.append({"n": i + 1, "stance": stance, "conviction": conviction,
                         "headline": headline, "text": text})
        print(f"  #{i+1}: STANCE={stance} CONVICTION={conviction} HEADLINE={headline}")

    stances = [r["stance"] for r in results]
    unique_stances = sorted(set(s for s in stances if s))
    print(f"\nDistinct stances across {N_REPEATS} draws: {unique_stances}")
    print(f"Distribution: {{{', '.join(f'{s}: {stances.count(s)}' for s in unique_stances)}}}")

    out = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "temperature": TEMPERATURE,
        "n_repeats": N_REPEATS,
        "audit_row_id": row["id"], "tier": row["tier"], "created_at": row["created_at"],
        "original_response": row["original_response"],
        "original_stance": _extract_stance(row["original_response"]),
        "completions": results,
        "stance_distribution": {s: stances.count(s) for s in unique_stances},
    }
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    asyncio.run(main())
