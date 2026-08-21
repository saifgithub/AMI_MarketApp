"""CR172 §7 — what happens to an option position when nobody touches it.

Slice 2. Expiry, OCC exercise-by-exception, assignment, early assignment and
pin risk, as **pure rules plus one effect calculator**. The row mutations live
in `SimEngine.run_option_lifecycle`, which owns holdings mechanics and reuses
`_apply_buy_row` / `_apply_sell_row` — exercise converting an option into 100
shares is an ordinary fill and must not get its own mechanics (§7).

## The one settlement rule, and why it is one rule

OCC exercises by exception: **in the money by $0.01 or more at the close on
expiry day is exercised, everything else expires worthless.** Long legs are
exercised, short legs are assigned — the same event seen from the two sides of
the contract, which is why one decision function answers for both and the sign
of `quantity` picks the side.

The threshold is measured on the RAW distance (`S − K` for a call, `K − S` for
a put), not on a rounded intrinsic value. A call $0.006 in the money rounds to
a penny and is still not exercised; taking the rounded number would exercise
it, and the position would settle for a cent it never earned.

## Pin risk is flagged, never simulated

An option expiring within pennies of its strike may or may not be exercised in
a real market — the holder has until 17:30 ET to file contrary instructions.
We pick the deterministic rule and **teach that pin risk exists** rather than
roll dice a user cannot learn anything from (§7). `pin_risk=True` rides on the
event so the surface can say so.

## The cash model, stated once

Slice 3 opens positions; the lifecycle has to know what those positions mean,
so the invariant is written here and both halves are held to it:

* **long leg** — `premium × shares` leaves cash, `collateral_posted = 0`, and
  the leg is worth `mark × shares`.
* **short leg** — the premium received NEVER enters cash; `collateral_posted`
  is posted and `collateral − premium × shares` leaves cash, so the leg is
  worth `collateral_posted − mark × shares`.

That is CR171's short model verbatim (`sim_shorts`'s `cash_required_for`), for
the same reason: a credit that is not spendable is indistinguishable from a
profit in the NAV series every downstream number is computed from.

Every settlement therefore releases `collateral_posted` in full and then pays
or collects the settlement leg. Under that rule **total value is continuous
across every settlement** — the cash and shares that arrive are worth exactly
the leg that left. A long call exercised at $110 on a $100 strike pays
`100 × K` and receives stock worth `100 × S`; the difference is the `(S − K)`
the option was worth a moment earlier.

## Premium goes into the basis when shares arrive, and is realised when they leave

An exercise that ADDS stock folds the premium into the lot's cost basis
(`strike + premium` for an exercised long call, `strike − premium` for an
assigned short put) and the leg realises nothing — the P&L is still live, in
the stock. An exercise that REMOVES stock realises the premium on the leg
(`−premium` for a long put, `+premium` for an assigned short call) because the
equity lot books its own `(strike − avg_cost)` and the premium belongs to
neither side of that subtraction. Either way the sum is the truth once and the
CR172 §11 lot-accounting slice has one convention to build on, not two.

## Physical settlement can degrade, and says so

Taking delivery needs cash; delivering stock needs stock. When either is
missing the leg is **cash-settled at parity** — economically identical to the
sell-to-close a broker would do for you — and `downgrade` carries the reason
so the event can say what happened instead of quietly moving a different
number. A short put never degrades: its collateral is exactly `strike ×
shares`, posted at open for precisely this moment, and CR171 §7's rule that a
forced close is never refused for insufficient cash holds here too.

Pure, no session, no config: every function below is a decision or an
arithmetic effect. Anything it cannot decide returns `None` and the caller
records `not_evaluated` (DEF169) — never a silent settlement.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import NamedTuple
from uuid import UUID

from app.trading_math.option import option_intrinsic_value

# OCC exercise by exception: ITM by this much or more, at the close on expiry
# day, is exercised. Below it the contract expires worthless even though it
# holds value — the single most surprising rule in the product, and the reason
# `in_the_money_by` travels on the decision so a surface can explain it.
EXERCISE_BY_EXCEPTION_THRESHOLD = 0.01

# Within this much of the strike at expiry, the outcome is a coin flip in a
# real market. We still apply the deterministic rule; the flag exists so the
# user is told the rule was close to going the other way.
PIN_RISK_BAND = 0.05

_RIGHTS = ("call", "put")

EXPIRE_WORTHLESS = "expire_worthless"
EXERCISE = "exercise"
ASSIGN = "assign"


class SettlementDecision(NamedTuple):
    """What expiry does to one leg, and how close it was to the other answer."""

    action: str              # expire_worthless | exercise | assign
    in_the_money_by: float   # raw S−K (call) / K−S (put); negative is OTM
    settlement_value: float  # per share, 2 dp; 0.0 when it expires worthless
    pin_risk: bool


class SettlementEffect(NamedTuple):
    """The money and the shares one settled leg moves."""

    mode: str                 # shares | cash
    shares_delta: float       # + delivered to the user, − taken from them
    strike_price: float       # the price the shares change hands at
    basis_price: float        # cost basis per share of an ADDED lot; 0.0 else
    cash_delta: float         # collateral released, plus/minus the settlement
    realised_pnl: float
    downgrade: str | None     # why physical settlement fell back to cash


class DividendEvent(NamedTuple):
    """The next cash dividend on an underlying — the early-assignment trigger."""

    ex_date: date
    amount_per_share: float


@dataclass
class LifecycleEvent:
    """One user-visible thing that happened to a leg without the user acting.

    §7: *every automatic close is reported, never silent.* A position that
    vanished overnight is the games lane's "the order simply VANISHED" defect
    on a bigger number — so this carries what happened, what it moved, and any
    compliance flag the resulting stock position raised, all the way to the
    caller rather than to a log line.
    """

    leg_id: UUID | None
    occ_symbol: str
    underlying: str
    action: str                # expired | exercised | assigned | not_evaluated
    settlement: str            # shares | cash | none
    contracts: float
    shares_delta: float
    cash_delta: float
    realised_pnl: float
    pin_risk: bool
    message: str
    # §8 allow-and-flag: what the mandate says about the position this
    # settlement CREATED. Never a refusal — the contract was already
    # exercised — and never empty-because-unchecked, which is what the
    # second list is for (DEF169).
    compliance_flags: list[str] = field(default_factory=list)
    compliance_not_evaluated: list[str] = field(default_factory=list)
    downgrade: str | None = None


def _finite(*values: float) -> bool:
    return all(isinstance(v, (int, float)) and math.isfinite(v) for v in values)


def settlement_decision(
    *, right: str, strike: float, quantity: float, settlement_price: float,
) -> SettlementDecision | None:
    """Expiry's verdict on one leg, or None when it cannot be decided.

    None means the inputs are unusable (a malformed right, a non-positive
    strike, a negative or missing settlement price, a flat leg). The caller
    leaves the leg open and records `not_evaluated` — settling on a price we
    do not trust is the one outcome worse than not settling at all.
    """
    r = right.strip().lower() if isinstance(right, str) else ""
    if r not in _RIGHTS:
        return None
    if not _finite(strike, quantity, settlement_price):
        return None
    if strike <= 0 or settlement_price < 0 or quantity == 0:
        return None

    in_the_money_by = (
        settlement_price - strike if r == "call" else strike - settlement_price
    )
    exercised = in_the_money_by >= EXERCISE_BY_EXCEPTION_THRESHOLD - 1e-9
    if not exercised:
        return SettlementDecision(
            action=EXPIRE_WORTHLESS,
            in_the_money_by=round(in_the_money_by, 4),
            settlement_value=0.0,
            pin_risk=abs(settlement_price - strike) < PIN_RISK_BAND,
        )

    intrinsic = option_intrinsic_value(r, strike, settlement_price)
    if intrinsic is None:
        return None
    return SettlementDecision(
        action=EXERCISE if quantity > 0 else ASSIGN,
        in_the_money_by=round(in_the_money_by, 4),
        settlement_value=intrinsic,
        pin_risk=abs(settlement_price - strike) < PIN_RISK_BAND,
    )


def early_assignment_due(
    *,
    right: str,
    quantity: float,
    strike: float,
    spot: float,
    option_mark: float,
    dividend: DividendEvent | None,
    on_date: date,
    expiry: date,
) -> bool:
    """D9's deterministic pre-dividend rule for a SHORT CALL.

    The only early exercise that is reliably rational on a US equity option is
    a deep-ITM call the day before an ex-dividend date, when the extrinsic
    value left in the contract is worth less than the dividend the holder
    would capture by exercising. That is a computation, not a coin flip, so it
    is modelled as one — and no probability model ships (§14 D9).

    False whenever the data to decide is missing: no dividend feed means no
    early assignment, and the caller says so out loud rather than implying the
    position is safe.
    """
    r = right.strip().lower() if isinstance(right, str) else ""
    if r != "call" or not isinstance(quantity, (int, float)) or quantity >= 0:
        return False
    if dividend is None or not isinstance(dividend.ex_date, date):
        return False
    if not _finite(strike, spot, option_mark, dividend.amount_per_share):
        return False
    if not (on_date < dividend.ex_date <= expiry):
        return False
    if dividend.amount_per_share <= 0:
        return False
    intrinsic = option_intrinsic_value(r, strike, spot)
    if intrinsic is None or intrinsic < EXERCISE_BY_EXCEPTION_THRESHOLD:
        return False
    extrinsic = max(0.0, option_mark - intrinsic)
    return extrinsic < dividend.amount_per_share


def settlement_effect(
    decision: SettlementDecision,
    *,
    right: str,
    strike: float,
    quantity: float,
    multiplier: float,
    avg_premium: float,
    collateral_posted: float,
    shares_available: float,
    cash_available: float,
) -> SettlementEffect | None:
    """The cash, the shares and the realised P&L one settled leg produces.

    See the module docstring for the invariant this holds to: the collateral
    is released in full, the settlement leg is paid or collected, and total
    value is continuous across the event.
    """
    r = right.strip().lower() if isinstance(right, str) else ""
    if r not in _RIGHTS or decision.action not in (EXPIRE_WORTHLESS, EXERCISE, ASSIGN):
        return None
    if not _finite(
        strike, quantity, multiplier, avg_premium, collateral_posted,
        shares_available, cash_available,
    ):
        return None
    if quantity == 0 or multiplier <= 0 or strike <= 0 or avg_premium < 0:
        return None

    sign = 1.0 if quantity > 0 else -1.0
    shares = abs(quantity) * multiplier
    premium_total = avg_premium * shares

    def cash_settled(downgrade: str | None) -> SettlementEffect:
        value_total = decision.settlement_value * shares
        return SettlementEffect(
            mode="cash",
            shares_delta=0.0,
            strike_price=0.0,
            basis_price=0.0,
            cash_delta=round(collateral_posted + sign * value_total, 2),
            realised_pnl=round(sign * (value_total - premium_total), 2),
            downgrade=downgrade,
        )

    if decision.action == EXPIRE_WORTHLESS:
        return cash_settled(None)

    # A call delivers stock to the long side, a put delivers it to the short
    # side — so the sign of the share movement flips with the right.
    shares_delta = sign * shares if r == "call" else -sign * shares
    if shares_delta > 0:
        # The collateral was posted for exactly this: a cash-secured put's is
        # `strike × shares`, so an assignment funds itself and can never be
        # refused for a low balance (CR171 §7). A long call has no collateral,
        # so a user who cannot fund delivery is sold out at parity instead —
        # which is what a broker's do-not-exercise handling does for them.
        if collateral_posted + cash_available + 1e-9 < strike * shares:
            return cash_settled(
                "not enough cash to take delivery — settled at parity instead"
            )
    elif shares_available + 1e-9 < shares:
        return cash_settled(
            "not enough shares to deliver — settled in cash at parity instead"
        )

    return SettlementEffect(
        mode="shares",
        shares_delta=shares_delta,
        strike_price=strike,
        # Premium folds into the basis when stock arrives, and is realised on
        # the leg when stock leaves — see the module docstring.
        basis_price=round(strike + sign * avg_premium, 4) if shares_delta > 0 else 0.0,
        cash_delta=round(collateral_posted - shares_delta * strike, 2),
        realised_pnl=0.0 if shares_delta > 0 else round(-sign * premium_total, 2),
        downgrade=None,
    )


def settlement_sort_key(quantity: float, right: str) -> tuple[int, int]:
    """Long legs settle before short legs, calls before puts.

    A vertical spread expiring in the money is one exercise and one
    assignment on the same underlying, and the assignment needs the shares
    the exercise delivers. Settling the long side first means the spread
    closes physically and nets to the width, instead of degrading to a cash
    settlement that happens to reach the same number by a different route.
    """
    return (0 if quantity > 0 else 1, 0 if str(right).lower() == "call" else 1)


def describe(
    *,
    occ_symbol: str,
    action: str,
    settlement: str,
    decision: SettlementDecision,
    effect: SettlementEffect,
    contracts: float,
) -> str:
    """The user-visible sentence for a settled leg — never a log line only."""
    if action == "expired":
        near = (
            f" It finished ${abs(decision.in_the_money_by):.2f} in the money, "
            f"under the ${EXERCISE_BY_EXCEPTION_THRESHOLD:.2f} auto-exercise "
            f"threshold, so it expired anyway."
            if decision.in_the_money_by > 0 else ""
        )
        return (
            f"{occ_symbol} expired worthless ({contracts:g} "
            f"contract{'s' if abs(contracts) != 1 else ''}).{near}"
        )
    verb = "exercised" if action == "exercised" else "assigned"
    if settlement == "shares":
        moved = (
            f"{abs(effect.shares_delta):g} shares "
            f"{'delivered to you' if effect.shares_delta > 0 else 'delivered from you'} "
            f"at ${effect.strike_price:.2f}"
        )
    else:
        moved = f"settled in cash at ${decision.settlement_value:.2f} per share"
    tail = f" {effect.downgrade}." if effect.downgrade else ""
    return (
        f"{occ_symbol} was {verb} at expiry: {moved}."
        f"{tail}"
    )
