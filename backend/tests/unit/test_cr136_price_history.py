"""CR136 M01 — period map, price_history_daily upsert/read-through, trading-day
derivation, bad-print detector.

Everything here is deterministic and offline: fake providers with canned
`Candle` lists are injected via `set_history_provider`, so no test can reach
live yfinance, and none depends on what the market did today.

The tests that matter most are the negative ones. `price_history` exists partly
because the shared provider stack would let a transient yfinance failure
persist fabricated mock bars into the analytic history (CR040), so there are
explicit tests that real mode never serves a `mock_walk` row and that a missing
provider yields an empty series rather than an invented one.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.db import get_session
from app.db.models import PriceHistoryDailyRow
from app.services import market_data, price_history
from app.services.market_data import Candle
from app.services.portfolio_health_constants import (
    BENCHMARK_TICKER,
    HISTORY_FETCH_PERIOD,
    HISTORY_MAX_ROWS,
)

# A Friday, so "yesterday" and "three days ago" are unambiguous weekdays.
_ANCHOR = date(2026, 7, 31)


# ── Helpers ─────────────────────────────────────────────────────────────────


def _trading_days(end: date, count: int) -> list[date]:
    """`count` weekdays ending at or before `end`, ascending."""
    days: list[date] = []
    cursor = end
    while len(days) < count:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor -= timedelta(days=1)
    return list(reversed(days))


def _epoch(day: date) -> int:
    """04:00 UTC — midnight New York, the stamp a daily US bar carries."""
    return int(datetime.combine(day, time(4, 0), tzinfo=timezone.utc).timestamp())


def _candles(days: list[date], start: float = 100.0, step: float = 0.5) -> list[Candle]:
    bars: list[Candle] = []
    for i, day in enumerate(days):
        close = start + step * i
        bars.append(Candle(t=_epoch(day), o=close, h=close, low=close, c=close, v=1e6))
    return bars


def _at(day: date, hour: int = 20) -> datetime:
    return datetime.combine(day, time(hour, 0), tzinfo=timezone.utc)


class FakeHistoryProvider:
    """Canned bars + a call counter. Name is deliberately NOT `mock_walk`, so
    real-mode provenance filtering can be exercised against it."""

    name = "fake_yahoo"

    def __init__(self, bars: dict[str, list[Candle]]) -> None:
        self._bars = bars
        self.calls: list[tuple[str, str]] = []

    def quote(self, ticker: str):
        return None

    def get_price(self, ticker: str):
        return None

    def history(self, ticker: str, period: str):
        self.calls.append((ticker.upper().strip(), period))
        return self._bars.get(ticker.upper().strip())

    def news(self, ticker: str, limit: int = 5):
        return None

    def earnings(self, ticker: str):
        return None


def _seed(
    ticker: str,
    days: list[date],
    *,
    fetched_at: datetime,
    source: str = "fake_yahoo",
    start: float = 100.0,
) -> None:
    with get_session() as session:
        price_history.upsert_daily_bars(
            session,
            ticker,
            [(day, start + i) for i, day in enumerate(days)],
            source=source,
            now=fetched_at,
        )


def _row_count() -> int:
    with get_session() as session:
        return session.execute(
            select(func.count()).select_from(PriceHistoryDailyRow)
        ).scalar_one()


# ── 1. The "2y" period ──────────────────────────────────────────────────────


def test_two_year_period_serves_daily_bars() -> None:
    """The critical-path entry: 504 daily bars where "3m" gave 65."""
    assert market_data._PERIOD_MAP["2y"] == ("2y", "1d", 504, 24 * 3600)
    assert "2y" in market_data.VALID_PERIODS

    bars = market_data.MockWalkProvider().history("AAPL", "2y")
    assert bars is not None and len(bars) == 504
    deltas = {bars[i + 1].t - bars[i].t for i in range(len(bars) - 1)}
    assert deltas == {24 * 3600}


def test_the_history_period_pin_is_the_one_the_map_serves() -> None:
    """Guards the seam: the constant M01 fetches on must exist in the map, or
    every fetch silently returns None (`YfinanceProvider.history` line 1)."""
    assert HISTORY_FETCH_PERIOD in market_data.VALID_PERIODS


# ── 2. Upsert ───────────────────────────────────────────────────────────────


def test_upsert_is_idempotent_and_revises_in_place() -> None:
    days = _trading_days(_ANCHOR, 300)
    bars = [(day, 100.0 + i) for i, day in enumerate(days)]
    now = _at(_ANCHOR, hour=12)

    with get_session() as session:
        first = price_history.upsert_daily_bars(
            session, "AAPL", bars, source="fake_yahoo", now=now,
        )
    assert first == {"inserted": 300, "updated": 0}

    with get_session() as session:
        second = price_history.upsert_daily_bars(
            session, "AAPL", bars, source="fake_yahoo", now=now,
        )
    assert second == {"inserted": 0, "updated": 300}
    assert _row_count() == 300

    # The split/dividend case: the provider re-serves a whole revised trailing
    # series. Skip-if-exists would freeze the stale value into every covariance
    # computed afterwards, so an existing row must be overwritten.
    with get_session() as session:
        revised = price_history.upsert_daily_bars(
            session, "AAPL", [(days[0], 55.5)], source="fake_yahoo", now=now,
        )
    assert revised == {"inserted": 0, "updated": 1}
    assert _row_count() == 300

    with get_session() as session:
        rows = session.execute(
            select(PriceHistoryDailyRow).where(PriceHistoryDailyRow.date == days[0])
        ).scalars().all()
    assert len(rows) == 1
    assert float(rows[0].adj_close) == pytest.approx(55.5)
    assert float(rows[0].close) == pytest.approx(55.5)


def test_upsert_of_an_empty_bar_list_is_a_no_op() -> None:
    with get_session() as session:
        assert price_history.upsert_daily_bars(
            session, "AAPL", [], source="fake_yahoo", now=_at(_ANCHOR),
        ) == {"inserted": 0, "updated": 0}
    assert _row_count() == 0


# ── 3. Read-through ─────────────────────────────────────────────────────────


def test_read_through_fetches_once_then_serves_from_the_table() -> None:
    days = _trading_days(_ANCHOR, 200)
    provider = FakeHistoryProvider({"AAPL": _candles(days)})
    price_history.set_history_provider(provider)
    now = _at(days[-1])

    out = price_history.get_daily_series(["AAPL"], min_days=126, now=now)
    assert len(provider.calls) == 1
    assert provider.calls[0] == ("AAPL", HISTORY_FETCH_PERIOD)
    assert out["AAPL"].dates == days
    assert _row_count() == 200

    price_history.get_daily_series(["AAPL"], min_days=126, now=now)
    assert len(provider.calls) == 1, "second call must be served from the table"

    price_history.get_daily_series(["AAPL"], min_days=126, now=now, force_refresh=True)
    assert len(provider.calls) == 2


def test_reads_are_trimmed_to_the_pinned_window() -> None:
    """`HISTORY_MAX_ROWS` is the estimator's stated ceiling — a table that has
    accumulated more (backfill, M10) must not silently widen the window."""
    days = _trading_days(_ANCHOR, HISTORY_MAX_ROWS + 16)
    _seed("AAPL", days, fetched_at=_at(days[-1]))

    out = price_history.get_daily_series(["AAPL"], min_days=126, now=_at(days[-1]))
    series = out["AAPL"]
    assert len(series.dates) == HISTORY_MAX_ROWS
    assert series.dates[-1] == days[-1], "the trailing window, not the leading one"
    assert series.dates[0] == days[16]


def test_tickers_are_normalised_and_deduped() -> None:
    days = _trading_days(_ANCHOR, 10)
    provider = FakeHistoryProvider({"AAPL": _candles(days)})
    price_history.set_history_provider(provider)

    out = price_history.get_daily_series(
        [" aapl ", "AAPL", ""], min_days=5, now=_at(days[-1]),
    )
    assert list(out) == ["AAPL"]
    assert len(provider.calls) == 1


# ── 4. Staleness / throttle boundaries ──────────────────────────────────────


def test_stale_series_refetches_but_only_outside_the_fresh_window() -> None:
    now = _at(_ANCHOR)
    long_ago = now - timedelta(days=2)
    just_now = now - timedelta(minutes=10)
    fresh_days = _trading_days(_ANCHOR, 10)

    provider = FakeHistoryProvider({
        "AAA": _candles(fresh_days),
        "BBB": _candles(fresh_days),
        "CCC": _candles(fresh_days),
    })
    price_history.set_history_provider(provider)

    # (a) newest bar three days old, last fetched two days ago → refetch.
    _seed("AAA", _trading_days(_ANCHOR - timedelta(days=3), 10), fetched_at=long_ago)
    price_history.get_daily_series(["AAA"], min_days=5, now=now)
    assert [c[0] for c in provider.calls] == ["AAA"]

    # (b) newest bar is yesterday and the window is full → no fetch. Yesterday
    # is the boundary: an unfinished today is not evidence of staleness.
    _seed("BBB", _trading_days(_ANCHOR - timedelta(days=1), 10), fetched_at=long_ago)
    price_history.get_daily_series(["BBB"], min_days=5, now=now)
    assert [c[0] for c in provider.calls] == ["AAA"]

    # (c) stale by date, but fetched ten minutes ago → throttled.
    _seed("CCC", _trading_days(_ANCHOR - timedelta(days=3), 10), fetched_at=just_now)
    price_history.get_daily_series(["CCC"], min_days=5, now=now)
    assert [c[0] for c in provider.calls] == ["AAA"]


def test_a_short_series_refetches_even_when_its_newest_bar_is_current() -> None:
    """`min_days` is a fetch trigger in its own right — a 60-bar series ending
    today is exactly the pre-CR136 failure and must not look 'fresh'."""
    days = _trading_days(_ANCHOR, 60)
    _seed("AAA", days, fetched_at=_at(_ANCHOR) - timedelta(days=2))
    provider = FakeHistoryProvider({"AAA": _candles(_trading_days(_ANCHOR, 200))})
    price_history.set_history_provider(provider)

    out = price_history.get_daily_series(["AAA"], min_days=126, now=_at(_ANCHOR))
    assert len(provider.calls) == 1
    assert len(out["AAA"].dates) == 200


def test_a_fetch_failure_serves_what_is_stored_and_never_fabricates() -> None:
    days = _trading_days(_ANCHOR, 30)
    _seed("AAA", days, fetched_at=_at(_ANCHOR) - timedelta(days=2))
    provider = FakeHistoryProvider({})  # history() returns None
    price_history.set_history_provider(provider)

    out = price_history.get_daily_series(["AAA"], min_days=126, now=_at(_ANCHOR))
    assert len(provider.calls) == 1
    assert out["AAA"].dates == days
    assert _row_count() == 30


# ── 5-7. Bad-print detector ─────────────────────────────────────────────────


def test_spike_with_next_day_reversal_is_flagged() -> None:
    # +50% then −33%: opposite sign, and 0.33 ≥ 0.6 × 0.50.
    assert price_history.detect_bad_print_days([100, 100, 150, 100.5, 101]) == [2]


def test_a_genuine_crash_day_passes() -> None:
    # −45% with same-sign follow-through, then a +3.7% day (< 0.6 × 0.45).
    assert price_history.detect_bad_print_days([100, 55, 54, 56]) == []


def test_returns_over_one_hundred_percent_are_flagged_unconditionally() -> None:
    assert price_history.detect_bad_print_days([100, 210, 205]) == [1]
    # A spike on the final day has no next day to test for reversal, so only
    # the hard bound can catch it.
    assert price_history.detect_bad_print_days([100, 100, 250]) == [2]
    assert price_history.detect_bad_print_days([100, 100, 145]) == []


def test_non_positive_prints_are_flagged() -> None:
    assert price_history.detect_bad_print_days([100, 0.0, 100]) == [1, 2]
    assert price_history.detect_bad_print_days([100, -5.0, 100]) == [1, 2]


def test_short_and_clean_inputs_return_nothing() -> None:
    assert price_history.detect_bad_print_days([]) == []
    assert price_history.detect_bad_print_days([100.0]) == []
    assert price_history.detect_bad_print_days([100, 101, 100.5, 102]) == []


def test_the_detector_bounds_are_arguments_not_hardcoded() -> None:
    """The seam register pins the values in `portfolio_health_constants` and the
    detector as taking them as arguments — so a recalibration is a one-line
    constant change, never a rewrite."""
    # +35% then a −25.9% reversal: under the pinned 40% spike bound this is a
    # move the estimator should see, and it passes.
    closes = [100, 100, 135, 100.0, 101]
    assert price_history.detect_bad_print_days(closes) == []
    assert price_history.detect_bad_print_days(closes, spike_abs_return=0.30) == [2]
    assert price_history.detect_bad_print_days(closes, reversal_min_fraction=0.99) == []


# ── 8. Trading days come from bars ──────────────────────────────────────────


def test_trading_days_are_derived_from_bars_not_the_calendar() -> None:
    days = [date(2026, 7, 23), date(2026, 7, 24), date(2026, 7, 27), date(2026, 7, 28)]
    assert [d.weekday() for d in days] == [3, 4, 0, 1], "Thu, Fri, Mon, Tue"

    provider = FakeHistoryProvider({"AAA": _candles(days)})
    price_history.set_history_provider(provider)

    out = price_history.get_daily_series(["AAA"], min_days=4, now=_at(days[-1]))
    series = out["AAA"]
    assert series.dates == days, "the weekend is an absence, never a filled gap"
    assert len(series.dates) == 4
    assert all(d.weekday() < 5 for d in series.dates)


def test_duplicate_dates_in_one_fetch_collapse_to_the_last_bar() -> None:
    day = date(2026, 7, 28)
    provider = FakeHistoryProvider({"AAA": [
        Candle(t=_epoch(day), o=1, h=1, low=1, c=10.0, v=1e6),
        Candle(t=_epoch(day) + 3600, o=1, h=1, low=1, c=11.0, v=1e6),
    ]})
    price_history.set_history_provider(provider)

    out = price_history.get_daily_series(["AAA"], min_days=1, now=_at(day))
    assert out["AAA"].dates == [day]
    assert out["AAA"].adj_closes == [pytest.approx(11.0)]


# ── 9. Provenance hygiene ───────────────────────────────────────────────────


def test_real_mode_never_serves_a_fabricated_row(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "use_real_market_data", True)
    now = _at(_ANCHOR)
    mock_day = date(2026, 7, 17)
    _seed("AAA", [mock_day], source="mock_walk", fetched_at=now)
    _seed("AAA", _trading_days(_ANCHOR, 10), source="fake_yahoo", fetched_at=now)

    price_history.set_history_provider(FakeHistoryProvider({}))
    series = price_history.get_daily_series(["AAA"], min_days=5, now=now)["AAA"]

    assert mock_day not in series.dates
    assert "mock_walk" not in series.sources
    assert series.sources == ("fake_yahoo",)


def test_mock_mode_marks_its_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "use_real_market_data", False)
    price_history.set_history_provider(None)  # → MockWalkProvider

    series = price_history.get_daily_series(["AAPL"], min_days=5)["AAPL"]
    assert series.sources == ("mock_walk",)
    assert series.dates, "mock mode still serves a series; M04 refuses it, not M01"


def test_real_mode_without_a_provider_returns_an_empty_series(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(price_history, "_leaf_provider", lambda: None)

    series = price_history.get_daily_series(
        ["AAA"], min_days=126, now=_at(_ANCHOR),
    )["AAA"]
    assert series.dates == []
    assert series.adj_closes == []
    assert series.sources == ()
    assert series.fetched_at is None
    assert _row_count() == 0, "a missing provider must never write a fabricated bar"


def test_the_fallback_stack_is_never_the_history_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The CR040 guard, asserted rather than assumed: persisting through
    `get_market_data_provider()` would let one transient yfinance failure write
    mock bars into the analytic history with nothing to show it happened."""
    monkeypatch.setattr(settings, "use_real_market_data", False)
    price_history.set_history_provider(None)
    provider = price_history._leaf_provider()
    assert provider is not None
    assert "fallback" not in provider.name
    assert "cache" not in provider.name


# ── 10. Numeric round-trip ──────────────────────────────────────────────────


def test_served_prices_are_plain_floats() -> None:
    """Postgres round-trips `Numeric` as `Decimal`; sqlite hides it. Every
    downstream float operation would raise on a Decimal/float mix."""
    days = _trading_days(_ANCHOR, 5)
    _seed("AAA", days, fetched_at=_at(days[-1]))

    series = price_history.get_daily_series(
        ["AAA"], min_days=5, now=_at(days[-1]),
    )["AAA"]
    assert series.adj_closes and series.closes
    assert all(type(v) is float for v in series.adj_closes)
    assert all(type(v) is float for v in series.closes)


# ── 11. Benchmark leg + trading-day helper ──────────────────────────────────


def test_benchmark_series_rides_the_same_path() -> None:
    days = _trading_days(_ANCHOR, 130)
    provider = FakeHistoryProvider({BENCHMARK_TICKER: _candles(days)})
    price_history.set_history_provider(provider)

    series = price_history.get_benchmark_series(min_days=126, now=_at(days[-1]))
    assert series.ticker == BENCHMARK_TICKER
    assert provider.calls == [(BENCHMARK_TICKER, HISTORY_FETCH_PERIOD)]
    assert len(series.dates) == 130

    with get_session() as session:
        stored = session.execute(
            select(func.count()).select_from(PriceHistoryDailyRow).where(
                PriceHistoryDailyRow.ticker == BENCHMARK_TICKER,
            )
        ).scalar_one()
    assert stored == 130


def test_latest_trading_day_reads_the_benchmark_calendar() -> None:
    assert price_history.latest_trading_day() is None

    days = _trading_days(_ANCHOR, 10)
    _seed(BENCHMARK_TICKER, days, fetched_at=_at(days[-1]))
    assert price_history.latest_trading_day() == days[-1]


def test_latest_trading_day_ignores_fabricated_rows_in_real_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_days = _trading_days(_ANCHOR - timedelta(days=7), 5)
    _seed(BENCHMARK_TICKER, real_days, source="fake_yahoo", fetched_at=_at(_ANCHOR))
    _seed(BENCHMARK_TICKER, [_ANCHOR], source="mock_walk", fetched_at=_at(_ANCHOR))

    monkeypatch.setattr(settings, "use_real_market_data", True)
    assert price_history.latest_trading_day() == real_days[-1]

    monkeypatch.setattr(settings, "use_real_market_data", False)
    assert price_history.latest_trading_day() == _ANCHOR
