# CR136 Rev 4 — verification fleet

The simulation scripts that produced every measured pin in
[`../CR136_portfolio_health_metrics.md`](../CR136_portfolio_health_metrics.md)
Rev 4. Archived from the authoring session's scratchpad so the pins stay
re-derivable and so the M02/M05 audit lane has the re-derivation pack in-repo
(M11 §audit).

**These are evidence, not product code.** They are not imported by the app,
not covered by the test suite, and deliberately use numpy/yfinance — the
opposite of `trading_math/`'s stdlib-only contract. Nothing here ships.

## Running them

```bash
"backend/.venv/bin/python" docs/forward_planning/CR136_portfolio_health_metrics/verification_fleet/<script>.py
```

Requires numpy (present in `backend/.venv`) and, for the live-data scripts,
network access to Yahoo. Seeds are fixed; reruns reproduce the numbers quoted
in Rev 4. **`s3_delta_sweep.py` additionally imports `scipy`** for the
root-find that refines δ\* — without scipy the sweep table (the load-bearing
part) still prints and the final `δ* = 0.4371` line is skipped.

## What each script establishes

| Script | Rev 4 pin it produced |
|---|---|
| `cr136lib.py` | shared helpers (EWMA covariance, DR², Euler, LW target) used by the others |
| `s1_analytic.py` | closed forms: fat-tail inflation √((κ+2)/2); TE identity → 16.82%; parametric bad-month 2.71/6.07/12.44%; Lo CI [−2.28, +4.28]; t_eff table |
| `s1_lw_cash_and_degeneracy.py` | **F1** — LW constant-correlation target NaNs on a zero-variance cash row; the risky-only-then-append fix (Euler exact to 0.0) |
| `s1b_n2_seeds.py` | **F1 related** — LW undefined at N=1, degenerate at N=2 (γ exactly 0 in 23% of 500 seeds) |
| `s2_f2_mc.py` | **F2** — R2 fires 89.0% (plain) vs 30.1% (LW-shrunk) on the twin book; σₚ −5.7% biased |
| `s2_mc_fattail_f17.py` | **F7** fat-tail SE by Monte Carlo; **F17** σ̂ₚ relative error 1/√(2T) independent of N (to N=200, singular) |
| `s3_delta_sweep.py` | **F2 ceiling** — DR² vs δ; crossing at δ\* = 0.4371 (review's "~0.5" corrected) |
| `s3_mdd.py` | **F10** — E[MDD] table provenance (discrete geometric walk, not √(π/2)σ√T); monotone ratchet; rolling-252 fix restores improvability (87.4% of paths) |
| `s4_ewma_se_echo.py` | **F11 + SE pin** — EWMA ESS 65.67; true SE 1.72pp vs naive 1.26pp (27% understatement); equal-weight echo −2.90pp |
| `s4b_echo_fix.py` | **F11 fix** — EWMA(0.97) has no exit discontinuity (−0.03pp) |
| `s4_lo_power.py` | Lo power: 49.7% rejection at 970 days, 80.2% at 1,982 |
| `s5_stability_hysteresis.py` | **R2 band** — EWMA flips 21.3% unbanded; h=0.15 → 5.5% flips, 99.3% detection |
| `s6_composition.py` | **final estimator composition** — unshrunk EWMA fires R2 at 82.1%; Euler exact to 3.3e-16 with cash under EWMA |
| `c1_f3_counterexample.py` | **F3** — R1's per-dollar claim false; trimming B is 2.23× better than the named A |
| `c2_f4_fire_rates.py` | **F4** — R3 fire rates 13.3/50.5/86.9% at true β 1.20/1.30/1.40; SE(β̂) ≈ 0.090 |
| `c3_c4_overlap_hysteresis.py` | **R3 band** — overlapping-window flips 18.7%; CI-gating rejected (50.8% detection at β 1.45); 0.6·SE confirmed |
| `c5_share_sampling_error.py` | **adjudication** — top-share sd ≈ 2.2pp at T/N=5 (PM_REVIEW's ±15–20pp refuted) |
| `c7_r1_band_derivation.py` | **R1 band** — ±1.5pp (worst flip 7.7%, detection 95.6%) |
| `f9_verify.py` / `f9_addendum.py` | **F9** — cash artefact (+29.3→+59.3pp); DR²/shares exactly cash-invariant; HHI non-monotone; invested-sleeve fix; bar-chart edge cases |
| `f21_verify.py` / `f21_gap.py` / `f21_lw.py` / `f21_robust.py` / `f21_fixtest.py` | **F21 re-grade** — live data: SPY+QQQ+AAPL DR² 1.261; R2's n≥8 gate silences every small book; R2b separates every test book |
| `f15_validators.py` | **F15** — naive digit validator rejects the CR's own mandated content; allow-list prototype 0 false accepts/rejects on 20 cases |
| `def213_attack2_measure.py` / `def213_attack2_sweep.py` / `def213_attack2_realistic.py` | **DEF213** — a non-contiguous joined grid annualised as daily. One path two ways (19.34% → 25.40%); 24-seed sweep 1.372× even-grid / 1.424× odd-grid, 24/24 overstated, √2 predicted; re-annualising at 126 periods/yr returns 0.970 (sd 0.060), localising the gap in the constant. Realistic arm — ONE gappy holding of three: +6.1% at 5% missing days, +29.8% at 40%, with `dropped_holdings` empty and `partial` false at every level |
| `def213_guard_threshold.py` | **DEF213 guard threshold** — where `GRID_DENSITY_MAX` goes. The gappy side was already measured (above); this is the CLEAN side, which is not 7/5 = 1.40 on a real calendar because market holidays remove trading days without removing calendar days. 10y of daily bars, 8 instruments across both venues and four asset classes: all 8 share ONE calendar (2513 of 2513 dates, so a clean book's join loses nothing for calendar reasons), and over 11,038 rolling windows at every length the engine consumes the ratio is mean 1.4535, **max 1.4921**. Yahoo's free endpoint caps that ticker at ~10y today, so 9/11 (4 sessions) and Sandy (2) are outside the fetchable window and the multi-day-closure tail is **constructed, not observed** — deleting L consecutive sessions from the real calendar reproduces the shape, worst **1.5556 at L=5**. 1.65 clears that by 6.1% and fires above 11.9% of one holding's days missing |
