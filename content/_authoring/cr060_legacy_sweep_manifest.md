# CR060 legacy sweep — running manifest (unsourced curriculum)

**Owner:** Claude (CR060). **Internal-only.** The 285 legacy lessons carry **no `sources:`**. This
sweep, per wave, has each unsourced lesson's reputable source **discovered and verified in one
pass** (never blindly assigned then rubber-stamped — that's the fabrication trap CR060 exists to
prevent): an agent reads the lesson, finds the reputable source that actually backs its claims,
verifies every claim/quiz against it with live web retrieval, and the passes get an adversarial
refute. Verdicts accumulate here.

**Verdict key:** `VERIFIED` (claims check out + a real source backs them → ready to stamp) ·
`NO_SOURCE_NEEDED` (pure AMI pedagogy/process, no external factual claim) · `FINDING` (a real error
— handed to the education lane, not fixed by CR060) · `ESCALATE` (legal/Sharia → human sign-off).

---

## Wave 1 — foundations (CORE) + news_macro (N&M), 35 lessons · 2026-07-22

**Result: 8 VERIFIED · 27 FINDING · 0 NO_SOURCE_NEEDED · 0 ESCALATE.** Design validated (44 agents,
0 connection deaths; found real SEC-filing/S&P-DJI/Cboe sources AND caught real errors).

**Measured defect rate: 27/35 = 77%** — do not extrapolate to the remaining 250 as fact; each wave
measures its own. But the pattern is stark and consistent.

**Dominant failure class — confabulated precise market history.** The 8 clean lessons are the
*definitional* ones (what a stock/market/brokerage is, order types, investing vs trading). Almost
every FINDING is a *data-dense worked example* citing specific index levels, ETF prices, dates, or
sector-return tables that are **confidently wrong against the real record** — e.g. dates landing on
**market holidays** (Feb 21 2022, 30 Jan 2019), a ticker error (**PBBANK** not "(PUBLIC)"), a wrong
regulator (**SAMA→CMA**), a misattributed quote (**"voting/weighing machine" is Graham, not
Buffett**), close-vs-intraday figures inverted, ETF levels off ~2× (XLK "$240" vs actual ~$117),
and inverted sector-leader tables. This is the CR046 class (numbers must be computed/sourced, not
hand-authored) applied to lesson prose. The data-heavy `news_macro` track was hit 18/19.

### Verdicts

| Code | Lesson | Verdict | # | Discovered source (VERIFIED) / defect + fix (FINDING) |
|---|---|---|---|---|
| CORE 1 | `001_what_is_a_stock` | VERIFIED | 0 | Apple Form 10-Q (SEC) shares+dividend; Bursa/Maybank issued shares; Bodie-Kane-Marcus (residual equity claim) — lesson's ~15B/~$1/12B are valid roundings; quizzes correct |
| CORE 2 | `002_why_companies_issue_shares` | FINDING | 3 | Amazon had **FOUR** splits not "two"; "AMZN ~$180 by 2026" is ~$247; Quiz1 "$5" wrong (fair-value raise leaves ~$10 not halved) |
| CORE 3 | `003_what_is_a_stock_exchange` | FINDING | 1 | "halt if a stock drops 7%" — 7/13/20% are **market-wide** S&P 500 circuit breakers; single-stock halt is LULD ±5% |
| CORE 4 | `004_us_markets_vs_bursa_malaysia` | FINDING | 3 | Public Bank ticker **PBBANK** not "(PUBLIC)"; Bursa is ~0.6–0.8% of US not "~2%"; US cap ~$65T not "$55T" |
| CORE 5 | `005_what_moves_stock_prices` | FINDING | 1 | NVDA "opened up 16%" — +16.4% was the **close** (opened ~11%) |
| CORE 6 | `006_what_is_volatility` | FINDING | 1 | "VIX touched 82, highest ever" — 82.69 was the record **close**; highest ever 89.53 intraday (2008-10-24) |
| CORE 7 | `007_investing_vs_trading` | VERIFIED | 0 | Nasdaq — MSFT daily closes (Jan-23 $240.95 → Jan-25 $410.19 = +70.2%); quizzes correct |
| CORE 8 | `008_time_horizon_and_goals` | VERIFIED | 0 | S&P DJI — S&P 500 perf + drawdowns; SPY 2022 TR −18.17%; Nasdaq NVDA vol >30% |
| CORE 9 | `009_risk_profile_basics` | VERIFIED | 0 | S&P DJI — S&P 500 closing levels 2018–19; SPY daily prices; SPY 2019 return |
| CORE 10 | `010_compounding_vs_active_trading` | FINDING | 2 | ">80% generated after year 15" is 68.5% (>80% only after ~yr 9); "8%≈long-term avg w/ dividends" understates ~10% nominal |
| CORE 11 | `011_long_term_wealth_building` | FINDING | 1 | Maybank "RM5 in early 2005" is ~RM10–11 nominal; the 2× price claim is wrong (return is dividend-driven) |
| CORE 12 | `280_what_is_a_stock` | VERIFIED | 0 | Apple Form 10-Q (SEC) shares issued+outstanding; Bodie-Kane-Marcus (equity vs debt) |
| CORE 13 | `281_what_is_a_market` | VERIFIED | 0 | U.S. SEC Investor.gov — Order Types (market vs limit); Bid/Ask & Spread |
| CORE 14 | `282_what_is_a_brokerage` | FINDING | 1 | Saudi securities regulator is **CMA**, not SAMA (SAMA is the central bank) |
| CORE 15 | `283_market_order_vs_limit` | VERIFIED | 0 | U.S. SEC Investor.gov — Understanding Order Types; Types of Orders |
| CORE 16 | `284_what_makes_a_price_move` | FINDING | 1 | "voting/weighing machine" misattributed to **Buffett** — it is **Graham** (Security Analysis, 1934) |
| N&M 1 | `059_bull_markets` | FINDING | 3 | 3,491 low was Oct-13 not 12; KLCI ~1,455 not 1,373 on 2023-12-11; "10.3% intraday" is the closing figure |
| N&M 2 | `060_bear_markets` | FINDING | 5 | Feb-21-2022 was a **market holiday**; XLK ~$88/$58 not 177/112; KLCI Jan-5-22 =1,548 not 1,624 |
| N&M 3 | `061_sideways_range_markets` | FINDING | 3 | XLF range/break example false (crossed $35 Nov'23); KLCI H1'23 example wrong |
| N&M 4 | `062_volatility_regimes` | FINDING | 1 | "VIX<15 for 47 of 65 days" → 45 of 67 (19-Jun a holiday); Oct-22 "30 consec >25" is ~37 |
| N&M 5 | `063_sector_rotation` | FINDING | 2 | "XLK peaked $240.50" — actual ~$117.41 (~2×); 10Y "4.05%→3.55%" wrong (hit 4.05% only Mar-2-23) |
| N&M 6 | `064_market_breadth` | FINDING | 2 | Both dated case studies **inverted** vs the record (Q1-24 was broadening; Dec-24 had a record neg-breadth streak) |
| N&M 7 | `242_late_bull_warning_signs` | FINDING | 4 | 200-SMA break dated to Feb-21-2022 (**holiday**); AAII +30 contradicts ~+12; some stats uncorroborable |
| N&M 8 | `243_this_time_is_different_trap` | FINDING | 1 | ARKK ATH $159.70 was 2021-02-16 intraday, not Feb-12 |
| N&M 9 | `244_bear_market_rallies` | FINDING | 6 | SPX 4,305 topped **below** the 200-SMA not above; Nasdaq 30-Sep =10,575.62/−19.4% not 10,213/−22.2%; +VIX/date errors |
| N&M 10 | `245_panic_vs_capitulation` | FINDING | 1 | "90%+ up-volume reversal on 14 Oct 2022" — SPX **fell** 2.37% that day; the up-day was Oct-13 |
| N&M 11 | `246_range_bound_asset_rotation` | FINDING | 4 | 2023 relative-return figures all wrong for the stated window (recompute XLK/XLF/XLE vs SPY) |
| N&M 12 | `247_volatility_compression` | FINDING | 4 | 2023 peak 4,588 was Jul-31 not 27; Oct-27 close 4,117 not 4,217; −10.3% not 8.3%; VIX date off |
| N&M 13 | `248_vix_term_structure` | FINDING | 3 | 85.47 intraday high was 2020-03-18 not 16; "SPX bottomed two sessions after Dec-24-18" — bottomed **on** Dec-24; VIX9D mislabeled |
| N&M 14 | `249_vvix_and_iv_rv_divergence` | FINDING | 1 | "VIX spiked to 38.57" — that was the **close**; intraday spike ~65.73; "3.0% intraday" was the close |
| N&M 15 | `250_rate_sensitive_sectors_hiking_cutting` | FINDING | 4 | 10Y 2021-12-31 =1.52% not 1.78%; 2024-07-01 =4.48% not 4.36%; H2-24 sector leader table **inverted** |
| N&M 16 | `251_defensive_cyclical_geographic_rotation` | FINDING | 5 | 5,667 record close was Jul-16 not 11; XLP 2022 **sign flip** (−0.8% not +0.5%); ringgit did not gain 11% H2-24 |
| N&M 17 | `252_regime_change_realtime_vs_hindsight` | FINDING | 3 | "SPX reclaimed 200-SMA on 2019-01-30" — closed ~2.5% **below** it; reclaim was mid-Feb 2019 |
| N&M 18 | `253_mandate_adjustments_by_regime` | FINDING | 2 | Q4-24 "+5.9%" is +6.7%; bear-ex "−25.4% over Mar-14→Oct-12-22" mismatched (that range = −14.3%) |
| N&M 19 | `287_news_that_moves_markets` | VERIFIED | 0 | Federal Reserve — FOMC SEP (dot plot); Bodie-Kane-Marcus (semi-strong efficiency; earnings surprise) |

### Ready-to-apply sources for the 8 VERIFIED (pending the stamp decision)

`001` Apple 10-Q (SEC); Bursa/Maybank; Bodie-Kane-Marcus · `007` Nasdaq MSFT closes · `008` S&P DJI;
SPY fact sheet; Nasdaq NVDA · `009` S&P DJI 2018–19; SPY prices · `280` Apple 10-Q; Bodie-Kane-Marcus
· `281` SEC Investor.gov order types + spread · `283` SEC Investor.gov order types · `287` Fed FOMC
SEP; Bodie-Kane-Marcus.

## Remaining sweep scope

fundamentals_analysis 66 · technical_analysis 45 · edge_process 98 · risk_portfolio 16 ·
sentiment_behaviour 10 · + new-track stragglers (asset_classes 3, ethics_integrity 6, quant_methods
6). Plus the 9 empty-`sources:[]` asset-class lessons (303/305/306/307/308/309/310/313/314). Next
wave gated on the strategy decision (patch vs regenerate the data-dense examples).
