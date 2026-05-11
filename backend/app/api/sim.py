"""Sim Trading endpoints.

GET  /v1/sim/portfolio/{user_id}             Snapshot (cash + holdings + marks + P&L)
POST /v1/sim/portfolio/{user_id}/reset       Wipe and restart with $10k
POST /v1/sim/submit                          Submit a trade (PM safety floor runs)
GET  /v1/sim/trades/{user_id}                List trades (filterable by status)
POST /v1/sim/trades/{user_id}/evaluate       Sweep open trades for stop/target hits
POST /v1/sim/trades/{user_id}/close          Manually close an open trade
GET  /v1/sim/quote/{ticker}                  Current mock mark
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from app.schemas.journal import EntryType, JournalEntryCreate, Outcome
from app.schemas.trade import OrderType, Side
from app.services.journal_store import get_journal_store
from app.services.mandate_store import resolve_mandate
from app.services.sim_engine import SimEngine, SimTrade, get_sim_engine


router = APIRouter(prefix="/v1/sim", tags=["sim"])


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
    # Active market-data provider — surfaced so the iPhone can show a
    # LIVE / MOCK pill next to the marks. Values: "mock_walk",
    # "fallback(cache(yahoo)->mock_walk)", or any future provider name.
    price_source: str = "mock_walk"


class TradeListResponse(BaseModel):
    trades: list[dict]


@router.get("/portfolio/{user_id}", response_model=PortfolioSnapshot)
async def get_portfolio(
    user_id: UUID,
    sim: SimEngine = Depends(get_sim_engine),
) -> PortfolioSnapshot:
    p = sim.ensure_portfolio(user_id)
    marks = sim.current_marks([h.ticker for h in p.holdings])
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
        price_source=sim.price_source,
    )


@router.post("/portfolio/{user_id}/reset", response_model=PortfolioSnapshot)
async def reset_portfolio(
    user_id: UUID,
    sim: SimEngine = Depends(get_sim_engine),
) -> PortfolioSnapshot:
    sim.reset_portfolio(user_id)
    return await get_portfolio(user_id, sim)  # type: ignore[arg-type]


@router.post("/submit")
async def submit_trade(
    req: SubmitTradeRequest,
    sim: SimEngine = Depends(get_sim_engine),
) -> dict:
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
    )
    if not result.accepted:
        return {
            "ok": False,
            "compliance": {
                "passed": result.compliance.passed,
                "violations": result.compliance.violations,
                "blocked_by": result.compliance.blocked_by,
            },
        }

    trade = result.trade
    assert trade is not None
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

    return {"ok": True, "trade": trade.to_json()}


@router.get("/trades/{user_id}", response_model=TradeListResponse)
async def list_trades(
    user_id: UUID,
    status_filter: str | None = None,
    sim: SimEngine = Depends(get_sim_engine),
) -> TradeListResponse:
    trades = sim.list_trades(user_id, status=status_filter)  # type: ignore[arg-type]
    return TradeListResponse(trades=[t.to_json() for t in trades])


@router.post("/trades/{user_id}/evaluate")
async def evaluate_trades(
    user_id: UUID,
    sim: SimEngine = Depends(get_sim_engine),
) -> dict:
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
    sim: SimEngine = Depends(get_sim_engine),
) -> dict:
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


@router.get("/quote/{ticker}")
async def quote(
    ticker: str,
    sim: SimEngine = Depends(get_sim_engine),
) -> dict:
    return {
        "ticker": ticker.upper(),
        "price": sim.current_price(ticker),
        "source": sim.price_source,
    }
