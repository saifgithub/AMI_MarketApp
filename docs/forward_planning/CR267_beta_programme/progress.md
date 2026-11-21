# CR267 — Progress log

**What this is:** the hand-over between sessions executing the CR267 Beta programme, with one dated
entry per work-package state change, its commit and its acceptance evidence. **Why:** the plan
(§1.4) makes this file the cold-start anchor for whoever picks the work up next.

Branch `beta/cr267`, worktree `.claude/worktrees/cr267-beta`, track B. Rollback tag `pre-cr267`.

---

## 2026-11-18 — S0 given; WP-00 started (session B1)

1. **S0:** Saiful: "go, start WP-00".
2. **No child CR for WP-00.** It is docs and registers only (exempt under CLAUDE.md); commits are
   tagged `(AT:B1 CR267)`.
3. **WP-00 step 1 — CR266 run: completed, gate FAIL.** `~/cr266_ami_cards_complete_v2/` on
   melehost: 60/60 rooms; coverage 57/60; ICC(A,1) 0.810 < 0.85; 13/30 tickers flipped; 23 APPROVE
   / 37 PASS. Recorded in `CR266_decision_reliability/progress.md`.
4. **WP-00 step 2 — rows.**
   1. Closed with reasons: CR251, CR255, CR257, CR265, CR266 → `dropped` (superseded);
      CR253, CR256, CR259 → `done`.
   2. **Deviation from the plan's list.** CR252 and CR257 were never executed: no commits since
      2026-10-15, and the stocktake says CR257 was "drafted, unsent". CR257 is dropped because WP-22
      absorbs it. CR252 (measured GO, never folded in) stays `proposed` for WP-01 to decide.
   3. `CR253_data_lane_completeness/` was a separate, shipped item that collided on the CR253 ID.
      The Architect minted **CR268** for it; its row is `done`. Child CRs for later WPs start at
      **CR269**.
5. **WP-01 done (gate S1).** Ledger `afee9f99` on `main`; outcome in plan §6 WP-01 item 3. Rows
   dropped on the branch: CR245, CR247, CR250, CR254. New WPs: WP-15 (CR252, behind S11), WP-38
   (CR239), WP-39 (CR022). Still to close: DEF386, DEF434. ⚠️ Company Apple/Google accounts are
   **not enrolled**; the Play account will be an Organisation account.
6. **Gates S11/S12 added** (Saiful): pause for an implementation-plan discussion before any LLM
   change (WP-15, WP-10–14) and before any Jev/grader change (WP-22, WP-23).
7. **WP-00 steps 3–5 and WP-01 closures.**
   1. Decisions D-076–D-089 appended; D-066/D-067 marked reopened, D-068 closed, D-072's hosting
      clause amended (`17fbacc5`).
   2. `project_plan.md` status block and Phase 2 point at CR267 (`17fbacc5`).
   3. The CR253 duplicate deletion is committed on main (`6ee0921c`); CR254 holds the same content.
   4. Ten October leftovers were read in full (836 lines, Sonnet reader, with the flag confirmed by me).
      Nine were clean and are committed on main under K's tag (`769f599b`).
   5. **Held back for Saiful:** `.deliveryos/checkpoint_history/20261017T222812Z_855f74dc…md`
      contains third parties' phone numbers and client-confidential deal details (non-AMI work).
      It is left untracked. Saiful decides whether to delete it, move it out of the repo, or redact
      and commit it.
   6. `20261118T111900Z_f2ac2318…md` is today's memo from the Fable session; not ours, left alone.
   7. DEF386 and DEF434 closed with evidence (`26bf7fb5`).
8. **WP-00 done.** Acceptance:
   1. `gen_registers.py gen all` after merging main leaves no diff.
   2. No WP-00-owned path is dirty. The two untracked memos above are listed here.
   3. Every row changed by WP-00/WP-01 reads `done` or `dropped` with a dated reason (13 rows).

## 2026-11-18 — WP-02 done; S11 approved; wave 1 merged

1. **WP-02 done.** Alpha runs `alpha-2026-11-18-1` (`ca164879`, from `beta/cr267`).
   1. Gates: hold, audit, tree, suite (PASS 7,900/0, on the third attempt), flutter analyze, local gate (PASS).
   2. Earlier suite failures: the first was the DEF465 row citing a Flutter target (reworded, `bb9759fd`); the second was the DEF136 timing test flaking under the load of three parallel worker suites (passes when the Mac is quiet).
   3. **UAT gate FAILED on inherited mobile debt.** Six areas changed by CR264 (10-20) have no case updates, and 14 device cases have not run since. Saiful: "Promote now; clear debt in WP-33" (backend-only promotion; the rsync excludes `mobile/`). The debt must be cleared before any TestFlight/Play build, which uses the same gate.
   4. Postflight PASSED 8/8. API UAT changed-only: 7/7 green. The alpha-post gate fails on the same deferred mobile debt.
   5. Alpha's LLM is unchanged: on-prem vLLM.
2. **S11 approved** (rulings in `S11_llm_implementation_plan.md` §3a). Alpha stays on on-prem until Beta; Ling joins WP-10.
3. **WP-15 done, no code.** CR252 had been folded into all 12 personas since `0f41f14e` (2026-10-08). The WP-00 note saying it was "never folded in" was wrong (I didn't check the persona files). CR252 row → done (`519112f8`).
4. **WP-11 merged** (`e9e730ab`). **WP-13 merged** (`ca164879`) in log mode; enforcement waits on a replay of stored replies.

## 2026-11-18 (late) — waves 2–3 merged; deploys #2 and #3

1. **Deploy #2** `alpha-2026-11-18-2` (`74c15825`): CR270 migration, DeepInfra backup registered.
   - **DEF488 outage:** the $5 daily ceiling refused every request, because pre-migration rows had tokens but no cost, and the Anthropic review model was unpriced. Mitigated by commenting out the ceiling; fixed in `1dce0c03`.
   - **Budget stays OFF on Alpha.** WP-10 harness rows land in Alpha's `llm_audit`, and 4 on-prem rows carry output tokens only, so they can't be priced. It goes ON for Beta, which has its own DB. Sonnet 4.6 priced at $3/$15 per M tokens.
2. **Merged:** WP-34 (`95f3b2b4`, plus DEF489 filed), WP-27 (`636267ae`), WP-31 (`6e3e1d25`, plus the enforcement switch in `06a69250`), WP-35 (`1d51dc50`), WP-32 (`e807a598`). DEF487 flake fixed (`2b1e504b`).
3. **Deploy #3** `alpha-2026-11-19-1` (`1d51dc50`):
   - Gates: suite PASS (8,041/0), flutter analyze 0, local gate PASS.
   - The UAT gate failed on the same deferred mobile debt; Saiful: deploy now. CI not run on the commit.
   - Migration `cr273a0b0c0d1` applied. Postflight 8/8. `ONBOARDING_AGE_GATE_ENFORCED=false` on Alpha.
4. **WP-33 part 1:** 14 of 15 mobile defects fixed on `lane/WP33-mobile-defects`. Beta was merged into the lane (`453ced12`); flutter test exit 0, 2,062 passed. DEF466 left open.
   - Calls for Saiful: "Ask AMI" (was AI Coach); "NO AMI VERDICT".
5. **WP-29:** `lane/WP29-copy` (`cc3379c4`). Doubts for Saiful: subtitle choice, "AMI tutor", Applied AI branding, and the stale Sharia line on the website.
6. **Running:** WP-10 (spend ≈$2.56 of $80), WP-21a (CR275 minted), WP-39 (CR022).

## 2026-11-18 (night) — WP-21a, WP-29, WP-33, WP-39, DEF490 merged; device lab agreed

1. **API UAT after deploy #3:** 4 failures, none a product regression.
   1. DEF458 and DEF459 were strict-xfail XPASSes: the bugs are fixed.
   2. ONB-044 expected the 18+ refusal, but it is switched off on Alpha on purpose.
   3. SUPP-004: the harness spoofed X-Forwarded-For, which DEF464 now correctly ignores, so the bug-report cases (7+ calls) exceed the 5/hour per-IP budget.
   4. Live users are fine: the tunnel peer is in the trusted CIDR.
   5. **DEF490** was filed and fixed (`535def50`): an admin-secret header exempts operator and UAT traffic (constant-time compare, logged, never exempts with an unset secret), the stale xfails were dropped, ONB-044's refusal half is a strict xfail until the gate is switched on, and SUPP-004 was rewritten to be bucket-state independent.
2. **Merged:**
   1. WP-33 (`3c0780d9`).
   2. WP-29 (`6fa280ac`, with the Sharia line fixed per N1 in `7f0590b6`). The live count is 215/503 as of 2026-11-17, so no number is printed.
   3. WP-39 (`852e8908`; `1ce548f4` fixed 3 entries that its truth test caught after the WP-33 ARB moves).
   4. DEF490.
   5. WP-21a / CR275 (`4c0a27db`).
3. **Website deploy blocked** by the permission check. The checksum dry run shows only `index.html` and `og-image.png` change, with no deletions. Waiting on Saiful's go.
4. **Device lab:** protocol v1.0 + am.1 agreed with the AMI AI Suite (MC, NXT; their ruling R-1495). See `device_lab_protocol.md`.
   1. Booking goes through NXT; the Suite's M4 testers operate, and inside a slot we work with the tester directly.
   2. Android is waiting on the Suite's stakeholder to grant the install, run and remove permissions.
   3. The iPhone already has TestFlight with AMI Trade on auto-update (Saiful), so the tester only checks the build number.
5. **Running:** WP-10, WP-30 (CR276 minted), WP-38. The deploy #4 suite gate is running on `4c0a27db`.

## 2026-11-19 — deploy #4 live; DEF491–493; WP-10 done; S2 ruled; WP-30/WP-38 merged

1. **Deploy #4** `alpha-2026-11-19-2` (`4c0a27db`): postflight 8/8. API UAT: 109 of 110. The one failure was DEF460's stale strict xfail (XPASS).
2. **DEF491 (security, fixed `b2f1ee3b`):** httpx logged full request URLs at INFO, which put the Alpha Vantage `apikey` in Alpha's container log. The request-URL loggers are now held at WARNING. **Saiful to rotate the AV key.**
3. **DEF492 (open):** sim news is still dark on Alpha after DEF461. Yahoo refuses melehost, and AV returns 200 with no usable feed (likely the free-tier quota). The UAT news xfails now cite it. The DEF460, DEF462 and DEF463 strict xfails were dropped after each XPASSed live (`245044dc`).
4. **WP-30 + WP-38 merged** (`0b31a855`).
   - Both added a migration on `cr273a0b0c0d1`. My first fix re-parented `cr276`, and the DEF278 immutability guard caught it. The lane was rebuilt with a no-op merge revision `m276a0cr239x276` instead (backup branch `backup/WP30-combined-pre-rebuild`).
   - My review fix `2f03b1b8`: an account inside grace never reaches OneSignal or RevenueCat erasure (its test fails before the fix).
5. **WP-10 done**, with **a financial limit hit:** DeepInfra suspended on balance at 18:37Z (its $25 credit limit; −$4.37). Alpha's DeepInfra backup is dead until Saiful tops up. Saiful: "I'll top it up".
6. **S2 ruled: DeepSeek-V4-Flash.** Alpha's `VLLM_FALLBACK_MODEL` was switched to it (gitignored env, with the price added).
7. **CR277 minted** (Room typewriter pacing adds ~2 min; Saiful: speed it up) and **DEF493 minted** (verdict review silently skipped on a hosted-only config). Both are with Sonnet workers.
8. Deploy #5 gates on `0b31a855`: suite PASS, 8,190 passed.
9. **Deploy #5** `alpha-2026-11-19-3` (`0b31a855`): migrations `cr276a0b0c0d1`, `cr239a0b0c0d1` and the merge `m276a0cr239x276` applied; postflight 8/8; error responses carry `x-request-id`; no `HTTP Request:` lines in the log (DEF491 effective).
   - **Saiful: "do not use deepinfra. Use ami-llm".** Alpha's `VLLM_FALLBACK_*` lines are commented out in `infra/alpha.env`. Live `/v1/llm/status` shows only `vllm` (ami-llm) active, with no fallback slot. Alpha has **no backup model** until he says otherwise.

## 2026-11-19 (early) — no outside LLM vendors on Alpha; deploys #5 and #6

1. **Saiful: "I did not give an ok to use sonnet or any Anthropic models."** He then ruled no Anthropic in the app, and remove Kimi and Gemini too.
   - Alpha's `ANTHROPIC_API_KEY`, `KIMI_API_KEY` and `GOOGLE_AI_API_KEY` are commented out (DeepInfra's were already). Live providers are now `vllm` (ami-llm), `glm` (self-hosted on our Tailscale host) and `mock`.
   - **Correction to my earlier spend report:** Anthropic had 773 calls on 2026-10-27 (before this session; model not recorded, so not priced) plus 10 on 2026-11-18 (≈ $0.08). I had said 7 calls, because I counted by model name, which only exists since CR270.
   - Kimi: 1,541 real calls since 25 Sep, mostly verdict reviews. The 141 tonight were the WP-10 harness pointing the kimi slot at on-prem ami-llm ($0).
   - The S12 labeller is now Ling-Fin on our own host (`f859de4d`). Memory: `feedback_no_anthropic_in_app.md`.
2. **Deploy #5's API UAT:** 116 passed, 3 failed, all WP-38: unmatched-route 404 (product bug, fixed in `615c67b7`), harness `_fake_ip` leftovers, and admin liveness "unknown" after a restart (fixed in `b0c4fe4b`).
3. **Merged:** CR277 (`720eb935`) and DEF493 (`ddd2c999`).
4. **Deploy #6** `alpha-2026-11-19-4` (`b0c4fe4b`): suite PASS 8,217; postflight PASS; 404 bodies now carry `request_id`.

## 2026-11-19 — WP-13 guard replay done (session B1, worker lane `lane/WP13-guard-replay`)

1. Replayed the CR271 guard over 80,759 stored Alpha agent texts (671 app, 79,980 harness, 108 UAT
   non-Room). Before tuning: 13 advice hits (3 true, 10 false), 0 abuse; after: 3 advice hits, all
   true. Two deterministic fixes ("can't lose", "guaranteed return") with 11 new test cases. Result and
   recommendation (enforce advice + abuse; adversarial 1-on-1/Concierge pass first):
   `wp13_guard_replay_2026-11-19.md`. `OUTPUT_GUARD_MODE` left at `log`.

## 2026-11-19 — WP-13b adversarial advice probe done (session B1, worker lane `lane/WP13b-advice-probe`)

1. 40 advice-eliciting prompts (15 1-on-1, 15 Concierge, 10 Brief; EN/MS/AR) sent through the live
   endpoints. Deployed guard caught 0 of 7 real advice replies and fired 4 false hits on refusals;
   after 13b it catches 4 of 7 with 0 false hits, 3 clear misses remain (all 1-on-1 desk-voice tickets
   with no second person). Model refused on its own in 31 of 40. Also replaced `off_topic` with
   `runaway_length` (`OUTPUT_GUARD_MAX_TURN_WORDS`, provisional 1500; p50/p99 and cut count NOT
   measured, no DB access). Recommendation: tune first for 1-on-1 (WP-13c), then enforce:
   `wp13b_advice_probe_2026-11-19.md`.

## 2026-11-19 — deploy #7 live; AMI-DL-1 run; WP-21b, WP-36, WP-40, WP-41 done (tracker lane `lane/tracker-1119b`)

1. **WP-02:** Deploy #7 `alpha-2026-11-19-5` = `dd640a6e`, postflight PASS. UAT gate override logged (ONB-043 reinstall, PLAT-005 stale from WP-36 app changes).
2. **WP-14:** Deploy #7 is live. WP-21b (CR260, `93d2912c`) and WP-36 (CR278, `f46152a1`, backend live; app half ships in the next store build) are live with it.
3. **WP-13:** WP-13b (`9ff95bf0`) probe run; WP-13c (`a00b2ce4`) merged after deploy #7, log mode. Probe detail is in the WP-13b entry above.
4. **WP-28:** Daily scoring is live (`30dda2bb`, 22:30 UTC, 500 due rows per run). Acceptance waits on the first run.
5. **WP-40 and WP-41 done.** WP-40 (`c67aec83`, research `363bb5cc`): Ling cannot run on Cloudflare; Workers AI not covered by Startups credits from Dec 1. WP-41 (CR279, `5700dc73` `5003ce68`) is the Beta env config. WP-12's budget code is present on the Beta env (ceiling $10, required by the CR279 boot check).
6. **WP-33:** AMI-DL-1 (Android, build 117, 08:27–09:21Z): 34 cases, 18 passed, 15 blocked, 1 failed (UAT-MAND-038). DEF494–497 filed and fixed (`lane/DL1-defects`, merged). AMI-DL-2 (iPhone) waits for the phone to update to 117 via TestFlight.
7. **In progress:** WP-37 (`b1ea98be`; CR222 slice A + toll prerequisites moved to CR280), WP-43, WP-44, WP-45 (`69aec6b2`, blocked on WP-49/S7), WP-51 (`588fb4bf`), WP-52 (`c9858a84`).
8. **Waiting on Saiful:** the WP-29 and WP-51 website changes share one deploy go (WEBSITE_ADMIN_SECRET, api-website restart, cPanel rsync). WP-52 has open items (Singapore claim, privacy link version, 'experimental' label).

Found: two users have duplicate training portfolios created 40 ms apart on 2026-09-28 (ISS001 insert race); portfolio snapshot ticks fail for them.

## 2026-11-19 (late) to 2026-11-20 — deploy #8, build 118, AMI-DL-2/3/4, Ling backup, CR281

1. **Deploy #8** `alpha-2026-11-19-6` = `7a205ebd`, postflight PASS. Verified live: DEF498 (UAT-ROOM-023), DEF492 news (SIM-004, HLTH-006; DEF492 closed `8e3cf4fc`), options SIM-020 after market open.
2. **Models (Saiful, S11 §3b `fe182185`):** Alpha's backup is Ling-3.0-flash-Fin on our own host, live since deploy #8. Beta: DeepSeek-V4-Flash primary, Ling-3.0-flash backup (thinking off via extra body). Ling re-score `61683185`: 0/20 gate failures, 0.70¢/Room vs DSV4 1.06¢, spend $0.46.
3. **CR281** (`b8eb01be`): Saiful rejected disabling vendors by commenting out keys ("isn't it better to check if the configuration exist"). `LLM_PROVIDER_ALLOWLIST` now gates providers; boot logs configured-but-blocked; postflight fails on a mismatch. Model swaps are config only; the key is sent only when set.
4. **Build 118** on TestFlight + Play internal (DEF494–497, WP-36 app half). UAT gate override logged with Saiful's ok.
5. **Device runs:** AMI-DL-2 (iPhone, 117), AMI-DL-3 (Android E5, 118) → DEF500–503 merged (`14b56da6`), AMI-DL-4 (iPhone E5, 118) → DEF504. Full suite on `14b56da6`: backend 8761 passed, flutter 2167 passed.
6. **AMI-DL-4 Room finding:** run `cc493ece` (MSFT) was not stuck. It completed at 14:30:19Z with a verdict and a journal entry; the 14:36Z "second run" was the 24 h dedup reattaching to it (`room_dedup_attached_completed`). One charge of 29 credits, no refund owed. The app showed nothing on reopen, which is DEF500.
7. **WP-43** (`e2ca401d`) and **WP-44** (`13ead8d2`) merged; acceptance still needs the Beta host (S4).
8. **Hold:** Saiful paused new work on 2026-11-19 and lifted it on 2026-11-20. Deploy #9 (CR281, DEF500–503, allow-list in alpha.env) and build 119 are next.
9. **Saiful 2026-11-20:** on reopen with a Room still running, the app opens on the Floor with a reconnect banner; no auto-jump into the Room. **Correction:** I put the question to him as if DEF500 already showed that Floor banner. It does not: DEF500 shows its banner inside the Room, and a cold start reaches the run only by convening the same ticker again. DEF506 builds the Floor banner he chose.

## 2026-11-20 (night) — deploy #9, build 119, WP-14 acceptance

1. **Standing go (Saiful, 2026-11-20):** Alpha promotions, internal store builds, lab APK-over installs and logged UAT overrides for stale device cases no longer need a per-item ask. The hard gates still stop.
2. **Deploy #9** `alpha-2026-11-20-1` = `83a6fb06`: suite PASS 8,761; local gate PASS; UAT gate override logged (stale device cases); postflight PASS, including the CR281 allow-list check; API UAT 67 passed, 1 xpassed, alpha-post PASS. The first suite run failed on register drift from my own half-written DEF504 row, not on the code.
3. **Build 119** (`032b873e`): TestFlight internal and Play internal. It carries DEF500–504 and DEF466 (the ticker tape is out of the semantics tree; its per-frame updates are the proven-in-test cause of the iPhone accessibility tree going dark).
4. **WP-14 forced-failover acceptance** (throwaway containers on melehost, $0): primary down → the Room completed on Ling-Fin, labelled `llm_backup_used`, with llm_audit showing 4 failed ami-llm calls and 16 Ling calls; both down → NO_VERDICT outage verdict, refunded, nothing tradeable stored. Both PASS. Found **DEF505**: the both-down verdict still claims `llm_backup_used=true`. Synthetic runs `9c7f02d0`, `1dec3be0` (users `c118bfd7`, `8e84ecbe`, no users-table rows; exclude them).
5. **AMI-DL-5** (Android) and **AMI-DL-6** (iPhone) re-runs on 119 booked with NXT.

## 2026-11-20 (early morning) — device re-runs on 119, DEF505–509, deploy #10, build 120

1. **AMI-DL-5** (Android, 119 via one granted `adb install -r`): 9 passed, 2 blocked (0 credits, so the Room cases did not run), Part B 2 blocked. DEF496, DEF501, DEF502, DEF503 and DEF504 held on the device. Found: the risk-limit chip cut its value off on six of seven limits (**DEF508**, a second attempt after DEF502).
2. **AMI-DL-6** (iPhone, 119 via one granted TestFlight update): 9 passed, 1 failed, 1 blocked. DEF500 (Room reattach replay, one charge) and DEF504 confirmed. E5-HLTH-01 "failed" because the server's 429 cadence refusal was shown as "AMI's engine did not respond" (**DEF509**). **DEF466 is still dark on 119** (after the Journal trash page, until relaunch), so it was reopened; round 2 could not reproduce it in a widget test and added a release-safe semantics-health line to user bug reports for the next device run.
3. **NXT stepped out** of AMI Trade phone work on the stakeholder's instruction; bookings now go to the M4 testers directly.
4. **DEF505** (WP-14): the backup label no longer claims the backup ran a Room in which it answered nothing. **DEF506**: Floor rejoin banner, per Saiful's reopen ruling. **DEF507**: scripted standing-guidance desk turns are flagged end to end and labelled in the app, never shown as a live desk's call (second "fallback shown as real" instance after DEF059; failure_patterns entry with tests). **DEF481**: 5 of 9 items fixed; 4 wait on product calls.
5. **Deploy #10** `alpha-2026-11-20-2` = `d739d8e8`: suite PASS 8,776; local gate PASS; UAT override logged (stale device cases only; the area gaps were fixed with real case updates first); postflight PASS (one re-run after a transient connection reset); API UAT 68 passed, 1 xpassed; alpha-post PASS. The first gate run failed on the DEF295 guard (two hand-copied English strings in ar/ms from DEF509); fixed by marking them as seeds.
6. **Build 120** from `fb855088`: DEF481, DEF506–509 and the DEF466 diagnostic.
7. **Correction on build 120's UAT override.** Its logged reason said only stale device cases remained. That was wrong: DEF481 had changed eight areas' screens (back-control identifiers; the Floor inbox button became an envelope) without case updates, and the override passed them. Fixed after the build: UAT-FLOOR-006/008 now say "envelope (inbox) button" instead of "bell", and the other seven areas carry a dated DEF481 note (identifiers only, no visible change). From now on the area check is cleared with real updates before any override.

## 2026-11-20 (morning) — device runs on build 120

1. Bookings now go to the M4 testers directly; each tester's stakeholder granted one 120 install (Android: am.2 widened to slots AMI Trade books directly).
2. **AMI-DL-7** (Android, 120): 10 passed, 1 blocked (HLTH-013: this account had trial Findings left, so no cadence refusal), Part B 2 blocked (no credits). **DEF508** confirmed: all seven chips show their value in full. **DEF481** confirmed: envelope inbox, Back works on every listed screen.
3. **AMI-DL-8** (iPhone, 120): 11 passed, 1 "failed", Part B 2 blocked. **DEF506** confirmed: reopen mid-Room lands on the Floor with "Your Room on AMZN is still running." and REJOIN; one charge. **DEF509** confirmed: "Your next reading is available on Dec 19, 2026." with no retry. The E5-MAND-01 "failure" is by design (CR129): that account has its own limits set, so the chip shows the mechanism-only label without a number. The pairing with "Set by you — overrides your risk profile" reads oddly, so it goes to Saiful as a copy question, not a defect.
4. **DEF466 diagnosis:** the tree went dark again (Settings, PROFILE scroll). The semantics-health line in the bug report filed while dark shows Flutter healthy: semantics on, updates flowing, 33 nodes, 0 errors, the same as the post-relaunch baseline. The fault is between iOS's accessibility bridge and WebDriverAgent, not in app code. Next step is on the harness side; DEF466 stays open with that scope.

## 2026-11-20 (afternoon) — Saiful's rulings on the open items

1. **DEF481 product calls:**
   1. OPEN MY MANDATE scrolls to the mandate.
   2. A pill is tappable only where a destination exists, otherwise it is restyled. Done, merged `c113197a`: RELATED LESSONS opens the lesson, RELATED AGENTS is plain text (no agent profile screen exists), and SEE ALSO terms are tappable where they resolve.
   3. Day Trader is high risk: highest risk tolerance and short term only, with the other settings to match.
   4. MANAGE ACCOUNT opens the subscription tier picker.
   5. New risk-limit chip copy is accepted.
   6. Items 1, 3, 4 and 5 are with a worker.
2. **Android lab account** topped up from 0 to 300 credits. Logged as a `credits_added` subscription event; Saiful: "you're testing, set your parameter".
3. **AR/MS:** a language update pass comes later. The seeds stay flagged.
4. **Tester exchange folder:** the 119/120 APKs and the old packets were deleted at Saiful's instruction.
5. **S4:** Saiful wants the options, with Cloudflare among them; no pick yet. A worker is writing `beta_host_options_2026-11-20.md`.
6. **S5:** Cloudflare for Startups Tier 3 and Alibaba AI Catalyst. The application drafts are being written.
7. **S7:** the company accounts are enrolled and empty: "prepare but do not release yet". WP-49 prep has started; nothing is released.
8. **Room chain:** the on-prem baseline runs first, at $0, and WP-26 re-runs on Beta's model. WP-20 has started on Alpha.
9. **Website:** deployed (WP-29 + WP-51). The deploy exposed **DEF510**: the website tables were still owned by `postgres` after CR124/M8, so the WP-51 column migration crash-looped api-website for about 2 minutes. Fixed by handing the tables to `ami_website`; the runbook is updated.
10. **WP-52:** I fix the four open checks and Saiful skims. **Keys (AV/Adanos):** later. **DEF499:** a 4th ISS001 contributor, then the fix. **A17 rig:** reconnect, which needs a person at melehost. **Counsel:** I draft a narrow brief with three questions.

## 2026-11-20 — WP-13 replay

1. **Replay (read-only, Alpha `llm_audit`, current rules, enforce mode):** 121,116 rows on the six user-visible flows (App 907, Harness 108,377, UAT/rig 11,832). Full table in `wp13_enforce_replay_2026-11-20.md`.
2. **Hit rate:** 10 of 121,116 rows would be withheld (0.0083%): advice 7, personal_advice 5, abuse 0; none in the 907 app-user rows. Before today's tuning it was 18; the 8 removed were all false positives (negations, a quoted mention, a conditional, "retard" as a verb, option lists and a quoted example read as tickets, "30% portfolio drawdown"). Hand-check of all 12 remaining hit instances: 10 true, 2 borderline, 0 clear false.
3. **runaway_length:** Room turns p50 192, p95 432, p99 570, p99.9 1,488 words (harness `room`); max 18,369. The cap stays 1,680: it trims 59 turns (0.049%), none from the app cohort, about 36 of them loops.
4. **Enforce is ready.** `OUTPUT_GUARD_MODE=enforce` in `infra/beta.env.example`, and Beta boot refuses any other value. Alpha is flipped at deploy. Brief now holds its reply in `enforce` mode, so a flagged reply never reaches the screen (before, only a retraction line could follow it).
5. **DEF511** (same lane): the forced-update Play URL is now `ANDROID_PLAY_STORE_URL` (default = the personal Alpha app), required on Beta, refused at Beta boot if empty or still the personal package.

## 2026-11-20 (evening) — deploys #11 and #12, WP-24, DEF499, ISS001

1. **Deploy #11** `alpha-2026-11-20-3` = `335ff5c3`: the DEF481 backend half (the Day Trader profile). Suite PASS 8,803; local gate PASS; UAT override logged for stale device cases only; postflight PASS; API UAT PASS (124 results).
2. **Deploy #12** `alpha-2026-11-20-4` = `d8566759`: WP-24, DEF499, DEF511, and the WP-13 guard in enforce mode.
   1. The first suite run failed on 2 config tests: the worktree held a stale copy of `alpha.env`, and `WEBSITE_ADMIN_SECRET` was undeclared. After the fix the suite passed, 8,915 passed and 0 failed.
   2. Postflight PASS.
   3. Migrations `def499a0b0c0d2` and `cr267a24bank01` ran.
   4. `OUTPUT_GUARD_MODE=enforce` is live on Alpha.
3. **DEF499 fixed and verified live.** The migration removed 3 empty duplicate training portfolios (2 users). Each user now holds 1, and partial unique indexes close the NULL-run hole.
4. **WP-24 live.** A repeat convene with unchanged inputs returns the banked Room at no charge. The key covers the mandate, the day's fact sheet, the policy version, the model root, the portfolio digest (holdings, legs, trades, cash to $1), the ticker's journal and the Alpaca digest. Unit acceptance: the 50-pair test.
5. **ISS001.**
   1. A 4th contributor (sonnet5.5) was added. The verdict ranks sonnet5.5 > kimi-k2 > opus5.0 > gemini; the judge also ran on Sonnet, so same-model bias is possible.
   2. Phase 1 (the `claim()` helper and the insert tripwire) is merged locally. The unit suite runs in raise mode; production runs in log mode.
   3. The real-Postgres acceptance passed: 8 threads × 15 rounds, and the read-then-insert control duplicated in 15 of 15 rounds.
   4. Saiful's rulings: the DEF308 sites are unfrozen and Phase 3 converts them; production stays in log mode until Phase 3 completes.
   5. Phase 1 collided with WP-24's new inserts, and a worker is converting them to `claim()`. `beta/cr267` stays unpushed until the suite is green.
6. **WP-20.** It was restarted on a frozen copy of the `d739d8e8` tree and the pinned image `ami-wp20:d739d8e8`, so deploys cannot change the Room mid-matrix.
7. **WP-39.** The 10-question Concierge check was routed to the "AMI AI" agent at Saiful's instruction.

## 2026-11-20 (night): DEF512, ISS001 Phase 3, deploy #13

1. **Deploy #12's API UAT found DEF512.** The fact-sheet freeze could not JSON-encode `RatioBaseline`, so no Room was ever banked. With the old 24 h reattach removed, a repeat convene charged again. The failure was logged at ERROR; no wrong Room was ever served.
   1. Fix: the CIO snapshot codec now tags and rebuilds any `app.` dataclass, NamedTuple or Enum. The decoder is restricted to those kinds of class under `app.`.
   2. Guard: a real-shape test asserts the frozen → thawed desk prompts are identical for all 12 desks.
   3. This is the third occurrence, recorded as failure pattern P41. The structural fix removes the hand-kept registry that caused all three.
2. **ISS001 Phase 3:** 8 of 9 DEF308 sites now go through `claim()`, one commit each, including sign-in, where the loser of a race is signed in as the winner.
   1. `ensure_field` is pending. A read-only count on Alpha showed 0 duplicate groups for `(cadence, starts_on)` among open, non-abandoned fields, and `week` legitimately has 2 open rows at once.
   2. WP-24's `room_runs` / `room_fact_sheets` inserts also go through `claim()`.
3. **Deploy #13** `alpha-2026-11-20-5` = `ef6edf57`: DEF512, ISS001 Phases 1 and 3, and WP-24 on `claim()`.
   1. Suite PASS: 8,991 passed, 0 failed.
   2. Local gate PASS.
   3. UAT override logged, for stale device cases only.
   4. Postflight PASS.
   5. The tripwire runs in `log` mode.
4. **WP-20:** 75 of arm 1's 300 Rooms done in about 8 h, about 6.4 min per Room effective against the pilot's 3.6. Arm 2 will likely be skipped by the 24 h rule.
5. **DEF512 verified live** after deploy #13: the API UAT passed (6 of 6 changed cases, both banked-Room cases included), Alpha logged 3 `room_bank_hit` events, and 0 freeze errors.
6. **DEF308: 9 of 9.** `ensure_field` is converted on a new partial unique index, migration `def308a0b0c0d3` (merged; ships in deploy #14).
7. **Build 0.1.0+121** (bump `45219e7e`, from `f5e9a42c`) is on TestFlight internal and Play internal, under a UAT override for stale device cases only. The APK sha256 is `e3e9f81f…cfe422b`. AMI-DL-9 (Android, 16 cases, including the WP-24 banked-Room case UAT-ROOM-031) and AMI-DL-10 (iPhone, 12 cases) are booked with the M4 testers. Each tester needs a per-build grant.

## 2026-11-21: device run AMI-DL-9 (Android, build 121)

1. **AMI-DL-9** (18:06–21:33Z): one APK-over 120 → 121. The sha256 and signer were checked first, and there was no uninstall. 17 ids: 10 passed and 7 blocked, with no failures.
   1. Passed: PLAT-005, FLOOR-007, E5-MAND-01, SUPP-010 (the related-lesson pills), SUPP-012, SIM-028, ROOM-016 (AAPL, 12 credits, about 14 min), ROOM-028 + FLOOR-011 (the rejoin banner, no second charge) and SIM-029. SIM-022 part A ran: OPEN MY MANDATE lands on RISK LIMITS.
   2. Blocked because the tester's stakeholder did not grant them: AUTH-044, MAND-031, SIM-022 part B, MAND-035 and BILL-012. Also blocked: HLTH-013 (the server day was still 20 Nov) and ONB-043 (it needs an uninstall).
   3. UAT-ROOM-031 (the WP-24 banked Room) was not run. My packet put it under "Pending lanes" instead of Part A. It moves to AMI-DL-9b.
   4. The tester saw NVDA disappear. A read-only check shows its stop filled on 20 Nov at 14:36Z ($141.90 stop, closed at $140.56): by design.
2. **AMI-DL-9b** is requested for after 00:00Z on 21 Nov, covering the blocked cases plus ROOM-031. The addendum is in the tester's `steps_in/`.
3. **AMI-DL-10** (iPhone) is granted but waits for a person to unlock the phone.

## 2026-11-21: AMI-DL-10 (iPhone, build 121); deploy #14

1. **AMI-DL-10** (22:31–23:24Z): 10 passed, 1 failed, 2 blocked.
   1. Passed: PLAT-005, E5-MAND-01, SUPP-010, SUPP-012, AUTH-044 (Delete account, CANCEL only), SIM-028, LESS-010, SIM-029, SIM-022 (OPEN MY MANDATE lands on RISK LIMITS for the NFLX cap refusal and on COMPLIANCE for the JPM halal refusal), MAND-035.
   2. Failed: UAT-MAND-031 on #4 only. Saving a 3% single-name cap while holding NFLX at about 46% showed no retro-tightening disclosure. **DEF514**: the disclosure is wired only to `max_open_positions`/`max_open_risk_pct`, behind a false comment. A worker is fixing it.
   3. Confirmed on device by the rest of MAND-031: the DEF481 Day Trader preset sets dial 5, short horizon, active path and 100% drawdown; deselecting it keeps those; the chip copy is right.
   4. Blocked: FLOOR-007 (no locked agent on this account) and ONB-043 (needs an uninstall).
   5. The mandate was restored exactly (v9 → v16 over seven Saves; the final read-back equals the baseline).
   6. DEF466 went dark on Settings again (harness side).
   7. Observation: the trade-ticket preview has no notional or cash-available line.
2. **Deploy #14** `alpha-2026-11-21-1` = `f0d9f99e`: DEF513 (every Room input in the bank key, including the Brief, the screening verdicts, the roster, 40 global settings and the plan tier) and the DEF308 `ensure_field` index (migration `def308a0b0c0d3`).
   1. Suite PASS 9,073.
   2. Local gate PASS.
   3. UAT override logged, for device cases only.
   4. Postflight PASS.
3. **AMI-DL-9b** (Android, 00:00–00:16Z on 21 Nov):
   1. UAT-HLTH-013 FAILED. FULL FINDING spun about 2 min, then showed "engine did not respond", and the card then claimed the trial was used up. Alpha's logs show no Finding POST from that account at all. Filed as **DEF515**; a worker is investigating.
   2. UAT-ROOM-031 steps 1–2 failed, by my deploy order. Deploy #14 (DEF513) changed the bank-key composition at about 23:45Z, between the two AAPL Rooms, so the 21:02Z Room could not match. Both Rooms carry a bank key. The re-test is a re-convene of AAPL; the 00:05Z Room is banked under the new key. Step 3 (Brief edit) is held for the same slot.
   3. The five ungranted cases are blocked.
