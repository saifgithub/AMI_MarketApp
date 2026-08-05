<!-- CR136 M11 — F16 bias-test reading log: dated sd(z) readings per portfolio; band [0.911, 1.089] is decision-grade at n=252. Record, don't gate. -->

# CR136 F16 — bias-test reading log

Tier 2 is Tier 1's validation layer. If the engine's predicted volatility is
right, a realised daily return divided by it has **sd(z) ≈ 1**. Below 1 means
the model over-states risk; **above 1 means it under-states it**, which is the
direction that matters and the reason this log exists at all.

## Command

```bash
ssh melehost "docker exec ami_api_alpha python -m scripts.cr136_bias_test"
ssh melehost "docker exec ami_api_alpha python -m scripts.cr136_bias_test --start 2026-09-01"
```

Prints `n`, `mean_z`, `sd_z` per portfolio against `BIAS_SD_BAND = (0.911, 1.089)`.

## How to read it — and what NOT to conclude

- **The band is Rev 4's acceptance band at T = 252.** Quoting it against thirty
  observations is exactly the over-confident reading the uncertainty contract
  exists to prevent. Readings below ~252 pairs are recorded as **immature** and
  are not judged.
- **The clock starts at ship, not at backfill.** A z-pair needs the prior day's
  `predicted_vol_ann`, and every M10-backfilled row carries null F16 columns by
  design — `bias_z_stats` skips those pairs structurally. So the series begins
  at the first live-tick row, no matter how deep the backfilled history goes.
- **Real books only.** Same exclusion filter as every other CR136 measurement:
  no `last_app_version = 'room-benchmark'` synthetics, no 05-24 05:10 seed rows
  (`memory/feedback_user_report_exclusions.md`).
- **Launch is never gated on this.** An out-of-band `sd_z` at n ≈ 252 on a real
  book mints a DEF against the estimator. It does not hold a release.

## Schedule

| Milestone | When | Expected n |
|---|---|---|
| First reading | ~1 month after ship | ≥ 21 |
| Monthly thereafter | every ~21 trading days | +21 |
| First **decision-grade** reading | ~12 months after ship | ~252 |

## Readings

| Date | Portfolio | n | mean_z | sd_z | In band? | Note |
|---|---|---|---|---|---|---|
| 2026-08-05 | all 95 | **0** | — | — | — | **Ship reading — the clock starts here.** `alpha-2026-08-04-1` promoted 2026-08-04; the first live snapshot tick ran 2026-08-05 and wrote **95 rows for as_of 2026-08-04**. Every portfolio reads `n<2 — nothing to say`, which is the structurally correct answer and not a defect: a z-pair needs the PRIOR day's `predicted_vol_ann`, and there is exactly one live row per book. Also recorded: that tick reported **`vol_null: 92` of 95** — only the three books whose price history had been warmed (2.6) carry a prediction at all, so the F16 series will accumulate for those three first and for the rest only as their histories warm. Nothing here is judged against `BIAS_SD_BAND`; per this file's own rule, that is decision-grade at n ≈ 252, i.e. ~12 months out. |
