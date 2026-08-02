# Run report — 2026-08-02_run-01

**Item:** CR136 (round 1) · **SHA:** `2c1e4e08` · **Verdict:** AWAITING_FIXES
**Lane type:** math/design audit — docs-only submission, no source diff.

## Method

- Worktree `.claude/worktrees/audit-CR136` at `2c1e4e08`.
- Docs-only confirmed: `git show --stat` on `2dd45937`, `03011bf4`, `2c1e4e08`
  — CR doc + row file + generated register only. Backend suite not applicable.
- `python3 scripts/registers/gen_registers.py verify all` → DEF 209 / CR 132 OK.
- Independent recomputation of C1–C6 from stated formulas/inputs, no repo code:
  - C1 Lo(2002): CI [−2.28, +4.28], T_sig = 970d ≈ doc's 971. ✓
  - C2 SE table: 40.0/1.77, 20.0/0.89, 8.9/0.40, 4.5/0.20 pp — exact. ✓
  - C3 DR²: closed form AND explicit-Σ numeric agree (1.22/3.57/1.24, 8.2×). ✓
  - C4: 0.533/0.233 → 2.29×. ✓
  - C5: own Monte Carlo (seeds 7/123, 20 & 40 yr, two vols) → 0.831 =
    √(252/365); doc's 0.845 within MC noise, direction confirmed. ✓
  - C6: substance confirmed on patent text (TEV, contribution by
    security/sector/factor, holdings × current exposures, MC among model
    types, no track record) — **attribution FALSE**: US10157419B1 is FMR LLC,
    not BlackRock; "~250k scenarios" unverified.
- Blind probes of my own (none suggested by the submission):
  - Euler identity with zero-vol cash row: Σ contributions = 1.000000, cash 0.
  - DR² out-of-model: 60/40, vols 16%/7%, ρ=0 → 1.54 ≠ 2 (framing exact only
    under equal vol/uniform ρ).
  - Kurtosis check on SE(σ̂): κ≈30 → ~1.9× Gaussian SE; asymmetry unchanged.
- File:line verification of every codebase claim the design rests on (14
  checks, all TRUE — see auditor lane file).

## Findings

- **M1** sufficiency thresholds unspecified (T per metric, T/N for Σ, SE
  formulas, short-history rule) — build would proceed to vibe-set floors, the
  exact class the CR exists to kill. Architect conceded; upheld independently.
- **M2** C6 misattribution (FMR patent cited as "BlackRock's own"; Aladdin
  claim unsupported by this patent).
- m1 row file stale (backwards "inflate Sharpe 1.204×" + BlackRock); m2
  contract example `value: 0.0` vs "no value when insufficient" (must be
  null); m3 DR² copy caveat; m4 LW implementation path unpinned (no declared
  numpy/scipy/sklearn; PSD-by-construction note); m5 weight-denominator
  convention unpinned.
- DoD absent — waived per gap-fill 7, recorded.

## Artefacts

- Verdict: `orchestration/audit/cr/CR136.auditor.md`
- Trail row appended: `orchestration/audit/audit-trail.md`
