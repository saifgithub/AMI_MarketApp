# CR127 — Reconsider the "THE PM DECIDES — THIS IS NOT A VOTE" caption

**Status:** done · **Session:** AT:R65 · **Filed:** 2026-07-30 · **Decided + shipped:** 2026-07-31
**Source:** in-app bug report `696099e0` (Platinum Anchor, `8f1e288a`, `0.1.0+60`) —
*"PM DECIDES. THIS IS NOT A VOTE."* / steps: *"this line does not need to appear
here. we already said 11 agents."*

---

## Decision (Saiful, 2026-07-31)

> *"CR127 should also specify a card specific for PM. Which makes the statement redundant."*

Not a copy edit and not a "keep it" — a **structural** fix. Give the Portfolio Manager
its own visibly-labelled card, and the caption stops being load-bearing because the
layout says what the caption was saying.

---

## Problem — and what the investigation actually found

The caption under the Room's 11-hex consensus comb read `THE PM DECIDES — THIS IS NOT A
VOTE` (`roomCombPmDecides`). A tester reported it as unnecessary now that the comb only
ever shows 11 hexes.

Filed as a CR, not a Defect: the caption was deliberate, documented CR106/T-VOTE design.
But scoping it turned up the thing neither the report nor the original filing named —
**the caption existed to correct a contradiction the board created one card higher up.**

The hero tile headed an approval `THE ROOM APPROVED` and a pass `THE ROOM PASSED`. Under
it sat eleven Room members arranged into FOR / NEUTRAL / AGAINST bands. That reads as a
vote by the room, tallied, resolving to a room decision — and it is wrong three times
over: the PM decides alone, the PM is not among the eleven, and the safety floor can
override even the PM. The caption was the board arguing with itself in 9pt type.

So the tester was right that the line is redundant, and right for a reason they could
not have known: it is redundant *once the hero stops mis-attributing the call*. Removing
it alone would have deleted the only correction while leaving the error in place.

Two further facts constrained the fix:

- **BOARD shows 11, TRANSCRIPT shows 12.** `transcriptVoicesFromRoomState` emits every
  agent in `kAgentPhase` (12, PM included); `kCombVoices` filters the PM out (11). The
  caption was the only text anywhere reconciling those two counts for a reader who
  toggles between the views.
- **`BLOCKED BY YOUR MANDATE` is not the PM's call.** A `reject` outcome is produced
  deterministically by the safety floor, never parsed from the model — so "name the
  decider" cannot be applied uniformly to all six outcomes without inventing an
  attribution. Same for `noResult`, where the run never reached the PM at all.

## What shipped

**1. The hero card names its decider.**
`roomHeroApprove` `THE ROOM APPROVED` → `THE PM APPROVED`; `roomHeroPass`
`THE ROOM PASSED` → `THE PM PASSED`. The other four headings were already correct and
are untouched — `BLOCKED BY YOUR MANDATE` (the user's own rules, and the override line
below it already reads *"YOUR RULES CHANGED THE PM'S CALL"*), `NO VERDICT ISSUED`,
`THE ROOM DID NOT FINISH` (the run failed — correctly the room, not the PM), and the raw
token for an unrecognised action.

**2. The hero card is visibly the PM's card.**
New `roomHeroPmCard` (`PORTFOLIO MANAGER`) as an identity label at the top of the tile,
in the PM's family purple — distinct from the tile's `accent`, which is the *outcome's*
status colour. Purple-as-type on this canvas is the pattern `_HexOutlinePainter` already
documents (`hexPurple` at 4.22 is itself the project's accent-as-type floor).

Shown for `approve` / `pass` / `reject` / `noVerdict` / `unknown`; **omitted for
`noResult`** alone, because that run never reached the PM and a PM-branded card would be
claiming a decision that was never made. Kept for `reject`: the mandate did the blocking
and the heading says so, but the card is still the verdict slot the PM's call went into.

**3. The caption is deleted.** `roomCombPmDecides` removed from `room_board.dart` and
from all three ARBs, along with the divider and spacer that existed only to set it off.

**4. The T-VOTE rationale moved, it did not disappear.** The doc comments in
`models/room_board.dart` and `models/room_board_mappers.dart` that cited the caption now
record why the hero carries the disclosure instead — including the 11-vs-12
reconciliation, so the next reader does not rediscover it as a bug.

## Acceptance — met

1. No surface attributes a PM decision to "the room". ✅ (`THE PM APPROVED` / `THE PM PASSED`)
2. A mandate block is never attributed to the PM. ✅ pinned by its own test
3. The PM identity label appears on every card carrying a PM decision and on none that
   doesn't. ✅ pinned across all six `VerdictOutcome` values
4. The caption is gone from the comb. ✅ asserted `findsNothing`, so a re-add fails
5. Both halves mutation-proven: making the label unconditional reddens the `noResult`
   case; reverting the heading to `THE ROOM APPROVED` reddens the attribution case. ✅
6. `flutter test` 401/401 green (398 baseline + 3 new); `flutter analyze --no-fatal-infos`
   clean at the 5 pre-existing infos. ✅

## Follow-ups owed

- **AR/MS review** — 3 strings, flagged in
  [`content/_authoring/cr127_room_hero_retranslate.md`](../../../content/_authoring/cr127_room_hero_retranslate.md).
  Values were composed from renderings already attested in the same ARB, not invented, so
  nothing ships untranslated; but two are verb phrases whose subject changed (Arabic verb
  agreement moves with it) and MS is internally inconsistent about `PM` vs
  `PENGURUS PORTFOLIO` for this agent.
- **Needs a device build to see.** Mobile-only change; not on any tester's phone until the
  next TestFlight/Play build.
- **Worth telling the reporter.** Platinum Anchor's report is what surfaced this, and the
  outcome is better than what they asked for — bug `696099e0` can be closed as fixed.
