# CR267 — Beta programme: executable project plan

**What this is:** the work-package plan that takes AMI Trade from the idle state of 2026-11-18 to an external Beta, written to be handed to an executing agent (Opus) with no other context. **Why:** Saiful paused the repo because the Room's agents were not working well; on 2026-11-18 he and the Architect agreed the direction below and he asked for a plan an agent can execute.

Filed 2026-11-18. Status: `proposed` until Saiful says go. Decisions marked "(Saiful, 2026-11-18)" are settled; do not reopen them.

**Rev 2 (2026-11-18):** this revision takes in the executor's pre-execution questions
([`questions_for_plan_author_2026-11-18.md`](questions_for_plan_author_2026-11-18.md)) and the
author's answers ([`answers_from_plan_author_2026-11-18.md`](answers_from_plan_author_2026-11-18.md)).
Saiful answered the open items the same day (§3a). Two facts remain to confirm: what is done on the company accounts (WP-01, WP-49) and the Play account type (S7).

---

## 1. How to execute this plan

1. Read `CLAUDE.md` first. Its rules override anything here that conflicts.
2. Work packages (WPs) are listed in section 5 and detailed in section 6. Take the lowest-numbered WP whose dependencies are `done` and which is not behind an open Saiful gate (section 4).
3. Before starting a WP, mint its child CR (next free number in `docs/forward_planning/_registry/`, check at mint time), write its row file, regenerate with `python3 scripts/registers/gen_registers.py gen cr`, and pathspec-commit. A WP that only fixes listed `DEF###` items uses those IDs instead of a new CR.
4. Record progress in `docs/forward_planning/CR267_beta_programme/progress.md` (create on first use): one dated entry per WP state change, with the commit hash and the acceptance evidence. That file is the hand-over between sessions. Update `tracker.md` (plan vs actual, one row per WP, deviations listed) at the same time.
5. A WP is `done` only when every acceptance line is shown with real output. If an acceptance line fails, record the failure and stop that WP; do not soften the criterion.
6. Stop and ask Saiful only at the gates in section 4. Everything else: decide, record the decision in `progress.md`, continue.

## 2. Ground rules for this programme

1. **Feature freeze.** Only work in this plan ships until Beta is live. New ideas go to the register as `proposed`.
2. **The Mac runs nothing.** Backend unit tests only (`pytest backend/tests/unit/ -q`). Everything else goes through `/promote-to-alpha`.
3. **Gates run bare.** Run `scripts/promotion/preflight_suite.sh` un-piped and read `.deliveryos/suite_verdict.json`. Never wrap a gate in a pipe.
4. **Branch, not `main` (Saiful, 2026-11-18).**
   1. All CR267 work happens on branch `beta/cr267`, in the worktree `.claude/worktrees/cr267-beta`. Never in the shared `main` checkout.
   2. Commit with an explicit pathspec, message before `--`. Touch only your WP's files. Push the branch after every commit (`git push origin beta/cr267`, bare). Never force-push.
   3. Merge `main` into the branch before minting a CR/DEF ID (the registry must be current) and before every promotion.
   4. While CR267 runs, Alpha is promoted only from the branch. Anything that lands on `main` reaches Alpha by being merged into the branch first.
   5. The branch merges to `main` at two points, each on Saiful's go: after WP-26 (Room acceptance) and at WP-54 (go-live).
   6. Rollback point: tag `pre-cr267` on `main`.
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

## 3a. Decisions from the rev 2 questions (Saiful, 2026-11-18)

1. **Automatic LLM failover, amending decision 3.** The hosted model is primary. A provider failure fails over automatically, in code: on Alpha to the on-prem vLLM, on Beta to a second DeepInfra model. External testers never get the abliterated on-prem build. A fallback verdict is labelled as such in the stream and in the stored record. If both providers are down, the Room shows "temporarily unavailable". Switching the primary model stays configuration only.
2. **Account closure:** Beta ships in `delete` or `anonymise` post-grace mode, with the button reading "Delete account". Switch to `archive` only if counsel approves (S6). S6 is off the launch path.
3. **Street rating:** shown to Beta testers after the verdict, with a source label, behind a setting.
4. **LLM spend:** $100 account cap for the measurement runs. Daily ceiling as a setting: $10/day Beta, $5/day Alpha.
5. **Track:** the executing session commits as track B, `(AT:B<N> CR###)`, numbered per session.
6. **Track K (Kimi) is closed.** WP-00 reads its leftovers, commits the clean ones under K's tag, and supersedes CR266.

## 4. Saiful gates (stop here and ask)

| Gate | Needed before | What Saiful does |
|---|---|---|
| S0 | any WP | Says go on this plan. |
| S1 | WP-01 | Answers the CR/Defect review questions live (`/daily-cr-def-review`). |
| S2 | WP-14 | Picks the hosted model from the WP-10 scorecard. |
| S3 | WP-23 | Picks the grader from the WP-22 bake-off scorecard; if Jev, obtains vendor terms. |
| S4 | WP-42 | Confirms the Beta host choice, opens the account, creates the server, gives go for SSH work. |
| S5 | WP-40 result | Picks the accelerator / credit programmes and applies. |
| S6 | WP-30 release to testers | Gets counsel's ruling on archive-instead-of-delete, plus the Singapore cross-border transfer under Malaysia's PDPA. Only this narrow question; the full legal review stays in §7. Off the launch path: Beta ships in `delete`/`anonymise` mode (§3a.2), and S6 is needed only to switch to `archive`. |
| S7 | WP-49 | Confirms company Apple/Google accounts are enrolled and usable, and whether the Play account is an organisation account. |
| S8 | WP-35 | Rotates the Adanos key at the vendor (closes DEF178). |
| S9 | WP-53 | Confirms the Room satisfaction bar. **Ruled 2026-11-18:** no fixed number; report the rate. Where a bar is required, it is 60% thumbs-up over 100 rated runs. |
| S10 | Room Lite | Gives go on Room Lite. Not on the Beta launch path. |
| S11 | WP-15, WP-10…WP-14 | Discusses and approves the implementation plan for the hosted-LLM work before any change (Saiful, 2026-11-18: "before you start making changes for JEV and the LLM, please pause so we can discuss implementation plans"). |
| S12 | WP-22, WP-23 | The same, for the Jev / grader / coded-rule work. |

## 5. Work packages

Model column: suggested worker tier (Opus = load-bearing, Sonnet = standard). "Lane" follows `orchestration/dispatch/DISPATCH_PROTOCOL.md`.

| WP | Title | Depends on | Gate | Model |
|---|---|---|---|---|
| WP-00 | Re-entry: registers, CR266 result, plan and decision log | — | S0 | Sonnet |
| WP-01 | Register decision review | WP-00 | S1 | interactive |
| WP-02 | Bring Alpha level with HEAD | WP-00 | — | Sonnet |
| WP-15 | CR252 institutional-heuristics fold-in (setting-gated) | WP-00 | S11 | Sonnet |
| WP-10 | Hosted-model shortlist and scorecard | WP-00, WP-15 | — | Opus |
| WP-11 | Pin temperature and sampling in config | WP-00 | — | Sonnet |
| WP-12 | LLM budget cap and per-user concurrent-run cap | WP-00 | — | Sonnet |
| WP-13 | Output text guard on agent text | WP-00 | — | Opus |
| WP-14 | Cut Alpha over to the hosted model, with automatic failover | WP-10, WP-11, WP-12 | S2 | Opus |
| WP-20 | Room baseline on the chosen model | WP-14, WP-21a | — | Sonnet |
| WP-21a | Room decides blind: consensus removed at source | WP-00 | — | Opus |
| WP-21b | Street comparison after the verdict | WP-21a, WP-14 | — | Sonnet |
| WP-22 | Narrow-question judge and three-grader bake-off (offline) | WP-20 | — | Opus |
| WP-23 | Coded decision rule, CONTESTED, CIO narrates | WP-22 | S3 | Opus |
| WP-24 | Same inputs return the same room | WP-20 | — | Opus |
| WP-25 | Flip explainer | WP-23, WP-24 | — | Sonnet |
| WP-26 | Room acceptance run | WP-21b, WP-23, WP-24, WP-25 | — | Opus |
| WP-27 | Room reliability defects | WP-00 | — | Sonnet |
| WP-28 | Turn on outcome scoring | WP-14 | — | Sonnet |
| WP-29 | Copy: stop leading with "12 analysts" | WP-00 | — | Sonnet |
| WP-30 | Account closure and data export | WP-00 | S6 only for `archive` | Opus |
| WP-31 | 18+ confirmation | WP-00 | — | Sonnet |
| WP-32 | iOS privacy manifest | WP-00 | — | Sonnet |
| WP-33 | Mobile defect batch | WP-00 | — | Sonnet |
| WP-34 | Backend defect batch | WP-00 | — | Sonnet |
| WP-35 | Security leftovers | WP-00 | S8 for DEF178 | Opus |
| WP-36 | Beta build settings, report button, Room thumbs | WP-23 | — | Sonnet |
| WP-37 | Close the CR231 gate items | WP-00 | — | Sonnet |
| WP-38 | Trace ID on every error, shown to the user (CR239) | WP-00 | — | Sonnet |
| WP-39 | App manual corpus for the Concierge (CR022) | WP-00 | — | Sonnet |
| WP-40 | Accelerator and credit-programme research | WP-00 | — | Sonnet |
| WP-41 | Beta environment configuration | WP-14 | — | Sonnet |
| WP-42 | Provision and harden the Beta host | WP-41 | S4 | Opus |
| WP-43 | Real `/promote-to-beta` and `/rollback-beta` | WP-42 | — | Opus |
| WP-44 | Beta backups, monitoring, alerts | WP-42 | — | Sonnet |
| WP-45 | Beta URL in the mobile build scripts | WP-41, WP-49 | — | Sonnet |
| WP-46 | Load test and drills | WP-43, WP-44 | — | Sonnet |
| WP-49 | Company-account migration (CR258) | WP-00 | S7 | Opus |
| WP-50 | Store records, listing, review notes | WP-29, WP-36, WP-49 | — | Sonnet |
| WP-51 | Website waitlist | WP-00 | — | Sonnet |
| WP-52 | Tester onboarding note and support inbox | WP-00 | — | Sonnet |
| WP-53 | Exit-criteria report | WP-36, WP-46 | S9 | Sonnet |
| WP-54 | Beta go-live | WP-12, WP-13 (enforcing), WP-26, WP-30…39, WP-45, WP-46, WP-50, WP-52, WP-53 | — | Architect |

Parallelism: after WP-00, the Phase 3 packages (WP-27, WP-29…35, WP-37), WP-21a, WP-40, WP-49, WP-51 and WP-52 are independent of the Room work and of each other. WP-10…13 run together. The Room chain WP-21a → 20 → 22 → 23 → 25 → 26 is the critical path. WP-28 and WP-51 are deliberately off the launch path: the first wave is the personal network and needs no waitlist.

Order at the start (rev 2): S0 → WP-00 step 2 (mechanical row fixes) → `/daily-cr-def-review` once, logged as WP-01/S1 → the rest of WP-00. This keeps Saiful from being asked about rows that are merely stale. `/bug-monitor` runs at session start as normal. Commit tag for the executing session: `(AT:B<N> CR###)`, numbered per session.

## 6. Work-package detail

### Phase 0 — Re-entry

**WP-00 Re-entry**

1. Goal: the registers and roadmap tell the truth again.
2. Steps:
   1. Find out whether the corrected CR266 60-room run finished on melehost. No file names its output folder; `progress.md` names only dead Claude task IDs. Search melehost in this order:
      1. the harness `out/` directory in melehost's copy of `docs/tools/room_investigation_V2/` (progress.md line 112 cites `out/cr266-legacy-card-report/`);
      2. `~/cr266_smoke/`;
      3. directories under home modified on or after 2026-10-29;
      4. any surviving tmux session or process.

      Record the result in `CR266_decision_reliability/progress.md`. If no complete 60-room set turns up, record "never completed"; that blocks nothing.
   2. Fix stale rows. The stocktake (`docs/Research/decision_consistency_programme_stocktake_2026-10-20.md`) is the authority, not this list. There is no `superseded` status: write `dropped` with "superseded by CR267" plus what was kept in the row text, and don't edit `gen_registers.py`.
      1. CR256 → `done` (a measurement that delivered its result, ICC 0.868 on a hosted model). `room_evidence_gate_thresholds_json` belongs to CR266, not CR256.
      2. CR251, CR265 → `dropped`, superseded (their goal was the approval curve).
      3. CR266 → after step 1, `dropped`: "superseded by CR267; card channel, DecisionRecord and threshold-policy code retained and reused by WP-22/WP-23". The code stays.
      4. CR252, CR253, CR255, CR257, CR259 → `done` or `dropped` per the stocktake, with a reason.
      5. Do not touch CR254 (WP-01 decides it), CR258 (WP-49) or CR260 (WP-21b).
      6. Read `CR253_data_lane_completeness/` (it has no row). If it is a sub-workstream of CR253, add a line to the CR253 row naming both folders. If it is a separate item, ask the Architect to mint an ID. Don't rename the folder.
   3. Append decisions to `docs/initial_specs/11_decisions/decision_log.md`, one per item in section 3, starting at D-076. Also one per item in §3a.1–4 (decision 3 as amended by §3a.1). Note that D-066/D-067 are reopened and D-068 is closed by decision 3. Mark **D-072 amended for its hosting clause only** ("on the current melehost Alpha stack" is replaced by decision 1); its payments-parked part stands. D-073 is unchanged.
   4. Rewrite the status block and Beta section of `docs/initial_specs/10_delivery/project_plan.md` to point at this plan.
   5. Resolve the dirty tree left from October:
      1. Deleted `CR253_tm_all_salvage_conversion.md`: confirm `CR254_tm_all_salvage_conversion/` holds the same content, then commit the deletion by pathspec.
      2. Untracked checkpoint memos (track K) and the three harness/docs files (`jev_verdict_relation.py`, `cr251-cap1-smoke.yaml`, `CR252…/production_section.md`): **`origin` is public.** Read each file whole; a pattern scan is not enough. If a file holds a credential, a personal detail or anything doubtful, leave it untracked and list it in `progress.md` for Saiful. Otherwise commit it, using K's tag for K's files.
      3. Do not discard another track's work without reading it. Track K is closed (§3a.6).
3. Acceptance: `python3 scripts/registers/gen_registers.py gen all` leaves no diff after commit; no path WP-00 owns is dirty (anything else dirty is listed in `progress.md`, since other tracks share the checkout); every row changed in step 2 reads `done` or `dropped` with a reason.

**WP-01 Register decision review (gate S1)**

1. Run `/daily-cr-def-review` with Saiful present. Bring a close / keep / defer / drop recommendation for each `proposed` CR and `open` defect, judged against the freeze. Run it once only; CLAUDE.md's session-start review counts as this WP.
2. Recommendations already agreed: move DEF469 (a real tester report) into WP-33, and decide CR254. Also ask Saiful what is actually done on the company accounts (CR258), which feeds WP-49.
3. **Outcome (2026-11-18, ledger `afee9f99` on main):**
   1. Added to Beta: CR252 (WP-15), CR239 (WP-38), CR022 (WP-39), DEF445 (WP-27), DEF469/470/482/485 (WP-33), DEF104 (WP-35, overriding the DEF204 hold).
   2. Absorbed: CR240 → WP-10; CR246 → WP-46. DEF200 → the WP-46 load test decides.
   3. Dropped: CR245, CR247, CR250, CR254.
   4. To close: DEF386 (retract CR164 Phase A findings), DEF434 (verify no `--delete` in the harness sync, then close).
   5. Company accounts are **not enrolled yet**; the Play account will be an Organisation account. Apple organisation enrollment needs a D-U-N-S number and can take weeks, and WP-49 is on the launch path: start enrollment now.
   6. Everything else is deferred or parked as recommended.
3. Acceptance: a dated section in `docs/governance/daily_cr_def_review_log.md`; every open item has a decision.

**WP-02 Bring Alpha level with HEAD**

1. Alpha runs `alpha-2026-10-19-1`. Since then, 6 `backend/app` files have changed (+1,149 lines, including `room_runner.py` +547 and a new `evidence_record.py`): this is CR266's code. Before promoting, read the `room_runner.py` diff and confirm every new path is behind `room_cards_envelope_enabled` or `room_evidence_gate_enabled` (both default `False`, config.py:1134/1144), and that neither flag is set in `infra/alpha.env`. Then run `/promote-to-alpha`. Promoting the code doesn't decide CR266's fate; the flags do.
2. Acceptance: `curl -s https://api-alpha.agenticmarketintel.ai/v1/health` shows the new tag and HEAD's SHA; postflight green.

### Phase 1 — Hosted LLM

**WP-15 CR252 institutional-heuristics fold-in (gate S11)**

1. Saiful at WP-01 (2026-11-18): fold in before WP-10, so the model scorecard and the WP-20 baseline both measure the final desk prompts. The draft is `docs/forward_planning/CR252_institutional_heuristics_injection/production_section.md` (34 lines, in the main checkout as an untracked file; WP-00 step 5 commits it). Its data dependencies (SBC, ROIC, WACC) shipped as CR268.
2. Behind a setting (forwarded in compose), ON for WP-10 and WP-20. Its design is part of the S11 discussion.
3. Note: the "measured GO" rests on 8 rooms (AAPL+V, R3, 2 reps) on the abliterated ami-llm. WP-10's side-by-side is its first real measurement.
4. Acceptance: unit test that the section reaches every desk prompt when ON and none when OFF; compose-parity green.

**WP-10 Shortlist and scorecard**

1. Goal: evidence for Saiful to pick one hosted model.
2. Context: `docs/forward_planning/CR240_llm_provider_evaluation/CR240.md`; harness `docs/tools/room_investigation_V2/` (read its `README.md` and `EXPERIMENT_LOG.md`); gateway `backend/app/services/llm_gateway.py`. The vLLM provider slot is OpenAI-compatible: `VLLM_BASE_URL`, `VLLM_MODEL`, `VLLM_API_KEY` point it at DeepInfra with no code change. Confirm that with one call before anything else, through both the gateway and the V2 harness. If the harness drops the key, fixing it is a tools change and doesn't break decision 3, which covers the product gateway.
3. Key and spend:
   1. Find the DeepInfra key's variable *name* in melehost's `.env` and the harness env; never print values. The CR257 runs used a provider key there in October. If it isn't there, Saiful places it.
   2. Account spend limit for the measurement runs: $100 (§3a.4). Saiful sets it at the vendor if the account allows.
   3. Check DeepInfra's rate limits against 10 concurrent Rooms (WP-46).
4. Steps:
   1. Read DeepInfra's live model catalogue. Shortlist three non-abliterated open-weight models: the current Qwen flash-class model, DeepSeek-V4-Flash, and one other fast model. Record each licence's position on commercial use, and whether the model returns token probabilities (WP-22).
   2. For each, run the harness on the 30-ticker universe at risk 2 and risk 4, two reps, with veto and resurrection reviews ON (production setting), and temperature pinned at the desk value (the model card's recommended sampling for reasoning mode if the provider publishes one, otherwise 0.3; record the choice in `progress.md`). Add a 10-ticker side arm at 0 and at the server default, scored on contract gates and grounding only. Avoid 0 on desks unless the side arm shows no looping or truncation.
   3. Score: contract gates (`tools/room_contract_gates.py`), grounding of cited figures (`tools/jev_score_runs.py`, `figures_consistent`), minutes per Room, cost per Room from the provider's usage figures, error rate over the run.
5. Out of scope: the approval curve. The desk writer no longer owns the verdict.
6. Acceptance: `docs/forward_planning/CR240_llm_provider_evaluation/scorecard_<date>.md` with one row per model and a recommendation against the bars (zero gate failures, under 2 minutes, at most 5 cents, licence clear). If no model reaches 2 minutes, say where the time goes per phase.

**WP-11 Pin temperature and sampling**

1. Production runs at the server default (1.0). Add explicit settings in `backend/app/core/config.py`, apply them in the gateway for every desk call, forward in `docker-compose.yml`. Desk value: the one chosen in WP-10. Judge: 0. With WP-24 banking, product consistency no longer depends on temperature, so choose the desk value on desk quality.
2. Acceptance: unit test proving the request body carries the configured temperature; compose-parity test green.

**WP-12 Budget cap and concurrent-run cap**

1. A daily spend ceiling on the hosted provider, as a setting. Count tokens from responses; on breach, Rooms return an honest "temporarily unavailable" state and an alert fires. Ceiling: $10/day Beta, $5/day Alpha (§3a.4). The ceiling counts primary and fallback spend together.
2. A per-user limit of one Room in flight: the only part left over from DEF186. If the DEF186 fix already enforces it, prove that with a test and drop this half.
3. Acceptance: unit tests for both; breach state is visible in the stream, not a fake verdict.

**WP-13 Output text guard**

1. A deterministic check on user-visible agent text before it is streamed or stored: personalised-advice phrasing ("you should buy"), content unrelated to markets, unsafe content. On a hit, replace the turn with a labelled sentinel and log it. Start in log-only mode behind a setting. Measure the hit rate by replaying stored agent text from `llm_audit`, not by waiting for calendar time (Alpha has had almost no live traffic since 2026-10-30). Then enforce.
2. Acceptance: unit tests with positive and negative examples; hit-rate note in `progress.md`; enforcement switched on before WP-54.

**WP-14 Cut Alpha over (gate S2)**

1. Set the three vLLM variables in `infra/alpha.env` to the chosen model; promote.
2. Automatic failover (§3a.1). This is a code change in `llm_gateway.py`, a shared hot path, so the full backend suite runs before merge.
   1. Add a second OpenAI-compatible provider slot (`VLLM_FALLBACK_BASE_URL`, `VLLM_FALLBACK_MODEL`, `VLLM_FALLBACK_API_KEY`), forwarded in `docker-compose.yml`. On Alpha it points at on-prem vLLM; on Beta at a second DeepInfra model.
   2. A desk call that fails on the primary retries on the fallback. Which errors trigger failover, and whether a Room may mix providers mid-run or must restart wholly on the fallback, are decided in the WP's CR doc. The default is to restart the whole Room on the fallback, so one Room never mixes models.
   3. A fallback Room is labelled in the stream and in the stored record, and carries the fallback model's `root` (so WP-24 banks it under its own key). It is never presented as the primary model.
   4. Both providers down: the visible "temporarily unavailable" state, never a verdict.
   5. The Beta env must not point the fallback at on-prem. WP-41 adds a startup check that refuses a LAN or abliterated fallback when `ENV=beta`.
3. Update the runtime table in `CLAUDE.md` (primary model, fallback model, where each runs, what the alias resolves to).
4. Acceptance: one live Room on Alpha completes on the hosted model (`llm_audit` shows it); a forced primary failure produces a completed Room labelled as the fallback, with the fallback model in `llm_audit`; forcing both down produces the unavailable state, not a verdict.

### Phase 2 — The Room

Read first: `docs/Research/decision_consistency_programme_stocktake_2026-10-20.md`, `docs/forward_planning/CR257_jev_decision_arm/spec.md` (§7–§8), `docs/forward_planning/CR255_decision_consistency/jev_deep_dive_2026-10-14.md`, `docs/forward_planning/CR266_decision_reliability/`. Known facts: prompt rewrites do not fix consistency; Jev repeats itself on the same transcript (299 of 300) but nobody has shown its calls are right; the debate itself varies between fresh runs.

**WP-20 Baseline on the chosen model**

1. Runs after WP-21a, so no desk sees consensus. Run the 30-ticker × 5-risk matrix, two reps, production settings (cards OFF). Freeze the result as `docs/forward_planning/CR267_beta_programme/room_baseline_<model>.md` in the format of `docs/forward_planning/CR251_risk_monotonicity_matrix/BASELINE.md`. Keep the raw runs; WP-22 reuses them.
2. A second arm of the same matrix with cards ON, for WP-22's code grader. It is about 300 more rooms; the cost is unmeasured. It is evidence only and does not change production.
3. If the 30 tickers include no Street Sell or Underperform name, add up to five of the lowest-consensus names from `docs/forward_planning/CR035_room_benchmark/tickers_150.txt` as a side set, and say so in the baseline file.
4. Acceptance: the baseline file states approvals per risk level, flip count across reps, minutes and cost per Room, n per cell, card completeness for the cards-on arm, and the gate report.

**WP-21a Room decides blind (consensus removed at the source)**

1. Remove analyst consensus ratings and price targets from the Room's fact sheet at the source (the pattern CR038 used for synthetic macro fields), so no desk and no judge can see them. First check whether the fact sheet carries consensus fields today. If it doesn't, this WP is only the guard test.
2. Acceptance: a unit test that fails if any consensus field appears in a desk prompt.

**WP-21b Street comparison after the verdict**

1. After the verdict, attach a computed comparison to the result: Street rating, the Room's action, and the reasons from the narrow answers when they differ. CR260 (analyst price targets) is re-scoped to this display.
2. Mobile: show it on the verdict card, behind a setting, with a source label (§3a.3). Public release needs a licensed source (CR007).
3. Acceptance: a Room on Alpha shows the comparison after the verdict; the comparison is setting-gated and carries a source label.

**WP-22 Narrow-question judge and bake-off (offline, no production change)**

1. Write the question set: five or six typed questions unbundled from the CR257 rubric, each checkable by a person reading the room. Starting set: is the bear's strongest objection answered with numbers; is there a named catalyst inside the mandate horizon; is there an unresolved terminal vulnerability; does event risk argue for waiting; is thesis support material and directional; did the desk propose a trade. Version the file.
2. Build one grader interface with three implementations:
   1. Jev: `tools/jev_v1_pilot.py` shows the call shape. Pin the version, never `latest`.
   2. The WP-14 hosted model at temperature 0, with constrained answers and token probabilities. If the model returns no probabilities, ask the close questions as a 1–5 score and build the Contested band from the scores. Record the missing probabilities as a minus under "control".
   3. Plain code over CR266 typed cards (the WP-20 cards-on arm). A missing cell makes that question "not computable" for that room; never impute. Report completeness as its own column. A code grader that can't answer for a material share of rooms can't be the sole grader. It can still own questions computable from structured fields without cards (e.g. "did the desk propose a trade").
3. Run all three over the WP-20 rooms. Score each:
   1. Consensus scores (reuse `backend/scripts/room_benchmark.py` and `room_benchmark_report.py`, on the WP-20 30-ticker universe plus any side set; not the 150-ticker list): approvals of Street Sell/Underperform names; share of approvals that are Street Buy per risk level; rank correlation of the decision score with the consensus score. Report n per cell, and the CIO's numbers on the same rooms beside them.
   2. Wording test: each question in five phrasings; share of answers that change.
   3. Input tests with known answers: planted fatal flaw must give pass; removing the bear's evidence must not make the answer more cautious; strengthening the bear's numbers must lower the score; reordering turns and renaming the ticker must change nothing.
   4. Fresh-room stability: disagreement across the two reps of the same ticker and risk level.
   5. Cost and latency per Room; control (version pin, visible prompt, switchable vendor).
4. Acceptance: `docs/forward_planning/CR267_beta_programme/grader_bakeoff_<date>.md` with the table, the failures listed by question, and a recommendation. No recommendation of Jev without noting that vendor terms are still owed.

**WP-23 Coded decision rule (gate S3)**

1. In `backend/app/services/room_runner.py`, behind a new setting (default off): after the debate, call the chosen grader, combine the answers with a written rule per risk level, and emit Approve / Pass / Contested. Contested covers the band where answers are close and lists which questions were close.
2. The rule is written in advance from the questions, not fitted:
   1. an unresolved terminal vulnerability gives Pass;
   2. no trade proposed gives Pass;
   3. an unanswered bear objection gives Pass at the conservative risk levels;
   4. strictness is monotone in risk level.

   Only the Contested band and any numeric cut-offs are fitted on the WP-20 rooms. Their targets are (a) agreement across the two reps of the same ticker and risk level, (b) the input tests with known answers, and (c) the CR257 holdouts. **Consensus is never a fitting target**; it is held out for evaluation in WP-22/WP-26. Store the result as versioned policy (reuse the shape of `room_evidence_gate_thresholds_json` in `config.py` rather than inventing a new one). The policy version includes the grader and its version.
3. The CIO becomes a single narration call that explains the computed decision; it cannot change it. The deterministic mandate compliance check still runs last and stays as it is.
4. Grader down or erroring: the Room ends in a visible "decision unavailable" state. Never a default verdict.
5. Full backend suite before merge (shared hot path).
6. Acceptance: unit tests for the rule, the Contested band, the unavailable state, and that narration cannot alter the action; flag on in Alpha produces a Room whose stored record contains every answer and the rule version.

**WP-24 Same inputs return the same room**

1. Freeze the fact sheet per ticker per trading day. Key a room on (user_id, ticker, mandate snapshot, fact-sheet hash, policy version, model `root` from `/v1/models`). The key is per user: sharing rooms across users is a later cost optimisation. A new trading day is a changed input, so it gets a new room; there is no materiality threshold in this programme. A convene with an existing key returns the banked room; state plainly in the UI that inputs are unchanged since the last run.
2. Decide and document what happens to credits on a banked return (recommended: no charge).
   - **Decided and built 2026-11-20: a banked return is not charged.** The convene is refused nothing and billed nothing: the key is looked up before the charge, so a user with no credits still gets the banked Room, and `done.credit_cost` reports `0` (never the original Room's cost). Cost to the programme: none, no model call is made.
   - **Implementation notes (WP-24).** Key = SHA-256 of (user, ticker, mandate content, fact-sheet hash, policy version, model `root`, trading day). The mandate digest excludes plan and credit state, the version counter and timestamps; a new `Mandate` field must be classified keyed-or-excluded (a unit test fails otherwise). The fact sheet is frozen per (ticker, trading day, entitlement variant) in `room_fact_sheets`; the trading day is the New York date rolled back over weekends and NYSE holidays (`trading_math/session_calendar.py`). Policy version = hash of every agent's derived prompt version plus `ROOM_POLICY_REVISION` (bump it when decision logic changes without a prompt change; WP-23's rule version should feed it). Model root = `/v1/models` `root`, cached `ROOM_MODEL_ROOT_TTL_S` (300 s); a vLLM slot with no readable root runs unbanked and logs `room_bank_degraded`; a hosted (`openai`-kind) slot with no root keys on the vendor's model `id`. `room_runs.bank_key` is UNIQUE (non-NULL) and holds a Room only while it is running or a whole, unrefunded, non-outage, no-scripted-desk completion; the row is reserved before the charge so two concurrent identical convenes are one Room and one charge. A Room restarted on the backup slot is re-keyed with the backup's root. The old `ROOM_DEDUP_COMPLETED_HOURS` window is removed.
   - **Not in the key (spec-literal, flagged for review):** the user's holdings and the Decision Journal. A user who buys the name and re-convenes the same day on an unchanged mandate is handed the earlier Room.
3. Acceptance: two convenes with identical inputs return the identical room ID in 100% of a 50-pair test; changing any keyed input produces a new room.

**WP-25 Flip explainer**

1. When a user's verdict on a ticker differs from their previous one, compute and store a diff: which inputs changed (price, news, filings, mandate) and which narrow answer changed. Both are required. Add which desk claims changed only when cards are on; the explainer must work without cards. Built from stored fields in code; no agent writes it.
2. Mobile: show it on the verdict card and in the Journal.
3. Acceptance: a forced input change yields a flip whose explainer names at least one changed input and one changed answer; a unit test rejects a flip stored without an explainer.

**WP-26 Room acceptance run**

1. Fresh 30-ticker × 5-risk run, two reps, all of WP-21a/21b/23/24/25 on.
2. Gates, judged by the letter:
   1. identical inputs return the identical room (100%);
   2. every verdict change carries a non-empty explainer;
   3. consensus scores at or above the CIO baseline from WP-22;
   4. wording and input tests still pass;
   5. zero holdout approvals: zero approvals when the banked CR257 holdout transcripts (spec §4.1, lines 74–76: RIOT-shaped, and APD/BA-shaped with a grounded bear case and negative SBC-adjusted FCF) are replayed through the chosen grader and rule;
   6. zero contract-gate failures.

   Diagnostics only: the fresh-run flip rate, and fresh RIOT/APD/BA rooms (their facts move).
3. Pass: turn the setting on for Alpha and Beta. Fail: leave it off, label the Room "experimental" in the app, stop tuning, and record which gate failed. **Beta still goes live on a FAIL**, with the Room labelled experimental. Then raise the Room Lite option below with Saiful (gate S10). Cards go on in production only if the WP-20 cards-on arm passes the contract gates; WP-26 doesn't require cards.
4. Acceptance: `docs/forward_planning/CR267_beta_programme/room_acceptance_<date>.md` with each gate's measured value and a single PASS or FAIL.

**WP-27 Room reliability defects**

1. DEF484 (verdict never shown after "Reconnect timed out"), DEF467 (streams stall with no keepalive: add heartbeats to Room, 1-on-1 and Brief streams), DEF471 (credits spent with no confirmation), DEF480 (ticker dropped on convene), DEF444 (checkpoint write blocks the event loop), DEF445 (false `fcf_yield` self-check flag; added at WP-01).
2. Acceptance: each defect's row moved to `fixed` with its test; a device run on the Android rig shows a verdict after a forced reconnect.

**WP-28 Outcome scoring**

1. 6,743 verdicts are banked and none scored. Schedule `backend/scripts/score_verdict_outcomes.py` on Alpha; make `room_outcome_report.py` part of the weekly report.
2. Acceptance: scored rows exist; the report runs unattended.

**WP-29 Copy**

1. Store listing draft (`marketing/users/assets/store_listing_copy.md`) and `website/`: lead with the learning outcome; the Room is the practice arena, described as a simulated desk. No claim about picking stocks or performance.
2. Acceptance: no "12 AI analysts" headline remains; website deployed with a cache-bust.

**Room Lite (only if WP-26 fails or WP-10 cannot reach 2 minutes; gate S10; not on the launch path)**

Keep all twelve voices on screen and cut the calls: one structured Research call renders the Bull, Bear and Research Manager voices, as CR201 did for the risk debators. Gate it against the WP-20 baseline with the same harness before it replaces anything.

### Phase 3 — App fixes before external testers

**WP-30 Account closure and data export (release gated by S6)**

1. Backend: routes to close an account (deactivate and revoke sessions at once; restorable for 30 days; then a scheduled job runs the post-grace step) and to export the user's data as a downloadable file. Make the post-grace step a setting with three modes (archive, anonymise, delete) so counsel's answer is a configuration change.
   - Beta mode (§3a.2): `delete` or `anonymise`, with the button reading "Delete account". The WP's CR doc records which of the two and why; it must remove the user's personal data, to meet Apple 5.1.1(v) and Play's deletion requirement. `archive` is switched on only after counsel approves (S6).
2. Mobile: Settings → Close account, and Settings → Export my data.
3. Wording everywhere says "delete account" in Beta (it changes to "close account" only if `archive` is enabled) and states what is kept and for how long. Update `legal/policies/terms_of_service.md` §10 and the privacy and data-deletion policies to match; they are still DRAFT. The privacy policy also notes Singapore hosting as a cross-border transfer under Malaysia's PDPA.
4. Acceptance: a deleted account cannot sign in after the grace period and its personal data is gone (or anonymised); restore works inside the grace period; export contains the user's trades, rooms, mandate and progress; device run on the rig. `archive` mode is not enabled before S6.

**WP-31 18+ confirmation**

1. One step in onboarding (`mobile/lib/screens/onboarding`); store a timestamped boolean, no birth date. Existing Alpha users are not retrofitted; Beta starts with an empty database.
2. Acceptance: onboarding cannot complete without it; widget test.

**WP-32 iOS privacy manifest**

1. Add `PrivacyInfo.xcprivacy` to the Runner target, consistent with the SDKs in `mobile/pubspec.yaml`.
2. Acceptance: release build succeeds; manifest present in the archive.

**WP-33 Mobile defect batch**

1. DEF473 (update button dead when `storeUrl` is empty), DEF478 (hardcoded English), DEF483 (stray backslash), DEF472, DEF477, DEF479, DEF474, DEF475, DEF476, DEF466, DEF486, and, added at WP-01: DEF469 (tester report), DEF470 ("discard changes" doesn't discard), DEF482 (RenderFlex overflows), DEF485 (price alert creation fails client-side). DEF481 is deferred post-Beta.
2. Acceptance: rows `fixed` with tests; `flutter analyze` and `flutter test` green.

**WP-34 Backend defect batch**

1. DEF458, DEF462, DEF463 (500s on bad input), DEF461 (sim news dark on Alpha), DEF468 (null candles), DEF459, DEF460.
2. Acceptance: rows `fixed` with tests; suite gate green.

**WP-35 Security leftovers**

1. DEF104 (plaintext mailbox credential in the support-KB scripts on melehost), DEF464 (rate limiter trusts client-supplied headers: `backend/app/services/rate_limit.py`).
2. DEF178: after gate S8, verify the old key is rejected by the vendor, then close the row and CR123. No history rewrite.
3. Acceptance: rows `fixed`; a spoofed header no longer changes the limiter's key (unit test).

**WP-36 Beta build settings**

1. English-only locale for Beta builds; credits free; paywall remains the information card. Treat both as new settings: a quick grep found neither. The free-credits switch is a backend setting under the compose-parity test. The locale lock is a build-time define in the mobile build scripts.
2. "Report this response" on agent output, feeding the existing bug-report path.
3. After each Room: "Did the verdict and its reasons make sense?" thumbs up or down, stored with the room ID.
4. Acceptance: Beta build shows no AR/MS switch; a report and a thumbs rating both arrive in the database from the rig.

**WP-37 CR231 gate items**

1. Close CR221, CR222, CR228 per `docs/forward_planning/CR245_beta_infra_1000_user_sizing/` §12. Run the E5 device matrix (`docs/forward_planning/CR004_release_readiness/e5_device_matrix_runbook.md`) on the Android rig; list the iPhone steps for Saiful.
2. Acceptance: rows closed; matrix results recorded.

**WP-38 Trace ID on every error (CR239; added at WP-01)**

1. Per CR239's two legs: every backend error response carries a trace ID that is logged with the request, and the app shows it on error states and attaches it to the WP-36 "Report" path, so a tester's report maps to one log line.
2. Acceptance: unit test that error responses carry the ID and the log line carries the same one; widget test that the error state shows it; one forced error on the rig traced end to end.

**WP-39 App manual corpus for the Concierge (CR022; added at WP-01)**

1. Per `docs/forward_planning/CR022_app_manual_corpus/`: app-usage knowledge, authored and indexed like lessons, so testers can ask the Concierge how the app works. English only for Beta. Content describes the Beta build as shipped (WP-36 settings, account deletion, report button).
2. Acceptance: the Concierge answers a fixed set of 10 how-do-I questions from the corpus on the rig; every answer cites a corpus entry; no answer describes a hidden or parked feature (payments).

### Phase 4 — Beta infrastructure

Position: recommended, not yet discussed in depth with Saiful. Gate S4 confirms it. Comparison and sources are in the planning record (`/Users/saiful/.claude/plans/i-have-neglected-this-inherited-cray.md`); copy that table into this folder as `hosting_comparison_2026-11-18.md` during WP-40. Re-check every price and limit on the vendor's own page before money is spent.

Recommendation: one Singapore VPS (2 vCPU / 4 GB) running the same Docker Compose stack as Alpha, Cloudflare Tunnel in front. Cheapest option found, no code change, and Beta becomes a second target for the pipeline that already works. Vercel does not fit this backend; Cloudflare stays in front but is not the host.

**WP-40 Accelerator and credit research**

1. Find accelerators and affiliate programmes open to a Malaysia-based company that are approved partners for the Google, Alibaba, AWS and Microsoft startup tiers: eligibility, deadlines, what they unlock. List the tiers needing no backer (Cloudflare for Startups, Google Start, Huawei, Microsoft Founders Hub) and each programme's rule on existing accounts.
2. Acceptance: `credits_and_accelerators_<date>.md` in this folder, with sources, for gate S5.

**WP-41 Beta environment configuration**

1. Add `beta` to the allowed `ENV` values in `backend/app/core/config.py`. Create `infra/beta.env.example` (no secrets) listing every key Beta needs: fresh `SECRET_KEY`, hosted-LLM keys for primary and fallback, no on-prem address. Add a startup check that refuses to boot with `ENV=beta` if either LLM base URL is a LAN or private address (§3a.1). Check that nothing in the code assumes `staging` or `prod` only.
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

1. `scripts/build_testflight.sh` and `scripts/build_playstore.sh` bake only the Alpha URL today. Add the Beta URL and a flag selecting the Beta channel; backend-switching stays off in Beta builds. Use the final company bundle IDs from WP-49.
2. `SENTRY_DSN`: `build_playstore.sh` treats it as optional and leaves it empty if unset (lines 42, 91, 461); check `build_testflight.sh`. A Beta build must fail when the DSN is empty, because WP-53's crash-free figure comes from Sentry release health.
3. Acceptance: a Beta build talks to the Beta hostname and cannot be switched to Alpha; a Beta build with an empty DSN fails.
4. **Built (lane `lane/WP45-beta-channel`).** `--channel alpha|beta` (default alpha, behaviour unchanged) and `--dry-run` on `build_testflight.sh`, `build_playstore.sh` and `publish_playstore.sh`; shared logic in `scripts/lib/release_channel.sh`; tests in `backend/tests/unit/test_cr267_wp45_beta_channel.py`. A Beta build bakes `AMI_API_URL_PROD=https://api-beta.agenticmarketintel.ai` (override `AMI_API_URL_BETA`), `ALLOW_BACKEND_SWITCH=false`, `AMI_BETA=true` (CR278), `AMI_ENV=beta` and `SENTRY_DSN`; no Alpha hostname or define is passed. It refuses (exit 1, before any gate or bump) without `--no-games`, without `SENTRY_DSN`, and without the WP-49 identifiers: `AMI_BETA_IOS_BUNDLE_ID` / `AMI_BETA_ANDROID_APPLICATION_ID` must be set, must not be the personal IDs, and must equal what the Xcode project / `build.gradle.kts` declare; Android also needs `AMI_BETA_GOOGLE_OAUTH_WEB_CLIENT_ID`. The schema-parity gate checks the Beta host on `--channel beta`. **Blocked on WP-49 / S7:** every real Beta build refuses today, because the project files still carry the personal IDs. WP-49 must change the IDs and signing in the project, then export the two env vars. Not done: a Play closed-testing fastlane lane (`publish_playstore.sh` still uploads to `internal`), and a post-build check that the Alpha hostname is absent from the binary (add once the first Beta artefact exists).

**WP-46 Load test and drills**

1. Run the k6 script in `infra/loadtest/` at 200 testers with 10 concurrent Rooms (check DeepInfra's rate limits first). Resize the server if needed. One rollback drill.
2. Acceptance: results file in this folder; drill recorded.

### Phase 5 — Launch

**WP-49 Company-account migration (CR258, gate S7)**

1. Move the apps to the company Apple and Google accounts: bundle IDs, signing, Sign in with Apple keys, Google OAuth audiences, OneSignal. RevenueCat stays parked with payments. Plan and identity register: `docs/forward_planning/CR258_company_account_migration/`. Find out at WP-01 how much is already done (D-073's 2026-10-13 update says "executing now").
2. Acceptance: a release build signed under the company accounts installs on the rig, signs in, and receives a push.
3. **Prep built (2026-11-20, lane `lane/wp49-prep`).** Founder: accounts enrolled but clean, "prepare but do not release yet". Done: company IDs/signing/OneSignal/Play service account read from gitignored `mobile/beta_accounts.env` (template `mobile/beta_accounts.env.example`); the Beta build patches the Xcode project for the run and restores it; Alpha untouched. Decision (new IDs, reasons cited) and the console checklist: `docs/forward_planning/CR258_company_account_migration/wp49_prep_2026-11-20.md`. Release steps (App ID, ASC/Play records, keys, first build) wait for the founder's go.

**WP-50 Store records, listing, review notes**

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
   1. Crash-free sessions ≥ 99% (Sentry release health).
   2. Room completes with a shown verdict in ≥ 95% of runs.
   3. WP-26 gates hold on the weekly harness run, or WP-26 recorded FAIL and the Room carries the experimental label.
   4. Room satisfaction ≥ the bar from S9 over at least 100 rated runs.
   5. Zero open defects in security, data loss or money categories.
   6. At least 20 testers active over 14 days; day-7 retention reported (computed from backend session/activity rows; no analytics SDK in Beta).
   7. One rollback drill and one restore drill on record.
   8. Diagnostic, not a bar: the day-over-day verdict flip rate. If it is high, a materiality threshold becomes a post-Beta item.
2. Acceptance: the report runs unattended and every line is computed, none typed by hand.

**WP-54 Beta go-live**

1. Invite the personal-network wave first; open the other channels as they are ready. Play's 12-testers-for-14-days clock applies to personal developer accounts. If S7 confirms the company Play account is an organisation account, it is a soft target only. Arm `/loop 6h /bug-monitor`. One Beta build a week.
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
7. Whether the V2 harness passes `VLLM_API_KEY`, and whether the chosen model returns token probabilities (WP-10 answers both).
8. Whether the 30-ticker universe contains any Street Sell/Underperform name, and whether RIOT/APD/BA are in it (WP-20 answers it).
9. The cost of the WP-20 cards-on arm (unmeasured).
