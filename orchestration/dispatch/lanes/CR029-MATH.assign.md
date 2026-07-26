<!-- dispatch assign lane — Architect-owned. CR052. -->
# CR029-MATH — assign (FIFO cost-basis lot matching + realised P&L, pure calc)

KIND: code
INSTANCE: coder.math
ACCEPTANCE: docs/forward_planning/CR029_cost_basis_lots/CR029_cost_basis_lots.md
DEPENDS-ON: none — pure library function; no DB, no schema, no cross-instance touch.
GATE: independent    <!-- realised-P&L numbers a user sees; hand-recompute the FIFO worked example in the audit like CR046/CR058-MATH. -->
HOT-FILES: backend/app/trading_math/ (coder.math-owned; no contention)

**What (this sub-lane only):** the **pure FIFO engine** for CR029 — given an ordered sequence of
buys and a sell quantity, match sells against open lots first-in-first-out and return realised P&L
per matched lot + the remaining open lots. No persistence, no API, no schema in this lane — a
deterministic library function in `trading_math` with a hand-worked example, exactly like the CR046
ledger math. This is the not-blocked core; it needs no `coder.api` slot, so it runs in parallel with
DEF099.

**Explicitly OUT of this sub-lane (later, behind a coder.api slot):**
- **CR029-BE** (`coder.api`, schema owner): the `lots` table + migration + wiring the FIFO engine into
  `sim.submit`'s sell path to persist realised P&L. DEPENDS-ON CR029-MATH.
- **CR029-MOBILE** (`coder.mobile`): the realised-P&L / lots UI. DEPENDS-ON CR029-BE; re-verify
  `fromJson` against live backend JSON before audit (hand-mirrored contract).

## Why split this way

`coder.api` is the bottleneck (DEF099 + CR030 + others queue on it). The FIFO math has zero backend
or schema dependency, so `coder.math` (idle) can land + audit it now; the schema/persistence half
picks it up as a library the moment a `coder.api` slot frees. Prioritizes not-blocked work per Saiful.

## Tests

- Hand-worked multi-lot example: buy 10@$100, buy 10@$120, sell 15 → realised P&L = (10×(sell−100)) +
  (5×(sell−120)); 5 open lots @ $120 remain. Assert exact figures.
- Sell qty > open qty → error/partial per the ACCEPTANCE doc's rule (decide deliberately).
- Zero/edge: sell with no open lots, fractional shares if the doc allows them.

**Self-test:** `cd backend && .venv/bin/python -m pytest tests/unit/ -q -k "trading_math or fifo or lot or cost_basis"` then full `tests/unit/ -q`.

## Delivery

Push source to `lane/CR029-MATH.coder.math`, never `main`. Hand-off (both to the SHARED branch):
`orchestration/dispatch/lanes/CR029-MATH.coder.math.md` (`STATUS: READY_FOR_AUDIT (round 1)`) +
`orchestration/audit/cr/CR029-MATH.architect.md` (`SUBMITTED: round 1`). Commit tag `(AT:coder.math CR029)`.

DISPATCH: ACCEPTED (round 1)    <!-- coder.math built in isolated worktree; Architect verified inline on main (78 green: FIFO subset + all trading_math; worked example hand-checked = 350.0) + integrated. Pure unwired calc → verify-inline per the reversibility rule; the INDEPENDENT gate is reserved for CR029-BE (sim wiring, where realised P&L reaches users). -->

ASSIGNED: coder.math round 1
