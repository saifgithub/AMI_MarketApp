# CR042 — randomise which position holds the correct quiz answer

**Filed:** 2026-07-18 (AT:R60) · **Status:** done

## Why

Found auditing the corpus for [[DEF064]]. The correct answer was not distributed across
the four slots — it clustered hard in the second:

| Corpus | index 0 | index 1 | index 2 | index 3 |
|---|---|---|---|---|
| Lessons (559 valid MCQs) | 17 (3.0%) | **397 (71.0%)** | 141 (25.2%) | 4 (0.7%) |
| Daily challenges (183) | 2 (1.1%) | **177 (96.7%)** | 4 (2.2%) | 0 |

"Always pick the second option" scored **71%** on lessons and **96.7%** on daily challenges
without reading anything.

The 100% pass threshold (`QUIZ_PASS_THRESHOLD = 1.0`) means this handed out no free passes —
a blind guesser still fails a 2-question lesson most of the time. But the authoring prompt
explicitly designs the quiz as a standalone assessment surface for users who skip the body,
and a positional tell that strong hollows that out.

## Scope

Positional randomisation only, across both corpora. One-off corrective rewrite.

## Explicitly NOT in scope — the length tell

The correct option is also the **longest** in 94.6% of lessons (529/559) and 91.3% of daily
challenges. This is the stronger tell of the two, and randomising position does nothing to
it.

Saiful's call: *"do not worry about the 'length' tell. this is adult education, not exam
prep."* Recorded in
[`rejected_features_register.md`](../../initial_specs/11_decisions/rejected_features_register.md).

## Dependency

**Gated on [[DEF065]].** 277 explanations referenced options by index ("option 2"), so
reordering options would have silently corrupted half the corpus's explanations. De-indexing
landed first. `scripts/shuffle_quiz_answers.py` refuses to run if it finds a surviving
citation — the ordering constraint is enforced, not just documented.

## Implementation

`scripts/shuffle_quiz_answers.py`, committed (seed `20260718`). Not a build step — a
one-off, kept so the approach can be reviewed and re-applied if the corpus ever re-clusters.

**Honest note on reproducibility:** the shipped content is the result of running the script
**twice**. The first implementation re-drew each permutation until the answer *moved* off
its current slot, which sounded tidier but inverted the tell rather than removing it —
with 71% of answers starting at index 1, must-move drove index 1 down to 10.3% on lessons
and **1.1%** on daily challenges, effectively turning those into 3-option questions. The
algorithm was changed to pick the target slot uniformly (so ~1/n questions legitimately
keep their position) and re-run over the already-shuffled corpus. Re-running is safe
precisely because the invariant below is positional-only. A single run of the committed
script against the pre-shuffle corpus would produce a different — equally valid — layout,
not the current one.

- Reorders the option **string literals in place**, leaving every byte between them
  (indentation, newlines, commas) untouched, so the diff shows moved strings and nothing
  else. Three MDX formatting variants exist (2-space multi-line, 4-space multi-line,
  single-line) and all survive unchanged.
- Daily-challenge JSON is rewritten textually for the same reason: a `json.dumps` re-dump
  expands the inline `"tags": [...]` arrays and buries the real change under ~280 lines of
  formatting noise per file.
- Every permutation is re-drawn until the answer actually moves off its current slot.

**Load-bearing invariant:** the correct answer's *text* must be byte-identical before and
after — only its position may change. Asserted per question inside the script, and
re-verified across the whole corpus after the run.

**Excluded:** `281_what_is_a_market__q1`, the corpus's only 2-option question
("True" / "False"). Reordering to False-then-True reads wrong, and changing the answer would
mean inverting the statement.

## No distribution test

`test_lesson_corpus_integrity.py` deliberately does **not** assert a uniform distribution.
A uniformity assertion would go red on legitimate future content edits and teach the next
session to weaken it. CR042 is a one-off correction, not an invariant. The authoring prompt
carries the guidance for new content instead.

## Related

- [[DEF064]], [[DEF065]] — the two defects found in the same audit.
