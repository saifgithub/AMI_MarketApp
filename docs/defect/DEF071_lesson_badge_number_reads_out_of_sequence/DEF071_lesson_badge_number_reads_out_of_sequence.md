# DEF071 — Lesson badge number reads as out-of-sequence

**Source:** `bug:b860aabf` · **Reporter:** Platinum Anchor (`8f1e288a`, floor_pass, iOS `0.1.0+39`) · **Filed:** 2026-07-20 (AT:R63) · **Status:** fixed (AT:R63) — tier section headers + a "Continue" label on floated tiles; badge left as the stable CR044 code.

## Symptom

Report (with screenshot): *"why is the lesson number not in sequence?"* The lessons list
shows badges reading **EDGE 49**, then **EDGE 2**, **EDGE 3**, **EDGE 4**, **EDGE 5** —
the first number is far larger than the ones below it, so the list looks mis-ordered.

## Root cause — working as designed, but illegible

Two independent, correct behaviours collide:

1. **The badge is a *stable canonical* number, not a position.** `lesson_tile.dart:59`
   renders `meta.codeLabel`; `LessonMeta.codeLabel` ([`mobile/lib/models/lessons.dart:130-136`](../../../mobile/lib/models/lessons.dart#L130))
   is the group-scoped code introduced in **CR044** — `"EDGE " + number`, where `number`
   is CR018's canonical reference (the numeric prefix of the lesson id, e.g. `49` from
   `049_…`). It is deliberately a permanent "say-it-out-loud" identifier, **frozen per
   lesson**, not a display counter.
2. **The list sorts by progress tier, not by number.** `track_lessons_screen.dart:101-112`
   (`_sortedWithStatus`) does a three-tier sort — *in-progress → never-started →
   completed*, catalogue order preserved within a tier. So a lesson the user has started
   (EDGE 49) is pinned above never-started lessons (EDGE 2–5).

Net: the prominent number is non-monotonic in the displayed order. Nothing is broken; the
UI just gives the user no cue *why* the order is what it is, so a stable id reads as a
sequence error.

## Fix plan (recommended direction — final call with the implementing agent)

Make the ordering legible **without** dropping the stable CR044 reference:

- **Add tier section headers** to the list — "In progress", "Not started", "Completed" —
  matching the existing three-tier sort in `_sortedWithStatus`. The jump from 49→2 then
  becomes self-explanatory (49 sits under "In progress").
- Optionally add a small **"Continue" / "In progress" chip** on the pinned in-progress
  tile (`lesson_tile.dart`) so it's obvious it was floated, not mis-sorted.

**Do NOT renumber the badge to list position** — that destroys the canonical CR044/CR018
reference the Concierge and the user both quote out loud, and re-breaks DEF068's badge work.

Scope: mobile-only, `track_lessons_screen.dart` + `lesson_tile.dart`. No backend, no API.

## Out of scope

The main lessons hex/feed screens (`lessons_screen.dart`) if they don't share the same
tile — verify whether the same confusion exists there and fold in if trivial.

## Resolution (AT:R63)

Ships mobile-only, as scoped:

- **Tier section headers** — the flat `ListView.separated` in `track_lessons_screen.dart`
  is now a `ListView.builder` over rows built by `buildTrackRows` (new
  `mobile/lib/screens/lessons/track_row_builder.dart`). Headers ("IN PROGRESS · n",
  "NOT STARTED · n", "COMPLETED · n") appear **only when more than one tier is non-empty**,
  so a first visit (everything never-started) is unchanged. The 49→2 jump now sits under a
  header that names it.
- **"CONTINUE" label** on in-progress tiles in `lesson_tile.dart`, mirroring the existing
  "COMPLETED" label, so a floated tile reads as resumable rather than mis-sorted. That
  hard-coded "COMPLETED" string was localised in the same edit (`lessonsTierCompleted`).
- **Badge untouched** — still `LessonMeta.codeLabel` (the CR044 code). No renumbering, so the
  say-it-out-loud reference and DEF068's gateway work are intact.
- Ordering was previously a `List.sort` on a tier key; `buildTrackRows` partitions instead, so
  "catalogue order within a tier" is now actually guaranteed (Dart's `List.sort` is not stable).

**Verified out-of-scope:** `LessonTile` is used only by `track_lessons_screen.dart`;
`lessons_screen.dart` is a hex cluster that renders no lesson list, so the confusion cannot
appear there.

**Guard:** `mobile/test/widgets/track_row_builder_test.dart` — 5 cases including the exact
reporter scenario (EDGE 49 in-progress floating above EDGE 2–5), the single-tier no-header
case, and catalogue-order-within-tier. New i18n keys in all three ARBs.

**Verification:** `flutter test` 29 passed · `flutter analyze --no-fatal-infos` clean (4
pre-existing infos).
