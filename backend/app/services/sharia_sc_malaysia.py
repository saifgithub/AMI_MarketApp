"""Securities Commission Malaysia — Shariah-compliant securities list (CR282 lane D).

The second Sharia standard AMI reads: the list the SC's Shariah Advisory Council (SAC)
publishes twice a year (effective the last Friday of May and November) for the
Bursa Malaysia Main / ACE / LEAP markets. Like the US standard it is a *sourced
allowlist* — AMI reads the published list and issues no ruling of its own.

What the file is (verified 2026-11-23 against the 29 May 2026 release):

- A PDF booklet, not a spreadsheet. The download URL is
  `https://www.sc.com.my/api/documentms/download.ashx?id=<GUID>` and the GUID changes on
  every release, so the stable thing to configure is the SC's INDEX page, which embeds
  the release list as JSON (`name` / `file_path` / `date_published`). `discover_list_url`
  reads the newest entry off it.
- The booklet carries three tables up front (Table 1: securities newly classified
  compliant; Table 2: securities newly classified NON-compliant; Table 3: counts by
  sector, whose "Total" row is the full compliant count and the Main/ACE/LEAP universe
  size), then the FULL compliant list: `<n>. <stock code> <name>` rows by market and
  sector, ending at "ADDITIONAL LIST" (Islamic REITs / ETFs / funds / business trusts,
  which the SC keeps in separate files). Stock codes are four digits (Main), or five
  starting `0` (ACE / LEAP: `03068`).
- So the file does NOT list every non-compliant security — only those newly reclassified
  (Table 2). The complement of the full compliant list, within Main/ACE/LEAP equities,
  IS the non-compliant set (the SC classifies every listed security; 886 of 1,099 were
  compliant as at 21 May 2026). `HalalUniverse(absent_screened_out=True)` encodes that:
  a `.KL` ticker absent from the list resolves SCREENED_OUT, not UNKNOWN. The accepted
  over-block: REITs, ETFs and business trusts live in the "additional list" files this
  parser does not read, so they resolve SCREENED_OUT too — the safe direction for a
  halal mandate, and stated in the verdict text rather than hidden.

Integrity (degrade loudly, CR040): the parsed compliant count must equal the booklet's own
Table 3 total. A mismatch — a layout change, a truncated download, a dropped page —
raises `ShariaSourceError`; the refresher keeps serving the held snapshot and logs, and
the reader pauses loudly once the held list ages past `sharia_sc_staleness_days`.

Pure parsing is separated from I/O: `parse_sc_list_text` takes extracted text and is
what the tests exercise; `fetch_sc_list` is the only function that opens a socket.
"""

from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass
from datetime import date, datetime

import httpx

from app.core.config import settings
from app.core.logging import logger
from app.trading_math.markets import Market, spec_for
from app.services.sharia_universe import ShariaSourceError

# `sharia_universe_snapshots.standard` key for this list.
STANDARD_KEY = "SC_MALAYSIA"
# What a verdict says. The source text is the one the CR282 acceptance names.
STANDARD_LABEL = "SC Malaysia"
SOURCE = "SC Malaysia Shariah Advisory Council list of Shariah-compliant securities"
COVERAGE = "Bursa Malaysia"

_SUFFIX = spec_for(Market.MY).yahoo_suffix  # ".KL"

# Honest identification, same as the US fetches. sc.com.my serves a plain client fine
# (checked 2026-11-23); no browser impersonation.
_USER_AGENT = "AMI-Trade/1.0 (+https://agenticmarketintel.ai)"
_FETCH_TIMEOUT_S = 45.0
_MAX_PDF_BYTES = 25 * 1024 * 1024

# A parse below this is truncated/garbled: the May 2026 list held 886 names.
_SC_MIN_ROWS = 500

# `<n>. <code> <name…>`: the row number, a 4-5 digit stock code (optionally a trailing
# letter), then the name. The two-column layout of Tables 1-2 puts two rows on one
# line, so this is matched with `finditer` over the section text, not line by line.
# The dot after the row number is optional: the 29 May 2026 booklet prints two rows
# ("1 0452", "2 0308" in ACE Property) without it, and the Table 3 cross-check below is
# what caught the 2 securities a dot-only pattern silently dropped.
_ROW_RE = re.compile(r"(?<![\w.])(\d{1,4})\.?\s+(\d{4,5}[A-Z]?)\s+(?=\S)")
_TABLE2_RE = re.compile(r"Table\s*2\s*:")
_TABLE3_RE = re.compile(r"Table\s*3\b")
# Heading that opens the full list ("LIST OF SHARIAH-COMPLIANT SECURITIES – MAY 2026").
_LIST_HEAD_RE = re.compile(r"LIST OF SHARIAH-COMPLIANT SECURITIES\s*[–—-]\s*[A-Z]+\s+\d{4}")
# Where the full list stops. pypdf may emit the "ADDITIONAL LIST" heading AFTER the
# trailing business-trust table, so the earliest of these markers wins.
_LIST_END_RE = re.compile(
    r"ADDITIONAL LIST|Please refer to the Securities Commission|"
    r"Shariah Status for Companies Seeking Listing|Islamic unit trust funds|Islamic business trust"
)
_TOTAL_RE = re.compile(r"Total\s+Jumlah\s+(\d[\d,]*)\s+(\d[\d,]*)")
_EFFECTIVE_RE = re.compile(
    r"takes\s+effect\s+from\s+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", re.IGNORECASE
)
# The cover prints the date in capitals ("29 MAY 2026"); case-sensitive on purpose, so the
# roster-date footnote ("* As at 21 May 2026") can never stand in for the effective date.
_COVER_DATE_RE = re.compile(r"\b(\d{1,2})\s+(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|"
                            r"SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s+(\d{4})\b")
_FOOTER_PREFIXES = (
    "Shariah Advisory Council of the Securities",
    "List of Shariah-Compliant Securities",
    "No.",
    "Bil.",
    "Stock",
    "Kod stok",
    "Name",
    "Nama",
)


@dataclass(frozen=True)
class ScSecurity:
    code: str  # as the SC prints it: "1155", "03068"
    name: str

    @property
    def ticker(self) -> str:
        return f"{self.code}{_SUFFIX}"


@dataclass(frozen=True)
class ScList:
    as_of: date
    compliant: tuple[ScSecurity, ...]
    non_compliant: tuple[ScSecurity, ...]  # Table 2 only: the NEWLY reclassified
    declared_total: int | None  # Table 3 "Total" — the integrity cross-check
    source_url: str = ""

    @property
    def compliant_tickers(self) -> frozenset[str]:
        return frozenset(s.ticker for s in self.compliant)

    @property
    def non_compliant_tickers(self) -> frozenset[str]:
        return frozenset(s.ticker for s in self.non_compliant)


def _clean_name(raw: str) -> str:
    """Keep the wrapped-name continuation lines, drop the page furniture and the
    all-caps sector headings that follow a table's last row."""
    kept: list[str] = []
    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith(_FOOTER_PREFIXES) or s.startswith("====="):
            break
        if s.isdigit():  # bare page number
            break
        if s == s.upper() and any(c.isalpha() for c in s) and len(s) > 3:
            break  # sector / market heading
        kept.append(s)
    name = re.sub(r"\s+", " ", " ".join(kept)).strip()
    return name.split(" * ")[0].strip()  # drop the "* For Sophisticated Investors" footnote


def _rows(section: str) -> list[ScSecurity]:
    matches = list(_ROW_RE.finditer(section))
    out: list[ScSecurity] = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(section)
        out.append(ScSecurity(code=m.group(2), name=_clean_name(section[m.end():end])))
    return out


_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}


def _date(day: str, month: str, year: str) -> date | None:
    mm = _MONTHS.get(month.lower())
    if mm is None:
        return None
    try:
        return date(int(year), mm, int(day))
    except ValueError:
        return None


def parse_sc_list_text(
    text: str, *, source_url: str = "", min_rows: int | None = None
) -> ScList:
    """Parse the booklet's extracted text into an `ScList`.

    Raises `ShariaSourceError` when the structure is not recognised, the effective date is
    missing, the compliant count is below the floor, or it disagrees with the booklet's own
    Table 3 total — never returns a short or undated list."""
    m_eff = _EFFECTIVE_RE.search(text) or _COVER_DATE_RE.search(text)
    as_of = _date(*m_eff.groups()) if m_eff else None
    if as_of is None:
        raise ShariaSourceError("SC list: no effective date found")

    head = _LIST_HEAD_RE.search(text)
    if head is None:
        raise ShariaSourceError("SC list: full-list heading not found")
    end = _LIST_END_RE.search(text, head.end())
    full = text[head.end(): end.start() if end else len(text)]
    compliant = _rows(full)

    non_compliant: list[ScSecurity] = []
    t2 = _TABLE2_RE.search(text)
    if t2 is not None:
        t3 = _TABLE3_RE.search(text, t2.end())
        non_compliant = _rows(text[t2.end(): t3.start() if t3 else head.start()])

    tickers = {s.ticker for s in compliant}
    if len(tickers) != len(compliant):
        raise ShariaSourceError(
            f"SC list: {len(compliant) - len(tickers)} duplicate stock code(s) in the compliant list"
        )
    min_rows = _SC_MIN_ROWS if min_rows is None else min_rows
    if len(compliant) < min_rows:
        raise ShariaSourceError(
            f"SC list parsed to {len(compliant)} securities (< floor {min_rows}) "
            f"— treating as truncated, refusing to enforce a short universe"
        )

    declared: int | None = None
    m_total = _TOTAL_RE.search(text)
    if m_total is not None:
        declared = int(m_total.group(1).replace(",", ""))
        if declared != len(compliant):
            raise ShariaSourceError(
                f"SC list: parsed {len(compliant)} compliant securities but the booklet's own "
                f"Table 3 total is {declared} — layout changed or pages missing"
            )
    else:
        logger.warning("sharia_sc_total_not_found", parsed=len(compliant))

    overlap = {s.ticker for s in non_compliant} & tickers
    if overlap:
        raise ShariaSourceError(
            f"SC list: {len(overlap)} code(s) appear as both compliant and non-compliant"
        )
    return ScList(
        as_of=as_of,
        compliant=tuple(compliant),
        non_compliant=tuple(non_compliant),
        declared_total=declared,
        source_url=source_url,
    )


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """PDF -> text via pypdf (imported lazily: a missing wheel fails the SC fetch loudly,
    it must not stop the app importing)."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - deploy-config failure
        raise ShariaSourceError("pypdf is not installed — cannot read the SC list PDF") from exc
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        raise ShariaSourceError(f"SC list PDF unreadable: {exc}") from exc


_ENTRY_RE = re.compile(
    r'"name"\s*:\s*"(?P<name>[^"]*)"\s*,\s*"file_path"\s*:\s*"(?P<url>[^"]+)"\s*,\s*'
    r'"date_published"\s*:\s*"(?P<date>[^"]+)"'
)


def discover_list_url(index_html: str) -> str:
    """Newest release's file URL off the SC index page (embedded `$X.PPG` JSON).
    Newest = latest `date_published`; raises if the page carries no release entries."""
    best: tuple[date, str] | None = None
    for m in _ENTRY_RE.finditer(index_html):
        try:
            d = datetime.strptime(m.group("date"), "%b %d, %Y").date()
        except ValueError:
            continue
        url = json.loads(f'"{m.group("url")}"')  # un-escape \/ and &
        if best is None or d > best[0]:
            best = (d, url)
    if best is None:
        raise ShariaSourceError("SC index page carried no list releases — page layout changed")
    return best[1]


def fetch_sc_list(client: httpx.Client, url: str) -> ScList:
    """The ONLY socket in this module. `url` is either the SC index page (newest release
    discovered from it) or a direct PDF link."""
    resp = client.get(url)
    resp.raise_for_status()
    if "pdf" in resp.headers.get("content-type", "").lower() or resp.content[:5] == b"%PDF-":
        pdf_url, pdf = url, resp.content
    else:
        pdf_url = discover_list_url(resp.text)
        r2 = client.get(pdf_url)
        r2.raise_for_status()
        pdf = r2.content
    if len(pdf) > _MAX_PDF_BYTES or pdf[:5] != b"%PDF-":
        raise ShariaSourceError(f"SC list download is not a PDF of sane size ({len(pdf)} bytes)")
    return parse_sc_list_text(extract_pdf_text(pdf), source_url=pdf_url)


def network_sc_fetch() -> tuple[frozenset, date, frozenset, str]:
    """-> (compliant tickers, as_of, explicit non-compliant tickers, resolved file URL)."""
    with httpx.Client(
        timeout=_FETCH_TIMEOUT_S,
        headers={"User-Agent": _USER_AGENT},
        follow_redirects=True,
    ) as client:
        sc = fetch_sc_list(client, settings.sharia_sc_list_url)
    return sc.compliant_tickers, sc.as_of, sc.non_compliant_tickers, sc.source_url
