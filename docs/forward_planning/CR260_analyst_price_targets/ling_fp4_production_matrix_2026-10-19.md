# Ling-3.0-flash-Fin-fp4 × production prompts — FINAL, 2026-10-19

**Arm:** CR262 (`cr262-ling-prod-r1..r5`), 300/300 rooms, 30 CR251 tickers ×
risk 1–5 × 2 reps. `backend-default` prompts — the production state at
`alpha-2026-10-18-2` (disposition ladder folded in). Thinking explicitly OFF
(`enable_thinking: false`; Ling's server defaults ON, the CR259 amendment
makes production config stick). Omega-spark :8004, conc 5, request 900s /
agent 600s. Gate: AAPL/BA @R5 PASS/PASS, ~6 min, zero fallbacks.

## Results

| | R1 | R2 | R3 | R4 | R5 | target |
|---|---|---|---|---|---|---|
| APPROVE | 4/60 (7%) | 11/60 (18%) | 19/60 (32%) | 29/60 (48%) | 27/60 (45%) | 5/15/30/45/46 |
| flips | 4/30 (13%) | 5/30 (17%) | 7/30 (23%) | 12/30 (40%) | 7/30 (23%) | — |

Room time: mean 9.1 / median 8.8 / max 20.3 min. Scripted fallbacks: 1
(timeout-touched rooms ≈ negligible).

## Fleet comparison (all at production/disposition prompt state)

| model | thinking | R1–R5 curve | flips R1–R5 | min/room |
|---|---|---|---|---|
| **Ling-fp4** | off | **4/11/19/29/27** | 13/17/23/40/23% | **9.1** |
| kolibri-on (arm 13) | on | 0/0/12/17/18 | 10% avg | 53.7 |
| kolibri-off × disp | off | 3/1/9/17/14 | 10/3/33/37/27% | 10.9 |
| ami × disposition | off | 0/0/3/22/36 | 0/0/10/37/27% | ~50 |
| dsv4 × disposition | off | 1/7/13/15/19 | — | — |
| ami × disposition (arm 15, in flight) | **on** | 0/0/0/0/2 (33 rms) | TBD | 84 (intrinsic) |

## Reads

1. **Best discrimination curve measured at production prompts.** Strictly
   monotone R1→R4 (7→18→32→48%), closest-to-target shape of any arm
   (4/11/19/29/27 vs 5/15/30/45/46); the R5 dip (48→45, 2 rooms) is noise,
   not dsv4's inversion class. ami-disposition jumps late (0/0/3/22/36);
   dsv4-disposition flattens (…15/19). Ling is the first model whose
   willingness ladder actually tracks the disposition instructions.
2. **Fastest model in the fleet: 9.1 min/room** — 6× ami, equal to
   kolibri-off, at 5-way concurrency.
3. **Stability mid-pack:** 13–23% flips at R1–R3/R5 (better than
   ami-disposition's R4–R5 37%, worse than kolibri-on's 10%). R4's 40%
   is the weak cell — worth a per-ticker look before acceptance.
4. **The finance training shows up as calibration, not knowledge**: with
   the same fact sheet feeding every model, Ling's edge is the willingness
   ladder tracking risk appetite — exactly what a purpose-trained finance
   model should be good at.
5. Open questions before any production candidacy: (a) R4 flip root-cause;
   (b) Ling thinking-on arm (does it get kolibri-on's stability at
   acceptable latency? Ling reasoning on the probe was modest, 381 tokens);
   (c) license/commercial terms confirmed MIT per HF card.

Data: `docs/tools/room_investigation_V2/out/ling-prod/` ·
melehost logs `/tmp/ling_prod_r{1..5}.log`.
