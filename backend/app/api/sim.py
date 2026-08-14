"""Sim Trading endpoints.

GET  /v1/sim/portfolio/{user_id}             Snapshot (cash + holdings + marks + P&L)
GET  /v1/sim/portfolio/{user_id}/history     Daily NAV series + window TWR (CR109 slice 1)
POST /v1/sim/portfolio/{user_id}/reset       Wipe and restart with $10k
POST /v1/sim/preview                         Dry-run a trade (compliance + cash check, no persist) — BL9
POST /v1/sim/submit                          Submit a trade (PM safety floor runs)
GET  /v1/sim/trades/{user_id}                List trades (filterable by status)
POST /v1/sim/trades/{user_id}/evaluate       Sweep open trades for stop/target hits
POST /v1/sim/trades/{user_id}/close          Manually close an open trade
GET  /v1/sim/lots/{user_id}/{ticker}         Per-lot cost-basis + FIFO realised/unrealised P&L (CR029)
GET  /v1/sim/quote/{ticker}                  Current quote (price + change_pct + market_state)
GET  /v1/sim/quotes?symbols=AAPL,MSFT,...    Batch quotes for ticker tape
GET  /v1/sim/history/{ticker}?period=1m      OHLCV candles for the ticker-detail chart (Bundle 2)
GET  /v1/sim/news/{ticker}?limit=5           Recent news articles for ticker (Bundle 4)
GET  /v1/sim/earnings/{ticker}               Upcoming earnings info within 90 days (Bundle 5)
"""

from __future__ import annotations

import asyncio
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select

from app.core.config import settings
from app.schemas.classification import ClassificationVerdict
from app.schemas.journal import EntryType, JournalEntryCreate, Outcome
from app.schemas.sharia import ShariaVerdict
from app.schemas.trade import OrderType, Side
from app.services.journal_store import get_journal_store
from app.services.mandate_store import resolve_mandate
from app.services.market_data import VALID_PERIODS
from app.services.portfolio_nav_daily import nav_history, twr_pct_for_window
from app.services.classification_universe import default_classification_universe_async
from app.services.sharia_universe import default_halal_universe_async
from app.services.sim_engine import (
    RESTING_ORDER_TIFS,
    SimEngine,
    SimTrade,
    get_sim_engine,
)
from app.services.sim_resting_orders import (
    bracket_closing_enabled,
    commitment_for,
    sweep_resting_orders,
)
from app.services.sim_trade_effects import apply_post_fill_effects
from app.services.ticker_reference import (
    TickerNotFoundError,
    require_ticker_exists,
    ticker_not_found_detail,
)
from app.api.dependencies import get_current_user
from app.db import get_session
from app.db.models import SimPortfolioRow, User


router = APIRouter(prefix="/v1/sim", tags=["sim"])


def _own(current_user: User, user_id: UUID) -> None:
    if current_user.id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "access denied")


def _require_ticker_or_422(ticker: str) -> None:
    """CR128 guard shared by preview + submit. Defense in depth — the client
    already checked via GET /v1/tickers/validate, so this only fires for a
    stale client or a direct API call."""
    try:
        with get_session() as session:
            require_ticker_exists(session, ticker)
    except TickerNotFoundError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail=ticker_not_found_detail(exc)
        ) from exc


class SubmitTradeRequest(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    user_id: UUID
    ticker: str
    side: Side = Side.BUY
    # CR170 §8 — `Field(gt=0)` was missing here and present at
    # `api/games.py:120`, whose own defect narrative is about zero-share orders
    # being accepted and reported as placed. One rule, one site swept — P11.
    quantity: float = Field(gt=0)
    order_type: OrderType = OrderType.MARKET
    limit_price: float | None = None
    trigger_price: float | None = None
    tif: str = "day"
    stop: float | None = None
    target: float | None = None
    horizon_days: int | None = None
    verdict_ref: UUID | None = None
    mandate_override: dict | None = None

    @model_validator(mode="after")
    def _prices_match_the_order_type(self) -> "SubmitTradeRequest":
        """CR170 §1 — 422 rather than a resting order that names no price.

        | order_type   | trigger_price | limit_price     |
        |--------------|---------------|-----------------|
        | `market`     | —             | —               |
        | `limit`      | —             | required, > 0   |
        | `stop`       | required, > 0 | —               |
        | `stop_limit` | required, > 0 | required, > 0   |

        Structural rather than a default, because the failure it prevents is an
        order that rests forever against a price nobody set — the shape CR040
        calls degrading silently.
        """
        ot = (
            self.order_type if isinstance(self.order_type, OrderType)
            else OrderType(self.order_type)
        )
        if ot in (OrderType.STOP, OrderType.STOP_LIMIT):
            if self.trigger_price is None or self.trigger_price <= 0:
                raise ValueError(f"{ot.value} order requires a trigger_price > 0")
        if ot in (OrderType.LIMIT, OrderType.STOP_LIMIT):
            if self.limit_price is None or self.limit_price <= 0:
                raise ValueError(f"{ot.value} order requires a limit_price > 0")
        if ot == OrderType.MARKET and self.tif != "day":
            raise ValueError("a market order has no time in force — it fills now")
        if self.tif not in RESTING_ORDER_TIFS:
            raise ValueError(
                f"unknown time in force '{self.tif}' — "
                f"expected one of {sorted(RESTING_ORDER_TIFS)}"
            )
        return self


class CancelRestingOrderResponse(BaseModel):
    """The SERVER's verdict, never the client's assumption.

    Carries `cancelled` **and** the resulting state, because a cancel can lose
    the race with a sweep. The games lane shipped `status ?? 'filled'` in build
    74 and had to fix it; this one is explicit from the start.
    """

    cancelled: bool
    state: str
    order: dict | None = None


class ShortPositionOut(BaseModel):
    """CR171 — one OPEN training short, priced.

    Typed rather than a hand-built dict (the reasoning `ComplianceBlock` records):
    an untyped member is a member the generated OpenAPI does not carry, and this
    schema is the artefact the client mirrors by hand.

    `leg_value` is **not** a market value — a short has none. It is §2's
    contribution to portfolio value: the cash that left, plus the move.
    Rendering `quantity × mark` here instead would show a growing number as the
    position went AGAINST the user.

    `margin_ratio` is `None`, never a sentinel number, when the mark is not
    positive and the ratio is therefore undefined. `float('inf')` is not JSON,
    and a stand-in like 999 is a number a client would happily render.
    """

    id: UUID
    ticker: str
    quantity: float
    entry_price: float
    mark: float
    leg_value: float
    unrealised_pnl: float
    cash_posted: float
    collateral_posted: float
    borrow_rate_pct: float
    borrow_rate_source: str
    borrow_accrued_total: float
    margin_ratio: float | None = None
    # Shipped alongside the ratio so the client compares against the server's
    # threshold rather than a second copy of 1.30 that can drift (DEF098).
    maintenance_margin: float
    stop: float | None = None
    target: float | None = None
    opened_at: datetime


class ClosedShortOut(BaseModel):
    """CR171 §7 — a short that closed inside the reporting window.

    Exists so *"the close is reported, never silent"* holds where the user can
    read it. `close_reason` is the load-bearing field: `margin` means the
    account took the decision away, and a position that vanished with no such
    sentence is indistinguishable from a bug.
    """

    id: UUID
    ticker: str
    quantity: float
    entry_price: float
    close_price: float | None = None
    # user | margin | stop | target
    close_reason: str | None = None
    realised_pnl: float | None = None
    borrow_accrued_total: float
    closed_at: datetime | None = None


class PortfolioSnapshot(BaseModel):
    user_id: UUID
    portfolio_id: UUID
    starting_capital: float
    current_cash: float
    holdings: list[dict]
    total_value: float
    drawdown_pct: float
    # Truthful aggregate source across the user's holdings — surfaced so
    # the iPhone can show a LIVE / MOCK pill next to the marks. Reports
    # the leaf provider that actually served the prices ("yahoo" or
    # "mock_walk"), NOT the configured stack name. "yahoo" only when
    # 100% of holdings were priced from Yahoo this snapshot — any
    # fall-through to mock_walk on any ticker downgrades the snapshot
    # to "mock_walk" so the LIVE pill never lies. See
    # `SimEngine.aggregate_source`.
    price_source: str = "mock_walk"

    # CR170 §6 — what the live resting book ties up. Computed at read time,
    # never reserved: a reserved-cash debit is indistinguishable from a loss in
    # the NAV series. See `sim_resting_orders.RestingCommitment` for why.
    #
    # `cash_available` is `current_cash - cash_committed` and is the number a
    # ticket must size against. It is NOT floored at zero — a negative here
    # means the book is over-committed, which is a real and reachable state
    # (five resting buys against one balance, FIFO, the loser refused at fill
    # with "insufficient cash: need $X, have $Y"). Clamping it to zero would
    # hide exactly the condition the field exists to show.
    #
    # `cash_committed` for a buy STOP is a floor, not an exact figure: Rule 2
    # fills at the worse of named and observed, so a gap fills above the
    # trigger and ties up more than this reports.
    cash_committed: float = 0.0
    cash_available: float = 0.0
    resting_order_count: int = 0
    shares_committed: dict[str, float] = Field(default_factory=dict)

    # CR171 — the short book. Empty on every portfolio that has never shorted,
    # which is almost all of them, so this costs a nearly-free `[]` in the
    # common case and is the only way the client can see a leg that
    # `total_value` has already been counting since `dd8a4f3f`.
    #
    # `closed_shorts` is windowed (7 days, capped) rather than complete: it is
    # not a trade history, it is §7's report that something closed WITHOUT the
    # user asking. A permanent record of every cover belongs in the trade
    # history surface, not on a polled snapshot.
    shorts: list[ShortPositionOut] = Field(default_factory=list)
    closed_shorts: list[ClosedShortOut] = Field(default_factory=list)


class NavPointOut(BaseModel):
    """One `portfolio_nav_daily` row. `price_source` rides on every point
    (CR040) — a mock-priced day must be visible to the client, never smoothed
    into a curve that reads as fact."""

    as_of_date: date
    nav: float
    cash: float
    price_source: str
    capital_event: str | None = None


class PortfolioHistoryResponse(BaseModel):
    user_id: UUID
    points: list[NavPointOut]
    # Chain-linked TWR over `points`, percent, 2dp. None below two points —
    # see `trading_math.twr.time_weighted_return`.
    twr_pct: float | None = None


class TradeListResponse(BaseModel):
    trades: list[dict]


class ComplianceBlock(BaseModel):
    """The wire shape of `ComplianceResult` (DEF094 + DEF112): declared here as a
    response-model field, not a hand-built dict, so `sharia_verdict` and
    `classification_verdicts` are typed members of the schema instead of silently
    dropped on serialization — and so `ShariaVerdict` / `ClassificationVerdict` are
    registered in the generated OpenAPI, the artefact coder.mobile mirrors by hand."""

    passed: bool
    violations: list[str] = Field(default_factory=list)
    blocked_by: str | None = None
    sharia_verdict: ShariaVerdict | None = None
    classification_verdicts: list[ClassificationVerdict] = Field(default_factory=list)
    # CR171 §6 — informational notices on a trade that PROCEEDS. Declared here
    # for the same reason the two verdict fields are: a field that only exists
    # on the service object is a field the client never receives, and an
    # advisory nobody renders informs nobody (CR040).
    advisories: list[str] = Field(default_factory=list)


class PreviewTradeResponse(BaseModel):
    accepted: bool
    compliance: ComplianceBlock
    fill_price: float
    notional: float
    cash_available: float
    held_quantity: float
    price_source: str


def _short_out(row, mark: float | None) -> ShortPositionOut:
    """One open short, priced off the snapshot's own marks.

    Falls back to `entry_price` when the ticker somehow missed the mark pass,
    exactly as the holdings branch above falls back to `avg_cost` — an unpriced
    position reads as flat rather than as a fabricated move. `margin_ratio`
    then reads 1.50-ish (the initial margin) rather than a breach, which is the
    safe direction: a client must never draw a margin call out of a missing
    quote.
    """
    from app.services import sim_shorts
    from app.trading_math.shorts import short_leg

    quantity = float(row.quantity)
    entry = float(row.entry_price)
    price = float(mark) if mark is not None else entry
    ratio = sim_shorts.margin_ratio(row, price)
    return ShortPositionOut(
        id=row.id,
        ticker=row.ticker,
        quantity=quantity,
        entry_price=entry,
        mark=price,
        leg_value=round(short_leg(float(row.cash_posted), quantity, entry, price), 2),
        unrealised_pnl=round((entry - price) * quantity, 2),
        cash_posted=float(row.cash_posted),
        collateral_posted=float(row.collateral_posted),
        borrow_rate_pct=float(row.borrow_rate_pct),
        borrow_rate_source=row.borrow_rate_source,
        borrow_accrued_total=float(row.borrow_accrued_total or 0.0),
        margin_ratio=round(ratio, 4) if math.isfinite(ratio) else None,
        maintenance_margin=float(settings.short_maintenance_margin),
        stop=float(row.stop) if row.stop is not None else None,
        target=float(row.target) if row.target is not None else None,
        opened_at=row.opened_at,
    )


def _closed_short_out(row) -> ClosedShortOut:
    return ClosedShortOut(
        id=row.id,
        ticker=row.ticker,
        quantity=float(row.quantity),
        entry_price=float(row.entry_price),
        close_price=float(row.close_price) if row.close_price is not None else None,
        close_reason=row.close_reason,
        realised_pnl=(
            float(row.realised_pnl) if row.realised_pnl is not None else None
        ),
        borrow_accrued_total=float(row.borrow_accrued_total or 0.0),
        closed_at=row.closed_at,
    )


@router.get("/portfolio/{user_id}", response_model=PortfolioSnapshot)
async def get_portfolio(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    sim: SimEngine = Depends(get_sim_engine),
) -> PortfolioSnapshot:
    _own(current_user, user_id)
    # DEF120 D1/D3: one to_thread hop around a single-fetch snapshot, not
    # four independent sync calls each parking the event loop for its own
    # quote pass.
    p, marks, total_value, drawdown_pct, price_source = await asyncio.to_thread(
        sim.portfolio_marks_snapshot, user_id,
    )
    # Its own hop: `commitment_for` is a synchronous DB read, and the D9 guard
    # exists because a sync session call on the event loop parks every other
    # request behind it. No quote fan-out here — a resting order names its own
    # price — so this is one indexed SELECT, not a second market-data pass.
    commitment = await asyncio.to_thread(commitment_for, user_id)
    # CR171 — one more indexed read, on the same no-quote terms: `marks` above
    # already priced every short's ticker (`SimEngine._marked_tickers`), so
    # this hop adds a SELECT, not a market-data pass.
    open_shorts, closed_shorts = await asyncio.to_thread(sim.shorts_snapshot, user_id)
    return PortfolioSnapshot(
        user_id=user_id,
        portfolio_id=p.id,
        starting_capital=p.starting_capital,
        current_cash=p.current_cash,
        holdings=[
            {
                "ticker": h.ticker,
                "quantity": h.quantity,
                "avg_cost": h.avg_cost,
                "mark": marks.get(h.ticker, h.avg_cost),
                "value": marks.get(h.ticker, h.avg_cost) * h.quantity,
                "unrealised_pnl": round(
                    (marks.get(h.ticker, h.avg_cost) - h.avg_cost) * h.quantity, 2,
                ),
                "opened_at": h.opened_at.isoformat(),
            }
            for h in p.holdings
        ],
        total_value=total_value,
        drawdown_pct=drawdown_pct,
        price_source=price_source,
        cash_committed=commitment.cash_committed,
        cash_available=round(p.current_cash - commitment.cash_committed, 2),
        resting_order_count=commitment.resting_order_count,
        shares_committed=commitment.shares_committed,
        shorts=[_short_out(r, marks.get(r.ticker)) for r in open_shorts],
        closed_shorts=[_closed_short_out(r) for r in closed_shorts],
    )


@router.get("/portfolio/{user_id}/history", response_model=PortfolioHistoryResponse)
async def get_portfolio_history(
    user_id: UUID,
    # Bounded, not bare: a negative `limit` is a silent no-op in SQLite (the
    # test fixture) and an error in Postgres (Alpha), so an unvalidated one
    # is a defect the unit suite structurally cannot see.
    limit: int = Query(365, ge=1, le=3650),
    current_user: User = Depends(get_current_user),
) -> PortfolioHistoryResponse:
    """CR109 slice 1 — the training portfolio's NAV series + its window TWR.

    `run_id` stays NULL: this endpoint only ever reads the TRAINING
    portfolio (see `PortfolioNavDailyRow`'s docstring) — a game run's history
    is a slice-2+ surface, on the same table. Pure DB read, no quote fetch,
    so unlike the handlers above this stays sync (matches `list_trades`).
    """
    _own(current_user, user_id)
    rows = nav_history(user_id, run_id=None, limit=limit)
    return PortfolioHistoryResponse(
        user_id=user_id,
        points=[
            NavPointOut(
                as_of_date=r.as_of_date,
                nav=float(r.nav),
                cash=float(r.cash),
                price_source=r.price_source,
                capital_event=r.capital_event,
            )
            for r in rows
        ],
        twr_pct=twr_pct_for_window(rows),
    )


@router.post("/portfolio/{user_id}/reset", response_model=PortfolioSnapshot)
async def reset_portfolio(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    sim: SimEngine = Depends(get_sim_engine),
) -> PortfolioSnapshot:
    _own(current_user, user_id)
    # CR004: 24h cooldown. Reset recreates the portfolio, so its
    # created_at IS the last-reset time — no extra column needed.
    # CR109 slice 2: scoped to kind="training" — a user can now also hold
    # GAME portfolio rows, and `reset_portfolio()`/this cooldown are a
    # training-only concept (`reset_portfolio()` itself is untouched by
    # this CR). Without this scope, a user holding both would make this
    # query raise MultipleResultsFound the moment they also had a game run.
    with get_session() as s:
        row = s.execute(
            select(SimPortfolioRow).where(
                SimPortfolioRow.user_id == user_id,
                SimPortfolioRow.kind == "training",
            )
        ).scalar_one_or_none()
        if row is not None:
            created_at = row.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            elapsed = datetime.now(timezone.utc) - created_at
            cooldown = timedelta(hours=24)
            if elapsed < cooldown:
                retry_after = int((cooldown - elapsed).total_seconds())
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="reset_cooldown",
                    headers={"Retry-After": str(retry_after)},
                )
    sim.reset_portfolio(user_id)
    return await get_portfolio(user_id, current_user=current_user, sim=sim)


@router.post("/preview", response_model=PreviewTradeResponse)
async def preview_trade(
    req: SubmitTradeRequest,
    current_user: User = Depends(get_current_user),
    sim: SimEngine = Depends(get_sim_engine),
) -> PreviewTradeResponse:
    """Dry-run a trade: runs the same mandate + cash/holdings pre-flight
    as /submit but never persists. Lets the mobile trade ticket render
    a 'would this trade be allowed?' + sizing preview before commit.
    """
    if current_user.id != req.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "access denied")
    _require_ticker_or_422(req.ticker)
    mandate = resolve_mandate(req.user_id, req.mandate_override)
    side = req.side if isinstance(req.side, Side) else Side(req.side)
    order_type = (
        req.order_type if isinstance(req.order_type, OrderType)
        else OrderType(req.order_type)
    )
    # Resolved here, not inside the sync engine: the fetch is blocking and
    # this handler owns the event loop (CR069 F3; DEF061 same seam).
    halal_universe = await default_halal_universe_async()
    classification_universe = await default_classification_universe_async()
    # DEF120 D1: sim.preview() reaches SimEngine.current_quote synchronously
    # (mark, compliance quotes) — off the event loop via to_thread.
    pv = await asyncio.to_thread(
        sim.preview,
        user_id=req.user_id,
        ticker=req.ticker,
        side=side,
        quantity=req.quantity,
        mandate=mandate,
        order_type=order_type,
        limit_price=req.limit_price,
        verdict_ref=req.verdict_ref,
        halal_universe=halal_universe,
        classification_universe=classification_universe,
    )
    return PreviewTradeResponse(
        accepted=pv.accepted,
        compliance=ComplianceBlock(
            passed=pv.compliance.passed,
            violations=pv.compliance.violations,
            blocked_by=pv.compliance.blocked_by,
            sharia_verdict=pv.compliance.sharia_verdict,
            classification_verdicts=pv.compliance.classification_verdicts,
        ),
        fill_price=pv.fill_price,
        notional=pv.notional,
        cash_available=pv.cash_available,
        held_quantity=pv.held_quantity,
        price_source=pv.price_source,
    )


@router.post("/submit")
async def submit_trade(
    req: SubmitTradeRequest,
    current_user: User = Depends(get_current_user),
    sim: SimEngine = Depends(get_sim_engine),
) -> dict:
    if current_user.id != req.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "access denied")
    _require_ticker_or_422(req.ticker)
    mandate = resolve_mandate(req.user_id, req.mandate_override)
    side = req.side if isinstance(req.side, Side) else Side(req.side)
    order_type = (
        req.order_type if isinstance(req.order_type, OrderType)
        else OrderType(req.order_type)
    )
    # Resolved here, not inside the sync engine: the fetch is blocking and
    # this handler owns the event loop (CR069 F3; DEF061 same seam).
    halal_universe = await default_halal_universe_async()
    classification_universe = await default_classification_universe_async()
    # DEF120 D1/acceptance-8: sim.submit() reaches SimEngine.current_quote
    # synchronously AND opens its own `get_session()` — off the event loop
    # via to_thread. The Session is created, used, and closed entirely
    # inside submit()'s body, so it never crosses a thread boundary; only
    # the whole synchronous call is handed to the worker thread.
    result = await asyncio.to_thread(
        sim.submit,
        user_id=req.user_id,
        ticker=req.ticker,
        side=side,
        quantity=req.quantity,
        mandate=mandate,
        order_type=order_type,
        limit_price=req.limit_price,
        trigger_price=req.trigger_price,
        tif=req.tif,
        stop=req.stop,
        target=req.target,
        horizon_days=req.horizon_days,
        verdict_ref=req.verdict_ref,
        halal_universe=halal_universe,
        classification_universe=classification_universe,
    )
    if not result.accepted:
        return {
            "ok": False,
            # CR170 §8 — on EVERY branch, including this one. The client must
            # never have to infer it from which of `trade`/`order` is null.
            "resting": False,
            "compliance": _compliance_json(result.compliance),
        }

    if result.resting:
        order = result.resting_order
        assert order is not None
        return {
            "ok": True,
            "resting": True,
            "trade": None,
            "order": order.to_json(),
            "compliance": _compliance_json(result.compliance),
        }

    # CR171 §1 — a sell-to-open writes NO `sim_trades` row (acceptance 5), so
    # there is no trade to return and none of the three post-fill effects
    # applies: there is nothing to add to the watchlist (a short is not a name
    # you are following), nothing to journal against a trade id, and
    # `trade_disciplined` is an award for bracketing a LONG. Carried on its own
    # branch, explicitly, rather than inferred from `trade is None` — that
    # inference is exactly what `resting` above exists to avoid making.
    if result.short_action is not None:
        return {
            "ok": True,
            "resting": False,
            "trade": None,
            "short": {
                "action": result.short_action,
                "ticker": result.short_ticker,
                "quantity": result.short_quantity,
                "realised_pnl": result.short_realised_pnl,
            },
            "compliance": _compliance_json(result.compliance),
        }

    trade = result.trade
    assert trade is not None

    # CR170 §7 — watchlist + journal + reputation. Properties of a FILL, not of
    # this route: the resting-order sweep reaches the same three effects with no
    # request in the call stack. Extracted before that second fill site exists,
    # so the two paths cannot diverge.
    apply_post_fill_effects(user_id=req.user_id, trade=trade)

    return {
        "ok": True,
        "resting": False,
        "trade": trade.to_json(),
        "compliance": _compliance_json(result.compliance),
    }


@router.get("/orders/{user_id}")
async def list_resting_orders(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    sim: SimEngine = Depends(get_sim_engine),
) -> dict:
    """CR170 §8 — every live order, plus terminal rows from the last 24h.

    Terminal rows are included by default (the games precedent) so a rejected or
    expired order never silently vanishes overnight — the failure the games
    lane's own `list_queued_orders` docstring records as *"from the player's
    side the order simply VANISHED."*

    A pure DB read: `last_seen_price` and `distance_pct` come off the row the
    sweep wrote, so this costs no quote fan-out.

    **This route's existence is load-bearing on the client.** The Flutter build
    treats any error here as "this backend has no book" and keeps the order-type
    picker hidden (`SimState.restingOrdersSupported`), because
    `POST /v1/sim/submit` accepted `order_type=limit` long before it meant
    anything. Removing or renaming this route silently re-hides a shipped
    feature rather than breaking loudly.
    """
    _own(current_user, user_id)
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    orders = await asyncio.to_thread(
        sim.list_resting_orders, user_id, terminal_since=since,
    )
    return {"orders": [o.to_json() for o in orders]}


@router.post("/orders/{user_id}/{order_id}/cancel", response_model=CancelRestingOrderResponse)
async def cancel_resting_order(
    user_id: UUID,
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    sim: SimEngine = Depends(get_sim_engine),
) -> CancelRestingOrderResponse:
    """CR170 §8 — returns the SERVER's verdict, which may be "no".

    A cancel can lose the race with a sweep that already claimed the order, and
    `{"cancelled": false, "state": "filled"}` is the honest answer. The client
    shows the race, not a success toast.
    """
    _own(current_user, user_id)
    cancelled, order = await asyncio.to_thread(
        sim.cancel_resting_order, user_id, order_id,
    )
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "order not found")
    return CancelRestingOrderResponse(
        cancelled=cancelled, state=order.state, order=order.to_json(),
    )


def _compliance_json(compliance) -> dict:
    return {
        "passed": compliance.passed,
        "violations": compliance.violations,
        "blocked_by": compliance.blocked_by,
        "sharia_verdict": (
            compliance.sharia_verdict.model_dump(mode="json")
            if compliance.sharia_verdict is not None else None
        ),
        "classification_verdicts": [
            v.model_dump(mode="json") for v in compliance.classification_verdicts
        ],
        # CR171 §6. `getattr` because this dict is also built from the games
        # lane's compliance object, which has no advisories concept.
        "advisories": list(getattr(compliance, "advisories", []) or []),
    }


@router.get("/trades/{user_id}", response_model=TradeListResponse)
async def list_trades(
    user_id: UUID,
    status_filter: str | None = None,
    current_user: User = Depends(get_current_user),
    sim: SimEngine = Depends(get_sim_engine),
) -> TradeListResponse:
    _own(current_user, user_id)
    trades = sim.list_trades(user_id, status=status_filter)  # type: ignore[arg-type]
    return TradeListResponse(trades=[t.to_json() for t in trades])


@router.post("/trades/{user_id}/evaluate")
async def evaluate_trades(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    sim: SimEngine = Depends(get_sim_engine),
) -> dict:
    _own(current_user, user_id)
    # CR170 §5 — the sweep's SECOND call site, scoped to this user.
    # `SimNotifier.refresh()` calls this route on every app open, which is what
    # makes the resting book feel alive without waiting for the background tick.
    # One trigger implementation, two call sites; the claim-first guard means an
    # app open racing a tick cannot double-fill.
    resting_stats = await asyncio.to_thread(sweep_resting_orders, user_id=user_id)
    # DEF120 D1: evaluate_outcomes() calls current_price per open trade.
    # Runs out of hours too: the sweep above gates its own bracket pass on
    # market hours, and this route is also the path a user's manual refresh
    # takes.
    #
    # DEF305 — but not while the kill switch is off. `SimNotifier.refresh()`
    # hits this on every app open, so gating only the background tick would
    # leave the app-open path closing positions at fabricated prices — the
    # guard would be real and simply not on one of the two paths that move the
    # money, which is the defect itself.
    updates = (
        await asyncio.to_thread(sim.evaluate_outcomes, user_id)
        if bracket_closing_enabled() else []
    )
    # For each closed trade, write a journal entry so the user sees the outcome
    if updates:
        store = get_journal_store()
        trades_by_id = {t.id: t for t in sim.list_trades(user_id)}
        for u in updates:
            t = trades_by_id.get(u.trade_id)
            if not t:
                continue
            try:
                store.append(JournalEntryCreate(
                    user_id=user_id,
                    entry_type=EntryType.SIM_TRADE,
                    reference_id=t.id,
                    title=f"Closed {t.ticker} ({u.new_status.upper()}) — ${u.realised_pnl:+.2f}",
                    summary=(
                        f"{'Target hit' if u.new_status == 'won' else 'Stop hit'} "
                        f"at ${u.closed_price:.2f}."
                    ),
                    ticker=t.ticker,
                    tags=["sim_trade", "closed", u.new_status],
                    outcome=Outcome.WIN if u.new_status == "won" else Outcome.LOSS,
                    payload={"trade": t.to_json()},
                ))
            except Exception:  # pragma: no cover
                pass
    return {
        "ok": True,
        "updates": [
            {
                "trade_id": str(u.trade_id),
                "new_status": u.new_status,
                "closed_price": u.closed_price,
                "realised_pnl": u.realised_pnl,
            }
            for u in updates
        ],
        "resting": resting_stats,
    }


class CloseRequest(BaseModel):
    trade_id: UUID


@router.post("/trades/{user_id}/close")
async def close_trade(
    user_id: UUID,
    req: CloseRequest,
    current_user: User = Depends(get_current_user),
    sim: SimEngine = Depends(get_sim_engine),
) -> dict:
    _own(current_user, user_id)
    # DEF120 D1: manual_close() calls current_price and opens its own
    # get_session() — same thread-hop shape as submit() above.
    closed: SimTrade | None = await asyncio.to_thread(
        sim.manual_close, user_id, req.trade_id,
    )
    if closed is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "trade not found or already closed",
        )
    try:
        get_journal_store().append(JournalEntryCreate(
            user_id=user_id,
            entry_type=EntryType.SIM_TRADE,
            reference_id=closed.id,
            title=f"Closed {closed.ticker} (MANUAL) — ${closed.realised_pnl:+.2f}",
            summary=f"Closed at ${closed.closed_price:.2f}.",
            ticker=closed.ticker,
            tags=["sim_trade", "closed", "manual"],
            outcome=Outcome.WIN if closed.realised_pnl >= 0 else Outcome.LOSS,
            payload={"trade": closed.to_json()},
        ))
    except Exception:  # pragma: no cover
        pass
    return {"ok": True, "trade": closed.to_json()}


@router.get("/lots/{user_id}/{ticker}")
async def get_holding_lots(
    user_id: UUID,
    ticker: str,
    current_user: User = Depends(get_current_user),
    sim: SimEngine = Depends(get_sim_engine),
) -> dict:
    """CR029 — per-lot cost-basis / FIFO realised-P&L for one ticker.

    Read-only reconstruction from the user's own `sim_trades` history: buys
    open lots, `sell` orders draw them down FIFO, self-closed buys (stop /
    target / manual) become fully-closed lots carrying their recorded P&L.
    `unrealised_pnl` on each open lot is marked against the current quote.
    """
    _own(current_user, user_id)
    q = await asyncio.to_thread(sim.current_quote, ticker)
    lots = sim.holding_lots(user_id, ticker, current_price=q.price)
    realised_total = round(sum(lot.realised_pnl for lot in lots), 2)
    unrealised_total = round(
        sum(lot.unrealised_pnl or 0.0 for lot in lots), 2
    )
    open_total = round(sum(lot.quantity_open for lot in lots), 6)
    return {
        "ticker": ticker.upper().strip(),
        "current_price": q.price,
        "price_source": q.source,
        "lots": [lot._asdict() for lot in lots],
        "totals": {
            "realised_pnl": realised_total,
            "unrealised_pnl": unrealised_total,
            "quantity_open": open_total,
        },
    }


@router.get("/quote/{ticker}")
async def quote(
    ticker: str,
    sim: SimEngine = Depends(get_sim_engine),
) -> dict:
    q = await asyncio.to_thread(sim.current_quote, ticker)
    return {
        "ticker": ticker.upper(),
        "price": q.price,
        "source": q.source,
        "change_pct": q.change_pct,
        "market_state": q.market_state,
    }


@router.get("/quotes")
async def quotes_batch(
    symbols: str,
    sim: SimEngine = Depends(get_sim_engine),
) -> list[dict]:
    """Batch quote fetch for the Flutter ticker tape.

    `symbols` is a comma-separated list (e.g. AAPL,MSFT,NVDA).
    Runs each quote in a thread-pool so network I/O overlaps.
    Returns an empty list on empty input.
    """
    tickers = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not tickers:
        return []

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=min(len(tickers), 10)) as pool:
        results: list = await asyncio.gather(
            *[loop.run_in_executor(pool, sim.current_quote, t) for t in tickers]
        )

    return [
        {
            "ticker": ticker,
            "price": q.price,
            "source": q.source,
            "change_pct": q.change_pct,
            "market_state": q.market_state,
        }
        for ticker, q in zip(tickers, results)
    ]


@router.get("/history/{ticker}")
async def history(
    ticker: str,
    period: str = "1m",
    sim: SimEngine = Depends(get_sim_engine),
) -> dict:
    """OHLCV candles for the ticker-detail chart.

    Public — same as `/quote`. Period must be one of:
    1d, 1w, 1m, 3m, 1y, 5y. Response is cached server-side
    for 60s per (ticker, period) in CachingProvider.

    DEF151: the period token is case-normalised before the allow-list check.
    `ticker_chart.dart` labels its chips `1D/1W/1M/3M/1Y/5Y` and sent that
    label verbatim on the wire, so every request 422'd and the chart was dark
    for every ticker on every period — measured 18/18 against live Alpha. Case
    was the entire fault. Normalising here rather than only at the call site is
    deliberate: it repairs the +56/+57 builds already in testers' hands, which
    a client-only fix cannot reach until the next release. The chip label is UI
    copy and stays uppercase; the wire token is a separate concern, and the
    response echoes the canonical form actually served.
    """
    period = (period or "").strip().lower()
    if period not in VALID_PERIODS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"invalid period; must be one of {','.join(VALID_PERIODS)}",
        )
    bars, source = await asyncio.to_thread(sim.current_history, ticker, period)
    return {
        "ticker": ticker.upper(),
        "period": period,
        "source": source,
        "candles": [
            {"t": b.t, "o": b.o, "h": b.h, "l": b.low, "c": b.c, "v": b.v}
            for b in bars
        ],
    }


@router.get("/news/{ticker}")
async def news(
    ticker: str,
    limit: int = 5,
    sim: SimEngine = Depends(get_sim_engine),
) -> dict:
    """Recent news articles for the ticker-detail screen.

    Public — same as /quote and /history. Response cached 5 min
    server-side in CachingProvider. Returns articles: [] when Yahoo
    has no news for the ticker (not an error).
    """
    items, source = await asyncio.to_thread(sim.current_news, ticker, limit)
    return {
        "ticker": ticker.upper(),
        "source": source,
        "articles": [
            {
                "title": a.title,
                "link": a.link,
                "publisher": a.publisher,
                "published_at": a.published_at,
            }
            for a in items
        ],
    }


@router.get("/earnings/{ticker}")
async def earnings(
    ticker: str,
    sim: SimEngine = Depends(get_sim_engine),
) -> dict:
    """Upcoming earnings window within 90 days for the ticker-detail screen.

    Public — same as /quote and /history. Response cached 6 hours
    server-side in CachingProvider. All fields are null when no
    earnings date is announced within 90 days.
    """
    info, source = await asyncio.to_thread(sim.current_earnings, ticker)
    return {
        "ticker": ticker.upper(),
        "source": source,
        "earnings_date": info.earnings_date if info else None,
        "quarter": info.quarter if info else None,
        "eps_estimate": info.eps_estimate if info else None,
        # CR030 — dividend fields; None (chip hidden) for non-payers / no-earnings-window.
        "ex_dividend_date": info.ex_dividend_date if info else None,
        "dividend_rate": info.dividend_rate if info else None,
    }
