# CR265 — ideas and trial-results ledger

Running record of prompt/decision-stability hypotheses. Each idea records its
mechanism, exact trial, result and next decision. Sonnet is reserved for final
confirmation; `ami-llm` and Ling are the iteration models.

## Measurement rules

1. Iterate on the established 30 tickers: AAPL APD BA BAC BGS CAG DE DHR FCEL
   JPM LEVI MA MO NKE PLD PYPL RIOT RIVN SEDG SLB SNAP SO SPCE T TMO V WFC WU
   XPEV XRX.
2. Freeze each ticker's complete profile once per trial; verify rendered lane
   hashes in `llm_audit`. Identical feature flags are part of the input.
3. Keep a same-model production control. Record contract health, verdicts,
   votes, adjacent flips, per-desk stances, repairs, duration and invalid rooms.
4. Treat one-ticker results as screening only. Use 30-ticker × two-repetition
   matrices for iteration. Sonnet runs only after a candidate earns confirmation.
5. A stable verdict is not automatically a correct verdict. Geometry repairs,
   independent evidence labels and holdouts remain separate quality gates.

## Completed trials

### T001 — combined 12-persona simplification, live AAPL inputs

1. **Hypothesis:** shorter, lane-specific, non-contradictory prompts improve
   stability.
2. **Trial:** production vs combined candidate; AAPL R4; five reps on `ami-llm`.
3. **Result:** control 80% agreement; candidate 60%; 10/10 contract gates OK.
4. **Decision:** NO-GO. Do not promote or rerun the combined suite.
5. **Evidence:** `results_aapl_ami_llm_2026-10-27.md`.

### T002 — isolated prompts, frozen AAPL, three models

1. **Hypothesis:** the combined result hides useful individual components.
2. **Trial:** control, CIO-only, lane-only and Trader-only; five reps per arm on
   `ami-llm`, Ling and Sonnet; identical rendered fact sheet across 60 rooms.
3. **Result:** CIO 80/20/60% by model; lane 60/100/80%; Trader 80/40/100%.
   Sonnet Trader needed geometry repair in 5/5 rooms.
4. **Decision:** no global change. Retire current CIO-only. Advance lane only on
   Ling and Trader only on `ami-llm`; Sonnet is confirmation-only thereafter.
5. **Evidence:** `results_frozen_ablation_2026-10-28.md`.

## Active trials

### T003 — Ling lane cleanup, 30 frozen tickers

1. **Hypothesis:** lane cleanup improves Ling beyond AAPL by reducing irrelevant
   instruction load and lane conflicts.
2. **Design:** production control and lane-only, 30 tickers × two reps at R4,
   identical frozen profiles, thinking OFF, reviews OFF.
3. **Success criterion:** higher verdict agreement and fewer adjacent flips than
   control without increased repair burden or contract failures. Also require
   per-desk direction results; verdict unanimity alone is insufficient.
4. **Status:** COMPLETE 2026-10-28. Control 13/30 unstable vs lane 5/30;
   approvals tied 33/60. Candidate 60/60 gates OK; control TMO rep2 was replaced
   by a clean pair which itself flipped PASS→APPROVE. Geometry repairs tied at
   seven per arm. Research Manager instability worsened 10→15/30, so the final
   verdict improved without full-pipeline stabilisation.
5. **Decision:** GO to T011 R1–R5 validation on Ling and later Sonnet
   confirmation; no production fold-in yet and no transfer claim to `ami-llm`.
6. **Evidence:** `results_t003_ling_lane_30_2026-10-28.md`.

### T004 — `ami-llm` Execution Desk clarification, 30 frozen tickers

1. **Hypothesis:** separating thesis direction from entry timing reduces
   unnecessary BUY/WAIT and downstream verdict changes.
2. **Design:** production control and Trader-only, 30 tickers × two reps at R4,
   identical frozen profiles, thinking OFF, reviews OFF.
3. **Success criterion:** improved verdict and Trader-stance stability without
   increased geometry repairs or incoherent R:R.
4. **Status:** COMPLETE 2026-10-28. Control 10/30 unstable vs Trader 12/30;
   approvals fell 24/60→18/60. Candidate LEVI rep2 failed PM JSON; replacement
   passed but flipped APPROVE→PASS. Fundamentals/Market/News improved, yet Trader
   and Research Manager worsened and the final verdict regressed. All 22 flip
   pairs involved split PM votes.
5. **Decision:** NO-GO. Retire this variant for `ami-llm`; no R1–R5 and no
   production fold-in. Next work targets the evidence/decision interface and PM
   vote boundary, not another Trader rewrite.
6. **Evidence:** `results_t004_ami_trader_30_2026-10-28.md`.

## Queued ideas

### T005 — decompose desk variance from PM variance using existing rooms

1. **Hypothesis:** most residual flips originate before the PM, so the next
   intervention should target the evidence channel rather than CIO wording.
2. **Design:** replay the PM against the exact recorded transcript/prompt from
   completed rooms, then replay selected upstream desks against their exact
   recorded prompts. No new full-room generation and no Sonnet cost.
3. **Status:** PARTIAL 2026-10-28. Existing vote audit before any replay:
   Ling had 5/17 original flip pairs with unanimous PMs in opposite directions;
   12 involved split votes. The TMO replacement added another split-vote flip.
   `ami-llm` had 0/22 unanimous-opposite pairs; all 22 involved split votes.
   PM vote boundaries are therefore a material amplifier, not just upstream text.
   Exact-prompt replay remains queued.

### T006 — temperature as calibration hygiene, not a stability claim

1. **Hypothesis:** low desk temperatures and PM T=0 reduce variance modestly but
   leave the structural residual.
2. **Design:** same frozen rooms, default vs explicit temperatures on `ami-llm`
   and Ling. Compare with T003/T004 without conflating prompt edits.
3. **Status:** proposed after T003/T004.

### T007 — typed evidence census before narrative debate

1. **Hypothesis:** a fixed, lane-specific evidence record is more stable than
   allowing each run to select a different natural-language evidence subset.
2. **Design:** enable and extend CR256 cards per model, compute data presence
   and objection status in code, and make the PM consume that record. Compare
   evidence-card agreement before measuring verdicts.
3. **Status:** structural candidate, not a prose-only prompt arm.

### T008 — separate the educational transcript from the binding decision

1. **Hypothesis:** the 12-agent narrative can remain the product experience while
   a typed evidence/geometry record produces a steadier verdict.
2. **Design:** narrative unchanged; decision reads only the typed record. Test
   against the full transcript control on the same frozen profiles.
3. **Status:** architectural candidate after T007 evidence is available.

### T009 — explicit contestedness instead of forced confidence

1. **Hypothesis:** some borderline flips are irreducible and should be presented
   as contested rather than hidden behind a confident binary label.
2. **Design:** use vote margin, evidence-score distance and repair/outage flags
   to label marginal rooms; assess calibration and user comprehension alongside
   flip rate.
3. **Status:** product-policy candidate, not a substitute for T007/T008.

### T010 — human analyst consensus as external calibration

1. **Hypothesis:** current human analyst views provide a useful comparison for
   model verdicts and can identify names needing manual review.
2. **Design:** capture MarketBeat consensus rating, analyst count, target range,
   close and bull/bear themes for all 30 tickers. Compare with later Room results.
3. **Result:** completed 2026-10-28 for all 30. Six Reduce/Sell and eight Hold
   names balance the Moderate Buy majority. Several Reduce/Sell names still show
   large target upside, and BGS/XRX/SPCE have only 3/4/7 covering analysts.
4. **Decision:** use as a review signal only, never ground truth. Consensus is
   already partly present in the Room fact sheet, and rating/target upside are
   separate measures.
5. **Evidence:** `human_analyst_consensus_2026-10-28.md`.

### T011 — risk-level calibration against the human market view

1. **Hypothesis:** the useful final comparison is not only flip rate, but how
   approval propensity and stability change across R1–R5 relative to human
   analyst consensus.
2. **Design:** after R4 candidate filtering, run the production control and any
   earning candidate on 30 frozen tickers across R1–R5 on `ami-llm` and Ling.
   Report per-model/per-risk approval rates, flips, vote margins, per-ticker
   monotonicity, and agreement/disagreement with the T010 human snapshot.
3. **Report dimensions:** where AMI is more conservative or permissive than the
   Street; where it agrees; where Reduce/Sell or low-coverage names receive
   APPROVE; and whether the change improves calibration without lowering evidence
   or geometry quality.
4. **Status:** Ling production + lane-only R1–R5 matrix running 2026-10-28
   (task `bash-dyn6gaxn`), enabled by the T003 result. `ami-llm` production-only
   R1–R5 matrix also running (task `bash-a2k79um3`); no prompt candidate advanced
   after T004. V2 now supports `risk_scores` with collision-safe arm keys.
