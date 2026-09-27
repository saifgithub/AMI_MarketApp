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
of the three. Every SEC GET goes through `edgar_cik.paced_get` (M4) — the
same rate-limited, single-retry-on-429/5xx helper `edgar_ownership.py` and
the CIK-map fetch use; this module does not keep its own pacing/retry
scheme (the old docstring here claimed "one retry" without ever
implementing it — `paced_get` is what actually does it now).

**B5 — a yfinance `.info` payload for a ticker it does NOT know is not
empty, it's `{'trailingPegRatio': None}`** (verified live, 2026-09-27,
`yf.Ticker("ZZZZQXQ").info`) — a single all-None key, which is truthy as a
dict. Treating any non-empty dict as "yfinance knows this ticker" would
make an unknown symbol read as a company with every field blank rather than
404ing. `_yf_profile_info` is therefore checked for an IDENTITY key
(`longName`/`shortName`/`quoteType`/`regularMarketPrice`) before a caller
may treat it as real; `_yf_has_identity` is that check. A ticker unknown to
BOTH sources still 404s at the route; unlike before, "yfinance answered
but every field in a section is null" now also collapses that SECTION to
`not_available` rather than a `live` section full of nulls (a `live`
section is a promise the fields mean something).

Cached in-process: `live` results 6h (matches the API contract's documented
server cache and `fundamentals.py`'s own `_STATEMENTS_TTL_S` precedent —
quarterly filings/financials move at most a few times a year), a
`not_available`/`partial` result only 5 minutes (M2) — a transient SEC or
yfinance outage should not lock a symbol out of a section for 6 hours once
the outage clears.

**Slice-1 audit (B1/M3):** the submissions fetch, form→label map, and
ownership-form set now live in `app.services.edgar_submissions` as the ONE
shared copy `edgar_filings_feed.py` (the Room agent feed) also uses —
`classify_filing` there is what tells a Schedule 13D/13G where the issuer is
the SUBJECT of someone else's ownership report apart from one where the
issuer is the FILER of its own stake in a different company; the Filings tab
relabels `description` by that same role (`_display_description`, below)
rather than the old generic per-form label for every 13D/13G/13F-HR/N-PX/
CORRESP/UPLOAD row.
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
from app.services.edgar_cik import (
    USER_AGENT,
    CikResolutionUnavailable,
    paced_get,
    resolve_cik,
)
from app.services.edgar_submissions import (
    OWNERSHIP_FORMS as _OWNERSHIP_FORMS,
    classify_filing,
    form_label as _form_label,
)

_FETCH_TIMEOUT_S = 15.0
_TTL_SECONDS = 6 * 60 * 60.0
_DEGRADED_TTL_SECONDS = 5 * 60.0  # M2
_MAX_CACHE_ENTRIES = 512

MAX_FILINGS = 20

_lock = threading.RLock()
_cache: dict[str, tuple[CompanyProfileResponse, float]] = {}

_IDENTITY_KEYS = ("longName", "shortName", "quoteType", "regularMarketPrice")


def clear_company_profile_cache() -> None:
    with _lock:
        _cache.clear()


def _sweep_expired_profile_cache_locked(now: float) -> None:
    """Called with `_lock` held (M3): drop expired entries opportunistically
    on insert, and cap total size, so the cache never grows unbounded."""
    expired = [
        k for k, (resp, cached_at) in _cache.items()
        if (now - cached_at) >= (_TTL_SECONDS if _is_fully_live(resp) else _DEGRADED_TTL_SECONDS)
    ]
    for k in expired:
        del _cache[k]
    if len(_cache) >= _MAX_CACHE_ENTRIES:
        for k, _ in sorted(_cache.items(), key=lambda kv: kv[1][1])[: len(_cache) - _MAX_CACHE_ENTRIES + 1]:
            _cache.pop(k, None)


def _is_fully_live(resp: CompanyProfileResponse) -> bool:
    return all(
        section.state == "live"
        for section in (resp.overview, resp.financials, resp.filings, resp.ownership)
    )


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


def _yf_has_identity(info: dict | None) -> bool:
    """B5: a yfinance `.info` dict for an unknown ticker is not empty — it's
    `{'trailingPegRatio': None}` (verified live). Only a dict carrying at
    least one identity field counts as "yfinance knows this ticker"."""
    if not info:
        return False
    return any(info.get(k) is not None for k in _IDENTITY_KEYS)


def _fetch_company_submissions(cik: int) -> dict | None:
    """This module's own convene-independent fetch (15s timeout, matching the
    display screen's own read budget) — kept distinct from
    `edgar_filings_feed`'s shorter-timeout convene-path fetch, but both route
    through the SAME `edgar_cik.paced_get` pacing clock (B1/M3)."""
    url = SUBMISSIONS_URL.format(cik=cik)
    try:
        with httpx.Client(timeout=_FETCH_TIMEOUT_S, headers={"User-Agent": USER_AGENT}) as client:
            r = paced_get(client, url)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warn("edgar_submissions_fetch_error", cik=cik, error=str(exc)[:200])
        return None


_INVESTMENT_MANAGER_FORMS = frozenset({"13F-HR", "13F-HR/A", "13F-NT", "13F-NT/A", "N-PX", "N-PX/A"})
_CORRESPONDENCE_FORMS = frozenset({"CORRESP", "UPLOAD"})
_SCHEDULE_13D_FORMS = frozenset({"SC 13D", "SC 13D/A", "SCHEDULE 13D", "SCHEDULE 13D/A"})
_SCHEDULE_13G_FORMS = frozenset({"SC 13G", "SC 13G/A", "SCHEDULE 13G", "SCHEDULE 13G/A"})


def _display_description(
    form: str, file_number: str | None, primary_doc_description: str | None, issuer_name: str,
) -> str:
    """B1 — the Filings tab keeps every non-3/4/5 row (it links out, so a
    user can judge for themselves) but must not present one issuer's own
    filing register as if every row were "by" the issuer. Relabelled by
    ROLE (`classify_filing`), not by form code alone:

      - a 13D/13G where the issuer is the FILER (its own stake in another
        company) — say so explicitly, don't reuse the generic label.
      - a 13D/13G where the issuer is the SUBJECT — "filed by a >=5% holder
        OF {issuer}", never phrased as if the issuer filed it.
      - 13F-HR/N-PX — the issuer's OWN holdings report as an investment
        manager, about OTHER companies' shares.
      - CORRESP/UPLOAD — SEC correspondence, not a public filing about the
        issuer's business.

    Every other form keeps `form_label`'s existing wording unchanged —
    `description` stays a plain string (the schema's own contract), only its
    text differs by role.
    """
    role = classify_filing(form, file_number)
    if role == "correspondence":
        return "SEC comment-letter correspondence"
    if role == "issuer_as_investor":
        if form in _INVESTMENT_MANAGER_FORMS:
            return f"{issuer_name}'s own holdings report as an investment manager"
        kind = "13G" if form in _SCHEDULE_13G_FORMS else "13D"
        return f"{issuer_name}'s own stake in another company ({kind})"
    if role == "about_issuer":
        return f"Filed by a >=5% holder of {issuer_name}"
    if form == "25-NSE":
        return "Exchange notice of removal from listing (may concern a debt series)"
    return _form_label(form, primary_doc_description)


def _filings_from_submissions(submissions: dict, cik: int, issuer_name: str) -> list[FilingItem] | None:
    """Newest-first, capped at MAX_FILINGS, every form except 3/4/5. None on
    a submissions shape this parser doesn't recognise (mirrors
    `edgar_8k.IndexUnreadable`'s "don't guess" rule) rather than a partial,
    silently-wrong list. An empty result (zero non-3/4/5 rows after the
    filter) is returned as `[]` — the caller (B/LOW) treats a truly empty
    filings list the same as `edgar_8k.recent_block`'s "index unreadable"
    read: a mapped CIK never has zero filings, so that shape means the
    index moved, not a quiet filer."""
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
    file_numbers = recent.get("fileNumber")
    if not isinstance(file_numbers, list) or len(file_numbers) != n:
        file_numbers = [None] * n

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
                description=_display_description(form, file_numbers[i], primary_descs[i], issuer_name),
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
    return info if _yf_has_identity(info) else None


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
                date_reported_raw = row.get("Date Reported")
                date_reported = None
                if date_reported_raw is not None:
                    try:
                        date_reported = date_reported_raw.date().isoformat()
                    except AttributeError:
                        try:
                            date_reported = date.fromisoformat(str(date_reported_raw)[:10]).isoformat()
                        except ValueError:
                            date_reported = str(date_reported_raw)
                row_dict = dict(row)
                pct_held = _yf_num(row_dict, "pctHeld")
                if pct_held is None:
                    pct_held = _yf_num(row_dict, "% Out")
                holders.append(HolderItem(
                    name=str(name),
                    kind=kind,
                    pct_held=pct_held,  # LOW: real 0.0 must survive — never `or`
                    shares=_yf_num(row_dict, "Shares"),
                    date_reported=date_reported,
                ))
    except Exception as exc:  # pragma: no cover - defensive
        logger.warn("yfinance_holders_error", ticker=ticker, error=str(exc)[:200])
        return [], False
    return holders, True


_EXCHANGE_DISPLAY_NAMES: dict[str, str] = {
    "NASDAQ": "Nasdaq",
    "NYSE": "NYSE",
    "NYSE AMERICAN": "NYSE American",
    "NYSE ARCA": "NYSE Arca",
    "CBOE BZX": "Cboe BZX",
}


def _exchange_display(code: str) -> str | None:
    """Contract-example casing ("Nasdaq"/"NYSE") layered on top of
    `fundamentals._EXCHANGE_NAMES` (all-caps venue names) WITHOUT changing
    that module's own output — this is a local display remap, not an edit
    to `fundamentals.py`."""
    from app.services.fundamentals import _EXCHANGE_NAMES

    raw = _EXCHANGE_NAMES.get(str(code or "").upper())
    if raw is None:
        return None
    return _EXCHANGE_DISPLAY_NAMES.get(raw.upper(), raw)


def _all_fields_null(section_kwargs: dict[str, Any], *, exclude: tuple[str, ...]) -> bool:
    return all(v is None for k, v in section_kwargs.items() if k not in exclude)


def _build_company_profile(ticker: str) -> CompanyProfileResponse | None:
    """None ⇒ unknown to both sources (404 at the route)."""
    sym = ticker.upper().strip()
    try:
        cik = resolve_cik(sym)
        cik_outage = False
    except CikResolutionUnavailable:
        cik = None
        cik_outage = True
    info = _yf_profile_info(sym)
    submissions = _fetch_company_submissions(cik) if cik is not None else None

    if info is None and submissions is None and not cik_outage:
        return None
    # info is None and submissions is None and cik_outage: a CIK-resolver
    # outage with yfinance also silent must still degrade loudly rather
    # than 404 a ticker that might well be real (B3) — fall through and let
    # each section report its own not_available/reason below.

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
        exchange = _exchange_display(info.get("exchange"))
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

    ov_fields = dict(
        legal_name=legal_name, display_name=display_name, description=description,
        sector=sector, industry=industry, sic=sic, sic_description=sic_description,
        exchange=exchange, employees=employees, website=website, address=address, phone=phone,
    )
    if ov_sources and not _all_fields_null(ov_fields, exclude=()):
        state = "live" if info and submissions else "partial"
        reason = None if state == "live" else (
            ("SEC EDGAR is temporarily unavailable — try again shortly" if cik_outage else
             "No SEC registrant found for this symbol" if cik is None else
             "SEC EDGAR data unavailable for this symbol") if not submissions
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
        # B4: yfinance (pinned >=1.0, this venv 1.3.0) returns `dividendYield`
        # as a PERCENT (KO → 2.41), not a fraction — verified live 2026-09-27,
        # same convention `fundamentals.trading_math.valuation.dividend_yield_pct`
        # documents (CR046 M04). The CR244 contract wants a FRACTION
        # (`"dividend_yield": 0.0002` for NVDA in its own example; KO ~0.024),
        # so this divides by 100 rather than reusing `dividend_yield_pct`
        # (which intentionally returns the percent figure for a different
        # contract) — same source convention, different target shape.
        dividend_yield_raw = _yf_num(info, "dividendYield")
        dividend_yield = (dividend_yield_raw / 100.0) if dividend_yield_raw is not None else None

        fin_fields = dict(
            market_cap=market_cap, revenue_ttm=revenue_ttm, gross_margin=gross_margin,
            operating_margin=operating_margin, net_margin=net_margin, trailing_pe=trailing_pe,
            forward_pe=forward_pe, eps_ttm=eps_ttm, debt_to_equity=debt_to_equity,
            free_cash_flow=free_cash_flow, dividend_yield=dividend_yield,
        )
        if _all_fields_null(fin_fields, exclude=()):
            financials = FinancialsSection(
                state="not_available",
                reason="yfinance returned no usable financial fields for this symbol", sources=[],
            )
        else:
            financials = FinancialsSection(
                state="live", reason=None, sources=["yfinance"], currency=info.get("currency"),
                **fin_fields,
            )
    else:
        financials = FinancialsSection(
            state="not_available", reason="yfinance data unavailable for this symbol", sources=[],
        )

    # ── filings ───────────────────────────────────────────────────────────
    if cik_outage and cik is None:
        filings = FilingsSection(
            state="not_available",
            reason="SEC EDGAR is temporarily unavailable — try again shortly", sources=[],
        )
    elif cik is None:
        filings = FilingsSection(
            state="not_available", reason="No SEC registrant found for this symbol", sources=[],
        )
    elif submissions is None:
        filings = FilingsSection(
            state="not_available",
            reason="SEC EDGAR is temporarily unavailable — try again shortly", sources=[],
        )
    else:
        parsed = _filings_from_submissions(submissions, cik, legal_name or display_name or sym)
        if parsed is None:
            filings = FilingsSection(
                state="not_available", reason="SEC EDGAR filings index is in an unrecognised format",
                sources=[],
            )
        elif not parsed:
            # A mapped CIK never has zero filings once 3/4/5 are excluded on
            # a real operating company — an empty result here is the index
            # having moved, same read `edgar_8k.recent_block` gives a
            # zero-row `filings.recent`, not a quiet filer (LOW).
            filings = FilingsSection(
                state="not_available", reason="SEC filing index unreadable", sources=[],
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
        own_fields_null = (
            shares_outstanding is None and float_shares is None
            and pct_institutions is None and pct_insiders is None and not holders
        )
        if not holders_ok:
            ownership = OwnershipSection(
                state="partial", reason="Named holders list unavailable; share/float figures still shown",
                sources=["yfinance"], shares_outstanding=shares_outstanding, float_shares=float_shares,
                pct_institutions=pct_institutions, pct_insiders=pct_insiders, holders=[],
            )
        elif own_fields_null:
            ownership = OwnershipSection(
                state="not_available",
                reason="yfinance returned no ownership fields for this symbol", sources=[],
            )
        else:
            ownership = OwnershipSection(
                state="live", reason=None, sources=["yfinance"],
                shares_outstanding=shares_outstanding, float_shares=float_shares,
                pct_institutions=pct_institutions, pct_insiders=pct_insiders, holders=holders,
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
    """Cached 6h (fully-live) / 5min (any section degraded, M2) per ticker.
    None ⇒ unknown to both sources (route returns 404)."""
    sym = ticker.upper().strip()
    now = time.monotonic()
    with _lock:
        cached = _cache.get(sym)
        if cached is not None:
            ttl = _TTL_SECONDS if _is_fully_live(cached[0]) else _DEGRADED_TTL_SECONDS
            if (now - cached[1]) < ttl:
                return cached[0]
    result = _build_company_profile(sym)
    if result is not None:
        with _lock:
            _sweep_expired_profile_cache_locked(time.monotonic())
            _cache[sym] = (result, time.monotonic())
    return result
