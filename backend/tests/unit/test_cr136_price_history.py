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

import random
import statistics
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
    assert first == {"inserted": 300, "updated": 0, "skipped": 0}

    with get_session() as session:
        second = price_history.upsert_daily_bars(
            session, "AAPL", bars, source="fake_yahoo", now=now,
        )
    assert second == {"inserted": 0, "updated": 300, "skipped": 0}
    assert _row_count() == 300

    # The split/dividend case: the provider re-serves a whole revised trailing
    # series. Skip-if-exists would freeze the stale value into every covariance
    # computed afterwards, so an existing row must be overwritten.
    with get_session() as session:
        revised = price_history.upsert_daily_bars(
            session, "AAPL", [(days[0], 55.5)], source="fake_yahoo", now=now,
        )
    assert revised == {"inserted": 0, "updated": 1, "skipped": 0}
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
        ) == {"inserted": 0, "updated": 0, "skipped": 0}
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


def test_a_failing_provider_is_throttled_like_a_succeeding_one() -> None:
    """The stored `fetched_at` cannot arm the throttle on failure — it is
    written only by a successful upsert. Without an attempt stamp a dead feed is
    re-hit on every evaluation, for every holding, forever."""
    provider = FakeHistoryProvider({})            # history() → None, always
    price_history.set_history_provider(provider)
    now = _at(_ANCHOR)

    price_history.get_daily_series(["AAA"], min_days=126, now=now)
    assert len(provider.calls) == 1

    price_history.get_daily_series(["AAA"], min_days=126, now=now)
    price_history.get_daily_series(["AAA"], min_days=126, now=now + timedelta(hours=5))
    assert len(provider.calls) == 1, "a failed fetch must arm the throttle too"

    price_history.get_daily_series(["AAA"], min_days=126, now=now + timedelta(hours=7))
    assert len(provider.calls) == 2, "...and release it when the window expires"

    price_history.get_daily_series(
        ["AAA"], min_days=126, now=now + timedelta(hours=7), force_refresh=True,
    )
    assert len(provider.calls) == 3, "force_refresh still overrides the throttle"


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
#
# The bound is volatility-scaled (Rev 4), so every case here runs on a
# realistic-length series with a known volatility rather than on four hand-typed
# closes — with five observations a single spike dominates the robust scale
# estimate and the fixture would be testing arithmetic that cannot occur in
# production, where T is 126-504.


# Seeded Gaussian walks, NOT an alternating ±d series: an exactly-alternating
# series has a median absolute deviation of exactly ZERO, so its robust sigma
# collapses, the sigma term vanishes and every case would silently end up
# testing the absolute floor instead of the scaled bound.
_SEED = 1360
_SIGMA_QUIET = 0.002033      # measured robust sigma of _series(200, 0.002) at this seed
_SIGMA_BASE = 0.008132       # ...of _series(200, 0.008)
_SIGMA_WILD = 0.030494       # ...of _series(200, 0.030)


def _series(n: int, sigma: float = 0.008, *, start: float = 100.0) -> list[float]:
    """A clean, deterministic lognormal-ish walk of `n` closes."""
    rnd = random.Random(_SEED)
    closes = [start]
    for _ in range(n - 1):
        closes.append(closes[-1] * (1.0 + rnd.gauss(0.0, sigma)))
    return closes


def _inject(closes: list[float], index: int, move: float, *, reversal: float = 1.0):
    """Put a `move` print at `index` and undo `reversal` of it the next day."""
    out = list(closes)
    prev = out[index - 1]
    out[index] = prev * (1.0 + move)
    out[index + 1] = out[index] - reversal * (out[index] - prev)
    return out


def _step(closes: list[float], index: int, factor: float) -> list[float]:
    """Re-scale everything from `index` onward: a jump that is never undone, so
    only the unconditional hard bound can reach it."""
    out = list(closes)
    for i in range(index, len(out)):
        out[i] *= factor
    return out


def test_the_fixtures_have_the_volatilities_the_cases_below_assume() -> None:
    """Vacuity guard. Every threshold assertion below is stated in terms of
    these three sigmas; if the fixture drifts, the cases stop testing what their
    names say."""
    def sigma(closes: list[float]) -> float:
        return price_history.robust_daily_sigma(
            [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]
        )

    assert abs(sigma(_series(200, 0.002)) - _SIGMA_QUIET) < 1e-6
    assert abs(sigma(_series(200, 0.008)) - _SIGMA_BASE) < 1e-6
    assert abs(sigma(_series(200, 0.030)) - _SIGMA_WILD) < 1e-6
    # ...and therefore the bounds are:
    assert abs(max(15.0 * _SIGMA_QUIET, 0.10) - 0.10) < 1e-9      # floor governs
    assert abs(max(15.0 * _SIGMA_BASE, 0.10) - 0.12198) < 1e-5    # sigma governs
    assert abs(max(15.0 * _SIGMA_WILD, 0.10) - 0.45741) < 1e-5


def test_the_bound_is_volatility_scaled_not_absolute() -> None:
    """Rev 4 pins "a same-day |return| exceeding a volatility-scaled bound".
    The same 12% print is garbage on a 0.2%/day bond ETF and unremarkable on a
    3%/day momentum name; a flat threshold cannot tell them apart, which is
    exactly how a 40% absolute bound ended up sitting at ~150 sigma on a bond
    ETF and screening nothing at all."""
    quiet = _series(200, 0.002)        # bound = the 10% floor
    wild = _series(200, 0.030)         # bound = 45.7%

    assert price_history.detect_bad_print_days(_inject(quiet, 100, 0.12)) == [100]
    assert price_history.detect_bad_print_days(_inject(wild, 100, 0.12)) == []


def test_the_reviews_phantom_forty_percent_print_is_caught() -> None:
    """PM_REVIEW §12 / EXTERNAL §F: "one bad adjusted close from yfinance prints
    a phantom ±40% return straight into the covariance". Both directions."""
    base = _series(200, 0.008)
    assert price_history.detect_bad_print_days(_inject(base, 90, 0.40)) == [90]
    assert price_history.detect_bad_print_days(_inject(base, 90, -0.40)) == [90]


def test_a_genuine_crash_day_passes() -> None:
    """The one-sided calibration: a real crash day is the single most
    informative observation sigma-hat has. Same-direction follow-through, and a
    partial bounce well under the reversal fraction, must both survive.

    Measured on real data before pinning: across 18 tickers x 3 two-year windows
    (incl. the COVID crash), 8,671 genuine days pass the reversal test and the
    calibration fires on none of them."""
    base = _series(200, 0.008)
    crash = list(base)
    crash[100] = crash[99] * 0.75            # -25%
    crash[101] = crash[100] * 0.97           # keeps falling
    crash[102] = crash[101] * 1.04           # small bounce
    assert price_history.detect_bad_print_days(crash) == []

    half_bounce = _inject(base, 100, -0.25, reversal=0.5)
    assert price_history.detect_bad_print_days(half_bounce) == []


def test_reversal_is_measured_on_price_not_on_the_two_returns() -> None:
    """An exact price round trip is a 100% reversal at ANY magnitude. Scoring it
    as `|r_next| / |r|` instead gives 1/(1+r), which silently exempted every
    upward print above +66.7% — a +80% phantom scores 0.56 that way and passes,
    while sitting below the 100% hard bound."""
    base = _series(200, 0.008)
    round_trip = _inject(base, 100, 0.80, reversal=1.0)
    assert price_history.detect_bad_print_days(round_trip) == [100]

    r = round_trip[100] / round_trip[99] - 1.0
    r_next = round_trip[101] / round_trip[100] - 1.0
    assert abs(r_next) / abs(r) < 0.60, "the returns-basis rule let this through"


def test_a_move_the_next_day_extends_is_never_a_reversal() -> None:
    """The direction requirement, pinned. Without it a genuine two-day rout
    would read as a bad print and the holding would be dropped."""
    base = _series(200, 0.008)
    rout = _step(base, 100, 0.70)        # -30% on day 100, and it stays there
    rout = _step(rout, 101, 0.85)        # -15% more on day 101, and that stays too
    assert price_history.detect_bad_print_days(rout) == []


def test_returns_over_one_hundred_percent_are_flagged_unconditionally() -> None:
    base = _series(200, 0.008)
    never_undone = _step(base, 100, 2.10)            # +110% and it stays there
    assert price_history.detect_bad_print_days(never_undone) == [100]

    # A spike on the final bar has no next day to test for reversal, so only
    # the hard bound can reach it.
    on_last = list(base)
    on_last[-1] = on_last[-2] * 2.50
    assert price_history.detect_bad_print_days(on_last) == [len(on_last) - 1]
    on_last[-1] = on_last[-2] * 1.45                 # +45%, still no next day
    assert price_history.detect_bad_print_days(on_last) == []


def test_non_positive_and_non_finite_prints_are_flagged() -> None:
    """NaN is the archetypal garbage print AND invisible to a naive screen:
    `nan > 0.40` and `nan <= 0.0` are BOTH False, so a threshold test written
    the obvious way lets it through and turns every covariance built from that
    ticker silently into NaN."""
    base = _series(200, 0.008)
    for garbage in (0.0, -5.0, float("nan"), float("inf"), float("-inf")):
        probe = list(base)
        probe[100] = garbage
        flagged = price_history.detect_bad_print_days(probe)
        assert 100 in flagged, garbage
        assert 101 in flagged, garbage


def test_short_and_clean_inputs_return_nothing() -> None:
    assert price_history.detect_bad_print_days([]) == []
    assert price_history.detect_bad_print_days([100.0]) == []
    assert price_history.detect_bad_print_days(_series(200, 0.008)) == []
    assert price_history.detect_bad_print_days(_series(200, 0.030)) == []


def test_robust_sigma_is_not_moved_by_the_print_it_is_hunting() -> None:
    """A plain standard deviation widens around the outlier and hides it. The
    MAD has a 50% breakdown point, so one spike in 200 days barely moves it —
    which is the only reason a sigma-scaled bound can work at all."""
    clean = _series(200, 0.008)
    spiked = _inject(clean, 100, 0.40)

    def returns(closes: list[float]) -> list[float]:
        return [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]

    robust_clean = price_history.robust_daily_sigma(returns(clean))
    robust_spiked = price_history.robust_daily_sigma(returns(spiked))
    plain_clean = statistics.pstdev(returns(clean))
    plain_spiked = statistics.pstdev(returns(spiked))

    # One 40% print in 200 days: the robust scale moves ~3%, the plain one 4.5x.
    assert robust_spiked / robust_clean < 1.05
    assert plain_spiked / plain_clean > 4.0, (
        "vacuity guard — if a plain sd barely moved either, this test proves "
        "nothing about robustness"
    )


def test_the_detector_bounds_are_arguments_not_hardcoded() -> None:
    """The seam register pins the values in `portfolio_health_constants` and the
    detector as taking them as arguments — so a recalibration is a one-line
    constant change, never a rewrite. Each bound is exercised on the side that
    changes the verdict."""
    # The absolute floor: 8% clears 15 sigma on the quiet series but not 10%.
    quiet = _inject(_series(200, 0.002), 100, 0.08)
    assert price_history.detect_bad_print_days(quiet) == []
    assert price_history.detect_bad_print_days(quiet, min_abs_return=0.05) == [100]

    # The sigma multiple: 20% clears 15 x 0.81% but not 30 x.
    over = _inject(_series(200, 0.008), 100, 0.20)
    assert price_history.detect_bad_print_days(over) == [100]
    assert price_history.detect_bad_print_days(over, sigma_mult=30.0) == []

    # The reversal fraction.
    partial = _inject(_series(200, 0.008), 100, 0.20, reversal=0.7)
    assert price_history.detect_bad_print_days(partial) == [100]
    assert price_history.detect_bad_print_days(
        partial, reversal_min_fraction=0.80,
    ) == []

    # The hard bound, on a jump nothing undoes — so only that bound can fire.
    huge = _step(_series(200, 0.008), 100, 2.5)
    assert price_history.detect_bad_print_days(huge) == [100]
    assert price_history.detect_bad_print_days(huge, hard_abs_return=2.0) == []


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
    mock bars into the analytic history with nothing to show it happened.

    Asserted in REAL mode, which is the only branch where it can fail — in mock
    mode `_leaf_provider()` and `get_market_data_provider()` return the same
    `mock_walk` object, so no implementation could fail the assertions there and
    the guard would be unconditionally satisfied."""
    monkeypatch.setattr(settings, "use_real_market_data", True)
    price_history.set_history_provider(None)

    sentinel = FakeHistoryProvider({})
    sentinel.name = "yfinance"
    monkeypatch.setattr(price_history, "YfinanceProvider", lambda: sentinel)

    provider = price_history._leaf_provider()
    assert provider is sentinel, "real mode must resolve the leaf, not a wrapper"
    assert "fallback" not in provider.name
    assert "cache" not in provider.name
    assert provider.name != "mock_walk"

    # Vacuity guard: the stack this guard exists to exclude really is a wrapper.
    market_data.set_market_data_provider(None)
    stack = market_data.get_market_data_provider()
    market_data.set_market_data_provider(market_data.MockWalkProvider())
    assert "fallback" in stack.name and "cache" in stack.name


def test_real_mode_without_yfinance_returns_no_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other half of the CR040 guard: a missing yfinance must yield None —
    not the keyless Yahoo path (whose `history()` returns None anyway) and above
    all not the mock walk, which would fabricate."""
    monkeypatch.setattr(settings, "use_real_market_data", True)
    price_history.set_history_provider(None)

    def _boom():
        raise ImportError("yfinance not installed")

    monkeypatch.setattr(price_history, "YfinanceProvider", _boom)
    assert price_history._leaf_provider() is None


def test_a_failed_fetch_is_distinguishable_from_a_young_security(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CR040: without this flag a feed outage and a genuinely young security are
    the same empty series, and the engine would tell the user "not enough price
    history for this holding" when the truth is "our feed is down"."""
    monkeypatch.setattr(settings, "use_real_market_data", True)
    price_history.set_history_provider(FakeHistoryProvider({}))   # history() → None

    series = price_history.get_daily_series(
        ["AAA"], min_days=126, now=_at(_ANCHOR),
    )["AAA"]
    assert series.dates == []
    assert series.fetch_failed is True

    price_history.set_history_provider(
        FakeHistoryProvider({"BBB": _candles(_trading_days(_ANCHOR, 200))})
    )
    ok = price_history.get_daily_series(["BBB"], min_days=126, now=_at(_ANCHOR))["BBB"]
    assert ok.fetch_failed is False


def test_a_mock_run_never_overwrites_real_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A local dev run in mock mode would otherwise walk over accumulated real
    bars in place — value and provenance both — and the damage would be
    invisible afterwards, because the rows still look like ordinary history."""
    days = _trading_days(_ANCHOR, 5)
    _seed("AAA", days, source="yfinance", fetched_at=_at(_ANCHOR), start=100.0)

    monkeypatch.setattr(settings, "use_real_market_data", False)
    with get_session() as session:
        result = price_history.upsert_daily_bars(
            session,
            "AAA",
            [(d, 1.0) for d in days],
            source="mock_walk",
            now=_at(_ANCHOR),
            replace_foreign_rows=False,
        )
    assert result == {"inserted": 0, "updated": 0, "skipped": 5}

    with get_session() as session:
        rows = session.execute(
            select(PriceHistoryDailyRow).where(PriceHistoryDailyRow.ticker == "AAA")
        ).scalars().all()
    assert {r.source for r in rows} == {"yfinance"}
    assert min(float(r.adj_close) for r in rows) >= 100.0


def test_a_naive_now_is_treated_as_utc(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stored stamps are normalised to aware UTC, so a caller passing
    `datetime.now()` would otherwise get a TypeError out of the throttle
    subtraction rather than a decision."""
    days = _trading_days(_ANCHOR, 200)
    _seed("AAA", days, fetched_at=_at(days[-1]))
    naive = datetime.combine(days[-1], time(20, 0))
    assert naive.tzinfo is None

    series = price_history.get_daily_series(["AAA"], min_days=126, now=naive)["AAA"]
    assert len(series.dates) == 200


def test_unusable_provider_closes_are_refused_at_the_door() -> None:
    """`YfinanceProvider.history` does not filter these: `float(row["Close"])`
    on a pandas NaN returns `nan` rather than raising. One malformed row would
    otherwise reach a `Numeric(12, 4)` column."""
    day = date(2026, 7, 28)
    provider = FakeHistoryProvider({"AAA": [
        Candle(t=_epoch(day - timedelta(days=1)), o=1, h=1, low=1, c=float("nan"), v=1e6),
        Candle(t=_epoch(day), o=1, h=1, low=1, c=-3.0, v=1e6),
        Candle(t=_epoch(day + timedelta(days=1)), o=1, h=1, low=1, c=25.0, v=1e6),
    ]})
    price_history.set_history_provider(provider)

    series = price_history.get_daily_series(["AAA"], min_days=1, now=_at(day))["AAA"]
    assert series.adj_closes == [pytest.approx(25.0)]
    assert all(v > 0.0 for v in series.adj_closes)


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
