# CR213 — Distance-normalised target/stop reporting in the backtest report

Filed 2026-08-31 (AT:R74). Status: proposed.

## What

Add level geometry and its null to `scripts/backtest_report.py`'s target/stop-hit
section, so raw hit counts are never printed without the two numbers needed to
interpret them: how far each level sits, and what the counts look like under no skill.

## Why

The section currently emits counts alone (`results/report_r70-outcome-2.md:76-83`):

```
- Target: evaluated 40, hit 10 (25.0% of scoreable), unscoreable 0
- Stop:   evaluated 40, hit 15 (37.5% of scoreable), unscoreable 0
- First-touch: target_first: 9, stop_first: 13, ambiguous: 0, neither: 18
```

Hit counts cannot show a level is misplaced without normalising for distance — a nearer
level is touched more often, which is geometry, not a defect. With nothing to compare
against, the four lines invite exactly one reading, and on 2026-08-20 they got it:
`PHASE_B_OUTCOME_2026-08-20.md` concluded *"the Room's level-setting places stops closer
to harm than targets to gain"* and called it the batch's one fixable mechanism.

That reading was withdrawn 2026-08-31 (`17ccfa3c`). The Room sets roughly **2.6 : 1**
reward-to-risk (mean stop 5.12%, mean target 13.17%, from the realized market-fill exits
in `results/trade_pnl_r70-outcome-2.md`), for which a driftless random walk predicts
**72.0%** stop-first among trades touching either level. Observed was **59.1%** (13/22,
z = −1.35) — *below* the null, and inside noise either way. A 37.5%/25.0% split is what
a 2.6 : 1 R:R produces mechanically.

**The numbers were never hidden.** The R:R was fully recoverable from a P&L table that
shipped in the same batch. Two artifacts simply were not read against each other, because
neither one prompted it. That is a reporting defect in the weak sense — the report is
correct and produces a wrong inference — which is why this is a CR and not a DEF: the
spec asked for `level_provenance`-gated target/stop-hit and delivered it. What the
acceptance criteria never asked was what the counts should be *compared to*.

Same failure class as **DEF335** and **DEF379**: an artifact whose confident surface stops
the next reader looking. Here the fix is to make the artifact carry its own disconfirming
number.

## Scope

Add to the target/stop section, beside the existing counts:

1. **Level geometry over the stated levels of all scoreable runs** — mean and median stop
   distance and target distance as % of entry, and the resulting R:R (mean and median).
   Computed from `room_runs` levels, **not** from realized exits: the hit-only subsample
   is biased toward close levels on both legs, and correcting that bias is the main reason
   this belongs in code rather than in a one-off analysis.
2. **The driftless-random-walk first-touch null** — `P(stop first | one touched) =
   target_dist / (stop_dist + target_dist)`, on both the mean and median geometry, printed
   beside the observed stop-first share with its z.
3. **A one-line label making the null a null** — it states what the counts look like under
   no skill. It is not a target, not a threshold, and not a pass/fail gate.

## Constraints

- **`level_provenance` gating is unchanged.** `ami_default` levels stay excluded from both
  legs. A minted `entry*0.94` / `entry*1.13` pair ([`room_runner.py:1801-1802`](../../../backend/app/services/room_runner.py#L1801-L1802))
  would hard-code a 2.17 : 1 R:R and make the statistic meaningless.
- **Not a promotion gate**, under any framing. Same rule `RETEST_RECIPE.md` already binds
  the edge number to: the pinned batch is a regression check against a quantified noise
  floor, never evidence a change improved the Room. At 22 first-touches this statistic has
  no power to gate anything, and the report must say so where it prints it.
- **Byte-reproducibility is preserved** — no new RNG, no unsorted iteration, report date
  still pinned by `--stamp`.
- **State the window mismatch.** Target/stop-hit is measured over a fixed 20-trading-day
  window while the P&L table walks each trade to its own stated horizon (median 90 days).
  They are different populations, and that is part of why they were not read against each
  other. The report should name this where both appear.

## Acceptance

1. Unit tests on the geometry and null computation, including: a provenance-excluded leg
   contributes to neither; a symmetric 1 : 1 R:R yields a 50% null; and a fixture whose
   counts are lopsided purely by geometry produces a null that matches the observed share.
2. `pytest backend/tests/unit/ -q` green.
3. Re-running the report on unchanged DB state is byte-identical to itself.
4. The pinned-batch baseline table in [`../CR164_room_backtest/RETEST_RECIPE.md`](../CR164_room_backtest/RETEST_RECIPE.md)
   is re-diffed against a re-run, since this changes `report_*.md` bytes. That is the
   ~1.5 h routine the recipe exists for — it is not free, and it is the main cost here.

## Priority

**Low.** It prevents a repeat of a misreading that has happened once and is now corrected
in the document a future reader reaches first. Filed so it is not lost. It should not go
ahead of **DEF335**'s `auto_adjust=False` re-backfill, which is a live-data correctness
problem across 119,311 rows in 201 tickers.

## Out of scope

- Any change to how the Room sets levels. Nothing here established a defect in the levels;
  the correction found the opposite of one.
- Re-running `r70-outcome-2` for a new result. The batch's numbers are unchanged.
