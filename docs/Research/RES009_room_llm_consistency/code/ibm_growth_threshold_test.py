#!/usr/bin/env python3
"""Test the claimed pivot fact directly: patch `TTM revenue growth: 1%` in the
real captured IBM fact sheet to 2%, 3%, 4%, 5% (one value at a time) and ask
the fundamentals_analyst question cold — not a follow-up, a fresh convene —
to see whether STANCE actually moves to FOR at the threshold both Kimi and
vLLM named unprompted (`ibm_stance_pivot_probe.py`'s "~5%" finding).

Only the single line `TTM revenue growth: 1%` is substituted (exact text
match against the real captured system_prompt); everything else — PEG,
P/E, margins, price, all narrative fields — is left exactly as captured, so
this isolates revenue growth as the one changed variable. PEG is NOT
recomputed: it's sourced directly from the market-data provider's own
`trailingPegRatio`/`pegRatio` field in `fundamentals.py` (forward EARNINGS
growth basis, not TTM REVENUE growth) — a different underlying metric, not
mechanically derived from the revenue-growth number this script changes, so
leaving it untouched does not introduce an internal inconsistency.

Cascade per Saiful's instruction: try Kimi first, at each growth value send
10 completions UNLESS stance is already consistent (10/10 agree) at a lower
repeat count — mirrors `ibm_run_a_t1_repeat10.py`'s temperature cascade,
applied to growth value instead of temperature. Kimi: T=0.6 (only value this
key accepts, verified live), thinking disabled. vLLM: no temperature set
(matches production default).

Usage (Kimi, on the Mac, DB tunnel open):
    export KIMI_API_KEY=... DB_PASSWORD=...
    python3 backend/scripts/ibm_growth_threshold_test.py \\
        --provider kimi --user-id <uuid> \\
        --since ... --until ... --growth-values 2,3,4,5 \\
        --out /tmp/ibm_growth_test_a_kimi.json
"""
from __future__ import annotations

import argparse
import functools
import json
import os
import re
import sys
from datetime import datetime, timezone

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Long batches (up to 40 sequential API calls) need visible interim progress —
# a piped/backgrounded stdout buffers by default and prints nothing until
# the process exits, which makes a multi-minute run look silently stuck.
print = functools.partial(print, flush=True)  # noqa: A001 — intentional shadow, this file only

ORIGINAL_LINE = "TTM revenue growth: 1%"


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
                SELECT id, tier, created_at, system_prompt, messages
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
            }
    finally:
        conn.close()


def _patch_growth(system_prompt: str, growth_pct: int) -> str:
    new_line = f"TTM revenue growth: {growth_pct}%"
    count = system_prompt.count(ORIGINAL_LINE)
    if count != 1:
        raise RuntimeError(
            f"expected exactly 1 occurrence of {ORIGINAL_LINE!r}, found {count} — "
            f"refusing to substitute blindly (the fact sheet format may have "
            f"changed, or this isn't the captured row we think it is)"
        )
    return system_prompt.replace(ORIGINAL_LINE, new_line)


def _extract_stance(text: str | None) -> str | None:
    if not text:
        return None
    m = re.search(r"STANCE:\s*([a-zA-Z]+)", text)
    return m.group(1).upper() if m else None


def _extract_headline(text: str | None) -> str | None:
    if not text:
        return None
    m = re.search(r"HEADLINE:\s*([^\]]+)\]", text)
    return m.group(1).strip() if m else None


def _call_vllm(base_url: str, model: str, system_prompt: str, messages: list, max_tokens: int = 800) -> str:
    openai_messages = [{"role": "system", "content": system_prompt}]
    for m in messages or []:
        openai_messages.append({"role": m.get("role", "user"), "content": m.get("content", "")})
    body = {"model": model, "messages": openai_messages, "max_tokens": max_tokens, "stream": False}
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=120.0) as client:
        resp = client.post("/v1/chat/completions", json=body)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


def _call_kimi(api_key: str, system_prompt: str, messages: list, max_tokens: int = 800) -> str:
    openai_messages = [{"role": "system", "content": system_prompt}]
    for m in messages or []:
        openai_messages.append({"role": m.get("role", "user"), "content": m.get("content", "")})
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
    ap.add_argument("--growth-values", default="2,3,4,5")
    ap.add_argument("--max-repeats", type=int, default=10)
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

    api_key = os.environ.get("KIMI_API_KEY") if args.provider == "kimi" else None
    if args.provider == "kimi" and not api_key:
        raise SystemExit("KIMI_API_KEY not set")

    growth_values = [int(v) for v in args.growth_values.split(",")]
    print(f"Captured row: {row['id']} tier={row['tier']} at {row['created_at']}")
    print(f"Testing growth values {growth_values} via {args.provider}, "
          f"up to {args.max_repeats}x each, stopping early once 10/10 agree\n")

    results = {}
    for growth in growth_values:
        patched_prompt = _patch_growth(row["system_prompt"], growth)
        print(f"=== TTM revenue growth = {growth}% ===")
        draws = []
        for i in range(args.max_repeats):
            try:
                if args.provider == "vllm":
                    text = _call_vllm(args.vllm_base_url, args.vllm_model, patched_prompt, row["messages"])
                else:
                    text = _call_kimi(api_key, patched_prompt, row["messages"])
                stance = _extract_stance(text)
                headline = _extract_headline(text)
                draws.append({"n": i + 1, "stance": stance, "headline": headline, "text": text, "error": None})
                print(f"  #{i+1}: STANCE={stance} HEADLINE={headline}")
            except Exception as exc:  # noqa: BLE001
                draws.append({"n": i + 1, "stance": None, "headline": None, "text": None, "error": str(exc)})
                print(f"  #{i+1}: ERROR {exc}")

            # Early stop: once every draw so far agrees (no errors mixed in)
            # and we've done at least half of max_repeats, Kimi/vLLM is
            # "consistent" at this growth value — no need to burn the rest
            # of the budget. A single-draw "consistency" isn't meaningful,
            # so the minimum sample before stopping early is max_repeats//2.
            stances_so_far = [d["stance"] for d in draws]
            all_no_error = all(d["error"] is None for d in draws)
            min_before_early_stop = max(1, args.max_repeats // 2)
            if (all_no_error and len(stances_so_far) >= min_before_early_stop
                    and len(set(stances_so_far)) == 1):
                print(f"  (consistent after {i + 1} draws — stopping early)")
                break

        stances = [d["stance"] for d in draws if d["stance"]]
        unique = sorted(set(stances))
        dist = {s: stances.count(s) for s in unique}
        print(f"  -> {len(draws)} draws, distribution: {dist}\n")
        results[growth] = {"draws": draws, "distribution": dist, "n_draws": len(draws)}

        # Written after EVERY growth value, not just at the end, so a
        # long-running batch is inspectable mid-run (`cat` the --out file)
        # instead of only visible once the whole thing finishes.
        out = {
            "generated": datetime.now(timezone.utc).isoformat(),
            "provider": args.provider,
            "audit_row_id": row["id"], "tier": row["tier"],
            "original_line": ORIGINAL_LINE,
            "growth_values_tested": growth_values,
            "growth_values_completed": list(results.keys()),
            "results": {str(k): v for k, v in results.items()},
        }
        with open(args.out, "w") as f:
            json.dump(out, f, indent=2)

    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
