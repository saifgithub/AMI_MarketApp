"""CR221 A1/A3 phase 2 — the sheet shows the debt block, and says what it is.

The source layer is tested per item (`test_cr221_a1_debt_maturity.py`,
`test_cr221_a3_interest_cost.py`). This pins the seam between it and the
prompt, where three things have to hold.

**The flag flip is the whole control arm.** §7 measures demand extinction
against ONE cached profile pickle per ticker, because market data moves
between fetches (R46). So the profile carries the block whether or not the
flag is on, and only the render is gated — a second profile build would
confound the comparison with everything else that moved in between.

**The ladder never renders bare.** Caterpillar's five buckets sum to $28,160M
next to a sheet reading gross debt $45,146M. Whatever else changes, the line
must carry the basis and the excluded short-term borrowings, or the $17B gap
reads as a contradiction and burns the turn CR219 exists to stop burning.

**A dark ingest is loud.** Alpha held 351,139 EDGAR facts and zero rows under
these tags on 2026-09-03, because the last ingest predated them. Absent data
and an un-run ingest are identical at the sheet, so they must not be identical
in the logs.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.db import get_session
from app.db.models import EdgarFactRow
from app.schemas.agents import AgentId
from app.services import edgar_tags, room_prompts, room_runner

_END = date(2025, 12, 31)
_FILED = date(2026, 2, 13)
_TAG_OF = dict(edgar_tags.DEBT_MATURITY_LADDER)
_CAT_LADDER = {"Within 1 year": 7_120, "Year 2": 8_920, "Year 3": 7_747,
               "Year 4": 3_112, "Year 5": 1_261}


def _profile() -> dict:
    """A profile shaped exactly as `_overlay_debt_structure` leaves it."""
    return {
        "field_state": {"debt_maturity": "live", "cost_of_debt": "live"},
        "debt_maturity_labels": list(_CAT_LADDER),
        "debt_maturity_values": list(_CAT_LADDER.values()),
        "debt_maturity_period_end": _END.isoformat(),
        "debt_maturity_beyond_5y": 9_656,
        "debt_maturity_excluded_st": 5_514,
        "cost_of_debt_pct": 5.1,
        "cost_of_debt_basis": "cash interest paid, fiscal year",
        "cost_of_debt_interest": 1_842,
        "cost_of_debt_gross_debt": 36_210,
        "cost_of_debt_period_end": _END.isoformat(),
    }


def _sheet(**flags) -> str:
    for name, value in flags.items():
        setattr(settings, name, value)
    return room_prompts._format_profile(_profile(), AgentId.FUNDAMENTALS_ANALYST)


@pytest.fixture(autouse=True)
def _flags_restored():
    before = (settings.room_debt_maturity_enabled, settings.room_cost_of_debt_enabled)
    yield
    (settings.room_debt_maturity_enabled,
     settings.room_cost_of_debt_enabled) = before


def test_both_flags_are_off_by_default() -> None:
    assert settings.room_debt_maturity_enabled is False
    assert settings.room_cost_of_debt_enabled is False


def test_the_same_profile_renders_nothing_with_the_flags_off() -> None:
    sheet = _sheet(room_debt_maturity_enabled=False, room_cost_of_debt_enabled=False)
    assert "Debt maturity ladder" not in sheet
    assert "Implied cost of debt" not in sheet


def test_the_ladder_appears_when_its_flag_is_on() -> None:
    sheet = _sheet(room_debt_maturity_enabled=True, room_cost_of_debt_enabled=False)
    assert "Debt maturity ladder" in sheet
    assert "Within 1 year $7,120M" in sheet
    assert "Year 5 $1,261M" in sheet
    assert "Implied cost of debt" not in sheet, "A3's flag must not ride on A1's"


def test_the_ladder_states_its_basis_and_what_it_excludes() -> None:
    sheet = _sheet(room_debt_maturity_enabled=True)
    assert "long-term debt principal as of 2025-12-31" in sheet
    assert "excludes short-term borrowings $5,514M" in sheet
    assert "beyond year 5 $9,656M (derived)" in sheet


def test_the_cost_of_debt_appears_with_both_its_inputs_and_its_basis() -> None:
    sheet = _sheet(room_cost_of_debt_enabled=True, room_debt_maturity_enabled=False)
    assert "Implied cost of debt" in sheet
    assert "5.1%" in sheet
    assert "$1,842M cash interest paid, fiscal year to 2025-12-31" in sheet
    assert "gross debt $36,210M" in sheet
    assert "Debt maturity ladder" not in sheet


def test_an_unavailable_block_never_renders_even_with_the_flag_on() -> None:
    profile = _profile()
    profile["field_state"] = {"debt_maturity": "unavailable",
                              "cost_of_debt": "unavailable"}
    settings.room_debt_maturity_enabled = True
    settings.room_cost_of_debt_enabled = True
    sheet = room_prompts._format_profile(profile, AgentId.FUNDAMENTALS_ANALYST)
    assert "Debt maturity ladder" not in sheet
    assert "Implied cost of debt" not in sheet


@pytest.fixture
def seeded():
    rows = [(tag, value * 1_000_000) for tag, value in
            [(_TAG_OF[k], v) for k, v in _CAT_LADDER.items()]
            ] + [(edgar_tags.LONG_TERM_DEBT_NONCURRENT, 30_696_000_000),
                 (edgar_tags.SHORT_TERM_BORROWINGS, 5_514_000_000),
                 ("InterestPaidNet", 1_842_000_000)]
    with get_session() as s:
        s.query(EdgarFactRow).filter(EdgarFactRow.ticker == "RNDX").delete()
        for tag, value in rows:
            duration = tag == "InterestPaidNet"
            s.add(EdgarFactRow(
                cik=3, ticker="RNDX", taxonomy="us-gaap", tag=tag, unit="USD",
                value=value,
                period_start=_END - timedelta(days=364) if duration else None,
                period_end=_END, filed=_FILED, accession_no=f"acc-{tag}",
                ingested_at=datetime(2026, 9, 3, tzinfo=timezone.utc),
            ))
        s.commit()
    yield
    with get_session() as s:
        s.query(EdgarFactRow).filter(EdgarFactRow.ticker == "RNDX").delete()
        s.commit()


def test_the_overlay_converts_edgar_dollars_to_the_sheets_millions(seeded) -> None:
    profile: dict = {}
    field_state: dict[str, str] = {}
    room_runner._overlay_debt_structure(profile, field_state, "RNDX", date(2026, 3, 1))

    assert field_state == {"debt_maturity": "live", "cost_of_debt": "live"}
    assert profile["debt_maturity_values"] == [7_120, 8_920, 7_747, 3_112, 1_261]
    assert profile["debt_maturity_beyond_5y"] == 9_656
    assert profile["cost_of_debt_interest"] == 1_842
    assert profile["cost_of_debt_gross_debt"] == 36_210
    assert profile["cost_of_debt_pct"] == 5.1


def test_an_un_ingested_store_is_logged_not_silently_absent(monkeypatch) -> None:
    """Absent data and an un-run ingest look identical on the sheet."""
    warned: list[tuple] = []
    monkeypatch.setattr(room_runner.logger, "warn",
                        lambda event, **kw: warned.append((event, kw)))
    field_state: dict[str, str] = {}
    room_runner._overlay_debt_structure({}, field_state, "NOSUCH", date(2026, 3, 1))

    assert field_state["debt_maturity"] == "unavailable"
    assert ("edgar_debt_structure_tags_not_ingested" in [e for e, _ in warned]), warned


def test_a_filer_present_in_the_store_does_not_trip_the_ingest_warning(
    seeded, monkeypatch
) -> None:
    warned: list[str] = []
    monkeypatch.setattr(room_runner.logger, "warn",
                        lambda event, **kw: warned.append(event))
    room_runner._overlay_debt_structure({}, {}, "OTHERTKR", date(2026, 3, 1))
    assert "edgar_debt_structure_tags_not_ingested" not in warned
