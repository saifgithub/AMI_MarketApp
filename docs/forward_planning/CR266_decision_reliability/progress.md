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
   normalized-score ICC(A,1), coverage and per-risk/rep diagnostics. Its pass
   criteria are being hardened so registry absence, duplicate run keys or
   skipped anomalous arms cannot pass silently.
3. Threshold fit committed as `20b83981`: fit-pool-scaled targets, explicit
   gate-eligible (not final-approval) metrics and refusal to emit production
   ladders from card self-report. `1bded1ba` reuses the repair-aware corpus
   loader and rejects anomalous partial fits.
4. Combined fit/report verification: **54 tests passed**. No real-provider
   threshold has been emitted and no gate acceptance has been claimed.
