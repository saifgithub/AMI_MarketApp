"""CR164 — as-of mode on the production data layer.

What must hold, per the CR's acceptance section:
  * guard (a): a data path that would serve a fact dated past `as_of` raises
    `AsOfLeakageError` — loud death, never silent truncation;
  * the as-of read path is a PURE read — filters `date <= as_of`, excludes
    mock rows unconditionally, never fetches;
  * the store-backed provider serves as-of candles to the same protocol the
    live stack serves, refuses OHLCV-incomplete windows, and switches in/out
    purely on the ContextVar — the live path is untouched when no context is
    active (the same-infrastructure regression pin);
  * the EDGAR PIT resolvers respect the filed-date cutoff, prefer amendments
    by filed-ordering, derive the standard missing-Q4, and refuse stale or
    holed TTM windows;
  * `_profile_for_ticker(as_of=...)` anchors `run_date` at the as-of date.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.db import get_session
from app.db.models import BacktestRunIndexRow, PriceHistoryDailyRow
from app.services import edgar_pit, market_data
from app.services.asof_context import (
    AsOfContext,
    AsOfLeakageError,
    asof_scope,
    assert_dates_within,
    current_asof,
)
from app.services.edgar_pit import _FactView
from app.services.price_history import get_asof_daily_rows

_NOW = datetime(2026, 8, 10, tzinfo=timezone.utc)
_AS_OF = date(2025, 6, 6)


def _seed_bars(ticker: str, days: list[date], *, source: str = "yfinance", full: bool = True) -> None:
    with get_session() as session:
        for i, d in enumerate(days):
            px = 100.0 + i
            session.add(PriceHistoryDailyRow(
                ticker=ticker, date=d, close=px, adj_close=px,
                open=px - 0.5 if full else None,
                high=px + 1.0 if full else None,
                low=px - 1.0 if full else None,
                volume=1_000_000 + i if full else None,
                source=source, fetched_at=_NOW,
            ))


# ── Context + guard (a) ─────────────────────────────────────────────────────


def test_asof_scope_sets_and_resets() -> None:
    assert current_asof() is None
    with asof_scope(AsOfContext(as_of=_AS_OF, batch_id="b1")) as ctx:
        assert current_asof() is ctx
    assert current_asof() is None


def test_leakage_assert_raises_on_future_date() -> None:
    with pytest.raises(AsOfLeakageError):
        assert_dates_within([_AS_OF, date(2025, 6, 7)], _AS_OF, origin="test")
    assert_dates_within([], _AS_OF, origin="test")
    assert_dates_within([_AS_OF], _AS_OF, origin="test")


def test_asof_rows_filter_cutoff_and_mock() -> None:
    _seed_bars("ASOF1", [date(2025, 6, 4), date(2025, 6, 5), date(2025, 6, 6), date(2025, 6, 9)])
    _seed_bars("ASOF1", [date(2025, 6, 3)], source="mock_walk")
    rows = get_asof_daily_rows("ASOF1", _AS_OF)
    assert [r[0] for r in rows] == [date(2025, 6, 4), date(2025, 6, 5), date(2025, 6, 6)]
    # ascending, adj_close populated, mock row refused even though it predates the cutoff
    assert rows[-1][5] == pytest.approx(102.0)


# ── Store-backed provider ───────────────────────────────────────────────────


def test_provider_switches_on_context_and_back() -> None:
    market_data.set_market_data_provider(None)
    live = market_data.get_market_data_provider()
    with asof_scope(AsOfContext(as_of=_AS_OF, batch_id="b1")):
        assert market_data.get_market_data_provider().name == "asof_store"
    after = market_data.get_market_data_provider()
    assert after.name == live.name != "asof_store"


def test_asof_quote_and_history_end_at_cutoff() -> None:
    days = [date(2025, 5, 30), date(2025, 6, 2), date(2025, 6, 5), date(2025, 6, 9)]
    _seed_bars("ASOF2", days)
    p = market_data.AsOfStoreProvider(_AS_OF)
    q = p.quote("ASOF2")
    assert q is not None and q.source == "asof_store"
    assert q.price == pytest.approx(102.0)  # the 2025-06-05 bar; 06-09 is the future
    candles = p.history("ASOF2", "3m")
    assert candles is not None and len(candles) == 3
    newest = datetime.fromtimestamp(candles[-1].t, timezone.utc).date()
    assert newest <= _AS_OF
    assert candles[-1].v == pytest.approx(1_000_002)


def test_asof_history_refuses_incomplete_ohlcv_and_unknown_period() -> None:
    _seed_bars("ASOF3", [date(2025, 6, 4), date(2025, 6, 5)], full=False)
    p = market_data.AsOfStoreProvider(_AS_OF)
    assert p.history("ASOF3", "3m") is None  # NULL OHLCV → whole window refused
    assert p.history("ASOF3", "1d") is None  # intraday unservable from daily store
    assert p.news("ASOF3") is None
    assert p.earnings("ASOF3") is None


# ── EDGAR PIT resolvers (pure fixtures) ─────────────────────────────────────


def _q(start: date, end: date, value: float, filed: date, tag: str = "Revenues") -> _FactView:
    return _FactView(tag=tag, value=value, period_start=start, period_end=end, filed=filed)


def _inst(end: date, value: float, filed: date, tag: str) -> _FactView:
    return _FactView(tag=tag, value=value, period_start=None, period_end=end, filed=filed)


def test_resolve_instant_filed_cutoff_is_the_caller_query_but_amendment_wins() -> None:
    facts = [
        _inst(date(2024, 12, 31), 100.0, date(2025, 2, 1), "CashAndCashEquivalentsAtCarryingValue"),
        _inst(date(2024, 12, 31), 110.0, date(2025, 4, 1), "CashAndCashEquivalentsAtCarryingValue"),
    ]
    v = edgar_pit.resolve_instant(
        facts, ("CashAndCashEquivalentsAtCarryingValue",), date(2025, 6, 1),
    )
    assert v == pytest.approx(110.0)  # the later-filed amendment supersedes


def test_resolve_instant_refuses_stale_balance() -> None:
    facts = [_inst(date(2023, 12, 31), 100.0, date(2024, 2, 1), "CashAndCashEquivalentsAtCarryingValue")]
    assert edgar_pit.resolve_instant(
        facts, ("CashAndCashEquivalentsAtCarryingValue",), date(2025, 6, 1),
    ) is None


def test_quarterly_series_differences_cumulative_ytd_facts() -> None:
    """The shape most filers actually use: one fiscal-year start, four
    cumulative period_ends (91/183/273/364 days). Keeping only quarter-length
    spans found ONE quarter per year and zeroed every TTM-derived field on the
    CR164 pilot — so consecutive YTD facts must be differenced."""
    facts = [
        _q(date(2025, 7, 1), date(2025, 9, 30), 21.0, date(2025, 10, 24)),   # Q1
        _q(date(2025, 7, 1), date(2025, 12, 31), 44.0, date(2026, 1, 23)),   # H1
        _q(date(2025, 7, 1), date(2026, 3, 31), 66.0, date(2026, 4, 24)),    # 9M
        _q(date(2025, 7, 1), date(2026, 6, 30), 90.0, date(2026, 8, 4)),     # FY
    ]
    series = edgar_pit.quarterly_series(facts, ("Revenues",))
    assert [round(v, 2) for _, _, v in series] == [21.0, 23.0, 22.0, 24.0]
    assert [e for _, e, _ in series] == [
        date(2025, 9, 30), date(2025, 12, 31), date(2026, 3, 31), date(2026, 6, 30),
    ]
    assert edgar_pit.ttm(series, date(2026, 8, 15)) == pytest.approx(90.0)


def test_quarterly_series_drops_a_gap_rather_than_calling_it_a_quarter() -> None:
    # Q1 then 9M with H1 missing: the difference spans ~182 days and must not
    # be passed off as a quarter.
    facts = [
        _q(date(2025, 7, 1), date(2025, 9, 30), 21.0, date(2025, 10, 24)),
        _q(date(2025, 7, 1), date(2026, 3, 31), 66.0, date(2026, 4, 24)),
    ]
    series = edgar_pit.quarterly_series(facts, ("Revenues",))
    assert [round(v, 2) for _, _, v in series] == [21.0]


def test_quarterly_series_keeps_genuinely_discrete_quarters() -> None:
    facts = [
        _q(date(2025, 1, 1), date(2025, 3, 31), 10.0, date(2025, 5, 1)),
        _q(date(2025, 4, 1), date(2025, 6, 30), 11.0, date(2025, 8, 1)),
    ]
    series = edgar_pit.quarterly_series(facts, ("Revenues",))
    assert [round(v, 2) for _, _, v in series] == [10.0, 11.0]


def test_quarterly_series_derives_q4_from_fy() -> None:
    facts = [
        _q(date(2024, 1, 1), date(2024, 3, 31), 10.0, date(2024, 5, 1)),
        _q(date(2024, 4, 1), date(2024, 6, 30), 11.0, date(2024, 8, 1)),
        _q(date(2024, 7, 1), date(2024, 9, 30), 12.0, date(2024, 11, 1)),
        _q(date(2024, 1, 1), date(2024, 12, 31), 50.0, date(2025, 2, 15)),  # FY total
    ]
    series = edgar_pit.quarterly_series(facts, ("Revenues",))
    assert len(series) == 4
    assert series[-1][1] == date(2024, 12, 31)
    assert series[-1][2] == pytest.approx(17.0)  # 50 − (10+11+12)


def test_ttm_requires_four_fresh_contiguous_quarters() -> None:
    quarters = [
        (date(2024, 7, 1), date(2024, 9, 30), 12.0),
        (date(2024, 10, 1), date(2024, 12, 31), 17.0),
        (date(2025, 1, 1), date(2025, 3, 31), 13.0),
        (date(2025, 4, 1), date(2025, 6, 30), 14.0),
    ]
    assert edgar_pit.ttm(quarters, date(2025, 8, 1)) == pytest.approx(56.0)
    assert edgar_pit.ttm(quarters[1:], date(2025, 8, 1)) is None  # only 3
    # stale: newest quarter ends >200 days before as_of
    assert edgar_pit.ttm(quarters, date(2026, 3, 1)) is None
    # holed: drop a middle quarter, pull in an older one → span guard refuses
    holed = [(date(2024, 4, 1), date(2024, 6, 30), 11.0)] + [quarters[0], quarters[1], quarters[3]]
    assert edgar_pit.ttm(holed, date(2025, 8, 1)) is None


def test_yoy_growth_matches_the_yfinance_definition() -> None:
    quarters = [
        (date(2024, 4, 1), date(2024, 6, 30), 100.0),
        (date(2025, 4, 1), date(2025, 6, 30), 110.0),
    ]
    g = edgar_pit.yoy_quarter_growth(quarters, date(2025, 8, 1))
    assert g == pytest.approx(0.10)
    assert edgar_pit.yoy_quarter_growth(quarters[:1], date(2025, 8, 1)) is None


# ── Profile anchor + regression pins ────────────────────────────────────────


def test_profile_run_date_anchors_at_as_of() -> None:
    from app.services.room_runner import _profile_for_ticker

    profile = _profile_for_ticker("ASOFX", as_of=_AS_OF)
    assert profile["run_date"] == "2025-06-06"


def test_profile_run_date_stays_today_without_as_of() -> None:
    from app.services.room_runner import _profile_for_ticker

    profile = _profile_for_ticker("ASOFX")
    assert profile["run_date"] == datetime.now(timezone.utc).date().isoformat()


def test_backtest_run_index_unique_constraint_is_the_idempotency_gate() -> None:
    from uuid import uuid4

    from sqlalchemy.exc import IntegrityError

    with get_session() as session:
        session.add(BacktestRunIndexRow(
            room_run_id=uuid4(), batch_id="b1", arm="pit_v1",
            ticker="AAPL", as_of=_AS_OF,
        ))
    with pytest.raises(IntegrityError):
        with get_session() as session:
            session.add(BacktestRunIndexRow(
                room_run_id=uuid4(), batch_id="b1", arm="pit_v1",
                ticker="AAPL", as_of=_AS_OF,
            ))
