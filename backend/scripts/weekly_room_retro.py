"""CR157 weekly Room retrospective — score every due LIVE Room verdict
against realized forward returns, from the database plus the existing
price-history read-through path. The live-data twin of CR164's
`backtest_report.py`, sharing its scoring helpers so retro numbers and
backtest numbers stay directly comparable by construction.

Selection (a "due" run): room_runs with status='completed', verdict
non-null and bucketable (APPROVE/PASS/REJECT/MODIFY), NOT the DEF059
LLM-outage fail-safe (DEF336: an outage PASS measures provider uptime,
not judgement), NOT indexed in backtest_run_index, owner passing the
synthetic-user exclusion (DEF403: `app.services.admin_analytics.is_real_user()`,
the one canonical definition of the CR051 rule — this script runs inside
`ami_api_alpha` so it imports it rather than hand-copying it), and
triggered_at aged >= --min-age-days (default 7) so the 1w horizon is
realizable.

Scoring — CR164 conventions, imported not reimplemented:
  - as_of = triggered_at's UTC calendar date; entry = adj_close at the
    last stored trading date <= as_of (the convene-time reference price;
    honest limitation: prior close, not the intraday quote).
  - +5/+20 TRADING-day returns, SPY excess, target/stop first-touch over
    20 forward bars gated per leg on level_provenance != 'ami_default'.
    Missing bars ⇒ unscoreable-and-counted, never fabricated (CR040).
  - Every rate is partitioned by llm_audit.prompt_version recovered per
    run via the user_id + wall-clock-window join (backtest_prompt_scan.py
    precedent); zero correlated rows ⇒ 'unversioned', mixed versions ⇒
    'mixed:…' — never silently pooled across prompt generations.
  - Per-agent scorecard from transcript stance/conviction vs 4w excess;
    a null stance is a separate gutter, NEVER neutral (CR106 T-SUM11);
    rates carry Wilson 95% CIs — confidence, not verdicts (small-n).

E1–E5 cause-class labeling of misses is deliberately NOT here: the batch
emits a misses digest (misses_<week>.jsonl + a report section) for a
Claude session to label; no LLM call runs unattended.

READ-ONLY on product tables by contract: the ONLY write path is the bar
refresh through app.services.price_history.get_daily_series (its own
read-through table), skippable with --no-refresh. This script never
INSERTs/UPDATEs room_runs, journal_entries (outcome stays user-set), or
any other product table — scores are an internal quality signal, never
user-facing. Outputs land under --out (report_<ISO-week>.md,
scored_<ISO-week>.jsonl, misses_<ISO-week>.jsonl; rerunning the same
week overwrites its own files — idempotent, never duplicating).

An empty week is a legitimate state: a loud "nothing due" and exit 0
(unlike backtest_report's exit-1 batch contract, where an empty batch is
a broken sweep).

Usage (inside the alpha container):
    python -m scripts.weekly_room_retro --out /backtest_results/weekly_retro
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db import get_session
from app.db.models import BacktestRunIndexRow, LLMAuditRow, RoomRunRow, SimTradeRow, User
from app.services.admin_analytics import is_real_user
from app.services.room_runner import init_schema, is_llm_outage_verdict
from scripts.backtest_report import (
    ACTIONS,
    entry_and_forward,
    fnum,
    load_series,
    mean,
    ret_at,
    scan_hits,
)

BENCHMARK = "SPY"
# backtest_prompt_scan.py:62 — the llm_audit correlation window either side of
# the run's started/finished wall-clock span.
CORRELATION_WINDOW_S = 60
# History depth for the pre-scoring bar refresh: oldest scoreable entry bars
# plus the 20-trading-day forward window, with margin.
REFRESH_MIN_DAYS = 120


def _as_utc(dt: datetime | None) -> datetime | None:
    """Naive stamps (sqlite) are UTC by storage convention."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def is_synthetic_user(user: User) -> bool:
    """The CR051 real-vs-synthetic rule, inverted.

    DEF403 — this used to reimplement CR035/seed-burst checks by hand and,
    because it runs inside `ami_api_alpha` (the container `app` is
    importable from), had no excuse not to import the canonical
    `admin_analytics.is_real_user()` instead. The hand-copy had already
    drifted: it never carried the 12 CR125/DEF227-229 probe-id exclusions
    the ORM copies got, so this script's synthetic-user accounting silently
    undercounted for as long as that copy existed.
    """
    return not is_real_user(user)


def select_due_runs(
    pairs: list[tuple[RoomRunRow, User]],
    backtest_ids: set,
    *,
    now: datetime,
    min_age_days: int,
) -> tuple[list[tuple[RoomRunRow, User]], Counter]:
    """Apply every exclusion, counting each loudly. Pure — unit-testable."""
    cutoff = now - timedelta(days=min_age_days)
    counts: Counter = Counter()
    due: list[tuple[RoomRunRow, User]] = []
    for run, user in pairs:
        if run.status != "completed":
            counts["non_completed"] += 1
            continue
        if run.verdict is None:
            counts["null_verdict"] += 1
            continue
        if run.id in backtest_ids:
            counts["backtest_run"] += 1
            continue
        if is_synthetic_user(user):
            counts["synthetic_user"] += 1
            continue
        if run.verdict.get("action") not in ACTIONS:
            counts["other_action"] += 1
            continue
        # DEF336 — the DEF059 outage fail-safe is a completed PASS whose shape
        # is indistinguishable from a reasoned PASS; scoring it grades uptime.
        if is_llm_outage_verdict(run.verdict):
            counts["llm_outage"] += 1
            continue
        triggered = _as_utc(run.triggered_at)
        if triggered is None or triggered > cutoff:
            counts["too_young"] += 1
            continue
        due.append((run, user))
    due.sort(key=lambda p: (_as_utc(p[0].triggered_at), p[0].ticker))
    return due, counts


def prompt_partition(session, run: RoomRunRow) -> str:
    """Which prompt generation produced this run — backtest_prompt_scan.py's
    user_id + wall-clock-window join. Zero correlated versioned rows is
    'unversioned' (CR158: NULL means unversioned, never version zero);
    disagreeing versions are 'mixed:…' — either way, never silently pooled."""
    started, finished = _as_utc(run.started_at), _as_utc(run.finished_at)
    if started is None or finished is None:
        return "unversioned"
    lo = started - timedelta(seconds=CORRELATION_WINDOW_S)
    hi = finished + timedelta(seconds=CORRELATION_WINDOW_S)
    versions = sorted({
        v for v in session.execute(
            select(LLMAuditRow.prompt_version).where(
                LLMAuditRow.user_id == run.user_id,
                LLMAuditRow.created_at >= lo,
                LLMAuditRow.created_at <= hi,
            )
        ).scalars()
        if v is not None
    })
    if not versions:
        return "unversioned"
    if len(versions) == 1:
        return versions[0]
    return "mixed:" + "+".join(versions)


def final_stances(transcript: list | None) -> dict[str, dict]:
    """Per agent, the LAST non-null stated stance in the transcript (the
    agent's final position across rounds). An agent that spoke but never
    stated one lands in the null gutter — null NEVER means neutral."""
    out: dict[str, dict] = {}
    for m in transcript or []:
        if not isinstance(m, dict) or m.get("role", "agent") != "agent":
            continue
        aid = m.get("agent_id")
        if not aid:
            continue
        out.setdefault(aid, {"stance": None, "conviction": None})
        if m.get("stance") is not None:
            out[aid] = {"stance": m.get("stance"), "conviction": m.get("conviction")}
    return out


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """Wilson score 95% interval — the small-n honesty device."""
    if n <= 0:
        return None
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def _fci(ci: tuple[float, float] | None) -> str:
    return "—" if ci is None else f"[{ci[0] * 100:.0f}%, {ci[1] * 100:.0f}%]"


@dataclass
class ScoredRun:
    run_id: str
    user_id: str
    ticker: str
    as_of: date
    action: str
    partition: str
    mandate_version: int
    entry: float | None
    r5: float | None
    r20: float | None
    excess5: float | None
    excess20: float | None
    target_hit: bool | None = None
    stop_hit: bool | None = None
    first_touch: str | None = None
    stances: dict = field(default_factory=dict)
    acted_trades: int = 0
    miss_kinds: list = field(default_factory=list)


def classify_miss(s: ScoredRun) -> list[str]:
    """Machine-flagged candidate misses for the HUMAN E1–E5 post-mortem.
    Directional only — the labeling of WHY (CR143 taxonomy) never runs
    unattended."""
    kinds: list[str] = []
    if s.action in ("APPROVE", "MODIFY"):
        if s.excess20 is not None and s.excess20 < 0:
            kinds.append("approve_negative_4w_excess")
        if s.first_touch == "stop_first":
            kinds.append("stop_hit_first")
    elif s.action in ("PASS", "REJECT"):
        if s.excess20 is not None and s.excess20 > 0:
            kinds.append("pass_missed_4w_upside")
    return kinds


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=Path("./retro_reports"),
                    help="output dir; on melehost pass /backtest_results/weekly_retro "
                         "(the rw mount) — ./retro_reports is NOT repo-gitignored")
    ap.add_argument("--stamp", default=date.today().isoformat(),
                    help="report date (ISO); outputs are keyed by its ISO week")
    ap.add_argument("--min-age-days", type=int, default=7)
    ap.add_argument("--no-refresh", action="store_true",
                    help="skip the price_history bar refresh (the script's only "
                         "write path) and score against stored bars only")
    args = ap.parse_args(argv)

    try:
        stamp = date.fromisoformat(args.stamp)
    except ValueError:
        raise SystemExit(f"FATAL: --stamp must be an ISO date, got {args.stamp!r}")
    iso = stamp.isocalendar()
    week = f"{iso.year}-W{iso.week:02d}"
    now = datetime.now(timezone.utc)

    init_schema()

    with get_session() as session:
        pairs = [
            (run, user)
            for run, user in session.execute(
                select(RoomRunRow, User).join(User, User.id == RoomRunRow.user_id)
            ).all()
        ]
        backtest_ids = set(
            session.execute(select(BacktestRunIndexRow.room_run_id)).scalars()
        )
        due, counts = select_due_runs(
            pairs, backtest_ids, now=now, min_age_days=args.min_age_days,
        )
        accounting = (
            f"room runs seen: {len(pairs)} — excluded: "
            f"non-completed {counts['non_completed']}, "
            f"null verdict {counts['null_verdict']}, "
            f"backtest-indexed {counts['backtest_run']}, "
            f"synthetic user {counts['synthetic_user']}, "
            f"non-bucket action {counts['other_action']}, "
            f"LLM-outage fail-safe {counts['llm_outage']} (DEF336), "
            f"younger than {args.min_age_days}d {counts['too_young']}"
        )
        print(f"[retro {week}] {accounting}", flush=True)

        if not due:
            print(
                f"[retro {week}] NOTHING DUE — no completed, scoreable room runs "
                "in window. A quiet alpha week is a legitimate state; no report "
                "written. (exit 0)",
                flush=True,
            )
            return 0

        tickers = sorted({run.ticker.upper() for run, _ in due} | {BENCHMARK})
        if args.no_refresh:
            print(f"[retro {week}] --no-refresh: scoring against stored bars only",
                  flush=True)

    # The ONLY write path — price_history's own read-through table, outside
    # the scoring session. Everything below is pure SELECT.
    if not args.no_refresh:
        from app.services.price_history import get_daily_series

        get_daily_series(tickers, min_days=REFRESH_MIN_DAYS, now=now)

    scored: list[ScoredRun] = []
    with get_session() as session:
        series_cache: dict[str, list] = {}

        def series(t: str) -> list:
            t = t.upper()
            if t not in series_cache:
                series_cache[t] = load_series(session, t)
            return series_cache[t]

        if not series(BENCHMARK):
            print(f"WARNING: no real {BENCHMARK} rows in price_history_daily — "
                  "all excess returns will be unscoreable", flush=True)

        for run, _user in due:
            v = run.verdict
            as_of = _as_utc(run.triggered_at).date()
            entry, fwd = entry_and_forward(series(run.ticker), as_of)
            spy_entry, spy_fwd = entry_and_forward(series(BENCHMARK), as_of)
            r5, r20 = ret_at(entry, fwd, 5), ret_at(entry, fwd, 20)
            spy5, spy20 = ret_at(spy_entry, spy_fwd, 5), ret_at(spy_entry, spy_fwd, 20)

            s = ScoredRun(
                run_id=str(run.id), user_id=str(run.user_id),
                ticker=run.ticker.upper(), as_of=as_of, action=v["action"],
                partition=prompt_partition(session, run),
                mandate_version=run.mandate_version,
                entry=entry, r5=r5, r20=r20,
                excess5=None if (r5 is None or spy5 is None) else r5 - spy5,
                excess20=None if (r20 is None or spy20 is None) else r20 - spy20,
                stances=final_stances(run.transcript),
            )

            # Target/stop first-touch — per-leg provenance gate exactly as
            # backtest_report.py: an 'ami_default' or absent provenance means
            # AMI minted the level; scoring it grades a default, not a decision.
            prov = v.get("level_provenance") or {}
            if (v["action"] in ("APPROVE", "MODIFY")
                    and v.get("entry") is not None
                    and v.get("target") is not None
                    and v.get("stop") is not None):
                want_target = prov.get("target") not in (None, "ami_default")
                want_stop = prov.get("stop") not in (None, "ami_default")
                if want_target or want_stop:
                    t_hit, s_hit, touch, _notes = scan_hits(
                        fwd,
                        float(v["target"]) if want_target else None,
                        float(v["stop"]) if want_stop else None,
                    )
                    s.target_hit, s.stop_hit, s.first_touch = t_hit, s_hit, touch

            s.acted_trades = len(session.execute(
                select(SimTradeRow.id).where(SimTradeRow.verdict_ref == run.id)
            ).scalars().all())
            s.miss_kinds = classify_miss(s)
            scored.append(s)

    # ---- render (DB no longer needed) -------------------------------------
    partitions = sorted({s.partition for s in scored})
    L: list[str] = [
        f"# CR157 weekly Room retrospective — {week}",
        "",
        f"Stamp {args.stamp} · min age {args.min_age_days}d · "
        f"{len(scored)} scored runs over {len({s.as_of for s in scored})} "
        f"as-of dates, {len({s.user_id for s in scored})} users.",
        "",
        "INTERNAL quality signal only — never user-facing, never written back "
        "to journal outcomes. Reference price = last stored adj close <= the "
        "convene UTC date (CR164 entry convention; prior close, not the "
        "intraday convene quote). Small-n honesty: intervals below are "
        "confidence, not verdicts.",
        "",
        "## Run accounting",
        "",
        f"- {accounting}",
    ]

    def bucket_table(runs: list[ScoredRun]) -> list[str]:
        rows = ["| bucket | horizon | n | mean raw | n | mean excess vs SPY | "
                "positive-excess rate (95% CI) |",
                "|---|---|---|---|---|---|---|"]
        for a in ACTIONS:
            in_bucket = [s for s in runs if s.action == a]
            for hz, raw_attr, ex_attr in (("1w", "r5", "excess5"),
                                          ("4w", "r20", "excess20")):
                raws = [getattr(s, raw_attr) for s in in_bucket
                        if getattr(s, raw_attr) is not None]
                exs = [getattr(s, ex_attr) for s in in_bucket
                       if getattr(s, ex_attr) is not None]
                pos = sum(1 for x in exs if x > 0)
                ci = wilson_ci(pos, len(exs))
                rows.append(
                    f"| {a} | {hz} | {len(raws)} | {fnum(mean(raws))} "
                    f"| {len(exs)} | {fnum(mean(exs))} "
                    f"| {pos}/{len(exs)} {_fci(ci)} |"
                )
        return rows

    def scorecard(runs: list[ScoredRun]) -> list[str]:
        per_agent: dict[str, dict] = {}
        for s in runs:
            if s.excess20 is None:
                continue
            for aid, st in s.stances.items():
                a = per_agent.setdefault(aid, {
                    "n": 0, "correct": 0, "neutral": 0, "null": 0,
                    "conv": Counter(), "conv_correct": Counter(),
                })
                stance = st.get("stance")
                if stance is None:
                    a["null"] += 1
                    continue
                if stance == "neutral":
                    a["neutral"] += 1
                    continue
                correct = (stance == "for" and s.excess20 > 0) or (
                    stance == "against" and s.excess20 < 0)
                a["n"] += 1
                a["correct"] += int(correct)
                conv = st.get("conviction") or "unstated"
                a["conv"][conv] += 1
                a["conv_correct"][conv] += int(correct)
        if not per_agent:
            return ["No agent stances scoreable at 4w this week."]
        rows = ["| agent | directional n | correct | rate (95% CI) | by conviction "
                "| neutral | null-stance gutter |",
                "|---|---|---|---|---|---|---|"]
        for aid in sorted(per_agent):
            a = per_agent[aid]
            ci = wilson_ci(a["correct"], a["n"])
            rate = "—" if a["n"] == 0 else f"{a['correct']}/{a['n']} {_fci(ci)}"
            conv = ", ".join(
                f"{c}: {a['conv_correct'][c]}/{a['conv'][c]}"
                for c in ("high", "medium", "low", "unstated") if a["conv"][c]
            ) or "—"
            rows.append(f"| {aid} | {a['n']} | {a['correct']} | {rate} "
                        f"| {conv} | {a['neutral']} | {a['null']} |")
        rows.append("")
        rows.append("Null stance = the agent stated no position (CR106 T-SUM11: "
                    "never counted as neutral, never in the rate).")
        return rows

    for part in partitions:
        runs = [s for s in scored if s.partition == part]
        mandates = Counter(s.mandate_version for s in runs)
        L += [
            "",
            f"## Partition: prompt_version `{part}` — {len(runs)} runs",
            "",
            "Rates below are NEVER pooled across prompt generations "
            "(CR158/CR153 lesson). Mandate-version mix in this partition: "
            + ", ".join(f"v{m}: {c}" for m, c in sorted(mandates.items()))
            + (" — mixed mandate regimes; do not headline-pool." if len(mandates) > 1 else "."),
            "",
        ]
        L += bucket_table(runs)
        touch = Counter(s.first_touch for s in runs if s.first_touch is not None)
        eligible = sum(1 for s in runs if s.first_touch is not None)
        L += [
            "",
            f"Target/stop first-touch (20 trading days, provenance-gated): "
            f"{eligible} evaluated — "
            + (", ".join(f"{k}: {v}" for k, v in sorted(touch.items())) or "none"),
            "",
            "### Per-agent scorecard (final stated stance vs 4w excess)",
            "",
        ]
        L += scorecard(runs)

    acted = [s for s in scored if s.acted_trades > 0]
    L += [
        "",
        "## Did the user act on it? (side table — behavioral, not quality)",
        "",
        f"- Runs with >=1 sim trade referencing the verdict "
        f"(`sim_trades.verdict_ref`): {len(acted)}/{len(scored)}",
        "- Rooms the user never acted on still score: the conclusion is the "
        "unit of quality, not the trade.",
    ]

    misses = [s for s in scored if s.miss_kinds]
    L += [
        "",
        "## Misses digest — for the HUMAN E1–E5 post-mortem",
        "",
        f"{len(misses)} flagged of {len(scored)} scored. Cause-class labeling "
        "(E1 hallucination / E2 arithmetic / E3 format / E4 scope / E5 "
        "missing-state — CR143 taxonomy) happens in a Claude session from "
        f"`misses_{week}.jsonl`, committed to "
        "docs/forward_planning/CR157_weekly_retrospective_loop/results/.",
        "",
    ]
    for s in misses:
        L.append(f"- `{s.run_id}` {s.ticker}@{s.as_of.isoformat()} {s.action}: "
                 f"{', '.join(s.miss_kinds)} (4w excess {fnum(s.excess20)}; "
                 f"transcript: room_runs.id = {s.run_id})")
    L.append("")

    args.out.mkdir(parents=True, exist_ok=True)
    report_path = args.out / f"report_{week}.md"
    report_path.write_text("\n".join(L))

    def jsonl_line(s: ScoredRun) -> dict:
        return {
            "run_id": s.run_id, "ticker": s.ticker, "as_of": s.as_of.isoformat(),
            "action": s.action, "partition": s.partition,
            "mandate_version": s.mandate_version, "entry": s.entry,
            "r5": s.r5, "r20": s.r20, "excess5": s.excess5, "excess20": s.excess20,
            "target_hit": s.target_hit, "stop_hit": s.stop_hit,
            "first_touch": s.first_touch, "acted_trades": s.acted_trades,
            "miss_kinds": s.miss_kinds,
            "stances": s.stances,
        }

    with (args.out / f"scored_{week}.jsonl").open("w") as fh:
        for s in scored:
            fh.write(json.dumps(jsonl_line(s)) + "\n")
    with (args.out / f"misses_{week}.jsonl").open("w") as fh:
        for s in misses:
            fh.write(json.dumps(jsonl_line(s)) + "\n")

    print(f"[retro {week}] {len(scored)} scored ({len(misses)} flagged misses) "
          f"→ {report_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
