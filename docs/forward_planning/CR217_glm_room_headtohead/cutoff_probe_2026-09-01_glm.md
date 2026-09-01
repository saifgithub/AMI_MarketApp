# CR164 model-cutoff probe — 2026-09-01

Model `LibertAIDAI/GLM-5.3-Flash-NVFP4` (server reports `/models/GLM-5.3-Flash-NVFP4`) at `http://100.94.223.38:8008`. 210 probes over 35 months × 6 anchors, temperature 0.

**Price-collapse month: 2025-05** · baseline event recall 100% · last recalled boundary event: **2025-06**

**window_start (first Friday ≥ max(collapse, last event) + 8w): 2025-08-01**

| Event | truth | answered | correct |
|---|---|---|---|
| svb_collapse (baseline) | 2023-03 | 2023-03 | ✓ |
| btc_etf (baseline) | 2024-01 | 2024-01 | ✓ |
| nvda_split (baseline) | 2024-06 | 2024-06 | ✓ |
| crowdstrike (baseline) | 2024-07 | 2024-07 | ✓ |
| fed_sep24_cut (boundary) | 2024-09 | 2024-09 | ✓ |
| us_election_winner (boundary) | 2024-11 | 2016-11 | ✗ |
| fed_dec24_cut (boundary) | 2024-12 | 2024-12 | ✓ |
| deepseek_r1 (boundary) | 2025-01 | 2025-01 | ✓ |
| liberation_day (boundary) | 2025-04 | 2025-04 | ✓ |
| circle_ipo (boundary) | 2025-06 | 2025-06 | ✓ |
| figma_ipo (boundary) | 2025-07 | UNKNOWN | ✗ |

| Month | median rel err | refusal rate | failing |
|---|---|---|---|
| 2023-09 | 0.9% | 0% |  |
| 2023-10 | 0.2% | 0% |  |
| 2023-11 | 0.0% | 0% |  |
| 2023-12 | 0.0% | 0% |  |
| 2024-01 | 1.3% | 0% |  |
| 2024-02 | 1.9% | 0% |  |
| 2024-03 | 0.1% | 0% |  |
| 2024-04 | 2.9% | 17% |  |
| 2024-05 | 0.1% | 0% |  |
| 2024-06 | 0.0% | 0% |  |
| 2024-07 | 6.4% | 0% |  |
| 2024-08 | 0.4% | 0% |  |
| 2024-09 | 0.6% | 0% |  |
| 2024-10 | 2.3% | 0% |  |
| 2024-11 | 1.6% | 0% |  |
| 2024-12 | 0.0% | 0% |  |
| 2025-01 | 1.8% | 0% |  |
| 2025-02 | 3.1% | 0% |  |
| 2025-03 | 1.1% | 33% |  |
| 2025-04 | 1.0% | 17% |  |
| 2025-05 | 0.0% | 83% | YES |
| 2025-06 | — | 100% | YES |
| 2025-07 | 22.9% | 83% | YES |
| 2025-08 | — | 100% | YES |
| 2025-09 | — | 100% | YES |
| 2025-10 | — | 100% | YES |
| 2025-11 | — | 100% | YES |
| 2025-12 | 6.2% | 83% | YES |
| 2026-01 | 5.1% | 83% | YES |
| 2026-02 | 5.2% | 83% | YES |
| 2026-03 | 0.1% | 83% | YES |
| 2026-04 | 14.6% | 83% | YES |
| 2026-05 | 10.6% | 67% | YES |
| 2026-06 | — | 100% | YES |
| 2026-07 | 9.0% | 83% | YES |
