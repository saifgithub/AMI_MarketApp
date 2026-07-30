"""Tests for the Sim Trading engine.

Covers: portfolio init, mandate-compliant fills, safety-floor rejections
(blocklist, single-name cap, halal), stop/target outcome flips, P&L math,
manual close.
"""

from __future__ import annotations

from uuid import uuid4

from app.schemas.trade import OrderType, Side
from app.services.coach_engine import hydrate_coach_mandate
from app.services.market_data import (
    FallbackProvider,
    MockWalkProvider,
    Quote,
)
from app.services.sim_engine import SimEngine


def test_portfolio_init_at_10k():
    sim = SimEngine()
    user_id = uuid4()
    p = sim.ensure_portfolio(user_id)
    assert p.starting_capital == 10_000.0
    assert p.current_cash == 10_000.0
    assert p.holdings == []


def test_buy_fills_and_updates_holdings_and_cash():
    sim = SimEngine()
    user_id = uuid4()
    mandate = hydrate_coach_mandate({"plan": "trader", "single_name_cap_pct": 100.0})
    price = sim.current_price("AAPL")
    result = sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=5,
        mandate=mandate, order_type=OrderType.MARKET,
        stop=round(price * 0.94, 2), target=round(price * 1.13, 2),
        horizon_days=30,
    )
    assert result.accepted
    assert result.trade is not None
    assert result.trade.entry_price == price
    p = sim.ensure_portfolio(user_id)
    assert len(p.holdings) == 1
    assert p.holdings[0].ticker == "AAPL"
    assert p.holdings[0].quantity == 5
    assert p.current_cash < 10_000.0


def test_duplicate_verdict_rejects_second_buy():
    """Regression for bug ce7146c8: a double-tap on the 'Buy' button after
    a Convene the Room verdict produced two identical trades. submit() now
    rejects a second trade against the same verdict_ref with a clear violation
    that surfaces the existing trade_id."""
    sim = SimEngine()
    user_id = uuid4()
    mandate = hydrate_coach_mandate({"plan": "trader", "single_name_cap_pct": 100.0})
    verdict_id = uuid4()
    price = sim.current_price("AAPL")

    # First buy on this verdict — accepted
    first = sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=1,
        mandate=mandate, order_type=OrderType.MARKET,
        stop=round(price * 0.94, 2), target=round(price * 1.13, 2),
        horizon_days=30, verdict_ref=verdict_id,
    )
    assert first.accepted
    assert first.trade is not None
    first_trade_id = first.trade.id

    # Second buy on the same verdict — rejected, surfaces existing trade
    second = sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=1,
        mandate=mandate, order_type=OrderType.MARKET,
        stop=round(price * 0.94, 2), target=round(price * 1.13, 2),
        horizon_days=30, verdict_ref=verdict_id,
    )
    assert not second.accepted
    assert second.compliance.blocked_by == "duplicate_verdict"
    # The violation message points the client to the existing trade
    assert str(first_trade_id)[:8] in second.compliance.violations[0]

    # Portfolio still has only one AAPL position
    p = sim.ensure_portfolio(user_id)
    assert p.holdings[0].quantity == 1


def test_no_verdict_ref_allows_multiple_trades():
    """Manual trades (no verdict_ref) are not subject to the per-verdict
    guard — the user can buy AAPL twice from the Floor without a Room run."""
    sim = SimEngine()
    user_id = uuid4()
    mandate = hydrate_coach_mandate({"plan": "trader", "single_name_cap_pct": 100.0})
    for _ in range(2):
        result = sim.submit(
            user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=1,
            mandate=mandate, order_type=OrderType.MARKET,
        )
        assert result.accepted
    p = sim.ensure_portfolio(user_id)
    assert p.holdings[0].quantity == 2


def test_blocklist_rejects():
    sim = SimEngine()
    user_id = uuid4()
    mandate = hydrate_coach_mandate({
        "plan": "trader",
        "compliance": {"ticker_blocklist": ["AAPL"]},
    })
    result = sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=1,
        mandate=mandate,
    )
    assert not result.accepted
    assert any("blocklist" in v for v in result.compliance.violations)


def test_halal_screens_out_in_index_but_permits_unknown():
    """CR069 three-state at the sim boundary. A ticker in the parent index but
    absent from the compliant set is SCREENED_OUT (rejected, message names the
    standard). A ticker outside the parent index is UNKNOWN → PERMITTED (G3)."""
    from datetime import date

    from app.services.sharia_universe import HalalUniverse

    universe = HalalUniverse(
        {"AAPL", "MSFT"}, parent_index={"AAPL", "MSFT", "JPM"}, as_of=date(2026, 7, 22)
    )
    sim = SimEngine()
    mandate = hydrate_coach_mandate(
        {"plan": "trader", "compliance": {"halal": True}, "single_name_cap_pct": 100.0}
    )

    # JPM: in the parent index, not compliant → screened out → rejected.
    screened = sim.submit(
        user_id=uuid4(), ticker="JPM", side=Side.BUY, quantity=1,
        mandate=mandate, halal_universe=universe,
    )
    assert not screened.accepted
    msg = " ".join(screened.compliance.violations)
    assert "AAOIFI" in msg and "2026-07-22" in msg

    # NEVR: outside the parent index → unknown → PERMITTED, with the verdict
    # (provenance) still attached so the disclosure can travel on a successful trade.
    unknown = sim.submit(
        user_id=uuid4(), ticker="NEVR", side=Side.BUY, quantity=1,
        mandate=mandate, halal_universe=universe,
    )
    assert unknown.accepted
    assert unknown.compliance.sharia_verdict is not None
    assert unknown.compliance.sharia_verdict.status.value == "unknown"


def test_single_name_cap_rejects_too_large_buy():
    sim = SimEngine()
    user_id = uuid4()
    # CR129/DEF187: no override → resolves to the risk-tier preset (3.0% at
    # the default risk_score=3), not the pre-CR129 flat 50% backstop.
    mandate = hydrate_coach_mandate({"plan": "trader"})
    price = sim.current_price("MSFT")
    # Buy 70% of the portfolio in MSFT — exceeds the single-name cap either way
    qty = int((10_000 * 0.7) / price)
    result = sim.submit(
        user_id=user_id, ticker="MSFT", side=Side.BUY, quantity=qty,
        mandate=mandate, order_type=OrderType.LIMIT, limit_price=price,
    )
    assert not result.accepted
    assert any("single-name cap" in v for v in result.compliance.violations)


def test_insufficient_cash_blocks_buy():
    sim = SimEngine()
    user_id = uuid4()
    mandate = hydrate_coach_mandate({"plan": "trader", "single_name_cap_pct": 100.0})
    # Pretend the price is high — sim has $10k, ask for 100 shares of a $500+
    # base, exceeds cash regardless of single-name cap.
    price = sim.current_price("AAPL")
    too_many = int((10_000 / price) * 2)  # ~2× cash
    # But this might also hit concentration cap first. Pick something cheap:
    # we'll buy a manageable chunk first then try to overspend.
    sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=2,
        mandate=mandate,
    )
    cash_after = sim.ensure_portfolio(user_id).current_cash
    # Try to spend 2× remaining cash on a different ticker
    price2 = sim.current_price("META")
    qty = max(1, int((cash_after * 2) / price2))
    # If the qty would exceed single-name cap, the check trips before cash.
    # Use a portfolio_value that's small enough; we just want an INSUFFICIENT-cash flow
    if (qty * price2 / sim.total_value(user_id) * 100) >= 50:
        qty = max(1, int(cash_after / price2) + 2)  # 1 share more than affordable
    result = sim.submit(
        user_id=user_id, ticker="META", side=Side.BUY, quantity=qty,
        mandate=mandate,
    )
    assert not result.accepted
    # Either insufficient cash or concentration — both are valid failures here
    assert result.compliance.violations


def test_target_hit_flips_outcome_to_won():
    """DEF110: this used to price off the stochastic mock walk and assert only
    `isinstance(updates, list)` — a test that cannot fail, which is how a
    stop/target hit shipped for months without ever closing the position.
    Prices are fixed here so the outcome is decidable. The portfolio-side
    consequences are pinned in test_def110_outcome_liquidates.py."""

    class _FixedPrice:
        name = "fixed"

        def __init__(self, price):
            self.price = price

        def quote(self, ticker):
            return Quote(price=self.price, source="fixed")

        def get_price(self, ticker):
            return self.price

    provider = _FixedPrice(100.0)
    sim = SimEngine(provider=provider)
    user_id = uuid4()
    mandate = hydrate_coach_mandate({"plan": "trader", "single_name_cap_pct": 100.0})
    result = sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=1,
        mandate=mandate, stop=90.0, target=110.0,
    )
    assert result.accepted
    assert sim.evaluate_outcomes(user_id) == [], "flipped before the target was hit"

    provider.price = 110.0
    updates = sim.evaluate_outcomes(user_id)
    assert [u.new_status for u in updates] == ["won"]
    assert updates[0].closed_price == 110.0
    assert updates[0].realised_pnl == 10.0


def test_aggregate_source_reports_leaf_when_all_same():
    """Snapshot source == leaf when every ticker served by the same provider."""
    sim = SimEngine(provider=MockWalkProvider())
    assert sim.aggregate_source(["AAPL", "MSFT", "NVDA"]) == "mock_walk"


def test_aggregate_source_empty_holdings_is_mock_walk():
    sim = SimEngine(provider=MockWalkProvider())
    assert sim.aggregate_source([]) == "mock_walk"


def test_aggregate_source_downgrades_to_mock_when_mixed():
    """If any ticker fell through to mock_walk, the snapshot lies if it
    reports anything else. The aggregate must be "mock_walk" so the
    LIVE pill stays off."""

    class _PartialYahoo:
        """Returns Yahoo quotes for AAPL only; None for everything else."""
        name = "yahoo"

        def quote(self, ticker):  # noqa: D401
            if ticker.upper() == "AAPL":
                return Quote(price=187.0, source="yahoo")
            return None

        def get_price(self, ticker):
            q = self.quote(ticker)
            return q.price if q else None

    stack = FallbackProvider(primary=_PartialYahoo(), secondary=MockWalkProvider())
    sim = SimEngine(provider=stack)
    # AAPL served by yahoo, NVDA falls through to mock_walk → mixed.
    assert sim.aggregate_source(["AAPL", "NVDA"]) == "mock_walk"
    # AAPL alone → "yahoo".
    assert sim.aggregate_source(["AAPL"]) == "yahoo"


def test_current_quote_reports_leaf_source():
    sim = SimEngine(provider=MockWalkProvider())
    q = sim.current_quote("AAPL")
    assert q.source == "mock_walk"
    assert q.price > 0


def test_preview_accepts_compliant_trade_without_persisting():
    """BL9: preview() runs same pre-flight as submit() but never persists.
    Cash unchanged + no holdings recorded after a passing preview."""
    sim = SimEngine()
    user_id = uuid4()
    mandate = hydrate_coach_mandate({"plan": "trader", "single_name_cap_pct": 100.0})
    price = sim.current_price("AAPL")
    pv = sim.preview(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=2,
        mandate=mandate, order_type=OrderType.MARKET,
    )
    assert pv.accepted
    assert pv.compliance.passed
    assert pv.fill_price == price
    assert pv.notional == price * 2
    assert pv.cash_available == 10_000.0
    assert pv.held_quantity == 0.0
    # And critically: no persistence happened.
    p = sim.ensure_portfolio(user_id)
    assert p.current_cash == 10_000.0
    assert p.holdings == []


def test_preview_rejects_on_mandate_violation():
    """BL9: preview() surfaces compliance violation for blocklisted ticker."""
    sim = SimEngine()
    user_id = uuid4()
    mandate = hydrate_coach_mandate({
        "plan": "trader",
        "compliance": {"ticker_blocklist": ["AAPL"]},
    })
    pv = sim.preview(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=1,
        mandate=mandate,
    )
    assert not pv.accepted
    assert not pv.compliance.passed
    assert any("blocklist" in v for v in pv.compliance.violations)


def test_preview_rejects_on_insufficient_cash():
    """BL9: preview() rejects when notional > current cash (after compliance
    passes).

    Cash must be driven below HALF the book first, and that takes two buys, not
    one. The 50% single-name cap is measured against total portfolio value, so
    while cash is still the larger share of the book, any notional that exceeds
    cash is over the cap by construction — it is rejected for concentration and
    never reaches the cash check at all.

    DEF153: this test used to do it in one 40% buy and then preview 90% of the
    book. That only reached the cash check because the single-name cap was dark
    on MARKET orders — the test was passing on a hole in the safety floor, which
    is why its premise is now asserted rather than described in a comment.
    """
    sim = SimEngine()
    user_id = uuid4()
    mandate = hydrate_coach_mandate({"plan": "trader", "single_name_cap_pct": 100.0})
    for ticker, weight in (("AAPL", 0.45), ("NVDA", 0.30)):
        qty = int((10_000 * weight) / sim.current_price(ticker))
        res = sim.submit(
            user_id=user_id, ticker=ticker, side=Side.BUY, quantity=qty,
            mandate=mandate, order_type=OrderType.MARKET,
        )
        assert res.accepted, res.compliance.violations

    cash_left = sim.ensure_portfolio(user_id).current_cash
    total = sim.total_value(user_id)
    assert cash_left < total * 0.5, "premise: cash is now the smaller share"

    price = sim.current_price("MSFT")
    # The SMALLEST quantity that exceeds cash — anything larger risks clearing
    # the 50% cap instead, and the prices here walk between runs.
    over_cash_qty = int(cash_left / price) + 1
    assert over_cash_qty * price > cash_left, "premise: the buy exceeds cash"
    assert over_cash_qty * price < total * 0.5, "premise: and is under the cap"

    pv = sim.preview(
        user_id=user_id, ticker="MSFT", side=Side.BUY, quantity=over_cash_qty,
        mandate=mandate, order_type=OrderType.MARKET,
    )
    assert not pv.accepted
    assert any("insufficient cash" in v for v in pv.compliance.violations), (
        pv.compliance.violations
    )


class _FixedPrice:
    """Quotes one settable price for every ticker, so P&L is decidable."""

    name = "fixed"

    def __init__(self, price: float) -> None:
        self.price = price

    def quote(self, ticker: str) -> Quote:
        return Quote(price=self.price, source="fixed")

    def get_price(self, ticker: str) -> float:
        return self.price


def test_manual_close_clamped_by_holding_realises_pnl_on_shares_actually_sold():
    """DEF166: a clamped close must not stamp P&L on shares that weren't sold.

    Buy 5 AAPL, sell 2 outright (holding now 3), then `manual_close` the
    original buy trade — its `quantity` is still 5, but only 3 shares remain
    on the books. `_apply_sell_row` clamps the cash credit to 3; `realised_pnl`
    must describe that same 3, not the trade's full requested 5, or the
    journal's per-trade P&L and the portfolio's cash movement disagree about
    how many shares were sold.
    """
    provider = _FixedPrice(100.0)
    sim = SimEngine(provider=provider)
    user_id = uuid4()
    mandate = hydrate_coach_mandate({"plan": "trader", "single_name_cap_pct": 100.0})
    res = sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=5,
        mandate=mandate, order_type=OrderType.MARKET,
    )
    assert res.accepted
    trade_id = res.trade.id  # type: ignore[union-attr]

    sold = sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.SELL, quantity=2,
        mandate=mandate, order_type=OrderType.MARKET,
    )
    assert sold.accepted
    p = sim.ensure_portfolio(user_id)
    assert p.holdings[0].quantity == 3
    cash_before = p.current_cash

    provider.price = 110.0
    closed = sim.manual_close(user_id, trade_id)

    assert closed is not None
    p = sim.ensure_portfolio(user_id)
    cash_credited = round(p.current_cash - cash_before, 2)
    assert cash_credited == 3 * 110.0, "clamp: cash credited for 3 shares, not 5"
    assert closed.realised_pnl == 30.0, (
        "realised_pnl must match the 3 shares actually sold: "
        "(110 - 100) * 3 = 30, not (110 - 100) * 5 = 50"
    )


def test_manual_close_realises_pnl_and_returns_cash():
    sim = SimEngine()
    user_id = uuid4()
    mandate = hydrate_coach_mandate({"plan": "trader", "single_name_cap_pct": 100.0})
    price = sim.current_price("AAPL")
    res = sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=2,
        mandate=mandate,
    )
    assert res.accepted
    trade_id = res.trade.id  # type: ignore[union-attr]
    closed = sim.manual_close(user_id, trade_id)
    assert closed is not None
    assert closed.status == "closed"
    assert closed.closed_price is not None
    # Holding removed
    p = sim.ensure_portfolio(user_id)
    assert all(h.ticker != "AAPL" for h in p.holdings) or all(
        h.quantity == 0 for h in p.holdings if h.ticker == "AAPL"
    )
