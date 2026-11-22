# WP-22 step 3 — grader scoring (DeepInfra deepseek-ai/DeepSeek-V4-Flash)

Model root: `DeepInfra deepseek-ai/DeepSeek-V4-Flash` (end `DeepInfra deepseek-ai/DeepSeek-V4-Flash`); question set `q1`; image `alpha-2026-11-21-6` `c3db07e5`; concurrency 4.

Rooms scored: **300**, errors: **0** (errors are excluded from every table below and listed at the end). CIO numbers are on the same Rooms.

## Cost, latency, control

| measure | value |
|---|---|
| latency per Room, mean / median / p95 / max (s) | 7.9 / 7.8 / 8.9 / 11.4 |
| Rooms where token probabilities came back for every question | 100% (300/300) |
| cost per Room (USD, priced from LLM_PRICES_JSON) | 0.00183 (n=300) |
| calls per Room (mean) | 6.0 |
| unparsed yes/no replies (total) | 0 |

## Answer distribution per question

| question | n | yes | no | not computable | close | mean confidence |
|---|---|---|---|---|---|---|
| bear_objection_answered | 300 | 35% (104/300) | 65% (196/300) | 0% (0/300) | 0% (0/300) | 1.00 |
| catalyst_in_horizon | 300 | 59% (178/300) | 41% (122/300) | 0% (0/300) | 0% (0/300) | 1.00 |
| terminal_vulnerability | 300 | 39% (118/300) | 61% (182/300) | 0% (0/300) | 0% (0/300) | 1.00 |
| event_risk_wait | 300 | 70% (210/300) | 30% (90/300) | 0% (0/300) | 0% (0/300) | 1.00 |
| thesis_material_directional | 300 | 17% (51/300) | 83% (249/300) | 0% (0/300) | 0% (0/300) | 1.00 |
| trade_proposed | 300 | 96% (287/300) | 4% (13/300) | 0% (0/300) | 0% (0/300) | 1.00 |

Yes share by risk level:

| question | R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|---|
| bear_objection_answered | 28% (17/60) | 23% (14/60) | 47% (28/60) | 43% (26/60) | 32% (19/60) |
| catalyst_in_horizon | 60% (36/60) | 58% (35/60) | 57% (34/60) | 60% (36/60) | 62% (37/60) |
| terminal_vulnerability | 43% (26/60) | 37% (22/60) | 35% (21/60) | 33% (20/60) | 48% (29/60) |
| event_risk_wait | 72% (43/60) | 75% (45/60) | 67% (40/60) | 75% (45/60) | 62% (37/60) |
| thesis_material_directional | 23% (14/60) | 22% (13/60) | 13% (8/60) | 12% (7/60) | 15% (9/60) |
| trade_proposed | 98% (59/60) | 93% (56/60) | 95% (57/60) | 92% (55/60) | 100% (60/60) |

## Decision-rule outcomes (default policy, rule r1)

| risk | n | grader APPROVE | PASS | CONTESTED | UNAVAILABLE | CIO APPROVE | CIO not-APPROVE |
|---|---|---|---|---|---|---|---|
| R1 | 60 | 1 | 59 | 0 | 0 | 3 | 57 |
| R2 | 60 | 2 | 58 | 0 | 0 | 3 | 57 |
| R3 | 60 | 4 | 56 | 0 | 0 | 10 | 50 |
| R4 | 60 | 5 | 55 | 0 | 0 | 13 | 47 |
| R5 | 60 | 31 | 29 | 0 | 0 | 20 | 40 |
| all | 300 | 43 | 257 | 0 | 0 | 49 | 251 |

Grader outcome against the CIO's action, same Rooms:

|  | grader APPROVE | grader PASS | grader CONTESTED | grader UNAVAILABLE |
|---|---|---|---|---|
| CIO APPROVE | 17 | 32 | 0 | 0 |
| CIO not APPROVE | 26 | 225 | 0 | 0 |

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
| grader | R1 | 60 | 1 | 0 | n/a | n/a | 1 | 0 |
| grader | R2 | 60 | 2 | 0 | 100% (2/2) | 0% (0/2) | 0 | 0 |
| grader | R3 | 60 | 4 | 0 | 33% (1/3) | 67% (2/3) | 1 | 0 |
| grader | R4 | 60 | 5 | 0 | 60% (3/5) | 40% (2/5) | 0 | 0 |
| grader | R5 | 60 | 31 | 0 | 74% (20/27) | 26% (7/27) | 4 | 0 |
| grader | all | 300 | 43 | 0 | 70% (26/37) | 30% (11/37) | 6 | 0 |

## Fresh-room stability (two reps of the same ticker and risk level)

Pairs where both reps were answered; `not_computable` pairs are dropped. CIO and rule rows compare APPROVE against anything else.

| measure | reps disagree |
|---|---|
| bear_objection_answered | 41% (62/150) |
| catalyst_in_horizon | 39% (58/150) |
| terminal_vulnerability | 16% (24/150) |
| event_risk_wait | 36% (54/150) |
| thesis_material_directional | 21% (31/150) |
| trade_proposed | 7% (11/150) |
| rule outcome APPROVE vs not (grader) | 6% (9/150) |
| CIO action APPROVE vs not (same Rooms) | 23% (35/150) |

## Wording test (five phrasings, share of answers that change vs phrasing 0)

Sample: 20 Rooms. Each cell: answers that differ from the base wording.

| question | phrasing 1 | phrasing 2 | phrasing 3 | phrasing 4 | phrasing 5 | any phrasing |
|---|---|---|---|---|---|---|
| bear_objection_answered | 35% (7/20) | 50% (10/20) | 40% (8/20) | 35% (7/20) | 45% (9/20) | 90% (18/20) |
| catalyst_in_horizon | 20% (4/20) | 25% (5/20) | 25% (5/20) | 15% (3/20) | 5% (1/20) | 50% (10/20) |
| terminal_vulnerability | 5% (1/20) | 5% (1/20) | 0% (0/20) | 5% (1/20) | 5% (1/20) | 15% (3/20) |
| event_risk_wait | 15% (3/20) | 15% (3/20) | 10% (2/20) | 15% (3/20) | 20% (4/20) | 35% (7/20) |
| thesis_material_directional | 40% (8/20) | 45% (9/20) | 15% (3/20) | 40% (8/20) | 10% (2/20) | 70% (14/20) |
| trade_proposed | 5% (1/20) | 5% (1/20) | 35% (7/20) | 5% (1/20) | 5% (1/20) | 40% (8/20) |

## Input tests with known answers (WP-22 3.3)

Each perturbed transcript is graded once on the on-prem grader and judged against its expectation. `n` counts Rooms where the perturbation applied and both grades parsed.

| test | expectation | n | pass rate | failing Rooms |
|---|---|---|---|---|
| Control: original regraded | all six answers unchanged (grader noise floor) | 20 | 90% (18/20) | BAC-r4-rep2, MA-r3-rep1 |
| Planted fatal flaw | terminal_vulnerability = yes and rule PASS at R1-R5 | 20 | 100% (20/20) | none |
| Bear evidence removed | rule outcome not more cautious than the original | 20 | 95% (19/20) | SEDG-r5-rep2 |
| Bear numbers strengthened (x2) | P(yes) on bear_objection_answered does not rise (+0.01 tolerance) and rule not less cautious | 20 | 95% (19/20) | MA-r2-rep1 |
| Turns reordered (seed 22) | all six answers unchanged | 20 | 50% (10/20) | BAC-r2-rep2, BAC-r4-rep2, MA-r1-rep1, MA-r4-rep1, SEDG-r1-rep2, SEDG-r2-rep2, SEDG-r3-rep2, SEDG-r5-rep2, WFC-r3-rep1, WFC-r5-rep1 |
| Ticker and company renamed | all six answers unchanged | 20 | 50% (10/20) | BAC-r1-rep2, BAC-r4-rep2, BAC-r5-rep2, MA-r1-rep1, MA-r2-rep1, MA-r3-rep1, MA-r5-rep1, SEDG-r4-rep2, SEDG-r5-rep2, WFC-r3-rep1 |

Per-Room detail (P = pass, F = fail, - = not applicable):

| Room | original rule outcome | Control: original regraded | Planted fatal flaw | Bear evidence removed | Bear numbers strengthened (x2) | Turns reordered (seed 22) | Ticker and company renamed |
|---|---|---|---|---|---|---|---|
| BAC-r1-rep2 | PASS | P | P | P | P | P | F |
| BAC-r2-rep2 | PASS | P | P | P | P | F | P |
| BAC-r3-rep2 | PASS | P | P | P | P | P | P |
| BAC-r4-rep2 | PASS | F | P | P | P | F | F |
| BAC-r5-rep2 | APPROVE | P | P | P | P | P | F |
| MA-r1-rep1 | PASS | P | P | P | P | F | F |
| MA-r2-rep1 | PASS | P | P | P | F | P | F |
| MA-r3-rep1 | PASS | F | P | P | P | P | F |
| MA-r4-rep1 | PASS | P | P | P | P | F | P |
| MA-r5-rep1 | APPROVE | P | P | P | P | P | F |
| SEDG-r1-rep2 | PASS | P | P | P | P | F | P |
| SEDG-r2-rep2 | PASS | P | P | P | P | F | P |
| SEDG-r3-rep2 | PASS | P | P | P | P | F | P |
| SEDG-r4-rep2 | PASS | P | P | P | P | P | F |
| SEDG-r5-rep2 | APPROVE | P | P | F | P | F | F |
| WFC-r1-rep1 | PASS | P | P | P | P | P | P |
| WFC-r2-rep1 | PASS | P | P | P | P | P | P |
| WFC-r3-rep1 | PASS | P | P | P | P | F | F |
| WFC-r4-rep1 | PASS | P | P | P | P | P | P |
| WFC-r5-rep1 | PASS | P | P | P | P | F | P |

Failures, with the measured values:

| test | Room | what happened |
|---|---|---|
| Control: original regraded | BAC-r4-rep2 | changed: bear_objection_answered,trade_proposed; max |dconf| 0.00; rule PASS -> PASS |
| Control: original regraded | MA-r3-rep1 | changed: thesis_material_directional; max |dconf| 0.00; rule PASS -> APPROVE |
| Bear evidence removed | SEDG-r5-rep2 | APPROVE -> PASS |
| Bear numbers strengthened (x2) | MA-r2-rep1 | P(yes) 0.00 -> 1.00; PASS -> PASS |
| Turns reordered (seed 22) | BAC-r2-rep2 | changed: terminal_vulnerability; max |dconf| 0.00; rule PASS -> PASS |
| Turns reordered (seed 22) | BAC-r4-rep2 | changed: bear_objection_answered,catalyst_in_horizon; max |dconf| 0.00; rule PASS -> PASS |
| Turns reordered (seed 22) | MA-r1-rep1 | changed: bear_objection_answered; max |dconf| 0.00; rule PASS -> PASS |
| Turns reordered (seed 22) | MA-r4-rep1 | changed: bear_objection_answered,catalyst_in_horizon; max |dconf| 0.00; rule PASS -> PASS |
| Turns reordered (seed 22) | SEDG-r1-rep2 | changed: bear_objection_answered,thesis_material_directional; max |dconf| 0.00; rule PASS -> PASS |
| Turns reordered (seed 22) | SEDG-r2-rep2 | changed: bear_objection_answered; max |dconf| 0.00; rule PASS -> PASS |
| Turns reordered (seed 22) | SEDG-r3-rep2 | changed: event_risk_wait; max |dconf| 0.00; rule PASS -> PASS |
| Turns reordered (seed 22) | SEDG-r5-rep2 | changed: event_risk_wait; max |dconf| 0.00; rule APPROVE -> APPROVE |
| Turns reordered (seed 22) | WFC-r3-rep1 | changed: trade_proposed; max |dconf| 0.00; rule PASS -> PASS |
| Turns reordered (seed 22) | WFC-r5-rep1 | changed: bear_objection_answered; max |dconf| 0.00; rule PASS -> PASS |
| Ticker and company renamed | BAC-r1-rep2 | changed: thesis_material_directional,trade_proposed; max |dconf| 0.00; rule PASS -> PASS |
| Ticker and company renamed | BAC-r4-rep2 | changed: catalyst_in_horizon; max |dconf| 0.00; rule PASS -> PASS |
| Ticker and company renamed | BAC-r5-rep2 | changed: terminal_vulnerability; max |dconf| 0.00; rule APPROVE -> PASS |
| Ticker and company renamed | MA-r1-rep1 | changed: catalyst_in_horizon,event_risk_wait; max |dconf| 0.00; rule PASS -> PASS |
| Ticker and company renamed | MA-r2-rep1 | changed: catalyst_in_horizon; max |dconf| 0.00; rule PASS -> PASS |
| Ticker and company renamed | MA-r3-rep1 | changed: event_risk_wait; max |dconf| 0.00; rule PASS -> PASS |
| Ticker and company renamed | MA-r5-rep1 | changed: bear_objection_answered; max |dconf| 0.00; rule APPROVE -> APPROVE |
| Ticker and company renamed | SEDG-r4-rep2 | changed: bear_objection_answered; max |dconf| 0.00; rule PASS -> PASS |
| Ticker and company renamed | SEDG-r5-rep2 | changed: bear_objection_answered,event_risk_wait; max |dconf| 0.00; rule APPROVE -> APPROVE |
| Ticker and company renamed | WFC-r3-rep1 | changed: terminal_vulnerability; max |dconf| 0.00; rule PASS -> PASS |

Rule outcome transitions, original -> perturbed (Room's own risk level):

| perturbation | transitions |
|---|---|
| Planted fatal flaw | APPROVE -> PASS x3; PASS -> PASS x17 |
| Bear evidence removed | APPROVE -> APPROVE x2; APPROVE -> PASS x1; PASS -> APPROVE x1; PASS -> PASS x16 |
| Bear numbers strengthened (x2) | APPROVE -> APPROVE x3; PASS -> PASS x17 |
| Turns reordered (seed 22) | APPROVE -> APPROVE x3; PASS -> PASS x17 |
| Ticker and company renamed | APPROVE -> APPROVE x2; APPROVE -> PASS x1; PASS -> PASS x17 |

Bear numbers strengthened: mean change in P(yes) on bear_objection_answered -0.150 (min -1.000, max +1.000, n=20); numbers scaled per Room: 8, 7, 9, 12, 5, 7, 3, 14, 11, 13, 8, 5, 11, 11, 10, 4, 11, 6, 4, 17.

Ticker rename: Rooms where the ticker string is still present after rename: none; Rooms with no company name found: none.

Perturbation builders (all in code): planted flaw = fixed terminal-risk paragraph appended to the last `bear_researcher` turn; bear removed = every `bear_researcher` turn replaced by one number-free line (later Bear turns dropped); strengthened = every number attached to %, x or $ (optional K/M/B/T, million, billion) inside a sentence containing a downside or leverage keyword multiplied by 2, decimals kept; reordered = non-CIO turns shuffled with `random.Random(22)`; renamed = the ticker and the `ticker_reference` company name (listing name and name without Inc/Corp/Common Stock suffixes) replaced by `TICKR` / `Company X` in every turn and in the header.


Not computed here: rank correlation of a decision score with the consensus score (the grader emits yes/no answers, not a score); the code and Jev graders.

