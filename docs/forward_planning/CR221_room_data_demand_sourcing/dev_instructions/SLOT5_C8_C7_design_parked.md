# CR221 slot 5 (C8 dividend-growth CAGR, C7 buyback average price) — SUPERSEDED

**Status: BUILT and merged, 2026-09-11, commit `b45bbda3`. This file is kept only as a record
of a parked design that was measured to be WRONG on both items. Do not build from it.**

The design below won a judge panel and read convincingly. Then the build measured it on live
feeds and two of its central choices turned out to produce false statements on the sheet. That is
the reason this file still exists: the parked reasoning is a useful example of a design that
survives review and does not survive measurement.

For what actually shipped, read **§7.12** of the CR doc. The tests are
`backend/tests/unit/test_cr221_c8_c7_capital_returns.py` (24 tests) and the producers are
`backend/app/services/dividend_growth.py` and `backend/app/services/buyback_price.py`.

---

## Where the parked design was wrong

### 1. C8's basis — the parked design would have printed a dividend cut that never happened

The parked design sums per-share payments **by calendar year of ex-date** and takes the CAGR of
those sums. The shipped implementation uses the **last declared rate of each year** instead, and
carries the calendar sums beside it as a secondary figure.

The measured case that forced the change is Realty Income. Its May 2024 ex-date slipped to
2024-06-03, so eleven ex-dates land in 2024 and thirteen in 2025. The calendar-year sums run:

| Year | Sum basis | Declared rate |
|---|---|---|
| 2023 | 3.062 | rising every month |
| 2024 | **2.872** | rising every month |
| 2025 | 3.490 | rising every month |

The sum basis falls 6% in 2024 and jumps 21% in 2025 for a payer whose declared rate rose every
single month. Sum-basis CAGR reads 5.90% against the rate basis's true 2.25%. An analyst reading
that sheet would see a monthly payer that cut and then surged, and nothing on the line would tell
them the cut was a calendar artefact.

The parked design's **cadence guard** — "walk back while the payment count per year is constant"
— was an attempt to catch exactly this, and it is not sufficient. It rejects the series outright
rather than reporting it correctly, so a monthly payer with one slipped ex-date gets no dividend
growth line at all instead of the true one. The shipped version reports the rate series and
discloses the uneven count (`payments per year 2024 11`) rather than refusing.

### 2. C7's window — the parked design's staleness rules do not require contiguity

The parked design takes "the last four paired quarters ending <= as_of under `ttm`'s own
staleness rules (newest <= 200 days old, span <= 430 days)". Those bounds admit a
**non-contiguous** window, which is `edgar_pit.ttm()`'s own documented hazard arriving through a
second series: four paired quarters with a hole in the middle sum a multi-year total and get
labelled trailing-twelve-month.

The shipped version requires the four quarters to abut (a week's slack) **and** to span 330 to
400 days. Both guards are load-bearing and neither subsumes the other: the upstream filter keeps
periods of 70 to 100 days, so four contiguous ones span between about 256 and 418 days, and four
with a one-month hole can span 395 days and still be wrong.

### 3. Both parked probe figures are wrong, and one is wrong by 60%

| Figure | Parked | Shipped, measured |
|---|---|---|
| CAT C8 series | calendar sums 4.28 … 5.84, "8.1% CAGR" | declared rate 1.11 … 1.51, **8.00% CAGR** (the sums are correct as the *secondary* figure) |
| CAT C7 price | **$410.45** over 17.6M shares | **$664.64** over 10,869,082 shares |

The parked C7 number rests on a **hand-built YTD shares series**, which the file states plainly.
The real `TreasuryStockSharesAcquired` ingest gives 10.9M shares for that window, not 17.6M. The
parked $410.45 is below CAT's own 52-week low of $386.02 only by a little, so it would not have
looked obviously wrong on the sheet — which is the point.

### 4. The line labels changed

The parked labels are "Dividend growth history" and a C7 line placed "against the sheet's live
`base_price`". Shipped labels are **"Dividend growth (declared rate, by year)"** and **"Buyback
average price (implied)"**, because the basis belongs in the label where a reader cannot miss it.

---

## What the parked design got right, and the build kept

- Two flags, two field-state keys, two pure producers, one new EDGAR tag — the `aff954b6`
  convention, adopted unchanged.
- `BUYBACK_SHARES = ("TreasuryStockSharesAcquired",)` unioned into `INGEST_TAGS_US_GAAP`, and the
  correct observation that **Alpha needs `ingest_edgar_facts.py --force`** because a non-force run
  skips every stored ticker. That prerequisite is real and still outstanding on Alpha.
- Pairing both legs from the EDGAR store at one `as_of`, never EDGAR shares over yfinance
  dollars — the B2/DEF400 basis-mismatch shape.
- Excluding specials by a structural rule (a payment above 3× the median of its year and
  neighbours), and the insight that a genuine step-up must survive that filter. Both shipped, and
  GE's 4.4× 2024 raise is the test case.
- Labelling C7 as AMI's own quotient of two filed figures, never a company-reported average
  price.
- The `_ALLOWLISTED_DENIALS` runtime-deference entry for the persona's new "not supplied" clause.

---

## Original parked design, verbatim below this line

Everything below was written before the build and is preserved unedited. **Its C8 basis and C7
window are the two errors described above.** Read it as a historical artefact.

---

# CR221 slot 5 (C8 dividend-growth CAGR, C7 buyback average price) — design, parked

**Status: NOT BUILT.** This is the design and the live probe output from a build stream that was
cut off by a session limit on 2026-09-11 before its builder ran. It is parked here rather than
discarded because the probe figures are real and the structural rules were derived from them.
Whoever builds slot 5 starts here and re-verifies every number before shipping any of it.

Two register items, one slot: **C8** historical dividend growth CAGR (3 lines / 3 agents) and
**C7** buyback average execution price (1 line / 1 agent). CR221 §5 routes C8 through decision 9
(`DividendPayment` history, CR206, already fetched) and C7 through decision 8
(`TreasuryStockSharesAcquired` ÷ R35's repurchase dollars).

## The design that won the judge panel

**Approach:** minimal — two flags, two state keys, two pure producers, one new EDGAR tag

Mirror aff954b6 with the smallest surface that keeps every CR221 property. C8 (dividend growth history) reads the CR206 feed that the options desk already fetches — `get_market_data_provider().dividend_history(ticker)` — through a new pure resolver `resolve_dividend_growth(payments, today)` that sums per-share payments by CALENDAR YEAR OF EX-DATE (the feed has no fiscal-year, pay-date or special flag), excludes specials by a stated structural rule (a payment > 3x the median of all payments in its year and the two neighbouring years), drops the current partial year, walks back from the last complete year while the payment count per year is constant (cadence guard: CAT's 2012 n=5 / 2013 n=3 pull-forward would otherwise print a -30.65% cut), takes the longest such run up to 5 years, requires at least 3, and returns years, annual sums, first->last CAGR and "raised N of the last M years". Run on the 2026-09-11 probe series in this task: CAT 2021-2025 = (4.28, 4.62, 5.00, 5.42, 5.84), 8.1% CAGR, raised 4 of 4, no specials; COST 2021-2025 = (3.07, 3.49, 3.96, 4.50, 5.06), 13.3%, raised 4 of 4, the $15.00 special of 2023-12-27 named and excluded (a naive calendar sum gives 18.96 for 2023); the CAT 2012/2013 boundary shape, a 2-full-year payer, a suspended payer and [] all resolve to None; a semi-annual payer with a $10 special resolves with the special excluded (0.0%, raised 0 of 4); a genuine 2x step-up (0.70->1.40) is kept as regular (26.0% over 3 years, raised 1 of 3). The overlay `_overlay_dividend_growth` runs ONLY under the earnings block's gate (`settings.use_real_market_data and as_of is None` — three test fixtures patch the provider to objects with no `dividend_history`, and the as-of provider returns None by design), catches every exception including AttributeError, and sets `field_state["dividend_growth"]` on every path: LIVE only when a figure resolved; UNAVAILABLE for feed None (warn), [] non-payer (info — an outage is not a non-payer and vice versa), insufficient history (info with series depth), a raise (warn), mock mode and as-of runs. C7 (buyback average price) takes BOTH legs from the EDGAR store at one as_of (`today`), never EDGAR shares over yfinance dollars (the B2/DEF400 basis-mismatch shape 9da0be32 fixed): a new tag tuple `BUYBACK_SHARES = ("TreasuryStockSharesAcquired",)` in edgar_tags.py unioned into INGEST_TAGS_US_GAAP (verified absent today: not in the 45-tag registry, 0 rows in the measurement store; `KEEP_UNITS` already keeps `shares`, so the ingest script needs no code change but Alpha needs `ingest_edgar_facts.py --force` because non-force skips every stored ticker), a pure `resolve_buyback_price(facts, as_of)` that runs the existing `quarterly_series` on `edgar_tags.BUYBACKS` and on `BUYBACK_SHARES`, pairs quarters on EXACT (period_start, period_end) like `margin_trend_bps`, takes the last four paired quarters ending <= as_of under `ttm`'s own staleness rules (newest <= 200 days old, span <= 430 days), refuses unless all four carry dollars > 0 AND shares > 0, and returns sum-dollars / sum-shares with the four quarter ends and the window start. Run in this task on CAT's measured USD YTD facts (Q1'25 3,660 ... Q2'26 6,522 -> quarters 3,660/828/362/340/5,028/1,494, TTM $7,224M) plus a HAND-BUILT YTD shares series: $410.45 over 2025-07-01 -> 2026-06-30 ($7,224M / 17.6M shares); Deere-shaped (USD only) -> None; PIT as_of 2026-08-04 (before the Q2'26 10-Q) -> a different window ($402.33 ending 2026-03-31), so `filed <= as_of` holds. The overlay `_overlay_buyback_price` runs under the existing EDGAR gate beside `_overlay_filing_dimensions`, one `field_state["buyback_price"]` key on every path, `edgar_buyback_price_unreadable` warn on a raise, and the CR040 `tags_ever_ingested(BUYBACK_SHARES)` probe warning `edgar_buyback_price_tags_not_ingested` with `fix="re-run backend/scripts/ingest_edgar_facts.py --force"` when nothing resolved and the store holds the tag for no filer. Render: two line helpers in fundamentals.py in `debt_split_line` style (`_labelled`, (LIVE), figures + basis + dates, `live=False`, None when structurally absent), emitted in `_format_profile` only when BOTH the item's Settings flag AND `_is("<key>","live")` hold; C7 is labelled as AMI's own quotient of two filed figures (R20, `capital_return_line` precedent) and placed against the sheet's live `base_price` when that is live. Persona: three edits to fundamentals_analyst.md deferring to the two lines by their exact labels and adding (7)/(8) to the multi-period enumeration (otherwise the allowlisted "single point in time with no series behind it" sentence becomes a false denial the guard cannot see); the two new "not supplied" clauses are the only guard hits (verified against `_DENIAL_PATTERNS` in this task; zero `_COMPUTE_IMPLYING_PATTERNS` hits; zero collision-marker hits on either rendered line) and get `_ALLOWLISTED_DENIALS` runtime-deference entries exactly as A2 did. Nothing to retire: no persona sentence denies dividend growth or buyback price today. No refactors, no dependencies, docs/forward_planning/CR221_room_data_demand_sourcing/** untouched.

## Flags and field-state keys

- `room_dividend_growth_enabled: bool = False  ->  ROOM_DIVIDEND_GROWTH_ENABLED: ${ROOM_DIVIDEND_GROWTH_ENABLED:-false}  (CR221 C8)`
- `room_buyback_price_enabled: bool = False  ->  ROOM_BUYBACK_PRICE_ENABLED: ${ROOM_BUYBACK_PRICE_ENABLED:-false}  (CR221 C7; needs `ingest_edgar_facts.py --force` once on Alpha)`

Field-state keys: `dividend_growth`, `buyback_price` — one per item, the aff954b6 convention.

## Rendered lines, as measured in the probe

- CAT (probe series, run in this task): Dividend growth history (LIVE): 2021 $4.28 · 2022 $4.62 · 2023 $5.00 · 2024 $5.42 · 2025 $5.84 per share, 8.1% CAGR over 4 years, raised 4 of the last 4 years; AMI's own calendar-year sums of the per-share payments by ex-date, 4 payments each year, 2026 excluded as a partial year

- COST (probe series, run in this task): Dividend growth history (LIVE): 2021 $3.07 · 2022 $3.49 · 2023 $3.96 · 2024 $4.50 · 2025 $5.06 per share, 13.3% CAGR over 4 years, raised 4 of the last 4 years; AMI's own calendar-year sums of the per-share payments by ex-date, 4 payments each year, 2026 excluded as a partial year, one special excluded: $15.00 ex 2023-12-27
