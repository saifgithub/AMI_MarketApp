# DEF065 — 277 quiz explanations cite an option by an index the user cannot see

**Filed:** 2026-07-18 (AT:R60) · **Source:** prompt · **Category:** content
**Status:** resolved

## What was wrong

Found while auditing the corpus for [[DEF064]]. 277 of 559 questions (49.6%), across 138
of 270 lessons, had explanations that name an answer option by number:

> "The tempting wrong answer is **option 0** — the headline number 'looks' cheaper."
> "**Option 2** ignores the mechanism. **Option 3** invents a relationship that doesn't exist."

**The reader renders no option labels.** `lesson_reader_screen.dart:637-658` draws an icon
and the option text — no A/B/C/D, no numbers. So every one of those references pointed at
something the user has no way to identify.

The explanation is the teaching surface: it is what a user sees after answering, and the
authoring prompt explicitly designs it as the thing that teaches a "skip-to-quiz" reader
who got it wrong. That surface was degraded on half the corpus.

## Worse — two contradictory conventions

The content was not even internally consistent:

- `039_the_pe_ratio` uses **"option 0"** for the *first* option (0-indexed)
- `115_harami_and_shooting_star` uses **"Option 4"** for the *fourth* option (1-indexed)

Both appear across the corpus, and `164_switching_costs_the_invisible_lock_in` mixes both
conventions **inside a single explanation** ("option 0", "Option 2" and "Option 4" in one
sentence). One file, `020_candlesticks_anatomy_of_a_bar` q1, cited an option that matches
under neither convention — the prose described the third option while saying "option 0".

Because of this, the fix could not be mechanical. Each of the 277 was resolved by reading
the prose against that question's `options` array to determine which option was actually
being described.

## Fix

Every numeric reference rewritten to name the option by its **content**:

```
BAD:  "The tempting wrong answer is option 0 — it looks cheaper."
GOOD: "The tempting wrong answer is the one citing the lower headline multiple."
```

Only explanation text changed — no `question`, no `options` array, no `answer={N}`.

## Consequence for CR042

This defect is what made the answer-position shuffle unsafe. While any explanation said
"option 2", reordering options would silently invalidate it. De-indexing had to land first;
`scripts/shuffle_quiz_answers.py` hard-refuses to run if it finds a surviving citation.

## Guard

`backend/tests/unit/test_lesson_corpus_integrity.py::test_no_explanation_cites_an_option_by_index`
— no parsed explanation may match `\boptions?\s+\d` (case-insensitive). Verified red
against the real defect before the fix.

`content/_authoring/lesson_authoring_prompt.md` now carries the rule with a good/bad
example.

## Related

- [[DEF064]] — the unanswerable-quiz defect this audit was chasing.
- [[CR042]] — the shuffle this unblocked.
