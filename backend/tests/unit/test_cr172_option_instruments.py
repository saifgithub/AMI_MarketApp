"""CR172 §1 + §3 — OCC identity, the option tables, and the reset paths.

The §3 invariants pinned here are the ones the whole CR leans on:

* `sim_option_legs.quantity` is SIGNED and a short leg row coexists with
  `sim_holdings` untouched — the separate-table rule that keeps
  `def110_backfill`, `compute_lots_fifo` and the sector cap blind to
  options by construction.
* `reset_portfolio` and `clear()` delete option rows EXPLICITLY — sqlite
  does not enforce FK CASCADEs, so without the explicit deletes the unit
  suite would pass while Alpha leaked legs across resets (the CR136-M03
  lesson, fifth and sixth occurrence).
"""

from __future__ import annotations

import datetime
from uuid import uuid4

from app.db import get_session
from app.db.models import SimHoldingRow, SimOptionLegRow, SimOptionTradeRow
from app.services.option_instruments import (
    OCC_SYMBOL_LENGTH,
    format_occ_symbol,
    parse_occ_symbol,
)
from app.services.sim_engine import get_sim_engine


# ── OCC symbols ──────────────────────────────────────────────────────────


def test_occ_format_matches_the_spec_example():
    sym = format_occ_symbol("AAPL", datetime.date(2026, 1, 16), "call", 250.0)
    assert sym == "AAPL  260116C00250000"
    assert len(sym) == OCC_SYMBOL_LENGTH


def test_occ_round_trips_including_fractional_strikes():
    cases = [
        ("AAPL", datetime.date(2026, 1, 16), "call", 250.0),
        ("F", datetime.date(2027, 12, 3), "put", 32.5),
        ("GOOGL", datetime.date(2026, 6, 19), "put", 7.125),
        ("ABCDEF", datetime.date(2026, 3, 20), "call", 1000.0),
    ]
    for underlying, expiry, right, strike in cases:
        sym = format_occ_symbol(underlying, expiry, right, strike)
        assert sym is not None and len(sym) == OCC_SYMBOL_LENGTH
        parsed = parse_occ_symbol(sym)
        assert parsed is not None
        assert parsed.underlying == underlying
        assert parsed.expiry == expiry
        assert parsed.right == right
        assert parsed.strike == strike


def test_occ_format_rejects_what_it_cannot_encode():
    d = datetime.date(2026, 1, 16)
    assert format_occ_symbol("TOOLONGX", d, "call", 250.0) is None
    assert format_occ_symbol("BRK.B", d, "call", 250.0) is None
    assert format_occ_symbol("AAPL", d, "call", 0.0) is None
    assert format_occ_symbol("AAPL", d, "call", -5.0) is None
    assert format_occ_symbol("AAPL", d, "straddle", 250.0) is None
    assert format_occ_symbol("AAPL", datetime.date(1999, 1, 16), "call", 250.0) is None


def test_occ_parse_rejects_malformed_symbols():
    assert parse_occ_symbol("AAPL 260116C00250000") is None    # 20 chars
    assert parse_occ_symbol("AAPL  260116X00250000") is None   # bad right
    assert parse_occ_symbol("AAPL  260231C00250000") is None   # Feb 31
    assert parse_occ_symbol("AAPL  260116C00000000") is None   # zero strike
    assert parse_occ_symbol("aapl  260116C00250000") is None   # lowercase
    assert parse_occ_symbol("") is None
    assert parse_occ_symbol(None) is None
    assert parse_occ_symbol("AAPL  26011AC00250000") is None   # letter in date


def test_occ_parse_carries_the_underlying_as_its_own_field():
    # §1: the OCC symbol must never be routed through the ticker gates; the
    # underlying — a separate field, not a sliced prefix — is what passes.
    parsed = parse_occ_symbol("MSFT  261218P00400000")
    assert parsed.underlying == "MSFT"
    assert parsed.right == "put"
    assert parsed.strike == 400.0


# ── Tables: signed quantity, separate from sim_holdings ──────────────────


def _seed_option_rows(user_id, portfolio_id):
    strategy = uuid4()
    with get_session() as s:
        s.add(SimOptionLegRow(
            user_id=user_id, portfolio_id=portfolio_id,
            occ_symbol="AAPL  260918C00250000", underlying="AAPL",
            right="call", strike=250.0, expiry=datetime.date(2026, 9, 18),
            quantity=-2, avg_premium=3.1, multiplier=100,
            collateral_posted=0, strategy_id=strategy,
            strategy_name="covered_call",
        ))
        s.add(SimOptionTradeRow(
            user_id=user_id, portfolio_id=portfolio_id, strategy_id=strategy,
            underlying="AAPL", strategy_name="covered_call",
            net_cost_at_open=-620.0, collateral_posted=0,
        ))
    return strategy


def _count_option_rows():
    with get_session() as s:
        legs = s.query(SimOptionLegRow).count()
        trades = s.query(SimOptionTradeRow).count()
    return legs, trades


def test_a_short_leg_row_never_touches_sim_holdings():
    engine = get_sim_engine()
    user_id = uuid4()
    portfolio = engine.ensure_portfolio(user_id)
    _seed_option_rows(user_id, portfolio.id)
    with get_session() as s:
        leg = s.query(SimOptionLegRow).one()
        assert float(leg.quantity) == -2.0  # SIGNED, and legal HERE
        assert s.query(SimHoldingRow).count() == 0  # the separate-table rule


def test_reset_portfolio_deletes_option_rows_explicitly():
    engine = get_sim_engine()
    user_id = uuid4()
    portfolio = engine.ensure_portfolio(user_id)
    _seed_option_rows(user_id, portfolio.id)
    assert _count_option_rows() == (1, 1)
    engine.reset_portfolio(user_id)
    # sqlite does not enforce the FK CASCADE — only the explicit deletes
    # make this true in the suite, which is exactly what they exist for.
    assert _count_option_rows() == (0, 0)


def test_clear_deletes_option_rows():
    engine = get_sim_engine()
    user_id = uuid4()
    portfolio = engine.ensure_portfolio(user_id)
    _seed_option_rows(user_id, portfolio.id)
    engine.clear()
    assert _count_option_rows() == (0, 0)
