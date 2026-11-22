"""CR229 — BLS direct fetcher for the H1 macro prints (CPI, PPI).

Fixtures are hand-built to the response shape BLS documents
(https://www.bls.gov/developers/api_signature.htm); no live call was made. The
REQUEST_NOT_PROCESSED message text is illustrative: BLS does not document it.
Tests cover our logic: parsing, labelling, gaps, and that every failure is loud and
never falls back to another source.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from app.core.config import settings
from app.services import macro_bls
from app.services.macro_bls import MacroSourceUnavailable, fetch_h1_series, fetch_series

_FIX = Path(__file__).parent / "fixtures"
_TODAY = date(2026, 11, 22)


def _load(name: str) -> dict:
    return json.loads((_FIX / name).read_text())


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _by_series_id(request: httpx.Request) -> httpx.Response:
    sid = request.url.path.rsplit("/", 1)[-1]
    name = {"CUSR0000SA0": "bls_v1_cusr0000sa0.json", "WPU00000000": "bls_v1_wpu00000000.json"}[sid]
    return httpx.Response(200, json=_load(name))


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    macro_bls.clear_cache()
    monkeypatch.setattr(settings, "macro_direct_bls_enabled", True)
    monkeypatch.setattr(settings, "bls_api_key", "")
    yield
    macro_bls.clear_cache()


def test_flag_off_by_default_in_settings():
    from app.core.config import Settings

    assert Settings.model_fields["macro_direct_bls_enabled"].default is False
    assert Settings.model_fields["bls_api_key"].default == ""


def test_flag_off_raises_loudly_and_makes_no_request(monkeypatch):
    monkeypatch.setattr(settings, "macro_direct_bls_enabled", False)
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={})

    with pytest.raises(MacroSourceUnavailable, match="MACRO_DIRECT_BLS_ENABLED is false"):
        fetch_series("CPI_ALL_ITEMS_SA", client=_client(handler), today=_TODAY)
    assert calls == []


def test_cpi_parses_ascending_monthly_with_source_labels_and_gap():
    s = fetch_series("CPI_ALL_ITEMS_SA", client=_client(_by_series_id), today=_TODAY)
    assert [o.period for o in s.observations] == ["2025-09", "2026-07", "2026-08", "2026-09"]
    assert s.latest.value == 333.1
    assert s.gaps == ("2025-10",)  # "-" is a published gap, not a zero
    assert "2025-13" not in [o.period for o in s.observations]  # M13 annual average dropped
    assert s.source == "BLS" and s.source_series_id == "CUSR0000SA0"
    assert "U.S. Bureau of Labor Statistics" in s.source_label and "v1" in s.source_label
    assert "cannot vouch" in s.disclaimer
    assert s.retrieved_on == "2026-11-22"


def test_ppi_parses():
    s = fetch_series("PPI_ALL_COMMODITIES", client=_client(_by_series_id), today=_TODAY)
    assert s.source_series_id == "WPU00000000"
    assert s.latest.period == "2026-09" and s.latest.value == 288.4
    assert s.gaps == ()


def test_v1_is_keyless_get():
    seen = []

    def handler(request):
        seen.append(request)
        return _by_series_id(request)

    fetch_series("CPI_ALL_ITEMS_SA", client=_client(handler), today=_TODAY)
    assert seen[0].method == "GET"
    assert str(seen[0].url) == "https://api.bls.gov/publicAPI/v1/timeseries/data/CUSR0000SA0"


def test_keyed_uses_v2_post_with_key_in_body_only(monkeypatch):
    monkeypatch.setattr(settings, "bls_api_key", "SECRETKEY123")
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=_load("bls_v1_cusr0000sa0.json"))

    s = fetch_series("CPI_ALL_ITEMS_SA", client=_client(handler), today=_TODAY)
    req = seen[0]
    assert req.method == "POST" and "/v2/" in str(req.url)
    assert "SECRETKEY123" not in str(req.url)
    body = json.loads(req.content)
    assert body["registrationkey"] == "SECRETKEY123"
    assert (body["startyear"], body["endyear"]) == ("2024", "2026")
    assert "v2" in s.source_label


def test_cache_serves_second_call_without_a_request():
    n = {"calls": 0}

    def handler(request):
        n["calls"] += 1
        return _by_series_id(request)

    c = _client(handler)
    fetch_series("CPI_ALL_ITEMS_SA", client=c, today=_TODAY)
    fetch_series("CPI_ALL_ITEMS_SA", client=c, today=_TODAY)
    assert n["calls"] == 1


def test_quota_exceeded_status_is_loud_with_bls_message():
    def handler(request):
        return httpx.Response(200, json=_load("bls_not_processed.json"))

    with pytest.raises(MacroSourceUnavailable) as e:
        fetch_series("CPI_ALL_ITEMS_SA", client=_client(handler), today=_TODAY)
    assert e.value.source == "BLS" and "REQUEST_NOT_PROCESSED" in e.value.reason
    assert "daily threshold" in e.value.reason


def test_http_error_is_loud_and_negative_cached():
    n = {"calls": 0}

    def handler(request):
        n["calls"] += 1
        return httpx.Response(503)

    c = _client(handler)
    with pytest.raises(MacroSourceUnavailable, match="HTTP 503"):
        fetch_series("CPI_ALL_ITEMS_SA", client=c, today=_TODAY)
    with pytest.raises(MacroSourceUnavailable, match="retry backoff"):
        fetch_series("CPI_ALL_ITEMS_SA", client=c, today=_TODAY)
    assert n["calls"] == 1  # the burst did not spend a second query of v1's 25/day


def test_transport_error_is_loud():
    def handler(request):
        raise httpx.ConnectTimeout("boom", request=request)

    with pytest.raises(MacroSourceUnavailable, match="ConnectTimeout"):
        fetch_series("CPI_ALL_ITEMS_SA", client=_client(handler), today=_TODAY)


def test_non_json_body_is_loud():
    def handler(request):
        return httpx.Response(200, text="<html>maintenance</html>")

    with pytest.raises(MacroSourceUnavailable):
        fetch_series("CPI_ALL_ITEMS_SA", client=_client(handler), today=_TODAY)


def test_wrong_series_in_response_is_rejected():
    def handler(request):
        return httpx.Response(200, json=_load("bls_v1_wpu00000000.json"))

    with pytest.raises(MacroSourceUnavailable, match="did not include series CUSR0000SA0"):
        fetch_series("CPI_ALL_ITEMS_SA", client=_client(handler), today=_TODAY)


def test_only_gaps_is_absent_not_an_empty_series():
    payload = {
        "status": "REQUEST_SUCCEEDED",
        "message": [],
        "Results": {"series": [{"seriesID": "CUSR0000SA0", "data": [{"year": "2025", "period": "M10", "value": "-"}]}]},
    }
    with pytest.raises(MacroSourceUnavailable, match="no monthly observations"):
        fetch_series("CPI_ALL_ITEMS_SA", client=_client(lambda r: httpx.Response(200, json=payload)), today=_TODAY)


def test_unknown_series_key_is_loud():
    with pytest.raises(MacroSourceUnavailable, match="unknown series key"):
        fetch_series("TTLCONS")


def test_h1_is_all_or_raise_no_half_print():
    def handler(request):
        if request.url.path.endswith("WPU00000000"):
            return httpx.Response(500)
        return _by_series_id(request)

    with pytest.raises(MacroSourceUnavailable) as e:
        fetch_h1_series(client=_client(handler), today=_TODAY)
    assert e.value.series_key == "PPI_ALL_COMMODITIES"


def test_h1_returns_both_series():
    out = fetch_h1_series(client=_client(_by_series_id), today=_TODAY)
    assert set(out) == {"CPI_ALL_ITEMS_SA", "PPI_ALL_COMMODITIES"}
