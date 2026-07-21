# M07 — Multiple-compression downside

**Origin:** CR046 MODE-A audit finding D-a → **DEF077** (AT:R62) · **Status:** done

## What
The price downside if a stock's P/E multiple compresses by a given number of points — the number the
Bear Researcher states as its quantified downside risk.

## The bug this fixed (DEF077)
The Room computed this inline as `int(pe/(pe+10)*100 − 50)` — which is simply **wrong**. A 10-point
compression from a P/E of 20 (20x → 10x) halves the price: a **50%** drop. The old formula printed
**16%** (~3× understated). At P/E 55 it printed ~34% against a true ~18% (~2× overstated). It swung
in both directions and was asserted to the user as a hard risk figure — exactly the DEF066 failure
class (a wrong risk number an agent presents as fact). This ships to real users, not just the demo,
because the scripted path is also the degraded-mode output on any per-agent LLM timeout.

## Formula
Price is proportional to the multiple when earnings are held constant, so a `delta`-point compression
from `pe` costs `delta/pe` of the price:
- `multiple_compression_downside(pe, delta_pts) = min(delta_pts, pe) / pe × 100`, 1 dp.
- Capped at the full multiple (a compression can't take the price below zero). Returns None for a
  non-positive P/E (loss-making) or a non-positive compression.

## Source data
The ticker's trailing P/E (`profile['pe']`, live yfinance or synthetic baseline).

## Consumed by
Bear Researcher (`bear_quant`).

## Computed in
`app/trading_math/valuation.py::multiple_compression_downside`. Wired at
`room_runner.py::_profile_for_ticker`.

## Guard test
`tests/unit/test_trading_math.py` — the formula at P/E {8, 20, 55, …} incl. the 20→50% anchor, the
0x cap, and a **RED-proof** assertion that the correct value disagrees with the old
`int(pe/(pe+10)*100−50)` expression. `tests/unit/test_room_runner.py::
test_bear_quant_downside_uses_library_not_the_old_broken_formula` guards the wiring.

## Changelog
- 2026-07-21 (CR046/DEF077, AT:R62): created to replace the wrong inline formula with the correct
  `delta/pe` downside, computed in the library and injected as a finished figure.
