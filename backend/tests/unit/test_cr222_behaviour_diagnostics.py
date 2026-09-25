"""CR222 §4 — behaviour diagnostics for every training user.

Covers: the two honesty floors independently (thin closed-lot count, thin
elapsed time) each refusing with zero numeric fields; PGR/PLR on a
hand-built lot fixture matched against Odean's own definition computed by
hand in the comments below; attention-trade classification for both trigger
paths (a Room convene the day after, a >=10% move within the trading-day
lookback) and the negative case just outside each window; median holding
period on a hand-built fixture; annualised turnover on a hand-built fixture
(the same arithmetic `day_trader_outcomes.py` now calls through
`behaviour_diagnostics.turnover`); the §F `behaviour` block passing
`validate_sections` with zero unregistered numbers and being absent with the
flag off; and `day_trader_outcomes.py`'s own test file passing unchanged
(run alongside this file in the coder's gate, not duplicated here).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.core.config import settings
from app.db import get_session
from app.db.models import PriceHistoryDailyRow, RoomRunRow, SimPortfolioRow, SimTradeRow
from app.services.behaviour_diagnostics import (
    MIN_ELAPSED_DAYS,
    MIN_TRADES_FOR_DIAGNOSTICS,
    STATUS_READY,
    STATUS_TOO_EARLY,
    _NEW_BASELINES,
    build_behaviour_block,
    compute_behaviour_diagnostics,
    turnover,
)
from app.services.portfolio_health_constants import VALIDATOR_FIXED_PCT, VALIDATOR_FIXED_RAW
from app.services.portfolio_finding import (
    build_allowlist,
    build_stripped_context,
    render_deterministic_sections,
    validate_sections,
)

pytestmark = pytest.mark.allow_ledger_drift


# ── Fixture helpers ─────────────────────────────────────────────────────


def _make_portfolio(user_id: UUID, starting_capital: float = 10_000.0) -> UUID:
    portfolio_id = uuid4()
    with get_session() as s:
        s.add(SimPortfolioRow(
            id=portfolio_id,
            user_id=user_id,
            name="Main",
            starting_capital=starting_capital,
            current_cash=starting_capital,
        ))
    return portfolio_id


def _insert_trade(
    user_id: UUID,
    portfolio_id: UUID,
    *,
    ticker: str = "AAPL",
    side: str = "buy",
    quantity: float = 10.0,
    entry_price: float = 100.0,
    opened_at: datetime,
    status: str = "open",
    closed_at: datetime | None = None,
    closed_price: float | None = None,
    realised_pnl: float = 0.0,
) -> None:
    with get_session() as s:
        s.add(SimTradeRow(
            id=uuid4(),
            user_id=user_id,
            portfolio_id=portfolio_id,
            ticker=ticker,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            opened_at=opened_at,
            status=status,
            closed_at=closed_at,
            closed_price=closed_price,
            realised_pnl=realised_pnl,
        ))


def _seed_prices(ticker: str, prices: dict[date, float]) -> None:
    with get_session() as s:
        for d, px in sorted(prices.items()):
            s.add(PriceHistoryDailyRow(
                ticker=ticker, date=d, close=px, adj_close=px,
                source="yfinance", fetched_at=datetime.now(timezone.utc),
            ))


def _seed_convene(user_id: UUID, ticker: str, triggered_at: datetime) -> None:
    with get_session() as s:
        s.add(RoomRunRow(
            id=uuid4(), user_id=user_id, ticker=ticker, triggered_at=triggered_at,
            started_at=triggered_at, finished_at=triggered_at + timedelta(seconds=60),
            mandate_version=1, model_tier="standard",
            transcript=[], verdict=None, status="completed",
        ))


def _assert_no_numeric_figures(obj) -> None:
    if isinstance(obj, dict):
        for v in obj.values():
            _assert_no_numeric_figures(v)
    elif isinstance(obj, list):
        for v in obj:
            _assert_no_numeric_figures(v)
    elif isinstance(obj, bool):
        return
    elif isinstance(obj, (int, float)):
        raise AssertionError(f"numeric figure present in a refusal payload: {obj!r}")


@pytest.fixture(autouse=True)
def _diagnostics_thresholds(monkeypatch):
    monkeypatch.setattr(settings, "min_trades_for_diagnostics", MIN_TRADES_FOR_DIAGNOSTICS)
    monkeypatch.setattr(settings, "min_elapsed_days_for_diagnostics", MIN_ELAPSED_DAYS)


def _build_closed_lots(
    user_id: UUID, portfolio_id: UUID, *, n: int, start: datetime, win: bool = True,
) -> None:
    """`n` independent closed round trips, one day apart, each opened then
    self-closed (won/lost) exactly 3 calendar days later."""
    for i in range(n):
        opened = start + timedelta(days=i)
        closed = opened + timedelta(days=3)
        fill = 110.0 if win else 90.0
        _insert_trade(
            user_id, portfolio_id, ticker="AAPL", side="buy",
            quantity=10.0, entry_price=100.0, opened_at=opened,
            status="won" if win else "lost", closed_at=closed, closed_price=fill,
            realised_pnl=(fill - 100.0) * 10.0,
        )


# ── (a) 9 closed lots -> too_early, zero numeric fields ─────────────────


def test_nine_closed_lots_is_too_early_with_no_numeric_fields():
    user_id = uuid4()
    portfolio_id = _make_portfolio(user_id)
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    start = now - timedelta(days=200)
    _build_closed_lots(user_id, portfolio_id, n=9, start=start)

    result = compute_behaviour_diagnostics(user_id, now=now)
    assert result["status"] == STATUS_TOO_EARLY
    assert set(result.keys()) == {"status", "message"}
    _assert_no_numeric_figures(result)


# ── (b) 10+ closed lots but <60 elapsed days -> too_early ────────────────


def test_ten_closed_lots_under_sixty_elapsed_days_is_too_early():
    user_id = uuid4()
    portfolio_id = _make_portfolio(user_id)
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    # First trade only 10 days before `now` — comfortably under the 60-day
    # floor even though there are 10 closed lots.
    start = now - timedelta(days=10)
    _build_closed_lots(user_id, portfolio_id, n=10, start=start - timedelta(days=3))

    result = compute_behaviour_diagnostics(user_id, now=now)
    assert result["status"] == STATUS_TOO_EARLY
    assert set(result.keys()) == {"status", "message"}
    _assert_no_numeric_figures(result)


def test_no_trades_at_all_is_too_early():
    result = compute_behaviour_diagnostics(uuid4())
    assert result["status"] == STATUS_TOO_EARLY
    _assert_no_numeric_figures(result)


# ── (f) annualised turnover, hand-built fixture ──────────────────────────


def test_annualised_turnover_hand_built_fixture():
    """starting_capital = $10,000, window = 10 days.
    5 BUY @ 10 x $100 = $5,000 notional; 5 SELL @ 10 x $100 = $5,000 notional.
    avg_side_notional = (5000+5000)/2 = $5,000
    turnover_pct = 5000/10000*100 = 50.0%
    annualise = 365.25/10 = 36.525
    turnover_pct_annualised = 50.0 * 36.525 = 1826.25
    """
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    trades = []

    class _T:
        def __init__(self, side, qty, price):
            self.side = side
            self.quantity = qty
            self.entry_price = price

    for _ in range(5):
        trades.append(_T("buy", 10.0, 100.0))
    for _ in range(5):
        trades.append(_T("sell", 10.0, 100.0))

    result = turnover(trades, window_days=10.0, starting_capital=10_000.0)
    assert result.turnover_pct == 50.0
    assert result.turnover_pct_annualised == pytest.approx(50.0 * 36.525, rel=1e-6)


def test_turnover_pct_and_annualised_on_the_full_fixture():
    user_id = uuid4()
    portfolio_id = _make_portfolio(user_id, starting_capital=10_000.0)
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    start = now - timedelta(days=100)
    _build_closed_lots(user_id, portfolio_id, n=MIN_TRADES_FOR_DIAGNOSTICS, start=start)

    result = compute_behaviour_diagnostics(user_id, now=now)
    assert result["status"] == STATUS_READY
    # 10 buys @ 10 x $100 = $1,000 notional each -> buy_notional = $10,000.
    # No explicit sells (self-closed buys), so sell_notional = 0.
    # avg_side_notional = (10000 + 0) / 2 = $5,000
    # window_days = now - first_trade_at = 100 days
    # turnover_pct = 5000 / 10000 * 100 = 50.0
    assert result["turnover_pct"] == pytest.approx(50.0, abs=0.05)
    # `window_days` in the payload is itself rounded to 2dp, so recomputing
    # the annualisation multiplier from it (rather than from the exact
    # elapsed-seconds figure `compute_behaviour_diagnostics` actually used)
    # only agrees with the stored `turnover_pct_annualised` to the rounding
    # tolerance of a double-rounded figure, not to 1e-6.
    annualise = 365.25 / result["window_days"]
    assert result["turnover_pct_annualised"] == pytest.approx(
        result["turnover_pct"] * annualise, abs=0.05,
    )


# ── (e) median holding period, hand-built fixture ────────────────────────


def test_median_holding_period_hand_built_fixture():
    """Three closed lots on AAPL with holding periods 1, 3, 5 calendar days —
    median = 3.0. A fourth lot on a different ticker held 100 days is
    included in the pool (pooled across tickers, per the module docstring),
    making the sorted set [1, 3, 5, 100] -> median (3+5)/2 = 4.0."""
    user_id = uuid4()
    portfolio_id = _make_portfolio(user_id)
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    base = now - timedelta(days=200)

    for i, hold_days in enumerate([1, 3, 5]):
        opened = base + timedelta(days=i * 20)
        closed = opened + timedelta(days=hold_days)
        _insert_trade(
            user_id, portfolio_id, ticker="AAPL", side="buy",
            quantity=1.0, entry_price=100.0, opened_at=opened,
            status="won", closed_at=closed, closed_price=110.0, realised_pnl=10.0,
        )
    opened = base + timedelta(days=60)
    closed = opened + timedelta(days=100)
    _insert_trade(
        user_id, portfolio_id, ticker="MSFT", side="buy",
        quantity=1.0, entry_price=200.0, opened_at=opened,
        status="lost", closed_at=closed, closed_price=190.0, realised_pnl=-10.0,
    )
    # Pad to clear the trade-count floor without disturbing the four lots
    # already built (extra same-day round trips on a third ticker).
    for i in range(6):
        opened = base + timedelta(days=150 + i)
        closed = opened + timedelta(days=2)
        _insert_trade(
            user_id, portfolio_id, ticker="GOOG", side="buy",
            quantity=1.0, entry_price=50.0, opened_at=opened,
            status="won", closed_at=closed, closed_price=51.0, realised_pnl=1.0,
        )

    result = compute_behaviour_diagnostics(user_id, now=now)
    assert result["status"] == STATUS_READY
    holds = sorted([1, 3, 5, 100] + [2] * 6)
    mid = len(holds) // 2
    expected_median = (
        holds[mid] if len(holds) % 2 else (holds[mid - 1] + holds[mid]) / 2.0
    )
    assert result["median_holding_period_days"] == pytest.approx(expected_median, abs=0.01)


# ── (d) attention-trade classification ────────────────────────────────────


def test_buy_one_day_after_convene_is_attention_triggered():
    user_id = uuid4()
    portfolio_id = _make_portfolio(user_id)
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    convened_at = datetime(2026, 1, 10, tzinfo=timezone.utc)
    buy_at = convened_at + timedelta(days=1)

    _seed_convene(user_id, "AAPL", convened_at)
    # Flat price history so the move-based path never fires for this ticker —
    # isolates the convene trigger.
    days = [date(2026, 1, 1) + timedelta(days=i) for i in range(40)]
    _seed_prices("AAPL", {d: 100.0 for d in days})

    _insert_trade(
        user_id, portfolio_id, ticker="AAPL", side="buy",
        quantity=1.0, entry_price=100.0, opened_at=buy_at,
        status="won", closed_at=buy_at + timedelta(days=1),
        closed_price=101.0, realised_pnl=1.0,
    )
    # Pad with clearly NON-attention closed lots (no convene, no move) so the
    # denominator has enough trades to clear the honesty floor without
    # diluting the assertion below to an unreadable fraction.
    _build_closed_lots(
        user_id, portfolio_id, n=MIN_TRADES_FOR_DIAGNOSTICS - 1,
        start=now - timedelta(days=250), win=True,
    )

    result = compute_behaviour_diagnostics(user_id, now=now)
    assert result["status"] == STATUS_READY
    # 1 attention-triggered buy out of (1 + 9 padding) = 10 buys = 10%.
    assert result["attention_trade_share_pct"] == pytest.approx(10.0, abs=0.01)


def test_buy_six_trading_days_after_a_ten_percent_move_is_not_triggered():
    user_id = uuid4()
    portfolio_id = _make_portfolio(user_id)
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)

    # A >=10% move on day 0, then flat prices for the rest of the window.
    days = [date(2026, 1, 1) + timedelta(days=i) for i in range(60)]
    prices = {days[0]: 100.0, days[1]: 111.0}
    for d in days[2:]:
        prices[d] = 111.0
    _seed_prices("NVDA", prices)

    # The buy lands 6 TRADING-DAY ROWS after the move's own row (row index
    # 1 -> buy at row index 7): outside the 5-trading-day lookback.
    buy_at = datetime.combine(days[7], datetime.min.time(), tzinfo=timezone.utc)
    _insert_trade(
        user_id, portfolio_id, ticker="NVDA", side="buy",
        quantity=1.0, entry_price=111.0, opened_at=buy_at,
        status="won", closed_at=buy_at + timedelta(days=1),
        closed_price=112.0, realised_pnl=1.0,
    )
    _build_closed_lots(
        user_id, portfolio_id, n=MIN_TRADES_FOR_DIAGNOSTICS - 1,
        start=now - timedelta(days=250), win=True,
    )

    result = compute_behaviour_diagnostics(user_id, now=now)
    assert result["status"] == STATUS_READY
    assert result["attention_trade_share_pct"] == 0.0


def test_buy_within_five_trading_days_of_a_ten_percent_move_is_triggered():
    user_id = uuid4()
    portfolio_id = _make_portfolio(user_id)
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)

    days = [date(2026, 1, 1) + timedelta(days=i) for i in range(60)]
    prices = {days[0]: 100.0, days[1]: 111.0}
    for d in days[2:]:
        prices[d] = 111.0
    _seed_prices("TSLA", prices)

    # Buy 3 trading-day-rows after the move — inside the 5-row lookback.
    buy_at = datetime.combine(days[4], datetime.min.time(), tzinfo=timezone.utc)
    _insert_trade(
        user_id, portfolio_id, ticker="TSLA", side="buy",
        quantity=1.0, entry_price=111.0, opened_at=buy_at,
        status="won", closed_at=buy_at + timedelta(days=1),
        closed_price=112.0, realised_pnl=1.0,
    )
    _build_closed_lots(
        user_id, portfolio_id, n=MIN_TRADES_FOR_DIAGNOSTICS - 1,
        start=now - timedelta(days=250), win=True,
    )

    result = compute_behaviour_diagnostics(user_id, now=now)
    assert result["status"] == STATUS_READY
    assert result["attention_trade_share_pct"] == pytest.approx(10.0, abs=0.01)


# ── (c) PGR/PLR — hand-built fixtures, Odean's tally computed by hand ────
#
# Odean 1998 p.1781, the rule every docstring below applies by hand: on each
# day a sale takes place in a portfolio holding two or more stocks at the
# start of that day, each stock sold is ONE realised gain/loss (selling price
# vs its average purchase price) and each stock held at the start of the day
# and not sold that day is ONE paper gain/loss (that day's price vs its
# average purchase price). Nothing else is counted.


def _pad_unmeasured_closed_lots(
    user_id: UUID, portfolio_id: UUID, *, n: int, before: datetime,
) -> None:
    """`n` back-to-back closed losing round trips on one unpriced ticker, all
    over well before `before`. Each closes on a day when only that one stock
    was held, so Odean's two-stock rule counts none of them — they exist only
    to lift `closed_lot_count` to the honesty floor without touching PGR/PLR."""
    for i in range(n):
        opened = before - timedelta(days=40) + timedelta(days=2 * i)
        _insert_trade(
            user_id, portfolio_id, ticker="PAD", side="buy",
            quantity=1.0, entry_price=50.0, opened_at=opened,
            status="lost", closed_at=opened + timedelta(days=1),
            closed_price=49.0, realised_pnl=-1.0,
        )


def _flat_prices(ticker: str, start: date, days: int, overrides: dict[date, float]) -> None:
    prices = {start + timedelta(days=i): 100.0 for i in range(days)}
    prices.update(overrides)
    _seed_prices(ticker, prices)


def test_disposition_ratio_hand_built_fixture_matches_odean_by_hand():
    """Odean's tally, by hand, sale day by sale day.

    Day 0: buy 10 AAA @ $100, buy 10 BBB @ $100 (both at 00:00 UTC).
    Day 10: AAA self-closes (won) at $120.
      Held at the start of day 10: {AAA, BBB} — 2 stocks, so the day counts.
      AAA sold: $120 vs average purchase price $100 -> 1 realised GAIN.
      BBB held, not sold: day-10 close $90 vs $100 -> 1 paper LOSS.
    Day 20: BBB self-closes (lost) at $80.
      Held at the start of day 20: {BBB} — 1 stock. Odean counts NOTHING.
    Days 101..108: eight CCC round trips, one at a time.
      Held at the start of each: {CCC} — 1 stock. Nothing counted.

      realised_gains_count  = 1   paper_gains_count  = 0
      realised_losses_count = 0   paper_losses_count = 1
      PGR = 1 / (1 + 0) = 1.0
      PLR = 0 / (0 + 1) = 0.0

    (Round 2's lot-per-event tally read 9 realised gains and PLR 0.5 here:
    it counted day 20's lone BBB sale and every CCC close.)
    """
    user_id = uuid4()
    portfolio_id = _make_portfolio(user_id)
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    day0 = now - timedelta(days=200)
    day10 = day0 + timedelta(days=10)
    day20 = day0 + timedelta(days=20)

    _flat_prices("AAA", day0.date(), 25, {day10.date(): 120.0})
    _flat_prices("BBB", day0.date(), 25, {day10.date(): 90.0, day20.date(): 80.0})

    _insert_trade(
        user_id, portfolio_id, ticker="AAA", side="buy",
        quantity=10.0, entry_price=100.0, opened_at=day0,
        status="won", closed_at=day10, closed_price=120.0, realised_pnl=200.0,
    )
    _insert_trade(
        user_id, portfolio_id, ticker="BBB", side="buy",
        quantity=10.0, entry_price=100.0, opened_at=day0,
        status="lost", closed_at=day20, closed_price=80.0, realised_pnl=-200.0,
    )
    for i in range(8):
        opened = day0 + timedelta(days=100 + i)
        _insert_trade(
            user_id, portfolio_id, ticker="CCC", side="buy",
            quantity=1.0, entry_price=50.0, opened_at=opened,
            status="won", closed_at=opened + timedelta(days=1),
            closed_price=51.0, realised_pnl=1.0,
        )

    result = compute_behaviour_diagnostics(user_id, now=now)
    assert result["status"] == STATUS_READY
    disposition = result["disposition"]
    assert disposition["realised_gains_count"] == 1
    assert disposition["paper_gains_count"] == 0
    assert disposition["realised_losses_count"] == 0
    assert disposition["paper_losses_count"] == 1
    assert disposition["unpriced_positions_excluded"] == 0
    assert disposition["pgr"] == pytest.approx(1.0, abs=1e-4)
    assert disposition["plr"] == pytest.approx(0.0, abs=1e-4)


def test_disposition_ratio_uses_count_basis_not_dollar_basis():
    """One $900 realised gain beside nine $10 paper gains.

    Day 10: BIG (10 sh @ $100) self-closes at $190 -> $900 realised gain.
    SM0..SM8 (1 sh @ $100 each) are held, not sold, day-10 close $110 each
    -> nine paper gains of $10 = $90 in total.
      Held at the start of day 10: BIG + 9 SM = 10 stocks, so the day counts.
      Count basis (Odean): PGR = 1 / (1 + 9) = 0.10
      Dollar basis (wrong): 900 / (900 + 90) = 0.909
    PAD's losing closes land on days when only PAD was held (1 stock), so
    Odean counts none of them: no loss is measured and PLR is None — not
    the 1.0 a per-close tally would print.
    """
    user_id = uuid4()
    portfolio_id = _make_portfolio(user_id)
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    day0 = now - timedelta(days=200)
    day10 = day0 + timedelta(days=10)

    _flat_prices("BIG", day0.date(), 15, {day10.date(): 190.0})
    small_tickers = [f"SM{i}" for i in range(9)]
    for tk in small_tickers:
        _flat_prices(tk, day0.date(), 15, {day10.date(): 110.0})

    _insert_trade(
        user_id, portfolio_id, ticker="BIG", side="buy",
        quantity=10.0, entry_price=100.0, opened_at=day0,
        status="won", closed_at=day10, closed_price=190.0, realised_pnl=900.0,
    )
    for tk in small_tickers:
        _insert_trade(
            user_id, portfolio_id, ticker=tk, side="buy",
            quantity=1.0, entry_price=100.0, opened_at=day0, status="open",
        )
    _pad_unmeasured_closed_lots(user_id, portfolio_id, n=9, before=day0)

    result = compute_behaviour_diagnostics(user_id, now=now)
    assert result["status"] == STATUS_READY
    disposition = result["disposition"]
    assert disposition["realised_gains_count"] == 1
    assert disposition["paper_gains_count"] == 9
    assert disposition["pgr"] == pytest.approx(0.10, abs=1e-4)
    assert disposition["realised_losses_count"] == 0
    assert disposition["paper_losses_count"] == 0
    assert disposition["plr"] is None


def test_disposition_p1_dca_built_holding_is_one_paper_gain_not_four():
    """Audit probe P1. AAA (1 buy) is sold at a gain; BBB was built in four
    buys (DCA) and is held at a gain.

    Day 20: AAA self-closes at $120 vs average $100 -> 1 realised gain.
    BBB lots @ $100/$102/$104/$106, average $103; day-20 close $115 -> ONE
    paper gain (one stock, however many lots).
      Held at the start of day 20: {AAA, BBB} — 2 stocks.
      PGR = 1 / (1 + 1) = 0.5   (per-lot tally: 1 / (1 + 4) = 0.2)
      PLR: no loss anywhere measured -> None.
    """
    user_id = uuid4()
    portfolio_id = _make_portfolio(user_id)
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    day0 = now - timedelta(days=200)
    sale = day0 + timedelta(days=20)
    _flat_prices("AAA", day0.date(), 25, {})
    _flat_prices("BBB", day0.date(), 25, {sale.date(): 115.0})

    _insert_trade(
        user_id, portfolio_id, ticker="AAA", side="buy",
        quantity=1.0, entry_price=100.0, opened_at=day0,
        status="won", closed_at=sale, closed_price=120.0, realised_pnl=20.0,
    )
    for i, px in enumerate([100.0, 102.0, 104.0, 106.0]):
        _insert_trade(
            user_id, portfolio_id, ticker="BBB", side="buy",
            quantity=1.0, entry_price=px, opened_at=day0 + timedelta(days=3 * i),
            status="open",
        )
    _pad_unmeasured_closed_lots(user_id, portfolio_id, n=9, before=day0)

    disposition = compute_behaviour_diagnostics(user_id, now=now)["disposition"]
    assert disposition["realised_gains_count"] == 1
    assert disposition["paper_gains_count"] == 1
    assert disposition["pgr"] == pytest.approx(0.5, abs=1e-4)
    assert disposition["plr"] is None


def test_disposition_p2_two_winners_closed_the_same_day_are_not_each_others_paper():
    """Audit probe P2. AAA, BBB, CCC each 1 sh @ $100, held since day 0.

    Sale day: AAA closes at $110 (10:00), BBB at $115 (15:00). CCC is held,
    not sold, close $108.
      Held at the start of the sale day: {AAA, BBB, CCC} — 3 stocks.
      Realised gains: AAA, BBB = 2. Paper gains: CCC = 1 (BBB was sold that
      day, so it is never AAA's paper gain).
      PGR = 2 / (2 + 1) = 0.667   (per-event tally: 2 / (2 + 3) = 0.4)
    """
    user_id = uuid4()
    portfolio_id = _make_portfolio(user_id)
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    day0 = now - timedelta(days=200)
    sale = day0 + timedelta(days=20)
    # AAA/BBB closes on the sale day sit above cost too, so a tally that
    # also counted a sold stock as paper would read 2 / (2 + 3) = 0.4.
    _flat_prices("AAA", day0.date(), 25, {sale.date(): 110.0})
    _flat_prices("BBB", day0.date(), 25, {sale.date(): 115.0})
    _flat_prices("CCC", day0.date(), 25, {sale.date(): 108.0})

    for tk, hour, px in (("AAA", 10, 110.0), ("BBB", 15, 115.0)):
        _insert_trade(
            user_id, portfolio_id, ticker=tk, side="buy",
            quantity=1.0, entry_price=100.0, opened_at=day0,
            status="won", closed_at=sale + timedelta(hours=hour),
            closed_price=px, realised_pnl=px - 100.0,
        )
    _insert_trade(
        user_id, portfolio_id, ticker="CCC", side="buy",
        quantity=1.0, entry_price=100.0, opened_at=day0, status="open",
    )
    _pad_unmeasured_closed_lots(user_id, portfolio_id, n=9, before=day0)

    disposition = compute_behaviour_diagnostics(user_id, now=now)["disposition"]
    assert disposition["realised_gains_count"] == 2
    assert disposition["paper_gains_count"] == 1
    assert disposition["pgr"] == pytest.approx(0.6667, abs=1e-4)


def test_disposition_p3_partial_sell_leaves_no_paper_remainder():
    """Audit probe P3. AAA 10 sh @ $100 and BBB 1 sh @ $100, held since day 0.

    Sale day: an explicit sell of 5 AAA @ $120. BBB held, not sold, close $110.
      Held at the start of the sale day: {AAA, BBB} — 2 stocks.
      Realised gains: AAA = 1. Paper gains: BBB = 1. AAA's unsold 5 shares
      are NOT a paper gain — AAA was sold that day.
      PGR = 1 / (1 + 1) = 0.5   (remainder-as-paper tally: 1 / (1 + 2) = 0.333)
    """
    user_id = uuid4()
    portfolio_id = _make_portfolio(user_id)
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    day0 = now - timedelta(days=200)
    sale = day0 + timedelta(days=20, hours=14)
    _flat_prices("AAA", day0.date(), 25, {sale.date(): 120.0})
    _flat_prices("BBB", day0.date(), 25, {sale.date(): 110.0})

    _insert_trade(
        user_id, portfolio_id, ticker="AAA", side="buy",
        quantity=10.0, entry_price=100.0, opened_at=day0, status="open",
    )
    _insert_trade(
        user_id, portfolio_id, ticker="BBB", side="buy",
        quantity=1.0, entry_price=100.0, opened_at=day0, status="open",
    )
    _insert_trade(
        user_id, portfolio_id, ticker="AAA", side="sell",
        quantity=5.0, entry_price=120.0, opened_at=sale, status="closed",
    )
    _pad_unmeasured_closed_lots(user_id, portfolio_id, n=9, before=day0)

    disposition = compute_behaviour_diagnostics(user_id, now=now)["disposition"]
    assert disposition["realised_gains_count"] == 1
    assert disposition["paper_gains_count"] == 1
    assert disposition["pgr"] == pytest.approx(0.5, abs=1e-4)


def _one_position_at_a_time(user_id: UUID, portfolio_id: UUID, day0: datetime) -> None:
    """Ten priced tickers held strictly one at a time, 6 wins then 4 losses.
    T_i closes at 15:00 on the same day T_(i+1) opens at 16:00, so at the
    START of every sale day exactly one stock is held."""
    for i in range(10):
        tk = f"T{i}"
        _flat_prices(tk, day0.date(), 120, {})
        opened = day0 + timedelta(days=10 * i, hours=16)
        closed = day0 + timedelta(days=10 * (i + 1), hours=15)
        win = i < 6
        fill = 110.0 if win else 90.0
        _insert_trade(
            user_id, portfolio_id, ticker=tk, side="buy",
            quantity=1.0, entry_price=100.0, opened_at=opened,
            status="won" if win else "lost", closed_at=closed,
            closed_price=fill, realised_pnl=fill - 100.0,
        )


def test_disposition_p4_one_position_at_a_time_is_not_measured():
    """Audit probe P4. No sale day ever starts with two or more stocks held,
    so Odean counts nothing: every count 0, PGR and PLR None. Not the
    algebraically forced 100% / 100% a per-close tally prints."""
    user_id = uuid4()
    portfolio_id = _make_portfolio(user_id)
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    _one_position_at_a_time(user_id, portfolio_id, now - timedelta(days=200))

    result = compute_behaviour_diagnostics(user_id, now=now)
    assert result["status"] == STATUS_READY
    disposition = result["disposition"]
    assert disposition == {
        "pgr": None, "plr": None,
        "realised_gains_count": 0, "paper_gains_count": 0,
        "realised_losses_count": 0, "paper_losses_count": 0,
        "unpriced_positions_excluded": 0,
    }


def test_disposition_p4_renders_not_measured_never_one_hundred_percent():
    """Audit probe P5: P4 through the real renderer and validator."""
    user_id = uuid4()
    portfolio_id = _make_portfolio(user_id)
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    _one_position_at_a_time(user_id, portfolio_id, now - timedelta(days=200))

    context = _metric_context()
    context["behaviour"] = compute_behaviour_diagnostics(user_id, now=now)
    rules = _rules_empty()
    sections = render_deterministic_sections(context, rules)
    assert "Disposition ratio: not measured this run" in sections["f3"]
    assert "100.0%" not in sections["f3"]
    assert "of their available gains" not in sections["f3"]
    assert validate_sections(sections, build_allowlist(context, rules)) is None


def test_disposition_classifies_against_average_purchase_price_not_the_lot():
    """Odean scores a stock against its AVERAGE purchase price.

    XXX: lot 1 @ $90 (held), lot 2 @ $130 self-closes at $120 on the sale day.
      Lot 2's own P&L is -$10 (a per-lot LOSS); the position's average
      purchase price just before the sale is (90 + 130) / 2 = $110, and
      $120 > $110 -> 1 realised GAIN.
    YYY: lot 1 @ $130, lot 2 @ $90, both held; sale-day close $115.
      Average $110, $115 > $110 -> 1 paper GAIN (first-lot basis $130 would
      call it a loss).
      Held at the start of the sale day: {XXX, YYY} — 2 stocks.
      PGR = 1 / (1 + 1) = 0.5, PLR None.
    """
    user_id = uuid4()
    portfolio_id = _make_portfolio(user_id)
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    day0 = now - timedelta(days=200)
    sale = day0 + timedelta(days=20, hours=14)
    _flat_prices("XXX", day0.date(), 25, {})
    _flat_prices("YYY", day0.date(), 25, {sale.date(): 115.0})

    _insert_trade(
        user_id, portfolio_id, ticker="XXX", side="buy",
        quantity=1.0, entry_price=90.0, opened_at=day0, status="open",
    )
    _insert_trade(
        user_id, portfolio_id, ticker="XXX", side="buy",
        quantity=1.0, entry_price=130.0, opened_at=day0 + timedelta(hours=1),
        status="lost", closed_at=sale, closed_price=120.0, realised_pnl=-10.0,
    )
    _insert_trade(
        user_id, portfolio_id, ticker="YYY", side="buy",
        quantity=1.0, entry_price=130.0, opened_at=day0, status="open",
    )
    _insert_trade(
        user_id, portfolio_id, ticker="YYY", side="buy",
        quantity=1.0, entry_price=90.0, opened_at=day0 + timedelta(hours=1),
        status="open",
    )
    _pad_unmeasured_closed_lots(user_id, portfolio_id, n=9, before=day0)

    disposition = compute_behaviour_diagnostics(user_id, now=now)["disposition"]
    assert disposition["realised_gains_count"] == 1
    assert disposition["realised_losses_count"] == 0
    assert disposition["paper_gains_count"] == 1
    assert disposition["paper_losses_count"] == 0
    assert disposition["pgr"] == pytest.approx(0.5, abs=1e-4)
    assert disposition["plr"] is None


def test_disposition_one_stock_sold_across_several_lots_is_one_realised_event():
    """AAA bought in three 10-share lots @ $100, then ONE sell of all 30
    shares @ $110 on the sale day (three FIFO lot closes). BBB 1 sh @ $100,
    held, sale-day close $95.
      Held at the start of the sale day: {AAA, BBB} — 2 stocks.
      Realised gains: AAA = 1 (one stock, not three lots).
      Paper losses: BBB = 1.
      PGR = 1 / (1 + 0) = 1.0, PLR = 0 / (0 + 1) = 0.0
    """
    user_id = uuid4()
    portfolio_id = _make_portfolio(user_id)
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    day0 = now - timedelta(days=200)
    sale = day0 + timedelta(days=20, hours=14)
    _flat_prices("AAA", day0.date(), 25, {})
    _flat_prices("BBB", day0.date(), 25, {sale.date(): 95.0})

    for i in range(3):
        _insert_trade(
            user_id, portfolio_id, ticker="AAA", side="buy",
            quantity=10.0, entry_price=100.0, opened_at=day0 + timedelta(days=i),
            status="open",
        )
    _insert_trade(
        user_id, portfolio_id, ticker="BBB", side="buy",
        quantity=1.0, entry_price=100.0, opened_at=day0, status="open",
    )
    _insert_trade(
        user_id, portfolio_id, ticker="AAA", side="sell",
        quantity=30.0, entry_price=110.0, opened_at=sale, status="closed",
    )
    _pad_unmeasured_closed_lots(user_id, portfolio_id, n=9, before=day0)

    disposition = compute_behaviour_diagnostics(user_id, now=now)["disposition"]
    assert disposition["realised_gains_count"] == 1
    assert disposition["paper_losses_count"] == 1
    assert disposition["pgr"] == pytest.approx(1.0, abs=1e-4)
    assert disposition["plr"] == pytest.approx(0.0, abs=1e-4)


def test_disposition_pgr_is_none_with_no_gain_and_an_unpriced_holding_is_named():
    """No gain anywhere: PGR's denominator is empty, so PGR is None — never
    a silent 0.0 (CR040). A held stock with no stored price is a NAMED
    exclusion, not a zero.

    LLL 1 sh @ $100 self-closes at $90 on the sale day -> 1 realised loss.
    MMM 1 sh @ $100 held, sale-day close $80 -> 1 paper loss.
    UNP 1 sh @ $100 held, no price on record -> excluded, counted once.
      Held at the start of the sale day: {LLL, MMM, UNP} — 3 stocks.
      PGR = None (0 + 0), PLR = 1 / (1 + 1) = 0.5
    """
    user_id = uuid4()
    portfolio_id = _make_portfolio(user_id)
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    day0 = now - timedelta(days=200)
    sale = day0 + timedelta(days=20, hours=14)
    _flat_prices("LLL", day0.date(), 25, {})
    _flat_prices("MMM", day0.date(), 25, {sale.date(): 80.0})

    _insert_trade(
        user_id, portfolio_id, ticker="LLL", side="buy",
        quantity=1.0, entry_price=100.0, opened_at=day0,
        status="lost", closed_at=sale, closed_price=90.0, realised_pnl=-10.0,
    )
    for tk in ("MMM", "UNP"):
        _insert_trade(
            user_id, portfolio_id, ticker=tk, side="buy",
            quantity=1.0, entry_price=100.0, opened_at=day0, status="open",
        )
    _pad_unmeasured_closed_lots(user_id, portfolio_id, n=9, before=day0)

    disposition = compute_behaviour_diagnostics(user_id, now=now)["disposition"]
    assert disposition["realised_losses_count"] == 1
    assert disposition["paper_losses_count"] == 1
    assert disposition["unpriced_positions_excluded"] == 1
    assert disposition["pgr"] is None
    assert disposition["plr"] == pytest.approx(0.5, abs=1e-4)


def test_disposition_ratio_is_not_measured_on_a_single_ticker_book():
    """Ten back-to-back AAPL round trips: every sale day starts with at most
    one stock held, so Odean counts nothing and both ratios are None."""
    user_id = uuid4()
    portfolio_id = _make_portfolio(user_id)
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    start = now - timedelta(days=200)
    _build_closed_lots(user_id, portfolio_id, n=MIN_TRADES_FOR_DIAGNOSTICS, start=start, win=True)

    result = compute_behaviour_diagnostics(user_id, now=now)
    assert result["status"] == STATUS_READY
    disposition = result["disposition"]
    assert disposition["pgr"] is None
    assert disposition["plr"] is None


# ── (g) §F `behaviour` block: allow-list validator + flag gating ─────────


def _metric_context():
    return build_stripped_context(
        [{
            "metric": "portfolio_volatility",
            "sufficient": True,
            "value": 0.184,
            "window_days": 126,
            "t_eff": 90.0,
            "n_observations": 126,
        }],
        as_of="2026-06-01",
    )


def _rules_empty():
    return []


def _ready_behaviour_block_no_fixed_literals() -> dict:
    """A `ready`-shape behaviour block where no numeric field, raw or ×100,
    equals a token in `VALIDATOR_FIXED_RAW`/`VALIDATOR_FIXED_PCT` or another
    field's rendered value (pinned by
    `test_ready_fixture_numbers_collide_with_no_fixed_literal`). The old
    fixture's `realised_gains_count = 5` passed only because "5" is
    registered for the attention sentence's fixed prose; a coincidence like
    that hides an unregistered field. The baselines are the shipped
    `_NEW_BASELINES` values, so the test tracks what users actually read."""
    return {
        "status": STATUS_READY,
        "first_trade_at": "2026-01-01T00:00:00+00:00",
        "window_days": 147.0,
        "closed_lot_count": 23,
        "turnover_pct": 68.4,
        "turnover_pct_annualised": 169.7,
        "median_holding_period_days": 7.8,
        "attention_trade_share_pct": 24.6,
        "disposition": {
            "pgr": 0.63, "plr": 0.34,
            "realised_gains_count": 17, "paper_gains_count": 14,
            "realised_losses_count": 9, "paper_losses_count": 19,
            "unpriced_positions_excluded": 7,
        },
        "baselines": {
            key: dict(_NEW_BASELINES[key])
            for key in ("barber_odean_2000_turnover", "odean_1998_disposition")
        },
    }


def _numeric_leaves_of(node):
    if isinstance(node, bool):
        return
    if isinstance(node, (int, float)):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from _numeric_leaves_of(value)


def test_ready_fixture_numbers_collide_with_no_fixed_literal():
    fixed = {Decimal(t).normalize() for t in VALIDATOR_FIXED_RAW | VALIDATOR_FIXED_PCT}
    seen: set[Decimal] = set()
    for value in _numeric_leaves_of(_ready_behaviour_block_no_fixed_literals()):
        forms = {Decimal(str(value)).normalize(), (Decimal(str(value)) * 100).normalize()}
        assert not forms & fixed, value
        assert not forms & seen, value
        seen |= forms


def test_disposition_baseline_is_odeans_per_account_average_not_the_pooled_figure():
    """Odean 1998 p.1784: average account PGR 0.57, PLR 0.36 — the average
    of the same per-account ratio this block computes for one user. The
    pooled Table I figures (0.148 / 0.098) are not comparable beside one
    account's ratio and must not be the rendered comparison."""
    assert _NEW_BASELINES["odean_1998_disposition"]["average_account_pgr"] == 0.57
    assert _NEW_BASELINES["odean_1998_disposition"]["average_account_plr"] == 0.36

    context = _metric_context()
    context["behaviour"] = _ready_behaviour_block_no_fixed_literals()
    rules = _rules_empty()
    sections = render_deterministic_sections(context, rules)
    f3 = sections["f3"]
    assert (
        "Published baseline (Odean 1998, average of per-account ratios): the "
        "average measured account realised 57.0% of its available gains and "
        "36.0% of its available losses."
    ) in f3
    assert "14.8" not in f3
    assert "9.8%" not in f3
    assert validate_sections(sections, build_allowlist(context, rules)) is None


def test_behaviour_block_passes_validator_ready_shape():
    context = _metric_context()
    context["behaviour"] = _ready_behaviour_block_no_fixed_literals()
    rules = _rules_empty()
    sections = render_deterministic_sections(context, rules)
    allowlist = build_allowlist(context, rules)
    assert validate_sections(sections, allowlist) is None
    assert "How this book has been traded" in sections["f3"]


_BANNED_TOKENS = (
    "underperform", "outperform", "you should", "well done", "poor",
    "good", "bad", "beat the market", "lagging", "the ai",
    "should", "recommend", "advice", "warning", "great", "excellent",
    "concerning", "worrying", "healthy", "unhealthy", "too much",
    "too little", "excessive",
)


def _assert_no_grade_no_warning_no_verdict(rendered_text: str) -> None:
    lowered = rendered_text.lower()
    for banned in _BANNED_TOKENS:
        assert banned not in lowered, banned


def test_the_behaviour_block_carries_no_grade_no_warning_no_verdict():
    """CR131's honesty rules, checked on the RENDERED text rather than only
    on the payload — the payload is not what a user reads. Mirrors
    `test_the_twin_block_carries_no_grade_no_warning_no_verdict`
    (test_cr222_passive_twin.py:499) for the behaviour block, covering every
    rendered branch: too_early; the full ready block; and each of the three
    independent not-measured variants (no closed lot -> median None, no buy
    on record -> attention None, no priced gain/loss -> disposition None)."""
    context = _metric_context()
    rules = _rules_empty()

    # too_early.
    context["behaviour"] = {"status": STATUS_TOO_EARLY, "message": "not enough data"}
    sections = render_deterministic_sections(context, rules)
    _assert_no_grade_no_warning_no_verdict(sections["f3"])

    # ready, every field populated.
    context["behaviour"] = _ready_behaviour_block_no_fixed_literals()
    sections = render_deterministic_sections(context, rules)
    _assert_no_grade_no_warning_no_verdict(sections["f3"])

    # ready, median_holding_period_days not measured (no closed lot).
    block = _ready_behaviour_block_no_fixed_literals()
    block["median_holding_period_days"] = None
    context["behaviour"] = block
    sections = render_deterministic_sections(context, rules)
    assert "Median holding period: not measured this run" in sections["f3"]
    _assert_no_grade_no_warning_no_verdict(sections["f3"])

    # ready, attention_trade_share_pct not measured (no buy on record).
    block = _ready_behaviour_block_no_fixed_literals()
    block["attention_trade_share_pct"] = None
    context["behaviour"] = block
    sections = render_deterministic_sections(context, rules)
    assert "Attention-triggered buys: not measured this run" in sections["f3"]
    _assert_no_grade_no_warning_no_verdict(sections["f3"])

    # ready, disposition not measured (no priced gain or loss on record).
    block = _ready_behaviour_block_no_fixed_literals()
    block["disposition"] = {"pgr": None, "plr": None}
    context["behaviour"] = block
    sections = render_deterministic_sections(context, rules)
    assert "Disposition ratio: not measured this run" in sections["f3"]
    _assert_no_grade_no_warning_no_verdict(sections["f3"])


def test_behaviour_block_passes_validator_too_early_shape():
    context = _metric_context()
    context["behaviour"] = {"status": STATUS_TOO_EARLY, "message": "not enough data"}
    rules = _rules_empty()
    sections = render_deterministic_sections(context, rules)
    allowlist = build_allowlist(context, rules)
    assert validate_sections(sections, allowlist) is None
    assert "Too early to measure this user's own trading behaviour" in sections["f3"]


def test_behaviour_block_absent_when_key_not_in_context():
    context = _metric_context()
    rules = _rules_empty()
    sections = render_deterministic_sections(context, rules)
    assert "How this book has been traded" not in sections["f3"]
    allowlist = build_allowlist(context, rules)
    assert validate_sections(sections, allowlist) is None


def test_build_behaviour_block_is_none_when_flag_off(monkeypatch):
    monkeypatch.setattr(settings, "portfolio_behaviour_diagnostics_enabled", False)
    assert build_behaviour_block(uuid4()) is None


def test_build_behaviour_block_returns_dict_when_flag_on(monkeypatch):
    monkeypatch.setattr(settings, "portfolio_behaviour_diagnostics_enabled", True)
    user_id = uuid4()
    result = build_behaviour_block(user_id)
    assert isinstance(result, dict)
    assert result["status"] == STATUS_TOO_EARLY
