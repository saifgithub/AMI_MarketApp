"""CR244 Part 1/2 — Form 3/4/5 insider-transaction feed for the Insider tab
and (slice 2, not wired here) the Bull/Bear Researcher prompts.

Genuinely new integration: Form 3/4/5 ownership data is NOT in the
submissions JSON's `filings.recent` block the way 8-Ks are — `edgar_8k.py`
reads that block for item codes and text; this module walks the SAME block
filtered to forms 3/4/5, then fetches each filing's own ownership XML (a
separate document per filing, not covered by anything `edgar_8k.py` or
`company_profile.py` already fetches).

**The xsl-vs-raw path, verified against a live filing (NVDA, CIK 1045810,
accession 0001696841-26-000014, read 2026-09-27):** `filings.recent`'s
`primaryDocument` for a Form 4 is the bare XML filename
(`wk-form4_1790196985.xml`) at the plain accession-folder URL — the SAME
`.../data/{cik}/{accession}/{document}` shape `edgar_8k.archive_url` already
uses for 8-Ks. The xsl-rendered HUMAN-READABLE view SEC's own index page
links to is a SEPARATE path, `.../{accession}/xslF345X06/{document}.html`
(version suffix varies by schema year — X05 also occurs on older filings).
This module fetches the raw XML directly from `primaryDocument`, never the
xsl path — there is nothing to "strip an xsl prefix" from because
`filings.recent` was never pointing at the xsl form to begin with.

**`plan_type` is a structural control, not a prompt instruction (CLAUDE.md
CR038):** read only from the Form 4/5 XML's own `aff10b5One` element — a
document-level flag (a sibling of `reportingOwnerRelationship` and
`nonDerivativeTable`, not per-transaction), added to the ownership schema
under the SEC's 2023 Rule 10b5-1 amendments. Verified against two live
filings: NVDA 0001696841-26-000014 carries `<aff10b5One>1</aff10b5One>` with
footnote F1 stating the sale followed a trading plan adopted 2026-05-22
(→ `scheduled_10b5-1`); NVDA 0001199039-26-000016 carries
`<aff10b5One>0</aff10b5One>` (→ `discretionary`). A pre-2023 filing carries
no such element at all (→ `unstated`). Never inferred from footnote text or
by a model — the element or its absence is the only signal read.

The ownership XML carries no namespace prefix on its elements (verified on
the same two live filings) — `ElementTree.find` runs on bare tag names
throughout, no namespace map needed.

Only transaction codes P (open-market purchase) and S (open-market sale) get
a buy/sell `direction` and count toward `net_direction`. Every other code
(M exercise, A grant, F tax withholding, G gift, C conversion, …) is `other`
— the mockup's "BUY · option ex." was wrong (CR244's own correction) and
must not recur here.

Rate pacing ≤10 req/s (SEC's own limit); cached 6h per ticker, same TTL as
`company_profile.py`.
"""

from __future__ import annotations

import threading
import time
from datetime import date, datetime, timedelta, timezone
from xml.etree import ElementTree

import httpx

from app.core.logging import logger
from app.schemas.company_profile import (
    InsiderResponse,
    InsiderSummary,
    InsiderTransaction,
)
from app.services.edgar_8k import SUBMISSIONS_URL
from app.services.edgar_cik import USER_AGENT, resolve_cik

_FETCH_TIMEOUT_S = 15.0
_TTL_SECONDS = 6 * 60 * 60.0
_MIN_REQUEST_INTERVAL_S = 0.1  # ≤10 req/s, SEC's own rate ceiling

WINDOW_DAYS = 90
MAX_FILINGS = 25

_OWNERSHIP_FORMS = frozenset({"3", "4", "5"})  # amendments (3/A etc.) excluded — restated, not new activity

_CODE_LABELS: dict[str, str] = {
    "P": "Open-market purchase",
    "S": "Open-market sale",
    "A": "Grant/award",
    "M": "Option exercise",
    "F": "Tax withholding",
    "G": "Gift",
    "C": "Conversion",
    "D": "Disposition to issuer",
    "X": "Option exercise (in-the-money)",
    "I": "Discretionary transaction",
    "J": "Other acquisition/disposition",
    "V": "Voluntary report",
    "W": "Acquisition/disposition by will or laws of descent",
}
_BUY_SELL_CODES = frozenset({"P", "S"})

_lock = threading.RLock()
_cache: dict[str, tuple[InsiderResponse, float]] = {}
_last_request_at: list[float] = [0.0]
_request_lock = threading.Lock()


def clear_insider_cache() -> None:
    with _lock:
        _cache.clear()


def _paced_get(client: httpx.Client, url: str) -> httpx.Response:
    with _request_lock:
        now = time.monotonic()
        wait = _MIN_REQUEST_INTERVAL_S - (now - _last_request_at[0])
        if wait > 0:
            time.sleep(wait)
        r = client.get(url)
        _last_request_at[0] = time.monotonic()
        return r


def _fetch_ownership_submissions(client: httpx.Client, cik: int) -> dict | None:
    try:
        r = _paced_get(client, SUBMISSIONS_URL.format(cik=cik))
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warn("edgar_ownership_submissions_error", cik=cik, error=str(exc)[:200])
        return None


def _select_ownership_refs(submissions: dict, cik: int, *, since: date) -> list[dict] | None:
    """Every Form 3/4/5 (excluding amendments) in `filings.recent` filed on
    or after `since`, newest first, capped at MAX_FILINGS. None on a shape
    this parser doesn't recognise."""
    filings = submissions.get("filings")
    recent = filings.get("recent") if isinstance(filings, dict) else None
    if not isinstance(recent, dict):
        return None
    forms = recent.get("form")
    accessions = recent.get("accessionNumber")
    filed_dates = recent.get("filingDate")
    primary_docs = recent.get("primaryDocument")
    if not all(isinstance(x, list) for x in (forms, accessions, filed_dates, primary_docs)):
        return None
    n = len(forms)
    if not all(len(x) == n for x in (accessions, filed_dates, primary_docs)):
        return None

    refs: list[tuple[str, dict]] = []
    for i in range(n):
        form = str(forms[i] or "")
        if form not in _OWNERSHIP_FORMS:
            continue
        filed_str = str(filed_dates[i] or "")
        try:
            filed = date.fromisoformat(filed_str)
        except ValueError:
            continue
        if filed < since:
            continue
        doc = str(primary_docs[i] or "")
        if not doc:
            continue
        accession = str(accessions[i] or "")
        refs.append((filed_str, {
            "form": form, "filed_date": filed_str, "accession_number": accession,
            "url": f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/{doc}",
        }))
    refs.sort(key=lambda t: t[0], reverse=True)
    return [ref for _, ref in refs[:MAX_FILINGS]]


def _find_text(elem: ElementTree.Element, path: str) -> str | None:
    found = elem.find(path)
    if found is None or found.text is None:
        return None
    text = found.text.strip()
    return text or None


def _parse_plan_type(root: ElementTree.Element) -> str:
    """`scheduled_10b5-1` (ticked) | `discretionary` (present, unticked) |
    `unstated` (element absent — older forms, pre-April-2023). Read ONLY
    from `aff10b5One`; nothing else in the document is consulted."""
    node = root.find("aff10b5One")
    if node is None or node.text is None:
        return "unstated"
    value = node.text.strip()
    return "scheduled_10b5-1" if value == "1" else "discretionary"


def _reporting_owner(root: ElementTree.Element) -> tuple[str, str | None]:
    name = _find_text(root, "./reportingOwner/reportingOwnerId/rptOwnerName") or "Unknown"
    rel = root.find("./reportingOwner/reportingOwnerRelationship")
    role = None
    if rel is not None:
        title = _find_text(rel, "officerTitle")
        if title:
            role = title
        elif (_find_text(rel, "isDirector") or "0") == "1":
            role = "Director"
        elif (_find_text(rel, "isTenPercentOwner") or "0") == "1":
            role = "10% owner"
        elif (_find_text(rel, "isOther") or "0") == "1":
            role = _find_text(rel, "otherText") or "Other"
    return name, role


def _parse_transactions(xml_text: str, *, form: str, filed_date: str, url: str) -> list[InsiderTransaction] | None:
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as exc:
        logger.warn("edgar_ownership_xml_parse_error", error=str(exc)[:200])
        return None
    plan_type = _parse_plan_type(root)
    insider_name, role = _reporting_owner(root)

    out: list[InsiderTransaction] = []
    table = root.find("nonDerivativeTable")
    if table is None:
        return []
    for tx in table.findall("nonDerivativeTransaction"):
        tx_code = _find_text(tx, "./transactionCoding/transactionCode") or ""
        shares_str = _find_text(tx, "./transactionAmounts/transactionShares/value")
        price_str = _find_text(tx, "./transactionAmounts/transactionPricePerShare/value")
        tx_date = _find_text(tx, "./transactionDate/value")
        try:
            shares = float(shares_str) if shares_str else None
        except ValueError:
            shares = None
        try:
            price = float(price_str) if price_str else None
        except ValueError:
            price = None
        direction = "buy" if tx_code == "P" else "sell" if tx_code == "S" else "other"
        out.append(InsiderTransaction(
            form=form, filed_date=filed_date, transaction_date=tx_date,
            insider_name=insider_name, role=role, code=tx_code,
            code_label=_CODE_LABELS.get(tx_code, tx_code or "Unspecified"),
            direction=direction, shares=shares, price=price,
            plan_type=plan_type, url=url,
        ))
    return out


def _fetch_transactions(client: httpx.Client, ref: dict) -> list[InsiderTransaction] | None:
    try:
        r = _paced_get(client, ref["url"])
        if r.status_code != 200:
            return None
        return _parse_transactions(
            r.text, form=ref["form"], filed_date=ref["filed_date"], url=ref["url"],
        )
    except httpx.HTTPError as exc:
        logger.warn("edgar_ownership_xml_fetch_error", url=ref.get("url"), error=str(exc)[:200])
        return None


def _summarize(transactions: list[InsiderTransaction]) -> InsiderSummary:
    buys = sum(1 for t in transactions if t.direction == "buy")
    sells = sum(1 for t in transactions if t.direction == "sell")
    other = sum(1 for t in transactions if t.direction == "other")
    if buys and sells:
        net = "mixed"
    elif buys:
        net = "buying"
    elif sells:
        net = "selling"
    else:
        net = "none"
    return InsiderSummary(buys=buys, sells=sells, other=other, net_direction=net)


def _build_insider_activity(ticker: str) -> InsiderResponse:
    sym = ticker.upper().strip()
    as_of = datetime.now(timezone.utc).isoformat()
    cik = resolve_cik(sym)
    if cik is None:
        return InsiderResponse(
            ticker=sym, as_of=as_of, cik=None, state="not_available",
            reason="No SEC registrant found for this symbol", sources=[],
            window_days=WINDOW_DAYS, summary=_summarize([]), transactions=[],
        )

    since = datetime.now(timezone.utc).date() - timedelta(days=WINDOW_DAYS)
    with httpx.Client(timeout=_FETCH_TIMEOUT_S, headers={"User-Agent": USER_AGENT}) as client:
        submissions = _fetch_ownership_submissions(client, cik)
        if submissions is None:
            return InsiderResponse(
                ticker=sym, as_of=as_of, cik=f"{cik:010d}", state="not_available",
                reason="SEC EDGAR data unavailable for this symbol", sources=[],
                window_days=WINDOW_DAYS, summary=_summarize([]), transactions=[],
            )
        refs = _select_ownership_refs(submissions, cik, since=since)
        if refs is None:
            return InsiderResponse(
                ticker=sym, as_of=as_of, cik=f"{cik:010d}", state="not_available",
                reason="SEC EDGAR filings index is in an unrecognised format", sources=[],
                window_days=WINDOW_DAYS, summary=_summarize([]), transactions=[],
            )
        if not refs:
            return InsiderResponse(
                ticker=sym, as_of=as_of, cik=f"{cik:010d}", state="live", reason=None,
                sources=["edgar"], window_days=WINDOW_DAYS, summary=_summarize([]), transactions=[],
            )

        transactions: list[InsiderTransaction] = []
        any_fetch_failed = False
        for ref in refs:
            parsed = _fetch_transactions(client, ref)
            if parsed is None:
                any_fetch_failed = True
                continue
            transactions.extend(parsed)

    transactions.sort(key=lambda t: t.filed_date, reverse=True)
    state = "partial" if any_fetch_failed else "live"
    reason = "Some filings could not be fetched from SEC EDGAR; the list below may be incomplete" if any_fetch_failed else None
    return InsiderResponse(
        ticker=sym, as_of=as_of, cik=f"{cik:010d}", state=state, reason=reason,
        sources=["edgar"], window_days=WINDOW_DAYS,
        summary=_summarize(transactions), transactions=transactions,
    )


def get_insider_activity(ticker: str) -> InsiderResponse:
    """Cached 6h per ticker."""
    sym = ticker.upper().strip()
    now = time.monotonic()
    with _lock:
        cached = _cache.get(sym)
        if cached is not None and (now - cached[1]) < _TTL_SECONDS:
            return cached[0]
    result = _build_insider_activity(sym)
    with _lock:
        _cache[sym] = (result, now)
    return result
