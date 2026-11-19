"""DEF501 guard: /v1/sim/earnings/{ticker} tells "none scheduled" from "unavailable".

AMI-DL-3 (E5-TICK-01): Ticker Detail showed no earnings pill, so a tester could
not tell a quiet calendar from a dead feed. Cause: `YfinanceProvider.earnings`
returned None for BOTH "calendar read, nothing in the next 90 days" and "could
not read it", and the app hid the pill on null. The provider now returns an
all-None `EarningsInfo` for the first and keeps None for the second; the route
names the state in `status`.

Test our logic with a fake yfinance Ticker for AAPL / MSFT / NVDA.
"""

from __future__ import annotations

import datetime
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.sim import router as sim_router
from app.services import market_data as _md
from app.services.market_data import EarningsInfo, YfinanceProvider
from app.services.sim_engine import SimEngine, get_sim_engine


def _provider_with_calendar(calendar, *, boom: bool = False) -> YfinanceProvider:
    class _Ticker:
        def __init__(self, symbol: str) -> None:
            self.symbol = symbol
            self.info = {}

        @property
        def calendar(self):
            if boom:
                raise RuntimeError("yahoo 429")
            return calendar

    p = YfinanceProvider.__new__(YfinanceProvider)
    p._yf = SimpleNamespace(Ticker=_Ticker)
    return p


def _in(days: int) -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)


@pytest.mark.parametrize("ticker", ["AAPL", "MSFT", "NVDA"])
def test_report_inside_window_is_scheduled(ticker: str) -> None:
    cal = {"Earnings Date": [_in(30)], "Earnings Average": 2.5}
    info = _provider_with_calendar(cal).earnings(ticker)
    assert info is not None and info.earnings_date is not None
    assert info.eps_estimate == 2.5


@pytest.mark.parametrize("ticker", ["AAPL", "MSFT", "NVDA"])
def test_report_beyond_window_is_a_measurement_not_an_outage(ticker: str) -> None:
    cal = {"Earnings Date": [_in(120)], "Earnings Average": 2.5}
    info = _provider_with_calendar(cal).earnings(ticker)
    assert info is not None, "a read calendar with nothing in window is not None"
    assert info.earnings_date is None
    assert info.quarter is None and info.eps_estimate is None


def test_calendar_without_an_earnings_date_is_none_scheduled() -> None:
    info = _provider_with_calendar({"Ex-Dividend Date": _in(10)}).earnings("AAPL")
    assert info is not None and info.earnings_date is None


@pytest.mark.parametrize("calendar", [{}, None])
def test_empty_calendar_stays_unavailable(calendar) -> None:
    assert _provider_with_calendar(calendar).earnings("MSFT") is None


def test_feed_error_stays_unavailable() -> None:
    assert _provider_with_calendar({}, boom=True).earnings("NVDA") is None


class _Provider:
    name = "fake"

    def __init__(self, info: EarningsInfo | None) -> None:
        self._info = info

    def earnings(self, ticker: str):
        return self._info

    def quote(self, ticker: str):
        return _md.Quote(price=100.0, source="yfinance")


def _client(info: EarningsInfo | None) -> TestClient:
    app = FastAPI()
    app.include_router(sim_router)
    app.dependency_overrides[get_sim_engine] = lambda: SimEngine(provider=_Provider(info))
    return TestClient(app)


def test_route_status_scheduled() -> None:
    body = _client(EarningsInfo("2026-12-20", "Q4", 2.1)).get("/v1/sim/earnings/AAPL").json()
    assert body["status"] == "scheduled"
    assert body["earnings_date"] == "2026-12-20"


def test_route_status_none_scheduled() -> None:
    body = _client(EarningsInfo(None, None, None)).get("/v1/sim/earnings/MSFT").json()
    assert body["status"] == "none_scheduled"
    assert body["earnings_date"] is None
    assert body["source"] == "yfinance"


def test_route_status_unavailable() -> None:
    body = _client(None).get("/v1/sim/earnings/NVDA").json()
    assert body["status"] == "unavailable"
    assert body["source"] == "unavailable"
