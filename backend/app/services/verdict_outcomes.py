"""CR219 R55 — the verdict-outcome ledger: bank a verdict, score it later.

**Framing discipline, and it is load-bearing.** This module is a *calibration
sanity floor*. The only two questions it may be read as answering are:

  1. "APPROVEs are not systematically worse than PASSes."
  2. "High conviction means something" — i.e. the graded signal separates.

Both are floors a functioning decision process must clear. Neither is a
performance claim, an alpha claim, or a track record. AMI Trade is a
simulation-only education product and is not licensed to give investment
advice; nothing computed here may be surfaced to a user or framed as evidence
that the Room picks winners. Internal only, admin-gated (Saiful's 2026-09-02
ruling on the internal-only half). Any string that could ever reach a user
names the AI **AMI**, never "the AI".

Why a ledger table rather than a query over `room_runs.verdict`: the reference
price must be **the price the Room actually saw on that run**. `room_runner`
already computes it (`_reference_close(ctx.profile)` — the last close of the
same series the 50-day range was built from, gated on LIVE technicals
provenance). A later re-derivation would score the Room against data it never
had, which converts a calibration check into a fabrication. So the price is
captured at bank time and frozen.

Horizon mapping — mandate `Horizon` → concrete `horizon_days`:

    short      21   (~1 trading month)
    medium     63   (~1 trading quarter)
    long      126   (~2 trading quarters)
    very_long 252   (~1 trading year)

Calendar days, not trading days: the scorer asks for the first stored bar at
or before `reference_at + horizon_days`, so weekends and holidays resolve
themselves off the store's own calendar (CR136 imports no trading calendar
anywhere). A verdict that states its own `time_horizon_days` overrides the
mandate default — the PM's stated horizon is the horizon its call should be
measured against.

Status lifecycle:

    pending      banked; horizon not yet elapsed, or not yet scored
    scored       `outcome_price` + `forward_return` are real market data
    unscorable   deliberately never scored; `exclusion_reason` says why

`unscorable` is the CR040 degrade-loudly application here. An excluded
synthetic user, a run with no reference price, and a horizon close that could
only come from `mock_walk` all land in `unscorable` with a reason string. None
of them is silently dropped, and none is silently scored against a random walk
— a ledger that quietly scores fabricated bars would report calibration it
never measured, which is worse than reporting nothing.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from app.core.logging import logger
from app.db import get_session
from app.db.models import PriceHistoryDailyRow, User, VerdictOutcomeRow
from app.schemas.mandate import Horizon
from app.schemas.room import VerdictAction
from app.services.admin_analytics import _real_users_clause
from app.services.price_history import _MOCK_SOURCE

# ── Status + reason vocabulary ──────────────────────────────────────────────

STATUS_PENDING = "pending"
STATUS_SCORED = "scored"
STATUS_UNSCORABLE = "unscorable"

REASON_EXCLUDED_USER = "excluded_user"
REASON_NO_REFERENCE_PRICE = "no_reference_price"
REASON_MOCK_PRICE = "mock_price_source"
REASON_NO_HORIZON_BAR = "no_horizon_bar"

# Mandate horizon → calendar days. See the module docstring for why calendar
# days are correct here (the store supplies the trading calendar).
HORIZON_DAYS: dict[str, int] = {
    Horizon.SHORT.value: 21,
    Horizon.MEDIUM.value: 63,
    Horizon.LONG.value: 126,
    Horizon.VERY_LONG.value: 252,
}
_DEFAULT_HORIZON_DAYS = HORIZON_DAYS[Horizon.MEDIUM.value]

# The verdict actions that carry a call worth scoring. An abstain has no call
# to score: NO_VERDICT is built in code when the Market desk withheld (CR098
# Amendment 2 / DEF376 / R51), so banking one would record a "decision" the
# Room explicitly declined to make. REJECT and MODIFY are absent for the same
# reason the aggregates only contrast APPROVE with PASS — those two are the
# floor's comparison, and a bucket of three MODIFYs answers nothing.
BANKABLE_ACTIONS = frozenset({VerdictAction.APPROVE.value, VerdictAction.PASS.value})

# Bucket labels for the graded CR214 conviction signal. The `Verdict` schema
# has NO conviction field — the PM never states one — so `approve_votes` out of
# `samples` (how many independent CIO samples wanted in) is the only
# conviction-shaped quantity the Room actually produces. `None` when
# self-consistency is off or the run predates CR214: absence is absence, never
# backfilled (T-BACKFILL).
CONVICTION_HIGH = "high"
CONVICTION_MEDIUM = "medium"
CONVICTION_LOW = "low"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(stamp: datetime | None) -> datetime | None:
    """sqlite round-trips naive datetimes; every writer here stamps UTC."""
    if stamp is None:
        return None
    return stamp if stamp.tzinfo is not None else stamp.replace(tzinfo=timezone.utc)


def conviction_bucket(approve_votes: int | None, samples: int | None) -> str | None:
    """The CR214 vote fraction as a coarse label, or None when ungraded.

    Deliberately three wide buckets rather than the raw fraction: with n=5 the
    fraction takes six values and a bucket-vs-hit-rate table over six levels on
    Alpha-scale volumes is noise. `>=0.8` high, `>=0.4` medium, else low.
    """
    if not samples or approve_votes is None or samples <= 0:
        return None
    frac = approve_votes / samples
    if frac >= 0.8:
        return CONVICTION_HIGH
    if frac >= 0.4:
        return CONVICTION_MEDIUM
    return CONVICTION_LOW


def horizon_days_for(horizon: str | None, verdict_horizon_days: int | None) -> int:
    """Concrete scoring horizon for a run.

    The PM's own stated `time_horizon_days` wins when present — a call made on
    a 10-day thesis should be scored at 10 days, not at the mandate's default
    quarter. Falls back to the mandate horizon map, then to medium.

    Accepts the horizon as either a `str` or a `Horizon` member. `Mandate` sets
    `use_enum_values=True`, so in practice it arrives as a string — but the
    annotation says `Horizon`, and that mismatch already cost one broken hook
    (`'str' object has no attribute 'value'` on every real convene). Normalise
    here rather than trusting each caller to guess which one it holds: a caller
    that guesses wrong the OTHER way would pass `Horizon.LONG`, miss the map,
    and silently score every long-horizon call at the medium default — a wrong
    number rather than a crash, which is the worse failure.
    """
    if verdict_horizon_days is not None and verdict_horizon_days > 0:
        return int(verdict_horizon_days)
    key = getattr(horizon, "value", horizon)
    return HORIZON_DAYS.get(str(key or "").lower(), _DEFAULT_HORIZON_DAYS)


# ── Exclusions ──────────────────────────────────────────────────────────────

def excluded_user_ids() -> set[UUID]:
    """The user ids the standing Alpha analytics exclusions remove.

    Reuses `admin_analytics._real_users_clause()` verbatim rather than minting
    a sixth hand-synced copy of the rule — the CR051 lineage already has five
    (`scripts/analytics/daily_report.py`, `scripts/users.sh`,
    `admin_analytics.py`, `inbox_store.py`, `scripts/weekly_room_retro.py`) and
    they have already drifted: only the two ORM copies carry the 12 by-id probe
    exclusions. Importing the most complete one keeps this ledger from becoming
    the sixth divergence.

    Covers: 13 CR035 room-benchmark synthetics (`last_app_version =
    'room-benchmark'`), the 10 seed fixtures (created in the one-minute burst
    [2026-05-24 05:10, 05:11) UTC with NULL `device_model` AND NULL
    `last_app_version` — all three conjuncts required), and 12 CR125/DEF227-229
    probe users by id (shape-indistinguishable from real bare sessions).

    Returns the complement — the ids to EXCLUDE — by selecting every user the
    clause rejects, so the ledger and the console can never disagree about who
    is real.
    """
    with get_session() as s:
        return {
            uid for (uid,) in s.execute(
                select(User.id).where(~_real_users_clause())
            ).all()
        }


def is_excluded_user(user_id: UUID) -> bool:
    """Single-user form of `excluded_user_ids`, for the writer hook."""
    with get_session() as s:
        row = s.execute(
            select(User.id).where(User.id == user_id, ~_real_users_clause())
        ).scalar_one_or_none()
    return row is not None


# ── Writer ──────────────────────────────────────────────────────────────────

def bank_verdict_outcome(
    *,
    room_run_id: UUID,
    user_id: UUID,
    ticker: str,
    verdict: Any,
    reference_price: float | None,
    reference_at: datetime | None = None,
    mandate_horizon: str | None = None,
) -> UUID | None:
    """Record one COMPLETED run's verdict in the ledger. Idempotent per run.

    Returns the ledger row id, or None when the verdict carries no call to
    score (an abstain, a missing verdict, or an action outside
    `BANKABLE_ACTIONS`). Never raises into the caller: the Room banking a run
    must not fail because a calibration ledger had a bad day, so every
    exception is logged and swallowed. That is safe here precisely because
    nothing user-facing reads this table.

    `reference_price` is the price the Room saw (`_reference_close(profile)`).
    A None reference banks the row as `unscorable` rather than skipping it —
    the count of runs the ledger COULD NOT score is itself the measurement of
    how often the Room decides without a live price.
    """
    try:
        action = getattr(verdict, "action", None)
        action = getattr(action, "value", action)
        if action not in BANKABLE_ACTIONS:
            return None

        ref_at = _as_utc(reference_at) or _utcnow()
        approve_votes = getattr(verdict, "approve_votes", None)
        samples = getattr(verdict, "samples", None)
        h_days = horizon_days_for(
            mandate_horizon, getattr(verdict, "time_horizon_days", None),
        )

        if is_excluded_user(user_id):
            status, reason = STATUS_UNSCORABLE, REASON_EXCLUDED_USER
        elif reference_price is None:
            status, reason = STATUS_UNSCORABLE, REASON_NO_REFERENCE_PRICE
        else:
            status, reason = STATUS_PENDING, None

        with get_session() as s:
            existing = s.execute(
                select(VerdictOutcomeRow).where(
                    VerdictOutcomeRow.room_run_id == room_run_id
                )
            ).scalar_one_or_none()
            if existing is not None:
                # A re-persist of the same run (the Room upserts) must update,
                # never duplicate — and must never un-score a scored row.
                if existing.status != STATUS_SCORED:
                    existing.verdict_action = str(action)
                    existing.conviction = conviction_bucket(approve_votes, samples)
                    existing.approve_votes = approve_votes
                    existing.samples = samples
                    existing.size_pct = getattr(verdict, "size_pct", None)
                    existing.reference_price = reference_price
                    existing.reference_at = ref_at
                    existing.horizon_days = h_days
                    existing.status = status
                    existing.exclusion_reason = reason
                return existing.id

            row = VerdictOutcomeRow(
                room_run_id=room_run_id,
                user_id=user_id,
                ticker=(ticker or "").upper().strip(),
                verdict_action=str(action),
                conviction=conviction_bucket(approve_votes, samples),
                approve_votes=approve_votes,
                samples=samples,
                size_pct=getattr(verdict, "size_pct", None),
                reference_price=reference_price,
                reference_at=ref_at,
                horizon_days=h_days,
                status=status,
                exclusion_reason=reason,
            )
            s.add(row)
            s.flush()
            return row.id
    except Exception as exc:  # noqa: BLE001 — see docstring
        logger.warning(
            "verdict_outcome_bank_failed", run_id=str(room_run_id), error=str(exc),
        )
        return None


# ── Scorer ──────────────────────────────────────────────────────────────────

def _horizon_close(ticker: str, target: date) -> tuple[float, date] | None:
    """The newest real stored close at or before `target`, or None.

    Excludes `mock_walk` rows UNCONDITIONALLY — not only in real mode. A
    calibration ledger scored against a random walk reports a hit rate it never
    measured, so a mock-only ticker yields no price and the row goes
    `unscorable` with `mock_price_source`, exactly the way
    `get_asof_daily_rows` refuses fabricated bars for a backtest.
    """
    with get_session() as s:
        row = s.execute(
            select(PriceHistoryDailyRow)
            .where(PriceHistoryDailyRow.ticker == ticker.upper().strip())
            .where(PriceHistoryDailyRow.date <= target)
            .where(PriceHistoryDailyRow.source != _MOCK_SOURCE)
            .order_by(PriceHistoryDailyRow.date.desc())
            .limit(1)
        ).scalar_one_or_none()
        if row is None:
            return None
        return float(row.adj_close), row.date


def _has_mock_only_history(ticker: str, target: date) -> bool:
    """True when the store holds bars at/before `target` but ALL are mock.

    Separates "we have no data yet" (`no_horizon_bar`, may become scorable
    later) from "everything we have is fabricated" (`mock_price_source`, never
    will be). Both are unscorable; conflating them would hide a mock-mode
    environment quietly filling the ledger with dead rows.
    """
    with get_session() as s:
        n = s.execute(
            select(func.count()).select_from(PriceHistoryDailyRow)
            .where(PriceHistoryDailyRow.ticker == ticker.upper().strip())
            .where(PriceHistoryDailyRow.date <= target)
        ).scalar_one()
    return bool(n)


def score_pending(*, now: datetime | None = None, limit: int = 1000) -> dict[str, int]:
    """Score every `pending` row whose horizon has elapsed. Idempotent.

    Re-running scores nothing twice: only `status == 'pending'` rows are
    selected, and a scored row's status flips out of that set. Rows whose
    horizon has NOT elapsed are left alone — the counter reports them so a
    daily run's output shows the ledger is alive rather than silent.

    Returns counts by outcome: scored / not_due / unscorable_mock /
    unscorable_no_bar / unscorable_no_reference / excluded. The unscorable
    reasons are counted SEPARATELY rather than summed — "the store has no bar
    yet" is transient and may resolve on a later run, "every bar is fabricated"
    never will, and "the Room decided without a live price" is a fact about the
    Room rather than about the data feed. A single lumped counter would hide
    which of the three is growing, which is the only thing the number is for.
    """
    now = _as_utc(now) or _utcnow()
    counts = {
        "scored": 0, "not_due": 0, "unscorable_mock": 0,
        "unscorable_no_bar": 0, "unscorable_no_reference": 0, "excluded": 0,
    }
    excluded = excluded_user_ids()

    with get_session() as s:
        rows = list(s.execute(
            select(VerdictOutcomeRow)
            .where(VerdictOutcomeRow.status == STATUS_PENDING)
            .order_by(VerdictOutcomeRow.reference_at)
            .limit(limit)
        ).scalars().all())
        pending = [
            (r.id, r.ticker, _as_utc(r.reference_at), r.horizon_days,
             float(r.reference_price) if r.reference_price is not None else None,
             r.user_id)
            for r in rows
        ]

    for row_id, ticker, ref_at, h_days, ref_price, user_id in pending:
        if user_id in excluded:
            _finish(row_id, STATUS_UNSCORABLE, reason=REASON_EXCLUDED_USER, now=now)
            counts["excluded"] += 1
            continue
        if ref_price is None:
            _finish(
                row_id, STATUS_UNSCORABLE, reason=REASON_NO_REFERENCE_PRICE, now=now,
            )
            counts["unscorable_no_reference"] += 1
            continue

        due_at = (ref_at or now) + timedelta(days=h_days)
        if due_at > now:
            counts["not_due"] += 1
            continue

        target = due_at.date()
        hit = _horizon_close(ticker, target)
        if hit is None:
            if _has_mock_only_history(ticker, target):
                _finish(row_id, STATUS_UNSCORABLE, reason=REASON_MOCK_PRICE, now=now)
                counts["unscorable_mock"] += 1
            else:
                counts["unscorable_no_bar"] += 1
                _finish(
                    row_id, STATUS_UNSCORABLE, reason=REASON_NO_HORIZON_BAR, now=now,
                )
            continue

        outcome_price, outcome_date = hit
        fwd = (outcome_price - ref_price) / ref_price if ref_price else None
        _finish(
            row_id, STATUS_SCORED, now=now,
            outcome_price=outcome_price, outcome_date=outcome_date, forward_return=fwd,
        )
        counts["scored"] += 1

    logger.info("verdict_outcomes_scored", **counts)
    return counts


def _finish(
    row_id: UUID,
    status: str,
    *,
    now: datetime,
    reason: str | None = None,
    outcome_price: float | None = None,
    outcome_date: date | None = None,
    forward_return: float | None = None,
) -> None:
    with get_session() as s:
        row = s.execute(
            select(VerdictOutcomeRow).where(VerdictOutcomeRow.id == row_id)
        ).scalar_one_or_none()
        if row is None or row.status == STATUS_SCORED:
            return
        row.status = status
        row.exclusion_reason = reason
        row.outcome_price = outcome_price
        row.outcome_date = outcome_date
        row.forward_return = forward_return
        row.scored_at = now


# ── Aggregates (internal, admin-gated) ──────────────────────────────────────

def _summarise(values: list[float]) -> dict[str, Any]:
    """n / mean / median / min / max for one bucket of forward returns.

    No standard error, no t-statistic, no p-value. A significance test printed
    beside these numbers would invite exactly the reading the module docstring
    forbids — this is a floor check, and a floor check needs the distribution's
    shape, not an inference that the difference is real.
    """
    if not values:
        return {"n": 0, "mean": None, "median": None, "min": None, "max": None}
    ordered = sorted(values)
    mid = len(ordered) // 2
    median = (
        ordered[mid] if len(ordered) % 2
        else (ordered[mid - 1] + ordered[mid]) / 2.0
    )
    return {
        "n": len(ordered),
        "mean": sum(ordered) / len(ordered),
        "median": median,
        "min": ordered[0],
        "max": ordered[-1],
    }


def aggregates() -> dict[str, Any]:
    """The internal calibration read. JSON only, admin-gated, never user-facing.

    Three blocks:
      `by_status`   row counts per lifecycle status + exclusion reasons — the
                    denominator, so a reader can see how much of the ledger is
                    actually scored before reading any distribution.
      `by_action`   APPROVE vs PASS forward-return distribution. The floor:
                    APPROVEs should not be systematically WORSE than PASSes.
      `conviction`  hit rate (share of positive forward returns) per graded
                    CR214 vote bucket, APPROVEs only — "high conviction means
                    something" is a claim about the calls the Room made, and a
                    PASS has no conviction to calibrate.

    `interpretation` carries the framing in the payload itself so a reader who
    reaches the JSON without reading this module still cannot mistake it for a
    performance claim.
    """
    with get_session() as s:
        status_rows = s.execute(
            select(VerdictOutcomeRow.status, func.count())
            .group_by(VerdictOutcomeRow.status)
        ).all()
        reason_rows = s.execute(
            select(VerdictOutcomeRow.exclusion_reason, func.count())
            .where(VerdictOutcomeRow.exclusion_reason.isnot(None))
            .group_by(VerdictOutcomeRow.exclusion_reason)
        ).all()
        scored = s.execute(
            select(
                VerdictOutcomeRow.verdict_action,
                VerdictOutcomeRow.conviction,
                VerdictOutcomeRow.forward_return,
            )
            .where(VerdictOutcomeRow.status == STATUS_SCORED)
            .where(VerdictOutcomeRow.forward_return.isnot(None))
        ).all()

    by_action: dict[str, list[float]] = {}
    buckets: dict[str, list[float]] = {}
    for action, conviction, fwd in scored:
        by_action.setdefault(str(action), []).append(float(fwd))
        if action == VerdictAction.APPROVE.value and conviction:
            buckets.setdefault(str(conviction), []).append(float(fwd))

    return {
        "by_status": {str(k): int(v) for k, v in status_rows},
        "exclusion_reasons": {str(k): int(v) for k, v in reason_rows},
        "by_action": {k: _summarise(v) for k, v in sorted(by_action.items())},
        "conviction": {
            k: {
                "n": len(v),
                "hit_rate": (sum(1 for x in v if x > 0) / len(v)) if v else None,
                "mean_forward_return": (sum(v) / len(v)) if v else None,
            }
            for k, v in sorted(buckets.items())
        },
        "interpretation": (
            "Internal calibration floor only. This is NOT a performance claim, "
            "an alpha claim, or a track record — AMI Trade is a simulation-only "
            "education product. The ledger answers two floor questions: are "
            "APPROVEs systematically worse than PASSes, and does the graded "
            "conviction signal separate at all. Read the by_status counts first: "
            "a small scored denominator means neither question is answerable yet."
        ),
    }
