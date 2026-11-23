"""CR282 lane D — the SC Malaysia Shariah list as the `.KL` Sharia standard.

No network. The parser runs on a hand-made fixture in the shape pypdf extracts from the
real 29 May 2026 booklet (sc_malaysia_list_sample.txt: dot-less rows, 5-digit ACE/LEAP
codes, wrapped names, a two-column Table 2, the trailing business-trust table, the
Table 3 total). The refresh runs with an injected fetcher; the reader resolves from a
stored `SC_MALAYSIA` snapshot row (the autouse sqlite `_isolated_db`).

The through-line is CR040: a missing or stale SC snapshot is UNAVAILABLE, never a PASS,
and the flag-off world is the pre-CR282 world.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from app.core.config import Settings, settings
from app.db import get_session
from app.schemas.sharia import ShariaStatus
from app.services import sharia_sc_malaysia as sc
from app.services import sharia_universe as su
from app.services.sharia_universe import (
    HalalUniverse,
    ShariaSourceError,
    default_halal_universe,
    latest_snapshot,
    reset_refresh_failures,
    reset_sharia_universe_provider,
    run_sharia_sc_refresh_tick,
    write_snapshot,
)

def _today() -> date:
    """The UTC date the provider's staleness arithmetic uses — not the local one, which
    runs a day ahead of UTC for part of every day east of Greenwich."""
    return datetime.now(timezone.utc).date()


_FIX = Path(__file__).parent / "fixtures" / "sc_malaysia_list_sample.txt"
_LIST_DATE = date(2026, 5, 29)
_COMPLIANT = {
    "7086.KL", "5015.KL", "5183.KL", "5099.KL", "3026.KL", "0452.KL", "0308.KL", "03051.KL",
}


def _text() -> str:
    return _FIX.read_text(encoding="utf-8")


def _parse(**kw):
    return sc.parse_sc_list_text(_text(), min_rows=3, **kw)


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    reset_sharia_universe_provider(None)
    reset_refresh_failures()
    monkeypatch.setattr(settings, "sharia_screen_enabled", True)
    yield
    reset_sharia_universe_provider(None)


@pytest.fixture
def bursa_on(monkeypatch):
    monkeypatch.setattr(settings, "market_bursa_enabled", True)


@pytest.fixture
def bursa_off(monkeypatch):
    monkeypatch.setattr(settings, "market_bursa_enabled", False)


def _seed_sc(*, as_of, compliant=_COMPLIANT, non_compliant=("1155.KL",), fetched_at=None):
    with get_session() as s:
        write_snapshot(
            s,
            standard=sc.STANDARD_KEY,
            source_url="sc://test",
            parent_source_url="",
            compliant=compliant,
            as_of=as_of,
            parent=non_compliant,
            fetched_at=fetched_at or datetime.now(timezone.utc),
        )


def _seed_us(as_of=None):
    with get_session() as s:
        write_snapshot(
            s,
            standard=su.STANDARD,
            source_url="spus://test",
            parent_source_url="parent://test",
            compliant={"AAA"},
            as_of=as_of or _today() - timedelta(days=2),
            parent={"AAA", "ZZZ"},
            fetched_at=datetime.now(timezone.utc),
        )


# ── parser ───────────────────────────────────────────────────────────────────


def test_parse_fixture_reads_date_codes_names_and_cross_checks_the_total():
    parsed = _parse()
    assert parsed.as_of == _LIST_DATE
    assert parsed.compliant_tickers == _COMPLIANT
    assert parsed.declared_total == 8 == len(parsed.compliant)
    by_code = {s.code: s.name for s in parsed.compliant}
    assert by_code["5015"] == "APM Automotive Holdings Bhd"  # wrapped name rejoined
    assert by_code["0452"] == "Gold Li Holdings Bhd"  # dot-less row kept
    assert by_code["03051"] == "Alpha Ocean Resources Bhd"  # footnote dropped
    assert by_code["3026"] == "Dutch Lady Milk Industries Bhd"  # sector heading not appended


def test_parse_keeps_five_digit_ace_leap_codes_as_printed():
    assert "03051.KL" in _parse().compliant_tickers


def test_parse_reads_table_2_two_column_layout_as_the_explicit_non_compliant_set():
    assert _parse().non_compliant_tickers == {
        "03067.KL", "03001.KL", "0382.KL", "7022.KL",
    }


def test_parse_stops_before_the_additional_list_business_trust():
    # pypdf emits the "ADDITIONAL LIST" heading AFTER its trailing table; that table's
    # 5320 is not in the booklet's own count and must not be read as a main-list row.
    assert "5320.KL" not in _parse().compliant_tickers


def test_parse_refuses_a_count_that_disagrees_with_the_booklets_own_total():
    bad = _text().replace("Jumlah 8 1,099 81", "Jumlah 9 1,099 81")
    with pytest.raises(ShariaSourceError, match="Table 3 total"):
        sc.parse_sc_list_text(bad, min_rows=3)


def test_parse_refuses_a_short_list_under_the_default_floor():
    with pytest.raises(ShariaSourceError, match="floor"):
        sc.parse_sc_list_text(_text())  # 8 rows < the 500-row floor


def test_parse_refuses_a_missing_date_and_a_missing_list():
    undated = (
        _text()
        .replace("takes effect from 29 May 2026", "takes effect")
        .replace("29 MAY 2026", "")
    )
    with pytest.raises(ShariaSourceError, match="effective date"):
        sc.parse_sc_list_text(undated, min_rows=3)
    with pytest.raises(ShariaSourceError, match="heading"):
        sc.parse_sc_list_text("takes effect from 29 May 2026", min_rows=3)


def test_discover_list_url_picks_the_newest_release_off_the_index_page():
    html = (
        '"pages": {"0":[{"name":"List as at 29 May 2026","file_path":'
        '"https://www.sc.com.my/api/documentms/download.ashx?id=NEW","date_published":'
        '"May 29, 2026"},{"name":"List as at 28 November 2025","file_path":'
        '"https://www.sc.com.my/api/documentms/download.ashx?id=OLD","date_published":'
        '"Nov 27, 2025"}]}'
    )
    assert sc.discover_list_url(html).endswith("id=NEW")
    with pytest.raises(ShariaSourceError):
        sc.discover_list_url("<html>no releases</html>")


def _tiny_pdf(lines: list[str]) -> bytes:
    """A one-page PDF with `lines` as Helvetica text — enough for pypdf to extract."""
    body = "BT /F1 10 Tf 12 TL 40 780 Td " + " T* ".join(f"({ln}) Tj" for ln in lines) + " ET"
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(body)} >>\nstream\n{body}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, o in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


def test_extract_pdf_text_round_trips_a_real_pdf():
    pytest.importorskip("pypdf")
    text = sc.extract_pdf_text(_tiny_pdf(["1. 7086 Ablegroup Bhd", "2. 5015 APM Holdings Bhd"]))
    assert "7086" in text and "Ablegroup" in text


def test_extract_pdf_text_rejects_garbage_loudly():
    pytest.importorskip("pypdf")
    with pytest.raises(ShariaSourceError):
        sc.extract_pdf_text(b"%PDF-1.4 not really a pdf")


def test_fetch_follows_the_index_page_to_the_pdf_and_parses_it(monkeypatch):
    pytest.importorskip("pypdf")
    pdf = _tiny_pdf(["unused"])
    monkeypatch.setattr(sc, "extract_pdf_text", lambda b: _text())
    monkeypatch.setattr(sc, "_SC_MIN_ROWS", 3)
    index = (
        '{"name":"L","file_path":"https://sc.test/dl?id=1","date_published":"May 29, 2026"}'
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/index":
            return httpx.Response(200, text=index, headers={"content-type": "text/html"})
        return httpx.Response(200, content=pdf, headers={"content-type": "application/pdf"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        got = sc.fetch_sc_list(client, "https://sc.test/index")
    assert got.source_url == "https://sc.test/dl?id=1"
    assert got.as_of == _LIST_DATE


# ── snapshot ingestion ───────────────────────────────────────────────────────


def _fetcher():
    parsed = _parse(source_url="https://sc.test/list.pdf")
    return parsed.compliant_tickers, parsed.as_of, parsed.non_compliant_tickers, parsed.source_url


def test_refresh_writes_a_snapshot_under_the_sc_standard_with_the_list_date(bursa_on):
    assert run_sharia_sc_refresh_tick(fetcher=_fetcher) == "stored"
    with get_session() as s:
        row = latest_snapshot(s, sc.STANDARD_KEY)
        us_row = latest_snapshot(s, su.STANDARD)
    assert row.standard == "SC_MALAYSIA"
    assert row.as_of == _LIST_DATE
    assert set(row.compliant) == _COMPLIANT
    assert set(row.parent) == {"03067.KL", "03001.KL", "0382.KL", "7022.KL"}
    assert row.source_url == "https://sc.test/list.pdf"
    assert us_row is None  # the US standard's rows are untouched


def test_refresh_is_a_noop_while_the_bursa_flag_is_off(bursa_off):
    assert run_sharia_sc_refresh_tick(fetcher=_fetcher) == "disabled"
    with get_session() as s:
        assert latest_snapshot(s, sc.STANDARD_KEY) is None


def test_refresh_failure_keeps_the_held_row_and_counts_loudly(bursa_on):
    _seed_sc(as_of=_LIST_DATE)

    def boom():
        raise httpx.ConnectError("sc.com.my down")

    for _ in range(3):
        assert run_sharia_sc_refresh_tick(fetcher=boom, force=True) == "fetch_failed"
    assert su.consecutive_sc_refresh_failures() == 3
    with get_session() as s:
        assert set(latest_snapshot(s, sc.STANDARD_KEY).compliant) == _COMPLIANT
    assert su.consecutive_refresh_failures() == 0  # the US counter is not conflated


def test_refresh_cadence_daily_in_release_windows_weekly_otherwise(bursa_on):
    # fetched 3 days ago: current outside a release window, due inside one
    fetched = datetime(2026, 8, 10, tzinfo=timezone.utc)
    _seed_sc(as_of=_LIST_DATE, fetched_at=fetched)
    assert (
        run_sharia_sc_refresh_tick(fetcher=_fetcher, now=fetched + timedelta(days=3))
        == "skipped_fresh"
    )
    assert (
        run_sharia_sc_refresh_tick(fetcher=_fetcher, now=fetched + timedelta(days=8)) == "stored"
    )
    nov = datetime(2026, 11, 20, tzinfo=timezone.utc)
    _seed_sc(as_of=_LIST_DATE, fetched_at=nov)
    assert su._in_sc_release_window(date(2026, 11, 27))
    assert su._in_sc_release_window(date(2026, 5, 29))
    assert not su._in_sc_release_window(date(2026, 8, 10))
    assert (
        run_sharia_sc_refresh_tick(fetcher=_fetcher, now=nov + timedelta(days=7)) == "stored"
    )  # 27 Nov: inside the window, a 7-day-old row is already stale


# ── per-market resolve ───────────────────────────────────────────────────────


def test_kl_ticker_on_the_list_passes_and_names_the_sc_source_and_date(bursa_on):
    _seed_us()
    _seed_sc(as_of=_today() - timedelta(days=30))
    v = default_halal_universe().resolve("5183.KL")
    assert v.status is ShariaStatus.PASS
    assert "SC Malaysia Shariah Advisory Council list" in v.source
    assert v.as_of == _today() - timedelta(days=30)
    assert v.coverage == "Bursa Malaysia"
    assert "SC Malaysia Shariah Advisory Council list" in v.message()
    assert "S&P" not in v.message()


def test_kl_ticker_absent_from_the_list_is_screened_out_and_blocks(bursa_on):
    """Maybank (1155.KL) is a conventional bank: not on the SC list. The booklet classifies
    every Main/ACE/LEAP security (886 of 1,099 compliant), so absence IS the classification
    — UNKNOWN here would permit it under a halal mandate (the DEF084 failure class)."""
    _seed_us()
    _seed_sc(as_of=_today() - timedelta(days=30))
    v = default_halal_universe().resolve("1155.KL")
    assert v.status is ShariaStatus.SCREENED_OUT
    assert v.is_blocking
    assert "not on the SC Malaysia" in v.message() and "won't trade it" in v.message()


def test_no_sc_snapshot_is_unavailable_never_pass(bursa_on):
    _seed_us()  # US fine, SC never fetched
    uni = default_halal_universe()
    v = uni.resolve("5183.KL")
    assert v.status is ShariaStatus.UNAVAILABLE and v.is_blocking
    assert uni.for_ticker("5183.KL").stale is True
    assert uni.resolve("AAA").status is ShariaStatus.PASS  # US unaffected by an SC outage


def test_stale_sc_snapshot_is_unavailable_but_a_semi_annual_gap_is_not(bursa_on):
    _seed_us()
    _seed_sc(as_of=_today() - timedelta(days=199))
    assert default_halal_universe().resolve("5183.KL").status is ShariaStatus.PASS
    reset_sharia_universe_provider(None)
    with get_session() as s:
        s.query(su.ShariaUniverseSnapshotRow).filter_by(standard=sc.STANDARD_KEY).delete()
    _seed_sc(as_of=_today() - timedelta(days=201))
    v = default_halal_universe().resolve("5183.KL")
    assert v.status is ShariaStatus.UNAVAILABLE
    assert v.standard == "SC Malaysia"  # the pause names the right standard


def test_sc_window_is_200_days_not_the_us_hold_window():
    assert Settings.model_fields["sharia_sc_staleness_days"].default == 200
    assert Settings.model_fields["sharia_hold_window_days"].default == 30
    # 100 days is far past the US window and well inside the SC one
    assert settings.sharia_sc_staleness_days > 100 > settings.sharia_hold_window_days


def test_us_tickers_resolve_against_the_us_standard_with_the_flag_on(bursa_on):
    _seed_us()
    _seed_sc(as_of=_today() - timedelta(days=30))
    uni = default_halal_universe()
    assert uni.resolve("AAA").status is ShariaStatus.PASS
    assert uni.resolve("ZZZ").status is ShariaStatus.SCREENED_OUT
    assert uni.resolve("NEVR").status is ShariaStatus.UNKNOWN
    assert uni.resolve("AAA").source == su.SOURCE
    assert uni.for_ticker("AAA") is uni


def test_flag_off_the_us_universe_is_returned_untouched(bursa_off):
    _seed_us()
    _seed_sc(as_of=_today() - timedelta(days=30))
    uni = default_halal_universe()
    assert uni.companions == {}
    assert uni is su.get_sharia_universe_provider().get()  # the very object US always got
    assert uni.for_ticker("5183.KL") is uni
    assert uni.resolve("5183.KL").status is ShariaStatus.UNKNOWN  # the pre-CR282 answer
    assert uni.resolve("AAA").coverage == "the S&P 500"


def test_us_verdict_text_is_unchanged_by_the_coverage_field():
    uni = HalalUniverse({"AAA"}, parent_index={"ZZZ"}, as_of=date(2026, 7, 22))
    assert uni.resolve("ZZZ").message() == (
        "ZZZ is in the parent index but does not pass the AAOIFI screen "
        f"({su.SOURCE}, as of 2026-07-22), so this mandate won't trade it."
    )
    assert uni.resolve("NEVR").message().startswith("NEVR isn't in the parent index")


def test_combined_universe_is_memoised_on_its_inputs(bursa_on):
    _seed_us()
    _seed_sc(as_of=_today() - timedelta(days=30))
    assert default_halal_universe() is default_halal_universe()


# ── the enforcement seams ────────────────────────────────────────────────────


def _floor(mandate, ticker, universe):
    from app.agents.safety_floor import check_mandate_compliance
    from app.schemas import Compliance
    from app.schemas.trade import ProposedTrade, Side

    m = mandate.model_copy(
        update={"compliance": Compliance(halal=True, long_only=True, liquid_only=True)}
    )
    return check_mandate_compliance(
        ProposedTrade(ticker=ticker, side=Side.BUY, quantity=100, limit_price=10.0),
        portfolio_value=100_000,
        current_drawdown_pct=0,
        mandate=m,
        halal_universe=universe,
        holdings=[], last_loss_closed_at=None, trade_open_timestamps=[],
        existing_open_risk_pct=0.0,
    )


def test_safety_floor_blocks_a_kl_name_off_the_sc_list_and_passes_one_on_it(
    bursa_on, base_mandate
):
    _seed_us()
    _seed_sc(as_of=_today() - timedelta(days=30))
    uni = default_halal_universe()

    on = _floor(base_mandate, "5183.KL", uni)
    assert on.sharia_verdict.status is ShariaStatus.PASS
    assert not any("Shariah" in v or "Sharia" in v for v in on.violations)

    off = _floor(base_mandate, "1155.KL", uni)
    assert not off.passed and off.blocked_by == "compliance"
    assert off.sharia_verdict.status is ShariaStatus.SCREENED_OUT
    assert "SC Malaysia Shariah Advisory Council list" in " ".join(off.violations)

    # and the US name through the very same object still resolves on the US standard
    us = _floor(base_mandate, "AAA", uni)
    assert us.sharia_verdict.source == su.SOURCE


def test_safety_floor_pauses_a_kl_trade_when_the_sc_list_is_missing(bursa_on, base_mandate):
    _seed_us()
    res = _floor(base_mandate, "5183.KL", default_halal_universe())
    assert not res.passed and res.sharia_verdict.status is ShariaStatus.UNAVAILABLE


def test_narration_for_a_kl_name_uses_the_sc_standard_not_the_us_one(bursa_on):
    from app.agents.overlay_generator import _halal_narration

    _seed_us()
    _seed_sc(as_of=_today() - timedelta(days=30))
    uni = default_halal_universe()
    text = _halal_narration(uni, "1155.KL")
    assert "SC Malaysia" in text and "SC Malaysia Shariah Advisory Council list" in text
    assert "NOT ON THE LIST" in text and "NOT REVIEWED" not in text
    us_text = _halal_narration(uni, "AAA")
    assert "NOT REVIEWED" in us_text and "SC Malaysia" not in us_text


def test_narration_for_a_kl_name_pauses_loudly_when_the_sc_list_is_missing(bursa_on):
    from app.agents.overlay_generator import _halal_narration

    _seed_us()
    uni = default_halal_universe()
    assert "PAUSED" in _halal_narration(uni, "5183.KL")
    assert "PAUSED" not in _halal_narration(uni, "AAA")


def test_room_bank_digest_follows_the_kl_tickers_own_market(bursa_on):
    from app.services import room_bank
    from app.services.classification_universe import ClassificationUniverse

    _seed_us()
    _seed_sc(as_of=_today() - timedelta(days=30))
    cls = ClassificationUniverse(fossil=set(), classified={"5183.KL"}, as_of=_LIST_DATE)
    on = room_bank.universe_digest(default_halal_universe(), cls, "5183.KL")
    off = room_bank.universe_digest(default_halal_universe(), cls, "1155.KL")
    assert on != off  # PASS vs SCREENED_OUT moves the key
    # the SC list going stale is a new Room, and a US ticker's key does not move with it
    us_before = room_bank.universe_digest(default_halal_universe(), cls, "AAA")
    reset_sharia_universe_provider(None)
    with get_session() as s:
        s.query(su.ShariaUniverseSnapshotRow).filter_by(standard=sc.STANDARD_KEY).delete()
    _seed_sc(as_of=_today() - timedelta(days=400))
    assert room_bank.universe_digest(default_halal_universe(), cls, "5183.KL") != on
    assert room_bank.universe_digest(default_halal_universe(), cls, "AAA") == us_before
