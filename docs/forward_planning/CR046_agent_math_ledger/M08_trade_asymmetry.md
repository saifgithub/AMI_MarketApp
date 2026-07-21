# M08 — Trade asymmetry (upside% vs downside%)

**Origin:** CR046 MODE-A audit finding F3 (AT:R62) · **Status:** done

## What
The upside and downside of a long setup, each as a percent of entry — the "asymmetry" the Research
Manager cites ("~X% upside vs Y% downside").

## The problem this fixed
The scripted Research Manager stated a fixed **"~28% upside vs 18% downside" for every ticker**
(hardcoded constants), and in the live path the figure was LLM-invented with no anchor (the RM speaks
before the Trader proposes levels). A precise-looking asymmetry presented as analysis but backed by
nothing — the DEF052 fabricated-quantification class.

## Formula
- `trade_asymmetry(entry, stop, target)`: `upside_pct = (target − entry)/entry × 100`,
  `downside_pct = (entry − stop)/entry × 100`, 1 dp each. Returns None unless `0 < stop < entry <
  target` (a coherent long setup).

## Source data
The reference trade levels (entry/stop/target).

## Consumed by
Research Manager (scripted `upside`/`downside`). In the scripted path these are now computed from the
reference levels, so the asymmetry the RM cites matches the levels the Trader template shows, instead
of a fixed fake.

## Computed in
`app/trading_math/trade.py::trade_asymmetry`. Wired into the Room scripted formatter (`room_runner.py`).

## Guard test
`tests/unit/test_trading_math.py` — `trade_asymmetry(100, 94, 113) → (13.0, 6.0)` and rejection of
unordered levels.

## Changelog
- 2026-07-21 (CR046, AT:R62): created from audit finding F3. Scripted RM asymmetry now computed from
  the reference levels; the live-path RM (which speaks before levels exist) no longer has a fabricated
  constant to fall back to — forcing a computed asymmetry there needs structured Trader output first
  (CR046 backlog).
