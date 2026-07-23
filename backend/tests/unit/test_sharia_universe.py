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
