# DEF077 — Bear Researcher's multiple-compression downside is computed with a wrong formula

**Source:** prompt (found in the CR046 MODE-A agent-math audit) · **Status:** resolved · **Session:** AT:R62 · **Date:** 2026-07-21

## Symptom

The Room's Bear Researcher states a quantified downside for a P/E de-rating, e.g.:

```
Quantification: a 10-point multiple compression = ~16% downside
```

For a stock at a P/E of 20, a 10-point compression (20x → 10x) is, holding earnings
constant, a **50%** price drop — not 16%. The figure is asserted to the user as a hard,
quantified risk number.

## Root cause

`room_runner.py::_profile_for_ticker` computed `bear_quant` inline:

```python
f"a 10-point multiple compression = ~{int(pe_val / (pe_val + 10) * 100 - 50)}% downside"
```

That expression has no relation to a multiple compression. Worked through:

| P/E | old formula | correct (`delta/pe`) | error |
|-----|-------------|----------------------|-------|
| 20  | ~16%        | 50%                  | ~3× understated |
| 34  | ~29%        | ~29%                 | ~coincidental |
| 55  | ~34%        | ~18%                 | ~2× overstated |

It understates at low multiples and overstates at high ones. Because the scripted
template is also the **degraded-mode output on any per-agent LLM timeout**
(`room_runner.py`'s `_scripted_for` fallback), this wrong number reaches real users, not
just the demo path. Exactly the failure-patterns **P5** class (an LLM/inline-computed
number an agent presents as fact) and a sibling of DEF066.

## Fix

The downside is now computed in the portable library and injected as a finished figure —
CR046 ledger entry **M07** (`trading_math/valuation.py::multiple_compression_downside`):

```python
downside = multiple_compression_downside(pe_val, 10)   # min(delta, pe) / pe * 100
```

Price ∝ multiple when earnings are held constant, so a `delta`-point compression of a P/E
of `pe` is a `delta/pe` drawdown (capped at 100%; None for a non-positive multiple).

Fix shipped structurally as part of the CR046 audit build-out in commit `270ec8a`
(tagged `(AT:R62 CR046)` — its message body references this defect by the number
`DEF075`, filed before the number-collision with the concurrent Android track's DEF075
was noticed; the correct id is **DEF077**).

## Guard

- `backend/tests/unit/test_trading_math.py` — `multiple_compression_downside` at P/E
  {8, 20, 55}, the 0x cap, and a **RED-proof** assertion that the correct value disagrees
  with the old `int(pe/(pe+10)*100−50)` expression.
- `backend/tests/unit/test_room_runner.py::test_bear_quant_downside_uses_library_not_the_old_broken_formula`
  — the Room's `bear_quant` string carries the library value, red against the old formula.

## Not in scope

- The Bear Researcher's other narrative fields (`bear_risk`, `bear_catalyst`) — prose, no
  fabricated number.
- The live-path Bear Researcher's own free-prose downside (LLM-authored) — constraining
  that needs structured agent output, logged in the CR046 backlog.

## Related

CR046 M07 (its ledger entry, origin = this defect). Found while auditing every
agent-facing number under the CR046 standing ledger.
