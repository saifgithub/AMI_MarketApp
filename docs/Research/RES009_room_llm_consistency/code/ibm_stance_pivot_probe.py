#!/usr/bin/env python3
"""Ask the model directly: what would move you from NEUTRAL to FOR?

Follow-up to `ibm_run_a_t1_repeat10.py` / `ibm_kimi_repeat10.py`, which showed
both vLLM and Kimi split between FOR and NEUTRAL on the identical IBM
fundamentals_analyst prompt. This sends the real captured system prompt, the
real "Convene on IBM." user turn, one of the model's own captured NEUTRAL
completions as assistant history (so the follow-up reacts to what it ACTUALLY
said, not a hypothetical), then a new user turn asking it to name the
specific fact/threshold that would flip its own stance to FOR.

Runs against whichever provider is configured (--provider vllm|kimi). For
vllm: no temperature set (matches production default). For kimi: fixed at
0.6 (the only value this API key's models accept, verified live) and
thinking disabled via `thinking: {"type": "disabled"}`.

Usage (vLLM):
    python3 -m scripts.ibm_stance_pivot_probe --provider vllm \\
        --neutral-response-file /tmp/run_a_neutral_example.txt \\
        --user-id 8f1e288a-b288-4b9e-942f-2003b88ba555 \\
        --since 2026-09-25T17:02:00+00:00 --until 2026-09-25T17:10:00+00:00 \\
        --out /tmp/ibm_pivot_probe_a_vllm.json

Usage (Kimi, on the Mac, tunnel to melehost DB already open):
    export KIMI_API_KEY=... DB_PASSWORD=...
    python3 backend/scripts/ibm_stance_pivot_probe.py --provider kimi ...
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FOLLOW_UP_QUESTION = (
    "Setting aside what you just wrote — answer this directly, as a distinct "
    "question, not a restatement of your analysis above.\n\n"
    "You just took a NEUTRAL stance. Name the SINGLE most decision-relevant "
    "fact on the sheet above that, if it were meaningfully different (state "
    "the direction and an approximate threshold), would move you from "
    "NEUTRAL to FOR. Do not name a fact that is already favorable in the "
    "sheet as-is — name what is currently working AGAINST a FOR stance, and "
    "the change that would flip it. One fact, one threshold, 2-3 sentences "
    "maximum. Do not repeat your GAPS line or your STANCE/CONVICTION/HEADLINE "
    "tag."
)


def _get_pg_dsn(host: str, port: str, password: str) -> str:
    return f"host={host} port={port} dbname=ami_trade user=postgres password={password}"


def _from_db_pg(dsn: str, user_id: str, since: str, until: str, agent_needle: str) -> dict | None:
    import psycopg2
    import psycopg2.extras

    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, agent_id, tier, created_at, system_prompt, messages, response_text
                FROM llm_audit
                WHERE user_id = %s AND created_at >= %s AND created_at <= %s
                  AND agent_id ILIKE %s
                ORDER BY created_at
                LIMIT 1
                """,
                (user_id, since, until, f"%{agent_needle}%"),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return {
                "id": str(row["id"]), "tier": row["tier"], "created_at": str(row["created_at"]),
                "system_prompt": row["system_prompt"], "messages": row["messages"],
                "original_response": row["response_text"],
            }
    finally:
        conn.close()


def _extract_stance(text: str | None) -> str | None:
    if not text:
        return None
    m = re.search(r"STANCE:\s*([a-zA-Z]+)", text)
    return m.group(1).upper() if m else None


def _call_vllm(base_url: str, model: str, openai_messages: list, max_tokens: int = 800) -> str:
    body = {"model": model, "messages": openai_messages, "max_tokens": max_tokens, "stream": False}
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=120.0) as client:
        resp = client.post("/v1/chat/completions", json=body)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


def _call_kimi(api_key: str, openai_messages: list, max_tokens: int = 800) -> str:
    body = {
        "model": "kimi-k3", "messages": openai_messages, "max_tokens": max_tokens,
        "temperature": 0.6, "stream": False, "thinking": {"type": "disabled"},
    }
    resp = httpx.post(
        "https://api.moonshot.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=body, timeout=120.0,
    )
    resp.raise_for_status()
    data = resp.json()
    msg = data["choices"][0]["message"]
    reasoning_tokens = data.get("usage", {}).get("completion_tokens_details", {}).get("reasoning_tokens") or 0
    if reasoning_tokens > 2 or (msg.get("reasoning_content") or "").strip():
        raise RuntimeError(f"thinking was not disabled (reasoning_tokens={reasoning_tokens})")
    return msg.get("content", "")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=["vllm", "kimi"], required=True)
    ap.add_argument("--user-id", required=True)
    ap.add_argument("--since", required=True)
    ap.add_argument("--until", required=True)
    ap.add_argument("--agent-needle", default="fundamentals_analyst")
    ap.add_argument("--neutral-response-text", default=None,
                     help="a NEUTRAL completion to seed as assistant history; "
                          "defaults to the original captured response if it was NEUTRAL, "
                          "else this is required")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--vllm-base-url", default=os.environ.get("VLLM_BASE_URL", "http://192.168.20.74:8000"))
    ap.add_argument("--vllm-model", default=os.environ.get("VLLM_MODEL", "ami-llm"))
    ap.add_argument("--db-host", default="127.0.0.1")
    ap.add_argument("--db-port", default="5434")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    db_password = os.environ.get("DB_PASSWORD")
    if not db_password:
        raise SystemExit("DB_PASSWORD not set")
    dsn = _get_pg_dsn(args.db_host, args.db_port, db_password)

    row = _from_db_pg(dsn, args.user_id, args.since, args.until, args.agent_needle)
    if row is None:
        raise SystemExit(f"no captured row found for user {args.user_id}")

    neutral_text = args.neutral_response_text
    if neutral_text is None:
        if _extract_stance(row["original_response"]) == "NEUTRAL":
            neutral_text = row["original_response"]
        else:
            raise SystemExit(
                "original captured response was not NEUTRAL and no "
                "--neutral-response-text was given — pass one explicitly"
            )

    openai_messages = [{"role": "system", "content": row["system_prompt"]}]
    for m in row["messages"] or []:
        openai_messages.append({"role": m.get("role", "user"), "content": m.get("content", "")})
    openai_messages.append({"role": "assistant", "content": neutral_text})
    openai_messages.append({"role": "user", "content": FOLLOW_UP_QUESTION})

    api_key = os.environ.get("KIMI_API_KEY") if args.provider == "kimi" else None
    if args.provider == "kimi" and not api_key:
        raise SystemExit("KIMI_API_KEY not set")

    print(f"Captured row: {row['id']} tier={row['tier']} at {row['created_at']}")
    print(f"Seeding assistant turn: {neutral_text[:100]}...")
    print(f"Asking {args.repeats}x via {args.provider}: what would flip NEUTRAL -> FOR?\n")

    answers = []
    for i in range(args.repeats):
        try:
            if args.provider == "vllm":
                text = _call_vllm(args.vllm_base_url, args.vllm_model, openai_messages)
            else:
                text = _call_kimi(api_key, openai_messages)
            answers.append({"n": i + 1, "text": text, "error": None})
            print(f"--- #{i+1} ---\n{text}\n")
        except Exception as exc:  # noqa: BLE001
            answers.append({"n": i + 1, "text": None, "error": str(exc)})
            print(f"--- #{i+1} ERROR: {exc} ---\n")

    out = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "provider": args.provider,
        "audit_row_id": row["id"], "tier": row["tier"],
        "seed_neutral_response": neutral_text,
        "follow_up_question": FOLLOW_UP_QUESTION,
        "answers": answers,
    }
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
