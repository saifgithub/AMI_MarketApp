"""US equities session calendar — "which trading day is it" for the Room bank.

CR267 WP-24 freezes a Room's fact sheet per ticker per trading day, so the day
needs a definition: the America/New_York calendar date, rolled back to the last
session when that date is a weekend or an NYSE full-day holiday. Early closes
(day after Thanksgiving, Christmas Eve) are sessions.

`market_hours.py` deliberately models no holidays (an order-queue simplification
stated in its docstring); this module does, because here a wrong answer would
either split one day into two rooms or serve Monday's Room on a Tuesday.

Pure — no DB, no network. The holiday rules are the NYSE's published schedule:
fixed-date holidays observe on the nearest weekday (Sat -> Fri, Sun -> Mon), except
New Year's Day, which on a Saturday is not observed at all.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

_ET = ZoneInfo("America/New_York")
_UTC = ZoneInfo("UTC")


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    last = nxt - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _easter(year: int) -> date:
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    el = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * el) // 451
    month = (h + el - 7 * m + 114) // 31
    day = (h + el - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def _observed(d: date) -> date | None:
    if d.weekday() == 5:
        return d - timedelta(days=1)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


def nyse_holidays(year: int) -> frozenset[date]:
    """NYSE full-day closures that fall inside calendar `year`."""
    days: set[date] = set()
    jan1 = date(year, 1, 1)
    if jan1.weekday() != 5:  # a Saturday New Year's Day is not observed
        days.add(_observed(jan1))  # type: ignore[arg-type]
    days.add(_nth_weekday(year, 1, 0, 3))   # Martin Luther King Jr. Day
    days.add(_nth_weekday(year, 2, 0, 3))   # Washington's Birthday
    days.add(_easter(year) - timedelta(days=2))  # Good Friday
    days.add(_last_weekday(year, 5, 0))     # Memorial Day
    if year >= 2022:
        days.add(_observed(date(year, 6, 19)))  # type: ignore[arg-type]  # Juneteenth
    days.add(_observed(date(year, 7, 4)))   # type: ignore[arg-type]  # Independence Day
    days.add(_nth_weekday(year, 9, 0, 1))   # Labor Day
    days.add(_nth_weekday(year, 11, 3, 4))  # Thanksgiving
    days.add(_observed(date(year, 12, 25))) # type: ignore[arg-type]  # Christmas
    return frozenset(d for d in days if d.year == year)


def is_us_session_day(d: date) -> bool:
    return d.weekday() < 5 and d not in nyse_holidays(d.year)


def last_us_session_date(now_utc: datetime) -> date:
    """The trading day `now_utc` belongs to: its New York calendar date, or the
    latest earlier session when that date is a weekend or holiday.

    `now_utc` may be naive (treated as UTC) or aware.
    """
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=_UTC)
    day = now_utc.astimezone(_ET).date()
    while not is_us_session_day(day):
        day -= timedelta(days=1)
    return day
