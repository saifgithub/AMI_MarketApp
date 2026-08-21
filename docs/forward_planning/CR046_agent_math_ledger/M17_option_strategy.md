# M17 — Option strategy metrics

**Origin:** CR172 §5/§6/§10 (options simulation, slice 1) · **Status:** done (library + guards; the slice-2 `option_strategist` candidate generator is built on this)

## What
Per structure: max loss, max gain, break-evens, net debit/credit, collateral requirement, net
greeks — every number on the §10 yes/no card. The engine is generic, not per-structure: an expiry
payoff over same-expiry legs is piecewise linear, so max/min live at the kinks (strikes + S=0) or
at infinity via the terminal call slope. One analysis covers every same-expiry structure exactly,
instead of fifteen formulas that can each drift.

## Why opened
CR172 §10's candidate generator emits fully-costed structures; §8's twin concentration caps and the
`max_loss`-based open-risk treatment need per-structure figures the stop-distance formula cannot
produce. **Unbounded is a flag (`unbounded_loss`), never a number and never a None-that-means-
missing** — §8 forbids an unbounded max loss entering any percentage sum.

## Formula
`strategy_metrics(legs, shares_held=0)` over signed `StrategyLeg`s (positive long, negative short;
premium per share; multiplier a real column). Collateral follows §6's table:
- long-only structures post nothing (the premium already left);
- covered calls lock SHARES, not cash (`shares_locked`; max loss is stock-basis dependent, so it
  is an explicit None + `covered_by_shares`, never a guess);
- cash-secured puts post `strike × multiplier × contracts` — premium NOT netted, per the table,
  so assignment is fully pre-funded;
- defined-risk credit structures post worst-case settlement liability minus net credit
  (reproduces `width − credit` for a vertical, the wider wing for an iron condor);
- **an uncovered short call has NO collateral figure** — None + `has_uncovered_short_call`, per
  the D3 ruling (2026-08-20): naked calls are FORBIDDEN and the refusal explains why; the math
  marks, the safety floor enforces.
- Share cover is allocated to the HIGHEST-strike short calls (least liable), so the paired
  remainder can only over-secure, never under.
- Multi-expiry structures (calendars/diagonals) → None: an expiry payoff does not exist for them
  (§10 defers them to a term-structure model).

`combine_greeks` sums quantity × multiplier × per-share Greeks; an empty input is None, not a free
claim of zero exposure.

## Source data
Legs from the (slice-2) strategist; per-leg greeks from M15 via the enrichment layer.

## Consumed by
Slice 2: `services/option_strategist.py` (candidate generation), the §8 floor checks, the §10
verdict card. Slice 1 ships the math + guards.

## Computed in
`app/trading_math/option_strategy.py::strategy_metrics` / `payoff_at_expiry` / `net_cost` /
`combine_greeks`.

## Guard test
`tests/unit/test_cr172_trading_math_options.py` — §6 pinned row by row (bull/credit verticals,
CSP full-strike, covered call shares-not-cash, naked-call flag with no number, iron condor wider
wing, partial share cover still uncovered, highest-strike cover allocation), break-evens for
spread/straddle, adjusted multiplier honoured, mixed-expiry refusal, invalid-leg refusals.
Mutation-proven (break-even interpolation break → red).

## Changelog
- 2026-08-20 (CR172 slice 1, AT:R73): created.
