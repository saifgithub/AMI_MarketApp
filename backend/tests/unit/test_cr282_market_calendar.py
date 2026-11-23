"""CR282 lane B — per-market sessions, holiday table, and the three consumers
(market state, resting-order expiry, Room bank trading day). No network; time is
passed in or frozen.
"""

from __future__ import annotations

import datetime as dt
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo
from uuid import uuid4

import pytest

from app.services import games_service, market_data, room_bank, sim_engine
from app.trading_math import bursa_holidays
from app.trading_math.market_calendar import (
    CalendarUnavailable,
    is_market_open,
    next_market_open,
    session_close_on_or_after,
    trading_date,
)
from app.trading_math.market_hours import is_us_market_open
from app.trading_math.market_hours import session_close_on_or_after as us_close
from app.trading_math.markets import Market

KL = ZoneInfo("Asia/Kuala_Lumpur")
MY = Market.MY


def kl(y, m, d, hh=0, mm=0) -> datetime:
    """A Kuala Lumpur wall-clock instant, as the aware datetime callers pass in."""
    return datetime(y, m, d, hh, mm, tzinfo=KL)


# ── sessions ─────────────────────────────────────────────────────────────────

MONDAY = (2026, 11, 23)  # a plain Bursa session day


@pytest.mark.parametrize(
    "hh,mm,expected",
    [
        (8, 59, False), (9, 0, True), (12, 29, True), (12, 30, False),
        (13, 0, False), (14, 29, False), (14, 30, True),
        (16, 49, True), (16, 50, False), (16, 55, False), (17, 0, False),
    ],
)
def test_my_session_boundaries(hh, mm, expected):
    assert is_market_open(MY, kl(*MONDAY, hh, mm)) is expected


def test_my_weekend_closed():
    assert is_market_open(MY, kl(2026, 11, 28, 10, 0)) is False  # Saturday
    assert is_market_open(MY, kl(2026, 11, 29, 10, 0)) is False  # Sunday


def test_my_session_is_independent_of_utc_date_and_us_dst():
    # 09:00 KL Monday is 01:00 UTC Monday; 17:00 UTC Sunday is 01:00 KL Monday (closed).
    assert is_market_open(MY, datetime(2026, 11, 23, 1, 0, tzinfo=timezone.utc)) is True
    assert is_market_open(MY, datetime(2026, 11, 22, 17, 0, tzinfo=timezone.utc)) is False
    # The same KL wall time is the same UTC offset in July and January (no DST).
    for month_day in ((1, 12), (7, 13)):
        t = kl(2026, *month_day, 9, 0)
        assert t.astimezone(timezone.utc).hour == 1
        assert is_market_open(MY, t) is True


def test_my_naive_datetime_is_utc():
    assert is_market_open(MY, datetime(2026, 11, 23, 2, 0)) is True  # 10:00 KL


@pytest.mark.parametrize("d", sorted(bursa_holidays.BURSA_HOLIDAYS_CONFIRMED))
def test_every_confirmed_2026_holiday_is_closed(d):
    assert is_market_open(MY, kl(d.year, d.month, d.day, 10, 0)) is False


def test_all_listed_holidays_closed_and_neighbour_weekday_open():
    for d in bursa_holidays.BURSA_HOLIDAYS:
        assert is_market_open(MY, kl(d.year, d.month, d.day, 10, 0)) is False
        assert d.weekday() < 5, f"{d} is a weekend — observed-day rule not applied"


def test_confirmed_2026_set_is_the_twelve_bursa_notice_days():
    assert bursa_holidays.BURSA_HOLIDAYS_CONFIRMED == {
        date(2026, 1, 1), date(2026, 2, 2), date(2026, 2, 17), date(2026, 2, 18),
        date(2026, 3, 20), date(2026, 3, 23), date(2026, 5, 27), date(2026, 6, 1),
        date(2026, 6, 2), date(2026, 8, 25), date(2026, 8, 31), date(2026, 9, 16),
    }


def test_2027_table_has_the_derived_observed_days():
    h = {d for d in bursa_holidays.BURSA_HOLIDAYS if d.year == 2027}
    assert h == {
        date(2027, 1, 1), date(2027, 1, 22), date(2027, 2, 1), date(2027, 2, 8),
        date(2027, 2, 9), date(2027, 3, 10), date(2027, 3, 11), date(2027, 5, 3),
        date(2027, 5, 17), date(2027, 5, 20), date(2027, 6, 7), date(2027, 6, 8),
        date(2027, 8, 16), date(2027, 8, 31), date(2027, 9, 16), date(2027, 10, 28),
        date(2027, 12, 27),
    }
    assert not any(d in bursa_holidays.BURSA_HOLIDAYS_CONFIRMED for d in h)


def test_lunch_on_a_session_day_is_closed_and_next_open_is_afternoon():
    assert is_market_open(MY, kl(*MONDAY, 13, 0)) is False
    assert next_market_open(MY, kl(*MONDAY, 13, 0)) == kl(*MONDAY, 14, 30).astimezone(timezone.utc)


def test_next_open_skips_holiday_and_weekend():
    # Fri 2026-08-28 after close -> Mon 31 Aug is a holiday -> Tue 1 Sep 09:00 KL.
    assert next_market_open(MY, kl(2026, 8, 28, 17, 30)) == kl(2026, 9, 1, 9, 0).astimezone(timezone.utc)


# ── beyond the table: loud ───────────────────────────────────────────────────


def test_beyond_table_raises_not_open():
    with pytest.raises(CalendarUnavailable):
        is_market_open(MY, kl(2028, 1, 4, 10, 0))
    with pytest.raises(CalendarUnavailable):
        is_market_open(MY, kl(2025, 12, 31, 10, 0))
    with pytest.raises(CalendarUnavailable):
        trading_date(MY, kl(2028, 1, 4, 10, 0))
    with pytest.raises(CalendarUnavailable):
        session_close_on_or_after(MY, kl(2027, 12, 31, 18, 0))  # next session is 2028


def test_trading_date_rolling_back_off_the_table_raises():
    with pytest.raises(CalendarUnavailable):
        trading_date(MY, kl(2026, 1, 1, 10, 0))  # 1 Jan holiday -> rolls into 2025


class _FrozenDatetime(dt.datetime):
    frozen: dt.datetime

    @classmethod
    def now(cls, tz=None):
        return cls.frozen.astimezone(tz) if tz else cls.frozen


def _freeze(monkeypatch, when: datetime) -> None:
    _FrozenDatetime.frozen = when
    monkeypatch.setattr(
        market_data, "datetime", SimpleNamespace(datetime=_FrozenDatetime, timezone=dt.timezone)
    )


def test_market_state_my_regular_closed_lunch_holiday(monkeypatch):
    _freeze(monkeypatch, kl(*MONDAY, 10, 0))
    assert market_data._market_state_for("1155.KL") == "REGULAR"
    _freeze(monkeypatch, kl(*MONDAY, 13, 0))
    assert market_data._market_state_for("1155.KL") == "CLOSED"
    _freeze(monkeypatch, kl(2026, 9, 16, 10, 0))  # Malaysia Day
    assert market_data._market_state_for("1155.KL") == "CLOSED"
    _freeze(monkeypatch, kl(2026, 11, 28, 10, 0))  # Saturday
    assert market_data._market_state_for("1155.KL") == "CLOSED"


def test_market_state_beyond_table_is_unknown_never_open(monkeypatch):
    _freeze(monkeypatch, kl(2028, 1, 4, 10, 0))
    assert market_data._market_state_for("1155.KL") == "UNKNOWN"


def test_market_state_us_still_follows_the_us_gate(monkeypatch):
    # 2026-11-23 15:00 UTC = 10:00 ET Monday.
    _freeze(monkeypatch, datetime(2026, 11, 23, 15, 0, tzinfo=timezone.utc))
    assert market_data._market_state_for("AAPL") == "REGULAR"
    _freeze(monkeypatch, datetime(2026, 11, 23, 22, 0, tzinfo=timezone.utc))
    assert market_data._market_state_for("AAPL") == "CLOSED"


# ── resting-order expiry ─────────────────────────────────────────────────────


def test_my_expiry_inside_morning_session_is_the_days_final_close():
    got = session_close_on_or_after(MY, kl(*MONDAY, 10, 0))
    assert got == kl(*MONDAY, 16, 50).astimezone(timezone.utc)


def test_my_expiry_at_lunch_survives_the_break():
    assert session_close_on_or_after(MY, kl(*MONDAY, 13, 0)) == kl(*MONDAY, 16, 50).astimezone(timezone.utc)


def test_my_expiry_after_close_rolls_to_next_session_day():
    assert session_close_on_or_after(MY, kl(*MONDAY, 16, 50)) == kl(2026, 11, 24, 16, 50).astimezone(timezone.utc)


def test_my_expiry_friday_evening_lands_monday():
    assert session_close_on_or_after(MY, kl(2026, 11, 27, 18, 0)) == kl(2026, 11, 30, 16, 50).astimezone(timezone.utc)


def test_my_expiry_skips_a_holiday():
    # Tue 2026-09-15 after close; Wed 16 Sep is Malaysia Day.
    assert session_close_on_or_after(MY, kl(2026, 9, 15, 17, 30)) == kl(2026, 9, 17, 16, 50).astimezone(timezone.utc)


def test_resting_order_expiry_routes_by_ticker():
    placed = kl(*MONDAY, 10, 0).astimezone(timezone.utc)
    assert sim_engine.resting_order_expiry("day", placed, "1155.KL") == kl(*MONDAY, 16, 50).astimezone(timezone.utc)
    assert sim_engine.resting_order_expiry("gtd_30", placed, "1155.KL") == kl(2026, 12, 23, 16, 50).astimezone(timezone.utc)


def test_resting_order_expiry_us_unchanged():
    placed = datetime(2026, 11, 23, 15, 0, tzinfo=timezone.utc)
    legacy = sim_engine.resting_order_expiry("gtd_30", placed)
    assert legacy == us_close(placed + timedelta(days=30))
    assert sim_engine.resting_order_expiry("gtd_30", placed, "AAPL") == legacy
    assert sim_engine.resting_order_expiry("gtd_30", placed, None) == legacy


# ── Room bank trading day ────────────────────────────────────────────────────


def test_my_trading_date_is_the_kuala_lumpur_date_not_the_utc_date():
    # 17:00 UTC Monday = 01:00 KL Tuesday.
    assert trading_date(MY, datetime(2026, 11, 23, 17, 0, tzinfo=timezone.utc)) == date(2026, 11, 24)


def test_my_trading_date_rolls_back_over_weekend():
    assert trading_date(MY, kl(2026, 11, 28, 11, 0)) == date(2026, 11, 27)
    assert trading_date(MY, kl(2026, 11, 29, 11, 0)) == date(2026, 11, 27)


def test_my_trading_date_monday_after_friday_holiday():
    # Fri 2026-03-20 and Mon 2026-03-23 are both closed -> Thursday 19 Mar.
    assert trading_date(MY, kl(2026, 3, 23, 10, 0)) == date(2026, 3, 19)
    assert trading_date(MY, kl(2026, 3, 22, 10, 0)) == date(2026, 3, 19)
    # Fri 2026-05-01 closed: Saturday rolls back to Thu 30 Apr; Monday 4 May is its own day.
    assert trading_date(MY, kl(2026, 5, 2, 10, 0)) == date(2026, 4, 30)
    assert trading_date(MY, kl(2026, 5, 4, 10, 0)) == date(2026, 5, 4)


def test_room_bank_trading_date_for_routes_by_ticker():
    now = datetime(2026, 3, 23, 3, 0, tzinfo=timezone.utc)  # 11:00 KL holiday; 23:00 ET Sunday
    assert room_bank.trading_date_for(now, "1155.KL") == date(2026, 3, 19)
    # US key unchanged: with or without a US ticker, the NY date rolled back.
    assert room_bank.trading_date_for(now) == room_bank.trading_date_for(now, "AAPL") == date(2026, 3, 20)


# ── US parity ────────────────────────────────────────────────────────────────


def test_us_delegation_is_the_existing_functions():
    for now in (
        datetime(2026, 11, 23, 15, 0, tzinfo=timezone.utc),
        datetime(2026, 11, 26, 15, 0, tzinfo=timezone.utc),  # Thanksgiving: the gate ignores holidays
        datetime(2026, 11, 28, 15, 0, tzinfo=timezone.utc),
        datetime(2026, 11, 23, 22, 0, tzinfo=timezone.utc),
    ):
        assert is_market_open(Market.US, now) == is_us_market_open(now)
        assert session_close_on_or_after(Market.US, now) == us_close(now)
        assert trading_date(Market.US, now) == room_bank.trading_date_for(now)


# ── Games stay US-only ───────────────────────────────────────────────────────


def test_games_reject_a_kl_ticker(monkeypatch):
    monkeypatch.setattr(games_service, "_require_live_entry", lambda *a, **k: None)
    with pytest.raises(games_service.MarketNotInGamesError):
        games_service.quote_trade(uuid4(), uuid4(), ticker="1155.KL", side=None, quantity=1)
    with pytest.raises(games_service.MarketNotInGamesError):
        games_service.submit_trade(uuid4(), uuid4(), ticker="1155.kl", side=None, quantity=1)
