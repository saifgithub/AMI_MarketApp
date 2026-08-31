"""CR164 scoring report — score a backtest batch's Room verdicts against
realized forward returns, from the database ONLY.

Inputs are `backtest_run_index ⋈ room_runs` (verdict JSONB) and
`price_history_daily` (source != mock) — never a live quote. The report is
BYTE-REPRODUCIBLE by contract: every RNG is `random.Random(--seed)`, every
iteration is sorted by (as_of, ticker) or by date, and the report date is
taken from --stamp (default: today ISO) so a rerun can pin it — same DB
state + same flags ⇒ identical bytes in both output files.

Scoring, per completed run (status == 'completed', verdict non-null):
  - entry = adj_close at the last stored trading date <= as_of; horizons
    +5/+20 TRADING days = the 5th/20th stored row strictly after as_of
    (ascending); a missing row makes that horizon unscoreable (counted).
  - SPY same-window returns from the same table; excess = raw − SPY.
  - Buckets by verdict.action (APPROVE/PASS/REJECT/MODIFY); primary read is
    APPROVE vs PASS, sensitivity (APPROVE+MODIFY) vs (PASS+REJECT).
  - Random-pick null: per as_of date with APPROVEs, --bootstrap seeded
    same-size draws (without replacement) from that date's convened tickers;
    p = fraction of draws with mean 4w excess >= the actual APPROVE mean;
    plus a pooled version weighted by |APPROVE_d|.
  - Date-clustered CI: block bootstrap over DATES for the APPROVE−PASS 4w
    excess spread (2.5/50/97.5 pct); effective n = #distinct dates.
  - Target/stop-hit over the 20 trading days after as_of, gated on
    level_provenance != 'ami_default' per level; first-touch by earliest
    day, same-day both = ambiguous; NULL high/low on a needed day makes
    that leg unscoreable (counted).
  - EDGAR PIT field coverage via `edgar_pit.fetch_pit_fundamentals`.

Outputs: <out-dir>/report_<batch-id>.md (all sections + the CR164
limitations register) and <out-dir>/scored_<batch-id>.jsonl (one line per
bucketed run). Degrade loudly (CR040): no runs for the batch, or nothing
scoreable, is a loud message and exit 1 — never an empty-but-green report.

Usage (inside the alpha container, or from backend/ against an
AMI_TEST_DATABASE_URL sqlite for local smokes):
    .venv/bin/python scripts/backtest_report.py --batch-id pit-pilot-1
    .venv/bin/python scripts/backtest_report.py --batch-id pit-pilot-1 \
        --stamp 2026-08-15 --seed 164 --bootstrap 10000
"""

from __future__ import annotations

import argparse
import bisect
import json
import math
import random
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db import get_session
from app.services.room_runner import is_llm_outage_verdict, init_schema
from app.db.models import BacktestRunIndexRow, PriceHistoryDailyRow, RoomRunRow
from app.services.edgar_pit import fetch_pit_fundamentals
from app.services.price_history import _MOCK_SOURCE

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = REPO_ROOT / "docs/forward_planning/CR164_room_backtest/results"

BENCHMARK = "SPY"
ACTIONS = ("APPROVE", "PASS", "REJECT", "MODIFY")
HIT_WINDOW = 20

# CR214 — a third scoring horizon. The 5/20 pair grades NAME SELECTION over a
# window the Room never claimed: PHASE_B_OUTCOME's own closing caveat is that
# stated horizons run to a median of 90 CALENDAR days while scoring stopped at
# 20 trading days, so "the four-week numbers grade name selection, not whether
# these theses worked". 62 trading rows is ~90 calendar days at 4.83 rows/week.
# It does not replace 20d — a longer window is not strictly better, it is a
# different question with fewer scoreable rows near the end of the sample — so
# both ship and the report says which is which.
H_LONG = 62
EDGAR_FIELDS = (
    "pe", "rev_growth", "profit_margin", "net_cash",
    "price_to_sales", "fcf_yield", "ev_to_ebitda", "dividend_yield",
)

# Ships with every report — the CR164 limitations register (7 items, from the
# approved plan §9; CR doc acceptance item 4).
LIMITATIONS = (
    "Selection edge only — no Sharpe/portfolio claims (no SELL action, no "
    "portfolio; `docs/benchmark/claude/09` R1/R3).",
    "~12% verdict-flip noise floor (no temperature/seed in the gateway); the "
    "repeat-run subsample re-quantifies it per sweep.",
    "Tested Room ≠ live Room: news, social, analyst target/rating, forward "
    "P/E, PEG, next-earnings all UNAVAILABLE.",
    "Effective n ≈ #as-of dates, not convene count (date clustering).",
    "Pre-cutoff structurally excluded; near-cutoff approximate price "
    "knowledge mitigated by the 8-week margin, not eliminated.",
    "Survivorship: tickers_150 is a July-2026 live-name screen; "
    "membership-audit counts published verbatim.",
    "Close-execution assumption, adj_close total-return proxy, static sector "
    "labels, no FOMC countdown for 2025 dates, differential EDGAR tag "
    "coverage (stats published).",
)


@dataclass
class Scored:
    ticker: str
    as_of: date
    action: str
    entry: float | None
    r5: float | None
    r20: float | None
    spy5: float | None
    spy20: float | None
    excess5: float | None
    excess20: float | None
    target_hit: bool | None = None
    stop_hit: bool | None = None
    first_touch: str | None = None
    # CR214 — the ~90-calendar-day horizon (see H_LONG).
    r62: float | None = None
    spy62: float | None = None
    excess62: float | None = None
    # CR214 — how many of the N independent CIO draws wanted in, and how many
    # draws were parseable. None on any run made before self-consistency was
    # raised above 1 sample; absence is absence and is never read as 0, which
    # would be a real "nobody approved" score.
    approve_votes: int | None = None
    samples: int | None = None


def load_series(session, ticker: str) -> list[tuple[date, float, float | None, float | None]]:
    """(date, adj_close, high, low) ascending, real rows only."""
    rows = session.execute(
        select(
            PriceHistoryDailyRow.date,
            PriceHistoryDailyRow.adj_close,
            PriceHistoryDailyRow.high,
            PriceHistoryDailyRow.low,
        )
        .where(
            PriceHistoryDailyRow.ticker == ticker.upper(),
            PriceHistoryDailyRow.source != _MOCK_SOURCE,
        )
        .order_by(PriceHistoryDailyRow.date)
    ).all()
    return [
        (d, float(c), None if h is None else float(h), None if lo is None else float(lo))
        for d, c, h, lo in rows
    ]


def entry_and_forward(series, as_of: date):
    """(entry_price, forward_rows) — entry at last date <= as_of, forward =
    rows strictly after as_of ascending. (None, []) when no entry bar."""
    dates = [r[0] for r in series]
    fwd_start = bisect.bisect_right(dates, as_of)
    entry_i = fwd_start - 1
    if entry_i < 0:
        return None, []
    return series[entry_i][1], series[fwd_start:]


def ret_at(entry: float | None, fwd: list, n: int) -> float | None:
    """Return over the n-th forward trading row (1-based), None if missing."""
    if entry is None or entry <= 0 or len(fwd) < n:
        return None
    return fwd[n - 1][1] / entry - 1.0


def mean(vals: list[float]) -> float | None:
    return sum(vals) / len(vals) if vals else None


def percentile(sorted_vals: list[float], p: float) -> float:
    """Linear-interpolation percentile on a pre-sorted list."""
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    rank = (p / 100.0) * (n - 1)
    lo = math.floor(rank)
    hi = min(lo + 1, n - 1)
    frac = rank - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def _avg_ranks(vals: list[float]) -> list[float]:
    """1-based ranks with ties averaged. Ties are the normal case here, not the
    edge case: `approve_votes` takes at most N+1 distinct values over ~100 names,
    so a rank statistic that broke on ties would be unusable on this data."""
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    ranks = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        r = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = r
        i = j + 1
    return ranks


def graded_score(sc) -> float | None:
    """The convene's approval FRACTION, or None when it carries no score.

    DEF388 — rank on `approve_votes / samples`, never on the raw count.
    `samples` records how many independent CIO draws actually came back, and a
    degrading provider returns fewer than the configured N: 1-of-5 was observed
    on the first convenes of the CR214 sweep. On a count-based score a 1-of-1
    approval (score 1) ranks BELOW a 3-of-5 approval (score 3) while meaning
    the opposite, so a provider wobble reorders the cross-section.

    None, not 0.0, when there is no usable denominator — a run that never
    reached the vote path expresses no view, and folding it in as the weakest
    possible score asserts a rejection the Room never made.
    """
    if sc.approve_votes is None or not sc.samples:
        return None
    return sc.approve_votes / sc.samples


def spearman(xs: list[float], ys: list[float]) -> float | None:
    """Tie-aware Spearman rank correlation, or None where it is undefined.

    None on fewer than 3 pairs (a 2-point rank correlation is always exactly ±1
    and carries no information) and None when either side has zero dispersion —
    a date on which every run scored the same `approve_votes` expresses no
    ranking, and folding that in as 0.0 would dilute the average toward a null
    the data never asserted. Undefined dates are counted and reported, not
    silently dropped (CR040)."""
    if len(xs) != len(ys):
        raise ValueError("spearman: length mismatch")
    if len(xs) < 3:
        return None
    rx, ry = _avg_ranks(xs), _avg_ranks(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    dy = math.sqrt(sum((b - my) ** 2 for b in ry))
    if dx == 0.0 or dy == 0.0:
        return None
    return num / (dx * dy)


def scan_hits(fwd: list, target: float | None, stop: float | None):
    """First-touch scan over up to HIT_WINDOW forward rows.

    Returns (target_hit, stop_hit, first_touch, notes). A hit is definitive
    the day it happens; a NULL high/low encountered BEFORE a hit makes that
    leg unscoreable (the needed day has no data), as does a truncated
    window with no touch."""
    window = fwd[:HIT_WINDOW]
    notes: list[str] = []
    t_day = s_day = None
    t_dead = s_dead = None
    for i, (_, _, hi, lo) in enumerate(window):
        if target is not None and t_day is None and t_dead is None:
            if hi is None:
                t_dead = f"NULL high on forward day {i + 1}"
            elif hi >= target:
                t_day = i
        if stop is not None and s_day is None and s_dead is None:
            if lo is None:
                s_dead = f"NULL low on forward day {i + 1}"
            elif lo <= stop:
                s_day = i

    def leg(day, dead, name):
        if day is not None:
            return True
        if dead is not None:
            notes.append(f"{name}: {dead}")
            return None
        if len(window) < HIT_WINDOW:
            notes.append(f"{name}: window truncated ({len(window)}/{HIT_WINDOW} rows)")
            return None
        return False

    t_hit = leg(t_day, t_dead, "target") if target is not None else None
    s_hit = leg(s_day, s_dead, "stop") if stop is not None else None

    if t_hit is None or s_hit is None:
        touch = "unscoreable"
    elif t_hit and s_hit:
        touch = "ambiguous" if t_day == s_day else (
            "target_first" if t_day < s_day else "stop_first")
    elif t_hit:
        touch = "target_first"
    elif s_hit:
        touch = "stop_first"
    else:
        touch = "neither"
    return t_hit, s_hit, touch, notes


def fnum(v: float | None) -> str:
    return "—" if v is None else f"{v * 100:+.2f}%"


def _sentinel_line(sentinel: dict) -> str:
    """Render the sweep's completion sentinel (DEF345), honestly (DEF358).

    The presence of the sentinel proves the sweep reached its own end; it does
    NOT prove every planned pair completed, and this line used to print an
    unqualified **COMPLETE** either way. On `r70-outcome-2` that rendered as
    "COMPLETE — planned 450, completed 50" directly above "Index rows: 450" —
    two contradictory claims, one of them wrong, in adjacent lines of a report
    whose whole job is to be trusted about its own population.

    So the label is derived from the numbers rather than from the file
    existing. `ran_this_process` is the marker that those numbers carry
    DEF358 semantics at all: before the fix, `completed` was the FINAL
    PROCESS's tally, so a resumed batch understated itself by however much an
    earlier attempt had already done. Deriving a verdict from a legacy count
    would turn this fix into a false alarm on exactly the batch that exposed
    it, so a sentinel without the field is reported as-is, labelled, and the
    reader is sent to `Index rows` for the real population.
    """
    planned = sentinel["planned_pairs"]
    completed = sentinel["completed"]
    ran = sentinel.get("ran_this_process")
    tail = (
        f"failed {sentinel['failed']}, finished {sentinel['finished_at']}."
    )

    if ran is None:
        return (
            f"- Sweep completion: **REACHED ITS END** — planned {planned}, "
            f"completed {completed}, {tail} This sentinel predates DEF358, so "
            f"`completed` counts only what the final process ran and "
            f"understates any batch that resumed after an interruption. Read "
            f"`Index rows` below for the population actually scored."
        )

    resumed = "" if ran == completed else (
        f" ({ran} run by the final process, {completed - ran} already on disk "
        f"from an earlier attempt)"
    )
    if completed < planned:
        label = (
            f"**INCOMPLETE — {planned - completed} of {planned} pairs never "
            f"reached a completed status.** The sweep was not killed (the "
            f"sentinel exists), but the population below is short of the "
            f"intended batch. Read every rate here as conditional on the "
            f"pairs that did complete."
        )
    else:
        label = "**COMPLETE**"
    return (
        f"- Sweep completion: {label} — planned {planned}, completed "
        f"{completed}{resumed}, {tail}"
    )


SIGNAL_ACTIONS = ("APPROVE", "MODIFY")
HORIZONS = (("4w", "excess20"), ("~13w (62d)", "excess62"))


def by_date(rows, attr: str, actions: tuple[str, ...]) -> dict:
    """Group one scored attribute by as-of date, for the given verdict bucket."""
    out: dict = {}
    for sc in rows:
        if sc.action in actions and getattr(sc, attr) is not None:
            out.setdefault(sc.as_of, []).append(getattr(sc, attr))
    return out


def clustered_ci(per_date: dict, *, bootstrap: int, rng) -> list[str]:
    """Block bootstrap over dates on a per-date statistic.

    Resampling DATES, not runs, is the whole point: two names convened on the
    same day share that day's market move, so treating them as independent
    draws understates the interval by roughly the square root of the names per
    date. Every null this project has published was bounded this way.
    """
    ds = sorted(per_date)
    if len(ds) < 2:
        return [f"SKIPPED — {len(ds)} usable date(s); an interval over "
                "one date would be fabricated."]
    actual = sum(per_date[d] for d in ds) / len(ds)
    reps = []
    for _ in range(bootstrap):
        draw = [per_date[rng.choice(ds)] for _ in range(len(ds))]
        reps.append(sum(draw) / len(draw))
    reps.sort()
    return [
        f"- Actual: **{fnum(actual)}**",
        f"- Block bootstrap over dates ({bootstrap} replicates):",
        f"  - 2.5th pct: {fnum(percentile(reps, 2.5))}",
        f"  - 50th pct: {fnum(percentile(reps, 50))}",
        f"  - 97.5th pct: {fnum(percentile(reps, 97.5))}",
        f"- **Effective n = {len(ds)} dates.**",
    ]


def paired_spread(rows, *, bootstrap: int, rng, horizons=HORIZONS) -> list[str]:
    """Mean of the per-date (signal - rest) spread.

    The pooled difference mixes dates: a bucket over-weighted on a good market
    day inherits that day's return. Both legs of a within-date term saw the
    same market, so the common factor drops out exactly. Only dates carrying
    both buckets contribute; the rest are counted and named, not dropped.
    """
    lines: list[str] = []
    for label, ex_attr in horizons:
        a_d = by_date(rows, ex_attr, SIGNAL_ACTIONS)
        p_d = by_date(rows, ex_attr, ("PASS", "REJECT"))
        both = sorted(set(a_d) & set(p_d))
        lines.append(f"**{label}** — dates with both buckets: "
                     f"{len(both)} of {len(sorted(set(a_d) | set(p_d)))}")
        if not both:
            lines += ["", "SKIPPED — no date carries both buckets.", ""]
            continue
        per_date = {d: mean(a_d[d]) - mean(p_d[d]) for d in both}
        lines += clustered_ci(per_date, bootstrap=bootstrap, rng=rng) + [""]
    return lines


def placebo_effect(rows, *, bootstrap: int, rng, horizons=HORIZONS) -> list[str]:
    """Room picks minus a matched-random pick of the same count from the same pool.

    RES001's binding rule: any selector looks good if it merely selects fewer.
    The expectation of a uniform same-size subset mean IS the pool mean, so the
    placebo leg is analytic — no RNG, no sampling noise, byte-stable. The pool
    retains the Room's own picks, which attenuates the effect toward zero; that
    is the conservative direction.
    """
    lines: list[str] = []
    for label, ex_attr in horizons:
        pool_d = by_date(rows, ex_attr, ACTIONS)
        room_d = by_date(rows, ex_attr, SIGNAL_ACTIONS)
        usable = sorted(d for d in room_d if len(pool_d.get(d, [])) >= 2)
        lines.append(
            f"**{label}** — dates with a scoreable pick and a pool of ≥2: "
            f"{len(usable)} of {len(room_d)}"
        )
        if not usable:
            lines += ["", "SKIPPED — no date has both.", ""]
            continue
        per_date = {d: mean(room_d[d]) - mean(pool_d[d]) for d in usable}
        lines += clustered_ci(per_date, bootstrap=bootstrap, rng=rng) + [""]
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--batch-id", required=True)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--bootstrap", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=164)
    ap.add_argument("--stamp", default=date.today().isoformat(),
                    help="report date (ISO); pin it to reproduce a prior report")
    ap.add_argument(
        "--allow-partial", action="store_true",
        help=(
            "Score a batch whose sweep never wrote its completion sentinel "
            "(DEF345). The result is a PARTIAL batch and is labelled as one "
            "in the report — use only when you know why the sweep stopped."
        ),
    )
    args = ap.parse_args()

    try:
        date.fromisoformat(args.stamp)
    except ValueError:
        raise SystemExit(f"FATAL: --stamp must be an ISO date, got {args.stamp!r}")
    if args.bootstrap < 1:
        raise SystemExit(f"FATAL: --bootstrap must be >= 1, got {args.bootstrap}")

    # DEF345 — the sweep runs as `docker compose exec`, so a container recreate
    # kills it mid-batch with no traceback and no exit line, leaving a partial
    # batch that is shaped exactly like a finished one. `r70-outcome-2` lost
    # 2.5 h that way after 17 of 450 runs, and the only reason anyone noticed
    # was arithmetic on wall-clock. Nothing IN the records is wrong, so no
    # per-record filter can catch it — the missing sentinel is the only
    # evidence, and a process that died cannot have written one.
    sentinel_path = args.out_dir / f"complete_{args.batch_id}.json"
    sentinel = None
    if sentinel_path.exists():
        sentinel = json.loads(sentinel_path.read_text())
    elif not args.allow_partial:
        print(
            f"ERROR: no completion sentinel at {sentinel_path} — the sweep for "
            f"'{args.batch_id}' never reached its own end, so this batch is "
            f"TRUNCATED, not finished, and scoring it would report a partial "
            f"sample as a whole one. Resume the sweep (completed pairs are "
            f"skipped), or pass --allow-partial if you know why it stopped. "
            f"(exit 5)",
            flush=True,
        )
        return 5

    init_schema()
    rng = random.Random(args.seed)

    with get_session() as session:
        index_rows = session.execute(
            select(BacktestRunIndexRow)
            .where(BacktestRunIndexRow.batch_id == args.batch_id)
        ).scalars().all()
        index_rows.sort(key=lambda r: (r.as_of, r.ticker))

        if not index_rows:
            print(f"ERROR: no runs for batch '{args.batch_id}' — nothing to score "
                  "(exit 1)", flush=True)
            return 1

        arms = sorted({r.arm for r in index_rows})
        excluded = {"missing_room_run": 0, "non_completed": 0,
                    "null_verdict": 0, "other_action": 0, "llm_outage": 0}
        pairs: list[tuple[BacktestRunIndexRow, RoomRunRow]] = []
        for idx in index_rows:
            run = session.get(RoomRunRow, idx.room_run_id)
            if run is None:
                excluded["missing_room_run"] += 1
                print(f"WARNING: {idx.ticker}@{idx.as_of} room_runs row "
                      f"{idx.room_run_id} missing — excluded", flush=True)
                continue
            if run.status != "completed":
                excluded["non_completed"] += 1
                continue
            if run.verdict is None:
                excluded["null_verdict"] += 1
                continue
            if run.verdict.get("action") not in ACTIONS:
                excluded["other_action"] += 1
                continue
            # DEF336 — the DEF059 outage fail-safe is a completed run with a
            # PASS verdict. Scoring it counts the provider's downtime as the
            # Room's conservatism, and it is invisible to every other filter
            # here because nothing about its shape is wrong.
            if is_llm_outage_verdict(run.verdict):
                excluded["llm_outage"] += 1
                continue
            pairs.append((idx, run))

        # An outage that took a meaningful share of the batch means the batch
        # measured uptime, not judgement. Refuse rather than report a
        # PASS-heavy result with a footnote nobody reads.
        considered = len(pairs) + excluded["llm_outage"]
        if considered and excluded["llm_outage"] / considered > 0.05:
            print(
                f"ERROR: {excluded['llm_outage']} of {considered} verdicts in "
                f"'{args.batch_id}' are DEF059 LLM-outage fail-safes "
                f"({excluded['llm_outage'] / considered:.0%}) — the provider "
                f"was down for this batch and it is NOT scoreable. Re-run "
                f"under a new --batch-id once the provider is healthy. (exit 4)",
                flush=True,
            )
            return 4

        if not pairs:
            print(f"ERROR: no runs for batch '{args.batch_id}' are completed with a "
                  "bucketable verdict — nothing to score (exit 1)", flush=True)
            return 1

        series_cache: dict[str, list] = {}

        def series(t: str) -> list:
            if t not in series_cache:
                series_cache[t] = load_series(session, t)
            return series_cache[t]

        spy = series(BENCHMARK)
        if not spy:
            print(f"WARNING: no real {BENCHMARK} rows in price_history_daily — "
                  "all excess returns will be unscoreable", flush=True)

        unscoreable = {"no_entry": 0, "no_r5": 0, "no_r20": 0,
                       "no_spy5": 0, "no_spy20": 0,
                       # CR214 — expected to be NON-ZERO near the end of any
                       # sample: a run needs 62 forward rows and the newest
                       # as-of dates do not have them yet. That is a smaller
                       # scoreable population at 62d, not a broken batch.
                       "no_r62": 0, "no_spy62": 0}
        scored: list[Scored] = []
        hit_stats = {
            "eligible": 0, "prov_excluded_target": 0, "prov_excluded_stop": 0,
            "target_eval": 0, "target_hits": 0, "target_unscoreable": 0,
            "stop_eval": 0, "stop_hits": 0, "stop_unscoreable": 0,
            "touch": {"target_first": 0, "stop_first": 0, "ambiguous": 0,
                      "neither": 0, "unscoreable": 0},
        }
        hit_notes: list[str] = []

        for idx, run in pairs:
            v = run.verdict
            entry, fwd = entry_and_forward(series(idx.ticker), idx.as_of)
            spy_entry, spy_fwd = entry_and_forward(spy, idx.as_of)
            r5 = ret_at(entry, fwd, 5)
            r20 = ret_at(entry, fwd, 20)
            r62 = ret_at(entry, fwd, H_LONG)
            spy5 = ret_at(spy_entry, spy_fwd, 5)
            spy20 = ret_at(spy_entry, spy_fwd, 20)
            spy62 = ret_at(spy_entry, spy_fwd, H_LONG)
            if entry is None:
                unscoreable["no_entry"] += 1
            else:
                if r5 is None:
                    unscoreable["no_r5"] += 1
                if r20 is None:
                    unscoreable["no_r20"] += 1
            if spy5 is None:
                unscoreable["no_spy5"] += 1
            if spy20 is None:
                unscoreable["no_spy20"] += 1
            if r62 is None and entry is not None:
                unscoreable["no_r62"] += 1
            if spy62 is None:
                unscoreable["no_spy62"] += 1

            s = Scored(
                ticker=idx.ticker, as_of=idx.as_of, action=v["action"],
                entry=entry, r5=r5, r20=r20, spy5=spy5, spy20=spy20,
                excess5=None if (r5 is None or spy5 is None) else r5 - spy5,
                excess20=None if (r20 is None or spy20 is None) else r20 - spy20,
                r62=r62, spy62=spy62,
                excess62=None if (r62 is None or spy62 is None) else r62 - spy62,
                approve_votes=v.get("approve_votes"),
                samples=v.get("samples"),
            )

            # Target/stop-hit: APPROVE/MODIFY with all three levels present,
            # each leg gated on its own provenance (ami_default = AMI minted
            # the level — scoring it would grade a default, not a decision;
            # missing/unknown provenance is excluded the same way, CR106
            # T-BACKFILL: absence is never inferred to be PM-stated).
            v_entry, v_target, v_stop = v.get("entry"), v.get("target"), v.get("stop")
            prov = v.get("level_provenance") or {}
            if (v["action"] in ("APPROVE", "MODIFY")
                    and v_entry is not None and v_target is not None
                    and v_stop is not None):
                hit_stats["eligible"] += 1
                want_target = prov.get("target") not in (None, "ami_default")
                want_stop = prov.get("stop") not in (None, "ami_default")
                if not want_target:
                    hit_stats["prov_excluded_target"] += 1
                if not want_stop:
                    hit_stats["prov_excluded_stop"] += 1
                if want_target or want_stop:
                    t_hit, s_hit, touch, notes = scan_hits(
                        fwd,
                        float(v_target) if want_target else None,
                        float(v_stop) if want_stop else None,
                    )
                    for n in notes:
                        hit_notes.append(f"{idx.ticker}@{idx.as_of.isoformat()}: {n}")
                    if want_target:
                        hit_stats["target_eval"] += 1
                        if t_hit is True:
                            hit_stats["target_hits"] += 1
                        elif t_hit is None:
                            hit_stats["target_unscoreable"] += 1
                    if want_stop:
                        hit_stats["stop_eval"] += 1
                        if s_hit is True:
                            hit_stats["stop_hits"] += 1
                        elif s_hit is None:
                            hit_stats["stop_unscoreable"] += 1
                    if want_target and want_stop:
                        hit_stats["touch"][touch] += 1
                    s.target_hit, s.stop_hit, s.first_touch = t_hit, s_hit, touch
            scored.append(s)

        # ---- EDGAR PIT field coverage (per bucketed run) -----------------
        field_counts = {f: 0 for f in EDGAR_FIELDS}
        edgar_none = 0
        for s in scored:
            facts = fetch_pit_fundamentals(s.ticker, s.as_of)
            if facts is None:
                edgar_none += 1
                continue
            for f in EDGAR_FIELDS:
                if f in facts:
                    field_counts[f] += 1

    # ---- bucket aggregates (DB no longer needed) -------------------------
    def bucket(actions: tuple[str, ...]) -> list[Scored]:
        return [s for s in scored if s.action in actions]

    def bucket_row(name: str, runs: list[Scored]) -> list[str]:
        out = []
        for horizon, raw_attr, ex_attr in (("1w", "r5", "excess5"),
                                           ("4w", "r20", "excess20")):
            raws = [getattr(s, raw_attr) for s in runs
                    if getattr(s, raw_attr) is not None]
            exs = [getattr(s, ex_attr) for s in runs
                   if getattr(s, ex_attr) is not None]
            out.append(
                f"| {name} | {horizon} | {len(raws)} | {fnum(mean(raws))} "
                f"| {len(exs)} | {fnum(mean(exs))} |"
            )
        return out

    n_by_action = {a: len(bucket((a,))) for a in ACTIONS}
    dates_all = sorted({s.as_of for s in scored})

    # ---- random-pick null (4w excess) ------------------------------------
    # Pool per date = convened tickers with a scoreable 4w excess; draws are
    # same-size ticker subsets WITHOUT replacement (a random pick of the same
    # number of names), seeded — byte-stable across reruns.
    ex20 = [s for s in scored if s.excess20 is not None]
    approve_by_date: dict[date, list[float]] = {}
    pool_by_date: dict[date, list[tuple[str, float]]] = {}
    for s in ex20:
        pool_by_date.setdefault(s.as_of, []).append((s.ticker, s.excess20))
        if s.action == "APPROVE":
            approve_by_date.setdefault(s.as_of, []).append(s.excess20)

    null_rows: list[str] = []
    null_dates = sorted(approve_by_date)
    date_draws: dict[date, list[float]] = {}
    for d in null_dates:
        k = len(approve_by_date[d])
        pool = sorted(pool_by_date[d])
        actual = mean(approve_by_date[d])
        draws = []
        for _ in range(args.bootstrap):
            pick = rng.sample(pool, k)
            draws.append(mean([p[1] for p in pick]))
        date_draws[d] = draws
        p = sum(1 for x in draws if x >= actual) / len(draws)
        null_rows.append(
            f"| {d.isoformat()} | {k} | {len(pool)} | {fnum(actual)} | {p:.4f} |"
        )

    pooled_p = pooled_actual = None
    if null_dates:
        weights = {d: len(approve_by_date[d]) for d in null_dates}
        total_w = sum(weights.values())
        pooled_actual = (
            sum(weights[d] * mean(approve_by_date[d]) for d in null_dates) / total_w
        )
        pooled_ge = 0
        for i in range(args.bootstrap):
            pooled_draw = (
                sum(weights[d] * date_draws[d][i] for d in null_dates) / total_w
            )
            if pooled_draw >= pooled_actual:
                pooled_ge += 1
        pooled_p = pooled_ge / args.bootstrap

    # ---- date-clustered CI on APPROVE − PASS 4w excess -------------------
    ci_lines: list[str] = []
    app_by_date: dict[date, list[float]] = {}
    pass_by_date: dict[date, list[float]] = {}
    for s in ex20:
        if s.action == "APPROVE":
            app_by_date.setdefault(s.as_of, []).append(s.excess20)
        elif s.action == "PASS":
            pass_by_date.setdefault(s.as_of, []).append(s.excess20)
    app_all = [x for xs in app_by_date.values() for x in xs]
    pass_all = [x for xs in pass_by_date.values() for x in xs]

    if not app_all or not pass_all:
        msg = (f"SKIPPED — a bucket is empty at 4w excess (APPROVE n={len(app_all)}, "
               f"PASS n={len(pass_all)}); a CI over an empty bucket would be "
               "fabricated.")
        print(f"WARNING: date-clustered CI {msg}", flush=True)
        ci_lines.append(msg)
    else:
        ci_dates = sorted(set(app_by_date) | set(pass_by_date))
        spread_actual = mean(app_all) - mean(pass_all)
        reps: list[float] = []
        degenerate = 0
        for _ in range(args.bootstrap):
            sample_dates = [rng.choice(ci_dates) for _ in range(len(ci_dates))]
            a = [x for d in sample_dates for x in app_by_date.get(d, [])]
            p = [x for d in sample_dates for x in pass_by_date.get(d, [])]
            if not a or not p:
                degenerate += 1
                continue
            reps.append(mean(a) - mean(p))
        if not reps:
            ci_lines.append(
                f"SKIPPED — all {args.bootstrap} replicates lost a bucket "
                "(buckets never co-occur across resampled dates)."
            )
        else:
            reps.sort()
            ci_lines += [
                f"- Actual spread (mean APPROVE − mean PASS, 4w excess): "
                f"**{fnum(spread_actual)}**",
                f"- Block bootstrap over dates ({len(reps)} usable of "
                f"{args.bootstrap} replicates; {degenerate} dropped an empty "
                "bucket):",
                f"  - 2.5th pct: {fnum(percentile(reps, 2.5))}",
                f"  - 50th pct: {fnum(percentile(reps, 50))}",
                f"  - 97.5th pct: {fnum(percentile(reps, 97.5))}",
                f"- **Effective n = {len(ci_dates)} distinct as-of dates** "
                f"(not {len(app_all) + len(pass_all)} runs — date clustering).",
            ]

    # ---- CR214: within-date paired spread --------------------------------
    # The pooled difference above mixes dates: a bucket that happens to be
    # over-weighted on a good market day inherits that day's return. Averaging
    # the WITHIN-date spread cancels the common factor exactly, because both
    # legs of every term were exposed to the same market. Only dates carrying
    # both buckets contribute; the rest are counted and named, not dropped.
    def _by_date(attr: str, actions: tuple[str, ...]) -> dict:
        return by_date(scored, attr, actions)

    def _clustered_ci(per_date: dict[date, float]) -> list[str]:
        return clustered_ci(per_date, bootstrap=args.bootstrap, rng=rng)

    paired_lines = paired_spread(scored, bootstrap=args.bootstrap, rng=rng)

    # ---- CR214: placebo-adjusted selection effect -------------------------
    # RES001's binding rule: any selector looks good if it merely selects fewer,
    # so the Room is measured against a matched-random pick of the SAME COUNT
    # from the SAME per-date pool, not against zero.
    #
    # The expectation of a uniform random same-size subset mean is exactly the
    # pool mean, so the placebo leg is analytic — no RNG, no sampling noise, and
    # byte-stable by construction. The pool retains the Room's own picks (the
    # construction the existing random-pick null uses), which attenuates the
    # measured effect toward zero. That is the conservative direction.
    placebo_lines = placebo_effect(scored, bootstrap=args.bootstrap, rng=rng)

    # ---- CR214: rank IC on the graded verdict -----------------------------
    # The bucket tests above spend ~90% of the batch in PASS, where a binary
    # verdict carries no ordering. `approve_votes` (CR214) is 0..N over the
    # independent CIO draws, so every convene enters the statistic and the
    # per-date estimate rests on the full cross-section instead of on the 1-4
    # names that happened to approve.
    #
    # A date is undefined, NOT zero, when every run on it scored the same vote
    # count — that date expresses no ranking, and averaging in a 0.0 would
    # assert a null the data never made. Undefined dates are counted below.
    ic_lines: list[str] = []
    graded = [sc for sc in scored if graded_score(sc) is not None]
    if not graded:
        ic_lines.append(
            "SKIPPED — no run in this batch carries `approve_votes`. The batch "
            "predates CR214, or ran with `pm_self_consistency_samples = 1` "
            "(one draw is a verdict, not a score). Not a failure; the bucket "
            "tests above are the whole read for such a batch."
        )
    else:
        ic_lines.append(
            f"Graded runs: **{len(graded)}** of {len(scored)}"
            + (f" — **{len(scored) - len(graded)} ungraded and excluded**"
               if len(graded) != len(scored) else "")
        )
        _samp: dict[int, int] = {}
        for sc in graded:
            _samp[sc.samples] = _samp.get(sc.samples, 0) + 1
        if len(_samp) > 1:
            _full = max(_samp)
            ic_lines.append(
                "Achieved CIO draws per convene: "
                + ", ".join(f"{k}x{v}" for k, v in sorted(_samp.items()))
                + f" — **{len(graded) - _samp[_full]} convene(s) returned fewer "
                f"than {_full} draws**, so their score sits on a coarser grid. "
                "The fraction keeps them comparable, but a large tail here means "
                "the provider was degrading, not that the Room was undecided."
            )
        for label, ex_attr in (("4w", "excess20"), ("~13w (62d)", "excess62")):
            by_date: dict[date, list[tuple[float, float]]] = {}
            for sc in graded:
                if getattr(sc, ex_attr) is not None:
                    by_date.setdefault(sc.as_of, []).append(
                        (graded_score(sc), getattr(sc, ex_attr))
                    )
            per_date: dict[date, float] = {}
            undefined = 0
            for d in sorted(by_date):
                rows = sorted(by_date[d])
                ic = spearman([r[0] for r in rows], [r[1] for r in rows])
                if ic is None:
                    undefined += 1
                else:
                    per_date[d] = ic
            ic_lines.append("")
            ic_lines.append(
                f"**{label}** — dates with a defined IC: {len(per_date)}"
                f" (undefined: {undefined} — fewer than 3 runs, or no "
                "dispersion in votes or returns)"
            )
            ic_lines += _clustered_ci(per_date) if per_date else [
                "SKIPPED — no date has a defined IC."
            ]
        ic_lines += [
            "",
            "> Read the magnitude against published cross-sectional ICs of "
            "**0.02-0.05**, not against 0.5. An interval that spans zero AND "
            "is wider than that band is a NON-MEASUREMENT, not a null — say "
            "which one it is.",
        ]

    # ---- render ----------------------------------------------------------
    L: list[str] = [
        f"# CR164 backtest scoring report — batch `{args.batch_id}`",
        "",
        f"Report date {args.stamp} · seed {args.seed} · bootstrap {args.bootstrap} · "
        f"arm(s): {', '.join(arms)}",
        "",
        "Sources: `backtest_run_index ⋈ room_runs` + `price_history_daily` "
        f"(source != '{_MOCK_SOURCE}') only — no live quotes. Byte-reproducible: "
        "rerun with the same DB state, --seed and --stamp to get identical bytes.",
        "",
        "## Run accounting",
        "",
        (
            _sentinel_line(sentinel)
            if sentinel else
            "- Sweep completion: **PARTIAL — no completion sentinel (DEF345).** "
            "The sweep never reached its own end, so the population below is a "
            "truncated sample of the intended batch, not the batch. Read every "
            "rate here as conditional on however far it got."
        ),
        f"- Index rows: **{len(index_rows)}**",
        f"- Excluded — missing room_runs row: {excluded['missing_room_run']}, "
        f"not completed: {excluded['non_completed']}, null verdict: "
        f"{excluded['null_verdict']}, non-bucket action: {excluded['other_action']}, "
        f"LLM-outage fail-safe: {excluded['llm_outage']}",
        f"- Bucketed (scored population): **{len(scored)}** — "
        + ", ".join(f"{a}: {n_by_action[a]}" for a in ACTIONS),
        f"- Distinct as-of dates: **{len(dates_all)}**",
        f"- Unscoreable at horizon — no entry bar: {unscoreable['no_entry']}, "
        f"no +5d row: {unscoreable['no_r5']}, no +20d row: {unscoreable['no_r20']}, "
        f"no SPY +5d: {unscoreable['no_spy5']}, no SPY +20d: {unscoreable['no_spy20']}",
        "",
        "## Forward returns by verdict bucket",
        "",
        "| bucket | horizon | n (raw) | mean raw | n (excess) | mean excess vs SPY |",
        "|---|---|---|---|---|---|",
    ]
    for a in ACTIONS:
        L += bucket_row(a, bucket((a,)))
    L += [
        "",
        "Primary read: **APPROVE vs PASS** mean 1w/4w raw and excess above.",
        "",
        "## Sensitivity: (APPROVE+MODIFY) vs (PASS+REJECT)",
        "",
        "| bucket | horizon | n (raw) | mean raw | n (excess) | mean excess vs SPY |",
        "|---|---|---|---|---|---|",
    ]
    L += bucket_row("APPROVE+MODIFY", bucket(("APPROVE", "MODIFY")))
    L += bucket_row("PASS+REJECT", bucket(("PASS", "REJECT")))
    L += ["", "## Random-pick null (4w excess vs SPY)", ""]
    if null_rows:
        L += [
            "Per as-of date with APPROVEs: draw |APPROVE_d| tickers uniformly "
            "(without replacement) from that date's convened tickers with a "
            f"scoreable 4w excess, {args.bootstrap}× seeded; "
            "p = P(draw mean ≥ actual APPROVE mean).",
            "",
            "| as_of | n APPROVE | pool | actual mean | p |",
            "|---|---|---|---|---|",
            *null_rows,
            "",
            f"Pooled (dates weighted by n APPROVE): actual **{fnum(pooled_actual)}**, "
            f"p = **{pooled_p:.4f}** over {args.bootstrap} pooled draws.",
        ]
    else:
        L.append("SKIPPED — no as-of date has an APPROVE with a scoreable 4w "
                 "excess; there is no APPROVE set to test against a null.")
        print("WARNING: random-pick null skipped — no scoreable APPROVEs at 4w",
              flush=True)
    L += ["", "## Date-clustered CI — APPROVE − PASS, 4w excess", "", *ci_lines]

    # CR214 — the three estimators added because the two-bucket pooled difference
    # above spends ~90% of a sweep in a bucket that carries no ordering.
    L += [
        "",
        "## CR214 — within-date paired spread (market factor cancelled)",
        "",
        "Mean of the per-date (APPROVE − PASS) spread, rather than the difference "
        "of pooled means. Both legs of every term saw the same market, so the "
        "common factor drops out exactly; the pooled estimator above leaves it in.",
        "",
        *paired_lines,
        "",
        "## CR214 — placebo-adjusted selection effect",
        "",
        "Room picks minus a matched-random pick of the SAME COUNT from the SAME "
        "per-date pool. RES001's rule: any selector looks good if it merely "
        "selects fewer. The placebo leg is analytic — the expectation of a "
        "uniform same-size subset mean IS the pool mean — so there is no sampling "
        "noise and no RNG. The pool retains the Room's own picks, which attenuates "
        "the effect toward zero; that is the conservative direction.",
        "",
        *placebo_lines,
        "",
        "## CR214 — rank IC on the graded verdict",
        "",
        "Per-date Spearman between the approval FRACTION "
        "(`approve_votes` / `samples`, over the independent CIO draws) and "
        "forward excess return, averaged over dates. Every convene enters this "
        "statistic, not just the minority that approved. DEF388: the fraction, "
        "not the raw count — a convene whose provider returned 1 draw of 5 "
        "would otherwise outrank a 3-of-5 approval.",
        "",
        *ic_lines,
    ]
    L += [
        "",
        "## Target/stop-hit (20 trading days after as-of, provenance-gated)",
        "",
        "APPROVE/MODIFY runs carrying entry+target+stop; each leg scored only "
        "when its `level_provenance` is a stated level (not 'ami_default', not "
        "missing).",
        "",
        f"- Runs with all three levels: **{hit_stats['eligible']}** — "
        f"target leg provenance-excluded: {hit_stats['prov_excluded_target']}, "
        f"stop leg provenance-excluded: {hit_stats['prov_excluded_stop']}",
        f"- Target: evaluated {hit_stats['target_eval']}, hit "
        f"{hit_stats['target_hits']}"
        + (f" ({hit_stats['target_hits'] / (hit_stats['target_eval'] - hit_stats['target_unscoreable']) * 100:.1f}% of scoreable)"
           if hit_stats['target_eval'] - hit_stats['target_unscoreable'] > 0 else "")
        + f", unscoreable {hit_stats['target_unscoreable']}",
        f"- Stop: evaluated {hit_stats['stop_eval']}, hit {hit_stats['stop_hits']}"
        + (f" ({hit_stats['stop_hits'] / (hit_stats['stop_eval'] - hit_stats['stop_unscoreable']) * 100:.1f}% of scoreable)"
           if hit_stats['stop_eval'] - hit_stats['stop_unscoreable'] > 0 else "")
        + f", unscoreable {hit_stats['stop_unscoreable']}",
        "- First-touch (both legs evaluated): "
        + ", ".join(f"{k}: {v}" for k, v in hit_stats["touch"].items()),
    ]
    if hit_notes:
        L += ["", "Unscoreable detail:"] + [f"- {n}" for n in hit_notes]
    L += [
        "",
        "## EDGAR PIT field coverage",
        "",
        f"Per bucketed run ({len(scored)} runs), via "
        "`edgar_pit.fetch_pit_fundamentals(ticker, as_of)`"
        + (f"; {edgar_none} run(s) returned None (no usable price row)."
           if edgar_none else "."),
        "",
        "| field | runs with field | coverage |",
        "|---|---|---|",
    ]
    for f in EDGAR_FIELDS:
        L.append(f"| {f} | {field_counts[f]}/{len(scored)} "
                 f"| {field_counts[f] / len(scored) * 100:.1f}% |")
    L += ["", "## Limitations register (CR164)", ""]
    L += [f"{i}. {item}" for i, item in enumerate(LIMITATIONS, 1)]
    L.append("")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.out_dir / f"report_{args.batch_id}.md"
    report_path.write_text("\n".join(L))

    jsonl_path = args.out_dir / f"scored_{args.batch_id}.jsonl"
    with jsonl_path.open("w") as fh:
        for s in sorted(scored, key=lambda x: (x.as_of, x.ticker)):
            fh.write(json.dumps({
                "ticker": s.ticker,
                "as_of": s.as_of.isoformat(),
                "action": s.action,
                "entry": s.entry,
                "r5": s.r5,
                "r20": s.r20,
                "spy5": s.spy5,
                "spy20": s.spy20,
                "excess20": s.excess20,
                "target_hit": s.target_hit,
                "stop_hit": s.stop_hit,
            }) + "\n")

    print(f"[report] {len(scored)} bucketed runs over {len(dates_all)} dates "
          f"→ {report_path}", flush=True)
    print(f"[report] scored lines → {jsonl_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
