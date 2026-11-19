"""DEF492 — Alpha Vantage NEWS_SENTIMENT: say why it was refused, and ask once.

On Alpha the sim news route went dark although the Room's NEWS_SENTIMENT calls
returned HTTP 200: Alpha Vantage answers 200 with `{"Information": "..."}` and no
`feed` when it refuses a call (quota, premium-only endpoint, bad key), and the
source discarded that body, so the cause was invisible.

These tests pin: the refusal text is logged and kept (never the key); one cached
per-ticker result serves every caller (Room + sim route) whatever `limit` each
asks for; a refusal is remembered for its own TTL; and no network is touched.
"""

from __future__ import annotations

import types

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.sim import router as sim_router
from app.core.config import settings
from app.services import market_data as _md
from app.services import news_context
from app.services.news_context import (
    _AlphaVantageSource,
    alpha_vantage_failure_reason,
    fetch_alpha_vantage_news_items,
    fetch_live_news,
    set_alpha_vantage_source,
)

_PREMIUM = {
    "Information": (
        "Thank you for using Alpha Vantage! This is a premium endpoint. You may "
        "subscribe to any of the premium plans to instantly unlock all premium endpoints"
    )
}
_QUOTA = {
    "Information": (
        "Thank you for using Alpha Vantage! Our standard API rate limit is 25 "
        "requests per day. Please subscribe to any of the premium plans"
    )
}


class _Resp:
    def __init__(self, status_code: int = 200, body=None) -> None:
        self.status_code = status_code
        self._body = body if body is not None else {}

    def json(self):
        return self._body


class _Client:
    """Scripted httpx.Client stand-in: pops one response per call, repeats the last."""

    def __init__(self, *responses) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    def get(self, url: str, params: dict | None = None):
        self.calls.append(dict(params or {}))
        r = self._responses.pop(0) if len(self._responses) > 1 else self._responses[0]
        if isinstance(r, Exception):
            raise r
        return r


class _Log:
    def __init__(self) -> None:
        self.events: list[tuple[str, str, dict]] = []

    def warn(self, event: str, **kw) -> None:
        self.events.append(("warn", event, kw))

    def info(self, event: str, **kw) -> None:
        self.events.append(("info", event, kw))

    def named(self, event: str) -> list[dict]:
        return [kw for _, e, kw in self.events if e == event]


def _article(title: str = "AAPL beats", ts: str = "20260718T104325") -> dict:
    return {
        "title": title,
        "url": "https://example.com/a",
        "time_published": ts,
        "source": "Benzinga",
        "summary": "s",
        "overall_sentiment_label": "Neutral",
        "ticker_sentiment": [{"ticker": "AAPL", "ticker_sentiment_label": "Bullish"}],
    }


def _feed(n: int) -> dict:
    return {"items": str(n), "feed": [_article(f"headline {i}") for i in range(n)]}


@pytest.fixture(autouse=True)
def _key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "alpha_vantage_api_key", "SECRETKEY123456")
    monkeypatch.setattr(settings, "alpha_vantage_news_cache_ttl_seconds", 1800.0)
    monkeypatch.setattr(settings, "alpha_vantage_news_negative_ttl_seconds", 900.0)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch):
    state = {"now": 1_000_000.0}
    monkeypatch.setattr(news_context, "time", types.SimpleNamespace(time=lambda: state["now"]))
    return state


@pytest.fixture
def log(monkeypatch: pytest.MonkeyPatch) -> _Log:
    rec = _Log()
    monkeypatch.setattr(news_context, "logger", rec)
    return rec


def _src(*responses) -> tuple[_AlphaVantageSource, _Client]:
    src = _AlphaVantageSource()
    client = _Client(*responses)
    src._client = client
    return src, client


# ── (a) the refusal text is visible ───────────────────────────────────────


@pytest.mark.parametrize("body, field", [
    (_PREMIUM, "Information"),
    (_QUOTA, "Information"),
    ({"Note": "Thank you for using Alpha Vantage! 5 calls per minute"}, "Note"),
    ({"Error Message": "Invalid API call."}, "Error Message"),
])
def test_refusal_text_is_logged_and_kept(body, field, log) -> None:
    src, _ = _src(_Resp(200, body))
    assert src.fetch("AAPL", 5) is None
    logged = log.named("news_context_alpha_vantage_no_feed")
    assert len(logged) == 1
    assert logged[0]["reason"].startswith(f"{field}: ")
    assert str(body[field])[:40] in logged[0]["reason"]
    assert src.last_failure("aapl") == logged[0]["reason"]


def test_empty_feed_without_information_is_named_not_guessed(log) -> None:
    src, _ = _src(_Resp(200, {"items": "0", "feed": []}))
    assert src.fetch("AAPL", 5) is None
    assert src.last_failure("AAPL").startswith("empty_feed")


def test_refusal_text_never_contains_the_key(log) -> None:
    echo = {"Information": "invalid key SECRETKEY123456 supplied"}
    src, _ = _src(_Resp(200, echo))
    src.fetch("AAPL", 5)
    assert "SECRETKEY123456" not in src.last_failure("AAPL")
    assert "SECRETKEY123456" not in repr(log.events)


def test_non_dict_body_is_a_loud_refusal_not_a_crash(log) -> None:
    src, _ = _src(_Resp(200, ["unexpected"]))
    assert src.fetch("AAPL", 5) is None
    assert log.named("news_context_alpha_vantage_parse_error")


def test_failure_reason_clears_after_a_success(clock, log) -> None:
    src, _ = _src(_Resp(200, _PREMIUM), _Resp(200, _feed(2)))
    src.fetch("AAPL", 5)
    assert src.last_failure("AAPL")
    clock["now"] += 901
    assert src.fetch("AAPL", 5) is not None
    assert src.last_failure("AAPL") is None


# ── (b) cache: hit, miss, TTL ─────────────────────────────────────────────


def test_hit_serves_second_call_without_network(clock, log) -> None:
    src, client = _src(_Resp(200, _feed(5)))
    first = src.fetch("AAPL", 5)
    second = src.fetch("aapl", 5)
    assert first == second and len(first) == 5
    assert len(client.calls) == 1


def test_one_entry_serves_every_limit(clock, log) -> None:
    src, client = _src(_Resp(200, _feed(10)))
    assert len(src.fetch("AAPL", 5)) == 5
    assert len(src.fetch("AAPL", 3)) == 3
    assert len(src.fetch("AAPL", 10)) == 10
    assert len(client.calls) == 1
    assert client.calls[0]["limit"] == "10"


def test_miss_on_a_different_ticker(clock, log) -> None:
    src, client = _src(_Resp(200, _feed(2)))
    src.fetch("AAPL", 5)
    src.fetch("MSFT", 5)
    assert [c["tickers"] for c in client.calls] == ["AAPL", "MSFT"]


def test_positive_ttl_expiry_refetches(clock, log, monkeypatch) -> None:
    monkeypatch.setattr(settings, "alpha_vantage_news_cache_ttl_seconds", 100.0)
    src, client = _src(_Resp(200, _feed(2)))
    src.fetch("AAPL", 5)
    clock["now"] += 99
    src.fetch("AAPL", 5)
    assert len(client.calls) == 1
    clock["now"] += 2
    src.fetch("AAPL", 5)
    assert len(client.calls) == 2


def test_refusal_is_cached_for_the_negative_ttl_then_retried(clock, log, monkeypatch) -> None:
    monkeypatch.setattr(settings, "alpha_vantage_news_negative_ttl_seconds", 60.0)
    src, client = _src(_Resp(200, _PREMIUM), _Resp(200, _feed(2)))
    assert src.fetch("AAPL", 5) is None
    clock["now"] += 59
    assert src.fetch("AAPL", 5) is None
    assert len(client.calls) == 1
    assert len(log.named("news_context_alpha_vantage_no_feed")) == 1
    clock["now"] += 2
    assert len(src.fetch("AAPL", 5)) == 2
    assert len(client.calls) == 2


def test_network_error_and_bad_status_are_not_negative_cached(clock, log) -> None:
    src, client = _src(httpx.ConnectError("dns"), _Resp(503), _Resp(200, _feed(1)))
    assert src.fetch("AAPL", 5) is None
    assert src.last_failure("AAPL").startswith("network_error")
    assert src.fetch("AAPL", 5) is None
    assert src.last_failure("AAPL") == "http_503"
    assert len(src.fetch("AAPL", 5)) == 1
    assert len(client.calls) == 3


# ── Room and the sim route share ONE cached result ────────────────────────


class _NoYahoo:
    name = "nope"

    def news(self, ticker, limit=5):
        return None

    def quote(self, ticker):
        return None

    def get_price(self, ticker):
        return None

    def history(self, ticker, period):
        return None

    def earnings(self, ticker):
        return None


@pytest.fixture
def real_source_on_fake_client(clock, log, monkeypatch):
    """The production wiring: `get_alpha_vantage_source()` is the one object both callers use."""
    monkeypatch.setattr(_md, "_provider", _NoYahoo())
    src, client = _src(_Resp(200, _feed(5)))
    set_alpha_vantage_source(src)
    # published recently relative to the frozen clock so the Room's recency floor keeps them
    yield src, client
    set_alpha_vantage_source(None)


def test_room_fetch_then_sim_route_fetch_make_one_call(real_source_on_fake_client, monkeypatch) -> None:
    src, client = real_source_on_fake_client
    monkeypatch.setattr(news_context, "_within_recency_floor", lambda item, now: True)
    assert fetch_live_news("AAPL")  # what the Room calls (limit 5)
    items = fetch_alpha_vantage_news_items("AAPL", 3)  # what GET /v1/sim/news calls
    assert items and len(items) == 3
    assert len(client.calls) == 1


def test_sim_route_fetch_then_room_fetch_make_one_call(real_source_on_fake_client, monkeypatch) -> None:
    src, client = real_source_on_fake_client
    monkeypatch.setattr(news_context, "_within_recency_floor", lambda item, now: True)
    assert fetch_alpha_vantage_news_items("AAPL", 8)
    assert fetch_live_news("AAPL")
    assert len(client.calls) == 1


def test_a_refusal_seen_by_the_room_is_not_re_asked_by_the_sim_route(clock, log, monkeypatch) -> None:
    monkeypatch.setattr(_md, "_provider", _NoYahoo())
    src, client = _src(_Resp(200, _PREMIUM))
    set_alpha_vantage_source(src)
    try:
        assert fetch_live_news("AAPL") is None
        assert fetch_alpha_vantage_news_items("AAPL", 5) is None
        reason = alpha_vantage_failure_reason("AAPL")
    finally:
        set_alpha_vantage_source(None)
    assert len(client.calls) == 1
    assert "premium endpoint" in reason


# ── sim_news_unavailable carries the provider's reason ────────────────────


def test_sim_news_unavailable_log_names_the_av_reason(clock, monkeypatch) -> None:
    from app.services import sim_engine

    rec = _Log()
    monkeypatch.setattr(sim_engine, "logger", rec)
    monkeypatch.setattr(news_context, "logger", _Log())
    monkeypatch.setattr(_md, "_provider", _NoYahoo())
    src, _ = _src(_Resp(200, _PREMIUM))
    set_alpha_vantage_source(src)
    try:
        app = FastAPI()
        app.include_router(sim_router)
        r = TestClient(app, raise_server_exceptions=False).get("/v1/sim/news/AAPL")
    finally:
        set_alpha_vantage_source(None)
    assert r.json() == {"ticker": "AAPL", "source": "unavailable", "articles": []}
    (logged,) = rec.named("sim_news_unavailable")
    assert logged["alpha_vantage_configured"] is True
    assert logged["alpha_vantage_reason"].startswith("Information: ")
    assert "premium endpoint" in logged["alpha_vantage_reason"]
    assert "SECRETKEY123456" not in repr(rec.events)


def test_sim_news_unavailable_without_key_has_no_reason(monkeypatch) -> None:
    from app.services import sim_engine

    rec = _Log()
    monkeypatch.setattr(sim_engine, "logger", rec)
    monkeypatch.setattr(settings, "alpha_vantage_api_key", "")
    monkeypatch.setattr(_md, "_provider", _NoYahoo())
    app = FastAPI()
    app.include_router(sim_router)
    TestClient(app, raise_server_exceptions=False).get("/v1/sim/news/AAPL")
    (logged,) = rec.named("sim_news_unavailable")
    assert logged["alpha_vantage_configured"] is False
    assert logged["alpha_vantage_reason"] is None


# ── Yahoo news: the locked yfinance must be one that still has a news endpoint ──


def test_locked_yfinance_is_new_enough_to_have_a_working_news_endpoint() -> None:
    """DEF492 — yfinance 1.3.0 posts to Yahoo's retired `/xhr/ncp` and raises
    "YAHOO! FINANCE IS CURRENTLY DOWN!" for every ticker on every network
    (reproduced from a laptop, not just melehost); 1.8.0 uses the live GraphQL
    endpoint. The container installs from uv.lock, so the lock is what matters."""
    import pathlib
    import tomllib

    root = pathlib.Path(__file__).resolve().parents[2]
    lock = tomllib.loads((root / "uv.lock").read_text())
    version = next(p["version"] for p in lock["package"] if p["name"] == "yfinance")
    assert tuple(int(x) for x in version.split(".")[:2]) >= (1, 8), version
    assert "yfinance>=1.8.0" in (root / "pyproject.toml").read_text()
