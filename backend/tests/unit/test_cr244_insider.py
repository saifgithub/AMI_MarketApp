"""CR244 — edgar_ownership.py (Form 3/4/5 parsing) and GET /v1/sim/insider/{ticker}.

No network anywhere in this file: `resolve_cik`, the submissions fetch, and
each filing's XML fetch are monkeypatched via a fake `httpx.Client` stand-in
(never the real `httpx.Client.get`, which starlette's own `TestClient`
subclasses). Fixtures
live under `tests/fixtures/cr244/`.

The load-bearing coverage is `plan_type` (CR244's structural control, CR038):
all three outcomes, read ONLY from the Form 4/5 XML's `aff10b5One` element,
never inferred from footnote text. Also covers the P/S-only buy/sell rule
(an M option exercise is `other`, never a buy), `net_direction`, and the
route's response shape.
"""

from __future__ import annotations

import time
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.sim import router as sim_router
from app.services import edgar_ownership as eo

FIXTURES = Path(__file__).parent.parent / "fixtures" / "cr244"

_SCHEDULED_XML = (FIXTURES / "form4_scheduled_10b5-1.xml").read_text()
_DISCRETIONARY_XML = (FIXTURES / "form4_discretionary.xml").read_text()
_UNSTATED_XML = (FIXTURES / "form3_unstated.xml").read_text()
_DERIVATIVE_XML = (FIXTURES / "form4_derivative_and_nonderivative.xml").read_text()


def _submissions_with_refs(*, since_ok: bool = True) -> dict:
    """Real filings (verified live, 2026-09-27): two NVDA Form 4s (one
    `aff10b5One=1` scheduled, one `aff10b5One=0` discretionary), an NVDA
    Form 3 (element absent → unstated), an AAPL Form 4 carrying BOTH a
    non-derivative table (P/S-eligible codes) and a derivative table (an M
    -code RSU settlement) — inside the 90-day window — plus a Form 10-K
    that must be ignored by the ownership-forms filter. `primaryDocument`
    values use the REAL xsl-rendered shape (`xslF345X06/...`), not the bare
    filename the old hand-written fixture wrongly assumed (B1)."""
    return {
        "filings": {
            "recent": {
                "form": ["4", "4", "3", "4", "10-K"],
                "accessionNumber": [
                    "0001696841-26-000014", "0001199039-26-000016",
                    "0001696841-26-000001", "0001140361-26-037020",
                    "0001045810-26-000050",
                ],
                "filingDate": ["2026-09-23", "2026-09-22", "2026-09-20", "2026-09-17", "2026-09-01"],
                "primaryDocument": [
                    "xslF345X06/wk-form4_1790196985.xml", "xslF345X06/wk-form4_1790110579.xml",
                    "xslF345X06/wk-form3_1788468666.xml", "xslF345X06/form4.xml",
                    "nvda-20260126.htm",
                ],
            },
        },
    }


class _FakeResponse:
    def __init__(self, status_code: int, text: str = "", json_body=None) -> None:
        self.status_code = status_code
        self.text = text
        self._json = json_body

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)

    def json(self):
        return self._json


class _FakeClient:
    """Stands in for `httpx.Client` as a context manager — NOT a subclass of
    the real `httpx.Client`, so patching `eo.httpx.Client` never touches
    starlette's `TestClient` (which itself subclasses `httpx.Client`;
    monkeypatching the real class's `.get` would break the route tests'
    own request machinery)."""

    def __init__(self, *args, **kwargs) -> None:
        self._get = kwargs.pop("_get", None)

    def __enter__(self) -> "_FakeClient":
        return self

    def __exit__(self, *args) -> None:
        return None

    def get(self, url, *args, **kwargs):
        return self._get(url)


def _patch_network(
    monkeypatch: pytest.MonkeyPatch,
    *,
    cik: int | None = 1045810,
    submissions: dict | None = None,
    xml_by_url: dict[str, str] | None = None,
    fail_urls: set[str] | None = None,
) -> None:
    monkeypatch.setattr(eo, "resolve_cik", lambda t: cik)
    fail_urls = fail_urls or set()
    xml_by_url = xml_by_url or {}

    def _get(url):
        if "submissions" in url:
            if submissions is None:
                return _FakeResponse(404)
            return _FakeResponse(200, json_body=submissions)
        if url in fail_urls:
            return _FakeResponse(500)
        return _FakeResponse(200, text=xml_by_url.get(url, ""))

    def _client_factory(*args, **kwargs):
        return _FakeClient(_get=_get)

    monkeypatch.setattr(eo.httpx, "Client", _client_factory)


@pytest.fixture(autouse=True)
def clear_cache():
    eo.clear_insider_cache()
    yield
    eo.clear_insider_cache()


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(sim_router)
    return TestClient(app, raise_server_exceptions=False)


# All refs resolve under CIK 1045810 in these tests (`_patch_network`'s
# mocked `resolve_cik` always returns 1045810, regardless of which real
# issuer originally filed the fixture XML) — so the derivative fixture's
# real AAPL accession is addressed under NVDA's CIK here, test-fixture-only.
_SCHEDULED_URL = "https://www.sec.gov/Archives/edgar/data/1045810/000169684126000014/wk-form4_1790196985.xml"
_DISCRETIONARY_URL = "https://www.sec.gov/Archives/edgar/data/1045810/000119903926000016/wk-form4_1790110579.xml"
_UNSTATED_URL = "https://www.sec.gov/Archives/edgar/data/1045810/000169684126000001/wk-form3_1788468666.xml"
_DERIVATIVE_URL = "https://www.sec.gov/Archives/edgar/data/1045810/000114036126037020/form4.xml"

# The DISPLAY urls (what a Response actually carries — the xsl path stays
# user-facing, B1) differ from the RAW fetch urls above only by the
# `xslF345X06/` prefix `_patch_network`'s fake client keys on the RAW url.
_SCHEDULED_DISPLAY_URL = "https://www.sec.gov/Archives/edgar/data/1045810/000169684126000014/xslF345X06/wk-form4_1790196985.xml"
_DISCRETIONARY_DISPLAY_URL = "https://www.sec.gov/Archives/edgar/data/1045810/000119903926000016/xslF345X06/wk-form4_1790110579.xml"
_DERIVATIVE_DISPLAY_URL = "https://www.sec.gov/Archives/edgar/data/1045810/000114036126037020/xslF345X06/form4.xml"


def _xml_map() -> dict[str, str]:
    return {
        _SCHEDULED_URL: _SCHEDULED_XML,
        _DISCRETIONARY_URL: _DISCRETIONARY_XML,
        _UNSTATED_URL: _UNSTATED_XML,
        _DERIVATIVE_URL: _DERIVATIVE_XML,
    }


# ── plan_type — the structural control, all three outcomes ─────────────────


def test_plan_type_scheduled_when_aff10b5one_ticked(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_network(monkeypatch, submissions=_submissions_with_refs(), xml_by_url=_xml_map())
    result = eo.get_insider_activity("NVDA")
    scheduled = [t for t in result.transactions
                 if t.url == _SCHEDULED_DISPLAY_URL and t.direction != "other"]
    assert scheduled and all(t.plan_type == "scheduled_10b5-1" for t in scheduled)


def test_plan_type_discretionary_when_aff10b5one_present_unticked(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_network(monkeypatch, submissions=_submissions_with_refs(), xml_by_url=_xml_map())
    result = eo.get_insider_activity("NVDA")
    discretionary = [t for t in result.transactions
                     if t.url == _DISCRETIONARY_DISPLAY_URL and t.direction != "other"]
    assert discretionary and all(t.plan_type == "discretionary" for t in discretionary)


def test_plan_type_unstated_when_element_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    # form3_unstated.xml has no nonDerivativeTransaction rows (it's a Form 3
    # holdings-only filing), so exercise the parser directly.
    from xml.etree import ElementTree

    root = ElementTree.fromstring(_UNSTATED_XML)
    assert eo._parse_plan_type(root) == "unstated"


def test_plan_type_never_inferred_from_footnote_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """The scheduled fixture's footnote F1 states the 10b5-1 plan in prose,
    but a discretionary fixture with an IDENTICAL footnote and aff10b5One=0
    must still read discretionary — proving the parser reads the element,
    not the footnote."""
    xml_with_misleading_footnote = _DISCRETIONARY_XML.replace(
        "</ownershipDocument>",
        '<footnotes><footnote id="F9">Effected pursuant to a Rule 10b5-1 trading plan.</footnote>'
        "</footnotes></ownershipDocument>",
    )
    from xml.etree import ElementTree

    root = ElementTree.fromstring(xml_with_misleading_footnote)
    assert eo._parse_plan_type(root) == "discretionary"


# ── P/S-only buy/sell rule ───────────────────────────────────────────────────


def test_only_p_and_s_get_buy_sell_direction(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_network(monkeypatch, submissions=_submissions_with_refs(), xml_by_url=_xml_map())
    result = eo.get_insider_activity("NVDA")
    by_code = {t.code: t.direction for t in result.transactions}
    assert by_code["S"] == "sell"
    assert by_code["M"] == "other"  # option exercise is NOT a buy


def test_option_exercise_never_counted_as_buy_in_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_network(monkeypatch, submissions=_submissions_with_refs(), xml_by_url=_xml_map())
    result = eo.get_insider_activity("NVDA")
    assert result.summary.buys == 0
    assert result.summary.other >= 1
    m_rows = [t for t in result.transactions if t.code == "M"]
    assert m_rows and all(t.direction == "other" for t in m_rows)


def test_code_label_present_for_other_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_network(monkeypatch, submissions=_submissions_with_refs(), xml_by_url=_xml_map())
    result = eo.get_insider_activity("NVDA")
    m_row = next(t for t in result.transactions if t.code == "M")
    assert m_row.code_label == "Option exercise"


# ── net_direction ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "buys,sells,expected",
    [(2, 0, "buying"), (0, 3, "selling"), (1, 1, "mixed"), (0, 0, "none")],
)
def test_net_direction(buys: int, sells: int, expected: str) -> None:
    from app.schemas.company_profile import InsiderTransaction

    transactions = []
    for i in range(buys):
        transactions.append(InsiderTransaction(
            form="4", filed_date="2026-09-01", insider_name="X", code="P",
            code_label="Open-market purchase", direction="buy", plan_type="unstated",
            url=f"https://example.com/{i}-buy",
        ))
    for i in range(sells):
        transactions.append(InsiderTransaction(
            form="4", filed_date="2026-09-01", insider_name="X", code="S",
            code_label="Open-market sale", direction="sell", plan_type="unstated",
            url=f"https://example.com/{i}-sell",
        ))
    summary = eo._summarize(transactions)
    assert summary.net_direction == expected
    assert summary.buys == buys
    assert summary.sells == sells


# ── Filings-window filter (forms 3/4/5 only, non-ownership excluded) ────────


def test_only_ownership_forms_selected_10k_excluded(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_network(monkeypatch, submissions=_submissions_with_refs(), xml_by_url=_xml_map())
    result = eo.get_insider_activity("NVDA")
    assert all(t.form in ("3", "4", "5") for t in result.transactions)


def test_window_excludes_filings_older_than_90_days(monkeypatch: pytest.MonkeyPatch) -> None:
    old_submissions = {
        "filings": {
            "recent": {
                "form": ["4"],
                "accessionNumber": ["0001696841-26-000014"],
                "filingDate": ["2025-01-01"],
                "primaryDocument": ["wk-form4_1790196985.xml"],
            },
        },
    }
    _patch_network(monkeypatch, submissions=old_submissions, xml_by_url=_xml_map())
    result = eo.get_insider_activity("NVDA")
    assert result.transactions == []
    assert result.summary.net_direction == "none"


# ── Degrade paths (CR040) ────────────────────────────────────────────────────


def test_no_cik_yields_not_available(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_network(monkeypatch, cik=None)
    result = eo.get_insider_activity("FOO")
    assert result.state == "not_available"
    assert result.cik is None
    assert result.reason == "No SEC registrant found for this symbol"


def test_submissions_fetch_failure_yields_not_available(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_network(monkeypatch, submissions=None)
    result = eo.get_insider_activity("NVDA")
    assert result.state == "not_available"
    # A submissions FETCH failure is a transient EDGAR outage, and its
    # reason must not say "for this symbol" (LOW).
    assert result.reason == "SEC EDGAR is temporarily unavailable — try again shortly"


def test_no_ownership_filings_in_window_is_live_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    empty_submissions = {
        "filings": {"recent": {"form": [], "accessionNumber": [], "filingDate": [], "primaryDocument": []}},
    }
    _patch_network(monkeypatch, submissions=empty_submissions)
    result = eo.get_insider_activity("NVDA")
    assert result.state == "live"
    assert result.transactions == []


def test_one_xml_fetch_failure_yields_partial_not_blank(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_network(
        monkeypatch, submissions=_submissions_with_refs(), xml_by_url=_xml_map(),
        fail_urls={_UNSTATED_URL},
    )
    result = eo.get_insider_activity("NVDA")
    assert result.state == "partial"
    assert result.reason
    # the Form 4s that DID fetch still show (url is the display/xsl path)
    assert any(t.url == _SCHEDULED_DISPLAY_URL for t in result.transactions)
    assert any(t.url == _DISCRETIONARY_DISPLAY_URL for t in result.transactions)


# ── Cache ─────────────────────────────────────────────────────────────────


def test_result_is_cached_across_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}
    real_submissions = _submissions_with_refs()

    monkeypatch.setattr(eo, "resolve_cik", lambda t: 1045810)

    def _get(url):
        if "submissions" in url:
            calls["n"] += 1
            return _FakeResponse(200, json_body=real_submissions)
        return _FakeResponse(200, text=_xml_map().get(url, ""))

    monkeypatch.setattr(eo.httpx, "Client", lambda *a, **k: _FakeClient(_get=_get))
    eo.get_insider_activity("NVDA")
    eo.get_insider_activity("NVDA")
    assert calls["n"] == 1


# ── Route shape ───────────────────────────────────────────────────────────


def test_route_returns_full_shape(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_network(monkeypatch, submissions=_submissions_with_refs(), xml_by_url=_xml_map())
    r = client.get("/v1/sim/insider/NVDA")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ticker"] == "NVDA"
    assert body["window_days"] == 90
    assert set(body.keys()) == {
        "ticker", "as_of", "cik", "state", "reason", "sources",
        "window_days", "summary", "transactions",
    }
    assert set(body["summary"].keys()) == {"buys", "sells", "other", "net_direction"}
    for t in body["transactions"]:
        assert set(t.keys()) == {
            "form", "filed_date", "transaction_date", "insider_name", "role",
            "code", "code_label", "direction", "shares", "price", "plan_type", "url",
        }


def test_route_is_public_no_auth_required(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_network(monkeypatch, cik=None)
    r = client.get("/v1/sim/insider/NVDA")
    assert r.status_code == 200


def test_route_ticker_normalized(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_network(monkeypatch, submissions=_submissions_with_refs(), xml_by_url=_xml_map())
    r = client.get("/v1/sim/insider/nvda")
    assert r.status_code == 200
    assert r.json()["ticker"] == "NVDA"


def test_route_never_404s_it_reports_not_available_instead(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Unlike company-profile, insider has no separate 'unknown ticker' 404 —
    the contract's only degrade path here is no-CIK → not_available."""
    _patch_network(monkeypatch, cik=None)
    r = client.get("/v1/sim/insider/ZZZZZZ")
    assert r.status_code == 200
    assert r.json()["state"] == "not_available"


def test_route_422s_a_malformed_ticker(client: TestClient) -> None:
    r = client.get("/v1/sim/insider/not$a$ticker")
    assert r.status_code == 422


# ── B1: xsl-vs-raw path (audit finding) ─────────────────────────────────────


def test_fetches_raw_xml_not_xsl_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """`primaryDocument` is the xsl-rendered path
    (`xslF345X06/wk-form4_....xml`, verified live against NVDA
    0001696841-26-000014) — fetching it returns HTML, not the ownership XML
    this module parses. This test FAILS if the xsl path is ever fetched: the
    fake client only serves XML at the RAW (prefix-stripped) url; the xsl
    url resolves to a 404-shaped fake response instead."""
    calls: list[str] = []

    def _get(url):
        calls.append(url)
        if "submissions" in url:
            return _FakeResponse(200, json_body=_submissions_with_refs())
        if "xslF345X06" in url:
            # The xsl path must never be requested — if it is, fail loudly
            # rather than silently serving something parseable.
            return _FakeResponse(200, text="<html>not xml</html>")
        return _FakeResponse(200, text=_xml_map().get(url, ""))

    monkeypatch.setattr(eo, "resolve_cik", lambda t: 1045810)
    monkeypatch.setattr(eo.httpx, "Client", lambda *a, **k: _FakeClient(_get=_get))

    result = eo.get_insider_activity("NVDA")
    assert not any("xslF345X06" in c for c in calls if "form" in c.lower() or "wk-" in c.lower())
    # The fetch must have succeeded (state live/partial with real rows), proving
    # the RAW path was used, not the html-serving xsl path.
    assert result.transactions
    assert result.state in ("live", "partial")


def test_url_field_stays_the_xsl_display_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """The user-facing `url` on each transaction is still the xsl-rendered,
    human-readable SEC page (B1) — only the FETCH target changes to the raw
    XML path, never the link a user is given."""
    _patch_network(monkeypatch, submissions=_submissions_with_refs(), xml_by_url=_xml_map())
    result = eo.get_insider_activity("NVDA")
    assert any(t.url == _SCHEDULED_DISPLAY_URL for t in result.transactions)
    assert all("xslF345X06" in t.url for t in result.transactions)


def test_html_fetch_gives_accurate_parse_error_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    """A filing that returns HTML (e.g. the xsl path was hit by mistake) must
    report an ACCURATE reason, not the old blanket 'could not be fetched'."""
    _, reason = eo._parse_transactions(
        "<!DOCTYPE html><html><body>SEC FORM 4</body></html>",
        form="4", filed_date="2026-09-23", url=_SCHEDULED_DISPLAY_URL,
    )
    assert reason is not None
    assert "html" in reason.lower()


# ── B2: aff10b5One / relationship-flag normalisation ────────────────────────


def test_plan_type_scheduled_for_string_true(monkeypatch: pytest.MonkeyPatch) -> None:
    """Real AAPL filing 0001140361-26-037584 encodes the SAME element as the
    literal string "true" (not "1") — a different filing agent's convention
    for the identical SEC schema field."""
    from xml.etree import ElementTree

    xml = (FIXTURES / "form4_aff10b5one_true_str.xml").read_text()
    root = ElementTree.fromstring(xml)
    assert eo._parse_plan_type(root) == "scheduled_10b5-1"


def test_plan_type_discretionary_for_string_false(monkeypatch: pytest.MonkeyPatch) -> None:
    """Real AAPL filing 0001140361-26-023363 encodes `aff10b5One` as the
    literal string "false"."""
    from xml.etree import ElementTree

    xml = (FIXTURES / "form4_aff10b5one_false_str.xml").read_text()
    root = ElementTree.fromstring(xml)
    assert eo._parse_plan_type(root) == "discretionary"


def test_plan_type_unstated_for_garbage_value() -> None:
    from xml.etree import ElementTree

    root = ElementTree.fromstring("<ownershipDocument><aff10b5One>maybe</aff10b5One></ownershipDocument>")
    assert eo._parse_plan_type(root) == "unstated"


def test_plan_type_unstated_for_empty_element() -> None:
    from xml.etree import ElementTree

    root = ElementTree.fromstring("<ownershipDocument><aff10b5One></aff10b5One></ownershipDocument>")
    assert eo._parse_plan_type(root) == "unstated"


def test_reporting_owner_relationship_flags_normalise_true_false_strings() -> None:
    """The SAME `{"1","true"}`/`{"0","false"}` normalisation `_parse_plan_type`
    uses also applies to `isDirector`/`isOfficer`/`isTenPercentOwner`/
    `isOther` — verified against the real "false"-string AAPL fixture, which
    has NO officerTitle and `isDirector=true` (string), so the role must
    resolve via the boolean flag, not just an officerTitle fallback."""
    from xml.etree import ElementTree

    xml = (FIXTURES / "form4_aff10b5one_false_str.xml").read_text()
    root = ElementTree.fromstring(xml)
    name, role = eo._reporting_owner(root)
    assert name == "LEVINSON ARTHUR D"
    assert role == "Director"


def test_reporting_owner_relationship_flags_normalise_1_0_strings() -> None:
    """The NVDA-convention "1"/"0" numeric-string encoding for the same
    relationship flags."""
    from xml.etree import ElementTree

    xml = (FIXTURES / "form4_scheduled_10b5-1.xml").read_text()
    root = ElementTree.fromstring(xml)
    name, role = eo._reporting_owner(root)
    assert name == "Teter Timothy S."
    assert role == "EVP, General Counsel and Sec"  # officerTitle wins when present


# ── M1: 25-filing cap truncating the 90-day window ──────────────────────────


def test_25_filing_cap_truncation_yields_partial_with_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    n = 30
    submissions = {
        "filings": {
            "recent": {
                "form": ["4"] * n,
                "accessionNumber": [f"0001696841-26-{i:06d}" for i in range(n)],
                "filingDate": [f"2026-09-{(i % 27) + 1:02d}" for i in range(n)],
                "primaryDocument": [f"xslF345X06/wk-form4_{i}.xml" for i in range(n)],
            },
        },
    }

    def _get(url):
        if "submissions" in url:
            return _FakeResponse(200, json_body=submissions)
        return _FakeResponse(200, text=_SCHEDULED_XML)

    monkeypatch.setattr(eo, "resolve_cik", lambda t: 1045810)
    monkeypatch.setattr(eo.httpx, "Client", lambda *a, **k: _FakeClient(_get=_get))

    result = eo.get_insider_activity("NVDA")
    assert result.state == "partial"
    assert result.reason == "Showing the 25 most recent filings in the window"


# ── M5: plan_type on non-P/S rows ───────────────────────────────────────────


def test_plan_type_is_unstated_on_every_non_p_s_row(monkeypatch: pytest.MonkeyPatch) -> None:
    """The 10b5-1 box is filing-level (M5). Carried onto an M exercise or an F
    tax withholding it would read as "a scheduled plan trade" to a slice-2
    agent, so only P/S rows carry it."""
    _patch_network(monkeypatch, submissions=_submissions_with_refs(), xml_by_url=_xml_map())
    result = eo.get_insider_activity("NVDA")
    other_rows = [t for t in result.transactions if t.direction == "other"]
    assert other_rows
    assert all(t.plan_type == "unstated" for t in other_rows)


# ── LOW: filing label map additions ─────────────────────────────────────────


def test_code_label_map_covers_144_and_new_codes() -> None:
    assert eo._CODE_LABELS.get("E") is not None
    assert eo._CODE_LABELS.get("H") is not None


# ── LOW: derivative-only rows included, never counted as buy/sell ──────────


def test_derivative_table_rows_included_as_other(monkeypatch: pytest.MonkeyPatch) -> None:
    """A real filing (AAPL 0001140361-26-037020) carries BOTH tables — its
    derivative-table RSU settlement (code M) must show up as an `other` row,
    not be silently dropped."""
    _patch_network(monkeypatch, submissions=_submissions_with_refs(), xml_by_url=_xml_map())
    result = eo.get_insider_activity("NVDA")
    derivative_rows = [t for t in result.transactions if t.url == _DERIVATIVE_DISPLAY_URL]
    assert len(derivative_rows) >= 4  # 3 nonDerivative + 1 derivative row in that filing
    assert all(t.direction in ("sell", "other") for t in derivative_rows)


# ── LOW: transaction_date is YYYY-MM-DD ─────────────────────────────────────


def test_transaction_date_is_iso_format(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_network(monkeypatch, submissions=_submissions_with_refs(), xml_by_url=_xml_map())
    result = eo.get_insider_activity("NVDA")
    dated = [t for t in result.transactions if t.transaction_date]
    assert dated
    for t in dated:
        assert len(t.transaction_date) == 10 and t.transaction_date[4] == "-" and t.transaction_date[7] == "-"


# ── B3: CIK-resolution outage degrades loudly, distinct reason ─────────────


def test_cik_resolution_outage_yields_not_available_distinct_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(t):
        raise eo.CikResolutionUnavailable("boom")

    monkeypatch.setattr(eo, "resolve_cik", _raise)
    result = eo.get_insider_activity("NVDA")
    assert result.state == "not_available"
    assert result.reason == "SEC EDGAR is temporarily unavailable — try again shortly"
    assert result.reason != "No SEC registrant found for this symbol"


# ── M4: single-flight lock ───────────────────────────────────────────────────


def test_concurrent_cold_calls_for_same_ticker_fetch_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two threads racing a cold `get_insider_activity('NVDA')` must not each
    fetch the submissions JSON independently — the per-ticker lock (M4)
    means the second thread blocks, then reads the populated cache."""
    import threading

    calls = {"n": 0}
    submissions_lock = threading.Lock()

    def _get(url):
        if "submissions" in url:
            with submissions_lock:
                calls["n"] += 1
            time.sleep(0.05)  # widen the race window
            return _FakeResponse(200, json_body=_submissions_with_refs())
        return _FakeResponse(200, text=_xml_map().get(url, ""))

    monkeypatch.setattr(eo, "resolve_cik", lambda t: 1045810)
    monkeypatch.setattr(eo.httpx, "Client", lambda *a, **k: _FakeClient(_get=_get))

    results: list = []

    def _worker():
        results.append(eo.get_insider_activity("NVDA"))

    threads = [threading.Thread(target=_worker) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert calls["n"] == 1
    assert len(results) == 3
