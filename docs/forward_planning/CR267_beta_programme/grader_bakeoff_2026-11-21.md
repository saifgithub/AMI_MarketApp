# CR267 WP-22 grader bake-off (3 LLM graders scored on arm 1; code grader scored on arm 2)

**Status:** all four graders scored. The on-prem, Jev and DeepInfra graders ran on the 300 WP-20 arm-1 Rooms (cards off); the code grader ran on the 300 arm-2 Rooms (cards on), because it needs the CR266 cards. Full tables: `grader_bakeoff_{onprem_arm1_2026-11-21,jev_arm1_2026-11-22,deepinfra_arm1_2026-11-22,code_arm2_2026-11-22}_tables.md` (from `docs/tools/room_investigation_V2/tools/wp22_score.py report`). Gate S3 (the pick) is Saiful's; the recommendation is below and the code grader does not change it.

**Measured on:** the 300 WP-20 arm-1 Rooms (30 tickers × R1–R5 × 2 reps, cards off), on-prem vLLM, model root `/models/qwen38-flash-next-abliterated-nvfp4` (read from `/v1/models`), temperature 0, question set q1, decision rule r1 with the default policy (unfitted placeholders). The grader saw the 11 desk turns, never the CIO's verdict. Read-only DB access; no `llm_audit` rows written; $0.

## Four-way comparison, 2026-11-22

The first three graders were scored on the same 300 arm-1 Rooms (cards off), same q1 questions, rule r1 default policy. **The code grader was scored on the 300 arm-2 Rooms (cards on), a different set of Rooms**: so its columns sit beside "CIO arm 2", the CIO on those same Rooms, and cross-column comparisons carry the draw noise between two sets of Rooms (arm 1 vs arm 2 differ by +9 approvals, within noise; see the baseline file item 7). Code grader runs: **Part A**, the input production would hand it (proposed-trade block with no `action`, so `trade_proposed` is not computable); **Part B**, the same cards with `action` added to the trade block (sensitivity). Jev pinned `jev-1.13.0`; DeepInfra `deepseek-ai/DeepSeek-V4-Flash` at temperature 0; on-prem `/models/qwen38-flash-next-abliterated-nvfp4`. Tables: `grader_bakeoff_{onprem_arm1_2026-11-21,jev_arm1_2026-11-22,deepinfra_arm1_2026-11-22,code_arm2_2026-11-22}_tables.md`. Input and wording tests are 20 Rooms each (4 tickers x R1-R5), so roughly +/-20 points; the code grader has neither (it never reads prose).

| measure | CIO arm 1 | on-prem Qwen3.8 | Jev 1.13.0 | DeepInfra DeepSeek-V4-Flash | CIO arm 2 | code A: production input | code B: trade action given |
|---|---|---|---|---|---|---|---|
| Rooms graded | 300 | 300 | 300 | 300 | 300 | 300 (arm 2) | 300 (arm 2) |
| errors | - | 0 | 0 | 0 | - | 0 | 0 |
| latency per Room | - | 31.4 s | 0.3 s | 7.9 s | - | under 1 ms | under 1 ms |
| cost per Room / 300 Rooms | - | $0 | $0.0003 / $0.10 | $0.0018 / $0.55 | - | $0 | $0 |
| approvals R1 / R2 / R3 / R4 / R5 | 3 / 3 / 10 / 13 / 20 | 1 / 3 / 13 / 10 / 27 | 0 / 0 / 0 / 0 / 20 | 1 / 2 / 4 / 5 / 31 | 4 / 2 / 12 / 16 / 24 | 0 / 0 / 0 / 0 / 0 | 0 / 0 / 28 / 24 / 53 |
| monotone in risk | yes | no (R3 > R4) | yes, but R1-R4 never approve | **yes** | yes (R1 > R2 by 2) | never approves | no (R3 > R4; R1/R2 never approve) |
| CONTESTED | - | 115 (38%) | 32 (11%) | **0** | - | 11 (4%) | 29 (10%) |
| UNAVAILABLE (rule cannot decide) | - | 0 | 0 | 0 | - | **200 (67%)** | 77 (26%) |
| Rooms the rule can decide at the Room's own level | - | 100% | 100% | 100% | - | **33% (100/300)** | 74% (223/300) |
| reps disagree on APPROVE vs not | 23% (35/150) | 16% (24/150) | **3% (4/150)** | 6% (9/150) | 24% (36/150) | 0% (vacuous: never approves) | 21% (31/150) |
| same transcript regraded: an answer changes | - | 35% (7/20) | 15% (3/20) | **10% (2/20)** | - | 0 by construction | 0 by construction |
| planted fatal flaw in the debate text, PASS at R1-R5 | - | 75% (15/20) | **100% (20/20)** | **100% (20/20)** | - | not applicable: does not read text | not applicable |
| bear evidence removed → not more cautious | - | 65% (13/20) | **100%** | 95% (19/20) | - | not applicable | not applicable |
| bear numbers x2 → not less cautious | - | 75% (15/20) | 70% (14/20) | **95% (19/20)** | - | not applicable | not applicable |
| turns reordered: answers unchanged | - | 20% (4/20) | 50% (10/20) | 50% (10/20) | - | not applicable | not applicable |
| turns reordered: rule outcome unchanged | - | 12/20 | 19/20 | **20/20** | - | not applicable | not applicable |
| ticker renamed: answers unchanged | - | 70% (14/20) | **80% (16/20)** | 50% (10/20) | - | not applicable | not applicable |
| ticker renamed: rule outcome unchanged | - | 19/20 | 19/20 | 19/20 | - | not applicable | not applicable |
| wording: most fragile question | - | thesis 70% | bear objection 85% | bear objection 90% | - | not applicable | not applicable |
| **questions computable (share of Rooms)** | 100% | 100% | 100% | 100% | - | trade 0%, catalyst 0%, event risk 0%, bear objection 60%, terminal 93%, thesis 92% | as A, but trade 100% |
| Rooms with all six computable | 100% | 100% | 100% | 100% | - | 0% | 0% |
| approvals that are Street Buy | 73% (33/45) | 67% (32/48) | 89% (16/18) | 70% (26/37) | 73% (41/56) | n/a (no approvals) | 65% (60/93) |
| agreement with the CIO's approvals | 49 | 17 of 49 | 9 of 49 | 17 of 49 | 58 | 0 of 58 | 37 of 58 (and 68 approvals the CIO did not make) |

Reading:
1. **DeepInfra DeepSeek-V4-Flash is the strongest of the three on every control measure that matters for a decision rule**: monotone approvals, no Contested band (its confidences are sharp, never inside 0.2 of 0.5), outcomes unchanged under turn reordering in 20/20, the planted fatal flaw caught in 20/20, and the lowest regrade noise. Its answer-level reorder and rename sensitivity (50%) mostly moves answers that do not decide the outcome.
2. **Jev is the most repeatable across fresh Rooms (3%)** but because it approves nothing at R1–R4 at all: `thesis_material_directional` is yes in only 5% of Rooms and `trade_proposed` yes in 100%, so the rule passes almost everything below R5. It is also the most wording-sensitive on `bear_objection_answered` (85%), and vendor terms are still owed.
3. **The on-prem Qwen3.8 grader is the weakest**: 38% Contested, 35% regrade noise, order-sensitive. Its one advantage is $0 and no third party.
4. **All three beat the CIO's 23% rep disagreement.** None can yet be judged on Street Sell names (none in the WP-20 data).
5. **Every grader is wording-sensitive on at least one deciding question.** Whatever is picked, the rule needs WP-23's changes: `trade_proposed` from the structured trade, and the fragile questions (DeepInfra: `bear_objection_answered` 90%, `thesis_material_directional` 70%) either averaged over phrasings or kept out of the conservative-level gates.

**CheapLLM pilot (Saiful, 2026-11-22: "test out CHEAPLLM_API_KEY ... use the DSV4 they have").** Endpoint `https://cheapllm.shop/v1`; its `/v1/models` lists one model, `deepseek-v4.1-flash-1017`. 10-Room pilot, temperature 0, same q1/r1: **2/10 Rooms failed** with the provider's capacity error ("The kitchen is packed right now and we could not get a seat for this request in time"); latency **33–432 s per Room** (mean about 176 s, vs 7.9 s on DeepInfra); the 8 answered Rooms returned token probabilities (6/8 PASS, 1 CONTESTED, 0 APPROVE). No price is published, so the run was call-capped (60 calls) and cost is unknown. Not scored on the full 300: a 20% decision-unavailable rate and minutes of added latency per Room rule it out as the Room's grader today. Re-test if its capacity changes.

**Recommendation (for gate S3), with the code grader scored (it does not change the pick; see "Code grader (arm 2)" below):** DeepInfra `deepseek-ai/DeepSeek-V4-Flash` at temperature 0 as the grader, with `terminal_vulnerability` and the structured `trade_proposed` as the fixed Pass gates, and the wording-fragile questions averaged over the five phrasings (5× calls, about $0.009 and ~40 s per Room). Caveats: (a) it needs a hosted call per Room, so Alpha's on-prem-only ruling (2026-11-19) must allow it for the grader, or the coded rule runs on Beta only; (b) on Beta the desks also run on DeepSeek-V4-Flash, so the grader would judge a debate from its own model family; (c) Street-Sell behaviour is unmeasured. Jev is not recommended (approves nothing at R1–R4; vendor terms owed).

## Code grader (arm 2), 2026-11-22

Plain code over the CR266 typed cards (`room_graders/code_cards.py`, `cards-1`), WP-22 §2.3: a missing cell is "not computable" for that question in that Room, never imputed, and completeness is its own column. Run on the 300 WP-20 arm-2 Rooms (cards on), no model, $0. Full tables, with the production-input run (Part A) and the sensitivity run with `trade_proposed` made computable (Part B): `grader_bakeoff_code_arm2_2026-11-22_tables.md`. Tool: `wp22_score.py score --grader code` (cards rebuilt from `llm_audit`, unit-tested in `test_wp22_score.py`, 71 tests pass on the Mac and in the deployed image).

**Completeness (the question the spec asks first).** The cards themselves are complete in 277/300 Rooms (92%; baseline file item 4). Per question, the share of the 300 Rooms the grader could answer at all:

| question | computable | yes | no | why not computable |
|---|---|---|---|---|
| `catalyst_in_horizon` | **0%** | - | - | no card item carries it |
| `event_risk_wait` | **0%** | - | - | no card item carries it |
| `trade_proposed` | **0%** as built (100% if the block carries an `action`) | 0% (Part B: 100%) | 0% | `proposed_trade` has no `action` or `side` in the production block |
| `bear_objection_answered` | 60% (180/300) | 52% (157) | 8% (23) | 97 Rooms: no adequate Bear objection filed (the channel is optional); 23: cards incomplete |
| `terminal_vulnerability` | 93% (279/300) | 3% (8) | 90% (271) | 21: a desk missing its balance-sheet card |
| `thesis_material_directional` | 92% (277/300) | 56% (168) | 36% (109) | 23: cards incomplete |

No Room has all six computable. A code grader that cannot answer two of six questions in any Room, and a third (bear objection) in 40%, cannot be the sole grader. The plan's own escape hatch applies: it can own questions computable from structured fields.

**Rule outcomes per risk (default policy r1).**

| risk | n | A: APPROVE / PASS / CONTESTED / UNAVAILABLE | B: APPROVE / PASS / CONTESTED / UNAVAILABLE | CIO APPROVE (arm 2) |
|---|---|---|---|---|
| R1 | 60 | 0 / 24 / 1 / 35 | 0 / 24 / 1 / 35 | 4 |
| R2 | 60 | 0 / 27 / 3 / 30 | 0 / 27 / 3 / 30 | 2 |
| R3 | 60 | 0 / 16 / 4 / 40 | 28 / 16 / 11 / 5 | 12 |
| R4 | 60 | 0 / 19 / 3 / 38 | 24 / 19 / 14 / 3 | 16 |
| R5 | 60 | 0 / 3 / 0 / 57 | 53 / 3 / 0 / 4 | 24 |
| all | 300 | 0 / 89 / 11 / 200 | 105 / 89 / 29 / 77 | 58 |

1. **As built, it never approves.** Part A is UNAVAILABLE in 200/300 Rooms because `trade_proposed` is required at every level and is never computable. Every non-PASS, non-CONTESTED Room is UNAVAILABLE.
2. **With `trade_proposed` fixed (Part B) it still cannot decide the conservative levels.** R1 and R2 require `catalyst_in_horizon` (R1 also `event_risk_wait`), which no card carries, so every R1/R2 Room that is not already a PASS is UNAVAILABLE (65/120). At R3-R5 it approves 28/24/53 (against the CIO's 12/16/24): the approval curve is not monotone (R3 > R4) and approves far more than the CIO at R5.
3. **Reps disagree:** Part B rule APPROVE-vs-not 21% (31/150) against 24% (36/150) for the CIO on the same Rooms; per question, `terminal_vulnerability` 3% (4/129 pairs), `bear_objection_answered` 16% (8/50), `thesis_material_directional` **34% (43/127)**. The thesis answer is the net-support score against a 0.2 cut-off and 17% of Rooms sit within 0.05 of it (the grader's own "close" flag). Regrading a Room never changes an answer (deterministic).
4. **Consensus.** Part B approvals that are Street Buy: 65% (60/93) at all levels (R3 64%, R4 60%, R5 67%) against the CIO's 73% (41/56); no approval of a Street Sell name, by either, because none exists in the data.
5. **The CIO on the same Rooms (arm 2):** approvals 4 / 2 / 12 / 16 / 24, reps disagree 24% (36/150), 73% of approvals on Street Buy names. Cards on moves none of the CIO's measures beyond noise (baseline file item 7).
6. **`terminal_vulnerability` is the one answer worth taking from cards.** It is computable in 93%, stable across reps (3%), and rarely fires (3% yes: an unresolved high-severity balance-sheet objection). Rarely firing is the safe direction for a fixed Pass gate but is also why it caught nothing in this corpus; whether it agrees with the LLM graders' much higher yes rates (Jev 46%) is not measured here, because they ran on different Rooms.

**What this means for WP-23.**
1. Keep DeepInfra DeepSeek-V4-Flash as the grader (recommendation above). The code grader is not a candidate for sole grader.
2. Answer `trade_proposed` from the structured trade, as the plan already says. This needs the production trade block to carry the action: today it has none, so even a code-owned `trade_proposed` would be not computable.
3. Cards could back `terminal_vulnerability` as a second, code-derived Pass gate when cards are on. That is a design call for WP-23, only if cards go on (the arm-2 card gate reads FAIL: 277/300 complete, evidence-score ICC 0.71-0.86 against 0.85; baseline file item 4).
4. **Two wiring findings in the flag-off code path, found while reading it (not fixed here, outside this lane):** (a) `room_runner._coded_transcript` builds `cards` as `{desk: {cards, objections, ...}}`, but `CodeCardsGrader` reads `cards["cards_by_desk"]` and `cards["field_state"]`; as wired, the code grader would return an error ("cards must carry a cards_by_desk object") on every cards-on Room. (b) The same function passes `proposed_trade` without `action` or `side`, so `trade_proposed` is not computable (Part A). Neither shows up in unit tests that build the cards dict by hand. Both need a DEF if the code grader is used in production.

Caveats. The cards are rebuilt from `llm_audit`, which the runner's persisted transcript does not carry; the rebuild uses the backend's own parser and reproduces the card report's 277/300, and treats an envelope re-ask as adopted whenever it produced a turn (a re-ask whose stance did not parse is not distinguished). The four graders were not scored on the same Rooms (code on arm 2, the others on arm 1); arm 1 and arm 2 CIO measures agree within noise, which is the only bridge. `inputs` and `wording` were not run for the code grader (it reads no prose, so they cannot move its answers).

## On-prem grader detail (2026-11-21)

### What it shows

1. **Runs clean.** 300/300 Rooms, 0 errors, 0 unparsed answers, token probabilities on every question. 31.4 s mean per Room (p95 63 s), 6 calls per Room, sharing the vLLM with WP-20 arm 2.
2. **More stable than the CIO across fresh Rooms.** The two reps of the same ticker and risk level disagree on APPROVE-vs-not in **16% (24/150)** of pairs with the grader + rule, against **23% (35/150)** for the CIO on the same Rooms.
3. **The Contested band is too wide.** 115/300 Rooms (38%) come out CONTESTED. The 0.2 "close" band is a placeholder: `catalyst_in_horizon` is close in 44% and `thesis_material_directional` in 41% of Rooms. This is the cut-off WP-23 fits on these Rooms (targets: rep agreement, input tests, CR257 holdouts; never consensus).
4. **Approvals rise with risk, not strictly.** Grader approvals R1–R5: 1 / 3 / 13 / 10 / 27 (CIO: 3 / 3 / 10 / 13 / 20). The rule itself is monotone for fixed answers (WP-23 test); the R3 > R4 dip comes from the answers differing Room to Room.
5. **Agreement with the CIO is low.** Of the CIO's 49 approvals the grader also approves 17; it approves 37 Rooms the CIO did not.
6. **Consensus check is not informative yet.** The 30-ticker universe holds no Street Sell/Underperform name, so "approvals of Street Sell" is 0 for both and proves nothing. The WP-20 side set (lowest-consensus names) exists for this and is not yet scored. Share of approvals that are Street Buy: grader 67% (32/48), CIO 73% (33/45).
7. **Per question.** `bear_objection_answered` is yes in 97% of Rooms (little signal); `event_risk_wait` flips between reps 41% of the time and `catalyst_in_horizon` 33%, the least stable answers.

## Side set (5 lowest-consensus names, 50 Rooms), on-prem grader

1. Grader approvals 3/50 (R2 1, R5 2), CIO 4/50 (R4 1, R5 3); both mostly PASS at R1–R4. 14/50 Contested. Tables: `grader_bakeoff_onprem_side_2026-11-21_tables.md`.
2. **No WP-20 Room is on a Street Sell/Underperform name.** The side set chosen as the lowest-consensus names from `tickers_150.txt` (CAR, CPB, ITW, JBLU, KSS) is Street **Hold** on every Room; arm 1 is 169 Buy / 89 Hold / 42 no Street data. So WP-22 3.1's first measure ("approvals of Street Sell/Underperform names") **cannot be computed on the WP-20 data for any grader**. It needs Rooms on names whose stored `street_stance` is sell, which the CR035 universe does not supply today. Decision for WP-26: either source Sell-rated names into the acceptance universe, or drop that measure and say so.

## Wording test (20 arm-1 Rooms × 5 phrasings), on-prem grader

Share of Rooms where at least one rephrasing changes the answer (100 grades, 0 errors; table in `grader_bakeoff_onprem_arm1_2026-11-21_tables.md`):

| question | any phrasing changes it |
|---|---|
| bear_objection_answered | 10% (2/20) |
| terminal_vulnerability | 15% (3/20) |
| event_risk_wait | 35% (7/20) |
| trade_proposed | 45% (9/20) |
| catalyst_in_horizon | 55% (11/20) |
| thesis_material_directional | 70% (14/20) |

**Consequence for WP-23's rule r1:** its two fixed Pass gates use one robust question (`terminal_vulnerability`, 15%) and one fragile one (`trade_proposed`, 45%; it is also answerable from the structured trade without a model, which the code grader already does). The R1/R2 ladder leans on `catalyst_in_horizon` and `thesis_material_directional`, the two least robust answers (55% and 70%) and the two most often "close". As written, the conservative-level decision is mostly a function of wording. Options before the flag goes on: answer `trade_proposed` from structure, not the model; drop or down-weight catalyst/thesis at R1/R2, or ask them as an average over the five phrasings; refit the close band with wording stability as a target.

## Input tests with known answers (WP-22 3.3), on-prem grader

20 arm-1 Rooms (same stride sample as the wording test: 4 tickers, BAC / MA / SEDG / WFC, × R1-R5), each graded as the original, an original regrade, and five perturbations built in code (140 grades, 0 errors, 72.5 min, concurrency 1, $0). Perturbation builders and the exact numeric transform (every number attached to %, x or $ inside a downside or leverage sentence of the Bear turn, multiplied by 2) are documented at the end of the table section in `grader_bakeoff_onprem_arm1_2026-11-21_tables.md`. Verdicts are judged by `judge()` in `wp22_score.py`; the tool also has `inputs --dry` to inspect the perturbations without grading.

| test | expectation | pass rate | failing Rooms |
|---|---|---|---|
| Control: original regraded (extra, not in the spec) | all six answers unchanged | 65% (13/20) | 7 |
| Planted fatal flaw | `terminal_vulnerability` yes and rule PASS at every risk level | 75% (15/20) | BAC-r2, BAC-r5, MA-r3, MA-r4, WFC-r2 |
| Bear evidence removed | rule not more cautious than the original | 65% (13/20) | BAC-r2/r3/r4, SEDG-r3/r4, WFC-r1/r5 |
| Bear numbers strengthened (x2) | P(yes) on `bear_objection_answered` does not rise (+0.01 tolerance) and rule not less cautious | 75% (15/20) | MA-r1, MA-r2, SEDG-r2, SEDG-r4, WFC-r4 |
| Turns reordered | all six answers unchanged | **20% (4/20)** | 16 Rooms |
| Ticker and company renamed | all six answers unchanged | 70% (14/20) | 6 Rooms |

## What the input tests show

1. **The grader is not deterministic at temperature 0, and that sets the floor for every "unchanged" test.** Regrading the identical transcript changes at least one of the six answers in 7/20 Rooms and changes the rule outcome in 4/20 (APPROVE to CONTESTED, CONTESTED to PASS, PASS to CONTESTED). Flipping questions: `trade_proposed` 3, `catalyst_in_horizon` 2, `thesis_material_directional` 2, `event_risk_wait` 1; `terminal_vulnerability` and `bear_objection_answered` 0. The "reordered" and "renamed" tests have to be read against this 35%, not against 0%.
2. **Reordering is the one clear failure.** 16/20 Rooms change at least one answer (control: 7/20) and the rule outcome changes in 8/20 (control 4/20). The grader's answers depend on the order of the desk turns, mostly on `trade_proposed` (9), `catalyst_in_horizon` (7), `thesis_material_directional` (5). The two answers the rule's fixed gates lean on hardest differ: `terminal_vulnerability` never changed under reordering (0/20), `trade_proposed` changed 9/20.
3. **Renaming is near the noise floor.** 6/20 Rooms change an answer (control 7/20), rule outcome 4/20 (control 4/20). No sign that the ticker or company name drives answers; `bear_objection_answered` and `event_risk_wait` unchanged in all 20. Rename coverage: the ticker string is gone from every turn in every Room, company names found for all four tickers.
4. **Planted fatal flaw: the grader finds it, the rule does not always convert it to PASS.** `terminal_vulnerability` flips to yes in 18/20 Rooms and the rule is PASS at the Room's own risk level in 18/20. Failure causes: 2 Rooms (MA-r3, MA-r4) answer `terminal_vulnerability` = no despite an explicit going-concern warning with numbers appended to the Bear turn; 3 more (BAC-r2, BAC-r5, WFC-r2) answer yes but the yes is flagged close at R5, so the rule returns CONTESTED at that level. The stricter "PASS at every level" reading is what drops 18 to 15. Four originally-APPROVE Rooms go to PASS and two to CONTESTED.
5. **Bear evidence removed: no APPROVE ever became PASS (0/20), but the strict not-more-cautious reading fails 7/20.** Five are CONTESTED to PASS (BAC-r2/r3/r4, SEDG-r3, WFC-r1) and two APPROVE to CONTESTED (SEDG-r4, WFC-r5). Under the spec's parenthetical ("an APPROVE must not become PASS") the test is 20/20; under the ordinal reading (APPROVE < CONTESTED < PASS) it is 65%. Either way removing the Bear's numbers is not making the answer more lenient; if anything the grader gets more cautious, in 7 Rooms.
6. **Bear numbers strengthened: P(yes) falls on average, not in every Room.** Mean change in P(yes) on `bear_objection_answered` is -0.057 (min -0.236, max +0.039, n=20); it rose by more than 0.01 in 3 Rooms (SEDG-r2 0.97 to 0.98, SEDG-r4 0.95 to 0.99, WFC-r4 0.90 to 0.94, all at already-saturated confidence) and the rule became less cautious in 2 (PASS to CONTESTED, MA-r1 and MA-r2). Question stays yes in 97% of Rooms, so there is little room to move.
7. **Consequence for WP-23 / the grader choice.** Only the fixed Pass gate on `terminal_vulnerability` behaves like a control: it never changed under reorder, rename or regrade, and it fired on a planted flaw in 18/20. The four other deciding questions move with turn order and under identical regrading, which agrees with the wording test (catalyst and thesis least robust). Before the flag goes on: fix turn order in the grader input (or grade an average over several orders), answer `trade_proposed` from structure, and fit the Contested band with this noise floor as a target. Sample caveat: 4 tickers, one rep each, 20 Rooms; pass rates carry roughly +/-20 points of sampling error.

## Not yet done

1. **Jev and DeepInfra graders: built (WP-22 hosted-graders lane), not yet run. They need `~/cr267_wp20/bakeoff.env` on melehost, which Saiful's team creates (the lane did not).** Spend for the bake-off is approved (2026-11-21).
   1. Format, two lines, no quotes, no spaces around `=`, mode 600:
      ```
      JEV_API_KEY=<Jev key>
      DEEPINFRA_API_KEY=<DeepInfra key>
      ```
   2. The key stays out of the repo, `~/ami_trade/.env` and `infra/alpha.env`. `wp22_run.sh` hands the file to the throwaway container with `docker compose run --env-from-file`; the scorer reads it from the container environment only and, if a key is missing or blank, stops with `bakeoff.env missing JEV_API_KEY` (name only, exit 2) before touching the database. `wp22_run.sh` itself refuses to start a paid grader if the file does not exist.
   3. Pins, so the run is reproducible: Jev `jev-1.13.0` (`--jev-version`; "latest" is refused; source: S12 plan section 3 item 1 and the October corpus). DeepInfra `deepseek-ai/DeepSeek-V4-Flash` (`--model`; Beta's primary, S11 plan section 3b; priced $0.09 in / $0.18 out per 1M tokens as in `infra/beta.env.example`). The grader runs on the gateway's hosted slot (`vllm_fallback`, kind openai, `https://api.deepinfra.com/v1/openai`) configured in-process by the scorer; `LLM_PROVIDER_ALLOWLIST` is `vllm_fallback` for DeepInfra, `mock` for Jev (no gateway provider), Anthropic blanked in both.
   4. Spend cap, enforced in code per Room before it starts: `--max-usd` (default 5.00) against each result's `cost_usd`; for Jev that is `usage.input_tokens` x $0.042 per 1M (constant from `jev_v1_pilot.py`, unverified against an invoice, outputs unbilled). A result with no cost (no usage returned, or a model with no price) counts toward `--max-calls` (default 300) instead. When a cap is hit the run stops cleanly, finished Rooms stay in the JSONL, `<out>.meta.json` records `spend.cap_hit`, `usd_spent`, `rooms_graded` and `rooms_skipped_by_cap`, and the same command resumes. With `--concurrency N` a run can overshoot by up to N-1 Rooms.
   5. Unknowns the pilot answers: whether DeepInfra returns token probabilities together with `response_format` json_schema (if not, the grader falls back to 1-5 scores and says so in `extra.logprobs`), whether `usage` is returned on the stream (cost would then be unpriced and the call cap applies), and whether DeepSeek-V4-Flash needs thinking switched off for the grader (no extra body is set).
2. **10-Room pilot per grader** (run on melehost; each is small at any plausible price; read the meta before going on):
   ```
   ssh melehost 'mkdir -p ~/cr267_wp20/out/wp22_jev ~/cr267_wp20/out/wp22_deepinfra'
   ssh melehost '~/cr267_wp20/wp22_tool/wp22_run.sh jev_pilot score --grader jev --jev-version jev-1.13.0 --runs /out/arm1/runs_wp20-arm1.jsonl --out /out/wp22_jev/pilot.jsonl --pilot 10 --max-usd 1.00 --max-calls 60'
   ssh melehost '~/cr267_wp20/wp22_tool/wp22_run.sh di_pilot score --grader deepinfra --model deepseek-ai/DeepSeek-V4-Flash --runs /out/arm1/runs_wp20-arm1.jsonl --out /out/wp22_deepinfra/pilot.jsonl --pilot 10 --max-usd 1.00 --max-calls 60'
   ```
   Cost per Room and the go/no-go for the full run (reads only the meta file, no keys; use `wp22_deepinfra` for the other grader):
   ```
   ssh melehost "python3 -c \"import json,sys; s=json.load(open(sys.argv[1]))['spend']; n=s['rooms_priced']; print(s); print('usd/room', s['usd_spent']/n if n else 'UNPRICED: use calls', 'x300 =', 300*s['usd_spent']/n if n else '')\" ~/cr267_wp20/out/wp22_jev/pilot.meta.json"
   ```
   Also check `errors` in the meta before spending more.
3. **Full 300 Rooms per grader, only if pilot USD per Room x 300 is under the cap (5.00; if a grader is unpriced, only if pilot calls per Room x 300 is under `--max-calls`).** Background, resumable; stop only your own container (`docker stop wp22_<name>`):
   ```
   ssh melehost 'nohup ~/cr267_wp20/wp22_tool/wp22_run.sh jev_full score --grader jev --jev-version jev-1.13.0 --runs /out/arm1/runs_wp20-arm1.jsonl --out /out/wp22_jev/scores_arm1.jsonl --max-usd 5.00 --max-calls 300 > ~/cr267_wp20/logs/wp22_jev_full.log 2>&1 &'
   ssh melehost 'nohup ~/cr267_wp20/wp22_tool/wp22_run.sh di_full score --grader deepinfra --model deepseek-ai/DeepSeek-V4-Flash --runs /out/arm1/runs_wp20-arm1.jsonl --out /out/wp22_deepinfra/scores_arm1.jsonl --max-usd 5.00 --concurrency 4 > ~/cr267_wp20/logs/wp22_di_full.log 2>&1 &'
   ```
   If the pilot says 300 Rooms would exceed the cap, do not raise `--max-usd` without Saiful. The wording (20 Rooms x 5 phrasings) and input (140 grades) tests on a hosted grader are separate runs with their own caps (`wording` and `inputs` take the same flags). Tables: `wp22_score.py report --runs ... --scores /out/wp22_<grader>/scores_arm1.jsonl --out ...` (the heading names the grader from the meta file).
4. Code grader over cards: done 2026-11-22 (section "Code grader (arm 2)" above).
5. Recommendation: stands (DeepInfra); no recommendation of Jev without noting that vendor terms are still owed.
