# DEF074 — Room fact-sheet drops the computed technical support; sends the 52-week low as the "recent range" floor

**Source:** prompt (found verifying CR046 M01 live on Alpha) · **Status:** resolved · **Session:** AT:R62 · **Date:** 2026-07-21

## Symptom

The Room fact-sheet injected into all 12 agents shows, for AAPL:

```
Recent range: $201.5–$334.99, breakout level: $334.99
```

`$201.5` is the **52-week low**. Meanwhile `compute_technicals` computes a real
**50-day support of $273.75** that never reaches the Room agents. The *same* Market
Analyst sees `$273.75` as "support" in a 1-on-1 but `$201.5` as the range floor in the
Room — two surfaces, two support numbers for the same ticker, same moment.

## Root cause

`room_prompts.py::_format_profile` rendered the range line from `profile['low']` /
`profile['high']` (the 52-week range set by the fundamentals overlay) plus
`profile['breakout']` (the 50-day max from technicals) — a floor and a ceiling from
**different lookback windows** — and never rendered `profile['support']` at all.

`room_runner.py:341` sets `profile['support'] = technicals.support` (the real 50-day
min), so the value is **computed and then silently dropped** in the Room path. The
1-on-1 path (`build_technicals_context_block`) *does* render it, hence the divergence.

Not a miscalculation — every value is real and correctly computed. A routing/display
bug: a computed number is discarded, the label "Recent range" describes a 52-week span,
and two agent surfaces disagree. Exactly the class CR046's ledger + failure-patterns
**P5** exist to catch (a computed number that must reach the agent; shown == shown
across surfaces).

## Fix

`_format_profile` now renders the coherent 50-day technical pair and keeps the 52-week
range as explicit context:

```
Recent range: $273.75–$334.99 (52-week: $201.5–$334.99)
```

`$273.75` = `profile['support']` (the technical 50-day support, matching the technical
breakout window and the value the 1-on-1 already shows). The computed technical support
is no longer dropped, the label is honest, and Room and 1-on-1 now agree on the support
number.

## Guard

`backend/tests/unit/test_room_prompts.py::test_recent_range_floor_is_technical_support_not_52w_low`
— a profile with distinct support/low asserts the recent-range floor is `support`
(273.75), the 52-week low survives only as labelled context, and the 52-week low is
never the floor. Verified **red** against the pre-fix line (which rendered
`profile['low']`).

## Not in scope

- Whether the fundamentals fallback support (`base × 0.9`, overwritten by technicals at
  line 341) should differ — the cascade is unchanged; this only fixes which of the
  already-computed fields the Room *renders*.
- Byte-identical formatting between the Room line and the 1-on-1 block — they carry the
  same support *number* now; the surrounding copy still differs by surface, which is
  fine.

## Related

CR046 M01 (technical indicators) — its ledger changelog links here. Found while
verifying M01 was sent correctly to the live agents (the answer: RSI/trend/volume/
breakout were; the 50-day support was computed and thrown away).
