<!--
CR077-CONCIERGE.auditor.md — AUDITOR verdict lane. Owner: AUDITOR (track U).
Spawned per GATE: spawned; this IS the required independent audit (PROTOCOL.md 4a),
NOT self-verification. Audited SHA f297196 in isolated worktree
.claude/worktrees/audit-CR077-CONCIERGE/.
-->

# CR077-CONCIERGE — auditor verdict

**Audited SHA:** `f297196` on `lane/CR077-CONCIERGE.coder.api` (base reorder `d99502f` + guard `f297196`).
**Chunk** (not CR-level) — chunk evidence list verified, no full DoD table required (PROTOCOL.md 4).
**GATE: spawned** — I am the Architect-spawned auditor; the lane is NOT self-verified.

## Method (independent, not on the coder's word)

Fresh detached worktree at `f297196`; suite via the absolute venv interpreter
(`/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python -m pytest tests/unit/`).
Live vLLM host `192.168.20.74:8000` hit LAN-direct with the **real** `build_concierge_messages()`
output. Pre-fix ordering reconstructed in a second throwaway worktree at `d99502f~1` for mutation tests.

## Findings

### F1 — Byte-identical-head test genuinely fails RED against pre-fix ordering — CONFIRMED
Copied the shipped `test_concierge_context_router.py` onto the pre-fix source (`d99502f~1`,
`system_prompt = base + floor_addition`) and ran it:
`test_catalogue_head_byte_identical_across_wildly_different_users` **FAILED**, diverging at
**char 2813** inside the mandate overlay (`display name: Someone Else` vs `Test User`) — exactly the
architect's claim. Green at `f297196`. The load-bearing deliverable is a real regression guard.
(`test_closing_instructions_follow_catalogue` passes in BOTH orderings — an invariant, not the
guard; correctly described by the coder as "order, not presence".)

### F2 — Live prefix-cache measurement reproduced INDEPENDENTLY — CONFIRMED
Sequential prefill-only requests (`max_tokens=1`), `/metrics` hit/query delta read tightly around
each; contamination guard = `query_delta` must ≈ this request's `prompt_tokens`.

| ordering | 2nd user, 1st msg — hit tokens | latency | prompt tokens | query_delta |
|---|---:|---:|---:|---:|
| OLD (catalogue last) | **0** | 2,684 ms | 15,768 | 15,768 |
| NEW (shipped, catalogue first) | **14,672** | 318 ms | 15,793 | 15,793 |

Target ≥14,672 cached / <500 ms → **met exactly** (14,672 = 7×2096, whole-block). `query_delta ==
prompt_tokens` on every request → **zero concurrent-traffic contamination**; the caveat the hand-off
flagged did NOT undermine the claim. Users A and B differ in every mandate field (plan/risk/
compliance/goal/horizon/path/user_id/journal) yet both land 14,672 → cross-user shared-catalogue
reuse proven, not same-fixture coincidence. `usage.cached_tokens` field read `None` (unreliable, as
warned — /metrics delta is authoritative).

### F3 — `unlock_requirements()` is per-user, correctly in the tail — CONFIRMED
`lessons_service.py:723-775` queries `LessonProgressRow.user_id == user_id` (passed lessons) and
`AgentActivationRow.user_id == user_id` (unlocked agents); both vary per user. The architect's
correction to the CR077 doc (leaving it in the per-user tail, not the static head) is correct.
Hoisting it would have silently zeroed the 14,672-token hit.

### F4 — Prompt content unchanged except reordering + one static divider — CONFIRMED (MINOR)
Built OLD vs NEW assembled prompt for an identical mandate; sorted-line diff shows the ONLY content
delta is a new static section divider at the head:
`─── FLOOR CONCIERGE — LESSON CATALOGUE (static; identical for every user) ───` (+ blank line).
Everything else is byte-identical, only reordered. The hand-off's "only order changed" is therefore
very slightly imprecise, but this is a **MINOR** observation, not a bounce: the divider is a static,
self-describing label in the cached head (does not break the prefix), changes no instruction / lesson
datum / routing rule / safety-floor text, is analogous to the pre-existing `─── FLOOR CONCIERGE
CONTEXT ───` divider, and broke **zero** existing content-assertion tests (all 1276 pass unedited).

### F5 — Auditor adversarial pin (3-user + leak-free head) — CONFIRMED
Wrote an independent pin (`orchestration/audit/regression/test_cr077_static_head_pin.py`): head
byte-identical across THREE mandates differing in every field, PLUS asserts NO per-user token
(display names, tickers, timezones, "halal", "Mandate snapshot") appears anywhere in the first
2-block window. **PASS at f297196, RED at pre-fix.** Stronger than the shipped test's same-value
fixture — catches a future personalised-head line by absence, not just by pairwise divergence.

### F6 — Second guard (startup prefix-cache logging) — CONFIRMED
`VLLMProvider.log_prefix_cache_status()` reads `/metrics`, logs hit rate, warns loudly on
`enable_prefix_caching` off; `_sum_prometheus_metric` sums labelled samples and parses scientific
notation (verified live: `2.35090447e+08` parsed cleanly). Wired best-effort into `main.py` lifespan
(try/except, matches the existing 4-task pattern), no request-path dependency. Gateway
`check_prefix_cache_at_startup()` no-ops without a vLLM provider. Substring match
`enable_prefix_caching="True"` verified present in the live host's actual `cache_config_info`. Unit
tests cover enabled / disabled / unreachable / no-vLLM.

**Stateful-lifecycle check (PROTOCOL.md):** the reorder is a pure function; the startup guard is a
fire-once best-effort boot log, not a cache/singleton/pool/background task persisting across calls.
No new stateful construct requiring full-lifecycle verification. The vLLM prefix cache itself is the
serving host's, exercised live above (warm across two distinct users). No concern.

## Suite (independent re-run)

- Full `tests/unit/ -q` at `f297196`: **1276 passed, 4 warnings, 148.79s** — matches coder + Architect.
- `test_concierge_context_router.py` + `test_llm_gateway.py` at `f297196`: **30 passed**.
- 4 warnings are pre-existing `HTTP_422_UNPROCESSABLE_ENTITY` deprecations, not introduced here.

## Scope

Diff `d99502f~1..f297196` = **5 files** (`main.py`, `concierge_prompts.py`, `llm_gateway.py`, 2 test
files). `agent_prompts.py`, `room_prompts.py`, `room_runner.py` untouched → GATE: spawned valid, not void.

## OUT-OF-SCOPE
None.

## Severity roll-up
BLOCKER: 0 · MAJOR: 0 · MINOR: 1 (F4 — hand-off wording, non-blocking).

**VERDICT: COMPLETE (round 1)**
Run report: `orchestration/audit/runs/2026-07-27_run-56/run_report.md`.
