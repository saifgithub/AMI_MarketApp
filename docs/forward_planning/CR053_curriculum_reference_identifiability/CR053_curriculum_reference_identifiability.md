# CR053 — Curriculum reference identifiability, quick-link feasibility, and unlock UX

**Status:** **IMPLEMENTED** (AT:R64, 2026-07-22) — Saiful: *"do it."* Built + audited under this same
CR053 id in 3 lanes: **CR053-BE** (`<Lesson id/>`→`{{lesson:}}` token + resolve guard, auditor COMPLETE
257587d) · **CR053-MOBILE** (`{{lesson:}}` chip + prerequisites render/link + tappable gateway rows,
auditor COMPLETE a4aede0) · **CR053-MIGRATE** (327 lesson-body refs → full-id `<Lesson/>` tags + 33 daily
→ CR044 codes, content review PASS). Phase 3 (runtime Concierge/chat code-regex linkifier) deferred as
optional per §5 — Saiful's call. Original filing was audit + feasibility only · **Session:** AT:R63 · **Filed:** 2026-07-21

> Directive (Saiful, verbatim): *"go through all educational and daily-challenge materials
> again. (1) any internal reference made to any material can be easily identified by the
> customer using the app. (2) While I do not want you to code, check the capability and
> possibility that any references can be made into a quick link to the material being
> referred to — what's the feasibility. (3) revisit how we tell customers of the material
> they need to cover for each agent with a view to making it user-friendly."*

This document is the **audit + feasibility assessment + UX review** that directive asks for.
It stops at findings and a recommended plan. Nothing here is implemented; a follow-up
implementation CR (or a split into two) is proposed at the end for Saiful to approve.

---

## 0. TL;DR

- **There is one root problem behind directive #1**, and it is not "references are missing" —
  it is a **vocabulary mismatch introduced by CR044**. In-content references address a lesson
  by its **bare id number** ("lesson 039"), but since CR044 the app only ever *shows* the
  lesson by its **group code** ("FUND 8"). The number the customer reads in the text appears
  **nowhere** in the app. A diligent user cannot resolve "see lesson 039" to any tile.
- **Feasibility of quick-links (#2) is high and mostly already built.** The deep-link target
  (`LessonReaderScreen(lessonId:)`), the inline tappable-chip renderer (`{{term:id}}`), and the
  server-side MDX-to-token substitution pipeline all exist today. Structured references are a
  *solved* pattern; free-text prose references need either an author-time tag or a client-side
  linkifier — both are medium effort, neither is research.
- **Directive #3 is 80% shipped (DEF068)** but has one glaring friction: the 5 gateway-lesson
  rows in the locked-agent sheet **name each lesson but aren't tappable**. The fix for #3 is
  largely the same work as #2 — make references tappable.

The three directives collapse into **one coherent body of work**: give every lesson a single
identifier the app both *shows* and *links*, and make every place that names a lesson a tap
target. Recommended as a phased implementation CR — see §5.

---

## 1. What was audited

| Corpus | Count | Location |
|---|---|---|
| Lessons | **270** `*.en.mdx` | `content/lessons/` |
| Daily challenges | **183** (30/31/31/30/31/30) | `content/daily_challenges/2026_{06..11}.json` |
| AI-coach Q&A | curated set | `content/ai_coach/` |
| Glossary terms | curated set | `content/glossary/` |
| Agent prompts | 13 | `content/agents/*.md` |

Every "reference to a material" was classified **structured** (a machine-readable field/tag the
app can act on) vs **free-text** (a number or name embedded in prose).

---

## 2. Directive #1 — are internal references identifiable in-app?

### 2.1 The reference surfaces, classified

| # | Surface | Reference form | Structured? | Identifiable in-app today? |
|---|---|---|---|---|
| A | Lesson frontmatter `prerequisites` | full lesson id (`033_profit_and_margins`) | ✅ | ❌ **not even rendered** in the reader |
| B | Lesson body `<Term id="…"/>` | glossary id | ✅ | ✅ tappable chip (`term_block` / inline) |
| C | Lesson body `<ChatWith agent="…"/>` | agent id | ✅ | ✅ tappable agent card |
| D | **Lesson body cross-lesson prose** ("lesson 039", "023", "Module 9") | bare number | ❌ | ❌ **number shown nowhere in app** |
| E | Daily-challenge `related_lesson` | bare id (`"065"`) | ✅ | ✅ tappable (deep-links to reader) |
| F | Daily-challenge `related_agent` | agent id | ✅ | ✅ surfaced |
| G | **Daily-challenge prose** ("lesson 070 fingerprint", "Module 11") | bare number | ❌ | ❌ not linked, number not shown |
| H | AI-coach `related_lessons` | id list | ✅ | ✅ tappable |
| I | Glossary `related_lessons` | id list | ✅ | ✅ tappable |
| J | Concierge / agent chat output | free-text, now cites CR044 `code` | ❌ (runtime) | partial — code is shown but not tappable |

### 2.2 The core finding — the CR044 vocabulary gap

CR044 replaced the user-visible lesson identifier. The badge on the lesson tile
(`lesson_tile.dart`) and the reader meta bar (`lesson_reader_screen.dart:256-258`) now render
**`meta.codeLabel`** — `"FUND 8"`, `"TECH 12"`, `"N&M 22"`. The raw numeric id (`039`) and the
raw track (`fundamentals_analysis`) were deliberately removed from view. That was the right call
for speakability — but the **content was written before CR044 and still speaks the old
language**:

- **238 free-text cross-lesson references** live in lesson bodies, across **117 of 270 files**.
- Of those, **only 17 carry the lesson title** in parentheses ("lesson 014 (Position sizing
  basics)"); the other **221 are a bare number** — "the math from Lesson 010", "the recovery
  cliff from lesson 018", "This assumes you've completed 023 (support and resistance)".
- **41 free-text lesson/module references** sit inside daily-challenge prose
  (scenario/question/options/explanation), likewise by bare number.

`content/lessons/039_the_pe_ratio.en.mdx` is the exemplar: its badge reads **FUND 8**, but three
*other* lessons point at it in prose as *"the P/E (lesson 039)"*. A customer holding the app sees
`FUND 8` on the tile and `lesson 039` in the sentence and has **no on-screen bridge** between the
two. The id `039` is not printed anywhere a user can see.

**So the answer to directive #1 is: no — not for free-text references.** Structured references
(B, C, E, F, H, I) are already identifiable and mostly already tappable. Free-text references
(D, G — 279 of them) are *not* identifiable, and the reason is specifically the CR044 code
switch, not a pre-existing authoring gap.

### 2.3 Severity

This is low-severity-per-instance but high-frequency: it doesn't break anything, but 117 lessons
contain at least one sentence that references material the reader cannot locate. The most
educational lessons are the worst affected — the synthesis lessons that tie ideas together
("combines growth with the P/E (lesson 039)", "the math from lessons 007–011") are *built* on
cross-references, and those are exactly the ones now pointing at invisible numbers.

---

## 3. Directive #2 — feasibility of turning references into quick-links

**Verdict: feasible, and cheaper than it looks, because every building block already exists.**
This is an *extend-a-pattern* job, not an invent-a-capability one.

### 3.1 The three mechanisms already in the codebase

1. **The deep-link destination exists and is proven.**
   `LessonReaderScreen(lessonId: <id>)` is already the navigation target from **three** live
   surfaces: daily-challenge cards (`daily_challenge_card.dart:322-335`), AI-coach answers
   (`ai_coach_screen.dart:269-278`), glossary term sheets (`term_block.dart:191-204`). Any new
   link just pushes the same route.

2. **Inline tappable text already exists.** The reader's prose renderer
   (`lesson_reader_screen.dart:_inline`, :523-563) tokenizes a paragraph into a mix of plain
   `TextSpan`s and **tappable `WidgetSpan`s**. The `{{term:id}}` glossary chip is exactly this:
   an inline token woven into running prose that opens a sheet on tap. A lesson-reference chip is
   **one more regex alternative and one more `else if`** in that same function.

3. **The server already rewrites MDX tags into inline tokens.**
   `lessons_service.py:122-127` turns `<Term id="X"/>` into the `{{term:X}}` token the client
   renders. A `<Lesson .../>` (or `<LessonRef .../>`) tag would ride the identical substitution
   path to a `{{lesson:039}}` token. The pipeline seam is already cut.

The distance from "reference" to "quick-link" is therefore: **define a token, add one client
branch, and decide how the token gets into the prose.** That last decision is the whole ballgame.

### 3.2 Two strategies for the free-text references (D, G)

| | **Strategy A — author-time structured tag** | **Strategy B — client-side linkifier** |
|---|---|---|
| Idea | Migrate the 279 prose refs to a `<Lesson code="FUND 8"/>` tag (or `{{lesson:039}}`) | Ship a regex that matches code tokens / "lesson NNN" in *any* rendered prose and auto-links |
| Content edits | ~279 edits across ~150 files (scriptable, like `shuffle_quiz_answers.py`) | **zero** content edits |
| Reliability | exact — the tag names the target | heuristic — must disambiguate "lesson 039", "023", "Module 9", ranges ("lessons 007–011") |
| Also fixes #1 identifiability? | ✅ yes — the tag renders the **code**, which matches the badge | ⚠️ only if it *rewrites* the visible text to the code; a linkifier that leaves "lesson 039" on screen links it but the vocabulary still mismatches |
| Where it works | lesson reader + daily challenges (content we control) | everywhere prose is rendered, **including live Concierge/agent chat output** |
| Risk | one-time migration; guardable by a corpus test (every `<Lesson/>` code must resolve) | false positives ("in 2024", "$135 price"), false negatives (ranges, "the P/E lesson"), locale drift when AR/MS land |

**These are not exclusive — the right answer is A for authored content, B for runtime chat.**
Authored corpora (lessons, daily challenges) get the reliable structured tag *and* the
vocabulary fix in one migration. Concierge/agent output can't be pre-tagged (it's generated at
runtime), so a narrow linkifier keyed to the **CR044 code regex** (`\b(CORE|FUND|TECH|N&M|SENT|
RISK|EDGE)\s?\d{1,3}\b`) makes its citations tappable — and CR044 already made the concierge
*emit* those codes, so the linkifier has a clean, unambiguous token to match (far safer than
matching "lesson NNN").

### 3.3 Feasibility matrix

| Surface | Strategy | Effort | Risk | Notes |
|---|---|---|---|---|
| Daily-challenge `related_lesson` (E) | already done | **0** | none | 181/183 already deep-link; backfill the 2 missing |
| AI-coach / glossary `related_lessons` (H, I) | already done | **0** | none | live |
| Lesson `prerequisites` (A) | render + link the existing field | **S** | low | data already structured; reader just doesn't show it. High-value, cheapest new win |
| Lesson body cross-refs (D) | A (migrate to `<Lesson/>`) | **M** | low w/ guard | 238 refs, 117 files; scripted + corpus-test-guarded |
| Daily-challenge prose (G) | A (tag) or promote to structured | **S–M** | low | only 41 refs |
| Concierge/agent chat (J) | B (code-regex linkifier) | **M** | medium | narrow regex on CR044 codes only; degrade-loudly if a code doesn't resolve |
| Locked-agent gateway rows (see §4) | make rows tappable | **S** | none | pure win; overlaps directive #3 |

S = small (hours), M = medium (1–2 days incl. migration + guard). **Nothing is L or research.**

### 3.4 The one real design decision

Whether to **rewrite the visible reference text to the code** ("FUND 8") or **keep the number and
just make it tappable**. Recommendation: **rewrite to the code.** It is the only option that
satisfies directive #1 (identifiability) as well as #2 (linkability) — a tappable "lesson 039"
still shows the user a number the rest of the app has abandoned. Rewriting to "FUND 8" makes the
sentence, the badge, and the Concierge all say the same thing. This is a content migration, and
it's the same 238-ref pass as Strategy A, so #1 and #2 are literally one edit.

---

## 4. Directive #3 — telling customers what to read per agent, user-friendly

### 4.1 What already shipped (DEF068) — don't rebuild

- `GET /v1/lessons/requirements/{user_id}` returns, per agent: `required:[{lesson_id, code,
  title, passed}]`, `passed_count`, `remaining_count`, `unlocked`.
- The locked-agent sheet (`floor_screen.dart:142-279`) renders from it: each of the 5 gateway
  lessons as a row with a check/school icon, the **CR044 code** (cyan mono), and the title; a
  "GO TO LESSONS" CTA; and a progress button that jumps to the next unfinished gateway lesson's
  *track*.
- Concierge context carries per-agent unlock paths, so "what unlocks the Trader?" is answerable.

### 4.2 Friction points found

1. **The gateway rows are not tappable.** `floor_screen.dart:201-225` renders each required
   lesson as a static `Row`. The user is told "pass FUND 8 · The P/E ratio" but tapping it does
   nothing. This is the single biggest friction and it is **the same fix as directive #2** —
   make the row a deep-link to `LessonReaderScreen(lessonId: lesson.lessonId)`.
2. **Both CTAs under-deliver on "take me there."** "GO TO LESSONS" dumps the user at the hex
   cluster (`LessonsScreen`); the progress button lands on the *track* list, where the user must
   still hunt for the right lesson among tiered rows. Directly deep-linking the **next unfinished
   gateway lesson** would remove that hunt.
3. **No sense of "how close am I."** The sheet shows per-lesson ticks and an "n / 5" count but no
   ordering cue for *which to do next* (the progress button picks one silently). A "NEXT: FUND 8"
   affordance would make the path obvious.
4. **Copy check.** `floorLockedHowTo` + `floorLockedEarnByLessons(n)` read acceptably post-CR044,
   but should be re-read against the friendlier flow (e.g. "Tap a lesson to start" once rows are
   tappable). The old factually-wrong "pass every lesson that involves them" string was already
   fixed in DEF068 — no regression there.
5. **Discovery is reactive only.** The 5-lesson requirement is visible **only** if the user taps a
   locked agent on the Floor. There's no "you're 3/5 toward unlocking the Fundamentals Analyst"
   nudge inside the Lessons area, where the user actually is when studying. Worth considering a
   forward pointer (out of scope to design fully here; flag for the implementation CR).

### 4.3 Recommendation for #3

The friendliness win is small and mostly overlaps #2: **make the gateway rows tappable
deep-links, and point the primary CTA at the next unfinished gateway lesson rather than a screen
the user has to search.** Copy tweak follows. Everything else (endpoint, curation, per-lesson
progress) is already in place from DEF068.

---

## 5. Proposed implementation (for a follow-up CR — NOT this one)

Because #1, #2, #3 converge on "one shown-and-linkable identifier, every reference a tap target,"
recommend a **single phased implementation CR** (or split 5A content / 5B client if Saiful wants
smaller commits):

- **Phase 1 — cheapest, highest value, no content migration.**
  - Render + link `prerequisites` in the lesson reader (surface A — data already exists).
  - Make the locked-agent gateway rows tappable; repoint the CTA to the next unfinished gateway
    lesson (directive #3, surfaces §4.2 #1–#2).
  - Backfill the 2 daily challenges missing `related_lesson`.
- **Phase 2 — the content migration (fixes #1 + #2 together).**
  - Define the `<Lesson code="…"/>` MDX tag → `{{lesson:…}}` token (server, mirrors `<Term>`).
  - Add the `{{lesson:…}}` branch to the reader's `_inline` tokenizer (one `else if`).
  - Scripted migration of the 238 lesson-body refs + 41 daily-challenge prose refs from bare
    number to the code tag (like `scripts/shuffle_quiz_answers.py`: textual, in-place, committed).
  - Corpus-test guard: every `<Lesson/>` code resolves to a real lesson; degrade-loudly if not
    (per `failure_patterns.md`).
- **Phase 3 — runtime chat (optional, gated on Phase 2).**
  - Narrow client-side linkifier over the CR044 **code regex** in Concierge/agent chat output,
    reusing the Phase-2 resolve map. Degrade-loudly: an unresolvable code renders as plain text,
    never a dead tap.

Effort estimate: Phase 1 ≈ small (hours); Phase 2 ≈ 1–2 days incl. migration + guard; Phase 3 ≈
half a day. No new dependencies, no backend schema change beyond the token substitution.

### Guards (when implemented)
- Extend `backend/tests/unit/test_lesson_corpus_integrity.py`: every `<Lesson/>`/`{{lesson:}}`
  token resolves; no bare "lesson NNN" left in migrated bodies (or an allowlist for intentional
  prose).
- Widget test: a `{{lesson:}}` token renders a tappable chip; an unresolvable one degrades to text.

---

## 6. Constraints honoured

- **The CR044 `code` is the canonical, frozen, speakable identifier.** All linking/identifiability
  builds on it. Nothing here renumbers it to list position — that would re-break DEF068 + DEF071.
- **No code was written for this CR** — audit + feasibility + UX only, per the directive.
- **Degrade-loudly (CR040):** every proposed link resolves or renders as plain text; no silent
  dead taps. Any config/token gap fails a corpus test, not the user's screen.
- **AMI by name** in any new user-facing copy; **LLM** only in code.

## 7. Registers

- Row added to `docs/forward_planning/cr_list.md` (CR053, status `planned`).
- This CR is **audit/planning**; the implementation lands under a follow-up CR id once Saiful
  approves the §5 plan. Commit tag for filing this doc: `(AT:R63 CR053)`.
