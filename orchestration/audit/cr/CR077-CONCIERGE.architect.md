<!--
CR077-CONCIERGE.architect.md — coder→audit hand-off. Chunk evidence, not the DoD (Architect renders
that once for the whole CR077). GATE: spawned per the assign file — self-verified below, no
independent auditor required.
-->

# CR077-CONCIERGE — audit lane

**Item:** CR077 Phase 0 — reorder `build_concierge_messages()` so the static 342-lesson catalogue
is a byte-identical head and everything derived from `mandate`/`user_id`/`recent_journal` is a
per-user tail, so the catalogue lands as a whole-block vLLM prefix-cache hit.

**Gate:** spawned (per `CR077-CONCIERGE.assign.md`) — reordering reference data inside one prompt
builder, no schema/store/legal-text/safety-floor change, no change to what the prompt says.

**Built SHA (round 1):** `f297196` on `lane/CR077-CONCIERGE.coder.api` (2 commits: `d99502f` the
reorder + tests, `f297196` the second guard).

**depends-on:** none.

## What changed / why

| SHA | Files | What |
|---|---|---|
| `d99502f` | `backend/app/services/concierge_prompts.py`, `backend/tests/unit/test_concierge_context_router.py` | `build_concierge_messages()` now emits `static_head` (the lesson catalogue) first, then `base` (concierge.md + mandate overlay, from `build_agent_prompt`), then `per_user_tail` (mandate one-liner, journal, unlocked agents, unlock paths, closing instructions). Prompt **content** unchanged — only order. |
| `f297196` | `backend/app/services/llm_gateway.py`, `backend/app/main.py`, `backend/tests/unit/test_llm_gateway.py` | Second guard: `VLLMProvider.log_prefix_cache_status()` reads `/metrics`, logs the measured hit rate, warns loudly if `enable_prefix_caching` is off. Wired into `main.py`'s `lifespan` (best-effort, matches the existing 4-task startup pattern). |

**Correction vs the CR077 doc:** the doc's Phase 0 description lists the unlock-path list as part
of the static head. Verified against `lessons_service.unlock_requirements()`
(`backend/app/services/lessons_service.py:723-775`) — it queries `LessonProgressRow` and
`AgentActivationRow` filtered by `user_id`, so it is per-user, not global. Left in the per-user
tail. Getting this wrong would have cost the entire 14,672-token cache hit silently — exactly the
failure mode the assign file warned about.

## Tests (self-verified — no independent auditor per GATE: spawned)

1. **Byte-identical head**, proven red first: `test_catalogue_head_byte_identical_across_wildly_different_users`
   (`test_concierge_context_router.py`) builds the prompt for two mandates differing in every field
   (plan, risk, compliance, goal/horizon/path, distinct `user_id`, distinct journal, distinct
   unlocked-agent set) and asserts the first `2 × 2096 × 4 = 16,768` characters are byte-identical.
   Ran against the pre-fix ordering first — **failed** (diverged at char 2813, inside the mandate
   overlay) — confirming the test catches the regression it exists to prevent. Green after the fix.
2. **Closing instructions still last:** `test_closing_instructions_follow_catalogue` asserts
   `system_prompt.index("Available lessons...") < system_prompt.index("name ONLY the lessons")` —
   order, not presence.
3. **Existing concierge tests unedited and green** — prompt content is unchanged, so no existing
   assertion about *what* the prompt says needed touching.
4. **Second-guard unit tests** (`test_llm_gateway.py`): hit-rate logged when enabled, loud warn when
   `enable_prefix_caching="False"`, warn-not-raise when `/metrics` is unreachable, gateway no-op when
   no vLLM provider is registered.

**Self-test commands + observed output:**
```
cd backend && .venv/bin/python -m pytest tests/unit/ -q -k "concierge or prompt"
  → 93 passed

cd backend && .venv/bin/python -m pytest tests/unit/ -q
  → 1276 passed, 4 warnings (pre-existing HTTP_422 deprecations, not introduced here), 149.66s
```

## Live measurement — §Verification 0 (required)

Measured 2026-07-27 against the live host `192.168.20.74:8000` (LAN-direct from the Mac), using the
**real** `build_concierge_messages()` output for two distinct mandates (differing in every field
above), `max_tokens=1` to isolate prefill, hit/query counters read as the `/metrics` delta across
each request (not the `usage.cached_tokens` field, per the assign file's caution — same
unreliability confirmed again here).

| order | request | prompt tokens | prefix-cache hit-token delta | latency |
|---|---:|---:|---:|---:|
| OLD (catalogue last) | user A (cold) | 15,634 | 0 | 2,583 ms |
| OLD (catalogue last) | user B (2nd user, 1st msg) | 15,632 | **0** | 2,492 ms |
| NEW (shipped, catalogue first) | user A (warms cache) | 15,791 | 0 | 2,516 ms |
| NEW (shipped, catalogue first) | user B (2nd user, 1st msg) | 15,789 | **14,672** | **310 ms** |

Target from the assign file was **≥ 14,672 cached tokens and < 500 ms** on a second user's first
message — hit exactly on both counts (14,672 is the same figure CR077's own measurement landed on).
Old ordering confirms the bug: 0 hit tokens both times, ~2.5 s regardless of request order.

Caveat: `192.168.20.74:8000` is the live shared serving host, not an isolated benchmark rig, so the
delta window can in principle catch concurrent traffic from other requests; no such contamination
was evident here (both OLD-order deltas landed at exactly 0, both prompt-token counts were stable
across repeat requests).

## Second guard — startup logging

`log_prefix_cache_status()` confirmed against the live host's actual `/metrics` shape during the
measurement above: `vllm:cache_config_info{...,enable_prefix_caching="True",block_size="2096",...}`
and `vllm:prefix_cache_hits_total{engine="0",model_name="ami-llm"}` /
`vllm:prefix_cache_queries_total{...}` are the exact metric names the parser targets (verified via a
live `curl .../metrics | grep prefix_cache` before writing the parser, not assumed).

## Out of scope, not touched

`room_prompts.py`, `room_runner.py`, `agent_prompts.py` — untouched (grep-clean). No schema change,
no `docs/forward_planning/CR077_*` content change (Architect's doc, not this lane's to edit).

## Uncertain / not verified

- The `/metrics` delta window's susceptibility to concurrent live traffic (see caveat above) — not
  fully ruled out, only observed clean this run.

**STATUS: READY_FOR_AUDIT (round 1)**
**SUBMITTED: round 1**
