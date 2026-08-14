"""CR170 §5 — the sweep that makes the resting-order book real.

Its closest sibling is **`price_alert_evaluator.py`**, not
`games_service.process_queued_orders`: one price fetch per ticker, never fires
on missing data, and *the state transition is the duplicate guard, not the
Python loop*. The games drain is time-triggered ("is the market open yet?") and
empties its queue on the first tick after 09:30; this one is price-triggered,
checks the whole book on every tick, all day, and most orders never fill.

Three sub-passes, and only two are market-hours gated:

| sub-pass                  | gated | why                                        |
|---------------------------|-------|--------------------------------------------|
| `_expire_elapsed`         | no    | an order expires at a session close whether or not the market is open now; gating it leaves dead orders looking alive all weekend |
| `_fill_triggered`         | yes   | outside the session a "trigger" is a trigger against a stale last price — CR109 §5.1's time machine |
| `_sweep_position_brackets`| yes   | drives `evaluate_outcomes` so the SHIPPED stop/target fires overnight, which is Saiful's decision and half the point of this CR |

## The quote-quality problem, which is the highest-severity item in the design

`SimEngine.current_quote` never returns `None` — it falls through to
`Quote(price=0.01, source="unavailable")`. **$0.01 is below every plausible buy
limit AND every sell stop**, so a total provider outage would fire the entire
book, in both directions, simultaneously. `_quote_is_fillable` is the guard, and
the >50%-unfillable circuit breaker is the second one: a partial-outage sweep
that fills half the book is worse than one that fills none.

## Idempotency: claim first, in three steps

1. `UPDATE ... SET state='filling' WHERE id=:id AND state IN ('working','triggered')`
   — `rowcount > 0` **is** the claim. An overlapping sweep, a concurrent user
   cancel and a racing `/evaluate` all lose here.
2. `SimEngine.fill_resting_order(...)`, its own transaction.
3. Stamp `filled` (+ ids and price) or `rejected` (+ `cancel_reason`).

Claim *first*, not after: a crash between the fill and the stamp then leaves the
order `filling` — visible and not double-filled — rather than `working` and
re-filled on the next tick. The **stale-claim reaper** moves a `filling` order
older than `_STALE_CLAIM_MINUTES` to `rejected`, and **never retries it**. A
retry of a money-moving operation whose outcome is unknown is how a phantom
double-buy happens.

Three transactions means two crash windows. That is the price of reusing the
engine's fill mechanics, and reusing them is what buys the safety floor
structurally — `fill_resting_order` re-runs `check_mandate_compliance`, because
a resting order must never become a time-delayed bypass of a floor specified
uncoachable.

## FIFO, explicitly

Oldest `placed_at` first. When the book exceeds cash, *which* orders fill must
not come down to whatever order Postgres returns rows in: oldest-first is the
only rule a user can reason about while placing the orders, and the only one
that does not reward re-queueing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, update

from app.core.config import settings
from app.core.logging import logger
from app.db import get_session, init_schema
from app.db.models import SimPortfolioRow, SimRestingOrderRow, SimTradeRow
from app.services.market_data import Quote
from app.services.mandate_store import resolve_mandate
from app.services.sim_engine import (
    LIVE_RESTING_STATES,
    SimEngine,
    SimRestingOrder,
    get_sim_engine,
)
from app.services.sim_trade_effects import apply_post_fill_effects
from app.schemas.trade import OrderType, Side
from app.trading_math.market_hours import is_us_market_open
from app.trading_math.order_pricing import is_triggered

#: A claim older than this is assumed dead. Ten minutes is two ticks at the
#: default interval — long enough that a slow fill is not reaped mid-flight,
#: short enough that a user is not left staring at a stuck order.
_STALE_CLAIM_MINUTES = 10

#: Abort the whole sweep above this share of unfillable tickers. A partial
#: outage that fills half the book is worse than one that fills none.
_UNFILLABLE_ABORT_RATIO = 0.5


def _quote_is_fillable(q: Quote | None) -> bool:
    """Whether this quote may move a real user's ledger.

    `source == "unavailable"` is `current_quote`'s $0.01 sentinel and would fire
    every buy limit and every sell stop in the book at once.

    A `mock_walk` price is a deterministic random walk with no relationship to
    reality. Booking a user's ledger off one is a fiction that never comes off
    the books. Under `USE_REAL_MARKET_DATA` a mock_walk source means Yahoo fell
    through — a degraded state, not the intended provider — so it is refused.
    With real data off, mock_walk IS the intended provider and is fine.
    """
    if q is None:
        return False
    if q.source == "unavailable" or q.price <= 0:
        return False
    if settings.use_real_market_data and q.source == "mock_walk":
        return False
    return True


def _live_orders(user_id: UUID | None) -> list[SimRestingOrder]:
    with get_session() as s:
        stmt = (
            select(SimRestingOrderRow)
            .where(SimRestingOrderRow.state.in_(LIVE_RESTING_STATES))
            .order_by(SimRestingOrderRow.placed_at.asc())
        )
        if user_id is not None:
            stmt = stmt.where(SimRestingOrderRow.user_id == user_id)
        return [SimRestingOrder.from_row(r) for r in s.execute(stmt).scalars().all()]


@dataclass(frozen=True)
class RestingCommitment:
    """§6 — what the live book ties up, computed AT READ TIME and never written.

    Reserving instead would redefine `current_cash`, which `Portfolio.total_value`,
    `total_drawdown_pct`, `portfolio_nav_daily`, `portfolio_value_snapshots`, the
    TWR chain and `_risk_limit_context` all read — a reserved-cash debit is
    indistinguishable from a **loss** in the NAV series unless every one of those
    sites learns about it. Reservation would also need a compensating credit on
    five terminal paths (cancel, expire, reject, reset, reap), and every one
    missed leaks a user's money permanently. Read-time computation has no
    compensating write, so there is nothing to leak.

    `cash_committed` for a **buy stop is a floor, not an exact figure**: Rule 2
    fills at the worse of named and observed, so a stop that gaps fills above its
    trigger and ties up more than this says. Naming it here so the client's copy
    can be honest about it rather than presenting an estimate as a total.
    """

    cash_committed: float
    shares_committed: dict[str, float]
    resting_order_count: int


def commitment_for(user_id: UUID) -> RestingCommitment:
    """A pure DB read over the live book — no quote fan-out.

    Strictly cheaper than the games precedent it follows (`_queued_orders_priced`
    prices every queued order at read time) because a resting order already
    names its own price. The problem is the same one, though, and it is Saiful's
    on build 74: *"This was the second order placed. But it is still showing I
    have 10K."* Without this, a user rests five buy limits and the portfolio
    keeps reporting the whole balance as spendable.

    `shares_committed` is the sell-side twin games never needed, and it is what
    stops a user resting two sells for shares they hold once. Per ticker, because
    the fence is per holding — a single total would let a sell of 10 AAPL cover
    a sell of 10 MSFT.
    """
    cash = 0.0
    shares: dict[str, float] = {}
    orders = _live_orders(user_id)
    for order in orders:
        named = order.named_price
        if order.side == Side.BUY:
            # A market order never rests, so `named` is None only for a row
            # written by something that bypassed the submit validator. Skipping
            # it under-reports rather than crashing the portfolio read, and the
            # order itself is already unfillable (`_fill_triggered` skips it).
            if named is not None:
                cash += named * order.quantity
        else:
            shares[order.ticker] = shares.get(order.ticker, 0.0) + order.quantity
    return RestingCommitment(
        cash_committed=round(cash, 2),
        shares_committed={k: round(v, 4) for k, v in shares.items()},
        resting_order_count=len(orders),
    )


def _expire_elapsed(now: datetime, user_id: UUID | None) -> int:
    """Retire orders whose TIF has elapsed. **Not** market-hours gated.

    `cancel_reason` is set, because this is the system retiring the order, not
    the user pulling it — the invariant the client's copy reads.
    """
    with get_session() as s:
        stmt = (
            update(SimRestingOrderRow)
            .where(
                SimRestingOrderRow.state.in_(LIVE_RESTING_STATES),
                SimRestingOrderRow.expires_at <= now,
            )
            .values(state="expired", cancel_reason="expired — time in force elapsed")
        )
        if user_id is not None:
            stmt = stmt.where(SimRestingOrderRow.user_id == user_id)
        return int(s.execute(stmt).rowcount or 0)


def _reap_stale_claims(now: datetime, user_id: UUID | None) -> int:
    """A `filling` order nobody finished is `rejected`, and **never retried**.

    Logged at ERROR: an interrupted fill means a transaction died between the
    claim and the stamp, and whether money moved is genuinely unknown. Reporting
    it is the only safe action — a retry here is how a phantom double-buy
    happens.
    """
    cutoff = now - timedelta(minutes=_STALE_CLAIM_MINUTES)
    with get_session() as s:
        stmt = (
            update(SimRestingOrderRow)
            .where(
                SimRestingOrderRow.state == "filling",
                SimRestingOrderRow.claimed_at.isnot(None),
                SimRestingOrderRow.claimed_at <= cutoff,
            )
            .values(
                state="rejected",
                cancel_reason="interrupted while filling — check your trade list",
            )
        )
        if user_id is not None:
            stmt = stmt.where(SimRestingOrderRow.user_id == user_id)
        reaped = int(s.execute(stmt).rowcount or 0)
    if reaped:
        logger.error("sim_resting_order_claim_reaped", count=reaped)
    return reaped


def _claim(order_id: UUID, now: datetime) -> bool:
    """Step 1. `rowcount > 0` IS the claim — the state transition is the
    duplicate guard, not the Python loop that selected the row."""
    with get_session() as s:
        res = s.execute(
            update(SimRestingOrderRow)
            .where(
                SimRestingOrderRow.id == order_id,
                SimRestingOrderRow.state.in_(LIVE_RESTING_STATES),
            )
            .values(state="filling", claimed_at=now)
        )
        return bool(res.rowcount)


def _stamp_observation(
    order_id: UUID, quote: Quote, now: datetime, *, seen_price: bool,
) -> None:
    """`last_checked_at` always; `last_seen_price` only on a fillable quote.

    An unfillable quote must not leave a $0.01 on the row: the client renders
    `last_seen_price` to the user, and a zero there reads as "about to fill".
    """
    values: dict = {"last_checked_at": now}
    if seen_price:
        values["last_seen_price"] = quote.price
        values["last_price_source"] = quote.source
    with get_session() as s:
        s.execute(
            update(SimRestingOrderRow)
            .where(SimRestingOrderRow.id == order_id)
            .values(**values)
        )


def _stamp_triggered(order_id: UUID, now: datetime) -> None:
    with get_session() as s:
        s.execute(
            update(SimRestingOrderRow)
            .where(
                SimRestingOrderRow.id == order_id,
                SimRestingOrderRow.state == "working",
            )
            .values(state="triggered", triggered_at=now)
        )


def _stamp_filled(
    order_id: UUID, *, trade_id: UUID, fill_price: float, now: datetime,
) -> None:
    with get_session() as s:
        s.execute(
            update(SimRestingOrderRow)
            .where(SimRestingOrderRow.id == order_id)
            .values(
                state="filled",
                filled_trade_id=trade_id,
                fill_price=fill_price,
                filled_at=now,
            )
        )


def _stamp_rejected(order_id: UUID, reason: str) -> None:
    with get_session() as s:
        s.execute(
            update(SimRestingOrderRow)
            .where(SimRestingOrderRow.id == order_id)
            .values(state="rejected", cancel_reason=reason)
        )


def _users_with_open_trades() -> list[UUID]:
    with get_session() as s:
        rows = s.execute(
            select(SimTradeRow.user_id)
            .join(SimPortfolioRow, SimPortfolioRow.id == SimTradeRow.portfolio_id)
            .where(
                SimTradeRow.status == "open",
                SimPortfolioRow.kind == "training",
            )
            .distinct()
        ).scalars().all()
    return list(rows)


def _sweep_position_brackets(engine: SimEngine, user_id: UUID | None) -> int:
    """Drive the SHIPPED `SimTradeRow.stop`/`.target` bracket from the tick.

    Two evaluators over two tables, and this sweep calls both rather than
    merging them: `evaluate_outcomes` is an **exit** bracket on an already-open
    position, the book above is an **entry** (or a standalone exit). Disjoint
    concepts, disjoint predicates. Merging them would put two predicates in one
    loop, which is P10's shape at the money-moving site.

    Before CR170 this only ran when a client called
    `POST /v1/sim/trades/{id}/evaluate`, i.e. on app open — and **a stop-loss
    that only fires when you open the app is not a stop-loss**, for an audience
    asleep 22:30–05:00 local while the US session runs.
    """
    users = [user_id] if user_id is not None else _users_with_open_trades()
    closed = 0
    for uid in users:
        try:
            closed += len(engine.evaluate_outcomes(uid))
        except Exception:  # pragma: no cover — one user must not stop the sweep
            logger.exception("sim_bracket_sweep_failed", user_id=str(uid))
    return closed


def _fill_triggered(
    engine: SimEngine,
    orders: list[SimRestingOrder],
    quotes: dict[str, Quote],
    now: datetime,
) -> tuple[int, int]:
    """Returns (filled, rejected). Orders arrive FIFO by `placed_at`."""
    filled = rejected = 0
    for order in orders:
        quote = quotes.get(order.ticker)
        fillable = _quote_is_fillable(quote)
        if quote is not None:
            _stamp_observation(order.id, quote, now, seen_price=fillable)
        if not fillable:
            logger.warning(
                "sim_resting_order_quote_unfillable",
                order_id=str(order.id),
                ticker=order.ticker,
                source=None if quote is None else quote.source,
            )
            continue

        mark = quote.price  # type: ignore[union-attr]
        named = order.named_price
        if named is None:
            continue

        if not is_triggered(
            side=order.side, order_type=order.order_type, named=named, mark=mark,
        ):
            continue

        # Phase 1 of a stop-limit: the trigger fired, so it becomes a resting
        # limit and Rule 1 re-applies against `limit_price`. It may never fill —
        # a stop-limit that gaps through its limit is the classic failure and
        # the reason the type is in the curriculum. Reproduced, not smoothed.
        if order.order_type == OrderType.STOP_LIMIT and order.state == "working":
            _stamp_triggered(order.id, now)
            if order.limit_price is None or not is_triggered(
                side=order.side,
                order_type=OrderType.LIMIT,
                named=order.limit_price,
                mark=mark,
            ):
                continue

        if not _claim(order.id, now):
            # Lost the race to an overlapping sweep, a user cancel, or an
            # expiry. Not an error — losing here is the guard working.
            continue

        try:
            mandate = resolve_mandate(order.user_id, None)
            result = engine.fill_resting_order(
                order=order, mark=mark, mandate=mandate,
            )
        except Exception as exc:  # pragma: no cover
            logger.exception(
                "sim_resting_order_fill_raised", order_id=str(order.id),
            )
            _stamp_rejected(order.id, f"could not be filled: {exc}")
            rejected += 1
            continue

        if not result.accepted or result.trade is None:
            reason = (
                result.compliance.violations[0]
                if result.compliance.violations
                else "refused at fill"
            )
            _stamp_rejected(order.id, reason)
            rejected += 1
            continue

        _stamp_filled(
            order.id,
            trade_id=result.trade.id,
            fill_price=result.trade.entry_price,
            now=now,
        )
        # The same three effects the ticket's own fill gets (§7). Extracted
        # before this call site existed, precisely so the two cannot diverge.
        apply_post_fill_effects(user_id=order.user_id, trade=result.trade)
        filled += 1
        logger.info(
            "sim_resting_order_filled",
            order_id=str(order.id),
            trade_id=str(result.trade.id),
            ticker=order.ticker,
            named=named,
            mark=mark,
            fill=result.trade.entry_price,
        )
    return filled, rejected


def sweep_resting_orders(
    *,
    user_id: UUID | None = None,
    now: datetime | None = None,
    engine: SimEngine | None = None,
) -> dict[str, int]:
    """One pass over the book. `user_id=None` sweeps everybody (the tick);
    a user id scopes it to one (the `/evaluate` route).

    One trigger implementation, two call sites — `SimNotifier.refresh()`
    already calls `/evaluate` on every app open, which is what makes the
    feature feel alive without waiting for a tick.
    """
    init_schema()
    engine = engine or get_sim_engine()
    now = now or datetime.now(timezone.utc)
    market_open = is_us_market_open(now)

    stats = {
        "expired": _expire_elapsed(now, user_id),
        "reaped": _reap_stale_claims(now, user_id),
        "checked": 0,
        "filled": 0,
        "rejected": 0,
        "brackets_closed": 0,
        "skipped_closed": 0,
        "aborted": 0,
    }

    if not market_open:
        # CR109 §5.1's time machine: outside the session a "trigger" is a
        # trigger against a stale last price. The expiry pass above still ran,
        # deliberately — an order dies at its session close whether or not the
        # market is open when we notice.
        stats["skipped_closed"] = 1
        return stats

    stats["brackets_closed"] = _sweep_position_brackets(engine, user_id)

    orders = _live_orders(user_id)
    if not orders:
        return stats
    stats["checked"] = len(orders)

    tickers = sorted({o.ticker for o in orders})
    quotes = engine.current_marks_with_source(tickers)
    unfillable = [t for t in tickers if not _quote_is_fillable(quotes.get(t))]
    if unfillable and len(unfillable) > _UNFILLABLE_ABORT_RATIO * len(tickers):
        logger.error(
            "sim_resting_order_sweep_aborted",
            unfillable=len(unfillable),
            total=len(tickers),
            reason="more than half the book's tickers had unusable quotes",
        )
        stats["aborted"] = 1
        return stats

    filled, rejected = _fill_triggered(engine, orders, quotes, now)
    stats["filled"] = filled
    stats["rejected"] = rejected
    return stats
