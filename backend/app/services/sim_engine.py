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
from collections import defaultdict
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select

from app.agents.safety_floor import check_mandate_compliance
from app.core.logging import logger
from app.db import get_session, init_schema
from app.db.models import (
    GameShortPositionRow,
    PortfolioValueSnapshotRow,
    SimHoldingRow,
    SimPortfolioRow,
    SimRestingOrderRow,
    SimShortPositionRow,
    SimTradeRow,
)
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
from app.trading_math.market_hours import session_close_on_or_after
from app.trading_math.order_pricing import (
    LotBracket,
    blended_bracket,
    bracket_hit,
    bracket_is_wrong_side,
    can_rest,
    fill_price_for,
    is_triggered,
    named_price_for,
)
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


# ── Resting order (CR170) ──────────────────────────────────────────────────


RestingOrderState = Literal[
    "working", "triggered", "filling", "filled", "cancelled", "expired", "rejected"
]

#: The two states a sweep may claim, and the only two a user may cancel.
LIVE_RESTING_STATES: tuple[str, ...] = ("working", "triggered")

#: Still in the book. `filling` is not claimable and not cancellable, but the
#: order has not left — it is mid-fill, and the client shows it as live.
OPEN_RESTING_STATES: tuple[str, ...] = ("working", "triggered", "filling")

#: The four ways an order leaves the book. Every one of them must stamp
#: `retired_at` — see `retire_values`.
TERMINAL_RESTING_STATES: tuple[str, ...] = (
    "filled", "cancelled", "expired", "rejected",
)


def retire_values(state: str, now: datetime, **extra) -> dict:
    """The `.values()` payload for a transition OUT of the book (DEF309).

    Five call sites retire an order — filled, user-cancelled, expired, refused
    at fill, and reaped from a stale claim — and each is a place to forget the
    timestamp. Routing all five through one function is what makes
    *terminal ⇒ `retired_at` is set* a property of the code rather than of five
    people remembering, and `test_def309_retired_at.py` drives all five paths
    and asserts it rather than reading them.
    """
    if state not in TERMINAL_RESTING_STATES:
        raise ValueError(f"{state!r} is not a terminal resting-order state")
    return {"state": state, "retired_at": now, **extra}

#: Wire value → calendar days to add before finding the session close.
#: DAY is 0 — the close of the session that applies at placement.
RESTING_ORDER_TIFS: dict[str, int] = {"day": 0, "gtd_30": 30, "gtd_90": 90}


def resting_order_expiry(tif: str, placed_at: datetime) -> datetime:
    """CR170 §2 — when this order dies, anchored to a **session** close.

    An unknown TIF collapses to DAY rather than to the longest one: guessing
    wrong in the permissive direction leaves an order the user never asked for
    resting against their cash for ninety days (DEF210's shape — an unknown
    value must never resolve to the most powerful option).
    """
    days = RESTING_ORDER_TIFS.get(tif, 0)
    return session_close_on_or_after(placed_at + timedelta(days=days))


@dataclass
class SimRestingOrder:
    """In-Python mirror of `SimRestingOrderRow`, the way `SimTrade` mirrors
    `SimTradeRow`. `mobile/lib/models/sim_resting_order.dart` is a near-copy of
    `to_json()`'s shape."""

    id: UUID
    user_id: UUID
    portfolio_id: UUID
    ticker: str
    side: Side
    quantity: float
    order_type: OrderType
    state: RestingOrderState
    tif: str
    expires_at: datetime
    placed_at: datetime
    trigger_price: float | None = None
    limit_price: float | None = None
    stop: float | None = None
    target: float | None = None
    horizon_days: int | None = None
    verdict_ref: UUID | None = None
    triggered_at: datetime | None = None
    claimed_at: datetime | None = None
    filled_at: datetime | None = None
    fill_price: float | None = None
    filled_trade_id: UUID | None = None
    cancel_reason: str | None = None
    last_checked_at: datetime | None = None
    last_seen_price: float | None = None
    last_price_source: str | None = None
    #: DEF309 — when the order left the book. NULL ⇔ still live.
    retired_at: datetime | None = None

    @property
    def named_price(self) -> float | None:
        return named_price_for(
            self.order_type,
            trigger_price=self.trigger_price,
            limit_price=self.limit_price,
        )

    @property
    def distance_pct(self) -> float | None:
        """How far the last observed mark sits from the price the order names.

        Signed toward the trigger: negative means the market still has to move
        against the sign to reach it. Null before the first sweep, which the
        client renders as "waiting for the first check" — never as a zero, which
        would read as "about to fill".
        """
        named = self.named_price
        if named is None or not named or self.last_seen_price is None:
            return None
        return (self.last_seen_price - named) / named * 100.0

    @classmethod
    def from_row(cls, row: SimRestingOrderRow) -> "SimRestingOrder":
        def _f(v) -> float | None:
            return float(v) if v is not None else None

        return cls(
            id=row.id,
            user_id=row.user_id,
            portfolio_id=row.portfolio_id,
            ticker=row.ticker,
            side=Side(row.side) if not isinstance(row.side, Side) else row.side,
            quantity=float(row.quantity),
            order_type=(
                row.order_type if isinstance(row.order_type, OrderType)
                else OrderType(row.order_type)
            ),
            state=row.state,  # type: ignore[arg-type]
            tif=row.tif,
            expires_at=row.expires_at,
            placed_at=row.placed_at,
            trigger_price=_f(row.trigger_price),
            limit_price=_f(row.limit_price),
            stop=_f(row.stop),
            target=_f(row.target),
            horizon_days=row.horizon_days,
            verdict_ref=row.verdict_ref,
            triggered_at=row.triggered_at,
            claimed_at=row.claimed_at,
            filled_at=row.filled_at,
            fill_price=_f(row.fill_price),
            filled_trade_id=row.filled_trade_id,
            cancel_reason=row.cancel_reason,
            last_checked_at=row.last_checked_at,
            last_seen_price=_f(row.last_seen_price),
            last_price_source=row.last_price_source,
            retired_at=row.retired_at,
        )

    def to_json(self) -> dict:
        def _iso(d: datetime | None) -> str | None:
            return d.isoformat() if d is not None else None

        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "portfolio_id": str(self.portfolio_id),
            "ticker": self.ticker,
            "side": self.side.value if hasattr(self.side, "value") else str(self.side),
            "quantity": self.quantity,
            "order_type": (
                self.order_type.value if hasattr(self.order_type, "value")
                else str(self.order_type)
            ),
            "state": self.state,
            "tif": self.tif,
            "trigger_price": self.trigger_price,
            "limit_price": self.limit_price,
            "stop": self.stop,
            "target": self.target,
            "horizon_days": self.horizon_days,
            "expires_at": _iso(self.expires_at),
            "placed_at": _iso(self.placed_at),
            "triggered_at": _iso(self.triggered_at),
            "filled_at": _iso(self.filled_at),
            "fill_price": self.fill_price,
            "filled_trade_id": (
                str(self.filled_trade_id) if self.filled_trade_id else None
            ),
            "cancel_reason": self.cancel_reason,
            "last_checked_at": _iso(self.last_checked_at),
            "last_seen_price": self.last_seen_price,
            "distance_pct": self.distance_pct,
            # DEF309 — when it left the book, for any of the four exits. The
            # client dates the RECENTLY CLOSED group off this; `filled_at`
            # answers it for one exit out of four.
            "retired_at": _iso(self.retired_at),
        }


# ── Result types ───────────────────────────────────────────────────────────


@dataclass
class ComplianceContext:
    """The six values every `check_mandate_compliance` call site needs.
    Assembled by `SimEngine._compliance_context`; see its docstring."""

    portfolio_value: float
    quotes: dict[str, float]
    drawdown_pct: float
    last_loss_closed_at: datetime | None
    trade_open_timestamps: list[datetime]
    existing_open_risk_pct: float


@dataclass
class SubmitResult:
    accepted: bool
    trade: SimTrade | None
    compliance: ComplianceResult
    portfolio_snapshot: Portfolio | None = None
    # CR170 §8 — carried EXPLICITLY on every branch, never inferred from which
    # of `trade`/`resting_order` is null. The games lane learned this twice, and
    # the client (`SimSubmitResult.fromJson`) reads this field rather than
    # deriving it.
    resting: bool = False
    resting_order: SimRestingOrder | None = None
    # CR171 — a short open/cover writes NO `sim_trades` row, so `trade` is None
    # on those and these carry what happened instead. Same shape the game lane
    # already uses (`GameSubmitResult.short_action`), for the same reason and
    # then one more: acceptance 5 requires `def110_backfill.expected()` to be
    # byte-identical before and after opening a short, and that formula
    # subtracts Σ quantity over open SELL trade rows. A short that wrote one
    # would make every genuine phantom share look accounted for.
    # "short_open" | "short_cover" | None (an ordinary fill).
    short_action: str | None = None
    short_ticker: str | None = None
    short_quantity: float | None = None
    short_realised_pnl: float | None = None


@dataclass
class GameSubmitResult:
    """Result of a GAME-path trade attempt (CR109 slice 2).

    Deliberately NOT `SubmitResult`: that type carries `compliance`, which
    is meaningless here — the game path never runs
    `check_mandate_compliance` (§7.1) — and reusing it would tempt a caller
    into reading a game result's non-existent compliance verdict. `fee` is
    the Amendment-D trading cost actually charged (0.0 on a rejection —
    nothing was charged); `reason` carries a rejection's plain-English
    cause (insufficient cash, no shares held, ...).
    """

    accepted: bool
    trade: SimTrade | None
    fee: float
    reason: str | None = None
    portfolio_snapshot: Portfolio | None = None
    # CR109 Amendment G — a short open/cover writes no `sim_trades` row (see
    # `_open_game_short`), so `trade` is None on those and this carries what
    # happened instead. "short_open" | "short_cover" | None (an ordinary fill).
    short_action: str | None = None
    short_ticker: str | None = None
    short_quantity: float | None = None
    short_realised_pnl: float | None = None


@dataclass
class SplitAdjustment:
    """Result of `SimEngine.apply_split` — the post-adjustment holding
    state, extracted inside the DB session (the ORM row itself doesn't
    survive the session closing on exit)."""

    ticker: str
    quantity: float
    avg_cost: float
    split_adjusted_at: datetime


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
    # CR109 Amendment G — shorts exist only in the game lane, so the query
    # is skipped entirely on a training portfolio rather than run and found
    # empty: `_portfolio_from_row` is on the hot path of every portfolio
    # read in the app.
    # CR171 — the training lane has its own short book now, on its own table
    # with its own cash model (§2/§7). The two resolvers are picked by `kind`
    # here, once, so no reader downstream has to know which lane it is in.
    shorts = []
    from sqlalchemy.orm import object_session

    session = object_session(row)
    if session is not None:
        if row.kind == "game":
            from app.services.games_shorts import open_shorts_for_portfolio

            shorts = open_shorts_for_portfolio(session, row.id)
        else:
            from app.services.sim_shorts import (
                open_shorts_for_portfolio as _training_shorts,
            )

            shorts = _training_shorts(session, row.id)
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
        shorts=shorts,
        created_at=row.created_at,
    )



def _marked_tickers(p: Portfolio) -> list[str]:
    """Every ticker whose price affects this portfolio's value — CR171 §2.

    `total_value` and `total_drawdown_pct` used to price `p.holdings` alone.
    That was complete while a short could only exist in the game lane (whose
    surfaces build their own marks at line 789), and it silently stopped being
    complete the moment the training lane got one: `Portfolio.total_value`
    falls back to `marks.get(s.ticker, s.entry_price)`, so an unpriced short
    marks at its ENTRY forever. A short that had doubled against the user would
    have shown as costless in `total_value`, in `total_drawdown_pct`, in
    `portfolio_nav_daily` and in the TWR chain — the exact invisibility §2's
    cash design exists to prevent, reintroduced one level up.

    One function, so the next site that needs the full set cannot pick up half
    of it.
    """
    return [h.ticker for h in p.holdings] + [s.ticker for s in p.shorts]


def training_trade_scope(user_id: UUID):
    """A WHERE clause pinning a `sim_trades` query to a user's TRAINING
    ledger — DEF269.

    `sim_trades` has been a per-USER table since long before it was a
    per-portfolio one. CR109 slice 2 gave a user many portfolios (one
    training + one per game run) and routed game fills through the same
    `_execute_fill`, so game rows land in `sim_trades` carrying the same
    `user_id` and a different `portfolio_id` — and every reader still
    filtering on `user_id` alone silently widened from "this user's training
    trades" to "this user's trades anywhere". The tester-visible half was
    game trades listed in the training portfolio's open trades. The
    dangerous half was `evaluate_outcomes`, which selected those same rows
    and then sold them against the TRAINING portfolio row.

    Scoping by `portfolio_id` rather than by a `kind` column on the trade
    itself is deliberate: the portfolio row already knows which lane it is,
    so there is nothing to keep in sync and no way to write a trade whose
    own lane label disagrees with the portfolio it belongs to.

    Returns no rows when the user has no training portfolio, which is the
    correct answer (they have no training trades) rather than a crash or a
    silent fall-through to everything.
    """
    return SimTradeRow.portfolio_id.in_(
        select(SimPortfolioRow.id).where(
            SimPortfolioRow.user_id == user_id,
            SimPortfolioRow.kind == "training",
        )
    )


def _open_quantity_by_lot(rows: Iterable[SimTradeRow]) -> dict[str, float]:
    """DEF318 — `{buy trade id: shares of that lot still held}`, FIFO.

    A stop/target belongs to the shares its own buy bought, and after a sell
    those shares can be gone while the row is still `open` (deliberately — see
    DEF316). Asking "is this TICKER flat" is right when the user exited and
    blind when they re-entered: sell out of NVDA at $103 and buy back in with a
    stop at $90, and the first lot's dead $95 stop is still live against the
    second lot's shares. Measured: it fires at $94 and stamps −$60.00 against
    the wrong entry price, stopping the user out at a price they never named.

    Delegates to `compute_lots_fifo` (CR029-MATH, audited) rather than walking
    the stream here — `Lot.quantity_open` already means exactly this, and a
    second implementation of FIFO in the engine is the DEF098 shape waiting to
    happen. Rows are grouped by ticker because lots are per ticker.
    """
    by_ticker: dict[str, list[SimTradeRow]] = defaultdict(list)
    for r in rows:
        by_ticker[r.ticker].append(r)

    open_by_lot: dict[str, float] = {}
    for trades in by_ticker.values():
        for lot in compute_lots_fifo(trades):
            open_by_lot[lot.entry_trade_id] = lot.quantity_open
    return open_by_lot


def _lot_brackets(
    rows: Iterable[SimTradeRow], lot_open: dict[str, float],
) -> list[LotBracket]:
    """CR189 — open BUY rows as `blended_bracket` inputs, one assembly.

    Both readers of the position bracket go through here: the sweep, which
    already holds the rows, and `position_bracket`, which queries for them. The
    weighting *rule* lives in `blended_bracket`; if the ASSEMBLY were written
    twice — which side counts, which status, how a NULL level maps — the two
    could still disagree while both looked right. That is DEF098's shape, and it
    is the reason this is a function and not two comprehensions.
    """
    return [
        LotBracket(
            quantity_open=lot_open.get(str(r.id), 0.0),
            stop=float(r.stop) if r.stop is not None else None,
            target=float(r.target) if r.target is not None else None,
        )
        for r in rows
        if r.status == "open"
        and (r.side.value if hasattr(r.side, "value") else str(r.side)) == "buy"
    ]


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

    def _load_portfolio_row(
        self, s, user_id: UUID, *, kind: str = "training", run_id: UUID | None = None,
    ) -> SimPortfolioRow | None:
        """CR109 slice 2: `kind`/`run_id` default to the TRAINING portfolio
        (`kind="training"`, `run_id=None`) so every existing caller —
        `reset_portfolio`, `evaluate_outcomes`, `manual_close`, `submit`,
        all of them — keeps its current behaviour untouched. Only the game
        trade path passes `kind="game"` + a real `run_id`."""
        stmt = select(SimPortfolioRow).where(
            SimPortfolioRow.user_id == user_id,
            SimPortfolioRow.kind == kind,
        )
        stmt = stmt.where(
            SimPortfolioRow.run_id.is_(None) if run_id is None
            else SimPortfolioRow.run_id == run_id
        )
        return s.execute(stmt).scalar_one_or_none()

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
                .where(training_trade_scope(user_id))
                .where(SimTradeRow.verdict_ref == verdict_ref)
                .order_by(SimTradeRow.opened_at.asc())
                .limit(1)
            ).scalar_one_or_none()
            return row

    def ensure_portfolio(
        self, user_id: UUID, *, kind: str = "training", run_id: UUID | None = None,
    ) -> Portfolio:
        """CR109 slice 2: defaulted `kind`/`run_id` — see
        `_load_portfolio_row`'s docstring. `ensure_portfolio(user_id,
        kind="game", run_id=<run>)` lazy-creates that run's own $10k
        AMI Cash game portfolio the first time it's touched, exactly like
        the training portfolio always has."""
        with get_session() as s:
            row = self._load_portfolio_row(s, user_id, kind=kind, run_id=run_id)
            if row is None:
                row = SimPortfolioRow(
                    id=uuid4(),
                    user_id=user_id,
                    kind=kind,
                    run_id=run_id,
                    name="Main" if kind == "training" else "Game Run",
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
                # CR136 M03: explicit, like the trades above. The FK's CASCADE
                # fires on Postgres but sqlite does not enforce FK pragmas by
                # default, so without this the test DB and production would
                # disagree about what a reset destroys.
                s.execute(
                    delete(PortfolioValueSnapshotRow).where(
                        PortfolioValueSnapshotRow.portfolio_id == existing.id
                    )
                )
                # CR170 §1 — the third explicit delete, for the same CR136-M03
                # reason as the second. Miss it and a resting order survives a
                # reset and later fills into a portfolio UUID that no longer
                # exists — **on Alpha only**, because sqlite's unenforced FK
                # pragmas mean the unit suite would never see it.
                s.execute(
                    delete(SimRestingOrderRow).where(
                        SimRestingOrderRow.portfolio_id == existing.id
                    )
                )
                # CR171 §3 — the FOURTH explicit delete, same CR136-M03 reason.
                # A short surviving a reset is worse than a resting order
                # doing so: it keeps accruing borrow against a portfolio UUID
                # that no longer exists, and the margin sweep would keep
                # reading it.
                s.execute(
                    delete(SimShortPositionRow).where(
                        SimShortPositionRow.portfolio_id == existing.id
                    )
                )
                s.delete(existing)
                s.flush()
        return self.ensure_portfolio(user_id)

    def total_value(self, user_id: UUID) -> float:
        p = self.ensure_portfolio(user_id)
        return p.total_value(self.current_marks(_marked_tickers(p)))

    def current_drawdown_pct(self, user_id: UUID) -> float:
        p = self.ensure_portfolio(user_id)
        return p.total_drawdown_pct(self.current_marks(_marked_tickers(p)))

    def portfolio_marks_snapshot(
        self, user_id: UUID, *, kind: str = "training", run_id: UUID | None = None,
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

        CR109 slice 2: `kind`/`run_id` default to the TRAINING portfolio —
        every existing caller is unaffected. The game NAV tick
        (`portfolio_nav_daily.run_game_nav_snapshot_tick`) passes
        `kind="game"` + a run's own `run_id`.
        """
        p = self.ensure_portfolio(user_id, kind=kind, run_id=run_id)
        # CR109 Amendment G — a short's ticker must be marked too, or its leg
        # falls back to `entry_price` and the position reads as permanently
        # flat: no P&L on the run screen, none in the daily NAV row, and a
        # TWR chain that never learns the trade happened. CR171: `p.shorts` is
        # no longer empty on a training portfolio either, which is why the same
        # set is now `_marked_tickers` rather than three copies of this line.
        tickers = _marked_tickers(p)
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

    def list_trades(
        self,
        user_id: UUID,
        *,
        status: TradeStatus | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[SimTrade]:
        with get_session() as s:
            stmt = select(SimTradeRow).where(training_trade_scope(user_id))
            if status is not None:
                stmt = stmt.where(SimTradeRow.status == status)
            # CR120 Phase 3: `id` tiebreaker because `opened_at` defaults to
            # _utcnow and CAN tie — pagination needs a total order or pages
            # overlap. UUID4 order is arbitrary but stable, which suffices.
            stmt = stmt.order_by(SimTradeRow.opened_at.desc(), SimTradeRow.id.desc())
            if offset:
                stmt = stmt.offset(offset)
            if limit is not None:
                stmt = stmt.limit(limit)
            rows = s.execute(stmt).scalars().all()
            return [SimTrade.from_row(r) for r in rows]

    def count_trades(self, user_id: UUID, *, status: TradeStatus | None = None) -> int:
        """Ledger size under the exact scope+filter `list_trades` reads —
        CR120 Phase 3's `total`. Reuses `training_trade_scope` so the count
        and the list structurally cannot disagree on lane (DEF269: a
        user_id-only count would let game fills inflate `total`)."""
        with get_session() as s:
            stmt = (
                select(func.count())
                .select_from(SimTradeRow)
                .where(training_trade_scope(user_id))
            )
            if status is not None:
                stmt = stmt.where(SimTradeRow.status == status)
            return int(s.execute(stmt).scalar_one())

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

    def risk_limit_context(
        self, user_id: UUID, *, portfolio_value: float, quotes: dict[str, float]
    ) -> tuple[datetime | None, list[datetime], float]:
        """Public entry point to `_risk_limit_context` — for callers outside
        submit()/preview() that need the SAME cooldown/over-trading/open-risk
        trade-history context those two build for their own `check_mandate_compliance`
        calls. CR101-BE2 round 2: the Room's scripted path (`room_runner._assemble_verdict`)
        and the LLM-override wrapper (`enforce_safety_floor`) previously supplied none
        of this, so three of the four new limits were silently off on the path the
        user actually watches — this method is what they now call instead."""
        return self._risk_limit_context(
            user_id, portfolio_value=portfolio_value, quotes=quotes,
        )

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

    def _compliance_context(
        self, user_id: UUID, portfolio: Portfolio, ticker: str,
    ) -> "ComplianceContext":
        """CR170 §4 — the six values `check_mandate_compliance` needs, assembled
        once.

        `submit()` and `preview()` each built this inline, identically. CR170
        makes `fill_resting_order()` the third, and the CR is explicit about
        the sequencing: *"hoist before the third arrives, not after."* Three
        copies of an assembly is how one of them quietly stops matching — which
        is exactly what DEF149 was, a compliance input that went missing on one
        path and nowhere else.

        The proposed ticker is priced alongside the holdings (DEF149) so the
        sector cap can value a first-time buy of a name not already held.
        """
        portfolio_value = self.total_value(user_id)
        # CR171 §6 — the SHORT tickers must be priced too, or gross
        # concentration values an existing short at zero and the cap passes a
        # position it should refuse.
        quotes = self.current_marks(_marked_tickers(portfolio) + [ticker])
        last_loss_closed_at, trade_open_timestamps, existing_open_risk = (
            self._risk_limit_context(
                user_id, portfolio_value=portfolio_value, quotes=quotes,
            )
        )
        return ComplianceContext(
            portfolio_value=portfolio_value,
            quotes=quotes,
            drawdown_pct=self.current_drawdown_pct(user_id),
            last_loss_closed_at=last_loss_closed_at,
            trade_open_timestamps=trade_open_timestamps,
            existing_open_risk_pct=existing_open_risk,
        )

    def position_brackets(
        self, user_id: UUID,
    ) -> dict[str, tuple[float | None, float | None]]:
        """CR189 — every held ticker's position bracket, in ONE query.

        The plural of `position_bracket`, and the reason it exists rather than
        the route looping: the Positions tab draws a stop chip per tile, so a
        per-ticker call is an N+1 against the database on the hottest read in
        the app. Same derivation (`_lot_brackets` → `blended_bracket`), so the
        chip and the sweep cannot disagree — which is the whole point of CR189,
        since a tile showing a level the sweep does not fire on is the defect.
        """
        with get_session() as s:
            rows = s.execute(
                select(SimTradeRow)
                .where(training_trade_scope(user_id))
                .order_by(SimTradeRow.opened_at.asc())
            ).scalars().all()

        by_ticker: dict[str, list[SimTradeRow]] = defaultdict(list)
        for r in rows:
            by_ticker[r.ticker].append(r)

        out: dict[str, tuple[float | None, float | None]] = {}
        for ticker, trades in by_ticker.items():
            lot_open = _open_quantity_by_lot(trades)
            out[ticker] = blended_bracket(_lot_brackets(trades, lot_open))
        return out

    def position_bracket(
        self, user_id: UUID, ticker: str, *, extra: LotBracket | None = None,
    ) -> tuple[float | None, float | None]:
        """CR189 — this ticker's position-level stop/target, weighted by open shares.

        The single derivation. The sweep fires on it, the ticket discloses moves
        to it, and the tile draws it — three readers of one number, because two
        derivations of one fact is what DEF098 was.

        `extra` prices a lot that does not exist yet: pass the order being
        submitted and this returns the bracket the position *would* have, which
        is what the disclosure names and the wrong-side refusal tests.
        """
        ticker = ticker.upper().strip()
        with get_session() as s:
            rows = s.execute(
                select(SimTradeRow)
                .where(training_trade_scope(user_id))
                .where(SimTradeRow.ticker == ticker)
                .order_by(SimTradeRow.opened_at.asc())
            ).scalars().all()
        lot_open = _open_quantity_by_lot(rows)
        lots = _lot_brackets(rows, lot_open)
        if extra is not None:
            lots.append(extra)
        return blended_bracket(lots)

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
                .where(training_trade_scope(user_id))
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
        trigger_price: float | None = None,
        tif: str = "day",
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
        # CR170 §3 — the P10/DEF153 ternary is GONE. It read
        # `mark if order_type == MARKET else (limit_price or mark)`, which made
        # `order_type` decide a price: a "limit order" filled instantly at
        # whatever the caller named. `order_type` now decides exactly one thing,
        # and it is not a price — see the branch below. Two duties, two
        # constructs.
        fill_price = mark
        proposed = ProposedTrade(
            ticker=ticker,
            side=side,
            order_type=order_type,
            quantity=quantity,
            limit_price=limit_price,
        )

        ctx = self._compliance_context(user_id, portfolio, ticker)

        compliance = check_mandate_compliance(
            proposed,
            portfolio_value=ctx.portfolio_value,
            current_drawdown_pct=ctx.drawdown_pct,
            mandate=mandate,
            halal_universe=halal_universe or default_halal_universe(),
            classification_universe=(
                classification_universe or default_classification_universe()
            ),
            locale_allowed_universe=locale_allowed_universe,
            # CR026: sector-concentration cap bites the same gate. Resolver reads the
            # stored snapshot — no request-path socket (CR075/DEF089).
            holdings=portfolio.holdings,
            # CR171 §6 — gross concentration. Without this the floor sees
            # the long leg only and reports a hedged pair as no exposure.
            shorts=portfolio.shorts,
            # DEF149: the proposed ticker must be priced too, or the sector cap
            # cannot value a first-time buy of a name not already held.
            quotes=ctx.quotes,
            sector_map=default_sector_map(),
            last_loss_closed_at=ctx.last_loss_closed_at,
            trade_open_timestamps=ctx.trade_open_timestamps,
            existing_open_risk_pct=ctx.existing_open_risk_pct,
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

        # CR170 §3 — rest or fill, decided by a BRANCH on the trigger rule.
        #
        # A **marketable** order — a buy limit at or above the market, a sell
        # limit at or below it — is already through the market, so it falls
        # through to the same `_execute_fill` at the same `mark` as a market
        # order would. That is acceptance 1, and it strengthens the DEF153
        # invariant: "identical economics get identical rulings" held only
        # inside `safety_floor` before; now it holds in `sim_engine` too, which
        # is where the defect actually lived.
        named = named_price_for(
            order_type, trigger_price=trigger_price, limit_price=limit_price,
        )
        if (
            can_rest(order_type)
            and named is not None
            and not is_triggered(
                side=side, order_type=order_type, named=named, mark=mark,
            )
        ):
            return self._rest_order(
                user_id=user_id,
                portfolio=portfolio,
                ticker=ticker,
                side=side,
                quantity=quantity,
                order_type=order_type,
                trigger_price=trigger_price,
                limit_price=limit_price,
                tif=tif,
                stop=stop,
                target=target,
                horizon_days=horizon_days,
                verdict_ref=verdict_ref,
                compliance=compliance,
            )

        return self._execute_fill(
            user_id=user_id,
            portfolio=portfolio,
            ticker=ticker,
            side=side,
            quantity=quantity,
            fill_price=fill_price,
            compliance=compliance,
            stop=stop,
            target=target,
            horizon_days=horizon_days,
            verdict_ref=verdict_ref,
        )

    def _execute_fill(
        self,
        *,
        user_id: UUID,
        portfolio: Portfolio,
        ticker: str,
        side: Side,
        quantity: float,
        fill_price: float,
        compliance: ComplianceResult,
        stop: float | None = None,
        target: float | None = None,
        horizon_days: int | None = None,
        verdict_ref: UUID | None = None,
        kind: str = "training",
        run_id: UUID | None = None,
        fee: float = 0.0,
        now: datetime | None = None,
    ) -> SubmitResult:
        """The mechanics shared by every fill path: cash/holdings check, the
        fill, the holding update and the trade row.

        CR109 §7.1 — this exists so the game's trade path can reuse the
        mechanics WITHOUT reusing the safety floor. **It deliberately takes no
        `skip_compliance` flag.** A boolean that switches the floor off is one
        wrong argument away from disabling it on the training path; instead
        this helper never runs compliance at all, and *deciding* compliance is
        the caller's job. `submit()` runs `check_mandate_compliance` and passes
        its verdict in; the game path (slice 2) will run its own market-hours
        rule and pass a clean result. The difference is then structural rather
        than conditional, which is what CR040 asks for.

        `compliance` is echoed onto the returned `SubmitResult` rather than
        consulted — a caller that has already decided to fill is telling this
        helper what to report, not asking it to re-check.

        CR109 slice 2 additions — `kind`/`run_id` select which portfolio
        row the fill lands on (default TRAINING; `submit()` never passes
        them, so it is unaffected). `fee` is Amendment D's trading cost:
        defaults to 0.0, so the training path moves exactly the cash it
        always did; only `submit_game_trade()` ever passes a non-zero fee,
        burned on both a buy and a sell (subtracted from cash, credited to
        nothing — `games_scoring.trade_fee`).
        """
        # DEF312 — an inverted bracket is refused HERE, at the one chokepoint
        # every fill path crosses, and against the price it will actually be
        # measured from. Not in `submit()`: a resting order's bracket has to be
        # judged against the price it FILLS at, which Rule 2 puts at the worse
        # of named and observed, not the price named days earlier.
        #
        # `is_short` is the same three-case rule the sell branch below applies:
        # a sell against zero held opens a short, and a short's bracket inverts.
        held_now = next(
            (h for h in portfolio.holdings if h.ticker == ticker), None,
        )
        opens_short = (
            side != Side.BUY
            and kind == "training"
            and (held_now is None or float(held_now.quantity) <= 1e-9)
        )
        if side == Side.BUY or opens_short:
            wrong_side = bracket_is_wrong_side(
                is_short=opens_short, entry=fill_price, stop=stop, target=target,
            )
            if wrong_side is not None:
                return SubmitResult(
                    accepted=False, trade=None,
                    compliance=ComplianceResult(
                        passed=False, violations=[wrong_side], blocked_by=None,
                    ),
                    portfolio_snapshot=portfolio,
                )

        # CR189 acceptance 6 — the order's OWN bracket can be perfectly placed
        # and the resulting POSITION bracket still be wrong-side, because the
        # blend moves. Buying into a held name with a high stop drags the
        # position's stop up; land it at or above the mark and the next sweep
        # liquidates everything, at market, and trips the post-stop-out cooldown
        # that blocks the user's next buy. That is DEF312's consequence arriving
        # by arithmetic instead of by typing, so it is a refusal, not a warning.
        if side == Side.BUY and kind == "training" and held_now is not None:
            blend_stop, blend_target = self.position_bracket(
                user_id, ticker,
                extra=LotBracket(quantity_open=quantity, stop=stop, target=target),
            )
            blend_wrong = bracket_is_wrong_side(
                is_short=False, entry=fill_price,
                stop=blend_stop, target=blend_target,
            )
            if blend_wrong is not None:
                held_after = float(held_now.quantity) + quantity
                level, name = (
                    (blend_stop, "stop") if blend_stop is not None
                    and blend_stop >= fill_price else (blend_target, "target")
                )
                return SubmitResult(
                    accepted=False, trade=None,
                    compliance=ComplianceResult(
                        passed=False,
                        violations=[
                            f"adding these shares would move your {name} for all "
                            f"{held_after:g} {ticker} to ${level:.2f}, which is on "
                            f"the wrong side of the ${fill_price:.2f} market — the "
                            f"position would be closed on the next sweep"
                        ],
                        blocked_by=None,
                    ),
                    portfolio_snapshot=portfolio,
                )

        notional = fill_price * quantity
        if side == Side.BUY:
            # CR171 — a buy against a standing short is a COVER, not a new long.
            # Without this branch `SimEngine.cover_short` is unreachable from
            # any client: a short could be opened and then only ever closed by
            # the margin call or a bracket, which is DEF259's shape (the games
            # lane shipped a position that could be opened and never closed) on
            # the one position type whose loss is unbounded. Buying long into a
            # standing short would also leave the user holding both legs of the
            # same name — a state the gross concentration rule (§6) measures as
            # double exposure and `def110_backfill` was never designed to read.
            covered = self._cover_short_fill(
                user_id=user_id, portfolio=portfolio, ticker=ticker,
                quantity=quantity, fill_price=fill_price,
                compliance=compliance, kind=kind,
            )
            if covered is not None:
                return covered
            total_cost = notional + fee
            if total_cost > portfolio.current_cash + 1e-6:
                fail = ComplianceResult(
                    passed=False,
                    violations=[
                        f"insufficient cash: need ${total_cost:.2f}, "
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
            held_qty = float(held.quantity) if held is not None else 0.0
            # CR171 §1 — a sell never crosses zero. Three cases, no ambiguous
            # middle, which is what makes the rest of this CR tractable:
            #
            #   held >= quantity   sell to close   (exactly today's behaviour)
            #   held == 0          sell to open    (a short)
            #   0 < held < qty     REFUSED, naming both numbers
            #
            # A real broker splits that third case into a close plus a short.
            # We refuse it: the split is two fills, two trade rows and two cost
            # bases from one user action, and the P&L attribution that follows
            # is exactly what DEF166 and DEF110 have already cost us twice.
            # Refusing is one sentence of copy and removes the whole class.
            if held_qty <= 1e-9 and kind == "training":
                return self._open_short_fill(
                    user_id=user_id,
                    portfolio=portfolio,
                    ticker=ticker,
                    quantity=quantity,
                    fill_price=fill_price,
                    compliance=compliance,
                    stop=stop,
                    target=target,
                )
            if held_qty < quantity - 1e-6:
                fail = ComplianceResult(
                    passed=False,
                    violations=(
                        [
                            f"cannot sell {quantity:g} {ticker}: you hold "
                            f"{held_qty:g}. Sell {held_qty:g} to close the "
                            f"position, or sell 0 to open a short — AMI will "
                            f"not do both in one order"
                        ]
                        if held_qty > 1e-9
                        else [f"cannot sell {quantity} {ticker}: not enough held"]
                    ),
                    blocked_by="long_only",
                )
                return SubmitResult(
                    accepted=False, trade=None,
                    compliance=fail, portfolio_snapshot=portfolio,
                )

        # Persist fill + trade in one transaction.
        trade_id = uuid4()
        # DEF326 — `now` is the caller's clock when it has one. Every game path
        # already threads a `now` for the market-hours gate and the settlement
        # sell; this line used to ignore it, so a fill stamped itself with the
        # wall clock while the sell that closes it carried the injected time.
        # The FIFO lot reconstruction orders by timestamp, so the sell then
        # drew before its own lot existed and the ledger read as a phantom.
        opened_at = now or datetime.now(timezone.utc)
        with get_session() as s:
            p_row = self._load_portfolio_row(s, user_id, kind=kind, run_id=run_id)
            assert p_row is not None  # ensure_portfolio ran above
            if side == Side.BUY:
                self._apply_buy_row(s, p_row, ticker, quantity, fill_price, opened_at)
            else:
                self._apply_sell_row(s, p_row, ticker, quantity, fill_price)
            if fee:
                # Amendment D — BURNED: subtracted from this fill's own
                # portfolio and credited to nothing (no table, counter or
                # aggregate anywhere accumulates it). Applied on BOTH a buy
                # (on top of the notional already deducted above) and a
                # sell (on top of the proceeds already credited above).
                p_row.current_cash = round(float(p_row.current_cash) - fee, 2)
            # DEF166/DEF110: a SELL trade row is created "open" and NEVER
            # transitions — only `evaluate_outcomes` closes trades, and it
            # only watches BUY rows against stop/target. This permanent-open
            # is load-bearing: `def110_backfill.py`'s `expected()` formula
            # subtracts Σ quantity over status='open' SELL trades to derive
            # what a portfolio's holdings SHOULD be. Closing a sell row here
            # (or anywhere) without updating that formula silently corrupts
            # its phantom-share detection. Guarded by
            # test_def110_backfill.py::test_sell_trade_rows_stay_open_forever.
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

    # ── Resting-order book (CR170) ────────────────────────────────────────

    def _rest_order(
        self,
        *,
        user_id: UUID,
        portfolio: Portfolio,
        ticker: str,
        side: Side,
        quantity: float,
        order_type: OrderType,
        trigger_price: float | None,
        limit_price: float | None,
        tif: str,
        stop: float | None,
        target: float | None,
        horizon_days: int | None,
        verdict_ref: UUID | None,
        compliance: ComplianceResult,
    ) -> SubmitResult:
        """Park an order in the book. **No `_execute_fill`, no cash movement.**

        Cash is computed at read time and never reserved (§6). Reserving would
        redefine `current_cash` — the number `total_value`, `total_drawdown_pct`,
        `portfolio_nav_daily`, the TWR chain and `_risk_limit_context` all read —
        and a reserved-cash debit is indistinguishable from a loss in the NAV
        series unless every one of those learns about it. It would also need a
        compensating credit on five terminal paths (cancel, expire, reject,
        reset, reap); every missed one leaks a user's money permanently. Read-time
        computation has no compensating write, so there is nothing to leak.
        """
        placed_at = datetime.now(timezone.utc)
        expires_at = resting_order_expiry(tif, placed_at)
        order_id = uuid4()
        with get_session() as s:
            p_row = self._load_portfolio_row(s, user_id)
            assert p_row is not None
            row = SimRestingOrderRow(
                id=order_id,
                user_id=user_id,
                portfolio_id=p_row.id,
                ticker=ticker,
                side=side.value if hasattr(side, "value") else str(side),
                quantity=quantity,
                order_type=(
                    order_type.value if hasattr(order_type, "value")
                    else str(order_type)
                ),
                trigger_price=trigger_price,
                limit_price=limit_price,
                stop=stop,
                target=target,
                horizon_days=horizon_days,
                verdict_ref=verdict_ref,
                tif=tif,
                expires_at=expires_at,
                state="working",
                placed_at=placed_at,
            )
            s.add(row)
            s.flush()
            order = SimRestingOrder.from_row(row)

        logger.info(
            "sim_order_rested",
            user_id=str(user_id),
            order_id=str(order_id),
            ticker=ticker,
            order_type=order.order_type.value,
            named=order.named_price,
            tif=tif,
            expires_at=expires_at.isoformat(),
        )
        return SubmitResult(
            accepted=True,
            trade=None,
            compliance=compliance,
            portfolio_snapshot=portfolio,
            resting=True,
            resting_order=order,
        )

    def fill_resting_order(
        self,
        *,
        order: SimRestingOrder,
        mark: float,
        mandate: Mandate,
        halal_universe: set[str] | None = None,
        classification_universe: object | None = None,
        locale_allowed_universe: set[str] | None = None,
    ) -> SubmitResult:
        """CR170 — the resting book's own entry point.

        Structurally distinct from `submit()` the way `submit_game_trade()` is,
        and for the **opposite** reason: this one DOES run
        `check_mandate_compliance`, because a resting order must never become a
        time-delayed bypass of the floor. Between placing and filling, the
        mandate, the drawdown, the sector allocation, the post-loss cooldown and
        the halal universe can all have changed, and the floor is specified
        *uncoachable* — a 90-day delay is not a way around it.

        It differs from `submit()` only in the price it books at: **Rule 2**, the
        worse of (named, observed), not the observed mark. See
        `trading_math/order_pricing.py` for why the mark would be a systematic,
        farmable edge here and is not at submit time.
        """
        user_id = order.user_id
        portfolio = self.ensure_portfolio(user_id)
        proposed = ProposedTrade(
            ticker=order.ticker,
            side=order.side,
            order_type=order.order_type,
            quantity=order.quantity,
            limit_price=order.limit_price,
        )
        ctx = self._compliance_context(user_id, portfolio, order.ticker)
        compliance = check_mandate_compliance(
            proposed,
            portfolio_value=ctx.portfolio_value,
            current_drawdown_pct=ctx.drawdown_pct,
            mandate=mandate,
            halal_universe=halal_universe or default_halal_universe(),
            classification_universe=(
                classification_universe or default_classification_universe()
            ),
            locale_allowed_universe=locale_allowed_universe,
            holdings=portfolio.holdings,
            # CR171 §6 — gross concentration. Without this the floor sees
            # the long leg only and reports a hedged pair as no exposure.
            shorts=portfolio.shorts,
            quotes=ctx.quotes,
            sector_map=default_sector_map(),
            last_loss_closed_at=ctx.last_loss_closed_at,
            trade_open_timestamps=ctx.trade_open_timestamps,
            existing_open_risk_pct=ctx.existing_open_risk_pct,
            proposed_stop=order.stop,
        )
        if not compliance.passed:
            logger.info(
                "sim_resting_order_refused_at_fill",
                user_id=str(user_id),
                order_id=str(order.id),
                ticker=order.ticker,
                violations=compliance.violations,
            )
            return SubmitResult(
                accepted=False, trade=None,
                compliance=compliance, portfolio_snapshot=portfolio,
            )

        named = order.named_price
        # A stop-limit that has triggered evaluates as a limit from here on, so
        # the price it books at is its LIMIT, not the trigger it passed.
        if order.order_type == OrderType.STOP_LIMIT:
            named = order.limit_price
        assert named is not None  # every resting order names a price
        return self._execute_fill(
            user_id=user_id,
            portfolio=portfolio,
            ticker=order.ticker,
            side=order.side,
            quantity=order.quantity,
            fill_price=fill_price_for(side=order.side, named=named, mark=mark),
            compliance=compliance,
            stop=order.stop,
            target=order.target,
            horizon_days=order.horizon_days,
            verdict_ref=order.verdict_ref,
        )

    def list_resting_orders(
        self,
        user_id: UUID,
        *,
        terminal_since: datetime | None = None,
    ) -> list[SimRestingOrder]:
        """Every live order, plus terminal rows since `terminal_since`.

        A pure DB read — `last_seen_price` and `distance_pct` come off the row
        the sweep wrote, so listing costs no quote fan-out (strictly better than
        the games lane's `_queued_orders_priced`, which prices on every call).

        Terminal rows are included by default so a rejected or expired order
        never silently vanishes overnight. That is the whole reason the games
        lane's own docstring records *"from the player's side the order simply
        VANISHED."*

        **The window is measured from `retired_at`, not from `placed_at`
        (DEF309).** It used to read `(filled_at or placed_at) >= terminal_since`,
        and `filled_at` is set on exactly one of the four exits — so a cancelled,
        expired or rejected order fell back to when it was *placed*. A GTD-90
        order placed last week and refused at fill this morning was therefore
        filtered out, and the longer an order had rested the more certainly its
        refusal was hidden. That is the vanishing this window exists to prevent,
        inverted onto the case that matters most: the compliance sentence the
        user most needs to read is the one on the order that waited longest.
        """
        with get_session() as s:
            rows = s.execute(
                select(SimRestingOrderRow)
                .where(SimRestingOrderRow.user_id == user_id)
                .order_by(SimRestingOrderRow.placed_at.desc())
            ).scalars().all()
            orders = [SimRestingOrder.from_row(r) for r in rows]
        if terminal_since is None:
            return orders

        def _aware(d: datetime) -> datetime:
            """Postgres hands back tz-aware datetimes for these columns; the
            unit suite's sqlite tempfile hands back naive ones. Comparing the
            two raises, so this comparison must not be the first thing that
            finds out which backend it is running on."""
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)

        return [
            o for o in orders
            if o.state in OPEN_RESTING_STATES
            # A terminal row with no `retired_at` predates the DEF309 migration's
            # backfill; show it rather than hide it. Erring toward visible is the
            # whole point of the window.
            or o.retired_at is None
            or _aware(o.retired_at) >= _aware(terminal_since)
        ]

    def cancel_resting_order(
        self, user_id: UUID, order_id: UUID,
    ) -> tuple[bool, SimRestingOrder | None]:
        """A **user** cancel. Returns (cancelled, order-as-it-now-stands).

        `cancel_reason` is deliberately left NULL — the invariant the client's
        copy is built on is that a non-null reason means the SYSTEM refused.

        `filling` is not cancellable: the sweep has claimed the order and a
        cancel would race a money-moving operation whose outcome is already
        unknown. The caller gets `(False, <order in its real state>)` so the
        client can show the race rather than a success toast — the games lane
        shipped `status ?? 'filled'` and had to fix it.
        """
        with get_session() as s:
            row = s.execute(
                select(SimRestingOrderRow).where(
                    SimRestingOrderRow.id == order_id,
                    SimRestingOrderRow.user_id == user_id,
                )
            ).scalar_one_or_none()
            if row is None:
                return False, None
            if row.state not in LIVE_RESTING_STATES:
                return False, SimRestingOrder.from_row(row)
            for k, v in retire_values("cancelled", datetime.now(timezone.utc)).items():
                setattr(row, k, v)
            s.flush()
            return True, SimRestingOrder.from_row(row)

    # ── Game trade path (CR109 slice 2, §7.1) ─────────────────────────────

    def submit_game_trade(
        self,
        *,
        user_id: UUID,
        run_id: UUID,
        ticker: str,
        side: Side,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: float | None = None,
        stop: float | None = None,
        target: float | None = None,
        horizon_days: int | None = None,
        now: datetime | None = None,
    ) -> GameSubmitResult:
        """CR109 slice 2, §7.1 — the game trade path's second public entry
        point, structurally distinct from `submit()`: it never calls
        `check_mandate_compliance` — not "skipped", simply absent from this
        function's body, the same way `_execute_fill` never contains it
        (see `test_cr109_trade_path_split.py`). No mandate is resolved, no
        `ProposedTrade`/compliance context is built — there is nothing here
        for a floor to run against.

        Always fills IMMEDIATELY at the CURRENT price — this method has no
        concept of "queued". Deciding whether to call it at all (the
        market-hours rule) is `games_service.py`'s job: an out-of-hours
        order never reaches here until the queue-drain sweep calls it,
        which is what fetches a FRESH price rather than the one on screen
        when the order was placed.

        Charges Amendment D's trading cost via `_execute_fill`'s `fee`
        parameter — the ONLY call site in the codebase that ever passes a
        non-zero one. `games_scoring.trade_fee` is computed off the ACTUAL
        fill price (not an estimate), so the fee is exact, never rounded
        from a quote shown earlier.
        """
        from app.services.games_scoring import trade_fee as _trade_fee

        ticker = ticker.upper().strip()
        portfolio = self.ensure_portfolio(user_id, kind="game", run_id=run_id)
        mark = self.current_price(ticker)
        # CR170 §3 — the same P10 ternary, hoisted here too, with **no routing**.
        # The games lane has no resting book and this call site is inert in
        # practice (nothing has ever sent a non-market order_type here). It moves
        # anyway, because P11's lesson is that fixing one instance is not fixing
        # the class — and a copy left behind is where the class comes back.
        fill_price = mark
        fee = _trade_fee(fill_price * quantity)

        # CR109 Amendment G — route the two legs that are NOT ordinary fills
        # before touching `_execute_fill`, which knows only about longs.
        routed = self._route_game_short(
            user_id=user_id, run_id=run_id, portfolio=portfolio,
            ticker=ticker, side=side, quantity=quantity, fill_price=fill_price,
        )
        if routed is not None:
            return routed

        result = self._execute_fill(
            user_id=user_id,
            portfolio=portfolio,
            ticker=ticker,
            side=side,
            quantity=quantity,
            fill_price=fill_price,
            # No mandate exists on this path — a clean, unconsulted
            # ComplianceResult (see `_execute_fill`'s own docstring: it
            # never reads `compliance`, only echoes it onto the result).
            compliance=ComplianceResult(passed=True, violations=[], blocked_by=None),
            stop=stop,
            target=target,
            horizon_days=horizon_days,
            kind="game",
            run_id=run_id,
            fee=fee,
            now=now,
        )
        if not result.accepted:
            return GameSubmitResult(
                accepted=False, trade=None, fee=0.0,
                reason=(
                    result.compliance.violations[0]
                    if result.compliance.violations else "rejected"
                ),
                portfolio_snapshot=result.portfolio_snapshot,
            )
        logger.info(
            "game_trade_filled",
            user_id=str(user_id), run_id=str(run_id), ticker=ticker,
            side=side.value if hasattr(side, "value") else str(side),
            qty=quantity, fill=fill_price, fee=fee,
        )
        return GameSubmitResult(
            accepted=True, trade=result.trade, fee=fee,
            portfolio_snapshot=result.portfolio_snapshot,
        )

    # ── Short legs of the game trade path (CR109 Amendment G) ─────────────

    def _route_game_short(
        self,
        *,
        user_id: UUID,
        run_id: UUID,
        portfolio: Portfolio,
        ticker: str,
        side: Side,
        quantity: float,
        fill_price: float,
    ) -> GameSubmitResult | None:
        """Decide whether this game fill is a short open, a short cover, a
        refusal, or an ordinary long fill.

        Returns `None` for "ordinary long fill — carry on"; anything else is
        the final result. Keeping the decision in ONE function is the point:
        the sell-never-crosses-zero rule and its buy-side mirror are two
        halves of one invariant, and splitting them across the two branches
        of `_execute_fill` is how they would drift apart.

            SELL, h >= q, no short   ordinary close        -> None
            SELL, 0 < h < q          REFUSED (both numbers)
            SELL, h == 0, no short   sell to open a short
            SELL, short already open REFUSED (no extending)
            BUY,  no short           ordinary buy          -> None
            BUY,  short open, q == short.q   cover in full
            BUY,  short open, q != short.q   REFUSED (both numbers)
        """
        from app.services.games_scoring import short_open_fee as _short_open_fee
        from app.services.games_scoring import trade_fee as _trade_fee
        from app.services.games_shorts import cover_short, find_open_short, open_short

        held = next((h for h in portfolio.holdings if h.ticker == ticker), None)
        held_qty = float(held.quantity) if held is not None else 0.0
        standing = next((s for s in portfolio.shorts if s.ticker == ticker), None)

        def refuse(reason: str) -> GameSubmitResult:
            return GameSubmitResult(
                accepted=False, trade=None, fee=0.0, reason=reason,
                portfolio_snapshot=portfolio,
            )

        if side == Side.SELL:
            if standing is not None:
                return refuse(
                    f"already short {standing.quantity:g} {ticker} — cover that "
                    f"position before selling more"
                )
            if held_qty >= quantity - 1e-6:
                return None  # ordinary close (or partial close) of a long
            if held_qty > 1e-6:
                return refuse(
                    f"cannot sell {quantity:g} {ticker}: you hold "
                    f"{held_qty:g}. Close the {held_qty:g} you hold, then "
                    f"short separately — one order cannot do both"
                )
            # h == 0: sell to open.
            notional = fill_price * quantity
            fee = _short_open_fee(notional)
            posted = round(notional, 2)
            if posted + fee > portfolio.current_cash + 1e-6:
                return refuse(
                    f"insufficient cash to short: need ${posted + fee:.2f}, "
                    f"have ${portfolio.current_cash:.2f}"
                )
            with get_session() as s:
                p_row = self._load_portfolio_row(s, user_id, kind="game", run_id=run_id)
                assert p_row is not None
                open_short(
                    s, portfolio_row=p_row, user_id=user_id, run_id=run_id,
                    ticker=ticker, quantity=quantity, fill_price=fill_price, fee=fee,
                )
                s.flush()
                snapshot = _portfolio_from_row(p_row)
            logger.info(
                "game_short_opened",
                user_id=str(user_id), run_id=str(run_id), ticker=ticker,
                qty=quantity, fill=fill_price, fee=fee, posted=posted,
            )
            return GameSubmitResult(
                accepted=True, trade=None, fee=fee, portfolio_snapshot=snapshot,
                short_action="short_open", short_ticker=ticker,
                short_quantity=quantity,
            )

        if standing is None:
            return None  # ordinary buy

        # BUY with a short standing — a cover, in full or not at all.
        if abs(quantity - standing.quantity) > 1e-6:
            return refuse(
                f"you are short {standing.quantity:g} {ticker} — a cover buys "
                f"back the whole position, not {quantity:g}"
            )
        fee = _trade_fee(fill_price * quantity)
        with get_session() as s:
            p_row = self._load_portfolio_row(s, user_id, kind="game", run_id=run_id)
            assert p_row is not None
            short_row = find_open_short(s, p_row.id, ticker)
            if short_row is None:
                # Covered between the snapshot and this transaction. Nothing
                # is owed and nothing should be charged — reporting a fill
                # that did not happen is worse than reporting nothing.
                return refuse(f"no open short in {ticker} to cover")
            realised = cover_short(
                s, portfolio_row=p_row, short_row=short_row,
                close_price=fill_price, fee=fee, reason="user",
            )
            s.flush()
            snapshot = _portfolio_from_row(p_row)
        logger.info(
            "game_short_covered",
            user_id=str(user_id), run_id=str(run_id), ticker=ticker,
            qty=quantity, fill=fill_price, fee=fee, realised=realised,
        )
        return GameSubmitResult(
            accepted=True, trade=None, fee=fee, portfolio_snapshot=snapshot,
            short_action="short_cover", short_ticker=ticker,
            short_quantity=quantity, short_realised_pnl=realised,
        )

    def apply_split(
        self,
        user_id: UUID,
        ticker: str,
        ratio: float,
        *,
        kind: str = "game",
        run_id: UUID | None = None,
    ) -> SplitAdjustment | None:
        """CR109 slice 2 (G2) — adjust a held position for a corporate
        split IN PLACE: `quantity *= ratio`, `avg_cost /= ratio`, so
        `quantity * avg_cost` (the position's cost basis) is unchanged and
        NAV stays continuous once the market price divides by the same
        ratio. Flags the row (`SimHoldingRow.split_adjusted_at`) rather
        than writing a `portfolio_nav_daily.capital_event` — a split
        leaves economic value unchanged, so (design §12) it must NOT split
        the TWR chain, and only `capital_event` does that.

        GAME-portfolio-only by convention (`kind` defaults to `"game"`):
        design §12.1 G2 — "training absorbs it with a free reset" — so
        nothing calls this against a training holding. Returns `None` if
        the ticker isn't held (a split notice for a ticker nobody holds is
        a no-op, not an error) or the portfolio doesn't exist.

        Detecting WHEN a split happened is intentionally not this
        function's job — this is the mechanical "apply" step only,
        exercised by its test with a known ratio; wiring it to a real
        split calendar is a follow-up, matching G3's "measure first before
        building detection machinery" posture in the design.
        """
        if ratio <= 0:
            raise ValueError(f"split ratio must be positive, got {ratio}")
        ticker = ticker.upper().strip()
        now = datetime.now(timezone.utc)
        with get_session() as s:
            p_row = self._load_portfolio_row(s, user_id, kind=kind, run_id=run_id)
            if p_row is None:
                return None
            # CR109 Amendment G — a SHORT in the splitting name divides the
            # same way, and for a sharper reason than the long does. The
            # market price halves on a 2:1; a short whose quantity and entry
            # price were left alone would mark at half its entry and show a
            # 50% gain that is pure arithmetic — a fabricated profit, on a
            # scored contest, from a corporate action that changed nothing.
            # `cash_posted` is deliberately NOT adjusted: it is already
            # `old_entry * old_quantity`, which equals
            # `(entry/ratio) * (quantity*ratio)`. Unchanged is correct.
            short = next(
                (
                    sp for sp in s.execute(
                        select(GameShortPositionRow).where(
                            GameShortPositionRow.portfolio_id == p_row.id,
                            GameShortPositionRow.ticker == ticker,
                            GameShortPositionRow.state == "open",
                        )
                    ).scalars().all()
                ),
                None,
            )
            if short is not None:
                short.quantity = float(short.quantity) * ratio
                short.entry_price = float(short.entry_price) / ratio
                s.add(short)

            holding = next((h for h in p_row.holdings if h.ticker == ticker), None)
            if holding is None:
                if short is not None:
                    s.flush()
                return None
            holding.quantity = float(holding.quantity) * ratio
            holding.avg_cost = float(holding.avg_cost) / ratio
            holding.split_adjusted_at = now
            s.flush()
            return SplitAdjustment(
                ticker=ticker,
                quantity=float(holding.quantity),
                avg_cost=float(holding.avg_cost),
                split_adjusted_at=now,
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
        # CR170 §3 — the third and last copy of the P10 ternary. Preview reports
        # what a fill WOULD cost, and after this CR a non-marketable order does
        # not fill at all, so naming the user's own limit as the price was the
        # one answer that could never be right. The mark is the price a fill
        # would book at right now; whether it fills is `submit()`'s branch.
        fill_price = mark
        proposed = ProposedTrade(
            ticker=ticker,
            side=side,
            order_type=order_type,
            quantity=quantity,
            limit_price=limit_price,
        )

        # CR101-BE2: same trade-history context as submit() (no `stop` param on
        # preview(), so the proposed trade's own open-risk contribution can't be
        # priced here — an ALREADY-breached existing_open_risk_pct still blocks).
        ctx = self._compliance_context(user_id, portfolio, ticker)

        compliance = check_mandate_compliance(
            proposed,
            portfolio_value=ctx.portfolio_value,
            current_drawdown_pct=ctx.drawdown_pct,
            mandate=mandate,
            halal_universe=halal_universe or default_halal_universe(),
            classification_universe=(
                classification_universe or default_classification_universe()
            ),
            locale_allowed_universe=locale_allowed_universe,
            # CR026: sector-concentration cap bites the preview gate too, so the
            # trade ticket's "would this be allowed?" reflects it. No request socket.
            holdings=portfolio.holdings,
            # CR171 §6 — gross concentration. Without this the floor sees
            # the long leg only and reports a hedged pair as no exposure.
            shorts=portfolio.shorts,
            # DEF149: the proposed ticker must be priced too, or the sector cap
            # cannot value a first-time buy of a name not already held.
            quotes=ctx.quotes,
            sector_map=default_sector_map(),
            last_loss_closed_at=ctx.last_loss_closed_at,
            trade_open_timestamps=ctx.trade_open_timestamps,
            existing_open_risk_pct=ctx.existing_open_risk_pct,
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

    def _cover_short_fill(
        self,
        *,
        user_id: UUID,
        portfolio: Portfolio,
        ticker: str,
        quantity: float,
        fill_price: float,
        compliance: ComplianceResult,
        kind: str,
    ) -> SubmitResult | None:
        """A buy that closes a standing short. `None` means "ordinary buy".

        **Whole position or nothing**, the mirror of §1's sell-never-crosses-
        zero: a partial cover blends two exit prices into one realised figure,
        which is the same attribution problem seen from the other end, and
        there is no `avg_cost` column here to hold the blend honestly. The
        refusal names the number that WOULD work, so the sentence is actionable
        rather than a rejection.

        Same shape as the game lane's `_game_short_fill` cover branch — the two
        differ only in the fee (none here) and the table.
        """
        if kind != "training":
            return None
        standing = next((s for s in portfolio.shorts if s.ticker == ticker), None)
        if standing is None:
            return None

        def refuse(sentence: str) -> SubmitResult:
            return SubmitResult(
                accepted=False, trade=None,
                compliance=ComplianceResult(
                    passed=False, violations=[sentence], blocked_by=None,
                ),
                portfolio_snapshot=portfolio,
            )

        if abs(quantity - standing.quantity) > 1e-6:
            return refuse(
                f"you are short {standing.quantity:g} {ticker} — a cover buys "
                f"back the whole position, not {quantity:g}"
            )

        # Aliased on import, not called as `sim_shorts.cover_short(...)`: D9's
        # guard resolves calls by BARE NAME across modules, so the unaliased
        # form collides with `SimEngine.cover_short` — which does reach the
        # network — and makes this method, and `_execute_fill` above it, read
        # as network-reaching. The guard's own docstring names that collision
        # class as the reason it does not attempt httpx detection.
        from app.services.sim_shorts import cover_short as _cover_short_row
        from app.services.sim_shorts import find_open_short as _find_open_short

        with get_session() as s:
            p_row = self._load_portfolio_row(s, user_id)
            if p_row is None:
                return refuse(f"no open short in {ticker} to cover")
            short_row = _find_open_short(s, p_row.id, ticker)
            if short_row is None:
                # Covered between the snapshot and this transaction — by the
                # bracket sweep or the margin pass. Reporting a fill that did
                # not happen is worse than reporting nothing.
                return refuse(f"no open short in {ticker} to cover")
            realised = _cover_short_row(
                s, portfolio_row=p_row, short_row=short_row,
                close_price=fill_price, reason="user",
            )
            s.flush()
            snapshot = _portfolio_from_row(p_row)

        logger.info(
            "sim_short_covered",
            user_id=str(user_id), ticker=ticker, close_price=fill_price,
            reason="user", realised_pnl=realised,
        )
        return SubmitResult(
            accepted=True,
            trade=None,
            compliance=compliance,
            portfolio_snapshot=snapshot,
            short_action="short_cover",
            short_ticker=ticker,
            short_quantity=quantity,
            short_realised_pnl=realised,
        )

    def _open_short_fill(
        self,
        *,
        user_id: UUID,
        portfolio: Portfolio,
        ticker: str,
        quantity: float,
        fill_price: float,
        compliance: ComplianceResult,
        stop: float | None,
        target: float | None,
    ) -> SubmitResult:
        """CR171 §1 — sell to open, in the TRAINING lane.

        Writes a `sim_short_positions` row and NO `sim_trades` row. That is
        acceptance 5 and it is not an omission: `def110_backfill.expected()`
        derives what a portfolio's holdings should be by subtracting Σ quantity
        over open SELL trade rows, so a short with a trade row would make every
        genuine phantom share look accounted for — on the one detector we have
        for the class of bug DEF110 was.
        """
        from app.services.short_borrow_rate import resolve_borrow_rate
        from app.services import sim_shorts

        # §5's inverted-bracket refusal used to live here, short-only. DEF312
        # moved it up to `_execute_fill`, which every fill path crosses and
        # which knows the long case too — the reason the long half was missing
        # for as long as it was is that this function is the only place it was
        # ever written, and this function is unreachable from a buy.

        notional = fill_price * quantity
        needed = sim_shorts.cash_required_for(notional)
        if needed > portfolio.current_cash + 1e-6:
            return SubmitResult(
                accepted=False, trade=None,
                compliance=ComplianceResult(
                    passed=False,
                    violations=[
                        f"insufficient cash to post margin on this short: need "
                        f"${needed:.2f}, have ${portfolio.current_cash:.2f}"
                    ],
                    blocked_by=None,
                ),
                portfolio_snapshot=portfolio,
            )

        # Resolved ONCE, here, and stored with its provenance. Never re-read
        # daily — §4's input updates monthly, and re-reading it every day
        # manufactures the appearance of a live rate.
        borrow = resolve_borrow_rate(ticker)

        with get_session() as s:
            p_row = self._load_portfolio_row(s, user_id)
            assert p_row is not None
            if sim_shorts.find_open_short(s, p_row.id, ticker) is not None:
                return SubmitResult(
                    accepted=False, trade=None,
                    compliance=ComplianceResult(
                        passed=False,
                        violations=[
                            f"you already hold a short in {ticker} — close it "
                            f"before opening another"
                        ],
                        blocked_by=None,
                    ),
                    portfolio_snapshot=portfolio,
                )
            sim_shorts.open_short(
                s,
                portfolio_row=p_row,
                user_id=user_id,
                ticker=ticker,
                quantity=quantity,
                fill_price=fill_price,
                borrow=borrow,
                stop=stop,
                target=target,
            )
            s.flush()

        logger.info(
            "sim_short_opened",
            user_id=str(user_id),
            ticker=ticker,
            quantity=quantity,
            entry=fill_price,
            cash_posted=sim_shorts.cash_required_for(notional),
            borrow_rate_pct=borrow.rate_pct,
            borrow_rate_source=borrow.source,
        )
        return SubmitResult(
            accepted=True,
            trade=None,
            compliance=compliance,
            portfolio_snapshot=self.ensure_portfolio(user_id),
            short_action="short_open",
            short_ticker=ticker,
            short_quantity=quantity,
        )

    def open_shorts(self, user_id: UUID) -> list[SimShortPositionRow]:
        """Every open training short, detached enough to read outside a session
        — the sweep needs ticker/quantity/rate, never a live ORM handle."""
        from app.services import sim_shorts  # noqa: F401  (schema registration)

        with get_session() as s:
            p_row = self._load_portfolio_row(s, user_id)
            if p_row is None:
                return []
            rows = s.execute(
                select(SimShortPositionRow).where(
                    SimShortPositionRow.portfolio_id == p_row.id,
                    SimShortPositionRow.state == "open",
                )
            ).scalars().all()
            for r in rows:
                s.expunge(r)
            return list(rows)

    def shorts_snapshot(
        self, user_id: UUID, *, closed_within_days: int = 7,
    ) -> tuple[list[SimShortPositionRow], list[SimShortPositionRow]]:
        """`(open, recently closed)`, both detached, in ONE session.

        Two lists out of one hop rather than two calls, because the portfolio
        route pays a thread hop per synchronous read and these are the same
        indexed table. No quote fan-out here — the caller already holds marks
        for every short's ticker (`_marked_tickers`), so pricing this list
        costs nothing extra.
        """
        from app.services import sim_shorts

        since = datetime.now(timezone.utc) - timedelta(days=closed_within_days)
        with get_session() as s:
            p_row = self._load_portfolio_row(s, user_id)
            if p_row is None:
                return [], []
            open_rows = s.execute(
                select(SimShortPositionRow)
                .where(
                    SimShortPositionRow.portfolio_id == p_row.id,
                    SimShortPositionRow.state == "open",
                )
                .order_by(SimShortPositionRow.opened_at.asc())
            ).scalars().all()
            closed_rows = sim_shorts.recently_closed_for_portfolio(
                s, p_row.id, since=since,
            )
            for r in (*open_rows, *closed_rows):
                s.expunge(r)
            return list(open_rows), list(closed_rows)

    def evaluate_short_brackets(self, user_id: UUID) -> list[str]:
        """§5 — a short's stop is ABOVE entry and its target BELOW.

        Returns the tickers closed. Separate from `evaluate_outcomes` because
        it reads a different table, but it shares `bracket_hit`, so "which way
        does this position want the price to go" is written down once.
        """
        from app.services import sim_shorts

        closed: list[str] = []
        with get_session() as s:
            p_row = self._load_portfolio_row(s, user_id)
            if p_row is None:
                return closed
            rows = s.execute(
                select(SimShortPositionRow).where(
                    SimShortPositionRow.portfolio_id == p_row.id,
                    SimShortPositionRow.state == "open",
                )
            ).scalars().all()
            for row in rows:
                mark = self.current_price(row.ticker)
                hit = bracket_hit(
                    is_short=True,
                    mark=mark,
                    stop=float(row.stop) if row.stop is not None else None,
                    target=float(row.target) if row.target is not None else None,
                )
                if hit is None:
                    continue
                sim_shorts.cover_short(
                    s,
                    portfolio_row=p_row,
                    short_row=row,
                    close_price=mark,
                    reason="stop" if hit == "lost" else "target",
                )
                closed.append(row.ticker)
            s.flush()
        return closed

    def accrue_short_borrow(
        self, user_id: UUID, *, on_date: str,
    ) -> float:
        """§4 — the daily borrow charge. Returns the total charged.

        `on_date` is an ISO date and is the **idempotency key**: a row already
        stamped with it is skipped, so running the pass twice in one day charges
        once and a container restart mid-day cannot double-charge. Same shape as
        `portfolio_nav_daily`'s guard, and it is a stored date rather than an
        elapsed-time comparison for the same reason — elapsed time is a
        different value on every restart.

        NOT market-hours gated: borrow accrues on calendar days, including the
        weekend a position is held over. That is one of the few carrying costs a
        simulator can teach honestly, and gating it on the session would quietly
        make weekends free.
        """
        from app.services.short_borrow_rate import daily_borrow_fee

        charged = 0.0
        with get_session() as s:
            p_row = self._load_portfolio_row(s, user_id)
            if p_row is None:
                return 0.0
            rows = s.execute(
                select(SimShortPositionRow).where(
                    SimShortPositionRow.portfolio_id == p_row.id,
                    SimShortPositionRow.state == "open",
                )
            ).scalars().all()
            for row in rows:
                if row.last_borrow_accrual_date == on_date:
                    continue
                fee = daily_borrow_fee(
                    mark=self.current_price(row.ticker),
                    quantity=float(row.quantity),
                    rate_pct=float(row.borrow_rate_pct),
                )
                row.borrow_accrued_total = round(
                    float(row.borrow_accrued_total) + fee, 2,
                )
                row.last_borrow_accrual_date = on_date
                # Burned, like the games fee: deducted from this portfolio and
                # credited to nothing.
                p_row.current_cash = round(float(p_row.current_cash) - fee, 2)
                charged = round(charged + fee, 2)
            s.flush()
        return charged

    def force_close_breached_shorts(self, user_id: UUID) -> list[str]:
        """§7 — the margin call. Returns the tickers force-closed.

        **No warning, no grace period.** A grace period needs a notification
        channel, a timer and a second state, and a user asleep in Riyadh could
        not act on it anyway. Close immediately and report it clearly — a
        position that vanished overnight with no explanation is the games lane's
        *"the order simply VANISHED"* defect on a much bigger number, which is
        why the close stamps `close_reason='margin'` rather than looking like
        any other exit.

        The caller gates this on market hours (§7): a margin close against a
        stale overnight print is CR109 §5.1's time machine in the direction that
        costs the user money.
        """
        from app.services import sim_shorts

        closed: list[str] = []
        with get_session() as s:
            p_row = self._load_portfolio_row(s, user_id)
            if p_row is None:
                return closed
            rows = s.execute(
                select(SimShortPositionRow).where(
                    SimShortPositionRow.portfolio_id == p_row.id,
                    SimShortPositionRow.state == "open",
                )
            ).scalars().all()
            for row in rows:
                mark = self.current_price(row.ticker)
                if not sim_shorts.is_margin_breached(row, mark):
                    continue
                realised = sim_shorts.cover_short(
                    s,
                    portfolio_row=p_row,
                    short_row=row,
                    close_price=mark,
                    reason="margin",
                )
                closed.append(row.ticker)
                logger.warning(
                    "sim_short_margin_closed",
                    user_id=str(user_id),
                    ticker=row.ticker,
                    mark=mark,
                    ratio=round(sim_shorts.margin_ratio(row, mark), 4),
                    realised_pnl=realised,
                )
            s.flush()
        return closed

    def cover_short(
        self,
        *,
        user_id: UUID,
        ticker: str,
        reason: str = "user",
        mark: float | None = None,
    ) -> SubmitResult | None:
        """Buy to cover, in full. None when no open short exists on the ticker.

        Whole position only — matching §1's sell-never-crosses-zero symmetry.
        A partial cover would blend two exit prices into one realised figure,
        the same attribution problem, from the other end.
        """
        from app.services import sim_shorts

        close_price = mark if mark is not None else self.current_price(ticker)
        with get_session() as s:
            p_row = self._load_portfolio_row(s, user_id)
            if p_row is None:
                return None
            row = sim_shorts.find_open_short(s, p_row.id, ticker)
            if row is None:
                return None
            quantity = float(row.quantity)
            realised = sim_shorts.cover_short(
                s,
                portfolio_row=p_row,
                short_row=row,
                close_price=close_price,
                reason=reason,
            )
            s.flush()

        logger.info(
            "sim_short_covered",
            user_id=str(user_id),
            ticker=ticker,
            close_price=close_price,
            reason=reason,
            realised_pnl=realised,
        )
        return SubmitResult(
            accepted=True,
            trade=None,
            compliance=ComplianceResult(passed=True),
            portfolio_snapshot=self.ensure_portfolio(user_id),
            short_action="short_cover",
            short_ticker=ticker,
            short_quantity=quantity,
            short_realised_pnl=realised,
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

        DEF316 moved that decision one level up: `evaluate_outcomes` and
        `manual_close` now ask `_held_quantity` (same `s.deleted` exclusion)
        before transitioning a row at all, because crediting no cash was only
        half right — the row still transitioned, and a transitioned buy row
        drops out of `expected()` while its sell row keeps subtracting. So the
        `h in s.deleted` skip below is a **backstop** at a helper three paths
        share, not the live guard against phantom cash. Read it as the former.
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
        self._retire_orphaned_resting_sells(s, p_row, ticker)
        return sold

    @staticmethod
    def _held_quantity(s, p_row: SimPortfolioRow, ticker: str) -> float:
        """Shares of `ticker` still on the books, correct MID-transaction.

        `h not in s.deleted` is the whole reason this is a function rather than
        a sum written at each call site: `evaluate_outcomes` closes several
        trades against one holding in a single pass, and a holding deleted
        earlier in that pass is still present in `p_row.holdings` until the
        session expires it. Two places now decide "is this position flat" —
        DEF311's resting-sell retirement and DEF316's bracket gate — and they
        must not answer it differently (DEF098's shape).
        """
        return sum(
            float(h.quantity) for h in p_row.holdings
            if h.ticker == ticker and h not in s.deleted
        )

    @staticmethod
    def _retire_orphaned_resting_sells(s, p_row: SimPortfolioRow, ticker: str) -> int:
        """DEF311 — a resting sell must not outlive the shares it was selling.

        **This is where a stop-loss turned into a short.** Nothing connected the
        two: `SimRestingOrderRow` was touched in five places in this engine —
        reset, placement, list, cancel, `clear()` — and neither `manual_close`
        nor this function was one of them. So:

          1. Hold 10 NVDA. Rest a sell stop, 10 @ $90.
          2. Close the position (or let the bracket close it). Holdings → 0.
             The order is untouched and still `working`.
          3. Price reaches $90. The sweep fills it, `_execute_fill` sees
             `held == 0`, and the three-case rule opens a **short**.

        The user's stop-loss becomes a short position with unbounded loss, in an
        account they believe is flat, and CR187 pushes them *"Sold 10 NVDA at
        $90.00"* — which reads exactly like the stop working.

        Retiring at the **chokepoint every share reduction crosses** rather than
        in `manual_close` is the point: `manual_close`, `evaluate_outcomes` and
        the sell path of `_execute_fill` all reduce a holding through here, and a
        fix in any one of them would have left the other two.

        `filling` is deliberately not retired — an order the sweep has claimed is
        mid-fill and is the very sell that brought us here.

        Not covered, and named rather than left implied: the mirror on the buy
        side, where covering a short by hand leaves a resting buy that opens a
        fresh long. Different path (`cover_short`), and the failure is a position
        the user pays cash for rather than one with unbounded loss.
        """
        remaining = SimEngine._held_quantity(s, p_row, ticker)
        rows = s.execute(
            select(SimRestingOrderRow).where(
                SimRestingOrderRow.portfolio_id == p_row.id,
                SimRestingOrderRow.ticker == ticker,
                SimRestingOrderRow.side == "sell",
                SimRestingOrderRow.state.in_(LIVE_RESTING_STATES),
            )
        ).scalars().all()

        retired = 0
        now = datetime.now(timezone.utc)
        for row in rows:
            if float(row.quantity) <= remaining + 1e-9:
                continue
            reason = (
                f"cancelled — you no longer hold enough {ticker} to sell "
                f"{float(row.quantity):g} (you hold {remaining:g})"
            )
            # `cancelled` + a non-NULL reason. The invariant the client's copy is
            # built on is on the REASON, not the state: non-NULL always means
            # the system did it. `expired` would claim a TIF elapsed and
            # `rejected` would claim it triggered and was refused; neither
            # happened.
            for k, v in retire_values(
                "cancelled", now, cancel_reason=reason,
            ).items():
                setattr(row, k, v)
            retired += 1

        if retired:
            logger.info(
                "sim_resting_sells_retired",
                portfolio_id=str(p_row.id), ticker=ticker,
                remaining=remaining, count=retired,
            )
        return retired

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
            # DEF318 — the FULL ledger, not just the open rows, because a
            # bracket belongs to the shares its own lot still has behind it and
            # only the whole order stream can say how many that is. One query,
            # then the audited FIFO primitive (CR029) decides; this engine does
            # not grow a second notion of "how much of this lot is left".
            all_rows = s.execute(
                select(SimTradeRow)
                .where(training_trade_scope(user_id))
                .order_by(SimTradeRow.opened_at.asc())
            ).scalars().all()
            lot_open = _open_quantity_by_lot(all_rows)
            rows = [r for r in all_rows if r.status == "open"]
            # Once, not per trade: N trades must sell against one live row.
            p_row = self._load_portfolio_row(s, user_id)
            live_lots: dict[str, list[tuple[SimTradeRow, float]]] = defaultdict(list)
            for t in rows:
                side = t.side
                side_enum = Side(side) if not isinstance(side, Side) else side
                # CR171 §5 — this gate stays. A SELL row in `sim_trades` is an
                # EXIT, so its levels are meaningless and firing on them would
                # close a position twice. Shorts do not live in this table at
                # all (they are `sim_short_positions`), and their inverted
                # bracket is evaluated in `evaluate_short_brackets` below,
                # through the same `bracket_hit` comparison.
                if side_enum != Side.BUY:
                    continue
                # DEF316 — a bracket belongs to SHARES, not to the row that
                # bought them. Selling through the ticket reduces the holding
                # and writes its own SELL row; it deliberately leaves this BUY
                # row `open`, because `def110_backfill.py`'s `expected()` is
                # (Σ open buys − Σ open sells) and closing it here would
                # subtract the same exit twice. So the row outlives its
                # position by design — and used to keep its stop/target live,
                # which meant the sweep would later "stop out" shares that were
                # already sold: the exit counted twice after all, `expected()`
                # driven negative, and the user shown a WON/LOST outcome at
                # $0.00 realised on a position they had exited days earlier
                # ($0.00 because `_apply_sell_row` clamps to a holding that is
                # gone). Same shape as DEF311 one layer in — that fix retired
                # the orphaned RESTING sell at the share-reduction chokepoint
                # and left the trade row's OWN bracket connected to nothing.
                #
                # Checked before `current_price` deliberately: a stale row must
                # not cost a quote on every sweep, forever.
                #
                # DEF318 narrowed this from the TICKER to the LOT. "Is the
                # ticker flat" is right when the user exited and blind when they
                # re-entered — a dead lot's stop then fires against the shares a
                # later lot bought. `lot_open` answers per lot, off the audited
                # FIFO reconstruction.
                #
                # Both gates stay, because they read different sources and
                # disagreeing is itself the signal: `lot_open` is the trade
                # LEDGER's view, `_held_quantity` is what `sim_holdings`
                # actually carries, and a gap between them is the exact
                # phantom-share condition `def110_backfill.py` exists to find.
                lot_left = lot_open.get(str(t.id), 0.0)
                if lot_left <= 1e-6:
                    continue
                live_lots[t.ticker].append((t, lot_left))

            # CR189 — the bracket is evaluated per POSITION, not per row. Two
            # lots of the same name have two stops and a tile has room for one,
            # and a tile showing a blended $97 while the sweep still fires $95
            # and $99 is lying about a risk control. One level, weighted by
            # shares still open; the sweep and the screen read the same number.
            for ticker, entries in live_lots.items():
                if p_row is not None and self._held_quantity(s, p_row, ticker) <= 1e-6:
                    continue
                stop, target = blended_bracket(
                    _lot_brackets((t for t, _ in entries), lot_open),
                )
                if stop is None and target is None:
                    continue
                # After the gates, so an unprotected or fully-exited position
                # never costs a quote.
                price = self.current_price(ticker)
                new_status: TradeStatus | None = bracket_hit(  # type: ignore[assignment]
                    is_short=False, mark=price, stop=stop, target=target,
                )
                if new_status is None:
                    continue
                # The trigger is shared; the P&L is not. Every live lot closes,
                # each realising against its OWN entry price, so a $110 lot and a
                # $95 lot exiting at $97 record a loss and a gain respectively
                # while both carry the position's status — the POSITION was
                # stopped out, which is the fact `won`/`lost` is describing.
                for t, lot_left in entries:
                    self._close_lot(s, p_row, t, price, new_status, lot_left, updates)
            s.flush()
        return updates

    def _close_lot(
        self, s, p_row, t: SimTradeRow, price: float, new_status: str,
        lot_left: float, updates: list[OutcomeUpdate],
    ) -> None:
        """Liquidate one live lot at `price` and record it. CR189 split this out
        of `evaluate_outcomes` when a single bracket hit began closing N lots."""
        t.status = new_status
        t.closed_at = datetime.now(timezone.utc)
        t.closed_price = price
        # DEF166: a clamped close (the holding has fewer shares than
        # `t.quantity` requests — see `_apply_sell_row`) must stamp
        # `realised_pnl` on the shares actually sold, or the P&L and the cash
        # movement disagree about how many shares moved.
        #
        # DEF318: capped at the LOT's remaining shares as well, not just the
        # row's original quantity. A lot half-consumed by an earlier sell
        # (bought 10, 6 already sold) would otherwise close for 10 and eat 6
        # shares belonging to a later lot — the same wrong-shares defect as the
        # gate above, one step further in.
        sold = (
            self._apply_sell_row(
                s, p_row, t.ticker, min(float(t.quantity), lot_left), price,
            )
            if p_row is not None else min(float(t.quantity), lot_left)
        )
        t.realised_pnl = round((price - float(t.entry_price)) * sold, 2)
        updates.append(OutcomeUpdate(
            trade_id=t.id, new_status=new_status,  # type: ignore[arg-type]
            closed_price=price, realised_pnl=float(t.realised_pnl),
        ))

    def manual_close(self, user_id: UUID, trade_id: UUID) -> SimTrade | None:
        with get_session() as s:
            row = s.execute(
                select(SimTradeRow).where(
                    training_trade_scope(user_id),
                    SimTradeRow.id == trade_id,
                    SimTradeRow.status == "open",
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            p_row = self._load_portfolio_row(s, user_id)
            # DEF316 — the same gate as `evaluate_outcomes`, for the same
            # reason, and this is the path that actually left the residue:
            # pre-DEF269 this reached across lanes and stamped three GAME buy
            # rows `closed` against the TRAINING portfolio, which held none of
            # those tickers. `_apply_sell_row` clamped to zero, so each row
            # recorded a close that moved no shares and no cash — and 2,317
            # shares of `expected()` went permanently negative behind them.
            # Returning None maps onto the route's existing 404 copy ("trade
            # not found or already closed"), which is the true statement: the
            # position IS already closed, this row just never recorded it.
            if p_row is not None and self._held_quantity(s, p_row, row.ticker) <= 1e-6:
                return None
            price = self.current_price(row.ticker)
            row.status = "closed"
            row.closed_at = datetime.now(timezone.utc)
            row.closed_price = price
            # DEF166: a clamped close (the holding has fewer shares than
            # `row.quantity` requests — see `_apply_sell_row`) must stamp
            # `realised_pnl` on the shares actually sold, or the P&L and
            # the cash movement disagree about how many shares moved.
            sold = (
                self._apply_sell_row(s, p_row, row.ticker, float(row.quantity), price)
                if p_row is not None else float(row.quantity)
            )
            row.realised_pnl = round((price - float(row.entry_price)) * sold, 2)
            s.flush()
            return SimTrade.from_row(row)

    def clear(self) -> None:
        with get_session() as s:
            s.execute(delete(PortfolioValueSnapshotRow))
            s.execute(delete(SimShortPositionRow))
            s.execute(delete(SimRestingOrderRow))
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
