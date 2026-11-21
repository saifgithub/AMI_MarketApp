# CR267 WP-20 — Room baseline, on-prem model (IN PROGRESS)

**Status:** pilot done, full run in flight on melehost (started 2026-11-20 11:55Z). Sections marked
`TO FILL` take their numbers from the finished runs (`wp20_analyze.py`, `room_contract_gates.py`,
`evidence_card_report.py`; commands below). Format follows
`docs/forward_planning/CR251_risk_monotonicity_matrix/BASELINE.md`.

**Measured on the on-prem primary model, NOT on Beta's DeepSeek-V4-Flash.** Founder ruling 2026-11-20:
baseline now on Alpha's on-prem models, zero spend, no hosted vendor. WP-26 re-runs on Beta's model.

1. **Model measured:** `root` = `/models/qwen38-flash-next-abliterated-nvfp4`, read from
   `http://192.168.20.74:8000/v1/models` before and after each job (`out/<label>/model_root_{start,end}.txt`);
   served as `qwen3.8-flash-next-abliterated`, alias `ami-llm` (a refusal-stripped reasoning build). Never
   identified by the alias.
2. **Code:** Alpha deploy #10, `GIT_SHA=d739d8e85b9435cf508b93b3e0fec4dbe6e80b74`. WP-21a (CR275, merge
   `4c0a27db`) is an ancestor of it, and `street_view_blind` is present in the deployed `room_runner`: no desk
   or judge sees the Street rating, targets, split or tape. Each Room's stored verdict still carries
   `analyst_view` and `street_comparison` (post-verdict), which the consensus scoring reads.
3. **Settings (production, live Alpha values):** prompts `backend-default`; `ROOM_CARDS_ENVELOPE_ENABLED=false`
   (arm 1) / `true` (arm 2, evidence only); `ROOM_EVIDENCE_GATE_ENABLED=false`; veto and resurrection reviews
   ON; `LLM_DESK_TEMPERATURE` unset (server default); live market data (no frozen profiles, as CR251).
4. **On-prem only, one model per Room:** failover slot blanked (`VLLM_FALLBACK_*` empty), no hosted key passed,
   `LLM_PROVIDER_ALLOWLIST` untouched. Every verdict records `llm_backup_used` (expected false throughout).
5. **Cost per Room: $0.** On-prem inference, no metered spend.
6. **Pacing:** at most 2 Rooms in flight (earlier matrix runs used 8 on-prem and 4 on the DSV4 box; lower
   taken). vLLM idle between jobs (`num_requests_waiting` 0, KV cache 0-9% with 2 in flight).

## Pilot (2026-11-20, AAPL R3/R4/R5, 1 rep, concurrency 2)

| Arm | Room | Action | Minutes | Contract gates |
|---|---|---|---|---|
| cards OFF | AAPL R3 | PASS (3/5 votes, veto upheld) | 8.8 | OK |
| cards OFF | AAPL R4 | PASS (0/5, resurrection upheld) | 7.6 | OK |
| cards OFF | AAPL R5 | APPROVE (5/5) | 5.2 | OK |
| cards ON | AAPL R3 | PASS (2/5) | 7.8 | OK |
| cards ON | AAPL R4 | PASS (3/5) | 10.1 | OK |
| cards ON | AAPL R5 | PASS (5/5) | 7.2 | OK |

1. **Minutes per Room (wall, 2 in flight):** cards OFF mean 7.2 (5.2 to 8.8); cards ON mean 8.3. Cards-on is
   about 1.15x. Effective throughput about 3.6 min/Room at concurrency 2, so 300 rooms is about 18-19 h.
2. **Outputs carry what acceptance needs:** `verdict.action` for approvals; arm keys
   `<TICKER>-r<risk>-rep<i>` for flips across reps; `street_comparison.street_rating` for consensus scoring;
   `llm_backup_used`; per-arm `user_id` for the audit join. 6/6 pilot rooms completed, 6/6 gate-OK
   (`room_contract_gates.py`).
3. **Card completeness (cards-on pilot):** 3/3 rooms complete (all four evidence desks, all five items), 0
   duplicate cards, `sheet_state` on every room. ICC is null at n=3 (needs 3+ tickers with 2 reps).
4. Pilot synthetic users (exclude from tester counts): base users `wp20-pilot` `48e9fdab-682c-4f00-b0c1-5af16701fb3e`,
   `wp20-pilot-cards` `e59852e0-0083-4c5c-8e8b-bbe4b2c80f90`; arm users are uuid5(base, arm key) and listed
   in each runs file. None has a `users` row.

## Full run

1. Jobs, one at a time via `wp20_driver.sh`: `arm1` (300 rooms, cards OFF), `side` (50 rooms, cards OFF),
   `arm2` (300 rooms, cards ON; started only if arm 1's wall time scaled by 1.15 predicts at most 24 h).
2. Raw runs (JSONL, per-arm user ids, model root files, logs): **melehost `~/cr267_wp20/out/{arm1,side,arm2,pilot,pilot-cards}/`**
   and `~/cr267_wp20/logs/`. Outside `~/ami_trade` (so no rsync `--delete` reaches it). Every turn of every
   room is also in Alpha's `llm_audit`, keyed by the arm user ids. WP-22 reuses these.
3. Benchmarks: `docs/tools/room_investigation_V2/benchmarks/wp20/*.yaml`. Harness: `tools/wp20_run.sh`
   (one job), `tools/wp20_driver.sh` (sequence), `tools/wp20_analyze.py` (tables).

## Side set (spec step 3)

1. None of the 30 tickers is a Street Sell or Underperform name today (Yahoo 2026-10-08 refresh: 16 buy, 14
   hold; lowest consensus WU 3.39, XRX 3.25, CAG 3.24, BGS 3.20, all hold).
2. Side set, the five lowest-consensus names in `tickers_150.txt` outside the 30, re-ranked on current
   Yahoo `recommendationMean` today: CAR 3.38, ITW 3.31, KSS 3.31, CPB 3.30, JBLU 3.29 (all Hold; no Street
   Sell exists in the 150 either: CR035's two Sell names, WU and BGS, are now Hold and already in the 30).
   Run as `wp20-side`, 5 risk levels x 2 reps = 50 rooms.

## Results — TO FILL when the jobs finish

1. Approvals per risk level, arm 1 (n per cell = 2 reps x 30 tickers per level = 60). All 300 Rooms completed, none errored (arm 1 ended 2026-11-21 08:45Z):

   | Risk | n | APPROVE | rate | PASS | other |
   |---|---|---|---|---|---|
   | R1 | 60 | 3 | 5% | 57 | 0 |
   | R2 | 60 | 3 | 5% | 57 | 0 |
   | R3 | 60 | 10 | 17% | 50 | 0 |
   | R4 | 60 | 13 | 22% | 47 | 0 |
   | R5 | 60 | 20 | 33% | 36 | 4 |

   Approvals rise with risk level in aggregate. Per ticker they are not monotone: e.g. MA approves at R1 and R3 but not R2/R4/R5, WFC at R2/R3/R4 but not R5. The per-ticker table is in `wp20_analyze.py`'s output.
2. Flip count across reps: **35 of 150** comparable cells (23%) disagree between rep 1 and rep 2. CR251 reference (a different stack): 29/150.
3. Minutes per Room (wall clock, 2 in flight): n=300, mean 8.05, median 7.77, p90 9.91, max 13.74. Arm 1 wall time about 20.7 h. Cost per Room $0 (on-prem).
4. Card completeness, arm 2 (`evidence_card_report.py`): TO FILL.
5. Gate report (`room_contract_gates.py`): **arm 1 296/300 gate-ok**. The 4 failing Rooms: three MISSING_STANCE (a Bull or Bear turn with no parseable decision and no successful repair: BAC R1 rep 1, SNAP R2 rep 1, SNAP R3 rep 2) and one PM_JSON_UNPARSEABLE (CAG R4 rep 1, CIO draw 4). Side set and arm 2: TO FILL.
6. Approvals of Street Sell/Underperform names: none exist in either set; report approvals by Street bucket
   (buy / hold) per risk level from `street_comparison.street_rating`: TO FILL.

## Commands

```
# analysis (runs files copied to the Mac; read-only)
scp -r melehost:cr267_wp20/out/arm1 melehost:cr267_wp20/out/side melehost:cr267_wp20/out/arm2 <dir>
python3 docs/tools/room_investigation_V2/tools/wp20_analyze.py <dir>/arm1/runs_wp20-arm1.jsonl [<dir>/side/runs_wp20-side.jsonl]
python3 -I docs/tools/room_investigation_V2/tools/room_contract_gates.py --runs <runs.jsonl> --out <gates.json>
# card completeness (arm 2), in a throwaway container with DATABASE_URL, see evidence_card_report.py header
```

## Resume (melehost)

```
ssh melehost 'ls ~/cr267_wp20/out; tail -5 ~/cr267_wp20/logs/driver.log'
# if the driver died (crash/reboot): it resumes on completed arms
ssh melehost 'cd ~/cr267_wp20 && rm -f STOP && setsid nohup bash wp20_driver.sh >> logs/driver.log 2>&1 < /dev/null &'
# stop: touch ~/cr267_wp20/STOP; docker stop wp20_<label>
```

Note: a resumed driver measures arm 1's wall from the resume, so the arm 2 gate then underestimates; check
`logs/arm1.log` start and end times by hand.

## Code freeze (2026-11-20 12:05Z)

1. The first launch ran `docker compose run api-alpha` from `~/ami_trade`. That directory is bind-mounted into the container (`backend/app` and the `/harness` repo copy), and its image tag is rebuilt on every deploy, so any Alpha deploy during the 40 h matrix would have changed the Room mid-run. Once WP-24 shipped, rep 2 could have returned rep 1's banked Room.
2. The run was stopped after 2 arm-1 Rooms (both on `d739d8e8`, kept; the harness resumes past them). It was then restarted on a frozen copy, `~/cr267_wp20/frozen/` (rsync of `~/ami_trade` at `d739d8e8`, minus host data dirs), using the pinned image `ami-wp20:d739d8e8` through `docker-compose.wp20.yml` (in `docs/tools/room_investigation_V2/tools/`). `wp20_run.sh` now runs compose from the frozen directory with project `ami-trade-local`, so it shares the live network and database.
3. The driver's arm-1 wall time undercounts by the two pre-restart Rooms and one failed relaunch (the frozen `.env` was briefly mode 600). For the arm-2 estimate, read `logs/arm1.log` by hand.
4. When WP-20 finishes, delete `~/cr267_wp20/frozen/`: it holds a copy of `.env`.
