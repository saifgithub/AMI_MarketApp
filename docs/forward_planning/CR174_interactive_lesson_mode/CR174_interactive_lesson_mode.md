# CR174 — Interactive lesson mode (book mode + interactive mode on one MDX source)

**Filed:** 2026-08-12 · **Status:** proposed · **Track:** Learn surface (sibling of CR173, which
took the Floor + Room from the same research programme).

**Decision provenance — Saiful, 2026-08-12.** Tester feedback on the education surface: *"(1) too
much words, not enough pictures on the education part (2) too passive, not enough 'activity'."*
His framing for the fix, verbatim: **"I am thinking two modes, the book mode (what we have now) and
the interactive mode."** On scope: *"ultimately, all, but this is a planning session."* On
sequencing: **research + plan now, build after the queued content fixes** (150 lesson P1 fixes,
daily-challenge regeneration). Then: *"create sample artifacts so i can have them reviewed"* — done,
see Prototype below.

**Research:** [`docs/Research/UI/Learn/README.md`](../../Research/UI/Learn/README.md).
**Prototype:** `docs/Research/UI/Learn/prototype/lesson_modes.html` (built from
`template_lesson_modes.html` via `build.py`).

---

## Why

Measured across `content/lessons/*.en.mdx` (2026-08-12):

| Metric | Measured |
|---|---|
| EN lessons | 348 |
| Prose words | **218,976** total · median **620**/lesson · p90 779 · max 1,091 |
| **Lessons containing an image** | **0 (0%)** |
| With a table / bullet list / numbered list | 4% / 20% / 6% |
| Paragraphs | 2,609 · median 65w · **24% ≥100 words** · max 251w |
| **First interaction** | **50% through the body** (median) |
| Interaction inventory | 748 `<Quiz>` · 348 `<ChatWith>` · 697 `<Term>` · 15 `<Animation>` |

Quiz correctness is revealed only after a batch `.submit()` (`lesson_reader_screen.dart`,
`revealResult`). So the shipped experience is a ~620-word scroll, no pictures, nothing to do until
halfway, no feedback until the end. The feedback is accurate.

**Reach justifies the work.** Of 172 alpha users, lessons are the **second-most-used core action —
30 users (17%)**, behind Room convenes (32). But daily challenges — the one interactive surface
already shipped — sit at **4 users (2%)**.

> **Therefore: do not build a new interactive destination.** A separate activity surface is what
> daily challenges already are, and it is not being found. Interactivity goes **inside the lesson
> flow** users already reach.

### The diagnosis is decorative visuals, not missing capability

Coverage counts are **not** the argument — A21 deliberately decoupled content adoption from
animation production, so low adoption in an alpha is expected, not a defect.

`014_position_sizing_basics` (RISK 2) is one of the 15 animated lessons. Its `## Example` is 240
words of arithmetic, containing this sentence (line 33):

> *"if you had set the stop at $470 instead, per-share risk drops to $10 and shares jump to 20 — the
> tighter the stop, the bigger the position you can carry at the same 1% risk."*

That is **a slider described in prose**. The animation it has renders
`BalanceScalePainter(leftValue: 2, rightValue: 2)` — a generic scale that never shows the lesson's
figures ($20,000 / $480 / $459 / 9 shares). The picture decorates the text instead of carrying it.

**The fix pattern, applied per lesson:** bind the visual to the lesson's real numbers → let the
learner move the parameter the prose asks them to imagine → delete the prose the visual now does
better. One change addresses all three complaints.

## Design — one lesson, two delivery modes

Same MDX source, same block pipeline, same server contract. Mode is a render-time choice, following
the pattern already sanctioned for the Room: **default one way, the other one toggle away,
persisted** (CR106 `RoomViewMode`; CR173's concept E adds a third value the same way).

- **Book mode** — today's reader, unchanged. Default for `learning_style == story`; the
  accessibility path, the "I want to read" path, and the AR/MS fallback.
- **Interactive mode** — the same lesson as a **beat deck**: single-objective cards, each earning its
  place with a visual *or* an interaction, instant per-card feedback.

### The existing section skeleton already maps onto beats

This is why the CR does not require re-authoring 219k words to start. Measured section frequencies:
`## Try it` 334, `## Takeaway` 334, `## The trap` 326, `## How this plays out in real markets` 233,
`## Example` 91, `## The steelman` 41.

| Section today | mean words | Becomes | Learner does |
|---|---|---|---|
| intro | — | the rule | reads 2 lines |
| `## Example` / `## How this plays out…` | 212 / **273** | the live model | **drags a parameter** |
| `## The trap` | 126 | commit-then-reveal | predicts, then sees |
| `## The steelman` | 133 | counter-argument | taps to reveal |
| `## Quiz` | — | retrieval, moved earlier | answers, instant reveal |
| `## Try it` | 68 | hands-on | **deep-links into the sim** |
| `## Takeaway` | 37 | the close | reads 3 lines |

## Scope

1. **Block kinds (additive).** Extend `LessonBlock.kind` in `backend/app/schemas/lessons.py` beyond
   `markdown|quiz|chat_with|animation|term`. New kinds carry their params as data so the client
   renders without new painter code. Additive only — existing clients keep parsing.
2. **`LessonViewMode`.** Persisted per user, seeded from the live `mandate.learning_style`
   (`quick|story|visual|hands_on` — already shapes agent tone in `overlay_generator.py:236`, never
   reaches lessons). Toggle always visible in the reader. Mirror `RoomViewMode`'s persistence.
3. **The beat-deck renderer.** New route/mode off the existing `switch (block.kind)` at
   `lesson_reader_screen.dart:307`. Reuse the `quizOnly` precedent (A19) for block filtering.
4. **Parameter-bound visuals.** The 7 painters in `mobile/lib/widgets/lessons/anim/` already take
   `level` / `points` / `series` / `leftValue`+`rightValue`. Bind a slider to those params; extend
   `animation_registry.dart` so an entry can declare its bound parameter and range. **A new visual
   is a registry entry (data), not painter code.**
5. **Interaction widgets.** Reuse the 5 daily-challenge activity types (predict the call · spot the
   violation · read the chart · match the agent · what's missing — authored and graded already) plus
   four in-card primitives: tap-to-reveal, parameter play, order-the-steps, binary sort.
6. **~3 new painter primitives** for measured gaps: comparison bars (ratio screens; the 4%-table
   lessons), flow/pipeline (the Room process, screening stages), distribution (base rates,
   expectancy). `fl_chart` (already a dependency) for real market-data charts where reading real
   data *is* the skill.
7. **Read the user's own mandate in the model.** CR101 made the risk caps disclosed and
   user-settable; the sizing model should therefore teach with **the learner's actual caps**, not a
   constant. That is D-030's "mandate context" personalisation with **zero LLM cost**.
8. **Authoring-prompt v4 addendum** — beat/card structure, a per-card word ceiling, and "every card
   earns a visual or an interaction", so new content is born interactive.

### Formative vs scored — a hard rule, not a preference

**DEF042** established that scored answers + explanations arrive **only post-attempt, server-side**
(anti-cheat). Keep that for the graded quiz. In-card **formative** interactions are not scored and
may resolve client-side for the instant loop. Every interaction type must be declared one or the
other. Get this wrong and we either break DEF042 or lose the feedback loop that is the point of the CR.

### Degrade loudly (CR040 / CLAUDE.md)

A lesson with no interactive assets must **not** present an empty interactive mode — hide the toggle
for that lesson, or state "book only". A placeholder box where a diagram belongs is the
"not enough pictures" complaint restated. Enforce structurally, not by authoring convention
(CR038: prompt instructions are not controls).

## Pilot — RISK 1–6 (lessons 013–018)

Chosen to demonstrate the animation capability: the densest animation cluster in the corpus and a
contiguous, beginner-critical block (level 1, module 3). **4 of 6 already have a registered
animation**, and all four are numeric-parameter lessons that map onto sliders with no new painter code.

| Lesson | Code | Existing animation → primitive | Slider |
|---|---|---|---|
| 013 why risk matters | RISK 1 | *(none — add)* | loss-streak depth → survival |
| **014 position sizing** | RISK 2 | `position_size_calc` → BalanceScale | **stop → share count** |
| **015 stop loss** | RISK 3 | `stop_loss_trigger` → ThresholdTrigger | stop level vs price path |
| **016 risk/reward** | RISK 4 | `risk_reward_scale` → BalanceScale | target/stop → R:R |
| 017 exposure & correlation | RISK 5 | *(none — add)* | correlation → combined drawdown |
| **018 drawdown** | RISK 6 | `drawdown_recovery` → CurveDraw | depth → gain to recover |

013 and 017 stay in deliberately — they test whether adding a visual is genuinely cheap. All six
already have `.ar`/`.ms` siblings, so the pilot also measures true re-translation cost per lesson.
`technical_analysis` module 4 (TECH 1/4/5) is wave two.

## Prototype (built, reviewed)

`prototype/lesson_modes.html` — lesson 014 both ways side by side with a **working** sizing model
that reproduces the lesson's own figures ($21/9 shares/21.6% at $459; $10/20 shares at $470) and
enforces the real `SINGLE_NAME_ABSOLUTE_CAP_PCT = 50.0`, so pushing the stop past ~$471 visibly hits
the PM floor. Plus six live samples across four interaction types: stop-loss (ThresholdTrigger,
drag), drawdown asymmetry (CurveDraw, drag), candle anatomy (CandleAnatomy, **tap to identify**),
RSI threshold vs signal count (Oscillator, drag — 9 signals at 55, 1 at 85 on one unchanged series),
ruin math (**new** streak-bar primitive), and the Sharia ratio screen (**new** comparison-bar
primitive, **toggle** — one balance sheet passes DJIM 33/33/5 and fails AAOIFI 30/30/5). Footer word
counts are DOM-read, so the density claim verifies itself.

## Translation

Every EN card change invalidates its AR/MS sibling per-`id`
([[feedback_content_change_flags_translation]]; DEF105 class). Cards carry **less** text per unit than
620-word prose, so this is a net reduction — but each change must be flagged in
`content/_authoring/cr060_lessons_retranslate.md`, and book mode protects the existing translated
corpus while interactive content lands. `locale_staleness_check.py` already flags stale siblings.

## Constraints — decided or rejected, do not re-litigate

- **D-027** education free, all tiers, never gated — interactive mode is not a paid tier.
- **D-029** static MDX, no CMS at MVP. **D-061** coded CustomPainter, **no Lottie**.
- **Rejected:** social leaderboards / copy-trading (comparison undermines personalised learning).
  Streaks are fine and specced — `daily_and_streaks.md` counts **trying, not correctness**
  ("anti-gambling-loop"). Honour that in any interactive scoring.
- **Rejected:** quiz "length-tell" normalisation — *"this is adult education, not exam prep."*
  Interactive mode must not become gamified drilling.
- **D-030** the AI-tutor wrapper is decided but unbuilt (no LLM coupling in `lessons_service.py`).
  **Recommend keeping it out of v1** — prove the format on static blocks before adding per-load LLM
  cost. Scope item 7 delivers the mandate-personalisation half of D-030 for free.

## Lane split

- `CR174-BE` (`coder.api`) — the `LessonBlock` kind extensions and any parse/serve changes.
  GATE independent.
- `CR174-MOBILE` (`coder.mobile`) — `LessonViewMode`, the beat-deck renderer, the interaction
  widgets, the slider→painter binding, registry extension. DEPENDS-ON `CR174-BE`.
- `noncoder.edu` (me) — the pilot's beat authoring, registry parameters per lesson, prompt v4
  addendum, re-translation flagging.

**Sequencing:** build starts **after** the 150 lesson P1 fixes (DEF101) and the daily-challenge work
land, per Saiful's call. Content-quality first, then delivery.

## Acceptance

1. **Book mode is byte-identical in output** — a regression diff on rendered book-mode blocks for a
   sample of lessons shows no change.
2. **Measured against the recorded baseline:** words-per-card ≤ ~60 (vs 620/lesson); first
   interaction at ≤1 card (vs 50% of body); ≥1 visual per lesson in the pilot (vs 0 in 96% today).
3. **Instant feedback on formative interactions**, server-authoritative grading preserved for scored
   quizzes; a test proves a scored answer is not present in the client payload pre-attempt (DEF042).
4. **Guard, derived not hard-coded:** a corpus test asserting no lesson declares an interactive block
   whose registry key or asset is missing — so a new block kind is inside the guard by construction.
   `failure_patterns.md` entry names the derived check.
5. `pytest backend/tests/unit/ -q` green incl. `test_lesson_corpus_integrity.py`; CR087 locale
   quiz-parity gate untouched; the full 348-lesson catalogue still serves.
6. **Judged on device**, not in theory — `flutter build ios --release` + `flutter install`, same
   lesson compared in both modes.
7. **Instrumentation before scale-out:** interactive-mode entry + per-card completion logged on the
   pilot. The daily-challenge 2% discovery number is the warning; do not re-author ~300 lessons
   before the pilot's numbers are in.

## Open decisions

1. Interactive as the **default** for new users, or opt-in? (Recommend: default derived from
   `learning_style`, toggle always visible, persisted.)
2. Does **D-030's LLM wrapper** enter scope, or is v1 fully static blocks? (Recommend: static.)
3. Pilot to **TestFlight** for tester judgement, or Saiful's device first?
4. Housekeeping: `backend/app/schemas/lessons.py` still documents `animation_name` as looking up
   "a Lottie asset" — contradicts D-061 and the shipped registry. One-line docstring fix.
