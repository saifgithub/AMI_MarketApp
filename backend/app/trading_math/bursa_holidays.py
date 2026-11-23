"""Bursa Malaysia market-closure table — data, never a formula (CR282 lane B).

Malaysian holidays follow the lunar/Hijri calendars and are re-gazetted every
year (Cabinet circular, then a Bursa notice), so there is no rule to compute
them from. This is a hand-maintained table, refreshed from Bursa's annual
holiday notice. `confirmed` says how far to trust a row:

  - True  — named in a Bursa market-holiday notice (primary source for 2026).
  - False — gazetted or derived but not yet in a Bursa notice. The calendar
    still treats the day as CLOSED; the flag exists so the refresh knows what to
    re-check, and so a wrong row is found by reading the table, not the code.

Sources
  - 2026 `confirmed=True`: Bursa Malaysia market-holiday notices as captured in
    the CR282 research (2026-11-23). 20-23 Mar: Bursa reopened 24 Mar; 21-22 Mar
    is a weekend, so the trading closures are 20 and 23 Mar. The notices give
    dates; the holiday names below are descriptive labels, not quoted.
  - 2026 `confirmed=False`: federal gazette, not yet in a Bursa notice.
  - 2027 (all `confirmed=False`): derived from Cabinet circular GI/15/2026.

Observed-day rule applied to 2027: a holiday that falls on a weekly rest day
(Saturday or Sunday) moves to the next day that is neither a rest day nor
already a holiday. Derivations:

  - Chinese New Year day 1 = Sat 6 Feb -> Mon 8 Feb; day 2 = Sun 7 Feb -> the
    next free day is Tue 9 Feb (Mon 8 Feb is already taken by day 1).
  - Labour Day Sat 1 May -> Mon 3 May.
  - Awal Muharram Sun 6 Jun -> Mon 7 Jun is the Agong's Birthday (first Monday
    of June), so the observed day is Tue 8 Jun.
  - Maulidur Rasul Sun 15 Aug -> Mon 16 Aug.
  - Christmas Sat 25 Dec -> Mon 27 Dec.
  The Saturday moves (Labour Day, Christmas) treat every weekly rest day alike;
  Malaysian practice for a Saturday holiday is the least certain part of the
  table, which is why every 2027 row is unconfirmed. Awal Muharram and
  Maulidur Rasul dates are moon-sighted and can shift a day.

Refresh when Bursa publishes the next year's notice; until then `LAST_YEAR`
stays put and the calendar fails loudly beyond it (see `market_calendar`).
"""

from __future__ import annotations

from datetime import date

FIRST_YEAR = 2026
LAST_YEAR = 2027

# (date, label, confirmed)
_ROWS: tuple[tuple[date, str, bool], ...] = (
    # 2026 — confirmed from Bursa notices
    (date(2026, 1, 1), "New Year's Day", True),
    (date(2026, 2, 2), "Thaipusam / Federal Territory Day (1 Feb Sun, observed)", True),
    (date(2026, 2, 17), "Chinese New Year", True),
    (date(2026, 2, 18), "Chinese New Year (day 2)", True),
    (date(2026, 3, 20), "Hari Raya Aidilfitri", True),
    (date(2026, 3, 23), "Hari Raya Aidilfitri (21 Mar Sat, observed)", True),
    (date(2026, 5, 27), "Hari Raya Aidiladha", True),
    (date(2026, 6, 1), "Agong's Birthday", True),
    (date(2026, 6, 2), "Wesak Day (31 May Sun; 1 Jun is Agong's, observed)", True),
    (date(2026, 8, 25), "Maulidur Rasul", True),
    (date(2026, 8, 31), "National Day", True),
    (date(2026, 9, 16), "Malaysia Day", True),
    # 2026 — gazetted, not yet Bursa-confirmed
    (date(2026, 5, 1), "Labour Day", False),
    (date(2026, 6, 17), "Awal Muharram", False),
    (date(2026, 11, 9), "Deepavali (8 Nov Sun, observed)", False),
    (date(2026, 12, 25), "Christmas Day", False),
    # 2027 — derived from Cabinet circular GI/15/2026, all unconfirmed
    (date(2027, 1, 1), "New Year's Day", False),
    (date(2027, 1, 22), "Thaipusam (Federal Territory)", False),
    (date(2027, 2, 1), "Federal Territory Day", False),
    (date(2027, 2, 8), "Chinese New Year (6 Feb Sat, observed)", False),
    (date(2027, 2, 9), "Chinese New Year day 2 (7 Feb Sun, observed)", False),
    (date(2027, 3, 10), "Hari Raya Aidilfitri", False),
    (date(2027, 3, 11), "Hari Raya Aidilfitri (day 2)", False),
    (date(2027, 5, 3), "Labour Day (1 May Sat, observed)", False),
    (date(2027, 5, 17), "Hari Raya Aidiladha", False),
    (date(2027, 5, 20), "Wesak Day", False),
    (date(2027, 6, 7), "Agong's Birthday", False),
    (date(2027, 6, 8), "Awal Muharram (6 Jun Sun; 7 Jun is Agong's, observed)", False),
    (date(2027, 8, 16), "Maulidur Rasul (15 Aug Sun, observed)", False),
    (date(2027, 8, 31), "National Day", False),
    (date(2027, 9, 16), "Malaysia Day", False),
    (date(2027, 10, 28), "Deepavali", False),
    (date(2027, 12, 27), "Christmas Day (25 Dec Sat, observed)", False),
)

BURSA_HOLIDAYS: dict[date, str] = {d: label for d, label, _ in _ROWS}
BURSA_HOLIDAYS_CONFIRMED: frozenset[date] = frozenset(d for d, _, c in _ROWS if c)

assert len(BURSA_HOLIDAYS) == len(_ROWS), "duplicate date in the Bursa holiday table"
