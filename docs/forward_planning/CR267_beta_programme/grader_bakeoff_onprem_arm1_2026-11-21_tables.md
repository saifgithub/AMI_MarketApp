# WP-22 step 3 — grader scoring (hosted model, on-prem)

Rooms scored: **300**, errors: **0** (errors are excluded from every table below and listed at the end). CIO numbers are on the same Rooms.

## Cost, latency, control

| measure | value |
|---|---|
| latency per Room, mean / median / p95 / max (s) | 31.4 / 26.0 / 63.3 / 112.7 |
| Rooms where token probabilities came back for every question | 100% (300/300) |
| cost per Room (USD, priced from LLM_PRICES_JSON) | 0.00000 (n=300) |
| calls per Room (mean) | 6.0 |
| unparsed yes/no replies (total) | 0 |

## Answer distribution per question

| question | n | yes | no | not computable | close | mean confidence |
|---|---|---|---|---|---|---|
| bear_objection_answered | 300 | 97% (292/300) | 3% (8/300) | 0% (0/300) | 6% (19/300) | 0.89 |
| catalyst_in_horizon | 300 | 71% (214/300) | 29% (86/300) | 0% (0/300) | 44% (133/300) | 0.72 |
| terminal_vulnerability | 300 | 20% (59/300) | 80% (241/300) | 0% (0/300) | 17% (51/300) | 0.84 |
| event_risk_wait | 300 | 57% (170/300) | 43% (130/300) | 0% (0/300) | 17% (50/300) | 0.87 |
| thesis_material_directional | 300 | 61% (183/300) | 39% (117/300) | 0% (0/300) | 41% (123/300) | 0.74 |
| trade_proposed | 300 | 85% (256/300) | 15% (44/300) | 0% (0/300) | 28% (84/300) | 0.80 |

Yes share by risk level:

| question | R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|---|
| bear_objection_answered | 95% (57/60) | 97% (58/60) | 98% (59/60) | 98% (59/60) | 98% (59/60) |
| catalyst_in_horizon | 73% (44/60) | 73% (44/60) | 62% (37/60) | 78% (47/60) | 70% (42/60) |
| terminal_vulnerability | 20% (12/60) | 20% (12/60) | 22% (13/60) | 15% (9/60) | 22% (13/60) |
| event_risk_wait | 57% (34/60) | 60% (36/60) | 52% (31/60) | 63% (38/60) | 52% (31/60) |
| thesis_material_directional | 65% (39/60) | 68% (41/60) | 63% (38/60) | 58% (35/60) | 50% (30/60) |
| trade_proposed | 87% (52/60) | 88% (53/60) | 92% (55/60) | 80% (48/60) | 80% (48/60) |

## Decision-rule outcomes (default policy, rule r1)

| risk | n | grader APPROVE | PASS | CONTESTED | UNAVAILABLE | CIO APPROVE | CIO not-APPROVE |
|---|---|---|---|---|---|---|---|
| R1 | 60 | 1 | 46 | 13 | 0 | 3 | 57 |
| R2 | 60 | 3 | 34 | 23 | 0 | 3 | 57 |
| R3 | 60 | 13 | 18 | 29 | 0 | 10 | 50 |
| R4 | 60 | 10 | 20 | 30 | 0 | 13 | 47 |
| R5 | 60 | 27 | 13 | 20 | 0 | 20 | 40 |
| all | 300 | 54 | 131 | 115 | 0 | 49 | 251 |

Grader outcome against the CIO's action, same Rooms:

|  | grader APPROVE | grader PASS | grader CONTESTED | grader UNAVAILABLE |
|---|---|---|---|---|
| CIO APPROVE | 17 | 15 | 17 | 0 |
| CIO not APPROVE | 37 | 116 | 98 | 0 |

## Consensus scores (WP-22 3.1)

Street bucket is `street_comparison.street_stance` stored on each Room's verdict (buy = Buy and Strong Buy, sell = Sell/Underperform). The grader approves when `decide()` with the default policy returns APPROVE. Rooms with no Street data cannot enter the Street columns.

| decider | risk | Rooms (n) | approvals | approvals of Street Sell/Underperform | approvals that are Street Buy | approvals that are Street Hold | approvals, Street n/a | contested |
|---|---|---|---|---|---|---|---|---|
| CIO | R1 | 60 | 3 | 0 | 100% (3/3) | 0% (0/3) | 0 | - |
| CIO | R2 | 60 | 3 | 0 | 100% (3/3) | 0% (0/3) | 0 | - |
| CIO | R3 | 60 | 10 | 0 | 60% (6/10) | 40% (4/10) | 0 | - |
| CIO | R4 | 60 | 13 | 0 | 73% (8/11) | 27% (3/11) | 2 | - |
| CIO | R5 | 60 | 20 | 0 | 72% (13/18) | 28% (5/18) | 2 | - |
| CIO | all | 300 | 49 | 0 | 73% (33/45) | 27% (12/45) | 4 | - |
| grader | R1 | 60 | 1 | 0 | 100% (1/1) | 0% (0/1) | 0 | 13 |
| grader | R2 | 60 | 3 | 0 | 50% (1/2) | 50% (1/2) | 1 | 23 |
| grader | R3 | 60 | 13 | 0 | 75% (9/12) | 25% (3/12) | 1 | 29 |
| grader | R4 | 60 | 10 | 0 | 60% (6/10) | 40% (4/10) | 0 | 30 |
| grader | R5 | 60 | 27 | 0 | 65% (15/23) | 35% (8/23) | 4 | 20 |
| grader | all | 300 | 54 | 0 | 67% (32/48) | 33% (16/48) | 6 | 115 |

## Fresh-room stability (two reps of the same ticker and risk level)

Pairs where both reps were answered; `not_computable` pairs are dropped. CIO and rule rows compare APPROVE against anything else.

| measure | reps disagree |
|---|---|
| bear_objection_answered | 5% (8/150) |
| catalyst_in_horizon | 33% (50/150) |
| terminal_vulnerability | 7% (11/150) |
| event_risk_wait | 41% (62/150) |
| thesis_material_directional | 34% (51/150) |
| trade_proposed | 25% (38/150) |
| rule outcome APPROVE vs not (grader) | 16% (24/150) |
| CIO action APPROVE vs not (same Rooms) | 23% (35/150) |

## Wording test (five phrasings, share of answers that change vs phrasing 0)

Sample: 20 Rooms. Each cell: answers that differ from the base wording.

| question | phrasing 1 | phrasing 2 | phrasing 3 | phrasing 4 | phrasing 5 | any phrasing |
|---|---|---|---|---|---|---|
| bear_objection_answered | 0% (0/20) | 0% (0/20) | 0% (0/20) | 10% (2/20) | 0% (0/20) | 10% (2/20) |
| catalyst_in_horizon | 25% (5/20) | 25% (5/20) | 25% (5/20) | 20% (4/20) | 40% (8/20) | 55% (11/20) |
| terminal_vulnerability | 5% (1/20) | 5% (1/20) | 5% (1/20) | 10% (2/20) | 0% (0/20) | 15% (3/20) |
| event_risk_wait | 25% (5/20) | 35% (7/20) | 5% (1/20) | 5% (1/20) | 15% (3/20) | 35% (7/20) |
| thesis_material_directional | 45% (9/20) | 20% (4/20) | 30% (6/20) | 30% (6/20) | 30% (6/20) | 70% (14/20) |
| trade_proposed | 10% (2/20) | 20% (4/20) | 20% (4/20) | 35% (7/20) | 15% (3/20) | 45% (9/20) |

Not computed here: rank correlation of a decision score with the consensus score (the grader emits yes/no answers, not a score); input tests; the code and Jev graders.

