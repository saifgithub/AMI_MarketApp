# CR251 risk-matrix analysis

APPROVE counts per ticker across risk levels 1–5 (n=2 reps each):

| Ticker | R1 | R2 | R3 | R4 | R5 | Monotone | Avg Jev score |
|---|---|---|---|---|---|---|---|
| AAPL | 0 | 0 | 1 | 2 | 2 | ✓ | 0.69 |
| APD | 0 | 0 | 1 | 0 | 0 | ✗ | 0.77 |
| BA | 0 | 0 | 0 | 0 | 0 | ✓ | 0.72 |
| BAC | 0 | 0 | 0 | 1 | 1 | ✓ | 0.72 |
| BGS | 0 | 0 | 0 | 0 | 0 | ✓ | 0.77 |
| CAG | 0 | 0 | 0 | 0 | 2 | ✓ | 0.77 |
| DE | 0 | 0 | 0 | 1 | 1 | ✓ | 0.76 |
| DHR | 0 | 0 | 0 | 1 | 1 | ✓ | 0.81 |
| FCEL | 0 | 0 | 0 | 0 | 1 | ✓ | 0.82 |
| JPM | 0 | 1 | 1 | 2 | 1 | ✗ | 0.65 |
| LEVI | 0 | 1 | 2 | 1 | 0 | ✗ | 0.86 |
| MA | 0 | 1 | 2 | 2 | 2 | ✓ | 0.64 |
| MO | 0 | 0 | 1 | 1 | 2 | ✓ | 0.68 |
| NKE | 0 | 0 | 1 | 1 | 0 | ✗ | 0.68 |
| PLD | 0 | 0 | 0 | 2 | 1 | ✗ | 0.73 |
| PYPL | 0 | 0 | 0 | 2 | 1 | ✗ | 0.81 |
| RIOT | 0 | 0 | 0 | 0 | 0 | ✓ | 0.79 |
| RIVN | 0 | 0 | 0 | 0 | 0 | ✓ | 0.74 |
| SEDG | 0 | 0 | 0 | 1 | 0 | ✗ | 0.80 |
| SLB | 0 | 0 | 0 | 1 | 1 | ✓ | 0.77 |
| SNAP | 0 | 0 | 0 | 1 | 2 | ✓ | 0.74 |
| SO | 0 | 0 | 0 | 0 | 2 | ✓ | 0.75 |
| SPCE | 0 | 0 | 0 | 0 | 0 | ✓ | 0.74 |
| T | 0 | 0 | 0 | 2 | 2 | ✓ | 0.78 |
| TMO | 0 | 0 | 0 | 2 | 1 | ✗ | 0.75 |
| V | 0 | 0 | 0 | 2 | 2 | ✓ | 0.73 |
| WFC | 0 | 0 | 0 | 0 | 1 | ✓ | 0.75 |
| WU | 0 | 0 | 0 | 0 | 0 | ✓ | 0.77 |
| XPEV | 0 | 0 | 0 | 0 | 0 | ✓ | 0.76 |
| XRX | 0 | 0 | 0 | 1 | 0 | ✗ | 0.76 |

## Pooled APPROVE counts (of 60 convenes per level)

| Risk | APPROVE |
|---|---|
| R1 | 0 |
| R2 | 3 |
| R3 | 9 |
| R4 | 26 |
| R5 | 26 |

Pooled monotonic: YES

## Discrimination — room evidence score, APPROVE vs PASS

| Risk | APPROVE rooms (n, mean) | PASS rooms (n, mean) | Δ |
|---|---|---|---|
| R2 | 6, 0.69 | 54, 0.75 | -0.06 |
| R3 | 14, 0.72 | 46, 0.77 | -0.04 |
| R4 | 36, 0.74 | 24, 0.76 | -0.02 |
| R5 | 36, 0.71 | 24, 0.74 | -0.03 |

## Risk-bar curve (min evidence score among APPROVEs)

| Risk | min support of an approving room |
|---|---|
| R1 | — |
| R2 | 0.6363636363636364 |
| R3 | 0.5909090909090909 |
| R4 | 0.5454545454545454 |
| R5 | 0.5555555555555556 |

## Stability across the 2 repeats

- comparable cells: 150
- verdict flips: 29 (19%)
- Jev room-score flips (>0.10): 52 (35%)

## Monotonicity violations — decomposition

- **APD** counts [0, 0, 1, 0, 0] → **decision-limited (support present, verdict curve still breaks)**
- **JPM** counts [0, 1, 1, 2, 1] → **decision-limited (support present, verdict curve still breaks)**
- **LEVI** counts [0, 1, 2, 1, 0] → **decision-limited (support present, verdict curve still breaks)**
- **NKE** counts [0, 0, 1, 1, 0] → **decision-limited (support present, verdict curve still breaks)**
- **PLD** counts [0, 0, 0, 2, 1] → **decision-limited (support present, verdict curve still breaks)**
- **PYPL** counts [0, 0, 0, 2, 1] → **decision-limited (support present, verdict curve still breaks)**
- **SEDG** counts [0, 0, 0, 1, 0] → **decision-limited (support present, verdict curve still breaks)**
- **TMO** counts [0, 0, 0, 2, 1] → **decision-limited (support present, verdict curve still breaks)**
- **XRX** counts [0, 0, 0, 1, 0] → **decision-limited (support present, verdict curve still breaks)**

## Per-desk mean support score (all levels)

| Agent | mean support | n |
|---|---|---|
| aggressive_debator | 0.50 | 286 |
| neutral_debator | 0.58 | 265 |
| bull_researcher | 0.60 | 283 |
| conservative_debator | 0.73 | 280 |
| bear_researcher | 0.74 | 289 |
| news_analyst | 0.77 | 271 |
| fundamentals_analyst | 0.80 | 276 |
| social_media_analyst | 0.80 | 272 |
| research_manager | 0.90 | 289 |
| market_analyst | 0.90 | 274 |
| trader | 0.92 | 293 |
