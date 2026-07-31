# CR127 — Reconsider the "THE PM DECIDES — THIS IS NOT A VOTE" caption

**Status:** done · **Session:** AT:R65 · **Filed:** 2026-07-30 · **Decided + shipped:** 2026-07-31
**Source:** in-app bug report `696099e0` (Platinum Anchor, `8f1e288a`, `0.1.0+60`) —
*"PM DECIDES. THIS IS NOT A VOTE."* / steps: *"this line does not need to appear
here. we already said 11 agents."*

---

## Decision (Saiful, 2026-07-31)

> *"CR127 should also specify a card specific for PM. Which makes the statement redundant."*
>
> *"The reason block is supposed to be in a card and the card header should say
> PORTFOLIO MANAGER."*

Structural, not a copy edit. The Portfolio Manager gets **a card of its own, after the
eleven voices** — and once the twelfth agent is visibly present on the board as itself,
the caption has nothing left to say.

**Explicitly ruled out:** re-attributing the hero to the PM. A first pass at this CR
changed `THE ROOM APPROVED` → `THE PM APPROVED`; Saiful reverted it. The hero reports
the **run's outcome**; the PM speaks in its own card lower down. Those are two different
facts and they belong on two different cards.

---

## Problem

The caption under the Room's 11-hex consensus comb read `THE PM DECIDES — THIS IS NOT A
VOTE` (`roomCombPmDecides`). A tester reported it as unnecessary now that the comb only
ever shows 11 hexes.

Filed as a CR, not a Defect: the caption was deliberate, documented CR106/T-VOTE design.
Scoping it surfaced the thing the report and the filing both missed — **the PM was the
only agent on the board with no card.** Its reasoning (`data.reason`, which is
`verdict.reason`) rendered as unheaded body text at the bottom, after eleven clearly
labelled analyst hexes. So the twelfth agent was simultaneously absent from the comb and
unnamed where it actually spoke, and the caption was the only thing anywhere saying it
existed.

Two facts that constrained the fix:

- **BOARD shows 11, TRANSCRIPT shows 12.** `transcriptVoicesFromRoomState` emits every
  agent in `kAgentPhase` (12, PM included); `kCombVoices` filters the PM out (11). The
  caption was the only text reconciling those counts for a reader who toggles views.
- **A run can produce no reasoning at all.** `reason` is `''` on a run that never
  reached a verdict, so the card has to be able to not exist.

## What shipped

**1. The reasoning block is the PM's card, titled `PORTFOLIO MANAGER`.**
New `roomPmCardHeading`, rendered above the reason prose in the PM's family purple,
following `_ConsensusComb`/`_RosterGap`'s existing header idiom — purple rather than
their neutral `textLow`, because this header identifies an *agent* where theirs name a
*section*. The block also gains a `slate700` border so it reads as a peer card rather
than a recessed panel. Purple-as-type on `slate900` is the pattern
`_HexOutlinePainter` already documents (`hexPurple` at 4.22 is itself the project's
accent-as-type floor, measured on exactly this fill).

**2. The header is hidden when there is no reasoning** (`reason.trim().isEmpty`). A
titled but empty PM card would assert the PM said something on a run where it said
nothing — T-BACKFILL, absent is never inferred.

**3. The caption is deleted.** `roomCombPmDecides` removed from `room_board.dart` and
from all three ARBs, with the divider and spacer that existed only to set it off.

**4. The hero is untouched.** Verified byte-identical to its pre-CR127 state by diff
against `972c0a0a^`: `_HeroTile` and all four `roomHero*` heading strings, in all three
locales.

**5. The T-VOTE rationale moved, it did not disappear.** The doc comments in
`models/room_board.dart` and `models/room_board_mappers.dart` that cited the caption now
point at the PM card instead — including the 11-vs-12 reconciliation, so the next reader
does not rediscover it as a bug.

## Acceptance — met

1. The PM's reasoning is a card headed `PORTFOLIO MANAGER`. ✅
2. Headed on every outcome that produced reasoning — pinned across all six
   `VerdictOutcome` values, so a new outcome cannot quietly skip it. ✅
3. No header when there is no reasoning, including whitespace-only. ✅
4. The caption is gone from the comb. ✅ asserted `findsNothing`, so a re-add fails
5. The hero still reports the ROOM outcome, unchanged. ✅ pinned by its own test
6. Both halves mutation-proven: making the header unconditional reddens the empty-reason
   case; blanking the header text reddens the title guards. ✅
7. `flutter test` 402/402 green (398 baseline + 4 new); `flutter analyze
   --no-fatal-infos` clean at the 5 pre-existing infos. ✅

## Follow-ups owed

- **AR/MS review** — one new key, flagged in
  [`content/_authoring/cr127_room_hero_retranslate.md`](../../../content/_authoring/cr127_room_hero_retranslate.md).
  Composed from a rendering already attested in the same ARB, not invented, so nothing
  ships untranslated; but MS is internally inconsistent about `PM` vs
  `PENGURUS PORTFOLIO` for this agent and should settle on one.
- **Needs a device build to see.** Mobile-only; not on any tester's phone until the next
  TestFlight/Play build.
- **Worth telling the reporter.** Bug `696099e0` can be closed back to Platinum Anchor
  as fixed.
