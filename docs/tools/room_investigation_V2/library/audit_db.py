"""audit_db — read-only access to melehost's Postgres for Room investigation.

Single parameterized implementation of the ssh -> `docker exec ami_postgres
psql` helper that v1 duplicated verbatim across `room_llm_audit_trace.py` and
`trace_lookup.py`, with f-string SQL interpolation in both. One helper exists
here so the quoting rules (the only thing standing between a caller and SQL
injection through a ticker string or a prompt fragment) are written, tested,
and fixed in exactly one place. All SQL goes through `run_psql` with `%s`
placeholders and literal-quoted params — no f-string interpolation of values
anywhere in this module.

## The user_id-correlation hazard (why this module refuses instead of warns)

`llm_audit` has NO `run_id` and NO `ticker` column. Correlation to a Room
convene works only because the toolkit mints a fresh synthetic `user_id` per
draw — one user_id = one convene = ~17 agent-call rows. But a batch driver
can reuse ONE user_id across a whole ticker sweep, back-to-back, and v1's
bare `get` then silently returned the WRONG ticker's call (hit live
2026-09-26: asked for SO's trader call, got AAPL's, no error). V1's answer
was a stderr WARNING that still returned a value. V2 makes it structural:
`get_field` raises `AmbiguousQueryError` (with the count and the full
`created_at` list) whenever more than one row matches and no `nth` was given,
and `NoRowsError` on zero rows. It is now impossible to silently read the
wrong ticker's call.

Requires: ssh access to `melehost` from the office LAN. No local Postgres
driver, no DATABASE_URL — read-only SELECTs only. When the Mac is off the
LAN, set AMI_AUDIT_SSH_HOST to a reachable alias (e.g. `melehost-ts` over
Tailscale, D32a); the default stays the LAN alias.

`call_metrics(user_id)` is the per-call token/error companion to
`list_calls`: output_tokens, error, and constraint_status per row with the
same nth-per-agent ordering `get_field` uses, so scoring.gate_report's
truncation heuristic can line a metric row up with a response_text read.
"""
from __future__ import annotations

import difflib
import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from typing import Sequence

SSH_HOST = os.environ.get("AMI_AUDIT_SSH_HOST", "melehost")
PG_CONTAINER = "ami_postgres"
PG_DB = "ami_trade"
PG_USER = "postgres"
PSQL_TIMEOUT_S = 60

VALID_FIELDS = frozenset({
    "system_prompt", "messages", "response_text", "agent_id", "flow", "tier",
    "provider", "locale", "created_at", "latency_ms", "input_tokens",
    "output_tokens", "constraint_status", "error",
})

# verdict_outcomes schema — verified live against melehost 2026-09-28 via
# information_schema (matches the ORM model VerdictOutcomeRow, CR219).
# fetch_verdict_outcomes() still discovers the column list on every call and
# never assumes this list — this note is for the reader, not the code.
VERDICT_OUTCOMES_SCHEMA_NOTE = (
    "verified live 2026-09-28 (19 columns): id uuid, room_run_id uuid, "
    "user_id uuid, ticker varchar, verdict_action varchar, conviction "
    "varchar, approve_votes int, samples int, size_pct float8, "
    "reference_price numeric, reference_at timestamptz, horizon_days int, "
    "status varchar, outcome_price numeric, outcome_date date, "
    "forward_return float8, scored_at timestamptz, exclusion_reason "
    "varchar, created_at timestamptz"
)


@dataclass(frozen=True)
class CallRow:
    created_at: str
    agent_id: str
    provider: str
    flow: str


@dataclass(frozen=True)
class CallMetrics:
    agent_id: str
    nth: int
    output_tokens: int | None
    error: str | None
    constraint_status: str | None


class AmbiguousQueryError(RuntimeError):
    pass


class NoRowsError(RuntimeError):
    pass


def _quote_literal(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    raise TypeError(f"unsupported SQL parameter type: {type(value).__name__}")


def run_psql(sql: str, params: Sequence[object] = ()) -> str:
    """Run one SQL statement against melehost's Postgres over ssh.

    `sql` contains `%s` placeholders; each param is literal-quoted by
    `_quote_literal` (strings single-quoted with `''` doubling, None -> NULL,
    numbers bare, bools -> TRUE/FALSE, anything else a TypeError) and
    substituted textually — psql has no bind-parameter channel through `-c`,
    so the quoting here is the entire injection boundary. Placeholder count
    must equal len(params).

    The whole remote `docker exec ... psql -c <sql>` invocation is built as
    ONE shell-quoted string (v1 lesson: an argv list splits `-c` from its SQL
    once it crosses the ssh boundary and the SQL is fed back to bash
    directly). Raises RuntimeError with stderr text on non-zero exit.
    """
    parts = sql.split("%s")
    if len(parts) - 1 != len(params):
        raise ValueError(
            f"placeholder count {len(parts) - 1} != {len(params)} params"
        )
    filled = parts[0]
    for value, tail in zip(params, parts[1:]):
        filled += _quote_literal(value) + tail
    remote_cmd = (
        f"docker exec {PG_CONTAINER} psql -U {PG_USER} -d {PG_DB} -t -A "
        f"-c {shlex.quote(filled)}"
    )
    result = subprocess.run(
        ["ssh", SSH_HOST, remote_cmd],
        capture_output=True, text=True, timeout=PSQL_TIMEOUT_S,
    )
    if result.returncode != 0:
        raise RuntimeError(f"psql failed: {result.stderr}")
    return result.stdout


def _window_clauses(user_id: str, after: str | None,
                    before: str | None) -> tuple[str, list[object]]:
    clauses = ["user_id=%s"]
    params: list[object] = [user_id]
    if after is not None:
        clauses.append("created_at >= %s")
        params.append(after)
    if before is not None:
        clauses.append("created_at <= %s")
        params.append(before)
    return " AND ".join(clauses), params


def list_calls(user_id: str, *, after: str | None = None,
               before: str | None = None) -> list[CallRow]:
    """Every llm_audit call for a user_id, in created_at order.

    `after`/`before` are inclusive created_at window bounds with the same
    semantics as get_field's — needed because deterministic per-arm user_ids
    (uuid5) mean a killed-then-resumed benchmark arm shares one user_id
    across the partial and the completed convene; the window scopes the
    listing to the convene of interest.

    Prints the v1 NOTE to stderr when more than 20 rows come back: one
    convene is ~17 rows, so a larger count means a batch driver reused this
    user_id across tickers and `get_field` needs after/before/nth to target
    the right convene.
    """
    where, params = _window_clauses(user_id, after, before)
    sql = (
        "SELECT created_at, agent_id, provider, flow FROM llm_audit "
        f"WHERE {where} ORDER BY created_at;"
    )
    out = run_psql(sql, params)
    rows: list[CallRow] = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        created_at, agent_id, provider, flow = line.split("|", 3)
        rows.append(CallRow(created_at=created_at, agent_id=agent_id,
                            provider=provider, flow=flow))
    if len(rows) > 20:
        print(
            f"\nNOTE: {len(rows)} rows for this user_id — one convene is ~17 "
            f"(4 analysts + bull/bear + research_manager + trader + 3 debators "
            f"+ up to 5 PM votes, occasionally +1 reformat). This user_id likely "
            f"spans MULTIPLE convenes (a batch run reusing one user_id). Use "
            f"get_field's after/before or nth to target the right one — "
            f"get_field refuses ambiguity, so a bare call will raise "
            f"AmbiguousQueryError rather than return the wrong ticker's call.",
            file=sys.stderr,
        )
    return rows


def call_metrics(user_id: str, *, after: str | None = None,
                 before: str | None = None) -> list[CallMetrics]:
    """Per-call token/error signals for one user_id, in created_at order.

    `after`/`before` are inclusive created_at window bounds, same semantics
    as get_field's — a killed-then-resumed arm shares its deterministic
    user_id with the partial convene, and the window scopes the metrics to
    the completed run so nth still lines up with get_field's nth.

    `nth` is the 0-indexed occurrence per agent_id in created_at order —
    the same semantics as get_field's `nth`, so a CallMetrics row and a
    get_field(..., nth=n) call target the same llm_audit row. NULL columns
    come back as None. The truncation signal scoring.gate_report derives
    from output_tokens is a heuristic: llm_audit has no finish_reason
    column.
    """
    where, params = _window_clauses(user_id, after, before)
    out = run_psql(
        "SELECT agent_id, output_tokens, error, constraint_status "
        f"FROM llm_audit WHERE {where} ORDER BY created_at;",
        params,
    )
    seen: dict[str, int] = {}
    rows: list[CallMetrics] = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("|")
        agent_id = parts[0]
        tokens_raw = parts[1] if len(parts) > 1 else ""
        error = "|".join(parts[2:-1]) or None
        constraint_status = parts[-1] or None
        nth = seen.get(agent_id, 0)
        seen[agent_id] = nth + 1
        rows.append(CallMetrics(
            agent_id=agent_id,
            nth=nth,
            output_tokens=int(tokens_raw) if tokens_raw else None,
            error=error,
            constraint_status=constraint_status,
        ))
    return rows


def get_field(user_id: str, agent_id: str, field: str, *,
              after: str | None = None, before: str | None = None,
              nth: int | None = None) -> str:
    """One field from one llm_audit row, with hard refusal on ambiguity.

    `after`/`before` are inclusive created_at window bounds; `nth` is the
    0-indexed occurrence in created_at order (the disambiguator for a shared
    batch user_id when you know "the Nth ticker" but not the timestamps).
    Zero rows -> NoRowsError; more than one row in the window and no `nth` ->
    AmbiguousQueryError carrying the count and the created_at list, so the
    wrong-ticker silent read v1 hit live cannot recur. `messages` gets v1's
    `::text` cast (jsonb column). Returns psql's raw stdout for the value.
    """
    if field not in VALID_FIELDS:
        raise ValueError(f"unknown field {field!r}; valid: {sorted(VALID_FIELDS)}")
    clauses = ["user_id=%s", "agent_id=%s"]
    params: list[object] = [user_id, agent_id]
    if after is not None:
        clauses.append("created_at >= %s")
        params.append(after)
    if before is not None:
        clauses.append("created_at <= %s")
        params.append(before)
    where = " AND ".join(clauses)
    stamps = [
        line.strip()
        for line in run_psql(
            f"SELECT created_at FROM llm_audit WHERE {where} "
            f"ORDER BY created_at;", params,
        ).splitlines()
        if line.strip()
    ]
    if not stamps:
        raise NoRowsError(
            f"no llm_audit rows for user_id={user_id} agent_id={agent_id}"
            f"{' in the given window' if (after or before) else ''}"
        )
    if nth is None:
        if len(stamps) > 1:
            raise AmbiguousQueryError(
                f"{len(stamps)} '{agent_id}' rows match user_id={user_id}"
                f"{' in the given window' if (after or before) else ''} — "
                f"this user_id likely spans multiple convenes (a batch run "
                f"reusing one user_id). Refusing to pick one silently. "
                f"created_at values: {stamps}. Narrow with after/before or "
                f"nth (0-indexed)."
            )
        offset = 0
    else:
        if nth < 0 or nth >= len(stamps):
            raise NoRowsError(
                f"nth={nth} out of range: {len(stamps)} '{agent_id}' rows "
                f"match user_id={user_id} (created_at: {stamps})"
            )
        offset = nth
    cast = "::text" if field == "messages" else ""
    return run_psql(
        f"SELECT {field}{cast} FROM llm_audit WHERE {where} "
        f"ORDER BY created_at LIMIT 1 OFFSET {offset};", params,
    )


def diff_fields(user_id_a: str, user_id_b: str, agent_id: str, *,
                field: str = "system_prompt",
                after_a: str | None = None, before_a: str | None = None,
                nth_a: int | None = None,
                after_b: str | None = None, before_b: str | None = None,
                nth_b: int | None = None) -> str:
    """Unified diff of one agent's field between two user_ids' convenes.

    Default field is `system_prompt`, NOT `messages` — per the v1 README,
    every Room agent's captured `messages` is the trivial placeholder
    `[{"role": "user", "content": "Convene on <TICKER>."}]`; the real
    role/task text, the live fact sheet, and the full upstream transcript are
    all in `system_prompt`. Diffing `messages` between two runs always comes
    back empty/trivial and proves nothing — that produced a wrong
    "prompts are byte-identical" conclusion live 2026-09-26. Diff/replay
    `system_prompt` for anything upstream-of-this-agent.

    Returns the diff as one string ("" when identical). Ambiguity on either
    side raises via `get_field`.
    """
    text_a = get_field(user_id_a, agent_id, field,
                       after=after_a, before=before_a, nth=nth_a)
    text_b = get_field(user_id_b, agent_id, field,
                       after=after_b, before=before_b, nth=nth_b)
    return "".join(difflib.unified_diff(
        text_a.splitlines(keepends=True), text_b.splitlines(keepends=True),
        fromfile=f"{user_id_a} ({agent_id})",
        tofile=f"{user_id_b} ({agent_id})",
    ))


def lookup_request_id(prefix: str) -> dict:
    """Absorbs v1 trace_lookup.py: one X-Request-Id -> the whole story.

    `prefix` is a full UUID or a >=8-char prefix (the "Error ref: a1b2c3d4"
    shape users report), matched via `id::text LIKE '<prefix>%'` against
    http_audit. Zero matches -> NoRowsError; more than one ->
    AmbiguousQueryError with the candidate ids (v1's refuse-on-ambiguity
    behaviour, kept). Returns:
      - "http_audit": the row as a dict
      - "room_runs": rows for the same user within +/-15min, only when the
        path starts with /v1/room (else [])
      - "docker_logs_grep": the ready-to-paste ssh command that greps
        ami_api_alpha's logs for the resolved id
    """
    if len(prefix) < 8:
        raise ValueError(f"prefix {prefix!r} too short; need >= 8 chars")
    if len(prefix) >= 32:
        request_id = prefix
    else:
        matches = [
            line.strip()
            for line in run_psql(
                "SELECT id FROM http_audit WHERE id::text LIKE %s "
                "ORDER BY created_at DESC;", [prefix + "%"],
            ).splitlines()
            if line.strip()
        ]
        if not matches:
            raise NoRowsError(f"no http_audit row matches prefix {prefix!r}")
        if len(matches) > 1:
            raise AmbiguousQueryError(
                f"ambiguous prefix {prefix!r} — {len(matches)} rows match: "
                f"{matches}. Pass a longer prefix or the full id."
            )
        request_id = matches[0]
    out = run_psql(
        "SELECT row_to_json(t) FROM (SELECT id, created_at, method, path, "
        "query, user_id, client_ip, status_code, latency_ms, is_streaming, "
        "response_truncated FROM http_audit WHERE id=%s) t;", [request_id],
    ).strip()
    if not out:
        raise NoRowsError(f"no http_audit row found for id {request_id}")
    row = json.loads(out)
    room_runs: list[dict] = []
    user_id = row.get("user_id")
    path = row.get("path") or ""
    if user_id and path.startswith("/v1/room"):
        room_out = run_psql(
            "SELECT row_to_json(t) FROM (SELECT id, ticker, status, "
            "triggered_at, finished_at, error_message FROM room_runs "
            "WHERE user_id=%s AND triggered_at BETWEEN "
            "%s::timestamptz - interval '15 minutes' AND "
            "%s::timestamptz + interval '15 minutes' "
            "ORDER BY triggered_at) t;",
            [user_id, row.get("created_at"), row.get("created_at")],
        )
        for line in room_out.splitlines():
            line = line.strip()
            if line:
                room_runs.append(json.loads(line))
    return {
        "http_audit": row,
        "room_runs": room_runs,
        "docker_logs_grep": (
            f'ssh {SSH_HOST} "docker logs ami_api_alpha 2>&1 | '
            f'grep {request_id}"'
        ),
    }


def fetch_verdict_outcomes(*, limit: int | None = None) -> list[dict]:
    """CR247 Phase 0.1 census support: read the verdict_outcomes ledger.

    The schema is NOT assumed — the column list is discovered live from
    information_schema on every call and the SELECT is built from what
    actually exists. If the table does not exist, raises NoRowsError saying
    so plainly. `limit` caps the row count (no ORDER BY is applied unless a
    `created_at` column is discovered, in which case newest-first).

    Authoring-time note (2026-09-28): live schema verification was NOT
    possible — melehost was unreachable from the authoring machine. The
    expected shape per the ORM model is recorded in the module-level
    VERDICT_OUTCOMES_SCHEMA_NOTE; replace that note with the observed live
    columns on first successful run.
    """
    cols = [
        line.split("|", 1)[0].strip()
        for line in run_psql(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name=%s ORDER BY ordinal_position;",
            ["verdict_outcomes"],
        ).splitlines()
        if line.strip()
    ]
    if not cols:
        raise NoRowsError(
            "table 'verdict_outcomes' does not exist in "
            f"{PG_DB} on {SSH_HOST} (no rows in information_schema.columns)"
        )
    order = " ORDER BY created_at DESC" if "created_at" in cols else ""
    inner = f"SELECT {', '.join(cols)} FROM verdict_outcomes{order}"
    params: list[object] = []
    if limit is not None:
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            raise ValueError(f"limit must be a positive int, got {limit!r}")
        inner += " LIMIT %s"
        params.append(limit)
    rows: list[dict] = []
    for line in run_psql(
        f"SELECT row_to_json(t) FROM ({inner}) t;", params,
    ).splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows
