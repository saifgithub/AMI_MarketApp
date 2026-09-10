"""The facts a filing carries only dimensionally, read from its XBRL instance (CR221 slot 4).

`companyfacts` — the endpoint every other EDGAR fact in this app comes from —
serves the consolidated, non-dimensional value of each concept and nothing
else: 0 of Caterpillar's 39,403 points carry a `segment` (CR221 §6). So the
three things the Room asked for most that live in a filing's *columns* rather
than its totals — the captive-finance debt split (A2), revenue by segment (D1)
and by geography (D2) — cannot come from it, and CR219's parked R38 build
could never fire.

They are in the filing itself. Every 10-K since inline XBRL became mandatory
ships an extracted instance document (`<primary>_htm.xml`) beside the HTML,
and its `xbrli:context` elements carry the `xbrldi:explicitMember` dimensions
that `companyfacts` strips. Measured on 2026-09-10 across four filers:

  * CAT splits its consolidating balance sheet on `srt:ProductOrServiceAxis`
    (`cat:FinancialProductsMember` / `cat:MachineryPowerEnergyMember`) — the
    two columns' `LongTermDebtAndCapitalLeaseObligations` sum to the
    non-dimensional `LongTermDebtNoncurrent` to the dollar ($20,018M +
    $10,678M = $30,696M);
  * F splits on `us-gaap:StatementBusinessSegmentsAxis` (`f:FordCreditMember` /
    `f:CompanyExcludingFordCreditMember`) with a combined-debt tag per side;
  * PCAR tags only the finance side; DE tags no captive-side debt at all.

**The industrial half is read from the filing's own column, never derived.**
The parked design computed it as consolidated − captive, and on CAT that
gives $3,593M against the filed $10,713M: the house gross-debt definition
(`DEBT_ANCHOR` + `DEBT_OPTIONAL_ADD`) is on a different tag family from the
consolidating column, so the subtraction crosses concepts. A filer that tags
only one side gets one side rendered, and the line says so.

This module is PURE: bytes in, row dicts out, shaped for `EdgarFactRow`. The
network and the store are the ingest script's (`scripts/ingest_edgar_dimensional.py`);
the render-time readers are in `filing_dimensions.py`. Derived rows carry the
`ami` taxonomy and an `ami:` tag prefix so the PIT resolver, which asks for
us-gaap/dei tags by name, can never mistake a member's figure for the whole
company's.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date
from typing import Iterable
from xml.etree import ElementTree as ET

from app.services import edgar_tags

_XBRLI = "http://www.xbrl.org/2003/instance"
_XBRLDI = "http://xbrl.org/2006/xbrldi"

# A duration fact spanning a fiscal year — `edgar_pit._ANNUAL_SPAN`'s bounds.
_ANNUAL_SPAN_DAYS = (330, 380)

# `srt:ConsolidationItemsAxis` members that qualify a segment figure as the
# segment's own revenue rather than an elimination or a reconciling item, and
# the tier label each maps to. "ext" (external sales) is the cleaner partition
# and is preferred at read time; "ops" includes intersegment sales; "bare" is
# a segment member with no consolidation qualifier at all (Deere's shape).
_SEGMENT_TIER_OF_CONSOLIDATION_MEMBER = {
    "operatingsegmentsexcludingintersegmentelimination": "ext",
    "operatingsegments": "ops",
}
SEGMENT_TIERS = ("ext", "ops", "bare")

_SEGMENT_AXIS = "StatementBusinessSegmentsAxis"
_GEOGRAPHIC_AXIS = "StatementGeographicalAxis"
_CONSOLIDATION_AXIS = "ConsolidationItemsAxis"


@dataclass(frozen=True)
class Context:
    """One `xbrli:context`: its explicit dimensions and its period."""

    dims: tuple[tuple[str, str], ...]  # (axis LOCAL name, member QName as written)
    instant: date | None
    start: date | None
    end: date | None

    @property
    def axes(self) -> tuple[str, ...]:
        return tuple(axis for axis, _ in self.dims)

    def member_on(self, axis: str) -> str | None:
        for a, member in self.dims:
            if a == axis:
                return member
        return None

    @property
    def is_annual(self) -> bool:
        if self.start is None or self.end is None:
            return False
        lo, hi = _ANNUAL_SPAN_DAYS
        return lo <= (self.end - self.start).days <= hi


@dataclass(frozen=True)
class Fact:
    """One numeric fact: concept, value, unit, and the context it sits in."""

    taxonomy: str  # namespace prefix as the filing declares it: us-gaap, dei, cat …
    tag: str       # concept local name
    value: float
    unit: str      # normalised: "USD", "SHARES", …
    context: Context


@dataclass(frozen=True)
class Filing:
    """Identity of the filing the facts were read from — the PIT keys."""

    cik: int
    ticker: str
    accession_no: str
    form: str
    filed: date
    fy: int | None


def _local(qname: str) -> str:
    return qname.rsplit(":", 1)[-1]


def _date(text: str | None) -> date | None:
    if not text:
        return None
    try:
        return date.fromisoformat(text.strip())
    except ValueError:
        return None


def _unit(measure: str | None) -> str:
    """`usd`, `USD`, `U_USD`, `iso4217_USD`, `iso4217:USD` → `USD`."""
    if not measure:
        return ""
    return measure.replace(":", "_").rsplit("_", 1)[-1].upper()


def _units(root: ET.Element) -> dict[str, str]:
    """`xbrli:unit` id → normalised measure. A `unitRef` is an opaque id that
    the filer's tool chooses — CAT writes `usd`, Deere's writes
    `Ifeqnbq-buca0lohammirw` — so the unit is only knowable through the unit
    element it points at. A divide unit (USD per share) joins its measures
    with `/` and so never reads as plain USD."""
    out: dict[str, str] = {}
    for unit in root.iter(f"{{{_XBRLI}}}unit"):
        uid = unit.get("id")
        if not uid:
            continue
        measures = [(m.text or "").strip() for m in unit.iter(f"{{{_XBRLI}}}measure")]
        out[uid] = "/".join(_unit(m) for m in measures if m)
    return out


def parse_instance(xml: bytes, *, tags: frozenset[str] | None = None) -> list[Fact]:
    """Every numeric fact in an XBRL instance, with its context resolved.

    `tags` narrows to a set of concept local names — an instance is 3–4k facts
    and the callers want a few dozen. A fact whose text is not a number (text
    blocks, nil facts) is skipped, never stored as zero.
    """
    prefixes: dict[str, str] = {}
    for _event, (prefix, uri) in ET.iterparse(io.BytesIO(xml), events=("start-ns",)):
        prefixes.setdefault(uri, prefix)
    root = ET.fromstring(xml)
    units = _units(root)

    contexts: dict[str, Context] = {}
    for c in root.iter(f"{{{_XBRLI}}}context"):
        cid = c.get("id")
        if not cid:
            continue
        dims = tuple(
            (_local(m.get("dimension") or ""), (m.text or "").strip())
            for m in c.iter(f"{{{_XBRLDI}}}explicitMember")
        )
        period = c.find(f"{{{_XBRLI}}}period")
        instant = start = end = None
        if period is not None:
            instant = _date(getattr(period.find(f"{{{_XBRLI}}}instant"), "text", None))
            start = _date(getattr(period.find(f"{{{_XBRLI}}}startDate"), "text", None))
            end = _date(getattr(period.find(f"{{{_XBRLI}}}endDate"), "text", None))
        contexts[cid] = Context(dims=dims, instant=instant, start=start, end=end)

    facts: list[Fact] = []
    for el in root.iter():
        cref = el.get("contextRef")
        if not cref:
            continue
        uri, _, local = el.tag[1:].partition("}") if el.tag.startswith("{") else ("", "", el.tag)
        if tags is not None and local not in tags:
            continue
        ctx = contexts.get(cref)
        if ctx is None:
            continue
        try:
            value = float((el.text or "").strip())
        except ValueError:
            continue
        if value != value:  # NaN
            continue
        unit_ref = el.get("unitRef") or ""
        facts.append(Fact(
            taxonomy=prefixes.get(uri, uri), tag=local, value=value,
            unit=units.get(unit_ref) or _unit(unit_ref), context=ctx,
        ))
    return facts


# ── Row extraction ──────────────────────────────────────────────────────────


def _row(filing: Filing, tag: str, value: float, ctx: Context) -> dict:
    period_end = ctx.end or ctx.instant
    assert period_end is not None
    return {
        "taxonomy": edgar_tags.DIMENSIONAL_TAXONOMY,
        "tag": tag,
        "unit": "USD",
        "value": value,
        "period_start": ctx.start,
        "period_end": period_end,
        "fy": filing.fy,
        "fp": "FY" if ctx.is_annual or ctx.instant else None,
        "form": filing.form,
        "filed": filing.filed,
        "accession_no": filing.accession_no,
    }


def _usd_us_gaap(facts: Iterable[Fact], tags: Iterable[str]) -> list[Fact]:
    wanted = frozenset(tags)
    return [f for f in facts if f.taxonomy == "us-gaap" and f.tag in wanted and f.unit == "USD"]


def debt_split_rows(facts: Iterable[Fact], ticker: str, filing: Filing) -> list[dict]:
    """`ami:CaptiveFinanceDebt:<tag>` / `ami:IndustrialDebt:<tag>` rows.

    One dimension only, on one of the consolidating axes, and the member must
    resolve through the registry — a registry miss is the common case (no
    captive lender) and yields nothing, not an "unavailable" row. A negative
    figure is refused: it means the column is not a balance-sheet carrying
    amount. Where a filer tags the same concept under two members for one
    column (CAT: `FinancialProductsMember` and `FinancialProductsSegmentMember`,
    same value) the first is kept; if the two DISAGREE the concept is dropped
    for that instant, because the filing is then saying two things.
    """
    if edgar_tags.captive_finance_lender(ticker) is None:
        return []
    seen: dict[tuple[str, date], float] = {}
    disputed: set[tuple[str, date]] = set()
    for f in _usd_us_gaap(facts, edgar_tags.DEBT_SPLIT_SOURCE_TAGS):
        ctx = f.context
        if ctx.instant is None or len(ctx.dims) != 1:
            continue
        axis, member = ctx.dims[0]
        if axis not in edgar_tags.DEBT_SPLIT_AXES:
            continue
        role = edgar_tags.captive_finance_role(ticker, member)
        if role is None or f.value < 0:
            continue
        prefix = edgar_tags.CAPTIVE_DEBT_TAG if role == "captive" else edgar_tags.INDUSTRIAL_DEBT_TAG
        key = (f"{prefix}:{f.tag}", ctx.instant)
        if key in seen and seen[key] != f.value:
            disputed.add(key)
        seen.setdefault(key, f.value)
    return [
        _row(filing, tag, value, Context(dims=(), instant=instant, start=None, end=None))
        for (tag, instant), value in seen.items()
        if (tag, instant) not in disputed
    ]


def _revenue_rank(tag: str) -> int:
    return edgar_tags.REVENUE_TAGS.index(tag)


def _keep_preferred(candidates: dict[tuple[str, date], tuple[int, float, Context]],
                    key: tuple[str, date], fact: Fact) -> None:
    """Between `Revenues` and `RevenueFromContractWithCustomerExcludingAssessedTax`
    for one member and period, keep the broader concept (`REVENUE_TAGS` order)."""
    rank = _revenue_rank(fact.tag)
    held = candidates.get(key)
    if held is None or rank < held[0]:
        candidates[key] = (rank, fact.value, fact.context)


def segment_revenue_rows(facts: Iterable[Fact], ticker: str, filing: Filing) -> list[dict]:
    """`ami:SegmentRevenue:<tier>:<member>` rows, annual durations only.

    A member on the segments axis alone is tier `bare`; crossed with
    `ConsolidationItemsAxis` it is admitted only under the two operating-
    segment qualifiers (tier `ext` / `ops`). Anything else — eliminations,
    corporate items, geography-crossed cells — is not a segment's revenue.
    """
    candidates: dict[tuple[str, date], tuple[int, float, Context]] = {}
    for f in _usd_us_gaap(facts, edgar_tags.REVENUE_TAGS):
        ctx = f.context
        if not ctx.is_annual or f.value <= 0:
            continue
        member = ctx.member_on(_SEGMENT_AXIS)
        if member is None:
            continue
        axes = set(ctx.axes)
        if axes == {_SEGMENT_AXIS}:
            tier = "bare"
        elif axes == {_SEGMENT_AXIS, _CONSOLIDATION_AXIS}:
            qualifier = edgar_tags.normalize_member_name(ctx.member_on(_CONSOLIDATION_AXIS) or "")
            tier = _SEGMENT_TIER_OF_CONSOLIDATION_MEMBER.get(qualifier)
            if tier is None:
                continue
        else:
            continue
        assert ctx.end is not None
        _keep_preferred(candidates, (f"{edgar_tags.SEGMENT_REVENUE_TAG}:{tier}:{member}", ctx.end), f)
    return [_row(filing, tag, value, ctx) for (tag, _), (_, value, ctx) in candidates.items()]


def geographic_revenue_rows(facts: Iterable[Fact], ticker: str, filing: Filing) -> list[dict]:
    """`ami:GeographicRevenue:<member>` rows — the geography axis alone, annual."""
    candidates: dict[tuple[str, date], tuple[int, float, Context]] = {}
    for f in _usd_us_gaap(facts, edgar_tags.REVENUE_TAGS):
        ctx = f.context
        if not ctx.is_annual or f.value <= 0 or len(ctx.dims) != 1:
            continue
        member = ctx.member_on(_GEOGRAPHIC_AXIS)
        if member is None:
            continue
        assert ctx.end is not None
        _keep_preferred(candidates, (f"{edgar_tags.GEOGRAPHIC_REVENUE_TAG}:{member}", ctx.end), f)
    return [_row(filing, tag, value, ctx) for (tag, _), (_, value, ctx) in candidates.items()]


def consolidated_revenue_rows(facts: Iterable[Fact], ticker: str, filing: Filing) -> list[dict]:
    """`ami:ConsolidatedRevenue:<tag>` — the non-dimensional annual total from
    the SAME instance, so a breakdown is always checked against its own
    filing's total rather than against a vendor TTM figure."""
    candidates: dict[tuple[str, date], tuple[int, float, Context]] = {}
    for f in _usd_us_gaap(facts, edgar_tags.REVENUE_TAGS):
        ctx = f.context
        if ctx.dims or not ctx.is_annual or f.value <= 0:
            continue
        assert ctx.end is not None
        _keep_preferred(candidates, (f"{edgar_tags.CONSOLIDATED_REVENUE_TAG}:{f.tag}", ctx.end), f)
    return [_row(filing, tag, value, ctx) for (tag, _), (_, value, ctx) in candidates.items()]


def dimensional_rows(facts: Iterable[Fact], ticker: str, filing: Filing) -> list[dict]:
    """Every derived row this filing yields, for the ingest to store."""
    facts = list(facts)
    return (
        debt_split_rows(facts, ticker, filing)
        + segment_revenue_rows(facts, ticker, filing)
        + geographic_revenue_rows(facts, ticker, filing)
        + consolidated_revenue_rows(facts, ticker, filing)
    )


# The concept local names `parse_instance` needs to keep for the extractors.
INSTANCE_TAGS: frozenset[str] = frozenset(edgar_tags.DEBT_SPLIT_SOURCE_TAGS) | frozenset(
    edgar_tags.REVENUE_TAGS
)
