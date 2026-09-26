#!/usr/bin/env python3
"""Pull every agent call's captured system_prompt/messages/response_text for
a given `user_id`, from melehost's `llm_audit` Postgres table — extracted
from the ad hoc psql one-liners repeated throughout the CR228/BAC
risk_score=2 instability investigation (2026-09) into a reusable tool.

## Why user_id, not run_id or ticker

`llm_audit` (backend/app/db/models.py, `LLMAuditRow`) has NO `run_id` and NO
`ticker` column — every column list this table has ever had is: id,
created_at, user_id, agent_id, flow, tier, provider, locale, system_prompt,
messages, response_text, latency_ms, input/output/cache tokens,
prompt_version, constraint_status, error. Every script in this toolkit
(room_risk_score_sweep.py, room_repeat_consistency.py) mints a FRESH
synthetic user_id per draw specifically so this correlation stays
unambiguous — one user_id = one Room convene = one full agent-call sequence.
If you ran a script from this toolkit, its output JSONL's `user_id` field is
the key to pass here.

## Connecting to the DB

This needs `DATABASE_URL` pointed at melehost's Postgres via the SSH tunnel
this investigation established:
    ssh -f -N -L 5434:127.0.0.1:5434 melehost
    export DB_PASSWORD=$(ssh melehost "docker exec ami_postgres printenv POSTGRES_PASSWORD")
    export DATABASE_URL="postgresql+psycopg2://postgres:${DB_PASSWORD}@127.0.0.1:5434/ami_trade"
This script shells out to `ssh melehost docker exec ami_postgres psql` directly
instead of using DATABASE_URL/psycopg2, matching how this investigation
actually pulled data — no local Postgres driver dependency, works from a
plain Python env with no extra installs.

## Usage

List every agent call for a user_id, in order:
    python3 room_llm_audit_trace.py list --user-id <uuid>

Pull one agent's full response_text for a user_id:
    python3 room_llm_audit_trace.py get --user-id <uuid> --agent-id trader --field response_text

Diff two user_ids' output for the same agent (e.g. compare a PASS run vs an
APPROVE run's `trader` call):
    python3 room_llm_audit_trace.py diff --user-id-a <uuid1> --user-id-b <uuid2> --agent-id trader --field system_prompt
"""
from __future__ import annotations

import argparse
import difflib
import json
import shlex
import subprocess
import sys

VALID_FIELDS = {
    "system_prompt", "messages", "response_text", "agent_id", "flow", "tier",
    "provider", "locale", "created_at", "latency_ms", "input_tokens",
    "output_tokens", "constraint_status", "error",
}


def _run_psql(sql: str) -> str:
    """`ssh melehost "<remote command>"` runs <remote command> through the
    remote shell as ONE string — so the whole `docker exec ... psql -c <sql>`
    invocation must be built as a single shell-quoted string, not a list of
    argv tokens (a list here would split `-c` from its SQL argument once it
    crosses the ssh boundary, and the SQL text would be fed back to bash
    directly — this broke on the very first live test of this tool).
    """
    remote_cmd = f"docker exec ami_postgres psql -U postgres -d ami_trade -t -A -c {shlex.quote(sql)}"
    result = subprocess.run(["ssh", "melehost", remote_cmd], capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"psql failed: {result.stderr}")
    return result.stdout


def cmd_list(args: argparse.Namespace) -> int:
    sql = (
        f"SELECT row_to_json(t) FROM (SELECT agent_id, provider, flow, created_at "
        f"FROM llm_audit WHERE user_id='{args.user_id}' ORDER BY created_at) t;"
    )
    out = _run_psql(sql)
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        print(f"{row['created_at']:30s} {row['agent_id']:22s} {row['provider']:8s} {row['flow']}")
    return 0


def cmd_get(args: argparse.Namespace) -> int:
    field = args.field
    if field not in VALID_FIELDS:
        print(f"unknown field {field!r}; valid: {sorted(VALID_FIELDS)}", file=sys.stderr)
        return 1
    cast = "::text" if field == "messages" else ""
    sql = (
        f"SELECT {field}{cast} FROM llm_audit "
        f"WHERE user_id='{args.user_id}' AND agent_id='{args.agent_id}' "
        f"ORDER BY created_at LIMIT 1;"
    )
    out = _run_psql(sql)
    print(out)
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    field = args.field
    if field not in VALID_FIELDS:
        print(f"unknown field {field!r}; valid: {sorted(VALID_FIELDS)}", file=sys.stderr)
        return 1
    cast = "::text" if field == "messages" else ""
    sql_a = (
        f"SELECT {field}{cast} FROM llm_audit "
        f"WHERE user_id='{args.user_id_a}' AND agent_id='{args.agent_id}' "
        f"ORDER BY created_at LIMIT 1;"
    )
    sql_b = (
        f"SELECT {field}{cast} FROM llm_audit "
        f"WHERE user_id='{args.user_id_b}' AND agent_id='{args.agent_id}' "
        f"ORDER BY created_at LIMIT 1;"
    )
    text_a = _run_psql(sql_a)
    text_b = _run_psql(sql_b)
    diff = difflib.unified_diff(
        text_a.splitlines(keepends=True), text_b.splitlines(keepends=True),
        fromfile=f"{args.user_id_a} ({args.agent_id})",
        tofile=f"{args.user_id_b} ({args.agent_id})",
    )
    sys.stdout.writelines(diff)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Trace llm_audit rows by user_id (no run_id/ticker column exists).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="list every agent call for a user_id, in order")
    p_list.add_argument("--user-id", required=True)
    p_list.set_defaults(func=cmd_list)

    p_get = sub.add_parser("get", help="pull one agent's full field value for a user_id")
    p_get.add_argument("--user-id", required=True)
    p_get.add_argument("--agent-id", required=True)
    p_get.add_argument("--field", default="response_text")
    p_get.set_defaults(func=cmd_get)

    p_diff = sub.add_parser("diff", help="diff one agent's field between two user_ids")
    p_diff.add_argument("--user-id-a", required=True)
    p_diff.add_argument("--user-id-b", required=True)
    p_diff.add_argument("--agent-id", required=True)
    p_diff.add_argument("--field", default="system_prompt")
    p_diff.set_defaults(func=cmd_diff)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
