"""CR244 audit B3/M4 — edgar_cik.py: stale-map fallback on a refresh
failure, the negative-cache backoff, and the shared `paced_get` helper.

No network: `httpx.Client` is monkeypatched via a fake context-manager
stand-in (same pattern `test_cr244_insider.py` uses), never the real
`httpx.Client.get`.
"""

from __future__ import annotations

import httpx
import pytest

from app.services import edgar_cik as ec


class _FakeResponse:
    def __init__(self, status_code: int, json_body=None) -> None:
        self.status_code = status_code
        self._json = json_body

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)

    def json(self):
        return self._json


class _FakeClient:
    def __init__(self, *args, **kwargs) -> None:
        self._get = kwargs.pop("_get", None)

    def __enter__(self) -> "_FakeClient":
        return self

    def __exit__(self, *args) -> None:
        return None

    def get(self, url, *args, **kwargs):
        return self._get(url)


_MAP_PAYLOAD = {
    "0": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA CORP"},
    "1": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
}


@pytest.fixture(autouse=True)
def clear_cache():
    ec.clear_cik_cache()
    yield
    ec.clear_cik_cache()


def _patch_client(monkeypatch: pytest.MonkeyPatch, responses: list) -> list:
    """`paced_get` retries once on a 429/5xx, so a single failing response in
    `responses` must still answer a second call within the same
    `paced_get` invocation — only pop when more than one response remains."""
    calls: list[str] = []

    def _get(url):
        calls.append(url)
        return responses.pop(0) if len(responses) > 1 else responses[0]

    monkeypatch.setattr(ec.httpx, "Client", lambda *a, **k: _FakeClient(_get=_get))
    return calls


# ── Happy path ───────────────────────────────────────────────────────────


def test_resolve_cik_returns_int_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(monkeypatch, [_FakeResponse(200, json_body=_MAP_PAYLOAD)])
    assert ec.resolve_cik("NVDA") == 1045810
    assert ec.resolve_cik("nvda") == 1045810  # case-insensitive


def test_resolve_cik_none_for_symbol_not_in_map(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(monkeypatch, [_FakeResponse(200, json_body=_MAP_PAYLOAD)])
    assert ec.resolve_cik("RY.TO") is None


# ── B3: stale-serve + negative-cache backoff ────────────────────────────────


def test_refresh_failure_serves_stale_map_when_one_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ec.time, "sleep", lambda s: None)
    _patch_client(monkeypatch, [_FakeResponse(200, json_body=_MAP_PAYLOAD)])
    assert ec.resolve_cik("NVDA") == 1045810

    ec._cached_at = 0.0  # force TTL expiry without waiting 24h
    _patch_client(monkeypatch, [_FakeResponse(500)])
    # A failed refresh must serve the STALE map, not raise or return None.
    assert ec.resolve_cik("NVDA") == 1045810


def test_cold_failure_with_no_stale_map_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ec.time, "sleep", lambda s: None)
    _patch_client(monkeypatch, [_FakeResponse(500)])
    with pytest.raises(ec.CikResolutionUnavailable):
        ec.resolve_cik("NVDA")


def test_negative_cache_backoff_prevents_refetch_storm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ec.time, "sleep", lambda s: None)
    calls = _patch_client(monkeypatch, [_FakeResponse(500)])
    with pytest.raises(ec.CikResolutionUnavailable):
        ec.resolve_cik("NVDA")
    first_call_count = len(calls)  # paced_get's own one-retry already fired

    # A second resolve_cik call inside the backoff window must NOT re-fetch
    # the ~1MB map at all — no new HTTP calls beyond the first attempt's.
    with pytest.raises(ec.CikResolutionUnavailable):
        ec.resolve_cik("NVDA")
    assert len(calls) == first_call_count


def test_negative_cache_backoff_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ec.time, "sleep", lambda s: None)
    calls = _patch_client(monkeypatch, [_FakeResponse(500)])
    with pytest.raises(ec.CikResolutionUnavailable):
        ec.resolve_cik("NVDA")
    assert calls  # paced_get's own retry already fired at least once

    ec._last_failed_at = 0.0  # force backoff expiry without waiting 60s
    responses = [_FakeResponse(200, json_body=_MAP_PAYLOAD)]
    monkeypatch.setattr(ec.httpx, "Client", lambda *a, **k: _FakeClient(_get=lambda url: responses.pop(0)))
    assert ec.resolve_cik("NVDA") == 1045810


# ── M4: paced_get ────────────────────────────────────────────────────────


def test_paced_get_retries_once_on_429(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ec.time, "sleep", lambda s: None)
    responses = [_FakeResponse(429), _FakeResponse(200, json_body={"ok": True})]
    client = _FakeClient(_get=lambda url: responses.pop(0))
    r = ec.paced_get(client, "https://example.com/x")
    assert r.status_code == 200


def test_paced_get_does_not_retry_404(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ec.time, "sleep", lambda s: None)
    calls = {"n": 0}

    def _get(url):
        calls["n"] += 1
        return _FakeResponse(404)

    client = _FakeClient(_get=_get)
    r = ec.paced_get(client, "https://example.com/x")
    assert r.status_code == 404
    assert calls["n"] == 1
