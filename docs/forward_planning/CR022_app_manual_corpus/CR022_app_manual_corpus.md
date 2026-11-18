# CR022 — App manual corpus (Concierge app-usage knowledge)

**Status:** in_progress (AT:B1, 2026-11-18) — built as CR267 WP-39; see "What was built" below.
Live rig check of the 10-question set is outstanding (Saiful runs it).
**Filed:** 2026-07-12 (AT:R54)
**Sequencing:** was "defer to just before release" (Saiful, 2026-07-31). Pulled into the Beta
programme at CR267 WP-01 (2026-11-18): the Beta build is the stopped-moving surface the
deferral was waiting for. English only; AR/MS flagged (`translation_pending`).
**Source:** Saiful — "the concierge is also supposed to know how to use the app fully."
Give the Concierge a manual of how the app works, **treated the same way as lessons** so
it flows through the same context router (CR021) and the same three modes
([CR019](../CR019_concierge_embedding_mode/CR019_concierge_embedding_mode.md) /
[CR020](../CR020_concierge_full_context_mode/CR020_concierge_full_context_mode.md)).

---

## What

A first-class **app-manual corpus** — structured "how to use the app" entries authored and
indexed exactly like lessons — so the Floor Concierge can answer "how do I convene the
Room?", "where's my watchlist?", "how do I brief an agent?", "how do I place a trade?"
accurately, instead of guessing or hallucinating UI. The manual is a *second knowledge
base* that rides the same pipeline as lessons: parsed → given topic/tags metadata →
supplied to the Concierge through the concierge context router (CR021), in whichever mode
is active (`saver` / `full_context` / `embedding`).

## Why

- The Concierge is the app's front door and "personal assistant — tap to chat," but today
  it has **no grounded knowledge of the app's own features/flows** — the AT:R54 trace
  found its context is lessons + unlocked agents + recent journal only. App-usage answers
  are ungrounded LLM guesses, which risks confidently wrong navigation instructions.
- Lessons teach *market knowledge*; the manual teaches *the product*. Both are "knowledge
  the Concierge routes people to." Reusing the lesson machinery (CR019/020/021) means the
  manual gets retrieval/full-context/fallback **for free** — no parallel system.
- Keeps product truth in one authored place that tracks the app as features ship (Convene,
  Brief Your Agent, league, share cards, daily challenge, etc.), rather than baked into the
  Concierge prompt as prose that silently drifts.

## Design

- **Content:** `content/manual/*.en.mdx`, mirroring `content/lessons/`. Frontmatter per
  entry: `id`, `title`, `topic`, `tags`, `section` (e.g. floor / trading / room / brief /
  portfolio / journal / lessons / league / account / settings), `related_routes` (the app
  routes/screens the entry covers, e.g. `/floor`, ticker detail), `updated_at`. Body =
  concise, accurate how-to prose in the AMI voice (numbers > adjectives, "AMI" by name).
  Coverage = every core-loop surface + every shipped feature.
- **Parsing/service:** a `manual_service.py` mirroring `lessons_service.py::parse_mdx` →
  a `ManualEntry` / `ManualMeta` schema. Small corpus (tens of entries, not 270).
- **Integration — the key requirement ("same way as lessons"):** the concierge context
  router (CR021) supplies manual entries alongside lessons in every mode:
  - `full_context` (CR020): append a compact all-entries manual index
    (`title + section + topic + tags`) to the prompt — cheap, tens of lines.
  - `embedding` (CR019): index manual entries in the **same** `LessonRetriever` /
    `lesson_embeddings` store (or a sibling `manual_embeddings`) so a user question
    retrieves the best lesson **and/or** the best manual entry, ranked together or in two
    labelled buckets ("relevant lessons" + "relevant how-to").
  - `saver`: include a short static manual summary (a handful of top entries).
- **Authoring split:** Claude drafts the manual entries from the real app surfaces + specs
  (`docs/initial_specs/01_product/core_loop_and_features.md`, the Flutter screens); Saiful
  reviews for product accuracy (a you-do/I-do content task, like lesson review).

## Scope

**In:** the `content/manual/` corpus + authoring; `ManualEntry` schema + `manual_service`
parser; extension of the CR021 router + each mode to also supply manual context (shared
retrieval/index with lessons under `embedding`); tests (parse + that manual entries reach
the Concierge context in each mode).

**Out:** a user-facing manual/help screen in the app (this CR is about the *Concierge's*
knowledge; a browsable in-app help centre could be a later CR); rewriting the lesson
corpus; the router/mode internals (CR019/020/021 own those — this CR consumes them).

## Acceptance

- The Concierge answers core "how do I use the app" questions (convene the Room, brief an
  agent, place/close a trade, watchlist, journal, daily challenge, league, account claim,
  language switch) with **grounded, correct** steps sourced from the manual corpus — in
  whichever context mode is active.
- Manual entries flow through the CR021 router in all three modes (verified per mode).
- Under `embedding`, a how-to question retrieves the right manual entry; a knowledge
  question retrieves the right lesson; a mixed question surfaces both.
- Manual content reviewed by Saiful for product accuracy; parse + integration tests green.

## Dependencies / sequencing

- Consumes CR021 (router) + CR020 (full-context) and, for `embedding`, CR019 (retrieval).
- Can ship its content + `full_context`/`saver` integration before CR019; the `embedding`
  path lights up when CR019's retriever exists (manual entries index into the same store).
- Content authoring should track shipped features — treat the manual as living product
  documentation, updated as CRs add/behaviour-change surfaces.


---

## What was built (AT:B1 CR267 WP-39, 2026-11-18)

**Corpus.** `content/manual/NN_slug.en.mdx`, 28 entries, frontmatter + MDX body exactly like
`content/lessons/`. Each entry carries `id`, `title`, `section`, `topic`, `tags`, `questions`
(the phrasings a tester types; the retrieval index), `short_answer` (the whole answer on the
LLM-offline path), `locale_versions: ["en"]` and `translation_pending: ["ar","ms"]` (the flag
the i18n lane reads), and three verification fields: `screens` (Flutter files described),
`arb_keys` (l10n keys the body quotes) and `literals` (hard-coded labels). Every step was
derived from `mobile/lib/screens/**` and `mobile/lib/l10n/app_en.arb` at commit `1d51dc50`.

**Excluded on purpose.** Payments, plans, credit purchase and the Membership section; the
Developer section; the GAME tab (compile-time gate `AMI_GAMES`, absent from store builds);
Silent Scout; the Alpaca paper-link flow (see follow-ups); and the two unbuilt Beta items,
account deletion/export (WP-30) and the in-app Report button (WP-36). A scope-guard test
fails the build if the corpus names any of them, or the retired agent titles (PM, Trader,
Debator, Market/News/Social Analyst).

**Parse + retrieve.** `backend/app/services/manual_service.py` (+ `schemas/manual.py`) parses
with `lessons_service._FRONTMATTER_RE`. Retrieval is lexical (stop-worded, lightly stemmed,
field-weighted, IDF-weighted, plus a query-coverage bonus), threshold `MIN_SCORE = 9.0`,
at most 2 entries (second only within 75% of the first). No embedding store: at 28 entries
the CR019 machinery would be a parallel system for no gain; CR019 stays the escape hatch.

**Router seam (CR021).** `concierge_prompts.build_concierge_messages`: an `id · title` index of
the whole manual joins the static head (byte-identical for every user, so the CR077 prefix
cache is unaffected); the retrieved entries' full text goes in the per-user tail, with three
distinct states (matched / nothing matched / corpus unavailable). The closing rule: answer
how-to questions only from the retrieved entries, with their exact names. It also corrects
the prompt's old "Settings → Mandate" navigation, which does not exist in the app, to
"YOU → SETTINGS → MY MANDATE" (scripted mandate reply too; `test_concierge_live` updated).

**Citation (structural).** `agent_runner._stream_concierge` appends
`— Source: AMI app manual · <title> (<id>)` computed from the entries it supplied, after the
stream ends cleanly. Not requested from the model (CR038). Skipped when the stream errored
mid-reply. The scripted LLM-offline path answers from `short_answer` and appends the same
line: first for plainly how-to messages ("how do I…", "where is…"), otherwise as the last stop
before the generic fallbacks so state-aware routes ("what's my mandate?") still win.
Limit: the line proves which entries the model was GIVEN, not that its sentences used them.

**Degrade loudly.** A corpus that fails to load logs `manual_corpus_unavailable` at error level
and the prompt says so ("do not describe app screens from memory"). A per-turn
`concierge_manual` log line records available / entry ids / scores.

**Acceptance (offline).** Fixture `backend/tests/fixtures/manual/howto_questions.v1.json`
(10 questions with expected entry, plus 5 must-not-match). `backend/tests/unit/test_manual_corpus.py`:
retrieval returns the expected entry for each of the 10 and nothing for the 5; every
screen file exists; every ARB key exists and is rendered by a listed screen; every literal is
in a listed screen; every **bold** label in a body is the exact text of a declared key or
literal; scope guard; citation end-to-end per question; no citation on no-match or
mid-stream error; scripted path cites; unavailable-corpus prompt.

**Not covered / follow-ups.**

1. Live rig check: the 10 questions against vLLM (Saiful runs it).
2. WP-30 (account deletion/export) and WP-36 (Report button/settings): entries to write when those ship.
3. Alpaca paper-link entry (Settings, ALPACA PAPER): deliberately not written: it is a
   brokerage-linking flow with its own data-handling disclosure (keys on device, account summary
   sent with each Room), which Saiful should approve before it is paraphrased into the manual.
4. AR/MS translation of the 28 entries (`translation_pending`).
5. Re-verify entries after any later UI change; the truth tests catch renamed labels and removed
   screens, not changed flows.
