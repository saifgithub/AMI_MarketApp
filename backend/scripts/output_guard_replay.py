#!/usr/bin/env python3
"""CR271 - replay the output text guard over recorded LLM responses.

Measures the hit rate BEFORE anyone flips `OUTPUT_GUARD_MODE=enforce`: reads
`llm_audit.response_text` (read-only) for the flows that feed user-visible
surfaces, runs `app.services.output_guard.check` in `enforce` mode over each,
and prints hit counts per rule and per surface/flow plus a sample of matched
spans. It never prints a full response and never writes to the database.

Surface mapping (the same labels the live seams log):
    room -> room_turn, room_pm -> room_verdict, one_on_one -> one_on_one,
    concierge_floor -> concierge, coach_chat -> brief

Usage (must be a Postgres URL; run it on melehost, inside ami_api_alpha):
    DATABASE_URL=postgresql://... python -m scripts.output_guard_replay \
        --since 2026-11-01T00:00:00Z --flow room --flow one_on_one
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from typing import Any, Iterable

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.output_guard import check  # noqa: E402

FLOW_TO_SURFACE = {
    "room": "room_turn",
    "room_pm": "room_verdict",
    "one_on_one": "one_on_one",
    "concierge_floor": "concierge",
    "coach_chat": "brief",
}
SAMPLES_PER_RULE = 8


def summarize(
    rows: Iterable[dict[str, Any]], *, samples_per_rule: int = SAMPLES_PER_RULE
) -> dict[str, Any]:
    """Pure counting core. Each row needs `flow` and `response_text`; `agent_id`
    is optional. Rows on a flow outside FLOW_TO_SURFACE are skipped; an empty
    response is scanned but cannot hit."""
    scanned: Counter[str] = Counter()
    rows_with_hit: Counter[str] = Counter()
    by_rule: Counter[str] = Counter()
    by_surface_rule: dict[str, Counter[str]] = defaultdict(Counter)
    samples: dict[str, list[dict[str, str]]] = defaultdict(list)
    withheld_rows = 0
    total = 0
    for r in rows:
        flow = r.get("flow")
        surface = FLOW_TO_SURFACE.get(flow)
        if surface is None:
            continue
        total += 1
        scanned[flow] += 1
        res = check(r.get("response_text"), surface=surface, mode="enforce")
        if not res.hits:
            continue
        rows_with_hit[flow] += 1
        if res.withhold:
            withheld_rows += 1
        for h in res.hits:
            by_rule[h.rule] += 1
            by_surface_rule[surface][h.rule] += 1
            if len(samples[h.rule]) < samples_per_rule:
                samples[h.rule].append({
                    "flow": flow,
                    "agent_id": str(r.get("agent_id")),
                    "span": h.span[:80],
                })
    return {
        "rows_scanned": total,
        "rows_that_would_be_withheld": withheld_rows,
        "scanned_per_flow": dict(scanned),
        "rows_with_any_hit_per_flow": dict(rows_with_hit),
        "hits_per_rule": dict(by_rule),
        "hits_per_surface_and_rule": {k: dict(v) for k, v in by_surface_rule.items()},
        "samples": dict(samples),
    }


def require_postgres(url: str) -> None:
    if not url.startswith(("postgresql://", "postgresql+psycopg2://", "postgres://")):
        raise SystemExit(
            "DATABASE_URL must be a Postgres URL (got a different scheme); "
            "this tool reads llm_audit on Alpha and does not run on sqlite."
        )


def _from_db(url: str, since: str | None, flows: list[str]) -> Iterable[dict[str, Any]]:
    from sqlalchemy import create_engine, text

    require_postgres(url)
    engine = create_engine(
        url.replace("postgres://", "postgresql://", 1),
        connect_args={"options": "-c default_transaction_read_only=on"},
    )
    sql = (
        "SELECT flow, agent_id, response_text FROM llm_audit "
        "WHERE flow = ANY(:flows) AND response_text IS NOT NULL"
    )
    params: dict[str, Any] = {"flows": flows}
    if since:
        sql += " AND created_at >= :since"
        params["since"] = since
    with engine.connect() as conn:
        for row in conn.execution_options(stream_results=True).execute(text(sql), params):
            yield {"flow": row[0], "agent_id": row[1], "response_text": row[2]}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--since", help="ISO timestamp; only rows created at/after it")
    ap.add_argument(
        "--flow", action="append", choices=sorted(FLOW_TO_SURFACE),
        help="llm_audit flow to scan (repeatable); default: all user-visible flows",
    )
    ap.add_argument("--json", action="store_true", help="print JSON instead of text")
    args = ap.parse_args()

    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise SystemExit("set DATABASE_URL to the Alpha Postgres URL")
    flows = args.flow or sorted(FLOW_TO_SURFACE)
    out = summarize(_from_db(url, args.since, flows))
    if args.json:
        print(json.dumps(out, indent=2))
        return
    print(f"rows scanned: {out['rows_scanned']}  "
          f"would be withheld in enforce: {out['rows_that_would_be_withheld']}")
    print("scanned per flow:", out["scanned_per_flow"])
    print("rows with any hit per flow:", out["rows_with_any_hit_per_flow"])
    print("hits per rule:", out["hits_per_rule"])
    for surface, rules in sorted(out["hits_per_surface_and_rule"].items()):
        print(f"  {surface}: {rules}")
    for rule, items in sorted(out["samples"].items()):
        print(f"samples [{rule}]:")
        for it in items:
            print(f"  {it['flow']}/{it['agent_id']}: {it['span']!r}")


if __name__ == "__main__":
    main()
