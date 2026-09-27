"""CR244 Part 1 — the Company Review screen's data: yfinance `.info` blended
with EDGAR's submissions JSON, section by section, never source by source.

Each of the four sections (overview/financials/filings/ownership) carries its
own `state`/`reason`/`sources` (CR040 degrade loudly): yfinance being down
does not blank the filings list, and EDGAR having no CIK for this symbol does
not blank the financials. `overview` blends both sources field-by-field
(legal name/SIC/address win from EDGAR when present, description/employees/
website/sector/industry win from yfinance) so it is `partial` rather than
`not_available` whenever either source answers.

Reuses `edgar_8k.SUBMISSIONS_URL`, `edgar_cik.resolve_cik`, and
`fundamentals._EXCHANGE_NAMES` rather than inventing a second scheme for any
of the three — this module fetches the submissions JSON with the exact same
etiquette (`edgar_cik.USER_AGENT`, one retry) `edgar_8k.py`'s own ingest path
uses, just read more broadly (every form type, not only 8-K Item 5.02).

Cached in-process 6h per ticker, matching the API contract's documented
server cache and `fundamentals.py`'s own `_STATEMENTS_TTL_S` precedent for
"how stale is tolerable" (quarterly filings/financials move at most a few
times a year).
"""

from __future__ import annotations

import math
import threading
import time
from datetime import date, datetime, timezone
from typing import Any

import httpx

from app.core.logging import logger
from app.schemas.company_profile import (
    CompanyProfileResponse,
    FilingItem,
    FilingsSection,
    FinancialsSection,
    HolderItem,
    OverviewSection,
    OwnershipSection,
)
from app.services.edgar_8k import SUBMISSIONS_URL
from app.services.edgar_cik import USER_AGENT, resolve_cik
from app.services.fundamentals import _EXCHANGE_NAMES

_FETCH_TIMEOUT_S = 15.0
_TTL_SECONDS = 6 * 60 * 60.0

# Form 3/4/5 belong to the Insider tab (edgar_ownership.py), not the filings
# list — excluded here regardless of amendment suffix (4/A etc.).
_OWNERSHIP_FORMS = frozenset({"3", "3/A", "4", "4/A", "5", "5/A"})
MAX_FILINGS = 20

_FORM_LABELS: dict[str, str] = {
    "10-K": "Annual report",
    "10-K/A": "Annual report (amended)",
    "10-Q": "Quarterly report",
    "10-Q/A": "Quarterly report (amended)",
    "8-K": "Current report",
    "8-K/A": "Current report (amended)",
    "DEF 14A": "Proxy statement",
    "DEFA14A": "Proxy statement (additional material)",
    "S-1": "Registration statement",
    "S-1/A": "Registration statement (amended)",
    "S-3": "Registration statement (shelf)",
    "424B1": "Prospectus",
    "424B2": "Prospectus",
    "424B3": "Prospectus",
    "424B4": "Prospectus",
    "424B5": "Prospectus",
    "SC 13D": "Beneficial ownership statement",
    "SC 13D/A": "Beneficial ownership statement (amended)",
    "SC 13G": "Beneficial ownership statement (passive)",
    "SC 13G/A": "Beneficial ownership statement (passive, amended)",
    "11-K": "Employee stock plan annual report",
    "25": "Notice of delisting",
    "6-K": "Foreign private issuer report",
    "20-F": "Foreign private issuer annual report",
}

_lock = threading.RLock()
_cache: dict[str, tuple[CompanyProfileResponse, float]] = {}


def clear_company_profile_cache() -> None:
    with _lock:
        _cache.clear()


def _yf_num(d: dict, key: str) -> float | None:
    v = d.get(key)
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _yf_int(d: dict, key: str) -> int | None:
    v = _yf_num(d, key)
    return int(v) if v is not None else None


def _fetch_company_submissions(cik: int) -> dict | None:
    url = SUBMISSIONS_URL.format(cik=cik)
    try:
        with httpx.Client(timeout=_FETCH_TIMEOUT_S, headers={"User-Agent": USER_AGENT}) as client:
            r = client.get(url)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warn("edgar_submissions_fetch_error", cik=cik, error=str(exc)[:200])
        return None


def _form_label(form: str, primary_doc_description: str | None) -> str:
    label = _FORM_LABELS.get(form)
    if label:
        return label
    if primary_doc_description:
        return str(primary_doc_description)
    return form


def _filings_from_submissions(submissions: dict, cik: int) -> list[FilingItem] | None:
    """Newest-first, capped at MAX_FILINGS, every form except 3/4/5. None on
    a submissions shape this parser doesn't recognise (mirrors
    `edgar_8k.IndexUnreadable`'s "don't guess" rule) rather than a partial,
    silently-wrong list."""
    filings = submissions.get("filings")
    recent = filings.get("recent") if isinstance(filings, dict) else None
    if not isinstance(recent, dict):
        return None
    forms = recent.get("form")
    accessions = recent.get("accessionNumber")
    filed_dates = recent.get("filingDate")
    if not isinstance(forms, list) or not isinstance(accessions, list) or not isinstance(filed_dates, list):
        return None
    n = len(forms)
    if len(accessions) != n or len(filed_dates) != n:
        return None
    report_dates = recent.get("reportDate")
    if not isinstance(report_dates, list) or len(report_dates) != n:
        report_dates = [None] * n
    primary_docs = recent.get("primaryDocument")
    if not isinstance(primary_docs, list) or len(primary_docs) != n:
        primary_docs = [None] * n
    primary_descs = recent.get("primaryDocDescription")
    if not isinstance(primary_descs, list) or len(primary_descs) != n:
        primary_descs = [None] * n

    items: list[tuple[str, FilingItem]] = []
    for i in range(n):
        form = str(forms[i] or "")
        if form in _OWNERSHIP_FORMS:
            continue
        filed = str(filed_dates[i] or "")
        if not filed:
            continue
        accession = str(accessions[i] or "")
        doc = str(primary_docs[i] or "")
        url = (
            f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/{doc}"
            if doc else f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}"
        )
        items.append((
            filed,
            FilingItem(
                form=form,
                description=_form_label(form, primary_descs[i]),
                filed_date=filed,
                report_date=str(report_dates[i]) if report_dates[i] else None,
                accession_number=accession,
                url=url,
            ),
        ))
    items.sort(key=lambda t: t[0], reverse=True)
    return [item for _, item in items[:MAX_FILINGS]]


def _yf_profile_info(ticker: str) -> dict[str, Any] | None:
    try:
        import yfinance as yf

        info = yf.Ticker(ticker.upper()).info
    except Exception as exc:  # pragma: no cover - defensive, mirrors fundamentals.py
        logger.warn("yfinance_company_profile_error", ticker=ticker, error=str(exc)[:200])
        return None
    return info or None


def _yf_holders(ticker: str) -> tuple[list[HolderItem], bool]:
    """(holders, ok). ok=False means the holders read itself errored — the
    ownership section still has share-count fields from `.info`, so this
    degrades the holders list alone rather than the whole section."""
    holders: list[HolderItem] = []
    try:
        import yfinance as yf

        tk = yf.Ticker(ticker.upper())
        for kind, frame in (("institution", tk.institutional_holders), ("mutual_fund", tk.mutualfund_holders)):
            if frame is None or frame.empty:
                continue
            for _, row in frame.iterrows():
                name = row.get("Holder")
                if not name:
                    continue
                date_reported = row.get("Date Reported")
                holders.append(HolderItem(
                    name=str(name),
                    kind=kind,
                    pct_held=_yf_num(dict(row), "pctHeld") or _yf_num(dict(row), "% Out"),
                    shares=_yf_num(dict(row), "Shares"),
                    date_reported=str(date_reported) if date_reported is not None else None,
                ))
    except Exception as exc:  # pragma: no cover - defensive
        logger.warn("yfinance_holders_error", ticker=ticker, error=str(exc)[:200])
        return [], False
    return holders, True


def _build_company_profile(ticker: str) -> CompanyProfileResponse | None:
    """None ⇒ unknown to both sources (404 at the route)."""
    sym = ticker.upper().strip()
    cik = resolve_cik(sym)
    info = _yf_profile_info(sym)
    submissions = _fetch_company_submissions(cik) if cik is not None else None

    if info is None and submissions is None:
        return None

    as_of = datetime.now(timezone.utc).isoformat()

    # ── overview ──────────────────────────────────────────────────────────
    ov_sources: list[str] = []
    legal_name = display_name = description = sector = industry = None
    sic = sic_description = exchange = website = address = phone = None
    employees: int | None = None

    if info:
        ov_sources.append("yfinance")
        display_name = info.get("longName") or info.get("shortName")
        description = info.get("longBusinessSummary")
        sector = info.get("sector")
        industry = info.get("industry")
        employees = _yf_int(info, "fullTimeEmployees")
        website = info.get("website")
        phone = info.get("phone")
        exchange = _EXCHANGE_NAMES.get(str(info.get("exchange") or "").upper())
        addr_parts = [
            info.get("address1"), info.get("city"), info.get("state"), info.get("zip"),
        ]
        addr = ", ".join(str(p) for p in addr_parts if p)
        address = addr or None

    if submissions:
        ov_sources.append("edgar")
        legal_name = submissions.get("name")
        sic = submissions.get("sic")
        sic_description = submissions.get("sicDescription")
        edgar_addr = submissions.get("addresses", {}).get("business") if isinstance(
            submissions.get("addresses"), dict
        ) else None
        if edgar_addr:
            edgar_parts = [
                edgar_addr.get("street1"), edgar_addr.get("city"),
                edgar_addr.get("stateOrCountry"), edgar_addr.get("zipCode"),
            ]
            edgar_full = ", ".join(str(p) for p in edgar_parts if p)
            if edgar_full:
                address = edgar_full

    if ov_sources:
        state = "live" if info and submissions else "partial"
        reason = None if state == "live" else (
            "SEC EDGAR data unavailable for this symbol" if not submissions
            else "yfinance data unavailable for this symbol"
        )
    else:
        state = "not_available"
        reason = "No company data available from EDGAR or yfinance for this symbol"

    overview = OverviewSection(
        state=state, reason=reason, sources=ov_sources,
        legal_name=legal_name, display_name=display_name, description=description,
        sector=sector, industry=industry, sic=str(sic) if sic is not None else None,
        sic_description=sic_description, exchange=exchange, employees=employees,
        website=website, address=address, phone=phone,
    )

    # ── financials ────────────────────────────────────────────────────────
    if info:
        market_cap = _yf_num(info, "marketCap")
        revenue_ttm = _yf_num(info, "totalRevenue")
        gross_margin = _yf_num(info, "grossMargins")
        operating_margin = _yf_num(info, "operatingMargins")
        net_margin = _yf_num(info, "profitMargins")
        trailing_pe = _yf_num(info, "trailingPE")
        forward_pe_raw = _yf_num(info, "forwardPE")
        forward_pe = forward_pe_raw if forward_pe_raw is not None and forward_pe_raw > 0 else None
        eps_ttm = _yf_num(info, "trailingEps")
        total_debt = _yf_num(info, "totalDebt")
        total_equity = _yf_num(info, "totalStockholderEquity") if "totalStockholderEquity" in info else None
        debt_to_equity_raw = _yf_num(info, "debtToEquity")
        debt_to_equity = (debt_to_equity_raw / 100.0) if debt_to_equity_raw is not None else (
            (total_debt / total_equity) if total_debt is not None and total_equity else None
        )
        free_cash_flow = _yf_num(info, "freeCashflow")
        dividend_yield = _yf_num(info, "dividendYield")
        financials = FinancialsSection(
            state="live", reason=None, sources=["yfinance"], currency=info.get("currency"),
            market_cap=market_cap, revenue_ttm=revenue_ttm, gross_margin=gross_margin,
            operating_margin=operating_margin, net_margin=net_margin, trailing_pe=trailing_pe,
            forward_pe=forward_pe, eps_ttm=eps_ttm, debt_to_equity=debt_to_equity,
            free_cash_flow=free_cash_flow, dividend_yield=dividend_yield,
        )
    else:
        financials = FinancialsSection(
            state="not_available", reason="yfinance data unavailable for this symbol", sources=[],
        )

    # ── filings ───────────────────────────────────────────────────────────
    if cik is None:
        filings = FilingsSection(
            state="not_available", reason="No SEC registrant found for this symbol", sources=[],
        )
    elif submissions is None:
        filings = FilingsSection(
            state="not_available", reason="SEC EDGAR data unavailable for this symbol", sources=[],
        )
    else:
        parsed = _filings_from_submissions(submissions, cik)
        if parsed is None:
            filings = FilingsSection(
                state="not_available", reason="SEC EDGAR filings index is in an unrecognised format",
                sources=[],
            )
        else:
            filings = FilingsSection(state="live", reason=None, sources=["edgar"], items=parsed)

    # ── ownership ─────────────────────────────────────────────────────────
    if info:
        shares_outstanding = _yf_num(info, "sharesOutstanding")
        float_shares = _yf_num(info, "floatShares")
        pct_institutions = _yf_num(info, "heldPercentInstitutions")
        pct_insiders = _yf_num(info, "heldPercentInsiders")
        holders, holders_ok = _yf_holders(sym)
        if holders_ok:
            ownership = OwnershipSection(
                state="live", reason=None, sources=["yfinance"],
                shares_outstanding=shares_outstanding, float_shares=float_shares,
                pct_institutions=pct_institutions, pct_insiders=pct_insiders, holders=holders,
            )
        else:
            ownership = OwnershipSection(
                state="partial", reason="Named holders list unavailable; share/float figures still shown",
                sources=["yfinance"], shares_outstanding=shares_outstanding, float_shares=float_shares,
                pct_institutions=pct_institutions, pct_insiders=pct_insiders, holders=[],
            )
    else:
        ownership = OwnershipSection(
            state="not_available", reason="yfinance data unavailable for this symbol", sources=[],
        )

    return CompanyProfileResponse(
        ticker=sym, as_of=as_of, cik=(f"{cik:010d}" if cik is not None else None),
        overview=overview, financials=financials, filings=filings, ownership=ownership,
    )


def get_company_profile(ticker: str) -> CompanyProfileResponse | None:
    """Cached 6h per ticker. None ⇒ unknown to both sources (route returns 404)."""
    sym = ticker.upper().strip()
    now = time.monotonic()
    with _lock:
        cached = _cache.get(sym)
        if cached is not None and (now - cached[1]) < _TTL_SECONDS:
            return cached[0]
    result = _build_company_profile(sym)
    if result is not None:
        with _lock:
            _cache[sym] = (result, now)
    return result
