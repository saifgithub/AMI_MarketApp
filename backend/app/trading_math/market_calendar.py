"""Per-market sessions and trading days (CR282 lane B).

The single answer to "is this market open / when does its day end / which
trading day is it" for every market in `markets.py`. US is a thin delegation to
the existing, unchanged `market_hours` / `session_calendar` functions so US
behaviour stays byte-identical (including `market_hours`' deliberate absence of
holidays for the open/closed gate). Malaysia is modelled here.

Bursa Malaysia, Mon-Fri, Asia/Kuala_Lumpur (no DST, so no clock-change cases):

    09:00-12:30   morning continuous
    12:30-14:30   lunch break  -> CLOSED
    14:30-16:45   afternoon continuous
    16:45-16:50   pre-close
    16:50         closing auction
    16:50-17:00   trading-at-last at the auction price

The simulator's fillable window is 09:00-12:30 and 14:30-16:50: continuous
trading plus the pre-close, ending at the auction. The 16:50-17:00 trading-at-last
leg is excluded because it trades only at the auction price, which a simulator
reading a delayed quote cannot reproduce — a fill there would be a price Bursa
never printed to that order. A day's close is therefore 16:50, and a resting
order's DAY expiry is 16:50 KL.

Holidays come from `bursa_holidays` (a table, never a formula). Outside the
table's years the calendar cannot know whether a weekday is a holiday, so it
raises `CalendarUnavailable` — callers surface that as UNKNOWN / a loud error,
never as "open" (CR040: degrade loudly).

Pure — no DB, no network.
"""

from __future__ import annotations

from datetime import date, datetime, time as dt_time, timedelta
from zoneinfo import ZoneInfo

from app.trading_math.bursa_holidays import BURSA_HOLIDAYS, FIRST_YEAR, LAST_YEAR
from app.trading_math.market_hours import (
    is_us_market_open,
    next_us_market_open,
    session_close_on_or_after as _us_session_close_on_or_after,
)
from app.trading_math.markets import Market, spec_for
from app.trading_math.session_calendar import is_us_session_day, last_us_session_date

_UTC = ZoneInfo("UTC")
_ONE_DAY = timedelta(days=1)

#: Fillable windows per local day, in order. The gap between them is closed.
MY_SESSIONS: tuple[tuple[dt_time, dt_time], ...] = (
    (dt_time(9, 0), dt_time(12, 30)),
    (dt_time(14, 30), dt_time(16, 50)),
)


class CalendarUnavailable(ValueError):
    """The market's holiday table does not cover this date, so its state is unknown."""

    def __init__(self, market: Market, day: date) -> None:
        self.market = market
        self.day = day
        super().__init__(
            f"{market.value} holiday table covers {FIRST_YEAR}-{LAST_YEAR}; "
            f"{day.isoformat()} is outside it — refresh bursa_holidays"
        )


def _aware(now: datetime) -> datetime:
    return now.replace(tzinfo=_UTC) if now.tzinfo is None else now


def _tz(market: Market) -> ZoneInfo:
    return ZoneInfo(spec_for(market).timezone)


def is_my_session_day(d: date) -> bool:
    if not FIRST_YEAR <= d.year <= LAST_YEAR:
        raise CalendarUnavailable(Market.MY, d)
    return d.weekday() < 5 and d not in BURSA_HOLIDAYS


def _my_session_day_on_or_after(d: date) -> date:
    while not is_my_session_day(d):
        d += _ONE_DAY
    return d


def is_market_open(market: Market, now_utc: datetime) -> bool:
    """Inside a fillable session. Raises `CalendarUnavailable` beyond the table (MY)."""
    if market is Market.US:
        return is_us_market_open(now_utc)
    local = _aware(now_utc).astimezone(_tz(market))
    if not is_my_session_day(local.date()):
        return False
    t = local.time()
    return any(o <= t < c for o, c in MY_SESSIONS)


def next_market_open(market: Market, now_utc: datetime) -> datetime:
    """The next session open at/after `now_utc` (the live session's own open if
    inside one), in UTC."""
    if market is Market.US:
        return next_us_market_open(now_utc)
    tz = _tz(market)
    local = _aware(now_utc).astimezone(tz)
    day = local.date()
    if is_my_session_day(day):
        for o, c in MY_SESSIONS:
            if local.time() < c:
                return datetime.combine(day, o, tzinfo=tz).astimezone(_UTC)
    day = _my_session_day_on_or_after(day + _ONE_DAY)
    return datetime.combine(day, MY_SESSIONS[0][0], tzinfo=tz).astimezone(_UTC)


def session_close_on_or_after(market: Market, now_utc: datetime) -> datetime:
    """The close of the trading DAY that applies at `now_utc`, in UTC.

    Same rule as the US function ("our 'day' should be the trading day of the
    market, not the local time day"): inside or before a session day, that day's
    final close; after it, or on a rest day or holiday, the next session day's.
    Midday on a Bursa session day the answer is still the day's 16:50, not the
    12:30 lunch close — a DAY order must survive the break.
    """
    if market is Market.US:
        return _us_session_close_on_or_after(now_utc)
    tz = _tz(market)
    local = _aware(now_utc).astimezone(tz)
    day = local.date()
    final_close = MY_SESSIONS[-1][1]
    if not (is_my_session_day(day) and local.time() < final_close):
        day = _my_session_day_on_or_after(day + _ONE_DAY)
    return datetime.combine(day, final_close, tzinfo=tz).astimezone(_UTC)


def trading_date(market: Market, now_utc: datetime) -> date:
    """The trading day `now_utc` belongs to: the market's local calendar date,
    rolled back to the latest earlier session day over weekends and holidays."""
    if market is Market.US:
        return last_us_session_date(now_utc)
    day = _aware(now_utc).astimezone(_tz(market)).date()
    while not is_my_session_day(day):
        day -= _ONE_DAY
    return day


def is_session_day(market: Market, d: date) -> bool:
    return is_us_session_day(d) if market is Market.US else is_my_session_day(d)
