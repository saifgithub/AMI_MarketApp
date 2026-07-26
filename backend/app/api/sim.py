"""Sim Trading endpoints.

GET  /v1/sim/portfolio/{user_id}             Snapshot (cash + holdings + marks + P&L)
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
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.schemas.journal import EntryType, JournalEntryCreate, Outcome
from app.schemas.sharia import ShariaVerdict
from app.schemas.trade import OrderType, Side
from app.services.journal_store import get_journal_store
from app.services.mandate_store import resolve_mandate
from app.services.market_data import VALID_PERIODS
from app.services.reputation_service import get_reputation_service
from app.services.classification_universe import default_classification_universe_async
from app.services.sharia_universe import default_halal_universe_async
from app.services.sim_engine import SimEngine, SimTrade, get_sim_engine
from app.services.watchlist_store import get_watchlist_store
from app.api.dependencies import get_current_user
from app.db import get_session
from app.db.models import SimPortfolioRow, User


router = APIRouter(prefix="/v1/sim", tags=["sim"])


def _own(current_user: User, user_id: UUID) -> None:
    if current_user.id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "access denied")


class SubmitTradeRequest(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    user_id: UUID
    ticker: str
    side: Side = Side.BUY
    quantity: float
    order_type: OrderType = OrderType.MARKET
    limit_price: float | None = None
    stop: float | None = None
    target: float | None = None
    horizon_days: int | None = None
    verdict_ref: UUID | None = None
    mandate_override: dict | None = None


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


class TradeListResponse(BaseModel):
    trades: list[dict]


class ComplianceBlock(BaseModel):
    """The wire shape of `ComplianceResult` (DEF094): declared here as a
    response-model field, not a hand-built dict, so `sharia_verdict` is a typed
    member of the schema instead of silently dropped on serialization — and so
    `ShariaVerdict` is registered in the generated OpenAPI, the artefact
    coder.mobile mirrors by hand."""

    passed: bool
    violations: list[str] = Field(default_factory=list)
    blocked_by: str | None = None
    sharia_verdict: ShariaVerdict | None = None


class PreviewTradeResponse(BaseModel):
    accepted: bool
    compliance: ComplianceBlock
    fill_price: float
    notional: float
    cash_available: float
    held_quantity: float
    price_source: str


@router.get("/portfolio/{user_id}", response_model=PortfolioSnapshot)
async def get_portfolio(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    sim: SimEngine = Depends(get_sim_engine),
) -> PortfolioSnapshot:
    _own(current_user, user_id)
    p = sim.ensure_portfolio(user_id)
    tickers = [h.ticker for h in p.holdings]
    marks = sim.current_marks(tickers)
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
        total_value=sim.total_value(user_id),
        drawdown_pct=sim.current_drawdown_pct(user_id),
        price_source=sim.aggregate_source(tickers),
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
    with get_session() as s:
        row = s.execute(
            select(SimPortfolioRow).where(SimPortfolioRow.user_id == user_id)
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
    mandate = resolve_mandate(req.user_id, req.mandate_override)
    side = req.side if isinstance(req.side, Side) else Side(req.side)
    order_type = (
        req.order_type if isinstance(req.order_type, OrderType)
        else OrderType(req.order_type)
    )
    pv = sim.preview(
        user_id=req.user_id,
        ticker=req.ticker,
        side=side,
        quantity=req.quantity,
        mandate=mandate,
        order_type=order_type,
        limit_price=req.limit_price,
        verdict_ref=req.verdict_ref,
        # Resolved here, not inside the sync engine: the fetch is blocking and
        # this handler owns the event loop (CR069 F3; DEF061 same seam).
        halal_universe=await default_halal_universe_async(),
        classification_universe=await default_classification_universe_async(),
    )
    return PreviewTradeResponse(
        accepted=pv.accepted,
        compliance=ComplianceBlock(
            passed=pv.compliance.passed,
            violations=pv.compliance.violations,
            blocked_by=pv.compliance.blocked_by,
            sharia_verdict=pv.compliance.sharia_verdict,
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
    mandate = resolve_mandate(req.user_id, req.mandate_override)
    side = req.side if isinstance(req.side, Side) else Side(req.side)
    order_type = (
        req.order_type if isinstance(req.order_type, OrderType)
        else OrderType(req.order_type)
    )
    result = sim.submit(
        user_id=req.user_id,
        ticker=req.ticker,
        side=side,
        quantity=req.quantity,
        mandate=mandate,
        order_type=order_type,
        limit_price=req.limit_price,
        stop=req.stop,
        target=req.target,
        horizon_days=req.horizon_days,
        verdict_ref=req.verdict_ref,
        # Resolved here, not inside the sync engine: the fetch is blocking and
        # this handler owns the event loop (CR069 F3; DEF061 same seam).
        halal_universe=await default_halal_universe_async(),
        classification_universe=await default_classification_universe_async(),
    )
    if not result.accepted:
        return {
            "ok": False,
            "compliance": {
                "passed": result.compliance.passed,
                "violations": result.compliance.violations,
                "blocked_by": result.compliance.blocked_by,
                "sharia_verdict": (
                    result.compliance.sharia_verdict.model_dump(mode="json")
                    if result.compliance.sharia_verdict is not None else None
                ),
            },
        }

    trade = result.trade
    assert trade is not None

    # Auto-add the traded ticker to the user's watchlist so it shows up
    # in the ticker tape. Idempotent on (user_id, ticker), best-effort.
    try:
        get_watchlist_store().add(req.user_id, trade.ticker)
    except Exception:  # pragma: no cover
        pass

    # Journal capture — sim_trade entry
    try:
        side_label = (
            trade.side.value if hasattr(trade.side, "value")
            else str(trade.side)
        ).upper()
        stop_str = f"${trade.stop:.2f}" if trade.stop is not None else "—"
        target_str = f"${trade.target:.2f}" if trade.target is not None else "—"
        get_journal_store().append(JournalEntryCreate(
            user_id=req.user_id,
            entry_type=EntryType.SIM_TRADE,
            reference_id=trade.id,
            title=f"{side_label} {trade.quantity:g} {trade.ticker} @ ${trade.entry_price:.2f}",
            summary=(
                f"Opened at ${trade.entry_price:.2f}. "
                f"Stop {stop_str}. Target {target_str}."
            ),
            ticker=trade.ticker,
            tags=["sim_trade"],
            outcome=Outcome.PENDING,
            payload={"trade": trade.to_json()},
        ))
    except Exception:  # pragma: no cover
        pass

    # Reputation (CR004): a buy with both stop AND target that cleared the
    # mandate check is a disciplined trade. Trade-id ref dedup + the ≤3/day
    # per-type limit keep it un-farmable.
    if side == Side.BUY and req.stop is not None and req.target is not None:
        try:
            with get_session() as s:
                get_reputation_service().award(
                    s, user_id=req.user_id,
                    event_type="trade_disciplined", ref_id=str(trade.id),
                )
        except Exception:  # pragma: no cover
            pass

    return {
        "ok": True,
        "trade": trade.to_json(),
        "compliance": {
            "passed": result.compliance.passed,
            "violations": result.compliance.violations,
            "blocked_by": result.compliance.blocked_by,
            "sharia_verdict": (
                result.compliance.sharia_verdict.model_dump(mode="json")
                if result.compliance.sharia_verdict is not None else None
            ),
        },
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
    updates = sim.evaluate_outcomes(user_id)
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
    closed: SimTrade | None = sim.manual_close(user_id, req.trade_id)
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
    q = sim.current_quote(ticker)
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
    q = sim.current_quote(ticker)
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
    """
    if period not in VALID_PERIODS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"invalid period; must be one of {','.join(VALID_PERIODS)}",
        )
    bars, source = sim.current_history(ticker, period)
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
    items, source = sim.current_news(ticker, limit)
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
    info, source = sim.current_earnings(ticker)
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
