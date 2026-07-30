"""DEF110 — a stop/target hit must close the position, not just label it.

`SimEngine.evaluate_outcomes` flipped a hit trade to `won`/`lost` and stamped
`realised_pnl`, but — unlike `manual_close` directly below it — never reduced
the holding or credited the proceeds. The shares stayed on the user's books
forever. Measured on live Alpha before the fix: one account showed 6 holdings
of which 5 were phantom, 97.5% of its displayed invested value.

That is not cosmetic. `sim_holdings` feeds `_build_room_sector_context` →
`allocate_by_sector` → `check_mandate_compliance`, where a sector breach is a
hard REJECT with `overridden_from_llm=True`. The measured account read
Technology 75.4% against a 40% cap when its real portfolio held no Technology
at all — so a Technology BUY was vetoed on a concentration made entirely of
shares the user did not own. A confident, mandate-shaped refusal derived from
stale state: the DEF059 class.

Why it shipped: `test_target_hit_flips_outcome_to_won` asserted
`isinstance(updates, list)` against a stochastic walk, which cannot fail.
These tests price deterministically and assert the *portfolio*, not the label.
"""

from __future__ import annotations

from uuid import uuid4

from app.schemas.trade import OrderType, Side
from app.services.coach_engine import hydrate_coach_mandate
from app.services.market_data import Quote
from app.services.sim_engine import SimEngine


class _FixedPrice:
    """Quotes one settable price for every ticker, so outcomes are decidable."""

    name = "fixed"

    def __init__(self, price: float) -> None:
        self.price = price

    def quote(self, ticker: str) -> Quote:
        return Quote(price=self.price, source="fixed")

    def get_price(self, ticker: str) -> float:
        return self.price


def _engine(price: float) -> tuple[SimEngine, _FixedPrice]:
    provider = _FixedPrice(price)
    return SimEngine(provider=provider), provider


def _mandate():
    return hydrate_coach_mandate({"plan": "trader", "single_name_cap_pct": 100.0})


def _buy(sim, user_id, ticker, qty, *, stop, target, verdict=None):
    result = sim.submit(
        user_id=user_id, ticker=ticker, side=Side.BUY, quantity=qty,
        mandate=_mandate(), order_type=OrderType.MARKET,
        stop=stop, target=target, horizon_days=30,
        verdict_ref=verdict if verdict is not None else uuid4(),
    )
    assert result.accepted, result.compliance.violations
    return result


def test_target_hit_removes_the_holding_and_credits_the_proceeds():
    sim, provider = _engine(100.0)
    user_id = uuid4()
    _buy(sim, user_id, "AAPL", 5, stop=90.0, target=110.0)

    p = sim.ensure_portfolio(user_id)
    assert p.current_cash == 9_500.0
    assert [(h.ticker, h.quantity) for h in p.holdings] == [("AAPL", 5)]

    provider.price = 110.0
    updates = sim.evaluate_outcomes(user_id)

    assert [u.new_status for u in updates] == ["won"]
    p = sim.ensure_portfolio(user_id)
    assert p.holdings == [], "DEF110: the won position is still on the books"
    assert p.current_cash == 10_050.0  # 9500 + 5 * 110


def test_stop_hit_removes_the_holding_and_credits_the_proceeds():
    sim, provider = _engine(100.0)
    user_id = uuid4()
    _buy(sim, user_id, "AAPL", 5, stop=90.0, target=110.0)

    provider.price = 90.0
    updates = sim.evaluate_outcomes(user_id)

    assert [u.new_status for u in updates] == ["lost"]
    p = sim.ensure_portfolio(user_id)
    assert p.holdings == [], "DEF110: the stopped-out position is still on the books"
    assert p.current_cash == 9_950.0  # 9500 + 5 * 90


def test_a_liquidated_position_leaves_the_sector_concentration_view():
    """The safety-floor consequence, asserted end to end.

    `check_mandate_compliance` reads holdings; a closed position that stays in
    them keeps voting on the user's sector concentration forever.
    """
    sim, provider = _engine(100.0)
    user_id = uuid4()
    _buy(sim, user_id, "NVDA", 5, stop=90.0, target=110.0)

    provider.price = 110.0
    sim.evaluate_outcomes(user_id)

    holdings = sim.ensure_portfolio(user_id).holdings
    assert not any(h.ticker == "NVDA" for h in holdings)
    assert sim.total_value(user_id) == 10_050.0  # all cash, nothing marked


def test_only_the_hit_trade_liquidates_partial_position_survives():
    """The live `abc5e232` case: 3 TSLA held, 2 genuinely open, 1 phantom."""
    sim, provider = _engine(100.0)
    user_id = uuid4()
    _buy(sim, user_id, "TSLA", 1, stop=90.0, target=110.0)   # hits at 110
    _buy(sim, user_id, "TSLA", 2, stop=50.0, target=900.0)   # stays open

    assert sim.ensure_portfolio(user_id).holdings[0].quantity == 3

    provider.price = 110.0
    updates = sim.evaluate_outcomes(user_id)

    assert [u.new_status for u in updates] == ["won"]
    p = sim.ensure_portfolio(user_id)
    assert [(h.ticker, h.quantity) for h in p.holdings] == [("TSLA", 2)], \
        "the untouched trade's shares must survive its sibling's close"
    assert p.current_cash == 9_810.0  # 9700 + 1 * 110


def test_two_trades_hitting_together_liquidate_the_whole_holding_once():
    sim, provider = _engine(100.0)
    user_id = uuid4()
    _buy(sim, user_id, "AAPL", 2, stop=90.0, target=110.0)
    _buy(sim, user_id, "AAPL", 3, stop=90.0, target=110.0)

    provider.price = 110.0
    updates = sim.evaluate_outcomes(user_id)

    assert sorted(u.new_status for u in updates) == ["won", "won"]
    p = sim.ensure_portfolio(user_id)
    assert p.holdings == []
    assert p.current_cash == 10_050.0  # 9500 + 5 * 110, credited exactly once


def test_a_second_pass_cannot_sell_the_position_again():
    sim, provider = _engine(100.0)
    user_id = uuid4()
    _buy(sim, user_id, "AAPL", 5, stop=90.0, target=110.0)

    provider.price = 110.0
    assert len(sim.evaluate_outcomes(user_id)) == 1
    cash_after_close = sim.ensure_portfolio(user_id).current_cash

    assert sim.evaluate_outcomes(user_id) == [], "a closed trade re-closed"
    p = sim.ensure_portfolio(user_id)
    assert p.current_cash == cash_after_close
    assert p.holdings == []


def test_a_trade_larger_than_its_holding_sells_only_what_is_there():
    """Guards `_apply_sell_row`'s clamp to the shares actually held.

    Buy 5, sell 2 outright, then the original buy stops out still carrying
    quantity 5 against a holding of 3. Unclamped it credits 5 shares of
    proceeds and drives the holding negative before deleting it.
    """
    sim, provider = _engine(100.0)
    user_id = uuid4()
    _buy(sim, user_id, "AAPL", 5, stop=90.0, target=110.0)
    sold = sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.SELL, quantity=2,
        mandate=_mandate(), order_type=OrderType.MARKET,
    )
    assert sold.accepted
    p = sim.ensure_portfolio(user_id)
    assert p.holdings[0].quantity == 3
    cash_before = p.current_cash  # 10000 - 500 + 200

    provider.price = 110.0
    sim.evaluate_outcomes(user_id)

    p = sim.ensure_portfolio(user_id)
    assert p.holdings == []
    assert p.current_cash == cash_before + 3 * 110.0, \
        "credited proceeds for 5 shares when only 3 were held"


def test_trades_outrunning_the_holding_never_credit_phantom_cash():
    """Guards `_apply_sell_row`'s already-deleted check.

    Two open buys of 5 against a holding of 5 — reachable when a sell order
    already drew the position down. The first close empties the holding; the
    second must find nothing to sell and credit nothing, or the user is paid
    for shares that do not exist.
    """
    sim, provider = _engine(100.0)
    user_id = uuid4()
    _buy(sim, user_id, "AAPL", 5, stop=90.0, target=110.0)
    _buy(sim, user_id, "AAPL", 5, stop=90.0, target=110.0)

    sold = sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.SELL, quantity=5,
        mandate=_mandate(), order_type=OrderType.MARKET,
    )
    assert sold.accepted
    p = sim.ensure_portfolio(user_id)
    assert p.holdings[0].quantity == 5   # 10 bought, 5 sold
    assert p.current_cash == 9_500.0     # 10000 - 1000 + 500
    cash_before = p.current_cash

    provider.price = 110.0
    updates = sim.evaluate_outcomes(user_id)

    assert sorted(u.new_status for u in updates) == ["won", "won"]
    p = sim.ensure_portfolio(user_id)
    assert p.holdings == []
    assert p.current_cash == cash_before + 5 * 110.0, \
        "cash credited for 10 shares when only 5 were held"
