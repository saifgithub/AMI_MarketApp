# WP-22 step 3 — grader scoring (Jev jev-1.13.0)

Model root: `Jev jev-1.13.0` (end `Jev jev-1.13.0`); question set `q1`; image `alpha-2026-11-21-6` `c3db07e5`; concurrency 1.

Rooms scored: **300**, errors: **0** (errors are excluded from every table below and listed at the end). CIO numbers are on the same Rooms.

## Cost, latency, control

| measure | value |
|---|---|
| latency per Room, mean / median / p95 / max (s) | 0.3 / 0.3 / 0.3 / 0.7 |
| Rooms where token probabilities came back for every question | n/a |
| cost per Room (USD, priced from LLM_PRICES_JSON) | 0.00034 (n=300) |
| calls per Room (mean) | 0.0 |
| unparsed yes/no replies (total) | 0 |

## Answer distribution per question

| question | n | yes | no | not computable | close | mean confidence |
|---|---|---|---|---|---|---|
| bear_objection_answered | 300 | 62% (185/300) | 38% (115/300) | 0% (0/300) | 68% (205/300) | 0.67 |
| catalyst_in_horizon | 300 | 98% (293/300) | 2% (7/300) | 0% (0/300) | 3% (9/300) | 0.96 |
| terminal_vulnerability | 300 | 46% (137/300) | 54% (163/300) | 0% (0/300) | 31% (93/300) | 0.79 |
| event_risk_wait | 300 | 67% (201/300) | 33% (99/300) | 0% (0/300) | 16% (49/300) | 0.89 |
| thesis_material_directional | 300 | 5% (14/300) | 95% (286/300) | 0% (0/300) | 14% (42/300) | 0.86 |
| trade_proposed | 300 | 100% (300/300) | 0% (0/300) | 0% (0/300) | 0% (0/300) | 0.96 |

Yes share by risk level:

| question | R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|---|
| bear_objection_answered | 52% (31/60) | 62% (37/60) | 60% (36/60) | 73% (44/60) | 62% (37/60) |
| catalyst_in_horizon | 97% (58/60) | 98% (59/60) | 98% (59/60) | 98% (59/60) | 97% (58/60) |
| terminal_vulnerability | 47% (28/60) | 47% (28/60) | 43% (26/60) | 40% (24/60) | 52% (31/60) |
| event_risk_wait | 72% (43/60) | 68% (41/60) | 62% (37/60) | 72% (43/60) | 62% (37/60) |
| thesis_material_directional | 10% (6/60) | 2% (1/60) | 8% (5/60) | 2% (1/60) | 2% (1/60) |
| trade_proposed | 100% (60/60) | 100% (60/60) | 100% (60/60) | 100% (60/60) | 100% (60/60) |

## Decision-rule outcomes (default policy, rule r1)

| risk | n | grader APPROVE | PASS | CONTESTED | UNAVAILABLE | CIO APPROVE | CIO not-APPROVE |
|---|---|---|---|---|---|---|---|
| R1 | 60 | 0 | 59 | 1 | 0 | 3 | 57 |
| R2 | 60 | 0 | 58 | 2 | 0 | 3 | 57 |
| R3 | 60 | 0 | 56 | 4 | 0 | 10 | 50 |
| R4 | 60 | 0 | 55 | 5 | 0 | 13 | 47 |
| R5 | 60 | 20 | 20 | 20 | 0 | 20 | 40 |
| all | 300 | 20 | 248 | 32 | 0 | 49 | 251 |

Grader outcome against the CIO's action, same Rooms:

|  | grader APPROVE | grader PASS | grader CONTESTED | grader UNAVAILABLE |
|---|---|---|---|---|
| CIO APPROVE | 9 | 29 | 11 | 0 |
| CIO not APPROVE | 11 | 219 | 21 | 0 |

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
| grader | R1 | 60 | 0 | 0 | n/a | n/a | 0 | 1 |
| grader | R2 | 60 | 0 | 0 | n/a | n/a | 0 | 2 |
| grader | R3 | 60 | 0 | 0 | n/a | n/a | 0 | 4 |
| grader | R4 | 60 | 0 | 0 | n/a | n/a | 0 | 5 |
| grader | R5 | 60 | 20 | 0 | 89% (16/18) | 11% (2/18) | 2 | 20 |
| grader | all | 300 | 20 | 0 | 89% (16/18) | 11% (2/18) | 2 | 32 |

## Fresh-room stability (two reps of the same ticker and risk level)

Pairs where both reps were answered; `not_computable` pairs are dropped. CIO and rule rows compare APPROVE against anything else.

| measure | reps disagree |
|---|---|
| bear_objection_answered | 50% (75/150) |
| catalyst_in_horizon | 5% (7/150) |
| terminal_vulnerability | 22% (33/150) |
| event_risk_wait | 38% (57/150) |
| thesis_material_directional | 8% (12/150) |
| trade_proposed | 0% (0/150) |
| rule outcome APPROVE vs not (grader) | 3% (4/150) |
| CIO action APPROVE vs not (same Rooms) | 23% (35/150) |

## Wording test (five phrasings, share of answers that change vs phrasing 0)

Sample: 20 Rooms. Each cell: answers that differ from the base wording.

| question | phrasing 1 | phrasing 2 | phrasing 3 | phrasing 4 | phrasing 5 | any phrasing |
|---|---|---|---|---|---|---|
| bear_objection_answered | 50% (10/20) | 55% (11/20) | 60% (12/20) | 25% (5/20) | 45% (9/20) | 85% (17/20) |
| catalyst_in_horizon | 5% (1/20) | 5% (1/20) | 15% (3/20) | 0% (0/20) | 5% (1/20) | 20% (4/20) |
| terminal_vulnerability | 15% (3/20) | 0% (0/20) | 25% (5/20) | 5% (1/20) | 15% (3/20) | 40% (8/20) |
| event_risk_wait | 15% (3/20) | 25% (5/20) | 5% (1/20) | 5% (1/20) | 15% (3/20) | 35% (7/20) |
| thesis_material_directional | 20% (4/20) | 15% (3/20) | 20% (4/20) | 5% (1/20) | 20% (4/20) | 40% (8/20) |
| trade_proposed | 0% (0/20) | 0% (0/20) | 65% (13/20) | 5% (1/20) | 0% (0/20) | 65% (13/20) |

## Input tests with known answers (WP-22 3.3)

Each perturbed transcript is graded once on the on-prem grader and judged against its expectation. `n` counts Rooms where the perturbation applied and both grades parsed.

| test | expectation | n | pass rate | failing Rooms |
|---|---|---|---|---|
| Control: original regraded | all six answers unchanged (grader noise floor) | 20 | 85% (17/20) | SEDG-r3-rep2, SEDG-r5-rep2, WFC-r2-rep1 |
| Planted fatal flaw | terminal_vulnerability = yes and rule PASS at R1-R5 | 20 | 100% (20/20) | none |
| Bear evidence removed | rule outcome not more cautious than the original | 20 | 100% (20/20) | none |
| Bear numbers strengthened (x2) | P(yes) on bear_objection_answered does not rise (+0.01 tolerance) and rule not less cautious | 20 | 70% (14/20) | BAC-r4-rep2, MA-r1-rep1, SEDG-r5-rep2, WFC-r1-rep1, WFC-r3-rep1, WFC-r5-rep1 |
| Turns reordered (seed 22) | all six answers unchanged | 20 | 50% (10/20) | BAC-r3-rep2, BAC-r5-rep2, MA-r1-rep1, SEDG-r1-rep2, SEDG-r2-rep2, SEDG-r3-rep2, SEDG-r4-rep2, SEDG-r5-rep2, WFC-r2-rep1, WFC-r5-rep1 |
| Ticker and company renamed | all six answers unchanged | 20 | 80% (16/20) | BAC-r1-rep2, SEDG-r3-rep2, SEDG-r4-rep2, WFC-r5-rep1 |

Per-Room detail (P = pass, F = fail, - = not applicable):

| Room | original rule outcome | Control: original regraded | Planted fatal flaw | Bear evidence removed | Bear numbers strengthened (x2) | Turns reordered (seed 22) | Ticker and company renamed |
|---|---|---|---|---|---|---|---|
| BAC-r1-rep2 | PASS | P | P | P | P | P | F |
| BAC-r2-rep2 | PASS | P | P | P | P | P | P |
| BAC-r3-rep2 | PASS | P | P | P | P | F | P |
| BAC-r4-rep2 | PASS | P | P | P | F | P | P |
| BAC-r5-rep2 | CONTESTED | P | P | P | P | F | P |
| MA-r1-rep1 | PASS | P | P | P | F | F | P |
| MA-r2-rep1 | PASS | P | P | P | P | P | P |
| MA-r3-rep1 | PASS | P | P | P | P | P | P |
| MA-r4-rep1 | PASS | P | P | P | P | P | P |
| MA-r5-rep1 | APPROVE | P | P | P | P | P | P |
| SEDG-r1-rep2 | PASS | P | P | P | P | F | P |
| SEDG-r2-rep2 | PASS | P | P | P | P | F | P |
| SEDG-r3-rep2 | PASS | F | P | P | P | F | F |
| SEDG-r4-rep2 | PASS | P | P | P | P | F | F |
| SEDG-r5-rep2 | CONTESTED | F | P | P | F | F | P |
| WFC-r1-rep1 | PASS | P | P | P | F | P | P |
| WFC-r2-rep1 | PASS | F | P | P | P | F | P |
| WFC-r3-rep1 | PASS | P | P | P | F | P | P |
| WFC-r4-rep1 | PASS | P | P | P | P | P | P |
| WFC-r5-rep1 | PASS | P | P | P | F | F | F |

Failures, with the measured values:

| test | Room | what happened |
|---|---|---|
| Control: original regraded | SEDG-r3-rep2 | changed: event_risk_wait; max |dconf| 0.02; rule PASS -> PASS |
| Control: original regraded | SEDG-r5-rep2 | changed: event_risk_wait; max |dconf| 0.03; rule CONTESTED -> CONTESTED |
| Control: original regraded | WFC-r2-rep1 | changed: bear_objection_answered; max |dconf| 0.03; rule PASS -> PASS |
| Bear numbers strengthened (x2) | BAC-r4-rep2 | P(yes) 0.68 -> 0.74; PASS -> PASS |
| Bear numbers strengthened (x2) | MA-r1-rep1 | P(yes) 0.30 -> 0.36; PASS -> PASS |
| Bear numbers strengthened (x2) | SEDG-r5-rep2 | P(yes) 0.66 -> 0.68; CONTESTED -> CONTESTED |
| Bear numbers strengthened (x2) | WFC-r1-rep1 | P(yes) 0.36 -> 0.49; PASS -> PASS |
| Bear numbers strengthened (x2) | WFC-r3-rep1 | P(yes) 0.45 -> 0.55; PASS -> PASS |
| Bear numbers strengthened (x2) | WFC-r5-rep1 | P(yes) 0.30 -> 0.48; PASS -> PASS |
| Turns reordered (seed 22) | BAC-r3-rep2 | changed: bear_objection_answered; max |dconf| 0.12; rule PASS -> PASS |
| Turns reordered (seed 22) | BAC-r5-rep2 | changed: bear_objection_answered; max |dconf| 0.12; rule CONTESTED -> PASS |
| Turns reordered (seed 22) | MA-r1-rep1 | changed: bear_objection_answered; max |dconf| 0.10; rule PASS -> PASS |
| Turns reordered (seed 22) | SEDG-r1-rep2 | changed: thesis_material_directional; max |dconf| 0.12; rule PASS -> PASS |
| Turns reordered (seed 22) | SEDG-r2-rep2 | changed: bear_objection_answered; max |dconf| 0.16; rule PASS -> PASS |
| Turns reordered (seed 22) | SEDG-r3-rep2 | changed: bear_objection_answered; max |dconf| 0.18; rule PASS -> PASS |
| Turns reordered (seed 22) | SEDG-r4-rep2 | changed: catalyst_in_horizon; max |dconf| 0.10; rule PASS -> PASS |
| Turns reordered (seed 22) | SEDG-r5-rep2 | changed: terminal_vulnerability,event_risk_wait; max |dconf| 0.15; rule CONTESTED -> CONTESTED |
| Turns reordered (seed 22) | WFC-r2-rep1 | changed: bear_objection_answered; max |dconf| 0.26; rule PASS -> PASS |
| Turns reordered (seed 22) | WFC-r5-rep1 | changed: event_risk_wait; max |dconf| 0.14; rule PASS -> PASS |
| Ticker and company renamed | BAC-r1-rep2 | changed: terminal_vulnerability; max |dconf| 0.06; rule PASS -> PASS |
| Ticker and company renamed | SEDG-r3-rep2 | changed: event_risk_wait; max |dconf| 0.02; rule PASS -> PASS |
| Ticker and company renamed | SEDG-r4-rep2 | changed: catalyst_in_horizon; max |dconf| 0.04; rule PASS -> PASS |
| Ticker and company renamed | WFC-r5-rep1 | changed: event_risk_wait; max |dconf| 0.10; rule PASS -> PASS |

Rule outcome transitions, original -> perturbed (Room's own risk level):

| perturbation | transitions |
|---|---|
| Planted fatal flaw | APPROVE -> PASS x1; CONTESTED -> PASS x2; PASS -> PASS x17 |
| Bear evidence removed | APPROVE -> APPROVE x1; CONTESTED -> APPROVE x1; CONTESTED -> CONTESTED x1; PASS -> CONTESTED x3; PASS -> PASS x14 |
| Bear numbers strengthened (x2) | APPROVE -> APPROVE x1; CONTESTED -> CONTESTED x2; PASS -> PASS x17 |
| Turns reordered (seed 22) | APPROVE -> APPROVE x1; CONTESTED -> CONTESTED x1; CONTESTED -> PASS x1; PASS -> PASS x17 |
| Ticker and company renamed | APPROVE -> APPROVE x1; CONTESTED -> CONTESTED x1; CONTESTED -> PASS x1; PASS -> PASS x17 |

Bear numbers strengthened: mean change in P(yes) on bear_objection_answered -0.002 (min -0.130, max +0.180, n=20); numbers scaled per Room: 8, 7, 9, 12, 5, 7, 3, 14, 11, 13, 8, 5, 11, 11, 10, 4, 11, 6, 4, 17.

Ticker rename: Rooms where the ticker string is still present after rename: none; Rooms with no company name found: none.

Perturbation builders (all in code): planted flaw = fixed terminal-risk paragraph appended to the last `bear_researcher` turn; bear removed = every `bear_researcher` turn replaced by one number-free line (later Bear turns dropped); strengthened = every number attached to %, x or $ (optional K/M/B/T, million, billion) inside a sentence containing a downside or leverage keyword multiplied by 2, decimals kept; reordered = non-CIO turns shuffled with `random.Random(22)`; renamed = the ticker and the `ticker_reference` company name (listing name and name without Inc/Corp/Common Stock suffixes) replaced by `TICKR` / `Company X` in every turn and in the header.


Not computed here: rank correlation of a decision score with the consensus score (the grader emits yes/no answers, not a score); the code and Jev graders.

