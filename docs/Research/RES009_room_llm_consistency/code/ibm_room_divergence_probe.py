#!/usr/bin/env python3
"""One-off diagnostic for the 2026-09-25 IBM Room divergence question.

Saiful ran two Room sessions on IBM ~78 seconds apart (two different users,
`room_runs.id` 7fd1a30c… on `premium` tier and 1707ad92… on `mid` tier) and
the agent responses came back noticeably different, most visibly a 200-day
SMA cited as $235.13 in one run and $258.13 in the other.

This script does NOT change product behavior. It:

  1. Pulls the full `llm_audit` rows (system_prompt, messages, response_text)
     for both runs' user_ids in their trigger window, and diffs them per
     agent_id — answers "compare the prompts and compare the output".
  2. Replays each run's exact captured (system_prompt, messages) verbatim
     against the live vLLM endpoint a second time, so each original run has
     a same-prompt replay sitting next to it — answers "take the same
     prompt and send it again... show me 4 runs".

Both model tiers route through the same underlying vLLM model (`VLLM_MODEL`,
aliased `ami-llm` — see docker-compose.yml and CLAUDE.md's runtime-state
table), so tier does not select a different model here; it only affects
`max_tokens`/prompt construction upstream. Worth confirming in the report,
not assuming.

Must run where `DATABASE_URL` points at melehost's Postgres (i.e. on
melehost itself, or from the Mac with an SSH tunnel) — the Mac has no local
DB (see CLAUDE.md "Runtime state": Mac is a pure editor).

Usage:
    python3 -m scripts.ibm_room_divergence_probe \\
        --user-a 8f1e288a-b288-4b9e-942f-2003b88ba555 \\
        --user-b d00000f5-c311-4f4e-b94f-cc1b56cdedbc \\
        --since 2026-09-25T17:02:00+00:00 \\
        --until 2026-09-25T17:10:00+00:00 \\
        --out /tmp/ibm_divergence_report.md
"""
from __future__ import annotations

import argparse
import asyncio
import difflib
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx  # noqa: E402


def _from_db(user_a: str, user_b: str, since: str, until: str) -> dict[str, list]:
    from sqlalchemy import select

    from app.db.models import LLMAuditRow
    from app.db.session import get_session

    out: dict[str, list] = {user_a: [], user_b: []}
    with get_session() as s:
        for uid in (user_a, user_b):
            q = (
                select(LLMAuditRow)
                .where(LLMAuditRow.user_id == uid)
                .where(LLMAuditRow.created_at >= since)
                .where(LLMAuditRow.created_at <= until)
                .order_by(LLMAuditRow.created_at)
            )
            out[uid] = [
                {
                    "id": str(r.id),
                    "created_at": str(r.created_at),
                    "agent_id": r.agent_id,
                    "flow": r.flow,
                    "tier": r.tier,
                    "provider": r.provider,
                    "system_prompt": r.system_prompt,
                    "messages": r.messages,
                    "response_text": r.response_text,
                    "input_tokens": r.input_tokens,
                    "output_tokens": r.output_tokens,
                }
                for r in s.execute(q).scalars()
            ]
    return out


def _diff_block(label_a: str, text_a: str, label_b: str, text_b: str) -> str:
    lines_a = (text_a or "").splitlines()
    lines_b = (text_b or "").splitlines()
    diff = difflib.unified_diff(lines_a, lines_b, fromfile=label_a, tofile=label_b, lineterm="")
    return "\n".join(diff) or "(identical)"


async def _replay(base_url: str, model: str, system_prompt: str, messages: list, max_tokens: int = 1500) -> str:
    """POST the exact captured prompt back to vLLM, non-streamed, no
    temperature/seed set — deliberately matching `OpenAICompatibleProvider`'s
    request shape (llm_gateway.py) with nothing pinned, since that's the
    live configuration being probed.
    """
    openai_messages = [{"role": "system", "content": system_prompt}]
    for m in messages or []:
        openai_messages.append({"role": m.get("role", "user"), "content": m.get("content", "")})
    body = {
        "model": model,
        "messages": openai_messages,
        "max_tokens": max_tokens,
        "stream": False,
    }
    async with httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=120.0) as client:
        resp = await client.post("/v1/chat/completions", json=body)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user-a", required=True)
    ap.add_argument("--user-b", required=True)
    ap.add_argument("--since", required=True)
    ap.add_argument("--until", required=True)
    ap.add_argument("--replay-agents", default="fundamentals_analyst,pm",
                     help="comma-separated agent_id substrings to replay against vLLM")
    ap.add_argument("--vllm-base-url", default=os.environ.get("VLLM_BASE_URL", "http://192.168.20.74:8000"))
    ap.add_argument("--vllm-model", default=os.environ.get("VLLM_MODEL", "ami-llm"))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rows = _from_db(args.user_a, args.user_b, args.since, args.until)
    rows_a = rows[args.user_a]
    rows_b = rows[args.user_b]

    by_agent_a = {r["agent_id"]: r for r in rows_a}
    by_agent_b = {r["agent_id"]: r for r in rows_b}
    all_agents = sorted(set(by_agent_a) | set(by_agent_b))

    replay_needles = [s.strip() for s in args.replay_agents.split(",") if s.strip()]

    out_lines = []
    out_lines.append("# IBM Room divergence — prompt/output diff + replay")
    out_lines.append(f"\nGenerated {datetime.now(timezone.utc).isoformat()}")
    out_lines.append(f"\nUser A: `{args.user_a}` ({len(rows_a)} calls) — User B: `{args.user_b}` ({len(rows_b)} calls)")
    out_lines.append(f"\nWindow: {args.since} .. {args.until}")

    for agent_id in all_agents:
        ra = by_agent_a.get(agent_id)
        rb = by_agent_b.get(agent_id)
        out_lines.append(f"\n\n## agent_id = `{agent_id}`")
        if not ra or not rb:
            out_lines.append(f"\nOnly present in {'A' if ra else 'B'} — skipping diff.")
            continue

        out_lines.append(f"\n- Run A: `{ra['id']}` tier={ra['tier']} at {ra['created_at']}")
        out_lines.append(f"- Run B: `{rb['id']}` tier={rb['tier']} at {rb['created_at']}")

        out_lines.append("\n### system_prompt diff (A → B)")
        out_lines.append("```diff")
        out_lines.append(_diff_block("run_a_system_prompt", ra["system_prompt"],
                                      "run_b_system_prompt", rb["system_prompt"]))
        out_lines.append("```")

        out_lines.append("\n### messages diff (A → B)")
        out_lines.append("```diff")
        out_lines.append(_diff_block(
            "run_a_messages", json.dumps(ra["messages"], indent=2, sort_keys=True),
            "run_b_messages", json.dumps(rb["messages"], indent=2, sort_keys=True),
        ))
        out_lines.append("```")

        out_lines.append("\n### response_text — Run A")
        out_lines.append(f"\n```\n{ra['response_text']}\n```")
        out_lines.append("\n### response_text — Run B")
        out_lines.append(f"\n```\n{rb['response_text']}\n```")

        should_replay = any(needle in (agent_id or "") for needle in replay_needles)
        if not should_replay:
            continue

        out_lines.append("\n### Replay — same captured prompt re-sent to vLLM now")
        try:
            replay_a, replay_b = await asyncio.gather(
                _replay(args.vllm_base_url, args.vllm_model, ra["system_prompt"], ra["messages"]),
                _replay(args.vllm_base_url, args.vllm_model, rb["system_prompt"], rb["messages"]),
            )
        except Exception as exc:  # noqa: BLE001 — diagnostic script, report and move on
            out_lines.append(f"\nReplay failed: {exc!r}")
            continue

        out_lines.append("\n**Replay-A** (Run A's exact prompt, sent again):")
        out_lines.append(f"\n```\n{replay_a}\n```")
        out_lines.append("\n**Replay-B** (Run B's exact prompt, sent again):")
        out_lines.append(f"\n```\n{replay_b}\n```")

        out_lines.append("\n### 4-way comparison for this agent")
        out_lines.append("\n| | Run A (orig) | Replay-A | Run B (orig) | Replay-B |")
        out_lines.append("|---|---|---|---|---|")
        out_lines.append(
            f"| response length (chars) | {len(ra['response_text'] or '')} | {len(replay_a)} "
            f"| {len(rb['response_text'] or '')} | {len(replay_b)} |"
        )

    report = "\n".join(out_lines)
    with open(args.out, "w") as f:
        f.write(report)
    print(f"Wrote {args.out} ({len(report)} chars, {len(all_agents)} agents)")


if __name__ == "__main__":
    asyncio.run(main())
