# CR199 — what the Bull and Bear Researchers actually carry

Deterministic read of **136 committed convenes** (2026-08-07, 2026-08-13, 2026-08-14, 2026-08-14b), no LLM involved, every agent joined to its own verbatim recorded prompt (0 convene(s) dropped for an ambiguous join). 13 distinct tickers (AMDx11, GRABx11, NVDAx11, ANETx11, KTOSx11, SNDKx11...). Clustered, not independent. Reproduce with `scripts/researcher_signal_report.py`.

## 1. Stance: judgement or costume?

| agent | for | against | neutral | none | H(stance) bits |
|---|---|---|---|---|---|
| bull_researcher | 135 | 1 | 0 | 0 | **0.063** |
| bear_researcher | 0 | 136 | 0 | 0 | **0.000** |
| research_manager | 28 | 90 | 15 | 3 | **1.210** |
| trader | 31 | 95 | 10 | 0 | **1.125** |

## 2. Conviction: the channel that is free to vary

| agent | low | medium | high | none | H bits |
|---|---|---|---|---|---|
| bull_researcher | 1 | 62 | 73 | 0 | **1.051** |
| bear_researcher | 0 | 39 | 97 | 0 | **0.865** |
| research_manager | 3 | 91 | 39 | 3 | **1.017** |

## 3. Mutual information with the decision

Two targets: the PM's OWN action parsed from its reply, and the shipped `verdict.action` (which the safety floor can overwrite).

| channel | I(.;PM reply) | I(.;shipped verdict) |
|---|---|---|
| trader.stance | 0.3599 | 0.3870 |
| research_manager.stance | 0.3217 | 0.3673 |
| trader.conviction | 0.0378 | 0.0470 |
| research_manager.conviction | 0.0225 | 0.0440 |
| bear_researcher.conviction | 0.0141 | 0.0121 |
| bull_researcher.conviction | 0.0096 | 0.0162 |
| bull_researcher.stance | 0.0020 | 0.0021 |
| bear_researcher.stance | 0.0000 | 0.0000 |

## 4. Do the researchers DERIVE numbers, or re-cite them?

Each agent's own recorded prompt carries the fact sheet plus every prior turn. A cited number absent from that prompt was minted by the agent — arithmetic, or invention.

| agent | mean numbers cited | mean minted (absent from own prompt) | minted share |
|---|---|---|---|
| bull_researcher | 14.3 | 0.8 | 6% |
| bear_researcher | 16.6 | 2.0 | 12% |
| research_manager | 13.8 | 0.5 | 4% |
| trader | 9.3 | 1.6 | 17% |

## 5. Provenance: numbers that reach a reader ONLY through a researcher

For each reader, of the numbers it cites, how many appear in a researcher's turn **and nowhere else in that reader's own prompt** (fact sheet, analyst turns, everything). Those are quantities the researchers introduced into the decision.

| reader | mean numbers cited | via Bull only | via Bear only | via either | share via researchers |
|---|---|---|---|---|---|
| research_manager | 13.8 | 0.07 | 0.46 | 0.60 | 4.4% |
| trader | 9.4 | 0.00 | 0.08 | 0.08 | 0.9% |
| portfolio_manager | 8.2 | 0.02 | 0.00 | 0.02 | 0.2% |

## 6. Attribution: who names whom

| reader | names 'Bull' | names 'Bear' | names both | n |
|---|---|---|---|---|
| bear_researcher | 62 (46%) | 28 (21%) | 21 (15%) | 136 |
| research_manager | 122 (90%) | 121 (89%) | 117 (86%) | 136 |
| trader | 17 (12%) | 20 (15%) | 8 (6%) | 136 |
| aggressive_debator | 12 (9%) | 44 (32%) | 4 (3%) | 136 |
| conservative_debator | 3 (2%) | 28 (21%) | 2 (1%) | 136 |
| neutral_debator | 46 (34%) | 50 (37%) | 40 (29%) | 136 |
| portfolio_manager | 26 (23%) | 29 (26%) | 18 (16%) | 113 |

The Bear speaks immediately after the Bull and is the only voice with a live opportunity to rebut it inside the same phase.

## 7. Do Bull and Bear say different things?

| pair | mean Jaccard over cited numbers |
|---|---|
| bull vs bear | 0.331 |
| bull vs research | 0.409 |
| bear vs research | 0.449 |

## 8. Researcher conviction vs the PM's own action


**bull_researcher**

| conviction | APPROVE | PASS | n |
|---|---|---|---|
| high | 15 | 57 | 72 |
| low | 0 | 1 | 1 |
| medium | 8 | 53 | 61 |

**bear_researcher**

| conviction | APPROVE | PASS | n |
|---|---|---|---|
| high | 13 | 82 | 95 |
| medium | 10 | 29 | 39 |

