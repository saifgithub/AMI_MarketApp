# CR127 — Reconsider the "THE PM DECIDES — THIS IS NOT A VOTE" caption

**Status:** proposed · **Session:** AT:architect · **Date:** 2026-07-30
**Source:** in-app bug report `696099e0` (Platinum Anchor, `8f1e288a`, `0.1.0+60`) —
*"PM DECIDES. THIS IS NOT A VOTE."* / steps: *"this line does not need to appear
here. we already said 11 agents."*

## Problem

The caption under the Room's 11-hex consensus comb reads `THE PM DECIDES — THIS IS
NOT A VOTE` (`roomCombPmDecides`, `room_board.dart:840`). A tester reports it as an
unnecessary line now that the comb itself only ever shows 11 hexes.

This is **not a defect** — the caption is deliberate. `room_board_mappers.dart:79-80`
and `room_board.dart:57-58` both document it as CR106's fix for a real prior problem
(T-VOTE): a bare 11-hex grid, with no PM among them, reads as a vote tally the PM's
decision might then appear to contradict. `room_board.dart:836-839` states the
reasoning plainly: *"There is no defensible weighting: the PM is not 1/11 of a
vote... (T-VOTE)."*

## Question for Saiful

Does showing exactly 11 hexes (as opposed to a nominal 12) already communicate
clearly enough on its own that the caption is now redundant — or does the caption
carry information the count alone can't: a first-time user has no baseline of "there
are normally 12 agents" to notice "11, not 12," so the caption may be the only thing
telling them the PM isn't one of the votes shown.

## Scope

Not yet decided. Options once Saiful weighs in:
- Keep as-is (design already considered, one tester's read doesn't override it).
- Remove entirely.
- Soften/shorten (keep the disambiguation, drop the emphasis).
- Show once (first Room a user ever convenes) then suppress.

## Acceptance

Not applicable until a direction is chosen.
