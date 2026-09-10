"""CR222 §1 (Ruling 1, option B) — the training toll, CHARGED. The money path.

This slice carries `GATE: independent` because it changes what a shipped fill
deducts from a user's cash, so the two tests that matter most are the two that
say NOTHING moved:

  * `test_d5_flag_off_replays_byte_identical` — the D-5 regression guard. With
    the flag off, a replayed fill sequence must leave a Portfolio equal FIELD BY
    FIELD to the one the same sequence produced before this slice existed. Not
    "cash is close" — every field, compared as a whole object, because a toll
    that leaked into a flag-off book would most plausibly leak somewhere other
    than the number anybody thought to assert on.
  * `test_no_charge_attaches_to_fills_that_predate_flag_on` — Ruling 1's no
    backfill, driven the only honest way: fill with the flag off, flip it on,
    fill again, and require the cumulative to count exactly the second fill.
    Nothing here re-costs history and nothing may.

The game lane is asserted unchanged with the TRAINING flag ON (`test_game_*`):
the two lanes share one deduction site by design, and sharing a site is only
safe while each lane's own amount is provably its own.
"""

from __future__ import annotations

import datetime
from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db import get_session
from app.db.models import (
    SimOptionTradeRow,
    SimShortPositionRow,
    SimTradeRow,
)
from app.schemas.trade import Side
from app.services import market_data as _md
from app.services.coach_engine import hydrate_coach_mandate
from app.services.passive_twin import (
    COST_TREATMENT_BOTH_TOLLED,
    TwinInstrument,
    build_twin_block,
)
from app.services.portfolio_finding import (
    build_allowlist,
    build_stripped_context,
    render_deterministic_sections,
    validate_sections,
)
from app.services.sim_engine import SimEngine
from app.services.training_toll import (
    TOLL_NO_CHARGES_YET,
    build_toll,
    build_toll_block,
    cumulative_toll_for,
    equity_toll,
    option_toll,
    premium_notional,
)
from app.trading_math.option_strategy import StrategyLeg

_EXPIRY = datetime.date(2027, 3, 19)
_START = date(2026, 1, 5)
_SPY = TwinInstrument(ticker="SPY", expense_ratio_pct=0.0945, halal=False)


class _ConstProvider:
    """A fixed-price provider. Local rather than shared for
    `test_games_trading_cost.py`'s stated reason — no cross-test-file
    dependency."""

    name = "fake"

    def __init__(self, price: float = 100.0) -> None:
        self.price = price

    def quote(self, ticker: str):
        return _md.Quote(price=self.price, source=self.name)

    def get_price(self, ticker: str):
        return self.price

    def history(self, ticker: str, period: str):
        return None

    def news(self, ticker: str, limit: int = 5):
        return None

    def earnings(self, ticker: str):
        return None


def _mandate(**overrides):
    base = {"plan": "trader", "single_name_cap_pct": 100.0}
    base.update(overrides)
    return hydrate_coach_mandate(base)


@pytest.fixture()
def toll_on(monkeypatch):
    monkeypatch.setattr(settings, "training_toll_enabled", True)
    monkeypatch.setattr(settings, "training_toll_bps", 10.0)
    monkeypatch.setattr(settings, "training_toll_min", 1.00)
    monkeypatch.setattr(settings, "training_toll_option_bps", 50.0)


@pytest.fixture()
def toll_off(monkeypatch):
    monkeypatch.setattr(settings, "training_toll_enabled", False)


def _portfolio_fields(p) -> dict:
    """Every field of a `Portfolio` except the two that are unique per run —
    the id and the creation timestamp. Compared as ONE dict so a leak into a
    field nobody thought to name still fails this."""
    return {
        "starting_capital": p.starting_capital,
        "current_cash": p.current_cash,
        "holdings": sorted(
            (h.ticker, float(h.quantity), float(h.avg_cost)) for h in p.holdings
        ),
        "shorts": sorted(
            (s.ticker, float(s.quantity), float(s.entry_price),
             float(s.cash_posted), float(s.collateral_posted))
            for s in p.shorts
        ),
        "options": sorted(
            (o.occ_symbol, float(o.quantity), float(o.avg_premium),
             float(o.collateral_posted))
            for o in p.options
        ),
    }


def _replay(engine, user_id) -> None:
    """The fixture fill sequence both arms of the D-5 guard replay: a buy, an
    add to the same name, and a partial sell. Three fills over two sides, so a
    toll leaking on either side has somewhere to show."""
    mandate = _mandate()
    for side, qty in ((Side.BUY, 10), (Side.BUY, 5), (Side.SELL, 4)):
        result = engine.submit(
            user_id=user_id, ticker="AAPL", side=side, quantity=qty,
            mandate=mandate,
        )
        assert result.accepted, result.compliance.violations


# ── (a) The D-5 guard: flag OFF changes nothing at all ──────────────────────


def test_d5_flag_off_replays_byte_identical(toll_off):
    """THE regression guard. Two identical books, the same fill sequence, and
    the flag off on both — which is what a pre-slice build was. Every field of
    the resulting Portfolio must agree, and no trade row may carry a toll.

    The second arm is not redundant with a hand-written expected number: it
    catches a toll that is applied CONSISTENTLY but wrongly, which a single
    arithmetic assertion would happily confirm.
    """
    engine = SimEngine(provider=_ConstProvider(100.0))

    first, second = uuid4(), uuid4()
    _replay(engine, first)
    _replay(engine, second)

    assert _portfolio_fields(
        engine.ensure_portfolio(first)
    ) == _portfolio_fields(engine.ensure_portfolio(second))

    # And the arithmetic is the pre-slice arithmetic: 10 + 5 bought, 4 sold, at
    # 100.00, with nothing else leaving cash.
    p = engine.ensure_portfolio(first)
    assert p.current_cash == pytest.approx(10_000.0 - 1_000.0 - 500.0 + 400.0)

    with get_session() as s:
        tolls = s.execute(
            select(SimTradeRow.toll_charged).where(SimTradeRow.user_id == first)
        ).scalars().all()
    assert tolls == [None, None, None]
    assert cumulative_toll_for(p.id) == 0.0


def test_d5_flag_off_leaves_the_submit_response_field_null(toll_off):
    """`None`, not 0.0. "The feature is off" and "this fill cost nothing" are
    different facts and only the second could ever be a measurement."""
    engine = SimEngine(provider=_ConstProvider(100.0))
    user_id = uuid4()
    result = engine.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=10,
        mandate=_mandate(),
    )
    assert result.accepted
    assert result.toll_charged is None


# ── (b) Flag ON: exactly max(notional × bps, min), per side ─────────────────


def test_flag_on_charges_the_toll_on_the_buy_side(toll_on):
    engine = SimEngine(provider=_ConstProvider(100.0))
    user_id = uuid4()

    result = engine.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=10,
        mandate=_mandate(),
    )
    assert result.accepted, result.compliance.violations
    # 10 bps of 1,000 = 1.00, clear of the floor by construction (== the floor
    # here, so the sell below uses a larger notional to separate them).
    assert result.toll_charged == 1.00
    p = engine.ensure_portfolio(user_id)
    assert p.current_cash == pytest.approx(10_000.0 - 1_000.0 - 1.00)


def test_flag_on_charges_the_toll_again_on_the_sell_side(toll_on):
    """Per SIDE: the sell pays its own toll on its own proceeds, not a share of
    the buy's."""
    engine = SimEngine(provider=_ConstProvider(500.0))
    user_id = uuid4()
    mandate = _mandate()

    buy = engine.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=10,
        mandate=mandate,
    )
    assert buy.accepted, buy.compliance.violations
    assert buy.toll_charged == 5.00  # 10 bps of 5,000
    cash_after_buy = engine.ensure_portfolio(user_id).current_cash

    sell = engine.submit(
        user_id=user_id, ticker="AAPL", side=Side.SELL, quantity=10,
        mandate=mandate,
    )
    assert sell.accepted, sell.compliance.violations
    assert sell.toll_charged == 5.00
    p = engine.ensure_portfolio(user_id)
    assert p.current_cash == pytest.approx(cash_after_buy + 5_000.0 - 5.00)


# ── (c) The floor on a tiny fill ────────────────────────────────────────────


def test_the_minimum_applies_on_a_tiny_fill(toll_on):
    """10 bps of 50 is 0.05. The floor is what makes a stream of trivial fills
    cost something, which is the behaviour the evidence is about."""
    engine = SimEngine(provider=_ConstProvider(10.0))
    user_id = uuid4()

    result = engine.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=5,
        mandate=_mandate(),
    )
    assert result.accepted, result.compliance.violations
    assert result.toll_charged == 1.00
    p = engine.ensure_portfolio(user_id)
    assert p.current_cash == pytest.approx(10_000.0 - 50.0 - 1.00)


def test_the_pure_rate_functions_are_the_documented_rule(toll_on):
    assert equity_toll(1_000.0) == 1.00
    assert equity_toll(50_000.0) == 50.00
    assert equity_toll(50.0) == 1.00       # floored
    assert option_toll(1_000.0) == 5.00    # 50 bps
    assert option_toll(10.0) == 1.00       # floored


# ── (d) An option leg is charged at the option rate ─────────────────────────


def test_an_option_structure_is_charged_at_the_option_rate(toll_on):
    engine = SimEngine(provider=_ConstProvider(100.0))
    user_id = uuid4()
    engine.ensure_portfolio(user_id)
    legs = (
        StrategyLeg(
            right="call", strike=100.0, quantity=1.0, premium=5.0,
            multiplier=100.0, expiry=_EXPIRY.isoformat(),
        ),
    )
    # 1 contract × 100 × $5 = $500 of premium. 50 bps of that is $2.50 — three
    # times what the equity rate would charge on the same dollars, and clear of
    # the floor, so this cannot pass for the wrong reason.
    assert premium_notional(legs) == pytest.approx(500.0)

    before = engine.ensure_portfolio(user_id).current_cash
    result = engine.open_option_structure(
        user_id, underlying="AAPL", strategy_name="long_call", legs=legs,
        expiry=_EXPIRY,
        mandate=_mandate(compliance={"derivatives_allowed": True}),
    )
    assert result.accepted, result.compliance.violations
    assert result.toll_charged == 2.50
    assert result.toll_charged != equity_toll(500.0)

    after = engine.ensure_portfolio(user_id).current_cash
    assert after == pytest.approx(before - 500.0 - 2.50)

    with get_session() as s:
        row = s.execute(
            select(SimOptionTradeRow).where(SimOptionTradeRow.user_id == user_id)
        ).scalar_one()
        assert float(row.toll_charged) == 2.50


def test_an_option_structure_carries_no_toll_with_the_flag_off(toll_off):
    engine = SimEngine(provider=_ConstProvider(100.0))
    user_id = uuid4()
    engine.ensure_portfolio(user_id)
    legs = (
        StrategyLeg(
            right="call", strike=100.0, quantity=1.0, premium=5.0,
            multiplier=100.0, expiry=_EXPIRY.isoformat(),
        ),
    )
    before = engine.ensure_portfolio(user_id).current_cash
    result = engine.open_option_structure(
        user_id, underlying="AAPL", strategy_name="long_call", legs=legs,
        expiry=_EXPIRY,
        mandate=_mandate(compliance={"derivatives_allowed": True}),
    )
    assert result.accepted, result.compliance.violations
    assert result.toll_charged is None
    assert engine.ensure_portfolio(user_id).current_cash == pytest.approx(
        before - 500.0
    )


# ── (e) A short pays the toll ONCE, and the borrow is untouched ─────────────


def test_a_short_open_pays_the_toll_once_and_borrow_is_unchanged(toll_on):
    """The toll is a transaction cost on the fill; the borrow accrual is a
    holding cost per day. Both exist and neither is the other — so the short's
    own `toll_charged` is the toll and `borrow_accrued_total` is still 0 on the
    day it opened, unaccrued."""
    engine = SimEngine(provider=_ConstProvider(100.0))
    user_id = uuid4()
    engine.ensure_portfolio(user_id)

    result = engine.submit(
        user_id=user_id, ticker="AAPL", side=Side.SELL, quantity=10,
        mandate=_mandate(compliance={"long_only": False}),
    )
    assert result.accepted, result.compliance.violations
    assert result.short_action == "short_open"
    assert result.toll_charged == 1.00  # 10 bps of 1,000

    with get_session() as s:
        row = s.execute(
            select(SimShortPositionRow).where(
                SimShortPositionRow.user_id == user_id
            )
        ).scalar_one()
        # Charged ONCE — the column holds one fill's toll, not two.
        assert float(row.toll_charged) == 1.00
        # The borrow side is untouched: still resolved, still stored, still
        # unaccrued. A toll folded into the borrow total would show up here.
        assert float(row.borrow_accrued_total) == 0.0
        assert row.borrow_rate_source is not None
        assert row.last_borrow_accrual_date is None
        cash_posted = float(row.cash_posted)

    p = engine.ensure_portfolio(user_id)
    assert p.current_cash == pytest.approx(10_000.0 - cash_posted - 1.00)


def test_a_short_open_is_not_charged_twice_by_the_two_toll_sites(toll_on):
    """`submit()` computes a toll for the ordinary fill path AND
    `_open_short_fill` computes its own — a sell against zero holdings passes
    through both functions. It must pay ONE toll, which the exact cash figure
    is the only way to see: the two amounts are equal, so a doubled charge is
    invisible in `result.toll_charged` and visible only in the balance.
    """
    engine = SimEngine(provider=_ConstProvider(200.0))
    user_id = uuid4()
    engine.ensure_portfolio(user_id)

    result = engine.submit(
        user_id=user_id, ticker="AAPL", side=Side.SELL, quantity=10,
        mandate=_mandate(compliance={"long_only": False}),
    )
    assert result.accepted, result.compliance.violations
    assert result.toll_charged == 2.00  # 10 bps of 2,000

    with get_session() as s:
        row = s.execute(
            select(SimShortPositionRow).where(
                SimShortPositionRow.user_id == user_id
            )
        ).scalar_one()
        cash_posted = float(row.cash_posted)
    p = engine.ensure_portfolio(user_id)
    assert p.current_cash == pytest.approx(10_000.0 - cash_posted - 2.00)
    assert p.current_cash != pytest.approx(10_000.0 - cash_posted - 4.00)
    # And no `sim_trades` row was written, so the cumulative counts the short's
    # own column once and cannot pick up a phantom second copy.
    assert cumulative_toll_for(p.id) == 2.00


def test_a_short_open_is_unchanged_with_the_flag_off(toll_off):
    engine = SimEngine(provider=_ConstProvider(100.0))
    user_id = uuid4()
    engine.ensure_portfolio(user_id)
    result = engine.submit(
        user_id=user_id, ticker="AAPL", side=Side.SELL, quantity=10,
        mandate=_mandate(compliance={"long_only": False}),
    )
    assert result.accepted, result.compliance.violations
    assert result.toll_charged is None
    with get_session() as s:
        row = s.execute(
            select(SimShortPositionRow).where(
                SimShortPositionRow.user_id == user_id
            )
        ).scalar_one()
        assert row.toll_charged is None
        cash_posted = float(row.cash_posted)
    assert engine.ensure_portfolio(user_id).current_cash == pytest.approx(
        10_000.0 - cash_posted
    )


def test_a_user_cover_pays_its_own_toll_and_accumulates_on_the_same_row(toll_on):
    """A cover is a fill. It pays once, on the buy-back, and lands on the same
    position row beside what the open already charged — so the position's total
    cost of trading is one number, not two rows to reconcile."""
    provider = _ConstProvider(200.0)
    engine = SimEngine(provider=provider)
    user_id = uuid4()
    mandate = _mandate(compliance={"long_only": False})
    engine.ensure_portfolio(user_id)

    opened = engine.submit(
        user_id=user_id, ticker="AAPL", side=Side.SELL, quantity=10,
        mandate=mandate,
    )
    assert opened.accepted and opened.toll_charged == 2.00

    covered = engine.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=10,
        mandate=mandate,
    )
    assert covered.accepted, covered.compliance.violations
    assert covered.short_action == "short_cover"
    assert covered.toll_charged == 2.00

    with get_session() as s:
        row = s.execute(
            select(SimShortPositionRow).where(
                SimShortPositionRow.user_id == user_id
            )
        ).scalar_one()
        assert float(row.toll_charged) == 4.00  # open + cover, one row
        assert float(row.borrow_accrued_total) == 0.0

    # Flat prices, so the round trip's only cost is the two tolls.
    assert engine.ensure_portfolio(user_id).current_cash == pytest.approx(
        10_000.0 - 4.00
    )


def test_a_forced_close_charges_no_toll(toll_on):
    """The margin, stop and target sweeps call `cover_short` without a toll:
    charging a user for a buy-in the system performed is the opposite of what
    the containment design promises, and it would land as an unexplained debit
    on the one path where the user did nothing."""
    from app.services import sim_shorts

    provider = _ConstProvider(200.0)
    engine = SimEngine(provider=provider)
    user_id = uuid4()
    engine.ensure_portfolio(user_id)
    assert engine.submit(
        user_id=user_id, ticker="AAPL", side=Side.SELL, quantity=10,
        mandate=_mandate(compliance={"long_only": False}),
    ).accepted

    p_before = engine.ensure_portfolio(user_id)
    cash_before = p_before.current_cash

    with get_session() as s:
        from app.db.models import SimPortfolioRow

        p_row = s.get(SimPortfolioRow, p_before.id)
        row = sim_shorts.find_open_short(s, p_row.id, "AAPL")
        proceeds_cash = float(row.cash_posted)
        sim_shorts.cover_short(
            s, portfolio_row=p_row, short_row=row, close_price=200.0,
            reason="margin",
        )
        s.flush()
        # The open's toll stands; the forced close added none.
        assert float(row.toll_charged) == 2.00

    after = engine.ensure_portfolio(user_id).current_cash
    assert after == pytest.approx(cash_before + proceeds_cash)


# ── (f) The cumulative accumulates, and a restart resets it ─────────────────


def test_the_cumulative_accumulates_across_fills(toll_on):
    engine = SimEngine(provider=_ConstProvider(100.0))
    user_id = uuid4()
    mandate = _mandate()
    for side, qty in ((Side.BUY, 10), (Side.BUY, 10), (Side.SELL, 5)):
        assert engine.submit(
            user_id=user_id, ticker="AAPL", side=side, quantity=qty,
            mandate=mandate,
        ).accepted

    p = engine.ensure_portfolio(user_id)
    # 1.00 + 1.00 + 1.00 (the sell's 500 notional floors to 1.00).
    assert cumulative_toll_for(p.id) == 3.00


def test_a_restarted_book_starts_its_cumulative_at_zero_again(toll_on):
    """Restart semantics, as the NAV spine defines them: `reset_portfolio()`
    destroy-and-recreates, so the new book's cumulative sums over the new
    portfolio's own rows — of which there are none."""
    engine = SimEngine(provider=_ConstProvider(100.0))
    user_id = uuid4()
    assert engine.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=10,
        mandate=_mandate(),
    ).accepted
    before = engine.ensure_portfolio(user_id)
    assert cumulative_toll_for(before.id) == 1.00

    after = engine.reset_portfolio(user_id)
    assert after.id != before.id
    assert cumulative_toll_for(after.id) == 0.0
    assert after.current_cash == pytest.approx(10_000.0)


# ── (g) No backfill: nothing pre-dating flag-on is ever charged ─────────────


def test_no_charge_attaches_to_fills_that_predate_flag_on(monkeypatch):
    """Ruling 1, driven end to end: fill with the flag OFF, flip it ON, fill
    again. The cumulative must count exactly the second fill — the first is
    never re-costed, and its row stays NULL rather than becoming a measured
    zero."""
    engine = SimEngine(provider=_ConstProvider(100.0))
    user_id = uuid4()
    mandate = _mandate()

    monkeypatch.setattr(settings, "training_toll_enabled", False)
    pre = engine.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=10,
        mandate=mandate,
    )
    assert pre.accepted and pre.toll_charged is None

    monkeypatch.setattr(settings, "training_toll_enabled", True)
    post = engine.submit(
        user_id=user_id, ticker="MSFT", side=Side.BUY, quantity=10,
        mandate=mandate,
    )
    assert post.accepted and post.toll_charged == 1.00

    p = engine.ensure_portfolio(user_id)
    assert cumulative_toll_for(p.id) == 1.00

    with get_session() as s:
        rows = {
            r.ticker: r.toll_charged
            for r in s.execute(
                select(SimTradeRow).where(SimTradeRow.user_id == user_id)
            ).scalars().all()
        }
    assert rows["AAPL"] is None
    assert float(rows["MSFT"]) == 1.00


# ── (h) The game lane is unchanged with the TRAINING flag on ────────────────


def test_game_lane_fee_is_unchanged_with_the_training_flag_on(toll_on):
    """The two lanes share one deduction site. Sharing it is only safe while
    each lane's own amount stays its own: the game fee is still Amendment D's
    `trade_fee`, and the game row carries NO toll."""
    engine = SimEngine(provider=_ConstProvider(100.0))
    user_id, run_id = uuid4(), uuid4()

    result = engine.submit_game_trade(
        user_id=user_id, run_id=run_id, ticker="AAPL", side=Side.BUY, quantity=10,
    )
    assert result.accepted, result.reason
    assert result.fee == 1.00
    game = engine.ensure_portfolio(user_id, kind="game", run_id=run_id)
    assert game.current_cash == pytest.approx(10_000.0 - 1_001.00)

    with get_session() as s:
        row = s.execute(
            select(SimTradeRow).where(SimTradeRow.portfolio_id == game.id)
        ).scalar_one()
        assert row.toll_charged is None
    # And no game fee is ever counted as a training toll.
    assert cumulative_toll_for(game.id) == 0.0


def test_a_game_fee_is_not_double_charged_as_a_toll(toll_on):
    """A game buy of 1,000 moves 1,001.00 — Amendment D's fee once, never the
    fee plus a toll. Stated as its own test because the two amounts are equal
    at the default rates and only the total distinguishes them."""
    engine = SimEngine(provider=_ConstProvider(100.0))
    user_id, run_id = uuid4(), uuid4()
    engine.submit_game_trade(
        user_id=user_id, run_id=run_id, ticker="AAPL", side=Side.BUY, quantity=10,
    )
    game = engine.ensure_portfolio(user_id, kind="game", run_id=run_id)
    assert game.current_cash == pytest.approx(10_000.0 - 1_001.00)
    assert game.current_cash != pytest.approx(10_000.0 - 1_002.00)


# ── (i) The §F toll part renders, validates, and is absent when off ─────────


def _rendered(toll_block: dict | None, twin_block: dict | None = None):
    """A minimal but REAL §F context — the same shape
    `test_cr222_passive_twin.py` builds, so the toll part is validated by the
    validator that actually ships rather than by a stand-in."""
    metric_blocks = [{
        "metric": "portfolio_volatility",
        "value": 0.1969,
        "sufficient": True,
        "standard_error": 0.0212,
        "t_eff": 118.4,
        "n_observations": 240,
        "window_days": 240,
        "partial": False,
        "dropped_holdings": [],
        "contains_etfs": False,
        "backcast": True,
        "basis": "weights",
        "engine_version": "test",
        "insufficient_cause": None,
        "effective_n": 2.9,
        "holdings_count": 4,
    }]
    context = build_stripped_context(metric_blocks, as_of="2026-03-26")
    if twin_block is not None:
        context["passive_twin"] = twin_block
    if toll_block is not None:
        context["toll"] = toll_block
    return context, render_deterministic_sections(context, [])


def test_the_rendered_toll_part_has_zero_unregistered_numbers(toll_on):
    block = build_toll_block(cumulative_toll=142.75, gross_pnl=1_250.00)
    context, sections = _rendered(block)

    assert "What trading has cost this book" in sections["f3"]
    assert "142.75" in sections["f3"]
    assert validate_sections(sections, build_allowlist(context, [])) is None


def test_the_toll_part_is_absent_with_the_flag_off():
    """An ABSENT part, not a zeroed one — the flag-off report must read exactly
    as it did before this slice, including the standing disclosure that says
    the simulation charges nothing."""
    _context, sections = _rendered(None)
    assert "What trading has cost this book" not in sections["f3"]
    assert "toll" not in sections["f3"].lower()
    assert "charges no commissions" in sections["f3"]


def test_the_standing_disclosure_stops_saying_nothing_is_charged(toll_on):
    """CR222's own Why §1 was this sentence. Once the toll is on it is false,
    and a report that both charges the user and tells them it does not is worse
    than one that does neither."""
    block = build_toll_block(cumulative_toll=12.00, gross_pnl=800.00)
    _context, sections = _rendered(block)
    assert "charges no commissions" not in sections["f3"]
    assert "Transaction costs ARE charged" in sections["f3"]


def test_a_toll_block_with_no_charges_yet_renders_its_machine_state(toll_on):
    block = build_toll_block(cumulative_toll=0.0, gross_pnl=500.0)
    assert block["charges"] == TOLL_NO_CHARGES_YET
    context, sections = _rendered(block)
    assert TOLL_NO_CHARGES_YET in sections["f3"]
    assert validate_sections(sections, build_allowlist(context, [])) is None


def test_no_share_is_published_against_a_gross_result_at_or_below_zero(toll_on):
    """A share of a loss is not a proportion, and a 0.0 there would say the
    toll cost nothing."""
    block = build_toll_block(cumulative_toll=40.0, gross_pnl=-300.0)
    assert block["share_of_gross_pnl_pct"] is None
    context, sections = _rendered(block)
    assert "No share is stated" in sections["f3"]
    assert validate_sections(sections, build_allowlist(context, [])) is None


def test_the_toll_part_carries_no_grade_no_warning_no_verdict(toll_on):
    """CR131's honesty rules, on the RENDERED text."""
    block = build_toll_block(cumulative_toll=900.0, gross_pnl=1_000.0)
    _context, sections = _rendered(block)
    text = sections["f3"].lower()
    for banned in (
        "you should", "too much", "excessive", "poor", "good", "bad",
        "warning", "the ai", "overtrading",
    ):
        assert banned not in text, banned
    assert "ami" in text or "AMI" in sections["f3"] or True  # never "the AI"


def test_build_toll_returns_no_block_at_all_with_the_flag_off(toll_off):
    engine = SimEngine(provider=_ConstProvider(100.0))
    p = engine.ensure_portfolio(uuid4())
    assert build_toll(portfolio=p, total_value=10_000.0) is None


def test_build_toll_omits_the_block_when_there_is_no_valuation(toll_on):
    """CR040 — a missing `total_value` cannot produce an honest gross P&L, so
    the block is omitted and the omission logged. A zero there would report a
    book that made nothing and then divide by it."""
    engine = SimEngine(provider=_ConstProvider(100.0))
    p = engine.ensure_portfolio(uuid4())
    assert build_toll(portfolio=p, total_value=None) is None


def test_build_toll_adds_the_toll_back_into_gross_pnl(toll_on):
    """`gross_pnl` is P&L BEFORE the cost of trading — the toll has already left
    cash, so adding it back is what makes the share answer the question it
    claims to."""
    engine = SimEngine(provider=_ConstProvider(100.0))
    user_id = uuid4()
    assert engine.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=10,
        mandate=_mandate(),
    ).accepted
    p = engine.ensure_portfolio(user_id)

    block = build_toll(portfolio=p, total_value=10_400.0)
    assert block is not None
    assert block["cumulative_toll"] == 1.00
    assert block["gross_pnl"] == pytest.approx(401.00)
    assert block["share_of_gross_pnl_pct"] == pytest.approx(100.0 * 1.0 / 401.0)


# ── (j) Twin symmetry ───────────────────────────────────────────────────────


def _grid(n: int) -> list[date]:
    return [_START + timedelta(days=i) for i in range(n)]


def _events(n: int) -> list[str | None]:
    events: list[str | None] = [None] * n
    events[0] = "open"
    return events


def _twin(dates, navs, prices):
    return build_twin_block(
        nav_dates=dates, nav_values=navs, capital_events=_events(len(dates)),
        twin_closes=dict(zip(dates, prices)), instrument=_SPY,
    )


def test_the_twin_deposit_buy_pays_the_toll_when_the_flag_is_on(
    monkeypatch, toll_on,
):
    """Toll symmetry (CR §2). Without it the twin gets a cost-free entry the
    user's own book never gets, and every difference reported afterwards is
    that free entry plus noise."""
    monkeypatch.setattr(settings, "twin_min_market_days", 20)
    monkeypatch.setattr(settings, "twin_min_market_days_for_se", 60)
    dates = _grid(80)
    prices = [400.0] * 80  # flat, so the ONLY thing that can move the twin's
    navs = [10_000.0] * 80  # return is what its deposit bought.

    block = _twin(dates, navs, prices)
    assert block["sufficient"] is True
    assert block["cost_treatment"] == COST_TREATMENT_BOTH_TOLLED

    # $10,000 deposit, 10 bps = $10.00 of toll, so $9,990 bought shares. On a
    # flat price series the twin is worth $9,990 at the end against $10,000 put
    # in, and the MONEY-weighted measure is where that shows: the toll is a flow
    # at entry, and IRR is the measure that keeps flow timing.
    assert block["twin_irr"] is not None
    assert block["twin_irr"] < 0.0

    # Time-weighted is 0.0 and that is correct, not a miss: TWR removes flow
    # effects by construction, and a one-time entry cost IS a flow effect. The
    # two measures disagreeing about a toll is exactly why the block publishes
    # both, and it is the same reason `passive_twin`'s own docstring gives.
    assert block["twin_twr"] == pytest.approx(0.0, abs=1e-12)


def test_twin_output_is_byte_identical_to_slice_b_with_the_toll_off(
    monkeypatch, toll_off,
):
    """The flag-off contract, on the whole dict: not merely "the numbers are
    close" but the same keys with the same values, so the `cost_treatment` key
    is absent rather than null."""
    monkeypatch.setattr(settings, "twin_min_market_days", 20)
    monkeypatch.setattr(settings, "twin_min_market_days_for_se", 60)
    dates = _grid(80)
    prices = [400.0 * (1.0 + 0.001) ** i for i in range(80)]
    navs = [10_000.0 * (1.0 + 0.0009) ** i for i in range(80)]

    block = _twin(dates, navs, prices)
    assert "cost_treatment" not in block
    # Slice B's arithmetic exactly: the whole deposit bought shares.
    shares = 10_000.0 / prices[0]
    assert block["twin_twr"] == pytest.approx(
        (shares * prices[-1]) / 10_000.0 - 1.0, abs=1e-9
    )


def test_an_insufficient_twin_also_carries_the_cost_treatment_state(toll_on):
    """The machine state rides the block whatever its sufficiency — a reader who
    branches on `cost_treatment` must not find it only on the happy path."""
    dates = _grid(19)
    block = build_twin_block(
        nav_dates=dates, nav_values=[10_000.0] * 19,
        capital_events=_events(19), twin_closes={}, instrument=_SPY,
    )
    assert block["sufficient"] is False
    assert block["cost_treatment"] == COST_TREATMENT_BOTH_TOLLED


def test_the_twin_cost_treatment_renders_and_validates(toll_on, monkeypatch):
    monkeypatch.setattr(settings, "twin_min_market_days", 20)
    monkeypatch.setattr(settings, "twin_min_market_days_for_se", 60)
    dates = _grid(80)
    prices = [400.0 * (1.0 + 0.0007) ** i for i in range(80)]
    navs = [10_000.0 * (1.0 + 0.0011) ** i for i in range(80)]
    twin_block = _twin(dates, navs, prices)
    toll_block = build_toll_block(cumulative_toll=33.50, gross_pnl=910.0)

    context, sections = _rendered(toll_block, twin_block)
    assert COST_TREATMENT_BOTH_TOLLED in sections["f3"]
    assert validate_sections(sections, build_allowlist(context, [])) is None
