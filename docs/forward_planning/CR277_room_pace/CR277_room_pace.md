# CR277 — Room typing pace

**What:** The Room's typewriter pacing (the delay between characters when a finished turn is replayed to the app) is now configurable and capped per turn and per Room. New defaults add roughly 35 s to a typical Room instead of roughly 112 s. Child of CR267 (follows WP-10).

**Why:** The WP-10 scorecard (CR240, `scorecard_2026-11-18.md` §3) found hosted-model time is only 0.8–1.5 min per Room, and the Room's own pacing (4–12 ms/char, estimated 1.7–2.0 min) is what pushed every model past the 2-minute Room target. Saiful ruled 2026-11-18: speed it up.

## Pacing sites found

Server (all typing pacing goes through one function):

1. `backend/app/services/room_runner.py` `_typewriter` (was line 9747): `await asyncio.sleep(random.uniform(delay_min, delay_max))` after each character. Every Room turn reaches it through `_stream_agent_text` (line 10197 before the edit), the two CIO paths in `_run_cio_step` (lines 5665, 5691), the live CIO restream (lines 6068/6082, `_restream_for_ui` is an alias of `_typewriter`, line 10849) and the CIO-retry route (passes the module defaults, line 9267).
2. `room_runner.py:6757-6758` `_CHAR_DELAY_MIN/MAX = 0.004 / 0.012`: hard-coded constants, and the default of `char_delay_min/max` on `start_run` (7881), `run` (8185) and the retry route (9267). Not settings.
3. `room_runner.py:6759` / `8659` `_PHASE_GAP_S = 0.25`, slept between phases (about 6 gaps, 1.5 s per Room). Left alone: a phase boundary, not typing.
4. `backend/app/services/llm_gateway.py:392` `MockProvider` streams at 5–20 ms/char. Mock provider only (no real LLM configured); not on the Alpha or Beta path. Left alone.

Not pacing (checked): `room_runner.py:7634` and `api/room.py:204` are retry backoff.

App (`mobile/lib`): none on the Room. `state/room_providers.dart` appends each `agent_token` event straight to the transcript (lines 336 and 563) with no timer or animation, so the server is the only delay and nothing stacks. `widgets/chat/streaming_text.dart` (50 chars/s) exists but nothing in `lib/` renders the Room with it. No mobile change.

## What changed

1. `_typewriter` draws each character's delay in the configured range, then clamps the turn's planned total to the per-turn cap and to what remains of the Room's budget (all delays scaled down proportionally, so a long turn is shown faster, never truncated). Every character is still sent, one event per character, in the same order.
2. Characters go out on a fixed schedule from the turn's start (sleep = scheduled time minus now), so event-loop oversleep on a 2 ms sleep no longer stretches the turn past its plan.
3. The Room budget is `_PACE_SPENT_S[run_id]`, released in the `finally` of `run()` and of the CIO-retry route.
4. Zero delays (tests, backtests) still call `sleep(0)` per character, so the event loop is yielded exactly as before.

No change to prompts, models, verdict, agents, or order.

## Settings (forwarded in the `docker-compose.yml` api-alpha block)

| Setting / env | Default | Was |
|---|---|---|
| `room_char_delay_min_ms` / `ROOM_CHAR_DELAY_MIN_MS` | 1.5 | 4 (constant) |
| `room_char_delay_max_ms` / `ROOM_CHAR_DELAY_MAX_MS` | 3.5 | 12 (constant) |
| `room_turn_pace_cap_s` / `ROOM_TURN_PACE_CAP_S` | 4.0 | none |
| `room_pace_cap_s` / `ROOM_PACE_CAP_S` | 40.0 | none |

Boot is refused if min > max. A cap of 0 means no pacing.

## Arithmetic

Typical transcript length: the scorecard estimated 1.7–2.0 min of pacing at 8 ms/char, so 102–120 s / 0.008 = 12,750–15,000 characters of agent turns per Room. Use 14,000 (the tests use 13 turns x 1,080 = 14,040). A real Room has roughly 10–13 turns; more turns means shorter turns and less cap clipping, so 13 is the conservative (higher-pacing) choice.

1. Before: 14,040 chars x 8 ms (mean of 4–12) = 112 s. Measured with the old code and a recording sleep: 112.7 s.
2. After: 14,040 chars x 2.5 ms (mean of 1.5–3.5) = 35 s. An average turn is 1,080 x 2.5 ms = 2.7 s, under the 4 s turn cap. A turn is clipped only above 1,600 chars (4 s / 2.5 ms), so the longest debate turns show slightly faster.
3. Worst case: bounded by the Room cap, 40 s, however long the transcript.
4. Saved: about 77 s (1.3 min) per Room. Scorecard medians of 3.05–3.68 min on hosted models become about 1.8–2.4 min. This is an estimate from the scorecard's own split, not a re-run.

Readability: 2.5 ms/char is about 400 chars/s, a full 1,080-char turn takes 2.7 s, and turns still appear one after another in order. Pacing was not removed.

## Acceptance

1. Pacing per turn never exceeds `room_turn_pace_cap_s`, even for a 200,000-char turn (test).
2. Pacing per Room never exceeds `room_pace_cap_s` across 40 long turns, and every character is still delivered (test).
3. 13 x 1,080 chars at defaults totals 25–40 s (test); old code totals 112.7 s.
4. Sleep overshoot does not stretch a turn (test); zero delay still yields (test); the budget is released when a Room finishes (test).
5. `test_config_compose_parity.py` passes (new env forwarded).
6. Full backend suite green.

Tests: `backend/tests/unit/test_cr277_room_pace.py`. Fails-before: all 10 fail on the pre-CR277 code (no settings, no caps, no injection points).

## Not done / open

1. No live timing of a Room on Alpha: nothing was run on a server. The 35 s figure is arithmetic on the scorecard's character estimate, not a measurement. Time the first Alpha Room after promotion.
2. Values can be tuned from the env without a code change (container recreate only).
