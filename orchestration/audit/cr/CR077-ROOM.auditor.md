<!--
CR077-ROOM.auditor.md — auditor lane file (track U owns). State derives from
round numbers here vs CR077-ROOM.architect.md (see PROTOCOL.md).
-->

# CR077-ROOM — audit lane (auditor)

**Item:** CR077 Phase 2 — parallelise the ANALYSTS phase of the Room. The four analysts
(fundamentals/market/news/social) are independent lenses on one shared data block, not a
dependency chain, so running them concurrently via `asyncio.gather` removes serialization
latency (measured ~3.1× on the analyst phase) with no change to any other phase — every
debate (RESEARCHERS/SYNTHESIS/EXECUTION/RISK/VERDICT) stays strictly sequential.

**Gate:** independent (D-5 — ships to two app stores, changes user-facing Room behaviour).

**Audited SHA:** `aec620c`, a merge commit on `lane/CR077-ROOM.coder.room` — the coder's
build `8af991a` rebased onto `main` to carry CR026's sector-cap integration (`dbfc127`),
since both features touch `room_runner.py`/`room_prompts.py`. Audited in an isolated
worktree `.claude/worktrees/audit-CR077-ROOM/`, own venv.

## Round 1

### Reproduced independently

| Check | Result |
|---|---|
| Rebase ancestry | `git merge-base --is-ancestor dbfc127 aec620c` → true, confirmed myself, not taken on the Architect's word. |
| Scope | `git diff 860e250 aec620c` isolated to CR077's own 3 files (the CR026-integrated main baseline vs the rebase tip) — +617/−39 exact. |
| Full suite | `.venv/bin/pytest tests/unit/ -q` — **1304 passed**, matching the Architect's claim exactly (151–173s across two runs). |
| Merge conflict resolution | Read `room_prompts.py` (537 lines) and the relevant `room_runner.py` sections in full — all 3 disclosed conflict hunks resolved keep-both correctly: `build_room_messages` carries both `parallel_phase` and `sector_weights`; both `collaboration_line` and `sector_line` are produced and consumed in the same f-string; both the scripted `_assemble_verdict` and live-PM `enforce_safety_floor` call sites carry both features' wiring. Nothing silently half-dropped. |
| Sequential-phase preservation | `_speak_one_agent` (the sequential wrapper) passes the LIVE `run.transcript` and `parallel_phase=False` to `_compute_agent_text` — architecturally identical to pre-refactor behavior for every non-ANALYSTS phase. |
| Fixed emit order | `asyncio.gather(*[... for agent_id in phase.agents])` returns results in the SAME order the awaitables were passed (a language guarantee, not extra code) — `zip(phase.agents, results)` is therefore always in `fundamentals→market→news→social` order regardless of completion order. Verified by reading, not just trusting the test's assertion. |

### Re-verified CR026's sector-cap wiring survives the rebase — Architect's own request, not skipped

The Architect explicitly flagged this: a keep-both merge is exactly where a feature can be
silently half-dropped, and the sector cap's failure direction is OPEN (block 6b no-ops
without context), so re-running CR026's 4 mutation drops on this rebased tip rather than
trusting the green suite alone was the right ask. Mutation-tested the two call sites that
live inside CR077's heavily-restructured files (the other two, in `sim_engine.py`, are
untouched by this diff — already verified independently in CR026 round 3):

- Dropped `holdings=`/`quotes=`/`sector_map=` from `_assemble_verdict` → exactly
  `test_assemble_verdict_scripted_path_rejects_a_sector_breaching_buy` failed.
- Dropped the same 3 kwargs from the live-PM `enforce_safety_floor` call → exactly
  `test_room_runner_live_pm_enforce_safety_floor_rejects_sector_breach` failed (log:
  `action=APPROVE` sailing through) — same clean demonstration as round 3.

Both reverted, suite re-confirmed clean before the next probe.

### Mutation-tested CR077's own two headline claims

1. **The DEF084-shape guard, against the REAL `PHASES` tuple** (not just the test file's
   own internal proof, which only mutates a local copy and never touches production data).
   Marked `RISK` `parallel=True` in the actual `PHASES` definition →
   `test_parallel_phases_are_exactly_the_independent_phases` and
   `test_debate_phases_are_never_parallel` both failed immediately.
2. **The concurrency claim itself.** Forced `if phase.parallel:` to never trigger (`if
   False:`), so ANALYSTS would silently fall back to sequential despite being marked
   parallel. Both `test_analysts_run_concurrently_but_emit_in_fixed_order` (the
   `max_in_flight == 4` assertion) and, as a bonus,
   `test_analysts_are_blind_to_each_other_but_downstream_sees_them_all` failed — the
   sequential fallback genuinely leaks each analyst's reply into the next one's prompt,
   proving the isolation test is sensitive to real behavior, not just a flag check.

All reverted; final full suite re-confirmed **1304/1304 clean**.

### Read directly, not mutation-tested (proportionate)

- Prompt rescope (`§Build 5`): `room_prompts.py`'s `parallel_phase` branch read directly —
  matches `test_parallel_phase_rescopes_the_build_on_transcript_line`'s claims exactly.
- Prefix-cache guard: `parse_prefix_cache_metrics`/`log_prefix_cache_status` read in full —
  confirmed-off emits `logger.error` (loud, CR040-consistent), unconfirmed emits a warning,
  any probe failure swallowed into one warning (never fatal), no-ops without a configured
  vLLM host. Matches the on/off/absent/no-host test coverage.

### Not independently re-verified (disclosed, not fabricated)

The coder's live 3.12× ANALYSTS-phase speedup was measured on `8af991a`, pre-rebase, and the
hand-off itself already flags it as unverified on `aec620c` (the rebase didn't touch the
analyst gather path, so it should hold, but is unproven on this SHA). This is a performance
claim, not a correctness/safety one — did not attempt a live LAN re-measurement myself. Noting
the same gap rather than independently closing it or accepting it as proven either way.

### Findings

None.

### Verdict

**VERDICT: COMPLETE (round 1)** — scope and full suite reproduced exactly, the 3-way merge
conflict resolution verified by reading both files in full (not assumed from the disclosure),
CR026's sector-cap wiring re-confirmed intact on this specific rebased tip via fresh mutation
testing (not trusted from a prior SHA's audit), and both of CR077's own headline claims
(the DEF084-shape guard and the actual concurrency) mutation-tested against production code,
not just the test file's self-contained proofs.

Run report: [`../runs/2026-07-27_run-57/run_report.md`](../runs/2026-07-27_run-57/run_report.md)
