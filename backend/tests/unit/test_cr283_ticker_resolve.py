"""CR283 — `GET /v1/tickers/resolve`: company name -> ticker, per market.

The network is mocked: every test feeds `ticker_resolve._fetch_search` a Yahoo
search payload (shape probed 2026-11-24) or an httpx MockTransport. The
load-bearing properties are the exchange filter (a Bursa listing never leaks into
the US answer or vice versa), the Bursa-off refusal, and that an upstream failure
is a 503 with a reason, never an empty candidate list (CR040).
"""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.tickers import router as tickers_router
from app.core.config import settings
from app.services import ticker_resolve
from app.trading_math.markets import Market


def _q(symbol, exchange, short, long=None, qtype="EQUITY"):
    return {
        "symbol": symbol,
        "exchange": exchange,
        "shortname": short,
        "longname": long or short,
        "quoteType": qtype,
    }


_CIMB = {
    "quotes": [
        _q("1023.KL", "KLS", "CIMB", "CIMB Group Holdings Berhad"),
        _q("CIMB", "NYQ", "CIMB Test Corp", "CIMB Test Corporation"),
        _q("CIMB.SI", "SES", "CIMB Singapore"),
        _q("1023.KL", "KLS", "CIMB duplicate"),
        _q("CIMBW.KL", "KLS", "warrant-shaped, not a code"),
        _q("BRK-B", "NYQ", "Berkshire Hathaway", "Berkshire Hathaway Inc."),
        _q("SOMEFUND", "NMS", "A mutual fund", qtype="MUTUALFUND"),
    ]
}


@pytest.fixture(autouse=True)
def _fresh_cache():
    ticker_resolve.clear_cache()
    yield
    ticker_resolve.clear_cache()


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(tickers_router)
    return TestClient(app)


@pytest.fixture
def bursa_on(monkeypatch):
    monkeypatch.setattr(settings, "market_bursa_enabled", True)


@pytest.fixture
def bursa_off(monkeypatch):
    monkeypatch.setattr(settings, "market_bursa_enabled", False)


@pytest.fixture
def yahoo(monkeypatch):
    calls: list[str] = []

    def fake(q, client=None):
        calls.append(q)
        return _CIMB

    monkeypatch.setattr(ticker_resolve, "_fetch_search", fake)
    return calls


def test_my_keeps_only_bursa_listings(client, bursa_on, yahoo):
    r = client.get("/v1/tickers/resolve", params={"q": "CIMB", "market": "MY"})
    assert r.status_code == 200
    body = r.json()
    assert body["market"] == "MY"
    assert body["candidates"] == [
        {
            "ticker": "1023.KL",
            "market": "MY",
            "short_name": "CIMB",
            "long_name": "CIMB Group Holdings Berhad",
        }
    ]


def test_us_keeps_only_us_venues_and_class_share_dot(client, bursa_on, yahoo):
    r = client.get("/v1/tickers/resolve", params={"q": "CIMB", "market": "us"})
    assert r.status_code == 200
    tickers = [c["ticker"] for c in r.json()["candidates"]]
    assert tickers == ["CIMB", "BRK.B"]
    assert all(c["market"] == "US" for c in r.json()["candidates"])


def test_us_works_with_bursa_off(client, bursa_off, yahoo):
    r = client.get("/v1/tickers/resolve", params={"q": "CIMB", "market": "US"})
    assert r.status_code == 200
    assert [c["ticker"] for c in r.json()["candidates"]] == ["CIMB", "BRK.B"]


def test_bursa_off_refuses_my_without_calling_yahoo(client, bursa_off, yahoo):
    r = client.get("/v1/tickers/resolve", params={"q": "CIMB", "market": "MY"})
    assert r.status_code == 422
    assert r.json()["detail"] == "Bursa Malaysia is not available yet."
    assert yahoo == []


def test_unknown_market_is_422(client, bursa_on, yahoo):
    r = client.get("/v1/tickers/resolve", params={"q": "CIMB", "market": "SG"})
    assert r.status_code == 422
    assert yahoo == []


def test_blank_query_is_422(client, bursa_on, yahoo):
    r = client.get("/v1/tickers/resolve", params={"q": "   ", "market": "US"})
    assert r.status_code == 422
    assert yahoo == []


def test_no_match_is_200_empty(client, bursa_on, monkeypatch):
    monkeypatch.setattr(ticker_resolve, "_fetch_search", lambda q, client=None: {"quotes": []})
    r = client.get("/v1/tickers/resolve", params={"q": "zzzzqq", "market": "MY"})
    assert r.status_code == 200
    assert r.json()["candidates"] == []


def test_upstream_failure_is_503_never_an_empty_list(client, bursa_on, monkeypatch):
    def boom(q, client=None):
        raise ticker_resolve.TickerResolveUnavailable("Yahoo search failed: ConnectError")

    monkeypatch.setattr(ticker_resolve, "_fetch_search", boom)
    r = client.get("/v1/tickers/resolve", params={"q": "CIMB", "market": "MY"})
    assert r.status_code == 503
    assert "unavailable" in r.json()["detail"]
    assert "ConnectError" in r.json()["detail"]


def test_failure_is_not_cached(client, bursa_on, monkeypatch):
    state = {"down": True, "calls": 0}

    def flaky(q, client=None):
        state["calls"] += 1
        if state["down"]:
            raise ticker_resolve.TickerResolveUnavailable("down")
        return _CIMB

    monkeypatch.setattr(ticker_resolve, "_fetch_search", flaky)
    assert client.get("/v1/tickers/resolve", params={"q": "CIMB", "market": "MY"}).status_code == 503
    state["down"] = False
    r = client.get("/v1/tickers/resolve", params={"q": "CIMB", "market": "MY"})
    assert r.status_code == 200
    assert r.json()["candidates"][0]["ticker"] == "1023.KL"


def test_results_are_cached_per_market_and_case_insensitive(client, bursa_on, yahoo):
    client.get("/v1/tickers/resolve", params={"q": "CIMB", "market": "MY"})
    client.get("/v1/tickers/resolve", params={"q": "cimb ", "market": "MY"})
    assert len(yahoo) == 1
    client.get("/v1/tickers/resolve", params={"q": "CIMB", "market": "US"})
    assert len(yahoo) == 2


def test_http_layer_maps_status_and_garbage_to_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["q"] == "boom":
            return httpx.Response(429, text="Too Many Requests")
        if request.url.params["q"] == "junk":
            return httpx.Response(200, text="<html>not json</html>")
        if request.url.params["q"] == "shape":
            return httpx.Response(200, json={"finance": {"error": "x"}})
        assert request.url.params["quotesCount"] == "10"
        assert request.url.params["newsCount"] == "0"
        return httpx.Response(200, json=_CIMB)

    http = httpx.Client(transport=httpx.MockTransport(handler))
    for bad in ("boom", "junk", "shape"):
        with pytest.raises(ticker_resolve.TickerResolveUnavailable):
            ticker_resolve.resolve(bad, Market.MY, client=http)
    got = ticker_resolve.resolve("CIMB", Market.MY, client=http)
    assert [c.ticker for c in got] == ["1023.KL"]


def test_real_client_sends_a_browser_user_agent():
    assert ticker_resolve._USER_AGENT.startswith("Mozilla/5.0")
