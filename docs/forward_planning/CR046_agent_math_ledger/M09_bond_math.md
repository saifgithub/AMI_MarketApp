# M09 — Bond price, yield to maturity, duration

**Origin:** CR054 §4.5 (BOK Wave-1 numbers) · **Status:** done (library + guards; Wave-1 lessons are the consumer)

## What
The full price↔yield↔duration arithmetic of a level-coupon bond, so every bond worked example in the
BOK's M13 ("Fixed income & rates") lessons is computed, never authored by hand. Standard
discrete-compounding textbook math.

## Why opened
CR054 Wave 1 authors ~7 fixed-income lessons (Level 9) full of numbers — "a 5% coupon at a 6% yield
prices at $925.61", "duration 2.86 years" — exactly the DEF064-class risk CR046 exists to remove: a
hand-authored figure that can be wrong and that nothing checks. Opened ahead of Wave 1 (this is lane
W0d's whole purpose) so the authoring pipeline has the functions before the first lesson is written.

## Formula
- `bond_price(face, coupon_rate_pct, ytm_pct, years, payments_per_year=2)` — PV of the coupon
  annuity + discounted face at the per-period yield, 2 dp. Rates are annual percents; the schedule
  must land on a whole number of periods (else None — refusing beats silently mis-discounting).
- `bond_ytm(price, face, coupon_rate_pct, years, payments_per_year=2)` — the yield implied by a
  price, solved by bisection (price is strictly decreasing in yield, so the root is unique), 3 dp so
  basis points survive. None when the price is unattainable inside the −90%…+1000% band.
- `macaulay_duration(...)` — PV-weighted average time to the cash flows, years, 2 dp. A zero-coupon
  bond's duration is exactly its maturity (the teaching anchor, guard-tested).
- `modified_duration(...)` — Macaulay / (1 + y/m), 2 dp — the "a 1-pt rate rise moves the price
  about −D%" figure.

## Source data
Lesson-authored example parameters (face, coupon, maturity, yield/price) — pedagogical inputs, not
market data.

## Consumed by
**No production caller yet — by design.** Wave-1 lesson authoring (M13 lessons + their quizzes)
routes every bond figure through these; the agents themselves gain a consumer if/when a fixed-income
surface ships. Staged here per CR054 Wave-0 plan ("open the bond/option/portfolio math entries with
guard tests").

## Computed in
`app/trading_math/bond.py::bond_price` / `bond_ytm` / `macaulay_duration` / `modified_duration`.

## Guard test
`tests/unit/test_trading_math_bok.py` — the classic $925.61 discount price, par/premium/discount
ordering, zero-coupon pure discounting (553.68), YTM round-trip (925.61 → 6.000, par → 5.000),
Macaulay 2.86 / modified 2.72 textbook values, zero-coupon duration == maturity, and the
None-on-nonsense guards (no face, negative coupon, fractional period count, yield ≤ −100%,
unattainable YTM prices).

## Changelog
- 2026-07-21 (CR054-W0d, AT:coder.math): created — first of the four BOK-math entries opened ahead
  of Wave-1 lesson authoring.
