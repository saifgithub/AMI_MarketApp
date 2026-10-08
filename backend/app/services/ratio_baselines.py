"""CR253 lane B(a) — rolling historical baselines for emitted daily ratios.

The "is 0.46 high?" problem: the sheet states a put/call ratio or a Reddit
sentiment score as a single point with nothing to compare it against, so
the agent reaches for training memory to judge it — the exact behaviour the
grounding directive forbids. This module gives every emitted ratio a
baseline companion computed from the ticker's OWN history:

  * Every successful live read of a baseline-bearing metric upserts one
    observation row per (ticker, metric, calendar day) — the read already
    happened for the sheet; persisting it costs one write.
  * `trailing_baseline` medians the trailing `_BASELINE_WINDOW_DAYS`
    EXCLUDING today (a baseline that contains the value being judged is not
    a baseline), and exists only once `_MIN_BASELINE_DAYS` distinct days are
    on file.
  * Nothing is fabricated: a day with no live read writes no row, and the
    renderers state "no baseline on file" rather than inventing one (CR040).
    Absence stays absence — a young store is a young store, said out loud.

Computed in code (CR179 Leg 4): the median is `statistics.median` here,
never the model's. Store failures degrade loudly and never raise through
the overlay: a lost baseline costs the companion line, never the convene
(the `_overlay_put_call` precedent).

Metrics are namespaced constants so the put/call overlay, the social
overlay, and the tests cannot drift apart on spelling.
"""

from __future__ import annotations

import math
import statistics
import threading
from datetime import UTC, date, datetime, timedelta
from typing import NamedTuple

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.core.logging import logger
from app.db.models import RatioBaselineRow
from app.db.session import get_session

# The put/call overlay's two ratios and the live-social overlay's two reads.
METRIC_PUT_CALL_VOLUME = "put_call_volume"
METRIC_PUT_CALL_OI = "put_call_oi"
METRIC_SENTIMENT_SCORE = "sentiment_score"
METRIC_MENTION_VOLUME = "mention_volume"

# The trailing window the sheet names on the line ("trailing-90d").
_BASELINE_WINDOW_DAYS = 90
# Below this many distinct observed days a median is two points wearing a
# baseline's clothes — the sheet says "no baseline on file yet" instead.
_MIN_BASELINE_DAYS = 5


class RatioBaseline(NamedTuple):
    """The trailing baseline itself: the window's median and its honest n."""

    median: float
    n: int
    window_days: int


def record_observation(
    ticker: str, metric: str, value: float, *, on: date | None = None,
) -> None:
    """Upsert one (ticker, metric, day) observation. One row per day: a
    second convene the same day replaces the read, because the baseline
    describes days, not convenes. Never raises — a store failure logs and
    costs the baseline, never the convene (the overlay precedent).

    Insert-first with an IntegrityError re-read-and-update (failure_patterns
    P15): the daily row is a unique-constraint upsert, so a concurrent
    convene that commits first is handled, not raced — and the loser's read
    still applies, last write wins per day.
    """
    sym = ticker.upper().strip()
    if not sym or not metric or not math.isfinite(value):
        logger.warn("ratio_baseline_bad_observation", ticker=sym, metric=metric)
        return
    day = on or datetime.now(UTC).date()
    try:
        with get_session() as s:
            try:
                s.add(RatioBaselineRow(ticker=sym, metric=metric, observed_on=day, value=value))
                s.commit()
            except IntegrityError:
                s.rollback()
                row = s.execute(
                    select(RatioBaselineRow).where(
                        RatioBaselineRow.ticker == sym,
                        RatioBaselineRow.metric == metric,
                        RatioBaselineRow.observed_on == day,
                    )
                ).scalar_one_or_none()
                if row is not None:
                    row.value = value
                    s.commit()
    except Exception as exc:
        logger.warn(
            "ratio_baseline_record_failed",
            ticker=sym, metric=metric, error=f"{type(exc).__name__}: {exc}",
        )


def trailing_baseline(
    ticker: str, metric: str, *, today: date | None = None,
) -> RatioBaseline | None:
    """The median of `metric`'s stored observations over the trailing window
    EXCLUDING `today`, or None until `_MIN_BASELINE_DAYS` distinct days
    exist. Never fabricates: no observations, no baseline.

    Today is excluded because the baseline exists to judge today's read —
    a window that contains the value being judged is not a baseline.
    """
    sym = ticker.upper().strip()
    day = today or datetime.now(UTC).date()
    window_start = day - timedelta(days=_BASELINE_WINDOW_DAYS)
    try:
        with get_session() as s:
            values = s.execute(
                select(RatioBaselineRow.value).where(
                    RatioBaselineRow.ticker == sym,
                    RatioBaselineRow.metric == metric,
                    RatioBaselineRow.observed_on >= window_start,
                    RatioBaselineRow.observed_on < day,
                ).order_by(RatioBaselineRow.observed_on)
            ).scalars().all()
    except Exception as exc:
        logger.warn(
            "ratio_baseline_read_failed",
            ticker=sym, metric=metric, error=f"{type(exc).__name__}: {exc}",
        )
        return None
    if len(values) < _MIN_BASELINE_DAYS:
        return None
    return RatioBaseline(
        median=round(statistics.median(values), 2),
        n=len(values),
        window_days=_BASELINE_WINDOW_DAYS,
    )


def comparison_clause(
    label: str, today_value: float, baseline: RatioBaseline | None, *,
    decimals: int = 2, signed: bool = True,
) -> str | None:
    """The rendered companion for one metric: "sentiment score 0.42 vs
    trailing-90d median +0.05 (9 daily reads on file)", or None when no
    baseline exists — the CALLER states the absence loudly (CR040), this
    helper never invents a figure. `signed=False` drops the +/- sign for
    unsigned quantities like mention counts.
    """
    if baseline is None:
        return None
    sign = "+" if (signed and baseline.median >= 0) else ""
    today = f"{today_value:+.{decimals}f}" if signed else f"{today_value:.{decimals}f}"
    return (
        f"{label} {today} vs trailing-{baseline.window_days}d median "
        f"{sign}{baseline.median:.{decimals}f} ({baseline.n} daily reads on file)"
    )


def no_baseline_clause() -> str:
    """The explicit honest absence, shared wording across lanes."""
    return (
        f"no baseline on file yet — fewer than {_MIN_BASELINE_DAYS} daily "
        f"reads in the trailing {_BASELINE_WINDOW_DAYS} days; judge the "
        "level against its own context, not against a number you were not given"
    )


# Test seam: drop every observation without dropping the schema.
def clear_observations() -> None:
    with _clear_lock:
        try:
            with get_session() as s:
                s.execute(delete(RatioBaselineRow))
                s.commit()
        except Exception as exc:
            logger.warn("ratio_baseline_clear_failed", error=f"{type(exc).__name__}: {exc}")


_clear_lock = threading.Lock()
