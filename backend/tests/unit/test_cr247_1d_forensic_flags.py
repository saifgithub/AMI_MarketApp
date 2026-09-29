"""CR247 Phase 1D — the four forensic metadata flags and the safety-floor
extension.

The flags are computed in Python from CR244's EDGAR reads and rendered as
sheet lines in the News/Macro lane; the LLM never computes a figure
(standing rule, DEF066→DEF241):

  1. Insider open-market buy/sell ratio (90d) — Form 4/5 codes P/S only,
     reusing `edgar_ownership`'s direction classification (M exercises, F
     withholdings and every other code are "other" there and excluded here).
  2. Rule 10b5-1 plan tag on insider sales — the Form 4's own `aff10b5One`
     checkbox (CR244's structural `plan_type`), never inferred.
  3. Cluster buying — ≥3 distinct insiders, code P, filing dates inside a
     14-day window. Absence renders ("no cluster buying"), never omits.
  4. 8-K timing/item flags (180d) — Friday ≥4:00 pm ET filings, Item 4.01
     (auditor change), Item 4.02 (non-reliance). Item 4.02 additionally
     hard-blocks a BUY at the safety floor, narrated in the verdict reason.

Pinned here: the per-flag math (P/S-only counting, cluster window logic,
Friday-ET boundary), the line renderers' exact labels, the overlay's live /
not_available / partial / live-only degrade states, the feed's new
`fetch_8k_item_flags` parse (item codes through edgar_8k's ONE token rule),
the render seam, and the Item 4.02 floor block (BUY blocked + narration;
APPROVE without the flag untouched; PASS untouched; SELL not trapped).
"""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path as _FsPath
from uuid import uuid4

import pytest

from app.agents.safety_floor import enforce_safety_floor
from app.core.config import settings
from app.schemas import AgentId, Mandate, Verdict, VerdictAction
from app.schemas.company_profile import (
    InsiderResponse,
    InsiderSummary,
    InsiderTransaction,
)
from app.schemas.trade import OrderType, ProposedTrade, Side
from app.services import (
    edgar_filings_feed,
    edgar_forensics,
    edgar_ownership,
    room_prompts,
    room_runner,
)
from app.services.room_runner import _assemble_verdict, _RoomContext

_THIS_DIR = _FsPath(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import test_config_compose_parity as _compose_parity  # noqa: E402

_NOW = datetime.now(UTC).date()  # the overlays window off the wall clock
_TODAY = date(2026, 9, 29)
_WS = date(2026, 7, 1)  # 90 days before _TODAY
_8K_WS = date(2026, 4, 2)  # 180 days before _TODAY


def _days_ago(n: int) -> str:
    return (_NOW - timedelta(days=n)).isoformat()


def _tx(
    code: str, direction: str, *, insider: str = "Jane Doe", filed: str = "2026-09-15",
    plan: str = "unstated",
) -> InsiderTransaction:
    return InsiderTransaction(
        form="4", filed_date=filed, transaction_date=filed,
        insider_name=insider, role="Officer", code=code, code_label=code,
        direction=direction, shares=100.0, price=1.0, plan_type=plan,
        url="https://example.test/form4.xml",
    )


def _insider_response(
    transactions: list[InsiderTransaction], *, state: str = "live", reason: str | None = None,
) -> InsiderResponse:
    buys = sum(1 for t in transactions if t.direction == "buy")
    sells = sum(1 for t in transactions if t.direction == "sell")
    other = len(transactions) - buys - sells
    net = "mixed" if buys and sells else "buying" if buys else "selling" if sells else "none"
    return InsiderResponse(
        ticker="AAPL", as_of=datetime(2026, 9, 29, tzinfo=UTC).isoformat(),
        cik="0000320193", state=state, reason=reason, sources=["edgar"],
        window_days=90, summary=InsiderSummary(buys=buys, sells=sells, other=other, net_direction=net),
        transactions=transactions,
    )


def _eight_k(
    filed: str, *, items: tuple[str, ...] = (), acceptance: datetime | None = None,
    accession: str = "0001-test", form: str = "8-K",
) -> edgar_forensics.EightKFiling:
    return edgar_forensics.EightKFiling(
        form=form, filed=date.fromisoformat(filed), accession=accession,
        items=items, acceptance=acceptance,
    )


def _utc(y, m, d, hh, mm) -> datetime:
    return datetime(y, m, d, hh, mm, tzinfo=UTC)


# ── Flag 1 — the ratio counts P/S only, reusing edgar_ownership's classes ──


def test_the_ratio_counts_p_and_s_only() -> None:
    txns = [
        _tx("P", "buy"), _tx("P", "buy"),
        _tx("S", "sell"), _tx("S", "sell"), _tx("S", "sell"), _tx("S", "sell"),
        _tx("M", "other"), _tx("M", "other"),  # option exercises — excluded
        _tx("F", "other"),                      # tax withholding — excluded
        _tx("A", "other"),                      # grant — excluded
    ]
    r = edgar_forensics.insider_ratio(txns, window_start=_WS, window_end=_TODAY)
    assert (r.buys, r.sells) == (2, 4)
    assert r.ratio == 0.5


def test_the_ratio_windows_by_filed_date() -> None:
    txns = [
        _tx("P", "buy", filed="2026-06-30"),   # before the window — dropped
        _tx("P", "buy", filed="2026-07-01"),   # left edge, inclusive — counted
        _tx("S", "sell", filed=str(_TODAY)),   # right edge, inclusive — counted
        _tx("S", "sell", filed="2026-09-30"),  # after the window — dropped
    ]
    r = edgar_forensics.insider_ratio(txns, window_start=_WS, window_end=_TODAY)
    assert (r.buys, r.sells) == (1, 1)


def test_no_sell_side_means_no_ratio_not_infinity() -> None:
    r = edgar_forensics.insider_ratio([_tx("P", "buy")], window_start=_WS, window_end=_TODAY)
    assert r.sells == 0 and r.ratio is None
    line = edgar_forensics.insider_ratio_line(r, live=True)
    assert "no sell side to ratio against" in line


def test_the_empty_window_renders_absence_not_omission() -> None:
    line = edgar_forensics.insider_ratio_line(
        edgar_forensics.insider_ratio([], window_start=_WS, window_end=_TODAY), live=True,
    )
    assert "no open-market insider purchases or sales" in line
    assert _WS.isoformat() in line and _TODAY.isoformat() in line


def test_the_ratio_line_states_counts_window_and_ami_computed() -> None:
    r = edgar_forensics.insider_ratio(
        [_tx("P", "buy"), _tx("S", "sell"), _tx("S", "sell")],
        window_start=_WS, window_end=_TODAY,
    )
    line = edgar_forensics.insider_ratio_line(r, live=True)
    assert line.startswith("Insider open-market buy/sell ratio (90d) (LIVE)")
    assert "1 open-market buy vs 2 open-market sales" in line
    assert "0.50 buys per sale" in line
    assert "AMI-computed from the issuer's SEC Form 4/5 filings" in line
    assert "codes P/S only" in line


def test_a_partial_feed_carries_its_caveat_on_the_line() -> None:
    line = edgar_forensics.insider_ratio_line(
        edgar_forensics.insider_ratio([_tx("S", "sell")], window_start=_WS, window_end=_TODAY),
        live=True, partial_reason="Showing the 25 most recent filings in the window",
    )
    assert "incomplete feed: Showing the 25 most recent filings in the window" in line


# ── Flag 2 — the 10b5-1 plan tag is the checkbox, never an inference ────────


def test_the_plan_tag_splits_the_windows_open_market_sales() -> None:
    txns = [
        _tx("S", "sell", plan="scheduled_10b5-1"),
        _tx("S", "sell", plan="scheduled_10b5-1"),
        _tx("S", "sell", plan="scheduled_10b5-1"),
        _tx("S", "sell", plan="discretionary"),
        _tx("S", "sell"),  # unstated (pre-2023 form)
        _tx("P", "buy", plan="scheduled_10b5-1"),  # buys don't carry the tag
    ]
    p = edgar_forensics.insider_plan_tag(txns, window_start=_WS, window_end=_TODAY)
    assert (p.sales, p.scheduled, p.discretionary, p.unstated) == (5, 3, 1, 1)
    line = edgar_forensics.insider_plan_tag_line(p, live=True)
    assert "of the 5 open-market sales in the window, 3 were pre-scheduled" in line
    assert "Form 4's own 10b5-1 checkbox, never inferred" in line
    assert "1 discretionary, 1 unstated" in line
    assert "not fresh conviction" in line


def test_the_plan_tag_with_no_sales_renders_absence() -> None:
    line = edgar_forensics.insider_plan_tag_line(
        edgar_forensics.insider_plan_tag([], window_start=_WS, window_end=_TODAY), live=True,
    )
    assert "none — no open-market insider sales filed" in line
    assert "has nothing to attach to" in line


# ── Flag 3 — cluster buying ─────────────────────────────────────────────────


def test_three_distinct_insiders_inside_14_days_is_a_cluster() -> None:
    txns = [
        _tx("P", "buy", insider="A", filed="2026-09-01"),
        _tx("P", "buy", insider="B", filed="2026-09-05"),
        _tx("P", "buy", insider="C", filed="2026-09-12"),
    ]
    c = edgar_forensics.cluster_buy(txns, window_start=_WS, window_end=_TODAY)
    assert c.cluster is True and c.insiders == 3
    assert (c.span_start, c.span_end) == (date(2026, 9, 1), date(2026, 9, 12))
    line = edgar_forensics.cluster_buy_line(c, live=True)
    assert "Cluster buying (LIVE): YES — 3 distinct insiders bought in the open market" in line
    assert "between 2026-09-01 and 2026-09-12" in line


def test_two_insiders_is_not_a_cluster_and_absence_renders() -> None:
    txns = [
        _tx("P", "buy", insider="A", filed="2026-09-01"),
        _tx("P", "buy", insider="B", filed="2026-09-02"),
    ]
    c = edgar_forensics.cluster_buy(txns, window_start=_WS, window_end=_TODAY)
    assert c.cluster is False
    line = edgar_forensics.cluster_buy_line(c, live=True)
    assert "Cluster buying: none — no cluster buying in the last 90 days" in line


def test_three_insiders_spanning_more_than_14_days_is_not_a_cluster() -> None:
    txns = [
        _tx("P", "buy", insider="A", filed="2026-09-01"),
        _tx("P", "buy", insider="B", filed="2026-09-08"),
        _tx("P", "buy", insider="C", filed="2026-09-16"),  # 15 days after A
    ]
    c = edgar_forensics.cluster_buy(txns, window_start=_WS, window_end=_TODAY)
    assert c.cluster is False


def test_the_14_day_window_edge_is_inclusive() -> None:
    txns = [
        _tx("P", "buy", insider="A", filed="2026-09-01"),
        _tx("P", "buy", insider="B", filed="2026-09-15"),  # exactly 14 days — inside
        _tx("P", "buy", insider="C", filed="2026-09-15"),
    ]
    c = edgar_forensics.cluster_buy(txns, window_start=_WS, window_end=_TODAY)
    assert c.cluster is True and c.insiders == 3


def test_the_same_insider_three_times_is_one_distinct_insider() -> None:
    txns = [_tx("P", "buy", insider="A", filed=f"2026-09-0{i}") for i in (1, 2, 3)]
    c = edgar_forensics.cluster_buy(txns, window_start=_WS, window_end=_TODAY)
    assert c.cluster is False and c.insiders == 0


# ── Flag 4 — 8-K timing/item flags ───────────────────────────────────────────


def test_friday_after_4pm_et_is_flagged_at_the_boundary() -> None:
    # 2026-09-25 is a Friday. EDT is UTC-4, so 4:00 pm ET == 20:00 UTC.
    filings = [
        _eight_k("2026-09-25", acceptance=_utc(2026, 9, 25, 20, 0)),   # exactly 4pm — inside
        _eight_k("2026-09-25", acceptance=_utc(2026, 9, 25, 16, 5)),   # 12:05 pm ET — before
        _eight_k("2026-09-24", acceptance=_utc(2026, 9, 24, 20, 5)),   # Thursday 4pm — not Friday
        _eight_k("2026-09-25", acceptance=_utc(2026, 9, 25, 21, 30)),  # 5:30 pm ET — inside
    ]
    f = edgar_forensics.eight_k_flags(filings, window_start=_8K_WS, window_end=_TODAY)
    assert len(f.friday_after_close) == 2
    assert f.friday_timing_determinable is True
    line = edgar_forensics.eight_k_flags_lines(f)[0]
    assert line.startswith("8-K Friday-after-close filings (180d): 2")
    assert "4:00 pm ET" in line
    assert "5:30 pm ET" in " ".join(edgar_forensics.eight_k_flags_lines(f))


def test_friday_after_4pm_et_respects_eastern_standard_time_in_winter() -> None:
    # 2026-01-02 is a Friday. EST is UTC-5, so 4:00 pm ET == 21:00 UTC.
    filings = [_eight_k("2026-01-02", acceptance=_utc(2026, 1, 2, 21, 1))]
    f = edgar_forensics.eight_k_flags(
        filings, window_start=date(2025, 12, 1), window_end=date(2026, 9, 29),
    )
    assert len(f.friday_after_close) == 1


def test_the_friday_flag_without_acceptance_times_is_not_determinable() -> None:
    filings = [_eight_k("2026-09-25")]  # index carried no acceptance column
    f = edgar_forensics.eight_k_flags(filings, window_start=_8K_WS, window_end=_TODAY)
    assert f.friday_timing_determinable is False
    assert "not determinable" in edgar_forensics.eight_k_flags_lines(f)[0]


def test_item_401_and_402_are_detected_and_dated() -> None:
    filings = [
        _eight_k("2026-08-14", items=("2.02", "4.02"), accession="0001140361-26-000001"),
        _eight_k("2026-07-20", items=("4.01",), accession="0001140361-26-000002"),
        _eight_k("2026-09-01", items=("5.02",)),
    ]
    f = edgar_forensics.eight_k_flags(filings, window_start=_8K_WS, window_end=_TODAY)
    assert [x.filed.isoformat() for x in f.item_402] == ["2026-08-14"]
    assert [x.filed.isoformat() for x in f.item_401] == ["2026-07-20"]
    lines = edgar_forensics.eight_k_flags_lines(f)
    assert "8-K Item 4.01 (change of auditor) (180d): 1 — 2026-07-20" in lines[1]
    assert "8-K Item 4.02 (non-reliance on prior financials) (180d): 1 — 2026-08-14" in lines[2]
    assert "safety floor hard-blocks new BUY proposals" in lines[2]


def test_absent_items_render_none_not_omission() -> None:
    f = edgar_forensics.eight_k_flags([], window_start=_8K_WS, window_end=_TODAY)
    lines = edgar_forensics.eight_k_flags_lines(f)
    assert lines[1] == (
        "8-K Item 4.01 (change of auditor) (180d): none filed between "
        "2026-04-02 and 2026-09-29."
    )
    assert lines[2].startswith(
        "8-K Item 4.02 (non-reliance on prior financials) (180d): none filed"
    )


def test_item_402_block_reason_names_the_newest_filing() -> None:
    filings = [
        _eight_k("2026-08-14", items=("4.02",), accession="ACC-1"),
        _eight_k("2026-09-10", items=("4.02",), accession="ACC-2"),
    ]
    f = edgar_forensics.eight_k_flags(filings, window_start=_8K_WS, window_end=_TODAY)
    reason = edgar_forensics.item_402_block_reason(f)
    assert reason is not None
    assert "2026-09-10" in reason and "ACC-2" in reason
    assert "non-reliance" in reason
    clean = edgar_forensics.eight_k_flags([], window_start=_8K_WS, window_end=_TODAY)
    assert edgar_forensics.item_402_block_reason(clean) is None


def test_the_not_available_line_degrades_loudly() -> None:
    line = edgar_forensics.forensic_not_available_line(
        edgar_forensics.INSIDER_RATIO_LABEL, "SEC EDGAR is temporarily unavailable",
    )
    assert line.startswith("Insider open-market buy/sell ratio (90d): not available this call")
    assert "SEC EDGAR is temporarily unavailable" in line
    assert "Do not estimate insider or filing activity from memory" in line


# ── The feed's 8-K flag parse (fetch_8k_item_flags) ──────────────────────────


@pytest.fixture(autouse=True)
def _clear_feed_cache():
    edgar_filings_feed.clear_filings_feed_cache()
    yield
    edgar_filings_feed.clear_filings_feed_cache()


def _submissions_with_8ks(rows: list[dict]) -> dict:
    n = len(rows)
    return {
        "filings": {
            "recent": {
                "form": [r.get("form", "8-K") for r in rows],
                "filingDate": [r["filed"] for r in rows],
                "accessionNumber": [r.get("accession", "0001-x") for r in rows],
                "items": [r.get("items", "") for r in rows],
                "acceptanceDateTime": [r.get("acceptance") for r in rows],
                "fileNumber": [""] * n,
                "primaryDocDescription": [None] * n,
            }
        }
    }


def test_the_feed_parses_item_codes_acceptance_and_windows_them(monkeypatch) -> None:
    monkeypatch.setattr(edgar_filings_feed, "resolve_cik", lambda t: 320193)
    monkeypatch.setattr(
        edgar_filings_feed, "_fetch_company_submissions",
        lambda cik: _submissions_with_8ks([
            {"filed": "2026-08-14", "items": "2.02,4.02", "accession": "ACC-1",
             "acceptance": "2026-08-14T20:05:00Z"},
            {"filed": "2026-09-25", "items": "5.02", "accession": "ACC-2",
             "acceptance": "2026-09-25T20:05:00Z"},
            {"filed": "2026-03-31", "items": "4.01", "accession": "ACC-0"},  # outside window
            {"filed": "2026-09-20", "items": "8.01", "accession": "ACC-3", "form": "8-K/A"},
        ]),
    )
    state, rows = edgar_filings_feed.fetch_8k_item_flags("AAPL", _TODAY)
    assert state == "live"
    assert [r["filed"] for r in rows] == ["2026-09-25", "2026-09-20", "2026-08-14"]
    assert rows[0]["items"] == ("5.02",)
    assert rows[0]["acceptance"] == "2026-09-25T20:05:00Z"
    assert rows[1]["form"] == "8-K/A"


def test_the_feed_degrades_on_no_cik_and_on_fetch_failure(monkeypatch) -> None:
    monkeypatch.setattr(edgar_filings_feed, "resolve_cik", lambda t: None)
    assert edgar_filings_feed.fetch_8k_item_flags("ZZZZ", _TODAY) == ("not_available", None)

    monkeypatch.setattr(edgar_filings_feed, "resolve_cik", lambda t: 320193)
    monkeypatch.setattr(edgar_filings_feed, "_fetch_company_submissions", lambda cik: None)
    assert edgar_filings_feed.fetch_8k_item_flags("AAPL", _TODAY) == ("not_available", None)


def test_the_feed_degrades_on_a_malformed_8k_items_row(monkeypatch) -> None:
    """P26: an 8-K whose item codes can't be read voids the 'none' claim —
    the whole read is not_available, never a partial index rendered as live."""
    monkeypatch.setattr(edgar_filings_feed, "resolve_cik", lambda t: 320193)
    monkeypatch.setattr(
        edgar_filings_feed, "_fetch_company_submissions",
        lambda cik: _submissions_with_8ks([
            {"filed": "2026-09-01", "items": "not-a-list", "accession": "ACC-9"},
        ]),
    )
    assert edgar_filings_feed.fetch_8k_item_flags("AAPL", _TODAY) == ("not_available", None)


def test_the_feed_pulls_the_files_page_when_recent_is_too_young(monkeypatch) -> None:
    """Audit B2 for the flags read: `recent` not reaching the window's left
    edge merges the overlapping `filings.files` page; a page failure is
    not_available, never a truncated live list."""
    calls: list[str] = []

    def _page(cik: int, name: str):
        calls.append(name)
        # `filings.files` pages are shaped like `filings.recent` itself —
        # flat column arrays, no wrapper.
        return _submissions_with_8ks([
            {"filed": "2026-04-10", "items": "4.02", "accession": "ACC-OLD"},
        ])["filings"]["recent"]

    recent_only = _submissions_with_8ks([
        {"filed": "2026-09-01", "items": "8.01", "accession": "ACC-NEW"},
    ])
    recent_only["filings"]["files"] = [
        {"name": "CIK0000320193-old.json", "filingFrom": "2026-01-01", "filingTo": "2026-06-30"},
    ]
    monkeypatch.setattr(edgar_filings_feed, "resolve_cik", lambda t: 320193)
    monkeypatch.setattr(edgar_filings_feed, "_fetch_company_submissions", lambda cik: recent_only)
    monkeypatch.setattr(edgar_filings_feed, "_fetch_submissions_page", _page)

    state, rows = edgar_filings_feed.fetch_8k_item_flags("AAPL", _TODAY)
    assert state == "live"
    assert calls == ["CIK0000320193-old.json"]
    assert any(r["filed"] == "2026-04-10" for r in rows)

    def _page_fails(cik: int, name: str):
        return None

    monkeypatch.setattr(edgar_filings_feed, "_fetch_submissions_page", _page_fails)
    edgar_filings_feed.clear_filings_feed_cache()
    assert edgar_filings_feed.fetch_8k_item_flags("AAPL", _TODAY) == ("not_available", None)


# ── The overlays (room_runner) ───────────────────────────────────────────────


@pytest.fixture
def real_market_data():
    prior = settings.use_real_market_data
    settings.use_real_market_data = True
    yield
    settings.use_real_market_data = prior


def test_the_insider_overlay_populates_three_keys_and_lines(monkeypatch, real_market_data) -> None:
    txns = [
        _tx("P", "buy", insider="A", filed=_days_ago(20)),
        _tx("P", "buy", insider="B", filed=_days_ago(16)),
        _tx("P", "buy", insider="C", filed=_days_ago(9)),
        _tx("S", "sell", plan="scheduled_10b5-1"),
        _tx("S", "sell"),
    ]
    monkeypatch.setattr(
        edgar_ownership, "get_insider_activity", lambda t: _insider_response(txns),
    )
    profile: dict = {"field_state": {}}
    fs = profile["field_state"]
    room_runner._overlay_insider_forensics(profile, fs, "AAPL", None)
    assert fs["insider_ratio"] == "live"
    assert fs["insider_plan_tag"] == "live"
    assert fs["insider_cluster"] == "live"
    assert "YES — 3 distinct insiders" in profile["insider_cluster_line"]
    assert "of the 2 open-market sales in the window, 1 was pre-scheduled" in (
        profile["insider_plan_tag_line"]
    )
    assert "1.50 buys per sale" in profile["insider_ratio_line"]


def test_the_insider_overlay_degrades_loudly(monkeypatch, real_market_data) -> None:
    monkeypatch.setattr(
        edgar_ownership, "get_insider_activity",
        lambda t: _insider_response([], state="not_available", reason="SEC EDGAR is temporarily unavailable"),
    )
    profile: dict = {"field_state": {}}
    fs = profile["field_state"]
    room_runner._overlay_insider_forensics(profile, fs, "AAPL", None)
    for key in ("insider_ratio", "insider_plan_tag", "insider_cluster"):
        assert fs[key] == "unavailable"
    assert "temporarily unavailable" in profile["insider_unavailable_reason"]


def test_the_insider_overlay_is_live_only_for_asof_runs(monkeypatch, real_market_data) -> None:
    monkeypatch.setattr(
        edgar_ownership, "get_insider_activity",
        lambda t: _insider_response([_tx("P", "buy", filed=_days_ago(5))]),
    )
    profile: dict = {"field_state": {}}
    fs = profile["field_state"]
    room_runner._overlay_insider_forensics(profile, fs, "AAPL", _NOW - timedelta(days=30))
    for key in ("insider_ratio", "insider_plan_tag", "insider_cluster"):
        assert fs[key] == "unavailable"
    assert "no historical insider store" in profile["insider_unavailable_reason"]


def test_the_insider_overlay_absorbs_an_exception_loudly(monkeypatch, real_market_data) -> None:
    def _boom(t):
        raise RuntimeError("store exploded")
    monkeypatch.setattr(edgar_ownership, "get_insider_activity", _boom)
    profile: dict = {"field_state": {}}
    fs = profile["field_state"]
    room_runner._overlay_insider_forensics(profile, fs, "AAPL", None)
    for key in ("insider_ratio", "insider_plan_tag", "insider_cluster"):
        assert fs[key] == "unavailable"
    assert "could not be read" in profile["insider_unavailable_reason"]


def test_the_8k_overlay_populates_lines_and_arms_the_floor(monkeypatch, real_market_data) -> None:
    monkeypatch.setattr(
        edgar_filings_feed, "fetch_8k_item_flags",
        lambda t, as_of: ("live", [{
            "form": "8-K", "filed": "2026-08-14", "accession": "ACC-1",
            "items": ("4.02",), "acceptance": "2026-08-14T20:05:00Z",
        }]),
    )
    profile: dict = {"field_state": {}}
    fs = profile["field_state"]
    room_runner._overlay_edgar_8k_flags(profile, fs, "AAPL", None)
    assert fs["edgar_8k_flags"] == "live"
    lines = profile["edgar_8k_flag_lines"]
    assert lines[2].startswith("8-K Item 4.02 (non-reliance on prior financials) (180d): 1")
    assert profile["edgar_8k_item_402_block"] is not None
    assert "2026-08-14" in profile["edgar_8k_item_402_block"]
    assert "ACC-1" in profile["edgar_8k_item_402_block"]


def test_the_8k_overlay_supports_asof_and_passes_the_date_through(monkeypatch, real_market_data) -> None:
    seen: list[date] = []

    def _fake(t, as_of):
        seen.append(as_of)
        return "live", []

    monkeypatch.setattr(edgar_filings_feed, "fetch_8k_item_flags", _fake)
    profile: dict = {"field_state": {}}
    fs = profile["field_state"]
    as_of = _NOW - timedelta(days=30)
    room_runner._overlay_edgar_8k_flags(profile, fs, "AAPL", as_of)
    assert seen == [as_of]
    assert fs["edgar_8k_flags"] == "live"
    assert profile["edgar_8k_item_402_block"] is None


def test_the_8k_overlay_degrades_loudly(monkeypatch, real_market_data) -> None:
    monkeypatch.setattr(
        edgar_filings_feed, "fetch_8k_item_flags", lambda t, as_of: ("not_available", None),
    )
    profile: dict = {"field_state": {}}
    fs = profile["field_state"]
    room_runner._overlay_edgar_8k_flags(profile, fs, "AAPL", None)
    assert fs["edgar_8k_flags"] == "unavailable"
    assert "could not be read" in profile["edgar_8k_flags_unavailable_reason"]


# ── The render seam (room_prompts) ───────────────────────────────────────────


def _live_profile() -> dict:
    return {
        "ticker": "AAPL",
        "field_state": {
            "run_date": "live",
            "insider_ratio": "live",
            "insider_plan_tag": "live",
            "insider_cluster": "live",
            "edgar_8k_flags": "live",
        },
        "insider_ratio_line": (
            "Insider open-market buy/sell ratio (90d) (LIVE): 2 open-market buys vs 4 open-market "
            "sales filed between 2026-07-01 and 2026-09-29 (codes P/S only) — 0.50 buys per sale, "
            "AMI-computed from the issuer's SEC Form 4/5 filings."
        ),
        "insider_plan_tag_line": (
            "Insider sales under Rule 10b5-1 plans (LIVE): of the 4 open-market sales in the "
            "window, 3 were pre-scheduled under Rule 10b5-1 plans (flag read from the Form 4's "
            "own 10b5-1 checkbox, never inferred), 1 discretionary, 0 unstated — a scheduled "
            "plan sale is not fresh conviction; a non-plan or unstated sale is the stronger signal."
        ),
        "insider_cluster_line": (
            "Cluster buying (LIVE): YES — 3 distinct insiders bought in the open market between "
            "2026-09-01 and 2026-09-12 (code P; window 2026-07-01 to 2026-09-29), AMI-computed "
            "from the issuer's SEC Form 4/5 filings."
        ),
        "edgar_8k_flag_lines": [
            "8-K Friday-after-close filings (180d): none filed Friday at/after 4:00 pm ET between 2026-04-02 and 2026-09-29.",
            "8-K Item 4.01 (change of auditor) (180d): none filed between 2026-04-02 and 2026-09-29.",
            "8-K Item 4.02 (non-reliance on prior financials) (180d): none filed between 2026-04-02 and 2026-09-29.",
        ],
        "edgar_8k_item_402_block": None,
    }


@pytest.fixture(autouse=True)
def _flags_restored():
    saved = {f: getattr(settings, f) for f in (
        "room_insider_ratio_enabled", "room_insider_plan_tag_enabled",
        "room_insider_cluster_enabled", "room_edgar_8k_flags_enabled",
    )}
    yield
    for f, v in saved.items():
        setattr(settings, f, v)


def test_the_four_flags_default_on_and_render_in_the_news_lane() -> None:
    for f in ("room_insider_ratio_enabled", "room_insider_plan_tag_enabled",
              "room_insider_cluster_enabled", "room_edgar_8k_flags_enabled"):
        assert getattr(settings, f) is True
    sheet = room_prompts._format_profile(_live_profile(), AgentId.NEWS_ANALYST)
    for fragment in (
        "Insider open-market buy/sell ratio (90d) (LIVE)",
        "Insider sales under Rule 10b5-1 plans (LIVE)",
        "Cluster buying (LIVE): YES — 3 distinct insiders",
        "8-K Friday-after-close filings (180d): none filed",
        "8-K Item 4.01 (change of auditor) (180d): none filed",
        "8-K Item 4.02 (non-reliance on prior financials) (180d): none filed",
    ):
        assert fragment in sheet, f"news sheet lost: {fragment}"
    # Header bullets disclose the four fields too.
    for fragment in (
        "- Insider open-market buy/sell ratio (90d): LIVE",
        "- Insider sales under Rule 10b5-1 plans: LIVE",
        "- Cluster buying: LIVE",
        "- 8-K forensic flags: LIVE",
    ):
        assert fragment in sheet, f"news header lost: {fragment}"


def test_the_lines_reach_the_full_sheet_and_not_the_technicals_lane() -> None:
    assert "Insider open-market buy/sell ratio (90d) (LIVE)" in room_prompts._format_profile(_live_profile())
    market_sheet = room_prompts._format_profile(_live_profile(), AgentId.MARKET_ANALYST)
    assert "Insider open-market buy/sell ratio" not in market_sheet
    assert "8-K forensic flags" not in market_sheet


def test_nothing_renders_with_the_flags_off() -> None:
    settings.room_insider_ratio_enabled = False
    settings.room_insider_plan_tag_enabled = False
    settings.room_insider_cluster_enabled = False
    settings.room_edgar_8k_flags_enabled = False
    sheet = room_prompts._format_profile(_live_profile(), AgentId.NEWS_ANALYST)
    assert "Insider open-market" not in sheet
    assert "10b5-1" not in sheet
    assert "Cluster buying" not in sheet
    assert "8-K forensic" not in sheet


def test_presence_is_not_provenance() -> None:
    """A hand-built profile with the lines but no recorded provenance must not
    render them as LIVE — the not-available degrade still names each field."""
    profile = _live_profile()
    profile["field_state"] = {}
    sheet = room_prompts._format_profile(profile, AgentId.NEWS_ANALYST)
    assert "Insider open-market buy/sell ratio (90d) (LIVE)" not in sheet
    assert "Cluster buying (LIVE)" not in sheet
    assert "Insider open-market buy/sell ratio (90d): not available this call" in sheet
    assert "Cluster buying: not available this call" in sheet
    assert "8-K forensic flags: not available this call" in sheet


def test_unavailable_blocks_render_their_reasons() -> None:
    profile = _live_profile()
    profile["field_state"] = {
        "insider_ratio": "unavailable",
        "insider_plan_tag": "unavailable",
        "insider_cluster": "unavailable",
        "edgar_8k_flags": "unavailable",
    }
    profile["insider_unavailable_reason"] = "no historical insider store"
    profile["edgar_8k_flags_unavailable_reason"] = "the SEC filings index could not be read"
    sheet = room_prompts._format_profile(profile, AgentId.NEWS_ANALYST)
    assert "Insider open-market buy/sell ratio (90d): not available this call — no historical insider store" in sheet
    assert "8-K forensic flags: not available this call — the SEC filings index could not be read" in sheet


# ── The Item 4.02 safety-floor block ─────────────────────────────────────────


_BLOCK = (
    "an 8-K Item 4.02 (non-reliance on previously issued financial statements) was filed on "
    "2026-08-14 (accession ACC-1), inside the 180-day window ending 2026-09-29 — AMI does not "
    "open a new BUY while the issuer's reported figures are under non-reliance; wait for the "
    "restated or re-audited statements before buying"
)
_HARMLESS = {
    "holdings": [], "last_loss_closed_at": None, "trade_open_timestamps": [],
    "existing_open_risk_pct": 0.0,
}


def _approve() -> Verdict:
    return Verdict(action=VerdictAction.APPROVE, reason="Clean thesis", size_pct=3.0,
                   approve_votes=4, samples=5)


def test_item_402_blocks_a_buy_with_the_narration(base_mandate: Mandate) -> None:
    final = enforce_safety_floor(
        _approve(),
        ProposedTrade(ticker="AAPL", side=Side.BUY, quantity=10,
                      order_type=OrderType.LIMIT, limit_price=100.0),
        portfolio_value=100_000, current_drawdown_pct=0.0, mandate=base_mandate,
        edgar_8k_item_402=_BLOCK, **_HARMLESS,
    )
    assert final.action == VerdictAction.REJECT
    assert final.overridden_from_llm is True
    assert "Forensic 8-K flag (safety floor override):" in final.reason
    assert "2026-08-14" in final.reason and "ACC-1" in final.reason
    assert "non-reliance" in final.reason
    # CR214 — the vote travels with the override.
    assert final.approve_votes == 4 and final.samples == 5


def test_item_402_leaves_approve_unaffected_without_the_flag(base_mandate: Mandate) -> None:
    final = enforce_safety_floor(
        _approve(),
        ProposedTrade(ticker="AAPL", side=Side.BUY, quantity=10,
                      order_type=OrderType.LIMIT, limit_price=100.0),
        portfolio_value=100_000, current_drawdown_pct=0.0, mandate=base_mandate,
        edgar_8k_item_402=None, **_HARMLESS,
    )
    assert final.action == VerdictAction.APPROVE
    assert final.overridden_from_llm is False


def test_item_402_respects_the_kill_switch(base_mandate: Mandate) -> None:
    """Flag off = the control arm: the narration may be present but the floor
    must not veto — the A/B arm changes the verdict with the sheet line."""
    prior = settings.room_edgar_8k_flags_enabled
    settings.room_edgar_8k_flags_enabled = False
    try:
        final = enforce_safety_floor(
            _approve(),
            ProposedTrade(ticker="AAPL", side=Side.BUY, quantity=10,
                          order_type=OrderType.LIMIT, limit_price=100.0),
            portfolio_value=100_000, current_drawdown_pct=0.0, mandate=base_mandate,
            edgar_8k_item_402=_BLOCK, **_HARMLESS,
        )
    finally:
        settings.room_edgar_8k_flags_enabled = prior
    assert final.action == VerdictAction.APPROVE


def test_item_402_never_touches_pass_or_llm_rejects(base_mandate: Mandate) -> None:
    passed = Verdict(action=VerdictAction.PASS, reason="No setup worth buying")
    final = enforce_safety_floor(
        passed,
        ProposedTrade(ticker="AAPL", side=Side.BUY, quantity=10,
                      order_type=OrderType.LIMIT, limit_price=100.0),
        portfolio_value=100_000, current_drawdown_pct=0.0, mandate=base_mandate,
        edgar_8k_item_402=_BLOCK, **_HARMLESS,
    )
    assert final is passed  # PASS carries no trade — returned untouched, same object

    rejected = Verdict(action=VerdictAction.REJECT, reason="Weak case")
    final = enforce_safety_floor(
        rejected,
        ProposedTrade(ticker="AAPL", side=Side.BUY, quantity=10,
                      order_type=OrderType.LIMIT, limit_price=100.0),
        portfolio_value=100_000, current_drawdown_pct=0.0, mandate=base_mandate,
        edgar_8k_item_402=_BLOCK, **_HARMLESS,
    )
    assert final is rejected


def test_item_402_does_not_trap_the_exit_side(base_mandate: Mandate) -> None:
    """The block is BUY-only: a SELL must reach the mandate check unblocked
    (this book holds nothing, so the mandate check itself may REJECT — the
    pin is that the reason is never the forensic narration)."""
    final = enforce_safety_floor(
        _approve(),
        ProposedTrade(ticker="AAPL", side=Side.SELL, quantity=10,
                      order_type=OrderType.LIMIT, limit_price=100.0),
        portfolio_value=100_000, current_drawdown_pct=0.0, mandate=base_mandate,
        edgar_8k_item_402=_BLOCK, **_HARMLESS,
    )
    assert "Forensic 8-K flag" not in final.reason


def test_the_scripted_pm_path_applies_the_same_block(base_mandate: Mandate) -> None:
    """`_assemble_verdict` doesn't route through `enforce_safety_floor`, so
    the same veto is applied there — one rule, two call sites."""
    ctx = _RoomContext(
        ticker="AAPL", mandate=base_mandate, portfolio_value=100_000.0,
        current_drawdown_pct=0.0, halal_universe=set(),
        classification_universe=None, locale_allowed_universe=None,
        user_id=uuid4(),
        risk_last_loss_closed_at=None, risk_trade_open_timestamps=[],
        risk_existing_open_risk_pct=0.0,
    )
    blocked = _assemble_verdict(ctx, {"edgar_8k_item_402_block": _BLOCK})
    assert blocked.action == VerdictAction.REJECT
    assert "Forensic 8-K flag (safety floor override):" in blocked.reason
    assert "2026-08-14" in blocked.reason

    clean = _assemble_verdict(ctx, {})
    assert clean.action == VerdictAction.APPROVE


# ── Compose parity (the four env flags reach the container) ─────────────────


def test_the_four_flags_are_forwarded_in_compose() -> None:
    block = _compose_parity._api_alpha_env_block()
    for key in (
        "ROOM_INSIDER_RATIO_ENABLED",
        "ROOM_INSIDER_PLAN_TAG_ENABLED",
        "ROOM_INSIDER_CLUSTER_ENABLED",
        "ROOM_EDGAR_8K_FLAGS_ENABLED",
    ):
        assert f"{key}:" in block, f"{key} is not forwarded to api-alpha (DEF038/DEF063 class)"
