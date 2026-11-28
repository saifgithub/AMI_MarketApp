# CR289 — Bursa full universe, two desk-model arms (Ling, ami-llm), risk 4

**Filed:** 2026-11-28 (AT:B1). **Source:** Saiful, 2026-11-28: "we can actually run all of the bursa tickers ... lets start with LING ... can we run two at a time, and not get confused? lets set risk level 4." Hold lifted the same day: "bismillah, go ahead". **Rescoped 2026-11-28:** no production change; the DSV4 arm was dropped and ami-llm is the second arm.

## What
Run all 1,072 Bursa tickers (`CR282_bursa_malaysia/bursa_batch/universe_2026-11-25.csv`) through the Room at mandate risk 4, once per desk model, as two separate batches that cannot be confused:

| Arm | Desk model (all 12 analysts and the CIO) | Batch id | Concurrency / stagger |
| --- | --- | --- | --- |
| LING | `ling-3.0-flash-fin-fp4` at `100.98.142.64:8004` | `cr289-ling-bursa-r4` | 8 / 8 s |
| AMI-LLM | `ami-llm` (`qwen38-flash-next-abliterated-nvfp4`) at `192.168.20.74:8000` | `cr289-amillm-bursa-r4` | 4 / 16 s |

Ami-llm stays at 4 on purpose: Saiful, 2026-11-28, "do not increase for ami-llm. we need to have some capacity for other services".

## How (no production code touched)
The existing V2 harness (`docs/tools/room_investigation_V2/tools/room_batch.py`) runs on melehost with `docker compose run --rm --no-deps --entrypoint python` against Alpha's Postgres and production flags, one directory and one batch id per arm (`~/cr289_<arm>_bursa/`). Each batch resumes from `runs_<batch>.jsonl` (rows with `status == "completed"` are skipped), so a restart or a rerun of failures reuses the same command. Adanos keys are blanked in both arms.

Harness changes (V2 tool only, not on Alpha's request path): `--start-stagger` releases the first wave of Rooms N seconds apart (e914b099); a `cheapllm` provider entry (06eea0d3).

## Findings
1. **Adanos has no Bursa coverage.** Every `.KL` ticker returns HTTP 422, and a 422 spends budget (the secondary key fell 164 to 98 before the keys were blanked in the batches). The Social analyst runs on the CR037 synthetic-sentiment fallback in both arms: **Social is synthetic for Bursa; read it that way in the results.** Production fix: DEF556 (deploy #45, alpha-2026-11-28-3).
2. **Throughput.** Ling at 4 / 6 / 8 concurrency: about 40 / 42 / 48 Rooms/h (median Room 350 / 433 / 570 s), so Ling saturates near 8. Ami-llm at 4: about 34-38 Rooms/h (median 325 s), no queueing.
3. **Model identity checked.** `llm_audit` rows for each arm carry only that arm's `provider / model`.
4. **CheapLLM DSV4 arm dropped.** CheapLLM allows one request per account at a time (HTTP 429 "one request at a time"); a Room fires parallel analyst calls, so a smoke Room failed within seconds. Serialising 1,072 Rooms is not feasible. Saiful, 2026-11-28: "skip it."

## Parked / abandoned
1. Per-Room `desk_provider` pin + `--risk-score` driver flag + CheapLLM on Alpha's allow-list: built on branch `cr289-desk-provider` (e62b8422). **Not to be merged.** Saiful rejected production changes for a test tool ("that would make this test dangerous"). Reverted from beta/cr267 by 7ad76439.
2. A separate `ami_ling` clone stack on melehost: built and torn down.

## Acceptance
1. Both batches finish with every ticker `completed` (rerun failures with the same `run.sh`).
2. Each arm's `llm_audit` rows show only its own `provider / model`.
3. Results summary (verdict mix, failures, timings) goes under this folder. **Room text and exports stay on melehost, never in git (the repo is public).**

## Constraints
Alpha stays on-prem only (ami-llm + Ling). Ami-llm load is capped at concurrency 4. Nothing here touches Alpha's code or live routing.
