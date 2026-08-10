# CR164 model-cutoff probe — 2026-08-10

Model `ami-llm` at `http://192.168.20.74:8000`. 210 probes over 35 months × 6 anchors, temperature 0.

**Price-collapse month: 2024-08** · baseline event recall 100% · last recalled boundary event: **2025-01**

**window_start (first Friday ≥ max(collapse, last event) + 8w): 2025-02-28**

| Event | truth | answered | correct |
|---|---|---|---|
| svb_collapse (baseline) | 2023-03 | 2023-03 | ✓ |
| btc_etf (baseline) | 2024-01 | 2024-01 | ✓ |
| nvda_split (baseline) | 2024-06 | 2024-06 | ✓ |
| crowdstrike (baseline) | 2024-07 | 2024-07 | ✓ |
| fed_sep24_cut (boundary) | 2024-09 | UNKNOWN | ✗ |
| us_election_winner (boundary) | 2024-11 | 2024-11 | ✓ |
| fed_dec24_cut (boundary) | 2024-12 | UNKNOWN | ✗ |
| deepseek_r1 (boundary) | 2025-01 | 2025-01 | ✓ |
| liberation_day (boundary) | 2025-04 | UNKNOWN | ✗ |
| circle_ipo (boundary) | 2025-06 | UNKNOWN | ✗ |
| figma_ipo (boundary) | 2025-07 | UNKNOWN | ✗ |

| Month | median rel err | refusal rate | failing |
|---|---|---|---|
| 2023-09 | 2.7% | 0% |  |
| 2023-10 | 10.4% | 0% | YES |
| 2023-11 | 0.2% | 0% |  |
| 2023-12 | 0.2% | 0% |  |
| 2024-01 | 2.4% | 0% |  |
| 2024-02 | 1.7% | 17% |  |
| 2024-03 | 1.2% | 0% |  |
| 2024-04 | 12.9% | 17% | YES |
| 2024-05 | 4.2% | 17% |  |
| 2024-06 | 1.5% | 50% | YES |
| 2024-07 | 3.1% | 33% |  |
| 2024-08 | 0.7% | 67% | YES |
| 2024-09 | 2.1% | 83% | YES |
| 2024-10 | — | 100% | YES |
| 2024-11 | — | 100% | YES |
| 2024-12 | — | 100% | YES |
| 2025-01 | — | 100% | YES |
| 2025-02 | — | 100% | YES |
| 2025-03 | — | 100% | YES |
| 2025-04 | — | 100% | YES |
| 2025-05 | — | 100% | YES |
| 2025-06 | — | 100% | YES |
| 2025-07 | — | 100% | YES |
| 2025-08 | — | 100% | YES |
| 2025-09 | — | 100% | YES |
| 2025-10 | — | 100% | YES |
| 2025-11 | — | 100% | YES |
| 2025-12 | — | 100% | YES |
| 2026-01 | — | 100% | YES |
| 2026-02 | — | 100% | YES |
| 2026-03 | — | 100% | YES |
| 2026-04 | — | 100% | YES |
| 2026-05 | — | 100% | YES |
| 2026-06 | — | 100% | YES |
| 2026-07 | — | 100% | YES |
