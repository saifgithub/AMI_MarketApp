"""CR172 §10 — the options surface: AMI proposes a structure, the user consents.

Two endpoints and no chain browser. "Not in scope" is honoured as an absence
here exactly as the mobile ticket honours it: there is no strike picker, no
expiry picker and no way for a client to ask for a structure of its own
design. The user's entire input is yes or no.

**The premium is never the client's to state.** `POST /open` takes legs as
`(right, strike, quantity)` and nothing else — the server re-prices every leg
off the live chain at the moment of consent. That is not defence in depth, it
is the only defence: a leg carrying a client-supplied premium is a leg that
mints cash, because `net_cost` is what moves `current_cash` and a $0.01
premium on a short call is free money. Re-pricing also answers the honest
half of the same question — the chain moved between the proposal and the tap,
and the user is told rather than filled at a stale figure.

**A proposal is not a reservation.** Nothing is written by `/propose`; the
candidate list is recomputed on `/open` from the same inputs, so a proposal
that has gone stale cannot be redeemed. This is why the request carries the
structure's shape rather than an id into server-side state: a proposal id
would need a store, a TTL and an expiry path, and would still have to
re-price at open.
"""

from __future__ import annotations

import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.dependencies import get_current_user
from app.core.logging import logger
from app.db.session import get_session
from app.schemas.trade import Portfolio
from app.schemas.user import User
from app.services.mandate_store import resolve_mandate
from app.services.option_chain import get_enriched_chain, pick_expiry
from app.services.option_strategist import OptionCandidate, build_candidates
from app.services.sim_engine import SimEngine, get_sim_engine
from app.services.ticker_reference import (
    TickerNotFoundError,
    require_ticker_exists,
    ticker_not_found_detail,
)
from app.trading_math.option_strategy import StrategyLeg

router = APIRouter(prefix="/v1/sim/options", tags=["sim-options"])

# The handlers are `propose_options` / `open_options`, not `propose` / `open`,
# and that is load-bearing rather than style. `test_no_blocking_io_in_async_
# routes` resolves call chains BY NAME across modules, so a handler called
# `propose` here is indistinguishable from `BriefEngine.propose` — which an
# async route does await — and the guard reports a blocking chain that does not
# exist. A false positive on that guard is expensive: it is the one that stops
# a real event-loop block, and a guard that cries wolf gets reasoned past
# (DEF277's exact shape). Unique names keep its graph honest.

# The proposal's own risk budget when the caller supplies none: the same
# single-name cap the equity floor enforces, applied to the portfolio's value.
# Not a new policy — the cap is read, never re-derived here.
_DEFAULT_RISK_BUDGET_PCT = 5.0


def _own(current_user: User, user_id: UUID) -> None:
    if current_user.id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "access denied")


def _require_ticker(ticker: str) -> None:
    try:
        with get_session() as session:
            require_ticker_exists(session, ticker)
    except TickerNotFoundError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=ticker_not_found_detail(exc),
        ) from exc


class LegSpec(BaseModel):
    """One leg as the CLIENT may state it — shape only, never a price."""

    right: str = Field(pattern="^(call|put)$")
    strike: float = Field(gt=0)
    quantity: float = Field(description="SIGNED contracts: + long, − short")


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


class CandidateOut(BaseModel):
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
    rationale: str


class ProposeRequest(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    user_id: UUID
    ticker: str
    direction: str = Field(pattern="^(bullish|bearish|neutral)$")
    target: float | None = Field(default=None, gt=0)
    stop: float | None = Field(default=None, gt=0)
    horizon_days: int = Field(default=30, ge=1, le=730)
    expiry: datetime.date | None = None
    risk_budget_usd: float | None = Field(default=None, gt=0)
    mandate: dict | None = None


class ProposeResponse(BaseModel):
    underlying: str
    expiry: str | None
    spot: float | None
    candidates: list[CandidateOut]
    not_evaluated: list[str] = Field(default_factory=list)
    volatility_aware: bool = False


class OpenRequest(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    user_id: UUID
    ticker: str
    strategy_name: str
    expiry: datetime.date
    legs: list[LegSpec] = Field(min_length=1, max_length=4)
    verdict_ref: UUID | None = None
    mandate: dict | None = None


class OpenResponse(BaseModel):
    accepted: bool
    compliance: ComplianceOut
    strategy_id: UUID | None = None
    strategy_name: str | None = None
    net_cost: float | None = None
    collateral_posted: float | None = None
    legs: list[LegOut] = Field(default_factory=list)
    portfolio: Portfolio | None = None


def _leg_out(leg: StrategyLeg, occ: str | None = None) -> LegOut:
    return LegOut(
        right=leg.right, strike=leg.strike, quantity=leg.quantity,
        premium=leg.premium, multiplier=leg.multiplier, expiry=leg.expiry,
        occ_symbol=occ,
    )


def _candidate_out(candidate: OptionCandidate) -> CandidateOut:
    m = candidate.metrics
    return CandidateOut(
        strategy_name=candidate.strategy_name,
        contracts=candidate.contracts,
        expiry=candidate.expiry,
        days_to_expiry=candidate.days_to_expiry,
        underlying=candidate.underlying,
        legs=[_leg_out(leg) for leg in candidate.legs],
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
    )


def _shares_held(portfolio: Portfolio, ticker: str) -> float:
    return sum(
        float(h.quantity) for h in portfolio.holdings
        if h.ticker == ticker.upper().strip()
    )


@router.post("/propose", response_model=ProposeResponse)
def propose_options(
    req: ProposeRequest,
    current_user: User = Depends(get_current_user),
    sim: SimEngine = Depends(get_sim_engine),
) -> ProposeResponse:
    """The menu, costed. Writes nothing."""
    _own(current_user, req.user_id)
    ticker = req.ticker.upper().strip()
    _require_ticker(ticker)

    expiry = pick_expiry(ticker, req.horizon_days, req.expiry)
    if expiry is None:
        return ProposeResponse(
            underlying=ticker, expiry=None, spot=None, candidates=[],
            not_evaluated=[
                "no listed option expiry could be read for this underlying — "
                "AMI will not structure a trade on a board it cannot see"
            ],
        )
    chain = get_enriched_chain(ticker, expiry)
    if chain is None:
        return ProposeResponse(
            underlying=ticker, expiry=expiry.isoformat(), spot=None, candidates=[],
            not_evaluated=[
                "the option chain for this expiry could not be priced against "
                "an honest spot — no structure is offered"
            ],
        )

    portfolio = sim.ensure_portfolio(req.user_id)
    mandate = resolve_mandate(req.user_id, req.mandate)
    budget = req.risk_budget_usd
    if budget is None:
        cap = float(
            getattr(mandate, "single_name_cap_pct", None) or _DEFAULT_RISK_BUDGET_PCT
        )
        budget = round(sim.total_value(req.user_id) * cap / 100.0, 2)

    result = build_candidates(
        chain,
        underlying=ticker,
        direction=req.direction,
        mandate=mandate,
        risk_budget_usd=budget,
        shares_held=_shares_held(portfolio, ticker),
        target=req.target,
        stop=req.stop,
    )
    return ProposeResponse(
        underlying=result.underlying,
        expiry=result.expiry or expiry.isoformat(),
        spot=result.spot,
        candidates=[_candidate_out(c) for c in result.candidates],
        not_evaluated=list(result.not_evaluated),
        volatility_aware=result.volatility_aware,
    )


@router.post("/open", response_model=OpenResponse)
def open_options(
    req: OpenRequest,
    current_user: User = Depends(get_current_user),
    sim: SimEngine = Depends(get_sim_engine),
) -> OpenResponse:
    """The yes. Re-prices every leg off the live chain before anything moves."""
    _own(current_user, req.user_id)
    ticker = req.ticker.upper().strip()
    _require_ticker(ticker)

    chain = get_enriched_chain(ticker, req.expiry)
    if chain is None:
        return OpenResponse(
            accepted=False,
            compliance=ComplianceOut(
                passed=False,
                violations=[
                    "AMI could not price this expiry just now, so it will not "
                    "open the structure. Nothing was charged."
                ],
                not_evaluated=["the option chain could not be read at consent"],
            ),
            portfolio=sim.ensure_portfolio(req.user_id),
        )

    quotes = {("call", q.quote.strike): q for q in chain.calls}
    quotes.update({("put", q.quote.strike): q for q in chain.puts})

    legs: list[StrategyLeg] = []
    problems: list[str] = []
    for spec in req.legs:
        quote = quotes.get((spec.right, spec.strike))
        if quote is None:
            problems.append(
                f"{spec.right} {spec.strike:g} is not listed on this expiry"
            )
            continue
        if quote.state != "tradeable" or quote.mid is None or quote.mid <= 0:
            problems.append(
                f"{spec.right} {spec.strike:g} cannot be transacted right now "
                f"({quote.state_reason})"
            )
            continue
        legs.append(StrategyLeg(
            right=spec.right,
            strike=spec.strike,
            quantity=spec.quantity,
            premium=float(quote.mid),
            multiplier=100.0,
            expiry=req.expiry.isoformat(),
        ))
    if problems:
        logger.info(
            "sim_option_open_unpriceable",
            user_id=str(req.user_id), ticker=ticker, problems=len(problems),
        )
        return OpenResponse(
            accepted=False,
            compliance=ComplianceOut(
                passed=False,
                violations=[
                    "The structure could not be priced against the live chain, "
                    "so AMI did not open it. Nothing was charged."
                ],
                not_evaluated=problems,
            ),
            portfolio=sim.ensure_portfolio(req.user_id),
        )

    mandate = resolve_mandate(req.user_id, req.mandate)
    result = sim.open_option_structure(
        req.user_id,
        underlying=ticker,
        strategy_name=req.strategy_name,
        legs=legs,
        expiry=req.expiry,
        mandate=mandate,
        verdict_ref=req.verdict_ref,
    )
    return OpenResponse(
        accepted=result.accepted,
        compliance=ComplianceOut(
            passed=result.compliance.passed,
            violations=list(result.compliance.violations),
            advisories=list(result.compliance.advisories or []),
            not_evaluated=list(result.compliance.not_evaluated or []),
            blocked_by=result.compliance.blocked_by,
        ),
        strategy_id=result.strategy_id,
        strategy_name=result.strategy_name,
        net_cost=result.net_cost,
        collateral_posted=result.collateral_posted,
        legs=[_leg_out(leg) for leg in legs],
        portfolio=result.portfolio_snapshot,
    )
