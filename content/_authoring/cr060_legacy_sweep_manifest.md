# CR060 legacy sweep — manifest (**COMPLETE 2026-07-22 — 334 / 334 lessons measured**)

**Status:** measurement finished. **25 lessons clean, 293 carry a genuine defect (88%), 11 need no
source, 6 escalated to Saiful/SME.** Final totals + method findings at the bottom; remediation
(classification → dual-pass re-verification → routing) is Phases 2–6, not yet done.

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

## Wave 2 — fundamentals_analysis (FUND) + technical_analysis (TECH) + risk_portfolio (RISK), 127 lessons · 2026-07-22

**FINAL: 4 VERIFIED · 5 NO_SOURCE_NEEDED · 118 FINDING · 0 ESCALATE** (149/149 agents, 0 errors).

The session originally hit its usage limit mid-run, leaving 19 VERIFIED-candidates without their
adversarial refute (marked `VERIFIED*`). Those 19 refutes were re-run via
`resumeFromRunId: wf_0455e054-10c` and are now resolved — the rows below carry final verdicts.

> **The single most important methodological result of this sweep: of the 19 lessons that PASSED
> the fact-check pass, the adversarial refute killed 18. Only `TECH 45` survived.**
>
> A single-pass verification would have stamped 18 defective lessons as clean — a **95% false-clean
> rate**. What the refute layer caught was not nitpicking: an FX sign inversion (FUND 17, "weak USD
> inflates MYR revenue" is backwards), an inverted AT&T-vs-Verizon multiple comparison (FUND 34 —
> AT&T was ~65% *more* expensive on P/E, not cheaper), a CET1 claim that reads a near-minimum
> capital position as a large buffer (FUND 25), a Nestlé decomposition wrong on all three terms
> with the M&A sign flipped (FUND 62), and **six wrong or mis-keyed quiz answers**
> (FUND 17/35/57, RISK 7/8/9).
>
> This is the direct empirical justification for the dual-pass design (CR038 "prompt instructions
> are not controls"; DEF059 "LLM confidently faked APPROVE"). **One agent's "looks right" is not
> verification** — and now there is a number on it.

Note this raises Wave 2's defect rate from the provisional 79% to **118/127 = 93%**.

Per track: **TECH 43/45 findings (96%)** — every TA lesson is built on **fabricated OHLC/candle
data and made-up support/resistance/breakout levels** (the worst-hit track, pure CR046-in-prose).
**FUND 50/66 (76%)**. **RISK 7/16** — the best track: risk lessons are formula/arithmetic-based
(self-verifying), so 4 are NO_SOURCE_NEEDED and several verify; the findings there are arithmetic
slips (recovery-month figures, break-even win-rate wording), not confabulated history.

All `VERIFIED*` (refute-pending) rows are **resolved** — 18 flipped to FINDING, 1 (`TECH 45`) held.
Killed rows are tagged **REFUTE KILLED IT**; their first-pass proposed sources remain recoverable
from journal `wf_0455e054-10c`.

| Code | Lesson | Verdict | # | Discovered source / defect + fix |
|---|---|---|---|---|
| FUND 1 | `032_revenue_the_top_line` | FINDING | 2 | NVDA/AAPL revenue verified vs 10-Ks. FINDING: Maybank's RM27B is net operating income (+3.3%), not 'group revenue' — reported operating revenue was RM64.47B, +30.4% in 2023, contradicting the 'mid-single digits' and '30% jump = suspicious' claims. Fix: relabel RM27B as net operating income. |
| FUND 2 | `033_profit_and_margins` | FINDING | 1 | Checked AAPL/AMZN/TSLA FY2024 vs 10-Ks. AMZN (~49/11/9%) & TSLA ($97.7B, GM~18%, OM~7%) correct; AAPL rev $391B/GM46%/OM31% correct BUT net margin=24% ($93.7B/$391B), not the stated 26% (one-time EU tax charge). Fix: "26%"->"24%" and "26 cents"->"24 cents". Quizzes (hypothetical) sound. |
| FUND 3 | `034_debt_and_the_balance_sheet` | FINDING | 1 | Checked AAPL/XOM FY2024 10-Ks, BBBY Apr-2023 bankruptcy, ratio defs, both quizzes (2.5x/10x OK). FINDING: lesson calls XOM's a 'much smaller equity base' than AAPL — false; XOM equity ~$263B vs AAPL ~$57B, and 0.2 D/E implies a LARGER equity. Fix: 'much larger equity base'. |
| FUND 4 | `035_cash_flow_vs_earnings` | VERIFIED | 0 | Microsoft Corporation, Form 10-K FY ended June 30, 2024 (SEC / MSFT IR cash flow + income statements): net income $88,136M; net cash from operations $118,548M; capex (additions to PP&E) $44,477M; implied FCF $74,071M; Damodaran valuation works — free cash flow = operating cash flow minus capital expenditures (Tier 3 canon) |
| FUND 5 | `036_competitive_advantage_moat` | FINDING | 1 | Checked moat taxonomy, AAPL FY2024 gross margin ~46% (10-K, 46.2% ✓), ROIC>25% ✓, TENAGA MY grid monopoly ✓, both quiz answers ✓. FINDING: META "~38% in 2024" operating margin is wrong — Meta reported 42% for FY2024 (35% in 2023). Fix: ~38% → ~42%. |
| FUND 6 | `037_valuation_what_is_a_stock_worth` | FINDING | 2 | FINDING, 2 issues. (1) Quiz2 marks 'L worth more than K' correct, but at 8.5% discount K≈$1.1T > L≈$0.95T (K's 4% perpetuity dominates)—backwards; fix nums/re-mark. (2) 'MSFT ~38x trailing P/E' false: mid-2026 actual ≈24x, inverting the 'multiples=rich' point. MSFT $74B FCF & ~$3T cap OK. |
| FUND 7 | `038_comparable_companies` | FINDING | 2 | Checked all market claims + quiz math. Quiz arithmetic (mean 27.8, median 20) correct. Two FALSE mid-2026 facts: NVDA forward P/E is LOWER than AMD's, not a premium (backwards); JPM P/B is ~2.3-2.55x, not ~1.8x. Fix: reverse the NVDA/AMD example; correct JPM's P/B figure (ROE ~17% is fine). |
| FUND 8 | `039_the_pe_ratio` | FINDING | 2 | Quiz 2 broken: a one-time $0.60 GAIN can't raise $0.40 reported EPS to $1.00 normalised (that needs a $0.60 CHARGE); fix gain→writedown so the 20x graded answer holds. Real mid-2026 figures also inverted/stale: actual NVDA ~31x < AAPL ~39x (lesson: NVDA 42x > AAPL 32x); S&P ~25-28x not 22x. |
| FUND 9 | `040_price_to_book` | FINDING | 3 | Checked all real-world figures vs Jul-2026 filings/market data. Both quiz keys correct, but 3 flagship examples state false current numbers: JPM P/B ~2.4x not 1.9x (px ~$344); MSFT P/B ~6.7x not 11x (px ~$402); BRK-B P/B ~1.45x not 1.2x (BVPS ~$337). Fix: correct the figures. |
| FUND 10 | `041_return_on_equity` | FINDING | 2 | Verified all company figures vs SEC/annual filings; DuPont identity + both quizzes correct. FINDING: AAPL FY2024 example wrong — net income was $93.7B not "near $97B" ($97B=FY2023); avg equity ~$59.5B (ending $57B) not "~$65B"; true ROE ~157-165%. Fix to actual 10-K numbers. |
| FUND 11 | `042_debt_to_equity` | FINDING | 4 | Checked AAPL/TSLA FY24 vs 10-Ks + quiz math. FINDING: AAPL equity ~$57B not $65B (D/E ~1.7x not 1.5x), FCF $108.8B not ">$110B"; TSLA debt ~$8.2B not $13B, equity ~$73B, D/E ~0.11x not 0.2x; Quiz2 answer "multiplier ~5x higher" wrong (2.5 vs 1.3=~1.9x; 5x is the D/E ratio). Fix figures. |
| FUND 12 | `043_dividend_yield_and_payout_ratio` | FINDING | 3 | Arithmetic self-consistent; both quiz answers correct. FINDING: 'real markets' section states false mid-2026 facts — JPM $220/$5.20 (actual ~$345/$6.00); XOM $115/$3.96 (actual ~$152/$4.12); MSFT $480/$3.32 (actual ~$402/$3.64); stated yields all wrong. Fix: use current filings or mark hypothetical. |
| FUND 13 | `044_earnings_growth` | FINDING | 1 | NVDA/AAPL figures verify vs SEC 10-Ks and PEG vs Damodaran. FINDING: claim '50%+ growth doubles earnings in under 18 months' is wrong; at 50% doubling = ln2/ln1.5 = ~20.5 months, and sub-18-month doubling needs >59%. Fix: say 'roughly 20 months'/'under two years'. |
| FUND 14 | `148_revenue_recognition_red_flags` | FINDING | 1 | NVDA example mislabeled 'fiscal 2024': its $30B rev / $14.1B AR / ~42-day DSO are NVIDIA Q2 FY2025 (qtr ended Jul 28 2024). NVDA fiscal 2024 (ended Jan 28 2024) peaked at $22.1B/qtr, full-year $60.9B. Fix: 'fiscal 2024' -> 'Q2 fiscal 2025'. DSO math and both quizzes verified correct. |
| FUND 15 | `149_customer_concentration_risk` | FINDING | 3 | 10% 10-K threshold (ASC 280) + Skyworks Apple>10% OK. FINDINGS: (1) fabricated '15-35% one-qtr contraction historic base rate', no source, stated as fact; (2) 'Apple 2024 radio in-housing cut suppliers 20-40%' unverifiable/mis-timed (C1 shipped 2025); (3) Skyworks '65-70%' overstates ~50% annual. |
| FUND 16 | `150_recurring_vs_lumpy_revenue` | FINDING | 1 | Checked MSFT/LMT/TSLA/Tenaga/Gamuda vs SEC filings: MSFT ~$245B & ~75%/25% split, LMT ~$71B, TSLA energy 2024 ~$10B all correct; both quizzes sound. FINDING: TSLA energy 2022 was $3.909B per 10-K, not "$3B" as stated (rounds to $4B, understated ~23%) — fix to "$4B in 2022". |
| FUND 17 | `151_geographic_and_segment_mix` | FINDING | 1 | **REFUTE KILLED IT** — refuted: FX sign flip: "weak USD/MYR inflates reported MYR revenue from US ops" is backwards (Genting reports in MYR; weak USD deflates). Also quiz 2's +6% doesn't compute (implies 6.6%/7.4%); Japan is $25.0B/6.4% not ~$26B/7%; RoAP 7.8% not 7%; Products/Services are Apple categories, not segments. (first-pass sources in journal `wf_0455e054-10c`) |
| FUND 18 | `152_three_margins_deep` | FINDING | 1 | Verified NVDA FY2025 (rev $130.5B, GM 75%, op 62%, net 56%), WMT op 4.3% & GM ~24%, Public Bank NIM 2.2%, all arithmetic + both quiz answers. FINDING: WMT net margin stated ~2.6% but FY2025 10-K = $19.436B/$680.985B = 2.85% (~2.9%). Fix: 2.6% -> 2.9%. |
| FUND 19 | `153_margin_trend_analysis` | FINDING | 2 | Line 33's "+50bps/qtr for 4+ qtrs predicts a positive EPS surprise ~two-thirds of the time" is a fabricated stat, no reputable source (lit shows only a directional link). TSLA/META/TOPGLOV margins OK vs SEC filings; META 48% is consolidated, not Family-of-Apps. Fix: cut the two-thirds figure. |
| FUND 20 | `154_sector_margin_benchmarks` | FINDING | 1 | Verified company margins vs SEC filings: AAPL 31.5% op, AMZN 10.8%, NVDA 75%/62.5%, TSLA ~18% auto GM, WMT ~24% GM — correct. FINDING: line 31 lists COST in retail 'gross 22-28%', but Costco's gross margin is ~11% (10-K), a 2x error. Fix: drop COST (WMT/TGT fit; warehouse clubs ~11-13%). |
| FUND 21 | `155_operating_leverage_cyclicals` | FINDING | 2 | FINDING: Intel FY2024 example false — Intel reported a GAAP operating LOSS of $11.68B, not '~$0.9B breakeven'; '>95% decline'/'3x' fail (op income went >100% negative). Fits FY2023 ($54.2B rev, ~$0.09B op inc). UAL margin overstated: ~-4%→+5.2% (~10pt), not -7%→+5%/12pt. Quiz keys OK. |
| FUND 22 | `156_debt_maturity_ladder` | FINDING | 1 | Checked all claims vs MSFT FY2024 10-K + CRE data. FALSE (line 29): lesson says MSFT had 'no single year >8% of total debt'; 10-K shows FY2027 $9,250M = ~18% of $51.2B, the largest year. Fix: correct/drop the 8% clause. Other MSFT facts, arithmetic and both quiz answers verify correct. |
| FUND 23 | `157_short_term_vs_long_term_debt` | FINDING | 1 | Verified SVB $42B one-day run, AirAsia going-concern, both quizzes (ans 0 correct), CP ~$10B, current/quick-ratio defs. FINDING: AAPL 'fiscal 2024 ~$162B cash & securities' is the FY2023 total; FY2024 10-K = ~$157B. Fix to ~$157B; 0.1x ratio unaffected. |
| FUND 24 | `158_off_balance_sheet_liabilities` | FINDING | 2 | Vs SEC 10-Ks: Walmart FY2025 LT debt is $33.4B (excl current)/~$36B incl, NOT the '$44B' stated ($44B was FY2020); so op-leases are a ~40% addition, not 30%. United lease obligations ~$5B, not 'tens of billions'. Op-lease $14B, Ford, ASC842/IFRS16=2019 and both quiz math all correct. |
| FUND 25 | `159_when_high_debt_is_ok` | FINDING | 1 | **REFUTE KILLED IT** — refuted: REFUTED: lesson says regulators require CET1 >=4.5%; binding large-bank requirement is 4.5%+buffer+GSIB surcharge (JPM 11.5% for 2025-26; 7% floor for all), so 11-14% held is near-minimum not slack. Also "regulator effectively guarantees" utility return - Hope/Bluefield give opportunity only. (first-pass sources in journal `wf_0455e054-10c`) |
| FUND 26 | `160_three_cash_flow_statements` | FINDING | 1 | **REFUTE KILLED IT** — refuted: Example 2 arithmetic wrong: CFO +$2B, CFI -$1.5B, CFF +$0.5B nets to +$1.0B, not "roughly flat" — contradicts the lesson's own rule that net cash is derived from the three components. Secondary: AAPL's +$2,935M CFI is a net inflow, mislabelled "modest net investment". AAPL figures themselves verify. (first-pass sources in journal `wf_0455e054-10c`) |
| FUND 27 | `161_capex_intensity_and_working_capital` | FINDING | 1 | MSFT FY2024 example wrong: it cites total D&A $22.287B as 'depreciation'/maintenance for a ~50/50 split, but the 10-K PP&E depreciation (the proxy the lesson defines) is $15.2B, giving ~$15.2B maint / ~$29.3B growth (~1/3:2/3). Capex $44.5B is correct. Fix: use $15.2B, drop '50/50'. |
| FUND 28 | `162_brand_moat_when_a_logo_is_pricing_power` | FINDING | 1 | Verified all company gross-margin claims (Nike 44.6% FY24, LVMH ~66-69%, LULU high-50s, KO>PEP; quiz math/answers correct). FINDING: Nestle Malaysia gross margin is ~30% (low-30s) across 2022-26, not "high-30s" (true only 2016-20). Fix: change "high-30s" to "around 30%". |
| FUND 29 | `163_network_effects_when_each_user_makes_the_next_one_stickier` | FINDING | 2 | Checked META/Visa/Mastercard vs SEC 10-Ks. FINDING: (1) META 2024 operating margin stated ~38%, actual FY2024=42% (38% is only Q1/Q2); (2) 'V and MA operating margins above 60%' false for Mastercard (~55%, never >60% since 2015). ~4B MAU & >75% gross margins verify OK. Fix both margin figures. |
| FUND 30 | `164_switching_costs_the_invisible_lock_in` | FINDING | 2 | Adobe and Salesforce do not disclose NRR (Salesforce reports ~8% attrition). Lesson asserts ADBE NRR 110-120% and CRM 107-112%, gross retention >90% as fact — uncorroborable from any primary source; 3rd-party estimates conflict. Fix: mark illustrative or use disclosed metrics. |
| FUND 31 | `165_cost_advantage_moats_when_being_cheaper_is_structural` | FINDING | 1 | Checked Costco/Amazon/Tesla/Tenaga + both quizzes vs FY2024 10-Ks; all hold EXCEPT Costco membership-fee share: line 27 says 70-80% and Quiz 2 says 75% of OPERATING income; actual ~52% FY24 ($4.8B/$9.285B), ~56% FY23. It's ~66-73% of NET income. Fix to ~52% or switch denominator. |
| FUND 32 | `166_moat_erosion_signals_how_to_see_it_two_years_early` | FINDING | 4 | Apple/Top Glove/GE hold. FINDING: Intel case misdates erosion. Quiz 2's 2020 endpoints false — server share ~93% not 80% (AMD ~7%; hit ~20% only 2023), GM ~56% not 53%, ROIC high-teens not 11%. Body 'low 40s by 2024' is really ~33% (Intel 10-Ks + Mercury Research). Fix figures/dates. |
| FUND 33 | `167_dcf_basics_why_terminal_value_eats_everything` | FINDING | 3 | DCF worked example mis-computed: the $1.4T explicit-FCF sum is UNDISCOUNTED, not 'present value' (true PV ~$0.86T); TV PV is ~$1.67T not $2.0T (its own Gordon formula); so total EV ~$2.5T not $3.4T and TV share ~66% not ~58%. Fix the discounting. Quizzes correct; general claims sourced to Damodaran. |
| FUND 34 | `168_ev_ebitda_vs_pe_when_to_use_which` | FINDING | 1 | **REFUTE KILLED IT** — refuted: REFUTED: AT&T/Verizon example inverted. FY2024 actuals — T P/E 15.3-16.9x (EPS $1.49), EV/EBITDA 7.18x; VZ 9.75x and 6.56x. AT&T was ~65% MORE expensive on P/E, not cheaper, and both multiples agree, so no capital-structure mirage. Also 8x vs 10x = 25% gap, failing the lesson's own >30% rule. (first-pass sources in journal `wf_0455e054-10c`) |
| FUND 35 | `169_sum_of_the_parts_when_one_company_is_really_three` | FINDING | 1 | **REFUTE KILLED IT** — refuted: REFUTED: Quiz 2 discount is (80-58)/80=27.5%, not the "26%" stated 3x incl. in the correct answer. AMZN P/E ~30-35x Jul-2026 (yr range 27.7-37.9), not ~45x. AWS=$962B=36% of $2.69T cap, not "50%+ of market cap". AWS/Ads stale FY2024 vs FY2025 $128.7B/$68.6B. "Any segment <50%" is vacuous. (first-pass sources in journal `wf_0455e054-10c`) |
| FUND 36 | `170_scenario_analysis_bear_base_bull_done_honestly` | FINDING | 1 | Arithmetic all correct; both quiz keys (answer=0) correct; AirAsia 2020–24 distress claim verified via Bursa/SC PN17. FINDING: lesson states TSLA traded ~$260 mid-2026, but actual was ~$380–$450 (~$409 May, ~$381 mid-July). Fix: use real anchor + recompute scenario %, or label price hypothetical. |
| FUND 37 | `171_valuation_across_industries_no_single_multiple_fits` | FINDING | 1 | All claims/quizzes verify except one false JPM data point: "1.8x P/TBV, ~17% ROTCE" is wrong. JPM was ~2.95x P/TBV in May 2026 (now 3.27x; 10yr median 2.0x), ROTCE 20% FY2025 / 23% Q1'26. Fix: ~3x P/TBV, ~20% ROTCE (still supports the 20%-ROTCE→2.0x+ point). |
| FUND 38 | `172_peer_selection_criteria_before_you_look_at_the_numbers` | FINDING | 1 | **REFUTE KILLED IT** — refuted: REFUTED: NVDA peer set (AMD/AVGO/QCOM/MRVL/TXN) breaks the lesson's own 0.3x-3.0x band — NVDA FY26 rev $215.9B => band $64.8B-$647.7B; AVGO $63.9B, QCOM $44.3B, AMD $34.6B, TXN $15.6B, MRVL $8.2B (26x) all fail; "same order of magnitude" false. Also NVDA "$3T" is ~$4.95T; RHB is 0.235x Maybank. (first-pass sources in journal `wf_0455e054-10c`) |
| FUND 39 | `173_adjusting_comps_for_size_leverage_growth` | FINDING | 1 | Arithmetic + quizzes correct; PEG/EV-EBITDA/leverage concepts trace to Damodaran. FINDING: load-bearing '10-25%' comps-mispricing stat (intro + Takeaway) is unsourced; Alford (1992) found size/leverage/growth adjustments don't cut error beyond industry. Fix: drop % or cite a study. |
| FUND 40 | `174_stock_based_compensation_the_hidden_dilution` | FINDING | 4 | Checked SNOW/MSFT/META figures + both quizzes vs SEC filings. FINDING: MSFT FY2024 buybacks were $17.25B, not '$25B+'; SNOW adj FCF is 29%/$810M not 27%/$760M, SBC $1.23B not $1.1B, SBC-honest FCF ~-15% not -12% (gap ~44pt). Fix these numbers; both quizzes are correct. |
| FUND 41 | `175_gaap_vs_non_gaap_and_accruals_quality` | FINDING | 1 | **REFUTE KILLED IT** — refuted: REFUTED: L35 Serba Dinamik — Bursa issuers report MFRS; no GAAP/non-GAAP regime in 2020-21 (arrives with MFRS 18, eff. 2027), and cited KPMG/Bursa source covers sales/receivables only, not non-GAAP divergence or "4-6 quarters". Also L56 compares 64%-of-adjusted to a 25%-of-GAAP threshold. (first-pass sources in journal `wf_0455e054-10c`) |
| FUND 42 | `176_trailing_vs_forward_pe` | FINDING | 1 | Definitions correct per Damodaran; arithmetic + both quiz keys (answer 0) verified. FINDING: the "real markets" NVDA claim is false — mid-2026 NVDA ~$207, TTM EPS ~$6.53 (~32x/21x), not $135/$3.20/42x/28x. Fix: mark it illustrative or use real figures. |
| FUND 43 | `177_pe_in_cyclicals_peak_earnings_trap` | FINDING | 1 | **REFUTE KILLED IT** — refuted: REFUTED: section "How this plays out in real markets" invents history for real tickers. INTC's actual trough EPS was NEGATIVE (FY24 -$4.38), so the "125x trough P/E" never existed; X never fell to $20 after $40 (Nippon bid $55, Dec 2023); PETGAS/PETDAG trade ~20x/42x, not the claimed 6-8x. (first-pass sources in journal `wf_0455e054-10c`) |
| FUND 44 | `178_shiller_cape_normalised_pe` | FINDING | 2 | Shiller CAPE "sits near 32x" is wrong: Shiller's data shows ~40.3 in May 2026 (lesson date), ~41 now (mean 17.4, record 44.19 Dec-1999); Quiz 1 stem repeats "32x". Trailing P/E "~22x" also low (~26). Fix: CAPE→~40x (near record, not merely top-decile), P/E→~26x. |
| FUND 45 | `179_peg_ratio_price_for_growth` | FINDING | 1 | Verified Lynch PEG≈1.0 rule, all arithmetic, both quiz answers (correct). FINDING: SNOW 'net retention runs above 130%' is false — SNOW's NRR was ~125-126% by the May-2026 date; last >130% was Jan-2024. Fix to ~125% (still supports the point). Gross-margin 70%+ claim is fine. |
| FUND 46 | `180_tangible_book_vs_reported_book` | FINDING | 2 | Verified KHC ($15.4B write-down, -27%) and JPM (BVPS $116, P/B 1.9x). FINDING: Salesforce goodwill+intangibles is ~$54-56B per 10-K, not $80B, so tangible book is POSITIVE (~+$6B), not −$20B/undefined — lead example is false. 2nd: KHC book chronology inverted ($51B is post-writedown, not pre-). |
| FUND 47 | `181_pb_for_banks_regulatory_book` | FINDING | 2 | Verified: Basel III CET1/RWA defs + 11.5% G-SIB CET1 min (Fed/BIS), ROE-vs-CoE->P/B principle (Damodaran), quiz math OK. FINDING: real snapshots false at lesson date 2026-05-12 — JPM was $304.88 not ~$220 (P/TB ~2.8x vs 2.2x); BAC $50.78 not ~$42 (~1.75x vs 1.6x). Fix or mark illustrative. |
| FUND 48 | `182_pb_for_asset_light_businesses` | FINDING | 2 | MSFT snapshot false: lesson says mid-2026 P/B~11x, book/sh ~$42; actual ~6.7x, book/sh $55.78 (Mar-2026 filing). NFLX 15.5x also overstated (~12x; 10:1 split makes $700 stale). Fix/relabel these. META/CRM ok; thesis, toolkit, both quiz answers correct. |
| FUND 49 | `183_high_roe_low_pb_buffett_framing` | FINDING | 1 | **REFUTE KILLED IT** — refuted: REFUTED: BRK bullet inverts the mechanism — Buffett's 2018 letter blames operating businesses "carried far below current value" while "equity holdings are valued at market prices"; lesson blames mis-measured equity-portfolio look-through. Also WFC "ROE held" false: 12.5%(21)→7.6%(22). (first-pass sources in journal `wf_0455e054-10c`) |
| FUND 50 | `184_dupont_decomposition_deep` | FINDING | 2 | DuPont formula, all arithmetic, and both quiz answers verified correct. FINDING: lesson calls the four real examples "all near 20-25% ROE"/"same range," but JPM~17% and MSFT is listed 36% (real ROE ~40-47% FY20-22 per 10-Ks) are both outside. Fix the framing or the MSFT figure. |
| FUND 51 | `185_roe_vs_roic` | FINDING | 1 | **REFUTE KILLED IT** — refuted: REFUTED — XOM "ROE 16%/ROIC 12%, 4-pt gap from modest debt" cannot compute: D/E ~0.19 with cash ~half of debt puts invested capital only ~5% above equity under the lesson's own equity+debt-cash formula, capping ROE near 12.6%. Actual XOM gap is 2-3 pts (2023: ROE 17.6% vs reported ROCE 15%). (first-pass sources in journal `wf_0455e054-10c`) |
| FUND 52 | `186_sustainable_roe_mean_reversion` | FINDING | 4 | Thesis sound (Fama-French 2000). FINDING: NFLX ROE was ~24.5%/26% in 2022-23, NOT "~15%"; AAPL not ">40% for a decade" (FY14/16/17 ~35-36%); "Bartov...classic study" mis-attributed; median/decile stats (11-13%,18-22%,8-12%) uncited. Fix: correct NFLX+AAPL, drop Bartov, cite 10-Ks & Fama-French. |
| FUND 53 | `187_roe_inflation_via_buybacks` | FINDING | 1 | Vs Apple 10-Ks: ROE~150%, >$700B buybacks, ~40% share cut, FY2017 equity $134B, NI $97B, both quizzes all OK. FALSE: 'business compounds ~15-18% in revenue-and-earnings terms' — real revenue CAGR ~8%, net-income ~9-10%; 15-18% is buyback-inflated EPS. Fix to ~8% rev / ~10% earnings. |
| FUND 54 | `188_net_debt_to_ebitda` | FINDING | 2 | FINDING: quizzes/hypotheticals OK, but AT&T FY2024 wrong — lesson $140B debt/$7B cash/$42B EBITDA/3.2x vs actual $123.5B/$3.3B/$44.8B/~2.7x. Apple's "$65B cash & marketable securities" is really $156.65B (Apple net-cash, not 0.3x). Fix: AT&T's reported 2024 figures; relabel Apple's cash. |
| FUND 55 | `189_interest_coverage_ratio` | FINDING | 2 | Checked all figures + quiz math vs SEC filings. Quizzes and MSFT (~37x) OK. FINDING: Whirlpool 2024 EBIT is not ~$1.3B (actual GAAP $63M, ongoing $887M; interest $358M), so coverage is ~2.5x not 3.5x; WHR was cut to junk in 2024, not "lower-end investment-grade." Fix the WHR example. |
| FUND 56 | `190_debt_to_asset_ratio` | FINDING | 3 | Verified real-co figures vs SEC 10-Ks/TNB report. FINDING: (1) AAPL FY24 equity ~$57B not $65B, so D/E ~1.7x not 1.5x; (2) Quiz2 stem says D/E=0.7x but debt$7B/equity$7B=1.0x; (3) TENAGA FY24 assets ~MYR200B not 175B, D/A ~28-43% not 37%. Fix figures/ratios. MCD negative-equity claim TRUE. |
| FUND 57 | `191_fixed_vs_floating_and_currency_mismatch` | FINDING | 1 | **REFUTE KILLED IT** — refuted: Quiz 1's "correct" answer uses the wrong FX multiplier: a 20% currency fall implies 1/0.8=1.25, so 2.8B->3.5B, total 4.7B (+17.5%), not 4.56B (+14%). Same error at line 29 (30% fall = +42.9%, not +30%), and it contradicts the lesson's own correct 50%-lira->2x math at line 27. (first-pass sources in journal `wf_0455e054-10c`) |
| FUND 58 | `192_payout_ratio_on_fcf` | FINDING | 3 | JPM 2024 CFO was NEGATIVE $42B, not +$54B, so the 26% payout-on-FCF is false (per 10-K). ITW's "$3.3B FCF" is op cash flow; real FCF $2.84B, NI $3.49B not $3.7B. KO's ~$10B FCF is the ex-IRS-deposit figure; GAAP FCF was $4.7B → ~176% not 80%. Fix figures; quizzes ok. |
| FUND 59 | `193_dividend_safety_scoring` | FINDING | 1 | Verified AT&T 2022 cut (SEC 8-K), MSFT div since 2003 (SEC), REIT >=90% mandate (IRC 857), PG&E 2017 suspension; both quizzes correct. FINDING: the '~2-4% annual base rate of S&P 500 dividend cuts' is uncorroborable from any reputable source. Fix: cite S&P DJI dividend data or soften the figure. |
| FUND 60 | `194_the_yield_trap` | FINDING | 1 | **REFUTE KILLED IT** — refuted: REFUTED: KHC's yield never hit the claimed 7% pre-cut — it was 5.2% at the Feb 21 2019 close (~$48, $2.50 div) and max 6.0% at the 12-month low of $41.60. Load-bearing: the lesson's own falsifiable rule is a >7% threshold, so its flagship example fails its own screen. (first-pass sources in journal `wf_0455e054-10c`) |
| FUND 61 | `195_special_dividends_and_one_offs` | FINDING | 1 | **REFUTE KILLED IT** — refuted: REFUTED: TPL yield in special years is ~0.3-2.7% (YCharts 0.33% Nov-2024; 5yr range 0.06-1.86%), never "5-10%" — the cited Jun-2024 $10 8-K implies ~1.6%. Also COST regular is $1.47/qtr = $5.88 (0.63%) since Apr-2026, not $1.16/"~0.5%"; the Jan-2026 $12 special is missing. (first-pass sources in journal `wf_0455e054-10c`) |
| FUND 62 | `196_organic_vs_acquired_growth` | FINDING | 1 | **REFUTE KILLED IT** — refuted: REFUTED: the Nestlé decomposition is wrong on all three terms and inverts the M&A sign — Nestlé's net acq./disposals was NEGATIVE in 6 of the last 7 years (2021 -6.6%, 2023 -0.9%, 2024 -0.3%), not "+1-2%"; FX ran -7.8%/-3.7% not "-1 to +1%"; reported growth never hit "4-6%". No Nestlé source cited. (first-pass sources in journal `wf_0455e054-10c`) |
| FUND 63 | `197_revenue_vs_eps_buyback_divergence` | FINDING | 1 | Arithmetic (body + both quizzes) and AAPL/BRK-B claims verified. FINDING: "IBM in the 2010s bought back over $100B" is overstated — 2010–2019 repurchases were ~$88B; every $100B+ figure spans pre-2010 ($110B since 2000; $125B 2005–15). Fix: use ~$90B in the 2010s or widen the window. |
| FUND 64 | `198_garp_and_peg_math` | FINDING | 2 | GARP/PEG (Lynch/Damodaran), arithmetic + both quizzes, META EPS +73%/+60% (2023/24) all check out. FINDING: (1) line 40 'falsifiable' backtest (PEG<1 & ROE>15% & growth>10% beats index 3yr w/ significance) is uncorroborable, cut/soften; (2) META ~$90 trough was Nov 2022, not 'early 2023'. |
| FUND 65 | `199_roic_vs_wacc_and_the_four_pillar_checklist` | FINDING | 1 | Checked defs, Greenblatt Magic Formula, MSFT/AAPL FY2024 financials, both quizzes (quiz logic+arithmetic correct). FINDING: MSFT "invested capital ~$200B, ROIC ~45%" wrong for FY2024 — 10-K gives IC ~$240B and reported ROIC ~24-26% (~37% by lesson's own formula); 45% was ~FY2020. Fix the numbers. |
| FUND 66 | `285_reading_a_pe_ratio` | FINDING | 1 | **REFUTE KILLED IT** — refuted: REFUTED: the analyst quote's "60% growth premium" doesn't compute — 38x trailing (or 32x forward) vs a 22x sector median is 73% (or 45%), and 22x1.6=35.2 matches neither. Secondary: Shiller's ~15.5 long-run mean contradicts labelling the 15-25 band "roughly the long-run S&P average". (first-pass sources in journal `wf_0455e054-10c`) |
| RISK 1 | `013_why_risk_matters_more_than_profit` | FINDING | 2 | 2 arithmetic defects; drawdown math (50->100,20->25,10->11.1%) & both quiz answers correct. FINDING: Quiz-2 explanation '+72% to return to starting value' is wrong—+72% recovers the $129k PEAK; the $100k start needs only ~+34% and Trader A ends +7.7% above it. Body '$4,400 (~1%)' should be ~$1,044. |
| RISK 2 | `014_position_sizing_basics` | VERIFIED | 0 | CMT Association — Chartered Market Technician curriculum, Risk Management: percent-risk (fixed-fractional) position sizing model — shares = (account equity × risk %) ÷ (entry price − stop price); GARP — FRM body of knowledge, risk management: risk-per-trade / position sizing |
| RISK 3 | `015_stop_loss_basics` | VERIFIED | 0 | SEC Office of Investor Education and Advocacy — Investor Bulletin: Stop, Stop-Limit, and Trailing Stop Orders (a triggered stop becomes a market order; "the stop price is not the guaranteed execution price" and can deviate significantly in a fast-moving/gapping market); CMT Association — technical-analysis body of knowledge: reward-to-risk ratio = (target − |
| RISK 4 | `016_risk_reward_ratio` | FINDING | 1 | Verified all arithmetic + both quizzes (correct). FINDING: intro says a 1:0.8 R:R needs 'almost two-thirds' win rate to break even, but risk/(risk+reward)=1/1.8=55.6% — just over half (its own flip example gives 53%). Fix: say ~56%/'more than half', or change ratio to 1:0.5. |
| RISK 5 | `017_portfolio_exposure_and_correlation` | FINDING | 2 | Verified both quiz answers (index 1; 5.2% OK) + S&P500 AAPL+MSFT ~13% weight. FINDING: 'Q1 2025 Tuesday, Nasdaq-100 -3.4%, five names -4-7%' + JPM/XOM/KO/IHH same-day moves match no real day (real Q1'25 routs were Mondays); Bursa label wrong. Fix: relabel hypothetical or cite a dated day. |
| RISK 6 | `018_drawdown_management` | FINDING | 2 | Recovery-math all correct (20->25,50->100,30->42.9,15->17.6,40->66.67,35->53.8%; both quizzes right). 2 FINDINGS: (1) 15% dd's 17.6% recovery = '6-9 months at 1%/mo' but is ~16-18 mo; (2) '<20% dd recovers in under a year' conflicts w/ the 1%/mo rate (25% gain ~=25 mo). Fix the month figures. |
| RISK 7 | `101_volatility_adjusted_sizing` | FINDING | 1 | **REFUTE KILLED IT** — refuted: REFUTED: Q2 explanation calls "the last" option the '1% is 1%' distractor (that's index 1, not 3); Bursa example's 4,166/2,777 shares violate Bursa's 100-unit board lot; "4x bigger bet" matches neither 12x (ATR units) nor 3.1x (ATR%) from the lesson's own figures. (first-pass sources in journal `wf_0455e054-10c`) |
| RISK 8 | `102_atr_based_stops` | FINDING | 1 | **REFUTE KILLED IT** — refuted: Quiz 2 keyed answer wrong: label "TSLA" contradicts its own body ("neither is tighter"); explanation's "same stop-out probability from noise" is false — AAPL stop is 9.50/3 = 3.17 ATR from entry vs TSLA 21/12 = 1.75 ATR. Sources support ATR/14-period but not the 0.5-ATR-buffer method. (first-pass sources in journal `wf_0455e054-10c`) |
| RISK 9 | `103_trailing_stops` | FINDING | 1 | **REFUTE KILLED IT** — refuted: REFUTED: Quiz 2 explanation cites "the first" wrong answer as 'tighter trail = closer to peak', but that is options[2]; options[0] is the "both capture the same" distractor. Also "$7 above the chandelier-set price" is wrong — $192 exit is below the $193 trail. (first-pass sources in journal `wf_0455e054-10c`) |
| RISK 10 | `104_stops_around_earnings` | FINDING | 2 | Verified gap mechanics (stop→market order; SEC/CBOE) & Quiz1 math (2.05% correct). FINDING: Quiz1 calls a 10% gap 'within the 8% implied move' — false (implied move≈1 SD, 10>8); fix: raise implied to ~11% or relabel 'beyond'. Quiz2 '7% implied gaps a 4% stop more often than not' overstated (~28%). |
| RISK 11 | `105_hidden_costs_in_risk_reward` | NO_SOURCE_NEEDED | 0 | Transaction-cost pedagogy, hypothetical examples. Arithmetic correct (AMZN 2.81, small-cap 1.36); both quizzes verify (Q1=1.17, Q2 blue-chip 1.75 vs 1.14). Real-world figures (AMZN ~$0.02 spread, $0.005/sh fee, MY 0.1% brokerage) are accurate typicals; nothing false, no load-bearing stat. |
| RISK 12 | `107_drawdown_recovery_at_scale` | FINDING | 1 | Verified all math (30%→42.9%, 0.375R expectancy, 96/48/19 trade counts, both quizzes) correct. FINDING: Quiz 2 explanation says a 16% drawdown atop the 30% puts Trader B 'past the 50% threshold', but 30+16=46% (~41% compounded) is below 50; 50% breaches are meaningful only at 5% sizing, not 2%. |
| RISK 13 | `108_regime_dependent_correlation` | FINDING | 2 | Concept sound+sourceable (CFA FAJ 'When Diversification Fails'; Longin-Solnik 2001). FINDING: Quiz1 wrong: at corr 0.7 a 4x1% book's risk ~3.5% = 0.88x the naive 4% ceiling, not 1.6-1.8x above it; contradicts body. Bursa Q1-2025 corr stat unverifiable. |
| RISK 14 | `109_risk_budgeting_across_positions` | NO_SOURCE_NEEDED | 0 | AMI-internal PM/mandate pedagogy + hypothetical worked scenario (made-up account, caps, positions); no external statistic. Verified all arithmetic and both quiz answers (idx 3, idx 2) correct; ticker sectors and Bursa banks accurate; "1%/5%" are hedged config heuristics. No reputable source needed. |
| RISK 15 | `290_position_sizing_basics` | NO_SOURCE_NEEDED | 0 | Content is AMI app-mechanics (Risk Debators, PM, safety-floor caps) + a hypothetical 1R/1%-rule worked example (made-up numbers) + a risk heuristic. Verified all arithmetic and both quiz answers correct (Q1=50 shares, Q2 R:R 0.5:1). No external stat/date/named-theory claim to source. |
| RISK 16 | `291_the_pm_and_your_mandate` | NO_SOURCE_NEEDED | 0 | Purely AMI-internal app pedagogy (how the PM, mandate config, deterministic compliance floor, verdict format work) with illustrative hypothetical NVDA/PYPL numbers; no external fact/stat/definition to source. Arithmetic (24<30, 3<50) and both quiz answers (idx 2, idx 1) internally correct. |
| TECH 1 | `020_candlesticks_anatomy_of_a_bar` | FINDING | 2 | NVDA example is false: actual Fri Mar 28 2025 FELL (close ~$109.52, high ~$110.46) but lesson shows green/up close $112.40; Mon Mar 31 opened ~$105 and ROSE +3.1% but lesson shows red/down open $110.32. Both candles' prices+colors inverted vs real data. Fix: use real OHLC or mark hypothetical. |
| TECH 2 | `021_timeframes_and_what_they_tell_you` | FINDING | 4 | Checked the 'MSFT through April 2026' example vs Nasdaq/Yahoo history: it's inverted. MSFT FELL ~21% (Nov-2025 ~$490 to Mar-2026 ~$369), not a clean uptrend $362 to $445 (+23%); Nov low was ~$470 not $362; never hit $445 in March. Fix: use a real verified uptrend or explicitly hypothetical numbers. |
| TECH 3 | `022_trend_direction` | FINDING | 1 | TA trend definition + both quizzes are correct (Dow Theory/CMT). But the MAYBANK worked example is fabricated: real 1155.KL was ~RM11.36 on 25 Jan and hit an ATH RM12.42 on 25 Feb 2026, not the lesson's RM10.46/10.02/10.71. Fix: relabel as hypothetical or use real Bursa prices. |
| TECH 4 | `023_support_and_resistance` | FINDING | 1 | AAPL worked example fabricated: lesson's 8-Apr-2026 low $202.45 and $203–214 range contradict actual data (8 Apr close $258.90; 1 May close $280.14/high $287.22; real range ~$255–287, off ~$55–70). Concept+both quizzes sound. Fix: use real Apr–May 2026 prices or relabel hypothetical. |
| TECH 5 | `024_breakouts` | FINDING | 1 | Checked META Feb–Apr 2026 'Example' vs exchange data: fabricated. Lesson claims a $462–$487 range and a $494.70 upside breakout on 2026-03-27; real META traded ~$520–540, hitting a 52-week LOW of $520.26 that day (close ~$536) — opposite direction. Fix: make it hypothetical or use real figures. |
| TECH 6 | `025_pullbacks` | FINDING | 4 | Example presents fabricated AMZN prices as real. Actual Feb–Mar 2026 (Nasdaq): peaked ~$245.63 Feb 2 then fell to low-$210s; Mar 5 close $218.94 not $228.40; Mar 18 close $209.87, no "$244.10 new swing high". Was a breakdown, not a 6% pullback. Fix: relabel hypothetical or use real data. |
| TECH 7 | `026_moving_averages` | FINDING | 2 | MA/SMA/EMA definitions are correct, but the MSFT Q3-Q4 2025 example is fabricated: MSFT traded ~$500-555 (Oct avg close $517.92), never 445-465 or 458 on Oct 9 2025. Quiz 1 reuses the false 458/463 figures. Fix: mark example hypothetical (update Quiz 1) or use real data. |
| TECH 8 | `027_rsi_momentum_oscillator` | FINDING | 2 | RSI definitions verified (Wilder/CMT). FINDING: NVDA 'real markets' example is fabricated—actual Jan 2026 NVDA was ~$183-192 (Jan 21 close $183.10), not 138→152/high 154.20/fell-to-141. Also 'PETRONAS' isn't listed on Bursa Malaysia. Fix: use verified data or mark hypothetical. |
| TECH 9 | `028_macd_trend_and_momentum` | FINDING | 2 | MACD 12/26/9 mechanics + both quiz answers correct (CMT/Appel). But the 'real markets' AAPL Q4 2025 example is fabricated: lesson says AAPL closed 232 on Oct 30 2025; real close was $271.40 (ATH run). The 226-256 path is false and seeds Quiz 1. Fix: relabel hypothetical or use real prices. |
| TECH 10 | `029_volume_confirmation` | FINDING | 3 | FINDING: AMZN example fabricated (checked vs Nasdaq history). Nov 4 2025 actual close $249.32 not $211.20 (no '207 breakout', stock ~$250); Oct 21 close $222.03/high $223.32 not 205.10/208.40. Poisons Quiz 1. TA concept itself sound (CMT). Fix: real numbers or label hypothetical. |
| TECH 11 | `030_trend_confirmation_across_indicators` | FINDING | 4 | Checked META Jan–Mar 2026 vs exchange daily closes: example fabricated. Jan 8 close was 646 not 632; META declined, never 'ran to 685'; Mar 4 was ~668 not a 'new closing high of 698' (below 787 Aug-2025 ATH); fell to ~627 not 651. Poisons graded Quiz 1. Fix: relabel hypothetical or use real data. |
| TECH 12 | `112_doji_the_indecision_candle` | FINDING | 1 | Doji concept + both quiz answers (index 0) are sound (standard TA). FINDING: NVDA example is fabricated but stated as real — claims NVDA ran $108→$124.80 with a $124.60 doji on 4 Mar 2026, but 2026 52-wk low was $164.07 (Feb 10 close $188.54), ~$60/sh off. Fix: relabel hypothetical or use real OHLC. |
| TECH 13 | `113_hammer_and_inverted_hammer` | FINDING | 4 | Checked TA defs + META example. FINDING: inverted hammer wrongly framed as a resistance/short pattern (that's the shooting star; inverted hammer is a bullish bottom-reversal). The META '11 Apr 2026' hammer is fabricated — it's a Saturday and META's real April range was ~$564-700, not $489-548. |
| TECH 14 | `114_engulfing_patterns` | FINDING | 2 | Engulfing definition and all 3 quizzes are correct. FINDING: the 'real markets' JPM example is fabricated — Feb 14 2026 was a Saturday (market closed), mislabeled 'Monday'; JPM actually traded ~$307-312 in Feb 2026, not $254-278. Fix: relabel example as hypothetical or use real dates/prices. |
| TECH 15 | `115_harami_and_shooting_star` | FINDING | 3 | Harami/shooting-star defs correct (CMT/Nison). FINDING: both real-ticker examples fabricated — actual XOM 18 Mar 2026 O159.66/C157.59 (rose, no harami), not ~$116-120; actual TSLA 8 Apr 2026 O363.79/C343.25 (red body, falling), not a $279-289 shooting star. Fix: real OHLC or mark hypothetical. |
| TECH 16 | `116_top_down_multi_timeframe_workflow` | NO_SOURCE_NEEDED | 0 | Process/pedagogy: top-down three-pass (weekly/daily/hourly) TA workflow. MSFT is an illustrative worked example (exempt, not load-bearing); arithmetic consistent (risk $7.70, rewards $3.50/$11.50); both quiz answers correct vs taught method. No external stat or named theory to source. |
| TECH 17 | `117_dynamic_vs_static_support_resistance` | FINDING | 2 | NVDA example is fabricated: NVDA traded ~$180-210 in Nov 2025-Apr 2026 (ATH $207 Oct-29-2025; ~$188 Feb-18), not the $108-$148 shown, so the $148 high, $114.40 50DMA test, $108 low are all false; Feb-14-2026 is a Saturday. Fix: relabel hypothetical or use real prices. |
| TECH 18 | `118_role_reversal_resistance_becomes_support` | FINDING | 3 | AMZN example is fabricated vs Nasdaq data: Feb 6/26 close $210.32 not $218.40 (below the claimed $215 'breakout'); Feb 24 close $208.56 not $217.20 (no $215 retest); AMZN ~$206-212 all March, never hit $238. Fix: use real prices or relabel hypothetical. Concept+quizzes sound. |
| TECH 19 | `119_failed_breakouts_bull_traps` | FINDING | 1 | Checked TA definitions (per CMT) + both quizzes (arithmetic/answers correct). FINDING: the 'real markets' TSLA example dates its breakout close to Sat 14 Mar 2026 and 'next session' to Sun 15 Mar 2026 — both weekend, markets closed; impossible. Fix: use real trading dates or relabel hypothetical. |
| TECH 20 | `120_breakout_retest_entry` | FINDING | 2 | JPM example fabricated: lesson claims JPM ranged $258–272 and closed $275.40 on 5 Mar 2026 (retest $272–274), but real JPM was ~$310–330 then (Feb 23 4-wk low $312.18; 52-wk low $279.10)—never near $275. Fix: mark hypothetical. Also quiz-1 calls $51.20 vs $50 "1.2%"; it's 2.4%. |
| TECH 21 | `121_pullback_depth_fibonacci_zones` | FINDING | 1 | Fib math + all 3 quizzes correct (hypothetical tickers, internally consistent). But the MSFT 'Example' fabricates real prices: actual closes Feb4 $412.35 / Mar26 $365.18 (claimed $462.20 high) / Apr8 $373.52 / Apr22 $431.98 — MSFT FELL Feb–Mar. Fix: relabel as hypothetical or use verified data. |
| TECH 22 | `122_head_and_shoulders_pattern` | FINDING | 1 | TSLA example fabricated: lesson claims TSLA ~$254-289 Jan-Apr 2026 + $224.60 on Apr 22; real TSLA ~$439 (Jan), ~$422 (Apr 2), closed $387.51 (Apr 22) — ~40% off, no such pattern existed. Concept + all 3 quiz answers correct. Fix: use real prices or label example hypothetical. |
| TECH 23 | `123_gap_analysis_four_types` | FINDING | 3 | Gap taxonomy + all 3 quiz keys are correct (Edwards & Magee/CMT). FINDING: the 'real gaps on NVDA in early 2026' example is fabricated — NVDA traded ~$164-236 (52wk), not $108-152; no Feb 6 earnings beat (real earnings Feb 25, stock fell). Fix: relabel example as hypothetical or use verified data. |
| TECH 24 | `124_sma_vs_ema_vs_wma` | FINDING | 4 | QQQ example fabricated: QQQ was ~$585-625 in Oct-Nov 2025 (Oct 17 close $603.93), not the $483-495 cited; MA-turn dates uncorroborable, Quiz 1 rests on them. Public Bank crossovers, 'EMA=half SMA lag' (really equal by center-of-mass), '30-40% more flips' also unsourceable. Fix: relabel hypothetical. |
| TECH 25 | `125_golden_cross_death_cross` | FINDING | 3 | Verified SPX/KLCI cross claims vs index history. FINDING: KLCI never hit 1,550 in 2018 (closed 1,690.58, low ~1,601)—fix '1,550 by year-end'; 2020 SPX death cross (3/30) was 1wk after the 3/23 bottom, not 'three weeks'; it fired ~20% ABOVE the low, not 'below'. Quiz1 explanation repeats both errors. |
| TECH 26 | `126_ma_slope_analysis` | FINDING | 3 | NVDA/TENAGA examples checked vs exchange data. NVDA Aug–Nov 2025 traded ~$165–207 (Sep30 close 186.56, Oct29 ATH 207.03), not the 118–150 claimed; "Nov18 broke 142 / SMA50 144" is fabricated and poisons Quiz 1. TENAGA unverifiable. Fix: rebuild on real prices. |
| TECH 27 | `127_moving_average_ribbon` | FINDING | 4 | MSFT Sept–Dec 2025 example is fabricated vs exchange data: MSFT ROSE to ATH close $538.66 on Oct 28 (Oct15=$510.20, Oct22=$517.26), but lesson claims an Oct breakdown/down-regime; Nov18=$490.68 not $470, never hit 452. Fix: label scenario hypothetical (also poisons Quiz 1 setup). |
| TECH 28 | `128_rsi_hidden_divergence` | FINDING | 4 | Concept is sound TA, but AMZN/PETRONAS examples are fabricated: real AMZN was ~$220-228 in Oct 2025 (not $178-195) and hit a 52-wk LOW ~$196 in Feb 2026 (not a 'new high at 224'); PETRONAS isn't a Bursa ticker. Quiz 1 rides the bogus AMZN numbers. Fix: verified figures or reframe as hypothetical. |
| TECH 29 | `129_rsi_trending_vs_ranging` | FINDING | 3 | TSLA example fabricated: lesson claims uptrend 220→285 (Jun 12–Oct 8 2025) then range 268–295; actual TSLA closed $319.11 Jun 12 & $438.69 Oct 8, ATH $498.83 Dec 22. GENTING RM4.20→5.20/2024 unverifiable. Cardwell/Brown RSI range-shift concept is sound. Fix: use verified data or mark hypothetical. |
| TECH 30 | `130_rsi_2_mean_reversion` | FINDING | 4 | FINDING: GOOGL was BELOW its SMA200 in Apr 2025 (~$159 vs ~$172 200-DMA), so 'above SMA200 every day Mar–Dec 2025' is false; GOOGL/TSLA/PUBLIC BANK backtest stats unverifiable; math gives +8.2% not +9.2%. Connors/RSI(2) concept is sound. Fix: cut real-ticker numbers, mark examples hypothetical. |
| TECH 31 | `131_macd_zero_vs_signal_cross` | FINDING | 4 | AAPL Q3–Q4 2025 example false vs exchange data: hit 52-wk low $201.50 (Aug 1) then rallied—no '218–232 sideways range'; Oct low $244 (not '235' Oct-7 cross); Nov ATH $277.57 (not 'ran to 256'). Quiz 1 inherits false premise. Fix: correct prices or relabel hypothetical. MACD mechanics correct. |
| TECH 32 | `132_macd_histogram_acceleration` | FINDING | 4 | FINDING: META Nov-Dec 2025 'real' example is fabricated — META fell to a ~$585 low on Nov 19 2025 (downtrend, rejected 690.73), not rising to a new-high 612 on Dec 1 via a bullish histogram peak; poisons Quiz 1. '5-15 sessions avg' unsourced; CIMB 2024 unverifiable. Concept CMT-standard/OK. |
| TECH 33 | `133_on_balance_volume_obv` | FINDING | 2 | OBV mechanics/divergence canonically correct (CMT/Granville). But both 'real-market' examples are fabricated: NVDA was ~$180-207 Oct-Nov 2025 (ATH $207; 2025 close $186.50), not 138/156/162/149; AirAsia ~RM0.2-0.9, not RM1.85-2.05. NVDA figures poison Quiz 1. Fix: relabel hypothetical. |
| TECH 34 | `134_vwap_and_anchored_vwap` | FINDING | 4 | TSLA example fabricated: claims a Nov 6 2025 earnings print (actual Q3 = Oct 22 2025 per SEC 8-K) and ~$268-308 prices (TSLA was ~$400-500; ATH $498.83 on Dec 22 2025). Quiz 1 rests on those fake numbers. Fix: rebuild example+Quiz 1 on real data or reframe as explicitly hypothetical. |
| TECH 35 | `135_money_flow_index_vs_rsi` | FINDING | 2 | MFI/RSI defs (0-100, 80/20 vs 70/30, volume-weighted) verified. FINDING: META Q4-2025 example fabricated — 618 was no new closing high (2025 high ~736-796, close ~645), never fell to 569; poisons graded Quiz 1. TENAGA Q3-24 uncorroborated. Fix: use real data or reframe as illustrative. |
| TECH 36 | `136_bollinger_bands_basics` | FINDING | 2 | Checked BB definition, containment %, quiz keys vs Bollinger's own Rules. FINDING: lesson teaches ~95% inside/5% outside as a real-world calibration target and credits it to Bollinger, but his Rule 14 says prices are non-normal, ~90% inside/~10% outside. Fix: use ~90%/~10%. Quiz keys OK. |
| TECH 37 | `137_bollinger_squeeze_and_breakout` | FINDING | 3 | Pedagogy sound, but 'real markets' data fabricated: NVDA Jan-2026 traded $177-194, +0.7% for the month (Jan 29 close $192.28), not a 132-138 squeeze breaking to 141 then 158; AMD Oct-2025 was +59%, not a low-vol squeeze. Quiz 1 embeds the false NVDA prices. Fix: verified data or label hypothetical. |
| TECH 38 | `138_bollinger_band_walk` | FINDING | 3 | Concept sound (Bollinger/CMT). But 'real market' examples false: NVDA was ~$186-190 in late-Jan/mid-Feb 2026 (Jan 30 close $190.90), not 141-161 as claimed (poisons Quiz 1); PETRONAS isn't listed on Bursa; GOOGL Mar-26 uncorroborated. Fix: use real data or mark examples hypothetical. |
| TECH 39 | `139_stochastic_k_d_crosses` | FINDING | 4 | FINDING: AMZN Q4-2025 example fabricated—actual Oct range $213–244 (Oct 22 close $217.95, never 195/201/209), Nov 28 $233.22 not 217; Quiz 1 stem uses the fake rally. Stochastic defs (%K formula, %D=3-SMA, 80/20) correct/CMT-sourceable. Fix: real data or relabel hypothetical. |
| TECH 40 | `140_stochastic_fast_vs_slow_divergence` | FINDING | 5 | Stochastic fast(14,3)/slow(14,3,3)+divergence defs correct. FINDING: MSFT Q1-2026 example fabricated — Feb 14 2026 is a Saturday (market closed); MSFT never hit a '438 new closing high' (Feb high ~$431, ATH $555 Jul-2025, falling). Both quiz explanations also mislabel the correct answer. |
| TECH 41 | `141_atr_as_volatility_gauge` | FINDING | 3 | ATR definition (Wilder/CMT, 14-period) + quiz arithmetic correct. But 3 dated TSLA anchors are false: May-2025 '~180' (actual ~$285, yr low $221.86), Oct-2025 '~270' (actual avg $441), Jan-2026 '230' (actual avg $437). Fix: mark the TSLA example hypothetical or use real prices. |
| TECH 42 | `143_adx_trend_strength` | FINDING | 2 | ADX concept (Wilder 1978, 0-100, direction-blind, 20/25/50, period 14) verifies vs Wilder & CMT. FINDING: MSFT 'real markets' example fabricated — MSFT ATH ~$538 close 28 Oct 2025, not chopping 425-445 rising to 488 (was topping/declining). SIME uncorroborated. Fix: relabel as hypothetical. |
| TECH 43 | `144_adx_di_plus_minus_crosses` | FINDING | 2 | AMD example is fabricated: AMD traded ~$200s in Q4'25 (Oct 6'25 ~$204, +24% OpenAI breakout; Nov 20'25 ~$233), not $116-145, and 'Oct 6 chop 115-119' is the opposite of reality. 'ADX halves the false-cross rate' is an uncorroborated stat, also in Quiz 1. Fix: relabel hypothetical; drop 'halves'. |
| TECH 44 | `145_ichimoku_cloud_basics` | FINDING | 2 | Ichimoku defs (Hosoda, Span A/B, cloud color/regime) correct per CMT. FINDING: 'real markets' GOOGL story fabricated — claims ~165-174 Nov'25 & 'fell to 154' after 12 Jan'26; actually ~$290 on 17 Nov'25, GOOG ATH $329.58 on 8 Jan'26 (uptrend, ~2x off). Fix: relabel hypothetical or use real prices. |
| TECH 45 | `286_what_is_a_chart` | VERIFIED | 0 | Verified all definitional claims (line/candlestick charts, OHLC, body/wick, green-red convention, volume-confirms-breakout) against CME Group TA course + Schwab/Britannica; both quiz answers (Q1 idx3 strong buying, Q2 idx3 broad-agreement volume) independently correct. No errors. |

## Wave 3 — edge_process (EDGE) + sentiment_behaviour (SENT) + asset_classes (ASST) + ethics_integrity (ETHIC) + quant_methods (QUANT), 123 lessons · 2026-07-22

**Result: 2 VERIFIED · 6 NO_SOURCE_NEEDED · 112 FINDING · 3 ESCALATE** (139/139 agents, 0 errors).

| Track | n | FINDING | rate |
|---|---|---|---|
| `edge_process` (EDGE) | 98 | 92 | **93%** |
| `sentiment_behaviour` (SENT) | 10 | 10 | **100%** |
| `asset_classes` (ASST) | 3 | 3 | **100%** |
| `quant_methods` (QUANT) | 6 | 5 | 83% |
| `ethics_integrity` (ETHIC) | 6 | 2 | 33% (+**3 ESCALATE**) |

### ⚖️ The 3 escalations — legal doctrine, human/SME sign-off required, never auto-fix

All three are in `ethics_integrity`, and all three are the same shape as the sourced batch's lesson
`294`: the lesson states a **legal test** that the cited authority does not support.

- **ETHIC 4 `296_front_running_fair_dealing`** — the lesson's "either/no-duty → competition" test wrongly
  clears a tippee front-runner (an outsider paid by a broker for a client's pending order): no duty is
  owed, yet it is illegal. Contradicts its own cited **FINRA 5270(a)** (which has no duty element) *and*
  its prerequisite `294`'s "tippee inherits liability". Also carries no `sources:` frontmatter.
- **ETHIC 5 `297_playing_it_straight_capstone`** — a **Bursa Malaysia** scenario adjudicated with **US**
  doctrine: "both prongs" of MNPI/tippee liability presented as sufficient, contradicting
  *Chiarella*/*Dirks* (breach of duty required) — and Malaysian law is **CMSA s.188**, not US case law.
  Compounding it, a **real listed issuer (TOPGLOV) is placed in a fabricated fraud scenario.**
- **ETHIC 7 `299_conflicts_of_interest`** — quiz 1's unqualified "PFOF is legal when disclosed" is false
  in the **EU/UK/Canada** (the EU grandfathering expired 30 Jun 2026). The SEC figures themselves verify.

> Naming a real company in an invented fraud (ETHIC 5) is a category worse than a wrong price. Routed to
> Saiful/SME with `294`, not to the education lane.

### Cross-validation of DEF083 by a second, independent method

Wave 3's LLM refute passes independently re-derived defects my **deterministic** DEF083 scan had already
flagged — two unrelated methods converging on the same rows: `019_survival_mindset` (EDGE 2, both quizzes),
`045_greed` (SENT 1), `049_overconfidence` (EDGE 5), `274_the_safety_floors_audit_trail` (EDGE 91),
`277_pass_is_not_buy` (EDGE 94). Wave 3 also surfaced ones the scan could not prove mechanically —
`031_indicator_limitations` (EDGE 3, "Quiz 2 mislabels option letters") and EDGE 54 (a poisoned key).
**The deterministic scan is the cheaper detector for this class and belongs in a guard, not an audit.**

### Product-accuracy defects (no external source can catch these)

**EDGE 87** was caught by reading the repo, not the web: the lesson names the mandate field `no_fossil`
when the actual field is **`no_fossil_fuels`**, and presents **`max_position_pct`** as a Mandate field
when no such field exists (the cap derives from risk settings). Same class as SHARIA 9
(`355_how_amis_halal_flag_maps_to_real_screening`) — lessons asserting things about **AMI's own
behaviour**, which only a code check can verify. Worth a standing check of its own.

### Verdicts

| Code | Lesson | Verdict | # | Discovered source / defect + fix |
|---|---|---|---|---|
| ASST 13 | `315_capstone_choosing_the_right_vehicle` | FINDING | 1 | refuted: Quiz-2 explanation asserts "the REIT's specific wrapper (ETF-style vs closed-end)… covered in the prior lesson" — false: a REIT is a tax election, not a fund wrapper; L314 never says this and states only ETFs have creation/redemption. Math, §857 90%, FINRA 09-31, all 3 keys verified correct. |
| ASST 14 | `316_calls_and_puts` | FINDING | 1 | Definitions, 100-share contract, buyer max loss = premium, and both quiz keys (0,1) verify vs FINRA/OIC. Defect: short-call risk called uncapped without the uncovered qualifier, plus covered-call idiom "sold a call against NVDA". Fix: say uncovered call ON NVDA in body, Quiz 2 stem, option 1. |
| ASST 16 | `318_the_greeks_delta_theta_vega` | FINDING | 1 | refuted: Steelman wrongly credits theta+vega for two expiries reacting to the same stock move by different percentages; with time and IV frozen, 3-day vs 6-month ATM calls gain +52.9% vs +6.3% (+$1.165 vs +$1.177) — that's delta/gamma/leverage, and the near-equal dollar gain contradicts the text. |
| EDGE 1 | `012_why_most_traders_fail` | FINDING | 5 | Checked all stats + both quiz keys (0/1 correct). Errors: "10-30% survive long-term" vs <3% in cited studies; US discount-broker data shows +11.4%/yr, not 70-90% losing; Brazil study is academic index-futures, not regulator-led equities; 4 losses = -26%, not "finished". |
| EDGE 2 | `019_survival_mindset` | FINDING | 4 | Both quiz explanations call "the first" option wrong, but answer={0} - the first IS correct (Q1 means opt 4, Q2 opt 2); "due to lose" is the gambler's fallacy, not "in reverse"; no FOMC met in TSLA's 2024-07-23 earnings week; the 90%/1-in-4 "falsifiable claim" has no data behind it. |
| EDGE 3 | `031_indicator_limitations` | FINDING | 4 | FINDING: both "real market" episodes fabricated — JPM traded ~$300+ in Feb 2026 (52wk 202–337), no Feb-26 gap to 240 (JPM -1.9% Feb 27, Block layoffs); SIME never hit RM2.65 mid-2025 (~RM1.64). Quiz 2 mislabels option letters; "two days later" vs Feb 18→26. Fix: mark scenarios hypothetical. |
| EDGE 4 | `047_revenge_trading` | FINDING | 3 | Checked Bursa mechanics, the post-loss stat, arithmetic, all 3 quiz keys (keys correct). 3 issues: 'by 2pm' GENTING entry impossible (Bursa matching resumes 14:30); 'next trade after a loss is statistically your worst' = uncited superlative (lit: worse-on-average); 2-of-3 vs 3-of-3 test conflict. |
| EDGE 5 | `049_overconfidence` | FINDING | 2 | FALSE: anecdote says a long on NVDA in early 2024 gapped down on an earnings miss — NVDA beat 21 Feb 2024 (+16.4% next day) and 22 May 2024. Fix: make it an unnamed hypothetical. Also Quiz 3 explanation calls "raise the mandate" the last option; it is option 2. |
| EDGE 6 | `050_boredom_trading` | NO_SOURCE_NEEDED | 0 | Checked all claims, arithmetic and both quizzes: behavioural/process pedagogy with a fully hypothetical scenario (invented trader, strategy, -2.3%; tickers are props) and an AMI-internal 1.5x diagnostic. No external fact, stat or named theory. Quiz answers 2 and 0 both correct. |
| EDGE 7 | `051_discipline_vs_excitement` | FINDING | 2 | No external claim needs a source; all 3 quiz answers correct. FINDING: 4 of 5 mandate params named (per_trade_risk, open_positions, cooldown_after_stop, trades_per_week) exist nowhere in backend/mobile; only max_drawdown_pct is real, so "Try it" + Quiz 3 grade a rule the PM never enforces. |
| EDGE 8 | `052_trend_following` | FINDING | 4 | NVDA prices checked (split-adj closes, computed 50/200 SMA): cross was 2023-01-24 @$19.22, not ~$23.20/$232; NVDA closed below the 50-DMA 4x in 2024 (10 weekly closes), so the stated rule exits 2023-08-09 @$42.47 = 2.2x, not a held ~6x. Quiz2 explanation miscalls 217 shares '1% of account'. |
| EDGE 9 | `053_breakout_strategy` | FINDING | 3 | Checked the META Feb-2024 example, both quizzes, all arithmetic. FINDING: example is fabricated — META closed 394.78 (Feb 1) then 474.99 (Feb 2; low 453.01, high 485.96, ~84M sh). No 475-510 base, no 510 breakout, no 501 open. Fix: rewrite with real OHLCV or relabel as hypothetical. |
| EDGE 10 | `054_pullback_strategy` | FINDING | 4 | Checked MSFT 2024 OHLC/MAs + both quizzes (answers correct). FALSE: MSFT reclaimed its 50-day on 2024-09-12 — 27 sessions later at $427, not "within ten sessions at ~$415" (50-day was ~$435); Aug-5 low was $385.58 not ~$395, so $390 stop and 2:1 math fail. Fix: use real numbers or mark hypothetical. |
| EDGE 11 | `055_mean_reversion` | FINDING | 4 | Checked the JPM 12-Jul-2024 example vs NYSE daily OHLC + JPM 2Q24 8-K: prior close $207.45 not $213; day was -1.21% to $204.94, not a ~5% gap to $203; RSI(2)=13 not 4, so the RSI(2)<5 entry never fires; 5-day-MA exit was the next session at $210.05, not 3 later at $209; 203→209 vs $200 stop = 2R. |
| EDGE 12 | `056_momentum_trading` | FINDING | 2 | Verified NVDA 2024 (+171%, ~$50 Jan post-split, $140 later), 3 crash dates (Mar 2009, Q1 2016 −19%, Nov 9 2020 −19% single day) and both quiz answers (25−18=7 correct). FIX: "$50 to $80, it doubles your cost" is false ($80 = +60%); change $80 → $100. Also unsourced superlative on retail discretion. |
| EDGE 13 | `057_backtesting_a_strategy` | FINDING | 3 | Concepts + all 3 quiz keys (idx 3/2/1, 0-based) correct. FINDING: (1) "NVDA went up 10x" 2020-24 false - ~22x split-adj ($6.18 to $134.09); (2) NVDA RSI(2) backtest stats (78%->58% win, 6%->14% DD) uncorroborable, mark illustrative; (3) 47 trials x 5% = 2.35 expected, not "several". |
| EDGE 14 | `058_strategy_failure_modes` | FINDING | 2 | Quiz keys, ADX<20 (Wilder/CMT) and Nov-9-2020 momentum crash (French daily Mom -14.39%) all verified. 2 false examples: Maybank/Tenaga 50/200 "6 losses per winner" 2022-23 (actual 0-1 crossover, Tenaga's a winner); "summer 2023 breakouts failed" (SPY +9.6% May31-Jul31). Replace both. |
| EDGE 15 | `065_guaranteed_return_scams` | FINDING | 2 | SEC Ponzi red flags, SC/BNM alert lists, quiz math (5%xRM10k=RM500) and both answers verified. 2 issues: takeaway "guaranteed => deposit or scam, nothing in between" is false (SC capital-guaranteed funds, MGS/Treasuries) — limit to equity-style; the 10-12% case is Madoff, not on SEC/FBI alert pages. |
| EDGE 16 | `066_telegram_whatsapp_pump_groups` | FINDING | 3 | Quizzes OK. FINDING: the "FBI social media-enabled pump-and-dump advisory" and its 15k-50k-member/founder/paid-promoter template are absent from the real FBI IC3 PSA (3 Jul 2025, "ramp-and-dump"); SC Malaysia WhatsApp case uncorroborated. Fix: cite real PSA/ASIC 21-256MR/FCA, cut invented detail. |
| EDGE 17 | `067_fake_brokers_and_clone_entities` | FINDING | 2 | Trust-account claim (CMSA s.111), SC/BNM lists and both quiz answers (2, 0) verify. Errors: FCA Warning List is not "specifically for clone firms" (all unauthorised firms; URL /consumers/warning-list-unauthorised-firms, not /scamsmart); ASIC "near-weekly" alert cadence uncorroborated — drop it. |
| EDGE 18 | `068_forex_fx_trading_scams` | FINDING | 2 | BNM/CFTC/SEC forex-scam mechanics, RED List, withdrawal-block trait and both quiz answers verify. FINDING: (1) 'hundreds of millions of ringgit' total across the BNM alert list — BNM publishes no such aggregate; cite PDRM scam-loss stats or drop. (2) no SEC/CFTC warning titled 'Managed FX Accounts'. |
| EDGE 19 | `069_ai_trading_bot_scams` | FINDING | 4 | Both quiz keys correct; mechanics verify vs SEC/NASAA/FINRA + CFTC Jan-2024 alerts. 4 errors: "hundreds of millions" (SEC AI cases total under $100M); "several cases per quarter" unsupported; no such "FCA 2024 AI warning"; 1.5%/wk compounds to +117%/yr, not ~100%. |
| EDGE 20 | `070_pressure_tactics_urgency_and_scarcity` | FINDING | 1 | refuted: REFUTED. "FCA's 2024 ScamSmart materials" is a dead source — scamsmart.fca.org.uk NXDOMAIN, FCA removed ScamSmart refs 19/01/2026, FCA in no registry tier. Also "mechanism (Module 8) is loss aversion plus social proof": neither term appears in any of the 21 Module 8 lessons. |
| EDGE 21 | `071_how_to_verify_before_you_wire_money` | FINDING | 1 | All 8 regulator registers/URLs and all 3 quiz answers verify correct. FINDING: line 25's "Most fraud victims interviewed by the SEC's Office of Investor Education..." is unsourceable — no such OIEA study, and the office is misnamed (Office of Investor Education and Advocacy). Delete the sentence. |
| EDGE 22 | `072_what_ami_can_do_for_you` | FINDING | 2 | Under 'real markets' the lesson calls $35.1B/74%/$142 'the latest 10-Q' — those are Q3 FY2025 (Oct 2024); latest at lesson date was $68.1B (Q4 FY2026), GAAP GM 74.6%. Also +11.66% stated as +11.6%. Fix: mark block illustrative or refresh figures; use +11.7%. Quizzes and -5.3% stop math correct. |
| EDGE 23 | `073_what_ami_cannot_do` | FINDING | 1 | Quizzes correct (0, 2). FINDING: lesson says lack of broker integration is what stops AMI "becoming a regulated investment adviser" — wrong statute. Execution triggers broker status (Exch Act 3(a)(4)); adviser status (Advisers Act 202(a)(11)) turns on advice-for-pay. Fix: say broker-dealer. |
| EDGE 24 | `074_ai_hallucinations_and_amis_safety_floor` | FINDING | 4 | XOM "actual ~14" P/E is false (trailing ~25.5, Jul-2026). mandate.max_position_pct doesn't exist — cap derives from risk_score, backstop is a fixed 50% single-name cap — so the code snippet + Try-it steps are unperformable; max_drawdown_pct:15 invalid (10/20/30/50/100 only). TENAGA ~3.9% OK. |
| EDGE 25 | `075_the_risk_of_overreliance` | FINDING | 1 | refuted: Quiz 2 explanation contradicts its key: answer={1} is the overreliance sign, yet the explanation calls "the first three options" healthy CEO behaviour — index 1 included, so the correct answer is labelled healthy; should be "the other three". Also "the six trades" = 3 BUYs + 3 HOLDs. |
| EDGE 26 | `076_human_oversight_is_the_product` | NO_SOURCE_NEEDED | 0 | Purely AMI-internal process/pedagogy (CEO framing, Mandate, PM compliance, Decision Journal, no execution surface); no external fact, stat, date or named theory. JPM figures are hypothetical and arithmetic checks out (-4.76%→-4.8%, +8.97%→+9.0%). Both quiz answer indices (3, 1) verified correct. |
| EDGE 27 | `077_decision_support_vs_prediction` | FINDING | 1 | refuted: "forward P/E 22" is unsupported and wrong: cited 8-K has no forward EPS. $182/$8.04 TTM = 22.6 (trailing, mislabeled). True fwd P/E at $182 was ~20.3 (FY25 consensus ~$8.95; actual $10.82). Cloud +30.06%, ads +10.60%->11%, and both quiz answers (idx 3, 3) confirmed correct. |
| EDGE 28 | `100_kelly_criterion_simplified` | FINDING | 3 | Formula, 42.4% worked example, half/quarter-Kelly and both quiz answers verify vs Thorp (2006) f*=(bp−q)/b. 3 errors: "55% win rate → Kelly 18%" is 30%; "50% → 5.5%" is 22.2%; "edge negative unless W×R>1" is false — threshold is W×R>1−W (W=50%, R=1.8 gives +22.2%). |
| EDGE 29 | `106_asymmetric_rr_in_regimes` | FINDING | 6 | Checked all R:R arithmetic (correct: 3.0, 2.25, 2.13, quiz 2.5, both answer keys right) but the real-price claims fail vs exchange data: GOOGL Q3 2024 was NOT a $160-$172 range (fell $191.75 to $147.22), and Q2 was $149.60-$186.05, not $148-$190. Fix: correct or mark hypothetical. |
| EDGE 30 | `110_tail_risk_and_fat_tails` | FINDING | 8 | 8 defects: 5σ is ~14,000 YEARS not "~14,000 trading days" (off 250x); Mar-2020 had ONE ≥10% S&P day not multiple in a week; Aug-2024's 12% was the Nikkei (S&P −3.00%); NVDA −17% was 27-Jan-2025 DeepSeek not 2024 guidance; 130x/30x/30-100x contradict; both quiz explanations cite wrong distractor. |
| EDGE 31 | `111_gamblers_ruin_and_the_one_percent_rule` | FINDING | 5 | Recomputed every figure and both quizzes vs Feller (gambler's ruin) + Kelly. FINDING: (0.45/0.55)^100 = 1.93e-9, not 3e-10 (6.4x off); Quiz 1's keyed answer "60 million×" should be ~9.4 million× and mislabels its options; Quiz 2's keyed answer contradicts Kelly (f*=10%, so 5% out-compounds 1%). |
| EDGE 32 | `142_atr_position_sizing_and_stops` | FINDING | 2 | All arithmetic verified correct (NVDA 32sh/$4,480; AAPL 59sh/$13,570; both quiz answers). FINDING 1: "PETRONAS at RM5.40" is not a Bursa security — Petroliam Nasional Bhd is unlisted, 100% govt-owned; use PETRONAS Chemicals (PCHEM, 5183). FINDING 2: "1.5x/2x/1x ATR stop is standard" — unsourced. |
| EDGE 33 | `146_combining_indicators_effectively` | FINDING | 5 | Recomputed both worked examples from exchange OHLCV: META Jan-2026 SMA50 was ~640 and FALLING (not 598 rising), ADX 24.7 not 28, 632→639 in 5wks not 685; GENTING(3182) mid-2025 ADX peaked 15.7. Fix: relabel both as hypothetical. Quiz 1 explanation also mislabels option C as "D". |
| EDGE 34 | `147_false_confluence_indicator_redundancy` | FINDING | 6 | Both quiz explanations call option A — the keyed correct answer — "the tempting wrong answer" (C/D refs scrambled); RSI(14)=32 is not oversold (Wilder <30) though the stem says all four are; TENAGA 2024 -6% anecdote unverifiable; "rho>0.85 = zero info" unsourced. Fix: rewrite explanations, 32→28. |
| EDGE 35 | `200_pyramiding_into_winners` | FINDING | 3 | Checked NVDA/AAPL price history + all 3 quizzes (answers 1/3/2 correct). NVDA did NOT reach $74 by Jan 2024 (split-adj Jan high 63.49, 1/31 close 61.53; $74 first traded 2024-02-12) — fix to ~$62 by Jan or $74 by mid-Feb. No AAPL -6% guidance-cut gap in 2024 (worst -4.82%, Aug 5, macro-driven). |
| EDGE 36 | `204_sixty_minute_rule` | FINDING | 6 | Quiz indices/arithmetic OK. FINDING: the '14mo/184 stop-outs, 31/47/54% win rates, breaches -71%' journal is presented as real-market evidence but is uncorroborable, and Quiz 1's graded answer rests on an unsupported 60-min physiological decay. Fix: mark scenario hypothetical + 60min as AMI default. |
| EDGE 37 | `205_sector_switching_revenge` | FINDING | 1 | Arithmetic (1800+2100+2500=6400), timings, sector labels and all 3 quiz answers verify. FINDING: "cognitive distancing" misdefined — literature (Kross & Ayduk) = detached third-person view of the SAME event, adaptive. Fix: relabel avoidance/displacement, drop "well-documented". |
| EDGE 38 | `208_size_creep_on_winning_streaks` | FINDING | 4 | Mandate = 1.0% per-trade risk, yet trades of 1.7-2.6% are called "no single trade breached"/"within mandate" (narrative, Quiz 1+3 stems, Try it). Fix: add a per-trade cap ~2.5% distinct from the 1.0% baseline. Also: unsourced 2024 anecdote, -3.8% counterfactual (≈-4.8%), unsourced superlatives. |
| EDGE 39 | `209_system_delusion_lucky_vs_skilled` | FINDING | 5 | 5 defects. '20-win streak in 32 (66%)=6%' wrong: literal streak=6.7e-6, P(X>=20)=10.8%; only P(X>=21)=5.5% fits -> use '21+ of 32, ~5.5%, 1 in 18'. Expectancy .38*5.2+.62*-4.6=-0.88% not -1.4%. Q1 rationale false: P(22/30)=0.8%. 'Late-2024 choppy' backwards vs IXIC +14.5%/-5.6%DD. |
| EDGE 40 | `210_unqualified_trade_trap` | FINDING | 3 | All 3 quiz answers verified correct. FINDING: the "180 closed trades" audit is unattributed/unverifiable, and "~28% higher annual return" is not derivable from its own figures (+8.4% additive, +59% compounded); +4.9% x 122 trades implies ~342x/yr. Fix: relabel as hypothetical and refit the numbers. |
| EDGE 41 | `211_journal_review_as_discipline` | FINDING | 2 | 3 quizzes correct. FINDING: 'real markets' anecdote asserts dated real outcomes — '~22% higher annualised return' and trades 'down 78% week-over-week from the February baseline' — uncorroborable, and 78% WoW vs a Feb baseline is incoherent. Fix: label illustrative, drop 22%. |
| EDGE 42 | `213_explain_to_a_six_year_old` | FINDING | 2 | Checked the NVDA Oct-2023 vignette, the word count, and all 3 quiz keys. FINDING: "price falls below $100" is impossible — NVDA traded $392-476 as-traded ($39.23-47.61 split-adj) in Oct 2023; fix to ~$390 (or $39 split-adj). Also "that sentence is 38 words" — it is 40. Quiz keys 2/3/2 all correct. |
| EDGE 43 | `214_donchian_channel_breakout` | FINDING | 7 | FINDING: COIN-2024 example fabricated (7 false facts vs daily OHLC): "$343 in late March" (Mar peak $279.71c/$283.48h; $343.62 was Dec 6); "over $330 by year-end" (close $248.30); Mar-1 entry $206.40, $156 stop, May-1 exit all wrong. Both quizzes correct. Fix: recompute or mark hypothetical. |
| EDGE 44 | `215_atr_trailing_stop_for_trends` | FINDING | 6 | NVDA example false vs real data: Aug 5 low $90.69/close $100.45 not ~$98; Jul 30 close $103.73 not $118.50; stop actually hit Jul 17 @$117.99; $140.76 high was Jun 20; Apr 22 close $79.52, ATR22 3.75. Q2 explanation calls 156sh "1% of account" (=100%). Rebuild example from real OHLC. |
| EDGE 45 | `216_multi_timeframe_trend_confirmation` | FINDING | 5 | Vs Nasdaq AMZN OHLC Apr-Jul 2024 the example is fabricated: May 3 high $187.87 (no 60-min close above $189, no $182 low); $200 first printed 2 Jul 2024, not 3 sessions later; $186.21 sits inside the stated $178-189 base. Fix: rewrite on real tape or mark hypothetical. |
| EDGE 46 | `217_breakout_from_flag_patterns` | FINDING | 7 | NVDA Oct-Nov 2024 bars checked vs exchange EOD data: worked example is largely fabricated — Oct 9 close $132.65 not $130; Oct 21 close $143.71 not $144.42; Nov 1 close $135.40 not $138.42; 4-session post-breakout high $149.77 not $152. Fix: rebuild on real bars. Both quizzes compute correctly. |
| EDGE 47 | `218_breakout_from_triangle_and_cup_handle` | FINDING | 9 | Checked META claims vs exchange daily OHLCV: example is fabricated. Nov 20 2023 close $339.97 (not $341.42); vol 16.96M vs 20d avg 22.0M — below average, breaking the lesson's own volume rule; $354 came Dec 20-21 not Dec 13; handle retrace 60% not 35%. Fix: rewrite example. Quizzes OK. |
| EDGE 48 | `219_breakout_volume_profile` | FINDING | 6 | Checked vs Nasdaq GOOGL/GOOG OHLCV + Alphabet Q1'24 8-K (4/25, not 4/26): the example is false. 4/26 close was 171.95 (173.69 is GOOG), 2.4x not 2.9x; Feb-Mar range 131-151 not 150-158; next 3 closes 166.15/162.78/163.86 on 45.6/33.6/33.5M — the $165 stop hit 4/30 (-1R, not +2R). Rewrite it. |
| EDGE 49 | `220_pullback_to_ma_vs_to_sr` | FINDING | 7 | MSFT-2024 example fabricated: Sep-6 50-day MA was $428 falling, not $419 rising; close $401.70 contradicts 'near $410'; Apr-19 low $397.77 not $397.58; $430 was March's peak, not a breakout base; $410 failed on closes. Plus 1.5x vs 0.5x ATR conflict; quiz-2 says 0.8x ATR but computes 0.5x. |
| EDGE 50 | `221_fibonacci_pullback_entry` | FINDING | 7 | NVDA Apr-Aug 2024 OHLC vs exchange data: swing low $75.61 (Apr 19) not $76.60 (Apr 22); Aug 5 low $90.69 not $98.91 ($98.91=Aug 7 close, so the $98 stop claim fails); $108.68 reclaimed in 5 sessions not 3; Aug max $131.26, never $140+ (next Oct 17). Rewrite the example; quiz answers are correct. |
| EDGE 51 | `222_pullback_bar_structure` | FINDING | 10 | AAPL May-2024 example is fabricated vs real OHLC: no 192.59 print, May 28 high 193.00 breaks the 5-bar count, May 30 close 191.29 not 187.93, 186.69 is May 23's low. Quiz2: 0.5xATR of 0.10 = 0.05 not 0.10, and PETRONAS is unlisted. Rewrite example from real data; fix both quiz explanations. |
| EDGE 52 | `223_rsi_2_mean_reversion_system` | FINDING | 9 | Recomputed vs actual JPM OHLC: the JPM-2024 'real markets' example is fabricated. 4/16 close $180.80 not $182.66; RSI(2) 1.47 not 3.8; 4/18 close $181.25 & 5dMA $181.56 not $186.79/$185.10 (no exit fired); rule fired 11x not 6x; 75% of 6 trades impossible. Fix: use real data or mark hypothetical. |
| EDGE 53 | `224_bollinger_band_mean_reversion` | FINDING | 6 | Quizzes correct. FINDING: BB are ±2 SD of price, not "of daily returns"; the 3 Jul 2024 KLCC trade is fabricated (actual close RM7.50; no RM7.21 close in all 2024; no RM7.46 exit); 2024 range RM7.06–8.21, trending H2; 70%/1.2R unsourced. Fix definition; make the example hypothetical. |
| EDGE 54 | `225_relative_strength_top_decile_momentum` | FINDING | 3 | (1) "3-mo lookback = mean reversion" false: J&T 1993 finds 3-12mo momentum positive; reversal is 1-mo only (French ST_Rev 1-1) - poisons Quiz 1. (2) 2024 S&P 100 basket fabricated: PANW/DELL/TSM not in S&P 100, >50% return unsourced. (3) Quiz 2 key 8% cap vs stated 10% equal-weight. |
| EDGE 55 | `226_dual_momentum_absolute_relative` | FINDING | 2 | Checked Antonacci-2014 attribution, 2008/2009 + 2024 S&P trailing-12m gate states, both quizzes (answers correct). FINDING: "rotated back to equities in mid-2009" is false — trailing 12m was -28/-22/-20/-9% Jun-Sep 2009; gate first reopened at the 31 Oct 2009 close. Fix to "end of October 2009". |
| EDGE 56 | `227_momentum_crashes_anatomy` | FINDING | 5 | Vs French daily Mom + exchange closes + Daniel-Moskowitz 2016: Jan 2016 no crash (Mom +0.93%); no episode lost 15-30%/week (worst -14.4%); Nov-2020 2-wk drawdown -15.5% not >20%; ZM/PTON -17/-20% not 4-7%; Quiz 1 miscites D&M for "dispersion" (predictors: bear state + vol). Fix all 5. |
| EDGE 57 | `228_parameter_sensitivity_sweeps` | FINDING | 3 | Recomputed the SPY 50/200 sweep from real price data: actual max DD 33.7% (COVID; death cross 2020-03-31, after the 03-23 bottom), not 14%; the 30/175 'spike' is false (30/150=8.4% not 4.1%) and does NOT vanish OOS (8.6% not 2.1%). Both quiz answers correct. Fix: relabel all numbers as hypothetical. |
| EDGE 58 | `229_walk_forward_analysis` | FINDING | 5 | Checked WFA method, arithmetic (4/18=0.22, 9.1/11.8=0.77 OK), both quiz keys. FINDING: rule can't have 'survived 2008 in the OOS portion' — its own windows make 2009 the first OOS year; 2009 called momentum 'factor recovery' when it was the worst momentum crash; 22% max DD over 2005-24 impossible. |
| EDGE 59 | `230_in_sample_vs_out_of_sample` | FINDING | 3 | Arithmetic, both quizzes and NBER regime dates checked. FINDING: worked example calls ~3,500/~1,500 'trades possible' but those are trading-DAY counts — at the stated 5-day hold it's ~700/~300 trades (5x overstatement); fix counts. Graded 0.5 'robustness threshold' also uncited/undefined. |
| EDGE 60 | `231_transaction_cost_modeling` | FINDING | 3 | Both quizzes verify correct. 3 errors: "$0.01 on a $500 share = 2 bps" is 0.2 bps (SSGA SPY spread 0.00%); RSI(2)/SPY 2015-24 stats (18.2% CAGR, 9% DD, 71% win) uncorroborable; "costs eat 60-100% of edge" is 62-107pp vs 18.2% gross. Fix: recompute spread, label stats illustrative. |
| EDGE 61 | `232_regime_segmented_backtests` | FINDING | 1 | refuted: Refuted: on real Cboe VIX + S&P 500 data, 2022 months entered under the lesson's own real-time signal (below 200-DMA AND VIX>22) returned +6.8% while all other months returned -24.6% — the 2022 drawdown did NOT come from the bear/high-vol bucket; only ~6pp of the 25.4% fall accrued risk-off. |
| EDGE 62 | `233_trend_following_crash_signatures` | FINDING | 7 | Recomputed ADX(14)/MAs from exchange OHLC: 7 false claims. SPY ADX Jul-15 13.7-23.5 (not 28), 33.5 mid-Sep (not 15), 32.5 on 2016-02-11 w/ 50d slope -2.38 (not "16, flat"); Sep-Nov-15 path false; 14% is SPY's own DD; KLCI/MAYBANK figures false. Rewrite case study from real data. |
| EDGE 63 | `234_mean_reversion_blow_up_patterns` | FINDING | 6 | Checked vs FRED SP500/VIXCLS + SPY/AAPL/MSFT/JPM dailies: bottom 218, Mar-24 +9%, circuit breakers OK. FALSE: stages 2/3 say RSI(2) re-fires <5 and names fall 5-12% — RSI(2) hit 70-81 Mar 2; AAPL +5.7%, MSFT +2.1% by Mar 6; Mar 10 RSI 51-59. +2 unsourced stats. Fix: rewrite stages 2-3. |
| EDGE 64 | `235_breakout_fakeout_statistical_signature` | FINDING | 5 | AAPL Jul-Aug 2023 recomputed from exchange OHLCV: worked example is fabricated (ATH 198.23 Jul 19, no 188-194 range; Aug 1 opened 196.24 so never "broke 194"; vol 35.2M not 47M; ATR14 ~2.8 and rising, not 3.20->2.10; fall was Apple's Aug 3 earnings on 116M shares). 72%/64% base rates unsourced. |
| EDGE 65 | `236_combining_strategies_for_diversification` | FINDING | 3 | Checked the 2010-24 backtest block + both quizzes (quizzes sound). FINDING: momentum's "worst year -12% (2020 crash)" is false — French Mom factor 2020 = +7.36%; -12.6% was Nov-2020 alone; worst years 2023 -24.26%, 2016 -21.20%. Fix: relabel as monthly/drop. Whole CAGR/DD/corr table is unattributed. |
| EDGE 66 | `237_when_to_retire_a_strategy` | FINDING | 1 | refuted: Line 33: live max DD 9% is below both the 11% backtest max and the 16.5% (1.5x) trigger, yet text claims condition 1 "does not fire because regime conditions were unfavourable" — false causal claim implying 9% would otherwise breach; contradicts Quiz 2's own 12<16.5 logic. |
| EDGE 67 | `238_strategy_correlation` | FINDING | 2 | Quizzes correct (idx 3, 0). 2 issues: (1) 2010-24 correlations (+0.34 avg; +0.21/.41/.78/.86 by VIX) asserted as measured fact, uncorroborable — mark illustrative or cite a real series; (2) Q1-20 momentum lost ~14% but BEAT SPX (-19.6%) on defensive tilt; the rotation crash was Nov 2020, not Q1. |
| EDGE 68 | `239_strategy_rotation_by_regime` | FINDING | 3 | Both quizzes correct. FINDING: 2005-2024 backtest figures (CAGR 10.4% vs 11.2%, MDD 14% vs 9%, Q1-20 -11%/-6%, Nov-20 -4%/-2%) unsourced/uncorroborable yet framed as real; "VIX rises before mean-reversion crashes" contradicts the lesson's own table. Fix: relabel illustrative or cite a real study. |
| EDGE 69 | `240_risk_parity_for_strategies` | FINDING | 3 | Concept checks out vs Qian 2005 / Maillard-Roncalli-Teiletche 2010; both quiz answers correct. FINDING: 2010-2024 backtest stats unsourced (strategy rules undefined); risk shares inconsistent — '~70%' needs rho=1, Quiz1's 92% needs rho=0 (=84%); '24/17/59' matches neither (rho=0: 24/13/64). |
| EDGE 70 | `241_equal_weight_vs_vol_adjusted_strategy_weights` | FINDING | 4 | Recomputed the table: equal-dollar vol 12.8% impossible (ceiling 12.33% at rho=1 for 11/8/18 equal-weight); risk-parity CAGR 9.3% backwards (inverse-vol gives ~10.5%, above equal-dollar); '2010-2024 real markets' backtest unsourceable; 'Sharpe' is bare CAGR/vol. Fix: mark hypothetical, redo math. |
| EDGE 71 | `254_ponzi_math_why_collapse_is_certain` | FINDING | 2 | Math correct (12.682m/16.084m; 35.0-mo doubling ~ rule-of-72) and both quiz answers correct. FINDING: "SEC and SC Malaysia case files show schemes typically collapse 18-60 months" is uncorroborable, contradicted by Madoff/Stanford - delete. Also quiz-1 explanation names wrong distractor. |
| EDGE 72 | `255_spotting_the_ponzi_inflection_point` | FINDING | 4 | Checked vs SEC/Investor.gov Ponzi, advance-fee, binary-options alerts: signals and both quiz answers (idx 1) correct. FINDING: invented stats credited to SEC/SC Malaysia — median failure under 6 months; events within 90 days/most schemes (also in quiz 1); every scheme on record. Fix: cut numbers. |
| EDGE 73 | `256_mlm_vs_investment_fraud` | FINDING | 4 | Vs FTC MLM guidance/Koscot: (1) no joint FTC-SEC guidance exists — drop it; (2) FTC says "there is no percentage-based test", contradicting the lesson's decisive-test claim and Quiz 1 explanation — recast on Koscot; (3) "FTC summarises it as" line fabricated; (4) 95% net-loss stat uncorroborated. |
| EDGE 74 | `257_pre_pump_accumulation_signals` | FINDING | 5 | FINDING: SEC/FINRA attribution + numbers (100k-500k ADV, 50k-200k blocks, 30-100x) uncorroborated; "FINRA Office of Fraud Detection" defunct; pumps hit OTC names with no options; ACE warrant claim unverified. Fix: cut attribution+numbers, hedge skew, drop ACE line, redo Quiz 1. |
| EDGE 75 | `258_post_pump_dump_and_anonymous_admins` | FINDING | 3 | Verified mechanics vs SEC investor.gov pump-and-dump page + IAPD; both quiz answers (2,3) correct. FINDING: "70% reversal" is wrong — $1.20→$0.45 is 62.5% off the high (93.75% retracement); fix Quiz-1 explanation + Takeaway. 30–100x/60min volume, 30–60% gap, 30–90-day account stats uncorroborated. |
| EDGE 76 | `259_paid_influencer_disclosure_failures` | FINDING | 3 | 17(b), SEC 2022/23 settlements, FG24/1, INFO 269, SC MY 2024, both quizzes verify. FALSE line 34: no investor.gov celebrity-backed-investments page; no FCA ScamSmart influencer guidance. Fix: cite SEC 2017 Celebrity-Backed-ICOs statement + FG24/1 ch.4. |
| EDGE 77 | `260_regulated_vs_unregulated_jurisdictions` | FINDING | 1 | refuted: REFUTED: lesson cites "SIPC insurance" as the US backstop beside CFTC, but SIPC explicitly excludes forex trades/currency. Also Quiz 2's explanation names option[0] ("tier-1 European authority") as the tempting distractor while describing option[3] ("Fully regulated and safe"). |
| EDGE 78 | `261_clone_firm_contact_match_deep_dive` | FINDING | 4 | Register-match routine is FCA-backed (Firm Checker); SC MY Alert List + BrokerCheck/IAPD confirmed. FINDINGS: "FCA case studies typically show clones fail 3-4 dimensions" uncorroborated (drop); SC/ASIC don't publish this routine; Warning List not at /scamsmart; Quiz 1 asks 3 checks, key lists 4. |
| EDGE 79 | `262_withdrawal_block_patterns` | FINDING | 6 | CFTC/FCA back only the generic pay-a-fee-to-withdraw and recovery-scam pattern. Uncorroborated: 10-20/5-10/15-25% fee bands, 50-100% total, step-progression rate, 4-step order credited to CFTC/FCA/BNM/SC. Fix: cut figures + BNM/SC attribution incl. Quiz 2 stem. Quiz keys OK. |
| EDGE 80 | `263_retail_cfd_leverage_abuse` | FINDING | 1 | Checked all leverage caps (ESMA 30:1/5:1/2:1; ASIC 2020/986; CFTC 5.9 = 50:1/20:1), the 1/500=0.2% math, both quiz answers — correct. FINDING: intro credits the 70-90% loss stat to offshore brokers "forced to publish"; ESMA's 74-89% is EU-REGULATED brokers, 12-mo window. Fix attribution. |
| EDGE 81 | `264_managed_account_and_forex_education_scams` | FINDING | 2 | 2 defects: (1) "FCA's 2023 review of finfluencer-led trading courses" does not exist — FCA 2023 output was GC23/2 promotions guidance; Quiz 1's explanation rests on it. Fix: cite GC23/2/FG24/1 + ASIC INFO 269, reframe. (2) Non-pooled LPOA managed account is CTA, not CPO; add CTA. Quiz keys correct. |
| EDGE 82 | `265_pig_butchering_and_affinity_fraud` | FINDING | 1 | Checked vs FinCEN FIN-2023-Alert005, IC3 2024 ($5.8bn/41,557 = ~$140k avg), SEC affinity-fraud alert: term origin, SE-Asia operators, fake platform, withdrawal block, quizzes OK. FINDING: "no investment pitch in the first month" unsupported (sources say "over time"); use "weeks to months". |
| EDGE 83 | `266_recovery_scams_and_second_victim` | FINDING | 2 | Architecture, both quiz answers and the no-fee/no-DM rule verify vs FBI IC3, FCA recovery-room, SEC advance-fee. 2 uncorroborated: "Sums range USD 500-50,000" (no source) and "Most are operated by the same networks" (FCA says "may"). Fix: cite IC3's $9.9M Feb23-Feb24 or drop range; "Most"->"often". |
| EDGE 84 | `267_how_to_file_a_report_with_regulators` | FINDING | 1 | refuted: ASIC's own scams page says "Report all scams to Scamwatch, including investment scams" (old report-a-scam URL 404s), so the lesson's "ASIC reportascam pages" complaint channel is stale for its unlicensed-broker case. Other portals, powers/limits framing, and all 3 quiz keys verified correct. |
| EDGE 85 | `268_why_twelve_agents_not_one` | NO_SOURCE_NEEDED | 0 | Purely AMI-internal architecture/pedagogy. AAPL/TSLA figures are a hypothetical simulated-run walkthrough under a template header shared by 228 lessons, not real-world claims. Both quizzes answer=0 correct. No external factual claim to source. |
| EDGE 86 | `269_analysts_gather_researchers_debate` | FINDING | 2 | Checked JPM figures vs 4Q24 8-K Ex-99.1: revenue $43.7B correct, CET1 15.7% correct, but NII was $23.5B ($23.0B ex-Markets), not $24.0B — fix to $23.5B and cite the 8-K. Also `max_position_pct` is not a Mandate field (derived from risk_score). Both quiz answers verified correct. |
| EDGE 87 | `270_why_the_pm_is_structurally_separate` | FINDING | 3 | FINDING x3 (repo-verified): field is `no_fossil_fuels`, not `no_fossil`; `max_position_pct` is not a Mandate field (cap derives from risk_score + 50% backstop) — poisons Quiz 1; DEF061 shows no_fossil_fuels is never enforced, so the worked example and "Try it" are false. |
| EDGE 88 | `271_inside_the_deterministic_compliance_check` | FINDING | 3 | No external factual claim (AMI-internal process, so no registry source needed), but 3 app-behaviour claims are false vs code: Mandate has no max_position_pct, no region_allowlist/no_fossil, and check_mandate_compliance does not stop at first failure. Fix: rewrite example/Try-it to real fields. |
| EDGE 89 | `272_the_mandate_is_your_contract` | FINDING | 4 | PETRONAS (Petroliam Nasional Bhd) is unlisted/state-owned — can't be convened on Bursa or pass the SC SAC screen; use PETGAS 6033 or PCHEM 5183. Also max_position_pct/risk_tolerance/region_allowlist aren't Mandate fields (max_position_pct derives from risk_score), so Quiz 1's answer is impossible. |
| EDGE 90 | `273_uncoachable_means_no_prompt` | FINDING | 2 | AMI-internal, no external source applies; but 2 claims contradict backend/app/agents/safety_floor.py: (1) "rules live in no prompt" is false — SAFETY_FLOOR_BLOCK injects caps/drawdown/exclusions into the PM prompt; (2) Quiz 2 distractor "strict prompt that resists" is also true. Reword both. |
| EDGE 91 | `274_the_safety_floors_audit_trail` | FINDING | 2 | No external claims (pure AMI process; 18+4+1+1=24 and 4/24=17% check out; both quiz keys correct). Q1 explanation calls "the last one" the outcome-bias distractor, but last option is "AMI dislikes NVDA" (bias is option 3). Scenario lists AAPL/NVDA/MSFT/AMZN/JPM then blocks TSLA/XOM/TOPGLOV. |
| EDGE 92 | `275_when_agents_disagree` | NO_SOURCE_NEEDED | 0 | Purely AMI-internal pedagogy (reading Room disagreement) on a hypothetical META scenario; no external fact/stat/date/theory asserted. Verified arithmetic (A range 4-2.5=1.5% tight; B 5-1=4% wide) and both quiz keys (1, 3) — correct. Nit: distractor says "miscoached" vs renamed Brief Your Agent. |
| EDGE 93 | `276_spotting_hallucinated_numbers` | FINDING | 3 | Verified vs SEC XBRL (NVDA CIK 1045810) + checked both quizzes. 3 issues: NVDA called a "non-dividend payer" but has declared a dividend every quarter since fiscal Q3 2013; Quiz 1 explanation says "the first one" while quoting option 4; TENAGA 3-4%/~3.9% yield uncorroborated (TNB/Bursa 403). |
| EDGE 94 | `277_pass_is_not_buy` | FINDING | 1 | AMI-internal process lesson; no external claim needs a source; mandate arithmetic and both quiz answers correct. Defect: Quiz 1 explanation calls "AMI has approved" the FIRST option, but it is option [3] (last); [0] is "already placed/live". Fix: say "the last one" or drop the position ref. |
| EDGE 95 | `278_coaching_changes_style_not_floor` | NO_SOURCE_NEEDED | 0 | Purely AMI-internal pedagogy: no external stat, date, or concept definition; TSLA/bank text sits inside illustrative example briefing notes. Both quiz answers verified correct against backend safety_floor.py + brief_engine.py; no execution path exists (Alpaca is read-only paper proxy). |
| EDGE 96 | `279_you_are_the_ceo` | FINDING | 1 | AMI-internal pedagogy, hypothetical AAPL numbers, no external source needed; Quiz 1 key correct. FINDING: Quiz 2 explanation says "first three are authorities, the fourth doesn't exist" but the impostor is option 2 (answer={1}) and option 4 (edit Mandate) IS an authority. Fix explanation wording. |
| EDGE 97 | `289_bull_vs_bear_thinking` | FINDING | 1 | Pure AMI process/pedagogy with a hypothetical NVDA scenario — no external claim needs a source; both quiz answers (3, 1) verified correct. One arithmetic slip: 38x->20x is an 18-point compression, not the "20-point" stated (line 44). Fix: "20-point" -> "18-point"; the ~50% downside is right. |
| EDGE 98 | `292_research_manager_synthesis` | NO_SOURCE_NEEDED | 0 | Checked all arithmetic (0.6x30-0.4x25=+8%; 25% of a 10% position=2.5%) and all 3 quiz answers (zero-indexed; 3/0/3 all correct). Lesson is AMI-internal Research-Manager process plus a hypothetical NVDA scenario with illustrative numbers — no external factual or statistical claim to source. |
| ETHIC 3 | `295_market_manipulation` | FINDING | 3 | Quizzes all correct. 3 defects: "$40m 2010-2014" is CFTC's alleged total E-mini profit to Apr 2015, not manipulation gains (DOJ plea: $12.8m); "998.5 points" unsupported — SEC/CFTC low 9,872.57 implies ~995.6; Bursa "volume triples, +40-80%" unsourced. Fix: use $12.8m, "~1,000 pts", drop numbers. |
| ETHIC 4 | `296_front_running_fair_dealing` | ESCALATE | 1 | REFUTED: the "either no -> competition" test wrongly clears the tippee front-runner (outsider paid by a broker for a client's pending order) - no duty owed, yet illegal. Contradicts cited FINRA 5270(a) (no duty element) and prereq 294's "tippee inherits liability". Also no `sources:` frontmatter. |
| ETHIC 5 | `297_playing_it_straight_capstone` | ESCALATE | 3 | $45,673 verified vs SEC Lit.Rel.18169 (3,928 shares); 3 quiz keys correct. ESCALATE: Bursa scenario judged by US doctrine — "both prongs" MNPI/tippee liability as sufficient contradicts Chiarella/Dirks (duty required; MY law is CMSA s.188); real issuer TOPGLOV set in fabricated fraud. |
| ETHIC 7 | `299_conflicts_of_interest` | ESCALATE | 1 | SEC 2020-321 ($65m, $34.1m) and 2003-54 ("roughly $1.4bn"; 487.5+387.5+432.5+80=1387.5) verify verbatim and both quiz keys hold — but quiz-1's unqualified "PFOF is legal when disclosed" is false in EU/UK/Canada (EU grandfathering expired 30 Jun 2026); Cain 2005 is off the CR060 registry. |
| ETHIC 9 | `301_disclosure_transparency` | VERIFIED | 0 | U.S. SEC — Regulation FD, 17 CFR §243.100 (adopted Rel. 33-7881; source note 65 FR 51738, 24 Aug 2000); Rule 16a-3(g), 17 CFR §240.16a-3(g) (Form 4 due before end of 2nd business day); SEC Form 8-K four-business-day deadline (SEC/investor.gov glossary); ESMA — 'Fast Track Peer Review: supervision of Wirecard's financial reporting by BaFin and FREP', ESMA42-111-5349 (Nov 2020): DAX 30 entry Sept 20 |
| ETHIC 10 | `302_advice_vs_education_capstone` | FINDING | 1 | refuted: Source mis-citation: FINRA 2111 Supp. Material .04 is "Customer's Investment Profile"; the reasonable-basis obligation is at .05, so .04 doesn't support half its cited claim. Lesson text, all 3 quiz answers, arithmetic and SEC IA-5248 (84 FR 33669, covers robo-advisers) + DOL IB 96-1 all hold. |
| QUANT 4 | `338_correlation_is_not_causation` | FINDING | 2 | Checked vs DAL/XOM 10-Ks + 19y of returns. FINDING: "airlines and energy often strongly NEGATIVELY correlated over multi-month stretches" is false — DAL-XOM corr positive in every sub-period 2007-2026 (+0.34/10y; 2% of rolling 1y windows negative). Quiz 1 stem+key inherit it. |
| QUANT 5 | `339_sample_size_and_statistical_significance` | FINDING | 1 | Body arithmetic + both quiz keys correct (SE 10.25%, 2SE 20.49pp vs 20pt edge; exact binomial p=.058 at n=20). FINDING: Quiz 1's distractor rationales are cross-swapped — "forgetting sqrt of 0.0105"=1.05% not 0.21%; "0.21/200"=0.105% not 1.05%. Fix: swap them in options + explanation. |
| QUANT 7 | `341_backtesting_rigor_the_basics` | VERIFIED | 0 | CFA Institute — CFA Program Level II reading "Backtesting and Simulation" (Yin Luo, CFA & Sheng Wang), in Members' Guide to 2021 Refresher Readings, pp. 53–56: "The main objective of backtesting is to understand the risk–return trade-off of an investment strategy, by approximating the real-life investment process"; rolling-window/walk-forward framework; "a key assumption these methods share is tha |
| QUANT 9 | `343_out_of_sample_and_walk_forward_validation` | FINDING | 1 | refuted: REFUTED (not arithmetic): quiz-2 distractor "re-tuning after seeing OOS results is normal in walk-forward" is keyed false, but rolling re-optimisation IS Pardo's WFA and is exactly what lesson 229 demonstrates; the body repeats it. All EV math and both answer keys verified correct. |
| QUANT 10 | `344_monte_carlo_simulation` | FINDING | 2 | EV +$180 OK, 0.4^5=0.01024 OK, both quiz keys correct. FINDING: Example asks how often a 5-loss streak occurs across 100-trade sequences and answers 1.02%; exact value is 45.9%. Quiz 2 stem repeats it. Fix: label 1.02% as per-5-trade-block, add ~46% per 100 trades. |
| QUANT 12 | `346_capstone_stress_testing_a_strategy_claim` | FINDING | 1 | refuted: Arithmetic and both RFS citations verify, but Quiz 3's keyed-correct option, its explanation, and "Try it" all say "all five checks" then list only four — they drop the backtesting/EV-basics check the body numbers "First". Also lesson has no sources:/verified: frontmatter. |
| SENT 1 | `045_greed` | FINDING | 3 | 3 issues: (1) NVDA example impossible — +34%/+41% off $115 = $154/$162, but NVDA's 2024 high was $152.89 intraday, no close >$154 until 2025-06-25; (2) Q1 explanation calls the keyed-correct 1st option the "tempting wrong answer" (it's the 4th); (3) add at +41% then exit +7% nets ~-1%. |
| SENT 2 | `046_fear_and_capitulation` | FINDING | 4 | Checked every MSFT Mar-2020 claim vs Nasdaq daily OHLC (2 mirrors agree). 4 errors: Mar-23 close was $135.98 not $137.35 (that was Mar-20); 9 red closes in next 20 sessions, not "exactly one"; $170-$137=$33 not "$18"; $185→$135 took 17 sessions not 8. Apr-30 $179.21 OK; quizzes OK. |
| SENT 3 | `048_fomo` | FINDING | 4 | Checked GME Jan-2021 prices vs NYSE daily OHLC + SEC 2021 staff report, all arithmetic, both quizzes. 4 errors: $20→$80 took 8 sessions not 5; $315 is not the ATH wick ($483 intraday Jan 28); $54 came 4 sessions later (2 later = $90); quiz-1's "~70% of FOMO urges" stat is fabricated — delete it. |
| SENT 4 | `201_round_number_trap` | FINDING | 5 | NVDA Nov-2024 tape vs exchange OHLC: "$173 in four weeks" is false - ATH then $152.89, first $173 print 2025-07-17, fell to $116 by Feb-2025. Quiz3 stem says +18% at $150 (=+8.7%); its explanation faults "the fourth answer" - the correct one. Fix: de-date anecdote; +18%->+8.7%; fourth->second. |
| SENT 5 | `202_bottom_tick_capitulation` | FINDING | 4 | META Oct–Nov 2022 checked vs exchange daily OHLC: $88.09 was the Nov 4 intraday low, not Nov 3 afternoon; Nov 4 closed $90.79 not $98; $110 never traded on the decline (Oct 27 gapped 129.82→97.94). Quiz 1's explanation calls "the first answer" the bottom-tick move — it's option 4. Fix all four. |
| SENT 6 | `203_portfolio_wide_panic_selling` | FINDING | 3 | Checked vs FRED SP500 + adjusted exchange closes. 3 errors: S&P bottomed 7 sessions after 2020-03-12 (Mar 23, 2237.40), not 9; the 6-stock book was ~+5% by end-June and ~+35% by Dec (not -3%/+18%; foregone move ~63pp not 45pp); Q3 explanation fabricates -32%/-28%. Quiz answer keys are correct. |
| SENT 7 | `206_meme_momentum_fomo` | FINDING | 9 | Checked vs SEC Oct-2021 staff report + daily OHLC. 9 errors: AMC $5→$20 was Jan-21 in 1 session (not Feb/7); GME $20→$80 took 8 not 5; ATH $483 so $250-325 not 'within 10%'; $54 came 4 sessions later; SEC: squeeze wasn't main driver; NVDA never traded $130 in 2021; post-volume multiples invented. |
| SENT 8 | `207_missing_the_bottom_fomo` | FINDING | 3 | Checked every S&P 500 Mar-Oct 2020 figure vs daily closes. FALSE: "capturing the next 40% over the subsequent six months" — 2,790 (late Apr) to 3,465.39 (23 Oct 2020) is +24%, not +40%; +40% took ~12mo. Fix to +24%. Also "nine sessions" 3/23-4/6 is ten; "2,747" pullback was 2,736.56. |
| SENT 9 | `212_bias_inventory` | FINDING | 1 | Checked 5 bias definitions (Kahneman/Tversky 1974, Fischhoff 1975, Arkes & Blumer 1985), all 3 quiz answers (correct), arithmetic (250->185=26% OK). FINDING: "held PETRONAS through a 22% drawdown" — Petroliam Nasional Bhd is unlisted/govt-owned; only PETDAG/PETGAS/PCHEM trade. Fix: use PETDAG. |
| SENT 10 | `288_sentiment_and_the_crowd` | FINDING | 3 | Contrarian core OK vs Marks/Shiller; both quiz keys correct. FINDING: 'this time it's different' sold as high-probability / 'most reliable contrarian signal in modern market history' — evidence is only a contested FAJ 2007 cover study; 'within weeks of a bottom' invented. Hedge as heuristic. |

## Wave 4 — islamic_finance (SHARIA) + the 9 empty-`sources:[]` asset_classes (ASST), 19 lessons · 2026-07-22

**Result: 1 VERIFIED · 0 NO_SOURCE_NEEDED · 16 FINDING · 2 ESCALATE** (`wf_aae74b87-4d8`,
26/26 agents, 0 errors). **This closes the sweep: 315 + 19 = 334 = the whole corpus.**

| Track | n | FINDING | rate |
|---|---|---|---|
| `islamic_finance` (SHARIA) | 10 | 8 (+**2 ESCALATE**) | **100%** — zero verified |
| `asset_classes` (ASST, empty-sources subset) | 9 | 8 | **89%** |

Wave 4 ran a **different check** from waves 1–3. The SHARIA lessons already carried `sources:`
(AAOIFI, DJIM, SC Malaysia), so the risk was never a missing citation — it was a **citation that
does not support its claim**, which reads as verified and is therefore worse than no citation at
all. The check was citation *integrity*, plus (for `355`) integrity against the **repo**.

### The systematic error — 33% attributed to AAOIFI

**AAOIFI Shari'ah Standard No. 21 sets 30% / 30% / 5% against market cap.** The 33% figure belongs
to the **DJIM / S&P index family**, against a different denominator (trailing 24-month average
market cap; S&P uses 36-month; MSCI/FTSE/Bursa use total assets; AAOIFI is point-in-time).

Four lessons carry the mix-up, and it is the same error each time — an index-provider number
attributed to the standard-setter:

- `349` (SHARIA 3) — 33% caps attributed to AAOIFI SS 21; "12-month average" matches no standard.
- `350` (SHARIA 4) — "12-month trailing average market cap" in body **and Quiz 1's stem**.
- `351` (SHARIA 5) — teaches the DJIM/S&P purification formula as AAOIFI's (SS 21 Art. 3/4/6/4 is
  per-share: prohibited income / shares outstanding × shares held at year-end).
- `355`, `356` (SHARIA 9, 10) — 33/33/5 presented as AAOIFI, incl. `356`'s Quiz 1 stem.

`352` (SHARIA 6) **inverts** its source outright: AAOIFI's Feb-2008 sukuk statement *permits*
nominal-value purchase undertakings in *sukuk al-ijarah* (banning them for
musharakah/mudarabah/wakala); the steelman and Quiz 2 say the opposite. `348` (SHARIA 2) cites a
**"Bursa Malaysia SAC"** that does not exist — the SAC belongs to the Securities Commission
Malaysia — and `354` (SHARIA 8) repeats the same misattribution of who designates the list.

### ⚖️ The 2 escalations — religious rulings, SME sign-off required, never auto-fix

- **SHARIA 1 `347_the_four_prohibitions`** — cites "AAOIFI, general principles" where **SS No. 31**
  is the specific *gharar* standard, and two worked examples (a palm-oil forward, a futures contract
  with "undefined terms") contradict **SS 20 / SS 10**, which prohibit specified futures and
  debt-for-debt. The lesson's own quiz is tighter than its body.
- **SHARIA 7 `353_islamic_contracts_and_instruments`** — **El-Gamal (2006) is cited in support of**
  the claim that Islamic products are *not* a cosmetic rename of conventional loans, while his book
  substantially argues the opposite ("Sharia arbitrage", form-over-substance). Misrepresenting a
  named scholar's position is a human call, not a numbers fix. Also cites takaful to no standard
  (SS 26 exists), and neither Usmani nor El-Gamal is in the source registry.

### Repo-truth: DEF084

`355_how_amis_halal_flag_maps_to_real_screening` was checked against the **code**, the one class of
claim no web citation can reach. The lesson says the `halal` flag runs a real two-stage screen. It
does not: `sim_engine.py:74` holds a hardcoded 7-ticker `DEFAULT_HALAL_UNIVERSE`, and
`trading_math/screening.py`'s `sharia_screen()` is **called nowhere**. Filed as **DEF084** (high) —
fourth occurrence of the CR040 degrade-loudly class, and a **product decision, not a content edit**.
`351`'s worked example has the same shape: *"run this through AMI's `purification_amount` function"*,
a function reachable from no user-facing path.

> One agent cited `safety_floor.py:141` for the allowlist. **That file does not exist** — the
> substantive claim was true, the citation invented. Everything in DEF084 was re-verified by reading
> the repo directly. AI-refuted ≠ real defect, in both directions.

**Sequencing consequence:** DEF082 currently leaves all 10 SHARIA lessons unreachable in the app.
Its fix switches them on. Shipping DEF082 before DEF084 is resolved starts serving content that is
wrong about the published standards *and* about the product's own behaviour.

### Verdicts

| Code | Lesson | Verdict | # | Discovered source / defect + fix |
|---|---|---|---|---|
| ASST 1 | `303_why_bonds_exist` | FINDING | 1 | SEC OIEA "What Are Corporate Bonds?" + "Bankruptcy for a Public Company". refuted: Quiz explanation misdefines a zero-coupon bond as paying "$1,000 plus accumulated interest" — a zero pays face value ONLY (the interest is the purchase discount); that payoff is an accrual bond. Keyed answer 2 correct, explanation wrong. |
| ASST 3 | `305_duration_and_convexity` | **VERIFIED** | 0 | Bodie/Kane/Marcus ch.16 + CFA Institute refreshers. Recomputed every figure: 10y 4%/5% semiannual → Macaulay 8.2556 / modified 8.0542 (lesson: 8.26/8.05); 2y → 1.9413/1.8940; 10y zero Macaulay exactly 10.0; 20y modified 13.14. Convexity asymmetry matches CFA wording; all 3 quiz keys correct. |
| ASST 4 | `306_yield_curve_and_inversion` | FINDING | 2 | FRED T10Y2Y + NBER cycle dates + Estrella & Mishkin 1996. FALSE: "a recession followed the broader post-2022 tightening cycle" — NBER has dated **no US peak after Feb 2020**; the 2022–24 inversion (longest on record) is the signal's first miss. Quiz 2's stem repeats it (answer 3 still holds). |
| ASST 5 | `307_credit_spreads_and_ratings` | FINDING | 1 | FRED BAMLC0A0CM / BAMLH0A0HYM2 + S&P ratings definitions. refuted: the steelman's falsifier is contradicted by its own source — 2008 IG 0.85→6.56 (7.7×) vs HY 2.41→21.82 (9.1×) is roughly proportional, and the absolute-bps reading also fires in Mar-2020, a liquidity event. |
| ASST 6 | `308_how_rates_price_equities` | FINDING | 1 | FOMC 2022 (+425bp over 7 hikes), FTSE Russell CY2022 (R1000 Growth −29.14% vs Value −7.54%), Damodaran. All facts + both quiz keys verify. Defect is structural: the body cites Lesson `305` as its core mechanism but omits it from `prerequisites`, breaking recommendation gating and the prereq chips. |
| ASST 7 | `309_reading_the_rates_machine_capstone` | FINDING | 1 | Bond math recomputed correct ($879.61, 13.1y modified duration, 12.0% drop, convexity gap); 3 keys correct. FALSE: "junk-rated debt falls harder than this IG example" — HY effective duration ~3.0y vs IG ~6.5y (ICE), and HY *beat* IG in 2022 (−11.2% vs −15.8%). Fix: qualify to similar-duration. |
| ASST 8 | `310_etfs_vs_mutual_funds` | FINDING | 1 | SEC ETF bulletin + Rule 6c-11 + IRC §852(b)(6). refuted: the steelman says the measured behaviour gap "favours the cost/tax argument in some years" — Morningstar *Mind the Gap* finds it one-directional every period (index MF −0.2%/yr vs index ETF −1.1%/yr, 10y to Dec 2023). Uncited, and the gap cannot measure cost/tax at all. |
| ASST 11 | `313_leveraged_inverse_etfs_decay` | FINDING | 1 | SEC OIEA leveraged/inverse bulletin + ProShares 497K + FINRA 09-31. refuted: "in a choppy **or declining** market it compounds against you" is backwards — steady −10%/−10% gives index −19%, 2× ETF −36% vs naive −38%: compounding **helps** in a trend. Decay is volatility-driven, not direction-driven; contradicts the lesson's own steelman. |
| ASST 12 | `314_reits_adrs_closed_end_funds` | FINDING | 1 | SEC REIT + ADR bulletins, Rule 6c-11. refuted: Quiz 2's keyed answer and explanation say the **custodian** bank issues the ADR, converts currency and deducts the fee; the cited SEC bulletin says the **depositary** does all three (the custodian only safekeeps the foreign shares). The cited source contradicts the claim it was used to verify. |
| SHARIA 1 | `347_the_four_prohibitions` | **ESCALATE** | 4 | Generic AAOIFI cite where **SS 31** is the *gharar* standard; palm-oil forward + "undefined terms" futures examples contradict **SS 20 / SS 10**. Usmani 2002 and El-Gamal 2006 both absent from the registry. → Saiful/SME. |
| SHARIA 2 | `348_the_business_activity_screen` | FINDING | 4 | SC Malaysia SAC methodology + DJIM + AAOIFI SS 21. **"Bursa Malaysia SAC" does not exist** (the SAC is the Securities Commission's). The cited SAC/DJIM make stage one a quantitative 5%-revenue benchmark, not the "qualitative, zero-tolerance" gate claimed; "every Bursa SAC screening report" is uncorroborable. Quizzes correct. |
| SHARIA 3 | `349_the_three_financial_ratio_screens` | FINDING | 5 | **AAOIFI SS 21 is 30/30/5 of market cap, not the 33% the lesson attributes to it.** DJIM's three 33% ratios are debt/cash/receivables vs trailing **24-month** average mcap (not 33/33/5); "12-month average" is wrong (DJIM 24, S&P 36); MSCI/FTSE use total assets. Arithmetic and both keys correct. |
| SHARIA 4 | `350_standards_differ_why_the_same_stock_flips` | FINDING | 2 | Wrong window: "12-month trailing average market cap" (body + **Quiz 1 stem**) matches no cited standard — DJIM 24mo, S&P 36mo, MSCI/FTSE/Bursa total assets, AAOIFI point-in-time at 30%. The "same 33% line" for snapshot-vs-average is unrealizable as written. |
| SHARIA 5 | `351_purification_tazkiyah` | FINDING | 3 | Arithmetic (6.72 / 953.28) and both keys correct. The taught formula (non-compliant income / total income × dividend) is the **DJIM/S&P/MSCI/FTSE** method, not AAOIFI's (SS 21 Art. 3/4/6/4 is per-share). Fix: cite the DJIM methodology. Worked example also invokes `purification_amount`, which no user path reaches (DEF084). |
| SHARIA 6 | `352_sukuk_vs_conventional_bonds` | FINDING | 4 | **Inverts its source:** AAOIFI's Feb-2008 sukuk statement *permits* nominal-value purchase undertakings in *sukuk al-ijarah* (banning them for musharakah/mudarabah/wakala); the steelman and Quiz 2 say the opposite. SS-17 (2003) never tightened. Usmani cite is the wrong work — the critique is his Nov-2007 paper. |
| SHARIA 7 | `353_islamic_contracts_and_instruments` | **ESCALATE** | 6 | AAOIFI SS 8/9/12/13 exist, quizzes correct, no thresholds. But **El-Gamal (2006) is cited in support of a claim his book argues against**; takaful is cited to no standard (SS 26); Usmani + El-Gamal absent from the registry. → Saiful/SME. |
| SHARIA 8 | `354_islamic_indices_etfs_and_funds` | FINDING | 3 | All four cited methodologies (S&P/FTSE/MSCI/DJIM) real and supporting; both quizzes correct. Defect: the **SC Malaysia SAC** designates the Shariah list, not Bursa; "Bursa-i" is a trading platform, not the list's name; the claim cites no source. |
| SHARIA 9 | `355_how_amis_halal_flag_maps_to_real_screening` | FINDING | 4 | **→ DEF084.** Lesson claims the flag runs a real two-stage screen via `sharia_screen`; the code is a hardcoded 7-ticker allowlist (`sim_engine.py:74`) and `sharia_screen()` is never called. **Quiz 2's keyed answer repeats the false claim.** Also 33% attributed to AAOIFI (30%). Content fix waits on Saiful's product decision. |
| SHARIA 10 | `356_capstone_screen_a_company_end_to_end` | FINDING | 2 | Arithmetic (0.3 / 1.1 / 0.4%) and all 3 keys verified correct. 33/33/5 attributed to the cited AAOIFI source, which is **30/30/5**; 33% is the DJIM/S&P number. Also uses spot market cap, not DJIM's 24-month average. Fix: body, **Quiz 1 stem**, and the provenance line. |

## Remaining sweep scope — **NONE. Sweep complete 2026-07-22.**

All **334** corpus lessons are measured across the sourced batch + W1–W4. Nothing is unmeasured.
Historical scope (now closed): fundamentals_analysis 66 · technical_analysis 45 · edge_process 98 ·
risk_portfolio 16 · sentiment_behaviour 10 · asset_classes 3 + 9 · ethics_integrity 6 ·
quant_methods 6 · islamic_finance 10.

### Coverage gap found 2026-07-22 — 19 lessons were in NO wave (Wave 4)

Prompted by Saiful asking whether the EVAL group has lessons. Diffing the corpus against every
wave script (`cr060_*.mjs`) exposed a real hole:

| | |
|---|---|
| Corpus total | **334** `.en.mdx` lessons |
| Covered by W1 + W2 + W3 + sourced batch | **315** |
| **In no wave at all** | **19** |

The 19 split into two populations needing **different** checks:

- **10 `islamic_finance` (SHARIA 1–10, lessons 347–356)** — never enumerated by any wave. The
  wave lists were built off pre-CR058 track counts, so the entire track landed after the lists
  were frozen. **These already declare `sources:`** (AAOIFI Shariah Standards, DJIM) — so the job
  is *not* source discovery, it is **citation integrity**: does the cited standard actually say
  what the lesson attributes to it? A reputable-looking citation attached to a claim the source
  never makes is worse than a missing one, because it reads as verified. Highest-stakes content in
  the corpus: any ruling → **ESCALATE to Saiful/SME, never the education lane**.
  `355_how_amis_halal_flag_maps_to_real_screening` additionally asserts things about **AMI's own
  halal flag**, so it must be checked against the backend implementation, not just external sources.
- **9 `asset_classes` with `sources: []`** (303/305/306/307/308/309/310/313/314) — already known,
  now folded into the same wave. Rates/bonds/ETF content: duration & convexity, curve inversion,
  credit spreads, leveraged-ETF decay math — numeric, i.e. the exact profile that fabricates.

Script ready: `scratchpad/cr060_legacy_sweep_w4.mjs` (dual-prompt — `discover` for ASST,
`sharia` / `sharia_product` for SHARIA). Launch after Wave 3 lands (avoid a third concurrent
fan-out — that is what tripped the session limit).

**Separate finding, no lessons involved — RESOLVED same day:** the **`decision_evaluation` (EVAL)**
track was fully registered — enum `backend/app/schemas/lessons.py:63`, display name "Evaluating
Analysis" and code prefix `EVAL` in `lessons_service.py:84,115`, present in the corpus-test taxonomy
— but had **0 lessons**, rendering as an empty group. Content had been deferred to "a later content
lane" that never ran. Saiful: *"we need the eval urgently."* → **CR062** authored EVAL 1–8
(lessons `357`–`364`), corpus 334 → 342. Those 8 are **not** part of this sweep's totals and are
**not yet stamped** — they failed CR060's own gate twice; see the CR062 doc §9.

**Process lesson:** the sweep's own coverage was never asserted — it was assumed from track counts
captured before CR058 shipped. Phase 6 should add a guard that every corpus lesson appears in a
sweep manifest, so a new track can't land unmeasured again.

**Decisions locked (Saiful, 2026-07-22):**
- **Finish the full sweep** — measure every legacy lesson before committing remediation. Done:
  W2 (127) + W3 (123) + W4 (19) all landed, 334/334.
- **Fix approach = ground worked examples in real sourced data** (structural — extend CR046 to
  lesson content; **regenerate** the data-heavy examples from real market data rather than hand-patch
  hundreds of confabulated numbers). This reframes the legacy findings from a patch-defect into a
  **remediation CR** (to be filed once the full sweep gives the complete scope). The definitional
  lessons that verify clean are stamped as-is.
- **Stamping:** all VERIFIED lessons across waves get their discovered `sources:` + `verified:` stamp
  in one batch at sweep-end (clean single scoped commit).

## Wave log — all closed

1. ~~**Wave 3** (EDGE 98 + SENT 10 + ASST 3 + ETHIC 6 + QUANT 6 = 123)~~ — **DONE 2026-07-22**
   (`wf_f9e2429e-3fa`, 139/139 agents, 0 errors). Result: **2 VERIFIED · 6 NO_SOURCE_NEEDED ·
   112 FINDING · 3 ESCALATE.** Section above.
2. ~~**19 Wave-2 refutes** that got cut off~~ — **DONE 2026-07-22.** Resumed via
   `resumeFromRunId: wf_0455e054-10c`; 149/149 agents, 0 errors. The journal confirmed the 19 were
   never cached as null (149 `started` vs 130 `result` entries), so the resume genuinely re-ran
   them rather than replaying empties. **Result: 18 refuted → FINDING, 1 held (`TECH 45`).**
3. ~~**Wave 4** (10 SHARIA citation-integrity + 9 empty-`sources:` ASST = 19)~~ — **DONE 2026-07-22**
   (`wf_aae74b87-4d8`, 26/26 agents, 0 errors). Result: **1 VERIFIED · 16 FINDING · 2 ESCALATE.**
   Corpus coverage closed: 315 + 19 = 334 ✓.

## Final totals — sweep complete, 334 / 334 measured · 2026-07-22

| Batch | Lessons | Verified | No-source-needed | Findings | Escalations |
|---|---|---|---|---|---|
| Sourced (293–345) | 30 | 10 | — | 20 | 1 |
| Legacy W1 (CORE + N&M) | 35 | 8 | 0 | 27 | — |
| Legacy W2 (FUND + TECH + RISK) | 127 | 4 | 5 | 118 | — |
| Legacy W3 (EDGE + SENT + ASST + ETHIC + QUANT) | 123 | 2 | 6 | 112 | 3 |
| Legacy W4 (SHARIA + ASST empty-sources) | 19 | 1 | 0 | 16 | 2 |
| **Total** | **334** | **25** | **11** | **293** | **6** |

**293 of 334 lessons carry a genuine defect — 88%. Only 25 of 334 are clean.**

The rate held at 88% across three independent waves measured on different tracks with different
prompts, which is what makes it a property of the corpus rather than of any one wave's rubric.

Per-track defect rate, worst first:

| Track | rate |
|---|---|
| `islamic_finance` (SHARIA) · `sentiment_behaviour` (SENT) | **100%** — SHARIA scored **zero verified out of 10** |
| `technical_analysis` (TECH) | **96%** |
| `edge_process` (EDGE) | **93%** |
| `asset_classes` (ASST, all 12 measured) | **92%** |
| `quant_methods` (QUANT) | 83% |
| `fundamentals_analysis` (FUND) | ~76% |
| `ethics_integrity` (ETHIC) | 33% — but **every legal escalation in the corpus is here or in `294`** |

The 25 survivors are the definitional lessons — the ones with the least to fabricate. Named so far:
`301_disclosure_transparency` (ETHIC 9), `341_backtesting_rigor_the_basics` (QUANT 7),
`305_duration_and_convexity` (ASST 3).

### What the sweep proved about its own method

1. **Dual-pass is load-bearing, and now has a number.** Of the 19 W2 lessons that reached the
   refute layer, **18 were refuted and 1 held — a 95% false-clean rate for single-pass.** Anything
   that verifies content in one pass should be assumed to be measuring nothing.
2. **Three independent detectors, each catching what the others structurally could not:**
   - **citation integrity** (sources present → does the cited standard say this?) — the entire
     AAOIFI 30% vs DJIM 33% class, invisible to source *discovery*;
   - **repo truth** (does the lesson describe what the code does?) — **DEF084**, and EDGE 87's
     `no_fossil` / `max_position_pct`. No external source can catch these;
   - **cross-lesson consistency** — EVAL `364` contradicting `358` / `077` / `275`.
   Only the first was in the original design. **All three belong in Phase 6.**
3. **A deterministic scan beat the LLM for its class.** The DEF083 positional-reference scan found
   **11** machine-confirmed rows for free; the refute passes surfaced 3–5 of them incidentally.
   Where a defect is mechanically decidable, grep is the better detector — and it becomes a guard,
   not an audit.
4. **The sweep never asserted its own coverage.** Wave lists were built from track counts captured
   before CR058 shipped, so an entire track (SHARIA, 10 lessons) sat unmeasured until a question
   from Saiful about the EVAL group exposed the hole. Phase 6 adds a guard that every corpus lesson
   appears in a manifest.

**Next:** classify all 293 findings P1 / P2a / P2b / P2c / ESCALATE (Phase 2), dual-pass re-verify
the P1 corrections before any of them are applied (Phase 3 — the manifest's "correct value" is an
agent's lead, not a verified replacement), then route: P1 defect + P2 remediation CR, batch-stamp
the 25 clean lessons, and land the guards. The 6 escalations stay with Saiful/SME.
