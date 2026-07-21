# M05 — Portfolio value + total drawdown denominator

**Origin:** pre-existing · **Status:** done (migrated to `trading_math/portfolio.py`)

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
`app/trading_math/portfolio.py` (`total_value`, `drawdown_pct`, `position_pct`, `shares_for_size`) —
`app/schemas/trade.py::Portfolio.total_value` / `total_drawdown_pct` delegate to it, surfaced by
`app/services/sim_engine.py`. The safety floor's position-weight% and the Room's size→shares
conversion also read `portfolio.py` now, so the drawdown denominator and the single-name weight have
one definition.

## Guard test
`tests/unit/test_trading_math.py` — direct unit tests for `total_value`, `drawdown_pct` (incl. the
0-denominator case), `position_pct`, `shares_for_size` (incl. the floor-at-1-share and 0-price cases).
`tests/unit/test_sim_engine.py` still exercises the delegated methods end-to-end.

## Changelog
- Seeded into the ledger 2026-07-20 (CR046, AT:R62) to record where this math lives.
- 2026-07-21 (CR046, AT:R62): pure value/drawdown/weight/size→shares arithmetic **migrated** into
  `trading_math/portfolio.py` (byte-identical); the schema methods, safety-floor weight%, and Room
  quantity conversion delegate. Closes the earlier gap (a direct `drawdown_pct` unit test now exists)
  — the denominator (M05) and the position-level contribution (M02) now live in one library.
