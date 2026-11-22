# CR267 WP-20 — Room baseline, on-prem model (DONE 2026-11-22)

**Status:** DONE 2026-11-22. All three jobs finished on melehost: arm 1 (300 Rooms, cards off, ended 2026-11-21 08:45Z),
the side set (50, cards off) and arm 2 (300 Rooms, cards on, 2026-11-21 12:14Z to 2026-11-22 13:56Z). Numbers below come from
`wp20_analyze.py`, `room_contract_gates.py` and `evidence_card_report.py` (commands at the end). Format follows
`docs/forward_planning/CR251_risk_monotonicity_matrix/BASELINE.md`. The WP-22 code grader over arm 2 is in
`grader_bakeoff_2026-11-21.md`.

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

## Results

Totals: 650 Rooms, all 650 completed, none errored; `llm_backup_used` false in all 650 (on-prem only, as required);
`model_root_start.txt` equals `model_root_end.txt` for every job (`/models/qwen38-flash-next-abliterated-nvfp4`). Cost per Room $0.

1. Approvals per risk level (n per cell = 2 reps x 30 tickers per level = 60; side set 10 per level):

   | Risk | arm 1 cards off: APPROVE | rate | arm 2 cards on: APPROVE | rate | side set (cards off): APPROVE |
   |---|---|---|---|---|---|
   | R1 | 3/60 | 5% | 4/60 | 7% | 0/10 |
   | R2 | 3/60 | 5% | 2/60 | 3% | 0/10 |
   | R3 | 10/60 | 17% | 12/60 | 20% | 0/10 |
   | R4 | 13/60 | 22% | 16/60 | 27% | 1/10 |
   | R5 | 20/60 | 33% | 24/60 | 40% | 3/10 |
   | all | 49/300 | 16% | 58/300 | 19% | 4/50 |

   Other verdicts: every non-APPROVE Room is PASS except REJECT in arm 1 R5 (SPCE and XRX, both reps, 4 Rooms) and arm 2 (BGS R2 rep 1, 1 Room). Approvals rise with risk level in aggregate in all three sets, but not per ticker (e.g. MA approves at R1 and R3 but not R2/R4/R5 in arm 1). Arm 2 R1 (4) is above R2 (2): at these counts that is rep noise. The per-ticker tables are in `wp20_analyze.py`'s output.
2. Flip count across reps (comparable cells = ticker x risk with both reps completed; a flip is the two reps returning different actions): **arm 1 35/150 (23%); arm 2 37/150 (25%)**; side set 2/25 (8%). CR251 reference (a different stack): 29/150. On APPROVE-vs-anything-else only: arm 1 35/150, arm 2 36/150.
3. Minutes per Room (wall clock, 2 in flight; cost $0, on-prem):

   | Job | n | mean | median | p90 | max | wall time |
   |---|---|---|---|---|---|---|
   | arm 1 (cards off) | 300 | 8.05 | 7.77 | 9.91 | 13.74 | about 20.7 h |
   | side set (cards off) | 50 | 8.05 | 7.58 | 10.21 | 12.48 | about 3.5 h |
   | arm 2 (cards on) | 300 | 10.02 | 8.78 | 13.27 | 32.05 | 25.7 h (2026-11-21 12:14Z to 2026-11-22 13:56Z) |

   Cards-on is 1.24x arm 1 per Room (the pilot's 1.15x estimate was low). arm 2 shared the vLLM with the WP-22 on-prem grader runs for part of its window, so its minutes are an upper bound for cards-on alone.
4. Card completeness, arm 2 (`evidence_card_report.py`, repair-aware, run read-only on melehost; report JSON at `~/cr267_wp20/out/arm2/card_report/card_report_qwen38-flash-next-abliterated-nvfp4.json`):
   1. **277/300 Rooms (92.3%) carry the complete CR266 census** (four evidence desks x five items, one card each, no duplicates): R1 56/60, R2 55/60, R3 55/60, R4 57/60, R5 54/60. `sheet_state` is present on 300/300 (registry-backed, 0 `card_self_report`), 0 duplicate cards, 0 loader anomalies.
   2. The 23 incomplete Rooms: 11 where a whole desk filed no card (Bull 6, Bear 4, Fundamentals 2 desk-instances; BAC R1 rep 1 is missing both Bull and Bear) and 12 where a desk filed some items but not all five (Research Manager 4 Rooms, Bear 4, Bull 3, Fundamentals 2; a few Rooms have two such desks). 58 malformed card lines and 14 malformed objection lines across the arm.
   3. **ICC(A,1) of the evidence score across reps** (bar 0.85): R1 0.86, R2 0.71, R3 0.86, R4 0.79, R5 0.80. Two of five levels clear the bar.
   4. The tool's own gate (`icc >= 0.85 AND complete machine channels AND registry sheet_state AND clean corpus`) therefore reads **FAIL** (`icc_pass` false, `coverage_pass` false; `registry_state_pass` and `corpus_pass` true). Plan text: cards go on in production only if the cards-on arm passes the contract gates; item 5 is the stance/JSON contract gate, which passes at the same rate as arm 1, and this item 4 is the card gate, which does not. The call is Saiful's.
5. Gate report (`room_contract_gates.py`, stance and JSON contract per Room): **arm 1 296/300, arm 2 296/300, side set 49/50 gate-ok.** The failing Rooms:
   1. arm 1: three MISSING_STANCE (a Bull or Bear turn with no parseable decision and no successful repair: BAC R1 rep 1, SNAP R2 rep 1, SNAP R3 rep 2) and one PM_JSON_UNPARSEABLE (CAG R4 rep 1, CIO draw 4).
   2. arm 2: two MISSING_STANCE (BA R3 rep 2 on the Fundamentals desk, RIVN R3 rep 2 on the Bear) and two PM_JSON_UNPARSEABLE (BA R5 rep 2, DHR R5 rep 1, both CIO draw 4).
   3. side set: one MISSING_STANCE (ITW R1 rep 2, News analyst).
6. Approvals of Street Sell/Underperform names: **none exist in any set** (every Room's Street stance is Buy, Hold or unavailable), so the measure cannot be computed. By Street bucket, from `street_comparison.street_stance` on each stored verdict (Rooms with no Yahoo rating data are in the "n/a" column):

   | Set | Risk | Rooms Buy / Hold / n/a | APPROVE on Buy | APPROVE on Hold | APPROVE n/a | share of approvals that are Street Buy | approval rate on Buy Rooms | on Hold Rooms |
   |---|---|---|---|---|---|---|---|---|
   | arm 1 | R1 | 34 / 18 / 8 | 3 | 0 | 0 | 100% (3/3) | 9% | 0% |
   | arm 1 | R2 | 33 / 18 / 9 | 3 | 0 | 0 | 100% (3/3) | 9% | 0% |
   | arm 1 | R3 | 34 / 18 / 8 | 6 | 4 | 0 | 60% (6/10) | 18% | 22% |
   | arm 1 | R4 | 34 / 18 / 8 | 8 | 3 | 2 | 73% (8/11) | 24% | 17% |
   | arm 1 | R5 | 34 / 17 / 9 | 13 | 5 | 2 | 72% (13/18) | 38% | 29% |
   | arm 1 | all | 169 / 89 / 42 | 33 | 12 | 4 | 73% (33/45) | 20% | 13% |
   | arm 2 | R1 | 34 / 20 / 6 | 2 | 2 | 0 | 50% (2/4) | 6% | 10% |
   | arm 2 | R2 | 33 / 19 / 8 | 1 | 1 | 0 | 50% (1/2) | 3% | 5% |
   | arm 2 | R3 | 34 / 20 / 6 | 9 | 2 | 1 | 82% (9/11) | 26% | 10% |
   | arm 2 | R4 | 34 / 20 / 6 | 12 | 4 | 0 | 75% (12/16) | 35% | 20% |
   | arm 2 | R5 | 34 / 20 / 6 | 17 | 6 | 1 | 74% (17/23) | 50% | 30% |
   | arm 2 | all | 169 / 99 / 32 | 41 | 15 | 2 | 73% (41/56) | 24% | 15% |
   | side | all | 0 / 50 / 0 | 0 | 4 | 0 | 0% (0/4) | - | 8% (4/50) |

   The Street data is live Yahoo, so the Buy/Hold/n-a split of the same 30 names differs a little between arms (arm 1 ran 2026-11-20/21, arm 2 2026-11-21/22). Approvals lean to Street Buy names (73% of approvals in both arms against 56% of Rooms) and the approval rate on Buy Rooms is at or above the Hold rate from R4 up in both arms; at R3 arm 1 is the other way (22% on Hold, 18% on Buy). Side set (Hold names only): 4 approvals, R4 1 and R5 3.
7. **Arm 1 (cards off) against arm 2 (cards on)**, same 300 keys `<ticker>-r<risk>-rep<i>`:
   1. Approvals 49 against 58 (16% against 19%), higher at R1, R3, R4, R5 and lower at R2. Rooms where the two arms disagree on APPROVE-vs-not: 75/300 (arm 1 only 33, arm 2 only 42, both 16), which is the same size as the within-arm rep disagreement (35/150 and 36/150 cells). A McNemar test on the 75 discordant Rooms gives chi-square 1.1 (p about 0.3): the +9 approvals are not distinguishable from draw noise. Correlation of the per-cell approval rate between the arms is 0.31.
   2. Flips across reps 35/150 against 37/150 (23% against 25%): cards on does not make the Room more repeatable.
   3. Time per Room 8.05 against 10.02 minutes (1.24x, p90 9.9 against 13.3, max 13.7 against 32.1).
   4. Stance/JSON gate-ok 296/300 in both. Card completeness is arm 2 only (item 4).
   5. Reading: cards-on changes neither the approval curve nor the flip rate beyond noise, costs about a quarter more time, and 8% of its Rooms lack a complete card census. The cards-on arm is evidence for WP-22's code grader; it changes nothing in production.

## Commands

```
# analysis (runs files copied to the Mac; read-only)
scp -r melehost:cr267_wp20/out/arm1 melehost:cr267_wp20/out/side melehost:cr267_wp20/out/arm2 <dir>
python3 docs/tools/room_investigation_V2/tools/wp20_analyze.py <dir>/arm1/runs_wp20-arm1.jsonl [<dir>/side/runs_wp20-side.jsonl]
python3 -I docs/tools/room_investigation_V2/tools/room_contract_gates.py --runs <runs.jsonl> --out <gates.json>
# card completeness (arm 2): throwaway container of the deployed image, read-only DB session (PGOPTIONS), on melehost
scp docs/tools/room_investigation_V2/tools/{evidence_card_report,cards_run,evidence_gate_fit}.py docs/tools/room_investigation_V2/tools/wp20_cards_report.sh melehost:cr267_wp20/cards_tool/
ssh melehost '~/cr267_wp20/cards_tool/wp20_cards_report.sh arm2 qwen38-flash-next-abliterated-nvfp4 /out/arm2/runs_wp20-arm2.jsonl /out/arm2/card_report'
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
4. WP-20 is finished (2026-11-22); `~/cr267_wp20/frozen/` (it holds a copy of `.env`) is deleted by the coordinator, not by this lane. The card report and the WP-22 code grader read its `.env` for the DB password only and copy it nowhere.
