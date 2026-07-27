<!-- archived lane pair — CR077-ROOM. Closed DISPATCH: ACCEPTED round 1, AT:R65 2026-07-27. -->
# CR077-ROOM — archived lane (assign + coder.room)

## assign

<!-- dispatch assign lane — Architect-owned. CR052. -->
# CR077-ROOM — assign (Phase 2: parallelise the ANALYSTS phase only)

KIND: code
INSTANCE: coder.room
ACCEPTANCE: docs/forward_planning/CR077_llm_prefill_caching_and_room_latency/CR077_llm_prefill_caching_and_room_latency.md (§Scope "Phase 2", §"Evidence added 2026-07-23", §Guard, §Verification 1-3)
DEPENDS-ON: none
GATE: independent    <!-- D-5: ships to two app stores and changes user-facing Room behaviour (the debate's first phase). The guard is a DEF084-shape guard — a phase that looks like a debate and silently isn't. Verify against real convene output, not a unit assertion alone. -->
HOT-FILES: room_runner.py, room_prompts.py (coder.room-owned; no cross-instance contention). Do NOT touch safety_floor.py (coder.api) or agent_prompts.py's floor ordering.

**What:** Run the four ANALYSTS (`fundamentals`, `market`, `news`, `social`) **concurrently** instead
of strictly sequentially. Every other phase stays exactly as it is.

The sequential loop is [room_runner.py:1375-1393](../../../backend/app/services/room_runner.py#L1375-L1393)
— `for phase in PHASES` wrapping `for agent_id in phase.agents`, each `_speak_one_agent()` fully
awaited before the next.

## This is decided, not exploratory — read before you gate yourself on an A/B

The concern that four concurrent analysts would "go blind to each other and repeat" was raised by the
Architect and **settled on measured evidence**, then reaffirmed by Saiful. Do not re-litigate it or
hold the lane behind a go/no-go A/B. The facts (all in the CR's "Evidence added 2026-07-23" section):

- The analysts are four independent lenses on **one shared data block**, not a dependency chain.
  Proven: `news_analyst` quoted the Reddit sentiment score (`+0.09` INGN, `+0.03` MSFT) — *social's*
  domain — **while speaking before social**. It read it from the shared `profile`, not the transcript.
- Structural confirmation: [room_prompts.py:338](../../../backend/app/services/room_prompts.py#L338)
  renders `Retail sentiment: … (sentiment_score)` into the `profile` fact-sheet, and `_format_profile`
  is **agent-independent** — every analyst's prompt already carries all four domains' numbers.
- They **already repeat** today, sequentially: `-7% margin`, `-1.4% FCF`, `$7.08` each appear in 3 of
  4 INGN turns despite the "do not repeat" line. Concurrency does not introduce the redundancy; it is
  already there.

So `"build on the transcript — do not repeat"` is **already inert for the ANALYSTS phase**. It is
load-bearing for RESEARCHERS (bull/bear rebut), RISK (three debators), VERDICT (PM reads all 11) —
which is exactly why those stay sequential.

## Build

1. **`parallel: bool` on `_Phase`.** Mark the ANALYSTS phase `parallel=True`; every other phase
   `parallel=False`. Decision visible in one place — do **not** special-case the label string in the
   loop. This field is what the guard test keys on.
2. **`asyncio.gather` the parallel phase.** For a parallel phase, run all four `_speak_one_agent()`
   concurrently against the gateway. RESEARCHERS / RISK / VERDICT keep the sequential path untouched.
3. **Deterministic stream order (hard requirement).** The mobile client renders analysts in a fixed
   order. Whichever agent's LLM call finishes first, the emitted `RoomEvent` sequence for the phase
   must stay `fundamentals → market → news → social`. Gather concurrently, emit in fixed order —
   collect-then-emit-in-order is fine; interleaving tokens out of order is not. A test must assert
   the event order is independent of completion order (e.g. inject a gateway that returns social
   first).
4. **Transcript snapshot + commit (Saiful's hard condition).** Each concurrent analyst must see the
   transcript **as of phase start** — which for ANALYSTS (the first phase) is empty. After all four
   finish, commit all four contributions to the transcript so RESEARCHERS onward see them. Only the
   four analysts are blind to each other; nothing downstream loses input.
5. **Strip or rescope the transcript line for concurrent analysts.**
   [room_prompts.py:234-235](../../../backend/app/services/room_prompts.py#L234-L235) says *"Build on
   the transcript — do not repeat what's already been said."* For an agent in a `parallel` phase this
   is a lie (there is no transcript to build on). Remove it for those agents, or rescope it to
   sharpen each analyst's own-domain lens so it cuts the repetition that already exists. Sequential
   phases keep the line unchanged — it is load-bearing there. Do **not** change the line's wording for
   RESEARCHERS/RISK/VERDICT.

## Guard (mandatory — this is the deliverable's spine, §Guard)

A test that asserts **the phases marked `parallel=True` are exactly the phases whose agents do not
read each other's output.** Today that set is `{ANALYSTS}`. The failure mode: someone later marks
RISK parallel because it *looks* like three independent debators — that silently deletes the risk
debate while every test passes and the UI still renders three contributions. That is DEF084's exact
shape: a feature that looks present and isn't. The test must fail if RESEARCHERS, RISK, or VERDICT
is ever marked parallel.

Second guard, cheap, in scope: assert `enable_prefix_caching` is on and log the measured prefix-cache
hit rate at startup — nobody would currently notice if caching were off.

## Verification you attach to the hand-off (Phase 1, now evidence not gate)

- **Two transcripts, 5 tickers, side by side:** sequential vs concurrent analysts, with the
  repetition count stated **as a number** for each. Evidence, not a gate — the ship decision is made.
  Only escalate if concurrent output is *worse* than today's already-redundant sequential output.
- **Wall-clock, measured, no estimates.** The thing you changed is four LLM calls going from serial
  to concurrent. Measure it directly against the live host (`ssh ami-host` reaches `192.168.20.74`;
  or hit `http://192.168.20.74:8000` over the LAN): 4 sequential analyst-sized calls vs 4 concurrent.
  The Architect measured the raw concurrency curve at 1→33.0, 2→57.1, 4→91.1 tok/s aggregate — your
  job is to confirm the *convene* sees it. If you cannot get a full-convene number without a promote,
  say so and hand off the per-call measurement rather than inferring a convene figure.

## Out of scope

- Concierge Phase 0 (`CR077-CONCIERGE`, coder.api's lane) — not yours.
- Phase 3, the `gpu_memory_utilization` bump — ops on the LLM host, Saiful's call.
- Restructuring Room prompts for a shared cacheable prefix — the CR explicitly refuses it (it moves
  the persona behind the safety floor, `agent_prompts.py:64-65`). Do not touch `agent_prompts.py`.

## Tests

`cd backend && .venv/bin/python -m pytest tests/unit/ -q -k "room"` then the full `tests/unit/ -q`.
The phase-parallelism guard must be proven **red** before the fix (mark RISK parallel, watch it fail),
then green.

## Delivery

Push to `lane/CR077-ROOM.coder.room`, never `main`. Hand-off:
`orchestration/dispatch/lanes/CR077-ROOM.coder.room.md` (`STATUS: READY_FOR_AUDIT (round 1)`) +
`orchestration/audit/cr/CR077-ROOM.architect.md` (`SUBMITTED: round 1`). Chunk evidence list, not the
DoD. Commit tag `(AT:coder.room CR077)`.

**Commit both hand-off files to the SHARED branch, not your lane branch** (DEF090) — source goes to
the lane branch; the lane files are shared coordination state and every board reads them on the shared
branch. A hand-off committed only to a lane branch is invisible to both boards and has already
stranded a finished round; an uncommitted one renders `UNCOMMITTED` (DEF087).

DISPATCH: ACCEPTED (round 1)

ASSIGNED: coder.room round 1

## coder.room lane

<!-- coder.room lane file — CR077-ROOM. Shared coordination state (DEF090). -->
# CR077-ROOM — coder.room lane

STATUS: READY_FOR_AUDIT (round 1)

Phase 2: parallelise the ANALYSTS phase of the Room only.

- **Branch:** `lane/CR077-ROOM.coder.room` · **SHA:** `8af991a`
- **Audit bridge:** `orchestration/audit/cr/CR077-ROOM.architect.md` (`SUBMITTED: round 1`)
- **Tests:** 10 new (CR077 guard, proven-red) + 156 room + full unit **1280 passed**.
- **Live evidence attached in the bridge:** 3.12× / ~17 s saved per convene; concurrent
  output measurably *less* redundant than today's sequential; prefix caching confirmed ON.
- Files: `room_runner.py`, `room_prompts.py`, `test_cr077_phase_parallelism.py`.
