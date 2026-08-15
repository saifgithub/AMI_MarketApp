# CR189 — one position, one average, one bracket

**Filed:** 2026-08-15 (AT:R70) · **Status:** proposed · **Follows:** CR188 slice 3, DEF316, DEF318 · **Depends on:** CR029 (FIFO lots)

Saiful, deciding the tile design for CR188 slice 3: *"When the user has bought shares at different
times, the holding tile should show the weighted average buying prices. And the stop loss and take
profit should also be recalculated based on weighted average."*

---

## Why

A bracket is stored per **trade row**. A tile is per **ticker**. Buy the same name twice and the
position has two stops, and there is no honest way to draw that on one tile.

It cannot be solved in the widget. If the tile shows a blended stop at $97 while the sweep still
fires each row's own $95 and $99, **the screen is lying about a risk control** — the user reads one
number and a different one liquidates them. So the sweep evaluates the position's bracket, or the
tile does not show one.

It also matches how the position is already described everywhere else: `sim_holdings.avg_cost` has
been a weighted average since the first commit, and `_apply_buy_row` recomputes it on every add. The
entry price was already position-level. The bracket is what never caught up.

---

## The rule

Over **live lots only**, weighted by shares still open:

```
stop(position)   = Σ(lot.stop   × lot.quantity_open) / Σ(lot.quantity_open)   ∀ lots with a stop
target(position) = Σ(lot.target × lot.quantity_open) / Σ(lot.quantity_open)   ∀ lots with a target
```

`quantity_open` is `cost_basis_lots.Lot.quantity_open` — CR029-MATH, audited, and the same input
DEF318 gates the sweep on. Dead lots weigh nothing, so a sold-out lot cannot drag the position's
stop, which is the DEF318 defect restated as arithmetic.

**Lots with no bracket are excluded from the average, not counted as zero.** That is the whole
special-case handling, and it falls out rather than being bolted on:

| lot 1 | lot 2 | position stop | reads as |
|---|---|---|---|
| 10 @ $100, stop $95 | 10 @ $110, stop $99 | **$97.00** | both stops blended |
| 10 @ $100, stop $95 | 10 @ $110, no stop | **$95.00** | existing protection carried across all 20 |
| 10 @ $100, no stop | 10 @ $110, no stop | none | unprotected, as asked |

The middle row is the case with no obviously-right answer, and excluding-rather-than-zeroing gives
the one we want: **a user with protection does not silently lose it by adding shares.** Counting the
unbracketed lot as zero would drag the stop to $47.50, which protects nothing; dropping the stop
entirely would remove a control the user set.

Shorts are out of scope — CR171 refuses extending an open short, so a short is single-lot by
construction and has nothing to average.

---

## The disclosure, which is the load-bearing half

**Adding to a position moves a stop the user set by hand.** Buy 10 @ $100 with a stop at $95, then
buy 10 more with a stop at $99, and the original $95 becomes $97 — the risk floor rose $2 because of
a later, separate decision. This project's rule is that a control does not change quietly
(CR040; "prompt instructions are not controls").

So the buy ticket states it **before** submit, in the slot CR188 slice 1 built for the short notice:

> *This raises your stop on all 20 NVDA from $95.00 to $97.00.*

Same slot, same mutual exclusion — one sentence above the button, never two. And per slice 1's own
finding, the sentence is not the control: it is stated before the press, not pushed after the fill.

**A blend that lands on the wrong side of the market is refused, not disclosed.** If the new average
would put the stop at or above the current mark (or the target at or below it), the position would
liquidate on the next sweep — DEF312's shape arriving by arithmetic rather than by typing. That is a
refusal on the client and the server, reusing `bracket_is_wrong_side`.

---

## Scope

1. **`sim_engine.evaluate_outcomes`** — compare the mark to the position's blended bracket, not to
   each row's. A hit closes every live lot, each realising at its **own** entry price (FIFO stays
   exact; only the trigger is shared).
2. **The blend is derived, never stored.** No column, no migration. Two derivations of one number is
   the DEF098 shape, and the lots already carry everything needed.
3. **Buy ticket** — compute the resulting blend, disclose the move, refuse a wrong-side result.
4. **Position tile (CR188 slice 3)** — weighted average cost and the one bracket, with distance;
   expanded shows the per-lot cards CR029 already built.
5. **i18n** — new keys for the disclosure, `retranslate:[ar,ms]`.

## Not in scope

- Editing a position's bracket after the fact. Today the only way to change a stop is a resting
  order; that stays true here, and is a separate CR if it should not be.
- Shorts (single-lot by CR171).
- Anything about the safety floor, placement, or the sweep's schedule.

---

## Acceptance

1. Two lots with different stops produce one position stop, weighted by open quantity.
2. A lot with no stop does not lower the position's stop; the existing one covers the whole position.
3. A fully-sold lot contributes nothing to the average (DEF318, as arithmetic).
4. The sweep fires on the blended level, and closing realises each lot at its own entry price.
5. A buy that moves an existing stop says so before submit, naming both numbers.
6. A buy whose resulting blend would sit on the wrong side of the mark is refused, client and server.
7. A single-lot position behaves exactly as it does today — the blend of one is itself.

Acceptance 7 is the non-vacuity guard: every other test here passes on an implementation that
quietly disables brackets for everyone with one lot, which is nearly all users.
