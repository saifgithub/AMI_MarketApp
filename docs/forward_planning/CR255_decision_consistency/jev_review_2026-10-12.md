# CR255 — Jev evidence-score review (track K audit, 2026-10-12)

Independent review of the Jev judge's output quality and the Jev↔verdict numbers
that anchor the C7 evidence-bar design. Read-only on all run data; tools re-run
from `docs/tools/room_investigation_V2/` with the backend venv. Frozen r1/r2
baselines and BASELINE.md untouched.

Scope: arms 1 (cr251-v2-dsv4), 9 (cr253-disp-matrix), 10+fix (cr251-v2-ami,
cr251-v2-ami-fix). 20-turn judge-accuracy sample, full tool reproduction, and a
6-room read of the disposition-arm R5 llm_audit trail (3 APPROVE, 3 PASS).

## 1. Judge accuracy (20-turn stratified sample)

Method: 20 scored turns across all four arms, risk levels R1–R5, and all desks
(bull / bear / technical-neutral), each read against the full fact sheet in its
prompt. Every cited figure was checked against the sheet; every thesis checked
for sheet support.

1. **Point estimate: 0 clear errors in 20 turns; ~3 borderline (adjacent-category)
   calls. Error rate ≤10%, best estimate ~5%, all adjacent-grade** (well vs
   partially). No unsupported/well flip was observed anywhere in the sample.
2. **The judge catches real agent errors.** CAG-rep1 R1 bear said "price at
   $12.81" when the close was $13.57 (level confused with current price) — judge
   returned partially_supported with figures_consistent 0.64. The ami BAC-rep2 R4
   bear treated the 24.9% implied cost of debt as a live number (a known
   cross-basis artifact the sheet itself flags) — judge returned
   partially_supported, conviction_justified 1.53 (weak). Both correct.
3. **No desk bias found.** Bear desks got well_supported in 4/6 bear turns read
   (BA×2, APD×2 — every figure verified correct); the two partials were
   earned. Bull desks were refused well_supported three times (SEDG, DE,
   NKE-fix) precisely when the re-rating thesis outran the sheet — with
   conviction_justified scored weak (0.97–1.43). If anything the judge is
   slightly *skeptical of bull theses*, the opposite of a leniency pattern.
4. **Mild leniency on technical-desk interpretation.** market_analyst/trader
   turns passed well_supported while using interpretive verbs the sheet cannot
   carry ("volume 2.08× confirms institutional distribution", "no capitulation").
   Numbers were always right; the interpretive layer went unpenalized. Low
   materiality for room means (1 of 8 turns), but a known ceiling of the rubric.
5. **Auxiliary scores are noisier than the headline choice.** figures_consistent
   noul read 0.46–0.65 on several turns where every cited figure checked out
   (BA-rep2 R3, MO R2, MA R5). The choice label (what the metrics consume) is
   reliable; the noul sub-scores should not be used as thresholds.

## 2. Systematic bias / score compression

1. **Compression is structural, not a judge defect.** Room means take only
   10–11 discrete values (8 turns/room → 1/16 steps): in dsv4 production, 70
   rooms sit at 0.750 and 59 at 0.812. There is no continuous signal to
   threshold — this is the measured half of the known tie problem.
2. **Net support is quantized at ±1/3 by construction.** The Jev logs carry only
   `bear_researcher` on the bear side (debator turns are absent), so
   net = mean(3 bull desks) − single bear score moves in ~0.33 steps. In dsv4
   production the modal net values are −0.167 (82 rooms) and +0.167 (47);
   +0.333 ties 40 rooms. A per-level threshold at net=+0.33 is slicing a
   three-valued variable — the single-metric bar was correctly declared dead
   (analysis_r4), and this is the mechanical reason.
3. **Direction-agnosticism confirmed at the turn level.** In APD-rep2 R5 the
   bull AND the bear turns both scored well_supported (both are sheet-grounded).
   Grounding cannot discriminate between sides of the same debate — the
   strongest first-principles confirmation in this review that a composite,
   direction-aware bar (C7) is the right shape.

## 3. Jev↔verdict reproduction (tools re-run)

| Arm | Reported | Reproduced | Verdict |
|---|---|---|---|
| dsv4 production net r | +0.19 | **+0.186** (pooled n=300) | Confirmed |
| dsv4 production lift | +0 pts | +1 pt pooled; **+10 pts at R3 and R4 per-level** | Confirmed with a caveat (below) |
| dsv4 disposition net r | — | +0.103 (n=299) | New number, consistent with "no discrimination" |
| dsv4 disposition lift | ~0 | +0 pts pooled, ≤+2 pts any level | Confirmed |
| ami clean net r | +0.03 | +0.043 (fix arm alone), +0.068 (5-level combine, R3 partial), +0.085 (R4+R5 clean) | **Challenged (exact value)** |
| ami clean lift | 0 | +0 pts | Confirmed |

1. **Production r=+0.19 confirmed exactly.** Per-level decomposition is more
   informative than the pooled figure: R2 +0.327, R3 +0.324, R4 +0.232, but
   R1 +0.022 and R5 +0.003. Net support carries real signal at mid levels and
   none at the tails — and the tails are where an R1/R5 bar operates.
2. **The pooled "lift +0" understates mid-level lift.** dsv4 production R3/R4
   thresholds beat always-PASS by +10 pts each. Pooled reporting hides this;
   it does not rescue the single-metric bar (a threshold fit at mid levels
   still does nothing at R1/R5), but analysis write-ups should quote per-level
   lift, not pooled.
3. **ami r=+0.03 not exactly reproducible.** Every clean join lands at
   +0.04…+0.09 depending on whether the partial-coverage R3 (83%) is included.
   Direction and conclusion (no usable discrimination) are confirmed; the exact
   figure in analysis_r6 looks provisional. Recommend the r6 table carry
   "+0.04…+0.09 (join-dependent)" rather than a point value.
4. Δ (APPROVE − PASS room mean) per level reproduced as reported for both dsv4
   arms (−0.06…−0.13 production; −0.03…−0.13 disposition). Decile tables confirm
   approvals are drawn from the *lower* score mass in both arms.

## 4. Six-room llm_audit read (disposition arm, R5)

Full per-turn response trail read from alpha `llm_audit` for: APPROVE = APD-rep2,
PYPL-rep1, XPEV-rep2; PASS = APD-rep1, DE-rep1, RIOT-rep1.

1. **Verdicts follow the debate in 5/6 rooms.** APD-rep1, DE-rep1, RIOT-rep1
   PASS with the full desk against (in DE even the bull_researcher argued
   against entry); PYPL-rep1 and APD-rep2 APPROVE with the desk split but
   risk-side seats (RM/trader/risk officer) leaning in. PM narrations cite the
   actual debate numbers, not generic prose.
2. **PM engagement with the losing side is real and quotable.** RIOT-rep1 PM
   explicitly weighed the bull's 26:1 asymmetry and rejected it on the mandate
   fit ("a squeeze narrative… not the durable compounding this mandate
   requires"). DE-rep1 PM adopted the RM's "wait for compression" conclusion.
   XPEV-rep2 PM named the bear's revision argument as "the strongest
   counterargument" and still approved on asymmetry.
3. **APD-rep2 APPROVE violates the target-curve holdout rule.** The CR255
   target doc states APD/BA-shaped names (grounded bear case, negative
   SBC-adjusted FCF) must PASS at every level including R5. APD-rep2 has
   −$350M SBC-adjusted FCF and was APPROVED at 5.0%. The approval rests on the
   "net-margin distortion is one-time" inference — which the sheet does not
   state and the bear explicitly flagged as unestablished. This is a concrete
   R5 escape of exactly the thesis-aware gate the holdout rule exists to test.
4. **The APD-rep1 / APD-rep2 flip is desk-phase variance, not data variance.**
   Identical fact sheet; rep1's fundamentals analyst and RM went against,
   rep2's went neutral/for, and the PM majority flipped with them. Same-input
   verdict instability (the 21% flip rate) is visible inside one ticker pair.
5. **Nothing in the transcripts contradicts the Jev scores; the contradiction
   is the design.** RIOT-rep1's turns are genuinely well-grounded (high Jev
   room score) and the verdict is PASS — the over-refusal failure shape (158
   high-support PASSes in production) is a *verdict-layer* behavior on
   well-evidenced transcripts, not judge noise. The judge measures what it
   measures honestly; it measures the wrong thing for the bar.
6. **Incidental findings.** (a) One PM candidate narration (APD-rep2) contained
   degenerate text ("Traffic analogy: green light… (Build a squirrel trap,)");
   the recorded verdict used a clean candidate — the multi-sample PM selection
   filtered it, but mid-tier sampling garbage exists in the audit trail.
   (b) XPEV-rep2's approval leans on the $18.46 consensus target as a
   destination after the bear showed that target is a lagging artifact of
   projections that missed by ~69% twice — the weakest reasoning chain of the
   six, defensible only under the R5 "any defensible thesis" reading.

## 5. Recommendation: is the Jev score trustworthy enough to anchor C7?

**Yes, with three structural changes — trust the judge, do not trust the
aggregate.**

1. **Judge quality is sufficient for an anchor component.** ~5% adjacent-grade
   error, no direction bias, catches real agent errors including subtle ones
   (basis-artifact cost of debt, level/price confusion). Continue spot-audits
   at ~20 turns per arm; no recalibration needed now.
2. **Do not use the room-mean or net-support scalar as the bar.** Quantization
   (1/16 room steps, ±1/3 net steps from the single-bear construction) makes
   single thresholds meaningless at the tails, and direction-agnostic grounding
   cannot separate bull from bear on the same fact sheet. This review's data
   says the same thing as analysis_r4/r6 from one level deeper.
3. **C7 composite should consume Jev at the turn level, per desk, with
   direction.** Well/partial/unsupported per desk turn, split bull/bear, is the
   informative grain; the room scalar is a lossy compression. Adding the two
   missing bear-desk turn streams (aggressive/conservative debators) would fix
   the ±1/3 net quantization at the source and is cheaper than any downstream
   repair.
4. **Add a mandate-fit gate orthogonal to grounding.** APD-rep2 shows a room
   can be fully grounded on both sides and still approve a name the target
   holdout rules forbid. Grounding ≠ investability; C7 needs a deterministic
   thesis-broken check (the C8 gate) in front of the evidence bar, or the
   RIOT-shaped protection is bought while the APD-shaped hole re-opens.

Bottom line: the evidence scores are honest and accurate; the program's
interpretation of them as verdict predictors is what failed, and it failed for
measurable structural reasons. The Jev turn-level output is a sound input to
the C7 composite once direction and desk granularity are preserved and the
scalar room mean is dropped from the decision path.
