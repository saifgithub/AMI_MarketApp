"""CR170 Rules 1 and 2 — when a resting order triggers, and what it books at.

Pure: no DB, no network, no clock — matching `market_hours.py` and `twr.py`.
`mobile/lib/features/sim/order_pricing.dart` mirrors **Rule 1 only**, for the
ticket's live hint; that mirroring is the DEF098 shape and the split of
authority is one-directional — the client predicts, this module decides. Rule 2
is deliberately absent from the client, because a price the server books is not
a thing the client should be guessing at.

## Rule 1 — trigger

    rests_below = (side == BUY  and order_type == LIMIT)
               or (side == SELL and order_type in (STOP, STOP_LIMIT))

    triggered   = (mark <= named) if rests_below else (mark >= named)

`named` is `limit_price` for LIMIT and `trigger_price` for STOP / STOP_LIMIT.
**Inclusive at the boundary**, matching `evaluate_outcomes`' existing
`price <= stop` / `price >= target`: the two now run in the same sweep, and a
user comparing them must not find them disagreeing at the exact touch.

Note the diagonal — a buy limit and a sell stop are the *same comparison*, as
are a buy stop and a sell limit. Two predicates cover four orders, which is why
`rests_below` returns a direction rather than switching on four cases.

## Rule 2 — fill price

    fill_price = max(named, mark)   for BUY
    fill_price = min(named, mark)   for SELL

The worse-for-the-user of the price named and the price observed. One
expression, all four orders, no hindsight edge in either direction:

| Order      | Named   | Observed | Books at | What it teaches                    |
|------------|---------|----------|----------|------------------------------------|
| Buy limit  | $190.00 | $187.40  | $190.00  | you pay what you asked             |
| Sell limit | $210.00 | $214.00  | $210.00  | you get what you asked             |
| Sell stop  |  $90.00 |  $85.00  |  $85.00  | slippage — a stop is no guarantee  |
| Buy stop   | $110.00 | $115.00  | $115.00  | slippage — breakouts cost more     |

**Why not the observed mark**, which is what a real venue gives on a gap:
market data is 15 minutes delayed and the sweep polls every ~5 minutes, so up
to 20 minutes of tape sits between the true touch and our observation. In that
window the price has already traded through — meaning **on trigger the mark is
systematically on the better-for-the-user side of the named price.** Filling at
the mark hands the user that entire gap and is directly farmable: rest a buy
limit a fraction under the market and harvest gappy opens. Filling at the worse
of the two removes the edge rather than bounding it.

## The one thing that looks like an inconsistency and is not

Rule 2 governs a **sweep** fill — an order that rested and later triggered.
An order that is *already marketable when submitted* fills at the mark, on the
market path, exactly like a market order (CR170 §3, acceptance 1). Both are
right, and the difference is the elapsed time: the sweep's mark is a stale
sample of a price that moved while nobody was looking, and a submit's mark is
the quote the user was looking at. There is no gap to hand back at submit time,
so there is nothing to defend against.

Concretely: a buy limit at $190 typed while the market is $187.40 fills at
$187.40 — it is a market order with a price cap, which is what a marketable
limit is. The same order *resting* from a market of $195 and triggering at
$187.40 books at $190. `sim_engine.submit()` therefore assigns `fill_price =
mark` unconditionally and lets a *branch* decide rest-vs-fill; only
`fill_resting_order()` calls `fill_price_for`.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import NamedTuple

from app.schemas.trade import OrderType, Side

_EPS = 1e-9

RESTING_ORDER_TYPES: frozenset[OrderType] = frozenset(
    {OrderType.LIMIT, OrderType.STOP, OrderType.STOP_LIMIT}
)


def _as_side(side: Side | str) -> Side:
    return side if isinstance(side, Side) else Side(str(side).lower())


def _as_order_type(order_type: OrderType | str) -> OrderType:
    return (
        order_type if isinstance(order_type, OrderType)
        else OrderType(str(order_type).lower())
    )


def can_rest(order_type: OrderType | str) -> bool:
    """A market order never rests. Everything else can."""
    return _as_order_type(order_type) in RESTING_ORDER_TYPES


def rests_below(*, side: Side | str, order_type: OrderType | str) -> bool:
    """Which side of the market this order waits on.

    |          | rests **below**         | rests **above**           |
    |----------|-------------------------|---------------------------|
    | **BUY**  | buy limit — buy the dip | buy stop — breakout entry |
    | **SELL** | sell stop — stop-loss   | sell limit — take profit  |
    """
    if _as_side(side) == Side.BUY:
        return _as_order_type(order_type) == OrderType.LIMIT
    return _as_order_type(order_type) in (OrderType.STOP, OrderType.STOP_LIMIT)


def named_price_for(
    order_type: OrderType | str,
    *,
    trigger_price: float | None = None,
    limit_price: float | None = None,
) -> float | None:
    """The price this order is named by. `None` for MARKET, which has none."""
    ot = _as_order_type(order_type)
    if ot == OrderType.LIMIT:
        return limit_price
    if ot in (OrderType.STOP, OrderType.STOP_LIMIT):
        return trigger_price
    return None


def is_triggered(
    *,
    side: Side | str,
    order_type: OrderType | str,
    named: float,
    mark: float,
) -> bool:
    """Rule 1. Inclusive at the boundary — see the module docstring."""
    if rests_below(side=side, order_type=order_type):
        return mark <= named
    return mark >= named


def fill_price_for(*, side: Side | str, named: float, mark: float) -> float:
    """Rule 2 — the worse-for-the-user of (named, observed).

    Takes no `order_type`, deliberately: the rule does not have one. A version
    that switched on the type would be P10's shape again, which is the defect
    this whole module exists to close.
    """
    if _as_side(side) == Side.BUY:
        return max(named, mark)
    return min(named, mark)


def stop_limit_becomes_limit(order_type: OrderType | str) -> bool:
    """A stop-limit is two-phase: the trigger converts it into a resting limit,
    and Rule 1 then re-applies against `limit_price`.

    Sell stop-limit, trigger $90, limit $88:
      - price eases to $89 → triggers → sell limit at $88 → 89 >= 88 → **fills at $88**
      - price **gaps** to $85 → triggers → sell limit at $88 → 85 >= 88 is false
        → **rests, and may never fill**

    That second line is the classic stop-limit failure and the reason the type
    is in the curriculum. The simulator reproduces it rather than smoothing it.
    """
    return _as_order_type(order_type) == OrderType.STOP_LIMIT


# ── CR171 §5 — the bracket inverts on a short ──────────────────────────────


def bracket_hit(
    *, is_short: bool, mark: float,
    stop: float | None, target: float | None,
) -> str | None:
    """Which side of an exit bracket the mark has crossed: "lost", "won", None.

    | | Long | Short |
    |---|---|---|
    | Stop fires when | `mark <= stop` | `mark >= stop` |
    | Target fires when | `mark >= target` | `mark <= target` |

    `evaluate_outcomes` used to gate on `if side_enum == Side.BUY`, which was
    **correct** — a SELL row there is an exit, so its levels are meaningless —
    and removing that gate rather than replacing it would have started firing
    brackets on exits. It becomes a branch on *what the row is*: a long
    position, or a short one. The comparison lives here, next to the direction
    logic Rule 1 already needed, so there is one place where "which way does
    this position want the price to go" is written down.

    Stop is checked first in both directions, matching the long-side order that
    shipped: when a single sweep observes a mark past both levels the user is
    given the loss, never the win. A simulator that resolves an ambiguous bar
    in the user's favour teaches that gaps are free.
    """
    if is_short:
        if stop is not None and mark >= stop:
            return "lost"
        if target is not None and mark <= target:
            return "won"
        return None
    if stop is not None and mark <= stop:
        return "lost"
    if target is not None and mark >= target:
        return "won"
    return None


def bracket_is_wrong_side(
    *, is_short: bool, entry: float, stop: float | None, target: float | None,
) -> str | None:
    """The submit-time refusal, as a reason string or None. Both directions.

    The exact inverse of `bracket_hit` above, and it lives beside it on purpose:
    the rule for *where a level belongs* and the rule for *when it fires* are one
    fact, and the way this defect happened was by writing them apart.

    | | Long | Short |
    |---|---|---|
    | Stop belongs | below entry | above entry |
    | Target belongs | above entry | below entry |

    **DEF312 — the long half of this did not exist.** §5 shipped as
    `short_bracket_is_wrong_side`, called from `_open_short_fill` alone, so a
    LONG bought with a stop above its entry was accepted by every layer. The
    consequence is not cosmetic: `bracket_hit` fires on `mark <= stop`, so such a
    position is liquidated on the **next** market-hours sweep, at market, and
    recorded as a stop-out — which then trips the post-stop-out cooldown that
    hard-blocks the user's next BUY. One typo, an instant liquidation and a
    trading ban, with nothing anywhere saying why.

    The client's `short_rules.dart` had the same shape and the same hole: its
    `stopIsWrongSide`/`targetIsWrongSide` take `isShort` and handle both cases
    correctly, and `_localRefusal` returns early on every buy so the long branch
    is unreachable. That is **P21** — a check present in the source and inert at
    runtime — on both sides of the wire at once.
    """
    if is_short:
        if stop is not None and stop <= entry:
            return (
                f"a short's stop must be ABOVE the entry price — ${stop:.2f} is "
                f"at or below ${entry:.2f}, so it could only fire after the "
                f"position had already lost everything it made"
            )
        if target is not None and target >= entry:
            return (
                f"a short's target must be BELOW the entry price — ${target:.2f} "
                f"is at or above ${entry:.2f}, which is where the position loses "
                f"money"
            )
        return None
    if stop is not None and stop >= entry:
        return (
            f"a stop must be BELOW the entry price — ${stop:.2f} is at or above "
            f"${entry:.2f}, so it would fire immediately and close the position "
            f"you just opened"
        )
    if target is not None and target <= entry:
        return (
            f"a target must be ABOVE the entry price — ${target:.2f} is at or "
            f"below ${entry:.2f}, so it would fire immediately and book a win "
            f"the position never made"
        )
    return None


class LotBracket(NamedTuple):
    """One live buy lot's contribution to its position's bracket (CR189)."""

    quantity_open: float
    stop: float | None
    target: float | None


def blended_bracket(
    lots: Iterable[LotBracket],
) -> tuple[float | None, float | None]:
    """CR189 — a position's single stop/target, weighted by shares still open.

    A bracket is stored per trade row; a position is per ticker. Buy the same
    name twice and there are two stops, and no honest way to draw one tile —
    if the screen shows a blended $97 while the sweep still fires $95 and $99,
    it is lying about a risk control. So the position gets one level and the
    sweep evaluates it.

    Weighted by `quantity_open` (`cost_basis_lots.Lot`, CR029-MATH), which makes
    a sold-out lot weigh nothing — DEF318 restated as arithmetic rather than
    enforced as a second gate.

    **A lot with no stop is EXCLUDED from the stop average, not counted as
    zero**, and that single choice is the whole special-case handling:

        10 @ $100 stop $95  +  10 @ $110 stop $99   ->  $97.00
        10 @ $100 stop $95  +  10 @ $110 no stop    ->  $95.00
        10 @ $100 no stop   +  10 @ $110 no stop    ->  None

    The middle case is the one with no obviously-right answer. Counting the
    unbracketed lot as zero drags the stop to $47.50, which protects nothing;
    dropping the stop removes a control the user set by hand. Excluding it
    carries the existing protection across the whole position, which is the only
    one of the three a user would recognise as their own intent.

    Stop and target are computed independently — a book where one lot set only a
    stop and the other only a target yields both, each over its own contributors.
    """
    stop_num = stop_den = 0.0
    target_num = target_den = 0.0
    for lot in lots:
        qty = float(lot.quantity_open)
        if qty <= _EPS:
            continue
        if lot.stop is not None:
            stop_num += float(lot.stop) * qty
            stop_den += qty
        if lot.target is not None:
            target_num += float(lot.target) * qty
            target_den += qty
    stop = round(stop_num / stop_den, 2) if stop_den > _EPS else None
    target = round(target_num / target_den, 2) if target_den > _EPS else None
    return stop, target
