"""CR244 Part 2 slice 1 — the issuer's recent SEC filings INDEX (form type +
filed date + plain label, no document text) reaching the News Analyst
("Macro & Events") and the Fundamentals Analyst.

Copies CR221 I1's 5-point pattern (extraction / `field_state` key / header
bullet / body line / persona sentence) for a live-fetched feed instead of a
store-backed one: there is no offline ingest here, `edgar_filings_feed` keeps
its OWN per-CIK submissions cache (audit M2 — an earlier revision claimed it
reused `company_profile.py`'s cache; it never did until this fix).

**Exclusions (audit B1).** Form 3/4/5(+/A) and Form 144(+/A) are
insider-related — slice 2's territory (Bull/Bear), not this feed's. Also
excluded: `issuer_as_investor` rows (13F-HR/13F-NT/N-PX, and a 13D/13G where
the issuer is the FILER of a stake in someone else — about a DIFFERENT
company), `correspondence` rows (CORRESP/UPLOAD — not a public disclosure,
and their `filingDate` isn't a release date), and 25-NSE (an exchange
delisting notice, often for a debt series). A 13D/13G where the issuer is
the SUBJECT (`about_issuer`, a >=5% holder reporting a stake IN the issuer)
IS included, relabelled to say so. `classify_filing`
(`app/services/edgar_submissions.py`) is the shared role classifier both
this feed and `company_profile.py`'s Filings tab route through.

**Window/cap.** Last 180 days, newest first, capped at 10 — a synthetic
13-row submissions fixture (not `submissions_nvda.json`, which has no Form
144 row and too narrow a date spread to exercise the cap) proves both the
window floor and the MAX_FILINGS cap independently.

**As-of / point-in-time.** A filing's `filed_date` is immutable, so the
window right edge is `as_of`, not the wall clock — the same PIT contract
`asof_context.py` states for every other EDGAR read in this Room.

**Not-available.** No CIK, a CIK-resolver outage, an EDGAR fetch failure, or
an unrecognised submissions shape all read `not_available` — never a
silently empty/blank line (CR040).

**Lane gating.** The header bullet and body line reach `news_analyst` and
`fundamentals_analyst` (and the full/`None` sheet), and are absent for
`market_analyst` and `social_media_analyst` — CR244's non-goal is new lane
infrastructure, so this reuses the existing two-domain OR gate the
`next_earnings` line already demonstrates (`room_prompts.py`).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from app.core.config import settings
from app.schemas import AgentId
from app.services import edgar_filings_feed, room_prompts, room_runner
from app.services.agent_prompts import load_base_prompt
from app.services.edgar_cik import CikResolutionUnavailable
from app.services.edgar_filings_feed import (
    FEED_LABEL,
    MAX_FILINGS,
    WINDOW_DAYS,
    _filings_index,
    fetch_recent_filings,
    recent_filings_line,
)

_AS_OF = date(2026, 9, 27)
_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "cr244"


def _load_fixture(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _clear_filings_feed_cache():
    """M2 gave this module its own per-CIK cache — several tests below reuse
    the same CIK (1045810/NVDA, 19617/JPM) across different monkeypatched
    fetch behaviours, so a stale cache entry from one test would otherwise
    silently answer a later one."""
    edgar_filings_feed.clear_filings_feed_cache()
    yield
    edgar_filings_feed.clear_filings_feed_cache()


def _synthetic_submissions() -> dict:
    """13 rows spanning the exclusion set, the 180-day window edge, and
    enough in-window non-insider rows (11) to prove the 10-item cap bites.

    `SC 13D`'s `fileNumber` starts "005-" — subject-side (`about_issuer`),
    same convention as the real NVDA fixture — so it stays INCLUDED and this
    fixture's cap-test intent (11 in-window non-excluded rows) is unchanged
    by the audit's role classification (B1)."""
    forms = [
        "10-K", "10-Q", "8-K", "8-K", "DEF 14A", "S-1", "S-3", "424B5",
        "SC 13D", "8-K/A",
        "3", "4/A", "144",
        "10-Q",  # the 11th in-window non-insider row — proves the cap
    ]
    dates = [
        "2026-09-20", "2026-09-10", "2026-08-01", "2026-07-01", "2026-06-15",
        "2026-06-01", "2026-05-15", "2026-05-01", "2026-04-15", "2026-04-01",
        "2026-08-15", "2026-08-10", "2026-08-05",
        "2026-03-31",  # 180 days before _AS_OF exactly — inside the window
    ]
    file_numbers = [
        "", "", "", "", "", "", "", "",
        "005-99999",  # SC 13D, subject-side — stays included
        "",
        "", "", "",
        "",
    ]
    n = len(forms)
    assert len(dates) == n and len(file_numbers) == n
    return {
        "filings": {
            "recent": {
                "form": forms,
                "filingDate": dates,
                "fileNumber": file_numbers,
                "primaryDocDescription": [None] * n,
            },
            "files": [],
        }
    }


# ── Extraction: exclusions, cap, window, as-of filter ───────────────────────


def test_insider_and_144_forms_are_excluded():
    subs = _synthetic_submissions()
    items = _filings_index(subs, since=_AS_OF.replace(year=2025), as_of=_AS_OF)
    forms = {i["form"] for i in items}
    assert forms.isdisjoint({"3", "4/A", "144"})


def test_newest_first_and_capped_at_ten():
    subs = _synthetic_submissions()
    items = _filings_index(subs, since=date(2026, 1, 1), as_of=_AS_OF)
    assert len(items) == MAX_FILINGS
    filed = [i["filed_date"] for i in items]
    assert filed == sorted(filed, reverse=True)
    # The 11th in-window non-insider row (oldest, 2026-03-31) is dropped by
    # the cap, not the window.
    assert "2026-03-31" not in filed


def test_window_floor_excludes_a_filing_181_days_back():
    subs = _synthetic_submissions()
    subs["filings"]["recent"]["form"].append("10-K")
    subs["filings"]["recent"]["filingDate"].append("2026-03-30")  # 181 days back
    subs["filings"]["recent"]["primaryDocDescription"].append(None)
    items = _filings_index(subs, since=_AS_OF.replace(month=3, day=31), as_of=_AS_OF)
    assert "2026-03-30" not in {i["filed_date"] for i in items}
    assert WINDOW_DAYS == 180


def test_as_of_filters_a_filing_after_the_convene_date():
    subs = _synthetic_submissions()
    subs["filings"]["recent"]["form"].append("10-K")
    subs["filings"]["recent"]["filingDate"].append("2026-09-28")  # after _AS_OF
    subs["filings"]["recent"]["primaryDocDescription"].append(None)
    items = _filings_index(subs, since=date(2026, 1, 1), as_of=_AS_OF)
    assert "2026-09-28" not in {i["filed_date"] for i in items}


def test_labels_come_from_the_shared_form_label_map():
    subs = _synthetic_submissions()
    items = _filings_index(subs, since=date(2026, 1, 1), as_of=_AS_OF)
    by_form = {i["form"]: i["label"] for i in items}
    assert by_form["10-K"] == "Annual report"
    assert by_form["8-K"] == "Current report"
    assert by_form["DEF 14A"] == "Proxy statement"


def test_an_unrecognised_submissions_shape_returns_none():
    assert _filings_index({}, since=date(2026, 1, 1), as_of=_AS_OF) is None
    assert _filings_index({"filings": {}}, since=date(2026, 1, 1), as_of=_AS_OF) is None


def test_a_quiet_quarter_is_live_with_an_empty_list():
    empty = {"filings": {"recent": {
        "form": ["4"], "filingDate": ["2026-09-01"], "primaryDocDescription": [None],
    }}}
    items = _filings_index(empty, since=date(2026, 1, 1), as_of=_AS_OF)
    assert items == []
    assert recent_filings_line("live", items) == (
        f"{FEED_LABEL}: none in the last {WINDOW_DAYS} days. Report the form and filed "
        "date only — do not infer a filing's contents or the issuer's reasons from its "
        "type or timing."
    )


# ── fetch_recent_filings: the not-available path ────────────────────────────


def test_no_cik_is_not_available(monkeypatch):
    monkeypatch.setattr(edgar_filings_feed, "resolve_cik", lambda t: None)
    state, items = fetch_recent_filings("ZZZZ", _AS_OF)
    assert state == "not_available" and items is None


def test_a_cik_resolver_outage_is_not_available(monkeypatch):
    def boom(t):
        raise CikResolutionUnavailable("outage")

    monkeypatch.setattr(edgar_filings_feed, "resolve_cik", boom)
    state, items = fetch_recent_filings("NVDA", _AS_OF)
    assert state == "not_available" and items is None


def test_a_submissions_fetch_failure_is_not_available(monkeypatch):
    monkeypatch.setattr(edgar_filings_feed, "resolve_cik", lambda t: 1045810)
    monkeypatch.setattr(edgar_filings_feed, "_fetch_company_submissions", lambda cik: None)
    state, items = fetch_recent_filings("NVDA", _AS_OF)
    assert state == "not_available" and items is None


def test_a_live_fetch_returns_the_windowed_items(monkeypatch):
    monkeypatch.setattr(edgar_filings_feed, "resolve_cik", lambda t: 1045810)
    monkeypatch.setattr(
        edgar_filings_feed, "_fetch_company_submissions", lambda cik: _synthetic_submissions(),
    )
    state, items = fetch_recent_filings("NVDA", _AS_OF)
    assert state == "live"
    assert len(items) == MAX_FILINGS


def test_recent_filings_line_is_none_off_the_live_state():
    assert recent_filings_line("not_available", None) is None
    assert recent_filings_line(None, None) is None


def test_recent_filings_line_renders_form_label_date():
    items = [{"form": "10-K", "label": "Annual report", "filed_date": "2026-09-20"}]
    line = recent_filings_line("live", items)
    assert line is not None
    assert "10-K — Annual report — filed 2026-09-20" in line
    assert "do not infer a filing's contents" in line


# ── The overlay ──────────────────────────────────────────────────────────────


def test_the_overlay_writes_the_live_key_and_items(monkeypatch):
    monkeypatch.setattr(
        edgar_filings_feed, "fetch_recent_filings",
        lambda ticker, as_of: ("live", [{"form": "10-K", "label": "Annual report", "filed_date": "2026-09-20"}]),
    )
    profile: dict = {}
    field_state: dict = {}
    room_runner._overlay_recent_filings(profile, field_state, "NVDA", _AS_OF)
    assert field_state["recent_filings"] == "live"
    assert profile["recent_filings_items"] == [
        {"form": "10-K", "label": "Annual report", "filed_date": "2026-09-20"}
    ]


def test_the_overlay_marks_unavailable_on_a_not_available_state(monkeypatch):
    monkeypatch.setattr(
        edgar_filings_feed, "fetch_recent_filings", lambda ticker, as_of: ("not_available", None),
    )
    profile: dict = {}
    field_state: dict = {}
    room_runner._overlay_recent_filings(profile, field_state, "ZZZZ", _AS_OF)
    assert field_state["recent_filings"] == "unavailable"
    assert "recent_filings_items" not in profile


def test_the_overlay_degrades_loudly_on_an_unexpected_exception(monkeypatch):
    def boom(ticker, as_of):
        raise RuntimeError("network exploded")

    monkeypatch.setattr(edgar_filings_feed, "fetch_recent_filings", boom)
    profile: dict = {}
    field_state: dict = {}
    room_runner._overlay_recent_filings(profile, field_state, "NVDA", _AS_OF)
    assert field_state["recent_filings"] == "unavailable"


# ── Lane gating at the render seam ───────────────────────────────────────────


def _profile_with_filings(items=None, *, live: bool = True) -> dict:
    field_state = {"recent_filings": "live" if live else "unavailable", "run_date": "live"}
    profile = {"field_state": field_state, "run_date": "2026-09-27"}
    if live:
        profile["recent_filings_items"] = items or [
            {"form": "10-K", "label": "Annual report", "filed_date": "2026-09-20"},
        ]
    return profile


def test_flag_off_renders_nothing_for_any_agent(monkeypatch):
    monkeypatch.setattr(settings, "room_recent_filings_enabled", False)
    profile = _profile_with_filings()
    for agent in (AgentId.NEWS_ANALYST, AgentId.FUNDAMENTALS_ANALYST, None):
        assert FEED_LABEL not in room_prompts._format_profile(profile, agent)


def test_flag_on_reaches_news_and_fundamentals_and_full_sheet(monkeypatch):
    monkeypatch.setattr(settings, "room_recent_filings_enabled", True)
    profile = _profile_with_filings()
    for agent in (AgentId.NEWS_ANALYST, AgentId.FUNDAMENTALS_ANALYST, None):
        sheet = room_prompts._format_profile(profile, agent)
        assert FEED_LABEL in sheet
        assert "10-K — Annual report — filed 2026-09-20" in sheet


def test_flag_on_withholds_from_market_and_social_lanes(monkeypatch):
    monkeypatch.setattr(settings, "room_recent_filings_enabled", True)
    profile = _profile_with_filings()
    for agent in (AgentId.MARKET_ANALYST, AgentId.SOCIAL_MEDIA_ANALYST):
        assert FEED_LABEL not in room_prompts._format_profile(profile, agent)


def test_not_available_state_renders_the_header_denial_not_a_blank(monkeypatch):
    monkeypatch.setattr(settings, "room_recent_filings_enabled", True)
    profile = _profile_with_filings(live=False)
    sheet = room_prompts._format_profile(profile, AgentId.NEWS_ANALYST)
    assert f"{FEED_LABEL}: not available this call" in sheet
    assert "do not supply a filing from memory" in sheet
    # No body line without a live state, even with the flag on.
    assert "newest first, last 180 days" not in sheet


def test_flag_on_but_absent_field_state_key_renders_the_denial_not_content(monkeypatch):
    """A hand-built profile with no `recent_filings` field_state entry at all
    (older tests, non-Room callers) reads as not-live and refuses by
    default — the header still names the field (same as every other
    field_state-gated line's "not available" branch), but no body line and
    no fabricated filing content ever renders."""
    monkeypatch.setattr(settings, "room_recent_filings_enabled", True)
    profile = {"field_state": {}, "run_date": "2026-09-27"}
    sheet = room_prompts._format_profile(profile, AgentId.NEWS_ANALYST)
    assert f"{FEED_LABEL}: not available this call" in sheet
    assert "newest first, last 180 days" not in sheet


def test_the_flag_is_forwarded_in_the_api_alpha_block():
    compose = (Path(__file__).resolve().parents[3] / "docker-compose.yml").read_text(encoding="utf-8")
    assert "ROOM_RECENT_FILINGS_ENABLED: ${ROOM_RECENT_FILINGS_ENABLED:-false}" in compose


# ── Audit B1: filer-vs-subject role classification (real NVDA fixture) ──────


def test_a_subject_side_13g_is_included_and_relabelled():
    """NVDA's SCHEDULE 13G, fileNumber "005-56649" (Vanguard reporting a
    >=5% stake IN NVDA — real live payload, 2026-09-27) is `about_issuer`:
    included, and relabelled so it does not read as NVDA's own filing."""
    subs = _load_fixture("nvda_submissions_role_classification.json")
    items = _filings_index(subs, since=date(2020, 1, 1), as_of=date(2026, 9, 27))
    thirteen_g = [i for i in items if i["form"] == "SCHEDULE 13G" and i["filed_date"] == "2026-04-28"]
    assert len(thirteen_g) == 1
    assert "5% holder" in thirteen_g[0]["label"]
    assert "13G" in thirteen_g[0]["label"]


def test_a_filer_side_13g_is_excluded():
    """NVDA's own SCHEDULE 13G, empty fileNumber (NVIDIA reporting ITS stake
    in Nebius — real live payload) is `issuer_as_investor`: about a
    DIFFERENT company, excluded from NVDA's own feed."""
    subs = _load_fixture("nvda_submissions_role_classification.json")
    items = _filings_index(subs, since=date(2020, 1, 1), as_of=date(2026, 9, 27))
    assert not any(i["filed_date"] == "2026-07-20" and i["form"] == "SCHEDULE 13G" for i in items)


def test_13f_hr_and_npx_are_excluded():
    subs = _load_fixture("nvda_submissions_role_classification.json")
    items = _filings_index(subs, since=date(2020, 1, 1), as_of=date(2026, 9, 27))
    forms = {i["form"] for i in items}
    assert forms.isdisjoint({"13F-HR", "N-PX"})


def test_corresp_and_upload_are_excluded():
    subs = _load_fixture("nvda_submissions_role_classification.json")
    items = _filings_index(subs, since=date(2020, 1, 1), as_of=date(2026, 9, 27))
    forms = {i["form"] for i in items}
    assert forms.isdisjoint({"CORRESP", "UPLOAD"})


def test_ordinary_issuer_filings_still_included_from_real_fixture():
    subs = _load_fixture("nvda_submissions_role_classification.json")
    items = _filings_index(subs, since=date(2020, 1, 1), as_of=date(2026, 9, 27))
    forms = {i["form"] for i in items}
    assert {"10-K", "10-Q", "8-K", "DEF 14A"} <= forms


# ── Audit B2: as-of coverage via filings.files pages ─────────────────────────


def test_recent_alone_understates_a_heavy_filer_and_files_pages_fill_it(monkeypatch):
    """Real JPM shape: `filings.recent` is truncated (here, to rows from
    2026-02-13 onward); `filings.files` names OLDER pages (real
    filingFrom/filingTo spans, e.g. `CIK...-submissions-005.json` covering
    2025-03-31..2025-04-30) that overlap a 2025-04-11 as_of window. Without
    fetching them, a 180-day window ending 2025-04-11 would falsely read as
    "none in the last 180 days" even though JPM filed plenty then. Every
    overlapping page is served the same real page005 payload here — this
    proves the MERGE mechanism (every needed page fetched and folded in),
    not the exact content of each distinct page."""
    truncated = _load_fixture("jpm_submissions_truncated_recent.json")
    page005 = _load_fixture("jpm_submissions_page005.json")

    monkeypatch.setattr(edgar_filings_feed, "resolve_cik", lambda t: 19617)
    monkeypatch.setattr(edgar_filings_feed, "_cached_submissions", lambda cik: truncated)
    monkeypatch.setattr(edgar_filings_feed, "_cached_submissions_page", lambda cik, name: page005)
    as_of = date(2025, 4, 11)
    state, items = fetch_recent_filings("JPM", as_of)
    assert state == "live"
    assert any(i["filed_date"] == "2025-04-11" for i in items)


def test_a_needed_page_fetch_failure_is_not_available_never_truncated(monkeypatch):
    """The same truncated-recent shape, but the overlapping page fails to
    fetch — must render `not_available`, never a silently truncated `live`
    list (CR040): a caller can't tell "genuinely quiet" from "couldn't read
    far enough back" if both read the same."""
    truncated = _load_fixture("jpm_submissions_truncated_recent.json")

    monkeypatch.setattr(edgar_filings_feed, "resolve_cik", lambda t: 19617)
    monkeypatch.setattr(edgar_filings_feed, "_cached_submissions", lambda cik: truncated)
    monkeypatch.setattr(edgar_filings_feed, "_cached_submissions_page", lambda cik, name: None)
    state, items = fetch_recent_filings("JPM", date(2025, 4, 11))
    assert state == "not_available" and items is None


def test_recent_alone_suffices_when_it_already_covers_the_window(monkeypatch):
    """The as-of coverage fetch must not fire at all when `recent` already
    reaches back far enough — proved by making the page-fetch seam explode
    if it's ever called."""
    truncated = _load_fixture("jpm_submissions_truncated_recent.json")

    def boom(cik, name):
        raise AssertionError("filings.files page fetch should not have been attempted")

    monkeypatch.setattr(edgar_filings_feed, "resolve_cik", lambda t: 19617)
    monkeypatch.setattr(edgar_filings_feed, "_cached_submissions", lambda cik: truncated)
    monkeypatch.setattr(edgar_filings_feed, "_cached_submissions_page", boom)
    # The fixture's own `recent` covers back to 2026-02-13 — a window ending
    # well within that needs no page fetch.
    state, items = fetch_recent_filings("JPM", date(2026, 9, 10))
    assert state == "live"


# ── Audit M2: per-CIK cache ──────────────────────────────────────────────────


def test_a_second_call_within_ttl_does_not_refetch(monkeypatch):
    calls = {"n": 0}

    def fake_fetch(cik):
        calls["n"] += 1
        return _load_fixture("nvda_submissions_role_classification.json")

    edgar_filings_feed.clear_filings_feed_cache()
    monkeypatch.setattr(edgar_filings_feed, "resolve_cik", lambda t: 1045810)
    monkeypatch.setattr(edgar_filings_feed, "_fetch_company_submissions", fake_fetch)
    fetch_recent_filings("NVDA", _AS_OF)
    fetch_recent_filings("NVDA", _AS_OF)
    assert calls["n"] == 1
    edgar_filings_feed.clear_filings_feed_cache()


def test_a_fetch_failure_is_negative_cached_not_retried_immediately(monkeypatch):
    calls = {"n": 0}

    def fake_fetch(cik):
        calls["n"] += 1
        return None

    edgar_filings_feed.clear_filings_feed_cache()
    monkeypatch.setattr(edgar_filings_feed, "resolve_cik", lambda t: 1045810)
    monkeypatch.setattr(edgar_filings_feed, "_fetch_company_submissions", fake_fetch)
    fetch_recent_filings("NVDA", _AS_OF)
    fetch_recent_filings("NVDA", _AS_OF)
    assert calls["n"] == 1
    edgar_filings_feed.clear_filings_feed_cache()


# ── LOW: persona pinning (index only, not content) ───────────────────────────


def test_news_analyst_persona_carries_the_recent_filings_sentence():
    body = load_base_prompt(AgentId.NEWS_ANALYST)
    assert FEED_LABEL in body


def test_fundamentals_analyst_persona_carries_the_recent_filings_sentence():
    body = load_base_prompt(AgentId.FUNDAMENTALS_ANALYST)
    assert FEED_LABEL in body


# ── LOW: body line renders exactly once for a full-sheet agent ──────────────


def test_body_line_appears_exactly_once_for_the_full_sheet(monkeypatch):
    """A full-sheet agent (`None`) satisfies BOTH the news and fundamentals
    lane OR-gate — the body line is rendered once in `_format_profile`
    regardless (see the comment above its render seam: "rendered ONCE here
    ... so a full-sheet agent never sees it twice"). `FEED_LABEL` itself
    also opens the HEADER bullet, so this counts the distinctive BODY-line
    phrase, not the label, to isolate what this test actually claims."""
    monkeypatch.setattr(settings, "room_recent_filings_enabled", True)
    profile = _profile_with_filings()
    sheet = room_prompts._format_profile(profile, None)
    assert sheet.count("newest first, last 180 days") == 1


# ── LOW: as-of (not wall-clock) reaches the overlay ──────────────────────────


def test_profile_for_ticker_as_of_reaches_the_overlay(monkeypatch):
    captured: dict = {}

    def fake_fetch(ticker, as_of):
        captured["as_of"] = as_of
        return "live", []

    monkeypatch.setattr(edgar_filings_feed, "fetch_recent_filings", fake_fetch)
    monkeypatch.setattr(settings, "use_real_market_data", False)
    historical = date(2025, 6, 15)
    room_runner._profile_for_ticker("NVDA", as_of=historical)
    assert captured["as_of"] == historical


# ── LOW: a filing dated exactly on as_of is included ─────────────────────────


def test_a_filing_dated_exactly_on_as_of_is_included():
    subs = _synthetic_submissions()
    subs["filings"]["recent"]["form"].append("10-K")
    subs["filings"]["recent"]["filingDate"].append(_AS_OF.isoformat())
    subs["filings"]["recent"]["primaryDocDescription"].append(None)
    items = _filings_index(subs, since=date(2026, 1, 1), as_of=_AS_OF)
    assert _AS_OF.isoformat() in {i["filed_date"] for i in items}


# ── assert_dates_within is exercised after filtering ─────────────────────────


def test_fetch_recent_filings_calls_assert_dates_within(monkeypatch):
    """`assert_dates_within` is the same structural leakage guard every other
    as-of read path in this Room (`edgar_8k.py`, `edgar_pit.py`,
    `price_history.py`) calls after its own filter — proved as a genuine
    call, not merely a passing happy path, by monkeypatching the guard
    itself and asserting it was invoked with this call's own `as_of`."""
    subs = _load_fixture("nvda_submissions_role_classification.json")
    captured: dict = {}

    def fake_guard(dates, as_of, *, origin):
        captured["dates"] = dates
        captured["as_of"] = as_of
        captured["origin"] = origin

    monkeypatch.setattr(edgar_filings_feed, "resolve_cik", lambda t: 1045810)
    monkeypatch.setattr(edgar_filings_feed, "_cached_submissions", lambda cik: subs)
    monkeypatch.setattr(edgar_filings_feed, "assert_dates_within", fake_guard)
    state, items = fetch_recent_filings("NVDA", _AS_OF)
    assert state == "live"
    assert captured["as_of"] == _AS_OF
    assert captured["origin"] == "edgar_filings_feed.fetch_recent_filings"
    assert captured["dates"] == [date.fromisoformat(i["filed_date"]) for i in items]
