"""Sim portfolio + trade + compliance check result."""

from datetime import date, datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.classification import ClassificationVerdict
from app.schemas.sharia import ShariaVerdict
from app.trading_math.portfolio import drawdown_pct as _drawdown_pct
from app.trading_math.portfolio import total_value as _total_value
from app.trading_math.option_strategy import option_legs_value as _option_legs_value
from app.trading_math.shorts import short_legs_value as _short_legs_value


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """CR170 — four types, and only MARKET is guaranteed to fill on submit.

    STOP and STOP_LIMIT arrive with the resting-order book. Before CR170 this
    enum held two values and LIMIT was a lie: `sim_engine` read it only to
    decide whether to use `limit_price` as the fill price, which made a "limit
    order" a price override that filled instantly at whatever the caller named
    (DEF149/DEF153, failure pattern P10). The value now means what it says —
    see `trading_math/order_pricing.py` for the trigger rule.
    """

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class Holding(BaseModel):
    ticker: str
    quantity: float
    avg_cost: float
    opened_at: datetime


class ShortLeg(BaseModel):
    """An OPEN short position on a portfolio — CR109 Amendment G, game lane
    only. The training portfolio's list is always empty, so every existing
    caller of `total_value` is arithmetically unchanged.

    Carried on `Portfolio` rather than fetched by whichever surface happens
    to need it, because value, drawdown, the daily NAV snapshot and the TWR
    chain the Close scores on all derive from this one object. A short the
    portfolio object does not know about is a short the score does not know
    about.
    """

    id: UUID
    ticker: str
    quantity: float
    entry_price: float
    cash_posted: float
    opened_at: datetime


class OptionLeg(BaseModel):
    """One OPEN option leg on a portfolio — CR172 §3, the training lane.

    Carried on `Portfolio` for the same reason `ShortLeg` is: value,
    drawdown, the daily NAV snapshot and every risk read derive from this one
    object, so a leg the portfolio does not know about is a leg the score does
    not know about.

    `quantity` is SIGNED contracts and `avg_premium` is per SHARE — both the
    conventions `sim_option_legs` stores, carried through unchanged so no
    second unit exists to drift (DEF098).

    `collateral_posted` travels because the value term needs it: the cash that
    left at open has to come back somewhere or opening a position moves
    `total_value` by itself. See `option_leg_value`.
    """

    id: UUID
    occ_symbol: str
    underlying: str
    right: str            # "call" | "put"
    strike: float
    expiry: date
    quantity: float       # SIGNED contracts: positive long, negative short
    avg_premium: float    # per share
    multiplier: float = 100.0
    collateral_posted: float = 0.0
    strategy_id: UUID
    strategy_name: str
    opened_at: datetime

    # Days until expiry, computed server-side at read time.
    #
    # The client must not derive this. A phone's clock is the user's, not the
    # settlement calendar's, and `expiry` is a bare date with no timezone — so
    # a device in UTC+8 and one in UTC-5 would disagree about DTE on the day
    # that matters most. `CostedStructure.days_to_expiry` is already
    # server-sent for the same reason; this keeps the open leg on the same
    # footing as the proposal it came from.
    #
    # **Deliberately SIGNED, unlike `option_strategist`'s
    # `max(0, ...)` at line 313.** That clamp is right there: you cannot
    # propose a structure off an expired chain, so negative is unreachable.
    # Here it is reachable and it means something — a leg still `state="open"`
    # past its expiry is one settlement has not processed. Clamping would
    # render that identically to "expires today", which is the one reading that
    # would stop a user asking why it is still on their book.
    days_to_expiry: int


class Portfolio(BaseModel):
    """Sim portfolio snapshot."""

    model_config = ConfigDict(use_enum_values=True)

    id: UUID
    user_id: UUID
    name: str = "Main"
    starting_capital: float = 10_000.0
    current_cash: float
    holdings: list[Holding] = Field(default_factory=list)
    shorts: list[ShortLeg] = Field(default_factory=list)
    options: list[OptionLeg] = Field(default_factory=list)
    created_at: datetime

    def total_value(
        self,
        marks: dict[str, float] | None = None,
        option_marks: dict[str, float] | None = None,
    ) -> float:
        """Sum cash + (quantity * price) for each holding, plus the short leg.

        marks: ticker→price. Arithmetic lives in app.trading_math.portfolio
        (CR046 M05) and app.trading_math.shorts (CR109 Amendment G).

        `shorts` is empty on every training portfolio, so this returns
        exactly what it always returned there — the second term is 0.0 and
        not merely negligible."""
        marks = marks or {}
        option_marks = option_marks or {}
        long_side = _total_value(
            self.current_cash,
            ((h.quantity, marks.get(h.ticker, h.avg_cost)) for h in self.holdings),
        )
        short_side = _short_legs_value(
            (s.cash_posted, s.quantity, s.entry_price, marks.get(s.ticker, s.entry_price))
            for s in self.shorts
        )
        # CR172 §11 — an option leg with no mark is held at the premium it was
        # opened at, exactly as a holding with no mark is held at `avg_cost`.
        # That keeps the total continuous across the open (the cash that left
        # equals the term that arrived) at the price of showing no P&L until
        # option marks are wired. A zero would be worse in the one way that
        # matters: it reports the position as a total loss the moment it opens.
        option_side = _option_legs_value(
            (
                o.collateral_posted,
                o.quantity,
                o.multiplier,
                option_marks.get(o.occ_symbol, o.avg_premium),
            )
            for o in self.options
        )
        return long_side + short_side + option_side

    def total_drawdown_pct(
        self,
        marks: dict[str, float] | None = None,
        option_marks: dict[str, float] | None = None,
    ) -> float:
        """Drawdown vs starting capital, as a positive percentage (CR046 M05)."""
        return _drawdown_pct(
            self.starting_capital, self.total_value(marks, option_marks),
        )


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
    # DEF169: checks that COULD NOT run (e.g. the single-name cap when
    # portfolio_value <= 0) — distinct from `violations`. A skipped check must
    # never collapse into either "blocked" or a silent "passed"; the caller reads
    # this list to tell "checked and clear" apart from "could not check" (CR040).
    not_evaluated: list[str] = Field(default_factory=list)
    # CR171 §6 — checks that RAN, found something the user should know, and
    # deliberately did not block. A third state, and it needs to be one: it is
    # neither a `violation` (which refuses) nor `not_evaluated` (which could not
    # check). Folding it into either would be a lie in one direction or the
    # other — a refusal that isn't, or an unknown that isn't.
    #
    # Its first occupant is Saiful's halal ruling on short selling, 2026-08-13:
    # *"Our job is only to inform. The user can continue with whatever trade
    # they want to do. So we will put a flag and notice to inform the user, but
    # we let the trade through."* This SUPERSEDES CR171 §6's proposed outright
    # refusal, which was escalated rather than decided in code.
    #
    # CR040 applies with full force: an advisory that is logged server-side and
    # never rendered is not informing anyone. It travels on the wire
    # (`ComplianceBlock.advisories`) for exactly that reason.
    advisories: list[str] = Field(default_factory=list)
