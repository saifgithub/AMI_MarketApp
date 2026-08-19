# CR197 — what the Risk Debators actually carry

Deterministic read of 118 committed convenes (2026-08-13, 2026-08-14, 2026-08-14b), no LLM involved. Every figure is reproducible by re-running `scripts/debate_signal_report.py`.

**Sample:** 118 convenes over 13 distinct tickers (ANET×10, AMD×9, AVGO×9, BAC×9, GRAB×9, KTOS×9…). Clustered, not independent.

## 1. Stance: is the position a judgement or a costume?

| agent | for | against | neutral | H(stance) bits | max 1.58 |
|---|---|---|---|---|---|
| aggressive_debator | 117 | 1 | 0 | **0.071** | |
| conservative_debator | 1 | 117 | 0 | **0.071** | |
| neutral_debator | 36 | 55 | 27 | **1.523** | |
| bull_researcher | 117 | 1 | 0 | **0.071** | |
| bear_researcher | 0 | 118 | 0 | **0.000** | |
| trader | 28 | 81 | 9 | **1.148** | |
| research_manager | 25 | 80 | 10 | **1.149** | |

A stance channel at ~0 bits is a constant: the role decided it before the ticker was known. That is the literal form of *"taking the two extremes and letting it fall in between"*.

## 2. Distinct debate outcomes across every convene

| (aggressive, conservative, neutral) | n |
|---|---|
| ('for', 'against', 'against') | 55 |
| ('for', 'against', 'for') | 34 |
| ('for', 'against', 'neutral') | 27 |
| ('for', 'for', 'for') | 1 |
| ('against', 'against', 'for') | 1 |

**5 distinct triples over 118 convenes.** If the extremes never move, the debate's whole stance output is the Neutral's one vote.

## 3. Conviction: the channel that is free to vary

| agent | low | medium | high | H bits |
|---|---|---|---|---|
| aggressive_debator | 0 | 21 | 97 | **0.676** |
| conservative_debator | 3 | 29 | 85 | **0.969** |
| neutral_debator | 5 | 90 | 23 | **0.951** |

## 4. Mutual information with the PM's action

| channel | I(channel; verdict) bits |
|---|---|
| trader.stance | 0.3606 |
| research_manager.stance | 0.3382 |
| neutral_debator.stance | 0.2334 |
| research_manager.conviction | 0.0568 |
| neutral_debator.conviction | 0.0532 |
| trader.conviction | 0.0530 |
| conservative_debator.conviction | 0.0522 |
| conservative_debator.stance | 0.0321 |
| aggressive_debator.conviction | 0.0300 |
| bull_researcher.conviction | 0.0236 |
| bear_researcher.conviction | 0.0115 |
| aggressive_debator.stance | 0.0024 |
| bull_researcher.stance | 0.0024 |
| bear_researcher.stance | 0.0000 |

Plug-in MI is upward-biased at this sample size, so a channel near zero is the safe reading and a small positive value may be bias. The ordering is what to read, not the absolute values.

## 5. Do they at least SAY different things?

| pair | mean Jaccard over cited numbers |
|---|---|
| aggressive vs conservative | 0.233 |
| aggressive vs neutral | 0.315 |
| conservative vs neutral | 0.346 |

Low overlap means the three turns are genuinely different arguments, not restatements — the prompts ARE doing work at the prose layer even where the stance layer is fixed.

## 6. Engagement: who answers whom

| speaker | names Aggressive | names Conservative | names Neutral | n |
|---|---|---|---|---|
| aggressive_debator | — | 22 (19%) | 6 (5%) | 118 |
| conservative_debator | 39 (33%) | — | 4 (3%) | 118 |
| neutral_debator | 116 (98%) | 115 (97%) | — | 118 |

The Aggressive speaks FIRST in a single sequential pass, so any reference it makes to the Conservative is anticipatory — it cannot have read one. Its prompt asks it to pre-empt, which is the honest instruction for that seat; the Conservative's ask to engage is the one with a real transcript behind it.

## 7. What the stance triple predicts

| (aggressive, conservative, neutral) | n | PM action |
|---|---|---|
| ('for', 'against', 'against') | 55 | PASS 55 |
| ('for', 'against', 'for') | 34 | PASS 18, REJECT 10, APPROVE 6 |
| ('for', 'against', 'neutral') | 27 | PASS 23, APPROVE 2, REJECT 2 |
| ('for', 'for', 'for') | 1 | APPROVE 1 |
| ('against', 'against', 'for') | 1 | PASS 1 |

**The Neutral alone, against the verdict:**

| neutral stance | PM action |
|---|---|
| against | PASS 55 |
| for | PASS 19, REJECT 10, APPROVE 7 |
| neutral | PASS 23, APPROVE 2, REJECT 2 |

This is the finding that cuts against a quick 'the debate is theatre' verdict, and it cuts both ways. Because the two extremes never move, the entire stance output of the RISK phase reduces to the Neutral's single call — and that call is strongly associated with the outcome (a `neutral: against` turn is followed by a PASS in every case observed here).

**But association is not influence, and the direction is genuinely ambiguous.** The Neutral speaks immediately before the PM and reads the same eleven turns the PM reads, so a shared upstream cause explains this pattern exactly as well as persuasion does. The Trader's stance scores comparably (MI 0.36, higher than the Neutral's 0.23) while merely *preceding* the decision. Nothing here can separate the two, which is precisely why the replay ablation exists: it holds the eleven upstream turns fixed and removes only the debate text.
