"""Price alert schemas — CR027 §4.

`threshold_type` semantics (enforced by the evaluator, not here):
stop/manual_below fire when price falls BELOW threshold_price;
target/manual_above fire when price rises ABOVE it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

ThresholdType = Literal["stop", "target", "manual_above", "manual_below"]
AlertStatus = Literal["active", "fired", "cancelled"]


class PriceAlertCreate(BaseModel):
    ticker: str
    threshold_type: ThresholdType
    threshold_price: float
    trade_ref: UUID | None = None


class PriceAlertOut(BaseModel):
    id: UUID
    user_id: UUID
    ticker: str
    threshold_type: str
    threshold_price: float
    status: str
    trade_ref: UUID | None
    created_at: datetime
    fired_at: datetime | None
    cancelled_at: datetime | None
    agent_commentary: str | None


class PriceAlertListResponse(BaseModel):
    items: list[PriceAlertOut]
    total: int
