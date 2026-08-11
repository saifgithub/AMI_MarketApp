"""DEF252 — a quote must state the day's change and the session, not the defaults.

`YfinanceProvider.quote()` was one line — `return Quote(price=..., source=...)`.
`change_pct` and `market_state` therefore fell through to the `Quote` NamedTuple
defaults, `0.0` and `"CLOSED"`, and the API handed both to the app, which renders
them as fact. Saiful saw the result on his iPhone at 14:37 ET on Monday
2026-08-10 — mid-session, on a −2% day — as `CLOSED · NFLX $75.51 −0.0% · AMD
$475.65 −0.0%`. yfinance is the production provider, so this was not a degraded
path; it was the only path, and it was wrong for every quote Alpha has ever
served.

The interesting part is that this was already known. `price_history.py` and
`trading_math/market_hours.py` both say in prose that `Quote.market_state` cannot
be trusted because the production provider never sets it, and CR109 built
`is_us_market_open()` rather than fix it. The workaround protected the game's fill
gate and left the user-facing tape wrong — a defaulted value asserting a fact
nobody supplied, which is CR040's rule inverted.

Two sources, deliberately different:

* `change_pct` is free. The previous close is on the SAME `fast_info` object the
  price came from, so there is no second round-trip.
* `market_state` is NOT on `fast_info` (`KeyError`, verified against the live
  API). It exists only on the heavy `.info` call CR145 flags as the uncached
  hot-path hazard, so it is derived from the pure no-network session calendar
  instead of bought.

The last test here is the P18 one: everything above proves the provider, and a
provider that is right while the route still emits a default would be DEF238 all
over again. So it drives the real `/v1/sim/quote/{ticker}` with only the network
faked.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
import structlog
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.sim import router as sim_router
from app.services import market_data as _md
from app.services.market_data import Quote, YfinanceProvider, _previous_close
from app.services.sim_engine import get_sim_engine


class _FastInfo:
    """Mimics yfinance's FastInfo: a mapping that RAISES on an absent key.

    That behaviour is the whole reason `_previous_close` is guarded — a plain
    dict returning None would not have reproduced it.
    """

    def __init__(self, price: float | None, **fields: float) -> None:
        self.last_price = price
        self._fields = fields

    def __getitem__(self, key: str) -> float:
        return self._fields[key]  # KeyError, exactly like FastInfo


class _YfModule:
    def __init__(self, fast_info: _FastInfo) -> None:
        self._fast_info = fast_info

    def Ticker(self, t: str):  # noqa: ANN201, N802
        return _Ticker(self._fast_info)


@dataclass
class _Ticker:
    fast_info: _FastInfo


def _provider(fast_info: _FastInfo) -> YfinanceProvider:
    p = YfinanceProvider.__new__(YfinanceProvider)
    p._yf = _YfModule(fast_info)
    return p


# ── change_pct ───────────────────────────────────────────────────────────


def test_the_change_is_computed_against_the_previous_close():
    p = _provider(_FastInfo(308.26, regular_market_previous_close=313.33))
    q = p.quote("AAPL")
    assert q is not None
    assert q.change_pct == pytest.approx(-1.62, abs=0.01)


def test_a_flat_session_is_zero_and_that_is_now_a_measurement():
    """0.0 was the bug's signature; it is also a legitimate answer. What changed
    is that it is now derived rather than assumed."""
    p = _provider(_FastInfo(100.0, regular_market_previous_close=100.0))
    assert p.quote("AAPL").change_pct == 0.0


def test_the_regular_session_close_wins_over_the_plain_one():
    """They genuinely disagree — 313.33 against 313.25 on AAPL, 2026-08-10 — and
    Yahoo's own `regularMarketChangePercent` divides by the regular one. The app
    shows this beside a price the user can check against Yahoo in another tab, so
    matching Yahoo beats picking the fresher-looking number."""
    info = _FastInfo(
        308.26, regular_market_previous_close=313.33, previous_close=313.25
    )
    assert _previous_close(info) == 313.33


def test_the_plain_close_is_used_when_the_regular_one_is_absent():
    assert _previous_close(_FastInfo(308.26, previous_close=313.25)) == 313.25


def test_a_zero_previous_close_is_not_a_previous_close():
    """Guards the division, and the falsy check that does it."""
    assert _previous_close(_FastInfo(308.26, regular_market_previous_close=0.0)) is None


def test_no_previous_close_says_so_out_loud():
    """CR040. 0.0 is indistinguishable from "flat" on the pixel, so the one case
    that still asserts a number it does not have must not do it silently. A
    nullable `change_pct` end to end is the real answer and needs the Flutter
    half — recorded on the DEF252 row, not smuggled in here."""
    p = _provider(_FastInfo(308.26))
    with structlog.testing.capture_logs() as captured:
        q = p.quote("AAPL")
    assert q.change_pct == 0.0
    assert [e for e in captured if e["event"] == "yfinance_quote_no_previous_close"]


def test_a_quote_that_knows_its_change_says_nothing(caplog):
    """Precision on that counter: if the good path logged too, the warning would
    be noise and stop being read."""
    p = _provider(_FastInfo(308.26, regular_market_previous_close=313.33))
    with structlog.testing.capture_logs() as captured:
        p.quote("AAPL")
    assert not [
        e for e in captured if e["event"] == "yfinance_quote_no_previous_close"
    ]


# ── market_state ─────────────────────────────────────────────────────────


def test_the_session_comes_from_the_calendar_not_the_default(monkeypatch):
    info = _FastInfo(308.26, regular_market_previous_close=313.33)
    monkeypatch.setattr(_md, "is_us_market_open", lambda _now: True)
    assert _provider(info).quote("AAPL").market_state == "REGULAR"
    monkeypatch.setattr(_md, "is_us_market_open", lambda _now: False)
    assert _provider(info).quote("AAPL").market_state == "CLOSED"


def test_the_calendar_is_consulted_with_an_aware_utc_now(monkeypatch):
    """`is_us_market_open` converts to ET, and a naive datetime would be read as
    UTC by convention — correct here, but only by luck. Assert the aware one,
    because the failure is a silent four-or-five-hour shift in when the market
    appears to open."""
    seen: list = []

    def _spy(now):  # noqa: ANN001, ANN202
        seen.append(now)
        return True

    monkeypatch.setattr(_md, "is_us_market_open", _spy)
    _provider(_FastInfo(308.26, regular_market_previous_close=313.33)).quote("AAPL")
    assert len(seen) == 1
    assert seen[0].tzinfo is not None


# ── the caller (P18) ─────────────────────────────────────────────────────


def test_the_route_serves_the_derived_values_not_the_defaults(monkeypatch):
    """Everything above proves the provider. This proves the thing the user
    actually hit: `GET /v1/sim/quote/AAPL` returned
    `{"change_pct":0.0,"market_state":"CLOSED"}` at 14:41 ET while Yahoo said
    REGULAR and −2.02%.

    A provider that is right while the response still carries a default is
    exactly DEF238's shape (P18) — proven on the builder, never on the caller.
    """
    monkeypatch.setattr(_md, "is_us_market_open", lambda _now: True)
    provider = _provider(_FastInfo(308.26, regular_market_previous_close=313.33))

    class _Sim:
        def current_quote(self, ticker: str) -> Quote:
            return provider.quote(ticker)

    app = FastAPI()
    app.include_router(sim_router)
    app.dependency_overrides[get_sim_engine] = lambda: _Sim()
    client = TestClient(app, raise_server_exceptions=False)

    body = client.get("/v1/sim/quote/AAPL").json()
    assert body["market_state"] == "REGULAR", body
    assert body["change_pct"] == pytest.approx(-1.62, abs=0.01), body
    # The two defaults, named, so a regression reads as itself in the failure.
    assert not (body["market_state"] == "CLOSED" and body["change_pct"] == 0.0)
