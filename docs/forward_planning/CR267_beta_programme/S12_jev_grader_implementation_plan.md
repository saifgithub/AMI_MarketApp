# CR267 gate S12 — narrow-question judge and coded decision rule: implementation plan (for discussion)

**Date:** 2026-11-18 · **Status:** APPROVED (gate S12, 2026-11-18, rulings in §0) · **Author:** CR267 track B

**What this is:** the implementation plan for WP-22 (narrow-question judge and bake-off) and WP-23 (coded decision rule), written for Saiful to discuss and approve before any Jev, grader or decision-rule change. **Why:** Saiful, 2026-11-18: *"before you start making changes for JEV and the LLM, please pause so we can discuss implementation plans."* S11 (the LLM work) was approved after such a discussion (`S11_llm_implementation_plan.md` §3a); this is its sibling. File:line references are to branch `beta/cr267` as read on 2026-11-18. Anything I could not verify says so; every estimate is labelled.

## 0. Saiful's rulings (2026-11-18): gate S12 approved

1. **Q4, rule power:** the rule decides, and the CIO only narrates; shadow first on Alpha. *"Rule decides, shadow first."*
2. **Q1, ground truth:** *"didn't we agree to use the current market analysis of the ticker?"* Yes: CR267 §1 item 6 makes **analyst consensus the reference for "correct"**. So there is **no human labelling**. The six-question answers are checked with no human in the loop (§4.2, revised), and the grader is **picked on the consensus scores** (§4.4, revised). Consensus stays out of every Room input (CR275) and is never a fitting target; using it to evaluate and pick the grader is what the plan intends.
3. **Q3, Jev before terms:** test only, on harness rooms, on trial access; ask TypeSafe for written terms now. Production waits for §5.4.
4. **Q2 and Q5–Q10:** recommendations accepted:
   - a $50 bake-off hard cap;
   - "decision unavailable", with the debate kept, a refund and retry, when the grader is down;
   - include the second-model judge;
   - switch off the veto and resurrection reviews when the rule decides;
   - Contested is stored as PASS plus a flag;
   - the card shows only the answers that differ from the Street, or that changed on a flip;
   - keep the six questions as drafted.
5. **No Anthropic models in the app (Saiful, 2026-11-19).** The reference labeller is Ling-3.0-flash-Fin on our own host, not Claude Sonnet (§4.2, §4.5). No grader, judge or reviewer may be an Anthropic model.

---

## 1. What a tester would see differently

1. Today the CIO decides APPROVE or PASS by taking five independent reads of the debate and counting votes. Re-running the same ticker can flip the answer: in CR266's last run, 13 of 30 tickers flipped between two reps (`CR266_decision_reliability/progress.md`, 2026-11-18 entry).
2. After WP-22/23 the Room debates exactly as now, then six fixed questions about the debate are answered by one grader. A written rule turns the answers into **Approve, Pass or Contested**. The CIO then explains the computed result and cannot change it. The mandate safety check still runs last and can still veto an Approve.
3. The tester sees the same Room, a verdict that is stable for stable inputs, and (with WP-24/25) a plain reason when a verdict changes ("the bear's objection is now answered with numbers"). If the grader is down they see "decision unavailable" with the debate intact, never a guessed verdict.
4. What we are **not** promising: that the new verdicts are more correct. Jev repeats itself (299 of 300) but no one has shown its calls are right (CR267 §6 Phase 2 preamble). The bake-off measures it; the report must say plainly if correctness stays unproven (CR267 §8 item 3).

## 2. The current decision path (verified in code)

Who decides APPROVE/PASS today, in order, all in `backend/app/services/room_runner.py` unless stated:

1. **CIO step.** `_run_cio_step` (`:5605`) is the only place the verdict is made; `run()` calls it from `:8640`. The CIO is `AgentId.PORTFOLIO_MANAGER` (`schemas/agents.py:22`), the code name for the CIO.
2. **Five independent CIO reads.** `_pm_samples = max(1, int(settings.pm_self_consistency_samples))` (`:5706`), default 5 (`core/config.py:919`). Draws come from `_draw_pm_candidates` (`:10441`), each one a `_stream_pm_response` call (`:10576`).
3. **The vote is counted in code.** `_vote_pm_samples` (`:10519`) uses `_approve_vote_threshold` (`:10487`): at n=5 the bar is 4 approves for risk 1–2, 3 for risk 3, 2 for risk 4–5. So the LLM decides; code only tallies.
4. **Fail-safes.** CIO unreachable → PASS with a sentinel reason (DEF059, `:5832`). Unparseable → PASS "did not return a machine-readable verdict" (`:5918`).
5. **Optional evidence gate (CR266).** If `room_evidence_gate_enabled` (`core/config.py:1303`, default False) and the score is below threshold, an APPROVE is forced to PASS (`:5932`). It needs the cards channel (`room_cards_envelope_enabled`, `:1279`, default False).
6. **The mandate check.** An APPROVE goes through `_floor_pm_approve` (`:5967`; defined `:6190`) into `enforce_safety_floor` (`agents/safety_floor.py:987`), which returns anything but APPROVE unchanged (`:1026`), checks the 8-K Item 4.02 veto first, then `check_mandate_compliance`, and turns violations into REJECT. A prompt-level `SAFETY_FLOOR_BLOCK` (`safety_floor.py:113`) is also appended last to the CIO's prompt.
7. **Two more LLM auditors can change the result.** After the floor, `_apply_verdict_review` (call at `:6012`) runs a veto review (APPROVE → PASS; `room_veto_review_enabled`, `core/config.py:1254`, default **True**) and a resurrection review (PASS → CIO re-runs once; `room_resurrection_review_enabled`, `:1267`, default **True**).
8. **Output guard** on the CIO's text (`_guard_pm_text`, `:6066`), then the narration is streamed.

What this means: today an LLM decides up to three times (the vote, the veto review, the resurrection re-run), and the mandate check is the only deterministic layer.

Facts the design depends on:
- The Room no longer sees Street ratings or targets (CR275, `backend/app/services/street_view_blind.py`, called from `room_prompts._format_profile`; `CR275_room_decides_blind.md` Change 1–2). The judge input must be built from the same blinded profile.
- Desks do see the user's portfolio snapshot and journal context (`room_prompts.py:2050`, `:2469`; call site `room_runner.py:9862`). Their turn text can therefore quote the user's holdings. This matters for §5.
- Contested already has a home: `DecisionRecord.contested` / `contested_reasons` (`schemas/room.py:151–152`), which the mobile app reads (`mobile/lib/models/room.dart`, `mobile/lib/widgets/room/room_board.dart`; I only confirmed those files mention the field, not how they render it). There is no `CONTESTED` value in `VerdictAction` (`schemas/room.py:14`).
- The execution numbers (size, entry, stop, target) come from the CIO's JSON today. `ctx.trader_*` fields are defaults (`room_runner.py:510–513`) and `trader_size_pct` is the mandate cap, not an Execution Desk proposal (comment at `:3676`).

## 3. Proposed design

### 3.1 The question set (versioned)

One file, `questions_v1`, proposed at `content/room_judge/questions_v1.json` (location is my proposal). Each question has an id, a type, closed answer options, a one-sentence definition a person can check by reading, and a version. Six questions, from the CR267 starting set:

| # | id | type | answers | checkable by reading |
|---|---|---|---|---|
| Q1 | `bear_objection_answered` | choice | answered_with_numbers / answered_without_numbers / unanswered / none_raised | the Bear's strongest objection and the Research Manager's reply |
| Q2 | `catalyst_in_horizon` | yes/no | a named catalyst inside the mandate horizon | Research Manager, Execution Desk |
| Q3 | `terminal_vulnerability_unresolved` | yes/no | a fatal flaw raised and not answered | Bear, Risk Officer |
| Q4 | `event_risk_argues_wait` | yes/no | a dated event (earnings, ruling) inside the horizon that the room says to wait for | Macro & Events, Risk Officer |
| Q5 | `thesis_support` | choice | material_directional / weak_or_mixed / against | Bull, Bear, Research Manager |
| Q6 | `trade_proposed` | yes/no | the Execution Desk gave entry, stop and target | Execution Desk (also computable by code) |

Why this shape: the evidence says one signal predicts verdicts, the Bear's evidence. Across six independent runs the room "approves in the absence of a well-evidenced objection" (`jev_deep_dive_2026-10-14.md` §4.1, r +0.19…+0.37, AUC 0.64–0.75). Q1 is therefore the question to get right, and the bear-support baseline (a single bear-turn score) is the bar any rule must beat (`jev_deep_dive` §7.3).

Control I propose for the hosted LLM judge only: each answer must carry a verbatim quote (≤200 characters) from the transcript, and **code checks the quote is a substring**. An answer whose quote is not found is "not computable". That makes "visible reasoning" a structural check, not a prompt wish (CLAUDE.md: prompt instructions are not controls). Jev's typed API cannot return quotes; that goes under "control" in its scorecard.

### 3.2 Who answers, and how each is called

All graders implement one interface: `grade(judge_input, question_set) -> answers[]`, each answer = `{question_id, answer, probability_or_score, quote, grader_id, grader_version, latency_ms, raw_response_hash}`. Failures raise a typed error; no grader returns a default.

1. **Jev (TypeSafe System One).** `POST https://api.typesafe.ai/v1/systemone`, body `{"state", "model", "questions"}`, bearer key `JEV_API_KEY` (`docs/tools/room_investigation_V2/tools/jev_v1_pilot.py`, `JEV_URL`, `jev_eval`). Question types `choice`, `noul` (yes/no with a probability), `score`. All six questions go in one call. The existing script retries only 429/529, 3 tries, 60 s timeout. **Pin the version**: the scripts send `"model": "jev-latest"`, while the October corpus logged `jev-1.13.0`. Production must send the pinned id and record `response.model`, because the grader version is part of the policy key (CR267 WP-23.2).
2. **Hosted LLM judge (WP-14 model, temperature 0).** Six narrow calls sharing one prefix (cheaper if the provider caches prefixes; unverified), JSON-schema `response_format` (the only constraint S11 WP-14.1 advertises for `openai`-kind slots). Token probabilities are **unverified** for DeepInfra (CR267 §8 item 7); if absent, the close questions are asked as 1–5 scores and the Contested band is built from them (CR267 WP-22.2.2). Temperature 0 is not determinism: Ling at exact T=0 still flipped 20–33% (stocktake §4.6), so test-retest is measured, not assumed.
3. **Second hosted model (optional arm).** The same judge on a different model family from the desk model, to expose same-model self-preference. It is the WP-14 fallback model or one more shortlist model; it is a bake-off arm only, never an automatic production fallback (§3.5).
4. **Plain code over CR266 typed cards.** Computable only on the cards-on arm; a missing cell is "not computable", never imputed, and completeness is its own column (CR267 WP-22.2.3). CR266's best card result was 57/60 complete, ICC 0.810 (bar 0.85, FAIL), so code is expected to own only structured questions: Q6, and possibly Q2 if the Execution Desk output parses reliably.
5. **A per-question owner is allowed.** The S3 outcome can be "code owns Q6, the judge owns Q1–Q5", with the policy version recording each owner.

**Judge input (built, not copied).** `ticker`, mandate (risk score, horizon, caps), the blinded fact sheet, and the turn text of the Bull, Bear, analysts, Research Manager, Execution Desk and Risk Officer in order. Not the CIO's system prompt. CR257 v2 sent the CIO's whole ~50K-character prompt (`CR257_jev_decision_arm/spec.md` §8), which in production would carry the Brief overlay, journal block and portfolio snapshot. Size: about 14.7K tokens per room in that run (8.84M ÷ 600; the spec text says "~15.7K", the arithmetic gives 14.7K).

### 3.3 The coded rule, and where it slots

**Slot** inside `_run_cio_step`, replacing steps 2–3 and 5 of §2 when the setting is on, keeping 6 and 8:

1. Debate completes (unchanged).
2. **NEW:** build judge input → grader → answers stored → rule → decision D ∈ {APPROVE, PASS, CONTESTED, UNAVAILABLE}.
3. **CIO: one call, action fixed by D.** It narrates, and for an APPROVE supplies size/entry/stop/target as today. Code ignores any action it writes; if it disagrees we store `cio_disagreed=true` (a useful signal, and free).
4. APPROVE → `_floor_pm_approve` → `enforce_safety_floor`, **unchanged and final**. It can still turn an Approve into REJECT. It is never given anything but the rule's APPROVE.
5. The two second-pass reviews (§2.7) are **skipped** when the rule is on: a second LLM changing a computed decision defeats the point, and the resurrection re-run calls the CIO again.
6. `_guard_pm_text` (§2.8) unchanged.

Boot check: the coded rule and `room_evidence_gate_enabled` may not both be on (the gate would bar an APPROVE the rule already decided). Refuse to start, loudly.

**The rule (written a priori; CR267 WP-23.2):**
1. Q3 = yes → PASS. Q6 = no → PASS.
2. Risk 1–2 and Q1 ∈ {unanswered, answered_without_numbers} → PASS.
3. Otherwise count supportive answers `s` (0–4): Q1 answered_with_numbers or none_raised; Q2 yes; Q4 no; Q5 material_directional.
4. APPROVE if `s ≥ c(risk)`. CONTESTED if `s = c(risk) − 1`, or any deciding answer is within margin `m` of a coin-flip (probability or score). Else PASS.
5. `c(risk)` is non-increasing from risk 1 to 5 (strictness monotone in risk). Only `c(1..5)` and `m` are fitted.

**Fitting protocol (proposed):** fit on 15 of the 30 tickers, test on the other 15, targets (a) agreement across the two reps of the same ticker/risk, (b) the known-answer input tests, (c) the CR257 holdouts. **Consensus is never a fitting target** (CR267 WP-23.2, answers doc item 26). Stored as versioned policy in the shape of `room_evidence_gate_thresholds_json` (`core/config.py:1318`); the policy version includes question-set version, owner and version of each question's grader, rule version, and the cut-offs.

**Contested** is stored as `action=PASS` plus `decision_record.contested=true` and `contested_reasons` listing the close questions (existing fields, so every consumer of `action` keeps working). A new `VerdictAction` value would touch the floor, journal, scoring, the sim and mobile; I would not add one without checking those.

**Sizing note.** Because Q6 = no forces PASS, every Approve has an Execution Desk proposal behind it. If the CIO's reply for a rule-APPROVE has no usable numbers, the Room ends UNAVAILABLE rather than inventing levels (same principle as `_parse_pm_verdict`, which returns no verdict when no size is stated).

### 3.4 Grader down: degrade loudly

1. Failure classes: HTTP error or timeout after 3 retries with backoff (same model only); malformed or schema-invalid reply; quote check failed; a question with no answer from its owner. **Any one of them → UNAVAILABLE.** No imputing, no default verdict, no switch to another grader mid-Room.
2. UNAVAILABLE is stored as `NO_VERDICT` with a new sentinel reason, the pattern CR219 R51 already uses (`PM_ROOM_INCOMPLETE_REASON`, tested by `room_verdict_is_incomplete`, `room_runner.py:814`). It must be added to `is_outage_shaped_verdict` (`:827`) so the existing refund path fires and analytics skip it. **Not stored as PASS.** DEF336 is the reason: an outage PASS "would have read as conservatism" in the backtest (`failure_patterns.md`, DEF336 note; DEF059 is the original).
3. The debate stays visible; the app shows "decision unavailable" with a retry, and credits go back through the existing CR039 refund path (S11 WP-14.4). Beta credits are free, so the refund matters on Alpha and for the spend ledger.
4. An operator signal: ERROR log plus a counter per grader and failure class; a boot check refuses `room_decision_mode=rule` with no grader configured; every new setting is forwarded in `docker-compose.yml`'s `api-alpha` block (`test_config_compose_parity.py`).
5. Test pinned by the failure-patterns rule: a dead grader can never yield APPROVE or PASS (sibling of `test_room_pm_llm_outage_fails_safe_to_pass`).

### 3.5 No grader failover

If Jev (or the judge model) is down, we do **not** auto-switch. A different grader is a different policy version, hence a different banked-room key (WP-24), and a verdict that depends on which grader was up is exactly the inconsistency WP-24 removes. Switching is a manual config change (minutes). The cost: grader downtime is Room downtime. For the hosted judge this is correlated with desk downtime anyway; for Jev it is a real exposure, covered in §5.

### 3.6 What WP-24 and WP-25 depend on

1. **WP-24** (same inputs → same room): the room key includes the policy version from §3.3 and the model `root` (CR267 WP-24.1). A grader or rule change must change the key. Not a grader-determinism requirement: the first compute is banked.
2. **WP-25** (flip explainer): needs per-question answers stored per room. The explainer diffs the previous and current `judge_record` (answers) and the changed inputs. Without WP-23 there is no "which answer changed". Stored as a new field on the verdict JSONB beside `decision_record` (the CR266 precedent: no migration).
3. **WP-21b** shows "reasons from the narrow answers" when the Street view differs, so it also reads `judge_record`.
4. **Gap in the plan:** nothing in WP-23/25 puts all six answers on the verdict card. I assume WP-21b and WP-25 show subsets. See question 9.

## 4. The bake-off (WP-22)

### 4.1 Data

1. **Evaluation set:** the WP-20 baseline on the chosen model, post-WP-21a (blind): 30 tickers × 5 risk levels × 2 reps = **300 rooms with cards off**, plus the **300-room cards-on arm** for the code grader (CR267 WP-20.1–2). 600 rooms in all.
2. **Primary scoring set:** the cards-on arm, because all graders can answer there. The cards-off arm checks that results hold in the production shape. Cards-on desks have a different prompt, so they are not the production Room; I report both and never merge them.
3. **Side set:** up to five lowest-consensus names if the 30 contain no Street Sell/Underperform name (WP-20.3).
4. **Development rooms** are separate: the October CR257 rooms (900 rooms, transcripts in Alpha `llm_audit`) are used to write and debug prompts. They were generated with the Street view visible, so they are invalid for consensus scoring. **Question wording, rubric and rule are frozen before anyone looks at WP-20 labels.**
5. The WP-20 users are harness users (deterministic per-arm `uuid5` ids; `room_contract_gates.py` header), so no tester data is involved.

### 4.2 Ground truth

1. **What "correct" means for the six questions:** a person reading the cited turns gets the same answer. I write a one-page rubric per question with two worked examples from the October rooms.
2. **Reference labels:** a model from a different family than the candidates labels all 300 cards-on rooms against the rubric. **Ling-3.0-flash-Fin on our own host** (`ling-3.0-flash-fin-fp4`, inclusionAI; measured in WP-10, $0 per call). It is a different family from the DeepSeek desk and judge, and from GLM. **No Anthropic model may be used (Saiful, 2026-11-19: no Anthropic models in the app).**
3. **Ruling (Saiful, 2026-11-18): no human labelling.** The reference for whether the **verdict** is right is **analyst consensus** (CR267 §1 item 6), scored as in §4.3.6. Approving a Street Sell or Underperform name is the error; a reasoned Pass on a Street-Buy name is acceptable.
4. **Checks on the per-question answers, with no human in the loop:**
   1. Agreement with the reference labeller.
   2. Agreement among the graders themselves.
   3. The input tests with constructed known answers (§4.3.4).
   4. The quote check: every answer's quote must exist in the transcript.

   A question on which the graders and the labeller disagree heavily is flagged in the report as unreliable, and it is not given power in the rule until fixed.
5. **Limitation, stated plainly:** consensus judges the final call, not whether each narrow question was answered correctly, and the reference labeller can share the graders' blind spots. The input tests are the only checks with a known truth. The report says this beside every per-question number.
6. **Precision caveat:** the 300 rooms are not 300 independent samples (same 30 tickers, two reps), and Street Sell/Underperform names are few (hence WP-20.3's side set). The S3 rule therefore uses a margin and tie-breaks.

### 4.3 Metrics (per grader, per question)

1. **Agreement with the reference labels:** accuracy and Cohen's kappa on the 300, plus agreement between graders. These are secondary to the consensus scores (item 6).
2. **Test-retest:** every grader runs the same 300 rooms twice; share of answers that change. (Jev's reference: 299/300 on the CR257 decision question, `spec.md` §8; 95.4% exact over 2,400 evidence texts, `jev_deep_dive` §3. These were different questions; the narrow ones are untested.)
3. **Wording test:** each question in five phrasings on 100 rooms; share of answers that change (WP-22.3.2).
4. **Input tests with known answers:** planted fatal flaw must give Pass; removing the Bear's evidence must not make the answer more cautious; strengthening the Bear's numbers must lower support; reordering turns and renaming the ticker must change nothing. 20 base rooms × 5 tests × 2 variants = 200 perturbed transcripts (my sizing).
5. **Fresh-room stability:** after the rule, disagreement between the two reps of the same ticker and risk level. Report beside the CIO's rate on the same rooms (CR266's 13/30 tickers; stocktake R4 flips 33%).
6. **Consensus scores (evaluation only, never fitted):** approvals of Street Sell/Underperform names; share of approvals that are Street Buy per risk level; rank correlation with the consensus score; n per cell; the CIO's numbers on the same rooms beside them (WP-22.3.1).
7. **Curve shape:** approvals per 60 rooms per risk level vs the target 5/15/30/45/46. Reported, not gated. Jev's last run on full inputs came out 1/4/20/21/14, the most conservative reader (`spec.md` §8), so I expect the rule to be strict at risk 1–2 and want it visible.
8. **Cost per Room, latency, failure rate** (defined below), and the "control" column: version pin, visible prompt, switchable vendor, quote check.

### 4.4 Decision rule for S3 (proposed, fixed before the run)

1. **Eligibility (all must hold):** failure rate ≤ 1% of room-judgings (proposed); planted-flaw tests 100% correct (this is a safety behaviour); wording-test change ≤ 10% and test-retest change ≤ 5% on the questions the grader owns (both proposed; I will state the measured values beside the bar); grader cost ≤ 1¢ per Room (the Room budget is 5¢, CR267 decision 3); p95 grader latency such that the Room stays under 2 minutes (WP-10 decides the desk part; I measure the grader part).
2. **Pick (per the Q1 ruling):** among eligible graders, the best **consensus scores** after running the coded rule on that grader's answers: the fewest approvals of Street Sell/Underperform names first, then the highest rank correlation with the consensus score. Fresh-room stability and agreement with the reference labels are the tie-breakers. If the top two are within the noise (reported with n per cell), prefer by control: our own pinned hosted judge, then code for structured questions, then Jev.
3. **Jev wins only if** it beats the best non-Jev eligible grader by more than that margin **and** the vendor-terms conditions in §5.4 are met. Otherwise the recommendation names the runner-up, and the report says "vendor terms still owed" (WP-22.4).
4. **Nobody eligible:** WP-23 still ships the rule with the best eligible owner per question where possible; if no grader owns Q1, the Room stays on the CIO vote behind the setting and the report says so. That is a valid S3 outcome (CR267 §8 item 3).

### 4.5 Cost in USD (all estimates; arithmetic shown)

Inputs: 15K tokens per judged room (Jev v2 measured 14.7K); DeepInfra judge priced at the **only DeepInfra rate card in the repo**, GLM-5.3-Flash $0.075 input / $0.25 output / $0.015 cached per million (`docs/Research/RES009_room_llm_consistency/13_cr240_glm53flash_9ticker_5x_internal_consistency.md`, September). **The S11 plan contains no per-token prices**; the real judge model is chosen at S2, so scale linearly. Jev at the script constant $0.042 per million input tokens, outputs free (`jev_v1_pilot.py:240`); that is a script constant, not a vendor quote, and the trial may be free or differently priced.

1. LLM judge, one question call: 15,000 × $0.075/M = $0.001125 + 50 output tokens × $0.25/M ≈ $0.00114. Six calls per room ≈ **$0.0068**. No prefix caching assumed.
2. Jev, one call per room (six questions): 15,000 × $0.042/M = **$0.00063**.

| item | volume | LLM judge | Jev |
|---|---|---|---|
| main set: 300 cards-on × 2 passes + 300 cards-off × 1 | 900 room-judgings | 900 × $0.0068 = $6.1 | 900 × $0.00063 = $0.57 |
| wording test: 100 rooms × 5 phrasings | 3,000 question calls (LLM) / 500 calls (Jev) | 3,000 × $0.00114 = $3.4 | 500 × $0.00063 = $0.32 |
| input tests | 200 perturbed rooms | 200 × $0.0068 = $1.4 | 200 × $0.00063 = $0.13 |
| **subtotal** | | **$10.9** | **$1.0** |

3. Second hosted model: same volume, assumed same price: **+$10.9**.
4. Reference labeller (Ling-3.0-flash-Fin, own host): **$0** in cash. Its cost is time: at the WP-10 measured speed the host is slow under load (8 min per full Room at 4 concurrent), but labelling one room is a single short call, not a Room. The run is serialised and given a time budget rather than a cash one.
5. **Total estimate: 10.9 + 10.9 + 1.0 + 0 ≈ $23** (was $35 with an Anthropic labeller). With 50% contingency for prompt iteration and retries ≈ $34.
6. Where it sits in the $100 DeepInfra measurement cap (§3a.4): WP-10 about $24 (estimate, S11 WP-10.3), WP-20 up to $30 (600 rooms at the 5¢ bar; if a room costs what GLM measured in September, $0.0095, it is about $6), WP-22's DeepInfra share about $22 (+50% = $33). Worst case ≈ $87 of $100. Tight but inside. The labeller runs on our own host at no cash cost.
7. Not in the estimate: Jev fees after the trial; the cost of authoring the 200 perturbed transcripts (a few dollars of LLM edits, my guess).

## 5. Jev specifics

### 5.1 What we know
1. We hold trial access (decision D-082; CR267 §3.7). The key is `JEV_API_KEY` read at run time from the repo `.env` by the research tools (`jev_v1_pilot.py:load_jev_key`). Whether it is on melehost: not verified.
2. About 18,200 turn judgments and 1,800 + 600 decision calls have run, 0 errors on the 600-call v2 run, about 2 minutes wall time (`jev_deep_dive` §1; `spec.md` §7–§8). Latency ~0.4 s per call in the spec (the pilot docstring says ~35 ms).
3. Self-consistency is real: 299/300 on the same transcript (mean |ΔP| 0.008) and 95.4% / r 0.994 across 2,400 duplicate scorings.
4. Accuracy on the old evidence questions: 0 clear errors in a 20-turn hand audit, about 5% adjacent-grade (`jev_review_2026-10-12.md` §1). That is a 20-turn sample, not a measurement of the narrow questions.
5. As a decider it failed: v1 and v2 NO-GO on curve shape and discrimination; v2 approvals were a strict subset of the CIO's (22 PM-only, 0 Jev-only); on the disposition arm it approved APD-rep2 R5, a holdout violation (`spec.md` §7–§8; `jev_deep_dive` §6). Its signal looks like a conservative second reader. The narrow-question design is a different use, and untested.

### 5.2 What we do not know
1. **Vendor terms:** none in the repo. Price (only the script constant), uptime or SLA, rate limits beyond the 429/529 retries, data retention, whether inputs are used for training, hosting region, sub-processors, how long a pinned model version is kept, deprecation notice, what happens when the trial ends.
2. Whether `jev-1.13.0` stays available; the scripts use `jev-latest` and a silent change would shift answers.
3. Whether Jev answers Q1–Q6 well. Never run.

### 5.3 Data sent to a third party, and the privacy policy
1. **Leaves our infrastructure per judged room:** the ticker, mandate numbers (risk score, horizon, caps), the blinded fact sheet, and the text of about 10 agent turns (the Bull, Bear, analysts, Research Manager, Execution Desk, Risk Officer). **Does not leave:** user id or email, Brief overlay, journal block, the portfolio snapshot as a block, the CIO prompt.
2. **Residual leak I cannot rule out:** desks see the portfolio snapshot and journal (§2), so a desk turn may quote a holding. Mitigations: judge only turn text, not prompts; log a count of judge inputs containing portfolio markers during Alpha shadow; decide at the end whether a scrub is needed. Beta's DeepInfra already receives all of this and more, so Jev would be a second recipient of a subset.
3. **Policy:** `legal/policies/privacy_policy.md` clause 7 (`:91–97`) lists the processors and says the primary AI is self-hosted with a contracted third-party fallback, deliberately without naming a vendor. That wording is already stale for a Beta whose primary is hosted (a CR267 / WP-30 item, not S12). Adding Jev means a new processor category ("decision-grading service") and matching Apple privacy labels and Play Data Safety entries (WP-50). The policy promises processors with "confidentiality and data-protection obligations equivalent to our own", which needs a signed agreement. This is a counsel item (CR267 §7 backlog); I am not giving legal advice.
4. The bake-off itself sends only harness-user rooms (synthetic user ids, real public market data), so no tester data goes to Jev before terms exist. Trial terms may still restrict use; unknown.

### 5.4 When Jev may carry production decisions
All of:
1. It is eligible and wins under §4.4.
2. Written terms in hand: price per call or per tier, rate limits, uptime commitment or stated target, no-training and retention terms, region and sub-processors, version pinning with a stated deprecation notice (I suggest at least 90 days; Saiful's call), termination and data deletion, a signed data-processing agreement.
3. The privacy policy and store data declarations are updated before Beta testers' rooms are sent.
4. A pinned fallback grader (the hosted judge) is tested and switchable by configuration, even though the switch is manual (§3.5).
5. WP-26 passes with Jev as the grader.
Until then Jev is measurement-only, and production uses the best non-Jev grader or stays on the CIO vote.

## 6. Rollout

New setting `room_decision_mode` = `cio` (default) | `shadow` | `rule`, plus `room_judge_owner_map` and `room_judge_policy_json`. All forwarded in compose (parity test).

1. **Step 0, WP-22 offline.** Build the questions file, the grader interface, the three or four graders, the label tooling and the scoring scripts. The module is unwired: `room_runner` does not import it, and a test asserts that. No change to `backend/app` behaviour, no setting, no Alpha promotion. Acceptance: `grader_bakeoff_<date>.md` per CR267 WP-22.4: table, failures by question, recommendation, "vendor terms still owed" if Jev is named. **Gate S3 here.**
2. **Step 1, shadow on Alpha (WP-23 part 1).** `shadow`: the CIO still decides; the grader runs after the debate and stores answers and the would-be decision; `cio_disagreed` and the CIO-vs-rule split are logged. Alpha has had almost no traffic since 2026-10-30, so shadow data comes from harness runs against Alpha. Acceptance: (a) verdict, size and floor results byte-identical to `cio` mode on a replay of 20 stored rooms; (b) a forced grader failure leaves the verdict untouched and logs the failure; (c) 100% of shadow rooms carry a complete answer record or an explicit failure; (d) full backend suite green (shared hot path, CR267 §2.8).
3. **Step 2, `rule` on Alpha (WP-23 part 2).** Acceptance = CR267 WP-23.6: unit tests for the rule, the Contested band, UNAVAILABLE, and narration unable to change the action; one live Room whose stored record holds every answer and the rule version; forced grader failure → NO_VERDICT and refund, never PASS or APPROVE; the boot checks of §3.3–3.4; full suite.
4. **Step 3, WP-26.** The acceptance run decides whether `rule` stays on. Pass: on for Alpha and Beta. Fail: off, Room labelled "experimental" (CR267 WP-26.3).
5. **Rollback.** Set `room_decision_mode=cio` (configuration only, minutes). Banked rooms are keyed by policy version and decision mode, so rule rooms are not served as CIO rooms. Stored verdicts keep their records. For a code defect: `/rollback-alpha`, and the `pre-cr267` tag (decision D-089). Jev specifically: change the owner map to the hosted judge, a different policy version, so affected rooms re-grade rather than mix.

## 7. Risks

1. **The judge inherits the debate's prior.** CR257 found the willingness lives in the debates, not the reader. *Mitigation:* promise consistency and explanation, not correctness; report consensus scores and the bear-support baseline; WP-26 decides.
2. **Too conservative at risk 1–2.** Jev on full input produced 1/4/20/21/14. *Mitigation:* the curve is reported in the bake-off; `c(risk)` is fitted per level; Contested absorbs the near-misses.
3. **Same-model bias** in an LLM judge scoring its own model's debate. *Mitigation:* second-family arm, reference labeller from a third family, consensus as the outside reference.
4. **Few Street Sell names in the sample.** *Mitigation:* WP-20.3's side set; n per cell reported; margin and tie-break by control.
5. **Reference labeller shares blind spots with the judges.** *Mitigation:* consensus decides the pick, not the labeller; input tests with constructed truths; low-agreement questions get no power in the rule.
6. **Overfitting the rule.** *Mitigation:* a-priori structure, only five cut-offs and one margin fitted, split by ticker, consensus excluded.
7. **Vendor dependency (Jev):** price, outage, silent version change, retention. *Mitigation:* §5.4 conditions, pinned id recorded per answer, manual switch, no Jev in production before terms.
8. **Data leaving the building.** *Mitigation:* built judge input, no identifiers, shadow-period leak counter, privacy and store declarations before use.
9. **Outage recorded as a conservative PASS** (DEF336 class). *Mitigation:* NO_VERDICT sentinel in `is_outage_shaped_verdict`; a test that analytics skip it.
10. **Latency pushes the Room past 2 minutes.** *Mitigation:* questions run in parallel; grader latency is a bake-off eligibility line; in shadow the grader runs alongside the CIO call.
11. **Hot-path regression in `_run_cio_step`.** *Mitigation:* behind a default-off setting; shadow replay equality; full suite before merge.
12. **Banked rooms silently mix policies.** *Mitigation:* the policy version, grader version and decision mode are in the room key; the Jev model id is recorded from the response.
13. **The CIO disagreeing with the rule goes unseen.** *Mitigation:* `cio_disagreed` stored and counted in shadow.
14. **Budget overrun.** *Mitigation:* the harness stops itself at the cap, like WP-10's $80 stop.
15. **Quote check rejects good answers** (punctuation, quote marks). *Mitigation:* normalise whitespace and quotes before the substring test; track rejection rate in shadow.

## 8. Questions for Saiful

> **All ruled on 2026-11-18; see §0.** Q1 was answered differently from every option below: consensus is the reference, and there is no human labelling. The options are kept as the record of what was asked.

1. **Who labels the ground truth?**
   1. Saiful labels 30 rooms blind (about 5–8 hours, my guess); a model from a different family labels the other 270; we check it agrees with him. **(Recommended)**
   2. A model labels all 300; Saiful reviews only the disagreements between graders and labeller. Less of your time, but the anchor is weaker.
   3. A person you name (trusted analyst) labels 30–60 rooms from my rubric.
2. **Bake-off budget cap** (my estimate $35; includes the second-model arm and the reference labeller):
   1. $25 hard stop: one hosted judge, Jev, reference labeller; no second model, no contingency.
   2. $50 hard stop: everything, about 43% headroom. **(Recommended)**
   3. $100: the same, with room to re-run after prompt changes. Pushes the DeepInfra total toward the $100 programme cap.
3. **May Jev be considered at all before written terms?**
   1. Yes for the bake-off only, on harness rooms (no tester data), on trial access; production waits for §5.4. In parallel you ask TypeSafe for terms now, because their lead time is unknown. **(Recommended)**
   2. No Jev runs until terms are signed. Cleanest, but the bake-off arrives without the third candidate.
   3. Yes, and allow production on trial access if it wins. I advise against it.
4. **May the coded rule override the CIO, or only veto?**
   1. The rule decides; the CIO narrates and cannot change it. Shadow mode first, so the CIO still decides until you see the comparison. **(Recommended; this is WP-23 as written)**
   2. Veto only: the rule can turn a CIO Approve into Pass/Contested but never create an Approve. Safer, but the CIO's five-vote flips remain, so consistency does not improve.
   3. Veto-only for Alpha, then switch to option 1 after WP-26 passes.
5. **What does the user see when the grader is unavailable?**
   1. "Decision unavailable", debate kept, credits refunded, a retry button. Stored as no verdict. **(Recommended; WP-23.4)**
   2. The same, but the debate is also hidden (a cleaner screen, but wastes the run).
   3. Fall back to the old CIO vote, labelled "backup decision". It gives an answer, but it is a different method, and the same ticker would then have two policies. I advise against it.
6. **Include the second-model judge arm?** (about $11 of the estimate)
   1. Yes, a different family from the desk model. **(Recommended)**
   2. No; the human anchor is enough.
7. **Second-pass reviews (veto and resurrection) when the rule is on:**
   1. Off, because a second LLM must not change a computed decision. **(Recommended)**
   2. Keep the veto review only, as an extra check on Approves.
8. **How is Contested stored?**
   1. As PASS plus `contested=true` and the list of close questions, reusing the CR266 fields. **(Recommended)**
   2. As a new action value. Cleaner in the data, but it touches the floor, journal, scoring, sim and mobile.
9. **Should the verdict card show all six answers?** Not in the current WP list.
   1. Show the answers that differ from the Street view (WP-21b) and the changed ones on a flip (WP-25); store all six. **(Recommended)**
   2. Show all six on every verdict card (a small UI work package to add).
10. **The six questions themselves:** keep the starting six, or swap one? (Q4, event risk, is the least certain to be answerable by reading.) Please skim §3.1 before I freeze it.

## 9. What I need from you to start

1. ~~Answers to questions 1–9~~: done (§0).
2. ~~Any question to add or drop~~: keep the six (§0).
3. ~~A labelling window~~: not needed; consensus is the reference (§0).
4. A request to TypeSafe for written terms covering §5.2, in parallel (question 3). I can draft the email.
5. ~~The Anthropic API key for the reference labeller~~: not used (no Anthropic in the app, 2026-11-19). The labeller is Ling-3.0-flash-Fin on our own host.
6. Gate dependencies, not for you: WP-20 (needs WP-14, WP-21a and the S2 model pick) must finish before the evaluation run. I can start the questions file, rubric, interface and scoring code, and develop on the October rooms, before that.
