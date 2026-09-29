"""CR247 Phase 1B — return on invested capital, every leg computed in code.

The Fundamentals lane carries ROE and ROA but nothing on the capital actually
employed: ROE's denominator is book equity, which buybacks shrink (the persona
already says so), so a high ROE cannot tell capital efficiency from a shrunken
denominator. ROIC — operating profit after tax over debt-plus-equity-minus-
cash — is the check.

The rules pinned here:

**One fiscal year, stated.** The operating income anchor's `period_end` is the
year the tax rate and the balance-sheet legs must all match — a rate struck
across two years is two facts wearing one name, and interest_cost's measured
Microsoft case (a two-year-old numerator over a current balance sheet) is why
the balance-sheet legs resolve at the numerator's own period end, never at
`as_of`.

**The tax rate is the assumption, and the line says so.** It is the filed
effective rate — realised history, not a forecast and not a normalisation.
Outside the sanity band (a pre-tax loss, a net benefit, a >75% year) no NOPAT
is struck: the figure would be a distortion wearing a ratio's clothes.

**No WACC, anywhere.** The comparison that makes ROIC decision-relevant is
the reader's own; the line says "no WACC is sourced on this sheet" so no
agent quotes a hurdle as if the sheet supplied one.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.core.config import settings
from app.db import get_session
from app.db.models import EdgarFactRow
from app.schemas.agents import AgentId
from app.services import edgar_pit, edgar_tags, room_prompts, room_runner
from app.services.fundamentals import roic_line
from app.services.roic import fetch_roic, resolve_roic

_FY_START = date(2024, 9, 29)
_FY_END = date(2025, 9, 27)
_FILED = date(2025, 10, 31)
_AS_OF = date(2026, 3, 1)

# Clean numbers so every derived figure is checkable by eye:
# rate 20/100 = 20.0%; NOPAT 100 × 0.8 = 80; IC 50 + 70 − 20 = 100 → 80.0%.
_OP = 100.0e9
_TAX = 20.0e9
_PRETAX = 100.0e9
_DEBT = 50.0e9
_EQUITY = 70.0e9
_CASH = 20.0e9


def _facts(
    *, op=_OP, tax=_TAX, pretax=_PRETAX, debt=_DEBT, equity=_EQUITY, cash=_CASH,
    tax_end=_FY_END, pretax_end=_FY_END,
):
    def dur(tag, value, end):
        return edgar_pit._FactView(
            tag=tag, value=value, period_start=_FY_START, period_end=end,
            filed=_FILED,
        )

    def inst(tag, value):
        return edgar_pit._FactView(
            tag=tag, value=value, period_start=None, period_end=_FY_END,
            filed=_FILED,
        )

    return [
        dur(edgar_tags.OPERATING_INCOME[0], op, _FY_END),
        dur(edgar_tags.INCOME_TAX_EXPENSE[0], tax, tax_end),
        dur(edgar_tags.PRETAX_INCOME[0], pretax, pretax_end),
        inst(edgar_tags.DEBT_ANCHOR[0], debt),
        inst(edgar_tags.EQUITY[0], equity),
        inst(edgar_tags.CASH_ANCHOR[0], cash),
    ]


# ── The resolver ─────────────────────────────────────────────────────────


def test_the_happy_path_computes_every_leg() -> None:
    out = resolve_roic(_facts(), _AS_OF)
    assert out is not None
    assert out.tax_rate_pct == 20.0
    assert out.nopat == pytest.approx(80.0e9)
    assert out.invested_capital == pytest.approx(100.0e9)
    assert out.roic_pct == 80.0
    assert out.period_end == _FY_END


def test_tax_tags_from_a_different_year_resolve_nothing() -> None:
    """The rate's legs must describe the anchor's own fiscal year."""
    facts = _facts(tax_end=date(2024, 9, 28), pretax_end=date(2024, 9, 28))
    assert resolve_roic(facts, _AS_OF) is None


def test_a_pretax_loss_yields_no_rate() -> None:
    assert resolve_roic(_facts(pretax=-1.0e9), _AS_OF) is None


def test_a_net_tax_benefit_is_refused() -> None:
    """A negative 'rate' would inflate NOPAT above operating income."""
    assert resolve_roic(_facts(tax=-2.0e9), _AS_OF) is None


def test_an_implausible_rate_is_refused() -> None:
    assert resolve_roic(_facts(tax=90.0e9), _AS_OF) is None


def test_a_missing_balance_sheet_leg_resolves_nothing() -> None:
    facts = [f for f in _facts() if f.tag != edgar_tags.CASH_ANCHOR[0]]
    assert resolve_roic(facts, _AS_OF) is None
    facts = [f for f in _facts() if f.tag != edgar_tags.DEBT_ANCHOR[0]]
    assert resolve_roic(facts, _AS_OF) is None


def test_cash_exceeding_debt_plus_equity_is_absent_not_infinite() -> None:
    assert resolve_roic(_facts(cash=200.0e9), _AS_OF) is None


def test_a_stale_anchor_ages_out() -> None:
    assert resolve_roic(_facts(), date(2027, 6, 1)) is None


# ── The line ─────────────────────────────────────────────────────────────


def test_the_line_states_every_leg_and_the_no_wacc_note() -> None:
    line = roic_line(133050, 15.6, 112294, 118000, 95.2, "2025-09-27")
    assert "Return on invested capital (LIVE)" in line
    assert "NOPAT $112,294M (operating income $133,050M taxed at the filed effective rate 15.6%)" in line
    assert "invested capital $118,000M = ROIC 95.2%" in line
    assert "AMI's estimate" in line
    assert "no WACC is sourced on this sheet" in line


def test_any_missing_leg_withholds_the_line() -> None:
    assert roic_line(None, 15.6, 112294, 118000, 95.2, "2025-09-27") is None
    assert roic_line(133050, None, 112294, 118000, 95.2, "2025-09-27") is None
    assert roic_line(133050, 15.6, 112294, 118000, 95.2, None) is None


# ── The overlay (store-backed) ───────────────────────────────────────────

_DUR_TAGS = {
    edgar_tags.OPERATING_INCOME[0], edgar_tags.INCOME_TAX_EXPENSE[0],
    edgar_tags.PRETAX_INCOME[0],
}


@pytest.fixture
def seeded():
    with get_session() as s:
        s.query(EdgarFactRow).filter(EdgarFactRow.ticker == "ROICX").delete()
        for f in _facts():
            s.add(EdgarFactRow(
                cik=11, ticker="ROICX", taxonomy="us-gaap", tag=f.tag,
                unit="USD", value=f.value,
                period_start=f.period_start, period_end=f.period_end,
                filed=f.filed, accession_no=f"acc-{f.tag}",
                ingested_at=datetime(2025, 11, 1, tzinfo=UTC),
            ))
        s.commit()
    yield
    with get_session() as s:
        s.query(EdgarFactRow).filter(EdgarFactRow.ticker == "ROICX").delete()
        s.commit()


def test_fetch_roic_reads_the_store(seeded) -> None:
    out = fetch_roic("ROICX", _AS_OF)
    assert out is not None and out.roic_pct == 80.0


def test_the_overlay_converts_edgar_dollars_to_the_sheets_millions(seeded) -> None:
    profile: dict = {}
    field_state: dict[str, str] = {}
    room_runner._overlay_sbc_and_roic(profile, field_state, "ROICX", _AS_OF)
    assert field_state["roic"] == "live"
    assert profile["roic_operating_income"] == 100_000
    assert profile["roic_tax_rate_pct"] == 20.0
    assert profile["roic_nopat"] == 80_000
    assert profile["roic_invested_capital"] == 100_000
    assert profile["roic_pct"] == 80.0
    assert profile["roic_period_end"] == "2025-09-27"
    # No SBC tag seeded — SBC is absent on its OWN state, not ROIC's.
    assert field_state["sbc"] == "unavailable"


# ── The render seam ──────────────────────────────────────────────────────


def _profile() -> dict:
    return {
        "field_state": {"roic": "live"},
        "roic_operating_income": 133050,
        "roic_tax_rate_pct": 15.6,
        "roic_nopat": 112294,
        "roic_invested_capital": 118000,
        "roic_pct": 95.2,
        "roic_period_end": "2025-09-27",
    }


@pytest.fixture(autouse=True)
def _flag_restored():
    before = settings.room_roic_enabled
    yield
    settings.room_roic_enabled = before


def test_nothing_renders_with_the_flag_off() -> None:
    settings.room_roic_enabled = False
    assert "Return on invested capital" not in room_prompts._format_profile(
        _profile(), AgentId.FUNDAMENTALS_ANALYST)


def test_the_flag_is_on_by_default() -> None:
    """Flipped ON 2026-09-29 (CR247 Phase 1B — unit suite + the live AAPL
    render probe). The env var stays as the kill switch; the flag-off render
    is pinned above."""
    assert settings.room_roic_enabled is True


def test_the_line_appears_with_the_flag_on() -> None:
    settings.room_roic_enabled = True
    sheet = room_prompts._format_profile(_profile(), AgentId.FUNDAMENTALS_ANALYST)
    assert "Return on invested capital (LIVE)" in sheet
    assert "ROIC 95.2%" in sheet
    assert "no WACC is sourced on this sheet" in sheet


def test_presence_is_not_provenance() -> None:
    settings.room_roic_enabled = True
    profile = _profile()
    profile["field_state"] = {}
    assert "Return on invested capital" not in room_prompts._format_profile(
        profile, AgentId.FUNDAMENTALS_ANALYST)


def test_an_unavailable_block_never_renders_even_with_the_flag_on() -> None:
    settings.room_roic_enabled = True
    profile = _profile()
    profile["field_state"] = {"roic": "unavailable"}
    assert "Return on invested capital" not in room_prompts._format_profile(
        profile, AgentId.FUNDAMENTALS_ANALYST)
