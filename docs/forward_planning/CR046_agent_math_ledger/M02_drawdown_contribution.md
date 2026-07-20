# M02 — Position drawdown contribution

**Origin:** DEF066 (AT:R59) · **Status:** done

## What
How much a single proposed position adds to *portfolio* drawdown if it's stopped out — handed to the
Risk Debators and PM as a finished figure so no agent re-derives (or mis-derives) it.

## Formula
- `stop_distance_pct = (entry − stop) / entry × 100`
- `contribution_pts  = size_pct × stop_distance_pct / 100`
- (caller then compares to the mandate's portfolio cap: `pct_of_cap = contribution_pts / cap × 100`)

The bug this fixes: comparing `stop_distance_pct` **directly** against the portfolio cap, ignoring
`size_pct` — a ~20× overstatement that refused 16 of 64 benchmark Buys. Example: at 5% size a 19%
stop costs 0.95 pt of the portfolio (≈3.2% of a 30% cap), not 19%.

## Source data
The Trader's pre-computed proposal (`size_pct`, `entry`, `stop`) + the mandate's `max_drawdown_pct`.

## Consumed by
Aggressive / Conservative / Neutral Debators and the Portfolio Manager (RISK + VERDICT phases).

## Computed in
`app/trading_math/risk.py::drawdown_contribution` (pure, returns a `DrawdownContribution` NamedTuple
or None for a nonsensical proposal). Rendered into the prompt by
`app/services/room_prompts.py::_drawdown_snapshot_line`.

## Guard test
`tests/unit/test_trading_math.py` (5% × 10% = 0.5 pt, not 10), `tests/unit/test_room_prompts.py`
(the derived line reaches RISK/VERDICT prompts; no bare `max_drawdown_pct` line).

## Changelog
- 2026-07-19 (DEF066): created inside `_drawdown_snapshot_line`.
- 2026-07-20 (CR046, AT:R62): pure formula extracted to `trading_math/risk.py`; the prompt-builder
  now calls it. Byte-identical output.
