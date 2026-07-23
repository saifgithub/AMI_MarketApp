"""CR069-DIVERGE — HLAL/FTSE Shariah divergence monitor.

Fixture-based, no network. Beyond the parser/fetcher-reuse coverage, the tests
that matter most here assert the hard boundaries from the assign lane: the
monitor is never wired into `safety_floor.py`/the verdict path, an unreachable
second source degrades to "no observation" rather than pausing the halal flag,
and only PASS/SCREENED_OUT AAOIFI verdicts are compared (UNKNOWN/UNAVAILABLE
carry no AAOIFI opinion to diverge from).
"""

from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

import httpx
import pytest

from app.schemas.sharia import ShariaStatus, ShariaVerdict
from app.services.sharia_universe import HalalUniverse
from app.services import sharia_divergence as diverge
from app.services.sharia_divergence import (
    HlalDivergenceProvider,
    HlalObservation,
    fetch_hlal_universe,
    log_divergence,
    log_divergences,
)

_FIX = Path(__file__).parent / "fixtures"
_HLAL = (_FIX / "hlal_holdings_sample.csv").read_text()


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
    def __init__(self, routes: dict[str, tuple[int, str]]) -> None:
        self._routes = routes

    def get(self, url: str) -> _FakeResponse:
        status, body = self._routes[url]
        return _FakeResponse(status, body, url)


def _verdict(status: ShariaStatus, ticker: str = "AAPL", as_of=date(2026, 7, 22)) -> ShariaVerdict:
    return ShariaVerdict(status=status, ticker=ticker, standard="AAOIFI", source="SPUS", as_of=as_of)


# ── fetcher reuse (same Tidal schema as SPUS) ────────────────────────────────


def test_fetch_hlal_universe_parses_tickers():
    client = _FakeClient({"u": (200, _HLAL)})
    tickers, as_of = fetch_hlal_universe(client, "u")
    assert len(tickers) == 160
    assert as_of == date(2026, 7, 22)
    assert "HAA" in tickers
    assert "003654100CVR" not in tickers


def test_fetch_hlal_universe_truncated_raises():
    truncated = "\n".join(_HLAL.splitlines()[:30]) + "\n"  # < 150-row floor
    client = _FakeClient({"u": (200, truncated)})
    with pytest.raises(diverge.ShariaSourceError):
        fetch_hlal_universe(client, "u")


def test_fetch_hlal_universe_http_error_raises():
    client = _FakeClient({"u": (500, "")})
    with pytest.raises(httpx.HTTPStatusError):
        fetch_hlal_universe(client, "u")


# ── provider: never raises past its own boundary (hard boundary 3) ──────────


def test_provider_ok_caches():
    calls = {"n": 0}

    def fetcher():
        calls["n"] += 1
        return frozenset({"AAA", "AAB"}), date(2026, 7, 22)

    p = HlalDivergenceProvider(url="u", fetcher=fetcher)
    obs1 = p.get()
    obs2 = p.get()
    assert obs1.available and obs1.compliant == {"AAA", "AAB"}
    assert obs2 is obs1  # cached, not refetched
    assert calls["n"] == 1


def test_provider_fetch_failure_yields_unavailable_not_an_exception():
    def boom():
        raise diverge.ShariaSourceError("truncated")

    p = HlalDivergenceProvider(url="u", fetcher=boom)
    obs = p.get()  # must not raise — a monitor outage is not the caller's problem
    assert obs.available is False
    assert obs.compliant == frozenset()


def test_provider_http_error_yields_unavailable_not_an_exception():
    def boom():
        raise httpx.ConnectError("refused")

    p = HlalDivergenceProvider(url="u", fetcher=boom)
    obs = p.get()
    assert obs.available is False


# ── divergence comparison ────────────────────────────────────────────────────


def test_divergence_logged_when_aaoifi_pass_but_ftse_excludes():
    hlal = HlalObservation(compliant=frozenset({"MSFT"}), as_of=date(2026, 7, 22), available=True)
    record = log_divergence("AAPL", _verdict(ShariaStatus.PASS, "AAPL"), hlal)
    assert record is not None
    assert record.ticker == "AAPL"
    assert record.aaoifi_status is ShariaStatus.PASS
    assert record.ftse_compliant is False


def test_divergence_logged_when_aaoifi_screens_out_but_ftse_includes():
    hlal = HlalObservation(compliant=frozenset({"META"}), as_of=date(2026, 7, 22), available=True)
    record = log_divergence("META", _verdict(ShariaStatus.SCREENED_OUT, "META"), hlal)
    assert record is not None
    assert record.ftse_compliant is True


def test_no_divergence_when_both_agree_compliant():
    hlal = HlalObservation(compliant=frozenset({"AAPL"}), as_of=date(2026, 7, 22), available=True)
    assert log_divergence("AAPL", _verdict(ShariaStatus.PASS, "AAPL"), hlal) is None


def test_no_divergence_when_both_agree_excluded():
    hlal = HlalObservation(compliant=frozenset(), as_of=date(2026, 7, 22), available=True)
    assert log_divergence("JPM", _verdict(ShariaStatus.SCREENED_OUT, "JPM"), hlal) is None


@pytest.mark.parametrize("status", [ShariaStatus.UNKNOWN, ShariaStatus.UNAVAILABLE])
def test_no_comparison_when_aaoifi_has_no_concrete_opinion(status):
    """UNKNOWN/UNAVAILABLE carry no AAOIFI ruling to diverge from — comparing
    against them would fabricate a disagreement the AAOIFI screen never made."""
    hlal = HlalObservation(compliant=frozenset({"ASML"}), as_of=date(2026, 7, 22), available=True)
    assert log_divergence("ASML", _verdict(status, "ASML"), hlal) is None


def test_unreachable_second_source_yields_no_observation_not_a_pause():
    """Hard boundary 3: HLAL unreachable must degrade to 'nothing logged,' never
    touch the AAOIFI-sourced halal flag's own pause state."""
    hlal = HlalObservation(compliant=frozenset(), as_of=None, available=False)
    assert log_divergence("AAPL", _verdict(ShariaStatus.PASS, "AAPL"), hlal) is None
    assert log_divergence("META", _verdict(ShariaStatus.SCREENED_OUT, "META"), hlal) is None


def test_log_divergences_batch_resolves_against_aaoifi_universe():
    aaoifi = HalalUniverse(
        {"AAPL"}, parent_index={"AAPL", "META", "JPM"}, as_of=date(2026, 7, 22)
    )
    hlal = HlalObservation(
        compliant=frozenset({"AAPL", "META"}), as_of=date(2026, 7, 22), available=True
    )
    records = log_divergences(["AAPL", "META", "JPM", "ASML"], aaoifi, hlal)
    # AAPL: both compliant -> no divergence.
    # META: AAOIFI screened_out (parent, not compliant), HLAL compliant -> divergence.
    # JPM: AAOIFI screened_out, HLAL not compliant -> agree, no divergence.
    # ASML: AAOIFI unknown (not in parent) -> no concrete opinion, skipped.
    assert [r.ticker for r in records] == ["META"]


# ── hard boundary 1: never wired into enforcement ────────────────────────────


def test_module_not_imported_by_safety_floor():
    """A mistake here is a redeploy away from fixed (per the assign lane's GATE
    note) precisely because nothing enforcement-side imports this module. Parse
    safety_floor.py's imports rather than grep, so a reformat can't hide it."""
    safety_floor = Path(__file__).resolve().parents[2] / "app" / "agents" / "safety_floor.py"
    tree = ast.parse(safety_floor.read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not any("sharia_divergence" in name for name in imported), (
        "safety_floor.py must never import sharia_divergence — the HLAL/FTSE "
        "second source must not reach the verdict path (CR069-DIVERGE boundary 1)"
    )


def test_halal_universe_resolve_is_read_only_from_divergence_module():
    """`log_divergences` must only call `HalalUniverse.resolve()` (a pure
    lookup) — never mutate or replace the AAOIFI universe it's handed. Since
    `HalalUniverse` is an immutable frozenset subclass, the strongest check is
    that the same object survives identical before/after, which frozenset
    already guarantees; this asserts the type contract that makes it true."""
    aaoifi = HalalUniverse({"AAPL"}, parent_index={"AAPL"}, as_of=date(2026, 7, 22))
    hlal = HlalObservation(compliant=frozenset({"AAPL"}), as_of=date(2026, 7, 22), available=True)
    before = frozenset(aaoifi)
    log_divergences(["AAPL"], aaoifi, hlal)
    assert frozenset(aaoifi) == before
    assert isinstance(aaoifi, frozenset)  # immutable by construction


def test_divergence_record_has_no_verdict_or_response_type():
    """The record type carries plain log fields only — no `ShariaVerdict`, no
    field that a response schema could pick up and re-emit by accident."""
    from app.services.sharia_divergence import DivergenceRecord

    fields = set(DivergenceRecord.__dataclass_fields__)
    assert fields == {"ticker", "aaoifi_status", "aaoifi_as_of", "ftse_compliant", "ftse_as_of"}
