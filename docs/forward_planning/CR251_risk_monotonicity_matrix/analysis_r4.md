# CR251 — analysis_r4: sub-cap variant test + R5 cap ladder + evidence-bar fit

**Status:** companion to frozen BASELINE.md / analysis_r2.md / analysis_r3.md.

**Arms in this report** (all dsv4, in-container, review layer OFF, R5 unless noted):
- `cr253-subcap-r5` — 11 size-sensitive tickers × 3 reps, PM persona =
  production + CR253 disposition table + sub-cap conditional. 33/33 rooms.
- R5 cap ladder — the 9 inversion tickers at caps 1/2/3/4% (2 reps each) +
  uncapped 5% from the main arm; BAC/PYPL/WFC ladder cells from the dose probe.
- Evidence-bar fit — net-thesis-support thresholds fit to the CR255 target
  curve (R1=5/15/30/45/60), uncapped 300-room arm.

## 1. Sub-cap variant: PARTIAL GO, wrong mechanism

Approvals moved the right way on size-gated names (sub-cap ×3 vs uncapped ×2):
BAC P/A/A vs P/P · PYPL A/A/A vs P/A · MO A/P/A vs A/P · TMO A/P/A vs P/A,
plus first-ever R5 approvals for DHR (P/P/A), LEVI (P/P/A), SO (P/A/P).
Total 13/33 vs ~9/33 expected from uncapped rates. CAG/DE stayed out
(evidence-gated, as the inversion probe predicted). WFC regressed 1/2 → 0/3.

**But the mechanism failed:** only **2 of 13 approvals** came in below the 5%
cap (BAC 3.5%, PYPL 4.5%) — **15% sub-cap usage**. The disposition table's
"R5 = pass only broken cases" did the work (more full-size approvals); the
sub-cap conditional barely engaged. Side effect: more 5% approvals on marginal
names — the opposite of evidence discipline given the negative discrimination
in analysis_r3. One narration was arithmetically incoherent ("Cut the
Execution Desk's 2.0% to 3.5%" — a cut that raises size).

**Decision: do NOT fold in as-is.** Next: disposition-table-ONLY variant
(same 11 × R5 × 3) to isolate which block drives the willingness shift; the
sub-cap conditional needs a rewrite with a size-arithmetic sanity guard before
re-test.

## 2. R5 cap ladder — per-name size thresholds (approvals per 2 reps)

| Ticker | 1% | 2% | 3% | 4% | 5% | shape |
|---|---|---|---|---|---|---|
| DHR | 2 | 2 | 2 | 0 | 0 | **clean decay, threshold 3→4%** |
| MO | 2 | 2 | 2 | 0 | 1 | threshold 3→4% |
| BAC | 2 | 2 | 1 | 1 | 0 | decay to zero by 5% |
| TMO | 2 | 1 | 1 | 0 | 1 | weak decay |
| LEVI | 2 | 0 | 2 | 1 | 0 | noisy |
| JPM | 1 | 2 | 1 | 1 | 1 | flat |
| DE | 0 | 0 | 0 | 1 | 0 | flat/noise |
| SO | 0 | 0 | 0 | 0 | 0 | never (evidence-gated) |
| CAG | 0 | 0 | 0 | 0 | 0 | never (evidence-gated) |

The size-worthiness coupling is **name-specific, not global**: ~3 names have a
real size threshold (DHR/MO/BAC), the rest are noise or evidence-gated. This
is the quantitative value map for any future sub-cap feature: per-name, not
per-level.

## 3. Evidence-bar fit (target curve 5/15/30/45/60): single-metric DEAD

Fitting per-level net-support thresholds to the target (full procedure in
CR255 target_curve.md): R1 +0.333 → 0/5 overlap with actual approvals; R5
−0.500 = "approve everything". Fatal flaws: (a) massive ties — ~40/60 R5 rooms
at exactly net=+0.33 (per-desk means over few turns quantize); (b) direction
fixed but resolution insufficient. **C7 must be a composite decision score**
(net support + unresolved objections + catalyst proximity + decision-record
factors) to rank rooms; the single-metric bar cannot implement the policy.

## 4. Net-support correlations (for the record)

Uncapped arm: pooled r=+0.186 (direction-corrected); cap1-pinned: +0.074.
Both at-or-below always-PASS threshold value. Per-desk decomposition:
trader −0.44 (verdict-aware prose artifact), bear −0.36 (rational), bull
+0.17 (correct sign, weak). Raw room-mean −0.36 conflates all three.

## 5. Standing recommendations

1. Disposition-only variant test (isolates the willingness driver).
2. C7 composite score build — scoped by the fit failure in §3.
3. Sub-cap conditional: rewrite + arithmetic guard, re-test only after (1).
4. Per-name size thresholds (§2) are the calibration target for the sub-cap
   feature when it ships — not per-level defaults.
5. ami-llm control arm (watcher armed, hourly) before any production fold-in.
