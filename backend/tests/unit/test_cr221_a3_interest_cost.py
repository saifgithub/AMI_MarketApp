"""CR221 A3 / DEF399 — the cost of debt names its basis, or it is absent.

DEF399 is what happens when two interest figures get blended: the shipped
`interest_coverage` divides EBIT by a non-operating stub and reads 31.8x for a
company covering ~6x. This module's job is to make that unrepresentable, and
these tests pin the three ways it does it.

**The basis travels with the number.** Accrued-TTM, accrued-annual and
cash-paid-annual are different measurements. Each is labelled; none is silently
substituted for another.

**Disagreement is absence, not a coin toss.** Where the accrual and cash tags
differ by more than 2x one of them excludes the finance arm, and which one
cannot be told from the fact store. Harley-Davidson ($31M vs $331M) and Ford
($7,613M vs $3,501M) are the measured cases and both must return nothing.

**Caterpillar has to work on cash alone.** It tags no income-statement interest
concept in `companyfacts` — the lines are dimensional — so a resolver that
required the accrual tag would be dark on the ticker the whole CR219 corpus
runs on.

Fixture values are live measured facts (CAT, DE, F, HOG companyfacts and CAT's
10-K `R3.htm`, read 2026-09-03), in millions of USD.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.db import get_session
from app.db.models import EdgarFactRow
from app.services import edgar_tags, interest_cost
from app.services.edgar_pit import _FactView

_AS_OF = date(2026, 3, 1)
_FY_END = date(2025, 12, 31)
_FILED = date(2026, 2, 13)

_CAT_CASH_INTEREST = 1_842
_CAT_NONCURRENT = 30_696
_CAT_SHORT_TERM = 5_514
_CAT_GROSS_DEBT = _CAT_NONCURRENT + _CAT_SHORT_TERM


def _instant(tag: str, value: float, end: date = _FY_END) -> _FactView:
    return _FactView(tag=tag, value=value, period_start=None, period_end=end,
                     filed=_FILED)


def _annual(tag: str, value: float, end: date = _FY_END) -> _FactView:
    return _FactView(tag=tag, value=value, period_start=end - timedelta(days=364),
                     period_end=end, filed=_FILED)


def _quarters(tag: str, values: list[float], end: date = _FY_END) -> list[_FactView]:
    """Four discrete quarters, oldest first, the last ending at `end`."""
    out = []
    for i, v in enumerate(reversed(values)):
        q_end = end - timedelta(days=91 * i)
        out.append(_FactView(tag=tag, value=v, period_start=q_end - timedelta(days=90),
                             period_end=q_end, filed=q_end + timedelta(days=40)))
    return out


def _debt() -> list[_FactView]:
    return [
        _instant(edgar_tags.LONG_TERM_DEBT_NONCURRENT, _CAT_NONCURRENT),
        _instant(edgar_tags.SHORT_TERM_BORROWINGS, _CAT_SHORT_TERM),
    ]


def test_caterpillar_resolves_on_cash_interest_because_it_tags_no_accrual_concept() -> None:
    facts = _debt() + [_annual("InterestPaidNet", _CAT_CASH_INTEREST)]
    cost = interest_cost.resolve_interest_cost(facts, _AS_OF)

    assert cost is not None
    assert cost.basis == interest_cost.CASH_ANNUAL
    assert cost.annual_interest == _CAT_CASH_INTEREST
    assert cost.gross_debt == _CAT_GROSS_DEBT
    assert cost.cost_of_debt_pct == 5.1


def test_a_quarterly_accrual_series_wins_and_says_it_is_ttm() -> None:
    facts = (_debt()
             + _quarters("InterestExpense", [780, 790, 800, 800])
             + [_annual("InterestPaidNet", 3_080)])
    cost = interest_cost.resolve_interest_cost(facts, _AS_OF)

    assert cost.basis == interest_cost.ACCRUED_TTM
    assert cost.annual_interest == 3_170


def test_an_annual_accrual_figure_is_used_when_the_quarters_do_not_make_a_year() -> None:
    facts = (_debt()
             + _quarters("InterestExpense", [780, 790, 800, 800])[:2]
             + [_annual("InterestExpense", 3_170)])
    cost = interest_cost.resolve_interest_cost(facts, _AS_OF)

    assert cost.basis == interest_cost.ACCRUED_ANNUAL
    assert cost.annual_interest == 3_170


@pytest.mark.parametrize(
    "name,accrued,cash",
    [("harley-davidson", 31, 331), ("ford", 7_613, 3_501)],
)
def test_two_irreconcilable_bases_return_nothing(name, accrued, cash) -> None:
    facts = _debt() + [_annual("InterestExpense", accrued),
                       _annual("InterestPaidNet", cash)]
    assert interest_cost.resolve_interest_cost(facts, _AS_OF) is None, (
        f"{name}: picking either figure is DEF399"
    )


def test_bases_that_agree_are_not_refused() -> None:
    """Deere: $3,170M accrued against $3,080M paid — a 1.03x gap is timing."""
    facts = _debt() + [_annual("InterestExpense", 3_170),
                       _annual("InterestPaidNet", 3_080)]
    cost = interest_cost.resolve_interest_cost(facts, _AS_OF)
    assert cost is not None
    assert cost.annual_interest == 3_170


def test_no_debt_on_the_balance_sheet_means_no_rate() -> None:
    facts = [_annual("InterestPaidNet", _CAT_CASH_INTEREST)]
    assert interest_cost.resolve_interest_cost(facts, _AS_OF) is None


def test_no_interest_on_either_basis_means_no_rate() -> None:
    assert interest_cost.resolve_interest_cost(_debt(), _AS_OF) is None


def test_an_implausible_rate_is_dropped_but_the_interest_figure_survives() -> None:
    """A year of interest against a repaid balance is an artifact, not a rate."""
    facts = [_instant(edgar_tags.LONG_TERM_DEBT_NONCURRENT, 1_000),
             _annual("InterestPaidNet", 500)]
    cost = interest_cost.resolve_interest_cost(facts, _AS_OF)
    assert cost.annual_interest == 500
    assert cost.cost_of_debt_pct is None


def test_a_negative_signed_interest_expense_is_the_same_outflow() -> None:
    facts = _debt() + [_annual("InterestPaidNet", -_CAT_CASH_INTEREST)]
    cost = interest_cost.resolve_interest_cost(facts, _AS_OF)
    assert cost.annual_interest == _CAT_CASH_INTEREST
    assert cost.cost_of_debt_pct == 5.1


@pytest.fixture
def seeded():
    rows = _debt() + [_annual("InterestPaidNet", _CAT_CASH_INTEREST)]
    with get_session() as s:
        s.query(EdgarFactRow).filter(EdgarFactRow.ticker == "INTX").delete()
        for f in rows:
            s.add(EdgarFactRow(
                cik=2, ticker="INTX", taxonomy="us-gaap", tag=f.tag, unit="USD",
                value=f.value, period_start=f.period_start, period_end=f.period_end,
                filed=f.filed, accession_no=f"acc-{f.tag}",
                ingested_at=datetime(2026, 9, 3, tzinfo=timezone.utc),
            ))
        s.commit()
    yield
    with get_session() as s:
        s.query(EdgarFactRow).filter(EdgarFactRow.ticker == "INTX").delete()
        s.commit()


def test_the_stored_figures_come_back_through_the_db_path(seeded) -> None:
    cost = interest_cost.fetch_interest_cost("intx", _AS_OF)
    assert cost is not None
    assert cost.cost_of_debt_pct == 5.1


def test_facts_filed_after_the_as_of_are_invisible(seeded) -> None:
    assert interest_cost.fetch_interest_cost("INTX", _FILED - timedelta(days=1)) is None


def test_both_interest_tag_families_are_ingested_so_the_resolver_can_fire() -> None:
    """The CR221 §6 shape: a correct resolver fed by a tag nobody stores."""
    needed = edgar_tags.INTEREST_ACCRUAL + edgar_tags.INTEREST_CASH
    missing = [t for t in needed if t not in edgar_tags.INGEST_TAGS_US_GAAP]
    assert not missing, f"ingest would never store {missing}"
