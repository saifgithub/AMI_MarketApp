"""Sim Trading — Postgres-backed portfolio + pluggable market data provider.

The user's "team" can issue verdicts via Convene the Room, but those
verdicts are only valuable if the user can act on them. This module turns a
Verdict (or a manually entered ticket) into a real position in a paper-
trade portfolio, prices it via a swappable market data provider, computes
P&L, and flags stop/target hits.

Persistence:
  - sim_portfolios + sim_holdings + sim_trades survive backend restarts.
    A user's open positions are still open after a reboot.
  - Prices come from `app.services.market_data` — see that module for the
    real-Yahoo / mock-walk provider stack. SimEngine itself owns no
    pricing logic.

Architecture overview:

  SimEngine
    ├── ensure_portfolio(user_id) → Portfolio (lazy-created, $10k start)
    ├── current_price(ticker) → delegates to MarketDataProvider
    ├── submit(user_id, ticker, side, qty, ...) →
    │       1. Construct ProposedTrade
    │       2. Run check_mandate_compliance() — same safety floor as PM
    │       3. If passed: execute fill, update holdings/cash, emit a
    │          SimTrade row with verdict_ref optionally linked.
    │       4. If failed: return ComplianceResult with violations.
    ├── tick_marks() → refresh every ticker's mark
    └── evaluate_outcomes() → for each open trade with a stop/target,
            flip outcome to WIN / LOSS when hit, and liquidate the
            position — reduce the holding, credit the proceeds.

Setting `USE_REAL_MARKET_DATA=true` in env flips quotes from the
deterministic mock walk to live Yahoo prices (with mock fallback on
network errors). DB schema does not change either way.
"""

from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import delete, select

from app.agents.safety_floor import check_mandate_compliance
from app.core.logging import logger
from app.db import get_session, init_schema
from app.db.models import SimHoldingRow, SimPortfolioRow, SimTradeRow
from app.services.cost_basis_lots import Lot, compute_lots_fifo
from app.schemas import Mandate
from app.schemas.trade import (
    ComplianceResult,
    Holding,
    OrderType,
    Portfolio,
    ProposedTrade,
    Side,
)
from app.services.market_data import (
    Candle,
    EarningsInfo,
    MarketDataProvider,
    MockWalkProvider,
    NewsItem,
    Quote,
    get_market_data_provider,
)
from app.services.classification_universe import default_classification_universe
from app.services.sector_allocation import default_sector_map
from app.services.sharia_universe import default_halal_universe
from app.trading_math.portfolio import position_pct as _position_pct
from app.trading_math.risk_limits import position_risk_contribution as _position_risk_contribution


# ── Halal-flag universe (CR069) ─────────────────────────────────────────────
#
# The retired 7-ticker DEFAULT_HALAL_DEMO_UNIVERSE placeholder (DEF084) is gone.
# The `halal` flag now enforces a SOURCED allowlist — the S&P 500 Sharia Industry
# Exclusions Index constituents (AAOIFI, via SPUS), resolved to three states with
# provenance by `app.services.sharia_universe`. It is a sourced allowlist, NOT a
# computed ratio screen (`trading_math.screening.sharia_screen` stays dormant,
# CR069 constraint 4). Callers that don't pass a universe get `default_halal_universe()`,
# which degrades loudly (pauses) when the source is disabled/unavailable/stale —
# never a silent fall back to the old demo set.


# ── Sim trade record (in-Python dataclass that mirrors SimTradeRow) ────────


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
    verdict_ref: UUID | None = None
    realised_pnl: float = 0.0

    @classmethod
    def from_row(cls, row: SimTradeRow) -> "SimTrade":
        side_val = row.side
        return cls(
            id=row.id,
            user_id=row.user_id,
            portfolio_id=row.portfolio_id,
            ticker=row.ticker,
            side=Side(side_val) if not isinstance(side_val, Side) else side_val,
            quantity=float(row.quantity),
            entry_price=float(row.entry_price),
            stop=float(row.stop) if row.stop is not None else None,
            target=float(row.target) if row.target is not None else None,
            horizon_days=row.horizon_days,
            opened_at=row.opened_at,
            closed_at=row.closed_at,
            closed_price=float(row.closed_price) if row.closed_price is not None else None,
            status=row.status,  # type: ignore[assignment]
            verdict_ref=row.verdict_ref,
            realised_pnl=float(row.realised_pnl or 0),
        )

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
class PreviewResult:
    """Pre-flight preview of a sim trade — same mandate + cash/holdings checks
    as submit(), but never persists. Returned to the client so the trade
    ticket UI can render 'would this trade be allowed?' + sizing context
    before the user commits.
    """

    accepted: bool
    compliance: ComplianceResult
    fill_price: float
    notional: float
    cash_available: float
    held_quantity: float  # current holding for the ticker; 0.0 if none
    price_source: str  # "yfinance" or "mock_walk"


@dataclass
class OutcomeUpdate:
    trade_id: UUID
    new_status: TradeStatus
    closed_price: float
    realised_pnl: float


# ── Engine ────────────────────────────────────────────────────────────────


_STARTING_CAPITAL = 10_000.0


def _portfolio_from_row(row: SimPortfolioRow) -> Portfolio:
    return Portfolio(
        id=row.id,
        user_id=row.user_id,
        name=row.name,
        starting_capital=float(row.starting_capital),
        current_cash=float(row.current_cash),
        holdings=[
            Holding(
                ticker=h.ticker,
                quantity=float(h.quantity),
                avg_cost=float(h.avg_cost),
                opened_at=h.opened_at,
            )
            for h in row.holdings
        ],
        created_at=row.created_at,
    )


class SimEngine:
    def __init__(self, provider: MarketDataProvider | None = None) -> None:
        init_schema()
        self._provider: MarketDataProvider = provider or get_market_data_provider()
        # Mock fallback used only if the configured provider mysteriously
        # returns None (the production stack already has a mock at the end
        # of its chain, so this is purely defensive — a price we can always
        # quote beats a 500 to the iPhone client).
        self._fallback = MockWalkProvider()
        self._lock = RLock()

    # ── Pricing ────────────────────────────────────────────────────────

    @property
    def provider_name(self) -> str:
        """Configured-stack name — diagnostic only, not user-visible.

        For the LIVE / MOCK pill use `current_quote()` or the per-snapshot
        `aggregate_source()` — the stack name contains "yahoo" even when
        every fetch silently fell through to mock_walk during rate-limits.
        """
        return getattr(self._provider, "name", "unknown")

    def current_quote(self, ticker: str) -> Quote:
        """Return a Quote whose `source` is the leaf provider that served it.

        Always returns a non-None Quote — falls back to the defensive
        mock so callers never see a 500. Logs a warning if the configured
        provider produced None (the production stack already ends in
        mock_walk, so this branch is purely defensive).
        """
        q = self._provider.quote(ticker)
        if q is not None:
            return q
        logger.warn(
            "market_data_fallback", ticker=ticker, provider=self.provider_name,
        )
        fb = self._fallback.quote(ticker)
        if fb is not None:
            return fb
        return Quote(price=0.01, source="unavailable")

    def current_price(self, ticker: str) -> float:
        return self.current_quote(ticker).price

    def current_marks(self, tickers: list[str]) -> dict[str, float]:
        return {t.upper(): q.price for t, q in self._marks_with_quotes(tickers).items()}

    def current_marks_with_source(
        self, tickers: list[str],
    ) -> dict[str, Quote]:
        """Return prices alongside the leaf provider that produced each."""
        return self._marks_with_quotes(tickers)

    def _marks_with_quotes(self, tickers: list[str]) -> dict[str, Quote]:
        """Fetch one Quote per (deduped) ticker, fanned out over a plain sync
        thread pool (DEF120 D2). Deliberately `concurrent.futures`, NOT
        `asyncio.loop.run_in_executor` — this method is called both directly
        (sync unit tests) and from inside an `asyncio.to_thread` worker (the
        route handlers below), and `run_in_executor` needs a *running* event
        loop, which a `to_thread` worker thread does not have. A sync pool
        needs nothing from the caller's context, so it composes either way.
        """
        unique = sorted({t.upper() for t in tickers})
        if not unique:
            return {}
        with ThreadPoolExecutor(max_workers=min(len(unique), 10)) as pool:
            quotes = list(pool.map(self.current_quote, unique))
        return dict(zip(unique, quotes))

    def aggregate_source(self, tickers: list[str]) -> str:
        """The truthful single-string source for a snapshot.

        Returns the leaf source name iff EVERY ticker resolved through the
        same leaf — otherwise returns "mock_walk" so the LIVE pill only
        lights up when 100% of the user's holdings are real. Empty list
        defaults to "mock_walk" — there's nothing to honestly mark as
        LIVE until at least one ticker has been served.
        """
        return self._aggregate_source_from_quotes(self._marks_with_quotes(tickers))

    @staticmethod
    def _aggregate_source_from_quotes(quotes: dict[str, Quote]) -> str:
        if not quotes:
            return "mock_walk"
        sources = {q.source for q in quotes.values()}
        if len(sources) == 1:
            return next(iter(sources))
        return "mock_walk"

    def current_history(self, ticker: str, period: str) -> tuple[list[Candle], str]:
        """Return (candles, source) for the requested period.

        Mirrors the `current_quote` contract: never raises, always
        returns *something* (even if it's the defensive mock floor) so
        the iPhone never sees a 500. `source` is the leaf provider that
        actually served the bars — drives the chart's LIVE/MOCK badge
        the same way Quote.source drives the quote chip.
        """
        bars = self._provider.history(ticker, period)
        if bars:
            # Infer the leaf source — we know the current production stack
            # is yfinance-primary / mock_walk-secondary. Match the leaf by
            # asking the cheaper quote() (already cached). Defaulting to
            # the configured stack's primary name keeps the chart's
            # source meaningful even if quote() somehow disagrees.
            q = self._provider.quote(ticker)
            source = q.source if q is not None else "yfinance"
            return bars, source
        fb = self._fallback.history(ticker, period)
        if fb:
            return fb, self._fallback.name
        return [], "unavailable"

    def current_news(self, ticker: str, limit: int = 5) -> tuple[list[NewsItem], str]:
        """Return (articles, source). Empty list when no data — never raises."""
        items = self._provider.news(ticker, limit)
        if items:
            q = self._provider.quote(ticker)
            return items, q.source if q is not None else "yfinance"
        return [], "unavailable"

    def current_earnings(self, ticker: str) -> tuple[EarningsInfo | None, str]:
        """Return (earnings_info, source). None info when outside 90-day window — never raises."""
        info = self._provider.earnings(ticker)
        if info is not None:
            q = self._provider.quote(ticker)
            return info, q.source if q is not None else "yfinance"
        return None, "unavailable"

    # ── Portfolio ──────────────────────────────────────────────────────

    def _load_portfolio_row(self, s, user_id: UUID) -> SimPortfolioRow | None:
        return s.execute(
            select(SimPortfolioRow).where(SimPortfolioRow.user_id == user_id)
        ).scalar_one_or_none()

    def _existing_trade_for_verdict(
        self, user_id: UUID, verdict_ref: UUID
    ) -> UUID | None:
        """Return the trade_id of any prior trade against this verdict (any status).

        Used by submit() to enforce one-purchase-per-verdict. Matches both
        open and closed trades — once a verdict has been executed, the user
        should run a fresh Convene the Room for a new opinion rather than
        re-trade the same verdict.
        """
        with get_session() as s:
            row = s.execute(
                select(SimTradeRow.id)
                .where(SimTradeRow.user_id == user_id)
                .where(SimTradeRow.verdict_ref == verdict_ref)
                .order_by(SimTradeRow.opened_at.asc())
                .limit(1)
            ).scalar_one_or_none()
            return row

    def ensure_portfolio(self, user_id: UUID) -> Portfolio:
        with get_session() as s:
            row = self._load_portfolio_row(s, user_id)
            if row is None:
                row = SimPortfolioRow(
                    id=uuid4(),
                    user_id=user_id,
                    name="Main",
                    starting_capital=_STARTING_CAPITAL,
                    current_cash=_STARTING_CAPITAL,
                    created_at=datetime.now(timezone.utc),
                )
                s.add(row)
                s.flush()
            return _portfolio_from_row(row)

    def reset_portfolio(self, user_id: UUID) -> Portfolio:
        with get_session() as s:
            existing = self._load_portfolio_row(s, user_id)
            if existing is not None:
                s.execute(
                    delete(SimTradeRow).where(SimTradeRow.portfolio_id == existing.id)
                )
                s.delete(existing)
                s.flush()
        return self.ensure_portfolio(user_id)

    def total_value(self, user_id: UUID) -> float:
        p = self.ensure_portfolio(user_id)
        marks = self.current_marks([h.ticker for h in p.holdings])
        return p.total_value(marks)

    def current_drawdown_pct(self, user_id: UUID) -> float:
        p = self.ensure_portfolio(user_id)
        marks = self.current_marks([h.ticker for h in p.holdings])
        return p.total_drawdown_pct(marks)

    def portfolio_marks_snapshot(
        self, user_id: UUID,
    ) -> tuple[Portfolio, dict[str, float], float, float, str]:
        """One-fetch snapshot: (portfolio, marks, total_value, drawdown_pct, price_source).

        DEF120 D3 — `get_portfolio` used to call `current_marks` /
        `total_value` / `current_drawdown_pct` / `aggregate_source`
        independently, each re-fetching every holding's quote (the
        60s `CachingProvider` hides the network cost once warm, but the
        redundancy is unconditional and the cold-cache first pass pays
        for all four). This does a single `_marks_with_quotes` fan-out and
        derives every downstream value from it. Also used by
        `mandate.audit_holdings` and `portfolio.sector_allocation`, which
        had the same N-then-3N shape.
        """
        p = self.ensure_portfolio(user_id)
        tickers = [h.ticker for h in p.holdings]
        quotes = self._marks_with_quotes(tickers)
        marks = {t: q.price for t, q in quotes.items()}
        return (
            p,
            marks,
            p.total_value(marks),
            p.total_drawdown_pct(marks),
            self._aggregate_source_from_quotes(quotes),
        )

    def valuation_snapshot(self, user_id: UUID) -> tuple[float, float]:
        """(total_value, drawdown_pct) from a single marks fetch — see
        `portfolio_marks_snapshot`. Used where only the two numbers are
        needed (e.g. `room.py`'s pre-trade mandate check)."""
        _p, _marks, total_value, drawdown_pct, _source = self.portfolio_marks_snapshot(user_id)
        return total_value, drawdown_pct

    def list_trades(self, user_id: UUID, *, status: TradeStatus | None = None) -> list[SimTrade]:
        with get_session() as s:
            stmt = select(SimTradeRow).where(SimTradeRow.user_id == user_id)
            if status is not None:
                stmt = stmt.where(SimTradeRow.status == status)
            stmt = stmt.order_by(SimTradeRow.opened_at.desc())
            rows = s.execute(stmt).scalars().all()
            return [SimTrade.from_row(r) for r in rows]

    def _risk_limit_context(
        self, user_id: UUID, *, portfolio_value: float, quotes: dict[str, float]
    ) -> tuple[datetime | None, list[datetime], float]:
        """CR101-BE2: the trade-history context `check_mandate_compliance` needs
        for the post-loss cooldown, over-trading brake, and total open-risk cap
        — computed here (not in the floor, which is pure/DB-free) from this
        user's real `sim_trades` history.

        Returns (last_loss_closed_at, all trade opened_at timestamps,
        existing_open_risk_pct). The risk sum is per OPEN TRADE ROW (each buy
        execution carries its own stop), not per aggregated holding — a ticker
        bought twice at different stops sums both legs correctly.
        """
        trades = self.list_trades(user_id)
        last_loss_closed_at = max(
            (t.closed_at for t in trades if t.status == "lost" and t.closed_at is not None),
            default=None,
        )
        trade_open_timestamps = [t.opened_at for t in trades]
        existing_open_risk_pct = 0.0
        for t in trades:
            if t.status != "open" or t.stop is None:
                continue
            mark = quotes.get(t.ticker, t.entry_price)
            market_value = mark * t.quantity
            position_pct = _position_pct(market_value, portfolio_value)
            existing_open_risk_pct += _position_risk_contribution(
                position_pct, t.entry_price, t.stop
            )
        return last_loss_closed_at, trade_open_timestamps, existing_open_risk_pct

    def existing_open_risk_pct(
        self, user_id: UUID, *, portfolio_value: float, quotes: dict[str, float]
    ) -> float:
        """Public entry point to the open-risk sum in `_risk_limit_context` — for
        callers (BL12's audit endpoint) that need only this one figure, not the
        full submit()-path context."""
        _, _, risk_pct = self._risk_limit_context(
            user_id, portfolio_value=portfolio_value, quotes=quotes,
        )
        return risk_pct

    def holding_lots(
        self, user_id: UUID, ticker: str, *, current_price: float | None = None,
    ) -> list[Lot]:
        """Reconstruct FIFO cost-basis lots for one of the user's tickers (CR029).

        Read-only: pulls this user+ticker's `sim_trades` history and delegates
        the reconstruction to the pure `compute_lots_fifo`. No schema, no sell
        path — a read-time view over the existing order ledger.
        """
        ticker = ticker.upper().strip()
        with get_session() as s:
            rows = s.execute(
                select(SimTradeRow)
                .where(SimTradeRow.user_id == user_id)
                .where(SimTradeRow.ticker == ticker)
                .order_by(SimTradeRow.opened_at.asc())
            ).scalars().all()
            trades = [SimTrade.from_row(r) for r in rows]
        return compute_lots_fifo(trades, current_price=current_price)

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
        classification_universe: object | None = None,
        locale_allowed_universe: set[str] | None = None,
    ) -> SubmitResult:
        portfolio = self.ensure_portfolio(user_id)
        ticker = ticker.upper().strip()

        # One purchase per verdict (bug ce7146c8). When the trade is being
        # placed off a Convene the Room verdict, prevent a duplicate caused
        # by a double-tap on the "Buy" button or a retry after a transient
        # network error. We surface the existing trade_id in the violation
        # text so the client can deep-link the user back to it.
        if verdict_ref is not None:
            existing_trade_id = self._existing_trade_for_verdict(user_id, verdict_ref)
            if existing_trade_id is not None:
                logger.info(
                    "sim_trade_duplicate_verdict",
                    user_id=str(user_id),
                    verdict_ref=str(verdict_ref),
                    existing_trade_id=str(existing_trade_id),
                )
                fail = ComplianceResult(
                    passed=False,
                    violations=[
                        f"this verdict has already been executed "
                        f"(trade {str(existing_trade_id)[:8]})"
                    ],
                    blocked_by="duplicate_verdict",
                )
                return SubmitResult(
                    accepted=False, trade=None,
                    compliance=fail, portfolio_snapshot=portfolio,
                )

        mark = self.current_price(ticker)
        fill_price = mark if order_type == OrderType.MARKET else (limit_price or mark)
        proposed = ProposedTrade(
            ticker=ticker,
            side=side,
            order_type=order_type,
            quantity=quantity,
            limit_price=limit_price,
        )

        submit_portfolio_value = self.total_value(user_id)
        submit_quotes = self.current_marks(
            [h.ticker for h in portfolio.holdings] + [ticker]
        )
        # CR101-BE2: cooldown / over-trading / open-risk all read this user's
        # real trade history — computed here (sim_engine owns the DB access;
        # the floor stays pure) and handed to the floor as plain data.
        last_loss_closed_at, trade_open_timestamps, existing_open_risk_pct = (
            self._risk_limit_context(
                user_id, portfolio_value=submit_portfolio_value, quotes=submit_quotes,
            )
        )

        compliance = check_mandate_compliance(
            proposed,
            portfolio_value=submit_portfolio_value,
            current_drawdown_pct=self.current_drawdown_pct(user_id),
            mandate=mandate,
            halal_universe=halal_universe or default_halal_universe(),
            classification_universe=(
                classification_universe or default_classification_universe()
            ),
            locale_allowed_universe=locale_allowed_universe,
            # CR026: sector-concentration cap bites the same gate. Resolver reads the
            # stored snapshot — no request-path socket (CR075/DEF089).
            holdings=portfolio.holdings,
            # DEF149: the proposed ticker must be priced too, or the sector cap
            # cannot value a first-time buy of a name not already held.
            quotes=submit_quotes,
            sector_map=default_sector_map(),
            last_loss_closed_at=last_loss_closed_at,
            trade_open_timestamps=trade_open_timestamps,
            existing_open_risk_pct=existing_open_risk_pct,
            proposed_stop=stop,
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

        notional = fill_price * quantity
        if side == Side.BUY:
            if notional > portfolio.current_cash + 1e-6:
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
        else:
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

        # Persist fill + trade in one transaction.
        trade_id = uuid4()
        opened_at = datetime.now(timezone.utc)
        with get_session() as s:
            p_row = self._load_portfolio_row(s, user_id)
            assert p_row is not None  # ensure_portfolio ran above
            if side == Side.BUY:
                self._apply_buy_row(s, p_row, ticker, quantity, fill_price, opened_at)
            else:
                self._apply_sell_row(s, p_row, ticker, quantity, fill_price)
            s.add(SimTradeRow(
                id=trade_id,
                user_id=user_id,
                portfolio_id=p_row.id,
                ticker=ticker,
                side=side.value if hasattr(side, "value") else str(side),
                quantity=quantity,
                entry_price=fill_price,
                stop=stop,
                target=target,
                horizon_days=horizon_days,
                opened_at=opened_at,
                status="open",
                verdict_ref=verdict_ref,
                realised_pnl=0,
            ))
            s.flush()
            portfolio = _portfolio_from_row(p_row)
            trade = SimTrade(
                id=trade_id,
                user_id=user_id,
                portfolio_id=p_row.id,
                ticker=ticker,
                side=side,
                quantity=quantity,
                entry_price=fill_price,
                stop=stop,
                target=target,
                horizon_days=horizon_days,
                opened_at=opened_at,
                verdict_ref=verdict_ref,
            )

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

    def preview(
        self,
        *,
        user_id: UUID,
        ticker: str,
        side: Side,
        quantity: float,
        mandate: Mandate,
        order_type: OrderType = OrderType.MARKET,
        limit_price: float | None = None,
        verdict_ref: UUID | None = None,
        halal_universe: set[str] | None = None,
        classification_universe: object | None = None,
        locale_allowed_universe: set[str] | None = None,
    ) -> PreviewResult:
        """Dry-run a trade through the same pre-flight checks as submit() —
        compliance, verdict dedup, cash/holdings — without persisting.
        """
        portfolio = self.ensure_portfolio(user_id)
        ticker = ticker.upper().strip()

        if verdict_ref is not None:
            existing_trade_id = self._existing_trade_for_verdict(user_id, verdict_ref)
            if existing_trade_id is not None:
                fail = ComplianceResult(
                    passed=False,
                    violations=[
                        f"this verdict has already been executed "
                        f"(trade {str(existing_trade_id)[:8]})"
                    ],
                    blocked_by="duplicate_verdict",
                )
                held = next(
                    (h.quantity for h in portfolio.holdings if h.ticker == ticker),
                    0.0,
                )
                return PreviewResult(
                    accepted=False, compliance=fail,
                    fill_price=0.0, notional=0.0,
                    cash_available=portfolio.current_cash,
                    held_quantity=held,
                    price_source="mock_walk",
                )

        quote = self.current_quote(ticker)
        mark = quote.price
        fill_price = mark if order_type == OrderType.MARKET else (limit_price or mark)
        proposed = ProposedTrade(
            ticker=ticker,
            side=side,
            order_type=order_type,
            quantity=quantity,
            limit_price=limit_price,
        )

        preview_portfolio_value = self.total_value(user_id)
        preview_quotes = self.current_marks(
            [h.ticker for h in portfolio.holdings] + [ticker]
        )
        # CR101-BE2: same trade-history context as submit() (no `stop` param on
        # preview(), so the proposed trade's own open-risk contribution can't be
        # priced here — an ALREADY-breached existing_open_risk_pct still blocks).
        last_loss_closed_at, trade_open_timestamps, existing_open_risk_pct = (
            self._risk_limit_context(
                user_id, portfolio_value=preview_portfolio_value, quotes=preview_quotes,
            )
        )

        compliance = check_mandate_compliance(
            proposed,
            portfolio_value=preview_portfolio_value,
            current_drawdown_pct=self.current_drawdown_pct(user_id),
            mandate=mandate,
            halal_universe=halal_universe or default_halal_universe(),
            classification_universe=(
                classification_universe or default_classification_universe()
            ),
            locale_allowed_universe=locale_allowed_universe,
            # CR026: sector-concentration cap bites the preview gate too, so the
            # trade ticket's "would this be allowed?" reflects it. No request socket.
            holdings=portfolio.holdings,
            # DEF149: the proposed ticker must be priced too, or the sector cap
            # cannot value a first-time buy of a name not already held.
            quotes=preview_quotes,
            sector_map=default_sector_map(),
            last_loss_closed_at=last_loss_closed_at,
            trade_open_timestamps=trade_open_timestamps,
            existing_open_risk_pct=existing_open_risk_pct,
        )

        notional = fill_price * quantity
        held = next(
            (h.quantity for h in portfolio.holdings if h.ticker == ticker),
            0.0,
        )

        accepted = compliance.passed
        if accepted:
            if side == Side.BUY:
                if notional > portfolio.current_cash + 1e-6:
                    accepted = False
                    compliance = ComplianceResult(
                        passed=False,
                        violations=[
                            f"insufficient cash: need ${notional:.2f}, "
                            f"have ${portfolio.current_cash:.2f}"
                        ],
                        blocked_by=None,
                    )
            else:
                if held < quantity - 1e-6:
                    accepted = False
                    compliance = ComplianceResult(
                        passed=False,
                        violations=[
                            f"cannot sell {quantity} {ticker}: not enough held"
                        ],
                        blocked_by="long_only",
                    )

        return PreviewResult(
            accepted=accepted,
            compliance=compliance,
            fill_price=fill_price,
            notional=notional,
            cash_available=portfolio.current_cash,
            held_quantity=held,
            price_source=quote.source,
        )

    def _apply_buy_row(
        self, s, p_row: SimPortfolioRow, ticker: str,
        qty: float, fill: float, opened_at: datetime,
    ) -> None:
        notional = fill * qty
        existing_holding = next(
            (h for h in p_row.holdings if h.ticker == ticker), None,
        )
        if existing_holding is None:
            s.add(SimHoldingRow(
                portfolio_id=p_row.id,
                ticker=ticker,
                quantity=qty,
                avg_cost=fill,
                opened_at=opened_at,
            ))
        else:
            new_qty = float(existing_holding.quantity) + qty
            new_avg = (
                float(existing_holding.quantity) * float(existing_holding.avg_cost)
                + qty * fill
            ) / new_qty
            existing_holding.quantity = new_qty
            existing_holding.avg_cost = new_avg
        p_row.current_cash = round(float(p_row.current_cash) - notional, 2)

    def _apply_sell_row(
        self, s, p_row: SimPortfolioRow, ticker: str, qty: float, fill: float,
    ) -> float:
        """Reduce (or remove) the holding, credit the proceeds, return qty sold.

        Sells only what is still on the books, and only cash for what it sold.
        `evaluate_outcomes` closes several trades against one holding in a
        single pass, and a row already deleted earlier in that pass is still
        present in `p_row.holdings` until the session expires it — selling it
        twice would credit cash for shares that no longer exist.
        """
        sold = 0.0
        for h in list(p_row.holdings):
            if h.ticker != ticker or h in s.deleted:
                continue
            sold = min(qty, float(h.quantity))
            remaining = float(h.quantity) - sold
            if remaining > 1e-6:
                h.quantity = remaining
            else:
                s.delete(h)
            break
        p_row.current_cash = round(float(p_row.current_cash) + fill * sold, 2)
        return sold

    # ── Outcomes ───────────────────────────────────────────────────────

    def evaluate_outcomes(self, user_id: UUID) -> list[OutcomeUpdate]:
        """Check open trades against stop/target, and liquidate the ones that hit.

        A hit closes the position for real — the holding is reduced or removed
        and the proceeds credited, exactly as `manual_close` does. DEF110: this
        used to stamp `realised_pnl` and leave the shares on the books, so a
        stopped-out position stayed in the portfolio, in `total_value`, and in
        the sector concentration `check_mandate_compliance` hard-REJECTs on.
        """
        updates: list[OutcomeUpdate] = []
        with get_session() as s:
            rows = s.execute(
                select(SimTradeRow).where(
                    SimTradeRow.user_id == user_id,
                    SimTradeRow.status == "open",
                )
            ).scalars().all()
            # Once, not per trade: N trades must sell against one live row.
            p_row = self._load_portfolio_row(s, user_id)
            for t in rows:
                price = self.current_price(t.ticker)
                new_status: TradeStatus | None = None
                side = t.side
                side_enum = Side(side) if not isinstance(side, Side) else side
                if side_enum == Side.BUY:
                    if t.stop is not None and price <= float(t.stop):
                        new_status = "lost"
                    elif t.target is not None and price >= float(t.target):
                        new_status = "won"
                if new_status is None:
                    continue
                t.status = new_status
                t.closed_at = datetime.now(timezone.utc)
                t.closed_price = price
                t.realised_pnl = round((price - float(t.entry_price)) * float(t.quantity), 2)
                if p_row is not None:
                    self._apply_sell_row(s, p_row, t.ticker, float(t.quantity), price)
                updates.append(OutcomeUpdate(
                    trade_id=t.id, new_status=new_status,
                    closed_price=price, realised_pnl=float(t.realised_pnl),
                ))
            s.flush()
        return updates

    def manual_close(self, user_id: UUID, trade_id: UUID) -> SimTrade | None:
        with get_session() as s:
            row = s.execute(
                select(SimTradeRow).where(
                    SimTradeRow.user_id == user_id,
                    SimTradeRow.id == trade_id,
                    SimTradeRow.status == "open",
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            price = self.current_price(row.ticker)
            row.status = "closed"
            row.closed_at = datetime.now(timezone.utc)
            row.closed_price = price
            row.realised_pnl = round(
                (price - float(row.entry_price)) * float(row.quantity), 2,
            )
            p_row = self._load_portfolio_row(s, user_id)
            if p_row is not None:
                self._apply_sell_row(s, p_row, row.ticker, float(row.quantity), price)
            s.flush()
            return SimTrade.from_row(row)

    def clear(self) -> None:
        with get_session() as s:
            s.execute(delete(SimTradeRow))
            s.execute(delete(SimHoldingRow))
            s.execute(delete(SimPortfolioRow))
        with self._lock:
            self._walks.clear()


_engine: SimEngine | None = None


def get_sim_engine() -> SimEngine:
    global _engine
    if _engine is None:
        _engine = SimEngine()
    return _engine


def round2(x: float) -> float:
    return math.floor(x * 100 + 0.5) / 100
