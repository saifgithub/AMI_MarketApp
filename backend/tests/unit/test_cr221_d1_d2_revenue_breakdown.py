"""CR221 D1 / D2 — revenue by segment and by geography, as partitions of the filing's own total.

Seven request lines from four agents. Two rules with measured cases behind them.

**A breakdown is a partition or it is nothing.** A filing tags overlapping
cuts: CAT carries `country:US` and `NonUsMember` beside its four regions, and
an aggregate segment member beside the four segments. The rendered set is
the largest subset whose sum sits within 10% of the same filing's
consolidated revenue, at least two members, so the shares add up — and the
coverage is stated either way (CAT's external segment sales are 101% of
revenue; corporate items net against them).

**Tiers, in order.** Segment revenue arrives crossed with
`srt:ConsolidationItemsAxis`. External sales (`...ExcludingIntersegment
Elimination`) is the cleanest partition and is tried first; segment sales
including intersegment second; a bare segment member last. Deere's bare
members cover 87% of revenue — outside the band — and its operating-segment
tier covers 101%, so a fixed tier would have missed it.

Fixture values are CAT's FY2025 10-K as read on 2026-09-10. No network.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.core.config import settings
from app.db import get_session
from app.db.models import EdgarFactRow
from app.schemas.agents import AgentId
from app.services import edgar_instance, edgar_tags, filing_dimensions, room_prompts, room_runner
from app.services.edgar_pit import _FactView
from app.services.fundamentals import revenue_breakdown_line
from tests.unit.test_cr221_a2_debt_split import instance_xml

_M = 1_000_000.0
_END = date(2025, 12, 31)
_FILED = date(2026, 2, 13)
_AS_OF = date(2026, 9, 11)
_NOW = datetime(2026, 9, 11, tzinfo=timezone.utc)
_FILING = edgar_instance.Filing(cik=18230, ticker="CAT", accession_no="acc", form="10-K", filed=_FILED, fy=2025)

_SEG, _CI, _GEO = "us-gaap:StatementBusinessSegmentsAxis", "srt:ConsolidationItemsAxis", "srt:StatementGeographicalAxis"
_EXT, _OPS = "us-gaap:OperatingSegmentsExcludingIntersegmentEliminationMember", "us-gaap:OperatingSegmentsMember"
_SEGMENTS = {
    "cat:ConstructionIndustriesMember": (24_800, 25_060),
    "cat:ResourceIndustriesMember": (12_185, 12_474),
    "cat:PowerEnergyMember": (27_143, 32_201),
    "cat:FinancialProductsSegmentMember": (4_220, 4_220),
}
_AGG = "us-gaap:ReportableSegmentAggregationBeforeOtherOperatingSegmentMember"
_REGIONS = {"srt:NorthAmericaMember": 36_609, "srt:LatinAmericaMember": 6_988,
            "us-gaap:EMEAMember": 12_793, "srt:AsiaPacificMember": 11_199}
_TOTAL = 67_589


def _cat_instance() -> bytes:
    fy = {"start": "2025-01-01", "end": "2025-12-31"}
    contexts: dict[str, dict] = {"whole": dict(fy), "q4": {"start": "2025-10-01", "end": "2025-12-31"},
                                 "bare_pe": {"dims": [(_SEG, "cat:PowerEnergyMember")], **fy},
                                 "bare_other": {"dims": [(_SEG, "us-gaap:AllOtherSegmentsMember")], **fy},
                                 "agg_ext": {"dims": [(_CI, _EXT), (_SEG, _AGG)], **fy},
                                 "elim_ci": {"dims": [(_CI, "us-gaap:IntersegmentEliminationMember"),
                                                      (_SEG, "cat:ConstructionIndustriesMember")], **fy},
                                 "three": {"dims": [(_CI, _OPS), (_SEG, "cat:ConstructionIndustriesMember"),
                                                    (_GEO, "srt:NorthAmericaMember")], **fy},
                                 "us": {"dims": [(_GEO, "country:US")], **fy},
                                 "nonus": {"dims": [(_GEO, "us-gaap:NonUsMember")], **fy}}
    facts: list[tuple[str, str, float]] = [
        ("us-gaap:Revenues", "whole", _TOTAL * _M),
        ("us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax", "whole", 63_980 * _M),
        ("us-gaap:Revenues", "q4", 17_000 * _M),
        ("us-gaap:Revenues", "bare_pe", 27_143 * _M), ("us-gaap:Revenues", "bare_other", 46 * _M),
        ("us-gaap:Revenues", "agg_ext", 68_348 * _M), ("us-gaap:Revenues", "elim_ci", -260 * _M),
        ("us-gaap:Revenues", "three", 14_064 * _M),
        ("us-gaap:Revenues", "us", 32_880 * _M), ("us-gaap:Revenues", "nonus", 34_709 * _M),
    ]
    for member, (ext, ops) in _SEGMENTS.items():
        contexts[f"ext_{member}"] = {"dims": [(_CI, _EXT), (_SEG, member)], **fy}
        contexts[f"ops_{member}"] = {"dims": [(_CI, _OPS), (_SEG, member)], **fy}
        facts.append(("us-gaap:Revenues", f"ext_{member}", ext * _M))
        facts.append(("us-gaap:Revenues", f"ops_{member}", ops * _M))
    for member, value in _REGIONS.items():
        contexts[f"geo_{member}"] = {"dims": [(_GEO, member)], **fy}
        facts.append(("us-gaap:Revenues", f"geo_{member}", value * _M))
        # A narrower concept for the same cell must lose to `Revenues`.
        facts.append(("us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax", f"geo_{member}", 1.0))
    return instance_xml(contexts, facts)


@pytest.fixture(scope="module")
def cat_rows() -> list[dict]:
    facts = edgar_instance.parse_instance(_cat_instance(), tags=edgar_instance.INSTANCE_TAGS)
    return edgar_instance.dimensional_rows(facts, "CAT", _FILING)


def _tags(rows: list[dict], prefix: str) -> dict[str, float]:
    return {r["tag"]: r["value"] for r in rows if r["tag"].startswith(prefix)}


def _views(rows: list[dict]) -> list[_FactView]:
    return [_FactView(tag=r["tag"], value=r["value"], period_start=r["period_start"],
                      period_end=r["period_end"], filed=r["filed"]) for r in rows]


# ── The parser ──────────────────────────────────────────────────────────────


def test_segment_cells_are_stored_by_tier_and_eliminations_and_three_way_cells_are_not(cat_rows) -> None:
    seg = _tags(cat_rows, edgar_tags.SEGMENT_REVENUE_TAG)
    assert seg[f"{edgar_tags.SEGMENT_REVENUE_TAG}:ext:cat:ConstructionIndustriesMember"] == pytest.approx(24_800 * _M)
    assert seg[f"{edgar_tags.SEGMENT_REVENUE_TAG}:ops:cat:ConstructionIndustriesMember"] == pytest.approx(25_060 * _M)
    assert seg[f"{edgar_tags.SEGMENT_REVENUE_TAG}:bare:cat:PowerEnergyMember"] == pytest.approx(27_143 * _M)
    assert -260 * _M not in seg.values() and 14_064 * _M not in seg.values()


def test_geography_cells_keep_the_broader_concept_and_the_quarter_is_not_annual(cat_rows) -> None:
    geo = _tags(cat_rows, edgar_tags.GEOGRAPHIC_REVENUE_TAG)
    assert geo[f"{edgar_tags.GEOGRAPHIC_REVENUE_TAG}:srt:NorthAmericaMember"] == pytest.approx(36_609 * _M)
    assert 1.0 not in geo.values()
    cons = _tags(cat_rows, edgar_tags.CONSOLIDATED_REVENUE_TAG)
    assert cons[f"{edgar_tags.CONSOLIDATED_REVENUE_TAG}:Revenues"] == pytest.approx(_TOTAL * _M)
    assert 17_000 * _M not in cons.values()


def test_every_row_is_an_annual_usd_row_under_the_ami_taxonomy(cat_rows) -> None:
    for r in cat_rows:
        assert r["taxonomy"] == "ami" and r["unit"] == "USD" and r["fp"] == "FY"
        assert r["period_end"] == _END and r["period_start"] == date(2025, 1, 1)


# ── The partition ───────────────────────────────────────────────────────────


def test_the_four_regions_beat_the_us_non_us_pair() -> None:
    members = {**{m: v * _M for m, v in _REGIONS.items()},
               "country:US": 32_880 * _M, "us-gaap:NonUsMember": 34_709 * _M}
    assert set(filing_dimensions.select_partition(members, _TOTAL * _M)) == set(_REGIONS)


def test_the_four_segments_beat_their_own_aggregate() -> None:
    members = {m: ext * _M for m, (ext, _) in _SEGMENTS.items()}
    members[_AGG] = 68_348 * _M
    assert set(filing_dimensions.select_partition(members, _TOTAL * _M)) == set(_SEGMENTS)


def test_no_subset_inside_the_band_means_no_partition() -> None:
    assert filing_dimensions.select_partition({"a": 30 * _M, "b": 20 * _M}, 100 * _M) is None
    assert filing_dimensions.select_partition({"a": 92 * _M}, 100 * _M) is None  # one share is not a breakdown
    assert filing_dimensions.select_partition({}, 100 * _M) is None


# ── The resolvers ───────────────────────────────────────────────────────────


def test_an_aggregate_beside_one_segment_is_refused_not_rendered_at_100_percent(cat_rows) -> None:
    """Slot-4 audit MAJOR-1. `_AGGREGATE_MEMBER` is the only thing that stops a filer's
    own subtotal being rendered as a sibling of one of its parts — at a flawless 100%
    coverage, with the reconciliation sentence confirming it. The partition test above
    never reaches the filter (it sits one layer up, in `_members_at`); this one does,
    with the exact case the filter's comment fears: an aggregate beside ONE segment."""
    fy_end, fy_start = date(2025, 12, 31), date(2025, 1, 1)
    ext = f"{edgar_tags.SEGMENT_REVENUE_TAG}:ext:"
    views = [v for v in _views(cat_rows)
             if not v.tag.startswith(edgar_tags.SEGMENT_REVENUE_TAG + ":")
             and not v.tag.startswith(edgar_tags.GEOGRAPHIC_REVENUE_TAG + ":")]
    for member, share in (("us-gaap:ReportableSegmentsMember", 0.92), ("acme:WidgetsMember", 0.08)):
        views.append(_FactView(tag=ext + member, value=share * _TOTAL * _M,
                               period_start=fy_start, period_end=fy_end, filed=_FILED))
    assert filing_dimensions._members_at(views, ext, fy_end) == {"acme:WidgetsMember": pytest.approx(0.08 * _TOTAL * _M)}
    assert filing_dimensions.resolve_segment_revenue(views, _AS_OF) is None


def test_segments_resolve_on_the_external_sales_tier_with_the_coverage_stated(cat_rows) -> None:
    b = filing_dimensions.resolve_segment_revenue(_views(cat_rows), _AS_OF)
    assert b.labels == ("Power Energy", "Construction Industries", "Resource Industries", "Financial Products")
    assert b.values[0] == pytest.approx(27_143 * _M) and b.total == pytest.approx(_TOTAL * _M)
    assert b.basis == "external sales by segment" and b.coverage_pct == 101.1


def test_without_an_external_tier_the_operating_segment_tier_is_used(cat_rows) -> None:
    views = [v for v in _views(cat_rows) if ":ext:" not in v.tag]
    b = filing_dimensions.resolve_segment_revenue(views, _AS_OF)
    assert b.basis == "segment sales including intersegment"
    assert sum(b.values) == pytest.approx((25_060 + 12_474 + 32_201 + 4_220) * _M)


def test_a_bare_tier_that_covers_too_little_yields_nothing(cat_rows) -> None:
    views = [v for v in _views(cat_rows) if ":ext:" not in v.tag and ":ops:" not in v.tag]
    assert filing_dimensions.resolve_segment_revenue(views, _AS_OF) is None


def test_geography_resolves_to_the_regions(cat_rows) -> None:
    b = filing_dimensions.resolve_geographic_revenue(_views(cat_rows), _AS_OF)
    assert b.labels == ("North America", "EMEA", "Asia Pacific", "Latin America")
    assert b.coverage_pct == 100.0


def test_no_consolidated_total_or_a_stale_one_yields_nothing(cat_rows) -> None:
    views = [v for v in _views(cat_rows) if not v.tag.startswith(edgar_tags.CONSOLIDATED_REVENUE_TAG)]
    assert filing_dimensions.resolve_geographic_revenue(views, _AS_OF) is None
    assert filing_dimensions.resolve_geographic_revenue(_views(cat_rows), date(2027, 4, 1)) is None


@pytest.mark.parametrize("qname,label", [
    ("cat:ConstructionIndustriesMember", "Construction Industries"),
    ("de:ProductionAndPrecisionAgricultureSegmentMember", "Production and Precision Agriculture"),
    ("us-gaap:EMEAMember", "EMEA"), ("us-gaap:NonUsMember", "Non-US"),
    ("country:US", "United States"), ("country:GB", "United Kingdom"), ("country:ZZ", "ZZ"),
    ("f:FordModelEMember", "Ford Model E"), ("pcar:OtherCountriesMember", "Other Countries"),
])
def test_member_labels(qname, label) -> None:
    assert filing_dimensions.member_label(qname) == label


# ── The store ───────────────────────────────────────────────────────────────


@pytest.fixture
def seeded_segx(cat_rows):
    with get_session() as s:
        s.query(EdgarFactRow).filter(EdgarFactRow.ticker == "SEGX").delete()
        for r in cat_rows:
            s.add(EdgarFactRow(cik=1, ticker="SEGX", ingested_at=_NOW, **r))
        s.commit()
    yield
    with get_session() as s:
        s.query(EdgarFactRow).filter(EdgarFactRow.ticker == "SEGX").delete()
        s.commit()


def test_both_breakdowns_come_back_through_the_db_path_for_a_filer_with_no_lender(seeded_segx) -> None:
    dims = filing_dimensions.fetch_filing_dimensions("segx", _AS_OF)
    assert dims.lender is None and dims.debt_split is None
    assert dims.segments.labels[0] == "Power Energy"
    assert dims.geography.labels[0] == "North America"
    assert filing_dimensions.fetch_filing_dimensions("SEGX", date(2026, 2, 12)).segments is None


# ── The line, the overlay, the render seam ──────────────────────────────────


def test_the_line_states_shares_and_exact_coverage() -> None:
    line = revenue_breakdown_line("geography", ["North America", "EMEA"], [36_609, 12_793], 49_402,
                                  "2025-12-31", "revenue by region as tagged")
    assert line.startswith("Revenue by geography FY2025 (LIVE): North America $36,609M (74%), EMEA $12,793M (26%)")
    assert "these sum to the $49,402M consolidated total" in line


def test_the_line_states_a_reconciling_difference_when_the_sum_is_off() -> None:
    line = revenue_breakdown_line("segment", ["A", "B"], [60_000, 8_348], 67_589, "2025-12-31", "external sales by segment")
    assert "these sum to 101% of the $67,589M consolidated total, the difference being corporate items" in line
    assert revenue_breakdown_line("segment", ["A"], [1, 2], 3, "2025-12-31", "x") is None
    assert revenue_breakdown_line("segment", ["A"], [1], 0, "2025-12-31", "x") is None


def test_the_overlay_writes_millions_and_one_block_key_per_breakdown(monkeypatch) -> None:
    b = filing_dimensions.RevenueBreakdown(_END, ("North America", "EMEA"), (36_609 * _M, 12_793 * _M),
                                           _TOTAL * _M, "revenue by region as tagged")
    monkeypatch.setattr(filing_dimensions, "fetch_filing_dimensions",
                        lambda t, a: filing_dimensions.FilingDimensions(None, None, None, b))
    profile: dict = {}
    state: dict = {}
    room_runner._overlay_filing_dimensions(profile, state, "SEGX", _AS_OF)
    assert profile["geographic_revenue_labels"] == ["North America", "EMEA"]
    assert profile["geographic_revenue_values"] == [36_609, 12_793]
    assert profile["geographic_revenue_total"] == _TOTAL
    assert state == {"debt_split": "unavailable", "segment_revenue": "unavailable", "geographic_revenue": "live"}


def test_nothing_resolved_and_an_empty_store_is_logged_as_an_un_run_ingest(monkeypatch) -> None:
    monkeypatch.setattr(filing_dimensions, "fetch_filing_dimensions",
                        lambda t, a: filing_dimensions.FilingDimensions(None, None, None, None))
    monkeypatch.setattr(room_runner.edgar_pit, "prefix_ever_ingested", lambda prefix: False)
    logged: list = []
    monkeypatch.setattr(room_runner.logger, "warn", lambda event, **kw: logged.append(event))
    room_runner._overlay_filing_dimensions({}, {}, "SEGX", _AS_OF)
    assert "edgar_dimensional_rows_not_ingested" in logged


def _profile() -> dict:
    return {
        "field_state": {"segment_revenue": "live", "geographic_revenue": "live"},
        "segment_revenue_labels": ["Power Energy", "Construction Industries"],
        "segment_revenue_values": [27_143, 24_800], "segment_revenue_total": _TOTAL,
        "segment_revenue_period_end": "2025-12-31", "segment_revenue_basis": "external sales by segment",
        "geographic_revenue_labels": ["North America", "EMEA"],
        "geographic_revenue_values": [36_609, 12_793], "geographic_revenue_total": _TOTAL,
        "geographic_revenue_period_end": "2025-12-31", "geographic_revenue_basis": "revenue by region as tagged",
    }


@pytest.fixture(autouse=True)
def _flags_restored():
    before = (settings.room_segment_revenue_enabled, settings.room_geographic_revenue_enabled)
    yield
    settings.room_segment_revenue_enabled, settings.room_geographic_revenue_enabled = before


def test_both_flags_are_off_by_default_and_render_nothing() -> None:
    assert settings.room_segment_revenue_enabled is False
    assert settings.room_geographic_revenue_enabled is False
    sheet = room_prompts._format_profile(_profile(), AgentId.FUNDAMENTALS_ANALYST)
    assert "Revenue by segment" not in sheet and "Revenue by geography" not in sheet


def test_each_flag_renders_only_its_own_line() -> None:
    settings.room_segment_revenue_enabled = True
    sheet = room_prompts._format_profile(_profile(), AgentId.FUNDAMENTALS_ANALYST)
    assert "Revenue by segment FY2025 (LIVE): Power Energy $27,143M (40%)" in sheet
    assert "Revenue by geography" not in sheet
    settings.room_geographic_revenue_enabled = True
    sheet = room_prompts._format_profile(_profile(), AgentId.FUNDAMENTALS_ANALYST)
    assert "Revenue by geography FY2025 (LIVE): North America $36,609M (54%)" in sheet


def test_presence_is_not_provenance() -> None:
    settings.room_segment_revenue_enabled = True
    profile = _profile()
    profile["field_state"] = {}
    assert "Revenue by segment" not in room_prompts._format_profile(profile, AgentId.FUNDAMENTALS_ANALYST)
