"""DEF549 — a Bursa Room's coded (non-LLM) lines never print "$".

Third currency-format defect on Bursa coded text (DEF531, DEF533, DEF549): the
Risk Officer's sizing line printed "$1,499 at risk" on a 1155.KL Room because
`risk_officer._rung_head` formatted through a `$`-hard-coded `_money`. The same
hard-coded `$` sat in the R:R geometry note, the direction-vs-price note, the
Trader repair note and the option-structure card.

Two guards, because the defect class is "a coded line forgot the market":

  1. `test_every_coded_line_builder_is_ringgit_on_a_bursa_room` renders every
     coded line builder with a Bursa market and asserts no "$" and an "RM".
  2. `test_no_dollar_fstring_interpolation_in_coded_room_modules` is a source
     scan: no f-string in the Room's coded-text modules may put a literal "$"
     directly before an interpolation. A new coded line that does so fails here
     before it can reach a Bursa user.

US output stays byte-identical (the CR282 golden covers the prompts; the US
assertions below cover the coded lines).
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.risk_officer import _rung_head, render_officer_turns
from app.services.room_prompts import _money, _render_option_candidates
from app.services.room_runner import (
    _annotate_direction_against_price,
    _annotate_rr_against_levels,
    _stop_clause,
    _verify_and_annotate_geometry,
)
from app.trading_math.markets import Market
from app.trading_math.option_ladder import build_option_ladder

_PV = 100_000.0  # an RM 100,000 Bursa book; the figure is the book's own value
_MY_PROFILE = {"market": Market.MY.value}


def _rows(portfolio_value: float | None = _PV):
    return build_option_ladder(
        reference_size_pct=50.0, entry=100.0, stop=94.0, target=113.0,
        cap_pts=50.0, current_drawdown_pct=0.0, portfolio_value=portfolio_value,
    )


# ── the reported line ────────────────────────────────────────────────────────


def test_rung_head_prints_ringgit_on_a_bursa_book():
    press = next(r for r in _rows() if r.label == "press")
    head = _rung_head(press, Market.MY)
    assert "RM" in head and "at risk" in head
    assert "$" not in head
    # the amount is the Bursa book's own value x the rung's drawdown share
    assert f"RM{press.dollar_risk:,.0f} at risk" in head


def test_rung_head_us_is_unchanged():
    press = next(r for r in _rows() if r.label == "press")
    assert f", ${press.dollar_risk:,.0f} at risk" in _rung_head(press)
    assert _rung_head(press) == _rung_head(press, Market.US)


def test_officer_turns_resolve_the_market_from_the_sheet_or_the_argument():
    rows = _rows()
    for kw in ({"profile": _MY_PROFILE}, {"market": Market.MY}):
        turns = render_officer_turns(
            None, rows, headline_max_chars=120, fallback_reason="the call failed", **kw,
        )
        assert all("$" not in t.text and "RM" in t.text for t in turns)
    us = render_officer_turns(
        None, rows, headline_max_chars=120, fallback_reason="the call failed",
    )
    assert all("$" in t.text and "RM" not in t.text for t in us)


# ── the guard: every coded line builder, rendered with a Bursa market ────────


def _option_candidate():
    metrics = SimpleNamespace(
        net_cost=-250.0, unbounded_loss=False, covered_by_shares=False,
        max_loss=1234.0, unbounded_gain=False, max_gain=2345.0,
        break_evens=[101.5], collateral_required=5000.0,
    )
    return SimpleNamespace(
        strategy_name="bull_call_spread", contracts=1, expiry="2026-12-18",
        days_to_expiry=21, metrics=metrics, legs=[], net_greeks=None,
        rationale="", mandate_violations=[], not_evaluated=[], advisories=[],
    )


_TEXT_WITH_LEVELS = "Entry 10.00, stop 9.40, target 11.30. R:R is 9:1."
_DIRECTION_TEXT = "Wait for the price to reclaim $9.00 before revisiting the name."


def _coded_lines(market: Market) -> dict[str, str]:
    sym = "RM" if market is Market.MY else "$"
    rows = _rows()
    out: dict[str, str] = {}
    out["risk_officer_rung_head"] = " | ".join(_rung_head(r, market) for r in rows)
    out["risk_officer_turns"] = "\n".join(
        t.text for t in render_officer_turns(
            None, rows, headline_max_chars=120, fallback_reason="the call failed",
            market=market,
        )
    )
    out["rr_geometry_note"] = _annotate_rr_against_levels(
        _TEXT_WITH_LEVELS, 10.0, 9.4, 11.3, 3.0, market=market,
    )[0]
    out["verify_and_annotate_geometry"] = _verify_and_annotate_geometry(
        _TEXT_WITH_LEVELS, size_pct=3.0, reference_close=10.0, market=market,
    )[0]
    out["direction_note"] = _annotate_direction_against_price(
        _DIRECTION_TEXT.replace("$", sym), 10.5, [("support", 9.0)], market,
    )[0]
    out["option_card"] = _render_option_candidates([_option_candidate()], 10.0, market)
    out["money"] = _money(1499.0, market) + _money(-80.0, market)
    out["stop_clause"] = _stop_clause("X", {"X": {9.4}}, {}, market)
    return out


def test_every_coded_line_builder_is_ringgit_on_a_bursa_room():
    for name, text in _coded_lines(Market.MY).items():
        # the direction note's INPUT carries the agent's own RM figure; the note
        # AMI appends must too
        assert "$" not in text, f"{name} printed a dollar sign on a Bursa Room: {text!r}"
        assert "RM" in text, f"{name} carried no ringgit amount: {text!r}"


def test_the_same_builders_stay_dollar_for_a_us_room():
    for name, text in _coded_lines(Market.US).items():
        assert "RM" not in text, f"{name} leaked RM into a US Room: {text!r}"
        assert "$" in text, f"{name} lost its dollar sign on a US Room: {text!r}"


# ── the source scan ──────────────────────────────────────────────────────────

_APP = Path(__file__).resolve().parents[2] / "app"
_CODED_ROOM_MODULES = (
    "services/risk_officer.py",
    "services/room_runner.py",
    "services/room_market.py",
    "services/room_rating.py",
    "services/room_decision_rule.py",
    "services/numeric_quotation.py",
    "agents/safety_floor.py",
    "services/output_guard.py",
)


def _dollar_fstrings(path: Path) -> list[int]:
    hits: list[int] = []
    for node in ast.walk(ast.parse(path.read_text())):
        if not isinstance(node, ast.JoinedStr):
            continue
        parts = node.values
        if any(
            isinstance(a, ast.Constant) and isinstance(a.value, str)
            and a.value.endswith("$") and isinstance(b, ast.FormattedValue)
            for a, b in zip(parts, parts[1:])
        ):
            hits.append(node.lineno)
    return hits


@pytest.mark.parametrize("module", _CODED_ROOM_MODULES)
def test_no_dollar_fstring_interpolation_in_coded_room_modules(module):
    """A coded line that interpolates after a literal "$" ignores the Room's
    market. Take the symbol from `spec_for(market).currency_symbol` (or
    `format_money`) instead. Prompt text in `room_prompts.py` is exempt: it is
    rewritten for the market by `localize_money` at its single exit."""
    assert _dollar_fstrings(_APP / module) == []
