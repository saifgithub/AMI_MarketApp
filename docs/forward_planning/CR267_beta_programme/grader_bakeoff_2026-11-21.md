# CR267 WP-22 grader bake-off (PARTIAL: on-prem grader, arm 1)

**Status:** 1 of 3 graders scored. Jev and the DeepInfra-hosted model need API keys that are not set (keys deferred by Saiful); the code grader needs WP-20 arm 2 (cards on), which is running. Full tables: `grader_bakeoff_onprem_arm1_2026-11-21_tables.md` (from `docs/tools/room_investigation_V2/tools/wp22_score.py report`).

**Measured on:** the 300 WP-20 arm-1 Rooms (30 tickers × R1–R5 × 2 reps, cards off), on-prem vLLM, model root `/models/qwen38-flash-next-abliterated-nvfp4` (read from `/v1/models`), temperature 0, question set q1, decision rule r1 with the default policy (unfitted placeholders). The grader saw the 11 desk turns, never the CIO's verdict. Read-only DB access; no `llm_audit` rows written; $0.

## What it shows

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

1. Jev and DeepInfra graders: **need keys** (Jev `JEV_API_KEY`; a DeepInfra key for the hosted slot). Spend for the bake-off is approved (2026-11-21); the keys are not set.
2. Code grader over cards: after WP-20 arm 2.
3. Recommendation: after all three graders are scored. No recommendation of Jev without noting that vendor terms are still owed.
