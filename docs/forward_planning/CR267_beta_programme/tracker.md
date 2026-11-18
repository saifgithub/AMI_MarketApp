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
| WP-02 | Bring Alpha level with HEAD | WP-00 | done | 2026-11-18 | 2026-11-18 | `440b82dd`; deploys `alpha-2026-11-18-1` `alpha-2026-11-18-2` `alpha-2026-11-19-1` | UAT gate failed on inherited mobile debt; Saiful: promote now, clear it in WP-33 (backend-only). Repeated for deploys #2 and #3. |
| WP-15 | CR252 heuristics fold-in | WP-00 · S11 ✅ | done | 2026-11-18 | 2026-11-18 | `519112f8` | No code: already folded into all 12 personas since `0f41f14e`. My WP-00 note was wrong. |
| WP-10 | Hosted-model shortlist + scorecard | WP-00, WP-15 · S11 ✅ | in progress | 2026-11-18 | | | Sonnet worker running on melehost. Ling-3.0-flash included. Spend ≈$2.56 of the $80 cap. |
| WP-11 | Pin temperature | WP-00 · S11 ✅ | done | 2026-11-18 | 2026-11-18 | `e9e730ab` | CR269. |
| WP-12 | Budget + concurrent-run cap | WP-00 · S11 ✅ | in progress | 2026-11-18 | | `74c15825` `1dce0c03` | CR270. Live on Alpha. DEF488: the $5 ceiling refused everything after deploy #2 (unpriced pre-migration rows); fixed. **Budget stays OFF on Alpha** (harness rows share its DB; output-only rows are unpriced); ON for Beta. |
| WP-13 | Output text guard | WP-00 · S11 ✅ | in progress | 2026-11-18 | | `ca164879` | CR271. Log mode on Alpha. Enforce after a replay of stored replies measures the hit rate. |
| WP-14 | Alpha cut-over + automatic failover | WP-10/11/12 · S2, S11 ✅ | in progress | 2026-11-18 | | `c3924bf9` | CR272. Alpha stays on on-prem (S11 ruling); DeepInfra Qwen3.8-Flash registered as backup. Forced-failover acceptance test still to run. |
| WP-20 | Room baseline | WP-14, WP-21a | not started | | | | |
| WP-21a | Room decides blind | WP-00 | in progress | 2026-11-18 | | | CR275. Split from WP-21 in rev 2. Sonnet worker. |
| WP-21b | Street comparison after verdict | WP-21a, WP-14 | not started | | | | |
| WP-22 | Narrow-question judge + bake-off | WP-20 · **S12** | blocked (gate) | | | | S12 added 2026-11-18. |
| WP-23 | Coded decision rule | WP-22 · S3, **S12** | blocked (gate) | | | | |
| WP-24 | Same inputs → same room | WP-20 | not started | | | | |
| WP-25 | Flip explainer | WP-23, WP-24 | not started | | | | |
| WP-26 | Room acceptance run | WP-21b/23/24/25 | not started | | | | |
| WP-27 | Room reliability defects | WP-00 | done | 2026-11-18 | 2026-11-18 | `636267ae` | DEF444/445/467/471/480/484 + CR272 backup notice. DEF471: the Room auto-starting is intended (10-20 ruling), so only a leave warning was added. |
| WP-28 | Outcome scoring | WP-14 | not started | | | | |
| WP-29 | Copy | WP-00 | in progress | 2026-11-18 | | lane `cc3379c4` | Store listing + website re-led on the learning outcome. Merge + website deploy pending. Sharia line on the website is stale vs claim register N1. |
| WP-30 | Account deletion + export | WP-00 | not started | | | | Beta mode delete/anonymise (§3a.2). |
| WP-31 | 18+ confirmation | WP-00 | done | 2026-11-18 | 2026-11-18 | `6e3e1d25` `06a69250` | CR273. Enforcement switch OFF on Alpha until the new build reaches testers. |
| WP-32 | iOS privacy manifest | WP-00 | done | 2026-11-18 | 2026-11-18 | `e807a598` | CR274. Declares no tracking; must change if personalised ads ever ship (flagged for WP-50). |
| WP-33 | Mobile defect batch | WP-00 | in progress | 2026-11-18 | | lane `453ced12` | 14 of 15 fixed; DEF466 stays open (iOS test-tool behaviour; simulator paused). Flutter suite 2,062 pass on the merge. Part 2: Android device run of the changed cases. |
| WP-34 | Backend defect batch | WP-00 | done | 2026-11-18 | 2026-11-18 | `95f3b2b4` `3c5b66ba` | DEF458–463, DEF468. Filed DEF489 (fixed in WP-35). |
| WP-35 | Security leftovers | WP-00 · S8 | blocked (gate) | 2026-11-18 | | `1d51dc50` | DEF464, DEF489, DEF104 merged. DEF178 waits on S8 (Adanos key rotation). |
| WP-36 | Beta build settings, report, thumbs | WP-23 | not started | | | | |
| WP-37 | CR231 gate items | WP-00 | not started | | | | |
| WP-38 | Trace ID on errors (CR239) | WP-00 | not started | | | | Added at WP-01. |
| WP-39 | App manual corpus (CR022) | WP-00 | in progress | 2026-11-18 | | | Added at WP-01. Sonnet worker. |
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
| S2–S10 | open | | S8 (Adanos key) blocks DEF178. |
| S11 | ✅ approved | 2026-11-18 | Plan: `S11_llm_implementation_plan.md` (rulings §3a). Alpha stays on-prem until Beta; Ling joins WP-10. |
| S12 | open | | Implementation-plan discussion before any Jev/grader change (WP-22, WP-23). Added 2026-11-18. |
