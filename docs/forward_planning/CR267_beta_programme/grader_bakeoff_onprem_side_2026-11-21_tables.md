# WP-22 step 3 — grader scoring (hosted model, on-prem)

Rooms scored: **50**, errors: **0** (errors are excluded from every table below and listed at the end). CIO numbers are on the same Rooms.

## Cost, latency, control

| measure | value |
|---|---|
| latency per Room, mean / median / p95 / max (s) | 30.6 / 25.8 / 56.6 / 78.7 |
| Rooms where token probabilities came back for every question | 100% (50/50) |
| cost per Room (USD, priced from LLM_PRICES_JSON) | 0.00000 (n=50) |
| calls per Room (mean) | 6.0 |
| unparsed yes/no replies (total) | 0 |

## Answer distribution per question

| question | n | yes | no | not computable | close | mean confidence |
|---|---|---|---|---|---|---|
| bear_objection_answered | 50 | 100% (50/50) | 0% (0/50) | 0% (0/50) | 2% (1/50) | 0.90 |
| catalyst_in_horizon | 50 | 62% (31/50) | 38% (19/50) | 0% (0/50) | 48% (24/50) | 0.73 |
| terminal_vulnerability | 50 | 42% (21/50) | 58% (29/50) | 0% (0/50) | 28% (14/50) | 0.79 |
| event_risk_wait | 50 | 64% (32/50) | 36% (18/50) | 0% (0/50) | 12% (6/50) | 0.91 |
| thesis_material_directional | 50 | 52% (26/50) | 48% (24/50) | 0% (0/50) | 32% (16/50) | 0.77 |
| trade_proposed | 50 | 90% (45/50) | 10% (5/50) | 0% (0/50) | 36% (18/50) | 0.76 |

Yes share by risk level:

| question | R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|---|
| bear_objection_answered | 100% (10/10) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 100% (10/10) |
| catalyst_in_horizon | 70% (7/10) | 50% (5/10) | 80% (8/10) | 50% (5/10) | 60% (6/10) |
| terminal_vulnerability | 30% (3/10) | 40% (4/10) | 40% (4/10) | 50% (5/10) | 50% (5/10) |
| event_risk_wait | 70% (7/10) | 70% (7/10) | 50% (5/10) | 60% (6/10) | 70% (7/10) |
| thesis_material_directional | 70% (7/10) | 50% (5/10) | 40% (4/10) | 30% (3/10) | 70% (7/10) |
| trade_proposed | 100% (10/10) | 90% (9/10) | 90% (9/10) | 80% (8/10) | 90% (9/10) |

## Decision-rule outcomes (default policy, rule r1)

| risk | n | grader APPROVE | PASS | CONTESTED | UNAVAILABLE | CIO APPROVE | CIO not-APPROVE |
|---|---|---|---|---|---|---|---|
| R1 | 10 | 0 | 10 | 0 | 0 | 0 | 10 |
| R2 | 10 | 1 | 8 | 1 | 0 | 0 | 10 |
| R3 | 10 | 0 | 5 | 5 | 0 | 0 | 10 |
| R4 | 10 | 0 | 8 | 2 | 0 | 1 | 9 |
| R5 | 10 | 2 | 2 | 6 | 0 | 3 | 7 |
| all | 50 | 3 | 33 | 14 | 0 | 4 | 46 |

Grader outcome against the CIO's action, same Rooms:

|  | grader APPROVE | grader PASS | grader CONTESTED | grader UNAVAILABLE |
|---|---|---|---|---|
| CIO APPROVE | 2 | 1 | 1 | 0 |
| CIO not APPROVE | 1 | 32 | 13 | 0 |

## Consensus scores (WP-22 3.1)

Street bucket is `street_comparison.street_stance` stored on each Room's verdict (buy = Buy and Strong Buy, sell = Sell/Underperform). The grader approves when `decide()` with the default policy returns APPROVE. Rooms with no Street data cannot enter the Street columns.

| decider | risk | Rooms (n) | approvals | approvals of Street Sell/Underperform | approvals that are Street Buy | approvals that are Street Hold | approvals, Street n/a | contested |
|---|---|---|---|---|---|---|---|---|
| CIO | R1 | 10 | 0 | 0 | n/a | n/a | 0 | - |
| CIO | R2 | 10 | 0 | 0 | n/a | n/a | 0 | - |
| CIO | R3 | 10 | 0 | 0 | n/a | n/a | 0 | - |
| CIO | R4 | 10 | 1 | 0 | 0% (0/1) | 100% (1/1) | 0 | - |
| CIO | R5 | 10 | 3 | 0 | 0% (0/3) | 100% (3/3) | 0 | - |
| CIO | all | 50 | 4 | 0 | 0% (0/4) | 100% (4/4) | 0 | - |
| grader | R1 | 10 | 0 | 0 | n/a | n/a | 0 | 0 |
| grader | R2 | 10 | 1 | 0 | 0% (0/1) | 100% (1/1) | 0 | 1 |
| grader | R3 | 10 | 0 | 0 | n/a | n/a | 0 | 5 |
| grader | R4 | 10 | 0 | 0 | n/a | n/a | 0 | 2 |
| grader | R5 | 10 | 2 | 0 | 0% (0/2) | 100% (2/2) | 0 | 6 |
| grader | all | 50 | 3 | 0 | 0% (0/3) | 100% (3/3) | 0 | 14 |

## Fresh-room stability (two reps of the same ticker and risk level)

Pairs where both reps were answered; `not_computable` pairs are dropped. CIO and rule rows compare APPROVE against anything else.

| measure | reps disagree |
|---|---|
| bear_objection_answered | 0% (0/25) |
| catalyst_in_horizon | 20% (5/25) |
| terminal_vulnerability | 12% (3/25) |
| event_risk_wait | 24% (6/25) |
| thesis_material_directional | 32% (8/25) |
| trade_proposed | 12% (3/25) |
| rule outcome APPROVE vs not (grader) | 12% (3/25) |
| CIO action APPROVE vs not (same Rooms) | 8% (2/25) |

Not computed here: rank correlation of a decision score with the consensus score (the grader emits yes/no answers, not a score); input tests; the code and Jev graders.

