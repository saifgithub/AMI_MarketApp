"""Bursa Malaysia PN17/GN3 list: parse, store, change-detect, and the Bursa fact-sheet line (CR286).

Why. The terminal question (CR267 v2) can only evidence a PN17/GN3 risk from the Room's own
materials, and a Bursa Room carries no filings. Bursa publishes the list of affected issuers
on one public page; AMI reads it once a week (`scripts/bursa_pn17_refresh.py`) and states each
stock's status on the sheet with the date of the read. Since 2025 an issuer under Main Market
paragraph 8.03A is an "affected listed issuer" and is not tagged PN17, so the list carries all
three categories.

Boundaries (CR286, coordinator): facts only. The tables hold stock code, company name, market,
a NORMALISED category and group, and first/last-seen dates. No Bursa page text is stored or
shown. The group is mapped onto a closed vocabulary here, never copied from the page.

This module does no network I/O: the script fetches (one request), this module parses the
text it is handed. Degrade loudly (CR040): a refused, unparsable or implausible read never
touches the stored list; `status_for` turns a list older than `STALE_AFTER_DAYS` into an
explicit "unavailable" line, never a quietly old answer.
"""

from __future__ import annotations

import csv
import io
import re
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.db import get_session
from app.db.ami_claim import claim
from app.db.models import BursaPn17ChangeRow, BursaPn17CurrentRow, BursaPn17RunRow

SOURCE_URL = (
    "https://www.bursamalaysia.com/trade/trading_resources/listing_directory/pn17_and_gn3_companies"
)
USER_AGENT = "AMI-Trade-PN17-refresh/1.0 (weekly; contact via app)"
STALE_AFTER_DAYS = 14
#: A read that drops below this share of the stored list is held back as implausible.
SHRINK_FLOOR = 0.5
#: Below this stored size the shrink check is not meaningful.
SHRINK_MIN_STORED = 4

CATEGORY_PN17 = "pn17"
CATEGORY_GN3 = "gn3"
CATEGORY_AFFECTED = "affected_listed_issuer_8_03a"
CATEGORY_UNCLASSIFIED = "unclassified"

TRADING = "trading"
SUSPENDED = "suspended"
_TRADING_STATUSES = (TRADING, SUSPENDED)

OUTCOME_OK = "ok"
OUTCOME_REFUSED = "refused"
OUTCOME_PARSE_FAILED = "parse_failed"
OUTCOME_FETCH_FAILED = "fetch_failed"

TRIGGER_WEEKLY = "weekly"
TRIGGER_MANUAL = "manual"

_CODE_RE = re.compile(r"^[0-9]{4}[A-Z0-9]{0,2}$")
_REFUSED_STATUSES = frozenset({401, 403, 429, 451, 503})
_CHALLENGE_MARKERS = ("just a moment", "challenges.cloudflare.com", "cf-chl", "attention required")


class ParseFailed(Exception):
    """The page could not be read as a list, or the read is implausible. Never wipes."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Row:
    stock_code: str
    company_name: str
    market: str  # Main | ACE | Unknown
    status_category: str
    status_group: str | None = None
    trading_status: str | None = None  # trading | suspended | None (not known)


@dataclass(frozen=True)
class Seed:
    """A parsed human-entered seed: the rows plus Bursa's own "Last updated" date, if given."""

    rows: list[Row]
    bursa_updated: date | None = None


def classify_response(status_code: int, body: str) -> str | None:
    """OUTCOME_REFUSED / OUTCOME_FETCH_FAILED for a response that is not a readable page, else None."""
    low = body[:4000].lower()
    if status_code in _REFUSED_STATUSES or any(m in low for m in _CHALLENGE_MARKERS):
        return OUTCOME_REFUSED
    if status_code != 200:
        return OUTCOME_FETCH_FAILED
    return None


# --------------------------------------------------------------------------- parsing


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _market_of(text: str) -> str:
    low = text.lower()
    if re.search(r"\bace\b", low):
        return "ACE"
    if re.search(r"\bmain\b", low):
        return "Main"
    return "Unknown"


def _category_of(text: str, market: str) -> str:
    low = text.lower()
    if "8.03a" in low or "affected listed issuer" in low:
        return CATEGORY_AFFECTED
    if "gn3" in low or market == "ACE":
        return CATEGORY_GN3
    if "pn17" in low or market == "Main":
        return CATEGORY_PN17
    return CATEGORY_UNCLASSIFIED


def _group_of(text: str) -> str | None:
    low = text.lower()
    if "uplift" in low:
        return "plan_approved_awaiting_uplift"
    if "under review" in low or "under evaluation" in low or "under consideration" in low:
        return "plan_under_review"
    if "pending" in low:
        return "pending_plan"
    if "approved" in low:
        return "plan_approved"
    return None


def _role(header: str) -> str | None:
    low = header.lower()
    if "code" in low or low == "stock":
        return "code"
    if "company" in low or "issuer" in low or "name" in low:
        return "name"
    if "market" in low:
        return "market"
    if any(k in low for k in ("status", "category", "group", "classification")):
        return "category"
    return None


@dataclass
class _Table:
    context: str
    rows: list[list[str]] = field(default_factory=list)
    header_rows: list[list[str]] = field(default_factory=list)


class _PageReader(HTMLParser):
    """Collects every table with the heading text that precedes it. No page text outlives the parse."""

    _HEADINGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6", "caption"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[_Table] = []
        self._headings: list[tuple[int, str]] = []
        self._level = 0
        self._in_heading = False
        self._heading_buf: list[str] = []
        self._table: _Table | None = None
        self._row: list[str] | None = None
        self._row_has_th = False
        self._cell: list[str] | None = None
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag in self._HEADINGS:
            self._in_heading, self._heading_buf = True, []
            self._level = int(tag[1]) if tag != "caption" else 0
        elif tag == "table":
            self._table = _Table(context=" | ".join(t for _, t in self._headings))
        elif tag == "tr" and self._table is not None:
            self._row, self._row_has_th = [], False
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
            self._row_has_th = self._row_has_th or tag == "th"

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
        elif tag in self._HEADINGS and self._in_heading:
            self._in_heading = False
            text = _norm(" ".join(self._heading_buf))
            if text and self._level == 0 and self._table is not None:
                self._table.context = f"{self._table.context} | {text}"
            elif text and self._level:
                self._headings = [(lv, t) for lv, t in self._headings if lv < self._level]
                self._headings.append((self._level, text))
        elif tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(_norm(" ".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._row is not None and self._table is not None:
            if any(self._row):
                (self._table.header_rows if self._row_has_th else self._table.rows).append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None

    def handle_data(self, data):
        if self._skip:
            return
        if self._cell is not None:
            self._cell.append(data)
        elif self._in_heading:
            self._heading_buf.append(data)


def parse_page(html: str) -> list[Row]:
    """Rows from every table that has a stock-code column and a company column.

    Raises ParseFailed: no recognisable table, a non-empty code that is not a Bursa stock
    code, a stock code listed twice, or zero rows. Strictness is the point: a page whose
    structure changed must fail loudly, not yield a partial list.
    """
    reader = _PageReader()
    reader.feed(html)
    reader.close()
    out: dict[str, Row] = {}
    recognised = False
    for table in reader.tables:
        header = table.header_rows[0] if table.header_rows else (table.rows[0] if table.rows else [])
        by_role: dict[str, int] = {}
        for i, h in enumerate(header):
            role = _role(h)
            if role and role not in by_role:
                by_role[role] = i
        if "code" not in by_role or "name" not in by_role:
            continue
        recognised = True
        body = table.rows if table.header_rows else table.rows[1:]
        for cells in body:
            def cell(role: str, _cells: list[str] = cells) -> str:
                i = by_role.get(role)
                return _cells[i] if i is not None and i < len(_cells) else ""

            code = cell("code").upper().replace(" ", "")
            if not code:
                continue
            if not _CODE_RE.match(code):
                raise ParseFailed("malformed_stock_code")
            name = cell("name")
            if not name:
                raise ParseFailed("missing_company_name")
            context = " ".join(filter(None, (table.context, cell("market"), cell("category"))))
            market = _market_of(f"{cell('market')} {table.context}")
            if code in out:
                raise ParseFailed("duplicate_stock_code")
            out[code] = Row(
                stock_code=code, company_name=name[:120], market=market,
                status_category=_category_of(context, market),
                status_group=_group_of(context),
            )
    if not recognised:
        raise ParseFailed("no_recognised_table")
    if not out:
        raise ParseFailed("zero_rows")
    return list(out.values())


def parse_seed(text: str, *, today: date | None = None) -> Seed:
    """A human-entered seed (CR286 What 4):
    `stock_code,company_name,market,status_category[,status_group][,trading_status][,bursa_updated]`.

    `bursa_updated` is Bursa's own "Last updated" date (ISO). It must be one date across every
    row that carries it, well formed and not after `today`; anything else is refused, never
    guessed. Old files without the two newer columns stay valid.
    """
    today = today or datetime.now(timezone.utc).date()
    reader = csv.DictReader(io.StringIO(text))
    need = {"stock_code", "company_name", "market", "status_category"}
    if not reader.fieldnames or not need <= set(reader.fieldnames):
        raise ParseFailed("seed_columns")
    categories = {CATEGORY_PN17, CATEGORY_GN3, CATEGORY_AFFECTED, CATEGORY_UNCLASSIFIED}
    out: dict[str, Row] = {}
    updated: set[date] = set()
    for r in reader:
        code = (r["stock_code"] or "").strip().upper()
        if not _CODE_RE.match(code):
            raise ParseFailed("malformed_stock_code")
        if code in out:
            raise ParseFailed("duplicate_stock_code")
        cat = (r["status_category"] or "").strip()
        market = (r["market"] or "").strip()
        trading = (r.get("trading_status") or "").strip().lower() or None
        if cat not in categories or market not in ("Main", "ACE", "Unknown"):
            raise ParseFailed("seed_vocabulary")
        if trading is not None and trading not in _TRADING_STATUSES:
            raise ParseFailed("seed_vocabulary")
        raw_date = (r.get("bursa_updated") or "").strip()
        if raw_date:
            try:
                parsed = date.fromisoformat(raw_date)
            except ValueError:
                raise ParseFailed("seed_bursa_updated") from None
            if parsed > today:
                raise ParseFailed("seed_bursa_updated")
            updated.add(parsed)
        out[code] = Row(
            code, _norm(r["company_name"] or "")[:120], market, cat,
            (r.get("status_group") or "").strip() or None, trading,
        )
    if len(updated) > 1:
        raise ParseFailed("seed_bursa_updated")
    if not out:
        raise ParseFailed("zero_rows")
    return Seed(list(out.values()), next(iter(updated), None))


def parse_csv(text: str, *, today: date | None = None) -> list[Row]:
    return parse_seed(text, today=today).rows


# --------------------------------------------------------------------------- storage


@dataclass(frozen=True)
class Applied:
    added: int
    changed: int
    removed: int


def apply_snapshot(
    session: Session, rows: Iterable[Row], *, run_id: uuid.UUID, today: date,
    source_url: str = SOURCE_URL, accept_shrink: bool = False,
) -> Applied:
    """Move the stored list to `rows`, logging every change. Raises ParseFailed BEFORE any write
    when the read would wipe most of a non-trivial list (an implausible read, not a news event)."""
    snapshot = {r.stock_code: r for r in rows}
    existing = {c.stock_code: c for c in session.execute(select(BursaPn17CurrentRow)).scalars()}
    if (
        not accept_shrink
        and len(existing) >= SHRINK_MIN_STORED
        and len(snapshot) < len(existing) * SHRINK_FLOOR
    ):
        raise ParseFailed("implausible_shrink")

    added = changed = removed = 0

    def log_change(
        kind: str, r: Row | BursaPn17CurrentRow, previous: str | None = None,
        previous_trading: str | None = None,
    ) -> None:
        session.add(BursaPn17ChangeRow(
            run_id=run_id, change_type=kind, stock_code=r.stock_code, company_name=r.company_name,
            market=r.market, status_category=r.status_category, status_group=r.status_group,
            previous_category=previous, trading_status=r.trading_status,
            previous_trading_status=previous_trading, observed_on=today, source_url=source_url,
        ))

    for row in snapshot.values():
        claimed = claim(
            session, BursaPn17CurrentRow, key={"stock_code": row.stock_code},
            values={
                "company_name": row.company_name, "market": row.market,
                "status_category": row.status_category, "status_group": row.status_group,
                "trading_status": row.trading_status,
                "first_seen": today, "last_seen": today, "source_url": source_url,
            },
        )
        if claimed.created:
            added += 1
            log_change("added", row)
            continue
        current = claimed.row
        previous = current.status_category
        if previous != row.status_category:
            changed += 1
            log_change("category_changed", row, previous)
        previous_trading = current.trading_status
        if previous_trading and row.trading_status and previous_trading != row.trading_status:
            changed += 1
            log_change("trading_changed", row, previous_trading=previous_trading)
        current.company_name = row.company_name
        current.market = row.market
        current.status_category = row.status_category
        current.status_group = row.status_group
        current.trading_status = row.trading_status
        current.last_seen = today
        current.source_url = source_url

    for code, current in existing.items():
        if code not in snapshot:
            removed += 1
            log_change("removed", current)
            session.delete(current)
    return Applied(added, changed, removed)


def record_run(
    session: Session, *, run_id: uuid.UUID, trigger: str, outcome: str, started_at: datetime,
    http_status: int | None = None, rows_found: int = 0, applied: Applied | None = None,
    detail: str | None = None, source_url: str = SOURCE_URL, finished_at: datetime | None = None,
    bursa_updated: date | None = None,
) -> None:
    session.add(BursaPn17RunRow(
        id=run_id, started_at=started_at, finished_at=finished_at or datetime.now(timezone.utc),
        trigger=trigger, outcome=outcome, http_status=http_status, rows_found=rows_found,
        added=applied.added if applied else 0, changed=applied.changed if applied else 0,
        removed=applied.removed if applied else 0, detail=(detail or None),
        bursa_updated_on=bursa_updated if outcome == OUTCOME_OK else None, source_url=source_url,
    ))


# --------------------------------------------------------------------------- the sheet line


STATE_LISTED = "listed"
STATE_NOT_LISTED = "not_listed"
STATE_STALE = "stale"
STATE_UNAVAILABLE = "unavailable"

_LABELS = {
    CATEGORY_PN17: "listed as a PN17 issuer",
    CATEGORY_GN3: "listed as a GN3 issuer",
    CATEGORY_AFFECTED: "listed as an affected listed issuer (Main Market paragraph 8.03A)",
    CATEGORY_UNCLASSIFIED: "on Bursa's PN17/GN3 page (category not classified by AMI)",
}
_GROUPS = {
    "pending_plan": "plan pending",
    "plan_under_review": "plan under review",
    "plan_approved": "plan approved",
    "plan_approved_awaiting_uplift": "plan approved, awaiting uplift",
}
_FAILURES = {
    OUTCOME_REFUSED: "Bursa's site refused the request",
    OUTCOME_PARSE_FAILED: "the page could not be read as a list",
    OUTCOME_FETCH_FAILED: "the page could not be fetched",
}
_SOURCE_PHRASE = "Source: Bursa Malaysia PN17 and GN3 list, read weekly by AMI."
_NO_MEMORY = "Do not state a PN17 or GN3 status from memory."


@dataclass(frozen=True)
class Status:
    state: str
    as_of: date | None = None
    row: Row | None = None
    first_seen: date | None = None
    baseline: date | None = None
    reason: str | None = None
    last_failure: tuple[date, str] | None = None
    bursa_updated: date | None = None


def stock_code_of(ticker: str) -> str:
    return ticker.upper().removesuffix(".KL")


def status_for(ticker: str, today: date, *, session: Session | None = None) -> Status:
    """The ticker's status from the stored list. Any read failure is `unavailable`, logged."""
    try:
        if session is not None:
            return _status(session, ticker, today)
        with get_session() as s:
            return _status(s, ticker, today)
    except Exception as exc:
        logger.error(
            "bursa_pn17_status_unreadable", ticker=ticker, error=f"{type(exc).__name__}: {exc}"[:200],
        )
        return Status(STATE_UNAVAILABLE, reason="AMI's stored copy of Bursa's list could not be read")


def _status(session: Session, ticker: str, today: date) -> Status:
    runs = session.execute(
        select(BursaPn17RunRow).order_by(BursaPn17RunRow.finished_at.desc())
    ).scalars().all()
    ok = [r for r in runs if r.outcome == OUTCOME_OK]
    last_failure = None
    if runs and runs[0].outcome != OUTCOME_OK:
        last_failure = (runs[0].finished_at.date(), runs[0].outcome)
    if not ok:
        return Status(
            STATE_UNAVAILABLE, last_failure=last_failure,
            reason="AMI has no successful read of Bursa's list on record",
        )
    as_of = ok[0].finished_at.date()
    baseline = ok[-1].finished_at.date()
    bursa_updated = ok[0].bursa_updated_on
    if (today - as_of).days > STALE_AFTER_DAYS:
        logger.warn("bursa_pn17_list_stale", as_of=as_of.isoformat(), today=today.isoformat())
        return Status(
            STATE_STALE, as_of=as_of, baseline=baseline, last_failure=last_failure,
            bursa_updated=bursa_updated,
        )
    code = stock_code_of(ticker)
    cur = session.execute(
        select(BursaPn17CurrentRow).where(BursaPn17CurrentRow.stock_code == code)
    ).scalars().first()
    if cur is None:
        return Status(
            STATE_NOT_LISTED, as_of=as_of, baseline=baseline, last_failure=last_failure,
            bursa_updated=bursa_updated,
        )
    return Status(
        STATE_LISTED, as_of=as_of, baseline=baseline, first_seen=cur.first_seen,
        row=Row(
            cur.stock_code, cur.company_name, cur.market, cur.status_category, cur.status_group,
            cur.trading_status,
        ),
        last_failure=last_failure, bursa_updated=bursa_updated,
    )


def historical_status() -> Status:
    return Status(
        STATE_UNAVAILABLE,
        reason="AMI's list is a current read and does not describe a past date",
    )


def _read_phrase(st: Status) -> str:
    """How current Bursa's list is, and when AMI read it. Bursa's date is stated only when known."""
    read = f"read by AMI {st.as_of.isoformat()}" if st.as_of else "read by AMI"
    if st.bursa_updated:
        return f"Bursa's list updated {st.bursa_updated.isoformat()}, {read}"
    return read


def line(st: Status) -> str:
    """The sheet line. The same words, bracketed, are the desk footer note (`note`)."""
    if st.state == STATE_LISTED and st.row and st.as_of:
        r = st.row
        where = f"{r.market} Market" if r.market in ("Main", "ACE") else None
        grp = _GROUPS.get(r.status_group or "")
        trading = {SUSPENDED: "trading suspended", TRADING: "trading"}.get(r.trading_status or "")
        paren = ", ".join(p for p in (where, grp, trading) if p)
        seen = st.first_seen.isoformat() if st.first_seen else "unknown"
        since = (
            f"already on Bursa's list when AMI first read it ({seen})"
            if st.first_seen and st.baseline and st.first_seen <= st.baseline
            else f"first seen on Bursa's list {seen}"
        )
        body = (
            f"Bursa PN17/GN3 status: {_LABELS.get(r.status_category, _LABELS[CATEGORY_UNCLASSIFIED])}"
            f"{f' ({paren})' if paren else ''}; {since}; {_read_phrase(st)}. {_SOURCE_PHRASE}"
        )
    elif st.state == STATE_NOT_LISTED and st.as_of:
        body = (
            "Bursa PN17/GN3 status: not on Bursa's PN17/GN3 list "
            f"({_read_phrase(st)}). {_SOURCE_PHRASE}"
        )
    elif st.state == STATE_STALE and st.as_of:
        body = (
            "Bursa PN17/GN3 status: unavailable; AMI's copy of Bursa's list is stale "
            f"(last successful read {st.as_of.isoformat()}). {_NO_MEMORY}"
        )
    else:
        body = (
            f"Bursa PN17/GN3 status: unavailable; {st.reason or 'the list could not be read'}. "
            f"{_NO_MEMORY}"
        )
    if st.last_failure:
        when, outcome = st.last_failure
        body += f" The latest refresh attempt ({when.isoformat()}) failed: {_FAILURES.get(outcome, outcome)}."
    return body


def note(st: Status) -> str:
    return f"[AMI note: {line(st)}]"
