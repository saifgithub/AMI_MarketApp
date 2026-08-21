"""CR172 §4 — the chain surface: fillability, providers, rate, enrichment.

What is pinned, and why it is the §4 shape and not a smaller one:

* `classify_option_quote` has THREE states — `bid=0/ask=0.05` is a real
  quote meaning worthless (closeable at 0, never openable), not a data
  failure; a wide spread is a LIQUIDITY failure surfaced by reason; only
  missing/degenerate quotes are `unusable`. Collapsing any pair of these
  is the CR170 §5 outage-fires-the-book bug wearing options clothes.
* Wrappers forward the LEAF chain — `CachingProvider` and
  `FallbackProvider` must never substitute a stack name for
  `OptionChain.source` (the LIVE/MOCK-pill honesty rule).
* `MockWalkProvider` and `AsOfStoreProvider` serve None (D10 ratified; no
  historical store exists) — options go dark honestly, never synthetically.
* `get_risk_free_rate` refuses a synthetic or implausible quote: the mock
  walk prices `^IRX` like a $300 stock and 300% would flow into every
  greek while looking like a number.
* `enrich_chain` figures are TRACEABLE: the greeks equal `bs_greeks` on
  the same inputs, the solved IV round-trips the mid, and every
  unpriceable strike carries an explicit reason.
"""

from __future__ import annotations

import datetime

from app.services import option_chain as oc
from app.services.market_data import (
    AsOfStoreProvider,
    CachingProvider,
    FallbackProvider,
    MockWalkProvider,
    OptionChain,
    OptionQuote,
    Quote,
    classify_option_quote,
    set_market_data_provider,
)
from app.trading_math import bs_greeks, bs_price

_EXPIRY = datetime.date(2027, 3, 19)


def _quote(strike, bid, ask, iv=0.25, last=None):
    return OptionQuote(
        strike=strike, bid=bid, ask=ask, last=last, volume=10,
        open_interest=100, implied_vol=iv,
    )


def _chain(source="fake_leaf", calls=None, puts=None):
    return OptionChain(
        underlying="AAPL", expiry=_EXPIRY,
        calls=tuple(calls if calls is not None else [_quote(100.0, 4.8, 5.2)]),
        puts=tuple(puts if puts is not None else [_quote(100.0, 3.4, 3.6)]),
        source=source,
    )


class FakeProvider:
    """A leaf provider serving one canned chain, counting calls."""

    name = "fake_leaf"

    def __init__(self, chain=None, expiry_dates=None, quote_price=100.0,
                 quote_source="fake_leaf"):
        self._chain = chain
        self._expiries = expiry_dates
        self._quote = Quote(price=quote_price, source=quote_source)
        self.chain_calls = 0
        self.expiries_calls = 0

    def quote(self, ticker):
        return self._quote

    def get_price(self, ticker):
        return self._quote.price

    def history(self, ticker, period):
        return None

    def news(self, ticker, limit=5):
        return None

    def earnings(self, ticker):
        return None

    def expiries(self, underlying):
        self.expiries_calls += 1
        return self._expiries

    def option_chain(self, underlying, expiry):
        self.chain_calls += 1
        return self._chain


# ── Three-state fillability ──────────────────────────────────────────────


def test_classify_tradeable_within_the_spread_threshold():
    assert classify_option_quote(4.8, 5.2) == ("tradeable", "ok")


def test_classify_zero_bid_is_worthless_not_unusable():
    assert classify_option_quote(0.0, 0.05) == ("worthless", "zero_bid")


def test_classify_missing_and_degenerate_quotes_are_unusable():
    assert classify_option_quote(None, 5.0) == ("unusable", "no_quote")
    assert classify_option_quote(4.0, None) == ("unusable", "no_quote")
    assert classify_option_quote(4.0, 0.0) == ("unusable", "no_quote")
    assert classify_option_quote(-1.0, 5.0) == ("unusable", "no_quote")
    assert classify_option_quote(float("nan"), 5.0) == ("unusable", "no_quote")


def test_classify_crossed_market_is_unusable():
    assert classify_option_quote(5.2, 4.8) == ("unusable", "crossed")


def test_classify_wide_spread_is_blocked_with_the_reason_surfaced():
    # (1.0, 1.5): spread 0.5 / mid 1.25 = 40% > 25% — a liquidity failure.
    assert classify_option_quote(1.0, 1.5) == ("unusable", "wide_spread")


# ── Provider surface ─────────────────────────────────────────────────────


def test_mock_walk_serves_no_chain_by_ruling_d10():
    p = MockWalkProvider()
    assert p.expiries("AAPL") is None
    assert p.option_chain("AAPL", _EXPIRY) is None


def test_asof_store_serves_no_chain_there_is_no_history():
    p = AsOfStoreProvider(datetime.date(2026, 1, 5))
    assert p.expiries("AAPL") is None
    assert p.option_chain("AAPL", _EXPIRY) is None


def test_caching_provider_caches_the_chain_and_keeps_the_leaf_source():
    inner = FakeProvider(chain=_chain(), expiry_dates=[_EXPIRY])
    cached = CachingProvider(inner, ttl_seconds=60.0)
    first = cached.option_chain("AAPL", _EXPIRY)
    second = cached.option_chain("AAPL", _EXPIRY)
    assert inner.chain_calls == 1  # served from cache the second time
    assert first is second
    assert first.source == "fake_leaf"  # never "cache(fake_leaf)"
    assert cached.expiries("AAPL") == [_EXPIRY]
    assert cached.expiries("AAPL") == [_EXPIRY]
    assert inner.expiries_calls == 1


def test_caching_provider_invalidate_drops_the_chain_entries():
    inner = FakeProvider(chain=_chain(), expiry_dates=[_EXPIRY])
    cached = CachingProvider(inner, ttl_seconds=60.0)
    cached.option_chain("AAPL", _EXPIRY)
    cached.expiries("AAPL")
    cached.invalidate("AAPL")
    cached.option_chain("AAPL", _EXPIRY)
    cached.expiries("AAPL")
    assert inner.chain_calls == 2
    assert inner.expiries_calls == 2


def test_fallback_provider_forwards_the_leaf_chain():
    primary = FakeProvider(chain=None, expiry_dates=None)
    secondary = FakeProvider(chain=_chain(source="secondary_leaf"),
                             expiry_dates=[_EXPIRY])
    fb = FallbackProvider(primary=primary, secondary=secondary)
    chain = fb.option_chain("AAPL", _EXPIRY)
    assert chain is not None and chain.source == "secondary_leaf"
    assert fb.expiries("AAPL") == [_EXPIRY]


# ── Risk-free rate ───────────────────────────────────────────────────────


def test_risk_free_rate_reads_percent_and_names_its_source():
    set_market_data_provider(FakeProvider(quote_price=5.23, quote_source="yfinance"))
    rate = oc.get_risk_free_rate()
    assert rate is not None
    assert abs(rate.rate - 0.0523) < 1e-12
    assert rate.source == "yfinance"


def test_risk_free_rate_refuses_a_synthetic_quote():
    set_market_data_provider(FakeProvider(quote_price=5.23, quote_source="mock_walk"))
    assert oc.get_risk_free_rate() is None


def test_risk_free_rate_refuses_an_implausible_reading():
    set_market_data_provider(FakeProvider(quote_price=312.0, quote_source="yfinance"))
    assert oc.get_risk_free_rate() is None


# ── Enrichment: every figure traceable to trading_math ───────────────────


def _now():
    return datetime.datetime(2026, 9, 18, 14, 0, tzinfo=datetime.timezone.utc)


def test_enrich_uses_a_sane_provider_iv_and_the_greeks_are_bs_greeks():
    chain = _chain(calls=[_quote(100.0, 4.8, 5.2, iv=0.25)], puts=[])
    enriched = oc.enrich_chain(chain, spot=100.0, rate=0.05,
                               rate_source="yfinance", now=_now())
    row = enriched.calls[0]
    assert row.iv_used == 0.25 and row.iv_source == "provider"
    assert row.state == "tradeable"
    expected = bs_greeks("call", 100.0, 100.0, enriched.t_years, 0.05, 0.25, 0.0)
    assert row.greeks == expected
    assert row.greeks_reason is None


def test_enrich_solves_iv_from_the_mid_when_the_provider_iv_is_absurd():
    sigma_true = 0.32
    t = oc.year_fraction_to_expiry(_EXPIRY, _now())
    fair = bs_price("call", 100.0, 100.0, t, 0.05, sigma_true)
    chain = _chain(calls=[_quote(100.0, fair - 0.01, fair + 0.01, iv=87.0)], puts=[])
    enriched = oc.enrich_chain(chain, spot=100.0, rate=0.05, now=_now())
    row = enriched.calls[0]
    assert row.iv_source == "solved"
    assert abs(row.iv_used - sigma_true) < 1e-3
    assert row.greeks is not None


def test_enrich_without_a_rate_degrades_visibly_not_silently():
    enriched = oc.enrich_chain(_chain(), spot=100.0, rate=None, now=_now())
    for row in (*enriched.calls, *enriched.puts):
        assert row.greeks is None
        assert row.greeks_reason == "no_risk_free_rate"
        assert row.state == "tradeable"  # bid/ask still serve


def test_enrich_marks_an_expired_chain_expired():
    past = datetime.datetime(2027, 3, 20, 12, 0, tzinfo=datetime.timezone.utc)
    enriched = oc.enrich_chain(_chain(), spot=100.0, rate=0.05, now=past)
    assert enriched.t_years == 0.0
    assert enriched.calls[0].greeks_reason == "expired"


def test_enrich_unpriceable_strike_carries_an_explicit_reason():
    # Zero bid (worthless) and no sane IV: nothing to price from.
    chain = _chain(calls=[_quote(180.0, 0.0, 0.05, iv=None)], puts=[])
    enriched = oc.enrich_chain(chain, spot=100.0, rate=0.05, now=_now())
    row = enriched.calls[0]
    assert row.state == "worthless"
    assert row.greeks is None and row.greeks_reason == "no_usable_iv"


def test_get_enriched_chain_refuses_a_synthetic_spot():
    fake = FakeProvider(chain=_chain(), quote_price=100.0, quote_source="mock_walk")
    set_market_data_provider(fake)
    assert oc.get_enriched_chain("AAPL", _EXPIRY) is None


def test_get_enriched_chain_composes_chain_spot_and_rate():
    fake = FakeProvider(chain=_chain(), quote_price=100.0, quote_source="yfinance")
    set_market_data_provider(fake)
    enriched = oc.get_enriched_chain("AAPL", _EXPIRY)
    assert enriched is not None
    assert enriched.spot == 100.0 and enriched.spot_source == "yfinance"
    # The same fake also serves ^IRX (price 100 → 100% — implausible), so
    # the rate is refused and the chain still serves, greeks not_evaluated.
    assert enriched.rate is None
    assert enriched.calls[0].greeks_reason == "no_risk_free_rate"


def test_get_enriched_chain_none_when_the_provider_has_no_chain():
    set_market_data_provider(FakeProvider(chain=None))
    assert oc.get_enriched_chain("AAPL", _EXPIRY) is None
