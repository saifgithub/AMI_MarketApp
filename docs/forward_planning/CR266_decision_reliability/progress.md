# CR266 — progress log

## 2026-10-29 — initiated

1. CR266 created. Parallel workstreams approved by Saiful.
2. Backend, mobile and calibration/outcome agents are starting with disjoint
   file ownership. Integrator owns shared-contract review and acceptance.
3. `ami-llm` and Ling continue as iteration models; Sonnet is confirmation-only.
4. No production rollout is authorised until per-model acceptance passes.

## 2026-10-29 — workstreams started

1. Backend evidence-gate agent is running (`agent-0`).
2. Mobile and calibration/outcome agents are queued behind the four available
   background slots; no work has been hidden or marked complete.
3. Ling's 600-room matrix is complete; 16 contract-failure replacements are
   running. `ami-llm` is at 237/300 rooms.
4. CR266 initiation committed as `abdb0d74`.

## 2026-10-29 — parallel implementation and gate hygiene

1. Mobile contested-card agent is now running (`agent-3`). Calibration/outcome
   remains queued.
2. Six Ling control replacements completed: 11/12 rooms passed; DHR-r1-rep1
   still failed PM JSON and needs a fresh replacement. It is not being counted
   as clean evidence.
3. `ami-llm` has reached 253/300 rooms.

## 2026-10-29 — mobile complete, outcomes started

1. Mobile implementation committed as `83aeb029`: decision record/delta models,
   contested and change cards, localization and parity tests. Full Flutter suite
   **1927 passed, 0 failed**. Old verdicts render no new placeholder state.
2. Calibration/outcome agent is now running (`agent-4`).
3. Backend evidence-gate agent remains in progress; its schema, prompt, runner
   and config changes are visible but not yet treated as complete or validated.

## 2026-10-29 — lane replacements clean

1. All 18 lane replacement rooms passed their contract gates. The only
   remaining invalid Ling room is DHR-r1-rep1; a second replacement pair is
   running with fresh benchmark ID `cr265-t011-ling-retry-dhr-r1-v2`.

## 2026-10-29 — Ling calibration complete

1. All 600 main rooms and 32 replacements validated. Lane curve is monotone:
   5/10/20/31/28 approvals vs control 10/10/17/26/26; flips 45→33; nonmonotone
   tickers 16→12; approvals 89/300→94/300. Flip CI 16.1–29.3% still fails <10%.
2. Lane earns only a CR266 structural comparison on Ling, not a global rollout.
   Full report committed as `04c6c311`.

## 2026-10-29 — outcome reporting and integration review

1. Calibration/outcome implementation committed as `f4c81519`; focused backend
   verification is 42 passed and the fit helper has 15 tests. No real thresholds
   have been fitted or enabled.
2. The real Alpha outcome report is saved as
   `room_outcome_report_2026-10-29.json`: 6,743 banked rows, 6,172 pending,
   571 unscorable and **zero scored**. It therefore provides no outcome or
   human-consensus alignment measurement. The daily scorer was not run and no
   cron was installed because production changes remain unauthorised.
3. Integration found and is correcting three contract issues before pilots:
   raw summed scores did not fit the sizing range; backend/mobile contested
   field names differed; and provider-only keys would share thresholds between
   `ami-llm` and Ling on vLLM. The normalized score is mean card support minus
   0.1 per unresolved objection, and threshold identity is provider plus model.
4. Required cards will be exactly one per desk/item. Duplicate cards fail
   closed rather than inflating the evidence score.

## 2026-10-29 — integration hardening and pilot preparation

1. Initial backend implementation committed as `8887ecf8`; its focused suites
   pass. Full-suite verification reported 7,768 passed, 7 skipped and two
   failures: the new provenance omission was fixed, while the remaining P30
   failure is the unrelated pre-existing `DEF465.row` citation of missing
   `debug_unpack_ios`. That other track's defect was not edited.
2. Review found a resurrection-review path that could overturn a gate-blocked
   PASS without reapplying evidence action/size rules. Backend integration is
   closing that bypass and making the final record describe the reviewed
   verdict before any pilot starts.
3. Mobile objector IDs now resolve `desk:item:index` correctly and the sizing
   comment matches the final capped value (`6b0c28e8`). Focused mobile result:
   48 tests passed; analyzer has only 11 pre-existing infos.
4. Two 60-room R4 cards-ON/gate-OFF pilot benchmarks are committed as
   `b87922f1`. A dedicated reporter is being added because the legacy card
   reporter uses a different score and misses `room_cards_repair` turns.
5. Calibration fitting must scale the 60-room target curve to the fit
   repetition; using unscaled counts would make R3–R5 too permissive. Real
   registry `sheet_state` is required before production thresholds can be
   emitted. No real fit or acceptance result exists yet.
6. The original general-improvement coverage register now distinguishes
   implemented, partial and outstanding items (`88e5bf06`). Register parity is
   clean.

## 2026-10-29 — calibration and reporter verification

1. Full mobile suite after the objector fix: **1,927 passed, 0 failed**.
2. Card reporter committed as `719025c1`: repair-aware turn selection,
   normalized-score ICC(A,1), coverage and per-risk/rep diagnostics. `9b1e69d0`
   completed the pass criteria: registry absence, duplicate run keys, bad risk
   levels and skipped anomalous arms all fail loudly.
3. Threshold fit committed as `20b83981`: fit-pool-scaled targets, explicit
   gate-eligible (not final-approval) metrics and refusal to emit production
   ladders from card self-report. `1bded1ba` reuses the repair-aware corpus
   loader and rejects anomalous partial fits.
4. Combined fit/report verification: **61 tests passed**. No real-provider
   threshold has been emitted and no gate acceptance has been claimed.
5. Real-tool diagnostic on the legacy 90-room dsv4 card corpus: only 69/90
   rooms met the exact 20-cell census; normalized evidence ICC(A,1) was
   **0.728**, below 0.85. All 90 lack registry `sheet_state`. This is a tool
   smoke and a negative historical diagnostic, not an `ami-llm`/Ling pilot or
   a production result. Report: `out/cr266-legacy-card-report/`.

## 2026-10-29 — backend integration candidate

1. `ecd1ae7a` implements normalized scoring, exact cards, provider+model
   identities, the mobile wire contract, unresolved-objection contestedness
   and review-safe action/size enforcement. `454aa3d3` adds the registry
   fail-closed rule. Focused backend/CR247/config/provenance verification:
   **113 passed**. Fit/report verification: **63 passed**.
2. A gate-forced PASS no longer routes to resurrection. An allowed rerun must
   apply the same computed size before the safety floor, and review changes
   rebuild the final record instead of leaving stale pre-review state.
3. Missing/empty fact-sheet registry now fails closed instead of masquerading
   as an all-neutral complete room. Frozen AAPL cards-ON/gate-OFF smoke runs
   started on `ami-llm` and Ling in isolated containers with the new app code
   mounted read-only; the Alpha service and gate remain unchanged.
4. The first Ling smoke is INVALID: vLLM currently exposes only `ami-llm`;
   every Ling call returned model-not-found 404 and the room ended NO_VERDICT
   with eight scripted desks. The artifact is preserved at
   `~/cr266_smoke/ling/` and is not evidence. Ling will use a fresh retry only
   when that model is actually available; no server restart or model swap was
   attempted while the `ami-llm` matrix is running.
5. Separate 300-room cards calibration and fresh gate acceptance definitions
   for both models are committed as `e161fca2`. They are not running yet.

## 2026-10-29 — valid ami smoke and R4 pilot started

1. The `ami-llm` frozen AAPL smoke completed with zero scripted desks and a
   split 2/5 PM APPROVE. Its Mac-side contract gate is clean, all 20 cards are
   present and the persisted verdict carries all 125 registry states. One-room
   ICC is correctly unmeasured, not a pass or fail claim.
2. The streamed harness verdict predated `_stamp_next_convene_basis` and had
   `sheet_state=null`. `a898688a` makes V2 record the completed stored verdict;
   two persistence tests bring the combined harness total to **66 passed**.
   The original smoke artifact is preserved; a derived persisted artifact was
   used to verify the registry without another LLM run.
3. Legacy arm keys without an explicit risk segment are supported by
   `5a1ac411`; the older AAPL smoke is no longer rejected for its identity
   shape. Fit/report verification after that addition: **64 passed**.
4. The 30-ticker × two-rep `ami-llm` R4 pilot is running as `bash-rob3u077`
   with cards ON, gate OFF and the fixed persistence harness. Ling remains
   paused on model availability. Production remains unchanged.
5. Full-suite environment diagnosis: the first attempt timed out on live-feed
   fixtures. A second attempt with `LLM_FORCE_PROVIDER=mock` produced 35
   failures + 15 errors because forcing mock invalidates provider fixtures;
   root-cwd also loads the production `.env`. The correct isolated invocation
   is `cd backend && USE_REAL_MARKET_DATA=false .venv/bin/pytest tests/unit/ -q`
   with no provider override. That complete run finished in 23m34s:
   **7,786 passed, 7 skipped, 1 failed**. The sole failure is the unrelated
   pre-existing `DEF465.row` citation of missing `debug_unpack_ios`; every
   CR266 backend test passed. The other track's defect remains untouched.
6. CR265 `ami-llm` production calibration is complete: canonical 300/300 gates
   pass after 14 replacements. Curve 0/1/11/19/34, 27/150 flips (18.0%,
   CI 12.7–24.9%), five nonmonotone tickers, all flips split-vote. Final report:
   `results_t011_ami_risk_calibration_2026-10-29.md`.
7. Early CR266 pilot check at 19 rooms: registry and corpus state are valid,
   but only 14/19 rooms have complete 20-cell evidence and early ICC is 0.545.
   APD rep1 also needs a PM-JSON replacement. Root cause: CR256 repaired absent
   blocks but accepted partial blocks/retries. A local completeness-repair
   candidate is being implemented for the next pilot; the current run remains
   unchanged as the measured control and is not being called a pass.
