<!-- coder.room → audit hand-off bridge — CR077-ROOM. Shared coordination state. -->
# CR077-ROOM — audit bridge (coder.room → audit)

SUBMITTED: round 1

**Item:** CR077 Phase 2 — parallelise the ANALYSTS phase of the Room only.
**Lane branch:** `lane/CR077-ROOM.coder.room`
**SHA:** `aec620c` — the **rebased** tip (build `8af991a` merged onto `main` carrying the
CR026 sector-cap integration). Audit THIS sha, not `8af991a`: the build predated CR026's
integration and CR026's own FLAG 1 called this contention out in advance ("any later
coder.room lane touching room_runner/room_prompts must rebase onto these").
**DEPENDS-ON:** none
**GATE:** independent (D-5 — ships to two app stores, changes user-facing Room behaviour)

---

## What changed & why

Ran the four ANALYSTS (`fundamentals`, `market`, `news`, `social`) **concurrently**
instead of strictly sequentially. Every other phase is untouched — they are genuine
debates and stay serial. The analysts are four independent lenses on one shared data
block, not a dependency chain (settled on measured evidence, CR §"Evidence added
2026-07-23"), so removing their serialization is pure latency win.

Two files, coder.room-owned only. Did NOT touch `safety_floor.py`, `agent_prompts.py`,
or any coder.api surface.

1. **`backend/app/services/room_runner.py`**
   - `_Phase` gains `parallel: bool = False`. ANALYSTS marked `parallel=True`; every
     other phase left default. **Single source of truth** — the loop keys on this flag,
     never on the label string (§Build 1).
   - Main phase loop: a `phase.parallel` branch that (a) snapshots the transcript as of
     phase START, (b) `asyncio.gather`s the four `_compute_agent_text` coroutines against
     the gateway, (c) streams + commits them in the fixed PHASES order
     (`fundamentals → market → news → social`) regardless of completion order (§Build 2/3/4).
   - `_speak_one_agent` split into `_compute_agent_text` (the awaitable a parallel phase
     gathers — builds the prompt from a caller-supplied transcript snapshot, does the LLM
     call/scripted fallback + DEF095 geometry annotation, returns `(text, geom_sig)`) and
     `_stream_agent_text` (typewriter → transcript append → checkpoint → `agent_done`).
     `_speak_one_agent` is now a thin sequential wrapper over the two — **behaviour of every
     sequential phase is byte-for-byte unchanged** (it passes the live `run.transcript` and
     `parallel_phase=False`).
   - Second guard: `parse_prefix_cache_metrics()` (pure) + `log_prefix_cache_status()` —
     probes the vLLM host `/metrics` once at `get_room_runner()` wiring, logs an **ERROR** if
     `enable_prefix_caching` is off, else an info line with the measured hit rate. No-ops when
     no vLLM host is configured (unit tests / mock). Reads the host; never touches it.

2. **`backend/app/services/room_prompts.py`**
   - `build_room_messages` gains `parallel_phase: bool = False`, threaded from the runner
     (NOT re-derived from the agent id — keeps `_Phase.parallel` the single source of truth).
   - §Build 5: for a concurrent analyst the transcript is empty, so the *"Build on the
     transcript — do not repeat what's already been said"* line is a lie. When
     `parallel_phase=True` it is **rescoped** to a "speaking at the same time / stay strictly
     in your own domain" instruction that sharpens the own-domain lens. Sequential phases keep
     the original line verbatim (it is load-bearing there).

## Tests + observed output

New: `backend/tests/unit/test_cr077_phase_parallelism.py` (10 tests).

- **Phase-parallelism guard (the spine, DEF084 shape).** `test_parallel_phases_are_exactly_the_independent_phases`
  asserts `{p.label for p in PHASES if p.parallel} == {"ANALYSTS"}`;
  `test_debate_phases_are_never_parallel` names RESEARCHERS/SYNTHESIS/EXECUTION/RISK/VERDICT
  and asserts each is sequential. `_PHASES_WITH_INDEPENDENT_AGENTS` is written out
  independently of the flag so the guard is a real cross-check, not a tautology.
- **Proven-red (required by the assign).** `test_guard_is_not_vacuous_...` mutates a copy of
  PHASES with RISK parallel and asserts the invariant breaks. Also demonstrated on the REAL
  PHASES from the CLI: marking RISK `parallel=True` → both guard tests FAIL
  (`AssertionError: RISK must stay sequential`); reverted → green.
- **Verified against REAL convene output (GATE requirement, not a unit assertion alone).**
  `test_analysts_run_concurrently_but_emit_in_fixed_order` drives the full `RoomRunner.run()`
  with a probe gateway whose per-agent sleeps make **social finish FIRST, fundamentals last**.
  Asserts: `max_in_flight == 4` (all four genuinely concurrent — a serial loop tops out at 1);
  completion order is social→…→fundamentals (reverse of emit); yet `agent_done` **and** token
  ownership order stay `fundamentals→market→news→social`.
  `test_analysts_are_blind_to_each_other_but_downstream_sees_them_all` asserts no analyst's
  captured system prompt contains another analyst's text, but the Bull Researcher's prompt
  contains all four.
- **Prompt rescope:** `test_parallel_phase_rescopes_the_build_on_transcript_line`.
- **Prefix-cache guard:** on/off/absent parse cases + `log_prefix_cache_status` no-ops without a host.

Commands + results (main venv, run from the worktree backend):
- `pytest tests/unit/test_cr077_phase_parallelism.py -q` → **10 passed**.
- `pytest tests/unit/ -q -k room` → **156 passed**.
- `pytest tests/unit/ -q` (full) → **1280 passed** (4 pre-existing HTTP_422 deprecation warnings, unrelated).

## Live-host verification (§Verification — evidence, ship decision already made)

Measured directly against the live vLLM host `192.168.20.74:8000` from the Mac (on-LAN),
using the **real** analyst system prompts from `build_room_messages`, salted to defeat the
prefix cache, `min_tokens=250` so token counts are identical between arms.

- **Wall-clock, 5 tickers, 4 analyst-sized calls (250 tok each), no estimates:**

  | | seq | conc | speedup |
  |---|---:|---:|---:|
  | avg ANALYSTS-phase wall clock | 24.96 s | 8.00 s | **3.12×** |

  Saves **~17 s per convene** on the analysts phase. Confirms the convene sees the concurrency
  curve the Architect measured (their 200-tok test: 4→2.77×; this production-sized 250-tok test: 3.12×).
  A full-convene number would need a promote — per the assign I hand off the per-call measurement
  rather than infer a convene figure.
- **Repetition (real generations, 5 tickers, distinct data-figures repeated across the 4 analyst turns):**

  | | ≥3 of 4 | ≥2 of 4 |
  |---|---:|---:|
  | sequential (today) | 18 | 38 |
  | concurrent (this lane) | **5** | **32** |

  Concurrent output is **less** redundant, not worse (72% fewer figures repeated in ≥3 of 4
  turns), so no escalation — the rescoped own-domain-lens line does its job.
- **Prefix caching confirmed ON** on the live host (`enable_prefix_caching="True"`), validating
  the second guard's assumption.

## Revert-proof QA / could-not-verify

- Sequential phases unchanged: `_speak_one_agent` delegates to the same two helpers with the live
  transcript and `parallel_phase=False`; the 156 room tests (incl. the full-transcript /
  safety-floor / DEF056/58/59/67/95 suites) pass unchanged.
- **Could not get a full-convene wall-clock without a promote** (Mac is a pure editor, no backend/DB).
  Handed off the per-call measurement above instead, per the assign's explicit allowance.
- Prefix-cache probe is best-effort (5 s timeout, swallows all errors into one warning) and only
  fires via `get_room_runner()` in-process, so it never runs in unit tests (they construct
  `RoomRunner()` directly with `vllm_base_url=""`).

## Files
- `backend/app/services/room_runner.py`
- `backend/app/services/room_prompts.py`
- `backend/tests/unit/test_cr077_phase_parallelism.py`


## Architect rebase note (AT:R65, 2026-07-27) — verify, do not take on faith

The coder built `8af991a` on a pre-CR026 base. CR026-BE integrated to `main` at `dbfc127`
while this lane was building, touching the same two files additively. Per the CR075
precedent the Architect performed the rebase; per that same precedent, **confirm it
independently** (`git merge-base --is-ancestor dbfc127 aec620c` should be true).

3 conflict hunks, all additive-vs-additive, resolved keep-both:

1. `build_room_messages` signature — `parallel_phase` (CR077) + `sector_weights` (CR026).
2. `room_prompts` body — CR077's parallel-analyst `collaboration_line` rescope + CR026's
   PM-gated `sector_line` block. The consuming `room_addition` f-string already referenced
   both (`:303` sector_line, `:312` collaboration_line), so only the producing blocks
   conflicted.
3. `room_runner` PM call site — `parallel_phase=` (CR077) + `sector_weights=ctx.sector_weights`
   (CR026).

**Both features verified to survive, not assumed:** CR026's 4 structural call-site tests and
CR077-ROOM's 10 parallelism/guard tests pass together (34 passed); full suite **1304**
(= 1294 on `main` + 10 new). Worth adversarial attention anyway — a keep-both resolution is
exactly where one feature can be silently half-dropped, and the sector wiring's failure
direction is OPEN (block 6b no-ops without context), so re-run CR026's 4 mutation drops on
this rebased tip rather than trusting the green suite alone.

**Not re-measured after the rebase:** the coder's live 3.12x speedup figure was taken on
`8af991a`. The rebase touched the PM call site and the prompt builder, not the analyst
gather path, so it should hold — but it is unverified post-rebase and should not be quoted
as measured on this SHA.
