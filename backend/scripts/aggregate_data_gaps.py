"""CR219 R53/R57 — roll the permanent turn-telemetry tails up: gap items and
stance-envelope emission, over real Alpha `room_runs`.

Modeled on the arms experiment's one-off prototype
(`docs/forward_planning/CR219_room_prompt_contradictions/evidence/analysis/
aggregate_arms.py`), which bucketed 84 turns' hand-appended `DATA I LACKED:`
sections by regex and produced the project's best data-roadmap evidence to
date (21 requests, 9/12 agents). This is the same bucket taxonomy, read from
the production `GAPS:` tail (`room_prompts._GAPS_FORMAT`,
`room_runner.parse_data_gaps`) instead of a harness addendum, over every real
convene instead of one 84-turn batch.

Two independent tallies, one script, because they ride the same JSONB column
and the same exclusion filter:

  * R53 — gap ITEMS, ranked by (bucket, ticker, agent) so a recurring ask
    (e.g. "segment revenue split" surfacing across many tickers and all four
    analysts) reads as a roadmap signal rather than one turn's complaint.
  * R57 — per-agent `envelope_parsed` EMISSION rate (found the tail at all —
    DEF251's own signal — never whether a field inside it validated). The
    measurement leg of `fable/05_further_improvements.md` item 11; the two
    pinned decisions (CR210's "no prose agent is ever grammar-constrained",
    DEF251's "measurement channel, never a control") are UNCHANGED by this
    script — it only reads what already shipped.

Exclusions: `app.services.verdict_outcomes.excluded_user_ids()` — described in
its own docstring as "the most complete" of six independently-drifted copies
of the CR035-synthetic + seed-burst + promotion-probe filter
(`memory/feedback_user_report_exclusions.md`). Reused rather than re-derived,
for the same reason that docstring gives: a seventh copy is how the drift
continues.

READ-ONLY. No table is written; this is pure `SELECT` + in-process tabulation.

Usage (inside the alpha container, or against a local sqlite fixture in
tests):
    python -m scripts.aggregate_data_gaps
    python -m scripts.aggregate_data_gaps --tickers AAPL,MSFT --since 2026-08-01
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db import get_session, init_schema
from app.db.models import RoomRunRow
from app.services.verdict_outcomes import excluded_user_ids

# The 4 analysts R53 scopes the GAPS ask to (room_prompts._GAPS_FORMAT).
# Duplicated here as string literals rather than importing AgentId — this
# script reads raw transcript dicts (post-JSONB-deserialization), which carry
# the wire string, not the enum, and the four analyst wire ids are stable API
# surface (`app/schemas/agents.py`), not an internal detail that would drift
# silently under this script's feet.
GAPS_AGENTS = frozenset({
    "fundamentals_analyst", "market_analyst", "news_analyst", "social_media_analyst",
})

# The 11 prose voices R57 measures emission over — every agent EXCEPT the PM
# (whose turn is a JSON verdict `parse_stance_envelope` never touches) and the
# two internal compute identities (`concierge`, `risk_officer` — the latter's
# rendered turns carry `envelope_parsed=None` by construction; see
# `risk_officer.RenderedRiskTurn`'s own docstring for why DEF247/DEF251/DEF257
# are unreachable on that path).
ENVELOPE_AGENTS = (
    "fundamentals_analyst", "market_analyst", "news_analyst", "social_media_analyst",
    "bull_researcher", "bear_researcher", "research_manager", "trader",
    "aggressive_debator", "conservative_debator", "neutral_debator",
)

# The arms prototype's own bucket taxonomy (aggregate_arms.py:24-39),
# unchanged — the point is that this script's ranking is directly comparable
# to the number the arms experiment already produced, not a fresh
# categorization that would break that comparison.
BUCKETS: list[tuple[str, str]] = [
    ("Debt: maturity / fixed-vs-floating / interest coverage", r'debt (maturity|schedule|breakdown|composition|structure)|fixed.{0,10}floating|interest coverage|industrial.*(financ|captive)|financial services'),
    ("Historical valuation multiples (5-10y median)",          r'histor.*(multiple|p/e|ev/ebitda|valuation)|median.*(multiple|p/e|valuation)|valuation.*histor|5.{0,3}(year|yr)|10.{0,3}(year|yr)'),
    ("Segment / geographic revenue split",                      r'segment|geograph|end.market|revenue (breakdown|exposure|mix|split)|backlog'),
    ("Historical FCF / capex / margin series",                  r'(fcf|free cash flow|capex|capital expenditure|margin).{0,40}(histor|average|conversion|trend|series|multi.year)'),
    ("Dividend / buyback sustainability & pacing",              r'dividend (histor|growth|sustain|safety)|payout.{0,20}histor|buyback.{0,20}(histor|pace|timeline|authoris|authoriz)'),
    ("Earnings revisions / surprise history / guidance",        r'revision|surprise|guidance'),
    ("Price series / higher timeframe / classic indicators",    r'weekly|monthly|time.series|price bar|chart pattern|crossover|macd|bollinger|intraday|volume.at.price|volume profile'),
    ("Order book / institutional & options flow",               r'level 2|order book|dark pool|options|institutional (flow|ownership|position)|implied volatility'),
    ("Volatility for stop sizing (ATR, gap risk)",              r'\batr\b|average true range|gap.down|slippage|overnight gap'),
    ("Capex / cash-flow statement detail",                      r'capex|capital expenditure|operating cash flow|\bcfo\b(?!.*transition)|cash conversion|working capital'),
    ("Peer / sector comparables",                               r'peer|comparable|competitor|sector (average|median|relative)'),
    ("Macro series (rates, CPI, Fed path, commodity)",          r'\bcpi\b|\bppi\b|\bpmi\b|inflation|rate (cut|hike|path|expectation)|fed (path|funds)|commodity'),
    ("Raw social split / buzz / mention counts",                r'sentiment|mention|buzz|reddit|bullish.{0,5}bearish'),
    ("News depth / catalyst detail",                            r'headline|news|catalyst|cfo|press release|filing|8-k|10-q'),
]
_UNBUCKETED = "(unbucketed)"


def _as_utc(dt: datetime | None) -> datetime | None:
    """Naive stamps (sqlite storage convention) are UTC — same helper
    `weekly_room_retro.py` and `verdict_outcomes.py` each already carry."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _bucket(item: str) -> str:
    for tag, pattern in BUCKETS:
        if re.search(pattern, item, re.IGNORECASE):
            return tag
    return _UNBUCKETED


def select_scoreable_runs(
    runs: list[RoomRunRow],
    excluded: set,
    *,
    tickers: set[str] | None,
    since: datetime | None,
) -> tuple[list[RoomRunRow], Counter]:
    """Apply every exclusion, counting each loudly (CR040) — pure, unit-testable.

    A run's `status` is deliberately NOT filtered on here, unlike
    `weekly_room_retro.py`'s `select_due_runs`: a still-running or failed
    convene's completed turns already carry whatever telemetry they emitted
    before it stopped, and dropping the whole run would undercount emission
    on exactly the runs most likely to show a degraded rate.
    """
    counts: Counter = Counter()
    kept: list[RoomRunRow] = []
    for run in runs:
        if run.user_id in excluded:
            counts["excluded_user"] += 1
            continue
        if tickers is not None and run.ticker.upper() not in tickers:
            counts["ticker_filtered"] += 1
            continue
        triggered = _as_utc(run.triggered_at)
        if since is not None and (triggered is None or triggered < since):
            counts["too_old"] += 1
            continue
        kept.append(run)
    return kept, counts


def tally_data_gaps(runs: list[RoomRunRow]) -> tuple[Counter, dict, dict, Counter]:
    """R53. Returns (bucket_counts, examples, by_item_ticker_agent, agent_counts):

      * `bucket_counts` — requests per bucket, across every run.
      * `examples` — one representative (agent, raw item) per bucket, for a
        human skimming the report to see what is actually being asked for.
      * `by_item_ticker_agent` — Counter keyed on (bucket, ticker, agent), the
        WP's own ranking axis: a bucket recurring across MANY tickers and
        agents is a stronger data-roadmap signal than one agent's one
        complaint about one name.
      * `agent_counts` — {"asked": n, "answered": n, "opted_out": n} per
        agent, so an analyst that stops emitting shows up as a RATE (asked
        minus answered) rather than a silent zero in the bucket table (the
        WP's own framing, verbatim).
    """
    bucket_counts: Counter = Counter()
    examples: dict[str, tuple[str, str]] = {}
    by_item_ticker_agent: Counter = Counter()
    agent_counts: Counter = Counter()

    for run in runs:
        ticker = (run.ticker or "").upper()
        for turn in run.transcript or []:
            if not isinstance(turn, dict) or turn.get("role", "agent") != "agent":
                continue
            agent = turn.get("agent_id")
            if agent not in GAPS_AGENTS:
                continue
            agent_counts[(agent, "asked")] += 1
            gaps = turn.get("data_gaps")
            if gaps is None:
                continue  # asked, never answered — an omission, not a zero
            agent_counts[(agent, "answered")] += 1
            if not gaps:
                agent_counts[(agent, "opted_out")] += 1  # explicit "GAPS: none"
                continue
            for item in gaps:
                if not isinstance(item, str) or not item.strip():
                    continue
                tag = _bucket(item)
                bucket_counts[tag] += 1
                by_item_ticker_agent[(tag, ticker, agent)] += 1
                examples.setdefault(tag, (agent, item[:100]))

    return bucket_counts, examples, by_item_ticker_agent, agent_counts


def tally_envelope_emission(runs: list[RoomRunRow]) -> dict[str, dict[str, int]]:
    """R57. {agent: {"parsed": n, "unparsed": n, "not_measured": n}} over
    `ENVELOPE_AGENTS`. `not_measured` covers a transcript entry that predates
    this field (rides the same JSONB with no migration — an older stored run
    simply has no `envelope_parsed` key at all, `dict.get` returns `None`) as
    well as any turn this script cannot attribute to a known voice; it is
    reported so the denominator a rate is computed over is never silently the
    wrong one.
    """
    out: dict[str, dict[str, int]] = {
        agent: {"parsed": 0, "unparsed": 0, "not_measured": 0}
        for agent in ENVELOPE_AGENTS
    }
    for run in runs:
        for turn in run.transcript or []:
            if not isinstance(turn, dict) or turn.get("role", "agent") != "agent":
                continue
            agent = turn.get("agent_id")
            if agent not in out:
                continue
            parsed = turn.get("envelope_parsed")
            if parsed is True:
                out[agent]["parsed"] += 1
            elif parsed is False:
                out[agent]["unparsed"] += 1
            else:
                out[agent]["not_measured"] += 1
    return out


def render_report(
    *,
    n_runs_seen: int,
    exclusion_counts: Counter,
    n_scoreable: int,
    bucket_counts: Counter,
    examples: dict[str, tuple[str, str]],
    by_item_ticker_agent: Counter,
    agent_counts: Counter,
    envelope_tally: dict[str, dict[str, int]],
) -> list[str]:
    L: list[str] = []
    L.append(
        f"room runs seen: {n_runs_seen} — excluded: "
        f"excluded_user {exclusion_counts['excluded_user']}, "
        f"ticker_filtered {exclusion_counts['ticker_filtered']}, "
        f"too_old {exclusion_counts['too_old']} "
        f"— scoreable: {n_scoreable}"
    )
    L.append("")

    L.append("=== R53 — DATA GAPS the four analysts asked for ===")
    L.append("")
    total_items = sum(bucket_counts.values())
    if total_items == 0:
        L.append("No gap items recorded on the scoreable runs.")
    else:
        L.append(f"{total_items} items, {len(bucket_counts)} buckets")
        L.append("-" * 78)
        for tag, n in bucket_counts.most_common():
            agent, ex = examples.get(tag, ("", ""))
            L.append(f"  {n:3d}x  {tag}")
            L.append(f"        [{agent}] {ex}")
        L.append("")
        L.append("Top (bucket, ticker, agent) triples — recurrence across BOTH axes")
        L.append("is the stronger roadmap signal than a single agent's single ask:")
        L.append("-" * 78)
        for (tag, ticker, agent), n in by_item_ticker_agent.most_common(20):
            L.append(f"  {n:3d}x  {tag} | {ticker} | {agent}")

    L.append("")
    L.append("--- Per-analyst emission (asked / answered / opted-out-'none') ---")
    for agent in sorted(GAPS_AGENTS):
        asked = agent_counts[(agent, "asked")]
        answered = agent_counts[(agent, "answered")]
        opted_out = agent_counts[(agent, "opted_out")]
        rate = f"{answered}/{asked} ({100.0 * answered / asked:.1f}%)" if asked else "—"
        L.append(f"  {agent:22s} asked={asked:4d} answered={rate:18s} opted_out_none={opted_out}")

    L.append("")
    L.append("=== R57 — stance-envelope emission (per-agent, all 11 prose voices) ===")
    L.append("")
    L.append(
        "'found the tail at all' (DEF251's own signal), independent of whether "
        "any field inside it parsed to a valid value. Never a control — the two "
        "pins (CR210: no prose agent grammar-constrained; DEF251: measurement "
        "channel only) are unaffected by this table."
    )
    L.append("-" * 78)
    worst_rate: float | None = None
    worst_agent: str | None = None
    worst_n = 0
    for agent in ENVELOPE_AGENTS:
        row = envelope_tally[agent]
        measured = row["parsed"] + row["unparsed"]
        rate_str = "—"
        if measured:
            rate = row["parsed"] / measured
            rate_str = f"{row['parsed']}/{measured} ({100.0 * rate:.1f}%)"
            if worst_rate is None or rate < worst_rate:
                worst_rate, worst_agent, worst_n = rate, agent, measured
        L.append(
            f"  {agent:22s} parsed={row['parsed']:4d} unparsed={row['unparsed']:4d} "
            f"not_measured={row['not_measured']:4d}  rate={rate_str}"
        )

    L.append("")
    if worst_agent is not None:
        L.append(f"Lowest emission rate: {worst_agent} at {100.0 * worst_rate:.1f}% (n={worst_n}).")
    L.append(
        "REVISIT RULE (verbatim, R57): If any debator's emission rate sustains "
        "<75% over >=100 real convenes, surface it at a daily review — amending "
        "the two pins is Saiful's decision, made on this data."
    )
    return L


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--tickers", default=None,
        help="comma-separated ticker filter, e.g. AAPL,MSFT (default: all)",
    )
    ap.add_argument(
        "--since", default=None,
        help="ISO date; only runs triggered on/after this date (default: all history)",
    )
    args = ap.parse_args(argv)

    tickers = (
        {t.strip().upper() for t in args.tickers.split(",") if t.strip()}
        if args.tickers else None
    )
    since = None
    if args.since:
        try:
            since = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)
        except ValueError:
            raise SystemExit(f"FATAL: --since must be an ISO date, got {args.since!r}")

    init_schema()

    with get_session() as session:
        runs: list[RoomRunRow] = list(session.execute(select(RoomRunRow)).scalars().all())
        excluded = excluded_user_ids()
        scoreable, exclusion_counts = select_scoreable_runs(
            runs, excluded, tickers=tickers, since=since,
        )

        bucket_counts, examples, by_item_ticker_agent, agent_counts = tally_data_gaps(scoreable)
        envelope_tally = tally_envelope_emission(scoreable)

        for line in render_report(
            n_runs_seen=len(runs),
            exclusion_counts=exclusion_counts,
            n_scoreable=len(scoreable),
            bucket_counts=bucket_counts,
            examples=examples,
            by_item_ticker_agent=by_item_ticker_agent,
            agent_counts=agent_counts,
            envelope_tally=envelope_tally,
        ):
            print(line, flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
