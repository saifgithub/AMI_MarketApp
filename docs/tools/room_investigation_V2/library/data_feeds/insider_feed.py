"""CR244 Part 2 reference implementation — the Form 3/4/5 insider-trade feed
for the Bull and Bear Researcher Room prompts.

This module is a faithful port of `backend/app/services/edgar_ownership.py`
(the slice-1 Insider-tab backend module) into standalone library form, per
CR244's "Part 2 — Room agent feeds" table. It imports nothing from
`backend.app`; SEC plumbing comes from this package's `_edgar_common` (itself
a port of `backend/app/services/edgar_cik.py`). Dependencies: stdlib + httpx.

The classification rules are the CR244 contract, not open design space:

- Only transaction codes **P** (open-market purchase) and **S** (open-market
  sale) get a buy/sell `direction` and count toward `net_direction`. Every
  other code (M exercise, A grant, F tax withholding, G gift, C conversion,
  …) is `other` — listed with its code label, NEVER counted. The mockup's
  "BUY · option ex." was wrong (CR244's own correction) and must not recur.
- **`plan_type` is a structural control, not a prompt instruction (CR038):**
  read only from the Form 4/5 XML's own `aff10b5One` element — box ticked
  (`"1"`/`"true"`, normalised case-insensitively; both encodings are live
  across filing agents) → `scheduled_10b5-1`; box present and unticked
  (`"0"`/`"false"`) → `discretionary`; element absent, empty, or an
  unrecognised value (pre-April-2023 filings) → `unstated`. Never inferred
  from footnote text or by a model. It is a FILING-LEVEL checkbox carried on
  P/S rows only; every other row gets `unstated`, so a tax withholding can
  never read as "a scheduled plan trade".
- Both the non-derivative and derivative tables are parsed; derivative rows
  (option/RSU grants, conversions) are included as `other` rows rather than
  silently dropped — a filing with only derivative activity must not read as
  "no insider activity".
- The raw ownership XML sits at the accession folder with the `xslF345X0N/`
  rendering prefix stripped from `primaryDocument` (fetching the xsl path
  returns text/html, not XML); the xsl path stays as the user-facing `url`.
- Amendments (3/A, 4/A, 5/A) are excluded — restated, not new activity.

**State/provenance discipline (CR040, degrade loudly).** Every feed carries
`state` ∈ `live` | `partial` | `not_available`, and `reason` is required
whenever `state != "live"`:

- `not_available`: CIK-resolver outage, no SEC registrant for the symbol, the
  submissions fetch failed, or the filings index is in an unrecognised
  format. An empty `transactions` list in this state is a failure, not a
  quiet filer.
- `live`: the window was fully read. `live` with zero transactions IS a
  dated claim ("none filed in the window") and the renderer says so.
- `partial`: some filings could not be fetched/parsed (each with its own
  reason logged), or the window held more than `max_filings` and the list
  is capped — both are disclosed, never silent.

Adaptations from the backend original (justified, documented):

- **No in-process cache or single-flight lock.** The backend's 6h/5min cache
  and per-ticker lock are request-path concerns of the FastAPI route; this
  reference keeps the fetch pure. An adopter adds caching at its own seam.
- **asyncio instead of threads** (see `_edgar_common`).
- **stdlib `logging` instead of `structlog`.**

`insider_line` is the `..._line()` renderer of CR244's 5-point pattern: the
exact compact text block a Room prompt body line would carry, including
per-row `10b5-1` tags on scheduled rows and an explicit not-available
sentence whenever `state != "live"`. Per-row URLs are carried on the data
model but omitted from the line (compactness; the 8-K precedent likewise
renders accession identity, not links). Prompt-safety sanitisation of
SEC-sourced strings is a backend seam concern (`sanitize_for_prompt`) and is
deliberately NOT ported here — an adopter sanitises at its own seam.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from xml.etree import ElementTree

import httpx

from ._edgar_common import (
    ARCHIVE_URL,
    FETCH_TIMEOUT_S,
    SUBMISSIONS_URL,
    USER_AGENT,
    CikResolutionUnavailable,
    paced_get,
    resolve_cik,
)

logger = logging.getLogger(__name__)

WINDOW_DAYS = 90
MAX_FILINGS = 25

_OWNERSHIP_FORMS = frozenset({"3", "4", "5"})

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


@dataclass(frozen=True)
class InsiderTransaction:
    form: str
    filed_date: str
    transaction_date: str | None
    insider_name: str
    role: str | None
    code: str
    code_label: str
    direction: str  # "buy" | "sell" | "other"
    shares: float | None
    price: float | None
    plan_type: str  # "scheduled_10b5-1" | "discretionary" | "unstated"
    url: str


@dataclass(frozen=True)
class InsiderFeed:
    ticker: str
    cik: str | None
    window_days: int
    state: str  # "live" | "partial" | "not_available"
    reason: str | None
    buys: int
    sells: int
    other: int
    net_direction: str  # "buying" | "selling" | "mixed" | "none"
    transactions: list[InsiderTransaction]


def _raw_xml_url(xsl_url_or_doc: str, *, cik: int, accession_nodash: str) -> str:
    doc = _XSL_PREFIX_RE.sub("", xsl_url_or_doc)
    return ARCHIVE_URL.format(cik=cik, accession=accession_nodash, document=doc)


def _xsl_display_url(primary_doc: str, *, cik: int, accession_nodash: str) -> str:
    return ARCHIVE_URL.format(cik=cik, accession=accession_nodash, document=primary_doc)


async def _fetch_ownership_submissions(client: httpx.AsyncClient, cik: int) -> dict | None:
    try:
        r = await paced_get(client, SUBMISSIONS_URL.format(cik=cik))
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("edgar_ownership_submissions_error cik=%s error=%s", cik, str(exc)[:200])
        return None


def _select_ownership_refs(
    submissions: dict, cik: int, *, since: date, max_filings: int
) -> tuple[list[dict] | None, bool]:
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
    truncated = len(refs) > max_filings
    return [ref for _, ref in refs[:max_filings]], truncated


def _find_text(elem: ElementTree.Element, path: str) -> str | None:
    found = elem.find(path)
    if found is None or found.text is None:
        return None
    text = found.text.strip()
    return text or None


def _bool_flag(value: str | None) -> bool:
    return (value or "").strip().lower() in ("1", "true")


def _parse_plan_type(root: ElementTree.Element) -> str:
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
    xml_text: str, *, form: str, filed_date: str, url: str
) -> tuple[list[InsiderTransaction] | None, str | None]:
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as exc:
        logger.warning("edgar_ownership_xml_parse_error url=%s error=%s", url, str(exc)[:200])
        stripped = xml_text.lstrip()[:100].lower()
        if "<html" in stripped or "<!doctype html" in stripped:
            return None, "SEC returned an HTML page instead of the ownership XML for this filing"
        return None, "the filing's XML could not be parsed"
    if root.tag != "ownershipDocument":
        logger.warning("edgar_ownership_unexpected_root url=%s tag=%s", url, root.tag)
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


async def _fetch_transactions(
    client: httpx.AsyncClient, ref: dict
) -> tuple[list[InsiderTransaction] | None, str | None]:
    try:
        r = await paced_get(client, ref["raw_url"])
        if r.status_code != 200:
            return None, f"SEC returned HTTP {r.status_code} for this filing"
        return _parse_transactions(r.text, form=ref["form"], filed_date=ref["filed_date"], url=ref["display_url"])
    except httpx.HTTPError as exc:
        logger.warning("edgar_ownership_xml_fetch_error url=%s error=%s", ref.get("raw_url"), str(exc)[:200])
        return None, "SEC EDGAR could not be reached for this filing"


def _summarize(transactions: list[InsiderTransaction]) -> tuple[int, int, int, str]:
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
    return buys, sells, other, net


def _unavailable(ticker: str, window_days: int, reason: str, *, cik: str | None = None) -> InsiderFeed:
    return InsiderFeed(
        ticker=ticker, cik=cik, window_days=window_days,
        state="not_available", reason=reason, buys=0, sells=0, other=0,
        net_direction="none", transactions=[],
    )


async def fetch_insider_feed(
    ticker: str, *, window_days: int = WINDOW_DAYS, max_filings: int = MAX_FILINGS
) -> InsiderFeed:
    sym = ticker.upper().strip()
    try:
        cik = await resolve_cik(sym)
    except CikResolutionUnavailable:
        return _unavailable(sym, window_days, "SEC EDGAR is temporarily unavailable — try again shortly")
    if cik is None:
        return _unavailable(sym, window_days, "No SEC registrant found for this symbol")

    cik_str = f"{cik:010d}"
    since = datetime.now(timezone.utc).date() - timedelta(days=window_days)
    async with httpx.AsyncClient(timeout=FETCH_TIMEOUT_S, headers={"User-Agent": USER_AGENT}) as client:
        submissions = await _fetch_ownership_submissions(client, cik)
        if submissions is None:
            return _unavailable(sym, window_days, "SEC EDGAR is temporarily unavailable — try again shortly", cik=cik_str)
        refs, truncated = _select_ownership_refs(submissions, cik, since=since, max_filings=max_filings)
        if refs is None:
            return _unavailable(sym, window_days, "SEC EDGAR filings index is in an unrecognised format", cik=cik_str)
        if not refs:
            return InsiderFeed(
                ticker=sym, cik=cik_str, window_days=window_days,
                state="live", reason=None, buys=0, sells=0, other=0,
                net_direction="none", transactions=[],
            )

        transactions: list[InsiderTransaction] = []
        fetch_errors: list[str] = []
        for ref in refs:
            parsed, error_reason = await _fetch_transactions(client, ref)
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
        reason = f"Showing the {max_filings} most recent filings in the window"
    else:
        state = "live"
        reason = None

    buys, sells, other, net = _summarize(transactions)
    return InsiderFeed(
        ticker=sym, cik=cik_str, window_days=window_days,
        state=state, reason=reason, buys=buys, sells=sells, other=other,
        net_direction=net, transactions=transactions,
    )


_TRAILER = (
    " A row tagged 10b5-1 was committed under a pre-arranged Rule 10b5-1 plan — "
    "not fresh conviction by the insider; a sale with no plan box ticked "
    "(discretionary) or with plan unstated is the stronger signal. Report what "
    "the filings state; do not infer a motive they do not state."
)


def _fmt_shares(value: float | None) -> str:
    if value is None:
        return "shares not stated"
    return f"{value:,.0f} sh"


def _fmt_price(value: float | None) -> str:
    if value is None:
        return "price not stated"
    return f"@ ${value:,.2f}"


def _render_row(tx: InsiderTransaction) -> str:
    who = tx.insider_name + (f" ({tx.role})" if tx.role else "")
    bits = [f"{tx.code} · {tx.code_label.lower()}", _fmt_shares(tx.shares)]
    if tx.price is not None:
        bits.append(_fmt_price(tx.price))
    if tx.plan_type == "scheduled_10b5-1":
        bits.append("10b5-1")
    txd = f", trade {tx.transaction_date}" if tx.transaction_date else ""
    return f"Form {tx.form} filed {tx.filed_date}{txd}: {who} — " + " · ".join(bits)


def insider_line(feed: InsiderFeed, *, max_rows: int = 5) -> str:
    label = f"Insider trades (SEC Form 3/4/5, last {feed.window_days} days"
    if feed.cik:
        label += f", CIK {feed.cik}"
    label += ")"

    if feed.state == "not_available":
        return (
            f"{label}: NOT AVAILABLE — {feed.reason}. Do not infer insider "
            f"activity from memory or from other fields on this sheet."
        )

    state_note = f" (partial — {feed.reason})" if feed.state == "partial" else ""
    if not feed.transactions:
        return (
            f"{label}{state_note}: none filed in the window per the issuer's SEC "
            f"submissions index. Do not supply insider activity from memory."
        )

    shown = feed.transactions[:max_rows]
    rows = " | ".join(f"[{i}] {_render_row(tx)}" for i, tx in enumerate(shown, 1))
    n = len(feed.transactions)
    count = f"{n} transaction{'s' if n != 1 else ''}"
    if n > len(shown):
        count += f" (newest {len(shown)} shown; {n - len(shown)} older not shown)"
    return (
        f"{label}{state_note}: {feed.buys} buys, {feed.sells} sells, {feed.other} other "
        f"(only codes P/S count as buys/sells; every other code is listed with its "
        f"code label and never counted); net direction: {feed.net_direction}; "
        f"{count}, newest first — {rows}{_TRAILER}"
    )
