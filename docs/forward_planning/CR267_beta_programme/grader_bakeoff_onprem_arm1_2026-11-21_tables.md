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

## Input tests with known answers (WP-22 3.3)

Each perturbed transcript is graded once on the on-prem grader and judged against its expectation. `n` counts Rooms where the perturbation applied and both grades parsed.

| test | expectation | n | pass rate | failing Rooms |
|---|---|---|---|---|
| Control: original regraded | all six answers unchanged (grader noise floor) | 20 | 65% (13/20) | MA-r2-rep1, MA-r4-rep1, SEDG-r1-rep2, SEDG-r2-rep2, SEDG-r4-rep2, SEDG-r5-rep2, WFC-r5-rep1 |
| Planted fatal flaw | terminal_vulnerability = yes and rule PASS at R1-R5 | 20 | 75% (15/20) | BAC-r2-rep2, BAC-r5-rep2, MA-r3-rep1, MA-r4-rep1, WFC-r2-rep1 |
| Bear evidence removed | rule outcome not more cautious than the original | 20 | 65% (13/20) | BAC-r2-rep2, BAC-r3-rep2, BAC-r4-rep2, SEDG-r3-rep2, SEDG-r4-rep2, WFC-r1-rep1, WFC-r5-rep1 |
| Bear numbers strengthened (x2) | P(yes) on bear_objection_answered does not rise (+0.01 tolerance) and rule not less cautious | 20 | 75% (15/20) | MA-r1-rep1, MA-r2-rep1, SEDG-r2-rep2, SEDG-r4-rep2, WFC-r4-rep1 |
| Turns reordered (seed 22) | all six answers unchanged | 20 | 20% (4/20) | BAC-r1-rep2, BAC-r2-rep2, BAC-r3-rep2, BAC-r4-rep2, MA-r1-rep1, MA-r2-rep1, MA-r3-rep1, MA-r5-rep1, SEDG-r1-rep2, SEDG-r2-rep2, SEDG-r3-rep2, SEDG-r4-rep2, SEDG-r5-rep2, WFC-r3-rep1, WFC-r4-rep1, WFC-r5-rep1 |
| Ticker and company renamed | all six answers unchanged | 20 | 70% (14/20) | BAC-r2-rep2, BAC-r3-rep2, BAC-r4-rep2, SEDG-r1-rep2, SEDG-r3-rep2, SEDG-r5-rep2 |

Per-Room detail (P = pass, F = fail, - = not applicable):

| Room | original rule outcome | Control: original regraded | Planted fatal flaw | Bear evidence removed | Bear numbers strengthened (x2) | Turns reordered (seed 22) | Ticker and company renamed |
|---|---|---|---|---|---|---|---|
| BAC-r1-rep2 | PASS | P | P | P | P | F | P |
| BAC-r2-rep2 | CONTESTED | P | F | F | P | F | F |
| BAC-r3-rep2 | CONTESTED | P | P | F | P | F | F |
| BAC-r4-rep2 | CONTESTED | P | P | F | P | F | F |
| BAC-r5-rep2 | APPROVE | P | F | P | P | P | P |
| MA-r1-rep1 | PASS | P | P | P | F | F | P |
| MA-r2-rep1 | PASS | F | P | P | F | F | P |
| MA-r3-rep1 | APPROVE | P | F | P | P | F | P |
| MA-r4-rep1 | APPROVE | F | F | P | P | P | P |
| MA-r5-rep1 | APPROVE | P | P | P | P | F | P |
| SEDG-r1-rep2 | PASS | F | P | P | P | F | F |
| SEDG-r2-rep2 | CONTESTED | F | P | P | F | F | P |
| SEDG-r3-rep2 | CONTESTED | P | P | F | P | F | F |
| SEDG-r4-rep2 | APPROVE | F | P | F | F | F | P |
| SEDG-r5-rep2 | CONTESTED | F | P | P | P | F | F |
| WFC-r1-rep1 | CONTESTED | P | P | F | P | P | P |
| WFC-r2-rep1 | PASS | P | F | P | P | P | P |
| WFC-r3-rep1 | CONTESTED | P | P | P | P | F | P |
| WFC-r4-rep1 | PASS | P | P | P | F | F | P |
| WFC-r5-rep1 | APPROVE | F | P | F | P | F | P |

Failures, with the measured values:

| test | Room | what happened |
|---|---|---|
| Control: original regraded | MA-r2-rep1 | changed: thesis_material_directional; max |dconf| 0.09; rule PASS -> CONTESTED |
| Control: original regraded | MA-r4-rep1 | changed: catalyst_in_horizon; max |dconf| 0.21; rule APPROVE -> APPROVE |
| Control: original regraded | SEDG-r1-rep2 | changed: catalyst_in_horizon,trade_proposed; max |dconf| 0.12; rule PASS -> PASS |
| Control: original regraded | SEDG-r2-rep2 | changed: trade_proposed; max |dconf| 0.17; rule CONTESTED -> PASS |
| Control: original regraded | SEDG-r4-rep2 | changed: event_risk_wait; max |dconf| 0.09; rule APPROVE -> CONTESTED |
| Control: original regraded | SEDG-r5-rep2 | changed: trade_proposed; max |dconf| 0.11; rule CONTESTED -> CONTESTED |
| Control: original regraded | WFC-r5-rep1 | changed: thesis_material_directional; max |dconf| 0.10; rule APPROVE -> APPROVE |
| Planted fatal flaw | BAC-r2-rep2 | terminal_vulnerability=yes; not PASS at R5=CONTESTED |
| Planted fatal flaw | BAC-r5-rep2 | terminal_vulnerability=yes; not PASS at R5=CONTESTED |
| Planted fatal flaw | MA-r3-rep1 | terminal_vulnerability=no; not PASS at R5=CONTESTED |
| Planted fatal flaw | MA-r4-rep1 | terminal_vulnerability=no; not PASS at R1=CONTESTED,R2=CONTESTED,R3=CONTESTED,R4=CONTESTED,R5=CONTESTED |
| Planted fatal flaw | WFC-r2-rep1 | terminal_vulnerability=yes; not PASS at R5=CONTESTED |
| Bear evidence removed | BAC-r2-rep2 | CONTESTED -> PASS |
| Bear evidence removed | BAC-r3-rep2 | CONTESTED -> PASS |
| Bear evidence removed | BAC-r4-rep2 | CONTESTED -> PASS |
| Bear evidence removed | SEDG-r3-rep2 | CONTESTED -> PASS |
| Bear evidence removed | SEDG-r4-rep2 | APPROVE -> CONTESTED |
| Bear evidence removed | WFC-r1-rep1 | CONTESTED -> PASS |
| Bear evidence removed | WFC-r5-rep1 | APPROVE -> CONTESTED |
| Bear numbers strengthened (x2) | MA-r1-rep1 | P(yes) 0.82 -> 0.59; PASS -> CONTESTED |
| Bear numbers strengthened (x2) | MA-r2-rep1 | P(yes) 0.95 -> 0.95; PASS -> CONTESTED |
| Bear numbers strengthened (x2) | SEDG-r2-rep2 | P(yes) 0.97 -> 0.98; CONTESTED -> CONTESTED |
| Bear numbers strengthened (x2) | SEDG-r4-rep2 | P(yes) 0.95 -> 0.99; APPROVE -> CONTESTED |
| Bear numbers strengthened (x2) | WFC-r4-rep1 | P(yes) 0.90 -> 0.94; PASS -> PASS |
| Turns reordered (seed 22) | BAC-r1-rep2 | changed: trade_proposed; max |dconf| 0.29; rule PASS -> PASS |
| Turns reordered (seed 22) | BAC-r2-rep2 | changed: thesis_material_directional; max |dconf| 0.28; rule CONTESTED -> APPROVE |
| Turns reordered (seed 22) | BAC-r3-rep2 | changed: thesis_material_directional,trade_proposed; max |dconf| 0.14; rule CONTESTED -> CONTESTED |
| Turns reordered (seed 22) | BAC-r4-rep2 | changed: bear_objection_answered,catalyst_in_horizon,thesis_material_directional,trade_proposed; max |dconf| 0.36; rule CONTESTED -> CONTESTED |
| Turns reordered (seed 22) | MA-r1-rep1 | changed: catalyst_in_horizon,event_risk_wait; max |dconf| 0.22; rule PASS -> PASS |
| Turns reordered (seed 22) | MA-r2-rep1 | changed: trade_proposed; max |dconf| 0.22; rule PASS -> PASS |
| Turns reordered (seed 22) | MA-r3-rep1 | changed: catalyst_in_horizon,event_risk_wait; max |dconf| 0.30; rule APPROVE -> APPROVE |
| Turns reordered (seed 22) | MA-r5-rep1 | changed: catalyst_in_horizon; max |dconf| 0.17; rule APPROVE -> APPROVE |
| Turns reordered (seed 22) | SEDG-r1-rep2 | changed: bear_objection_answered,trade_proposed; max |dconf| 0.15; rule PASS -> PASS |
| Turns reordered (seed 22) | SEDG-r2-rep2 | changed: bear_objection_answered,catalyst_in_horizon; max |dconf| 0.29; rule CONTESTED -> CONTESTED |
| Turns reordered (seed 22) | SEDG-r3-rep2 | changed: catalyst_in_horizon,trade_proposed; max |dconf| 0.34; rule CONTESTED -> CONTESTED |
| Turns reordered (seed 22) | SEDG-r4-rep2 | changed: event_risk_wait; max |dconf| 0.29; rule APPROVE -> CONTESTED |
| Turns reordered (seed 22) | SEDG-r5-rep2 | changed: trade_proposed; max |dconf| 0.13; rule CONTESTED -> CONTESTED |
| Turns reordered (seed 22) | WFC-r3-rep1 | changed: catalyst_in_horizon,trade_proposed; max |dconf| 0.15; rule CONTESTED -> PASS |
| Turns reordered (seed 22) | WFC-r4-rep1 | changed: thesis_material_directional,trade_proposed; max |dconf| 0.20; rule PASS -> CONTESTED |
| Turns reordered (seed 22) | WFC-r5-rep1 | changed: thesis_material_directional; max |dconf| 0.22; rule APPROVE -> CONTESTED |
| Ticker and company renamed | BAC-r2-rep2 | changed: thesis_material_directional; max |dconf| 0.18; rule CONTESTED -> CONTESTED |
| Ticker and company renamed | BAC-r3-rep2 | changed: thesis_material_directional; max |dconf| 0.17; rule CONTESTED -> CONTESTED |
| Ticker and company renamed | BAC-r4-rep2 | changed: catalyst_in_horizon; max |dconf| 0.19; rule CONTESTED -> CONTESTED |
| Ticker and company renamed | SEDG-r1-rep2 | changed: catalyst_in_horizon,trade_proposed; max |dconf| 0.06; rule PASS -> PASS |
| Ticker and company renamed | SEDG-r3-rep2 | changed: thesis_material_directional; max |dconf| 0.03; rule CONTESTED -> CONTESTED |
| Ticker and company renamed | SEDG-r5-rep2 | changed: trade_proposed; max |dconf| 0.21; rule CONTESTED -> CONTESTED |

Rule outcome transitions, original -> perturbed (Room's own risk level):

| perturbation | transitions |
|---|---|
| Planted fatal flaw | APPROVE -> CONTESTED x2; APPROVE -> PASS x4; CONTESTED -> PASS x8; PASS -> PASS x6 |
| Bear evidence removed | APPROVE -> APPROVE x4; APPROVE -> CONTESTED x2; CONTESTED -> CONTESTED x3; CONTESTED -> PASS x5; PASS -> PASS x6 |
| Bear numbers strengthened (x2) | APPROVE -> APPROVE x3; APPROVE -> CONTESTED x3; CONTESTED -> CONTESTED x6; CONTESTED -> PASS x2; PASS -> CONTESTED x2; PASS -> PASS x4 |
| Turns reordered (seed 22) | APPROVE -> APPROVE x2; APPROVE -> CONTESTED x4; CONTESTED -> APPROVE x1; CONTESTED -> CONTESTED x5; CONTESTED -> PASS x2; PASS -> CONTESTED x1; PASS -> PASS x5 |
| Ticker and company renamed | APPROVE -> APPROVE x3; APPROVE -> CONTESTED x3; CONTESTED -> CONTESTED x7; CONTESTED -> PASS x1; PASS -> PASS x6 |

Bear numbers strengthened: mean change in P(yes) on bear_objection_answered -0.057 (min -0.236, max +0.039, n=20); numbers scaled per Room: 8, 7, 9, 12, 5, 7, 3, 14, 11, 13, 8, 5, 11, 11, 10, 4, 11, 6, 4, 17.

Ticker rename: Rooms where the ticker string is still present after rename: none; Rooms with no company name found: none.

Perturbation builders (all in code): planted flaw = fixed terminal-risk paragraph appended to the last `bear_researcher` turn; bear removed = every `bear_researcher` turn replaced by one number-free line (later Bear turns dropped); strengthened = every number attached to %, x or $ (optional K/M/B/T, million, billion) inside a sentence containing a downside or leverage keyword multiplied by 2, decimals kept; reordered = non-CIO turns shuffled with `random.Random(22)`; renamed = the ticker and the `ticker_reference` company name (listing name and name without Inc/Corp/Common Stock suffixes) replaced by `TICKR` / `Company X` in every turn and in the header.

Not computed here: rank correlation of a decision score with the consensus score (the grader emits yes/no answers, not a score); the code and Jev graders.

