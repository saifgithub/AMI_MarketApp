"""CR183 — GET /v1/sector-watch/{user_id}.

Covers the composing endpoint's contract: happy path (leading sector = largest
absolute mean day move over LIVE-sourced touched tickers, leader = largest
absolute mover in it, top headline attached), mock_walk exclusion (a fabricated
mock change_pct must never feed the mean nor crown a leader — CR040), the
empty state (no touched tickers) being distinct from the unavailable state
(feed unreadable), ownership 404, and never-500 on provider failure.

The sim engine is replaced via FastAPI dependency_overrides with a fake that
controls each ticker's Quote source; the sector map is seeded through the
CR026 test seam (conftest resets it between tests).
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.sector_watch import router
from app.services.auth_service import AuthService
from app.services.market_data import NewsItem, Quote
from app.services.sector_allocation import (
    SectorMapProvider,
    reset_sector_map_provider,
)
from app.services.sim_engine import get_sim_engine
from app.services.watchlist_store import get_watchlist_store

SECTORS = {"NVDA": "Technology", "AAPL": "Technology", "XOM": "Energy"}


class FakeSim:
    """Just the three surfaces _compose reads, with per-ticker quote control."""

    def __init__(self, quotes: dict[str, Quote], *, holdings: list[str] = (),
                 news: list[NewsItem] | None = None, news_source: str = "yfinance"):
        self._quotes = quotes
        self._holdings = list(holdings)
        self._news = news if news is not None else [
            NewsItem(title="Chips rally on AI demand", link="https://x",
                     publisher="Reuters", published_at=1755600000),
        ]
        self._news_source = news_source
        self.news_asked_for: list[str] = []

    def ensure_portfolio(self, user_id):
        return SimpleNamespace(
            holdings=[SimpleNamespace(ticker=t) for t in self._holdings],
        )

    def current_marks_with_source(self, tickers):
        return {t: self._quotes[t] for t in tickers if t in self._quotes}

    def current_news(self, ticker, limit=5):
        self.news_asked_for.append(ticker)
        if not self._news:
            return [], "unavailable"
        return self._news[:limit], self._news_source


def _app_with(fake: FakeSim) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_sim_engine] = lambda: fake
    return app


def _user_and_headers():
    auth = AuthService()
    user, token, _ = auth.ensure_anonymous(device_user_id=None)
    return user.id, {"Authorization": f"Bearer {token}"}


def _seed_sector_map():
    reset_sector_map_provider(SectorMapProvider(fetcher=lambda: dict(SECTORS)))


@pytest.fixture(autouse=True)
def _sector_map():
    _seed_sector_map()
    yield
    reset_sector_map_provider(None)


def _live(change_pct: float) -> Quote:
    return Quote(price=100.0, source="yfinance", change_pct=change_pct)


def test_happy_path_leading_sector_leader_and_headline():
    user_id, headers = _user_and_headers()
    get_watchlist_store().add(user_id, "NVDA")
    get_watchlist_store().add(user_id, "XOM")
    fake = FakeSim(
        {"NVDA": _live(3.0), "AAPL": _live(1.0), "XOM": _live(0.5)},
        holdings=["AAPL"],
    )
    client = TestClient(_app_with(fake), raise_server_exceptions=False)

    r = client.get(f"/v1/sector-watch/{user_id}", headers=headers)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["state"] == "ok"
    assert body["sector"] == "Technology"  # |mean(3,1)|=2.0 beats |0.5|
    assert body["move_pct"] == pytest.approx(2.0)
    assert body["leader"] == "NVDA"
    assert body["leader_change_pct"] == pytest.approx(3.0)
    assert body["tickers_considered"] == 3
    assert body["headline"]["title"] == "Chips rally on AI demand"
    assert body["headline"]["publisher"] == "Reuters"
    assert body["quote_source"] == "yfinance"
    assert body["news_source"] == "yfinance"
    assert fake.news_asked_for == ["NVDA"]


def test_mock_walk_quotes_are_excluded_from_the_move():
    user_id, headers = _user_and_headers()
    get_watchlist_store().add(user_id, "NVDA")
    get_watchlist_store().add(user_id, "AAPL")
    get_watchlist_store().add(user_id, "XOM")
    # NVDA's huge move is a mock fabrication — with it excluded, Technology's
    # mean is AAPL's +1.0 and Energy's +2.0 leads with XOM.
    fake = FakeSim({
        "NVDA": Quote(price=100.0, source="mock_walk", change_pct=9.9),
        "AAPL": _live(1.0),
        "XOM": _live(2.0),
    })
    client = TestClient(_app_with(fake), raise_server_exceptions=False)

    body = client.get(f"/v1/sector-watch/{user_id}", headers=headers).json()

    assert body["state"] == "ok"
    assert body["sector"] == "Energy"
    assert body["leader"] == "XOM"
    assert body["move_pct"] == pytest.approx(2.0)
    assert body["tickers_considered"] == 2  # NVDA never fed the computation


def test_all_mock_quotes_is_unavailable_never_a_zero_move():
    user_id, headers = _user_and_headers()
    get_watchlist_store().add(user_id, "NVDA")
    fake = FakeSim({"NVDA": Quote(price=100.0, source="mock_walk", change_pct=1.5)})
    client = TestClient(_app_with(fake), raise_server_exceptions=False)

    body = client.get(f"/v1/sector-watch/{user_id}", headers=headers).json()

    assert body["state"] == "unavailable"
    assert body["reason"] == "no_live_quotes"
    assert body["move_pct"] is None
    assert body["sector"] is None
    assert body["leader"] is None


def test_no_touched_tickers_is_empty_not_unavailable():
    user_id, headers = _user_and_headers()
    fake = FakeSim({})
    client = TestClient(_app_with(fake), raise_server_exceptions=False)

    body = client.get(f"/v1/sector-watch/{user_id}", headers=headers).json()

    assert body["state"] == "empty"
    assert body["reason"] is None
    assert body["tickers_considered"] == 0


def test_no_news_for_leader_is_unavailable():
    user_id, headers = _user_and_headers()
    get_watchlist_store().add(user_id, "NVDA")
    fake = FakeSim({"NVDA": _live(2.0)}, news=[])
    client = TestClient(_app_with(fake), raise_server_exceptions=False)

    body = client.get(f"/v1/sector-watch/{user_id}", headers=headers).json()

    assert body["state"] == "unavailable"
    assert body["reason"] == "no_news"
    assert body["move_pct"] is None


def test_other_users_id_is_404():
    _, headers = _user_and_headers()
    client = TestClient(_app_with(FakeSim({})), raise_server_exceptions=False)

    r = client.get(f"/v1/sector-watch/{uuid4()}", headers=headers)

    assert r.status_code == 404


def test_provider_failure_degrades_to_unavailable_never_500():
    user_id, headers = _user_and_headers()

    class ExplodingSim(FakeSim):
        def current_marks_with_source(self, tickers):
            raise RuntimeError("feed down")

    get_watchlist_store().add(user_id, "NVDA")
    client = TestClient(
        _app_with(ExplodingSim({})), raise_server_exceptions=False,
    )

    r = client.get(f"/v1/sector-watch/{user_id}", headers=headers)

    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "unavailable"
    assert body["reason"] == "error"
