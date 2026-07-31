"""PriceAlertStore — CR027 §4. Stop/target/manual price-threshold watches.

State machine: ACTIVE -> FIRED (threshold breach, the evaluator's job, not
this store's) or ACTIVE -> CANCELLED (user cancels, here). Terminal states
are read-only audit trail — `cancel()` on an already-terminal alert is a
409, never a silent no-op or a resurrection.

10-active-alert cap: enforced here at creation time by auto-cancelling the
user's oldest active alert once the 11th would-be-active alert lands,
rather than rejecting the new one — matches CR027's locked spec ("oldest
auto-close past that").
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import func, select

from app.db import get_session, init_schema
from app.db.models import PriceAlertRow, SimTradeRow
from app.schemas.price_alert import PriceAlertCreate, PriceAlertOut
from app.services.ticker_reference import require_ticker_exists

MAX_ACTIVE_ALERTS_PER_USER = 10


class PriceAlertConflictError(ValueError):
    """Raised on an operation that would mutate a terminal (fired/cancelled)
    alert — those are audit-trail rows, read-only by design."""


class PriceAlertStore:
    def __init__(self) -> None:
        init_schema()

    def create(self, user_id: UUID, req: PriceAlertCreate) -> PriceAlertOut:
        ticker_norm = req.ticker.strip().upper()
        if not ticker_norm:
            raise ValueError("ticker cannot be empty")
        with get_session() as s:
            # CR128 parity: this is a 4th ticker-entry point (Room/Trade/
            # Watchlist already guard this) — a garbage ticker should never
            # sit ACTIVE forever silently never firing.
            require_ticker_exists(s, ticker_norm)

            if req.trade_ref is not None:
                trade = s.get(SimTradeRow, req.trade_ref)
                if trade is None or trade.user_id != user_id:
                    raise ValueError("trade_ref does not belong to this user")

            row = PriceAlertRow(
                id=uuid4(),
                user_id=user_id,
                ticker=ticker_norm,
                threshold_type=req.threshold_type,
                threshold_price=req.threshold_price,
                status="active",
                trade_ref=req.trade_ref,
            )
            s.add(row)
            s.flush()
            created = _row_to_out(row)

            self._enforce_active_cap(s, user_id)
            return created

    def _enforce_active_cap(self, s, user_id: UUID) -> None:
        active_ids = s.execute(
            select(PriceAlertRow.id)
            .where(PriceAlertRow.user_id == user_id, PriceAlertRow.status == "active")
            .order_by(PriceAlertRow.created_at.desc())
        ).scalars().all()
        if len(active_ids) <= MAX_ACTIVE_ALERTS_PER_USER:
            return
        # Newest MAX_ACTIVE_ALERTS_PER_USER survive; the rest (oldest) close.
        overflow_ids = active_ids[MAX_ACTIVE_ALERTS_PER_USER:]
        now = datetime.now(timezone.utc)
        for row in s.execute(
            select(PriceAlertRow).where(PriceAlertRow.id.in_(overflow_ids))
        ).scalars():
            row.status = "cancelled"
            row.cancelled_at = now

    def list_for_user(self, user_id: UUID, status: str | None = None) -> list[PriceAlertOut]:
        with get_session() as s:
            query = select(PriceAlertRow).where(PriceAlertRow.user_id == user_id)
            if status is not None:
                query = query.where(PriceAlertRow.status == status)
            rows = s.execute(query.order_by(PriceAlertRow.created_at.desc())).scalars().all()
            return [_row_to_out(r) for r in rows]

    def cancel(self, user_id: UUID, alert_id: UUID) -> PriceAlertOut | None:
        """None if the alert doesn't exist / isn't owned by this user.
        Raises PriceAlertConflictError if it exists but is already terminal.
        """
        with get_session() as s:
            row = s.get(PriceAlertRow, alert_id)
            if row is None or row.user_id != user_id:
                return None
            if row.status != "active":
                raise PriceAlertConflictError(f"alert is already {row.status}")
            row.status = "cancelled"
            row.cancelled_at = datetime.now(timezone.utc)
            s.flush()
            return _row_to_out(row)

    def count_active(self, user_id: UUID) -> int:
        with get_session() as s:
            return s.execute(
                select(func.count(PriceAlertRow.id)).where(
                    PriceAlertRow.user_id == user_id, PriceAlertRow.status == "active",
                )
            ).scalar_one()


def _row_to_out(row: PriceAlertRow) -> PriceAlertOut:
    return PriceAlertOut(
        id=row.id,
        user_id=row.user_id,
        ticker=row.ticker,
        threshold_type=row.threshold_type,
        threshold_price=float(row.threshold_price),
        status=row.status,
        trade_ref=row.trade_ref,
        created_at=row.created_at,
        fired_at=row.fired_at,
        cancelled_at=row.cancelled_at,
        agent_commentary=row.agent_commentary,
    )


_store: PriceAlertStore | None = None


def get_price_alert_store() -> PriceAlertStore:
    global _store
    if _store is None:
        _store = PriceAlertStore()
    return _store
