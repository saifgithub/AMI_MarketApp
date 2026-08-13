"""US regular-session market hours — CR109 slice 2's queue-vs-fill gate.

No reliable "is the market open right now" signal exists elsewhere in this
codebase. `market_data.Quote.market_state` looks like the natural reuse, but
cannot substitute for a trading calendar. **The stated reason went stale and
CR170 §2 corrects it here:** this docstring used to say the production
`YfinanceProvider.quote` leaves `market_state` at the `CLOSED` default always,
which DEF252 made false — `market_data.py:586` now derives `market_state` from
`is_us_market_open()`, i.e. from *this module*. The conclusion is unchanged and
in fact stronger: reading it back would be circular, not merely uninformative.
So the gate is computed from wall-clock time here, and everything else derives
from that one answer.

Pure — no DB, no network — matching `trading_math/twr.py`'s contract.

US equities regular session: Mon-Fri, 09:30-16:00 America/New_York.
Deliberately does NOT model NYSE market holidays (Thanksgiving, Christmas,
the half-days, etc.) — an accepted slice-2 simplification, same shape as
G3's "measure first" stance on quote lag in the CR109 design (§12.1): a
holiday reads as "open" here, so a fill attempt during a real holiday
closure gets whatever price the provider stack serves. Revisit if that
turns up exploit pressure; not worth the calendar-maintenance cost before
there is a board to protect.
"""

from __future__ import annotations

from datetime import datetime, time as dt_time, timedelta
from zoneinfo import ZoneInfo

_ET = ZoneInfo("America/New_York")
_OPEN = dt_time(9, 30)
_CLOSE = dt_time(16, 0)
_ONE_DAY = timedelta(days=1)


def is_us_market_open(now_utc: datetime) -> bool:
    """True inside the Mon-Fri 09:30-16:00 America/New_York regular session.

    `now_utc` may be naive (treated as UTC, matching every other `now`
    convention in this codebase) or aware.
    """
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=ZoneInfo("UTC"))
    local = now_utc.astimezone(_ET)
    if local.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    return _OPEN <= local.time() < _CLOSE


def next_us_market_open(now_utc: datetime) -> datetime:
    """The next regular-session open at/after `now_utc`, returned in UTC.

    If `now_utc` already falls inside a live session, returns THAT
    session's own open (today) — a caller already knows a live session
    doesn't queue; this is for orders placed outside one, to show a
    deadline ("your order queues, fills at the open on <date>").
    """
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=ZoneInfo("UTC"))
    local = now_utc.astimezone(_ET)
    day = local.date()
    if local.weekday() >= 5 or local.time() >= _CLOSE:
        day = day + _ONE_DAY
        while day.weekday() >= 5:
            day = day + _ONE_DAY
    open_at = datetime.combine(day, _OPEN, tzinfo=_ET)
    return open_at.astimezone(ZoneInfo("UTC"))


def session_close_on_or_after(now_utc: datetime) -> datetime:
    """CR170 §2 — the 16:00 ET close of the session that applies at `now_utc`.

    Every resting order's `expires_at` is one of these. Saiful's correction is
    load-bearing: *"our 'day' should be the trading day of the market, not the
    local time day."* A TIF anchored to a local calendar boundary would expire a
    Malaysian user's DAY order at a different moment than an American's, for the
    same order on the same tape.

    One rule — the close of whichever session opens next — and no special cases:

      - Tuesday 11:00 ET, inside a live session → **Tuesday 16:00 ET**
      - Tuesday 08:00 ET, before the open       → **Tuesday 16:00 ET**
      - Tuesday 21:00 ET, after the close       → **Wednesday 16:00 ET**
      - Saturday, any time                      → **Monday 16:00 ET**

    GTD_30 / GTD_90 apply the same function to `placed_at + N days`, which is
    why "the trading day on or after" needs no separate implementation.

    Inherits this module's deliberate absence of an NYSE holiday calendar, so an
    expiry can land on a holiday. Accepted and stated (CR170 §2); the
    alternative is a calendar to maintain, and the cost of being wrong is an
    order expiring one session early.
    """
    open_at = next_us_market_open(now_utc)
    local_open = open_at.astimezone(_ET)
    close_at = datetime.combine(local_open.date(), _CLOSE, tzinfo=_ET)
    return close_at.astimezone(ZoneInfo("UTC"))
