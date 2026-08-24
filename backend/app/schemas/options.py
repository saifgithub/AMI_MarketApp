"""CR172 — one wire shape for "an option structure AMI has costed".

Three surfaces need to describe the same thing: `POST /v1/sim/options/propose`
returns a menu of them, a Room verdict now carries the one the Chief Investment
Officer chose, and `POST /v1/sim/options/reprice` returns the same structure
costed again against a fresher chain. Before this module each of those would
have grown its own DTO, and the mobile ticket — which parses exactly one shape —
would have needed a parser per surface.

**Why that matters more than the deduplication.** `OptionProposalTicket` is the
only screen in the app that renders a max loss, and its whole design rests on
*every figure coming off the payload* — it computes nothing, and prints "not
computed" where the server sent nothing, because a client-side zero and a real
zero are indistinguishable on a max loss (DEF059). A second DTO is a second
chance for one of those fields to go missing on one surface only, which the
ticket would render as a confident absence rather than a wire gap. One class,
one parser, one set of keys.

**`spot` and `priced_at` are on the structure, not on an envelope.** /propose
carries a spot on its response and could have left it there, but a structure
that travels — into a verdict, into a re-price comparison, into a client that
holds it while the user thinks — has to be able to answer "what was the market
when you costed this?" on its own. Without that, the drift the user is shown at
consent has no honest baseline. Both fields are `None` only when the source
genuinely could not state them; neither is ever defaulted to now/spot-today,
which would manufacture a provenance nobody measured.
"""

from __future__ import annotations

import datetime

from pydantic import BaseModel, Field, field_validator

from app.trading_math.option_strategy import StrategyLeg


class LegOut(BaseModel):
    """One leg as the SERVER states it, priced."""

    right: str
    strike: float
    quantity: float
    premium: float
    multiplier: float
    expiry: str
    occ_symbol: str | None = None


class MetricsOut(BaseModel):
    """`StrategyMetrics`, key for key — the mobile model mirrors this."""

    net_cost: float
    max_loss: float | None
    max_gain: float | None
    unbounded_loss: bool
    unbounded_gain: bool
    break_evens: list[float]
    collateral_required: float | None
    has_uncovered_short_call: bool
    shares_locked: float
    covered_by_shares: bool


class GreeksOut(BaseModel):
    delta: float
    gamma: float
    theta_per_day: float
    vega_per_point: float
    rho_per_point: float


class ComplianceOut(BaseModel):
    """`ComplianceResult` as the ticket reads it — `passed` always present.

    The client fails closed on a missing `passed`, so it is never omitted
    here: a serialiser that drops falsy fields is exactly what that guard was
    written against.
    """

    passed: bool
    violations: list[str] = Field(default_factory=list)
    advisories: list[str] = Field(default_factory=list)
    not_evaluated: list[str] = Field(default_factory=list)
    blocked_by: str | None = None


class CostedStructure(BaseModel):
    """One structure, priced, checked, and stamped with what it was priced on.

    Every number here was computed by `option_strategist` off a chain the
    server read. None of it is ever model-stated: a premium or a strike that
    arrived from an LLM would be the defect with a cash consequence, because
    `net_cost` is what `open_option_structure` charges.
    """

    strategy_name: str
    contracts: int
    expiry: str
    days_to_expiry: int
    underlying: str
    legs: list[LegOut]
    metrics: MetricsOut
    net_greeks: GreeksOut | None = None
    greeks_not_evaluated: list[str] = Field(default_factory=list)
    compliance: ComplianceOut
    not_evaluated: list[str] = Field(default_factory=list)
    rationale: str = ""

    # What the market was when this was costed. `None` means the source could
    # not state it — never "assume today's".
    # CR172 §12 — the expiry payoff as (price, pnl) VERTICES, not samples.
    # A structure's payoff is piecewise-linear with kinks only at the strikes,
    # so these describe the whole curve losslessly and the client interpolates.
    # Server-computed so the drawing and the `max_loss` / `break_evens` printed
    # beside it come from one derivation — a diagram that disagrees with its own
    # caption is DEF098's shape, and on this surface the diagram is what the
    # user actually reads.
    payoff_curve: list[tuple[float, float]] = Field(default_factory=list)

    spot: float | None = None
    priced_at: datetime.datetime | None = None

    @field_validator("priced_at")
    @classmethod
    def _utc(cls, v):
        return as_utc(v)


def as_utc(value: datetime.datetime | None) -> datetime.datetime | None:
    """Force a timestamp to be tz-aware UTC.

    **This is a wire-correctness fence, not tidiness.** `app.core.time.now_utc`
    returns *naive* UTC by deliberate design — it exists to drain a deprecation
    without breaking comparisons against the many naive datetimes already
    persisted — so a `priced_at` stamped with it serialises as
    `2026-08-23T02:14:07` with no offset. Dart's `DateTime.tryParse` reads a
    string with no offset as **local time**, and the client then calls
    `.toUtc()` on it: on a UTC+8 device the age of the price the user is being
    shown would be wrong by eight hours, in the direction that makes a stale
    price look fresh.

    Applied as a validator on every field that carries one rather than at the
    call sites, because a convention every stamper must remember is a
    convention one of them will not (CR038's principle, one layer down: if it
    must hold, make it structural).

    A naive value is INTERPRETED as UTC rather than rejected — every producer in
    this codebase means UTC when it omits the offset, and refusing would break
    the callers this helper exists to quietly correct.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.timezone.utc)
    return value.astimezone(datetime.timezone.utc)


def leg_out(leg: StrategyLeg, occ: str | None = None) -> LegOut:
    return LegOut(
        right=leg.right, strike=leg.strike, quantity=leg.quantity,
        premium=leg.premium, multiplier=leg.multiplier, expiry=leg.expiry,
        occ_symbol=occ,
    )


def _payoff_curve(legs, *, spot):
    from app.trading_math.option_strategy import payoff_curve

    return payoff_curve(legs, spot=spot)


def costed_structure(
    candidate, *, spot: float | None = None,
    priced_at: datetime.datetime | None = None,
) -> CostedStructure:
    """Build the wire shape from an `OptionCandidate`.

    `candidate` is deliberately untyped: importing `OptionCandidate` here would
    pull `option_strategist` — and through it the chain reader — into every
    module that merely wants to describe a structure, including the Room's
    schema module. The attributes are read positionally by name and a candidate
    missing one is a programming error, not a wire condition.
    """
    m = candidate.metrics
    return CostedStructure(
        strategy_name=candidate.strategy_name,
        contracts=candidate.contracts,
        expiry=candidate.expiry,
        days_to_expiry=candidate.days_to_expiry,
        underlying=candidate.underlying,
        legs=[leg_out(leg) for leg in candidate.legs],
        payoff_curve=[
            list(pt) for pt in _payoff_curve(candidate.legs, spot=spot)
        ],
        metrics=MetricsOut(
            net_cost=m.net_cost,
            max_loss=m.max_loss,
            max_gain=m.max_gain,
            unbounded_loss=m.unbounded_loss,
            unbounded_gain=m.unbounded_gain,
            break_evens=list(m.break_evens),
            collateral_required=m.collateral_required,
            has_uncovered_short_call=m.has_uncovered_short_call,
            shares_locked=m.shares_locked,
            covered_by_shares=m.covered_by_shares,
        ),
        net_greeks=(
            None if candidate.net_greeks is None
            else GreeksOut(**candidate.net_greeks._asdict())
        ),
        greeks_not_evaluated=list(candidate.greeks_not_evaluated),
        compliance=ComplianceOut(
            passed=not candidate.mandate_violations,
            violations=list(candidate.mandate_violations),
            advisories=list(candidate.advisories),
            not_evaluated=list(candidate.not_evaluated),
            blocked_by="compliance" if candidate.mandate_violations else None,
        ),
        not_evaluated=list(candidate.not_evaluated),
        rationale=candidate.rationale,
        spot=spot,
        priced_at=priced_at,
    )
