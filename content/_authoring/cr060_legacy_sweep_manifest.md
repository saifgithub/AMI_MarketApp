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

## Wave 2 — fundamentals_analysis (FUND) + technical_analysis (TECH) + risk_portfolio (RISK), 127 lessons · 2026-07-22

**Result: 3 VERIFIED · 19 VERIFIED\* (pending refute) · 5 NO_SOURCE_NEEDED · 100 FINDING.** The
session hit its usage limit mid-run — all 127 got their discover-verify verdict, but 19
VERIFIED-candidates' adversarial refute could not run (marked **VERIFIED\***; re-run the 19 refutes
after the limit resets to confirm).

Per track: **TECH 43/45 findings (96%)** — every TA lesson is built on **fabricated OHLC/candle
data and made-up support/resistance/breakout levels** (the worst-hit track, pure CR046-in-prose).
**FUND 50/66 (76%)**. **RISK 7/16** — the best track: risk lessons are formula/arithmetic-based
(self-verifying), so 4 are NO_SOURCE_NEEDED and several verify; the findings there are arithmetic
slips (recovery-month figures, break-even win-rate wording), not confabulated history.

`VERIFIED*` = discover-verify passed, refute pending (not yet confirmed clean).

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
| FUND 17 | `151_geographic_and_segment_mix` | VERIFIED* | 1 | Apple Inc. — 2024 Form 10-K (FY ended Sept 28, 2024), MD&A: net sales by segment (Americas $167,045M, Europe $101,328M, Greater China $66,952M, Japan $25,052M, Rest of Asia Pacific $30,658M; total $391,035M), by category (Products $294,866M, Services $96,169M), Gross Margin (Products 37.2%, Services 73.9%); Genting Berhad — group results, segment revenue by |
| FUND 18 | `152_three_margins_deep` | FINDING | 1 | Verified NVDA FY2025 (rev $130.5B, GM 75%, op 62%, net 56%), WMT op 4.3% & GM ~24%, Public Bank NIM 2.2%, all arithmetic + both quiz answers. FINDING: WMT net margin stated ~2.6% but FY2025 10-K = $19.436B/$680.985B = 2.85% (~2.9%). Fix: 2.6% -> 2.9%. |
| FUND 19 | `153_margin_trend_analysis` | FINDING | 2 | Line 33's "+50bps/qtr for 4+ qtrs predicts a positive EPS surprise ~two-thirds of the time" is a fabricated stat, no reputable source (lit shows only a directional link). TSLA/META/TOPGLOV margins OK vs SEC filings; META 48% is consolidated, not Family-of-Apps. Fix: cut the two-thirds figure. |
| FUND 20 | `154_sector_margin_benchmarks` | FINDING | 1 | Verified company margins vs SEC filings: AAPL 31.5% op, AMZN 10.8%, NVDA 75%/62.5%, TSLA ~18% auto GM, WMT ~24% GM — correct. FINDING: line 31 lists COST in retail 'gross 22-28%', but Costco's gross margin is ~11% (10-K), a 2x error. Fix: drop COST (WMT/TGT fit; warehouse clubs ~11-13%). |
| FUND 21 | `155_operating_leverage_cyclicals` | FINDING | 2 | FINDING: Intel FY2024 example false — Intel reported a GAAP operating LOSS of $11.68B, not '~$0.9B breakeven'; '>95% decline'/'3x' fail (op income went >100% negative). Fits FY2023 ($54.2B rev, ~$0.09B op inc). UAL margin overstated: ~-4%→+5.2% (~10pt), not -7%→+5%/12pt. Quiz keys OK. |
| FUND 22 | `156_debt_maturity_ladder` | FINDING | 1 | Checked all claims vs MSFT FY2024 10-K + CRE data. FALSE (line 29): lesson says MSFT had 'no single year >8% of total debt'; 10-K shows FY2027 $9,250M = ~18% of $51.2B, the largest year. Fix: correct/drop the 8% clause. Other MSFT facts, arithmetic and both quiz answers verify correct. |
| FUND 23 | `157_short_term_vs_long_term_debt` | FINDING | 1 | Verified SVB $42B one-day run, AirAsia going-concern, both quizzes (ans 0 correct), CP ~$10B, current/quick-ratio defs. FINDING: AAPL 'fiscal 2024 ~$162B cash & securities' is the FY2023 total; FY2024 10-K = ~$157B. Fix to ~$157B; 0.1x ratio unaffected. |
| FUND 24 | `158_off_balance_sheet_liabilities` | FINDING | 2 | Vs SEC 10-Ks: Walmart FY2025 LT debt is $33.4B (excl current)/~$36B incl, NOT the '$44B' stated ($44B was FY2020); so op-leases are a ~40% addition, not 30%. United lease obligations ~$5B, not 'tens of billions'. Op-lease $14B, Ford, ASC842/IFRS16=2019 and both quiz math all correct. |
| FUND 25 | `159_when_high_debt_is_ok` | VERIFIED* | 1 | Internal Revenue Code §857(a) (REIT distribution requirement) — REITs must distribute ≥90% of taxable income; Federal Reserve capital rules (12 CFR Part 217) / Basel III (BCBS) — 4.5% minimum CET1; Fed S&R data — large-bank CET1 ~12%; Company 10-K filings (Duke, Southern, AEP) + Tenaga Nasional Bursa filings — utility net debt/EBITDA 5–6x, TNB coverage ~3x |
| FUND 26 | `160_three_cash_flow_statements` | VERIFIED* | 1 | Apple Inc. Form 10-K for FY ended September 28, 2024 (SEC EDGAR accession 0000320193-24-000123) — Consolidated Statements of Cash Flows: operating $118,254M; investing +$2,935M; financing $(121,983)M |
| FUND 27 | `161_capex_intensity_and_working_capital` | FINDING | 1 | MSFT FY2024 example wrong: it cites total D&A $22.287B as 'depreciation'/maintenance for a ~50/50 split, but the 10-K PP&E depreciation (the proxy the lesson defines) is $15.2B, giving ~$15.2B maint / ~$29.3B growth (~1/3:2/3). Capex $44.5B is correct. Fix: use $15.2B, drop '50/50'. |
| FUND 28 | `162_brand_moat_when_a_logo_is_pricing_power` | FINDING | 1 | Verified all company gross-margin claims (Nike 44.6% FY24, LVMH ~66-69%, LULU high-50s, KO>PEP; quiz math/answers correct). FINDING: Nestle Malaysia gross margin is ~30% (low-30s) across 2022-26, not "high-30s" (true only 2016-20). Fix: change "high-30s" to "around 30%". |
| FUND 29 | `163_network_effects_when_each_user_makes_the_next_one_stickier` | FINDING | 2 | Checked META/Visa/Mastercard vs SEC 10-Ks. FINDING: (1) META 2024 operating margin stated ~38%, actual FY2024=42% (38% is only Q1/Q2); (2) 'V and MA operating margins above 60%' false for Mastercard (~55%, never >60% since 2015). ~4B MAU & >75% gross margins verify OK. Fix both margin figures. |
| FUND 30 | `164_switching_costs_the_invisible_lock_in` | FINDING | 2 | Adobe and Salesforce do not disclose NRR (Salesforce reports ~8% attrition). Lesson asserts ADBE NRR 110-120% and CRM 107-112%, gross retention >90% as fact — uncorroborable from any primary source; 3rd-party estimates conflict. Fix: mark illustrative or use disclosed metrics. |
| FUND 31 | `165_cost_advantage_moats_when_being_cheaper_is_structural` | FINDING | 1 | Checked Costco/Amazon/Tesla/Tenaga + both quizzes vs FY2024 10-Ks; all hold EXCEPT Costco membership-fee share: line 27 says 70-80% and Quiz 2 says 75% of OPERATING income; actual ~52% FY24 ($4.8B/$9.285B), ~56% FY23. It's ~66-73% of NET income. Fix to ~52% or switch denominator. |
| FUND 32 | `166_moat_erosion_signals_how_to_see_it_two_years_early` | FINDING | 4 | Apple/Top Glove/GE hold. FINDING: Intel case misdates erosion. Quiz 2's 2020 endpoints false — server share ~93% not 80% (AMD ~7%; hit ~20% only 2023), GM ~56% not 53%, ROIC high-teens not 11%. Body 'low 40s by 2024' is really ~33% (Intel 10-Ks + Mercury Research). Fix figures/dates. |
| FUND 33 | `167_dcf_basics_why_terminal_value_eats_everything` | FINDING | 3 | DCF worked example mis-computed: the $1.4T explicit-FCF sum is UNDISCOUNTED, not 'present value' (true PV ~$0.86T); TV PV is ~$1.67T not $2.0T (its own Gordon formula); so total EV ~$2.5T not $3.4T and TV share ~66% not ~58%. Fix the discounting. Quizzes correct; general claims sourced to Damodaran. |
| FUND 34 | `168_ev_ebitda_vs_pe_when_to_use_which` | VERIFIED* | 1 | Damodaran — Investment Valuation (relative-valuation / earnings-multiples chapters) [Tier 3 canon]: EV/EBITDA vs P/E, leverage & tax distortion of equity multiples, EBITDA's capex + SBC blind spots, EV/EBIT when D&A != capex, sector multiples (banks->P/B, REITs->P/FFO); AT&T / Verizon / Tesla / Ford FY2024 10-K filings [Tier 1] + market-data providers — corr |
| FUND 35 | `169_sum_of_the_parts_when_one_company_is_really_three` | VERIFIED* | 1 | Amazon.com, Inc. — Form 10-K / 2024 Annual Report (FY2024 segments): AWS revenue $107.6B & operating income $39.8B (~37% margin); Advertising services $56.2B; total net sales $638.0B — backs lesson's AWS ~$110B/~35%, Ads ~$60B, Retail ~$450B residual; Aswath Damodaran — valuation works: sum-of-the-parts valuation and the conglomerate/diversification discount |
| FUND 36 | `170_scenario_analysis_bear_base_bull_done_honestly` | FINDING | 1 | Arithmetic all correct; both quiz keys (answer=0) correct; AirAsia 2020–24 distress claim verified via Bursa/SC PN17. FINDING: lesson states TSLA traded ~$260 mid-2026, but actual was ~$380–$450 (~$409 May, ~$381 mid-July). Fix: use real anchor + recompute scenario %, or label price hypothetical. |
| FUND 37 | `171_valuation_across_industries_no_single_multiple_fits` | FINDING | 1 | All claims/quizzes verify except one false JPM data point: "1.8x P/TBV, ~17% ROTCE" is wrong. JPM was ~2.95x P/TBV in May 2026 (now 3.27x; 10yr median 2.0x), ROTCE 20% FY2025 / 23% Q1'26. Fix: ~3x P/TBV, ~20% ROTCE (still supports the 20%-ROTCE→2.0x+ point). |
| FUND 38 | `172_peer_selection_criteria_before_you_look_at_the_numbers` | VERIFIED* | 1 | Aswath Damodaran — Investment Valuation (relative valuation / comparable-company selection): peers matched on sector, size/scale, growth, risk; EV/EBITDA for capital-intensive sectors (Tier 3 canon); SEC EDGAR — FY2024 Forms 10-K, annual operating revenue: UAL ~$57.1B, DAL ~$61.6B, AAL ~$54.2B, LUV ~$27.5B, JBLU ~$9.28B (Tier 1); Bursa Malaysia / Malayan Ban |
| FUND 39 | `173_adjusting_comps_for_size_leverage_growth` | FINDING | 1 | Arithmetic + quizzes correct; PEG/EV-EBITDA/leverage concepts trace to Damodaran. FINDING: load-bearing '10-25%' comps-mispricing stat (intro + Takeaway) is unsourced; Alford (1992) found size/leverage/growth adjustments don't cut error beyond industry. Fix: drop % or cite a study. |
| FUND 40 | `174_stock_based_compensation_the_hidden_dilution` | FINDING | 4 | Checked SNOW/MSFT/META figures + both quizzes vs SEC filings. FINDING: MSFT FY2024 buybacks were $17.25B, not '$25B+'; SNOW adj FCF is 29%/$810M not 27%/$760M, SBC $1.23B not $1.1B, SBC-honest FCF ~-15% not -12% (gap ~44pt). Fix these numbers; both quizzes are correct. |
| FUND 41 | `175_gaap_vs_non_gaap_and_accruals_quality` | VERIFIED* | 1 | Sloan, R. G. (1996). "Do Stock Prices Fully Reflect Information in Accruals and Cash Flows About Future Earnings?" The Accounting Review, 71(3), 289–315 — accruals anomaly; ~10% hedge abnormal annual return (NOT on registry allowlist, but a clearly reputable peer-reviewed canonical source); U.S. SEC — Regulation G and Item 10(e) of Regulation S-K (non-GAAP m |
| FUND 42 | `176_trailing_vs_forward_pe` | FINDING | 1 | Definitions correct per Damodaran; arithmetic + both quiz keys (answer 0) verified. FINDING: the "real markets" NVDA claim is false — mid-2026 NVDA ~$207, TTM EPS ~$6.53 (~32x/21x), not $135/$3.20/42x/28x. Fix: mark it illustrative or use real figures. |
| FUND 43 | `177_pe_in_cyclicals_peak_earnings_trap` | VERIFIED* | 1 | Aswath Damodaran — "Ups and Downs: Valuing Cyclical and Commodity Companies" (Stern/NYU, SSRN #1466041): trailing P/E misleads for cyclicals; normalize earnings across the cycle; Graham & Dodd — Security Analysis: average earnings over a full business cycle (allowlist Tier 3) |
| FUND 44 | `178_shiller_cape_normalised_pe` | FINDING | 2 | Shiller CAPE "sits near 32x" is wrong: Shiller's data shows ~40.3 in May 2026 (lesson date), ~41 now (mean 17.4, record 44.19 Dec-1999); Quiz 1 stem repeats "32x". Trailing P/E "~22x" also low (~26). Fix: CAPE→~40x (near record, not merely top-decile), P/E→~26x. |
| FUND 45 | `179_peg_ratio_price_for_growth` | FINDING | 1 | Verified Lynch PEG≈1.0 rule, all arithmetic, both quiz answers (correct). FINDING: SNOW 'net retention runs above 130%' is false — SNOW's NRR was ~125-126% by the May-2026 date; last >130% was Jan-2024. Fix to ~125% (still supports the point). Gross-margin 70%+ claim is fine. |
| FUND 46 | `180_tangible_book_vs_reported_book` | FINDING | 2 | Verified KHC ($15.4B write-down, -27%) and JPM (BVPS $116, P/B 1.9x). FINDING: Salesforce goodwill+intangibles is ~$54-56B per 10-K, not $80B, so tangible book is POSITIVE (~+$6B), not −$20B/undefined — lead example is false. 2nd: KHC book chronology inverted ($51B is post-writedown, not pre-). |
| FUND 47 | `181_pb_for_banks_regulatory_book` | FINDING | 2 | Verified: Basel III CET1/RWA defs + 11.5% G-SIB CET1 min (Fed/BIS), ROE-vs-CoE->P/B principle (Damodaran), quiz math OK. FINDING: real snapshots false at lesson date 2026-05-12 — JPM was $304.88 not ~$220 (P/TB ~2.8x vs 2.2x); BAC $50.78 not ~$42 (~1.75x vs 1.6x). Fix or mark illustrative. |
| FUND 48 | `182_pb_for_asset_light_businesses` | FINDING | 2 | MSFT snapshot false: lesson says mid-2026 P/B~11x, book/sh ~$42; actual ~6.7x, book/sh $55.78 (Mar-2026 filing). NFLX 15.5x also overstated (~12x; 10:1 split makes $700 stale). Fix/relabel these. META/CRM ok; thesis, toolkit, both quiz answers correct. |
| FUND 49 | `183_high_roe_low_pb_buffett_framing` | VERIFIED* | 1 | Aswath Damodaran — 'Price-Book Value Ratio' valuation notes (NYU Stern) — justified P/B = (ROE − g)/(r − g), ROE as the primary determinant of P/B (Tier 3); Bodie, Kane & Marcus — 'Investments' — DuPont decomposition of ROE (equity multiplier / financial leverage), basis for Quiz 1's leverage diagnostic (Tier 3); Berkshire Hathaway Inc. — Form 8-K, 2018-07-1 |
| FUND 50 | `184_dupont_decomposition_deep` | FINDING | 2 | DuPont formula, all arithmetic, and both quiz answers verified correct. FINDING: lesson calls the four real examples "all near 20-25% ROE"/"same range," but JPM~17% and MSFT is listed 36% (real ROE ~40-47% FY20-22 per 10-Ks) are both outside. Fix the framing or the MSFT figure. |
| FUND 51 | `185_roe_vs_roic` | VERIFIED* | 1 | Aswath Damodaran (NYU Stern), 'Return on Capital (ROC), Return on Invested Capital (ROIC) and Return on Equity (ROE): Measurement and Implications' — ROIC = NOPAT/(BV equity + BV debt − cash); value created only when ROIC > cost of capital (Tier 3 canon: Damodaran valuation works); Company annual filings (10-K / annual report): Ford, Microsoft, Netflix, Exxo |
| FUND 52 | `186_sustainable_roe_mean_reversion` | FINDING | 4 | Thesis sound (Fama-French 2000). FINDING: NFLX ROE was ~24.5%/26% in 2022-23, NOT "~15%"; AAPL not ">40% for a decade" (FY14/16/17 ~35-36%); "Bartov...classic study" mis-attributed; median/decile stats (11-13%,18-22%,8-12%) uncited. Fix: correct NFLX+AAPL, drop Bartov, cite 10-Ks & Fama-French. |
| FUND 53 | `187_roe_inflation_via_buybacks` | FINDING | 1 | Vs Apple 10-Ks: ROE~150%, >$700B buybacks, ~40% share cut, FY2017 equity $134B, NI $97B, both quizzes all OK. FALSE: 'business compounds ~15-18% in revenue-and-earnings terms' — real revenue CAGR ~8%, net-income ~9-10%; 15-18% is buyback-inflated EPS. Fix to ~8% rev / ~10% earnings. |
| FUND 54 | `188_net_debt_to_ebitda` | FINDING | 2 | FINDING: quizzes/hypotheticals OK, but AT&T FY2024 wrong — lesson $140B debt/$7B cash/$42B EBITDA/3.2x vs actual $123.5B/$3.3B/$44.8B/~2.7x. Apple's "$65B cash & marketable securities" is really $156.65B (Apple net-cash, not 0.3x). Fix: AT&T's reported 2024 figures; relabel Apple's cash. |
| FUND 55 | `189_interest_coverage_ratio` | FINDING | 2 | Checked all figures + quiz math vs SEC filings. Quizzes and MSFT (~37x) OK. FINDING: Whirlpool 2024 EBIT is not ~$1.3B (actual GAAP $63M, ongoing $887M; interest $358M), so coverage is ~2.5x not 3.5x; WHR was cut to junk in 2024, not "lower-end investment-grade." Fix the WHR example. |
| FUND 56 | `190_debt_to_asset_ratio` | FINDING | 3 | Verified real-co figures vs SEC 10-Ks/TNB report. FINDING: (1) AAPL FY24 equity ~$57B not $65B, so D/E ~1.7x not 1.5x; (2) Quiz2 stem says D/E=0.7x but debt$7B/equity$7B=1.0x; (3) TENAGA FY24 assets ~MYR200B not 175B, D/A ~28-43% not 37%. Fix figures/ratios. MCD negative-equity claim TRUE. |
| FUND 57 | `191_fixed_vs_floating_and_currency_mismatch` | VERIFIED* | 1 | Federal Reserve — FOMC policy actions Mar 2022–Jul 2023 (fed funds target range raised from 0–0.25% to 5.25–5.50%); Bursa Malaysia / Capital A (AirAsia Group) — PN17 classification Jan 2022 & annual reports (USD aircraft-lease/fuel liabilities vs ringgit revenue); IMF — EM currency-crisis / currency-mismatch literature (Mexico 1994, Asia 1997, Argentina 2001 |
| FUND 58 | `192_payout_ratio_on_fcf` | FINDING | 3 | JPM 2024 CFO was NEGATIVE $42B, not +$54B, so the 26% payout-on-FCF is false (per 10-K). ITW's "$3.3B FCF" is op cash flow; real FCF $2.84B, NI $3.49B not $3.7B. KO's ~$10B FCF is the ex-IRS-deposit figure; GAAP FCF was $4.7B → ~176% not 80%. Fix figures; quizzes ok. |
| FUND 59 | `193_dividend_safety_scoring` | FINDING | 1 | Verified AT&T 2022 cut (SEC 8-K), MSFT div since 2003 (SEC), REIT >=90% mandate (IRC 857), PG&E 2017 suspension; both quizzes correct. FINDING: the '~2-4% annual base rate of S&P 500 dividend cuts' is uncorroborable from any reputable source. Fix: cite S&P DJI dividend data or soften the figure. |
| FUND 60 | `194_the_yield_trap` | VERIFIED* | 1 | AT&T Inc. Form 8-K (SEC EDGAR, CIK 0000732717), filed Feb 1 2022 — WarnerMedia/Discovery spinoff; post-close annual dividend reset to $1.11 from $2.08 (~47% cut); The Kraft Heinz Company Form 8-K / Q4 2018 earnings release, Feb 21 2019 — quarterly dividend cut $0.625->$0.40 (36%) alongside $15.4B impairment; Company/exchange filings: Enbridge Inc. investor d |
| FUND 61 | `195_special_dividends_and_one_offs` | VERIFIED* | 1 | Costco Wholesale Corp — SEC Form 8-K filings & IR dividend history: specials $7 (Dec 2012), $5 (2015), $7 (2017), $10 (2020), $15 (2024); regular qtr dividend $1.16→$1.47 [Tier 1]; Costco Form 8-K Nov 28 2012 (EX-99.1): $7.00 special accelerated to Dec 18 2012 ahead of the 2013 dividend-tax increase / fiscal cliff [Tier 1]; Texas Pacific Land Corp — press re |
| FUND 62 | `196_organic_vs_acquired_growth` | VERIFIED* | 1 | Damodaran — valuation works (value creation from growth; ROIC vs. cost of capital) — Tier 3 canon; backs the organic-vs-acquired framework and Quiz 2; Constellation Software Inc. annual reports / MD&A (long-run revenue CAGR ~20%+, low-single-digit organic growth, ROIC ~25%) — Tier 1 company filings; Valeant Pharmaceuticals International Form 8-K FY2015/FY201 |
| FUND 63 | `197_revenue_vs_eps_buyback_divergence` | FINDING | 1 | Arithmetic (body + both quizzes) and AAPL/BRK-B claims verified. FINDING: "IBM in the 2010s bought back over $100B" is overstated — 2010–2019 repurchases were ~$88B; every $100B+ figure spans pre-2010 ($110B since 2000; $125B 2005–15). Fix: use ~$90B in the 2010s or widen the window. |
| FUND 64 | `198_garp_and_peg_math` | FINDING | 2 | GARP/PEG (Lynch/Damodaran), arithmetic + both quizzes, META EPS +73%/+60% (2023/24) all check out. FINDING: (1) line 40 'falsifiable' backtest (PEG<1 & ROE>15% & growth>10% beats index 3yr w/ significance) is uncorroborable, cut/soften; (2) META ~$90 trough was Nov 2022, not 'early 2023'. |
| FUND 65 | `199_roic_vs_wacc_and_the_four_pillar_checklist` | FINDING | 1 | Checked defs, Greenblatt Magic Formula, MSFT/AAPL FY2024 financials, both quizzes (quiz logic+arithmetic correct). FINDING: MSFT "invested capital ~$200B, ROIC ~45%" wrong for FY2024 — 10-K gives IC ~$240B and reported ROIC ~24-26% (~37% by lesson's own formula); 45% was ~FY2020. Fix the numbers. |
| FUND 66 | `285_reading_a_pe_ratio` | VERIFIED* | 1 | Damodaran — valuation works (P/E = price ÷ trailing EPS; trailing vs forward P/E; P/E as market pricing of expected growth); Bodie, Kane & Marcus — Investments (earnings multiplier / P/E and the P/E-to-growth relationship underpinning Quiz 2's PEG intuition); Shiller — Irrational Exuberance / long-run S&P 500 P/E dataset (long-run trailing mean ~15.5, suppor |
| RISK 1 | `013_why_risk_matters_more_than_profit` | FINDING | 2 | 2 arithmetic defects; drawdown math (50->100,20->25,10->11.1%) & both quiz answers correct. FINDING: Quiz-2 explanation '+72% to return to starting value' is wrong—+72% recovers the $129k PEAK; the $100k start needs only ~+34% and Trader A ends +7.7% above it. Body '$4,400 (~1%)' should be ~$1,044. |
| RISK 2 | `014_position_sizing_basics` | VERIFIED | 0 | CMT Association — Chartered Market Technician curriculum, Risk Management: percent-risk (fixed-fractional) position sizing model — shares = (account equity × risk %) ÷ (entry price − stop price); GARP — FRM body of knowledge, risk management: risk-per-trade / position sizing |
| RISK 3 | `015_stop_loss_basics` | VERIFIED | 0 | SEC Office of Investor Education and Advocacy — Investor Bulletin: Stop, Stop-Limit, and Trailing Stop Orders (a triggered stop becomes a market order; "the stop price is not the guaranteed execution price" and can deviate significantly in a fast-moving/gapping market); CMT Association — technical-analysis body of knowledge: reward-to-risk ratio = (target − |
| RISK 4 | `016_risk_reward_ratio` | FINDING | 1 | Verified all arithmetic + both quizzes (correct). FINDING: intro says a 1:0.8 R:R needs 'almost two-thirds' win rate to break even, but risk/(risk+reward)=1/1.8=55.6% — just over half (its own flip example gives 53%). Fix: say ~56%/'more than half', or change ratio to 1:0.5. |
| RISK 5 | `017_portfolio_exposure_and_correlation` | FINDING | 2 | Verified both quiz answers (index 1; 5.2% OK) + S&P500 AAPL+MSFT ~13% weight. FINDING: 'Q1 2025 Tuesday, Nasdaq-100 -3.4%, five names -4-7%' + JPM/XOM/KO/IHH same-day moves match no real day (real Q1'25 routs were Mondays); Bursa label wrong. Fix: relabel hypothetical or cite a dated day. |
| RISK 6 | `018_drawdown_management` | FINDING | 2 | Recovery-math all correct (20->25,50->100,30->42.9,15->17.6,40->66.67,35->53.8%; both quizzes right). 2 FINDINGS: (1) 15% dd's 17.6% recovery = '6-9 months at 1%/mo' but is ~16-18 mo; (2) '<20% dd recovers in under a year' conflicts w/ the 1%/mo rate (25% gain ~=25 mo). Fix the month figures. |
| RISK 7 | `101_volatility_adjusted_sizing` | VERIFIED* | 1 | CMT Association — Body of Knowledge, technical-analysis standards: Average True Range (ATR) as a volatility measure and volatility-based stop placement (Tier 2 allowlist); J. Welles Wilder Jr. — New Concepts in Technical Trading Systems (1978): definition of Average True Range and its 14-period default (canonical TA origin) |
| RISK 8 | `102_atr_based_stops` | VERIFIED* | 1 | CMT Association — technical-analysis standards / body of knowledge (Average True Range; 14-period standard) [Tier 2 allowlist]; J. Welles Wilder Jr., New Concepts in Technical Trading Systems (1978) — canonical origin of ATR + 14-period default (reputable TA canon; not on allowlist) |
| RISK 9 | `103_trailing_stops` | VERIFIED* | 1 | CMT Association — technical-analysis standards (Chandelier Exit, per Chuck LeBeau; ATR-based trailing stops; swing-low stops) [Tier 2 allowlist]; J. Welles Wilder Jr., New Concepts in Technical Trading Systems (1978) — Average True Range, 14-period default (canonical primary source for ATR) |
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
| TECH 45 | `286_what_is_a_chart` | VERIFIED* | 1 | CME Group — Technical Analysis course, "Chart Types: Candlestick, Line, Bar" (cmegroup.com/education) — line chart = closing prices; candlestick OHLC structure, body = open-to-close range, wicks = high/low, up/down color convention; CMT Association — technical-analysis standards (candlestick interpretation; volume-confirmation conventions on breakouts) |

## Remaining sweep scope

fundamentals_analysis 66 · technical_analysis 45 · edge_process 98 · risk_portfolio 16 ·
sentiment_behaviour 10 · + new-track stragglers (asset_classes 3, ethics_integrity 6, quant_methods
6). Plus the 9 empty-`sources:[]` asset-class lessons (303/305/306/307/308/309/310/313/314).

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

**Separate finding, no lessons involved:** the **`decision_evaluation` (EVAL)** track is fully
registered — enum `backend/app/schemas/lessons.py:63`, display name "Evaluating Analysis" and code
prefix `EVAL` in `lessons_service.py:84,115`, present in the corpus-test taxonomy — but has
**0 lessons**. It renders as an empty group. The code comment says content was deferred to "a
later content lane" that never ran. Needs either content or de-registration; flagged to Saiful.

**Process lesson:** the sweep's own coverage was never asserted — it was assumed from track counts
captured before CR058 shipped. Phase 6 should add a guard that every corpus lesson appears in a
sweep manifest, so a new track can't land unmeasured again.

**Decisions locked (Saiful, 2026-07-22):**
- **Finish the full sweep** — measure every legacy lesson before committing remediation. Wave 2
  (FUND+TECH+RISK, 127) + Wave 3 (EDGE+SENT+ASST+ETHIC+QUANT, 123) run next.
- **Fix approach = ground worked examples in real sourced data** (structural — extend CR046 to
  lesson content; **regenerate** the data-heavy examples from real market data rather than hand-patch
  hundreds of confabulated numbers). This reframes the legacy findings from a patch-defect into a
  **remediation CR** (to be filed once the full sweep gives the complete scope). The definitional
  lessons that verify clean are stamped as-is.
- **Stamping:** all VERIFIED lessons across waves get their discovered `sources:` + `verified:` stamp
  in one batch at sweep-end (clean single scoped commit).

## Resume state — session usage limit hit 2026-07-22 (resets 4:20am Asia/Riyadh)

Two things pending, both cheap; run after the limit resets (or next session):

1. **Wave 3** (EDGE 98 + SENT 10 + ASST 3 + ETHIC 6 + QUANT 6 = 123) — script ready at
   `scratchpad/cr060_legacy_sweep_w3.mjs` (embedded lessons, compact returns). Launch with
   `Workflow({scriptPath: ".../cr060_legacy_sweep_w3.mjs"})`.
2. **19 Wave-2 refutes** that got cut off (marked `VERIFIED*` above) — re-run to confirm-clean:
   `Workflow({scriptPath: ".../cr060_legacy_sweep_w2.mjs", resumeFromRunId: "wf_0455e054-10c"})`
   (replays the 108 cached agents instantly, re-runs only the 19 failed refutes). Pending codes:
   FUND 17, 25, 26, 34, 35, 38, 41, 43, 49, 51, 57, 60, 61, 62, 66 · RISK 7, 8, 9 · TECH 45.

**At sweep-end** (after Wave 3 + the 19 refutes): batch-stamp every VERIFIED lesson with its
discovered `sources:` + `verified:` (one scoped commit), and file the **remediation CR** (ground
worked examples in real sourced data / regenerate the data-heavy examples — the FINDINGs across all
waves are its scope).

### Running totals (measured 192 of ~317 unverified lessons)

| Batch | Lessons | Verified | Pending refute | No-source-needed | Findings |
|---|---|---|---|---|---|
| Sourced (293–345) | 30 | 10 | — | — | 20 (+1 legal escalation) |
| Legacy W1 (CORE+N&M) | 35 | 8 | — | 0 | 27 |
| Legacy W2 (FUND+TECH+RISK) | 127 | 3 | 19 | 5 | 100 |
| **Total** | **192** | **21** | **19** | **5** | **147** |

**~77% of measured lessons carry a genuine defect**, overwhelmingly confabulated worked-example
data. Remaining unmeasured: Legacy W3 (123) + the 9 empty-`sources:[]` asset-class lessons.
