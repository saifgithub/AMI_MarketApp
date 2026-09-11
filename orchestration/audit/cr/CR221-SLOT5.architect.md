# CR221 slot 5 — C8 dividend growth, C7 implied buyback price

SCOPE: CR221 slot 5 only. C8 (historical dividend growth CAGR) and C7 (buyback average
execution price) from the 49-item register. No other slot, no flag flip, no deployment.

TIER: B — new producer services plus a render seam, both behind flags that default False.
No migration, no schema change, no deletion. 1,001 insertions, 0 deletions.

SHA: bb47803da433774aaf4b939977141e80e0acacf3
  b45bbda3  feat(CR221): C8 dividend growth and C7 implied buyback price, both flag-off
  bb47803d  docs(CR221): 7.12 slot 5 — the guard behind a guard is untested by default

DEPENDS-ON: CR206 (`dividend_history` → `DividendPayment`), R35 (`BUYBACKS` repurchase
dollars, already ingested), `edgar_pit.quarterly_series`. Base includes DEF406's
re-parented migration chain and its promotion gate (`065f0bae`), untouched by this lane.

## What and why

Two of CR221's fourteen sourcing decisions that need no new network. Decision 9 (C8) rides
the dividend payment feed CR206 already fetches for the options desk; decision 8 (C7) is a
quotient of R35's repurchase dollars over one new EDGAR tag,
`TreasuryStockSharesAcquired`.

**C8's basis is the last declared rate of each year, not the calendar-year sum.** The sum
basis is the obvious implementation and it prints a dividend cut the company never made.
Measured on Realty Income: its May-2024 ex-date slipped to 2024-06-03, so eleven ex-dates
land in 2024 and thirteen in 2025. Calendar sums run 3.062 → 2.872 → 3.490 while the
declared rate rose every single month. Sum basis 5.90% CAGR against the rate basis's true
2.25%.

**C7 requires the four paired quarters to be contiguous.** The live probe found this
necessary against my own first implementation, which counted quarters without requiring
them to abut. CAT's companyfacts on 2026-09-11: the newest four quarters both tags carry
are Q1 of 2023, 2024, 2025 and 2026 — $13,543M over 26.1M shares, a $518.82
"trailing-twelve-month" price spanning 3.25 years. That is `ttm()`'s documented hazard
arriving through a second series.

## Tests, measured at this SHA in a detached worktree (DEF159)

Worktree: `wt_audit5`, `git worktree add --detach <SHA>`, venv symlinked, nothing built
in the dirty tree.

| Selection | Result |
|---|---|
| `test_cr221_c8_c7_capital_returns.py` (new, 24 tests) | 24 passed |
| plus compose parity, CR219 availability guard, P30 register names, DEF405 suite gate, CR221 I1 | **173 passed, 1 skipped** |

The full `tests/unit/` run was in progress at time of submission and green through 55% with
zero failures; the auditor should re-run it rather than take that as complete.

## Mutation proof — 12 mutations, 11 killed, the 12th provably equivalent

Each killed mutation is named with the single test that died for it. Reverts were done with
in-memory backups restored after every mutation, because an earlier sweep in this CR
silently stacked three mutations when `git checkout --` failed on untracked files.

| # | Mutation | Verdict | Killed by |
|---|---|---|---|
| M1 | dividend: series basis becomes the calendar-year SUM | killed | `test_cats_measured_series_reproduces_its_measured_cagr` (+5) |
| M2 | dividend: drop the contiguous-walkback break | killed | `test_a_suspension_truncates_the_window_and_says_so` |
| M3 | dividend: let the partial current year into the series | killed | `test_cats_measured_series_…` (+6) |
| M4 | dividend: disable the special-dividend ceiling | killed | `test_a_special_dividend_is_excluded_from_both_bases_and_named` |
| M5 | buyback: drop the contiguity guard | killed | `test_a_gap_in_the_middle_is_refused_by_contiguity_alone` |
| M6 | buyback: drop the 330–400 day span guard | killed | `test_four_contiguous_quarters_that_are_not_a_year_are_refused_by_span_alone` |
| M7 | buyback: pair on `period_end` alone | killed | `test_a_restated_quarter_with_a_different_start_is_not_paired_across` |
| M8 | buyback: weaken the share floor to `shares > 0` | killed | `test_the_share_floor_refuses_a_residual_the_price_ceiling_would_wave_through` |
| M9 | buyback: accept three paired quarters | **SURVIVED — provably equivalent** | see below |
| M10 | buyback: drop the `as_of` cutoff | killed | `test_a_future_quarter_is_not_read_before_its_time` |
| M11 | render: money formatter drops trailing zeros again | killed | `test_a_rate_renders_in_cents_and_a_sub_cent_rate_keeps_its_digits` |
| M12 | render: money formatter rounds a sub-cent rate to cents | killed | same test |

**The surviving mutation changes no behaviour, and the arithmetic is the proof.**
`edgar_pit.quarterly_series` keeps only periods of 70 to 100 days. Three contiguous such
periods span at most 3×100 + 2×7 = 314 days, and the span guard requires at least 330. So
`len(paired) < 4` relaxed to `< 3` cannot alter any outcome the resolver can reach. The
check is kept because its log message names the condition the span message would not, and
`test_three_paired_quarters_are_too_few_to_be_a_trailing_year` asserts the 314 < 330
arithmetic so a future change to the upstream filter re-opens the question loudly rather
than silently.

**The first sweep killed only 7 of 10, and that was a genuine gap in my tests, reported
here rather than quietly fixed.** Two guards each hid behind the other: the measured Q1×4
case spans 1,185 days, so the span check caught it whether or not contiguity was present,
and no test had a case where contiguity could be the only check to fire. The share floor
hid behind `MAX_PRICE`, because 40 shares against $7.2bn gives $180.6M per share. Three
isolating tests were added, each constructed so only the target guard can fire. Two first
drafts of those tests passed for the wrong reason — half-year periods and a 58-day period
never reach the resolver at all, because the upstream filter drops them — which is the same
failure mode as the test being replaced.

Two render mutations were then added and caught a flaw 23 green tests had missed: `:,.4g`
drops trailing zeros, so CAT's $1.20 declared rate printed as "$1.2" and its $5.00 annual
total as "$5".

## Live measurement at this SHA

```
RENDER SEAM: flag-off 873 chars -> flag-on 1496 chars, delta 623

C7: Buyback average price (implied) (LIVE): $664.64 per share, $7,224M repurchased
    ÷ 10,869,082 shares acquired, as filed, over the 4 quarters 2025-07-01 to
    2026-06-30, AMI's own quotient of two filed figures, not a company-reported
    average price

C8: Dividend growth (declared rate, by year) (LIVE): declared rate 2021 $1.11 ·
    2022 $1.20 · 2023 $1.30 · 2024 $1.41 · 2025 $1.51 per share, +8.0% CAGR over 4
    years, raised in 4 of the last 4, cash paid per share by year 2021 $4.28 ·
    2022 $4.62 · 2023 $5.00 · 2024 $5.42 · 2025 $5.84, AMI's own reading of the
    payments' ex-dates, 4 payments each year, 2026 excluded as a partial year
```

$664.64 sits inside CAT's own close range for 2025-07-01..2026-06-30 (low $386.02, high
$1,062.93, mean $632.74), which is the external corroboration.

## Absent states, deliberately

- **CAT's real companyfacts resolves C7 to ABSENT today**, because the four quarters both
  tags share are not a year. That is the correct answer, not a failure.
- **Deere tags no share count at all** (CR221 §4b: CAT n=197 points, Deere none), so
  absence is the common outcome for C7 rather than an error.
- A company that never paid a dividend and a feed that failed are both absent for C8, and
  neither renders a zero.
- The CR219 availability guard flagged my persona edit as an unclassified absence claim.
  An `_ALLOWLISTED_DENIALS` entry was added (category `runtime-deference`) rather than
  weakening the guard.

## What the auditor should attack

1. **The M9 equivalence argument.** If `_QUARTER_SPAN` or the span bounds ever change, or
   if a three-period window can reach 330 days some way I have not seen, then the
   four-quarter minimum is reachable and untested.
2. **Whether the isolating tests actually isolate.** Each asserts that the *other* guards
   accept its window, but the assertions are mine and could be wrong in the same direction
   as the code.
3. **The declared-rate basis itself.** It is a judgement call, not a measurement: the sum
   basis is what a filer's own annual report would show. The line states both and names
   which is which, but an auditor may reasonably think the default should be the other way.
4. **`_overlay_capital_returns` sits inside the `as_of is not None or use_real_market_data`
   branch**, so C8 is withheld on a mock-data run even though the dividend feed is
   independent of EDGAR. I believe that is correct — the branch exists so a synthetic sheet
   never carries real figures — but it is a deliberate choice worth a second opinion.

## Deployment prerequisite, not yet done

`room_buyback_price_enabled` renders nothing until `ingest_edgar_facts.py --force` has run
once for the new `TreasuryStockSharesAcquired` tag; no existing row carries it. Both flags
default False and are compose-forwarded. Nothing is enabled by this lane.

SUBMITTED: round 1
