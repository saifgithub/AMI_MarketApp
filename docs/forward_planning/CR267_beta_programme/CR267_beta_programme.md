# CR267 — Beta programme: executable project plan

**What this is:** the work-package plan that takes AMI Trade from the idle state of 2026-11-18 to an external Beta, written to be handed to an executing agent (Opus) with no other context. **Why:** Saiful paused the repo because the Room's agents were not working well; on 2026-11-18 he and the Architect agreed the direction below and he asked for a plan an agent can execute.

Filed 2026-11-18. Status: `proposed` until Saiful says go. Decisions marked "(Saiful, 2026-11-18)" are settled; do not reopen them.

---

## 1. How to execute this plan

1. Read `CLAUDE.md` first. Its rules override anything here that conflicts.
2. Work packages (WPs) are listed in section 5 and detailed in section 6. Take the lowest-numbered WP whose dependencies are `done` and which is not behind an open Saiful gate (section 4).
3. Before starting a WP, mint its child CR (next free number in `docs/forward_planning/_registry/`, check at mint time), write its row file, regenerate with `python3 scripts/registers/gen_registers.py gen cr`, and pathspec-commit. A WP that only fixes listed `DEF###` items uses those IDs instead of a new CR.
4. Record progress in `docs/forward_planning/CR267_beta_programme/progress.md` (create on first use): one dated entry per WP state change, with the commit hash and the acceptance evidence. That file is the hand-over between sessions.
5. A WP is `done` only when every acceptance line is shown with real output. If an acceptance line fails, record the failure and stop that WP; do not soften the criterion.
6. Stop and ask Saiful only at the gates in section 4. Everything else: decide, record the decision in `progress.md`, continue.

## 2. Ground rules for this programme

1. **Feature freeze.** Only work in this plan ships until Beta is live. New ideas go to the register as `proposed`.
2. **The Mac runs nothing.** Backend unit tests only (`pytest backend/tests/unit/ -q`). Everything else goes through `/promote-to-alpha`.
3. **Gates run bare.** Run `scripts/promotion/preflight_suite.sh` un-piped and read `.deliveryos/suite_verdict.json`. Never wrap a gate in a pipe.
4. **Shared checkout.** Commit with an explicit pathspec, message before `--`. Touch only your WP's files. Push `main` after every commit (`git push origin main`, bare). Never force-push.
5. **Degrade loudly.** Every new env-driven setting is forwarded in `docker-compose.yml` (`backend/tests/unit/test_config_compose_parity.py` enforces it). No silent fallbacks: if a grader, model or feed is down, the user sees an honest state.
6. **Prompts are not controls.** Anything that must hold is done in code or by removing data at the source.
7. **User-visible text says AMI**, never "the AI". Use the CR160 titles (CIO, Risk Officer, Execution Desk…) in copy and messages.
8. **Workers.** Refactors of shared hot paths (`room_runner.py`, `llm_gateway.py`) run the full backend suite before merge. Accept a worker's result by git diff and test exit code, never by its report.
9. **Remote hosts.** melehost is ours. Any new host (the Beta server) needs Saiful's explicit go per step.
10. **Measurements.** State a number only if measured in that session or cite the file it came from. Mark estimates as estimates.

## 3. Decisions already made (Saiful, 2026-11-18)

1. **Beta definition:** external TestFlight + Play closed testing, from company store accounts, on a newly allocated Beta host, hosted LLM, payments parked, English only, credits free.
2. **Company is Malaysia-based.** Beta runs on the cheapest sensible host first; an accelerator or affiliate programme is joined to unlock cloud credits before the production cloud is chosen. GCP Cloud Run + Supabase (D-066/D-067) is reopened, not assumed.
3. **Hosted LLM:** open-weight model through the existing DeepInfra account; the switch must be configuration only; one model for every desk; at most 5 US cents and under 2 minutes per Room; on-prem vLLM kept as fallback.
4. **Room design:** keep the desks. Replace the CIO's 5-sample vote with a judge that answers narrow typed questions, plus a coded rule that decides. First action set: Approve / Pass / Contested.
5. **Consistency means:** a verdict changes only when its inputs change, and every change comes with a computed explanation.
6. **Reference for "correct":** analyst consensus. The Room decides blind (consensus removed from its inputs) and the Street comparison is shown after the verdict. A reasoned pass on a Street-Buy name is acceptable; approving a Street Sell/Underperform name is the error.
7. **Jev** (TypeSafe System One, third-party API) is a candidate judge only. We hold trial access. It must win the bake-off in WP-22 and have written vendor terms before it carries production decisions.
8. **Account closure:** deactivate at once, restorable 30 days, then a full access-locked archive. The UI and Terms say "close account", never "delete", until counsel rules (gate S6).
9. **Age gate:** one "I am 18 or older" confirmation; no birth date stored.
10. **No features hidden in Beta** (Alpaca paper, Sharia screen, options simulator stay visible).
11. **DEF178:** closed by Saiful rotating the key at the vendor. No history rewrite.
12. **Beta cohort:** 20–200 testers from personal network, website waitlist, investing communities, YouTube audience. Length 6–12 weeks. Exit criteria in WP-53.

## 4. Saiful gates (stop here and ask)

| Gate | Needed before | What Saiful does |
|---|---|---|
| S0 | any WP | Says go on this plan. |
| S1 | WP-01 | Answers the CR/Defect review questions live (`/daily-cr-def-review`). |
| S2 | WP-14 | Picks the hosted model from the WP-10 scorecard. |
| S3 | WP-23 | Picks the grader from the WP-22 bake-off scorecard; if Jev, obtains vendor terms. |
| S4 | WP-42 | Confirms the Beta host choice, opens the account, creates the server, gives go for SSH work. |
| S5 | WP-40 result | Picks the accelerator / credit programmes and applies. |
| S6 | WP-30 release to testers | Gets counsel's ruling on archive-instead-of-delete. |
| S7 | WP-50 | Confirms company Apple/Google accounts are enrolled and usable. |
| S8 | WP-35 | Rotates the Adanos key at the vendor (closes DEF178). |
| S9 | WP-53 | Confirms the Room satisfaction bar (proposed: 70% positive over 100 rated runs). |

## 5. Work packages

Model column: suggested worker tier (Opus = load-bearing, Sonnet = standard). "Lane" follows `orchestration/dispatch/DISPATCH_PROTOCOL.md`.

| WP | Title | Depends on | Gate | Model |
|---|---|---|---|---|
| WP-00 | Re-entry: registers, CR266 result, plan and decision log | — | S0 | Sonnet |
| WP-01 | Register decision review | WP-00 | S1 | interactive |
| WP-02 | Bring Alpha level with HEAD | WP-00 | — | Sonnet |
| WP-10 | Hosted-model shortlist and scorecard | WP-00 | — | Opus |
| WP-11 | Pin temperature and sampling in config | WP-00 | — | Sonnet |
| WP-12 | LLM budget cap and per-user concurrent-run cap | WP-00 | — | Sonnet |
| WP-13 | Output text guard on agent text | WP-00 | — | Opus |
| WP-14 | Cut Alpha over to the hosted model | WP-10, WP-11, WP-12 | S2 | Sonnet |
| WP-20 | Room baseline on the chosen model | WP-14 | — | Sonnet |
| WP-21 | Room decides blind; Street comparison after verdict | WP-14 | — | Opus |
| WP-22 | Narrow-question judge and three-grader bake-off (offline) | WP-20 | — | Opus |
| WP-23 | Coded decision rule, CONTESTED, CIO narrates | WP-22 | S3 | Opus |
| WP-24 | Same inputs return the same room | WP-20 | — | Opus |
| WP-25 | Flip explainer | WP-23, WP-24 | — | Sonnet |
| WP-26 | Room acceptance run | WP-21, WP-23, WP-24, WP-25 | — | Opus |
| WP-27 | Room reliability defects | WP-00 | — | Sonnet |
| WP-28 | Turn on outcome scoring | WP-14 | — | Sonnet |
| WP-29 | Copy: stop leading with "12 analysts" | WP-00 | — | Sonnet |
| WP-30 | Account closure and data export | WP-00 | S6 to release | Opus |
| WP-31 | 18+ confirmation | WP-00 | — | Sonnet |
| WP-32 | iOS privacy manifest | WP-00 | — | Sonnet |
| WP-33 | Mobile defect batch | WP-00 | — | Sonnet |
| WP-34 | Backend defect batch | WP-00 | — | Sonnet |
| WP-35 | Security leftovers | WP-00 | S8 for DEF178 | Opus |
| WP-36 | Beta build settings, report button, Room thumbs | WP-23 | — | Sonnet |
| WP-37 | Close the CR231 gate items | WP-00 | — | Sonnet |
| WP-40 | Accelerator and credit-programme research | WP-00 | — | Sonnet |
| WP-41 | Beta environment configuration | WP-14 | — | Sonnet |
| WP-42 | Provision and harden the Beta host | WP-41 | S4 | Opus |
| WP-43 | Real `/promote-to-beta` and `/rollback-beta` | WP-42 | — | Opus |
| WP-44 | Beta backups, monitoring, alerts | WP-42 | — | Sonnet |
| WP-45 | Beta URL in the mobile build scripts | WP-41 | — | Sonnet |
| WP-46 | Load test and drills | WP-43, WP-44 | — | Sonnet |
| WP-50 | Store records, listing, review notes | WP-36 | S7 | Sonnet |
| WP-51 | Website waitlist | WP-00 | — | Sonnet |
| WP-52 | Tester onboarding note and support inbox | WP-00 | — | Sonnet |
| WP-53 | Exit-criteria report | WP-36, WP-46 | S9 | Sonnet |
| WP-54 | Beta go-live | WP-26, WP-30…37, WP-46, WP-50, WP-52, WP-53 | — | Architect |

Parallelism: after WP-00, the Phase 3 packages (WP-27, WP-29…35, WP-37), WP-40, WP-51 and WP-52 are independent of the Room work and of each other. WP-10…13 run together. The Room chain WP-20 → 22 → 23 → 25 → 26 is the critical path.

## 6. Work-package detail

### Phase 0 — Re-entry

**WP-00 Re-entry**

1. Goal: the registers and roadmap tell the truth again.
2. Steps:
   1. Find out whether the corrected CR266 60-room run finished on melehost (`ssh melehost`, look under the harness output folder named in `docs/forward_planning/CR266_decision_reliability/progress.md`). Record the result, or "never completed", in that file.
   2. Fix stale row statuses: CR252, CR253, CR255, CR256, CR257, CR259 (executed, still `proposed`). Source: `docs/Research/decision_consistency_programme_stocktake_2026-10-20.md`. Mark CR251, CR254, CR265, CR266 as superseded by this programme where their goal was the approval curve.
   3. Append decisions to `docs/initial_specs/11_decisions/decision_log.md`, one per item in section 3 (next free D-numbers). Note that D-066/D-067 are reopened and D-068 is closed by decision 3.
   4. Rewrite the status block and Beta section of `docs/initial_specs/10_delivery/project_plan.md` to point at this plan.
   5. Resolve the dirty tree left from October: the deleted `CR253_tm_all_salvage_conversion.md` and the untracked checkpoint memos and harness files. Commit what is real, restore what was deleted by accident; do not discard another track's work without reading it.
3. Acceptance: `python3 scripts/registers/gen_registers.py gen all` leaves no diff after commit; `git status --short` is empty; the six stale rows read `done` or `dropped` with a reason.

**WP-01 Register decision review (gate S1)**

1. Run `/daily-cr-def-review` with Saiful present. Bring a close / keep / defer / drop recommendation for each `proposed` CR and `open` defect, judged against the freeze.
2. Acceptance: a dated section in `docs/governance/daily_cr_def_review_log.md`; every open item has a decision.

**WP-02 Bring Alpha level with HEAD**

1. Alpha runs `alpha-2026-10-19-1`; a handful of `backend/app` files changed since. Run `/promote-to-alpha`.
2. Acceptance: `curl -s https://api-alpha.agenticmarketintel.ai/v1/health` shows the new tag and HEAD's SHA; postflight green.

### Phase 1 — Hosted LLM

**WP-10 Shortlist and scorecard**

1. Goal: evidence for Saiful to pick one hosted model.
2. Context: `docs/forward_planning/CR240_llm_provider_evaluation/CR240.md`; harness `docs/tools/room_investigation_V2/` (read its `README.md` and `EXPERIMENT_LOG.md`); gateway `backend/app/services/llm_gateway.py`. The vLLM provider slot is OpenAI-compatible: `VLLM_BASE_URL`, `VLLM_MODEL`, `VLLM_API_KEY` point it at DeepInfra with no code change. Confirm that with one call before anything else.
3. Steps:
   1. Read DeepInfra's live model catalogue. Shortlist three non-abliterated open-weight models: the current Qwen flash-class model, DeepSeek-V4-Flash, and one other fast model. Record each licence's position on commercial use.
   2. For each, run the harness on the 30-ticker universe at risk 2 and risk 4, two reps, with veto and resurrection reviews ON (production setting), temperature pinned.
   3. Score: contract gates (`tools/room_contract_gates.py`), grounding of cited figures (`tools/jev_score_runs.py`, `figures_consistent`), minutes per Room, cost per Room from the provider's usage figures, error rate over the run.
3. Out of scope: the approval curve. The desk writer no longer owns the verdict.
4. Acceptance: `docs/forward_planning/CR240_llm_provider_evaluation/scorecard_<date>.md` with one row per model and a recommendation against the bars (zero gate failures, under 2 minutes, at most 5 cents, licence clear). If no model reaches 2 minutes, say where the time goes per phase.

**WP-11 Pin temperature and sampling**

1. Production runs at the server default (1.0). Add explicit settings in `backend/app/core/config.py`, apply them in the gateway for every desk call, forward in `docker-compose.yml`.
2. Acceptance: unit test proving the request body carries the configured temperature; compose-parity test green.

**WP-12 Budget cap and concurrent-run cap**

1. A daily spend ceiling on the hosted provider (count tokens from responses; on breach, Rooms return an honest "temporarily unavailable" state and an alert fires) and a per-user limit of one Room in flight (left over from DEF186).
2. Acceptance: unit tests for both; breach state is visible in the stream, not a fake verdict.

**WP-13 Output text guard**

1. A deterministic check on user-visible agent text before it is streamed or stored: personalised-advice phrasing ("you should buy"), content unrelated to markets, unsafe content. On a hit, replace the turn with a labelled sentinel and log it. Start in log-only mode behind a setting; measure the hit rate on a week of Alpha traffic; then enforce.
2. Acceptance: unit tests with positive and negative examples; hit-rate note in `progress.md` before enforcement is switched on.

**WP-14 Cut Alpha over (gate S2)**

1. Set the three vLLM variables in `infra/alpha.env` to the chosen model; register on-prem as the fallback provider; promote.
2. Update the runtime table in `CLAUDE.md` (model, where it runs, what the alias resolves to).
3. Acceptance: one live Room on Alpha completes; `llm_audit` rows show the hosted model; a forced provider failure produces the labelled fallback, not a silent one.

### Phase 2 — The Room

Read first: `docs/Research/decision_consistency_programme_stocktake_2026-10-20.md`, `docs/forward_planning/CR257_jev_decision_arm/spec.md` (§7–§8), `docs/forward_planning/CR255_decision_consistency/jev_deep_dive_2026-10-14.md`, `docs/forward_planning/CR266_decision_reliability/`. Known facts: prompt rewrites do not fix consistency; Jev repeats itself on the same transcript (299 of 300) but nobody has shown its calls are right; the debate itself varies between fresh runs.

**WP-20 Baseline on the chosen model**

1. Run the 30-ticker × 5-risk matrix, two reps, production settings. Freeze the result as `docs/forward_planning/CR267_beta_programme/room_baseline_<model>.md` in the format of `docs/forward_planning/CR251_risk_monotonicity_matrix/BASELINE.md`. Keep the raw runs; WP-22 reuses them.
2. Acceptance: the baseline file states approvals per risk level, flip count across reps, minutes and cost per Room, and the gate report.

**WP-21 Room decides blind; Street comparison after the verdict**

1. Remove analyst consensus ratings and price targets from the Room's fact sheet at the source (the pattern CR038 used for synthetic macro fields), so no desk and no judge can see them.
2. After the verdict, attach a computed comparison to the result: Street rating, the Room's action, and the reasons from the narrow answers when they differ. CR260 (analyst price targets) is re-scoped to this display.
3. Mobile: show it on the verdict card.
4. Acceptance: a unit test that fails if any consensus field appears in a desk prompt; a Room on Alpha shows the comparison after the verdict; consensus data is labelled internal-evaluation-only until a licensed source exists.

**WP-22 Narrow-question judge and bake-off (offline, no production change)**

1. Write the question set: five or six typed questions unbundled from the CR257 rubric, each checkable by a person reading the room. Starting set: is the bear's strongest objection answered with numbers; is there a named catalyst inside the mandate horizon; is there an unresolved terminal vulnerability; does event risk argue for waiting; is thesis support material and directional; did the desk propose a trade. Version the file.
2. Build one grader interface with three implementations: Jev (`tools/jev_v1_pilot.py` shows the call shape; pin the version, never `latest`); the WP-14 hosted model at temperature 0 with constrained answers and token probabilities; and plain code over CR266 typed cards for any question that can be computed.
3. Run all three over the WP-20 rooms. Score each:
   1. Consensus scores (via `backend/scripts/room_benchmark.py` and `room_benchmark_report.py`, `tickers_150.txt`): approvals of Street Sell/Underperform names; share of approvals that are Street Buy per risk level; rank correlation of the decision score with the consensus score. Report the CIO's numbers on the same rooms beside them.
   2. Wording test: each question in five phrasings; share of answers that change.
   3. Input tests with known answers: planted fatal flaw must give pass; removing the bear's evidence must not make the answer more cautious; strengthening the bear's numbers must lower the score; reordering turns and renaming the ticker must change nothing.
   4. Fresh-room stability: disagreement across the two reps of the same ticker and risk level.
   5. Cost and latency per Room; control (version pin, visible prompt, switchable vendor).
4. Acceptance: `docs/forward_planning/CR267_beta_programme/grader_bakeoff_<date>.md` with the table, the failures listed by question, and a recommendation. No recommendation of Jev without noting that vendor terms are still owed.

**WP-23 Coded decision rule (gate S3)**

1. In `backend/app/services/room_runner.py`, behind a new setting (default off): after the debate, call the chosen grader, combine the answers with a written rule per risk level, and emit Approve / Pass / Contested. Contested covers the band where answers are close and lists which questions were close.
2. Fit rule weights and bands on the WP-20 rooms; store them as versioned policy (reuse the shape of `room_evidence_gate_thresholds_json` in `config.py` rather than inventing a new one).
3. The CIO becomes a single narration call that explains the computed decision; it cannot change it. The deterministic mandate compliance check still runs last and stays as it is.
4. Grader down or erroring: the Room ends in a visible "decision unavailable" state. Never a default verdict.
5. Full backend suite before merge (shared hot path).
6. Acceptance: unit tests for the rule, the Contested band, the unavailable state, and that narration cannot alter the action; flag on in Alpha produces a Room whose stored record contains every answer and the rule version.

**WP-24 Same inputs return the same room**

1. Freeze the fact sheet per ticker per trading day. Key a room on (ticker, mandate snapshot, fact-sheet hash, policy version). A convene with an existing key returns the banked room; state plainly in the UI that inputs are unchanged since the last run.
2. Decide and document what happens to credits on a banked return (recommended: no charge).
3. Acceptance: two convenes with identical inputs return the identical room ID in 100% of a 50-pair test; changing any keyed input produces a new room.

**WP-25 Flip explainer**

1. When a user's verdict on a ticker differs from their previous one, compute and store a diff: which inputs changed (price, news, filings, mandate), which desk claims changed, which narrow answer changed. Built from stored fields in code; no agent writes it.
2. Mobile: show it on the verdict card and in the Journal.
3. Acceptance: a forced input change yields a flip whose explainer names at least one changed input and one changed answer; a unit test rejects a flip stored without an explainer.

**WP-26 Room acceptance run**

1. Fresh 30-ticker × 5-risk run, two reps, all of WP-21/23/24/25 on.
2. Gates, judged by the letter: identical inputs return the identical room (100%); every verdict change carries a non-empty explainer; consensus scores at or above the CIO baseline from WP-22; wording and input tests still pass; zero holdout approvals (the RIOT / APD / BA shapes from CR257); zero contract-gate failures. Report the fresh-run flip rate as a diagnostic only.
3. Pass: turn the setting on for Alpha and Beta. Fail: leave it off, label the Room "experimental" in the app, stop tuning, and record which gate failed. Then raise the Room Lite option below with Saiful.
4. Acceptance: `docs/forward_planning/CR267_beta_programme/room_acceptance_<date>.md` with each gate's measured value and a single PASS or FAIL.

**WP-27 Room reliability defects**

1. DEF484 (verdict never shown after "Reconnect timed out"), DEF467 (streams stall with no keepalive: add heartbeats to Room, 1-on-1 and Brief streams), DEF471 (credits spent with no confirmation), DEF480 (ticker dropped on convene), DEF444 (checkpoint write blocks the event loop).
2. Acceptance: each defect's row moved to `fixed` with its test; a device run on the Android rig shows a verdict after a forced reconnect.

**WP-28 Outcome scoring**

1. 6,743 verdicts are banked and none scored. Schedule `backend/scripts/score_verdict_outcomes.py` on Alpha; make `room_outcome_report.py` part of the weekly report.
2. Acceptance: scored rows exist; the report runs unattended.

**WP-29 Copy**

1. Store listing draft (`marketing/users/assets/store_listing_copy.md`) and `website/`: lead with the learning outcome; the Room is the practice arena, described as a simulated desk. No claim about picking stocks or performance.
2. Acceptance: no "12 AI analysts" headline remains; website deployed with a cache-bust.

**Room Lite (only if WP-26 fails or WP-10 cannot reach 2 minutes; needs Saiful's go)**

Keep all twelve voices on screen and cut the calls: one structured Research call renders the Bull, Bear and Research Manager voices, as CR201 did for the risk debators. Gate it against the WP-20 baseline with the same harness before it replaces anything.

### Phase 3 — App fixes before external testers

**WP-30 Account closure and data export (release gated by S6)**

1. Backend: routes to close an account (deactivate and revoke sessions at once; restorable for 30 days; then a scheduled job moves the full record to an access-locked archive) and to export the user's data as a downloadable file. Make the post-grace step a setting with three modes (archive, anonymise, delete) so counsel's answer is a configuration change.
2. Mobile: Settings → Close account, and Settings → Export my data.
3. Wording everywhere says "close account" and states what is kept and for how long. Update `legal/policies/terms_of_service.md` §10 and the privacy and data-deletion policies to match; they are still DRAFT.
4. Acceptance: closed account cannot sign in after the grace period; restore works inside it; export contains the user's trades, rooms, mandate and progress; device run on the rig. Do not ship to external testers before S6.

**WP-31 18+ confirmation**

1. One step in onboarding (`mobile/lib/screens/onboarding`); store a timestamped boolean, no birth date.
2. Acceptance: onboarding cannot complete without it; widget test.

**WP-32 iOS privacy manifest**

1. Add `PrivacyInfo.xcprivacy` to the Runner target, consistent with the SDKs in `mobile/pubspec.yaml`.
2. Acceptance: release build succeeds; manifest present in the archive.

**WP-33 Mobile defect batch**

1. DEF473 (update button dead when `storeUrl` is empty), DEF478 (hardcoded English), DEF483 (stray backslash), DEF472, DEF477, DEF479, DEF474, DEF475, DEF476, DEF466, DEF486.
2. Acceptance: rows `fixed` with tests; `flutter analyze` and `flutter test` green.

**WP-34 Backend defect batch**

1. DEF458, DEF462, DEF463 (500s on bad input), DEF461 (sim news dark on Alpha), DEF468 (null candles), DEF459, DEF460.
2. Acceptance: rows `fixed` with tests; suite gate green.

**WP-35 Security leftovers**

1. DEF104 (plaintext mailbox credential in the support-KB scripts on melehost), DEF464 (rate limiter trusts client-supplied headers: `backend/app/services/rate_limit.py`).
2. DEF178: after gate S8, verify the old key is rejected by the vendor, then close the row and CR123. No history rewrite.
3. Acceptance: rows `fixed`; a spoofed header no longer changes the limiter's key (unit test).

**WP-36 Beta build settings**

1. English-only locale for Beta builds; credits free; paywall remains the information card.
2. "Report this response" on agent output, feeding the existing bug-report path.
3. After each Room: "Did the verdict and its reasons make sense?" thumbs up or down, stored with the room ID.
4. Acceptance: Beta build shows no AR/MS switch; a report and a thumbs rating both arrive in the database from the rig.

**WP-37 CR231 gate items**

1. Close CR221, CR222, CR228 per `docs/forward_planning/CR245_beta_infra_1000_user_sizing/` §12. Run the E5 device matrix (`docs/forward_planning/CR004_release_readiness/e5_device_matrix_runbook.md`) on the Android rig; list the iPhone steps for Saiful.
2. Acceptance: rows closed; matrix results recorded.

### Phase 4 — Beta infrastructure

Position: recommended, not yet discussed in depth with Saiful. Gate S4 confirms it. Comparison and sources are in the planning record (`/Users/saiful/.claude/plans/i-have-neglected-this-inherited-cray.md`); copy that table into this folder as `hosting_comparison_2026-11-18.md` during WP-40. Re-check every price and limit on the vendor's own page before money is spent.

Recommendation: one Singapore VPS (2 vCPU / 4 GB) running the same Docker Compose stack as Alpha, Cloudflare Tunnel in front. Cheapest option found, no code change, and Beta becomes a second target for the pipeline that already works. Vercel does not fit this backend; Cloudflare stays in front but is not the host.

**WP-40 Accelerator and credit research**

1. Find accelerators and affiliate programmes open to a Malaysia-based company that are approved partners for the Google, Alibaba, AWS and Microsoft startup tiers: eligibility, deadlines, what they unlock. List the tiers needing no backer (Cloudflare for Startups, Google Start, Huawei, Microsoft Founders Hub) and each programme's rule on existing accounts.
2. Acceptance: `credits_and_accelerators_<date>.md` in this folder, with sources, for gate S5.

**WP-41 Beta environment configuration**

1. Add `beta` to the allowed `ENV` values in `backend/app/core/config.py`. Create `infra/beta.env.example` (no secrets) listing every key Beta needs: fresh `SECRET_KEY`, hosted-LLM keys, no on-prem address. Check that nothing in the code assumes `staging` or `prod` only.
2. Beta starts with an empty database built the same way Alpha's was. DEF421 is not a Beta blocker on this path; it stays open as a blocker for any managed Postgres (production).
3. Acceptance: unit tests green with `ENV=beta`; compose config renders with the example env.

**WP-42 Provision and harden the host (gate S4)**

1. After Saiful creates the server: SSH keys only, inbound firewall closed (the tunnel is the only entry), unattended security updates, Docker at the version melehost runs. New Cloudflare Tunnel at `api-beta.agenticmarketintel.ai`.
2. Acceptance: no open inbound port from outside; `/v1/health` over the public hostname returns `env=beta`.

**WP-43 `/promote-to-beta` and `/rollback-beta`**

1. Parameterise the host in `scripts/promotion/` and write the two commands by adapting `.claude/commands/promote-to-alpha.md` and `rollback-alpha.md`. Beta promotes an existing `alpha-*` tag, never HEAD. Replace the stale stubs. Mark `.github/workflows/deploy-beta.yml` and `infra/gcp/` as parked.
2. Acceptance: one promotion and one rollback performed end to end; identity stamp correct in `/v1/health` after each.

**WP-44 Backups, monitoring, alerts**

1. Nightly encrypted backup with `infra/backups/pg-backup.sh`, copied off the server; Sentry DSN set for backend and app; external uptime check; alerts on 5xx rate, LLM spend and Room failure rate; reuse `infra/watchdog/` for the tunnel.
2. Acceptance: one restore drill recorded with timings; a test alert received.

**WP-45 Beta URL in the mobile build scripts**

1. `scripts/build_testflight.sh` and `scripts/build_playstore.sh` bake only the Alpha URL today. Add the Beta URL and a flag selecting the Beta channel; backend-switching stays off in Beta builds.
2. Acceptance: a Beta build talks to the Beta hostname and cannot be switched to Alpha.

**WP-46 Load test and drills**

1. Run the k6 script in `infra/loadtest/` at the invited-cohort size, including concurrent Rooms. Resize the server if needed. One rollback drill.
2. Acceptance: results file in this folder; drill recorded.

### Phase 5 — Launch

**WP-50 Store records, listing, review notes (gate S7)**

1. App records under the company accounts (CR258), English listing, screenshots from the rig, Apple privacy labels, Play Data Safety form. Review notes that explain: simulation only, no real orders, Alpaca is paper-only, the Sharia screen makes no certification claim, how to reach account closure.
2. Acceptance: TestFlight external build accepted by Beta App Review; Play closed track live.

**WP-51 Website waitlist**

1. Sign-up form on `website/` writing to the existing website API; batch-invite export.
2. Acceptance: a test sign-up appears in the export; deployed with cache-bust.

**WP-52 Tester onboarding note and support inbox**

1. One-page note (what the app is, what is simulated, how to report a problem, how to close the account). A monitored support address; finish the outstanding email DNS work (A3).
2. Acceptance: test mail delivered both ways.

**WP-53 Exit-criteria report (gate S9)**

1. A script producing the weekly Beta report from real data:
   1. Crash-free sessions ≥ 99%.
   2. Room completes with a shown verdict in ≥ 95% of runs.
   3. WP-26 gates still hold on the weekly harness run.
   4. Room satisfaction ≥ the bar from S9 over at least 100 rated runs.
   5. Zero open defects in security, data loss or money categories.
   6. At least 20 testers active over 14 days; day-7 retention reported.
   7. One rollback drill and one restore drill on record.
2. Acceptance: the report runs unattended and every line is computed, none typed by hand.

**WP-54 Beta go-live**

1. Invite the personal-network wave first so Play's 12-testers-for-14-days clock starts; open the other channels as they are ready. Arm `/loop 6h /bug-monitor`. One Beta build a week.
2. Beta runs 6 to 12 weeks and ends once every WP-53 line has held for 14 days in a row. At week 12, any red line goes to Saiful for an explicit decision.

## 7. Not in this plan (public-release backlog, do not start)

Counsel review of the legal documents; a licensed market-data source to replace yfinance (CR007); payments or free-with-ads; ads verification (CR225/CR226); the production cloud, managed Postgres and DEF421; moving background loops out of the API process; independent security re-review; analytics; AR/MS languages; content verification (CR060); Buy / Hold / Sell actions. These were listed on 2026-11-18 but not discussed; they become their own plan after Beta starts.

## 8. Known unknowns

1. Whether the corrected CR266 run ever finished (WP-00 answers it).
2. Whether any DeepInfra model reaches 2 minutes per Room with the debate run in sequence (WP-10 answers it).
3. Whether any grader beats the CIO on the consensus scores (WP-22 answers it). If none does, WP-23 still buys consistency and explanation, and the report must say plainly that correctness is unproven.
4. Jev's price, uptime and data-retention terms.
5. Counsel's view on archiving closed accounts.
6. Vendor prices and limits in the hosting comparison that came from third-party pages.
