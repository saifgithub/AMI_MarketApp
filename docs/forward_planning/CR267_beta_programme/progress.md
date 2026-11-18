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
