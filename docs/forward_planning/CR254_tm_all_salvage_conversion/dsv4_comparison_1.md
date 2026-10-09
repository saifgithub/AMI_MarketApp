# CR254 — DSV4 comparison #1: tm-all vs production at R5 (2026-10-09)

First head-to-head under the new-mission protocol, on DeepSeek-V4-Flash
(alpha-spark:8003). Production arm: the parallel agent's DSV4 matrix
(`~/cr251_v2_dsv4/r5`, production prompts, reviews disabled, 60/60 clean).
tm-all arm: `out/cr254-tmall-r5/` (wholesale teammate suite, 60/60 clean).
Same tickers (CR228 30), same mandate (R5), same model, same day-window.

## DSV4 production curve (their full matrix)

| Risk | APPROVE |
|---|---|
| R1 | 5/60 (8%) |
| R2 | 11/60 (18%) |
| R3 | 22/60 (37%) |
| R4 | 27/60 (45%) |
| **R5** | **17/60 (28%)** |

Rises R1→R4 cleanly, **breaks at R5** (45→28). DSV4's curve is not monotone
at the top — a real model-dependent behavior, worth its own analysis once
the Jev pass lands on their arms.

## R5 head-to-head

| | tm-all | production |
|---|---|---|
| APPROVE | 20/60 (33%) | 17/60 (28%) |
| Per-ticker divergence | higher on 8, lower on 5, tie 17 | |
| APPROVE size | mean 3.5% (1.5–5.0) | mean 4.8% (3.5–5.0) |
| Trade horizons | 60/120/180/200/270/365d | mandate-driven |

**Contract health (tm-all, 60 rooms): zero** PM-unparseable, missing-stance,
envelope-displaced, NO_VERDICT. The constitution's strict-JSON demands did
NOT break the envelope on DSV4 (third model; envelope survival now
qwen38/GLM/DSV4 = 3/3). CR249 fired 7 geometry repairs (10 implausible
detections) — the repair gate is doing live work on tm-all's trader too.

## The D2 refusal, reconfirmed on a third model

tm-all's approved trades carry horizons of 60–365d against an R5 mandate —
the hardcoded constitution horizon still overrides mandates on DSV4.
Conversion (mandate-referenced horizon, CR254 spec §1) remains a
precondition for any tm-all element touching trade params.

## Read

On DSV4, wholesale tm-all is **contract-viable** (cleanest cross-provider
showing yet) and slightly more permissive than production with a third of
tickers diverging — but it still overrides mandates on horizon, and its
size distribution argues wider (1.5–5.0 vs production's tight 3.5–5.0 at
R5). Net: not adoptable wholesale (D2 stands); per-element salvage gains
evidence — the personas' *analysis* content moves stances (13/30 tickers),
their *constitutional overrides* are the poison. Next conversions per the
CR254 queue: mandate-referenced horizon, then TIER-vocabulary.
