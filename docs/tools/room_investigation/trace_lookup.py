#!/usr/bin/env python3
"""CR239 Leg A — "paste the number, get the whole story" for one request id.

`HTTPAuditMiddleware` mints one UUID per request, echoes it as `X-Request-Id`
on the response (and in every error body's `request_id` field), and that same
value is `http_audit.id` — not a second number. A user's screenshot carries
this id (as "Error ref: <8-char prefix>" for a REST error, or the trace
reference on a Room error card, or a full UUID off `X-Request-Id` if a support
session has network logs); this script goes from that id to the http_audit
row plus every table the request is known to touch, in one command, the same
way `room_llm_audit_trace.py` does for `llm_audit`.

## Connecting

Same SSH-to-melehost pattern as the rest of this toolkit — no local Postgres
driver, no DATABASE_URL needed:
    python3 trace_lookup.py <request-id-or-8-char-prefix>

A prefix is resolved via `id::text LIKE '<prefix>%'`; the script refuses (with
a clear list of matches) if more than one row matches a short prefix, rather
than silently picking the first — the tool this whole toolkit's docstrings
warn against building being wrong quietly.

## What it prints

1. The `http_audit` row itself: method, path, status, latency, user_id,
   created_at — the request's own shape.
2. If `user_id` is set and the path looks like a Room path (`/v1/room/...`),
   the nearest `room_runs` row for that user_id around the same time (Room's
   own `run_id` is the more useful reference for a Room incident — see CR239
   scope item 5 — this is a bridge for the rare case only the HTTP-level id
   was reported).
3. A ready-to-paste `docker logs` grep for the exact request_id, so every
   structlog line `bind_contextvars` attached it to (agent calls included,
   during a Room) is one more command away.
"""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys


def _run_psql(sql: str) -> str:
    remote_cmd = f"docker exec ami_postgres psql -U postgres -d ami_trade -t -A -c {shlex.quote(sql)}"
    result = subprocess.run(["ssh", "melehost", remote_cmd], capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"psql failed: {result.stderr}")
    return result.stdout


def _resolve_id(prefix: str) -> str:
    """A bare UUID resolves to itself; anything shorter is matched as a
    prefix, refusing ambiguity the same way room_llm_audit_trace.py's
    get/diff refuse a bare query against a shared user_id."""
    if len(prefix) >= 32:
        return prefix
    sql = f"SELECT id FROM http_audit WHERE id::text LIKE '{prefix}%' ORDER BY created_at DESC;"
    out = [line.strip() for line in _run_psql(sql).splitlines() if line.strip()]
    if not out:
        print(f"No http_audit row matches prefix '{prefix}'.", file=sys.stderr)
        sys.exit(1)
    if len(out) > 1:
        print(
            f"Ambiguous prefix '{prefix}' — {len(out)} rows match:\n  "
            + "\n  ".join(out)
            + "\nPass a longer prefix or the full id.",
            file=sys.stderr,
        )
        sys.exit(1)
    return out[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("request_id", help="Full request id, or an 8+ char prefix (e.g. off 'Error ref: a1b2c3d4')")
    args = parser.parse_args()

    request_id = _resolve_id(args.request_id)

    row_sql = (
        "SELECT row_to_json(t) FROM (SELECT id, created_at, method, path, query, "
        "user_id, client_ip, status_code, latency_ms, is_streaming, response_truncated "
        f"FROM http_audit WHERE id='{request_id}') t;"
    )
    out = _run_psql(row_sql).strip()
    if not out:
        print(f"No http_audit row found for id {request_id}.", file=sys.stderr)
        return 1
    row = json.loads(out)
    print("=== http_audit ===")
    for k, v in row.items():
        print(f"  {k}: {v}")

    user_id = row.get("user_id")
    path = row.get("path") or ""
    created_at = row.get("created_at")

    if user_id and path.startswith("/v1/room"):
        print("\n=== nearby room_runs (same user, +/- 15 min) ===")
        room_sql = (
            "SELECT row_to_json(t) FROM (SELECT id, ticker, status, triggered_at, "
            "finished_at, error_message FROM room_runs WHERE user_id="
            f"'{user_id}' AND triggered_at BETWEEN "
            f"'{created_at}'::timestamptz - interval '15 minutes' AND "
            f"'{created_at}'::timestamptz + interval '15 minutes' "
            "ORDER BY triggered_at) t;"
        )
        room_out = _run_psql(room_sql)
        found = False
        for line in room_out.splitlines():
            line = line.strip()
            if not line:
                continue
            found = True
            print(f"  {line}")
        if not found:
            print("  (none)")

    print(f"\n=== docker logs grep ===\n  ssh melehost \"docker logs ami_api_alpha 2>&1 | grep {request_id}\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
