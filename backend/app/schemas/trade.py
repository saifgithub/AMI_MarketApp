"""Sim portfolio + trade + compliance check result."""

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.classification import ClassificationVerdict
from app.schemas.sharia import ShariaVerdict
from app.trading_math.portfolio import drawdown_pct as _drawdown_pct
from app.trading_math.portfolio import total_value as _total_value


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
        """Sum cash + (quantity * price) for each holding. marks: ticker→price.

        Arithmetic lives in app.trading_math.portfolio (CR046 M05)."""
        marks = marks or {}
        return _total_value(
            self.current_cash,
            ((h.quantity, marks.get(h.ticker, h.avg_cost)) for h in self.holdings),
        )

    def total_drawdown_pct(self, marks: dict[str, float] | None = None) -> float:
        """Drawdown vs starting capital, as a positive percentage (CR046 M05)."""
        return _drawdown_pct(self.starting_capital, self.total_value(marks))


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
    blocked_by: Literal[
        "compliance", "drawdown", "concentration", "long_only", "blocklist",
        "allowlist", "locale", "duplicate_verdict",
        "cooldown", "max_open_positions", "over_trading", "open_risk",
        None,
    ] = None
    # CR069: the sourced Sharia verdict (with provenance) when the halal flag is
    # on. Present on BOTH a blocked screened-out trade AND a permitted PASS/UNKNOWN
    # one, so the disclosure travels even when the trade succeeds — a permitted
    # unknown that says nothing is a silent pass on an observance decision (G3).
    # None when the halal flag is off (or the legacy bare-set path was used).
    sharia_verdict: ShariaVerdict | None = None
    # DEF061: the sourced sector/industry verdicts for the no_fossil_fuels /
    # no_tobacco_alcohol_gambling flags. One entry per ACTIVE flag, present on BOTH
    # a blocked (EXCLUDED) trade AND a permitted (PERMITTED/UNKNOWN) one — so an
    # UNKNOWN disclosure ("AMI hasn't classified this name") travels even when the
    # trade succeeds. Empty when neither flag is on.
    classification_verdicts: list[ClassificationVerdict] = Field(default_factory=list)
