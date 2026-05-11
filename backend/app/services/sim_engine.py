"""Sim Trading — in-memory portfolio + mock price engine.

The user's "team" can issue verdicts via Convene the Room, but those
verdicts are only valuable if the user can actually act on them. This
module turns a Verdict into a real position in a paper-trade portfolio,
runs a deterministic-per-ticker mock price feed, computes P&L, and flags
stop/target hits.

Architecture overview:

  SimEngine
    ├── ensure_portfolio(user_id) → SimPortfolio (lazy-created, $10k start)
    ├── current_price(ticker) → deterministic-but-volatile mark
    ├── submit(user_id, ticker, side, qty, ...) →
    │       1. Construct ProposedTrade
    │       2. Run check_mandate_compliance() — same safety floor as PM
    │       3. If passed: execute fill, update holdings/cash, emit a
    │          SimTrade record with verdict_ref optionally linked.
    │       4. If failed: return ComplianceResult with violations.
    ├── tick_marks() → refresh every ticker's mark
    └── evaluate_outcomes() → for each open trade with a stop/target,
            flip outcome to WIN / LOSS when hit (pure function so the
            API layer can attach this to the Journal entry).

Mock price engine: deterministic hash-seeded random walk per ticker.
Same ticker → same trajectory across the session. We *do* let the walk
drift over time so trades that just opened can hit stops/targets within
the alpha demo timeframe (a few minutes of real time).

A real market data feed (Polygon, Yahoo, etc.) is a swap for
`current_price()` at W8+.

Spec: docs/01_product/core_loop_and_features.md (Sim & Decision Journal),
      docs/08_tech/data_model.md (sim_portfolios / sim_holdings / sim_trades).
"""

from __future__ import annotations

import math
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Literal
from uuid import UUID, uuid4

from app.agents.safety_floor import check_mandate_compliance
from app.core.logging import logger
from app.schemas import Mandate
from app.schemas.trade import (
    ComplianceResult,
    Holding,
    OrderType,
    Portfolio,
    ProposedTrade,
    Side,
)


# ── Mock price engine ──────────────────────────────────────────────────────


# Demo-only halal universe. Mirrors room_runner.
DEFAULT_HALAL_UNIVERSE = {"AAPL", "MSFT", "NVDA", "GOOGL", "META", "TSLA", "AMZN"}


@dataclass
class _PriceWalk:
    """Per-ticker random walk state."""
    base: float
    drift_per_sec: float
    volatility: float
    started_at: float = field(default_factory=time.time)
    rng_seed: int = 0

    def price_at(self, now_ts: float | None = None) -> float:
        """Compute current price given the seeded random walk."""
        now_ts = now_ts or time.time()
        elapsed = max(0.0, now_ts - self.started_at)
        # Geometric brownian-ish: drift + noise. Each second is one step.
        steps = int(elapsed)
        rng = random.Random(self.rng_seed)
        v = self.base
        for _ in range(steps):
            shock = rng.gauss(0, self.volatility)
            v = v * (1 + self.drift_per_sec + shock)
        return max(0.01, round(v, 2))


def _walk_for(ticker: str) -> _PriceWalk:
    seed = hash(ticker.upper())
    rng = random.Random(seed)
    base = 50 + rng.uniform(0, 400)
    drift = rng.uniform(-0.0002, 0.0004)  # small per-second drift
    vol = rng.uniform(0.002, 0.008)
    return _PriceWalk(
        base=round(base, 2),
        drift_per_sec=drift,
        volatility=vol,
        rng_seed=seed,
    )


# ── Sim trade record ───────────────────────────────────────────────────────


TradeStatus = Literal["open", "won", "lost", "closed"]


@dataclass
class SimTrade:
    id: UUID
    user_id: UUID
    portfolio_id: UUID
    ticker: str
    side: Side
    quantity: float
    entry_price: float
    stop: float | None
    target: float | None
    horizon_days: int | None
    opened_at: datetime
    closed_at: datetime | None = None
    closed_price: float | None = None
    status: TradeStatus = "open"
    verdict_ref: UUID | None = None  # link to RoomRun.id if from a Room
    realised_pnl: float = 0.0

    def to_json(self) -> dict:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "portfolio_id": str(self.portfolio_id),
            "ticker": self.ticker,
            "side": self.side.value if hasattr(self.side, "value") else str(self.side),
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "stop": self.stop,
            "target": self.target,
            "horizon_days": self.horizon_days,
            "opened_at": self.opened_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "closed_price": self.closed_price,
            "status": self.status,
            "verdict_ref": str(self.verdict_ref) if self.verdict_ref else None,
            "realised_pnl": self.realised_pnl,
        }


# ── Result types ───────────────────────────────────────────────────────────


@dataclass
class SubmitResult:
    accepted: bool
    trade: SimTrade | None
    compliance: ComplianceResult
    portfolio_snapshot: Portfolio | None = None


@dataclass
class OutcomeUpdate:
    trade_id: UUID
    new_status: TradeStatus
    closed_price: float
    realised_pnl: float


# ── Engine ────────────────────────────────────────────────────────────────


_STARTING_CAPITAL = 10_000.0


class SimEngine:
    def __init__(self) -> None:
        self._portfolios: dict[UUID, Portfolio] = {}
        self._trades: dict[UUID, list[SimTrade]] = defaultdict(list)  # user_id → trades
        self._walks: dict[str, _PriceWalk] = {}
        self._lock = RLock()

    # ── Pricing ────────────────────────────────────────────────────────

    def current_price(self, ticker: str) -> float:
        t = ticker.upper().strip()
        with self._lock:
            walk = self._walks.get(t)
            if walk is None:
                walk = _walk_for(t)
                self._walks[t] = walk
        return walk.price_at()

    def current_marks(self, tickers: list[str]) -> dict[str, float]:
        return {t.upper(): self.current_price(t) for t in tickers}

    # ── Portfolio ──────────────────────────────────────────────────────

    def ensure_portfolio(self, user_id: UUID) -> Portfolio:
        with self._lock:
            p = self._portfolios.get(user_id)
            if p is not None:
                return p
            p = Portfolio(
                id=uuid4(),
                user_id=user_id,
                name="Main",
                starting_capital=_STARTING_CAPITAL,
                current_cash=_STARTING_CAPITAL,
                holdings=[],
                created_at=datetime.now(timezone.utc),
            )
            self._portfolios[user_id] = p
            return p

    def reset_portfolio(self, user_id: UUID) -> Portfolio:
        with self._lock:
            self._portfolios.pop(user_id, None)
            self._trades.pop(user_id, None)
        return self.ensure_portfolio(user_id)

    def total_value(self, user_id: UUID) -> float:
        p = self.ensure_portfolio(user_id)
        marks = self.current_marks([h.ticker for h in p.holdings])
        return p.total_value(marks)

    def current_drawdown_pct(self, user_id: UUID) -> float:
        p = self.ensure_portfolio(user_id)
        marks = self.current_marks([h.ticker for h in p.holdings])
        return p.total_drawdown_pct(marks)

    def list_trades(self, user_id: UUID, *, status: TradeStatus | None = None) -> list[SimTrade]:
        with self._lock:
            trades = list(self._trades.get(user_id, []))
        if status is not None:
            trades = [t for t in trades if t.status == status]
        trades.sort(key=lambda t: t.opened_at, reverse=True)
        return trades

    # ── Trading ────────────────────────────────────────────────────────

    def submit(
        self,
        *,
        user_id: UUID,
        ticker: str,
        side: Side,
        quantity: float,
        mandate: Mandate,
        order_type: OrderType = OrderType.MARKET,
        limit_price: float | None = None,
        stop: float | None = None,
        target: float | None = None,
        horizon_days: int | None = None,
        verdict_ref: UUID | None = None,
        halal_universe: set[str] | None = None,
        locale_allowed_universe: set[str] | None = None,
    ) -> SubmitResult:
        portfolio = self.ensure_portfolio(user_id)
        ticker = ticker.upper().strip()
        mark = self.current_price(ticker)
        fill_price = mark if order_type == OrderType.MARKET else (limit_price or mark)
        proposed = ProposedTrade(
            ticker=ticker,
            side=side,
            order_type=order_type,
            quantity=quantity,
            limit_price=limit_price,
        )

        # Safety floor — same as 1-on-1 + Room
        compliance = check_mandate_compliance(
            proposed,
            portfolio_value=self.total_value(user_id),
            current_drawdown_pct=self.current_drawdown_pct(user_id),
            mandate=mandate,
            halal_universe=halal_universe or DEFAULT_HALAL_UNIVERSE,
            locale_allowed_universe=locale_allowed_universe,
        )

        if not compliance.passed:
            logger.info(
                "sim_trade_rejected",
                user_id=str(user_id),
                ticker=ticker,
                violations=compliance.violations,
            )
            return SubmitResult(
                accepted=False, trade=None,
                compliance=compliance, portfolio_snapshot=portfolio,
            )

        # Execute the fill
        notional = fill_price * quantity
        if side == Side.BUY:
            if notional > portfolio.current_cash + 1e-6:
                # Not enough cash — convert to a compliance-like failure
                fail = ComplianceResult(
                    passed=False,
                    violations=[
                        f"insufficient cash: need ${notional:.2f}, "
                        f"have ${portfolio.current_cash:.2f}"
                    ],
                    blocked_by=None,
                )
                return SubmitResult(
                    accepted=False, trade=None,
                    compliance=fail, portfolio_snapshot=portfolio,
                )
            portfolio = self._apply_buy(portfolio, ticker, quantity, fill_price)
        else:  # SELL — close some/all of an existing long holding
            held = next((h for h in portfolio.holdings if h.ticker == ticker), None)
            if held is None or held.quantity < quantity - 1e-6:
                fail = ComplianceResult(
                    passed=False,
                    violations=[
                        f"cannot sell {quantity} {ticker}: not enough held"
                    ],
                    blocked_by="long_only",
                )
                return SubmitResult(
                    accepted=False, trade=None,
                    compliance=fail, portfolio_snapshot=portfolio,
                )
            portfolio = self._apply_sell(portfolio, ticker, quantity, fill_price)

        with self._lock:
            self._portfolios[user_id] = portfolio

        trade = SimTrade(
            id=uuid4(),
            user_id=user_id,
            portfolio_id=portfolio.id,
            ticker=ticker,
            side=side,
            quantity=quantity,
            entry_price=fill_price,
            stop=stop,
            target=target,
            horizon_days=horizon_days,
            opened_at=datetime.now(timezone.utc),
            verdict_ref=verdict_ref,
        )
        with self._lock:
            self._trades[user_id].append(trade)

        logger.info(
            "sim_trade_filled",
            user_id=str(user_id),
            ticker=ticker,
            side=side.value if hasattr(side, "value") else str(side),
            qty=quantity,
            fill=fill_price,
        )
        return SubmitResult(
            accepted=True, trade=trade,
            compliance=compliance, portfolio_snapshot=portfolio,
        )

    def _apply_buy(
        self, p: Portfolio, ticker: str, qty: float, fill: float
    ) -> Portfolio:
        notional = fill * qty
        existing = next((h for h in p.holdings if h.ticker == ticker), None)
        if existing is None:
            holdings = [*p.holdings, Holding(
                ticker=ticker, quantity=qty, avg_cost=fill,
                opened_at=datetime.now(timezone.utc),
            )]
        else:
            new_qty = existing.quantity + qty
            new_avg = (existing.quantity * existing.avg_cost + qty * fill) / new_qty
            holdings = [
                h if h.ticker != ticker else Holding(
                    ticker=ticker, quantity=new_qty, avg_cost=new_avg,
                    opened_at=existing.opened_at,
                )
                for h in p.holdings
            ]
        return p.model_copy(update={
            "holdings": holdings,
            "current_cash": round(p.current_cash - notional, 2),
        })

    def _apply_sell(
        self, p: Portfolio, ticker: str, qty: float, fill: float
    ) -> Portfolio:
        proceeds = fill * qty
        new_holdings: list[Holding] = []
        for h in p.holdings:
            if h.ticker != ticker:
                new_holdings.append(h)
                continue
            remaining = h.quantity - qty
            if remaining > 1e-6:
                new_holdings.append(Holding(
                    ticker=ticker, quantity=remaining,
                    avg_cost=h.avg_cost,  # unchanged
                    opened_at=h.opened_at,
                ))
            # else: fully closed — drop
        return p.model_copy(update={
            "holdings": new_holdings,
            "current_cash": round(p.current_cash + proceeds, 2),
        })

    # ── Outcomes ───────────────────────────────────────────────────────

    def evaluate_outcomes(self, user_id: UUID) -> list[OutcomeUpdate]:
        """Check open trades against stop/target and flip status if hit."""
        updates: list[OutcomeUpdate] = []
        with self._lock:
            trades = list(self._trades.get(user_id, []))
        for t in trades:
            if t.status != "open":
                continue
            price = self.current_price(t.ticker)
            new_status: TradeStatus | None = None
            if t.side == Side.BUY:
                if t.stop is not None and price <= t.stop:
                    new_status = "lost"
                elif t.target is not None and price >= t.target:
                    new_status = "won"
            else:  # short — ignore for alpha (long_only mandate default)
                pass
            if new_status is None:
                continue
            t.status = new_status
            t.closed_at = datetime.now(timezone.utc)
            t.closed_price = price
            t.realised_pnl = round((price - t.entry_price) * t.quantity, 2)
            updates.append(OutcomeUpdate(
                trade_id=t.id, new_status=new_status,
                closed_price=price, realised_pnl=t.realised_pnl,
            ))
        return updates

    def manual_close(self, user_id: UUID, trade_id: UUID) -> SimTrade | None:
        with self._lock:
            trades = list(self._trades.get(user_id, []))
        for t in trades:
            if t.id == trade_id and t.status == "open":
                price = self.current_price(t.ticker)
                t.status = "closed"
                t.closed_at = datetime.now(timezone.utc)
                t.closed_price = price
                t.realised_pnl = round((price - t.entry_price) * t.quantity, 2)
                # close the sim holding by simulating a sell
                p = self.ensure_portfolio(user_id)
                p = self._apply_sell(p, t.ticker, t.quantity, price)
                with self._lock:
                    self._portfolios[user_id] = p
                return t
        return None

    def clear(self) -> None:
        with self._lock:
            self._portfolios.clear()
            self._trades.clear()


_engine: SimEngine | None = None


def get_sim_engine() -> SimEngine:
    global _engine
    if _engine is None:
        _engine = SimEngine()
    return _engine


# Test helper — round helper so engine output is comparable in fixtures
def round2(x: float) -> float:
    return math.floor(x * 100 + 0.5) / 100
