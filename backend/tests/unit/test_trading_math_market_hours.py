"""CR109 slice 2 — `trading_math/market_hours.py`'s pure US-session gate.

Standalone from the DB-touching games tests: this is the pure function the
market-hours rule rests on, so it gets its own direct coverage.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.trading_math.market_hours import is_us_market_open, next_us_market_open


def test_weekday_regular_session_is_open():
    # Monday 2026-08-10, 15:00 UTC = 11:00 ET — inside 09:30-16:00.
    assert is_us_market_open(datetime(2026, 8, 10, 15, 0, tzinfo=timezone.utc)) is True


def test_weekend_is_closed():
    # Saturday 2026-08-08, midday UTC.
    assert is_us_market_open(datetime(2026, 8, 8, 15, 0, tzinfo=timezone.utc)) is False


def test_weekday_before_open_is_closed():
    # Monday 2026-08-10, 03:00 UTC = Sunday 23:00 ET — before Monday's open.
    assert is_us_market_open(datetime(2026, 8, 10, 3, 0, tzinfo=timezone.utc)) is False


def test_weekday_after_close_is_closed():
    # Monday 2026-08-10, 21:00 UTC = 17:00 ET — after the 16:00 close.
    assert is_us_market_open(datetime(2026, 8, 10, 21, 0, tzinfo=timezone.utc)) is False


def test_naive_datetime_treated_as_utc():
    assert is_us_market_open(datetime(2026, 8, 10, 15, 0)) is True


def test_next_open_from_a_weekend_rolls_to_monday():
    next_open = next_us_market_open(datetime(2026, 8, 8, 15, 0, tzinfo=timezone.utc))
    assert next_open.astimezone(timezone.utc).date().isoformat() == "2026-08-10"


def test_next_open_from_inside_a_live_session_is_todays_own_open():
    now = datetime(2026, 8, 10, 15, 0, tzinfo=timezone.utc)  # already open (11:00 ET)
    next_open = next_us_market_open(now)
    # 09:30 ET on the same Monday, expressed in UTC (EDT = UTC-4 in August).
    assert next_open == datetime(2026, 8, 10, 13, 30, tzinfo=timezone.utc)


def test_next_open_from_pre_market_same_day():
    now = datetime(2026, 8, 10, 11, 0, tzinfo=timezone.utc)  # 07:00 ET, before open
    next_open = next_us_market_open(now)
    assert next_open == datetime(2026, 8, 10, 13, 30, tzinfo=timezone.utc)
    assert next_open - now < timedelta(hours=3)
