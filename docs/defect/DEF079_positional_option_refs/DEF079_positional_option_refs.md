# DEF079 — Quiz explanations cite an option by POSITION ("the first option"), which breaks under answer-shuffle

**Status:** planned · **Session:** AT:R64 · **Filed:** 2026-07-22 · **Kind:** prompt-spotted · **Area:** content

> Sibling of **DEF065** (numeric "option 2" refs) and gated by the same mechanism. DEF065 fixed
> *numeric* index citations; this is the *positional-word* variant it didn't cover.

## The defect

**10 quiz explanations across 8 lessons refer to a distractor by its position** — "The first
option (anger) is real but unfalsifiable", "the second option does the reverse", "the last option
denies a correlation that is real". The reader (`lesson_reader_screen.dart`) renders no option
labels — no A/B/C/D, no numbers, no ordinal — so "the first option" already names something the
user cannot identify. Worse, it is a **latent correctness bug**: `scripts/shuffle_quiz_answers.py`
**`shuffle_lessons()`** reorders lesson quiz options (it targets `content/lessons/*.en.mdx`, not
just dailies), so once shuffle runs, "the first option" points at a *different* distractor and the
explanation teaches the wrong thing. Exactly the failure DEF065 closed for numeric refs, left open
for positional words because the guard (`_OPTION_INDEX_CITATION = \boptions?\s+\d`) only matches
digits.

## The 10 refs (8 lessons)

| Lesson | ref(s) |
|---|---|
| `047_revenge_trading` | "The first option (anger)…" |
| `211_journal_review_as_discipline` | "The first option is a performance dashboard…" |
| `324_inflation_mechanics_cpi_pce` | "the first option states the right number but the wrong m…" |
| `332_fiscal_policy_deficits_and_debt` | "the last option is simply false" |
| `335_expected_value_the_core_of_every_decision` | "the second option does the reverse" |
| `337_distributions_and_fat_tails` | "the second option overcorrects into nihilism" |
| `338_correlation_is_not_causation` | "the last option" ×2 (+ "the first two options") |
| `339_sample_size_and_statistical_significance` | "The first option skips the square root…", "the second option is the pre-square-root variance" |

## The fix

1. **Content:** reword each of the 10 to name the distractor by its **content**, not position —
   e.g. "The first option (anger)…" → "The 'anger' answer…"; read each against that question's
   `options` array (like DEF065's remediation). Only explanation text changes; never touch the
   question, options, or `answer`.
2. **Guard:** extend `_OPTION_INDEX_CITATION` (or add a companion) so
   `test_no_question_text_cites_an_option_by_index` also catches
   `\b(first|second|third|fourth|fifth|last)\s+options?\b` (case-insensitive). The test already
   scans explanation + question + option bodies across `lesson.quizzes`, so this closes all surfaces.
3. **Shuffle parity:** `shuffle_quiz_answers.py` should hard-refuse to run if a positional ref
   survives (it already refuses on numeric "option N") — so a reorder can never silently corrupt one.
4. **Bundled (Wave-1 wrap housekeeping):** bump `LESSON_COUNT_FLOOR` 270 → 334 in the same test file
   (corpus grew from the CR054 BOK + CR058 waves; tighten the deletion tripwire).

## Guard / acceptance

`cd backend && uv run pytest tests/unit/test_lesson_corpus_integrity.py -q` green — the extended guard
passes only when all 10 are content-named. AMI by name; simulation framing untouched; no `answer`
index changed.

Commit tag: `(AT:R64 DEF079)`.
