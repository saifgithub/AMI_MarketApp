# CR021 — Concierge context router (saver / full_context / embedding)

**Status:** proposed (documentation only — no implementation in this CR)
**Filed:** 2026-07-12 (AT:R54)
**Source:** Saiful — a selector over the three ways the Concierge can be given lesson
(and later app-manual) knowledge. Routes to:
[CR020](../CR020_concierge_full_context_mode/CR020_concierge_full_context_mode.md)
(cheap) + [CR019](../CR019_concierge_embedding_mode/CR019_concierge_embedding_mode.md)
(robust), with the current behaviour as the fallback mode.

---

## What

A single switch — the **concierge context flag** — that selects how much lesson knowledge
the Floor Concierge is given, so the three approaches are pluggable and comparable
without a code change:

| Mode | Env value | What it does | CR |
|---|---|---|---|
| **Saver** | `saver` | Today's behaviour — first 25 lessons, `id/title/track/level` only | (current) |
| **Full context** | `full_context` | Compact index of **all** lessons (`number + title + topic + tags`) in the prompt | CR020 |
| **Embedding** | `embedding` | Semantic retrieval — top-K relevant lessons per question | CR019 |

**At the moment, route on an environment flag only** — `CONCIERGE_CONTEXT_MODE`, **default
`full_context`**. No per-user / per-plan / adaptive routing yet (that is a later CR once
the modes are proven).

## Why

- The three routes are a **speed/cost/quality spectrum**; which one is "right" depends on
  corpus size, whether an embedding model is stood up (CR019 needs one; none exists today),
  and cost appetite. A flag lets us ship the safe default now (`full_context`), fall back
  to `saver` instantly if something regresses, and flip to `embedding` the moment CR019
  lands — all via `infra/alpha.env`, no redeploy of logic.
- It also gives a clean **A/B / degradation** story: `embedding` failures fall back to
  `full_context`, and `full_context` is always available with zero infra.
- Keeps the Concierge context-building behind one seam so CR022's app-manual corpus can
  plug into the same router.

## Design

- **Flag:** `CONCIERGE_CONTEXT_MODE` in `app/core/config.py` settings, values
  `saver | full_context | embedding`, **default `full_context`**. Set in `infra/alpha.env`;
  flows to melehost via `/promote-to-alpha` step 4 (env scp). Unknown/empty → default.
- **Seam:** a `ConciergeContextBuilder` (or a strategy function) chosen by the flag,
  consumed at the single injection point in `build_concierge_messages` /
  `load_concierge_context` (`concierge_prompts.py:39-82, 305-341`). Each mode returns the
  lesson-context block; the rest of the Concierge prompt is unchanged.
  - `saver` → the existing `_format_lessons(lessons[:25])` path (kept as-is).
  - `full_context` → CR020's compact all-lesson index.
  - `embedding` → CR019's `LessonRetriever.search(user_message, k)`.
- **Graceful degradation:** if the selected mode's dependency is unavailable (e.g.
  `embedding` set but the embedder/index is down, or `LessonRetriever` not built yet), the
  router logs once and **falls back to `full_context`** (then `saver`), never erroring the
  Concierge turn.
- **Observability:** log the active mode + (for embedding) the retrieved lesson ids + the
  lesson-context token size per turn, so mode comparison is measurable.

## Scope

**In:** the `CONCIERGE_CONTEXT_MODE` setting (default `full_context`); the router/strategy
seam at the single concierge context-build site; wiring `saver` (existing) + `full_context`
(CR020) + `embedding` (CR019) behind it; degradation fallbacks; per-turn mode/size logging;
tests for flag selection + fallback.

**Out:** the mode implementations themselves (CR019, CR020 own their internals);
adaptive/per-user/per-plan routing (future); the app-manual corpus (CR022, though it routes
through the same seam).

## Acceptance

- Setting `CONCIERGE_CONTEXT_MODE` to each of the three values changes the Concierge's
  lesson context accordingly, with **no code change** — verified by test + a live env flip.
- Default (unset) resolves to `full_context`.
- With `embedding` selected but its dependency absent, the Concierge still answers, using
  `full_context`, and logs the fallback once.
- Active mode + lesson-context token size are logged per turn.

## Dependencies / sequencing

- `saver` exists today → the router can ship with `saver` + `full_context` as soon as
  CR020 lands, defaulting to `full_context`.
- `embedding` becomes selectable when CR019 lands; until then the `embedding` value
  degrades to `full_context`.
- CR022 (app manual) extends each mode to also supply app-usage knowledge through this seam.
