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
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.dependencies import get_current_user
from app.core.logging import logger
from app.core.time import now_utc
from app.db.session import get_session
from app.schemas.options import (
    ComplianceOut,
    CostedStructure,
    as_utc,
    LegOut,
    costed_structure,
    leg_out,
)
from app.schemas.trade import Portfolio
from app.schemas.user import User
from app.services.mandate_store import resolve_mandate
from app.services.option_chain import get_enriched_chain, pick_expiry
from app.services.option_strategist import (
    OptionCandidate,
    build_candidates,
    cost_existing_structure,
)
from app.services.sim_engine import SimEngine, get_sim_engine
from app.services.ticker_reference import (
    TickerNotFoundError,
    require_ticker_exists,
    ticker_not_found_detail,
)
from app.trading_math.option_strategy import StrategyLeg, strategy_metrics
from app.trading_math.risk import drawdown_contribution

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
# CR172 — a LOSS percentage now, not a position-size percentage. Used only
# when the mandate carries no `max_open_risk_pct` at all.
_DEFAULT_MAX_LOSS_PCT = 5.0


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


# CR172 — these moved to `app.schemas.options` when the Room verdict and
# `/reprice` began describing the same thing. `CandidateOut` is kept as a name
# because it reads correctly at the /propose call site — a menu entry IS a
# candidate — but it is the identical class, so a field can never exist on one
# surface and not the other.
CandidateOut = CostedStructure


class ProposeRequest(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    user_id: UUID
    ticker: str
    direction: str = Field(pattern="^(bullish|bearish|neutral)$")
    target: float | None = Field(default=None, gt=0)
    stop: float | None = Field(default=None, gt=0)
    horizon_days: int = Field(default=30, ge=1, le=730)
    expiry: datetime.date | None = None
    # CR172 — renamed from `risk_budget_usd`, which two callers read two
    # different ways: /propose treated it as a position-size cap and the
    # Room as a loss budget, 28x apart on the same $10k book while both
    # fed the same divisor. Saiful's ruling (2026-08-22): it means
    # **lose at most $X**, everywhere, and the name now says so.
    max_loss_budget_usd: float | None = Field(default=None, gt=0)
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


def _shares_held(portfolio: Portfolio, ticker: str) -> float:
    return sum(
        float(h.quantity) for h in portfolio.holdings
        if h.ticker == ticker.upper().strip()
    )


def result_spot_for_budget(chain) -> float | None:
    """The chain's own spot, if it has one. Kept tiny and named so the budget
    derivation below reads as one idea rather than an attribute walk."""
    spot = getattr(chain, "spot", None)
    return float(spot) if spot else None


def _default_max_loss_budget(
    *, mandate, portfolio_value: float, spot: float | None, stop: float | None,
) -> float:
    """A **loss** budget, when the caller named none (CR172).

    This used to be `portfolio_value x single_name_cap_pct`, which is a
    POSITION-SIZE cap — how much to deploy, not how much to lose. It was then
    handed to `_size_to_budget`, which divides by max loss. On a $10,000 book a
    20% single-name cap produced $2,000 where the Room, sizing the same trade
    off the equity leg's own dollar risk, produced ~$70: the same field meaning
    two things 28x apart, with nothing in the name to catch it.

    Two honest derivations, in order of how much they actually know:

    1. **A stop was supplied.** Then the position cap converts exactly, using
       the same function the safety floor enforces the drawdown cap with:
       a position of `single_name_cap_pct` stopped at `stop` costs
       `contribution_pts` of the portfolio. This is the Room's own derivation,
       so the two callers now agree by construction rather than by comment.
    2. **No stop.** A position cap cannot be turned into a loss without one --
       "spend $2,000" says nothing about the downside. So fall back to a figure
       that is ALREADY a loss in percentage points: `max_open_risk_pct`, which
       CR129 derives from the user's own `max_drawdown_pct`. Never
       `single_name_cap_pct` here; that is the substitution this whole change
       exists to stop.
    """
    if spot and stop:
        cap = float(getattr(mandate, "single_name_cap_pct", None) or 0.0)
        if cap > 0:
            contribution = drawdown_contribution(cap, spot, stop)
            if contribution is not None:
                return round(
                    portfolio_value * contribution.contribution_pts / 100.0, 2
                )

    loss_pct = float(
        getattr(mandate, "max_open_risk_pct", None) or _DEFAULT_MAX_LOSS_PCT
    )
    return round(portfolio_value * loss_pct / 100.0, 2)



class LegAsShown(BaseModel):
    """A leg the client is holding, with the premium it was SHOWN.

    `premium_then` is display-only and is never trusted for money: it exists so
    the server can compute the drift itself rather than have the client
    subtract two numbers, keeping the ticket's "computes nothing" fence intact.
    A client that lies about it flatters its own drift line and changes nothing
    else — `/open` re-prices regardless, and so does `/reprice`.
    """

    right: str = Field(pattern="^(call|put)$")
    strike: float = Field(gt=0)
    quantity: float = Field(description="SIGNED contracts: + long, - short")
    premium_then: float | None = Field(default=None, ge=0)


class RepriceRequest(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    user_id: UUID
    ticker: str
    strategy_name: str
    expiry: datetime.date
    legs: list[LegAsShown] = Field(min_length=1, max_length=4)
    spot_then: float | None = Field(default=None, gt=0)
    priced_at_then: datetime.datetime | None = None
    mandate: dict | None = None

    @field_validator("priced_at_then")
    @classmethod
    def _utc(cls, v):
        # An older client — or any client that echoes back a stamp minted before
        # `CostedStructure` began forcing an offset — sends a naive string. It
        # means UTC; subtracting it from an aware `now` would raise instead.
        return as_utc(v)


class LegDriftOut(BaseModel):
    right: str
    strike: float
    quantity: float
    premium_then: float | None
    premium_now: float
    change: float | None


class DriftOut(BaseModel):
    """What moved between the price the user was shown and the price now.

    Every field is `None` when its "then" half was not supplied — a drift
    against an unknown baseline is not zero drift, and rendering it as zero
    would tell the user nothing moved when the truth is that nobody knows.
    """

    spot_then: float | None = None
    spot_now: float | None = None
    spot_change: float | None = None
    spot_change_pct: float | None = None
    net_cost_then: float | None = None
    net_cost_now: float
    net_cost_change: float | None = None
    net_cost_change_pct: float | None = None
    max_loss_then: float | None = None
    max_loss_now: float | None = None
    aged_seconds: float | None = None
    legs: list[LegDriftOut] = Field(default_factory=list)


class RepriceResponse(BaseModel):
    """The structure, costed again. Nothing was opened and nothing charged.

    `structure` is authoritative and `drift` is narration. They are separate
    fields rather than one merged object because a client that renders the
    drift is telling a story about the past, and a client that renders the
    structure is stating what a tap will cost — conflating them is how a stale
    figure ends up on the button.
    """

    repriced: bool
    structure: CostedStructure | None = None
    compliance: ComplianceOut
    drift: DriftOut | None = None


def _price_legs(
    chain, specs: list[LegSpec], expiry: datetime.date,
) -> tuple[list[StrategyLeg], list[str]]:
    """Client-stated shape + server-read price. The only place either happens.

    `/open` and `/reprice` must produce the same premium for the same leg on
    the same chain — otherwise the figure shown at consent is computed by
    different code than the figure that charges, and any gap between them is
    unattributable. So there is one pricer and both call it.

    A leg that cannot be transacted becomes a SENTENCE, not a silent omission:
    a structure priced without one of its legs has a net cost that is simply
    wrong, and the caller is expected to refuse rather than round down.
    """
    quotes = {("call", q.quote.strike): q for q in chain.calls}
    quotes.update({("put", q.quote.strike): q for q in chain.puts})

    legs: list[StrategyLeg] = []
    problems: list[str] = []
    for spec in specs:
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
            expiry=expiry.isoformat(),
        ))
    return legs, problems


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
    budget = req.max_loss_budget_usd
    if budget is None:
        budget = _default_max_loss_budget(
            mandate=mandate,
            portfolio_value=sim.total_value(req.user_id),
            spot=result_spot_for_budget(chain),
            stop=req.stop,
        )

    result = build_candidates(
        chain,
        underlying=ticker,
        direction=req.direction,
        mandate=mandate,
        max_loss_budget_usd=budget,
        shares_held=_shares_held(portfolio, ticker),
        target=req.target,
        stop=req.stop,
    )
    # The spot and the clock are stamped on every candidate, not only on the
    # envelope: a structure that a client holds while the user thinks — or that
    # travels onto a Room verdict — has to be able to answer "what was the
    # market when you costed me?" without its envelope.
    priced_at = datetime.datetime.now(datetime.timezone.utc)
    return ProposeResponse(
        underlying=result.underlying,
        expiry=result.expiry or expiry.isoformat(),
        spot=result.spot,
        candidates=[
            costed_structure(c, spot=result.spot, priced_at=priced_at)
            for c in result.candidates
        ],
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

    legs, problems = _price_legs(chain, req.legs, req.expiry)
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
        legs=[leg_out(leg) for leg in legs],
        portfolio=result.portfolio_snapshot,
    )


def _pct(change: float | None, base: float | None) -> float | None:
    """Percent change, or None when the base cannot carry one.

    A zero base has no percent change — it has an undefined one — and printing
    0.0 there states that nothing moved off a number that could not move.
    """
    if change is None or base is None or base == 0:
        return None
    return round(change / abs(base) * 100.0, 2)


@router.post("/reprice", response_model=RepriceResponse)
def reprice_options(
    req: RepriceRequest,
    current_user: User = Depends(get_current_user),
    sim: SimEngine = Depends(get_sim_engine),
) -> RepriceResponse:
    """Cost this structure again, now. Opens nothing, charges nothing.

    **Why this exists as its own route.** `/open` already re-prices — it has to,
    it is the surface that moves cash — but it re-prices and fills in one
    motion, so the user never sees the number that charged them until after it
    charged them. Saiful's ruling on the consent flow (2026-08-23) is that the
    app re-prices live and shows what moved BEFORE opening, which is the DEF305
    rule stated as a product requirement: never act off a price nobody checked.

    So the sequence is proposal -> reprice -> the user reads the drift ->
    `/open`, and `/open` re-prices a third time regardless. That last re-price
    is not redundant with this one: seconds pass while the user reads, and a
    route that trusted this response would be trusting a price it did not take.
    This one informs; that one commits.

    `/propose` cannot serve this purpose. It regenerates the menu from
    blueprints and there is no guarantee the structure the user is holding is
    still in the list, let alone at the same strikes and contract count.
    """
    _own(current_user, req.user_id)
    ticker = req.ticker.upper().strip()
    _require_ticker(ticker)

    chain = get_enriched_chain(ticker, req.expiry)
    if chain is None:
        return RepriceResponse(
            repriced=False,
            compliance=ComplianceOut(
                passed=False,
                violations=[],
                not_evaluated=[
                    "the option chain for this expiry could not be read just "
                    "now, so AMI cannot tell you what this structure costs at "
                    "this moment"
                ],
            ),
        )

    specs = [
        LegSpec(right=leg.right, strike=leg.strike, quantity=leg.quantity)
        for leg in req.legs
    ]
    legs, problems = _price_legs(chain, specs, req.expiry)
    if problems or len(legs) != len(req.legs):
        return RepriceResponse(
            repriced=False,
            compliance=ComplianceOut(
                passed=False, violations=[], not_evaluated=problems,
            ),
        )

    portfolio = sim.ensure_portfolio(req.user_id)
    mandate = resolve_mandate(req.user_id, req.mandate)
    candidate = cost_existing_structure(
        chain,
        underlying=ticker,
        strategy_name=req.strategy_name,
        legs=legs,
        mandate=mandate,
        shares_held=_shares_held(portfolio, ticker),
        days_to_expiry=max((req.expiry - datetime.date.today()).days, 0),
    )
    if candidate is None:
        return RepriceResponse(
            repriced=False,
            compliance=ComplianceOut(
                passed=False,
                violations=[],
                not_evaluated=[
                    "the structure could not be costed against this chain — "
                    "AMI will not show a total it cannot stand behind"
                ],
            ),
        )

    now = datetime.datetime.now(datetime.timezone.utc)
    structure = costed_structure(candidate, spot=chain.spot, priced_at=now)

    shown = {(leg.right, leg.strike): leg.premium_then for leg in req.legs}
    leg_drift = [
        LegDriftOut(
            right=leg.right,
            strike=leg.strike,
            quantity=leg.quantity,
            premium_then=shown.get((leg.right, leg.strike)),
            premium_now=leg.premium,
            change=(
                None if shown.get((leg.right, leg.strike)) is None
                else round(leg.premium - float(shown[(leg.right, leg.strike)]), 4)
            ),
        )
        for leg in legs
    ]
    # The "then" net cost is recomputed from the premiums the client says it was
    # shown, rather than taken as a number — same reason the ticket computes
    # nothing: whoever does the arithmetic owns the mistake, and here that is us.
    net_then: float | None = None
    max_loss_then: float | None = None
    if all(d.premium_then is not None for d in leg_drift):
        then_legs = [
            leg._replace(premium=float(shown[(leg.right, leg.strike)]))
            for leg in legs
        ]
        then_metrics = strategy_metrics(
            then_legs, shares_held=_shares_held(portfolio, ticker),
        )
        if then_metrics is not None:
            net_then = round(then_metrics.net_cost, 2)
            max_loss_then = then_metrics.max_loss
    net_now = structure.metrics.net_cost
    spot_change = (
        None if req.spot_then is None else round(chain.spot - req.spot_then, 4)
    )
    drift = DriftOut(
        spot_then=req.spot_then,
        spot_now=chain.spot,
        spot_change=spot_change,
        spot_change_pct=_pct(spot_change, req.spot_then),
        net_cost_then=net_then,
        net_cost_now=net_now,
        net_cost_change=(
            None if net_then is None else round(net_now - net_then, 2)
        ),
        net_cost_change_pct=_pct(
            None if net_then is None else net_now - net_then, net_then
        ),
        max_loss_then=max_loss_then,
        max_loss_now=structure.metrics.max_loss,
        aged_seconds=(
            None if req.priced_at_then is None
            else round((now - req.priced_at_then).total_seconds(), 1)
        ),
        legs=leg_drift,
    )
    logger.info(
        "sim_option_repriced",
        user_id=str(req.user_id), ticker=ticker,
        strategy=req.strategy_name,
        net_cost_change=drift.net_cost_change,
        aged_seconds=drift.aged_seconds,
    )
    return RepriceResponse(
        repriced=True,
        structure=structure,
        compliance=structure.compliance,
        drift=drift,
    )
