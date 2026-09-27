"""CR244 slice-1 audit (B1/M3) — the ONE shared submissions-JSON fetch, form
label map, and filing-role classifier every CR244 EDGAR-submissions reader
uses: `company_profile.py` (the Filings tab) and `edgar_filings_feed.py` (the
Room agent feed). Before this module the two kept independent copies of the
fetch/label/exclusion logic, which is how the audit's filer-vs-subject bug
(B1) went unnoticed in one copy while the other never had it.

**The core finding this module exists to fix.** In an issuer's
`filings.recent` block, SCHEDULE 13D/13G rows (and their legacy "SC 13D"/
"SC 13G" spellings, and all "/A" amendments) appear in BOTH directions —
the issuer can be the SUBJECT of someone else's beneficial-ownership report,
or the FILER reporting its OWN stake in a different company. `filings.recent`
does not separate these; only the `fileNumber` field does (verified live,
2026-09-27, NVDA CIK 1045810):

- `fileNumber` starting `"005-"` — a **Schedule 13D/G file number**, assigned
  to the SUBJECT company being reported on. Example: accession
  0002100119-26-000017 (Vanguard reporting a >=5% NVDA stake), fileNumber
  `"005-56649"` — the "005-56649" file number is NVDA's, reused across every
  13D/G filed ABOUT it by any filer.
- `fileNumber` empty (`""`) — the issuer itself is the FILER, reporting a
  stake it holds in someone else. Example: accession 0001045810-26-000062
  (NVIDIA reporting its own stake in Nebius), fileNumber `""`.

13F-HR/13F-NT/N-PX (+/A) rows carry a DIFFERENT file-number series
(`"028-…"`, an investment-manager registration number) — verified on NVDA's
own 13F-HR/N-PX rows, both `"028-23915"`. These are always the issuer ACTING
AS an investment manager reporting on OTHER companies' shares; never about
the issuer's own stock.

`classify_filing` is the single decision point every caller routes through,
so "which rows are about THIS issuer's own stock" is answered once, not
copied and drifted per caller.
"""

from __future__ import annotations

from typing import Literal

import httpx

from app.core.logging import logger
from app.services.edgar_8k import SUBMISSIONS_URL
from app.services.edgar_cik import USER_AGENT, paced_get

_SUBMISSIONS_FETCH_TIMEOUT_S = 15.0

FilingRole = Literal["issuer", "about_issuer", "issuer_as_investor", "correspondence"]

# Form 3/4/5 belong to the Insider tab (edgar_ownership.py) — excluded by
# every CR244 submissions reader regardless of amendment suffix (4/A etc.).
OWNERSHIP_FORMS = frozenset({"3", "3/A", "4", "4/A", "5", "5/A"})

# Schedule 13D/13G, both spellings SEC has used, all amendments. A row here
# is EITHER about the issuer (subject-side) or by the issuer (filer-side,
# `issuer_as_investor`) — `classify_filing` tells them apart via `fileNumber`.
_SCHEDULE_13D_13G_FORMS = frozenset({
    "SC 13D", "SC 13D/A", "SC 13G", "SC 13G/A",
    "SCHEDULE 13D", "SCHEDULE 13D/A", "SCHEDULE 13G", "SCHEDULE 13G/A",
})

# The issuer acting as an INVESTMENT MANAGER reporting on other companies'
# shares — never about the issuer's own stock. `fileNumber` for these is a
# "028-…" manager-registration number, distinct from a 13D/G's "005-…"
# subject file number, but the form type alone is already unambiguous.
_INVESTMENT_MANAGER_FORMS = frozenset({"13F-HR", "13F-HR/A", "13F-NT", "13F-NT/A", "N-PX", "N-PX/A"})

# SEC correspondence, not a public disclosure about the issuer's business at
# all — a comment-letter reply (CORRESP) or an EDGAR-system document upload
# (UPLOAD). Their `filingDate` is the date it hit EDGAR, not any public-
# release date the way a 10-K/8-K's is, so a backtest treating it as
# "public knowledge on this date" would leak process noise into a sheet.
_CORRESPONDENCE_FORMS = frozenset({"CORRESP", "UPLOAD"})

FORM_LABELS: dict[str, str] = {
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
    "S-3ASR": "Registration statement (automatic shelf)",
    "S-8": "Employee stock plan registration",
    "S-8 POS": "Employee stock plan registration (post-effective)",
    "424B1": "Prospectus",
    "424B2": "Prospectus",
    "424B3": "Prospectus",
    "424B4": "Prospectus",
    "424B5": "Prospectus",
    "SC 13D": "Beneficial ownership statement",
    "SC 13D/A": "Beneficial ownership statement (amended)",
    "SC 13G": "Beneficial ownership statement (passive)",
    "SC 13G/A": "Beneficial ownership statement (passive, amended)",
    "SCHEDULE 13D": "Beneficial ownership statement",
    "SCHEDULE 13D/A": "Beneficial ownership statement (amended)",
    "SCHEDULE 13G": "Beneficial ownership statement (passive)",
    "SCHEDULE 13G/A": "Beneficial ownership statement (passive, amended)",
    "11-K": "Employee stock plan annual report",
    "25": "Notice of delisting",
    "25-NSE": "Exchange notice of removal from listing",
    "6-K": "Foreign private issuer report",
    "20-F": "Foreign private issuer annual report",
    "144": "Notice of proposed insider sale (Form 144)",
    "144/A": "Notice of proposed insider sale (amended)",
    "SD": "Conflict minerals disclosure",
    "FWP": "Free writing prospectus",
    "13F-HR": "Institutional investment manager holdings report",
    "13F-HR/A": "Institutional investment manager holdings report (amended)",
    "13F-NT": "Institutional investment manager notice",
    "13F-NT/A": "Institutional investment manager notice (amended)",
    "N-PX": "Proxy voting record",
    "N-PX/A": "Proxy voting record (amended)",
    "ARS": "Annual report to shareholders",
    "425": "Business combination communication",
    "CORRESP": "SEC correspondence",
    "UPLOAD": "SEC correspondence",
}


def form_label(form: str, primary_doc_description: str | None) -> str:
    label = FORM_LABELS.get(form)
    if label:
        return label
    if primary_doc_description:
        return str(primary_doc_description)
    return form


def classify_filing(form: str, file_number: str | None) -> FilingRole:
    """The role a submissions-JSON row plays relative to ITS OWN issuer.

    - `"issuer"` — an ordinary filing by the issuer about itself (10-K, 8-K,
      DEF 14A, S-1, ...), the default for anything not otherwise classified.
    - `"about_issuer"` — a Schedule 13D/13G where the issuer is the SUBJECT:
      a third party is reporting a >=5% stake IN this issuer. `fileNumber`
      starts `"005-"` (verified live, NVDA 0002100119-26-000017, Vanguard
      reporting on NVDA, fileNumber "005-56649").
    - `"issuer_as_investor"` — the issuer acting as the FILER: either a
      Schedule 13D/13G reporting the issuer's OWN stake in someone else
      (`fileNumber` empty — verified live, NVDA 0001045810-26-000062,
      NVIDIA's stake in Nebius, fileNumber ""), or a 13F-HR/13F-NT/N-PX row
      (the issuer filing as a registered investment manager, about OTHER
      companies' shares — form type alone is unambiguous, no fileNumber
      check needed).
    - `"correspondence"` — CORRESP/UPLOAD: SEC correspondence, not a public
      disclosure with a real release date.

    Form 3/4/5(+/A) and Form 144(+/A) are NOT classified here — both callers
    exclude them upstream (Insider tab / Bull-Bear territory, not this
    module's concern) before this function ever sees them.
    """
    if form in _CORRESPONDENCE_FORMS:
        return "correspondence"
    if form in _INVESTMENT_MANAGER_FORMS:
        return "issuer_as_investor"
    if form in _SCHEDULE_13D_13G_FORMS:
        fn = (file_number or "").strip()
        if fn.startswith("005-"):
            return "about_issuer"
        return "issuer_as_investor"
    return "issuer"


def fetch_company_submissions(cik: int) -> dict | None:
    """The one submissions-JSON GET every CR244 EDGAR-submissions reader
    uses. Returns None on a 404 (no such CIK) or any fetch/parse failure —
    callers degrade their own section loudly (CR040) rather than propagate
    an exception."""
    url = SUBMISSIONS_URL.format(cik=cik)
    try:
        with httpx.Client(
            timeout=_SUBMISSIONS_FETCH_TIMEOUT_S, headers={"User-Agent": USER_AGENT}
        ) as client:
            r = paced_get(client, url)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warn("edgar_submissions_fetch_error", cik=cik, error=str(exc)[:200])
        return None


def fetch_submissions_page(name: str) -> dict | None:
    """One `filings.files[i].name` page (older filings, paginated out of
    `filings.recent` once an issuer has "at least 1 year or 1000 filings").
    Same fetch/pacing/error-handling contract as `fetch_company_submissions`
    — a page is just a submissions-shaped JSON document at a different URL,
    `https://data.sec.gov/submissions/{name}`."""
    url = f"https://data.sec.gov/submissions/{name}"
    try:
        with httpx.Client(
            timeout=_SUBMISSIONS_FETCH_TIMEOUT_S, headers={"User-Agent": USER_AGENT}
        ) as client:
            r = paced_get(client, url)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warn("edgar_submissions_page_fetch_error", name=name, error=str(exc)[:200])
        return None
