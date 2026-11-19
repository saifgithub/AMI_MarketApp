# CR267 — Plan vs actual tracker

**What this is:** one row per work package, comparing what the plan said with what actually happened:
status, dates, commits, and every deviation from the plan. **Why:** Saiful asked (2026-11-18) for a
tracker to measure execution against the plan. `progress.md` holds the narrative and the evidence;
this file is the scoreboard. Update both on every WP state change.

Status values: `not started` · `in progress` · `blocked (gate)` · `done` · `failed` · `dropped`.

## Work packages

| WP | Title | Plan deps / gate | Status | Started | Done | Commits | Deviations from plan |
|---|---|---|---|---|---|---|---|
| WP-00 | Re-entry | S0 ✅ 2026-11-18 | done | 2026-11-18 | 2026-11-18 | `5cf24439` `17fbacc5` `6ee0921c` `769f599b` | (1) CR252 and CR257 were never executed: CR257 dropped (WP-22 absorbs it); CR252 went to WP-01 (now WP-15). (2) CR253 ID collision: CR268 minted. (3) CR266's run *did* complete; result recorded (gate FAIL). (4) One K memo held back (third-party personal data); Saiful decides. |
| WP-01 | Register decision review | S1 ✅ | done | 2026-11-18 | 2026-11-18 | `afee9f99` (main), branch rows | Ledger committed to `main` so other sessions don't re-trigger today's review. 13 items accepted on recommendation in one go (Saiful). New scope: WP-15, WP-38, WP-39; batch additions to WP-27/33/35. DEF386 and DEF434 closed (verified). |
| WP-02 | Bring Alpha level with HEAD | WP-00 | done | 2026-11-18 | 2026-11-18 | `440b82dd`; deploys `alpha-2026-11-18-1` `-18-2` `-19-1` `-19-2` | UAT gate failed on inherited mobile debt; Saiful: promote now, clear it in WP-33 (backend-only). Repeated for deploys #2–#4. Deploy #3's API UAT found **DEF490** (the harness spoofed IPs, which DEF464 now ignores); fixed in `535def50`. |
| WP-15 | CR252 heuristics fold-in | WP-00 · S11 ✅ | done | 2026-11-18 | 2026-11-18 | `519112f8` | No code: already folded into all 12 personas since `0f41f14e`. My WP-00 note was wrong. |
| WP-10 | Hosted-model shortlist + scorecard | WP-00, WP-15 · S11 ✅ | done | 2026-11-18 | 2026-11-19 | lane `a96b1123` | Scorecard `CR240_llm_provider_evaluation/scorecard_2026-11-18.md`. **DeepInfra suspended on balance mid-run** (its $25 credit limit; balance −$4.37), so 70–82% of hosted Rooms are valid. WP-10 spend measured at $4.38. DSV4 0/86 gate failures, 1.1¢ per Room, MIT. No model meets 2 min wall-clock: the typewriter pacing adds ~2 min, so CR277 was minted. Findings: the openai slot sends no thinking-off field (not needed for DSV4); verdict review skipped on a hosted-only config, so DEF493 was minted. CR277 (`720eb935`) caps typing at about 35 s a Room (estimate); timed live after deploy #6. |
| WP-11 | Pin temperature | WP-00 · S11 ✅ | done | 2026-11-18 | 2026-11-18 | `e9e730ab` | CR269. |
| WP-12 | Budget + concurrent-run cap | WP-00 · S11 ✅ | in progress | 2026-11-18 | | `74c15825` `1dce0c03` | CR270. Live on Alpha. DEF488: the $5 ceiling refused everything after deploy #2 (unpriced pre-migration rows); fixed. **Budget stays OFF on Alpha** (harness rows share its DB; output-only rows are unpriced); ON for Beta. |
| WP-13 | Output text guard | WP-00 · S11 ✅ | in progress | 2026-11-18 | | `ca164879` | CR271. Log mode on Alpha. Enforce after a replay of stored replies measures the hit rate. |
| WP-14 | Alpha cut-over + automatic failover | WP-10/11/12 · S2, S11 ✅ | in progress | 2026-11-18 | | `c3924bf9` | CR272. Alpha stays on on-prem (S11 ruling); DeepInfra Qwen3.8-Flash registered as backup. Forced-failover acceptance test still to run. DEF493 (`e05b3b11`, merged `ddd2c999`): the verdict review never uses Anthropic and runs same-model, flagged, when no other provider exists. Saiful 2026-11-19: Alpha on-prem only (no DeepInfra, Anthropic, Kimi or Gemini). |
| WP-20 | Room baseline | WP-14, WP-21a | not started | | | | |
| WP-21a | Room decides blind | WP-00 | done | 2026-11-18 | 2026-11-18 | `4c0a27db` | CR275. The sheet DID carry rating, targets, split and tape to every agent by default; now withheld at `_format_profile` (prefix `analyst_`), data kept for WP-21b. Left in, for Saiful: news headlines that mention upgrades; consensus EPS estimates. |
| WP-21b | Street comparison after verdict | WP-21a, WP-14 | not started | | | | |
| WP-22 | Narrow-question judge + bake-off | WP-20 · **S12** | not started | | | | S12 approved 2026-11-18; waits on WP-20. |
| WP-23 | Coded decision rule | WP-22 · S3, **S12** | not started | | | | |
| WP-24 | Same inputs → same room | WP-20 | not started | | | | |
| WP-25 | Flip explainer | WP-23, WP-24 | not started | | | | |
| WP-26 | Room acceptance run | WP-21b/23/24/25 | not started | | | | |
| WP-27 | Room reliability defects | WP-00 | done | 2026-11-18 | 2026-11-18 | `636267ae` | DEF444/445/467/471/480/484 + CR272 backup notice. DEF471: the Room auto-starting is intended (10-20 ruling), so only a leave warning was added. |
| WP-28 | Outcome scoring | WP-14 | not started | | | | |
| WP-29 | Copy | WP-00 | in progress | 2026-11-18 | | `6fa280ac` `7f0590b6` | Merged. The website deploy was blocked by the permission check and awaits Saiful's go. The stale Sharia line was fixed per claim register N1. |
| WP-30 | Account deletion + export | WP-00 | in progress | 2026-11-18 | | `0b31a855` `2f03b1b8` | CR276. Live on Alpha since deploy #5 (backend). Left: device check via the next app build; counsel items for S6. |
| WP-31 | 18+ confirmation | WP-00 | done | 2026-11-18 | 2026-11-18 | `6e3e1d25` `06a69250` | CR273. Enforcement switch OFF on Alpha until the new build reaches testers. |
| WP-32 | iOS privacy manifest | WP-00 | done | 2026-11-18 | 2026-11-18 | `e807a598` | CR274. Declares no tracking; must change if personalised ads ever ship (flagged for WP-50). |
| WP-33 | Mobile defect batch | WP-00 | in progress | 2026-11-18 | | `3c0780d9` | Part 1 merged: 14 of 15 (DEF466 open). Part 2 = device run on the Suite's phones per `device_lab_protocol.md`. |
| WP-34 | Backend defect batch | WP-00 | done | 2026-11-18 | 2026-11-18 | `95f3b2b4` `3c5b66ba` | DEF458–463, DEF468. Filed DEF489 (fixed in WP-35). |
| WP-35 | Security leftovers | WP-00 · S8 | blocked (gate) | 2026-11-18 | | `1d51dc50` | DEF464, DEF489, DEF104 merged. DEF178 waits on S8 (Adanos key rotation). |
| WP-36 | Beta build settings, report, thumbs | WP-23 | not started | | | | |
| WP-37 | CR231 gate items | WP-00 | not started | | | | |
| WP-38 | Trace ID on errors (CR239) | WP-00 | in progress | 2026-11-18 | | `0b31a855` `615c67b7` `b0c4fe4b` | Live since deploy #5. Deploy #5's API UAT found unmatched-route 404s without a body `request_id` (the handler was registered for FastAPI's subclass); fixed in `615c67b7` with a real-app test. Left: trace one error end to end on a device. |
| WP-39 | App manual corpus (CR022) | WP-00 | in progress | 2026-11-18 | | `852e8908` `1ce548f4` | Merged: 28 entries, a cited source line on every answer, 10 how-to questions pass offline. Left: a rig check after deploy #4. |
| WP-40 | Credits / accelerator research | WP-00 | not started | | | | |
| WP-41 | Beta env config | WP-14 | not started | | | | |
| WP-42 | Provision Beta host | WP-41 · S4 | not started | | | | |
| WP-43 | promote/rollback-beta | WP-42 | not started | | | | |
| WP-44 | Backups, monitoring, alerts | WP-42 | not started | | | | |
| WP-45 | Beta URL in builds | WP-41, WP-49 | not started | | | | |
| WP-46 | Load test + drills | WP-43, WP-44 | not started | | | | |
| WP-49 | Company-account migration (CR258) | WP-00 · S7 | not started | | | | Added in rev 2. ⚠️ Company accounts not enrolled yet (WP-01); long lead time. |
| WP-50 | Store records + listing | WP-29/36/49 | not started | | | | |
| WP-51 | Website waitlist | WP-00 | not started | | | | |
| WP-52 | Tester note + support inbox | WP-00 | not started | | | | |
| WP-53 | Exit-criteria report | WP-36, WP-46 · S9 | not started | | | | |
| WP-54 | Beta go-live | see plan | not started | | | | |

## Gates

| Gate | Status | Date | Note |
|---|---|---|---|
| S0 | ✅ given | 2026-11-18 | "go, start WP-00" |
| S1 | ✅ done | 2026-11-18 | 66 items ruled (53 asked, 13 accepted on recommendation) |
| S2 | ✅ ruled | 2026-11-19 | Saiful: **DeepSeek-V4-Flash** for Beta (WP-10 scorecard). Alpha's backup model was switched to it; it works once DeepInfra is topped up (Saiful). |
| S3–S8, S10 | open | | S8 (Adanos key) blocks DEF178. S4 and S7 are Saiful's actions and can be released now. |
| S9 | ✅ ruled | 2026-11-18 | Saiful: "Lets not set a number, but if we need to set it to 60%". WP-53 reports the satisfaction rate without a pass/fail bar; where a bar is required, it is 60% thumbs-up over 100 rated runs. |
| S11 | ✅ approved | 2026-11-18 | Plan: `S11_llm_implementation_plan.md` (rulings §3a). Alpha stays on-prem until Beta; Ling joins WP-10. |
| S12 | ✅ approved | 2026-11-18 | Plan `S12_jev_grader_implementation_plan.md` §0. The rule decides (shadow first on Alpha). **Analyst consensus is the reference, with no human labelling** (Saiful: "didn't we agree to use the current market analysis of the ticker?"). Jev in the test only; ask TypeSafe for terms now. Other 7 recommendations accepted ($50 cap, etc.). |
