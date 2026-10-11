# CR251 — analysis_r6: four-arm overlay (production/disposition × dsv4/ami-llm)

**Status:** companion to the frozen series. The ami-llm R2/R5 levels are being
re-run (contamination, below) — this doc's ami numbers for those levels are
PROVISIONAL.

## Arm curves (APPROVE per 60 rooms)

| Arm | R1 | R2 | R3 | R4 | R5 | Monotone |
|---|---|---|---|---|---|---|
| CR255 target | 5 | 15 | 30 | 45 | 60 | ✓ |
| dsv4 production (arm 1) | 5 | 11 | 22 | 27 | 17 | ✗ (R5 inverts) |
| **dsv4 disposition (arm 9)** | 1 | 7 | 13 | 15 | 19 | **✓** |
| ami-llm clean (arm 10) | 0 | 0* | 4 | 10 | 2* | ✗ (R4→R5 drop) |

\* R2/R5 provisional — contaminated (see below).

## Per-arm quality metrics

| Metric | dsv4 production | dsv4 disposition | ami-llm (valid levels) |
|---|---|---|---|
| Verdict flips | 17% | 21% | ~10% (caveated) |
| Discrimination Δ (all levels) | −0.06…−0.13 | −0.03…−0.13 | TBD post-fix |
| Net-support threshold lift | +0 pts | +0–2 pts | TBD post-fix |
| Sub-cap spontaneous rate | 2.6% (2/78) | — | — |

## Findings

1. **The disposition table fixes the curve SHAPE, nothing else.** First
   monotone curve of the program (1/7/13/15/19). Discrimination stays negative
   (Δ −0.03…−0.13), threshold lift ≈ 0, flip rate slightly worse (21%). This
   is exactly the prior-calibration vs evidence-channel split from analysis_r5:
   prose moves the prior, structure must carry the evidence weighting.

2. **The R5 inversion is stack-level, not provider-specific.** The ami-llm
   control arm shows the same R4→R5 collapse (10→2, provisional). Combined
   with the cap-ladder evidence (analysis_r4), the size-worthiness coupling is
   a property of the room's current prompts/data-lanes, present on both
   models. It is the disease CR253/255 target.

3. **Every arm sits far below the target curve.** Best willingness is 19/60
   (disposition, R5) vs target 60/60. Either the target is aspirational
   (fit the bar as a slope toward it over iterations) or the universe's
   uninvestable tail (≈11 names) makes 100% at R5 unattainable by construction
   — the target needs a floor-adjusted reading (e.g. % of investable universe).

4. **ami-llm flips less than dsv4** (~10% vs 17–21%) — preliminary, since the
   contaminated levels could be artificially stable (degraded rooms agreeing
   on PASS). Confirm on the fix arm.

5. **Contamination record:** the DGX hard-died ~19:43 UTC 2026-10-11 during
   the ami matrix's R5 (644 + 1433 'connection attempts failed'; R2 rooms
   averaged 2.5 min). Host shows the pre-collapse memory signature again
   (117/121GB used, no cap — Saiful declined the cap for now, re-run accepted
   as the risk). Fix arm: ~/cr251_v2_fix (R5→R2, ETA ~5h).

## Recommendations

1. **Disposition fold-in: now supported on TWO grounds** (monotone curve +
   willingness calibration), still gated on (a) ami-llm disposition twin and
   (b) the CR253 acceptance benchmark. Ship with C7, not before.
2. **Target curve needs the investable-universe adjustment** — Saiful
   decision: keep 5/15/30/45/60 as aspirational slope, or re-anchor as
   percentages of ~19 investable names (e.g. R5 ≈ 38/60)?
3. **Composite evidence bar (C7) is the only remaining lever for
   discrimination** — every prompt-level mechanism has now been measured and
   none moves it. Prioritize the C7 build.
4. **DGX memory cap remains the top infrastructure risk** — third death
   observed. Cap + watchdog before any production fold-in depends on ami-llm
   uptime.
