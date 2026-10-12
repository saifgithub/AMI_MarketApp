# analysis_r7 — CR254 converted-tm-all matrix on DSV4 (30×5×2, 300 rooms)

Lane spec: EXPERIMENT_LOG.md §2/§4. Arm 11. Variant `cr254-tmall`
(production personas + mandate-compliant converted teammate frameworks;
conversion rules: horizon mandate-referenced, sizing vocabulary mapped to
the computed cap, JSON subordinate to the STANCE envelope, SCS floats
dropped, constitution supremacy deleted). Ran in-container on melehost
2026-10-11/12; Jev-scored Mac-side (2,400 prose turns; debator turns absent
from Jev logs as in other DSV4 arms). Raw: `~/cr254_tmall_matrix/r{1..5}`,
local mirror `out/cr254-tmall-matrix/`.

## Curve (with arms 1, 9 and the CR255 target)

| Risk | prod (arm 1) | disposition (arm 9) | **converted tm-all** | target |
|---|---|---|---|---|
| R1 | 5 (8%) | 1 (2%) | **4 (7%)** | 5 (8%) |
| R2 | 11 (18%) | 7 (12%) | **6 (10%)** | 15 (25%) |
| R3 | 22 (37%) | 13 (22%) | **15 (25%)** | 30 (50%) |
| R4 | 27 (45%) | 15 (25%) | **16 (27%)** | 45 (75%) |
| R5 | 17 (28%) | 19 (32%) | **17 (28%)** | 60 (100%) |

**Monotone: YES — 4/6/15/16/17, strictly non-decreasing, zero non-PASS/PASS
verdicts in 300 rooms.** First arm of the program with a fully clean,
monotone curve. Disposition is also monotone but lower; production inverts
at R5. Contract completion: 300/300 decided.

## Discrimination (net_support, per §2.10 — raw room-mean anti-correlates)

- pooled Pearson r = **+0.074** (arm 1: +0.19). Weaker than production.
- Best threshold lift over always-PASS: **+1 pt** pooled (R5 +3). No
  usable threshold, same conclusion as arm 1: evidence support does not
  drive verdicts in either suite.

## Stability

Repeat flips: **40/150 cells = 27%** — worse than arm 1 (17%) and arm 2
(21%). The converted frameworks argue harder (mandatory rebuttals, named
catalysts, counter-proposals) and harder arguments flip more across draws.
Honest negative: the conversion buys curve shape at the cost of per-draw
stability.

## Conversion acceptance audit

- **Sizing: PASS, strongly.** APPROVE sizes rise monotonically with the
  risk level — R1 mean 1.0% (1.0–1.0), R2 1.8, R3 2.4, R4 3.9, R5 4.1
  (0.5–5.0). The vocabulary-mapped-to-cap conversion produces exactly the
  risk-scaled sizing the TIER ontology was trying to get — without ever
  exceeding the computed cap (max 5.0).
- **Horizon: FAIL (model-caused).** Approved trades still carry mixed
  horizons (R5: h30/45/90/180/365; h90 — the mandate value — present but
  not exclusive). The mandate-referenced conversion text is correct; DSV4
  simply does not comply with numeric mandate parameters (same leak seen in
  production prompts on this model). **Conclusion: numeric mandate params
  need deterministic enforcement at assembly (AMI rewrites trade-param
  horizon := mandate horizon), not prompt text. Prompt-level conversion has
  now failed on both suites — this is a code fix, overdue.**
- **Envelope/contract: PASS.** Zero MISSING_STANCE / displaced-envelope /
  PM-unparseable findings across 300 rooms under the strictest output
  demands in any arm.

## Per-desk support (Jev)

Weakest: fundamentals 0.46, bull 0.48. Strongest: social 0.89, market 0.86,
trader 0.73, bear 0.71. The converted research triangle argues thinly by
Jev's read — the frameworks demand more (explicit rebuttals, named
catalysts, adjudication verdicts) and Jev scores those turns as
partially-supported more often. RM 0.69 mid-pack.

## Read for the production question

1. **The conversion works as designed where prompts can work:** sizing
   became risk-scaled and cap-disciplined; the curve became monotone; the
   contract held under the strictest demands. The teammate analysis layer
   is adoptable in mandate-compliant form.
2. **Its character is disciplined-and-conservative** (~28% ceiling at R5)
   — it will not generate willingness toward the CR255 target. Neither will
   disposition. The target curve requires the C7 decision-score lever
   (already the program's locked next build), not more prompt work.
3. **Stability regressed (27%)** — the stronger argumentation frameworks
   amplify draw variance. If adopted, expect the PM's 5-draw self-consistency
   to absorb more of it; flag for the C7 design.
4. **Deterministic mandate enforcement is now measured-necessary** on DSV4
   (horizon leak is model behavior, present in both suites). Recommend a
   small room_runner change: rewrite trade-param horizon := mandate horizon
   with an audit note, same family as the CR249 geometry gate.

**Recommendation:** adopt the converted frameworks into production (the
salvage wins: monotone curve, risk-scaled sizing, dissent-audit discipline),
paired with (a) the deterministic horizon enforcement and (b) stability
work in C7. Wholesale tm-all remains rejected; its converted form is the
best-measured prompt suite in the program.
