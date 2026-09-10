"""8-K Item 5.02 — executive and board changes, in the filing's own words (CR221 I1).

The News Analyst asked, in five of seven CAT convenes, who the incoming CFO
was, where he came from and whether the outgoing one retired or was pushed.
CAT's 2026-04-10 8-K (accession 0001104659-26-042062) states all of it
outright: Kyle Epley, 53, with the company since 1996, succeeds Andrew R.J.
Bonfield, who retires on 2026-10-01. The SEC's submissions index tags every
8-K with its item codes, and 5.02 is "Departure of Directors or Certain
Officers; Election of Directors; Appointment of Certain Officers" — so the
route is the index, then the primary document, then the Item 5.02 section.

**Store-backed, like every other EDGAR slot.** `scripts/ingest_edgar_8k.py`
fetches and parses; the Room reads `edgar_8k_items` and `edgar_8k_scans`
and never touches sec.gov inside a convene.

**Three states, and they must not blur** (CR040):

  * `filed` — the scan covers the window and found Item 5.02 filings in it;
  * `none_in_window` — the scan covers the window and found none. That is a
    dated claim ("none filed between X and Y"), which is why the scan row
    exists: without it, an empty store and a quiet filer look the same;
  * unavailable, with a reason — the store is unreadable, the ticker was
    never scanned, or the scan is too old to vouch for the render window.

An index the ingest could not READ is not an index with nothing on it
(P26): a renamed column, an item string in a new format or an unparseable
date raises `IndexUnreadable` and the ingest writes no scan row, so the
Room says "unscanned", never "none filed".

Item 5.02 is a catch-all (director elections, pay terms, non-C-suite
departures), so the sheet quotes what the filing says and never classifies
it. The excerpt is sentence-bounded and capped — CAT's section leads with the
succession and ends with the pay bullets, and the cap drops the latter.

PURE except `fetch_8k_state` and `ever_scanned`, which touch the store; the
network is the ingest script's.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser

from sqlalchemy import select

from app.core.logging import logger
from app.db.models import Edgar8kItemRow, Edgar8kScanRow
from app.db.session import get_session
from app.services.asof_context import assert_dates_within
from app.services.prompt_safety import sanitize_for_prompt

ITEM_CODE = "5.02"
EXEC_CHANGE_LABEL = "Executive change (8-K Item 5.02)"

RENDER_WINDOW_DAYS = 180
INGEST_WINDOW_DAYS = 365
EXCERPT_CAP = 1200
MAX_ITEMS_RENDERED = 2
_MIN_SECTION_CHARS = 40

EXTRACTED = "extracted"
UNEXTRACTED = "unextracted"
FETCH_FAILED = "fetch_failed"

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"


@dataclass(frozen=True)
class FilingRef:
    accession_no: str
    form: str
    filed: date
    report_date: date | None
    primary_document: str
    item_codes: tuple[str, ...]


@dataclass(frozen=True)
class Item502:
    accession_no: str
    form: str
    filed: date
    report_date: date | None
    extract_status: str
    section_text: str | None


@dataclass(frozen=True)
class Scan:
    scanned_at: datetime
    covered_since: date
    window_days: int


# ── The SEC index ────────────────────────────────────────────────────────────


class IndexUnreadable(ValueError):
    """The submissions JSON is not the index this module knows how to read:
    a column is missing or renamed, the columns disagree in length, an 8-K
    inside the window carries an item string that is not a list of
    `d.dd` codes, or a filing date does not parse. The ingest writes NO scan
    row on this — an unreadable index and a quiet filer must never produce
    the same record (P26, CR040)."""


_REQUIRED_COLUMNS = ("form", "items", "filingDate", "accessionNumber", "primaryDocument")
_ITEM_TOKEN = re.compile(r"^\d{1,2}\.\d{2}$")


def has_item(items: str, code: str = ITEM_CODE) -> bool:
    """Token match on the index's comma-separated item string: "5.02" must
    not match "5.03" or "15.02"."""
    return code in [t.strip() for t in str(items or "").split(",")]


def _item_tokens(items: object, *, row: int) -> tuple[str, ...]:
    tokens = tuple(t.strip() for t in str(items or "").split(",") if t.strip())
    if not tokens or any(not _ITEM_TOKEN.match(t) for t in tokens):
        raise IndexUnreadable(f"row {row}: items {str(items)!r} is not a list of d.dd codes")
    return tokens


def _parse_date(value: object, *, row: int, column: str) -> date | None:
    if value is None or value == "":
        return None
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError) as exc:
        raise IndexUnreadable(f"row {row}: {column} {value!r} does not parse") from exc


def recent_block(submissions: dict) -> dict:
    """`filings.recent` with every column this module reads present and of
    one length, or `IndexUnreadable`. An index with ZERO filings is readable
    (every column present, all empty)."""
    if not isinstance(submissions, dict):
        raise IndexUnreadable("submissions is not an object")
    filings = submissions.get("filings")
    recent = filings.get("recent") if isinstance(filings, dict) else None
    if not isinstance(recent, dict):
        raise IndexUnreadable("filings.recent is missing")
    missing = [c for c in _REQUIRED_COLUMNS if not isinstance(recent.get(c), list)]
    if missing:
        raise IndexUnreadable(f"filings.recent lacks column(s) {', '.join(missing)}")
    lengths = {c: len(recent[c]) for c in _REQUIRED_COLUMNS}
    if len(set(lengths.values())) != 1:
        raise IndexUnreadable(f"filings.recent columns disagree in length: {lengths}")
    return recent


def select_502_filings(submissions: dict, *, since: date) -> list[FilingRef]:
    """Every 8-K (and 8-K/A) in `filings.recent` tagged Item 5.02 and filed on
    or after `since`, newest first. Raises `IndexUnreadable` rather than
    skipping: an 8-K in the window whose items or date cannot be read means
    the index cannot vouch for "none filed"."""
    recent = recent_block(submissions)
    forms = recent["form"]
    report_dates = recent.get("reportDate")
    if not isinstance(report_dates, list) or len(report_dates) != len(forms):
        report_dates = [None] * len(forms)
    refs: list[FilingRef] = []
    for i, form in enumerate(forms):
        form = str(form or "")
        if not form.startswith("8-K"):
            continue
        filed = _parse_date(recent["filingDate"][i], row=i, column="filingDate")
        if filed is None:
            raise IndexUnreadable(f"row {i}: filingDate is empty on an 8-K")
        if filed < since:
            continue
        tokens = _item_tokens(recent["items"][i], row=i)
        if ITEM_CODE not in tokens:
            continue
        refs.append(FilingRef(
            accession_no=str(recent["accessionNumber"][i]),
            form=form,
            filed=filed,
            report_date=_parse_date(report_dates[i], row=i, column="reportDate"),
            primary_document=str(recent["primaryDocument"][i]),
            item_codes=tokens,
        ))
    refs.sort(key=lambda r: r.filed, reverse=True)
    return refs


def covered_since(submissions: dict) -> date | None:
    """The oldest filing date in `filings.recent` — how far back the index
    page the ingest read actually reaches. None for an index with no filings
    at all; `IndexUnreadable` for one whose dates do not parse."""
    recent = recent_block(submissions)
    dates: list[date] = []
    for i, value in enumerate(recent["filingDate"]):
        parsed = _parse_date(value, row=i, column="filingDate")
        if parsed is not None:
            dates.append(parsed)
    return min(dates) if dates else None


def archive_url(cik: int, ref: FilingRef) -> str:
    return ARCHIVE_URL.format(
        cik=cik, accession=ref.accession_no.replace("-", ""), document=ref.primary_document,
    )


# ── The document ─────────────────────────────────────────────────────────────

# Content a human reader of the filing never sees must not reach the prompt:
# these elements, and any element styled invisible (a filer-controlled channel).
_DROP_TAGS = frozenset({
    "script", "style", "title", "ix:header", "noscript", "textarea", "template",
    "iframe", "svg",
})
_VOID_TAGS = frozenset({
    "br", "hr", "img", "input", "meta", "link", "area", "base", "col", "embed",
    "source", "track", "wbr",
})
_BLOCK_TAGS = frozenset({
    "p", "div", "br", "tr", "td", "th", "li", "table", "h1", "h2", "h3", "h4",
})
_HIDDEN_STYLE = re.compile(
    r"display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0(?:\.0*)?\s*(?:p[xt]|em|%|;|$)",
    re.I,
)


def _is_hidden(attrs) -> bool:
    for name, value in attrs or ():
        if name == "hidden":
            return True
        if name == "style" and value and _HIDDEN_STYLE.search(value):
            return True
    return False


class _TextExtractor(HTMLParser):
    """Dropping is a stack of (tag, depth): a dropped element ends at ITS
    matching end tag, nested same-name tags counted, so a hidden `<div>` with
    visible `<div>`s inside it is dropped whole and nothing after it is."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._dropping: list[list] = []  # [tag, depth]

    def handle_starttag(self, tag: str, attrs) -> None:
        if self._dropping:
            if tag == self._dropping[-1][0] and tag not in _VOID_TAGS:
                self._dropping[-1][1] += 1
            return
        if tag in _DROP_TAGS or (tag not in _VOID_TAGS and _is_hidden(attrs)):
            self._dropping.append([tag, 1])
            return
        if tag in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self._dropping:
            if tag == self._dropping[-1][0]:
                self._dropping[-1][1] -= 1
                if self._dropping[-1][1] == 0:
                    self._dropping.pop()
            return
        if tag in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._dropping:
            self._parts.append(data)

    def text(self) -> str:
        lines = (" ".join(line.split()) for line in "".join(self._parts).split("\n"))
        return "\n".join(line for line in lines if line)


def html_to_text(html: str) -> str:
    """Visible text of an inline-XBRL 8-K, one line per block, with the
    `<ix:header>` hidden facts, script/style/title/noscript/template/iframe/
    svg/textarea and anything styled invisible dropped."""
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    return parser.text()


# A heading STARTS a block line of `html_to_text`; an in-body cross-reference
# does not ("The information set forth in Item 5.02 of this Current Report …",
# "filed pursuant to Item 5.02 of Form 8-K", AAPL's "called for by Item
# 5.02(c)(3) of Form 8-K"). Anchoring on the line start is what keeps a
# reference in Item 1.01 from being read as the section, and a reference
# inside the section from cutting it short — either would have been labelled
# "complete, the filing's own words". No parenthesis lookahead: Alphabet's
# 2026-06-05 8-K heads its section "Item 5.02(c) Appointment of Principal
# Officer", and that IS the heading.
_HEADING_502 = re.compile(r"^\s*Item\s*5\.02\b", re.I | re.M)
_NEXT_HEADING = re.compile(r"^\s*(?:Item\s*\d{1,2}\.\d\d\b|SIGNATURES?\b)", re.I | re.M)


def extract_item_502(html: str) -> str | None:
    """The Item 5.02 section as ONE sanitised line, or None when no heading
    starts a line or no candidate section is long enough to be one. The
    first line-start heading whose section clears the floor wins, so a
    line-start reference ahead of the real heading is passed over."""
    text = html_to_text(html)
    for heading in _HEADING_502.finditer(text):
        tail = _NEXT_HEADING.search(text, heading.end())
        end = tail.start() if tail else len(text)
        section = sanitize_for_prompt(text[heading.start():end])
        if len(section) >= _MIN_SECTION_CHARS:
            return section
    return None


_ITEM_PREFIX = re.compile(r"^\s*Item\s*5\.02(?:\s*\([a-z0-9]{1,2}\))*\s*[.:]?\s*", re.I)
_REG_SK_CAPTION = re.compile(
    r"^Departure of Directors or Certain Officers;\s*Election of Directors;\s*"
    r"Appointment of Certain Officers(?:;\s*Compensatory Arrangements of Certain Officers)?\.?\s*",
    re.I,
)


def strip_item_title(section: str) -> str:
    """Drop the "Item 5.02" prefix and the Reg S-K caption so the excerpt
    starts on the filing's own sentence. Removes nothing else."""
    body = _ITEM_PREFIX.sub("", section, count=1)
    return _REG_SK_CAPTION.sub("", body, count=1)


_SENTENCE_END = re.compile(r"[.!?][\"”’)]?\s")
# A period after one of these is not a sentence end ("Mr. Epley", "Andrew R.J.
# Bonfield", "Caterpillar Inc."). Cutting there would leave a dangling name.
_ABBREVIATION = re.compile(r"(?:\b(?:Mr|Mrs|Ms|Dr|Inc|Co|Corp|Ltd|No|Jr|Sr|St|vs)|\b[A-Z])$")


def excerpt(section: str, cap: int = EXCERPT_CAP) -> tuple[str, bool, int]:
    """(text, truncated, full_len). The read side never trusts the row: the
    text is re-sanitised here. A cut lands on the last sentence end inside
    `cap` when one sits past 40% of it; otherwise a hard cut with an ellipsis."""
    s = sanitize_for_prompt(section)
    full_len = len(s)
    if full_len <= cap:
        return s, False, full_len
    cut = 0
    for m in _SENTENCE_END.finditer(s):
        if m.end() > cap:
            break
        if _ABBREVIATION.search(s[: m.start()]):
            continue
        cut = m.end()
    if cut >= cap * 0.4:
        return s[:cut].rstrip(), True, full_len
    return s[:cap].rstrip() + "…", True, full_len


# ── The store ────────────────────────────────────────────────────────────────


def fetch_8k_state(ticker: str, as_of: date) -> tuple[Scan | None, list[Item502]]:
    """The newest scan for `ticker` and the Item 5.02 rows of ITS CIK filed
    inside the render window ending at `as_of`, newest first. Items are read
    by CIK, not ticker: the ingest dedups on `(cik, accession_no)`, so a
    filing stored under GOOGL must show for GOOG (same CIK) rather than
    letting GOOG read as a quiet filer. `filed <= as_of` in SQL and
    re-asserted after (the PIT property). RAISES on store failure — the
    caller decides what a missing store costs. No scan → no items: without
    a scan there is no window to read them against."""
    sym = ticker.upper().strip()
    since = as_of - timedelta(days=RENDER_WINDOW_DAYS)
    scan_stmt = (
        select(Edgar8kScanRow)
        .where(Edgar8kScanRow.ticker == sym)
        .order_by(Edgar8kScanRow.scanned_at.desc())
        .limit(1)
    )
    with get_session() as session:
        scan_row = session.execute(scan_stmt).scalars().first()
        rows = []
        scan = None
        if scan_row is not None:
            item_stmt = (
                select(Edgar8kItemRow)
                .where(Edgar8kItemRow.cik == scan_row.cik)
                .where(Edgar8kItemRow.filed <= as_of)
                .where(Edgar8kItemRow.filed >= since)
                .order_by(Edgar8kItemRow.filed.desc())
            )
            rows = session.execute(item_stmt).scalars().all()
            scanned_at = scan_row.scanned_at
            # sqlite hands a tz-aware column back naive; the ingest writes UTC.
            if scanned_at.tzinfo is None:
                scanned_at = scanned_at.replace(tzinfo=timezone.utc)
            scan = Scan(
                scanned_at=scanned_at,
                covered_since=scan_row.covered_since,
                window_days=int(scan_row.window_days),
            )
        items = [
            Item502(
                accession_no=r.accession_no,
                form=r.form,
                filed=r.filed,
                report_date=r.report_date,
                extract_status=r.extract_status,
                section_text=r.section_text,
            )
            for r in rows
        ]
    assert_dates_within([i.filed for i in items], as_of, origin="edgar_8k.fetch_8k_state")
    return scan, items


def ever_scanned() -> bool:
    """Has the ingest ever written a scan row for ANY ticker? The loud-degrade
    probe that tells "never ran" from "this ticker is not on the list"."""
    with get_session() as session:
        return session.execute(select(Edgar8kScanRow.id).limit(1)).first() is not None


# ── The sheet line ───────────────────────────────────────────────────────────

_TRAILER = (
    " Item 5.02 also covers director elections and pay terms — report the role "
    "and circumstance the filing names; do not infer a reason it does not state."
)


def _gap_sentence(unverified_days: object, v_through: str) -> str:
    """The days between the scan and the sheet's run date are a hole the
    line must name: a "none filed through X" read on X+120 is not "none
    filed"."""
    try:
        gap = int(unverified_days or 0)
    except (TypeError, ValueError):
        gap = 0
    if gap <= 0:
        return ""
    return (
        f" The {gap} day{'s' if gap != 1 else ''} after {v_through}, up to this sheet's run "
        f"date, {'are' if gap != 1 else 'is'} NOT verified — a filing in that gap would not "
        f"appear here."
    )


def executive_change_line(
    state: str | None,
    items: list[dict] | None,
    verified_from: str | None,
    verified_through: str | None,
    *,
    live: bool = True,
    total: int | None = None,
    unverified_days: int | None = None,
) -> str | None:
    """The sheet line, or None when the state is not a live one. Every string
    lifted from an item passes `sanitize_for_prompt` here, at the seam, and
    the excerpt is re-capped here too — the profile dict is not trusted for
    length any more than for content. `total` is the count of Item 5.02
    filings in the verified window (the overlay renders at most
    MAX_ITEMS_RENDERED of them); the line states the true count and says how
    many are shown, never a count the scan contradicts."""
    if state not in ("filed", "none_in_window") or not verified_from or not verified_through:
        return None
    marker = " (LIVE)" if live else ""
    v_from = sanitize_for_prompt(verified_from)
    v_through = sanitize_for_prompt(verified_through)
    basis = (
        f"(the issuer's SEC 8-K index, item code 5.02, verified by AMI's SEC scan "
        f"through {v_through})"
    )
    gap = _gap_sentence(unverified_days, v_through)
    if state == "none_in_window":
        return (
            f"{EXEC_CHANGE_LABEL}{marker}: none filed between {v_from} and {v_through} "
            f"{basis}.{gap} Do not supply one from memory."
        )
    if not items:
        return None
    shown = items[:MAX_ITEMS_RENDERED]
    parts: list[str] = []
    for i, item in enumerate(shown, 1):
        form = sanitize_for_prompt(item.get("form"))
        filed = sanitize_for_prompt(item.get("filed"))
        report_date = sanitize_for_prompt(item.get("report_date")) or "not stated"
        accession = sanitize_for_prompt(item.get("accession_no"))
        age = item.get("age_days")
        head = (
            f"[{i}] {form} filed {filed} ({age} days before this sheet's run date; "
            f"event date {report_date}; accession {accession})"
        )
        raw = item.get("excerpt")
        if raw is None:
            parts.append(
                head + ": tagged Item 5.02 by the SEC index but its text could not be "
                "extracted — the filing exists; its content is not supplied."
            )
            continue
        clean = sanitize_for_prompt(raw)
        recapped = len(clean) > EXCERPT_CAP + 1  # excerpt() yields at most cap + "…"
        ex = clean[:EXCERPT_CAP].rstrip() + "…" if recapped else clean
        truncated = bool(item.get("truncated")) or recapped
        full_len = max(int(item.get("full_len") or 0), len(clean))
        bounded = ", sentence-bounded" if truncated and not ex.endswith("…") else ""
        parts.append(
            head
            + f"; the filing's own words, {'opening sentences' if truncated else 'complete'} "
            f"({len(ex):,} of {full_len:,} chars{bounded}): \"{ex}\""
        )
    n_shown = len(shown)
    try:
        n = max(int(total or 0), len(items))
    except (TypeError, ValueError):
        n = len(items)
    count = f"{n} filing{'s' if n != 1 else ''}"
    if n > n_shown:
        count += f" (newest {n_shown} shown; {n - n_shown} older not shown)"
    return (
        f"{EXEC_CHANGE_LABEL}{marker}: {count} between {v_from} and {v_through} {basis}, "
        f"newest first — " + " | ".join(parts) + gap + _TRAILER
    )
