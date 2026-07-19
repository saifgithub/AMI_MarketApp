# CR044 — Group-scoped lesson codes

**Status:** done · **Session:** AT:R60 · **Filed:** 2026-07-19

## What

Give every lesson a permanent, speakable code scoped to its group — `TECH 12`, `N&M 22`,
`FUND 23` — and make that code the identifier the badge, the Concierge, and the agents use.

## Why

Saiful: *"The training material is hard to reference. We have 7 lesson groups. We should
number them based on the group so that when the user refers to 'Tech 34' or 'Fund 23', we
know which they are referring to. Additionally, in the concierge agent communication (and
others too) we can tell the customer to go read 'N&M (or News and Macro) 22'. Right now the
referencing is all over the place."*

He is right, and the reason is structural. Lessons carry a `track` (the 7 groups) *and* a
numeric id prefix, but the prefix follows the **module/level curriculum sequence**, not the
track. The two axes are documented as deliberately orthogonal in
[`curriculum_map.md`](../../initial_specs/04_education/curriculum_map.md) — level/module is
the user's journey, track is the cross-cutting facet driving agent-unlock routing and
Concierge search. The consequence is that the 270 lessons interleave into **39 contiguous
track runs**:

```
001-011 foundations        065-100 edge_process       201-203 sentiment_behaviour
012-012 edge_process       101-105 risk_portfolio     204-205 edge_process
013-018 risk_portfolio     106-106 edge_process       206-207 sentiment_behaviour
019-019 edge_process       107-109 risk_portfolio     208-211 edge_process
020-030 technical_analysis 110-111 edge_process       212-212 sentiment_behaviour
031-031 edge_process       112-141 technical_analysis 213-241 edge_process
032-044 fundamentals       142-142 edge_process       242-253 news_macro
045-046 sentiment          143-145 technical_analysis 254-279 edge_process
047-047 edge_process       146-147 edge_process       280-292 (one-per-track sampler)
049-058 edge_process       148-199 fundamentals
059-064 news_macro         200-200 edge_process
```

`edge_process` in particular acts as a single-lesson interrupt scattered throughout. So
"lesson 142" tells a user nothing about what group it belongs to, and there is no way to
say "the 12th technical lesson" at all.

Meanwhile the only user-visible identifier is `LessonMeta.numberLabel` — a bare zero-padded
`016` in a 36×36 cyan badge ([`lesson_tile.dart:55`](../../../mobile/lib/widgets/lessons/lesson_tile.dart),
[`lesson_reader_screen.dart:258`](../../../mobile/lib/screens/lessons/lesson_reader_screen.dart)).
No group prefix exists anywhere. Track short labels are hardcoded as Dart constants in two
duplicate maps and never reach the backend or the prompts.

## Scope

### The code format

`<PREFIX> <n>` — `n` contiguous `1..N` within the track, assigned once in current id order.

| track | prefix | count |
|---|---|---|
| `foundations` | `CORE` | 16 |
| `fundamentals_analysis` | `FUND` | 66 |
| `technical_analysis` | `TECH` | 45 |
| `news_macro` | `N&M` | 19 |
| `sentiment_behaviour` | `SENT` | 10 |
| `risk_portfolio` | `RISK` | 16 |
| `edge_process` | `EDGE` | 98 |

`foundations → CORE`, not `FND`. These codes exist to be spoken and typed into a chat box;
`FND` and `FUND` are one letter apart and would collide constantly in exactly the surface
this CR exists to serve.

### Frozen, not derived

The code lives in frontmatter and is **assigned once, never recomputed**. A derived per-track
rank is tempting — it needs no content change — but inserting one lesson mid-track would
renumber every lesson after it, invalidating any code already spoken, screenshotted, or
written into a chat log. That is precisely the drift CR018 called out when it chose to derive
`number` from the id prefix rather than from a sequence:

> the lesson's canonical reference number = the numeric prefix of its `id` … Stable per lesson
> (a recomputed sequence would drift as lessons are added/removed).

Freezing in frontmatter keeps CR018's stability property while gaining the readable small
numbers Saiful asked for. New lessons append (`TECH 46`); nothing renumbers.

`LessonMeta.number` **stays**. `number` is identity and sort key; `code` is display. They are
not redundant — the catalogue sorts on id/number, and swapping the sort to code order would
reorder the curriculum away from its designed journey sequence.

### Changes

| Area | Change |
|---|---|
| Content | `code: "TECH 12"` added to all 270 `content/lessons/*.en.mdx` frontmatter, by a committed one-off script (same shape as `scripts/shuffle_quiz_answers.py`: textual in-place edit so the diff shows only the added line) |
| Backend | `LessonMeta.code: str` in `backend/app/schemas/lessons.py`; parsed in `lessons_service.py` alongside `number`. **No silent default** — a missing code fails the corpus test rather than degrading to a blank badge (CLAUDE.md degrade-loudly) |
| Mobile | `code` on `models/lessons.dart`; badge swapped at `lesson_tile.dart:55` and `lesson_reader_screen.dart:258`. The tile badge's fixed `36×36` box becomes padding-sized — `TECH 12` does not fit in 36px |
| Mobile | The reader meta line (`lesson_reader_screen.dart:264`) renders `meta.track` **raw snake_case** — users currently see literally `risk_portfolio`. Dropped; the code carries the track now |
| Prompts | `concierge_prompts.py` — code becomes the primary reference in `_full_context_index` and `_format_lessons`; the instruction changes from *"name the lesson ID"* to naming the code |
| Prompts | `content/agents/concierge.md:44-53` — both worked examples are **fabricated** (*"Lesson 12: Order Types"*, *"Lesson 47: Reading P/E Ratios"*; 047 is `047_revenge_trading`). A system prompt that demonstrates a hallucination is teaching one. Replaced with real lessons and real codes |
| Spec | `content/_authoring/lesson_authoring_prompt.md` — document `code`, that the author takes the next free number in the track, and that codes are never reissued |

## Acceptance

- All 270 lessons carry a `code`; codes unique; prefix matches `track`; per-track numeric
  parts form contiguous `1..N`; counts match `16/66/45/19/10/16/98`.
- The corpus test fails loudly if any of the above breaks — verified red before green.
- Lesson tile and reader badge render the code, not `016`; no raw snake_case track anywhere
  in the reader.
- The Concierge cites lessons by code, and its own persona file contains no fabricated
  lesson references.

## Related

- **CR018** — established `LessonMeta.number` and the id-derived stability argument this CR
  follows.
- **DEF068** — shipped in the same commit; the locked-agent sheet lists gateway lessons by
  the code this CR introduces.
- **P3** in [`failure_patterns.md`](../../initial_specs/08_tech/failure_patterns.md) — the
  corpus-integrity test extended here is P3's enforcing check.
