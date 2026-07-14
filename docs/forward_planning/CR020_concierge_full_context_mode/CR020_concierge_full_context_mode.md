# CR020 — Concierge lesson context: full context mode (cheap)

**Status:** ✅ done (AT:R59) — shipped with CR021. `full_context` is the default
mode: all 270 lessons emitted as `NNN · id · title · topic · tags`, grouped by
track, in `concierge_prompts.py::_full_context_index`. Measured ~10.2k tokens
(under the ≤12k target). Backend 753 tests green (+11).
**Filed:** 2026-07-12 (AT:R54)
**Source:** Saiful — after the AT:R54 analysis of how the Concierge knows which lessons
teach what. This CR documents the **cheap** route: put a compact index of *all* lessons
in the prompt, no embeddings. Sibling routes:
[CR019](../CR019_concierge_embedding_mode/CR019_concierge_embedding_mode.md) (robust /
embedding) + the selector
[CR021](../CR021_concierge_context_router/CR021_concierge_context_router.md).

---

## What

Replace the truncated 25-lesson list the Concierge sees today with a **compact index of
all 270 lessons** — `id + CR018 number + title + topic + tags + track` per lesson — dropped
straight into the Concierge prompt. No embeddings, no retrieval, no new infra. The LLM
picks the right lesson because it can finally *see* the whole catalogue. This is the
`full_context` value of the concierge context flag (see CR021).

## Why

The AT:R54 trace found the Concierge is blind to ~90% of the catalogue
(`concierge_prompts.py:192-200` truncates to the first 25 lessons, exposing only
`id + title + track + level`). The single cheapest fix that removes the blindness is to
stop truncating and stop hiding the knowledge fields: a compact all-lesson index costs
only prompt tokens and lands ~80% of the benefit of full retrieval, with **zero new
dependencies** — no embedding model, no vector store, no index-freshness pipeline. It is
the right first move and the sensible default (see CR021, which defaults to this mode).

## Design

- **Content of the index:** for every lesson, one line: `NNN · id · title · topic ·
  tags · track` (CR018 gives the stable `NNN` number). Optionally group by track using
  the existing `TRACK_TITLES` taxonomy (`lessons_service.py:61-69`) for readability.
- **Where:** extend `_format_lessons` / `build_concierge_messages`
  (`concierge_prompts.py:192-200`) to emit the full compact index instead of `lessons[:25]`
  and instead of only `id/title/track/level`. Surface `topic` + `tags` (currently parsed
  but never read — `LessonMeta.topic` is populated at `lessons_service.py:194` and read
  nowhere).
- **Token budget:** ~270 lines × ~30–45 tokens ≈ **8–12k tokens**. Well within the vLLM
  262k context. Measure + cap: if a future catalogue pushes this too high, that is exactly
  the signal to switch the flag to `embedding` (CR019).
- **No backend/model/schema change** beyond the prompt-building function and a token
  measurement. Reuses the already-loaded `all_meta()` (270 lessons already fetched by
  `load_concierge_context`, `concierge_prompts.py:305-341`) — today they are loaded then
  thrown away past the 25th.

## Scope

**In:** rework `_format_lessons` / the lesson block in `build_concierge_messages` to emit
the full compact `topic/tags`-bearing index; a token-size guard + log; the `full_context`
branch of the router (CR021); a test asserting all lessons + topic/tags reach the prompt
and the size stays under budget.

**Out:** embeddings / retrieval (CR019); the router mechanics (CR021); the app-manual
corpus (CR022); any change to lesson content or schema.

## Acceptance

- With the concierge context flag = `full_context`, the Concierge prompt contains **all
  270 lessons** with `number + title + topic + tags`, and the model can correctly name a
  lesson for a topic anywhere in the corpus (not just the first 25).
- Prompt token cost measured + logged; within a defined budget (target ≤ ~12k tokens).
- No new runtime dependency; backend tests green.

## Relationship to the other routes

`full_context` is the **default** mode (CR021). It is strictly better than the current
`saver` mode and needs no infra. `embedding` mode (CR019) supersedes it on precision +
scale once an embedding model is stood up; until then `full_context` is the recommended
production setting.
