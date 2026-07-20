# M05 — Portfolio value + total drawdown denominator

**Origin:** pre-existing · **Status:** done (not yet migrated to the library)

## What
The portfolio's total value and its total drawdown — the *denominator* every risk figure the agents
and the safety floor reason about is measured against. The DEF066 bug (M02) was rooted in this
denominator living apart from the position-level contribution that should have been compared to it.

## Formula
- `total_value = cash + Σ(qty × price)`.
- `total_drawdown_pct = max(0, (starting_capital − value) / starting_capital × 100)`,
  `starting_capital = 10_000.0`.

## Source data
The user's simulated holdings + current marks (`sim_engine`).

## Consumed by
Safety floor (`check_mandate_compliance` — position-% and drawdown-breach gates), the Room API
(passes `portfolio_value` + `current_drawdown_pct` into a convene), and indirectly every agent that
reasons about the drawdown cap.

## Computed in
`app/schemas/trade.py::Portfolio.total_value` / `total_drawdown_pct`, surfaced by
`app/services/sim_engine.py::total_value` / `current_drawdown_pct`.

## Guard test
`tests/unit/test_sim_engine.py` (portfolio inits at 10k, fills update value; drawdown exercised
indirectly). **Gap:** no direct unit test of `total_drawdown_pct` in isolation.

## Changelog
- Seeded into the ledger 2026-07-20 (CR046, AT:R62) to record where this math lives.
- **Backlog:** add a direct unit test for `total_drawdown_pct`, and migrate the pure value/drawdown
  arithmetic into `trading_math/` alongside M02 so the denominator and the contribution live together.
