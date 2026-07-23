"""CR069 Phase 1 — sourced Sharia universe: fetcher, parser, cache, resolver.

Never touches the network: the provider's fetcher is injectable and the fetch
functions run against checked-in CSV fixtures (a SPUS-shaped holdings file and an
iShares-shaped parent-index file). Covers the acceptance items: 219 tickers parsed,
junk rows dropped, as-of extracted; a truncated body and a 500 both RAISE; three-state
resolution; loud degrade on disable/stale.
"""

from datetime import date
from pathlib import Path

import httpx
import pytest

from app.schemas.sharia import ShariaStatus
from app.services.sharia_universe import (
    HalalUniverse,
    ShariaSourceError,
    ShariaUniverseProvider,
    fetch_compliant_universe,
    fetch_parent_index,
    parse_holdings_csv,
)

_FIX = Path(__file__).parent / "fixtures"
_SPUS = (_FIX / "spus_holdings_sample.csv").read_text()
_PARENT = (_FIX / "parent_index_sample.csv").read_text()


class _FakeResponse:
    def __init__(self, status_code: int, text: str, url: str) -> None:
        self.status_code = status_code
        self.text = text
        self._url = url

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"{self.status_code}",
                request=httpx.Request("GET", self._url),
                response=httpx.Response(self.status_code),
            )


class _FakeClient:
    """Maps url → (status, body). No network."""

    def __init__(self, routes: dict[str, tuple[int, str]]) -> None:
        self._routes = routes

    def get(self, url: str) -> _FakeResponse:
        status, body = self._routes[url]
        return _FakeResponse(status, body, url)


# ── parser ──────────────────────────────────────────────────────────────────


def test_parse_spus_extracts_tickers_and_as_of():
    tickers, as_of = parse_holdings_csv(_SPUS)
    assert len(tickers) == 219
    assert as_of == date(2026, 7, 22)
    # share-class dot survives; digit-carrying non-equity rows are dropped.
    assert "BRK.B" in tickers
    assert "003654100CVR" not in tickers
    assert "2602335D" not in tickers


def test_parse_parent_index_skips_preamble_and_footer():
    tickers, _ = parse_holdings_csv(_PARENT)
    assert len(tickers) == 420  # 420 members, preamble + footer disclaimer dropped


# ── fetchers assert plausible-row floors ─────────────────────────────────────


def test_fetch_compliant_universe_ok():
    client = _FakeClient({"u": (200, _SPUS)})
    tickers, as_of = fetch_compliant_universe(client, "u")
    assert len(tickers) == 219 and as_of == date(2026, 7, 22)


def test_fetch_parent_index_ok():
    client = _FakeClient({"u": (200, _PARENT)})
    assert len(fetch_parent_index(client, "u")) == 420


def test_truncated_body_raises_not_short_universe():
    truncated = "\n".join(_SPUS.splitlines()[:30]) + "\n"  # ~29 tickers < floor 150
    client = _FakeClient({"u": (200, truncated)})
    with pytest.raises(ShariaSourceError):
        fetch_compliant_universe(client, "u")


def test_http_500_raises():
    client = _FakeClient({"u": (500, "")})
    with pytest.raises(httpx.HTTPStatusError):
        fetch_compliant_universe(client, "u")


# ── resolver (three states + loud degrade) ───────────────────────────────────


def test_resolver_three_states():
    u = HalalUniverse(
        {"AAA", "AAB"}, parent_index={"AAA", "AAB", "ZZZ"}, as_of=date(2026, 7, 22)
    )
    assert u.resolve("AAA").status is ShariaStatus.PASS
    assert u.resolve("ZZZ").status is ShariaStatus.SCREENED_OUT
    assert u.resolve("NEVR").status is ShariaStatus.UNKNOWN


def test_stale_universe_resolves_unavailable():
    u = HalalUniverse({"AAA"}, parent_index={"AAA"}, as_of=date(2026, 1, 1), stale=True)
    v = u.resolve("AAA")
    assert v.status is ShariaStatus.UNAVAILABLE
    assert "paused" in v.message().lower()


# ── provider (cache + loud degrade) ──────────────────────────────────────────


def _fetcher_ok():
    return (frozenset(parse_holdings_csv(_SPUS)[0]), date(2026, 7, 22),
            frozenset(parse_holdings_csv(_PARENT)[0]))


def test_provider_disabled_pauses_without_network():
    p = ShariaUniverseProvider(
        compliant_url="x", parent_url="y", staleness_days=7, enabled=False,
        fetcher=lambda: (_ for _ in ()).throw(AssertionError("must not fetch when disabled")),
    )
    u = p.get(now=date(2026, 7, 23))
    assert u.stale and u.resolve("AAA").status is ShariaStatus.UNAVAILABLE


def test_provider_enabled_loads_and_caches():
    p = ShariaUniverseProvider(
        compliant_url="x", parent_url="y", staleness_days=7, enabled=True,
        fetcher=_fetcher_ok,
    )
    u = p.get(now=date(2026, 7, 23))
    assert not u.stale
    assert u.resolve("AAA").status is ShariaStatus.PASS
    assert u.as_of == date(2026, 7, 22)


def test_provider_stale_as_of_pauses():
    p = ShariaUniverseProvider(
        compliant_url="x", parent_url="y", staleness_days=7, enabled=True,
        fetcher=lambda: (frozenset({"AAA"}), date(2026, 1, 1), frozenset({"AAA"})),
    )
    u = p.get(now=date(2026, 7, 23))  # as-of 200+ days old > 7-day window
    assert u.stale and u.resolve("AAA").status is ShariaStatus.UNAVAILABLE


def test_provider_fetch_error_pauses_loudly():
    def boom():
        raise ShariaSourceError("truncated")

    p = ShariaUniverseProvider(
        compliant_url="x", parent_url="y", staleness_days=7, enabled=True, fetcher=boom,
    )
    u = p.get(now=date(2026, 7, 23))
    assert u.stale  # degrade loudly — never a silent fall back to a placeholder set


# ── round 2: DEF089 parent source, F2 cache lifecycle, F3 async accessor ─────

_CONSTITUENTS = (_FIX / "parent_constituents_sample.csv").read_text()


def test_parse_constituent_list_shape():
    """DEF089's replacement source: `Symbol` header, no preamble, dotted share
    classes. The iShares endpoint it replaced served an HTML interstitial to a
    plain client, so this shape is what actually ships."""
    tickers, as_of = parse_holdings_csv(_CONSTITUENTS)
    assert len(tickers) > 490
    assert {"AAPL", "MSFT", "META", "JPM", "BRK.B"} <= tickers
    assert as_of is None


def test_constituent_date_added_is_not_mistaken_for_as_of():
    """`Date added` holds each name's index-admission date (1957 for MMM). If the
    date-column match were a prefix/substring match it would land there and every
    fetch would look decades stale."""
    _, as_of = parse_holdings_csv(_CONSTITUENTS)
    assert as_of is None


def test_fetch_parent_index_accepts_constituent_list():
    client = _FakeClient({"u": (200, _CONSTITUENTS)})
    assert len(fetch_parent_index(client, "u")) > 490


def _counting_fetcher(as_of: date):
    calls = {"n": 0}

    def fetch():
        calls["n"] += 1
        return frozenset({"AAA"}), as_of, frozenset({"AAA", "ZZZ"})

    return fetch, calls


def test_f2_staleness_is_rechecked_after_the_cache_is_warm():
    """F2. The first cut evaluated staleness only inside `_build()`, which only ran
    when the cache was empty — so a container that booted with fresh data served it
    forever. Same warm provider, later `now`, no refetch: must pause."""
    fetch, calls = _counting_fetcher(date(2026, 7, 22))
    p = ShariaUniverseProvider(
        compliant_url="x", parent_url="y", staleness_days=7, enabled=True,
        fetcher=fetch, refetch_interval_s=10_000,
    )
    fresh = p.get(now=date(2026, 7, 23))
    assert not fresh.stale
    assert fresh.resolve("AAA").status is ShariaStatus.PASS

    stale = p.get(now=date(2026, 8, 30))  # 39 days past a 7-day window
    assert stale.stale
    assert stale.resolve("AAA").status is ShariaStatus.UNAVAILABLE
    assert stale.resolve("ZZZ").status is ShariaStatus.UNAVAILABLE
    assert calls["n"] == 1, "staleness must be re-derived, not re-fetched"


def test_f2_refetch_is_throttled_while_the_source_is_down():
    """Staleness is re-derived per call, but the network retry is not: a dead
    source must not be hammered once per trade while the flag is paused."""
    calls = {"n": 0}

    def boom():
        calls["n"] += 1
        raise ShariaSourceError("truncated")

    p = ShariaUniverseProvider(
        compliant_url="x", parent_url="y", staleness_days=7, enabled=True,
        fetcher=boom, refetch_interval_s=10_000,
    )
    for _ in range(5):
        assert p.get(now=date(2026, 7, 23)).stale
    assert calls["n"] == 1


def test_f2_refetch_fires_once_the_interval_elapses():
    fetch, calls = _counting_fetcher(date(2026, 7, 22))
    p = ShariaUniverseProvider(
        compliant_url="x", parent_url="y", staleness_days=7, enabled=True,
        fetcher=fetch, refetch_interval_s=0,
    )
    p.get(now=date(2026, 7, 23))
    p.get(now=date(2026, 7, 23))
    assert calls["n"] == 2


def test_f3_async_accessor_does_not_block_the_event_loop():
    """F3. `_default_fetcher` is a synchronous httpx client doing two round-trips at
    up to 15s each; the API runs one uvicorn worker, so calling it straight from an
    `async def` handler stalls every concurrent request. The accessor must hand the
    blocking work to a thread — asserted by keeping the loop responsive while a
    deliberately slow fetch is in flight."""
    import asyncio
    import time as _time

    from app.services import sharia_universe as su

    def slow_fetch():
        _time.sleep(0.3)
        return frozenset({"AAA"}), date(2026, 7, 22), frozenset({"AAA", "ZZZ"})

    provider = ShariaUniverseProvider(
        compliant_url="x", parent_url="y", staleness_days=7, enabled=True,
        fetcher=slow_fetch,
    )
    su.reset_sharia_universe_provider(provider)
    try:
        async def scenario():
            ticks = 0

            async def ticker():
                nonlocal ticks
                while True:
                    await asyncio.sleep(0.01)
                    ticks += 1

            t = asyncio.create_task(ticker())
            u = await su.default_halal_universe_async()
            t.cancel()
            return u, ticks

        universe, ticks = asyncio.run(scenario())
        assert universe.resolve("AAA").status is ShariaStatus.PASS
        # A blocking call on the loop would have frozen the ticker at ~0.
        assert ticks > 5, f"event loop was blocked during the fetch (ticks={ticks})"
    finally:
        su.reset_sharia_universe_provider(None)
