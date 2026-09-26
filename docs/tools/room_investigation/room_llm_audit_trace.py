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

## A shared/reused user_id holds MULTIPLE convenes — bound the window

Not every user_id is one-convene-only. `room_repeat_consistency.py` and
`room_risk_score_sweep.py` mint a fresh user_id per draw, so for THEIR output
a bare `get`/`diff` is safe. But a 30-ticker batch driver script (e.g. this
investigation's `run_local_kimi.py`/`run_pilot.sh`-style sweeps) can reuse ONE
user_id across the whole batch, back-to-back, with no gap between one
ticker's PM votes ending and the next ticker's analysts starting. `get`/`diff`
default to `ORDER BY created_at LIMIT 1` — against a shared user_id that
silently returns the WRONG ticker's call with no error (this happened live,
2026-09-26: a bare `get --agent-id trader` on a batch user_id returned an
earlier ticker's trader call, not the intended one).

If `list --user-id <uuid>` shows more than ~17 rows (one convene is ~17: 4
analysts + bull/bear + research_manager + trader + 3 debators + up to 5 PM
votes, occasionally +1 PM reformat), the user_id is shared. Narrow `get`/
`diff` to the right convene with `--after`/`--before` (from the batch
driver's own JSONL `triggered_at`, or read off the `list` output directly —
find the PM-votes block that ends right before your ticker's analysts start,
that gap is the convene boundary) or `--nth` (0-indexed, Nth occurrence of
`--agent-id` in the whole user_id's history, in `created_at` order — simpler
when you just know "the 6th ticker in this batch", no timestamps needed).
`get`/`diff` print a loud warning to stderr whenever the (optionally
windowed) query still matches more than one row, specifically so this class
of silent-wrong-answer can't repeat.
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
    n = 0
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        n += 1
        print(f"{row['created_at']:30s} {row['agent_id']:22s} {row['provider']:8s} {row['flow']}")
    if n > 20:
        print(
            f"\nNOTE: {n} rows for this user_id — one convene is ~17 "
            f"(4 analysts + bull/bear + research_manager + trader + 3 debators "
            f"+ up to 5 PM votes, occasionally +1 reformat). This user_id likely "
            f"spans MULTIPLE convenes (a batch run reusing one user_id). Use "
            f"get/diff's --after/--before or --nth to target the right one — a "
            f"bare get/diff will otherwise silently return the wrong ticker's call.",
            file=sys.stderr,
        )
    return 0


def _window_clause(after: str | None, before: str | None) -> str:
    parts = []
    if after:
        parts.append(f"created_at >= '{after}'")
    if before:
        parts.append(f"created_at <= '{before}'")
    return (" AND " + " AND ".join(parts)) if parts else ""


def _count_matches(user_id: str, agent_id: str, after: str | None, before: str | None) -> int:
    sql = (
        f"SELECT count(*) FROM llm_audit WHERE user_id='{user_id}' "
        f"AND agent_id='{agent_id}'{_window_clause(after, before)};"
    )
    out = _run_psql(sql).strip()
    return int(out) if out else 0


def _fetch_field(
    user_id: str, agent_id: str, field: str, *,
    after: str | None, before: str | None, nth: int | None,
) -> tuple[str, int]:
    """Returns (value, total_matches_in_window) so callers can warn on ambiguity."""
    cast = "::text" if field == "messages" else ""
    window = _window_clause(after, before)
    total = _count_matches(user_id, agent_id, after, before)
    offset = f"OFFSET {nth}" if nth else ""
    sql = (
        f"SELECT {field}{cast} FROM llm_audit "
        f"WHERE user_id='{user_id}' AND agent_id='{agent_id}'{window} "
        f"ORDER BY created_at LIMIT 1 {offset};"
    )
    return _run_psql(sql), total


def cmd_get(args: argparse.Namespace) -> int:
    field = args.field
    if field not in VALID_FIELDS:
        print(f"unknown field {field!r}; valid: {sorted(VALID_FIELDS)}", file=sys.stderr)
        return 1
    out, total = _fetch_field(
        args.user_id, args.agent_id, field,
        after=args.after, before=args.before, nth=args.nth,
    )
    if total > 1 and args.nth is None:
        print(
            f"WARNING: {total} '{args.agent_id}' rows match this user_id"
            f"{' in the given window' if (args.after or args.before) else ''} "
            f"— this user_id likely spans multiple convenes (a batch run). "
            f"Returning the earliest by created_at, which may be the WRONG "
            f"ticker/draw. Narrow with --after/--before or --nth. "
            f"Run `list --user-id {args.user_id}` to see convene boundaries.",
            file=sys.stderr,
        )
    print(out)
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    field = args.field
    if field not in VALID_FIELDS:
        print(f"unknown field {field!r}; valid: {sorted(VALID_FIELDS)}", file=sys.stderr)
        return 1
    text_a, total_a = _fetch_field(
        args.user_id_a, args.agent_id, field,
        after=args.after_a, before=args.before_a, nth=args.nth_a,
    )
    text_b, total_b = _fetch_field(
        args.user_id_b, args.agent_id, field,
        after=args.after_b, before=args.before_b, nth=args.nth_b,
    )
    for label, uid, total, nth in (
        ("A", args.user_id_a, total_a, args.nth_a),
        ("B", args.user_id_b, total_b, args.nth_b),
    ):
        if total > 1 and nth is None:
            print(
                f"WARNING: side {label} ({uid}) has {total} '{args.agent_id}' rows "
                f"matching — this user_id likely spans multiple convenes. Returning "
                f"the earliest by created_at, which may be the WRONG ticker/draw. "
                f"Narrow with --after-{label.lower()}/--before-{label.lower()} or "
                f"--nth-{label.lower()}.",
                file=sys.stderr,
            )
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
    p_get.add_argument("--after", default=None, help="only rows with created_at >= this (ISO timestamp) — use when --user-id spans multiple convenes")
    p_get.add_argument("--before", default=None, help="only rows with created_at <= this (ISO timestamp)")
    p_get.add_argument("--nth", type=int, default=None, help="0-indexed: the Nth occurrence of --agent-id for this user_id, in created_at order (alternative to --after/--before)")
    p_get.set_defaults(func=cmd_get)

    p_diff = sub.add_parser("diff", help="diff one agent's field between two user_ids")
    p_diff.add_argument("--user-id-a", required=True)
    p_diff.add_argument("--user-id-b", required=True)
    p_diff.add_argument("--agent-id", required=True)
    p_diff.add_argument("--field", default="system_prompt")
    p_diff.add_argument("--after-a", default=None, help="window bound for side A — use when --user-id-a spans multiple convenes")
    p_diff.add_argument("--before-a", default=None)
    p_diff.add_argument("--nth-a", type=int, default=None, help="0-indexed occurrence of --agent-id for side A (alternative to --after-a/--before-a)")
    p_diff.add_argument("--after-b", default=None, help="window bound for side B")
    p_diff.add_argument("--before-b", default=None)
    p_diff.add_argument("--nth-b", type=int, default=None, help="0-indexed occurrence of --agent-id for side B")
    p_diff.set_defaults(func=cmd_diff)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
