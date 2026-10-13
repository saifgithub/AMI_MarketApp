# CR256 Step 0 memo — evidence-bar proxy-gate simulation (2026-10-13)

**Verdict: PASS for bar mechanics.** The quantile gate is computable, the holdout
exclusions enforce the investable universe, and split-fit thresholds land near the
locked target curve. The composite's incremental value over `stance_only` is NOT
measurable at this step — it requires claim cards + objections (spec prerequisite M7:
debator turns are absent from all four arms' Jev logs). That is the honest boundary of
this result.

Tool: `docs/tools/room_investigation_V2/tools/evidence_bar.py` (stdlib only, CPU only,
zero new rooms). Raw numbers: `docs/tools/room_investigation_V2/out/evidence_bar_step0/report.{md,json}`.

## Method

- Four committed 300-room arms: dsv4-prod (cr251-v2-dsv4), dsv4-disp (cr253-disp-matrix),
  ami-clean (cr251-v2-ami + fix), dsv4-tmall (cr254-tmall-matrix).
- Proxy scores over Jev-scored turns: `desk_net_cont` (legacy desk-signing),
  `stance_signed` (direction-signing, spec proxy), `stance_only` (baseline the composite
  must beat), `early_signed` (pre-synthesis only).
- Honest validation per review M5: in-sample quantile fit reproduces any curve
  trivially, so thresholds are **fit on rep-1 rooms and applied to rep-2** (split-fit).
- Targets per 60: R1–R5 = 5/15/30/45/**46** (amended). The 7-name holdout list
  (APD, BA, FCEL, RIOT, RIVN, SNAP, SPCE) is excluded from the approval set before
  ranking at every level; R5 is therefore 46 of 53 eligible.
- Falsifier check per spec: would the fitted bar approve a holdout on score alone?

## Headline (stance_signed, rep-1-fit approvals vs target 5/15/30/45/46)

| arm | R1..R5 | test-retest r | rep flips | non-monotone |
|---|---|---|---|---|
| dsv4-prod | 9 / 27 / 43 / 46 / 46 | +0.83 | 11/150 (7%) | 0/60 |
| dsv4-disp | 8 / 28 / 46 / 45 / 46 | +0.73 | 9/150 (6%) | 1/60 |
| ami-clean | 9 / 31 / 44 / 44 / 46 | +0.78 | 12/150 (8%) | 1/60 |
| dsv4-tmall | 13 / 31 / 46 / 45 / 42 | +0.75 | 15/150 (10%) | 4/60 |

## Findings

1. **Direction-signing re-confirmed on every arm.** `desk_net_cont` (desk-signed) runs
   r ≈ +0.01…+0.37 with 12–16% flips; `stance_signed` runs r ≈ +0.45…+0.78 with 6–10%
   flips. The measured flaw the review found is real and consistent — desk membership
   must never sign a card.
2. **The bar lands the top of the curve; the middle overshoots.** R4/R5 land within
   1 room of target on every arm (tm-all R5 under at 42). R2/R3 overshoot by 12–16
   rooms: rep-2 top-end scores run higher than rep-1 at those levels, so a threshold
   fit on 23 eligible rep-1 rooms shifts. This is threshold sampling noise, not a
   structural failure — but it means AC1 curve-matching must be evaluated on the
   fresh 30×5 fit per spec §6, not assumed from the proxy.
3. **The gate stabilizes decisions even on the worst arm.** tm-all raw rep flips were
   27%; under the gate they drop to 10% with non-monotone paths 4/60. The residual
   variance is the card-pilot's target.
4. **The holdout exclusion is load-bearing; the score does not separate the broken
   theses.** On score alone, holdouts clear the fitted bar at multiple levels on every
   arm — RIVN and SNAP most often (up to 5/5 levels on dsv4-disp desk Net), SPCE close
   behind. The RIOT-shaped "high grounding, broken thesis" falsifier is contained only
   because the deterministic exclusion forces PASS. Implication for the real composite:
   `evidence_score` must either beat this (cards surface the broken datum as
   `data_present: no` / unsupported) or the exclusion list stays a permanent policy
   layer. This is the single most important Step-0 finding.
5. **`stance_only` ≈ `stance_signed` on every metric here** (r within ±0.03, same
   test-retest). The Jev grounding adds nothing at the turn-proxy level — expected,
   since the proxy aggregates the same stance tags either way. The composite's claim
   to beat the baseline rests on cards + objections, which this step cannot measure.

## What this does NOT prove

- That the real `evidence_score` (cards + unresolved objections) discriminates — no
  cards exist yet; M7 (debator turns in llm_audit/Jev) is still the gating prerequisite.
- That curve-matching holds on fresh rooms — the R2/R3 overshoot says fit-once-per-model
  needs the §6 held-out-ticker procedure, exactly as specced.
- Temperature pinning (determinism note) — untouched.

## Next

Card pilot per spec: few tickers × one mid level × 3 reps, go/no-go on card-direction
test-retest r ≥ 0.85, with debator turns reconciled into Jev first (M7).
