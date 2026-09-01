"""CR217 — per-agent LLM call profile for one backtest batch, from `llm_audit`.

`room_runs.duration_ms` gives a convene's wall clock, which mixes LLM time with
EDGAR/price fetching and orchestration. This splits out the LLM half per agent:
how long each of the twelve agents' calls took, how many tokens they produced,
and which provider actually served them.

That last column is the point, not a decoration. `_active_provider_name` falls
through to the normal preference order when a forced provider is not registered —
deliberately, so a typo'd env var cannot 500 a live flow — so `LLM_FORCE_PROVIDER=glm`
with no `GLM_BASE_URL` silently runs the INCUMBENT. `llm_audit.provider` is NOT NULL
and written per call, which makes it the only ground truth for which model actually
answered. A head-to-head that trusts the env var it set instead of this column can
score a model against itself and report the null as a finding.

Tokens matter as much as seconds here. A reasoning model is not necessarily slower
per token — it emits far more of them, most of them invisible — and the two
explanations imply completely different fixes, so the report carries both.

Usage (inside the container, which has DATABASE_URL):
    python scripts/agent_call_profile.py --batch-id r70-outcome-2
    python scripts/agent_call_profile.py --batch-id cr217-glm-1 --out /backtest_results/profile.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.db.session import get_session  # noqa: E402

# Rows are attributed to a batch through its own runs, never through a time
# window: the container serves live traffic while a sweep runs, and a window
# would fold that traffic into the batch's numbers.
_SQL = text(
    """
    WITH batch_users AS (
        SELECT DISTINCT r.user_id, min(r.started_at) AS t0, max(r.finished_at) AS t1
        FROM room_runs r
        JOIN backtest_run_index i ON i.room_run_id = r.id
        WHERE i.batch_id = :batch_id
        GROUP BY r.user_id
    )
    SELECT a.agent_id,
           a.provider,
           count(*)                                              AS calls,
           avg(a.latency_ms) / 1000.0                            AS mean_s,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY a.latency_ms) / 1000.0 AS median_s,
           percentile_cont(0.9) WITHIN GROUP (ORDER BY a.latency_ms) / 1000.0 AS p90_s,
           max(a.latency_ms) / 1000.0                            AS max_s,
           avg(a.input_tokens)                                   AS mean_in,
           avg(a.output_tokens)                                  AS mean_out,
           count(*) FILTER (WHERE a.error IS NOT NULL)           AS errors,
           count(*) FILTER (WHERE coalesce(a.response_text, '') = '') AS empty_responses
    FROM llm_audit a
    JOIN batch_users b ON b.user_id = a.user_id
    WHERE a.created_at >= b.t0 - interval '10 minutes'
      AND a.created_at <= coalesce(b.t1, now()) + interval '10 minutes'
    GROUP BY a.agent_id, a.provider
    ORDER BY mean_s DESC NULLS LAST
    """
)


def fmt(v, nd=1):
    return "—" if v is None else f"{float(v):.{nd}f}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-id", required=True)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    with get_session() as s:
        rows = s.execute(_SQL, {"batch_id": args.batch_id}).mappings().all()

    if not rows:
        raise SystemExit(
            f"no llm_audit rows attributable to batch {args.batch_id!r} — either the "
            "batch has not run, or its runs are not in backtest_run_index"
        )

    providers = sorted({r["provider"] for r in rows})
    L = [
        f"# Per-agent LLM call profile — batch `{args.batch_id}`",
        "",
        f"Provider(s) that actually served this batch, from `llm_audit.provider`: "
        f"**{', '.join(providers)}**",
        "",
    ]
    if len(providers) > 1:
        L += [
            "> **More than one provider served this batch.** Any per-agent number below "
            "mixes them, and a model comparison drawn from it is not valid. This usually "
            "means the arm was started or restarted without its provider override.",
            "",
        ]

    total_calls = sum(r["calls"] for r in rows)
    total_s = sum((r["mean_s"] or 0) * r["calls"] for r in rows)
    L += [
        "| agent | provider | calls | mean | median | p90 | max | mean in | mean out | errors | empty |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        L.append(
            f"| {r['agent_id'] or '—'} | {r['provider']} | {r['calls']} | "
            f"{fmt(r['mean_s'])}s | {fmt(r['median_s'])}s | {fmt(r['p90_s'])}s | "
            f"{fmt(r['max_s'])}s | {fmt(r['mean_in'], 0)} | {fmt(r['mean_out'], 0)} | "
            f"{r['errors']} | {r['empty_responses']} |"
        )
    L += [
        "",
        f"- Calls: **{total_calls}**",
        f"- Summed LLM time across all agents: **{total_s / 3600:.2f}h** "
        f"(mean {total_s / max(total_calls, 1):.1f}s per call)",
        "",
        "`empty` counts calls whose `response_text` came back blank. A reasoning model "
        "whose decode budget sits below its thinking preamble returns exactly this, and "
        "the Room turns an empty turn into a DEF059 fail-safe PASS — which reads as the "
        "model declining to trade rather than as a starved decode budget (CR130, CR211, "
        "CR217). A non-zero count here invalidates the arm's action mix.",
    ]

    text_out = "\n".join(L) + "\n"
    if args.out:
        args.out.write_text(text_out)
        print(f"wrote {args.out}")
    else:
        print(text_out)


if __name__ == "__main__":
    main()
