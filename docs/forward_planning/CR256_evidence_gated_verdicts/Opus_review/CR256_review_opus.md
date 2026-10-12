# CR256 — Independent review (Opus)

**Reviewed:** `CR256_evidence_gated_verdicts.md` at `48d46ea0` (spec + purpose section)
**Reviewer:** Claude Opus 5.5 · **Date:** 2026-10-12 · **Mode:** review only. No CR text, code or run data was changed.
**Brief:** be critical but constructive, aim to improve the capability, and back every suggestion with evidence.

**Method.** I read the CR and everything it cites: analysis_r3–r7, `EXPERIMENT_LOG.md`, CR255
`target_curve.md` / `decision_record_spec.md` / `jev_review_2026-10-12.md`, CR257, and the code
anchors. I then ran new measurements over the four committed 300-room arms (1, 9, 10+fix, 11). These
need no new rooms and no network access. Every number below that is marked **[R]** is reproduced by
[`repro_cr256_review.py`](repro_cr256_review.py), and its full output is in
[`repro_output.txt`](repro_output.txt) (`python3 -I repro_cr256_review.py`). Any other number is cited
to the document it comes from.

---

## 0. Verdict

**The direction is right. The spec is not build-ready.** The record strongly supports the CR's core
idea: evidence becomes a computed input, and code decides which actions the PM may take. When I
simulated the CR's own Layer-3 procedure on a *direction-aware* proxy score, it did what the program
has been unable to get from prompts:

1. It hit the target curve exactly.
2. It cut per-ticker monotonicity violations from **20/60 to 1/60** (dsv4 production) **[R]**.
3. It cut verdict flips from 17–27% to **9–17%** **[R]**.

Five defects would still sink the build as written. All five are cheap to fix on paper:

1. **AC4 is circular.** "APPROVE rooms score higher" is guaranteed when the gate approves exactly the higher-scoring rooms.
2. **The target curve and the holdout rule contradict each other at R5** (60/60 approvals vs. "holdouts out at every level").
3. **The Layer-2 core is the measured-noise component.** `net_support` signs evidence by desk membership. Its rep-to-rep reliability is r = −0.11…+0.25 **[R]**. A gate on it would flip *more* than today's PM.
4. **Both determinism prerequisites are wrong in code:**
   - `seeded=False` is the *fixed*-order mode, so turning seeding on adds variance.
   - Temperature is not plumbed anywhere. `force_provider()` exits if you pass one.
5. **There is already a per-level bar in the verdict path.** The CR228 graded vote, 4/4/3/2/2 of 5, is not mentioned. With the CR's gate added, the spec would have two per-level bars in series.

The rest of this review covers each defect with its evidence and a concrete fix (§2–§4), answers the
CR's four open questions with data (§5), and proposes a revised build sequence (§6).

---

## 1. What the CR gets right (keep)

1. **Structure over prose is the correct conclusion from the record.** analysis_r4 §1 (sub-cap inert), analysis_r5 (disposition moves only the level of willingness), analysis_r7 (tm-all: 27% flips) and analysis_r6 (the same picture on both models) all point the same way.
2. **Action-set restriction is the right enforcement point.** It extends the house pattern: the deterministic floor runs after the LLM decides (`room_runner.py:5070-5073`, DEF056). CR228 vote arithmetic is "structural, not prompt-hoped-for" (`_approve_vote_threshold` docstring).
3. **The pieces that should stay are already in the spec:** per-model thresholds (§5), a frozen-then-versioned fit, an additive `llm_audit`, and degrade-loudly card parsing (`card_malformed`).
4. **Holdouts work as falsifiers.** Using RIOT/APD as tests that a bare threshold cannot pass is good design (target_curve.md).
5. **The code anchors are accurate.** All nine resolve at HEAD (`2847c137`). The backend has no changes since the stated `bf0fa99f`, so the line numbers are exact.

---

## 2. Blocking findings (fix in the spec before any build)

### B1. AC4 is true by construction, and nothing measures whether decisions are *right*

**CR text (§4.4):** "Discrimination Δ positive at every level (APPROVE rooms score higher)."

**Evidence.** Layer 3 approves iff `evidence_score ≥ T(level)`. Holdouts only remove approvals. So
whenever AC4 is measured on `evidence_score`, every APPROVE room scores at least as high as every
non-holdout PASS room. Δ > 0 follows from the definition and does not test anything. At R5, a 60/60
target leaves no PASS rooms, so Δ is undefined. At R1, Δ rests on 5 rooms.

**Why it matters.** The program's original question is whether decisions track evidence. That needs
a criterion the gate does not consume. The jev_review conclusion is "the judge measures what it
measures honestly; it measures the wrong thing for the bar" (§4.5). AC4 has to be scored on something
other than the score that drives the gate.

**Fix.**
1. Re-state AC4 against signals the gate does not read. Options:
   - Jev turn-level grades on the *winning side's* cards, if the gate uses self-grades.
   - The CR257 Jev-decision label.
   - A hand-audited stratified set, using the jev_review protocol of about 20 rooms.
2. Add holdout recall as a separate, explicit accuracy measure.
3. Report Δ only at levels where both classes have n ≥ 10.

### B2. The target curve and the holdout rule cannot both hold at R5, and the holdout rule is not yet defined

**Evidence.**
1. target_curve.md sets **R5 = 60/60**. The same document says RIOT-shaped names "must stay out at every level" and APD/BA-shaped names should PASS "even at R5". CR256 AC1 (±8) and AC3 (0 holdout approvals) are therefore jointly infeasible as soon as more than 4 holdout tickers exist.
2. In all 20 proxy-gate simulations, RIOT, APD and BA are approved **2/2 at R5** **[R]**. A quantile fit to 60/60 approves everything.
3. CR256 says APD-shaped means "negative SBC-adjusted FCF", encoded as a data check. Applied literally to the fact sheets, that rule bars **7 of 30 tickers**: APD, BA, FCEL, RIOT, RIVN, SNAP, SPCE **[R]**. That caps R5 at **46/60**, outside AC1's ±8. The datum is also **absent for 9 tickers** (BAC, JPM, MO, PLD, SO, T, WFC, WU, XPEV) **[R]**, so the rule also needs a `data_present: no` branch.
4. The RIOT rule ("high grounding, negative thesis") is not yet a data check. "Negative thesis" is a judgment.
5. analysis_r6 already raised this. Finding 3 ("≈11 uninvestable names makes 100% at R5 unattainable by construction") and Recommendation 2 ("Saiful decision: … re-anchor as % of investable universe?") were both left open. CR256 uses the unadjusted curve without addressing them.

**Fix (needs Saiful's decision before any fit).**
1. Re-anchor R5 to the investable universe, or set AC1's tolerance per level net of holdouts.
2. Define each holdout as an explicit predicate over **code-computed fact-sheet fields**. The SBC-adjusted FCF line is already "AMI's own arithmetic, computed in code". Include the absent-datum branch.
3. Publish the resulting holdout list for the 30-ticker universe before fitting, so AC3's denominator is fixed in advance.

### B3. Both determinism prerequisites are backwards or unimplementable

**CR text:** "harness runs must stop disabling it (`seeded=False` — find and remove the harness-side switch, `library/runner.py`)" and "pin analysts to 0.2 via `force_provider()`".

**Evidence.**
1. `seeded=False` is not a harness switch. It is the backend default (`backend/app/core/config.py:851`, `room_debate_order_seeded: bool = False`), forwarded in `docker-compose.yml:428`. When it is false, the code leaves the order untouched: "exactly today's fixed Bull-then-Bear order" (`room_runner.py:7506-7511`). Turning it **on** selects the order from `run_id.int % 2` (`room_runner.py:245-258`). Run ids are uuid4, so two reps of the same cell would get different orders about half the time. That is **more** rep-to-rep variance, not less. CR219 R58's purpose was anchoring balance (`library/anchoring.py:30`), not determinism.
2. `force_provider(temperature=…)` unconditionally raises `SystemExit("temperature is not plumbed through LLMGateway/RoomRunner anywhere in this codebase (RES009 01-06) …")` (`library/provider_gateway.py:111-122`). `grep -rn temperature backend/app` returns nothing. Matrix arms also run in-container through `room_benchmark.py` with `VLLM_*` env (EXPERIMENT_LOG §2), not through `force_provider`.

**Fix.**
1. Delete the seeding bullet. If balanced order is wanted for measurement, seed by `(ticker, risk_level)`, not `run_id`, so the two reps of a cell share an order.
2. Re-scope temperature pinning as new backend plumbing in `LLMGateway`/`RoomRunner`, with a compose-parity entry per CR040.
3. Measure first whether pinning helps. `direct_call` replay is the path the gateway error message itself recommends. A reasoning model at 0.2 is an untested setting in this program, and the reliability gain is unmeasured.

### B4. Layer 2's core term is the component the data says is noise

**CR text:** `net_support` = mean(bull-side cards) − mean(bear-side cards), "the metric `tools/net_support.py` computes today". The CR says the single-metric bar "died of score-ties", and that adding dimensions fixes this.

**Evidence [R].** I separated the two explanations. `desk_net_cont` is the same metric made continuous with Jev's per-choice probabilities, which removes ties (55–60 distinct values per level instead of 6–9). If ties had killed the bar, this version should work. It does not:

| Arm | Score | Rep-to-rep r | Simulated gate flips | Non-monotone ticker paths |
|---|---|---|---|---|
| dsv4 prod | desk_net (today) | +0.21 | 23% | 18/60 |
| | desk_net_cont (no ties) | +0.18 | 25% | 13/60 |
| | **stance_signed** | **+0.84** | **11%** | **1/60** |
| dsv4 disp | desk_net / cont / stance_signed | +0.11 / +0.21 / **+0.73** | 24% / 22% / **17%** | 15/59 / 12/59 / **1/60** |
| ami clean | desk_net / cont / stance_signed | −0.11 / −0.10 / **+0.78** | 24% / 21% / **15%** | 12/47 / 14/47 / **2/50** |
| dsv4 tm-all | desk_net / cont / stance_signed | +0.25 / +0.23 / **+0.75** | 29% / 23% / **9%** | 25/60 / 17/60 / **5/60** |
| *Actual PM verdicts* | | | *17% / 21% / 15% / 27%* | *20/60 / 20/60 / 7/50 / 21/60* |

The definitions are in `repro_cr256_review.py`. In short, `stance_signed` is the mean over non-trader
turns of (STANCE sign: for = +1, against = −1, neutral = 0) × (Jev expected support).

**Why.** `net_support.py:31` assigns `fundamentals_analyst` and `trader` to the bull desk
whatever they argue. The jev_review §4.4 transcripts show that fundamentals desks argue *against* in
some rooms (APD-rep1), and in DE-rep1 even the bull researcher argued against. The jev_review's own
§2.3 diagnosis is that "direction-agnosticism confirmed at the turn level". The bar died because the
metric has no reliable direction. Ties were a secondary symptom.

**Consequence.** A gate built on desk-signed `net_support`, even with more dimensions, would flip
*more* often than the PM does today (22–29% vs. 15–27%), with or without ties. AC2 would fail.

**Fix.** Sign every card by its own `direction` field, never by desk membership. State this
explicitly in Layer 2. The card schema already carries `direction`, but the formula text points back
to the desk-based tool. Make `stance_only` (direction with no grading) the **baseline the composite
must beat**. It already achieves rep-to-rep r = +0.71…+0.83 and 11–18% simulated flips **[R]**.

### B5. A per-level bar already exists in the verdict path, and the CR does not mention it

**Evidence.** `pm_self_consistency_samples` defaults to 5 (`config.py:751`). `_vote_pm_samples` →
`_approve_vote_threshold` then requires 4, 4, 3, 2, 2 APPROVE votes of 5 for R1–R5 (`room_runner.py:9224`, docstring: "three distinct, monotonic bars"). Every room with a vote record in the four arms ran with `samples=5` (13 ami R3 rooms have no vote record) **[R]**.

1. **On ami-llm the vote bar binds.** Votes are spread (R5: 28/11/12/1/3/5 rooms at 0–5 votes). Lowering R4/R5 to 1 vote would give 24 and 32 approvals instead of 10 and 20 **[R]**. Part of ami's "conservative" curve is vote arithmetic, not evidence.
2. **On dsv4 the vote bar barely binds.** Votes are bimodal at 0 or 5, so moving the bar by ±1 vote shifts approvals by at most 5 at any level, against up to 13 on ami **[R]**.

**Why it matters.** Layer 3 adds a second per-level bar in series with the vote bar. Its fit would
absorb whatever the vote bar is already doing, and that differs by model. "Fit once per model" then
silently depends on `PM_SELF_CONSISTENCY_SAMPLES`.

**Fix.** State the vote's role after the gate. Either retire the graded threshold when the gate is on
(the PM's 5 draws then become narration candidates only), or freeze it and fit T conditional on it. In
both cases, record `samples` and the vote outcome in the decision record.

---

## 3. Major findings (fix in the spec; none blocks a feasibility pass)

### M1. "Census kills failure mode B at the source" overclaims

**Evidence [R].** Among flipped rep pairs, the PM was **unanimous both times with opposite answers**
(0/5 vs. 5/5 votes) in **15/26** (dsv4 prod), **17/31** (disp) and **24/40** (tm-all) pairs. The
PM was sure each time. The *debate* changed direction between reps. jev_review §4.4 shows the same
in a single pair (APD-rep1/rep2: identical sheet, fundamentals desk and RM flipped). A fixed checklist
makes *coverage* identical across runs. It does not make each card's *direction* or *grade*
identical, and that is where the flips originate. On ami-llm only 2/22 flipped pairs were unanimous,
so its instability sits closer to the vote boundary, which is a different mechanism (see B5).

**Fix.** Make card-level test-retest the Layer-1 acceptance metric: agreement on `direction` per
(ticker, level, item) across reps. Pilot it on a few tickers before any 300-room matrix (§6, step 4).

### M2. The checklist the census enumerates is not where the decisions are made

**Evidence.**
1. All nine card-filing personas carry the **same five fundamental items**: earnings quality, value creation, valuation hygiene, balance-sheet survival, moat durability (`content/agents/*.md`, `## Evaluation parameters`). Market, news and social desks would be filing fundamental cards outside their lane.
2. The PM's dominant PASS reason is timing. `catalyst_wait` accounts for 130 of 158 high-support PASSes (decision_record_spec; EXPERIMENT_LOG arm 1: 82%). Technical setup is next. Neither is a checklist item.
3. `factor_coverage` (the share of items with data present) becomes largely a **ticker constant**. Nine of 30 tickers lack the SBC-adjusted FCF datum, and the banks lack it structurally ("the sheet's TTM free cash flow is not live this call") **[R]**. The composite would penalise those names at every level for reasons unrelated to the debate.

**Fix.**
1. Make the census lane-specific: technical setup and levels (market desk), catalyst and timing (news), sentiment (social), mandate fit (RM/debators), plus the five fundamentals.
2. Drop `factor_coverage` from the score, or normalise it against what the sheet *could* supply for that ticker.

### M3. Several gate inputs are still controlled by the actor being gated

**Evidence.**
1. **Objection resolution.** Under CR256, the PM marks objections "resolved" in its rebuttal, and that count enters the score. This reverses `decision_record_spec.md`, which computed `unresolved_objections_count` from Jev grades of bear turns.
2. **`data_present`.** It is self-reported, but the fact sheet is code-built and already knows what is absent (the "not live this call" lines above).
3. **`catalyst_proximity`.** It is taken from LLM `key_numbers`. `decision_record_spec.md` requires it to be **computed from structured fact-sheet fields** (earnings date, FOMC countdown), with an LLM value only as a flagged fallback that is never invented.
4. **Self-reported confidence does not rank-order with judged support.** A *conviction* proxy measures this today **[R]**: turns stated LOW are Jev-well-supported 67/67/73/70% of the time across the four arms, MEDIUM 43/39/53/32%, and HIGH 56/56/71/44%. Stated-HIGH rates are also strongly desk-asymmetric. Bear researcher vs. bull researcher: 57% vs. 17% (dsv4 prod), 63% vs. 21% (tm-all). Self-grades with that asymmetry would bias `net_support` toward the bear side.

**Fix.** Apply the rule from `decision_record_spec.md`: *every field is computed, or explicitly LLM-reported, never both silently*.
1. Compute `data_present` from the fact-sheet field registry.
2. Compute objection resolution: an objection is resolved iff an opposite-direction card exists on the same `item` with grade ≥ the objection's.
3. Compute catalyst proximity from structured fields.
4. Treat self-grades as tie-breakers only, never the primary term (see §5 Q1).

### M4. `catalyst_proximity` has no defined sign and is not evidence quality

It is the main reason the PM *waits* (M2.2). Adding it to an "evidence" score with a fitted weight
mixes timing preference with evidence strength, and the fit could give it either sign. **Fix:** keep it
out of `evidence_score`. Apply it as a separate, explicit policy rule ("APPROVE-eligible but catalyst
within N days → size or wait"), or report it as a diagnostic, which was its role in the
decision_record_spec Phase-B regression.

### M5. Weights are "fit, not hand-set (§4)", but §4 has no fitting objective, and the curve cannot identify them

**Evidence.** With a per-level quantile threshold, *any* weight vector reproduces 5/15/30/45/60
exactly on the calibration arm, and the simulated gate hits the targets for every proxy **[R]**. The
curve criterion therefore says nothing about weights. The spec also fits 4 weights, 5 thresholds and
the sub-cap map on 300 rooms, then accepts on the **same 30 tickers**.

**Fix.**
1. Choose the objective explicitly. Maximise rep-to-rep reliability of the score (test-retest r) plus agreement with the *independent* label from B1.
2. Cross-validate by **holding out tickers**, not just reps.
3. Constrain T(1) ≥ … ≥ T(5) so one name cannot clear R2 and fail R3 on the same score.
4. Add a fresh ticker set to the final acceptance run.

### M6. Gate failure and override semantics are unspecified (DEF059 class)

The spec says a malformed card sets `card_malformed`. It does not say what the **gate** does when
`evidence_score` cannot be computed. **Fix:**
1. A missing or uncomputable score → PASS with an honest reason. This is the existing DEF058/DEF059 fail-safe path: `_parse_pm_verdict` "fails safe to PASS rather than fabricating APPROVE" (`room_runner.py:3133-3137`). The gate must never be skipped silently.
2. Compute the gate *before* the PM call and pass the allowed actions and computed size as context, so the narration stays coherent.
3. If the PM still emits a disallowed action, treat it as a parse failure → PASS, with `overridden_from_llm=true` (the field already exists, `schemas/room.py:135`). Never print APPROVE narration under a PASS record.

### M7. Debator turns are missing from every Jev log, so OBJECTIONS cannot be audited

**Evidence [R].** None of the four arms' Jev logs contains an `aggressive_`, `conservative_` or
`neutral_debator` turn, although `jev_score_runs.py:30-33` lists them in `PROSE_AGENTS`. The cause is
therefore upstream of the scorer, in what `llm_audit` records for those turns. I did not verify the
exact cause, because that needs DB access. jev_review §2.2/§5.3 already names this as the cause of
the ±1/3 net quantisation.

A second conflict: the CR's card-level Jev audit needs a **new** Jev question, because today's four
questions are turn-level, and CR257 §6.3 freezes the Jev question set.

**Fix.** Make "debator turns present in `llm_audit` and Jev-scored" an explicit prerequisite, and
reconcile the question-set freeze with CR257.

### M8. AC2 ("flips < 10%") has no stated precision and is at the edge of what the proxies reach

With 150 pairs, a 10% observed rate carries a 95% CI of about ±5 points. The best direction-aware
proxies land at **9–18%** **[R]**, so AC2 is borderline even for a working gate. **Fix:** pair AC2
with a leading indicator that can be measured on a smaller pilot (score test-retest r ≥ 0.85), and state
AC2 with its CI or the number of pairs it needs.

---

## 4. Accuracy corrections to §0–§1 (the "do not re-litigate" table)

1. **ami net-support r = +0.03.** jev_review §3.3 could not reproduce this and recommends "+0.04…+0.09 (join-dependent)". The CR table still quotes the point value.
2. **"Threshold lift 0 pts" (dsv4 production).** Per level, the lift is **+10 pts at R3 and R4**, with r = +0.327/+0.324 at R2/R3 (jev_review §3.1–3.2). The failure is concentrated at the R1/R5 tails. That matters for where a bar has work to do.
3. **Failure mode A is stated too strongly.** The PM *does* follow the debate's direction. `stance_only` correlates with the verdict at r = +0.55/+0.78/+0.78/+0.69 for R2–R5 on dsv4 production, and +0.33…+0.69 at R2–R5 in the other arms **[R]**. "No discrimination" is a property of the direction-agnostic grounding metric, not proof that the verdict ignores the debate. This **strengthens** the CR's case: a direction-aware gate will mostly agree with the PM's direction while fixing what the PM gets wrong, which is per-draw stability, level calibration and per-name monotonicity. It also means correctness needs the independent check in B1.
4. **Failure mode B evidence.** Remove "`seeded=False` in harness runs" as a cause (B3).
5. **Wording (§2 Layer 3).**
   - "Holdout rules override thresholds both ways" is wrong. Both rules are *exclusions* (target_curve.md).
   - "grounded-bear cases … pass at every level" reads as "pass the gate". It should say "verdict PASS at every level".
   - "R1=5/15/30/45/60" should read "R1–R5 = 5/15/30/45/60".
6. **Sub-cap map `f(score, ATR)`.** No measured evidence for ATR is cited. The only measured size-coupling evidence is **per-name** (analysis_r4 §2: DHR and MO approve at ≤3% and refuse at ≥4%; SO and CAG never approve), and r4 Recommendation 4 says to calibrate per name, not per level. Either justify ATR or drop it from v1.

---

## 5. Answers to the CR's open questions (§6), with evidence

1. **Card grade trust: is a self-grade bias measurement needed?** Yes, but the existing data already answers most of it.
   - Self-reported conviction does not rank-order with Jev support (LOW turns are the best-supported, M3.4), and it is desk-asymmetric.
   - Direction carries the signal. `stance_only` (no grades at all) already reaches rep-to-rep r = +0.71…+0.83, and adding Jev grades (`stance_signed`) changes that by at most ±0.04 while mainly breaking ties (12–14 → ~59 distinct values) **[R]**.
   - **Recommendation:** let self-grades break ties only. Gate primarily on direction plus code-computed features. Keep Jev audit sampling as planned to detect drift.
2. **Gate bypass: are `key_numbers` enough?** No. Close the surface structurally.
   - Compute `data_present` in code (M3).
   - Verify cited numbers deterministically against the fact sheet. The numeral-matching and plausibility machinery in `_match_level` / DEF237 / DEF242 (`room_runner.py:4675-4700`) is a starting point.
   - Do **not** use Jev `figures_consistent` for this. jev_review §1.5 found its scores of 0.46–0.65 on turns where every figure checked out.
3. **Fit stability: is n = 60 per level enough?** It is adequate for the curve on the same tickers, but it is not the binding risk. **[R]** Thresholds fit on rep-1 rooms (n = 30 per level) and applied to rep-2 rooms land within about ±4 of the per-30 target at R2–R5 for `stance_signed`: dsv4 prod 1/11/15/21/30 vs. targets 2.5/7.5/15/22.5/30. R1 is relatively noisy, because its quantile rests on 2–5 rooms. **Recommendations:**
   - Fit one monotone ladder over all 300 rooms rather than five independent quantiles.
   - Bootstrap T(1).
   - Spend the extra reps on **held-out tickers** (M5), not a third rep of the same 30.
4. **Sub-cap map: linear or step?** Prefer **continuous and monotone from T upward**, so the smallest size sits at the threshold.
   - Rooms near T are the flip-prone ones (B4/M1).
   - A continuous map makes a borderline flip cost a minimum-size position.
   - A step map adds discontinuities that create new size flips between reps.
   - This is reasoning, not a measurement. Validate it on the pilot. User-facing copy can still show bands derived from the continuous value.

---

## 6. Recommended revised sequence

1. **Step 0 — zero-run feasibility pass (cost: CPU only).** Promote `repro_cr256_review.py`'s proxy-gate simulation into the planned `tools/evidence_bar.py`.
   - This *is* the "retroactive validation on the existing scored rooms" that §4 calls for, without the LLM card re-extraction step, which would measure an extractor rather than the system.
   - Baselines to beat: `stance_only` and `stance_signed` (B4).
2. **Saiful decisions:**
   - R5 target vs. the investable universe (B2).
   - Exact holdout predicates and the published holdout list (B2).
   - What happens to the graded vote when the gate is on (B5).
3. **Prerequisites:**
   - Debator turns into `llm_audit`/Jev (M7).
   - Delete the seeding bullet. Temperature only after a `direct_call` replay measurement (B3).
4. **Card schema v2:**
   - Per-card `direction` drives the sign.
   - Lane-specific items, including catalyst, technical and mandate fit (M2).
   - `data_present`, catalyst and objection resolution computed in code (M3).
   - Gate-before-PM with fail-safe PASS (M6).
5. **Card pilot before any matrix:** a handful of tickers × one mid level × 3 reps. Go/no-go on card-direction test-retest and score reliability (M1, M8).
6. **Fit and accept:**
   - Monotone ladder, ticker-held-out CV, an objective that does not depend on the curve (M5).
   - AC4 on an independent label (B1).
   - Fresh matrix including held-out tickers.
7. **CR257 in parallel.** It is offline over the same arms and gives the independent decision label that B1 needs. Note: CR257's evaluation (its §4.3) scores discrimination against desk-based net support, the metric shown in B4 to be unreliable. It should use a direction-aware reference too.

---

## 7. Caveats on this review's own evidence

1. The proxies use **Jev grades on every turn plus the existing STANCE envelope**, not self-graded claim cards. They show what a direction-aware score *can* do. They do not forecast card performance.
2. All arms ran with the veto/resurrection review off and on the same 30 tickers. The simulated flip rates are in-sample for the thresholds.
3. A gate that tracks desk direction mostly re-expresses the debate. Its measured value is stability, calibration and monotonicity. Whether the debate's direction is *correct* remains unmeasured (B1).
4. The ami arm merges the R2/R5 fix re-runs over the first pass. That gives 290 rooms with Jev data, because R3 coverage is partial (analysis_r6).
