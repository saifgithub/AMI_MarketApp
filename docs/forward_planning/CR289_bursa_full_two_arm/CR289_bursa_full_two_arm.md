# CR289 — Bursa full universe, two desk-model arms (Ling, DSV4), risk 4

**Filed:** 2026-11-28 (AT:B1). **Source:** Saiful, 2026-11-28: "we can actually run all of the bursa tickers ... lets start with LING and the free DSV4 from cheapllm. can we run two at a time, and not get confused? lets set risk level 4." Hold lifted the same day: "bismillah, go ahead".

## What
Run all 1,072 Bursa tickers (`CR282_bursa_malaysia/bursa_batch/universe_2026-11-25.csv`) through the Room twice, at mandate risk 4: arm LING (desk model `ling-3.0-flash-fin-fp4`, the `vllm_fallback` slot) and arm DSV4 (CheapLLM `deepseek-v4.1-flash-1017`, the `deepseek` slot). Both arms run at the same time on Alpha through `backend/scripts/bursa_batch.py`.

## Why it needs code
Alpha picks the desk model globally from env. The 200-ticker batch (`bursa282-2026-11-25`) ran on ami-llm only because that is the default. Two models at once needs a per-Room pin that live users can never use.

## Scope
1. `desk_provider` on `POST /v1/room/stream`: honoured only for users with `app_version = "room-benchmark"`, only for `vllm_fallback` and `deepseek`, only when the slot is registered. Any other case is a loud 4xx, never a silent fall-back to the default model.
2. A pinned Room never fails over or retries on another model. A pinned-provider failure is a failed Room.
3. Bank key built from the pinned model's root, so an arm can never be handed the other arm's Room.
4. Driver: `--risk-score` (default 5), `--desk-provider`, both stamped on each record; a pin refusal stops the batch.
5. Alpha config: CheapLLM on the `deepseek` slot (`DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL`, `DEEPSEEK_API_KEY`), `deepseek` added to `LLM_PROVIDER_ALLOWLIST`. **New vendor on Alpha's path, approved by Saiful 2026-11-28 ("on alpha")**, reachable only through the benchmark pin.

## Acceptance
1. Unit tests: non-benchmark user 403; unknown or unregistered provider 422; pin routes every gateway call to the pinned provider; pinned failure does not reach ami-llm; unpinned requests unchanged; no live-traffic path can select `deepseek`.
2. Full backend suite exits 0 via `preflight_suite.sh`.
3. After deploy, every Room of each arm shows only its own provider in `room_llm_calls` (SQL check per arm, zero strays).
4. Results: `runs_<batch>.jsonl` per arm under `docs/forward_planning/CR289_bursa_full_two_arm/` (Room text stays out of the repo, public).

## Constraints
CheapLLM is testing-only and never a user path. Re-check it is still free before the run. Do not touch ami-llm or live users' routing.
