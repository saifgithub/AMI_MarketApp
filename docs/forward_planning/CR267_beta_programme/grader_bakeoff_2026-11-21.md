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

## Not yet done

1. Wording test (20 Rooms × 5 phrasings), input tests with known answers.
2. Jev and DeepInfra graders: **need keys** (Jev `JEV_API_KEY`; a DeepInfra key for the hosted slot). Spend for the bake-off is approved (2026-11-21); the keys are not set.
3. Code grader over cards: after WP-20 arm 2.
4. Recommendation: after all three graders are scored. No recommendation of Jev without noting that vendor terms are still owed.
