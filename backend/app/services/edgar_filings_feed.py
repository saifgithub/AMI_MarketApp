"""CR244 Part 2 slice 1 — the issuer's recent SEC filings INDEX (form type +
filed date + plain label, no document text), read by the News Analyst and the
Fundamentals Analyst.

Deliberately narrow, and the exact shape the CR names: no document text, no
MD&A/risk-factor extraction (that is a non-goal — no parser for it exists
anywhere in this codebase), just the same submissions-JSON filings index
`company_profile.py` (CR244 Part 1) already fetches and parses, windowed and
capped for a prompt line instead of a 6-tab screen.

Reuses `edgar_submissions.fetch_company_submissions`/`form_label`/
`classify_filing` (the shared fetch, label map, and filer-vs-subject role
classifier — audit B1/M3) rather than a second fetch or a second label/
exclusion scheme. `edgar_cik.resolve_cik`/`CikResolutionUnavailable` is the
same resolver every other CR244 EDGAR read in this backend uses — no second
CIK cache.

**Role-based exclusions (audit B1).** `filings.recent` mixes rows that are
NOT "this issuer's own regulatory activity" in the way an agent would read
them: a Schedule 13D/13G where the issuer is merely the SUBJECT of someone
else's ownership report reads very differently from one where the issuer
itself is the FILER of a stake in another company, and neither reads like a
13F-HR/N-PX (the issuer acting as an investment manager, about OTHER
companies). `classify_filing` (`edgar_submissions.py`) tells these apart via
`fileNumber`; this feed:

  - EXCLUDES `issuer_as_investor` rows (13F-HR/13F-NT/N-PX, and a 13D/13G
    where the issuer is the filer) — these are about a DIFFERENT company,
    not this one.
  - EXCLUDES `correspondence` rows (CORRESP/UPLOAD) — their `filingDate` is
    when it hit EDGAR, not any public-release date, so treating it as a
    knowable-on-that-date fact would leak into a backtest (PIT violation).
  - EXCLUDES `25-NSE` — an exchange notice of removal from listing, often
    filed for a debt/preferred series rather than the common stock; the form
    code alone can't tell an agent which, so it's misreadable as "the stock
    was delisted" and is excluded rather than mislabelled.
  - INCLUDES `about_issuer` rows (a 13D/13G where the issuer is the
    SUBJECT — a >=5% holder reporting a stake IN this issuer), relabelled to
    say so explicitly rather than carry `company_profile.py`'s generic
    "Beneficial ownership statement" wording, which reads as if the issuer
    filed it.

The existing exclusions (Form 3/4/5 + Form 144, and their amendments) stay —
both insider-related, slice 2's territory (Bull/Bear), not this feed's.

Point-in-time (CR040): a filing's `filed` date is immutable once public, so
a historical/as-of convene filters to `filed_date <= as_of` — the same
"knowable on that date" contract `asof_context.py` states for the rest of
the Room's EDGAR reads. `recent_filings_line` takes `as_of` explicitly and
never reads the wall clock itself. `assert_dates_within` re-asserts this
after filtering, the same structural check every other as-of read path in
this backend runs.

**As-of coverage (audit B2).** `filings.recent` covers only "at least 1 year
or 1000 filings" per SEC's own documentation — for a heavy filer (JPM, GS),
`recent`'s oldest row can be as young as ~1 year back, so an `as_of` further
back than that would otherwise render a false "none in the window" from a
window `recent` never covered. When `since` (the window's left edge) is
older than `recent`'s own oldest filed date, this fetches whichever
`filings.files` page(s) overlap `[since, as_of]` (paced, same GET as the
main submissions fetch) and merges their rows in. A page fetch failure
returns `not_available` with a reason — never a truncated list rendered as
live (CR040): a caller cannot tell "genuinely quiet" from "we couldn't read
far enough back" if both look the same.

**Caching (audit M2).** Per-CIK: the submissions JSON (and any `files` pages
fetched for as-of coverage) are cached ~6h on success, ~5min on failure —
same TTLs `company_profile.py` uses for the identical shape of read, so a
transient SEC outage doesn't lock a symbol out for 6h once it clears. The
as-of window filter runs AFTER the cache read, never baked into the cached
value, so one cached submissions payload serves every `as_of` a backtest
sweep asks for. The convene-path fetch uses a short (5s) timeout — a hung
SEC endpoint should delay a convene by seconds, not the ~15-30s a full-page
timeout would cost.
"""

from __future__ import annotations

import threading
import time
from datetime import date, timedelta
from typing import Any

import httpx

from app.core.logging import logger
from app.services.asof_context import assert_dates_within
from app.services.edgar_cik import USER_AGENT, CikResolutionUnavailable, paced_get, resolve_cik
from app.services.edgar_submissions import (
    OWNERSHIP_FORMS,
    classify_filing,
    form_label,
)
from app.services.prompt_safety import sanitize_for_prompt

WINDOW_DAYS = 180
MAX_FILINGS = 10

FEED_LABEL = "Recent SEC filings"

# Form 144 (proposed insider sale notice) is insider-related like 3/4/5 —
# slice 2's territory, not this feed's. Matched with its amendment suffix
# the same way `OWNERSHIP_FORMS` matches 3/A, 4/A, 5/A.
_FORM_144 = frozenset({"144", "144/A"})
_EXCLUDED_FORMS = OWNERSHIP_FORMS | _FORM_144

# Never mislabel-or-include: an exchange delisting notice whose form code
# alone can't say whether it concerns the common stock or a debt/preferred
# series (audit B1).
_FORM_25_NSE = frozenset({"25-NSE"})

_TRAILER = (
    " Report the form and filed date only — do not infer a filing's contents "
    "or the issuer's reasons from its type or timing."
)

_FETCH_TIMEOUT_S = 5.0  # M2: short — a hung SEC read must delay a convene by
# seconds, not the ~15-30s a full-page timeout would cost.
_TTL_SECONDS = 6 * 60 * 60.0
_DEGRADED_TTL_SECONDS = 5 * 60.0
_MAX_CACHE_ENTRIES = 512

_lock = threading.RLock()
# cik -> (submissions_dict_or_None, cached_at). None on a cached failure
# (negative cache) — distinct from "not yet fetched" (key absent).
_cache: dict[int, tuple[dict | None, float]] = {}
# (cik, page_name) -> (page_dict_or_None, cached_at)
_page_cache: dict[tuple[int, str], tuple[dict | None, float]] = {}


def clear_filings_feed_cache() -> None:
    with _lock:
        _cache.clear()
        _page_cache.clear()


def _sweep_locked(now: float) -> None:
    for store in (_cache, _page_cache):
        expired = [
            k for k, (val, cached_at) in store.items()
            if (now - cached_at) >= (_TTL_SECONDS if val is not None else _DEGRADED_TTL_SECONDS)
        ]
        for k in expired:
            del store[k]
        if len(store) >= _MAX_CACHE_ENTRIES:
            for k, _ in sorted(store.items(), key=lambda kv: kv[1][1])[: len(store) - _MAX_CACHE_ENTRIES + 1]:
                store.pop(k, None)


def _fetch_company_submissions(cik: int) -> dict | None:
    """Convene-path fetch: short timeout (M2), same URL/pacing/User-Agent as
    `edgar_submissions.fetch_company_submissions`, kept as its own function
    (rather than reusing that one directly) only so this module's shorter
    timeout doesn't change the Filings-tab read's own 15s budget."""
    from app.services.edgar_8k import SUBMISSIONS_URL

    url = SUBMISSIONS_URL.format(cik=cik)
    try:
        with httpx.Client(timeout=_FETCH_TIMEOUT_S, headers={"User-Agent": USER_AGENT}) as client:
            r = paced_get(client, url)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warn("edgar_recent_filings_submissions_fetch_error", cik=cik, error=str(exc)[:200])
        return None


def _fetch_submissions_page(cik: int, name: str) -> dict | None:
    url = f"https://data.sec.gov/submissions/{name}"
    try:
        with httpx.Client(timeout=_FETCH_TIMEOUT_S, headers={"User-Agent": USER_AGENT}) as client:
            r = paced_get(client, url)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warn("edgar_recent_filings_page_fetch_error", cik=cik, name=name, error=str(exc)[:200])
        return None


def _cached_submissions(cik: int) -> dict | None:
    """Per-CIK cache (M2): 6h on success, 5min negative cache on failure.
    The as-of window filter is applied by the CALLER, after this read —
    never baked into the cached value, so one fetch serves every `as_of` a
    backtest sweep asks for."""
    now = time.monotonic()
    with _lock:
        cached = _cache.get(cik)
        if cached is not None:
            ttl = _TTL_SECONDS if cached[0] is not None else _DEGRADED_TTL_SECONDS
            if (now - cached[1]) < ttl:
                return cached[0]
    result = _fetch_company_submissions(cik)
    with _lock:
        _sweep_locked(time.monotonic())
        _cache[cik] = (result, time.monotonic())
    return result


def _cached_submissions_page(cik: int, name: str) -> dict | None:
    key = (cik, name)
    now = time.monotonic()
    with _lock:
        cached = _page_cache.get(key)
        if cached is not None:
            ttl = _TTL_SECONDS if cached[0] is not None else _DEGRADED_TTL_SECONDS
            if (now - cached[1]) < ttl:
                return cached[0]
    result = _fetch_submissions_page(cik, name)
    with _lock:
        _sweep_locked(time.monotonic())
        _page_cache[key] = (result, time.monotonic())
    return result


def _row_included(form: str, file_number: str | None) -> bool:
    if form in _EXCLUDED_FORMS or form in _FORM_25_NSE:
        return False
    role = classify_filing(form, file_number)
    return role in ("issuer", "about_issuer")


def _label_for_row(form: str, file_number: str | None, primary_doc_description: str | None) -> str:
    """Audit B1: an `about_issuer` 13D/13G must not read as the issuer's own
    filing — relabelled explicitly rather than `edgar_submissions.form_label`'s
    generic "Beneficial ownership statement" wording."""
    role = classify_filing(form, file_number)
    if role == "about_issuer":
        if form in ("SC 13G", "SCHEDULE 13G", "SC 13G/A", "SCHEDULE 13G/A"):
            suffix = " (amended)" if form.endswith("/A") else ""
            return f"Filed by a >=5% holder reporting a stake in this issuer (13G, passive{suffix})"
        suffix = " (amended)" if form.endswith("/A") else ""
        return f"Filed by a >=5% holder reporting a stake in this issuer (13D, active{suffix})"
    return form_label(form, primary_doc_description)


def _rows_from_recent(recent: dict) -> list[tuple[date, str, str | None, str]] | None:
    """[(filed, form, file_number, label)], newest-first not yet applied —
    caller windows/sorts/caps. None on a shape this parser doesn't recognise."""
    forms = recent.get("form")
    filed_dates = recent.get("filingDate")
    if not isinstance(forms, list) or not isinstance(filed_dates, list):
        return None
    n = len(forms)
    if len(filed_dates) != n:
        return None
    file_numbers = recent.get("fileNumber")
    if not isinstance(file_numbers, list) or len(file_numbers) != n:
        file_numbers = [None] * n
    primary_descs = recent.get("primaryDocDescription")
    if not isinstance(primary_descs, list) or len(primary_descs) != n:
        primary_descs = [None] * n

    out: list[tuple[date, str, str | None, str]] = []
    for i in range(n):
        form = str(forms[i] or "")
        fn = file_numbers[i]
        if not _row_included(form, fn):
            continue
        raw_date = filed_dates[i]
        if not raw_date:
            continue
        try:
            filed = date.fromisoformat(str(raw_date))
        except ValueError:
            continue
        out.append((filed, form, fn, _label_for_row(form, fn, primary_descs[i])))
    return out


def _filings_index(
    submissions: dict, *, since: date, as_of: date,
) -> list[dict[str, Any]] | None:
    """Newest-first, capped at MAX_FILINGS, role-excluded (audit B1) and
    windowed to `[since, as_of]`. None on a submissions shape this parser
    doesn't recognise — mirrors `edgar_8k.IndexUnreadable`'s "don't guess"
    rule rather than a partial, silently-wrong list."""
    filings = submissions.get("filings")
    recent = filings.get("recent") if isinstance(filings, dict) else None
    if not isinstance(recent, dict):
        return None
    rows = _rows_from_recent(recent)
    if rows is None:
        return None
    items = [
        (filed, {"form": form, "label": label, "filed_date": filed.isoformat()})
        for filed, form, _fn, label in rows
        if since <= filed <= as_of
    ]
    items.sort(key=lambda t: t[0], reverse=True)
    return [item for _, item in items[:MAX_FILINGS]]


def _recent_oldest_filed(recent: dict) -> date | None:
    dates = recent.get("filingDate") if isinstance(recent, dict) else None
    if not isinstance(dates, list) or not dates:
        return None
    parsed = []
    for raw in dates:
        try:
            parsed.append(date.fromisoformat(str(raw)))
        except (ValueError, TypeError):
            continue
    return min(parsed) if parsed else None


def _overlapping_pages(files_index: Any, since: date, as_of: date) -> list[str]:
    """`filings.files[i].name` for every page whose [filingFrom, filingTo]
    overlaps `[since, as_of]` — a heavy filer's older history, paginated out
    of `filings.recent` (audit B2)."""
    if not isinstance(files_index, list):
        return []
    names: list[str] = []
    for page in files_index:
        if not isinstance(page, dict):
            continue
        name = page.get("name")
        frm_raw, to_raw = page.get("filingFrom"), page.get("filingTo")
        if not name or not frm_raw or not to_raw:
            continue
        try:
            frm = date.fromisoformat(str(frm_raw))
            to = date.fromisoformat(str(to_raw))
        except ValueError:
            continue
        if frm <= as_of and to >= since:
            names.append(str(name))
    return names


def fetch_recent_filings(ticker: str, as_of: date) -> tuple[str, list[dict[str, Any]] | None]:
    """(state, items). `state` is one of:

      "live"          — items is the (possibly empty) filings index, PIT-filtered.
      "not_available" — no CIK, an EDGAR outage, an unreadable index, or a
                         needed `filings.files` page that could not be
                         fetched (audit B2 — never a truncated list rendered
                         as live); items is None.

    A CIK-mapped issuer can legitimately have filed nothing non-insider,
    non-`issuer_as_investor`, non-correspondence in the last 180 days (a
    quiet quarter) — that is `"live"` with an empty list, not
    `"not_available"`; unlike the 8-K precedent's "a mapped CIK never has
    zero filings" rule, 180 days is a much narrower window than a full-
    history index, so an empty result here is ordinary, not suspicious.
    """
    sym = ticker.upper().strip()
    try:
        cik = resolve_cik(sym)
    except CikResolutionUnavailable:
        return "not_available", None
    if cik is None:
        return "not_available", None
    submissions = _cached_submissions(cik)
    if submissions is None:
        return "not_available", None
    since = as_of - timedelta(days=WINDOW_DAYS)

    filings = submissions.get("filings")
    recent = filings.get("recent") if isinstance(filings, dict) else None
    if not isinstance(recent, dict):
        return "not_available", None

    rows = _rows_from_recent(recent)
    if rows is None:
        return "not_available", None

    # Audit B2: `filings.recent` only covers "at least 1 year or 1000
    # filings" — for a heavy filer, its oldest row can be within the window
    # we need. When it doesn't reach back far enough, fetch the overlapping
    # `filings.files` page(s) and merge before windowing, rather than
    # silently rendering whatever `recent` alone happened to cover.
    oldest_recent = _recent_oldest_filed(recent)
    if oldest_recent is not None and oldest_recent > since:
        files_index = filings.get("files") if isinstance(filings, dict) else None
        page_names = _overlapping_pages(files_index, since, as_of)
        for name in page_names:
            page = _cached_submissions_page(cik, name)
            if page is None:
                logger.warn(
                    "edgar_recent_filings_page_unavailable",
                    ticker=sym, cik=cik, page=name,
                )
                return "not_available", None
            page_rows = _rows_from_recent(page)
            if page_rows is None:
                return "not_available", None
            rows.extend(page_rows)

    items = [
        (filed, {"form": form, "label": label, "filed_date": filed.isoformat()})
        for filed, form, _fn, label in rows
        if since <= filed <= as_of
    ]
    items.sort(key=lambda t: t[0], reverse=True)
    capped = [item for _, item in items[:MAX_FILINGS]]
    assert_dates_within(
        [date.fromisoformat(i["filed_date"]) for i in capped], as_of,
        origin="edgar_filings_feed.fetch_recent_filings",
    )
    return "live", capped


def recent_filings_line(state: str | None, items: list[dict[str, Any]] | None) -> str | None:
    """The sheet line, or None when the state is not `"live"`. Every string
    lifted from an item passes `sanitize_for_prompt` at this render seam,
    the same discipline `edgar_8k.executive_change_line` applies — the
    profile dict is not trusted for content any more than for length."""
    if state != "live" or items is None:
        return None
    if not items:
        return f"{FEED_LABEL}: none in the last {WINDOW_DAYS} days.{_TRAILER}"
    parts = []
    for item in items:
        form = sanitize_for_prompt(item.get("form"))
        label = sanitize_for_prompt(item.get("label"))
        filed = sanitize_for_prompt(item.get("filed_date"))
        parts.append(f"{form} — {label} — filed {filed}")
    return (
        f"{FEED_LABEL} (newest first, last {WINDOW_DAYS} days, max {MAX_FILINGS}): "
        + "; ".join(parts) + "." + _TRAILER
    )
