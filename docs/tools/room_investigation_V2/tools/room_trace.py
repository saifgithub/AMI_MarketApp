"""Trace melehost's audit tables — `llm_audit` by user_id and `http_audit` by
request-id prefix — over ssh. V2 replacement for v1
`docs/tools/room_investigation/room_llm_audit_trace.py` and
`trace_lookup.py`: both are absorbed into `library/audit_db.py`, and this CLI
is a 1:1 mapping onto its functions.

Subcommands:

    list    every llm_audit call for a user_id, in created_at order
    get     one field from one agent's llm_audit row (hard refusal on ambiguity)
    diff    unified diff of one agent's field between two user_ids' convenes
    lookup  one X-Request-Id (or >=8-char prefix) -> http_audit row + nearby
            room_runs + a ready-to-paste docker-logs grep

`llm_audit` has NO run_id/ticker column: correlation works only because the
toolkit mints one fresh synthetic user_id per convene (structural in v2 —
`library/runner.py` mints the ids). When a user_id spans multiple convenes (an
old batch driver reusing one id), v1 warned and returned the earliest row —
the wrong ticker's call, silently, hit live 2026-09-26. V2 refuses:
AmbiguousQueryError / NoRowsError print their message and exit 2.

No provider/env bootstrap needed: read-only SELECTs via
`ssh melehost docker exec ami_postgres psql`, parameterized in
`library/audit_db.py` — no local Postgres driver, no DATABASE_URL.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from library import audit_db  # noqa: E402


def cmd_list(args: argparse.Namespace) -> int:
    for row in audit_db.list_calls(args.user_id):
        print(f"{row.created_at:30s} {row.agent_id:22s} {row.provider:8s} {row.flow}")
    return 0


def cmd_get(args: argparse.Namespace) -> int:
    print(audit_db.get_field(
        args.user_id, args.agent_id, args.field,
        after=args.after, before=args.before, nth=args.nth,
    ))
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    diff = audit_db.diff_fields(
        args.user_id_a, args.user_id_b, args.agent_id,
        field=args.field,
        after_a=args.after_a, before_a=args.before_a, nth_a=args.nth_a,
        after_b=args.after_b, before_b=args.before_b, nth_b=args.nth_b,
    )
    print(diff, end="")
    if not diff:
        print("(identical)")
    return 0


def cmd_lookup(args: argparse.Namespace) -> int:
    result = audit_db.lookup_request_id(args.request_id)
    print("=== http_audit ===")
    for k, v in result["http_audit"].items():
        print(f"  {k}: {v}")
    if result["http_audit"].get("user_id") and (result["http_audit"].get("path") or "").startswith("/v1/room"):
        print("\n=== nearby room_runs (same user, +/- 15 min) ===")
        if result["room_runs"]:
            for row in result["room_runs"]:
                print(f"  {row}")
        else:
            print("  (none)")
    print(f"\n=== docker logs grep ===\n  {result['docker_logs_grep']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Trace llm_audit/http_audit on melehost (read-only, over ssh).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="list every agent call for a user_id, in order")
    p_list.add_argument("--user-id", required=True)
    p_list.set_defaults(func=cmd_list)

    p_get = sub.add_parser("get", help="pull one agent's full field value for a user_id")
    p_get.add_argument("--user-id", required=True)
    p_get.add_argument("--agent-id", required=True)
    p_get.add_argument("--field", default="response_text",
                       help=f"valid: {sorted(audit_db.VALID_FIELDS)}")
    p_get.add_argument("--after", default=None,
                       help="only rows with created_at >= this (ISO timestamp) — use when --user-id spans multiple convenes")
    p_get.add_argument("--before", default=None, help="only rows with created_at <= this (ISO timestamp)")
    p_get.add_argument("--nth", type=int, default=None,
                       help="0-indexed: the Nth occurrence of --agent-id for this user_id, in created_at order (alternative to --after/--before)")
    p_get.set_defaults(func=cmd_get)

    p_diff = sub.add_parser("diff", help="diff one agent's field between two user_ids")
    p_diff.add_argument("--user-id-a", required=True)
    p_diff.add_argument("--user-id-b", required=True)
    p_diff.add_argument("--agent-id", required=True)
    p_diff.add_argument("--field", default="system_prompt",
                        help="default system_prompt, NOT messages — messages is a trivial placeholder for every Room agent (see library/audit_db.py)")
    p_diff.add_argument("--after-a", default=None, help="window bound for side A — use when --user-id-a spans multiple convenes")
    p_diff.add_argument("--before-a", default=None)
    p_diff.add_argument("--nth-a", type=int, default=None, help="0-indexed occurrence of --agent-id for side A (alternative to --after-a/--before-a)")
    p_diff.add_argument("--after-b", default=None, help="window bound for side B")
    p_diff.add_argument("--before-b", default=None)
    p_diff.add_argument("--nth-b", type=int, default=None, help="0-indexed occurrence of --agent-id for side B")
    p_diff.set_defaults(func=cmd_diff)

    p_lookup = sub.add_parser("lookup", help="one X-Request-Id (or >=8-char prefix) -> the whole story")
    p_lookup.add_argument("request_id", help="full request id, or an 8+ char prefix (e.g. off 'Error ref: a1b2c3d4')")
    p_lookup.set_defaults(func=cmd_lookup)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except (audit_db.AmbiguousQueryError, audit_db.NoRowsError) as exc:
        print(exc, file=sys.stderr)
        return 2
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
