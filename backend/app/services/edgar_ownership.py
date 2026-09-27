"""CR244 Part 1/2 — Form 3/4/5 insider-transaction feed for the Insider tab
and (slice 2, not wired here) the Bull/Bear Researcher prompts.

Genuinely new integration: Form 3/4/5 ownership data is NOT in the
submissions JSON's `filings.recent` block the way 8-Ks are — `edgar_8k.py`
reads that block for item codes and text; this module walks the SAME block
filtered to forms 3/4/5, then fetches each filing's own ownership XML (a
separate document per filing, not covered by anything `edgar_8k.py` or
`company_profile.py` already fetches).

**The xsl-vs-raw path, corrected against a LIVE filing (NVDA CIK 1045810,
accession 0001696841-26-000014, re-verified 2026-09-27):** `filings.recent`'s
`primaryDocument` for a Form 3/4/5 is the XSL-RENDERED path,
`xslF345X06/wk-form4_1790196985.xml` (the version suffix varies by schema
year — X05/X06/etc.) — fetching that path returns `text/html` (a rendered
human-readable table, confirmed via `content-type: text/html` on the same
live filing), NOT the ownership XML this module parses. The raw XML sits at
the SAME accession folder, one level up, under the document's bare
filename: `.../data/{cik}/{accession_nodash}/wk-form4_1790196985.xml` — the
same `.../data/{cik}/{accession}/{document}` shape `edgar_8k.archive_url`
uses for 8-Ks, once the `xslF345X06/` prefix is stripped. This module
fetches THAT raw path for parsing and keeps the xsl path as the user-facing
`url` (SEC's own human-readable rendering is the right thing to link a user
to; the raw XML is not).

**`plan_type` is a structural control, not a prompt instruction (CLAUDE.md
CR038):** read only from the Form 4/5 XML's own `aff10b5One` element — a
document-level flag (a sibling of `reportingOwnerRelationship` and
`nonDerivativeTable`, not per-transaction), added to the ownership schema
under the SEC's 2023 Rule 10b5-1 amendments. Verified against real filings
on both sides of a convention split SEC itself is inconsistent about: NVDA
filings encode the element as `"1"`/`"0"` (0001696841-26-000014 → `1`,
0001199039-26-000016 → `0`), while AAPL filings from the SAME filing agent
encode it as `"true"`/`"false"` (0001140361-26-037584 → `true`,
0001140361-26-023363 → `false`) — both forms live, both current, both
`documentType 4`. `_parse_plan_type` normalises case-insensitively:
`{"1","true"}` → `scheduled_10b5-1`, `{"0","false"}` → `discretionary`, an
empty string or any other value → `unstated` (never guessed), and the
element's absence (pre-April-2023 filings; verified against AAPL
0000320193-22-000078, a 2022 Form 4/A, which carries no `aff10b5One` element
at all) → `unstated`. Never inferred from footnote text or by a model — the
element or its absence is the only signal read. The SAME `{"1","true"}` /
{"0","false"}` normalisation applies to `isDirector`/`isOfficer`/
`isTenPercentOwner`/`isOther` in `_reporting_owner` for the identical reason
(same filing agents, same inconsistency).

The ownership XML carries no namespace prefix on its elements (verified on
the same filings) — `ElementTree.find` runs on bare tag names throughout, no
namespace map needed.

Only transaction codes P (open-market purchase) and S (open-market sale) get
a buy/sell `direction` and count toward `net_direction`. Every other code
(M exercise, A grant, F tax withholding, G gift, C conversion, …) is `other`
— the mockup's "BUY · option ex." was wrong (CR244's own correction) and
must not recur here. Rows from the derivative table (option/RSU grants,
conversions — verified against a real filing, AAPL 0001140361-26-037020,
which carries both tables) are included as `other` rows too, with their own
code label, rather than silently dropped — a filing with only derivative
activity must not read as "no insider activity" (verified: that filing's
own nonDerivativeTable also had P/S-eligible rows, but a filing could carry
derivative rows alone).

`plan_type` (M5) is a filing-level checkbox, not a per-transaction fact. It
is emitted on the P/S rows it can describe; every other row (an M exercise,
an F tax withholding) gets `unstated`, so a slice-2 agent can never read a
tax withholding as "a scheduled plan trade".

Rate pacing ≤10 req/s (SEC's own limit) via `edgar_cik.paced_get`, the ONE
paced-GET helper this feature's every SEC fetch shares (M4) — including the
CIK map and the submissions JSON, both routed through the same clock.
Cached 6h per ticker for a `live` result; a `not_available`/`partial` result
is cached only 5 minutes (M2) — a transient SEC outage must not lock a
symbol into "no data" for 6 hours. A per-ticker single-flight lock (M4)
means two concurrent cold requests for the same ticker do ONE fetch, not
two — the 25-filing fetch is the expensive path this protects.
"""

from __future__ import annotations

import re
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
from app.services.edgar_cik import (
    USER_AGENT,
    CikResolutionUnavailable,
    paced_get,
    resolve_cik,
)

_FETCH_TIMEOUT_S = 15.0
_TTL_SECONDS = 6 * 60 * 60.0
_DEGRADED_TTL_SECONDS = 5 * 60.0  # M2: a not_available/partial result is not cached 6h

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
    "E": "Expiration of short derivative position",
    "H": "Expiration of long derivative position",
    "K": "Equity swap transaction",
    "L": "Small acquisition",
    "U": "Disposition pursuant to a tender offer",
    "Z": "Deposit/withdrawal of voting trust",
}
_BUY_SELL_CODES = frozenset({"P", "S"})
_XSL_PREFIX_RE = re.compile(r"^xsl[\w-]*/")

_lock = threading.RLock()
_cache: dict[str, tuple[InsiderResponse, float]] = {}
_MAX_CACHE_ENTRIES = 512
# M4: one single-flight lock per in-flight ticker build, so two concurrent
# cold requests for the same symbol fetch once, not twice.
_inflight_locks: dict[str, threading.Lock] = {}
_inflight_locks_guard = threading.Lock()


def clear_insider_cache() -> None:
    with _lock:
        _cache.clear()


def _sweep_expired_locked(now: float) -> None:
    """Called with `_lock` held. Drops expired entries opportunistically on
    insert so the cache never grows unbounded between explicit clears (M3)."""
    expired = [
        k for k, (resp, cached_at) in _cache.items()
        if (now - cached_at) >= (_TTL_SECONDS if resp.state == "live" else _DEGRADED_TTL_SECONDS)
    ]
    for k in expired:
        del _cache[k]
    if len(_cache) >= _MAX_CACHE_ENTRIES:
        for k, _ in sorted(_cache.items(), key=lambda kv: kv[1][1])[: len(_cache) - _MAX_CACHE_ENTRIES + 1]:
            _cache.pop(k, None)


def _raw_xml_url(xsl_url_or_doc: str, *, cik: int, accession_nodash: str) -> str:
    """The raw ownership XML path for a `primaryDocument` value that may
    carry an `xslF345X06/`-style rendering prefix. Strips exactly that
    leading `xsl.../` segment (verified live: NVDA's is `xslF345X06/`,
    older schema years use `xslF345X05/` etc.) and rebuilds the bare
    `.../data/{cik}/{accession}/{document}` path `edgar_8k.archive_url` uses
    for 8-Ks. A `primaryDocument` with no such prefix (an older filing,
    before SEC started xsl-rendering ownership forms) is used as-is."""
    doc = _XSL_PREFIX_RE.sub("", xsl_url_or_doc)
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/{doc}"


def _xsl_display_url(primary_doc: str, *, cik: int, accession_nodash: str) -> str:
    """The user-facing link — SEC's own human-readable rendering, exactly the
    path `primaryDocument` names (xsl-prefixed or not). Never the raw XML."""
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/{primary_doc}"


def _fetch_ownership_submissions(client: httpx.Client, cik: int) -> dict | None:
    try:
        r = paced_get(client, SUBMISSIONS_URL.format(cik=cik))
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warn("edgar_ownership_submissions_error", cik=cik, error=str(exc)[:200])
        return None


def _select_ownership_refs(submissions: dict, cik: int, *, since: date) -> tuple[list[dict] | None, bool]:
    """(refs, truncated). Every Form 3/4/5 (excluding amendments) in
    `filings.recent` filed on or after `since`, newest first, capped at
    MAX_FILINGS. `truncated=True` when the 90-day window itself held more
    than MAX_FILINGS (M1) — the cap and the window both narrowing the same
    list must be told apart. `(None, False)` on a shape this parser doesn't
    recognise."""
    filings = submissions.get("filings")
    recent = filings.get("recent") if isinstance(filings, dict) else None
    if not isinstance(recent, dict):
        return None, False
    forms = recent.get("form")
    accessions = recent.get("accessionNumber")
    filed_dates = recent.get("filingDate")
    primary_docs = recent.get("primaryDocument")
    if not all(isinstance(x, list) for x in (forms, accessions, filed_dates, primary_docs)):
        return None, False
    n = len(forms)
    if not all(len(x) == n for x in (accessions, filed_dates, primary_docs)):
        return None, False

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
        accession_nodash = accession.replace("-", "")
        refs.append((filed_str, {
            "form": form, "filed_date": filed_str, "accession_number": accession,
            "raw_url": _raw_xml_url(doc, cik=cik, accession_nodash=accession_nodash),
            "display_url": _xsl_display_url(doc, cik=cik, accession_nodash=accession_nodash),
        }))
    refs.sort(key=lambda t: t[0], reverse=True)
    truncated = len(refs) > MAX_FILINGS
    return [ref for _, ref in refs[:MAX_FILINGS]], truncated


def _find_text(elem: ElementTree.Element, path: str) -> str | None:
    found = elem.find(path)
    if found is None or found.text is None:
        return None
    text = found.text.strip()
    return text or None


def _bool_flag(value: str | None) -> bool:
    """`{"1","true"}` (case-insensitive) → True; everything else (including
    `"0"`/`"false"`/empty/garbage) → False. Shared by `plan_type` and the
    reporting-owner relationship flags — both encodings appear live across
    filing agents (NVDA's own filer uses `"1"`/`"0"`, AAPL's uses
    `"true"`/`"false"`, same document type, same SEC schema)."""
    return (value or "").strip().lower() in ("1", "true")


def _parse_plan_type(root: ElementTree.Element) -> str:
    """`scheduled_10b5-1` (ticked) | `discretionary` (present, unticked) |
    `unstated` (element absent, empty, or an unrecognised value — older
    forms, or a shape this parser doesn't vouch for). Read ONLY from
    `aff10b5One`; nothing else in the document is consulted. Normalises
    `"1"`/`"true"` and `"0"`/`"false"` case-insensitively (both encodings are
    live, per the module docstring); any other text (a typo, a future
    schema value) is `unstated` rather than guessed either way."""
    node = root.find("aff10b5One")
    if node is None or node.text is None:
        return "unstated"
    value = node.text.strip()
    if not value:
        return "unstated"
    low = value.lower()
    if low in ("1", "true"):
        return "scheduled_10b5-1"
    if low in ("0", "false"):
        return "discretionary"
    return "unstated"


def _reporting_owner(root: ElementTree.Element) -> tuple[str, str | None]:
    name = _find_text(root, "./reportingOwner/reportingOwnerId/rptOwnerName") or "Unknown"
    rel = root.find("./reportingOwner/reportingOwnerRelationship")
    role = None
    if rel is not None:
        title = _find_text(rel, "officerTitle")
        if title:
            role = title
        elif _bool_flag(_find_text(rel, "isDirector")):
            role = "Director"
        elif _bool_flag(_find_text(rel, "isTenPercentOwner")):
            role = "10% owner"
        elif _bool_flag(_find_text(rel, "isOther")):
            role = _find_text(rel, "otherText") or "Other"
    return name, role


def _report_date_iso(raw: str | None) -> str | None:
    """`YYYY-MM-DD`, re-normalised through `date.fromisoformat` rather than
    passed through — SEC's own field is already ISO, but this guards against
    a stray time component or separator variant reaching the wire."""
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10]).isoformat()
    except ValueError:
        return None


def _parse_one_table(
    table: ElementTree.Element | None, *, tag: str, plan_type: str,
    insider_name: str, role: str | None, form: str, filed_date: str, url: str,
) -> list[InsiderTransaction]:
    out: list[InsiderTransaction] = []
    if table is None:
        return out
    for tx in table.findall(tag):
        tx_code = _find_text(tx, "./transactionCoding/transactionCode") or ""
        shares_str = _find_text(tx, "./transactionAmounts/transactionShares/value")
        price_str = _find_text(tx, "./transactionAmounts/transactionPricePerShare/value")
        tx_date = _report_date_iso(_find_text(tx, "./transactionDate/value"))
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
            plan_type=plan_type if direction != "other" else "unstated",
            url=url,
        ))
    return out


def _parse_transactions(
    xml_text: str, *, form: str, filed_date: str, url: str,
) -> tuple[list[InsiderTransaction] | None, str | None]:
    """(transactions, error_reason). `error_reason` is None on success —
    a distinct, honest string on XML-parse failure or on a document that
    parsed but isn't the ownership shape (e.g. HTML fetched by mistake)."""
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as exc:
        logger.warn("edgar_ownership_xml_parse_error", url=url, error=str(exc)[:200])
        stripped = xml_text.lstrip()[:100].lower()
        if "<html" in stripped or "<!doctype html" in stripped:
            return None, "SEC returned an HTML page instead of the ownership XML for this filing"
        return None, "the filing's XML could not be parsed"
    if root.tag != "ownershipDocument":
        logger.warn("edgar_ownership_unexpected_root", url=url, tag=root.tag)
        return None, f"unexpected document shape (root element {root.tag!r})"

    plan_type = _parse_plan_type(root)
    insider_name, role = _reporting_owner(root)
    out = _parse_one_table(
        root.find("nonDerivativeTable"), tag="nonDerivativeTransaction",
        plan_type=plan_type, insider_name=insider_name, role=role,
        form=form, filed_date=filed_date, url=url,
    )
    out.extend(_parse_one_table(
        root.find("derivativeTable"), tag="derivativeTransaction",
        plan_type=plan_type, insider_name=insider_name, role=role,
        form=form, filed_date=filed_date, url=url,
    ))
    return out, None


def _fetch_transactions(client: httpx.Client, ref: dict) -> tuple[list[InsiderTransaction] | None, str | None]:
    """(transactions, error_reason). `error_reason` is set on ANY failure —
    fetch or parse — so the caller can say WHY a filing didn't render rather
    than a blanket "could not be fetched" (B1)."""
    try:
        r = paced_get(client, ref["raw_url"])
        if r.status_code != 200:
            return None, f"SEC returned HTTP {r.status_code} for this filing"
        return _parse_transactions(r.text, form=ref["form"], filed_date=ref["filed_date"], url=ref["display_url"])
    except httpx.HTTPError as exc:
        logger.warn("edgar_ownership_xml_fetch_error", url=ref.get("raw_url"), error=str(exc)[:200])
        return None, "SEC EDGAR could not be reached for this filing"


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
    try:
        cik = resolve_cik(sym)
    except CikResolutionUnavailable:
        return InsiderResponse(
            ticker=sym, as_of=as_of, cik=None, state="not_available",
            reason="SEC EDGAR is temporarily unavailable — try again shortly", sources=[],
            window_days=WINDOW_DAYS, summary=_summarize([]), transactions=[],
        )
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
                reason="SEC EDGAR is temporarily unavailable — try again shortly", sources=[],
                window_days=WINDOW_DAYS, summary=_summarize([]), transactions=[],
            )
        refs, truncated = _select_ownership_refs(submissions, cik, since=since)
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
        fetch_errors: list[str] = []
        for ref in refs:
            parsed, error_reason = _fetch_transactions(client, ref)
            if parsed is None:
                fetch_errors.append(error_reason or "could not be fetched")
                continue
            transactions.extend(parsed)

    transactions.sort(key=lambda t: t.filed_date, reverse=True)

    if fetch_errors:
        state = "partial"
        reason = "Some filings could not be fetched from SEC EDGAR; the list below may be incomplete"
    elif truncated:
        state = "partial"
        reason = "Showing the 25 most recent filings in the window"
    else:
        state = "live"
        reason = None

    return InsiderResponse(
        ticker=sym, as_of=as_of, cik=f"{cik:010d}", state=state, reason=reason,
        sources=["edgar"], window_days=WINDOW_DAYS,
        summary=_summarize(transactions), transactions=transactions,
    )


def _get_lock(sym: str) -> threading.Lock:
    """The per-ticker single-flight lock (M4). Bounded the same way the
    response cache is (M3): an unlocked, unheld lock is dropped opportunistically
    once the map exceeds `_MAX_CACHE_ENTRIES` — a lock currently held by an
    in-flight build is never evicted (`locked()` guards that)."""
    with _inflight_locks_guard:
        lock = _inflight_locks.get(sym)
        if lock is None:
            if len(_inflight_locks) >= _MAX_CACHE_ENTRIES:
                for k in [k for k, v in _inflight_locks.items() if not v.locked()][
                    : len(_inflight_locks) - _MAX_CACHE_ENTRIES + 1
                ]:
                    _inflight_locks.pop(k, None)
            lock = threading.Lock()
            _inflight_locks[sym] = lock
        return lock


def get_insider_activity(ticker: str) -> InsiderResponse:
    """Cached 6h (live) / 5min (degraded, M2) per ticker. A per-ticker
    single-flight lock (M4) means two concurrent cold callers for the same
    symbol build once, not twice — the second caller blocks on the lock,
    then reads the (now populated) cache instead of re-fetching."""
    sym = ticker.upper().strip()
    now = time.monotonic()
    with _lock:
        cached = _cache.get(sym)
        if cached is not None:
            ttl = _TTL_SECONDS if cached[0].state == "live" else _DEGRADED_TTL_SECONDS
            if (now - cached[1]) < ttl:
                return cached[0]

    with _get_lock(sym):
        with _lock:
            cached = _cache.get(sym)
            if cached is not None:
                ttl = _TTL_SECONDS if cached[0].state == "live" else _DEGRADED_TTL_SECONDS
                if (now - cached[1]) < ttl:
                    return cached[0]
        result = _build_insider_activity(sym)
        with _lock:
            _sweep_expired_locked(time.monotonic())
            _cache[sym] = (result, time.monotonic())
    return result
