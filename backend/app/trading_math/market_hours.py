"""US regular-session market hours — CR109 slice 2's queue-vs-fill gate.

No reliable "is the market open right now" signal exists elsewhere in this
codebase. `market_data.Quote.market_state` looks like the natural reuse, but
`price_history.py`'s `_should_fetch` docstring already documents why it
can't be trusted: "there is no trading calendar to consult, and
`Quote.market_state` cannot substitute for one (only the legacy-fallback
`YahooQuoteProvider` ever sets it; the production `YfinanceProvider.quote`
leaves it at the `CLOSED` default, always)". The game's "did this fill
happen for real or on hindsight" gate needs an answer that holds on the
PRODUCTION provider stack, so it is computed from wall-clock time instead.

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
