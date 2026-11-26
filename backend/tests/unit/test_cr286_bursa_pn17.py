"""CR286 — Bursa PN17/GN3 list: parse, change detection, stale logic, refusal, never-wipe, sheet line.

The fixture (`fixtures/cr286_pn17_page.html`) is hand-written from a GUESS at the page's visible
columns: Bursa refused the one probe (Cloudflare challenge), so the live structure is unverified.
No network anywhere: the refresh script's one request goes through `httpx.MockTransport`.
"""

from __future__ import annotations

import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db import get_session
from app.db.models import BursaPn17ChangeRow, BursaPn17CurrentRow, BursaPn17RunRow
from app.schemas import AgentId
from app.services import bursa_pn17 as pn17
from app.services import room_bank, room_runner
from app.services.room_market import my_desk_footer
from app.services.room_prompts import _format_profile

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[2]
_FIXTURE = (_HERE / "fixtures" / "cr286_pn17_page.html").read_text()
_BACKEND = _HERE.parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from scripts import bursa_pn17_refresh as script  # noqa: E402

D1 = datetime(2026, 12, 1, 2, 17, tzinfo=timezone.utc)
D2 = D1 + timedelta(days=7)


def _client(status: int, body: str) -> httpx.Client:
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(status, text=body)

    c = httpx.Client(transport=httpx.MockTransport(handler))
    c.seen = seen  # type: ignore[attr-defined]
    return c


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(settings, "bursa_pn17_refresh_enabled", True)


def _current() -> dict[str, BursaPn17CurrentRow]:
    with get_session() as s:
        return {r.stock_code: r for r in s.execute(select(BursaPn17CurrentRow)).scalars()}


def _runs() -> list[BursaPn17RunRow]:
    with get_session() as s:
        return list(s.execute(select(BursaPn17RunRow).order_by(BursaPn17RunRow.started_at)).scalars())


def _changes() -> list[BursaPn17ChangeRow]:
    with get_session() as s:
        return list(s.execute(select(BursaPn17ChangeRow)).scalars())


# ── parse ────────────────────────────────────────────────────────────────────


def test_parse_reads_codes_names_market_category_and_group_from_the_visible_columns():
    rows = {r.stock_code: r for r in pn17.parse_page(_FIXTURE)}
    assert set(rows) == {"1001", "1002", "1003", "1004", "0001"}
    assert rows["1001"] == pn17.Row("1001", "Alpha Fixture Berhad", "Main", pn17.CATEGORY_PN17, "plan_under_review")
    assert rows["1002"].company_name == "Beta Fixture Berhad"
    assert rows["1003"].status_group == "plan_approved_awaiting_uplift"
    assert rows["1004"].status_category == pn17.CATEGORY_AFFECTED
    assert rows["0001"] == pn17.Row("0001", "Epsilon Fixture Berhad", "ACE", pn17.CATEGORY_GN3, "pending_plan")


def test_parse_ignores_script_content_and_unrelated_tables():
    assert "9999" not in {r.stock_code for r in pn17.parse_page(_FIXTURE)}


@pytest.mark.parametrize("html,reason", [
    ("<html><body><p>nothing here</p></body></html>", "no_recognised_table"),
    ("<table><tr><th>Stock Code</th><th>Company Name</th></tr></table>", "zero_rows"),
    ("<table><tr><th>Stock Code</th><th>Company Name</th></tr><tr><td>ABC</td><td>X</td></tr></table>",
     "malformed_stock_code"),
    ("<table><tr><th>Stock Code</th><th>Company Name</th></tr>"
     "<tr><td>1001</td><td>X</td></tr><tr><td>1001</td><td>Y</td></tr></table>", "duplicate_stock_code"),
    ("<table><tr><th>Stock Code</th><th>Company Name</th></tr><tr><td>1001</td><td></td></tr></table>",
     "missing_company_name"),
])
def test_a_page_whose_structure_changed_fails_loudly_never_partially(html, reason):
    with pytest.raises(pn17.ParseFailed) as exc:
        pn17.parse_page(html)
    assert exc.value.reason == reason


def test_a_challenge_page_is_a_refusal_not_a_parse_problem():
    assert pn17.classify_response(403, "<title>Just a moment...</title>") == pn17.OUTCOME_REFUSED
    assert pn17.classify_response(200, "<title>Just a moment...</title>") == pn17.OUTCOME_REFUSED
    assert pn17.classify_response(429, "") == pn17.OUTCOME_REFUSED
    assert pn17.classify_response(500, "boom") == pn17.OUTCOME_FETCH_FAILED
    assert pn17.classify_response(200, _FIXTURE) is None


# ── refresh script: success, change detection, idempotence ───────────────────


def test_first_run_stores_the_list_and_logs_every_row_as_added(enabled):
    assert script.run(client=_client(200, _FIXTURE), now=D1) == 0
    assert set(_current()) == {"1001", "1002", "1003", "1004", "0001"}
    assert [c.change_type for c in _changes()] == ["added"] * 5
    (run,) = _runs()
    assert (run.outcome, run.trigger, run.rows_found, run.added, run.http_status) == ("ok", "weekly", 5, 5, 200)


def test_one_request_with_the_honest_user_agent_and_no_redirect_following(enabled):
    c = _client(200, _FIXTURE)
    script.run(client=c, now=D1)
    assert len(c.seen) == 1
    assert str(c.seen[0].url) == pn17.SOURCE_URL
    assert c.seen[0].headers["user-agent"] == pn17.USER_AGENT


def test_a_rerun_with_the_same_page_changes_nothing_but_last_seen(enabled):
    script.run(client=_client(200, _FIXTURE), now=D1)
    before = len(_changes())
    assert script.run(client=_client(200, _FIXTURE), now=D2) == 0
    assert len(_changes()) == before
    row = _current()["1001"]
    assert (row.first_seen, row.last_seen) == (D1.date(), D2.date())
    assert _runs()[-1].added == _runs()[-1].removed == _runs()[-1].changed == 0


def test_changes_are_detected_added_category_changed_and_removed(enabled):
    script.run(client=_client(200, _FIXTURE), now=D1)
    page2 = _FIXTURE.replace("<td>1004</td><td>Delta Fixture Berhad</td>", "<td>1005</td><td>Zeta Fixture Berhad</td>")
    # 1003 moves from the 'awaiting uplift' table into an 8.03A one: category changes.
    page2 = page2.replace(
        "<h3>Plan approved awaiting uplift</h3>", "<h3>Affected listed issuers (paragraph 8.03A)</h3>",
    )
    assert script.run(client=_client(200, page2), now=D2) == 0
    new = [c for c in _changes() if c.observed_on == D2.date()]
    kinds = {(c.change_type, c.stock_code) for c in new}
    assert kinds == {("added", "1005"), ("removed", "1004"), ("category_changed", "1003")}
    moved = next(c for c in new if c.stock_code == "1003")
    assert (moved.previous_category, moved.status_category) == (pn17.CATEGORY_PN17, pn17.CATEGORY_AFFECTED)
    assert "1004" not in _current() and "1005" in _current()
    assert _current()["1003"].first_seen == D1.date()
    assert len(_changes()) == 5 + 3  # append-only: the first run's rows are still there


# ── never wipe ───────────────────────────────────────────────────────────────


def _seeded(enabled_fixture=None):
    script.run(client=_client(200, _FIXTURE), now=D1)
    return {k: (v.company_name, v.status_category) for k, v in _current().items()}


@pytest.mark.parametrize("status,body,outcome", [
    (403, "<title>Just a moment...</title>", "refused"),
    (429, "slow down", "refused"),
    (200, "<html><body>moved</body></html>", "parse_failed"),
    (200, "<table><tr><th>Stock Code</th><th>Company Name</th></tr></table>", "parse_failed"),
    (500, "boom", "fetch_failed"),
])
def test_refusal_or_an_unreadable_page_never_touches_the_list(enabled, status, body, outcome):
    before = _seeded()
    assert script.run(client=_client(status, body), now=D2) == 1
    assert {k: (v.company_name, v.status_category) for k, v in _current().items()} == before
    last = _runs()[-1]
    assert (last.outcome, last.http_status) == (outcome, status)
    assert last.rows_found == last.added == last.removed == 0
    assert len(_changes()) == 5


def test_an_implausible_shrink_is_held_back_unless_a_human_accepts_it(enabled):
    before = _seeded()
    one_row = (
        "<h2>Main Market</h2><table><tr><th>Stock Code</th><th>Company Name</th></tr>"
        "<tr><td>1001</td><td>Alpha Fixture Berhad</td></tr></table>"
    )
    assert script.run(client=_client(200, one_row), now=D2) == 1
    assert {k: (v.company_name, v.status_category) for k, v in _current().items()} == before
    assert _runs()[-1].outcome == "parse_failed" and _runs()[-1].detail == "implausible_shrink"
    assert script.run(client=_client(200, one_row), now=D2, accept_shrink=True) == 0
    assert set(_current()) == {"1001"}


def test_a_network_error_is_recorded_and_the_list_kept(enabled):
    before = _seeded()

    def boom(req):
        raise httpx.ConnectError("down")

    c = httpx.Client(transport=httpx.MockTransport(boom))
    assert script.run(client=c, now=D2) == 1
    assert {k: (v.company_name, v.status_category) for k, v in _current().items()} == before
    assert _runs()[-1].outcome == "fetch_failed"


def test_the_script_says_so_and_does_nothing_when_the_switch_is_off(monkeypatch, capsys):
    monkeypatch.setattr(settings, "bursa_pn17_refresh_enabled", False)
    c = _client(200, _FIXTURE)
    assert script.run(client=c, now=D1) == 3
    assert not c.seen and not _runs()
    assert "disabled" in capsys.readouterr().err


# ── manual seed ──────────────────────────────────────────────────────────────

_SEED = "stock_code,company_name,market,status_category,status_group\n1001,Alpha Fixture Berhad,Main,pn17,plan_under_review\n"


def test_a_human_seed_is_recorded_as_manual_and_needs_no_network_or_switch(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "bursa_pn17_refresh_enabled", False)
    f = tmp_path / "seed.csv"
    f.write_text(_SEED)
    assert script.run(from_file=f, now=D1) == 0
    (run,) = _runs()
    assert (run.trigger, run.outcome, run.http_status) == ("manual", "ok", None)
    assert set(_current()) == {"1001"}


@pytest.mark.parametrize("text", [
    "stock_code,company_name\n1001,X\n",
    "stock_code,company_name,market,status_category\nABC,X,Main,pn17\n",
    "stock_code,company_name,market,status_category\n1001,X,Main,not_a_category\n",
    "stock_code,company_name,market,status_category\n",
])
def test_a_bad_seed_fails_and_leaves_the_list(tmp_path, text):
    f = tmp_path / "seed.csv"
    f.write_text(text)
    assert script.run(from_file=f, now=D1) == 1
    assert not _current() and _runs()[-1].outcome == "parse_failed"


# ── stale logic and the sheet line ───────────────────────────────────────────


def _status(ticker: str, today: date) -> pn17.Status:
    return pn17.status_for(ticker, today)


def test_unavailable_when_no_run_has_ever_succeeded():
    st = _status("1001.KL", date(2026, 12, 2))
    assert st.state == pn17.STATE_UNAVAILABLE
    assert "no successful read" in pn17.line(st)
    assert "%" not in pn17.line(st)


def test_listed_names_the_category_first_seen_and_the_as_of_date(enabled):
    script.run(client=_client(200, _FIXTURE), now=D1)
    script.run(client=_client(200, _FIXTURE.replace("</body>", "<h2>Main Market</h2>"
                                                    "<table><tr><th>Stock Code</th><th>Company Name</th></tr>"
                                                    "<tr><td>1006</td><td>Eta Fixture Berhad</td></tr></table></body>")),
               now=D2)
    st = _status("1006.KL", D2.date())
    assert st.state == pn17.STATE_LISTED
    text = pn17.line(st)
    assert "listed as a PN17 issuer (Main Market)" in text
    assert f"first seen on Bursa's list {D2.date().isoformat()}" in text
    assert f"read by AMI {D2.date().isoformat()}" in text
    assert "Bursa's list updated" not in text
    early = pn17.line(_status("1001.KL", D2.date()))
    assert f"already on Bursa's list when AMI first read it ({D1.date().isoformat()})" in early
    assert "plan under review" in early


def test_the_affected_listed_issuer_category_is_named_as_such(enabled):
    script.run(client=_client(200, _FIXTURE), now=D1)
    assert "affected listed issuer (Main Market paragraph 8.03A)" in pn17.line(_status("1004.KL", D1.date()))
    assert "GN3 issuer (ACE Market, plan pending)" in pn17.line(_status("0001.KL", D1.date()))


def test_not_listed_carries_the_as_of_date(enabled):
    script.run(client=_client(200, _FIXTURE), now=D1)
    st = _status("5555.KL", D1.date())
    assert st.state == pn17.STATE_NOT_LISTED
    assert pn17.line(st).startswith(
        f"Bursa PN17/GN3 status: not on Bursa's PN17/GN3 list (read by AMI {D1.date().isoformat()}). Source:"
    )


def test_after_fourteen_days_without_a_success_the_answer_is_stale_for_every_ticker(enabled):
    script.run(client=_client(200, _FIXTURE), now=D1)
    at14 = _status("1001.KL", D1.date() + timedelta(days=14))
    assert at14.state == pn17.STATE_LISTED
    at15 = _status("1001.KL", D1.date() + timedelta(days=15))
    assert at15.state == pn17.STATE_STALE
    text = pn17.line(at15)
    assert "unavailable" in text and f"last successful read {D1.date().isoformat()}" in text
    assert "PN17 issuer" not in text and "not on Bursa" not in text
    assert pn17.line(_status("5555.KL", D1.date() + timedelta(days=15))) == text


def test_a_failed_latest_attempt_is_stated_on_the_line_even_while_the_list_is_fresh(enabled):
    script.run(client=_client(200, _FIXTURE), now=D1)
    script.run(client=_client(403, "<title>Just a moment...</title>"), now=D2)
    text = pn17.line(_status("1001.KL", D2.date()))
    assert "listed as a PN17 issuer" in text
    assert f"latest refresh attempt ({D2.date().isoformat()}) failed: Bursa's site refused the request" in text
    script.run(client=_client(200, _FIXTURE), now=D2 + timedelta(days=1))
    assert "latest refresh attempt" not in pn17.line(_status("1001.KL", D2.date() + timedelta(days=1)))


def test_the_note_is_the_line_in_ami_note_brackets():
    st = pn17.Status(pn17.STATE_NOT_LISTED, as_of=date(2026, 12, 1))
    assert pn17.note(st) == f"[AMI note: {pn17.line(st)}]"


def test_an_unreadable_store_degrades_to_unavailable_not_to_an_exception(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(pn17, "_status", boom)
    st = _status("1001.KL", date(2026, 12, 2))
    assert st.state == pn17.STATE_UNAVAILABLE and "could not be read" in pn17.line(st)


def test_no_page_text_is_stored_only_the_closed_vocabulary():
    cols = {c.name for c in BursaPn17CurrentRow.__table__.columns}
    assert cols == {
        "id", "stock_code", "company_name", "market", "status_category", "status_group",
        "trading_status", "first_seen", "last_seen", "source_url",
    }
    for text in pn17._GROUPS.values():
        assert len(text) < 40


# ── the Bursa sheet ──────────────────────────────────────────────────────────


def _profile_with(st: pn17.Status) -> dict:
    return {
        "market": "MY", "ticker": "1001.KL",
        "my_pn17_line": pn17.line(st), "my_pn17_note": pn17.note(st),
        "field_state": {},
    }


def test_the_sheet_line_renders_for_bursa_in_the_fundamentals_lane_only():
    st = pn17.Status(pn17.STATE_NOT_LISTED, as_of=date(2026, 12, 1))
    p = _profile_with(st)
    assert pn17.line(st) in _format_profile(p, AgentId.FUNDAMENTALS_ANALYST)
    assert pn17.line(st) in _format_profile(p)
    assert pn17.line(st) not in _format_profile(p, AgentId.NEWS_ANALYST)
    assert pn17.line(st) not in _format_profile(p, AgentId.MARKET_ANALYST)


def test_a_us_sheet_never_renders_the_line_even_if_a_stray_key_is_present():
    st = pn17.Status(pn17.STATE_NOT_LISTED, as_of=date(2026, 12, 1))
    p = _profile_with(st)
    del p["market"]
    assert "PN17" not in _format_profile(p, AgentId.FUNDAMENTALS_ANALYST)
    assert my_desk_footer(AgentId.FUNDAMENTALS_ANALYST, p) is None


def test_the_fundamentals_desk_turn_ends_with_the_note_so_it_reaches_the_transcript():
    st = pn17.Status(pn17.STATE_NOT_LISTED, as_of=date(2026, 12, 1))
    footer = my_desk_footer(AgentId.FUNDAMENTALS_ANALYST, _profile_with(st))
    assert footer.endswith(pn17.note(st))
    for other in (AgentId.MARKET_ANALYST, AgentId.NEWS_ANALYST, AgentId.SOCIAL_MEDIA_ANALYST):
        assert pn17.note(st) not in (my_desk_footer(other, _profile_with(st)) or "")
    bare = my_desk_footer(AgentId.FUNDAMENTALS_ANALYST, {"market": "MY"})
    assert "PN17" not in bare


def test_the_note_gives_the_terminal_grader_something_it_can_ground_on():
    from app.services.room_graders.ling_terminal import is_grounded

    st = pn17.Status(
        pn17.STATE_LISTED, as_of=date(2026, 12, 1), first_seen=date(2026, 12, 1), baseline=date(2026, 12, 1),
        row=pn17.Row("1001", "Alpha Fixture Berhad", "Main", pn17.CATEGORY_PN17, "plan_under_review"),
    )
    transcript = "Fundamentals read.\n\n" + pn17.note(st)
    assert is_grounded("Bursa shows it listed as a PN17 issuer in the Main Market", transcript)
    assert not is_grounded("Bursa shows it listed as a GN3 issuer in the ACE Market", transcript)


def test_the_runner_stamps_the_line_and_note_for_a_bursa_ticker(enabled):
    script.run(client=_client(200, _FIXTURE), now=D1)
    profile: dict = {}
    room_runner._stamp_my_pn17(profile, "1001.KL", D1.date(), historical=False)
    assert "listed as a PN17 issuer" in profile["my_pn17_line"]
    assert profile["my_pn17_note"] == f"[AMI note: {profile['my_pn17_line']}]"
    hist: dict = {}
    room_runner._stamp_my_pn17(hist, "1001.KL", D1.date(), historical=True)
    assert "does not describe a past date" in hist["my_pn17_line"]


def test_the_bursa_bank_variant_is_bumped_and_us_is_untouched():
    assert room_bank.MY_SHEET_REVISION == 7
    assert "my_rev=7" in room_bank.sheet_variant(
        news_state="live", social_state="live", market_withheld=False, ticker="1155.KL",
    )
    assert "my_rev" not in room_bank.sheet_variant(
        news_state="live", social_state="live", market_withheld=False, ticker="NVDA",
    )


# ── wiring ───────────────────────────────────────────────────────────────────


def test_the_switch_is_forwarded_in_compose_and_listed_in_the_beta_example():
    assert "BURSA_PN17_REFRESH_ENABLED: ${BURSA_PN17_REFRESH_ENABLED:-false}" in (_REPO / "docker-compose.yml").read_text()
    assert "BURSA_PN17_REFRESH_ENABLED=false" in (_REPO / "infra" / "beta.env.example").read_text()
    assert settings.bursa_pn17_refresh_enabled is False


def test_the_cron_line_in_the_repo_matches_the_script_and_is_not_installed_by_it():
    cron = (_REPO / "infra" / "cron" / "cr286_bursa_pn17_refresh.cron").read_text()
    assert "python -m scripts.bursa_pn17_refresh" in cron
    assert "17 2 * * 1" in cron


# ── follow-up 2026-11-26: Bursa's own update date + trading status ───────────

_SEED2 = (
    "stock_code,company_name,market,status_category,status_group,trading_status,bursa_updated\n"
    "1001,Alpha Fixture Berhad,Main,pn17,pending_plan,Suspended,2026-10-30\n"
    "1002,Beta Fixture Berhad,ACE,gn3,,TRADING,2026-10-30\n"
    "1003,Gamma Fixture Berhad,Main,pn17,,,\n"
)
TODAY = date(2026, 11, 26)


def test_parse_seed_reads_trading_status_lowercased_and_one_bursa_date():
    seed = pn17.parse_seed(_SEED2, today=TODAY)
    assert seed.bursa_updated == date(2026, 10, 30)
    assert [r.trading_status for r in seed.rows] == ["suspended", "trading", None]


def test_an_old_five_column_seed_is_still_valid_and_carries_no_date():
    seed = pn17.parse_seed(_SEED, today=TODAY)
    assert seed.bursa_updated is None
    assert seed.rows == [pn17.Row("1001", "Alpha Fixture Berhad", "Main", pn17.CATEGORY_PN17, "plan_under_review")]
    assert pn17.parse_csv(_SEED, today=TODAY) == seed.rows


_HDR = "stock_code,company_name,market,status_category,trading_status,bursa_updated\n"


@pytest.mark.parametrize("body,reason", [
    ("1001,X,Main,pn17,trading,2026-10-30\n1002,Y,Main,pn17,trading,2026-10-29\n", "seed_bursa_updated"),
    ("1001,X,Main,pn17,trading,30/10/2026\n", "seed_bursa_updated"),
    ("1001,X,Main,pn17,trading,2026-11-27\n", "seed_bursa_updated"),
    ("1001,X,Main,pn17,halted,2026-10-30\n", "seed_vocabulary"),
])
def test_a_bad_bursa_date_or_trading_value_is_refused_with_its_reason(body, reason):
    with pytest.raises(pn17.ParseFailed) as exc:
        pn17.parse_seed(_HDR + body, today=TODAY)
    assert exc.value.reason == reason


def test_bursa_date_today_is_accepted_and_rows_may_omit_it():
    seed = pn17.parse_seed(_HDR + "1001,X,Main,pn17,trading,2026-11-26\n1002,Y,Main,pn17,,\n", today=TODAY)
    assert seed.bursa_updated == TODAY


def _seed_file(tmp_path, text):
    f = tmp_path / "seed.csv"
    f.write_text(text)
    return f


def test_the_seed_stores_trading_status_and_the_run_keeps_bursas_date(tmp_path):
    assert script.run(from_file=_seed_file(tmp_path, _SEED2), now=D1) == 0
    cur = _current()
    assert (cur["1001"].trading_status, cur["1002"].trading_status, cur["1003"].trading_status) == (
        "suspended", "trading", None,
    )
    assert _runs()[-1].bursa_updated_on == date(2026, 10, 30)
    assert all(c.change_type == "added" for c in _changes())


def test_a_bad_dated_seed_fails_and_leaves_the_list(tmp_path):
    bad = _SEED2.replace("2026-10-30", "2027-01-01", 1)
    assert script.run(from_file=_seed_file(tmp_path, bad), now=D1) == 1
    assert not _current()
    last = _runs()[-1]
    assert (last.outcome, last.detail, last.bursa_updated_on) == ("parse_failed", "seed_bursa_updated", None)


def test_a_trading_status_change_is_recorded_like_any_other_change(tmp_path):
    script.run(from_file=_seed_file(tmp_path, _SEED2), now=D1)
    later = _SEED2.replace("pending_plan,Suspended", "pending_plan,trading")
    assert script.run(from_file=_seed_file(tmp_path, later), now=D2) == 0
    (chg,) = [c for c in _changes() if c.change_type == "trading_changed"]
    assert (chg.stock_code, chg.previous_trading_status, chg.trading_status) == ("1001", "suspended", "trading")
    assert chg.observed_on == D2.date()
    assert _current()["1001"].trading_status == "trading"
    assert _runs()[-1].changed == 1


def test_learning_a_trading_status_that_was_unknown_is_not_a_recorded_change(tmp_path):
    script.run(from_file=_seed_file(tmp_path, _SEED), now=D1)
    script.run(from_file=_seed_file(tmp_path, _SEED2), now=D2)
    assert not [c for c in _changes() if c.change_type == "trading_changed"]
    assert _current()["1001"].trading_status == "suspended"


def _listed(trading: str | None, bursa_updated: date | None = date(2026, 10, 30)) -> pn17.Status:
    return pn17.Status(
        pn17.STATE_LISTED, as_of=TODAY, first_seen=TODAY, baseline=TODAY, bursa_updated=bursa_updated,
        row=pn17.Row("1001", "Alpha Fixture Berhad", "Main", pn17.CATEGORY_PN17, "pending_plan", trading),
    )


_SRC = "Source: Bursa Malaysia PN17 and GN3 list, read weekly by AMI."


def test_listed_line_with_trading_suspended_and_bursas_date():
    assert pn17.line(_listed("suspended")) == (
        "Bursa PN17/GN3 status: listed as a PN17 issuer (Main Market, plan pending, trading suspended); "
        "already on Bursa's list when AMI first read it (2026-11-26); "
        f"Bursa's list updated 2026-10-30, read by AMI 2026-11-26. {_SRC}"
    )


def test_listed_line_says_trading_when_trading_and_omits_it_when_unknown():
    assert "(Main Market, plan pending, trading);" in pn17.line(_listed("trading"))
    unknown = pn17.line(_listed(None))
    assert "(Main Market, plan pending);" in unknown and "trading" not in unknown.split(";")[0]


def test_not_listed_line_states_bursas_date_and_the_read_date():
    st = pn17.Status(pn17.STATE_NOT_LISTED, as_of=TODAY, bursa_updated=date(2026, 10, 30))
    assert pn17.line(st) == (
        "Bursa PN17/GN3 status: not on Bursa's PN17/GN3 list "
        f"(Bursa's list updated 2026-10-30, read by AMI 2026-11-26). {_SRC}"
    )


def test_an_unknown_bursa_date_is_never_invented():
    listed = pn17.line(_listed("suspended", bursa_updated=None))
    assert "read by AMI 2026-11-26. Source" in listed and "Bursa's list updated" not in listed
    st = pn17.Status(pn17.STATE_NOT_LISTED, as_of=TODAY)
    assert pn17.line(st) == (
        f"Bursa PN17/GN3 status: not on Bursa's PN17/GN3 list (read by AMI 2026-11-26). {_SRC}"
    )


def test_stale_stays_keyed_on_amis_read_date_not_bursas(tmp_path):
    script.run(from_file=_seed_file(tmp_path, _SEED2), now=D1)
    fresh = _status("1001.KL", D1.date() + timedelta(days=14))
    assert fresh.state == pn17.STATE_LISTED and fresh.bursa_updated == date(2026, 10, 30)
    stale = _status("1001.KL", D1.date() + timedelta(days=15))
    assert stale.state == pn17.STATE_STALE
    assert "Bursa's list updated" not in pn17.line(stale)
    assert f"last successful read {D1.date().isoformat()}" in pn17.line(stale)


def test_the_stored_status_renders_trading_and_bursas_date_on_the_line(tmp_path):
    script.run(from_file=_seed_file(tmp_path, _SEED2), now=D1)
    text = pn17.line(_status("1001.KL", D1.date()))
    assert "(Main Market, plan pending, trading suspended)" in text
    assert f"Bursa's list updated 2026-10-30, read by AMI {D1.date().isoformat()}" in text


def test_the_follow_up_migration_is_additive_idempotent_and_reversible(tmp_path):
    import importlib.util

    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    path = _BACKEND / "alembic" / "versions" / "cr286b1c2d3e4_bursa_pn17_trading_and_update_date.py"
    spec = importlib.util.spec_from_file_location("cr286b_mig", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.down_revision == "cr286a0b0c0d1"
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'mig.db'}")
    with engine.begin() as conn:
        for t in ("bursa_pn17_current", "bursa_pn17_changes", "bursa_pn17_runs"):
            conn.execute(sa.text(f"CREATE TABLE {t} (id VARCHAR PRIMARY KEY)"))
        ops = Operations(MigrationContext.configure(conn))
        with Operations.context(ops.migration_context):
            mod.upgrade()
            mod.upgrade()
        for model in (BursaPn17CurrentRow, BursaPn17ChangeRow, BursaPn17RunRow):
            db_cols = {c["name"]: c for c in sa.inspect(conn).get_columns(model.__tablename__)}
            for name in ("trading_status", "previous_trading_status", "bursa_updated_on"):
                if name in model.__table__.columns:
                    assert name in db_cols and db_cols[name]["nullable"] is True
        with Operations.context(ops.migration_context):
            mod.downgrade()
        for t in ("bursa_pn17_current", "bursa_pn17_changes", "bursa_pn17_runs"):
            assert {c["name"] for c in sa.inspect(conn).get_columns(t)} == {"id"}


def test_single_alembic_head_is_the_follow_up_migration():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(_BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND / "alembic"))
    assert ScriptDirectory.from_config(cfg).get_heads() == ["cr286b1c2d3e4"]
