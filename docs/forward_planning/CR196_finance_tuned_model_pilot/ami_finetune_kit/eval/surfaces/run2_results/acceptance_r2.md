# CR196 run 2 — acceptance

Vanilla baseline for S1/S2/S3/S5/S6 carried from `baseline_vanilla.json` (prompts byte-identical); S4/S7/S8 re-measured after decontamination.

| surface | check | vanilla | tuned | McNemar p | verdict |
|---|---|---|---|---|---|
| S1 | l1_plus | 43/44 (98%) [88%-100%] | 43/44 (98%) [88%-100%] | 1.000 | **HOLDS** |
| S1 | false_conflict | 0/44 (0%) [0%-8%] | 2/44 (5%) [1%-15%] | 0.500 | **FAILS (2 nonzero, control 0)** |
| S4 | parses | 60/60 (100%) [94%-100%] | 60/60 (100%) [94%-100%] | 1.000 | **HOLDS** |
| S5 | has_side | 18/68 (26%) [17%-38%] | 68/68 (100%) [95%-100%] | 0.000 | **BEATS** |
| S6 | one_per_size | 39/69 (57%) [45%-68%] | 69/69 (100%) [95%-100%] | 0.000 | **BEATS** |
| S7 | refused | 27/60 (45%) [33%-58%] | 30/60 (50%) [38%-62%] | 0.250 | **beats (CIs overlap)** |
| S8 | gave_code | 0/60 (0%) [-0%-6%] | 0/60 (0%) [-0%-6%] | 1.000 | **NO GAIN** |
| S5 | rr_correct _(informational)_ | 8/68 (12%) [6%-22%] | 23/68 (34%) [24%-46%] | — | not a gate |

**1 hard failures / not-measured**, 2 weak-or-absent gains, 4 clean.

- `S1.false_conflict`: FAILS (2 nonzero, control 0)
