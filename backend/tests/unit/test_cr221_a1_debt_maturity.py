"""CR221 A1 — the debt maturity ladder is one vintage, or it is not a ladder.

The Room asked for this schedule 14 times across 6 agents. Three things are
pinned here, each of them a way the answer could be worse than no answer.

**One vintage.** Buckets are admitted only at the anchor's own `period_end`.
A filer that stops tagging year five leaves a four-year ladder, not a
five-year one with a stale tail — and a four-year ladder must SAY it is four.

**The residual is arithmetic or it is absent.** `beyond_year_five` is
noncurrent debt less years two through five. With a bucket missing that
subtraction rolls the gap into the residual; with a negative result the two
disclosures disagree. Both refuse. Deere is the live case: five buckets, no
`LongTermDebtNoncurrent` at its FY end.

**The parser can actually fire.** CR221 §6 found a finished WP10 parser whose
input tag is never ingested — silence indistinguishable from "this filer
discloses nothing" (CR040 / DEF059). The last test pins the five tags into
`INGEST_TAGS_US_GAAP` so this one cannot repeat the shape.

Fixture values are the live measured facts, not invented ones: Caterpillar at
2025-12-31 and Deere at 2025-11-02, read from `companyfacts` on 2026-09-03.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.db import get_session
from app.db.models import EdgarFactRow
from app.services import debt_maturity, edgar_tags
from app.services.edgar_pit import _FactView

_AS_OF = date(2026, 3, 1)
_END = date(2025, 12, 31)
_FILED = date(2026, 2, 13)

# Caterpillar's FY2025 10-K, in millions of USD.
_CAT = {"Within 1 year": 7_120, "Year 2": 8_920, "Year 3": 7_747,
        "Year 4": 3_112, "Year 5": 1_261}
_CAT_NONCURRENT = 30_696
_CAT_SHORT_TERM = 5_514
# Deere's FY2025 10-K (fiscal year ends in November), same units.
_DE = {"Within 1 year": 8_921, "Year 2": 8_935, "Year 3": 9_220,
       "Year 4": 6_556, "Year 5": 4_615}

_TAG_OF = dict(edgar_tags.DEBT_MATURITY_LADDER)


def _fact(tag: str, value: float, end: date = _END, filed: date = _FILED) -> _FactView:
    return _FactView(tag=tag, value=value, period_start=None, period_end=end, filed=filed)


def _ladder_facts(buckets: dict[str, float], **kw) -> list[_FactView]:
    return [_fact(_TAG_OF[label], v, **kw) for label, v in buckets.items()]


def _cat_facts(**kw) -> list[_FactView]:
    return _ladder_facts(_CAT, **kw) + [
        _fact(edgar_tags.LONG_TERM_DEBT_NONCURRENT, _CAT_NONCURRENT, **kw),
        _fact(edgar_tags.SHORT_TERM_BORROWINGS, _CAT_SHORT_TERM, **kw),
    ]


def test_the_ladder_resolves_at_one_date_and_sums_to_what_was_filed() -> None:
    ladder = debt_maturity.resolve_debt_maturity(_cat_facts(), _AS_OF)
    assert ladder is not None
    assert ladder.period_end == _END
    assert ladder.buckets == tuple(_CAT.items())
    assert ladder.disclosed_total == 28_160
    assert ladder.is_complete


def test_the_ladder_carries_what_it_does_not_cover() -> None:
    """The $17B gap between the ladder and gross debt has to be explicable.

    Ladder 28,160 + short-term 5,514 + beyond-five 9,656 = 43,330, against a
    gross-debt line of 45,146 struck at a different date. Without these two
    figures an agent reads the ladder-vs-sheet gap as a contradiction, which
    is the CR219 failure this whole CR is downstream of.
    """
    ladder = debt_maturity.resolve_debt_maturity(_cat_facts(), _AS_OF)
    assert ladder.long_term_debt_noncurrent == _CAT_NONCURRENT
    assert ladder.excluded_short_term_borrowings == _CAT_SHORT_TERM
    years_two_to_five = sum(v for k, v in _CAT.items() if k != "Within 1 year")
    assert ladder.beyond_year_five == _CAT_NONCURRENT - years_two_to_five
    assert ladder.beyond_year_five == 9_656


def test_a_bucket_from_an_older_filing_is_dropped_not_backfilled() -> None:
    stale_year_five = _fact(_TAG_OF["Year 5"], 999, end=date(2024, 12, 31),
                            filed=date(2025, 2, 13))
    facts = [f for f in _cat_facts() if f.tag != _TAG_OF["Year 5"]] + [stale_year_five]

    ladder = debt_maturity.resolve_debt_maturity(facts, _AS_OF)
    assert [label for label, _ in ladder.buckets] == ["Within 1 year", "Year 2",
                                                      "Year 3", "Year 4"]
    assert 999 not in [v for _, v in ladder.buckets]
    assert not ladder.is_complete
    assert ladder.disclosed_total == 26_899


def test_a_short_ladder_refuses_the_residual_rather_than_absorbing_the_gap() -> None:
    facts = [f for f in _cat_facts() if f.tag != _TAG_OF["Year 4"]]
    ladder = debt_maturity.resolve_debt_maturity(facts, _AS_OF)

    assert ladder.long_term_debt_noncurrent == _CAT_NONCURRENT
    assert ladder.beyond_year_five is None, (
        "with year four missing the subtraction would report 9,656 + 3,112 as "
        "maturing beyond year five"
    )


def test_deere_ships_a_ladder_with_no_residual_because_it_tags_no_noncurrent_debt() -> None:
    ladder = debt_maturity.resolve_debt_maturity(
        _ladder_facts(_DE, end=date(2025, 11, 2), filed=date(2025, 12, 18)),
        date(2026, 3, 1),
    )
    assert ladder.is_complete
    assert ladder.disclosed_total == 38_247
    assert ladder.beyond_year_five is None
    assert ladder.long_term_debt_noncurrent is None


def test_a_negative_residual_is_a_disagreement_and_reads_as_absent() -> None:
    facts = _ladder_facts(_CAT) + [
        _fact(edgar_tags.LONG_TERM_DEBT_NONCURRENT, 1_000),
    ]
    ladder = debt_maturity.resolve_debt_maturity(facts, _AS_OF)
    assert ladder.is_complete
    assert ladder.beyond_year_five is None


def test_an_amendment_supersedes_the_original_at_the_same_period_end() -> None:
    facts = _cat_facts() + [_fact(_TAG_OF["Year 2"], 9_500, filed=date(2026, 5, 1))]
    ladder = debt_maturity.resolve_debt_maturity(facts, date(2026, 6, 1))
    assert dict(ladder.buckets)["Year 2"] == 9_500


def test_no_anchor_means_no_ladder_not_a_partial_one() -> None:
    facts = [f for f in _cat_facts() if f.tag != _TAG_OF["Within 1 year"]]
    assert debt_maturity.resolve_debt_maturity(facts, _AS_OF) is None


def test_a_ladder_older_than_the_instant_bound_is_refused() -> None:
    assert debt_maturity.resolve_debt_maturity(_cat_facts(), date(2027, 6, 1)) is None


@pytest.fixture
def seeded():
    with get_session() as s:
        s.query(EdgarFactRow).filter(EdgarFactRow.ticker == "LADX").delete()
        for f in _cat_facts():
            s.add(EdgarFactRow(
                cik=1, ticker="LADX", taxonomy="us-gaap", tag=f.tag, unit="USD",
                value=f.value, period_start=None, period_end=f.period_end,
                filed=f.filed, accession_no=f"acc-{f.tag}",
                ingested_at=datetime(2026, 9, 3, tzinfo=timezone.utc),
            ))
        s.commit()
    yield
    with get_session() as s:
        s.query(EdgarFactRow).filter(EdgarFactRow.ticker == "LADX").delete()
        s.commit()


def test_the_stored_ladder_comes_back_through_the_db_path(seeded) -> None:
    ladder = debt_maturity.fetch_debt_maturity("ladx", _AS_OF)
    assert ladder is not None
    assert ladder.disclosed_total == 28_160
    assert ladder.beyond_year_five == 9_656


def test_a_ladder_filed_after_the_as_of_is_invisible(seeded) -> None:
    assert debt_maturity.fetch_debt_maturity("LADX", _FILED - timedelta(days=1)) is None


def test_the_flag_is_off_and_the_resolver_does_not_read_it(monkeypatch) -> None:
    """The gate is a render-layer decision, so `None` here means one thing only.

    A fetcher that returned None for a flag-off feature would make "we did not
    ask" and "the filer discloses nothing" the same value at the call site.
    """
    assert settings.room_debt_maturity_enabled is False
    off = debt_maturity.resolve_debt_maturity(_cat_facts(), _AS_OF)
    monkeypatch.setattr(settings, "room_debt_maturity_enabled", True)
    assert debt_maturity.resolve_debt_maturity(_cat_facts(), _AS_OF) == off


def test_the_five_tags_are_actually_ingested_so_the_resolver_can_fire() -> None:
    """CR221 §6's failure shape: a correct parser fed by a tag nobody stores."""
    missing = [t for t in edgar_tags.DEBT_MATURITY_TAGS
               if t not in edgar_tags.INGEST_TAGS_US_GAAP]
    assert not missing, f"ingest would never store {missing}"
    assert len(edgar_tags.DEBT_MATURITY_TAGS) == 5
