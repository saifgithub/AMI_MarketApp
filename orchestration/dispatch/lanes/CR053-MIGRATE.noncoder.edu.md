<!-- dispatch hand-off — noncoder.edu. CR053-MIGRATE. -->
# CR053-MIGRATE — noncoder.edu hand-off

STATUS: READY_FOR_REVIEW (round 1)

COMMIT: 320bf45 (pushed to origin/main)

## Manifest

- **Class 1 (global-id) refs resolved:** 270
- **Class 2 (within-module ordinal) refs resolved:** 57
- **Flagged (unresolved, left untouched):** 0
- **Daily-challenge prose refs migrated:** 33 (across 4 files: 2026_07, 2026_08, 2026_11, 2026_12)
- **Lesson-body files touched:** 134 of 334
- **Script:** `scripts/migrate_lesson_refs.py` (textual, in-place, idempotent —
  re-run confirmed as a no-op after applying)
- **Report:** `content/_authoring/cr053_migration_report.md` — every edit as
  `file | class | before -> after`, FLAGGED section (empty)
- **Guard test:** `backend/tests/unit/test_lesson_corpus_integrity.py::test_no_untagged_global_lesson_ref_remains_in_any_body`
- **Self-test:** `cd backend && uv run pytest tests/unit/test_lesson_corpus_integrity.py tests/unit/test_daily_challenge_service.py -q` — **35 passed, exit 0**

## One deliberate deviation from the assign doc's literal phrasing

The assign doc's examples write the tag as `<Lesson id="039"/>` (bare 3-digit).
The actual `id` attribute value used is the **full frontmatter id**
(`<Lesson id="039_the_pe_ratio"/>`), not the bare number. Reason: CR053-BE's
already-committed resolve guard (`test_every_lesson_token_resolves_to_a_real_lesson_id`)
checks `token_id` against `{l.meta.id for l in lessons}`, which is the full
frontmatter id string — a bare "039" would fail that guard (and would also
fail to resolve against the real production catalogue via mobile's
`_findLessonMetaById`, which matches on the same full id). CR053-MOBILE's
own widget-test fixture used a bare "039" as `LessonMeta.id`, which is a
test-fixture shorthand, not a statement about the real id format. Full-id
tagging is what makes the resolve guard pass AND what actually resolves
end-to-end against real data — confirmed by the green guard-test run above.
Flagging this explicitly since it deviates from the assign doc's literal
attribute examples.

## Notable bug caught + fixed during self-review (not just the self-test)

First dry-run pass missed 4 refs, all sharing one root cause: the bare
`NNN (title)` matcher (for refs with no "lesson" keyword, e.g. "023 (support
and resistance)") would also match on an unrelated leading number followed
by an unrelated parenthetical that happened to contain a REAL ref inside it
— e.g. "2023 (covered in lesson 061 as a range case)" matched "2023 (...)"
as a candidate bare ref first, failed its own title-overlap check (correctly,
"2023" isn't a lesson), but then swallowed the whole span — including the
genuine "lesson 061" living inside those parens — advancing past it
unexamined. Fixed by making a failed bare-match advance only past the
number, not the whole parenthetical, so the next scan pass still sees what's
inside. Caught via the new guard test on the first pytest run (4 offenders
listed by name), not just by trusting the report's "0 flagged" count — the
guard test is exactly what it's for. Re-ran the full dry-run -> apply ->
idempotency-check cycle after the fix; 327 (not 323) edits, 0 flagged, guard
green.

## Report review notes for the architect

- All 17 bare-paren (no "lesson" keyword) matches spot-checked against their
  real target lesson's title — no false positives from prices/dates (the
  title-word-overlap filter rejected ~184 candidate price/date parentheticals
  during development; see script docstring/`classify_bare`).
- Class 2 spot-checked: e.g. `328_capstone_reading_the_macro_machine`
  (code `MACRO 6`) "lesson 1/3/4/5" -> resolved to lessons coded `MACRO 1/3/4/5`
  (323/325/326/327), confirmed against their frontmatter `code` fields directly.
- Ranges (`lessons 007–011`, `lessons 039–044`, `lessons 2-3` within-module)
  tag both endpoints, preserve the original dash character.
- Lists (`lessons 034, 156, and 157`, `lessons 2, 3, and 4`) tag each item,
  preserve original separators verbatim (", " vs " and ").
- Daily-challenge `related_lesson`: every ref-bearing row already had one set
  (verified, none missing) — no structured-field changes were needed, only
  the visible-text rewrite to the CR044 code. One CR035 `test_string`
  synthetic row (`dc_2026_07_14_test_string_telegram`) skipped per spec (it
  has no lesson refs in it anyway, but the skip logic is in place and tested).
- All 7 touched daily-challenge JSON files confirmed to still parse
  (`json.loads` check baked into the script's apply path — refuses to leave
  an unparseable file).

## Constraint check

- AMI by name: untouched (no user-facing app-copy strings edited, only
  cross-lesson refs + one JSON prose field).
- No verified quiz numbers/answers/P2 figures touched — matcher only fires on
  `\blessons?\b`-anchored or title-overlap-confirmed spans; quiz `answer=`/
  `options=` attributes were never candidates.
- CR044 codes untouched (frozen) — only referenced via lookup.
- Idempotent: confirmed via a second `--dry-run` immediately after apply (0
  edits, 0 files).
