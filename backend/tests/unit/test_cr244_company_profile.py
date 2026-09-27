"""CR244 — company_profile.py (blend logic) and GET /v1/sim/company-profile/{ticker}.

No network anywhere in this file: `edgar_cik.resolve_cik`, the submissions
fetch, and `yfinance.Ticker` are all monkeypatched. Fixtures live under
`tests/fixtures/cr244/`.

Covers the merge logic, each degrade path (no CIK, yfinance down, EDGAR
down, unrecognised submissions shape, unknown-to-both → 404), the filings
3/4/5 exclusion + 20-item cap, and the route's response shape.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.sim import router as sim_router
from app.services import company_profile as cp

FIXTURES = Path(__file__).parent.parent / "fixtures" / "cr244"


def _load_submissions() -> dict:
    return json.loads((FIXTURES / "submissions_nvda.json").read_text())


class _FakeInfo(dict):
    pass


class _FakeFrame:
    """Minimal pandas-DataFrame-shaped stub: `.empty` and `.iterrows()`."""

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self.empty = not rows

    def iterrows(self):
        for i, row in enumerate(self._rows):
            yield i, row


class _FakeTicker:
    def __init__(self, info: dict | None, institutional=None, mutualfund=None) -> None:
        self.info = info or {}
        self.institutional_holders = institutional
        self.mutualfund_holders = mutualfund


@pytest.fixture(autouse=True)
def clear_caches():
    cp.clear_company_profile_cache()
    yield
    cp.clear_company_profile_cache()


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(sim_router)
    return TestClient(app, raise_server_exceptions=False)


_FULL_INFO = {
    "longName": "NVIDIA Corporation",
    "shortName": "NVIDIA",
    "longBusinessSummary": "NVIDIA designs GPUs.",
    "sector": "Technology",
    "industry": "Semiconductors",
    "fullTimeEmployees": 29600,
    "website": "https://www.nvidia.com",
    "phone": "408-486-2000",
    "exchange": "NMS",
    "address1": "2788 San Tomas Expressway",
    "city": "Santa Clara",
    "state": "CA",
    "zip": "95051",
    "currency": "USD",
    "marketCap": 4.3e12,
    "totalRevenue": 1.65e11,
    "grossMargins": 0.72,
    "operatingMargins": 0.61,
    "profitMargins": 0.53,
    "trailingPE": 52.1,
    "forwardPE": 31.0,
    "trailingEps": 3.4,
    "debtToEquity": 11.0,
    "freeCashflow": 7.2e10,
    "dividendYield": 0.0002,
    "sharesOutstanding": 2.44e10,
    "floatShares": 2.34e10,
    "heldPercentInstitutions": 0.674,
    "heldPercentInsiders": 0.042,
}


def _patch_yf(monkeypatch: pytest.MonkeyPatch, info: dict | None, institutional=None, mutualfund=None) -> None:
    import yfinance as yf

    def _ticker(symbol: str) -> _FakeTicker:
        return _FakeTicker(info, institutional, mutualfund)

    monkeypatch.setattr(yf, "Ticker", _ticker)


# ── Merge logic — live path ──────────────────────────────────────────────────


def test_full_blend_all_sections_live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cp, "resolve_cik", lambda t: 1045810)
    monkeypatch.setattr(cp, "_fetch_company_submissions", lambda cik: _load_submissions())
    _patch_yf(monkeypatch, _FULL_INFO, institutional=_FakeFrame([
        {"Holder": "The Vanguard Group, Inc.", "pctHeld": 0.0824, "Shares": 2.0e9, "Date Reported": "2026-06-30"},
    ]))

    result = cp.get_company_profile("NVDA")
    assert result is not None
    assert result.ticker == "NVDA"
    assert result.cik == "0001045810"

    assert result.overview.state == "live"
    assert result.overview.legal_name == "NVIDIA CORP"  # EDGAR wins
    assert result.overview.display_name == "NVIDIA Corporation"  # yfinance wins
    assert result.overview.sic == "3674"
    assert result.overview.sic_description == "Semiconductors & Related Devices"
    assert result.overview.exchange == "NASDAQ"
    assert result.overview.employees == 29600
    assert sorted(result.overview.sources) == ["edgar", "yfinance"]

    assert result.financials.state == "live"
    assert result.financials.market_cap == pytest.approx(4.3e12)
    assert result.financials.forward_pe == pytest.approx(31.0)

    assert result.filings.state == "live"
    assert result.filings.sources == ["edgar"]

    assert result.ownership.state == "live"
    assert result.ownership.shares_outstanding == pytest.approx(2.44e10)
    assert len(result.ownership.holders) == 1
    assert result.ownership.holders[0].name == "The Vanguard Group, Inc."
    assert result.ownership.holders[0].kind == "institution"


# ── Filings: 3/4/5 exclusion + 20 cap ────────────────────────────────────────


def test_filings_excludes_forms_3_4_5(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cp, "resolve_cik", lambda t: 1045810)
    monkeypatch.setattr(cp, "_fetch_company_submissions", lambda cik: _load_submissions())
    _patch_yf(monkeypatch, _FULL_INFO)

    result = cp.get_company_profile("NVDA")
    forms = {item.form for item in result.filings.items}
    assert forms == {"10-Q", "8-K", "DEF 14A", "10-K"}
    assert "4" not in forms and "3" not in forms


def test_filings_newest_first_and_capped_at_20(monkeypatch: pytest.MonkeyPatch) -> None:
    submissions = _load_submissions()
    n = 30
    submissions["filings"]["recent"] = {
        "form": ["10-K"] * n,
        "accessionNumber": [f"0000000000-26-{i:06d}" for i in range(n)],
        "filingDate": [f"2026-01-{(i % 28) + 1:02d}" for i in range(n)],
        "reportDate": [None] * n,
        "primaryDocument": [f"doc{i}.htm" for i in range(n)],
        "primaryDocDescription": [None] * n,
    }
    monkeypatch.setattr(cp, "resolve_cik", lambda t: 1045810)
    monkeypatch.setattr(cp, "_fetch_company_submissions", lambda cik: submissions)
    _patch_yf(monkeypatch, _FULL_INFO)

    result = cp.get_company_profile("NVDA")
    assert len(result.filings.items) == 20
    dates = [item.filed_date for item in result.filings.items]
    assert dates == sorted(dates, reverse=True)


def test_filings_form_label_map_and_unknown_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    submissions = _load_submissions()
    submissions["filings"]["recent"] = {
        "form": ["10-K", "XYZ-9"],
        "accessionNumber": ["0000000000-26-000001", "0000000000-26-000002"],
        "filingDate": ["2026-01-01", "2026-01-02"],
        "reportDate": [None, None],
        "primaryDocument": ["a.htm", "b.htm"],
        "primaryDocDescription": [None, "Custom filing type"],
    }
    monkeypatch.setattr(cp, "resolve_cik", lambda t: 1045810)
    monkeypatch.setattr(cp, "_fetch_company_submissions", lambda cik: submissions)
    _patch_yf(monkeypatch, _FULL_INFO)

    result = cp.get_company_profile("NVDA")
    by_form = {item.form: item.description for item in result.filings.items}
    assert by_form["10-K"] == "Annual report"
    assert by_form["XYZ-9"] == "Custom filing type"


# ── Degrade paths (CR040) ────────────────────────────────────────────────────


def test_no_cik_yields_partial_overview_and_not_available_filings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cp, "resolve_cik", lambda t: None)
    _patch_yf(monkeypatch, _FULL_INFO)

    result = cp.get_company_profile("FOO")
    assert result is not None
    assert result.cik is None
    assert result.overview.state == "partial"
    assert result.filings.state == "not_available"
    assert result.filings.reason == "No SEC registrant found for this symbol"
    assert result.financials.state == "live"  # yfinance unaffected


def test_yfinance_down_degrades_financials_and_ownership_not_filings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cp, "resolve_cik", lambda t: 1045810)
    monkeypatch.setattr(cp, "_fetch_company_submissions", lambda cik: _load_submissions())
    monkeypatch.setattr(cp, "_yf_profile_info", lambda ticker: None)

    result = cp.get_company_profile("NVDA")
    assert result is not None
    assert result.financials.state == "not_available"
    assert result.ownership.state == "not_available"
    assert result.overview.state == "partial"  # EDGAR still answered
    assert result.overview.legal_name == "NVIDIA CORP"
    assert result.filings.state == "live"  # untouched by yfinance outage


def test_edgar_submissions_failure_degrades_filings_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cp, "resolve_cik", lambda t: 1045810)
    monkeypatch.setattr(cp, "_fetch_company_submissions", lambda cik: None)
    _patch_yf(monkeypatch, _FULL_INFO)

    result = cp.get_company_profile("NVDA")
    assert result.filings.state == "not_available"
    assert result.filings.reason == "SEC EDGAR data unavailable for this symbol"
    assert result.financials.state == "live"  # yfinance still answered
    assert result.overview.state == "partial"


def test_unrecognised_submissions_shape_yields_not_available_filings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cp, "resolve_cik", lambda t: 1045810)
    monkeypatch.setattr(cp, "_fetch_company_submissions", lambda cik: {"filings": {"recent": {"form": []}}})
    _patch_yf(monkeypatch, _FULL_INFO)

    result = cp.get_company_profile("NVDA")
    assert result.filings.state == "not_available"


def test_holders_read_failure_degrades_ownership_to_partial_not_blank(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cp, "resolve_cik", lambda t: 1045810)
    monkeypatch.setattr(cp, "_fetch_company_submissions", lambda cik: _load_submissions())
    _patch_yf(monkeypatch, _FULL_INFO)

    def _broken_holders(ticker: str):
        return [], False

    monkeypatch.setattr(cp, "_yf_holders", _broken_holders)
    result = cp.get_company_profile("NVDA")
    assert result.ownership.state == "partial"
    assert result.ownership.shares_outstanding == pytest.approx(2.44e10)  # figures survive
    assert result.ownership.holders == []


def test_unknown_to_both_sources_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cp, "resolve_cik", lambda t: None)
    monkeypatch.setattr(cp, "_yf_profile_info", lambda ticker: None)

    assert cp.get_company_profile("ZZZZZZ") is None


# ── Cache ─────────────────────────────────────────────────────────────────


def test_result_is_cached_across_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def _fetch(cik):
        calls["n"] += 1
        return _load_submissions()

    monkeypatch.setattr(cp, "resolve_cik", lambda t: 1045810)
    monkeypatch.setattr(cp, "_fetch_company_submissions", _fetch)
    _patch_yf(monkeypatch, _FULL_INFO)

    cp.get_company_profile("NVDA")
    cp.get_company_profile("NVDA")
    assert calls["n"] == 1


# ── Route shape ───────────────────────────────────────────────────────────


def test_route_returns_full_shape(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cp, "resolve_cik", lambda t: 1045810)
    monkeypatch.setattr(cp, "_fetch_company_submissions", lambda cik: _load_submissions())
    _patch_yf(monkeypatch, _FULL_INFO)

    r = client.get("/v1/sim/company-profile/NVDA")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ticker"] == "NVDA"
    assert body["cik"] == "0001045810"
    assert set(body.keys()) == {"ticker", "as_of", "cik", "overview", "financials", "filings", "ownership"}
    for section in ("overview", "financials", "filings", "ownership"):
        assert "state" in body[section]
        assert "reason" in body[section]
        assert "sources" in body[section]


def test_route_is_public_no_auth_required(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cp, "resolve_cik", lambda t: None)
    _patch_yf(monkeypatch, _FULL_INFO)
    r = client.get("/v1/sim/company-profile/NVDA")
    assert r.status_code == 200


def test_route_404_for_ticker_unknown_to_both(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cp, "resolve_cik", lambda t: None)
    monkeypatch.setattr(cp, "_yf_profile_info", lambda ticker: None)
    r = client.get("/v1/sim/company-profile/ZZZZZZ")
    assert r.status_code == 404


def test_route_ticker_normalized(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cp, "resolve_cik", lambda t: 1045810)
    monkeypatch.setattr(cp, "_fetch_company_submissions", lambda cik: _load_submissions())
    _patch_yf(monkeypatch, _FULL_INFO)
    r = client.get("/v1/sim/company-profile/nvda")
    assert r.status_code == 200
    assert r.json()["ticker"] == "NVDA"
