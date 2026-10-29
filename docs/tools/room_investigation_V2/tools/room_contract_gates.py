#!/usr/bin/env python3
"""room_contract_gates — Mac-side V2 contract validator for CR265/CR266 acceptance.

Reusable gate over a runs_<bench>.jsonl file: every arm must be completed and
every completed arm's convene must pass `library.scoring.gate_report` over its
exact [triggered_at, finished_at] window, audited against melehost's
llm_audit. Exit 0 only when every arm is completed and every gate report is
ok; otherwise a detailed JSON report is written and the exit is 1. There is
no skip path — a noncompleted arm or a gate finding fails the run loudly.

llm_audit has no run_id/ticker column, so arms are correlated by their
deterministic per-arm user_id (library/runner.py's uuid5) and windowed by the
run record's timestamps — a killed-then-resumed arm shares one user_id across
the partial and completed convene, and the inclusive window scopes the audit
to this run's rows exactly as library/audit_db.py's after/before do.

SSH-storm avoidance: instead of per-agent/per-arm psql reads, arms are
chunked (--chunk-size, default 25) and each chunk makes ONE
`audit_db.run_psql` call — a json_agg(json_build_object(...)) over llm_audit
for all chunk user_ids, ordered created_at, ctid in a subquery. Placeholders
are generated for the chunk's user ids and the ids travel as parameters
through audit_db.run_psql's literal quoting; no value is interpolated into
the SQL text here. Rows are parsed locally and filtered per arm to the
inclusive window by BulkAudit, a duck-typed audit module with the same
list_calls/get_field/call_metrics semantics as audit_db (nth per agent in
created_at order; NoRowsError/AmbiguousQueryError), so scoring.gate_report
consumes it unchanged.

The arm key is reported verbatim (<ticker>-r<risk>-rep<i> or the legacy
<ticker>-rep<i>); it is never parsed — identity beyond the key is not needed
for acceptance.

Usage:
  python3 room_contract_gates.py --runs ../out/<bench>/runs_<name>.jsonl \
      --out ../out/<bench>/contract_gates.json [--chunk-size 25]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from library import audit_db, scoring  # noqa: E402

DEFAULT_CHUNK_SIZE = 25

# One bulk read pulls these llm_audit columns per row; user_id rides along
# as the arm discriminator because the WHERE spans a whole chunk's user_ids.
BULK_FIELDS = (
    "user_id", "agent_id", "flow", "provider", "created_at",
    "response_text", "output_tokens", "error", "constraint_status",
)


def _parse_ts(value: object) -> datetime:
    """Parse a created_at/triggered_at string from either source to an aware
    datetime: the runner writes ISO-8601 (`2026-10-27T10:00:00.123456+00:00`,
    occasional trailing `Z`), psql -A renders timestamptz as
    `2026-10-27 10:00:00.123456+00` (space separator, minute-less offset).
    Naive values are assumed UTC. Never a silent guess: unparseable input
    raises ValueError.
    """
    text = str(value).strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    text = text.replace(" ", "T", 1)
    if len(text) >= 3 and text[-3] in "+-" and text[-2:].isdigit():
        text += ":00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def load_arms(runs_path: Path) -> list[dict]:
    """Latest record per arm_key, in first-seen file order.

    A killed-then-resumed arm appends a partial record and later a completed
    one under the same key; the newest record is the arm's state. A malformed
    line or a record without arm_key is a loud ValueError — a silently
    skipped record would let a broken arm pass unvalidated.
    """
    latest: dict[str, dict] = {}
    with open(runs_path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{runs_path}: line {lineno}: malformed JSON: {exc}"
                ) from exc
            key = rec.get("arm_key")
            if not key:
                raise ValueError(
                    f"{runs_path}: line {lineno}: record has no arm_key — "
                    "cannot attribute it to an arm"
                )
            latest[str(key)] = rec
    return list(latest.values())


def chunked(items: list, n: int) -> list:
    items = list(items)
    return [items[i:i + n] for i in range(0, len(items), n)]


def fetch_chunk_rows(user_ids: list[str], psql) -> list[dict]:
    """ONE read for a whole chunk: json_agg(json_build_object(...)) over
    llm_audit for all chunk user_ids, ordered created_at, ctid in a subquery
    (ctid breaks created_at ties so per-arm ordering is the row order
    audit_db's ORDER BY created_at yields in practice). Placeholders are
    generated for exactly the chunk's ids and passed as parameters — no value
    interpolation here; audit_db.run_psql's quoting is the injection
    boundary. Returns the parsed row list ([] for no rows / NULL aggregate).
    """
    if not user_ids:
        return []
    placeholders = ", ".join(["%s"] * len(user_ids))
    obj = ", ".join(f"'{f}', {f}" for f in BULK_FIELDS)
    sql = (
        "SELECT json_agg(sub.row_json) FROM ("
        f"SELECT json_build_object({obj}) AS row_json "
        "FROM llm_audit "
        f"WHERE user_id IN ({placeholders}) "
        "ORDER BY created_at, ctid) sub;"
    )
    out = psql(sql, list(user_ids)).strip()
    if not out:
        return []
    rows = json.loads(out)
    return rows if rows else []


class BulkAudit:
    """Duck-typed audit module over one chunked llm_audit read.

    Implements the contract scoring.gate_report injects: list_calls /
    get_field / call_metrics, plus NoRowsError/AmbiguousQueryError resolved
    by attribute name. Semantics mirror library/audit_db.py exactly — rows
    in (created_at, ctid) fetch order, nth is the 0-indexed occurrence per
    agent_id, get_field refuses ambiguity without nth and raises NoRowsError
    on zero rows or out-of-range nth, NULL response_text comes back as ""
    (psql's empty output for a NULL column), call_metrics pairs token/error
    rows with get_field's nth. Every method applies the inclusive
    after/before window on top of the fetched rows, so gate_report's window
    threading lands on the same rows a direct audit_db read would return.
    """

    NoRowsError = audit_db.NoRowsError
    AmbiguousQueryError = audit_db.AmbiguousQueryError

    def __init__(self, rows: list[dict]):
        self._rows = [(_parse_ts(r["created_at"]), r) for r in rows]

    def _window(self, user_id: str, after: str | None,
                before: str | None) -> list[dict]:
        lo = _parse_ts(after) if after is not None else None
        hi = _parse_ts(before) if before is not None else None
        out = []
        for ts, row in self._rows:
            if row.get("user_id") != user_id:
                continue
            if lo is not None and ts < lo:
                continue
            if hi is not None and ts > hi:
                continue
            out.append(row)
        return out

    def window_rows(self, user_id: str, after: str | None,
                    before: str | None) -> list[dict]:
        return self._window(user_id, after, before)

    def list_calls(self, user_id: str, *, after: str | None = None,
                   before: str | None = None) -> list:
        return [
            audit_db.CallRow(
                created_at=row["created_at"],
                agent_id=row["agent_id"],
                provider=row.get("provider"),
                flow=row.get("flow"),
            )
            for row in self._window(user_id, after, before)
        ]

    def get_field(self, user_id: str, agent_id: str, field: str, *,
                  after: str | None = None, before: str | None = None,
                  nth: int | None = None):
        if field not in audit_db.VALID_FIELDS:
            raise ValueError(
                f"unknown field {field!r}; valid: {sorted(audit_db.VALID_FIELDS)}"
            )
        matching = [r for r in self._window(user_id, after, before)
                    if r["agent_id"] == agent_id]
        stamps = [r["created_at"] for r in matching]
        window_note = " in the given window" if (after or before) else ""
        if not stamps:
            raise self.NoRowsError(
                f"no llm_audit rows for user_id={user_id} agent_id={agent_id}"
                f"{window_note}"
            )
        if nth is None:
            if len(stamps) > 1:
                raise self.AmbiguousQueryError(
                    f"{len(stamps)} '{agent_id}' rows match "
                    f"user_id={user_id}{window_note} — refusing to pick one "
                    f"silently. created_at values: {stamps}. Narrow with "
                    "after/before or nth (0-indexed)."
                )
            offset = 0
        else:
            if nth < 0 or nth >= len(stamps):
                raise self.NoRowsError(
                    f"nth={nth} out of range: {len(stamps)} '{agent_id}' rows "
                    f"match user_id={user_id} (created_at: {stamps})"
                )
            offset = nth
        value = matching[offset].get(field)
        return "" if value is None else str(value)

    def call_metrics(self, user_id: str, *, after: str | None = None,
                     before: str | None = None) -> list:
        seen: dict[str, int] = {}
        out = []
        for row in self._window(user_id, after, before):
            agent = row["agent_id"]
            nth = seen.get(agent, 0)
            seen[agent] = nth + 1
            tokens = row.get("output_tokens")
            out.append(audit_db.CallMetrics(
                agent_id=agent,
                nth=nth,
                output_tokens=int(tokens) if tokens is not None else None,
                error=row.get("error") or None,
                constraint_status=row.get("constraint_status") or None,
            ))
        return out


def gate_arms(arms: list[dict], *, chunk_size: int = DEFAULT_CHUNK_SIZE,
              psql=None, gate=None) -> dict:
    """Validate every arm: completed status + gate_report over its exact
    inclusive [triggered_at, finished_at] window. `psql` and `gate` are
    injectable for tests (default to audit_db.run_psql and
    scoring.gate_report). Returns the report dict; report["ok"] is the exit
    predicate — True only when every arm completed and every gate passed.
    """
    psql = audit_db.run_psql if psql is None else psql
    gate = scoring.gate_report if gate is None else gate
    arms = list(arms)
    report: dict = {
        "tool": "room_contract_gates",
        "chunk_size": chunk_size,
        "arms_total": len(arms),
        "arms": [],
        "failures": [],
    }
    if not arms:
        report["failures"].append(
            "runs file has no arms — nothing to validate; a vacuous pass is "
            "refused"
        )
        report["ok"] = False
        return report

    gateable: list[tuple[dict, dict]] = []
    for arm in arms:
        entry = {
            "arm_key": arm.get("arm_key"),
            "user_id": arm.get("user_id"),
            "status": arm.get("status"),
            "triggered_at": arm.get("triggered_at"),
            "finished_at": arm.get("finished_at"),
            "audit_rows_in_window": 0,
            "gate": None,
        }
        report["arms"].append(entry)
        if arm.get("status") != "completed":
            msg = (f"arm {entry['arm_key']}: status {arm.get('status')!r} "
                   f"(error_message={arm.get('error_message')!r}) — not "
                   "completed; acceptance requires every arm completed")
            entry["error"] = msg
            report["failures"].append(msg)
            continue
        if not arm.get("triggered_at") or not arm.get("finished_at"):
            msg = (f"arm {entry['arm_key']}: completed but missing "
                   "triggered_at/finished_at — the audit window is unknown, "
                   "refusing to guess")
            entry["error"] = msg
            report["failures"].append(msg)
            continue
        gateable.append((arm, entry))

    ok = not report["failures"]
    for chunk in chunked(gateable, chunk_size):
        user_ids = [arm["user_id"] for arm, _ in chunk]
        try:
            rows = fetch_chunk_rows(user_ids, psql)
        except Exception as exc:  # noqa: BLE001 — a chunk read failure fails the run
            msg = (f"chunk read failed for {len(user_ids)} arm(s) "
                   f"({type(exc).__name__}: {exc})")
            report["failures"].append(msg)
            ok = False
            for _, entry in chunk:
                entry["error"] = msg
            continue
        bulk = BulkAudit(rows)
        for arm, entry in chunk:
            after = arm["triggered_at"]
            before = arm["finished_at"]
            entry["audit_rows_in_window"] = len(
                bulk.window_rows(arm["user_id"], after, before))
            rep = gate(arm["user_id"], audit_module=bulk,
                       after=after, before=before)
            entry["gate"] = {
                "ok": rep.ok,
                "findings": [
                    {"user_id": f.user_id, "agent_id": f.agent_id,
                     "kind": f.kind, "detail": f.detail}
                    for f in rep.findings
                ],
                "stances": dict(rep.stances),
            }
            if not rep.ok:
                ok = False
                report["failures"].append(
                    f"arm {arm['arm_key']}: gate failed with "
                    f"{len(rep.findings)} finding(s)"
                )
                for f in rep.findings:
                    report["failures"].append(
                        f"  - {f.kind} [{f.agent_id}] {f.detail}"
                    )

    report["ok"] = ok
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="room_contract_gates",
        description="CR265/CR266 acceptance validator: every arm completed and "
                    "every convene passing scoring.gate_report over its exact "
                    "triggered_at/finished_at window. No skip option exists.",
    )
    parser.add_argument("--runs", required=True, type=Path,
                        help="runs_<bench>.jsonl from library/runner.py")
    parser.add_argument("--out", required=True, type=Path,
                        help="report JSON path (written on pass and fail)")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE,
                        help="arms per single llm_audit read (default 25)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.chunk_size < 1:
        raise SystemExit(f"--chunk-size must be >= 1, got {args.chunk_size}")
    try:
        arms = load_arms(args.runs)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"error: {exc}") from exc
    report = gate_arms(arms, chunk_size=args.chunk_size)
    report["runs"] = str(args.runs)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    n_gated = sum(1 for a in report["arms"] if a["gate"] is not None)
    n_ok = sum(1 for a in report["arms"]
               if a["gate"] is not None and a["gate"]["ok"])
    print(f"arms: {report['arms_total']}  gate-ok: {n_ok}/{n_gated}  "
          f"failures: {len(report['failures'])}  report: {args.out}")
    for failure in report["failures"]:
        print(f"  FAIL {failure}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
