<!--
Auditor run report — run-56 (2026-07-27, track U). Round-1 audit of CR077-CONCIERGE.
Audited SHA f297196 on lane/CR077-CONCIERGE.coder.api. Verdict COMPLETE. Owner: AUDITOR.
-->

# run-56 (round 1) — CR077-CONCIERGE prefix-cache reorder → COMPLETE

- **Audited SHA:** `f297196`, tip of `lane/CR077-CONCIERGE.coder.api` (`d99502f` reorder +
  `f297196` startup guard). Isolated worktree `.claude/worktrees/audit-CR077-CONCIERGE/` (detached).
- **GATE: spawned** — I am the required Architect-spawned independent auditor. The hand-off's
  "self-verified below, no independent auditor required" is a misread of PROTOCOL.md 4a; this audit
  is the gate, reaching DONE only on VERDICT: COMPLETE. Lane NOT treated as self-verified.
- **The item (chunk):** reorder `build_concierge_messages()` so the 342-lesson catalogue is a
  byte-identical static head (whole-block vLLM prefix-cache hit) and everything mandate/user/journal-
  derived is a per-user tail; plus a boot-time prefix-cache-hit-rate log guard.

## Verification

### Reproduced independently
- Diff `d99502f~1..f297196`: **5 files, +312/−12** — `main.py` (+10), `concierge_prompts.py` (reorder),
  `llm_gateway.py` (+68 guard), `test_concierge_context_router.py` (+105), `test_llm_gateway.py` (+106).
- Full `tests/unit/ -q` @ f297196: **1276 passed, 4 warnings, 148.79s** (matches coder + Architect).
- `test_concierge_context_router.py` + `test_llm_gateway.py` @ f297196: **30 passed**.

### Mutation test — the load-bearing byte-identical head (F1)
Shipped `test_catalogue_head_byte_identical_across_wildly_different_users` copied onto the pre-fix
source (`d99502f~1`, `system_prompt = base + floor_addition`) → **FAILED**, diverging at **char 2813**
(`display name: Someone Else` vs `Test User`, inside the mandate overlay). Green at f297196. Confirms
the deliverable catches the exact regression it exists to prevent. Architect's "diverged at char 2813"
reproduced exactly.

### Live measurement — reproduced independently (F2)
Real `build_concierge_messages()` output for two mandates differing in every field, sent LAN-direct
to `192.168.20.74:8000` (`enable_prefix_caching="True"`, `block_size="2096"`, model `ami-llm`,
verified live). `max_tokens=1` prefill-only; `/metrics` `prefix_cache_{hits,queries}_total` delta read
tightly around each request; contamination guard = `query_delta ≈ prompt_tokens`.

| ordering | 2nd user, 1st msg — hit | latency | prompt tokens | query_delta |
|---|---:|---:|---:|---:|
| OLD (catalogue last) | **0** | 2,684 ms | 15,768 | 15,768 |
| NEW (shipped) | **14,672** | 318 ms | 15,793 | 15,793 |

`query_delta == prompt_tokens` on every request → **no concurrent-traffic contamination** in any
window; the flagged caveat did not undermine the claim. Target (≥14,672 / <500 ms) met exactly;
14,672 = 7×2096 (whole-block). Distinct users A≠B both hit 14,672 → cross-user shared-catalogue reuse.
`usage.cached_tokens` read `None` (unreliable, as warned).

### Independent code reads
- `unlock_requirements()` (`lessons_service.py:723-775`) per-user (filters both `LessonProgressRow`
  and `AgentActivationRow` by `user_id`) → correctly in the tail; the CR077-doc correction is right (F3).
- OLD-vs-NEW assembled-prompt sorted-line diff: only content delta is a new static catalogue divider
  in the head; all else identical, reordered (F4, MINOR). Ordering verified by char index:
  catalogue(247) → base → tail divider(57325) → closing(58330).
- Second guard reviewed (F6): `_sum_prometheus_metric` parses live scientific notation; best-effort
  lifespan wiring; no-op without vLLM. Not a stateful lifecycle construct (fire-once boot log).

### Auditor adversarial pin (F5)
`orchestration/audit/regression/test_cr077_static_head_pin.py` — 3 wildly-different mandates, head
byte-identical AND leak-free (no display name / ticker / timezone / "halal" / "Mandate snapshot" in
the first 2 blocks). **PASS @ f297196, RED @ pre-fix.**

## Verdict
BLOCKER 0 · MAJOR 0 · MINOR 1 (F4 hand-off wording). **COMPLETE (round 1).**

## Artifacts
- Verdict: `orchestration/audit/cr/CR077-CONCIERGE.auditor.md`
- Pin: `orchestration/audit/regression/test_cr077_static_head_pin.py`
- Ledger row appended to `orchestration/audit/audit-trail.md`.
