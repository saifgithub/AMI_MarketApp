# Jev corpus deep dive + provenance forensics — 2026-10-14 (AT:K4)

Companion to `jev_review_2026-10-12.md` (judge accuracy audit). This doc covers three
later analyses over the same corpus: (1) what the full turn-level corpus says about
where decision signal lives, (2) provenance anomalies found when pooling arms, and
(3) the first readout of the CR257 PM-level Jev decision data against its GO criteria.

Analysis scripts were throwaway (`/tmp/jev_deep*.py`, `/tmp/jev_forensics*.py`,
`/tmp/jev_cr257.py`), read-only on run data, backend venv python. All numbers below
are reproducible from `docs/tools/room_investigation_V2/out/` with the joins stated.

## 1. Data and joins used

- Turn-level corpus: 18,228 Jev judgments across 8 arm dirs (`jev-1.13.0`, all vllm),
  ~151M input tokens. After dedup (§2) there are **6 independent room runs**:
  dsv4 production, disposition, tm-all (one copy), cap1, ami clean, v1 risk-matrix.
- Pooled desk statistics use 12,000 turns from 5 runs (dsv4, disp, tmall, cap1, ami
  clean); v1 is reported separately (different turn set: includes debators, 106
  model-less rows, 1 duplicate row, uneven level coverage).
- **ami clean join used here:** base `cr251-v2-ami` R1/R4 + `cr251-v2-ami-fix`
  R2/R3/R5 → 298 joined rooms, curve **0/0/10/10/20**. This differs from the
  previously reported join (base R3, 286 rooms, curve 0/0/4/10/20) — see §2.2.

## 2. Provenance anomalies (found 2026-10-14)

### 2.1 `cr254-tmall` ≡ `cr254-tmall-matrix`: same run scored twice

100% identical agent outputs (2400/2400 output-hash matches on room+agent+level),
identical `created_at` ranges, Jev `logged_at` 4 min apart, identical verdict curves.
EXPERIMENT_LOG lists both as "arm 11" pointing at the same melehost dir. Any pooled
analysis over both double-weights tm-all. Consequence: an earlier pooled
"fundamentals 16.7% unsupported" figure was an artifact of this double-count — see
§5 for the corrected, per-arm attribution. Side benefit: the duplicate scoring is a
free judge test–retest dataset (§3).

### 2.2 ami has TWO R3 datasets; the canonical curve depends on the choice

`cr251-v2-ami-fix` contains a complete, later **R3** re-run (480 Jev rows, created
2026-10-12 07:57–10:50) in addition to the documented R2/R5 re-runs. EXPERIMENT_LOG
describes the fix arm as R2/R5-only. Base R3 (DGX-era, 83% scored) has 4/60 approvals;
fix R3 has 10/60. The "settled" ami curve 0/0/4/10/20 uses base R3; the full clean
join gives 0/0/10/10/20. **Open:** which R3 is canonical needs a documented decision
in EXPERIMENT_LOG; ami r values shift by join (this is the same join-sensitivity
flagged in the 10-12 review, now with a concrete cause).

### 2.3 CR257 ami leg was built on the old (contaminated) join

`out/cr257/cr251_v2/jev_decision/` includes 102 NO_VERDICT rooms (of 300 replay-1
rows) and the base R5 curve (2/60), i.e. pre-fix runs. Redo this leg on the §1 clean
join before reading ami conclusions from CR257.

### 2.4 Benign

v2 arms' verdict files named `runs_cr251-risk-matrix-*` is benchmark-name reuse only:
0% output overlap with the actual v1 `cr251-risk-matrix` run, disjoint created_at.

## 3. Judge test–retest reliability (from the §2.1 duplicate)

Same 2,400 texts, two independent Jev scorings:

- **95.4% exact choice agreement** (2289/2400); disagreements almost all
  adjacent-grade (well↔partial 74, partial↔unsupported 35, well↔unsupported **2**).
- Soft support E = P(well)+½P(partial): **r = 0.994**, mean |Δ| = 0.017,
  0.0% of pairs differ by >0.2.
- Per-desk agreement 92.7–98.3% (lowest: fundamentals 92.7%, trader 93.7%).

Implications: judge noise is negligible as an error source (consistent with the ~5%
adjacent-grade human-audit estimate), and the rep-to-rep room-score instability
(§4.5) is **agent sampling variance, not judge variance**.

## 4. Where the decision signal lives (turn-level corpus)

### 4.1 The room is a bear-veto machine, not a bull−bear weigher

Bear-researcher support (negated) vs APPROVE, soft scores, per independent run:

| Run | n | r | AUC (low bear support → approve) |
|---|---|---|---|
| dsv4 production | 300 | +0.368 | 0.747 |
| tm-all | 300 | +0.338 | 0.735 |
| cap1 | 300 | +0.305 | 0.701 |
| disposition | 300 | +0.254 | 0.698 |
| ami clean (§1 join) | 298 | +0.199 | 0.685 |
| v1 risk-matrix | 288 | +0.188 | 0.642 |

Positive at essentially every level in every arm; APPROVE rooms always have
less-supported bear cases (per-level Δ = −0.10…−0.20 in dsv4). Meanwhile **bull-side
support correlates NEGATIVELY with approval** (−0.22…−0.33 across dsv4/disp/tmall),
and room-mean support anti-correlates (−0.26…−0.33). `net = bull − bear` therefore
dilutes the one real signal by adding the bull term with the sign the PM does not
use (net r = +0.13…+0.20, below bear-only). Mechanistic read: **the PM approves in
the absence of a well-evidenced objection, not in the presence of a well-evidenced
case.** In-sample, correlational — but replicated independently six times.

### 4.2 Still no standalone gate

Best single-threshold agreement for even the bear-only signal beats the always-PASS
base rate by only +1–2 pts (base rates 73–82% PASS). Ranking information is real;
a usable single cut does not exist. Jev scores are features and audit triggers,
not verdict replacements by threshold.

### 4.3 Soft probabilities: free dequantization, but compression wasn't binding

Using E[support] instead of hard labels: distinct room net values 11 → ~200 (the
net=+0.33 tie problem disappears with zero rescoring), pooled r improves slightly
(dsv4 +0.186→+0.204; tmall +0.071→+0.134), threshold lift unchanged (~0). The tie
problem was real but not the binding constraint; feature choice was.

### 4.4 Evidence is level-flat; only the verdict layer responds to risk

Mean soft support per side is constant R1→R5 (dsv4 bull 0.610→0.625, bear ~0.63–0.66;
disposition similar) while verdict curves swing 5→27%. Risk appetite changes how the
PM treats identical-quality evidence, not the evidence.

### 4.5 Per-room scores are noisy across reps; judge is not the cause

rep1-vs-rep2 room-mean soft score: r = +0.36 (dsv4) / +0.20 (disposition),
mean |Δ| = 0.067/0.081. Combined with §3: this is debate-generation variance.
Distribution-level and per-desk statistics are stable; single-room thresholds would
flip on reruns. Any per-room operational use needs replay-averaging.

## 5. Desk health and conviction (deduped pools)

Per-desk support, 12,000 turns / 5 independent runs:

| agent | well% | partial% | unsup% | soft E |
|---|---|---|---|---|
| social_media_analyst | 76.3 | 21.9 | 1.8 | 0.773 |
| market_analyst | 76.7 | 21.7 | 1.6 | 0.750 |
| trader | 61.2 | 36.9 | 1.9 | 0.714 |
| research_manager | 60.6 | 37.3 | 2.1 | 0.689 |
| bear_researcher | 47.4 | 50.5 | 1.9 | 0.645 |
| fundamentals_analyst | 43.9 | 46.9 | 9.1 | 0.609 |
| news_analyst | 36.9 | 59.5 | 3.5 | 0.606 |
| bull_researcher | **15.7** | 75.9 | 8.4 | **0.483** |

- **bull_researcher is robustly the least grounded desk** (well_supported 7–22% in
  every arm). Cross-desk room averages mostly measure desk composition (baselines
  span 0.48–0.77), not room quality; normalizing by global desk means does not
  change correlations (composition is fixed) but matters for absolute thresholds.
- **tm-all conversion specifically breaks the fundamentals desk**: 33% unsupported /
  23% well in tm-all vs 1.0–5.6% unsupported and 47–58% well in all other arms.
  New CR254-relevant defect signal, invisible in verdict curves.
- **Stated conviction carries no positive signal.** high vs low mean
  conviction_justified both 2.13; weak/contradicted (score<1.5) rate high **14.1%**
  vs low **8.3%** (medium 22.5%, mean 1.75). At high conviction:
  **social_media_analyst 97% weak (n=35), news_analyst 81% (n=135)**,
  bull_researcher 26% (n=238); all other desks ≤12%. Raw agent conviction should
  not reach users ungated; high conviction on social/news is near-uninformative.

## 6. CR257 PM-level Jev: first readout (dsv4 + disposition, 300 rooms × 2 replays each)

One typed decision call per room over transcript + mandate (~4.3K input tokens/room
vs ~40K for scoring all 8 desks — ~10× cheaper than full turn scoring).

- **Mimicry:** 93–94% verdict agreement with the PM.
- **Slightly more evidence-consistent than the PM** (bear-support r, Jev decision vs
  PM verdict): dsv4 **+0.421 vs +0.368**; disposition **+0.309 vs +0.254**. Largest
  gain at R1 (dsv4 +0.399 vs +0.166; disposition +0.521 vs +0.287).
- **Replay stability:** choice agreement **100% (dsv4) / 98.7% (disposition)**,
  mean |ΔP(approve)| ≤ 0.006. (Same-transcript replays — comparable to §3 judge
  reliability, NOT to cross-rerun PM flip rates.)
- **Curves (Jev replay-1 approvals/60 vs PM vs target%):**
  dsv4: 11/15/22/20/16 vs PM 5/11/22/27/17 (target 5/15/30/45/60) — R4 dips.
  disposition: 8/16/14/12/18 vs PM 1/7/13/15/19 — low-end willingness rises toward
  target but shape stays non-monotone (R3>R4), top end unchanged.
- **Holdouts:** APD-rep2 R5 — the room the PM wrongly APPROVEd (10-12 review) —
  **Jev also approves, P=0.76/0.73 across replays.** Jev-at-PM ratifies the policy
  violation; it is not an enforcement layer.

### Against the CR257 GO criteria (spec.md)

1. Holdouts (incl. APD-rep2 R5 out): **FAIL** on current data.
2. Curve shape vs 5/15/30/45/60, monotone-or-better: **FAIL** (R4 dips both arms).
3. Discrimination materially above PM: **partial/mixed** — improved vs bear-support
  r (+0.05) but not a step change; net-support variant not yet computed.
4. Disagreement hand-audit (~20 rooms): **not done** (disagreement pools: dsv4
  10 PASS→approve + 8 APPROVE→pass; disposition 17 + 4 — small, auditable).
Replay flips ≈0: **PASS** (the one clean win).

**Current verdict: NO-GO as a PM replacement on this data**; viable shape remains
Jev as PM second-reader (P(approve) + contestedness as consistency/audit signal)
with code keeping all policy enforcement.

## 7. Recommendations

1. **Placement:** decision-relevant Jev belongs at the PM (one call), per-desk Jev
   is the diagnostic instrument — keep full 8-desk scoring on experiment arms and a
   sample of production rooms, not every production room. Cheapest always-on
   turn-level signal, if wanted: bear_researcher only (one call; the only desk whose
   score predicts verdicts).
2. **C7 anchor:** per-level, per-desk, direction-aware distributions — specifically
   bear-support — never room means or net scalars; soft probabilities, not hard
   labels; no single-room thresholds without replay-averaging.
3. **CR257 evaluation baseline:** any Jev-decider must beat the trivial
   "one bear turn's support score" baseline (AUC 0.64–0.75 by arm) to justify its
   existence.
4. **Record fixes needed (not yet applied):** EXPERIMENT_LOG — merge duplicate
   arm-11 rows, note tmall/tmall-matrix local duplication, document the ami fix R3
   re-run + canonical-R3 decision; CR257 ami leg rebuild on the clean join;
   analysis docs to state which ami R3 join each number uses; CR254 write-up to add
   the fundamentals-grounding defect (33% unsupported).
5. **Prompt/QA targets:** bull_researcher grounding (all models), tm-all
   fundamentals conversion, high-conviction gating for social/news desks.

## 8. Jev/PM 5-seat panel mixes (Saiful's "3 Jev + 2 PM?" question)

Exact offline simulation over the 600 fully joined rooms (300/arm): runs records
carry `approve_votes` k of 5 PM samples; CR257 supplies the Jev vote (replay-1;
replay agreement 98.7–100% justifies treating the Jev bloc as unanimous). For a
j-Jev + p-PM panel, P(approve) per room is enumerated exactly over hypergeometric
PM-candidate subsets. Script: throwaway `/tmp/jev_panel.py`.

**Mechanical trap: 3J+2PM ≡ 4J+1PM ≡ 5J exactly.** A unanimous 3-vote bloc in a
5-seat majority panel decides every room; the 2 PM calls can never change any
outcome. "3 Jevs + 2 PMs" is therefore not a hedge — it is full Jev-as-decider
(currently NO-GO per §6) with two decorative PM calls. Only 1J+4PM and 2J+3PM are
genuine mixes (2J+3PM = Jev decides unless the 3 sampled PMs unanimously override).

| Mix | dsv4 curve (exp/60) | disp curve | bear-r dsv4/disp | flip% dsv4/disp | dist-to-target dsv4/disp |
|---|---|---|---|---|---|
| 0J+5PM (status quo) | 6/12/22/27/17 | 2/12/13/15/19 | +0.379/+0.258 | 18.7/22.0 | 0.790/0.896 |
| 1J+4PM | 7/13/22/26/17 | 4/13/14/15/19 | +0.399/+0.264 | 19.3/22.4 | 0.798/0.891 |
| 2J+3PM | 9/14/22/24/16 | 5/14/14/15/18 | +0.418/+0.275 | 18.9/23.8 | 0.820/0.896 |
| 3J+2PM (=5J) | 11/15/22/20/16 | 8/16/14/12/18 | +0.421/+0.309 | 20.0/26.7 | 0.860/0.931 |

(Expected flips across rep1/rep2; realized PM-majority flips 17.3%/20.7% for
reference. Curves rounded; dsv4 0J R1 shows 6 vs realized 5 because the expected
panel samples PM candidates probabilistically.)

Findings:
1. Mixes interpolate only marginally: +0.02–0.04 bear-r for 1–2 Jev seats, low-end
   approvals up slightly, **curve distance to target gets WORSE with more Jev**
   (Jev's R4 dip dominates), **flips do not improve** (disp worsens 22.0→26.7%).
2. Holdouts are mix-invariant: all mixes PASS APD/RIOT in dsv4; all mixes APPROVE
   the disposition APD-rep2 violation (PM was 5/5 approve AND Jev approve — the
   violation is shared, so no panel can catch it; code must).
3. **There is no sweet spot.** If the goal is cost: one Jev call already equals the
   whole 3J+2PM panel — but that is the NO-GO replacement path. If the goal is a
   hedge keeping PM character: 1J+4PM buys +0.02 bear-r at zero measured stability
   or curve benefit — not worth the complexity on current evidence.
4. The decision-relevant measurement is still the missing CR257 criterion 4:
   **who is right in the 18–21 disagreement rooms per arm?** Jev winning those
   justifies Jev-dominant panels; PM winning them confirms 5PM. Mix arithmetic
   cannot substitute for that audit.
5. If a real jury is ever wanted: differentiate Jev roles (advocate/skeptic/rubric
   variants), not seeds — identical Jev calls are ~deterministic, so extra Jev
   seats add weight, never diversity.

## 9. CR257 v2: Jev on the PM's OWN input (2026-10-14)

Motivation: v1 confounded decider with inputs (no fact sheet, no risk content,
4-field mandate). v2 fed the judge the exact recorded `portfolio_manager`
`system_prompt` per room (300/300 present in llm_audit, ~50K chars, candidate
prompts identical). Tool `tools/jev_decision_arm_v2.py`; 600 calls, 0 errors,
8.84M tokens; full acceptance record in `CR257_jev_decision_arm/spec.md` §8.

| Metric | PM | v1 (reduced) | v2 (full PM input) | target/60 |
|---|---|---|---|---|
| Curve R1–R5 | 5/11/22/27/17 | 11/15/22/20/16 | **1/4/20/21/14** | 5/15/30/45/46 |
| net-support r | +0.186 | +0.204 | +0.201 | — |
| bear-support r | +0.368 | +0.421 | +0.299 | — |
| Replay choice agreement | — | 100% | 99.7% | — |
| Holdouts APD/BA/RIOT | some fail | pass (this arm) | pass all levels | out |

Key findings:
1. **Identical inputs do not rescue Jev-as-decider.** v2 NO-GO on the same
   gates as v1: curve worse (most conservative reader), discrimination ties
   the PM. The v1 NO-GO was not a reduced-record artifact.
2. **Information effect = more conservative:** v1→v2 = 30 flips, 27 toward
   pass, concentrated at R1/R2 (11→1, 15→4). Seeing the full fact sheet and
   risk stage makes the judge stricter, not more willing.
3. **v2 approvals are a strict subset of PM approvals** (22 PM-approve→v2-pass,
   0 reverse) — a conservative filter shape, not a replacement shape. The
   22-room one-directional disagreement pool (v2 P 0.14–0.48; mixes of strong
   bear and strong bull cases) is the hand-audit set that decides whether this
   filter has value.
4. Natural next tests: the 22-room audit (who is right), and v2 on the
   disposition arm — the arm where v1 actually failed holdouts (APD 2/2,
   BA 1/2) — to see whether full input fixes the holdout failures too.

## 10. Why would a stock be OK at R1 but not R5? (payoff-shape tests)

Saiful's two candidate rational explanations for inversions, tested on the dsv4
300 rooms (features parsed from recorded market_analyst/trader text, no new
calls; range50 n=187, dist200 n=169 of 300; trader entry/target/stop too sparse
+ selection-biased to use — geometry exists almost only where the trader
proposed, and at R3+ no PASS room has it):

**H1 — "return doesn't warrant the risk at bigger size" (Kelly/utility).**
Economically valid, but implies RESIZE not REFUSE: higher cap only expands the
feasible set, so any R1 position is still available at R5. Supports: cap-1%
pinning removed the R4→R5 inversion (EXPERIMENT_LOG arm 2), and sub-cap
approvals are rare (~11%) — the room mostly refuses instead of resizing.

**H2 — "a high-risk investor WANTS riskier, higher-upside names" (payoff-shape
preference).** This one *can* legitimize inversions (a boring name approved at
R1 may rationally be passed at R5). But the room demonstrably does NOT do it:

- 50-day range width (volatility proxy), mean approve vs pass:
  R2 18.6 vs 27.8 · R3 19.8 vs 31.7 · R4 20.9 vs 34.0 · R5 21.2 vs 34.0
  (R1 24.6 vs 27.6, n=2 approvals). At R5 the room still passes WIDE-RANGE
  (riskier, bigger-swing) names — the opposite of moonshot selection.
  Per-level r(range50, approve): −0.04/−0.23/−0.53/−0.41/−0.32.
- Distance above/below the 200-day: approvals +4…+7% vs passes −5…−10% at
  EVERY level. The room's selection is "uptrend + low volatility", invariant
  across risk levels; risk appetite moves only counts and size.
- Inversions (14 ticker-reps approved at R1–R3 then passed at R4/R5) therefore
  read as noise around stable trend/vol filters plus R5 size-coupling, not as
  rational preference expression.

**The policy fork this exposes (needs Saiful, not more mechanism):**
1. Risk appetite = size ceiling only → selection should be level-invariant.
2. Risk appetite = evidence-bar loosening (the locked target curve's current
   semantics) → inversions are always bugs; R5 approves every defensible name.
3. Risk appetite = payoff-shape preference (Saiful's moonshot semantics) →
   inversions for low-upside names are CORRECT, and the target curve needs a
   per-ticker composition dimension, not just approval counts.
Whichever is chosen, the room currently lacks the numeric payoff inputs
(expected upside, volatility) to implement it deliberately — that, not more
prompt nuance, is the missing piece.
