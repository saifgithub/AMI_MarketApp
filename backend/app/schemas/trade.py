"""Sim portfolio + trade + compliance check result."""

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class Holding(BaseModel):
    ticker: str
    quantity: float
    avg_cost: float
    opened_at: datetime


class Portfolio(BaseModel):
    """Sim portfolio snapshot."""

    model_config = ConfigDict(use_enum_values=True)

    id: UUID
    user_id: UUID
    name: str = "Main"
    starting_capital: float = 10_000.0
    current_cash: float
    holdings: list[Holding] = Field(default_factory=list)
    created_at: datetime

    def total_value(self, marks: dict[str, float] | None = None) -> float:
        """Sum cash + (quantity * price) for each holding. marks: ticker→price."""
        marks = marks or {}
        invested = sum(h.quantity * marks.get(h.ticker, h.avg_cost) for h in self.holdings)
        return self.current_cash + invested

    def total_drawdown_pct(self, marks: dict[str, float] | None = None) -> float:
        """Drawdown vs starting capital, as a positive percentage."""
        if self.starting_capital <= 0:
            return 0.0
        v = self.total_value(marks)
        return max(0.0, (self.starting_capital - v) / self.starting_capital * 100)


class ProposedTrade(BaseModel):
    """A trade idea to be checked against mandate before submission."""

    model_config = ConfigDict(use_enum_values=True)

    ticker: str
    side: Side
    quantity: float
    order_type: OrderType = OrderType.MARKET
    limit_price: float | None = None

    @property
    def is_buy(self) -> bool:
        return self.side == Side.BUY

    @property
    def is_sell(self) -> bool:
        return self.side == Side.SELL


class ComplianceResult(BaseModel):
    """Output of the deterministic mandate-compliance check."""

    passed: bool
    violations: list[str] = Field(default_factory=list)
    blocked_by: Literal["compliance", "drawdown", "concentration", "long_only", "blocklist", "allowlist", "locale", "duplicate_verdict", None] = None
