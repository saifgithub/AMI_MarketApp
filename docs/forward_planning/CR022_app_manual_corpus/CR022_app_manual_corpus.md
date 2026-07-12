# CR022 — App manual corpus (Concierge app-usage knowledge)

**Status:** proposed (documentation only — no implementation in this CR)
**Filed:** 2026-07-12 (AT:R54)
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
