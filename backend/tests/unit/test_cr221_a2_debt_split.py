"""CR221 A2 — the industrial vs. captive-finance debt split, from the filing itself.

Eighteen request lines from nine agents. CR219's R38 build parked because
`companyfacts` carries no dimensional facts (0 of 39,403 on CAT); this is the
re-route through the filing's XBRL instance, and four things are pinned.

**The columns are the source, and subtraction is not.** CAT's consolidating
balance sheet tags both sides on `srt:ProductOrServiceAxis`; the two
`LongTermDebtAndCapitalLeaseObligations` figures sum to the non-dimensional
`LongTermDebtNoncurrent` to the dollar. The parked design derived the
industrial half as consolidated minus captive and would have printed $3,593M
for a filed $10,713M, because the house gross-debt tags are a different
family. A filer that tags one side gets one side.

**Registry matching is exact.** Ford's industrial column is
`CompanyExcludingFordCreditMember`; a substring rule for "fordcredit" files it
under the lender.

**Units resolve through `xbrli:unit`.** A `unitRef` is an opaque id — CAT
writes `usd`, Deere writes `Ifeqnbq-buca0lohammirw` — and the first parser
draft dropped every one of Deere's 278 facts on it.

**Three states, never blurred.** No lender → no line. Lender known, nothing
resolved → UNAVAILABLE, and the sheet says the gross debt is blended.
Captive only → the captive figure, and the line says the industrial figure is
not the difference.

Fixture values are the measured filings (CAT FY2025 10-K, F FY2025 10-K,
PCAR FY2025 10-K), read on 2026-09-10. No network anywhere in this file.
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app.core.config import settings
from app.db import get_session
from app.db.models import EdgarFactRow
from app.schemas.agents import AgentId
from app.services import edgar_instance, edgar_tags, filing_dimensions, room_prompts, room_runner
from app.services.edgar_pit import _FactView
from app.services.fundamentals import debt_split_line

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from ingest_edgar_dimensional import instance_url, latest_annual_filing  # noqa: E402

_M = 1_000_000.0
_END = date(2025, 12, 31)
_FILED = date(2026, 2, 13)
_AS_OF = date(2026, 9, 11)
_NOW = datetime(2026, 9, 11, tzinfo=timezone.utc)
_FILING = edgar_instance.Filing(
    cik=18230, ticker="CAT", accession_no="0000018230-26-000008", form="10-K", filed=_FILED, fy=2025,
)

_NS = {
    "xbrli": "http://www.xbrl.org/2003/instance",
    "xbrldi": "http://xbrl.org/2006/xbrldi",
    "us-gaap": "http://fasb.org/us-gaap/2025",
    "srt": "http://fasb.org/srt/2025",
    "dei": "http://xbrl.sec.gov/dei/2025",
    "cat": "http://www.caterpillar.com/20251231",
    "f": "http://www.ford.com/20251231",
    "iso4217": "http://www.xbrl.org/2003/iso4217",
}


def instance_xml(contexts: dict[str, dict], facts: list[tuple[str, str, float]],
                 *, unit_id: str = "usd", unit_measure: str = "iso4217:USD") -> bytes:
    """A minimal XBRL instance in the SEC's own element vocabulary.

    `contexts`: id → {"dims": [(axis, member)], "instant": iso} or
    {"dims": [...], "start": iso, "end": iso}. `facts`: (concept QName,
    context id, value), all on the one declared unit.
    """
    xmlns = " ".join(f'xmlns:{p}="{u}"' for p, u in _NS.items())
    out = [f'<?xml version="1.0" encoding="utf-8"?><xbrli:xbrl {xmlns}>',
           f'<xbrli:unit id="{unit_id}"><xbrli:measure>{unit_measure}</xbrli:measure></xbrli:unit>']
    for cid, spec in contexts.items():
        dims = "".join(
            f'<xbrldi:explicitMember dimension="{axis}">{member}</xbrldi:explicitMember>'
            for axis, member in spec.get("dims", [])
        )
        segment = f"<xbrli:segment>{dims}</xbrli:segment>" if dims else ""
        if "instant" in spec:
            period = f"<xbrli:instant>{spec['instant']}</xbrli:instant>"
        else:
            period = f"<xbrli:startDate>{spec['start']}</xbrli:startDate><xbrli:endDate>{spec['end']}</xbrli:endDate>"
        out.append(
            f'<xbrli:context id="{cid}"><xbrli:entity>'
            f'<xbrli:identifier scheme="http://www.sec.gov/CIK">0000018230</xbrli:identifier>'
            f"{segment}</xbrli:entity><xbrli:period>{period}</xbrli:period></xbrli:context>"
        )
    for concept, cid, value in facts:
        out.append(f'<{concept} contextRef="{cid}" unitRef="{unit_id}" decimals="-6">{value:.0f}</{concept}>')
    out.append("</xbrli:xbrl>")
    return "".join(out).encode()


_POS = "srt:ProductOrServiceAxis"
_FP, _FPS, _MET = "cat:FinancialProductsMember", "cat:FinancialProductsSegmentMember", "cat:MachineryPowerEnergyMember"


def _cat_contexts() -> dict[str, dict]:
    return {
        "whole": {"instant": "2025-12-31"},
        "fp": {"dims": [(_POS, _FP)], "instant": "2025-12-31"},
        "fps": {"dims": [(_POS, _FPS)], "instant": "2025-12-31"},
        "met": {"dims": [(_POS, _MET)], "instant": "2025-12-31"},
        "fp_prior": {"dims": [(_POS, _FP)], "instant": "2024-12-31"},
        "met_prior": {"dims": [(_POS, _MET)], "instant": "2024-12-31"},
        # Two dimensions: a consolidating cell crossed with an elimination member.
        "fp_x": {"dims": [(_POS, _FP), ("srt:ConsolidationItemsAxis", "srt:ConsolidationEliminationsMember")],
                 "instant": "2025-12-31"},
        # A fair-value disclosure axis — not a consolidating column.
        "fv": {"dims": [("us-gaap:FairValueByFairValueHierarchyLevelAxis", "us-gaap:FairValueInputsLevel2Member")],
               "instant": "2025-12-31"},
    }


def _cat_facts() -> list[tuple[str, str, float]]:
    ltd, ltd_cur, st = (
        "us-gaap:LongTermDebtAndCapitalLeaseObligations",
        "us-gaap:LongTermDebtAndCapitalLeaseObligationsCurrent",
        "us-gaap:ShortTermBorrowings",
    )
    return [
        ("us-gaap:LongTermDebtNoncurrent", "whole", 30_696 * _M),
        (ltd, "fp", 20_018 * _M), (ltd, "fps", 20_018 * _M), (ltd, "met", 10_678 * _M),
        (ltd_cur, "fp", 7_085 * _M), (ltd_cur, "met", 35 * _M),
        (st, "fp", 5_514 * _M), (st, "met", 0.0),
        (ltd, "fp_prior", 18_787 * _M), (ltd, "met_prior", 8_564 * _M),
        (ltd, "fp_x", 1.0), (ltd, "fv", 99_999 * _M),
    ]


def _rows(contexts=None, facts=None, ticker="CAT", **xml_kw) -> list[dict]:
    xml = instance_xml(contexts or _cat_contexts(), facts if facts is not None else _cat_facts(), **xml_kw)
    parsed = edgar_instance.parse_instance(xml, tags=edgar_instance.INSTANCE_TAGS)
    return edgar_instance.debt_split_rows(parsed, ticker, _FILING)


def _by_tag(rows: list[dict], end: date = _END) -> dict[str, float]:
    return {r["tag"]: r["value"] for r in rows if r["period_end"] == end}


# ── The parser ──────────────────────────────────────────────────────────────


def test_both_columns_are_read_from_the_filing_and_reconcile_to_the_consolidated_figure() -> None:
    by_tag = _by_tag(_rows())
    captive = by_tag[f"{edgar_tags.CAPTIVE_DEBT_TAG}:LongTermDebtAndCapitalLeaseObligations"]
    industrial = by_tag[f"{edgar_tags.INDUSTRIAL_DEBT_TAG}:LongTermDebtAndCapitalLeaseObligations"]
    assert captive == pytest.approx(20_018 * _M)
    assert industrial == pytest.approx(10_678 * _M)
    assert captive + industrial == pytest.approx(30_696 * _M)


def test_rows_carry_the_filing_identity_not_the_run_clock() -> None:
    for row in _rows():
        assert row["taxonomy"] == edgar_tags.DIMENSIONAL_TAXONOMY
        assert row["filed"] == _FILED
        assert row["accession_no"] == _FILING.accession_no
        assert row["form"] == "10-K" and row["fy"] == 2025 and row["unit"] == "USD"


def test_a_second_member_name_for_the_same_column_dedupes_and_a_disagreeing_one_drops_it() -> None:
    assert sum(1 for r in _rows() if r["tag"].endswith(":LongTermDebtAndCapitalLeaseObligations")
               and r["tag"].startswith(edgar_tags.CAPTIVE_DEBT_TAG) and r["period_end"] == _END) == 1
    facts = [f for f in _cat_facts() if f[1] != "fps"]
    facts.append(("us-gaap:LongTermDebtAndCapitalLeaseObligations", "fps", 21_000 * _M))
    assert f"{edgar_tags.CAPTIVE_DEBT_TAG}:LongTermDebtAndCapitalLeaseObligations" not in _by_tag(_rows(facts=facts))


def test_only_single_dimension_contexts_on_a_consolidating_axis_count() -> None:
    values = set(_by_tag(_rows()).values())
    assert 1.0 not in values            # the two-dimension elimination cell
    assert 99_999 * _M not in values    # the fair-value axis
    assert not any(r["tag"].endswith(":LongTermDebtNoncurrent") for r in _rows())  # non-dimensional


def test_a_negative_column_figure_is_refused() -> None:
    facts = [("us-gaap:ShortTermBorrowings", "fp", -1.0 * _M)]
    assert _rows(facts=facts) == []


def test_an_unregistered_ticker_yields_nothing_even_with_the_members_present() -> None:
    assert _rows(ticker="AAPL") == []


def test_an_opaque_unit_id_resolves_through_the_unit_element() -> None:
    """Deere's shape. The unitRef says nothing; the `xbrli:unit` it names does."""
    rows = _rows(unit_id="Ifeqnbq-buca0lohammirw", unit_measure="iso4217:USD")
    assert _by_tag(rows)[f"{edgar_tags.CAPTIVE_DEBT_TAG}:LongTermDebtAndCapitalLeaseObligations"] == pytest.approx(20_018 * _M)


def test_a_non_usd_unit_is_not_a_debt_figure() -> None:
    assert _rows(unit_measure="iso4217:EUR") == []


def test_prior_year_columns_are_kept_as_their_own_period() -> None:
    by_prior = _by_tag(_rows(), date(2024, 12, 31))
    assert by_prior[f"{edgar_tags.CAPTIVE_DEBT_TAG}:LongTermDebtAndCapitalLeaseObligations"] == pytest.approx(18_787 * _M)


# ── The registry ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize("ticker,member,role", [
    ("CAT", "cat:FinancialProductsMember", "captive"),
    ("CAT", "cat:FinancialProductsSegmentMember", "captive"),
    ("CAT", "cat:MachineryPowerEnergyMember", "industrial"),
    ("F", "f:FordCreditMember", "captive"),
    ("F", "f:CompanyExcludingFordCreditMember", "industrial"),
    ("PCAR", "pcar:FinancialServicesMember", "captive"),
    ("DE", "de:FinancialServicesSegmentMember", "captive"),
    ("de", "de:EquipmentOperationsMember", "industrial"),
])
def test_registry_roles(ticker, member, role) -> None:
    assert edgar_tags.captive_finance_role(ticker, member) == role


@pytest.mark.parametrize("ticker,member", [
    ("CAT", "cat:ConstructionIndustriesMember"),
    ("F", "f:FordBlueMember"),
    ("AAPL", "cat:FinancialProductsMember"),
    ("CAT", ""),
])
def test_non_finance_segments_and_unregistered_tickers_have_no_role(ticker, member) -> None:
    assert edgar_tags.captive_finance_role(ticker, member) is None


def test_matching_is_exact_so_the_excluding_column_never_reads_as_the_lender() -> None:
    assert edgar_tags.normalize_member_name("f:CompanyExcludingFordCreditMember") == "companyexcludingfordcredit"
    assert "fordcredit" in edgar_tags.normalize_member_name("f:CompanyExcludingFordCreditMember")
    assert edgar_tags.captive_finance_role("F", "f:CompanyExcludingFordCreditMember") != "captive"


def test_every_registry_entry_names_a_lender_and_both_columns() -> None:
    for ticker in edgar_tags.captive_finance_tickers():
        entry = edgar_tags.CAPTIVE_FINANCE[ticker]
        assert entry.lender and entry.captive and entry.industrial
        assert edgar_tags.captive_finance_lender(ticker) == entry.lender
    assert edgar_tags.captive_finance_lender("AAPL") is None


# ── The resolver ─────────────────────────────────────────────────────────────


def _view(tag: str, value_m: float, end: date = _END, filed: date = _FILED) -> _FactView:
    return _FactView(tag=tag, value=value_m * _M, period_start=None, period_end=end, filed=filed)


def _cat_views(**kw) -> list[_FactView]:
    c, i = edgar_tags.CAPTIVE_DEBT_TAG, edgar_tags.INDUSTRIAL_DEBT_TAG
    return [
        _view(f"{c}:LongTermDebtAndCapitalLeaseObligations", 20_018, **kw),
        _view(f"{c}:LongTermDebtAndCapitalLeaseObligationsCurrent", 7_085, **kw),
        _view(f"{c}:ShortTermBorrowings", 5_514, **kw),
        _view(f"{i}:LongTermDebtAndCapitalLeaseObligations", 10_678, **kw),
        _view(f"{i}:LongTermDebtAndCapitalLeaseObligationsCurrent", 35, **kw),
        _view(f"{i}:ShortTermBorrowings", 0, **kw),
    ]


def test_each_side_sums_its_three_families() -> None:
    split = filing_dimensions.resolve_debt_split(_cat_views(), "Caterpillar Financial Services", _AS_OF)
    assert split is not None
    assert split.captive == pytest.approx(32_617 * _M)
    assert split.industrial == pytest.approx(10_713 * _M)
    assert split.period_end == _END and split.lender == "Caterpillar Financial Services"


def test_a_combined_concept_wins_over_the_sum_and_debt_current_displaces_short_term() -> None:
    """Ford Credit: $89,665M noncurrent + $51,752M DebtCurrent (which already
    holds the $18,350M short-term) = the $141,417M it also tags combined."""
    c = edgar_tags.CAPTIVE_DEBT_TAG
    with_combined = [
        _view(f"{c}:DebtLongtermAndShorttermCombinedAmount", 141_417),
        _view(f"{c}:LongTermDebtNoncurrent", 89_665),
        _view(f"{c}:DebtCurrent", 51_752),
        _view(f"{c}:ShortTermBorrowings", 18_350),
    ]
    assert filing_dimensions.resolve_debt_split(with_combined, "Ford Credit", _AS_OF).captive == pytest.approx(141_417 * _M)
    without = [v for v in with_combined if "Combined" not in v.tag]
    assert filing_dimensions.resolve_debt_split(without, "Ford Credit", _AS_OF).captive == pytest.approx(141_417 * _M)


def test_a_filer_that_tags_only_the_finance_column_resolves_captive_only() -> None:
    views = [_view(f"{edgar_tags.CAPTIVE_DEBT_TAG}:DebtLongtermAndShorttermCombinedAmount", 15_666)]
    split = filing_dimensions.resolve_debt_split(views, "PACCAR Financial", _AS_OF)
    assert split.captive == pytest.approx(15_666 * _M)
    assert split.industrial is None


def test_the_industrial_side_alone_is_not_a_split() -> None:
    views = [_view(f"{edgar_tags.INDUSTRIAL_DEBT_TAG}:LongTermDebtNoncurrent", 10_678)]
    assert filing_dimensions.resolve_debt_split(views, "X", _AS_OF) is None


def test_the_newest_period_wins_and_the_newest_filing_wins_within_it() -> None:
    views = (
        _cat_views(end=date(2024, 12, 31), filed=date(2025, 2, 14))
        + _cat_views()
        + [_view(f"{edgar_tags.CAPTIVE_DEBT_TAG}:LongTermDebtAndCapitalLeaseObligations", 20_500,
                 filed=date(2026, 3, 1))]
    )
    split = filing_dimensions.resolve_debt_split(views, "X", _AS_OF)
    assert split.period_end == _END
    assert split.captive == pytest.approx((20_500 + 7_085 + 5_514) * _M)


def test_a_split_older_than_the_annual_bound_is_refused() -> None:
    assert filing_dimensions.resolve_debt_split(_cat_views(), "X", date(2027, 4, 1)) is None
    assert filing_dimensions.resolve_debt_split(_cat_views(), "X", date(2027, 3, 1)) is not None


# ── The store ────────────────────────────────────────────────────────────────


@pytest.fixture
def seeded_pcar():
    with get_session() as s:
        s.query(EdgarFactRow).filter(EdgarFactRow.ticker == "PCAR").delete()
        s.add(EdgarFactRow(
            cik=75362, ticker="PCAR", taxonomy=edgar_tags.DIMENSIONAL_TAXONOMY,
            tag=f"{edgar_tags.CAPTIVE_DEBT_TAG}:DebtLongtermAndShorttermCombinedAmount",
            unit="USD", value=15_665.9 * _M, period_start=None, period_end=_END,
            filed=date(2026, 2, 18), accession_no="0001193125-26-057025", ingested_at=_NOW,
        ))
        s.commit()
    yield
    with get_session() as s:
        s.query(EdgarFactRow).filter(EdgarFactRow.ticker == "PCAR").delete()
        s.commit()


def test_the_stored_split_comes_back_through_the_db_path(seeded_pcar) -> None:
    dims = filing_dimensions.fetch_filing_dimensions("pcar", _AS_OF)
    assert dims.lender == "PACCAR Financial"
    assert dims.debt_split.captive == pytest.approx(15_665.9 * _M)
    assert dims.debt_split.industrial is None


def test_the_store_read_is_point_in_time(seeded_pcar) -> None:
    dims = filing_dimensions.fetch_filing_dimensions("PCAR", date(2026, 2, 17))
    assert dims.debt_split is None and dims.lender == "PACCAR Financial"


def test_a_ticker_with_no_lender_reads_no_lender_and_no_split() -> None:
    dims = filing_dimensions.fetch_filing_dimensions("AAPL", _AS_OF)
    assert dims.lender is None and dims.debt_split is None


# ── The line ─────────────────────────────────────────────────────────────────


def test_resolved_renders_both_halves_named_and_dated() -> None:
    line = debt_split_line("resolved", "Caterpillar Financial Services", 32_617, 10_713, "2025-12-31")
    assert "industrial $10,713M" in line and "captive finance $32,617M" in line
    assert "Caterpillar Financial Services" in line and "2025-12-31" in line and "(LIVE)" in line
    assert "different credit profiles" in line


def test_captive_only_names_the_figure_and_refuses_the_subtraction() -> None:
    line = debt_split_line("captive_only", "PACCAR Financial", 15_666, None, "2025-12-31")
    assert "captive finance $15,666M" in line
    assert "industrial $" not in line
    assert "NOT the gross debt above less this figure" in line


def test_unresolved_renders_an_explicit_unavailable_line() -> None:
    line = debt_split_line("unresolved", "John Deere Capital", None, None, None)
    assert "UNAVAILABLE" in line and "John Deere Capital" in line and "BLENDED" in line
    assert "industrial $" not in line and "captive finance $" not in line


def test_absent_renders_nothing_and_a_resolved_state_without_its_halves_falls_to_unavailable() -> None:
    assert debt_split_line(None, None, None, None, None) is None
    assert "UNAVAILABLE" in debt_split_line("resolved", "X", None, None, "2025-12-31")
    assert "(LIVE)" not in debt_split_line("resolved", "X", 1, 2, "2025-12-31", live=False)


# ── The overlay and the render seam ──────────────────────────────────────────


def _dims(**kw) -> filing_dimensions.FilingDimensions:
    base = dict(lender=None, debt_split=None, segments=None, geography=None)
    base.update(kw)
    return filing_dimensions.FilingDimensions(**base)


def _overlay(monkeypatch, ticker: str, dims=None, *, boom: bool = False) -> tuple[dict, dict]:
    def fake(t, as_of):
        if boom:
            raise RuntimeError("store unreachable")
        return dims

    monkeypatch.setattr(filing_dimensions, "fetch_filing_dimensions", fake)
    profile: dict = {}
    field_state: dict = {}
    room_runner._overlay_filing_dimensions(profile, field_state, ticker, _AS_OF)
    return profile, field_state


def test_the_overlay_writes_millions_and_one_live_block_key(monkeypatch) -> None:
    split = filing_dimensions.DebtSplit("Caterpillar Financial Services", _END, 32_617 * _M, 10_713 * _M)
    profile, state = _overlay(monkeypatch, "CAT", _dims(lender=split.lender, debt_split=split))
    assert profile["debt_split_state"] == "resolved"
    assert profile["debt_split_captive"] == 32_617 and profile["debt_split_industrial"] == 10_713
    assert profile["debt_split_period"] == "2025-12-31"
    assert state["debt_split"] == "live"


def test_a_registry_filer_with_nothing_resolved_is_live_and_unresolved(monkeypatch) -> None:
    profile, state = _overlay(monkeypatch, "DE", _dims(lender="John Deere Capital"))
    assert profile["debt_split_state"] == "unresolved" and profile["debt_split_entity"] == "John Deere Capital"
    assert state["debt_split"] == "live"


def test_a_filer_with_no_lender_gets_no_block(monkeypatch) -> None:
    profile, state = _overlay(monkeypatch, "AAPL", _dims())
    assert not [k for k in profile if k.startswith("debt_split")]
    assert state["debt_split"] == "unavailable"


def test_a_store_failure_is_logged_and_leaves_the_lender_named(monkeypatch) -> None:
    logged: list = []
    monkeypatch.setattr(room_runner.logger, "warn", lambda event, **kw: logged.append(event))
    profile, state = _overlay(monkeypatch, "CAT", boom=True)
    assert "edgar_filing_dimensions_unreadable" in logged
    assert profile["debt_split_state"] == "unresolved" and state["debt_split"] == "live"
    assert state["segment_revenue"] == "unavailable"


def _profile(state: str = "resolved") -> dict:
    return {
        "field_state": {"debt_split": "live"},
        "debt_split_state": state, "debt_split_entity": "Caterpillar Financial Services",
        "debt_split_captive": 32_617, "debt_split_industrial": 10_713, "debt_split_period": "2025-12-31",
    }


@pytest.fixture(autouse=True)
def _flag_restored():
    before = settings.room_debt_split_enabled
    yield
    settings.room_debt_split_enabled = before


def test_the_flag_is_off_by_default_and_the_same_profile_renders_nothing() -> None:
    assert settings.room_debt_split_enabled is False
    assert "Debt split" not in room_prompts._format_profile(_profile(), AgentId.FUNDAMENTALS_ANALYST)


def test_the_flag_on_renders_the_split_and_the_unresolved_line() -> None:
    settings.room_debt_split_enabled = True
    sheet = room_prompts._format_profile(_profile(), AgentId.FUNDAMENTALS_ANALYST)
    assert "Debt split (industrial vs. captive finance) (LIVE): industrial $10,713M, captive finance $32,617M" in sheet
    sheet = room_prompts._format_profile(_profile("unresolved"), AgentId.FUNDAMENTALS_ANALYST)
    assert "UNAVAILABLE — Caterpillar Financial Services" in sheet


def test_presence_is_not_provenance() -> None:
    settings.room_debt_split_enabled = True
    profile = _profile()
    profile["field_state"] = {"debt_split": "unavailable"}
    assert "Debt split" not in room_prompts._format_profile(profile, AgentId.FUNDAMENTALS_ANALYST)


def test_the_three_flags_are_forwarded_in_the_api_alpha_block() -> None:
    compose = (Path(__file__).resolve().parents[3] / "docker-compose.yml").read_text()
    for name in ("ROOM_DEBT_SPLIT_ENABLED", "ROOM_SEGMENT_REVENUE_ENABLED", "ROOM_GEOGRAPHIC_REVENUE_ENABLED"):
        assert f"{name}: ${{{name}:-false}}" in compose


# ── The ingest route ─────────────────────────────────────────────────────────


def test_the_newest_original_10k_is_chosen_and_an_amendment_is_not() -> None:
    submissions = {"filings": {"recent": {
        "form": ["10-Q", "10-K/A", "10-K", "10-K"],
        "accessionNumber": ["a", "b", "0000018230-26-000008", "d"],
        "primaryDocument": ["q.htm", "ka.htm", "cat-20251231.htm", "old.htm"],
        "filingDate": ["2026-08-05", "2026-03-01", "2026-02-13", "2025-02-14"],
        "reportDate": ["2026-06-30", "2025-12-31", "2025-12-31", "2024-12-31"],
    }}}
    filing = latest_annual_filing(submissions)
    assert filing["accession_no"] == "0000018230-26-000008" and filing["filed"] == date(2026, 2, 13)
    assert instance_url(18230, filing) == (
        "https://www.sec.gov/Archives/edgar/data/18230/000001823026000008/cat-20251231_htm.xml"
    )
    assert latest_annual_filing({"filings": {"recent": {"form": ["10-Q"]}}}) is None
