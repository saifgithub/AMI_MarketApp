"""DEF269 — game fills leaked into every TRAINING read of `sim_trades`.

Reported by a tester on the shipped build: *"game trades are appearing in
portfolio open trades."*

`sim_trades` was a per-USER table before it was a per-portfolio one. CR109
slice 2 gave a user many portfolios (one training, one per game run) and
routed game fills through the same `_execute_fill`, so a game row lands in
`sim_trades` carrying the same `user_id` and a different `portfolio_id`.
Six readers still filtered on `user_id` alone, and each of them silently
widened from "this user's training trades" to "this user's trades
anywhere."

The display leak is the mild half. The severe one is `evaluate_outcomes`,
which selected those same rows and then sold them against the **training**
portfolio: a game position hitting its stop would liquidate shares the
training account had bought for its own reasons, credit the proceeds to
training cash, and leave the game position open. Nothing about that is
visible to the user until the shares are gone.

These tests are written against the OBSERVABLE guarantee — "the training
lane cannot see or act on a game fill" — rather than against the query
text, so a future refactor that re-widens the scope by some other route
fails here too.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.schemas.trade import Side
from app.services import market_data as _md
from app.services.coach_engine import hydrate_coach_mandate
from app.services.sim_engine import SimEngine


class _ConstProvider:
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


def _permissive_mandate():
    """Caps wide open — this file is about lane SCOPE, not about the floor,
    and a single-name-cap rejection here would look like a scoping bug."""
    return hydrate_coach_mandate({"plan": "trader", "single_name_cap_pct": 100.0})


def _training_buy(sim: SimEngine, user_id, ticker="AAPL", qty=5, **kw):
    result = sim.submit(
        user_id=user_id, ticker=ticker, side=Side.BUY, quantity=qty,
        mandate=_permissive_mandate(), **kw,
    )
    assert result.accepted, result.compliance.violations
    return result


def _game_buy(sim: SimEngine, user_id, run_id, ticker="AAPL", qty=10, **kw):
    result = sim.submit_game_trade(
        user_id=user_id, run_id=run_id, ticker=ticker,
        side=Side.BUY, quantity=qty, **kw,
    )
    assert result.accepted, result.reason
    return result


# ── The reported symptom ────────────────────────────────────────────────


def test_game_fill_does_not_appear_in_the_training_trade_list():
    """The tester's report, as an assertion."""
    sim = SimEngine(provider=_ConstProvider(100.0))
    user_id, run_id = uuid4(), uuid4()
    _game_buy(sim, user_id, run_id, ticker="AAPL", qty=10)

    assert sim.list_trades(user_id) == []


def test_training_fill_still_appears_in_the_training_trade_list():
    """The fix must not narrow the list to nothing — the other failure mode
    of a scope change, and the one a green suite would not otherwise show."""
    sim = SimEngine(provider=_ConstProvider(100.0))
    user_id = uuid4()
    _training_buy(sim, user_id, ticker="AAPL", qty=5)

    trades = sim.list_trades(user_id)
    assert [t.ticker for t in trades] == ["AAPL"]


def test_the_two_lanes_are_listed_separately_for_the_same_user():
    """One user, both lanes live at once — the state every tester is in."""
    sim = SimEngine(provider=_ConstProvider(100.0))
    user_id, run_id = uuid4(), uuid4()
    _training_buy(sim, user_id, ticker="MSFT", qty=5)
    _game_buy(sim, user_id, run_id, ticker="AAPL", qty=10)

    assert [t.ticker for t in sim.list_trades(user_id)] == ["MSFT"]
    # And the game portfolio still really holds what it bought — the scope
    # fix must not have suppressed the fill itself.
    game = sim.ensure_portfolio(user_id, kind="game", run_id=run_id)
    assert [h.ticker for h in game.holdings] == ["AAPL"]


# ── The severe half: cross-portfolio liquidation ────────────────────────


def test_a_game_stop_never_liquidates_the_training_portfolio():
    """The dangerous one. `evaluate_outcomes` selected open trades by user,
    then sold them against `_load_portfolio_row(user_id)` — which defaults
    to the TRAINING row. A game trade whose stop is hit would therefore sell
    shares out of the training account.

    Here the training account holds 5 MSFT it bought for its own reasons,
    and the game account holds 10 AAPL with a stop the price has blown
    through. Nothing about MSFT — or about the game position — may move.
    """
    sim = SimEngine(provider=_ConstProvider(100.0))
    user_id, run_id = uuid4(), uuid4()
    _training_buy(sim, user_id, ticker="MSFT", qty=5)
    _game_buy(sim, user_id, run_id, ticker="AAPL", qty=10, stop=99.0)

    training_before = sim.ensure_portfolio(user_id)
    game_before = sim.ensure_portfolio(user_id, kind="game", run_id=run_id)

    # The price collapses well through the game trade's stop.
    sim._provider = _ConstProvider(50.0)
    updates = sim.evaluate_outcomes(user_id)

    assert updates == [], "a game trade was evaluated on the training path"

    training_after = sim.ensure_portfolio(user_id)
    assert {h.ticker: h.quantity for h in training_after.holdings} == {
        h.ticker: h.quantity for h in training_before.holdings
    }
    assert training_after.current_cash == pytest.approx(training_before.current_cash)

    game_after = sim.ensure_portfolio(user_id, kind="game", run_id=run_id)
    assert {h.ticker: h.quantity for h in game_after.holdings} == {
        h.ticker: h.quantity for h in game_before.holdings
    }


def test_a_training_stop_still_fires():
    """The mutation guard for the test above: with the scope applied, a
    genuine TRAINING stop must still be found and acted on. Without this,
    scoping `evaluate_outcomes` to nothing at all would pass."""
    sim = SimEngine(provider=_ConstProvider(100.0))
    user_id = uuid4()
    _training_buy(sim, user_id, ticker="MSFT", qty=5, stop=99.0)

    sim._provider = _ConstProvider(50.0)
    updates = sim.evaluate_outcomes(user_id)

    assert [u.new_status for u in updates] == ["lost"]
    assert sim.ensure_portfolio(user_id).holdings == []


def test_manual_close_cannot_close_a_game_trade():
    """`manual_close` sells against the training row too. A game trade id
    reaching it is the same cross-portfolio sale by another door."""
    sim = SimEngine(provider=_ConstProvider(100.0))
    user_id, run_id = uuid4(), uuid4()
    fill = _game_buy(sim, user_id, run_id, ticker="AAPL", qty=10)

    assert sim.manual_close(user_id, fill.trade.id) is None

    game = sim.ensure_portfolio(user_id, kind="game", run_id=run_id)
    assert [h.ticker for h in game.holdings] == ["AAPL"]


# ── The quiet halves: cost basis and the safety floor ───────────────────


def test_holding_lots_do_not_mix_game_fills_into_a_training_cost_basis():
    """Same ticker in both lanes, bought at different prices. The training
    holding's FIFO lots must describe the training buy alone — a blended
    basis is a wrong average cost on a screen the user reads as fact."""
    sim = SimEngine(provider=_ConstProvider(100.0))
    user_id, run_id = uuid4(), uuid4()
    _training_buy(sim, user_id, ticker="AAPL", qty=4)

    sim._provider = _ConstProvider(200.0)
    _game_buy(sim, user_id, run_id, ticker="AAPL", qty=10)

    lots = sim.holding_lots(user_id, "AAPL")
    assert sum(lot.quantity for lot in lots) == pytest.approx(4)
    assert all(lot.entry_price == pytest.approx(100.0) for lot in lots)


def test_game_trades_do_not_consume_the_training_open_risk_budget():
    """`_risk_limit_context` reads the same list. Game fills counted toward
    the training account's open-risk cap and over-trading brake means
    playing the game can REFUSE a training trade — the safety floor firing
    on activity that never happened in the account it is protecting."""
    sim = SimEngine(provider=_ConstProvider(100.0))
    user_id, run_id = uuid4(), uuid4()

    for i in range(6):
        _game_buy(sim, user_id, run_id, ticker="AAPL", qty=1, stop=80.0)

    _last_loss, opened_at, open_risk_pct = sim.risk_limit_context(
        user_id, portfolio_value=10_000.0, quotes={"AAPL": 100.0},
    )
    assert opened_at == []
    assert open_risk_pct == pytest.approx(0.0)
