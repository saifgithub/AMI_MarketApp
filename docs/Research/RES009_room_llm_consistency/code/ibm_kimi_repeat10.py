#!/usr/bin/env python3
"""A captured (Run A's or Run B's) fundamentals_analyst prompt, sent 10 times
to Kimi (Moonshot's Coding Plan API), thinking DISABLED, at one explicit
temperature — the Kimi equivalent of `ibm_run_a_t1_repeat10.py`'s vLLM cascade.

Runs on the MAC, not melehost — this uses the Kimi key set in the Mac's own
`.env`. Confirmed live (2026-09-25) that this is a Moonshot OPEN PLATFORM key
(`api.moonshot.ai`, prefix `sk-ZJutc...`), NOT melehost's `KIMI_API_KEY` (Kimi
CODING PLAN, `api.kimi.com/coding`, prefix `sk-kimi-...`, a different product
with a different model-id namespace) — melehost's key must never be reused
here, and Saiful confirmed the Mac key is not a Coding Plan key. Model
defaults to `kimi-k3`, the only one of the 4 available Open Platform models
(`kimi-k2.6`, `kimi-k2.7-code`, `kimi-k2.7-code-highspeed`, `kimi-k3`) that
genuinely zeroes `reasoning_content`/`reasoning_tokens` when thinking is
disabled (verified live) — `kimi-k2.7-code*` 400s on this key entirely (Coding
Plan namespace), `kimi-k2.6` left a 1-token reasoning residue even disabled.
melehost's Postgres is loopback-only (127.0.0.1:5434 on melehost itself), so
this script expects an SSH tunnel already open:
`ssh -f -N -L 5434:127.0.0.1:5434 melehost`.

Every model here is `supports_reasoning: true` (Moonshot's own `/v1/models`).
Turning thinking off needs `"thinking": {"type": "disabled"}` in the request
body — verified live against 4 candidate parameter shapes; the others
(`no_thinking`, `enable_thinking`, `thinking: false`) either silently kept
reasoning on or errored outright. This script asserts `reasoning_tokens` is
at most 2 (a documented near-zero residue on some models, not a real
chain-of-thought) on every completion, so a silent thinking-still-on failure
is never mistaken for a clean non-thinking run.

Usage:
    export $(grep -v '^#' .env | grep KIMI_API_KEY)
    export DB_PASSWORD=<melehost's POSTGRES_PASSWORD>
    python3 backend/scripts/ibm_kimi_repeat10.py \\
        --user-id 8f1e288a-b288-4b9e-942f-2003b88ba555 \\
        --since 2026-09-25T17:02:00+00:00 \\
        --until 2026-09-25T17:10:00+00:00 \\
        --temperature 1.0 \\
        --out /tmp/ibm_run_a_kimi_t1_repeat10.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

import httpx
import psycopg2
import psycopg2.extras

N_REPEATS = 10
KIMI_BASE_URL = "https://api.moonshot.ai"
KIMI_MODEL = "kimi-k3"
# kimi-k2.6 leaves ~1 residual reasoning_token even with thinking disabled
# (verified live) — a real API quirk, not a sign thinking stayed on.
_REASONING_TOKEN_TOLERANCE = 2
# Verified live (2026-09-25): every model on this key 400s
# ("invalid temperature: only 0.6 is allowed for this model") on any
# temperature other than 0.6 — a server-side lock, not a request-shape bug.
# No sweep is possible; this is the one value Kimi will accept here.
FIXED_TEMPERATURE = 0.6


def _from_db(dsn: str, user_id: str, since: str, until: str, agent_needle: str) -> dict | None:
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
                "id": str(row["id"]), "agent_id": row["agent_id"], "tier": row["tier"],
                "created_at": str(row["created_at"]),
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


def _call_kimi(api_key: str, system_prompt: str, messages: list, temperature: float,
                max_tokens: int = 4000) -> dict:
    """Returns {"content": ..., "reasoning_content": ..., "reasoning_tokens": ...}.
    Raises if the server did not actually honor thinking-disabled (a silent
    thinking-still-on result would corrupt every stance comparison downstream).
    """
    openai_messages = [{"role": "system", "content": system_prompt}]
    for m in messages or []:
        openai_messages.append({"role": m.get("role", "user"), "content": m.get("content", "")})
    body = {
        "model": KIMI_MODEL,
        "messages": openai_messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
        "thinking": {"type": "disabled"},
    }
    resp = httpx.post(
        f"{KIMI_BASE_URL}/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=body, timeout=120.0,
    )
    resp.raise_for_status()
    data = resp.json()
    msg = data["choices"][0]["message"]
    reasoning_tokens = data.get("usage", {}).get("completion_tokens_details", {}).get("reasoning_tokens") or 0
    reasoning_content = (msg.get("reasoning_content") or "").strip()
    if reasoning_tokens > _REASONING_TOKEN_TOLERANCE or reasoning_content:
        raise RuntimeError(
            f"thinking was NOT disabled (reasoning_tokens={reasoning_tokens}, "
            f"reasoning_content={'present' if reasoning_content else 'absent'}) — "
            f"the 'thinking: disabled' request param did not take effect this call"
        )
    return {"content": msg.get("content", ""), "reasoning_tokens": reasoning_tokens}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user-id", required=True)
    ap.add_argument("--since", required=True)
    ap.add_argument("--until", required=True)
    ap.add_argument("--agent-needle", default="fundamentals_analyst")
    ap.add_argument("--temperature", type=float, default=FIXED_TEMPERATURE,
                     help=f"Kimi only accepts {FIXED_TEMPERATURE} on this key (verified live) — "
                          f"passing anything else will 400")
    ap.add_argument("--db-host", default="127.0.0.1")
    ap.add_argument("--db-port", default="5434")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    api_key = os.environ.get("KIMI_API_KEY")
    if not api_key:
        raise SystemExit("KIMI_API_KEY not set in environment (source the Mac .env first)")
    db_password = os.environ.get("DB_PASSWORD")
    if not db_password:
        raise SystemExit("DB_PASSWORD not set in environment")

    dsn = (f"host={args.db_host} port={args.db_port} dbname=ami_trade "
           f"user=postgres password={db_password}")

    row = _from_db(dsn, args.user_id, args.since, args.until, args.agent_needle)
    if row is None:
        raise SystemExit(f"no captured row found for user {args.user_id}")

    print(f"Captured row: {row['id']} tier={row['tier']} at {row['created_at']}")
    print(f"Original (vLLM): STANCE={_extract_stance(row['original_response'])} "
          f"CONVICTION={_extract_conviction(row['original_response'])} "
          f"HEADLINE={_extract_headline(row['original_response'])}")
    print(f"Sending {N_REPEATS} completions to Kimi ({KIMI_MODEL}, thinking disabled) "
          f"at T={args.temperature}...")

    results = []
    for i in range(N_REPEATS):
        try:
            out = _call_kimi(api_key, row["system_prompt"], row["messages"], args.temperature)
            text = out["content"]
            stance = _extract_stance(text)
            conviction = _extract_conviction(text)
            headline = _extract_headline(text)
            results.append({"n": i + 1, "stance": stance, "conviction": conviction,
                             "headline": headline, "text": text, "error": None})
            print(f"  #{i+1}: STANCE={stance} CONVICTION={conviction} HEADLINE={headline}")
        except Exception as exc:  # noqa: BLE001 — record and continue, report at the end
            results.append({"n": i + 1, "stance": None, "conviction": None,
                             "headline": None, "text": None, "error": str(exc)})
            print(f"  #{i+1}: ERROR {exc}")

    errors = [r for r in results if r["error"]]
    stances = [r["stance"] for r in results if not r["error"]]
    unique_stances = sorted(set(s for s in stances if s))
    print(f"\nErrors: {len(errors)}/{N_REPEATS}")
    print(f"Distinct stances across {len(stances)} successful draws: {unique_stances}")
    if unique_stances:
        print(f"Distribution: {{{', '.join(f'{s}: {stances.count(s)}' for s in unique_stances)}}}")

    out = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "provider": "kimi", "model": KIMI_MODEL, "thinking": "disabled",
        "temperature": args.temperature,
        "n_repeats": N_REPEATS,
        "audit_row_id": row["id"], "tier": row["tier"], "created_at": row["created_at"],
        "original_response_vllm": row["original_response"],
        "original_stance_vllm": _extract_stance(row["original_response"]),
        "completions": results,
        "stance_distribution": {s: stances.count(s) for s in unique_stances},
        "error_count": len(errors),
    }
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
