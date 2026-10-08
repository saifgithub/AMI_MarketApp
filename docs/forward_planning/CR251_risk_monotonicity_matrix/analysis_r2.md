# CR251 risk-matrix analysis

APPROVE counts per ticker across risk levels 1–5 (n=2 reps each):

| Ticker | R1 | R2 | R3 | R4 | R5 | Monotone | Avg Jev score |
|---|---|---|---|---|---|---|---|
| AAPL | 0 | 0 | 1 | 2 | 2 | ✓ | 0.69 |
| APD | 0 | 0 | 1 | 0 | 0 | ✗ | 0.77 |
| BA | 0 | 0 | 0 | 0 | 0 | ✓ | 0.69 |
| BAC | 0 | 0 | 0 | 1 | 1 | ✓ | 0.72 |
| BGS | 0 | 0 | 0 | 0 | 0 | ✓ | 0.76 |
| CAG | 0 | 0 | 0 | 0 | 2 | ✓ | 0.78 |
| DE | 0 | 0 | 0 | 1 | 1 | ✓ | 0.78 |
| DHR | 0 | 0 | 0 | 1 | 1 | ✓ | 0.78 |
| FCEL | 0 | 0 | 0 | 0 | 1 | ✓ | 0.80 |
| JPM | 0 | 1 | 0 | 0 | 1 | ✗ | 0.68 |
| LEVI | 0 | 1 | 0 | 1 | 0 | ✗ | 0.87 |
| MA | 0 | 1 | 0 | 2 | 2 | ✗ | 0.65 |
| MO | 0 | 0 | 1 | 1 | 2 | ✓ | 0.68 |
| NKE | 0 | 0 | 1 | 1 | 0 | ✗ | 0.69 |
| PLD | 0 | 0 | 0 | 2 | 1 | ✗ | 0.72 |
| PYPL | 0 | 0 | 0 | 2 | 1 | ✗ | 0.80 |
| RIOT | 0 | 0 | 0 | 0 | 0 | ✓ | 0.81 |
| RIVN | 0 | 0 | 0 | 0 | 0 | ✓ | 0.74 |
| SEDG | 0 | 0 | 0 | 1 | 0 | ✗ | 0.83 |
| SLB | 0 | 0 | 0 | 1 | 1 | ✓ | 0.77 |
| SNAP | 0 | 0 | 0 | 1 | 2 | ✓ | 0.75 |
| SO | 0 | 0 | 0 | 0 | 2 | ✓ | 0.75 |
| SPCE | 0 | 0 | 0 | 0 | 0 | ✓ | 0.75 |
| T | 0 | 0 | 0 | 2 | 2 | ✓ | 0.78 |
| TMO | 0 | 0 | 0 | 2 | 1 | ✗ | 0.69 |
| V | 0 | 0 | 0 | 2 | 2 | ✓ | 0.73 |
| WFC | 0 | 0 | 0 | 0 | 1 | ✓ | 0.74 |
| WU | 0 | 0 | 0 | 0 | 0 | ✓ | 0.78 |
| XPEV | 0 | 0 | 0 | 0 | 0 | ✓ | 0.75 |
| XRX | 0 | 0 | 0 | 1 | 0 | ✗ | 0.73 |

## Pooled APPROVE counts (of 60 convenes per level)

| Risk | APPROVE |
|---|---|
| R1 | 0 |
| R2 | 3 |
| R3 | 4 |
| R4 | 24 |
| R5 | 26 |

Pooled monotonic: YES

## Discrimination — room evidence score, APPROVE vs PASS

| Risk | APPROVE rooms (n, mean) | PASS rooms (n, mean) | Δ |
|---|---|---|---|
| R2 | 6, 0.68 | 54, 0.76 | -0.07 |
| R3 | 8, 0.74 | 52, 0.75 | -0.01 |
| R4 | 34, 0.74 | 26, 0.74 | -0.01 |
| R5 | 36, 0.71 | 24, 0.74 | -0.03 |

## Risk-bar curve (min evidence score among APPROVEs)

| Risk | min support of an approving room |
|---|---|
| R1 | — |
| R2 | 0.5909090909090909 |
| R3 | 0.6363636363636364 |
| R4 | 0.5454545454545454 |
| R5 | 0.5555555555555556 |

## Stability across the 2 repeats

- comparable cells: 131
- verdict flips: 26 (20%)
- Jev room-score flips (>0.10): 41 (31%)

## Monotonicity violations — decomposition

- **APD** counts [0, 0, 1, 0, 0] → **decision-limited (support present, verdict curve still breaks)**
- **JPM** counts [0, 1, 0, 0, 1] → **decision-limited (support present, verdict curve still breaks)**
- **LEVI** counts [0, 1, 0, 1, 0] → **decision-limited (support present, verdict curve still breaks)**
- **MA** counts [0, 1, 0, 2, 2] → **decision-limited (support present, verdict curve still breaks)**
- **NKE** counts [0, 0, 1, 1, 0] → **decision-limited (support present, verdict curve still breaks)**
- **PLD** counts [0, 0, 0, 2, 1] → **decision-limited (support present, verdict curve still breaks)**
- **PYPL** counts [0, 0, 0, 2, 1] → **decision-limited (support present, verdict curve still breaks)**
- **SEDG** counts [0, 0, 0, 1, 0] → **decision-limited (support present, verdict curve still breaks)**
- **TMO** counts [0, 0, 0, 2, 1] → **decision-limited (support present, verdict curve still breaks)**
- **XRX** counts [0, 0, 0, 1, 0] → **decision-limited (support present, verdict curve still breaks)**

## Per-desk mean support score (all levels)

| Agent | mean support | n |
|---|---|---|
| aggressive_debator | 0.49 | 291 |
| neutral_debator | 0.57 | 259 |
| bull_researcher | 0.62 | 286 |
| bear_researcher | 0.74 | 294 |
| conservative_debator | 0.74 | 282 |
| news_analyst | 0.77 | 267 |
| social_media_analyst | 0.78 | 264 |
| fundamentals_analyst | 0.79 | 273 |
| research_manager | 0.90 | 294 |
| market_analyst | 0.90 | 270 |
| trader | 0.92 | 295 |
