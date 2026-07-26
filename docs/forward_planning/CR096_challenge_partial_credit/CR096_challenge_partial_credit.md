# CR096 — Daily challenge partial-credit scoring

**Status:** proposed · **Session:** AT:R65 · **Date:** 2026-07-27
**Source:** CR065 drift item #6, verdict "build it" (Saiful, 2026-07-27).

## What

`daily_and_streaks.md` specifies 3-outcome challenge scoring: **Got it right** (+5
reputation), **Got it close** / partial credit (+2), **Got it wrong but tried** (+1).
The shipped code (`reputation_service.py`'s `POINTS` dict) has only 2 outcomes:
`challenge_attempted: 2`, `challenge_correct: 3` — no "close" tier, **and the point
values themselves don't match the spec** (correct is +3 in code vs +5 in spec;
attempted/wrong-but-tried is +2 in code vs +1 in spec).

## Why

Saiful's verdict: build it. Note this is a **numeric reconciliation, not just a
missing middle tier** — shipping the spec's 3-outcome table means changing all three
values, not adding one.

## Scope

**In:**
- Add a third scoring path (`challenge_close` or similar) at +2 reputation.
- Reconcile `challenge_correct` from +3 → +5, and `challenge_attempted` (the
  wrong-but-tried case) from +2 → +1, to match the spec's table exactly.
- The "close" classification itself needs a definition — today's challenge types
  (multiple-choice-shaped: "Predict the Call", "Spot the violation", etc.) may not
  have an obvious partial-credit answer space for every type. Confirm at build time
  whether "close" applies uniformly or only to specific challenge types.

**Out:** any change to non-challenge `POINTS` entries (lesson_passed, room_verdict,
etc.) — those are unaffected by this drift item.

## Acceptance

- Challenge scoring produces exactly the spec's three point values: right=+5,
  close=+2, wrong-but-tried=+1.
- Existing challenge-scoring tests updated to the new values (this is a deliberate,
  documented point-value change, not a regression).
