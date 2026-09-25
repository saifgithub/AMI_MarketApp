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
    build_behaviour_block,
    compute_behaviour_diagnostics,
    turnover,
)
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


# ── (c) PGR/PLR — hand-built lot fixture, Odean's definition by hand ─────


def test_disposition_ratio_hand_built_fixture_matches_odean_by_hand():
    """Two tickers, AAA and BBB, each bought once at $100/share, 10 shares.

    Day 0: buy 10 AAA @ $100, buy 10 BBB @ $100.
    Day 10: AAA closes (self-close, won) at $120 -> realised gain, one event.
            At this instant BBB is still open, entered at $100. BBB's price
            on day 10 is $90 (seeded) -> paper LOSS event (90 < 100), NOT a
            paper gain.
    Day 20: BBB closes (self-close, lost) at $80 -> realised loss, one event.
            At this instant AAA is already closed (no longer open), so it
            contributes nothing to this sale's paper terms.

    Odean (1998) defines PGR/PLR as COUNT proportions — number of realised
    gain/loss EVENTS over number of (realised + paper) gain/loss EVENTS of
    the same sign, not a dollar-weighted average. By hand, counting events
    from AAA/BBB alone:
      AAA/BBB realised_gains_count = 1 (AAA's close)
      AAA/BBB realised_losses_count = 1 (BBB's close)
      paper_gains_count = 0 (BBB's day-10 mark was a paper LOSS event, not a
          paper gain event)
      paper_losses_count = 1 (BBB's day-10 mark, at AAA's sale instant)

    The padding block below (8 independent CCC round trips, each a small
    realised WIN, on a ticker with no price history) adds 8 more realised
    gain events and 8 `priced_lots_excluded` (CCC itself has no price row,
    and AAA/BBB are both closed or not-yet-open at each CCC sale instant, so
    they contribute no paper terms there) — it does not touch
    realised_losses_count, paper_gains_count or paper_losses_count. So,
    counting the whole fixture:
      realised_gains_count = 1 (AAA) + 8 (CCC) = 9
      realised_losses_count = 1 (BBB)
      paper_gains_count = 0
      paper_losses_count = 1
      pgr = realised_gains_count / (realised_gains_count + paper_gains_count)
          = 9 / (9 + 0) = 1.0
      plr = realised_losses_count / (realised_losses_count + paper_losses_count)
          = 1 / (1 + 1) = 0.5
    """
    user_id = uuid4()
    portfolio_id = _make_portfolio(user_id)
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    day0 = now - timedelta(days=200)
    day10 = day0 + timedelta(days=10)
    day20 = day0 + timedelta(days=20)

    days = [day0.date() + timedelta(days=i) for i in range(25)]
    aaa_prices = {d: 100.0 for d in days}
    aaa_prices[day10.date()] = 120.0
    _seed_prices("AAA", aaa_prices)

    bbb_prices = {d: 100.0 for d in days}
    bbb_prices[day10.date()] = 90.0
    bbb_prices[day20.date()] = 80.0
    _seed_prices("BBB", bbb_prices)

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
    # Padding to clear the trade-count floor, on a THIRD ticker with no price
    # history at all — proves an unpriced padding position is excluded
    # (`priced_lots_excluded`), never silently folded in as a zero.
    for i in range(8):
        opened = day0 + timedelta(days=100 + i)
        closed = opened + timedelta(days=1)
        _insert_trade(
            user_id, portfolio_id, ticker="CCC", side="buy",
            quantity=1.0, entry_price=50.0, opened_at=opened,
            status="won", closed_at=closed, closed_price=51.0, realised_pnl=1.0,
        )

    result = compute_behaviour_diagnostics(user_id, now=now)
    assert result["status"] == STATUS_READY
    disposition = result["disposition"]
    assert disposition["realised_gains_count"] == 9
    assert disposition["paper_gains_count"] == 0
    assert disposition["realised_losses_count"] == 1
    assert disposition["paper_losses_count"] == 1
    assert disposition["pgr"] == pytest.approx(1.0, abs=1e-4)
    assert disposition["plr"] == pytest.approx(0.5, abs=1e-4)


def test_disposition_ratio_uses_count_basis_not_dollar_basis():
    """One $900 realised gain plus nine $100 paper gains: dollar-weighted PGR
    would read 900 / (900 + 900) = 0.50; Odean's own count-weighted PGR reads
    1 / (1 + 9) = 0.10. This pins the count basis directly against a fixture
    engineered so the two bases diverge sharply — a regression to the dollar
    basis would fail this test even if every other PGR/PLR assertion in this
    file happened not to notice (most use unit qty/price so the two bases
    coincide by construction). Padding trades are closed LOSSES on a
    no-price-history ticker so they clear the trade-count floor without
    perturbing realised_gains_count or paper_gains_count."""
    user_id = uuid4()
    portfolio_id = _make_portfolio(user_id)
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    day0 = now - timedelta(days=200)
    day10 = day0 + timedelta(days=10)

    days = [day0.date() + timedelta(days=i) for i in range(15)]

    # BIG: bought at $100, 10 shares -> $900 realised gain on close at $190.
    big_prices = {d: 100.0 for d in days}
    big_prices[day10.date()] = 190.0
    _seed_prices("BIG", big_prices)

    # Nine SMALL tickers, each bought at $100/1 share, each up $10/share
    # (a $100 paper gain each) and still open at BIG's sale instant.
    small_tickers = [f"SM{i}" for i in range(9)]
    for tk in small_tickers:
        prices = {d: 100.0 for d in days}
        prices[day10.date()] = 110.0
        _seed_prices(tk, prices)

    _insert_trade(
        user_id, portfolio_id, ticker="BIG", side="buy",
        quantity=10.0, entry_price=100.0, opened_at=day0,
        status="won", closed_at=day10, closed_price=190.0, realised_pnl=900.0,
    )
    for tk in small_tickers:
        _insert_trade(
            user_id, portfolio_id, ticker=tk, side="buy",
            quantity=1.0, entry_price=100.0, opened_at=day0,
            status="open",
        )
    # Padding to clear the trade-count floor (need closed_lot_count >= 10;
    # BIG contributes 1, so 9 more here). Losses on a no-price-history
    # ticker, opened+closed entirely BEFORE day0 (BIG/SM's own open date),
    # so at their own sale instants BIG and every SM ticker are not yet
    # opened (`_open_lots_as_of` filters on `opened_at <= as_of`) and cannot
    # be counted as an "other open lot" — and at BIG's/SM's later sale
    # instants PAD is already fully closed, so it contributes nothing back
    # either way.
    for i in range(9):
        opened = day0 - timedelta(days=20 + i)
        closed = opened + timedelta(days=1)
        _insert_trade(
            user_id, portfolio_id, ticker="PAD", side="buy",
            quantity=1.0, entry_price=50.0, opened_at=opened,
            status="lost", closed_at=closed, closed_price=49.0, realised_pnl=-1.0,
        )

    result = compute_behaviour_diagnostics(user_id, now=now)
    assert result["status"] == STATUS_READY
    disposition = result["disposition"]
    assert disposition["realised_gains_count"] == 1
    assert disposition["paper_gains_count"] == 9
    assert disposition["pgr"] == pytest.approx(0.10, abs=1e-4)


def test_disposition_ratio_is_none_when_no_closed_lot_has_a_priced_paper_leg():
    """A single-position account (no OTHER open lot at any sale instant) has
    no paper terms at all — pgr/plr are still computable from realised-only
    denominators here (paper=0 is a valid, measured zero, not an absence),
    so this pins the shape rather than a None."""
    user_id = uuid4()
    portfolio_id = _make_portfolio(user_id)
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    start = now - timedelta(days=200)
    _build_closed_lots(user_id, portfolio_id, n=MIN_TRADES_FOR_DIAGNOSTICS, start=start, win=True)

    result = compute_behaviour_diagnostics(user_id, now=now)
    assert result["status"] == STATUS_READY
    disposition = result["disposition"]
    # All wins, no losses at all -> plr has zero denominator -> None.
    assert disposition["pgr"] == pytest.approx(1.0, abs=1e-4)
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
    """A `ready`-shape behaviour block where NO numeric field equals 1, 5, or
    10 (or any other token in `VALIDATOR_FIXED_RAW`/`VALIDATOR_FIXED_PCT`) —
    unlike the old fixture, whose `realised_gains_count = 5` only passed
    because "5" happens to be independently registered for the CR222 §4
    attention-trade sentence's fixed prose (`ATTENTION_MOVE_LOOKBACK_
    TRADING_DAYS`). A fixture built this way would have caught THAT
    coincidence, and is designed to catch the next one."""
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
            "pgr": 0.57, "plr": 0.34,
            "realised_gains_count": 17, "paper_gains_count": 13,
            "realised_losses_count": 9, "paper_losses_count": 17,
            "priced_lots_excluded": 0,
        },
        "baselines": {
            "barber_odean_2000_turnover": {
                "average_household_annual_turnover_pct": 75.0,
                "most_active_quintile_annual_turnover_pct": 250.0,
            },
            "odean_1998_disposition": {
                "proportion_gains_realised": 0.148,
                "proportion_losses_realised": 0.098,
            },
        },
    }


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
