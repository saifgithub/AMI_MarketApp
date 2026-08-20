# CR190 — The app tour covers the Journal, framed as a learning tool

**Status:** built (AT:R73) · **Source:** Saiful's Floor v0.2 reaction notes — bug:d8783e4b (0.1.0+90), bug:a345042c (0.1.0+96) · **Re-scoped:** 2026-08-20 (AT:R73)

## What / why

The two source reports are Saiful's own reaction notes on the Floor v0.2 redesign,
not a feature request. The first ("feels a bit too different") is resolved by the
v0.2 iteration the second praises. The actionable residue is one sentence:

> "Tour necessary for the journal i feel, journal important for the learners and
> to avoid seeming like signal generators." — bug:a345042c

The gap at HEAD: the Journal has its own 3-step coach-mark tour
(`journal_tour.dart`), but since CR133 moved the Journal inside `YOU`, that tour
only fires once the user taps into the JOURNAL segment. The YOU tour (CR180) —
the app tour's actual entry point for the tab — taught SETTINGS and INSIGHTS and
skipped JOURNAL. A learner who never taps the segment is never told the Journal
exists, or why it matters.

## Scope (what shipped)

- `you_tour.dart`: a 4th step, `you_journal`, between `you_settings` and
  `you_insights` (segment-bar order), targeting the JOURNAL segment cell.
  Existing `TargetFocus`/`TourCard` pattern — no new tour framework.
- `you_screen.dart`: `_journalSegmentKey` on the JOURNAL `AmiSegment`, passed to
  `buildYouTargets`.
- Copy (`tourYouJournalTitle` / `tourYouJournalBody`, en + ar/ms seeds,
  `retranslate:[ar,ms]`): learning frame — decisions land with reasoning
  attached, review the why against the outcome — and the anti-signal line is
  explicit: "Your agents brief you; they never hand you signals."
- Untouched on purpose: the Journal's own 3-step tour (mechanics, still fires on
  first segment entry), the `tour_journal_seen` key, and the CR180 nav-change
  notice.

## Acceptance

- `mobile/test/features/tour/you_tour_journal_test.dart` — step present, in bar
  order, keyed to the JOURNAL segment; copy is the CR190 keys and keeps the
  reasoning/signal frame; NEXT/DONE flow intact (only the last step ends the
  tour). Mutation-proven (wrong keyTarget, neighbour body key, mid-tour DONE —
  all red; restored green).
- `you_screen_test.dart` — every segment cell carries a key, so no tour step
  aims at nothing.
- Full `flutter test` exit 0.
