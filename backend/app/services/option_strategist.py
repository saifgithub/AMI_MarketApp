"""CR172 §10 step 1 — the candidate structures AMI offers, computed not chosen.

The Room's job on an options trade splits cleanly in two: the *direction* is an
equity judgement the twelve agents already make, and the *structure* is
arithmetic. This module does the arithmetic half. It takes the run's seeded
directional inputs, an enriched chain, the mandate and what the user already
holds, and emits fully costed candidates. The Portfolio Manager then picks one
by index (§10 step 2) and never states a strike, a premium or a greek that did
not come from here — P5 is explicit that an LLM asked to compute a number it
presents as fact is the defect.

Three rules this module holds to, each with a rival that quietly changes what
the user is shown:

* **A candidate that violates the mandate is MARKED, never hidden.** §10 is
  explicit: the PM should be able to say "the natural structure here is a naked
  call, which your mandate forbids, so instead…". Filtering the violators out
  deletes that teaching moment and leaves the user believing the menu was the
  whole menu. The marking comes from `check_option_open` — the floor itself, so
  there is one renderer of each rule (DEF098) and a candidate cannot be marked
  permitted by a check the floor would refuse.
* **A structure that cannot be costed is not emitted.** `strategy_metrics`
  returning None means the legs are unusable; a card built on that has a blank
  where the max loss goes, and CR040's question — *if this fires constantly and
  silently, what does the user end up believing?* — answers itself. The reason
  travels in `not_evaluated` on the response so the absence is loud.
* **Sizing is bounded by the risk the user can actually take, and when the risk
  is not a number the size is one contract.** An unbounded-loss structure has no
  budget-derived size; picking one anyway would be inventing a bound. It is
  emitted at a single contract with the reason recorded, and the floor refuses
  it separately if D3 applies.

What this module does NOT do: choose. It offers; `_parse_pm_verdict` validates
the choice against the set issued here and `enforce_safety_floor` remains the
only vetoer (DEF059).

Volatility-awareness is honest about its own absence. §10 wants IV rank versus
realised vol to order income structures against debit ones. When the caller
supplies a realised vol AND the chain carries an at-the-money IV, that ordering
runs; when either is missing the order is structural and a `not_evaluated` line
says so, because an ordering presented as volatility-aware when no volatility
was read is a claim we did not measure.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Sequence

from app.core.logging import logger
from app.schemas.mandate import Mandate
from app.services.option_chain import EnrichedChain, EnrichedOptionQuote
from app.trading_math.greeks import Greeks
from app.trading_math.option_strategy import (
    StrategyLeg,
    StrategyMetrics,
    combine_greeks,
    strategy_metrics,
)

CONTRACT_MULTIPLIER = 100.0

DIRECTIONS = ("bullish", "bearish", "neutral")

# Ordering when volatility cannot be read: long/defined-risk structures first,
# income structures after. Not a preference ranking — a stable order, so two
# identical runs issue identical `structure_id` indices (§10 step 3 validates
# the PM's pick against this list by position).
_STRUCTURE_ORDER = (
    "long_call",
    "bull_call_spread",
    "long_put",
    "bear_put_spread",
    "protective_put",
    "covered_call",
    "cash_secured_put",
)

# An IV this far above realised vol makes selling premium the structurally
# indicated trade rather than buying it. 1.1 is a threshold, not a model: it
# separates "options are dear" from measurement noise in the realised estimate.
_RICH_IV_RATIO = 1.1


@dataclass(frozen=True)
class OptionCandidate:
    """One fully costed structure — every figure the §10 card renders."""

    strategy_name: str
    legs: tuple[StrategyLeg, ...]
    metrics: StrategyMetrics
    net_greeks: Greeks | None
    greeks_not_evaluated: tuple[str, ...]
    contracts: int
    expiry: str
    days_to_expiry: int
    underlying: str
    mandate_violations: tuple[str, ...]
    advisories: tuple[str, ...]
    not_evaluated: tuple[str, ...]
    rationale: str


@dataclass(frozen=True)
class CandidateSet:
    """What `build_candidates` returns: the menu, and why it is this size."""

    candidates: tuple[OptionCandidate, ...]
    underlying: str
    expiry: str
    spot: float
    not_evaluated: tuple[str, ...]
    volatility_aware: bool


def _tradeable(quotes: tuple[EnrichedOptionQuote, ...]) -> list[EnrichedOptionQuote]:
    """Only strikes that can actually be transacted at a known price.

    `worthless` and `unusable` both carry a mid we must not build a card on:
    the first is a real quote meaning nobody wants it, the second means the
    provider served something we could not read. Neither is a price.
    """
    return [
        q for q in quotes
        if q.state == "tradeable" and q.mid is not None and q.mid > 0
    ]


def _nearest(
    quotes: list[EnrichedOptionQuote], price: float
) -> EnrichedOptionQuote | None:
    """The tradeable strike closest to `price`; ties go to the lower strike."""
    if not quotes or not _finite_positive(price):
        return None
    return min(quotes, key=lambda q: (abs(q.quote.strike - price), q.quote.strike))


def _finite_positive(value: float | None) -> bool:
    try:
        return value is not None and float(value) > 0 and float(value) == float(value)
    except (TypeError, ValueError):
        return False


def _leg(
    quote: EnrichedOptionQuote, right: str, contracts: float, expiry: str
) -> StrategyLeg:
    assert quote.mid is not None
    return StrategyLeg(
        right=right,
        strike=float(quote.quote.strike),
        quantity=float(contracts),
        premium=float(quote.mid),
        multiplier=CONTRACT_MULTIPLIER,
        expiry=expiry,
    )


def _scale(legs: tuple[StrategyLeg, ...], contracts: int) -> tuple[StrategyLeg, ...]:
    """Re-issue a one-contract structure at `contracts`, signs preserved."""
    return tuple(
        leg._replace(quantity=leg.quantity * contracts) for leg in legs
    )


def _size_to_budget(
    legs: tuple[StrategyLeg, ...], budget_usd: float, shares_held: float
) -> tuple[int, str | None]:
    """How many contracts of this structure the risk budget buys.

    Returns `(contracts, reason_not_sized)`. The reason is set whenever the
    count fell back to one rather than being divided out of the budget — an
    unbounded loss, a loss bounded by shares rather than by the legs, or a
    budget too small to buy a single contract. Sizing off a budget when the
    loss has no ceiling would be inventing the ceiling.

    DEF354 — that last case used to return `(1, None)`: silent. One contract
    is the right answer (a menu that hides the structure teaches nothing), but
    it is not the *sized* answer, and the gap is not small. Measured on the
    first live convene of this path: a $10,000 paper portfolio risking 3% at a
    6% stop has an $18 budget against a ~$920 at-the-money contract, so every
    candidate was offered at **51x** the risk the equivalent share trade would
    have taken, described as sized to the mandate. $10,000 is the starting
    portfolio for every alpha user, so this was not an edge case — it was the
    ordinary case. CR040's question answers itself: a user told AMI sized this
    to their budget, when it did the opposite.
    """
    unit = strategy_metrics(legs, shares_held=shares_held)
    if unit is None:
        return 1, "structure could not be costed at one contract"
    risk = unit.max_loss
    if risk is None or risk <= 0:
        if unit.unbounded_loss:
            return 1, "loss has no ceiling, so no budget divides into it"
        if unit.covered_by_shares:
            return 1, "loss is bounded by shares held, not by the legs"
        return 1, "structure carries no computable loss to size against"
    if not _finite_positive(budget_usd):
        return 1, "no risk budget was supplied"
    count = int(budget_usd // risk)
    if count < 1:
        # One decimal under 10x, none above: a $9,030 loss against a $9,000
        # budget is a 0.3% overrun, and printing it as a flat "1x" reads as
        # "exactly the budget" — the opposite of the disclosure's job. The two
        # dollar figures carry the fact; the multiple is there so nobody has to
        # divide (CR179 Leg 4's reasoning), and it has to survive both ends of
        # its own range to be worth printing.
        over = risk / budget_usd
        gap = f"{over:.1f}x" if over < 10 else f"{over:.0f}x"
        return 1, (
            f"the risk budget of ${budget_usd:,.0f} does not cover one "
            f"contract, whose loss is ${risk:,.0f} — offered at the minimum "
            f"size of one, which risks {gap} the budget"
        )
    return count, None


def _greeks_for(
    parts: list[tuple[EnrichedOptionQuote, float]]
) -> tuple[Greeks | None, tuple[str, ...]]:
    """Net greeks across the legs, or None with the reason each leg failed.

    A structure whose greeks are half-computed is worse than one with none:
    summing the legs that happened to price gives a net delta that reads as
    the position's exposure and is not.
    """
    missing = [
        f"{q.right} {q.quote.strike:g}: {q.greeks_reason or 'greeks not computed'}"
        for q, _ in parts
        if q.greeks is None
    ]
    if missing:
        return None, tuple(missing)
    return (
        combine_greeks([
            (contracts, CONTRACT_MULTIPLIER, q.greeks)  # type: ignore[arg-type]
            for q, contracts in parts
        ]),
        (),
    )


def _atm_iv(chain: EnrichedChain) -> float | None:
    """The at-the-money implied vol, calls and puts averaged where both price."""
    ivs: list[float] = []
    for side in (chain.calls, chain.puts):
        near = _nearest(_tradeable(side), chain.spot)
        if near is not None and _finite_positive(near.iv_used):
            ivs.append(float(near.iv_used))  # type: ignore[arg-type]
    if not ivs:
        return None
    return sum(ivs) / len(ivs)


def _income_first(chain: EnrichedChain, realised_vol: float | None) -> bool | None:
    """True when premium is dear enough that selling it is the indicated side.

    None means the comparison could not be made — the caller records that
    rather than presenting a structural order as a volatility judgement.
    """
    if not _finite_positive(realised_vol):
        return None
    iv = _atm_iv(chain)
    if not _finite_positive(iv):
        return None
    return float(iv) > float(realised_vol) * _RICH_IV_RATIO  # type: ignore[arg-type]


_INCOME_STRUCTURES = frozenset({"covered_call", "cash_secured_put"})


def _order_key(name: str, income_first: bool | None) -> tuple[int, int]:
    base = _STRUCTURE_ORDER.index(name) if name in _STRUCTURE_ORDER else len(
        _STRUCTURE_ORDER
    )
    if income_first is None:
        return (0, base)
    return (0 if (name in _INCOME_STRUCTURES) == income_first else 1, base)


def build_candidates(
    chain: EnrichedChain,
    *,
    underlying: str,
    direction: str,
    mandate: Mandate,
    max_loss_budget_usd: float,
    shares_held: float = 0.0,
    target: float | None = None,
    stop: float | None = None,
    realised_vol: float | None = None,
    now: datetime.datetime | None = None,
    portfolio_value: float | None = None,
    existing_structures: Sequence[Sequence[StrategyLeg]] = (),
) -> CandidateSet:
    """Every structure this chain supports for this direction, fully costed.

    `direction` is the equity judgement the Room already made — "bullish",
    "bearish" or "neutral". `target` and `stop` anchor the strikes that carry
    a view (the short leg of a spread, the floor of a protective put); when
    either is missing the structures that need it are skipped with the reason
    recorded, never re-anchored onto a strike we invented.
    """
    from app.agents.safety_floor import check_option_open

    reasons: list[str] = []
    ticker = underlying.upper().strip()
    if direction not in DIRECTIONS:
        reasons.append(f"unknown direction {direction!r} — no structures built")
        return CandidateSet((), ticker, "", chain.spot, tuple(reasons), False)

    expiry = chain.chain.expiry.isoformat()
    now = now or datetime.datetime.now(datetime.UTC)
    days_to_expiry = max(0, (chain.chain.expiry - now.date()).days)

    calls = _tradeable(chain.calls)
    puts = _tradeable(chain.puts)
    if not calls and not puts:
        reasons.append(
            "no strike on this expiry carries a transactable quote — "
            "every call and put was worthless, crossed or unquoted"
        )
        return CandidateSet((), ticker, expiry, chain.spot, tuple(reasons), False)

    atm_call = _nearest(calls, chain.spot)
    atm_put = _nearest(puts, chain.spot)
    target_call = _nearest(calls, target) if _finite_positive(target) else None
    target_put = _nearest(puts, target) if _finite_positive(target) else None
    stop_put = _nearest(puts, stop) if _finite_positive(stop) else None

    # (name, one-contract legs, quotes-with-signed-contracts, rationale)
    blueprints: list[tuple[str, tuple[StrategyLeg, ...], list[tuple[EnrichedOptionQuote, float]], str]] = []

    def add(
        name: str,
        parts: list[tuple[EnrichedOptionQuote, str, float]],
        rationale: str,
    ) -> None:
        legs = tuple(_leg(q, right, qty, expiry) for q, right, qty in parts)
        blueprints.append(
            (name, legs, [(q, qty) for q, _, qty in parts], rationale)
        )

    if direction == "bullish":
        if atm_call is not None:
            add(
                "long_call",
                [(atm_call, "call", 1.0)],
                "The simplest expression of the view: the whole loss is the "
                "premium, paid up front, and it is the only figure at risk.",
            )
            if target_call is not None and target_call.quote.strike > atm_call.quote.strike:
                add(
                    "bull_call_spread",
                    [(atm_call, "call", 1.0), (target_call, "call", -1.0)],
                    "The same view, capped at the Room's own target: selling "
                    "the target strike pays for part of the entry and gives up "
                    "the gain above a price the analysis did not forecast.",
                )
            elif _finite_positive(target):
                reasons.append(
                    "no tradeable call strike above the money at or near the "
                    "target — the spread was not built"
                )
            else:
                reasons.append("no target price — the call spread was not built")
        else:
            reasons.append("no tradeable call near the money")
        if stop_put is not None:
            add(
                "cash_secured_put",
                [(stop_put, "put", -1.0)],
                "Getting paid to bid: the premium is kept if the stock holds "
                "above the strike, and assignment buys the shares at the level "
                "the analysis called support — fully funded, no leverage.",
            )
        elif _finite_positive(stop):
            reasons.append("no tradeable put strike near the stop")

    if direction == "bearish":
        if atm_put is not None:
            add(
                "long_put",
                [(atm_put, "put", 1.0)],
                "Bounded-loss bearish exposure with no borrow and no "
                "assignment risk: the premium is the whole downside.",
            )
            if target_put is not None and target_put.quote.strike < atm_put.quote.strike:
                add(
                    "bear_put_spread",
                    [(atm_put, "put", 1.0), (target_put, "put", -1.0)],
                    "The same view capped at the target: the strike below pays "
                    "for part of the entry and surrenders the move past a price "
                    "the analysis did not forecast.",
                )
            elif _finite_positive(target):
                reasons.append(
                    "no tradeable put strike below the money at or near the "
                    "target — the spread was not built"
                )
            else:
                reasons.append("no target price — the put spread was not built")
        else:
            reasons.append("no tradeable put near the money")

    if shares_held >= CONTRACT_MULTIPLIER:
        if stop_put is not None:
            add(
                "protective_put",
                [(stop_put, "put", 1.0)],
                "Insurance on shares already held: the premium buys a floor at "
                "the strike, and the shares keep every dollar above it.",
            )
        if target_call is not None and direction != "bearish":
            add(
                "covered_call",
                [(target_call, "call", -1.0)],
                "Rent on shares already held: the premium is kept, and the "
                "shares are called away at the target if it trades there. The "
                "shares cover the call, so nothing here is uncovered.",
            )
    elif direction == "neutral" and stop_put is not None:
        add(
            "cash_secured_put",
            [(stop_put, "put", -1.0)],
            "No directional edge, so the trade is the premium itself: kept if "
            "the stock holds the level, assigned at it if not.",
        )

    if not blueprints:
        reasons.append(
            f"no structure could be assembled for a {direction} view on this "
            "expiry from the strikes that quote"
        )
        return CandidateSet((), ticker, expiry, chain.spot, tuple(reasons), False)

    income_first = _income_first(chain, realised_vol)
    if income_first is None:
        reasons.append(
            "implied versus realised volatility could not be read — the order "
            "below is structural, not a volatility judgement"
        )

    built: list[OptionCandidate] = []
    for name, unit_legs, parts, rationale in blueprints:
        contracts, size_reason = _size_to_budget(
            unit_legs, max_loss_budget_usd, shares_held
        )
        legs = _scale(unit_legs, contracts)
        metrics = strategy_metrics(legs, shares_held=shares_held)
        if metrics is None:
            reasons.append(f"{name}: could not be costed — not offered")
            logger.warn(
                "option_candidate_uncostable", underlying=ticker, strategy=name,
            )
            continue
        greeks, greeks_missing = _greeks_for(
            [(q, qty * contracts) for q, qty in parts]
        )
        # CR172 §9 — marked with the SAME book context the open path enforces
        # with, so a candidate the floor will refuse is never offered as though
        # it would be accepted. Without this the user would meet the cap only
        # after saying yes, which is the late-refusal shape DEF305 is about.
        compliance = check_option_open(
            legs, mandate,
            shares_held=shares_held,
            portfolio_value=portfolio_value,
            existing_structures=existing_structures,
        )
        per_candidate: list[str] = []
        if size_reason:
            per_candidate.append(f"sized at one contract — {size_reason}")
        built.append(
            OptionCandidate(
                strategy_name=name,
                legs=legs,
                metrics=metrics,
                net_greeks=greeks,
                greeks_not_evaluated=greeks_missing,
                contracts=contracts,
                expiry=expiry,
                days_to_expiry=days_to_expiry,
                underlying=ticker,
                mandate_violations=tuple(compliance.violations),
                advisories=tuple(compliance.advisories or ()),
                not_evaluated=(
                    *per_candidate, *(compliance.not_evaluated or ()),
                ),
                rationale=rationale,
            )
        )

    built.sort(key=lambda c: _order_key(c.strategy_name, income_first))
    logger.info(
        "option_candidates_built",
        underlying=ticker,
        expiry=expiry,
        direction=direction,
        candidates=len(built),
        marked=sum(1 for c in built if c.mandate_violations),
    )
    return CandidateSet(
        candidates=tuple(built),
        underlying=ticker,
        expiry=expiry,
        spot=chain.spot,
        not_evaluated=tuple(reasons),
        volatility_aware=income_first is not None,
    )


def cost_existing_structure(
    chain: EnrichedChain,
    *,
    underlying: str,
    strategy_name: str,
    legs: Sequence[StrategyLeg],
    mandate: Mandate,
    shares_held: float = 0.0,
    days_to_expiry: int,
    rationale: str = "",
    portfolio_value: float | None = None,
    existing_structures: Sequence[Sequence[StrategyLeg]] = (),
) -> OptionCandidate | None:
    """Re-cost a structure that already exists, against this chain.

    `build_candidates` answers *"what should we propose?"*. This answers the
    other question the consent flow asks: *"what does the thing already on the
    table cost NOW?"* — and it must be answered by the same assembly, or the
    figures shown at consent are produced by different code than the figures
    shown at proposal, and any discrepancy between them is unattributable.

    **The premium comes off the chain, never off the caller's legs.** The
    quantity, right and strike are the caller's — that is the shape of the
    structure — but every price is re-read here. `POST /reprice` happens to
    hand in legs it has already priced through `_price_legs`, so today this
    re-read changes nothing; it stays because this is a public function and the
    next caller will not necessarily have done that. `net_cost` moves cash, so
    a caller-supplied premium mints it, and a fence that only holds while an
    upstream caller remembers is not a fence.
    `test_cost_existing_structure_ignores_the_premium_it_was_handed` drives
    this function directly, past `_price_legs`, for exactly that reason.

    Returns `None` when any leg cannot be priced against this chain — a
    partially-priced structure is not a cheaper answer, it is a wrong one, and
    the caller must say so rather than show a total that omits a leg.
    """
    # Deferred for the same reason `build_candidates` defers it: the safety
    # floor imports back into this layer, and a module-level import here closes
    # the cycle at interpreter start.
    from app.agents.safety_floor import check_option_open

    quotes = {("call", q.quote.strike): q for q in chain.calls}
    quotes.update({("put", q.quote.strike): q for q in chain.puts})

    parts: list[tuple[EnrichedOptionQuote, float]] = []
    priced: list[StrategyLeg] = []
    for leg in legs:
        quote = quotes.get((leg.right, leg.strike))
        if quote is None or quote.mid is None or quote.mid <= 0:
            return None
        priced.append(leg._replace(premium=float(quote.mid)))
        parts.append((quote, leg.quantity))

    costed = tuple(priced)
    metrics = strategy_metrics(costed, shares_held=shares_held)
    if metrics is None:
        return None
    greeks, greeks_missing = _greeks_for(parts)
    compliance = check_option_open(
        costed, mandate,
        shares_held=shares_held,
        portfolio_value=portfolio_value,
        existing_structures=existing_structures,
    )
    contracts = int(max(abs(leg.quantity) for leg in costed)) if costed else 0
    return OptionCandidate(
        strategy_name=strategy_name,
        legs=costed,
        metrics=metrics,
        net_greeks=greeks,
        greeks_not_evaluated=greeks_missing,
        contracts=contracts,
        expiry=costed[0].expiry,
        days_to_expiry=days_to_expiry,
        underlying=underlying,
        mandate_violations=tuple(compliance.violations),
        advisories=tuple(compliance.advisories or ()),
        not_evaluated=tuple(compliance.not_evaluated or ()),
        rationale=rationale,
    )
