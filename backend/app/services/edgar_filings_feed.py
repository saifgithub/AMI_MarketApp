"""CR244 Part 2 slice 1 — the issuer's recent SEC filings INDEX (form type +
filed date + plain label, no document text), read by the News Analyst and the
Fundamentals Analyst.

Deliberately narrow, and the exact shape the CR names: no document text, no
MD&A/risk-factor extraction (that is a non-goal — no parser for it exists
anywhere in this codebase), just the same submissions-JSON filings index
`company_profile.py` (CR244 Part 1) already fetches and parses, windowed and
capped for a prompt line instead of a 6-tab screen.

Reuses `company_profile._fetch_company_submissions` and `_form_label`/
`_FORM_LABELS` (the same form→label map, Form 3/4/5(+/A) and Form 144(+/A)
excluded — all insider-related, slice 2) rather than a second fetch or a
second label scheme. `edgar_cik.resolve_cik`/`CikResolutionUnavailable` and
`edgar_cik.paced_get` are the same resolver and rate limiter every other
CR244 EDGAR read in this backend uses — no second CIK cache, no second
pacing clock.

Point-in-time (CR040): a filing's `filed` date is immutable once public, so
a historical/as-of convene filters to `filed_date <= as_of` — the same
"knowable on that date" contract `asof_context.py` states for the rest of
the Room's EDGAR reads. `recent_filings_line` takes `as_of` explicitly and
never reads the wall clock itself.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.services.company_profile import (
    _OWNERSHIP_FORMS,
    _fetch_company_submissions,
    _form_label,
)
from app.services.edgar_cik import CikResolutionUnavailable, resolve_cik
from app.services.prompt_safety import sanitize_for_prompt

WINDOW_DAYS = 180
MAX_FILINGS = 10

FEED_LABEL = "Recent SEC filings"

# Form 144 (proposed insider sale notice) is insider-related like 3/4/5 —
# slice 2's territory, not this feed's. Matched with its amendment suffix
# the same way `_OWNERSHIP_FORMS` matches 3/A, 4/A, 5/A.
_FORM_144 = frozenset({"144", "144/A"})
_EXCLUDED_FORMS = _OWNERSHIP_FORMS | _FORM_144

_TRAILER = (
    " Report the form and filed date only — do not infer a filing's contents "
    "or the issuer's reasons from its type or timing."
)


def _filings_index(
    submissions: dict, *, since: date, as_of: date,
) -> list[dict[str, Any]] | None:
    """Newest-first, capped at MAX_FILINGS, excluding insider forms
    (3/4/5/144 and amendments), filed within `[since, as_of]`. None on a
    submissions shape this parser doesn't recognise — mirrors
    `edgar_8k.IndexUnreadable`'s "don't guess" rule rather than a partial,
    silently-wrong list."""
    filings = submissions.get("filings")
    recent = filings.get("recent") if isinstance(filings, dict) else None
    if not isinstance(recent, dict):
        return None
    forms = recent.get("form")
    filed_dates = recent.get("filingDate")
    if not isinstance(forms, list) or not isinstance(filed_dates, list):
        return None
    n = len(forms)
    if len(filed_dates) != n:
        return None
    primary_descs = recent.get("primaryDocDescription")
    if not isinstance(primary_descs, list) or len(primary_descs) != n:
        primary_descs = [None] * n

    items: list[tuple[date, dict[str, Any]]] = []
    for i in range(n):
        form = str(forms[i] or "")
        if form in _EXCLUDED_FORMS:
            continue
        raw_date = filed_dates[i]
        if not raw_date:
            continue
        try:
            filed = date.fromisoformat(str(raw_date))
        except ValueError:
            continue
        if not (since <= filed <= as_of):
            continue
        items.append((filed, {
            "form": form,
            "label": _form_label(form, primary_descs[i]),
            "filed_date": filed.isoformat(),
        }))
    items.sort(key=lambda t: t[0], reverse=True)
    return [item for _, item in items[:MAX_FILINGS]]


def fetch_recent_filings(ticker: str, as_of: date) -> tuple[str, list[dict[str, Any]] | None]:
    """(state, items). `state` is one of:

      "live"          — items is the (possibly empty) filings index, PIT-filtered.
      "not_available" — no CIK, an EDGAR outage, or an unreadable index; items is None.

    A CIK-mapped issuer can legitimately have filed nothing non-insider in
    the last 180 days (a quiet quarter) — that is `"live"` with an empty
    list, not `"not_available"`; unlike the 8-K precedent's "a mapped CIK
    never has zero filings" rule, 180 days is a much narrower window than a
    full-history index, so an empty result here is ordinary, not suspicious.
    """
    sym = ticker.upper().strip()
    try:
        cik = resolve_cik(sym)
    except CikResolutionUnavailable:
        return "not_available", None
    if cik is None:
        return "not_available", None
    submissions = _fetch_company_submissions(cik)
    if submissions is None:
        return "not_available", None
    since = as_of - timedelta(days=WINDOW_DAYS)
    items = _filings_index(submissions, since=since, as_of=as_of)
    if items is None:
        return "not_available", None
    return "live", items


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
