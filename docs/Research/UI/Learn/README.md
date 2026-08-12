# Learn-surface research — interactive lesson delivery

**2026-08-12** · planning only; build deferred until the queued content-quality work lands
(150 lesson P1 fixes, daily-challenge regeneration). Sibling lane `../Version-0.2/` covers the
Floor and the Room and explicitly not Learn, so this is the untouched surface, not a duplicate.

## The complaint

Tester feedback: **(1) too many words, not enough pictures; (2) too passive, not enough activity.**
Saiful's framing for the fix: **two modes — "book mode" (what ships) and an "interactive mode."**

## The complaint, measured

Measured across `content/lessons/*.en.mdx` (2026-08-12):

| Metric | Measured |
|---|---|
| EN lessons | 348 |
| Prose words | **218,976** total · median **620**/lesson · p90 779 · max 1,091 |
| **Lessons containing an image** | **0 (0%)** |
| With a table / bullet list / numbered list | 4% / 20% / 6% |
| Paragraphs | 2,609 · median 65w · **24% ≥100 words** · max 251w |
| **First interaction** | **50% through the body** (median) |
| Interaction inventory | 748 `<Quiz>` (2.15/lesson) · 348 `<ChatWith>` · 697 `<Term>` · 15 `<Animation>` |

Quiz correctness is revealed only after a batch `.submit()` at the end
(`lesson_reader_screen.dart`, `revealResult`). So: a ~620-word scroll, no pictures, nothing to do
until halfway, and no feedback until the end.

**Real-user data (172 alpha users, `../Version-0.2/claude/08_personas.md`):** lessons are the
**second-most-used core action — 30 users (17%)**, behind Room convenes (32). But daily challenges —
the one genuinely interactive surface already shipped — sit at **4 users (2%)**.

> **Design conclusion:** do not build a new interactive destination. A separate activity surface is
> what daily challenges already are, and it is not being found. Interactivity belongs **inside the
> lesson flow** users already reach.

## The diagnosis: the visuals are decorative, not instructional

Not a coverage problem — coverage counts are not the argument, since A21 deliberately decoupled
content adoption from animation production, so low adoption in an alpha is expected. The problem is
what the visuals *do*.

**`014_position_sizing_basics` (RISK 2)** is one of the 15 animated lessons. Its `## Example` is 240
words of arithmetic, including this sentence (line 33):

> *"if you had set the stop at $470 instead, per-share risk drops to $10 and shares jump to 20 — the
> tighter the stop, the bigger the position you can carry at the same 1% risk."*

That is **a slider described in prose**. Meanwhile the animation it has renders
`BalanceScalePainter(leftValue: 2, rightValue: 2)` — a generic scale that never shows the lesson's own
figures ($20,000 / $480 / $459 / 9 shares). The picture decorates the text instead of carrying it.

**So the fix is:** bind the visual to the lesson's real numbers → let the learner move the parameter
the prose asks them to imagine → delete the prose the visual now does better. One change, all three
complaints.

## House levers (what already exists)

| Asset | State |
|---|---|
| 7 parameterized CustomPainters | Built — `mobile/lib/widgets/lessons/anim/`. Take `level` / `points` / `series` / `leftValue`+`rightValue`, so a new visual is a **registry entry (data)**, not painter code |
| 15 registered animations | Built and rendering, but authored with fixed decorative params — none bound to its lesson's figures |
| Block-based delivery | `LessonBlock.kind: markdown\|quiz\|chat_with\|animation\|term` — new kinds are additive (`backend/app/schemas/lessons.py`) |
| Block dispatch | One `switch` at `lesson_reader_screen.dart:307` |
| A view-mode precedent | `quizOnly` already filters blocks in the reader (A19); the Room's `RoomViewMode` is the sanctioned "default + one toggle away, persisted" pattern |
| `fl_chart`, `flutter_svg` | Already dependencies. No Lottie — D-061 implemented |
| `learning_style` | **Live** (`quick\|story\|visual\|hands_on`), already shapes agent tone via `overlay_generator.py`; never reaches lessons |
| D-030 AI-tutor wrapper | **Decided 2026-05, never built** — no LLM coupling in `lessons_service.py`. Spec already includes adaptive quizzing + remedial micro-lessons |
| 5 activity types | Authored + graded in daily challenges — proven as content, not as engagement (2% discovery) |

## Recommendation — one lesson, two delivery modes

Same MDX source, same block pipeline, same server contract; mode is a render-time choice.

- **Book mode** — today's reader, unchanged. Default for `STORY`; the accessibility path, the
  "I want to read" path, and the AR/MS fallback.
- **Interactive mode** — the same lesson as a **beat deck**: single-objective cards, each earning its
  place with a visual *or* an interaction, instant per-card feedback.

**The existing section skeleton already maps onto beats**, which is why this can start from the corpus
we have rather than 219k rewritten words: intro → the rule; `## Example` → the live model;
`## The trap` → commit-then-reveal; `## Quiz` → retrieval, moved earlier; `## Try it` → a deep-link
into the sim instead of 68 words describing it; `## Takeaway` → the close.

**Formative vs scored.** DEF042 established that scored answers + explanations arrive only
post-attempt, server-side. Keep that for the graded quiz. In-card formative interactions are not
scored and may resolve client-side for the instant loop. Stating which is which per interaction type
is mandatory, or we break DEF042 or lose the feedback loop.

**Degrade loudly (CR040/CLAUDE.md).** A lesson with no interactive assets must not present an empty
interactive mode — hide the toggle or state "book only". A placeholder box where a diagram belongs is
the "not enough pictures" complaint.

## Prototype

`prototype/lesson_modes.html` — two parts, all live.

**Part 1 — lesson 014 delivered both ways, side by side.** A working sizing model: drag the stop,
watch per-share risk, share count and notional recompute. It reproduces the lesson's own figures
exactly ($21/9 shares/21.6% at $459; $10/20 shares at $470) and enforces the real
`SINGLE_NAME_ABSOLUTE_CAP_PCT = 50.0` from `backend/app/trading_math/sizing.py`, so pushing the stop
past ~$471 visibly hits the PM floor. Word counts in the footer are DOM-read, so the density claim
verifies itself.

**Part 2 — six more beats, six interaction types**, to show breadth beyond one lesson and beyond
sliders. Four reuse shipped painters; two need a new primitive, which is the honest cost of covering
the rest of the corpus.

| Sample | Primitive | Interaction | What it teaches |
|---|---|---|---|
| RISK 3 · stop loss | ThresholdTrigger | drag | a tight stop is taken out by noise, then misses the recovery |
| RISK 6 · drawdown | CurveDraw | drag | −50% needs +100%; −75% needs +300% |
| TECH 1 · candle anatomy | CandleAnatomy | **tap to identify** | names the 4 parts by retrieval, not a labelled diagram |
| TECH 8 · RSI | Oscillator | drag | same 20 bars yield 9 signals at 55 and 1 at 85 — the level is a choice |
| RISK 1 · why risk matters | **new** (streak bars) | drag | 10 straight losses at 25%/trade leaves 5.6% |
| SHARIA 3 · ratio screen | **new** (comparison bars) | toggle | one company passes DJIM 33/33/5 and fails AAOIFI 30/30/5 |

The Sharia sample doubles as a check on the DEF117/DEF118 work: it shows the same balance sheet
flipping verdict on the standard alone, which is lesson 350's topic.

Source of truth is `prototype/template_lesson_modes.html`; regenerate with
`python3 docs/Research/UI/Learn/prototype/build.py` (never hand-edit the output).

## Pilot — RISK 1–6 (lessons 013–018)

Chosen to demonstrate the animation capability: the densest animation cluster in the corpus and a
contiguous beginner block — **4 of 6 lessons already have a registered animation**, and all four are
numeric-parameter lessons that map onto sliders with no new painter code.

| Lesson | Code | Existing animation → primitive | Slider |
|---|---|---|---|
| 013 why risk matters | RISK 1 | *(none — add)* | loss-streak depth → survival |
| **014 position sizing** | RISK 2 | `position_size_calc` → BalanceScale | **stop → share count** |
| **015 stop loss** | RISK 3 | `stop_loss_trigger` → ThresholdTrigger | stop level vs path |
| **016 risk/reward** | RISK 4 | `risk_reward_scale` → BalanceScale | target/stop → R:R |
| 017 exposure & correlation | RISK 5 | *(none — add)* | correlation → combined drawdown |
| **018 drawdown** | RISK 6 | `drawdown_recovery` → CurveDraw | depth → gain to recover |

013 and 017 are kept in deliberately — they test whether adding a visual is genuinely cheap. All six
already have `.ar`/`.ms` siblings, so the pilot also measures true re-translation cost.
`technical_analysis` module 4 (TECH 1/4/5) is wave two.

## Constraints — do not re-litigate

- **D-027** education free, all tiers, never gated. **D-029** static MDX, no CMS at MVP.
  **D-061** coded CustomPainter, no Lottie.
- **Rejected:** social leaderboards (comparison undermines personalised learning). Streaks are fine
  and specced — `daily_and_streaks.md` counts **trying, not correctness**.
- **Rejected:** quiz "length-tell" normalisation — *"this is adult education, not exam prep."*
  Interactive mode must not become gamified drilling.
- **Translation:** every EN card change invalidates AR/MS per-`id`. Cards carry less text per unit
  than 620-word prose, so this is a net reduction — but it must be flagged, and book mode protects
  the translated corpus.

## Open decisions

1. Interactive as the **default** for new users, or opt-in? (Recommend: default from `learning_style`,
   toggle always visible, persisted like `RoomViewMode`.)
2. Does **D-030's LLM wrapper** come into scope, or is v1 fully static blocks? (Recommend: static
   first — prove the format before adding per-load LLM cost.)
3. Ship the pilot to **TestFlight** for tester judgement, or judge on Saiful's device first?
4. One stale docstring to fix: `backend/app/schemas/lessons.py` still says `animation_name` looks up
   "a Lottie asset" — contradicts D-061 and the shipped registry.
