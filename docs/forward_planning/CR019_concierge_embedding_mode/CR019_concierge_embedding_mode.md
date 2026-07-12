# CR019 — Concierge lesson retrieval: embedding mode (robust)

**Status:** proposed (documentation only — no implementation in this CR)
**Filed:** 2026-07-12 (AT:R54)
**Source:** Saiful — after the AT:R54 analysis of how the Concierge knows which lessons
teach what. This CR documents the **robust** route: semantic retrieval over lessons.
Sibling routes: [CR020](../CR020_concierge_full_context_mode/CR020_concierge_full_context_mode.md)
(cheap / full-context) + the selector [CR021](../CR021_concierge_context_router/CR021_concierge_context_router.md).

---

## What

Give the Floor Concierge **semantic retrieval** over the lesson corpus: embed every
lesson, embed the user's question at chat time, and inject the top-K most relevant
lessons into the Concierge prompt — instead of the current truncated 25-of-270 title
dump. This is the `embedding` value of the concierge context flag (see CR021).

## Why

The AT:R54 trace found the Concierge sees only `id + title + track + level` for the
**first 25 of 270** lessons (`concierge_prompts.py:192-200`), blind to ~90% of the
catalogue, and there is **no topic→lesson lookup** (`topic` is parsed and read
nowhere). "Which lesson teaches X" is unbacked LLM guessing over 25 titles. Embedding
retrieval fixes this decisively and handles conceptual/paraphrase queries
("help me stop panic-selling" → drawdown/psychology lessons) that title-matching can't.

## Design

**Prerequisite — an embedding model on-prem (the crux; none exists today).**
`/v1/embeddings` on the vLLM host returns `Not Found`; both served models
(`ami-llm`, `qwen3.6-35b`) are generative. Two options:
- **A (recommended at this scale):** a small CPU `sentence-transformers` model
  (e.g. `bge-small-en-v1.5`, 384-dim) inside the `ami_api_alpha` image on melehost.
  ~10–50 ms/query on CPU; self-contained; no GPU-host dependency. Cost: heavier image.
- **B:** a dedicated embedder served on the vLLM GPU host (e.g. `Qwen3-Embedding-0.6B`,
  `bge-m3`) at `/v1/embeddings`. Faster, but another served model to keep alive.

**What we embed:** one vector per lesson (270). Embedding text = `title + topic + tags
+ body` (lessons are short — no chunking).

**Storage / index:** a Postgres table `lesson_embeddings(lesson_id, embedding,
content_hash, model, dim, updated_at)`. At 270 vectors, **brute-force cosine over an
in-memory numpy matrix is microseconds — no pgvector / ANN index needed** (add pgvector
+ HNSW only when the corpus reaches thousands).

**Indexing pipeline:** `scripts/build_lesson_index.py` — per lesson, hash content; embed
+ upsert only if new/changed (incremental, idempotent). Wired as a `/promote-to-alpha`
step so the index tracks each content promote.

**Runtime:** a `LessonRetriever` service loads vectors at startup; `search(query, k=8)`
embeds the query via a new `gateway.embed()` method (mirrors the `stream_chat` provider
pattern, provider-fallback like generation), cosine-ranks, returns top-K `LessonMeta`
+ score. Injected into `build_concierge_messages` as "Most relevant lessons for what the
user just asked" (id + CR018 number + title + topic + tags + one line).

**Fallback:** embedding path down → degrade to `full_context` (CR020) or `saver`
behaviour via the router (CR021). Stale index → rebuilt on next promote.

**Optional v2:** expose `search_lessons(query)` as an LLM **tool** (agentic retrieval,
model decides when to search) instead of always-on per-turn injection.

## Scope

**In:** embedding model decision (A/B) + gateway `embed()`; `lesson_embeddings`
migration; `build_lesson_index.py` + promote step; `LessonRetriever`; the `embedding`
branch of the concierge context router (CR021); tests (index build, retrieval ranking,
fallback).

**Out:** the router mechanics themselves (CR021); the full-context path (CR020);
fine-tuning an embedder (Silent_Scout, out of scope); the app-manual corpus (CR022 — but
this CR's index/retriever should be built so the manual can reuse it).

## Acceptance

- With the concierge context flag = `embedding`, a Concierge question like "which lesson
  covers stop losses / position sizing / candlesticks" surfaces the correct lesson(s)
  from anywhere in the 270-lesson corpus, ranked by relevance — not limited to the first 25.
- Index build is incremental (only changed lessons re-embed) and runs in the promote flow.
- Embedding-path failure degrades gracefully (no Concierge outage).
- Backend tests green; retrieval quality spot-checked on a set of representative queries.

## Notes / open decisions

1. Embedding model location: **A (CPU-in-backend)** vs **B (GPU-served)** — recommend A now.
2. Which embedder + dimension.
3. Plain-Postgres float array vs pgvector (recommend plain at 270; pgvector when it grows).
4. Per-turn implicit injection vs `search_lessons` tool (recommend implicit v1, tool v2).
