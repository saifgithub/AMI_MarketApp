<!-- dispatch assign lane — Architect-owned. CR052. -->
# CR077-CONCIERGE — assign (Phase 0: static catalogue first, per-user context last)

KIND: code
INSTANCE: coder.api
ACCEPTANCE: docs/forward_planning/CR077_llm_prefill_caching_and_room_latency/CR077_llm_prefill_caching_and_room_latency.md (§Scope "Phase 0", §Verification 0)
DEPENDS-ON: none
GATE: spawned    <!-- Reordering reference data inside one prompt builder. No schema, no store upload, no legal text, no safety floor (that is PM-only), no change to what the prompt SAYS. A mistake is a redeploy away from fixed. What it is NOT is silent-safe — see "The failure mode" — which is why the byte-identical-head test is the deliverable, not a nicety. If the diff touches agent_prompts.py's floor ordering or any Room prompt, this gate is void: escalate. -->
HOT-FILES: backend/app/services/concierge_prompts.py (coder.api-internal; no cross-instance contention)

**What:** In `build_concierge_messages()`
([concierge_prompts.py:60-134](../../../backend/app/services/concierge_prompts.py#L60-L134)), split
the system prompt into a **fully static head** and a **per-user tail**. Move the 342-lesson
catalogue — today `lesson_block` at line 117, the last big block before the closing instructions —
in front of everything derived from a `Mandate`, a `user_id`, or a journal. Keep the closing
instructions last.

Nothing about the prompt's *content* changes. Only the order.

## Why — and this is measured, not argued

Architect re-measured against the live host `192.168.20.74:8000` on 2026-07-23, using a prompt built
from scratch rather than the CR's:

| shape | prompt tokens | **prefix-cache hit tokens** | latency |
|---|---:|---:|---:|
| catalogue last (today's order), brand-new user | 29,892 | **0** | 5,218 ms |
| catalogue first, same brand-new user | 29,892 | **29,344** | **284 ms** |

Measured as the delta on `vllm:prefix_cache_hits_total` / `queries_total` across a single request.
That synthetic prompt is ~2× the real Concierge prompt, so **do not quote those latencies as the
app's** — CR077 measured the real 15,731-token prompt at 14,672 cached / 344 ms and that is the
figure to reproduce. What both measurements agree on is the shape: today's order caches **exactly
zero**, and the only reason is where the static block sits.

Serving config also independently confirmed: `block_size="2096"`, `_block_size_resolved="True"`,
`user_specified_block_size="False"`, `enable_prefix_caching="True"`, `mamba_cache_mode="align"`.
Caching is whole-block only, so a cacheable prefix under 2,096 tokens is worth nothing at all —
which is what `base` alone (892 tokens, and mandate-derived anyway) currently is.

## The head must be provably static

`base = build_agent_prompt(AgentId.CONCIERGE, mandate, user_id=user_id)` (line 84) is itself
mandate-derived, so it **cannot** sit in the head as-is. Whatever you hoist must contain nothing
from `mandate`, `user_id`, `recent_journal`, or `unlocked_agents`.

`unlock_requirements` looks global rather than per-user — **verify that, don't assume it**. If any
element of it varies by user, it belongs in the tail. One interpolated field costs the entire
14,672 tokens, silently.

## The failure mode this lane exists to survive

Someone later adds a personalised line to the head — a greeting with the user's name, a plan badge,
anything. The prompt still renders. Every existing test still passes. The Concierge still answers.
The 2.3 s/message simply comes back and **nobody finds out**, because there is no signal. That is
the CR040 class arriving from inside the inference server, and CR077 records a second flavour of it:
in `align` cache mode a Mamba checkpoint landing in request-unique tokens makes vLLM discard the
*whole* prefix match with no error (vllm-project/vllm #45238).

So the test is the load-bearing deliverable.

## Tests

1. **Byte-identical head.** Build the prompt for two mandates that differ in **every** field, with
   different `user_id`, different journals, different unlocked-agent sets. Assert the first N
   characters are byte-identical, N ≥ 2 × 2,096 tokens' worth of text (use a character count you
   justify in a comment; chars/4 is the estimator already used at line 88). Prove it **red against
   today's ordering first**, then green.
2. **Closing instructions still last** — they say *"name ONLY the lessons in that agent's list
   above"*, which stays true only if the catalogue precedes them. Assert ordering, not just presence.
3. Existing concierge tests stay green — the prompt's content is unchanged, so any test asserting
   *what* the prompt says must not need editing. If one does, you have changed content: stop.

**Self-test:** `cd backend && .venv/bin/python -m pytest tests/unit/ -q -k "concierge or prompt"`
then the full `tests/unit/ -q`.

## Live measurement (required — §Verification 0)

Before and after, against `192.168.20.74:8000` with the **real** builder output for two distinct
users: report prompt tokens, hit tokens (metrics delta on `vllm:prefix_cache_hits_total`), and
latency. Target ≥ 14,672 cached tokens and < 500 ms on a second user's first message. Note the
`cached_tokens` field in the OpenAI usage response read **0** for the Architect even when the cache
was demonstrably serving 29,344 tokens — trust the `/metrics` delta, not that field.

**No estimates.** If you cannot reach the host, say so and hand off without the number rather than
inferring one.

## Second guard, cheap, in scope

Log the measured prefix-cache hit rate at startup and assert `enable_prefix_caching` is on. Right
now nobody would notice if it were switched off — which is exactly how it sat at 0% on this prompt
without anyone knowing.

## Out of scope — do not drift into it

CR077's Phases 1–3 (Room analyst parallelisation, and the vLLM `gpu_memory_utilization` bump) are
**not** this lane and are not yours. Phase 2 changes what the Room *is* and is held pending Saiful.
Do not touch `room_prompts.py`, `room_runner.py`, or `agent_prompts.py`. Restructuring the *Room*
prompts for a shared cacheable prefix is explicitly refused by the CR — it would move the persona
behind the safety floor.

## Delivery

Push to `lane/CR077-CONCIERGE.coder.api`, never `main`. Hand-off:
`orchestration/dispatch/lanes/CR077-CONCIERGE.coder.api.md` (`STATUS: READY_FOR_AUDIT (round 1)`) +
`orchestration/audit/cr/CR077-CONCIERGE.architect.md` (`SUBMITTED: round 1`). Chunk evidence list,
not the DoD. Commit tag `(AT:coder.api CR077)`.

**Commit both hand-off files to the SHARED branch, not your lane branch** (DEF090) — source goes to
the lane branch; the lane files are shared coordination state and every board reads them on the
shared branch. A hand-off committed only to a lane branch is invisible to both boards and has
already stranded a finished round; an uncommitted one renders `UNCOMMITTED` (DEF087).

ASSIGNED: coder.api round 1

DISPATCH: ACCEPTED

## Integrated (AT:R65, 2026-07-27)

Architect-spawned auditor VERDICT: COMPLETE (round 1) — zero BLOCKER/MAJOR, 1 non-blocking
MINOR (a static divider added to the head, so "only order changed" is imprecise). Merged
`f297196` to `main` @ `882b1c9`, post-merge suite 1300 passed. The live claim was reproduced
independently by the auditor (14,672 hit tokens / 318 ms vs 0 / 2,684 ms), not accepted from
the hand-off. Note for future lanes on this instance: the builder died on its $5 budget cap
but had committed incrementally so nothing was lost, and its hand-off misread this lane's
`GATE: spawned` as "no independent auditor required" — PROTOCOL.md 4a means an
Architect-spawned auditor, which is what ran.
