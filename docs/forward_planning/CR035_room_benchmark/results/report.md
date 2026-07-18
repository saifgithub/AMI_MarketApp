# CR035 Room-vs-Street benchmark report

Generated 2026-07-18 09:21 UTC · baseline batch `baseline150-2026-07-17`

## Headline

- Scored runs: **146** (rejects: 0, unscored: 0, PM parse-fallbacks excluded per DEF058: 4 — MSFT, ORCL, PEP, UAL)
- Agreement vs pooled Street consensus (all scored): **73/146 (50%)**
- Agreement on Buy/Hold-consensus names (Room's expressible space): **73/144 (51%)**, Cohen's κ = **0.14**
- Red-line violations (Room Buy on Street-Sell name): **0/2**

## Confusion matrix (baseline)

| Room \ Street | Buy | Hold | Sell |
|---|---|---|---|
| **Buy** | 29 | 7 | 0 |
| **Hold** | 64 | 44 | 2 |

The Room is buy-side only (no Sell verdict exists), so the Sell column can
never be 'matched' — on Street-Sell names the pass criterion is Hold, not Buy.

## Per-source agreement (Buy/Hold-consensus names)

- yahoo: 73/144 (51%)
- stockanalysis: 71/144 (49%)

## Target sanity (Room target vs Yahoo mean analyst target, Buy verdicts)

Average diff: **-0.7%** over 36 names. Per ticker:

- AAPL: +17.2%
- ABBV: -0.0%
- ABT: -0.0%
- AMZN: +0.0%
- AVGO: +0.0%
- BLK: -0.0%
- CMCSA: +0.0%
- DAL: -0.0%
- DASH: +0.0%
- DE: -0.0%
- DELL: -0.0%
- DIS: -0.0%
- EOG: -0.0%
- FDX: +0.0%
- GILD: +0.0%
- GS: +10.1%
- HRL: +0.0%
- INTC: +0.0%
- INTU: -0.0%
- LVS: -17.6%
- NKE: +0.0%
- PGR: +0.0%
- PINS: +0.0%
- QCOM: -0.0%
- RTX: +0.0%
- SOUN: -0.0%
- SPOT: -0.1%
- STZ: -10.4%
- SWKS: +0.0%
- SYK: +0.0%
- T: -12.1%
- TSLA: +6.5%
- VRTX: +0.0%
- WDC: -0.0%
- WMT: +0.0%
- WYNN: -17.3%

## Per-ticker detail (baseline)

| Ticker | Room | Street | Match | Reason (truncated) |
|---|---|---|---|---|
| AAPL | APPROVE | buy | ✅ | The entry and sizing are approved as modified to mitigate extreme short-term exhaustion risks signaled by high RSI and volume divergence. The allocation is redu |
| ABBV | APPROVE | buy | ✅ | The PM rejects the trader's aggressive 8% allocation due to high valuation and low volume, opting instead for a modified 5% position to preserve capital. This e |
| ABNB | PASS | buy | — | Verdict: PASS (WAIT). The research synthesis and risk debators correctly identify that entry at $146.03 is premature, as the stock trades at the upper bound of  |
| ABT | APPROVE | buy | ✅ | I approve the 3% size to capture the technical breakout above $102.13, which is confirmed by above-average volume and an RSI of 64, leaving room for expansion t |
| ADBE | PASS | hold | ✅ | The Trader’s WAIT directive is endorsed: the RSI of 80 confirms extreme overbought conditions, and the lack of volume above the 20-day average indicates no imme |
| ADI | PASS | buy | — | The provided input contains an action value 'MODIFY-AND-APPROVE' which is invalid according to the strict schema requiring either 'APPROVE' or 'PASS'. Although  |
| ADP | PASS | hold | ✅ | Compliance and risk checks confirm a WAIT; the RSI of 81 and failed breakout at $257.36 present immediate mean-reversion risk that conflicts with the long-term  |
| AES | PASS | hold | ✅ | The proposal is REJECTED in the sense of execution: no entry is authorized at this time. Consensus aligns on a WAIT stance due to the insufficient 1.3% upside t |
| AMC | PASS | hold | ✅ | I uphold the Trader's PASS directive and the Research Manager's synthesis: AMC's $7.59B net cash burden and -11% FCF margin constitute a structural capital allo |
| AMD | PASS | buy | — | The proposed 5% size is rejected; a 19% drawdown to the $407 stop consumes 63% of the user's total 30% max drawdown allowance, violating the mandate's risk prof |
| AMZN | APPROVE | buy | ✅ | The portfolio manager modifies the trader's original 15% size down to 5% to mitigate value-trap risks and volatility concerns identified by the risk debaters. T |
| APD | PASS | buy | — | APD is REJECTED due to valuation-risk misalignment: 31.8x P/E and PEG 2.22 justify a $267.00 entry to respect the 30% max drawdown, while the $314.87 breakout r |
| AVGO | APPROVE | buy | ✅ | The 0.44 PEG ratio validates the growth thesis against the 48% TTM revenue, making the current entry efficient for a long-horizon mandate despite the 62.0x P/E. |
| BA | PASS | buy | — | The verdict remains PASS as the proposed entry at $215.45 lacks momentum confirmation and presents an unappealing 1:1 risk-reward against a 3/5 risk score. Nega |
| BAC | PASS | buy | — | The proposed 'WAIT' status is compliant with the long-horizon wealth mandate, as entering at RSI 71 and $61.93 would violate prudent risk management for a risk  |
| BBAI | PASS | hold | ✅ | I concur with the WAIT directive; the proposed 1.5% size from the Neutral Debator exposes the portfolio to a 30%+ drawdown if the $2.91 support fails, directly  |
| BBWI | PASS | hold | ✅ | We agree with the Trader's WAIT stance; entering at $21.12 ignores the Bear's valid warning of a retest to $14.28, which would breach the 30% max drawdown cap.  |
| BGS | PASS | sell | — | The mandate prioritizes long-horizon wealth preservation, which is incompatible with a distressed balance sheet carrying -$1994M net cash and negative FCF, as t |
| BKNG | PASS | buy | — | Trade rejected due to compliance: mandate requires long-term wealth compounding (3–10 year horizon), but the proposed 12-month horizon violates this core constr |
| BLK | APPROVE | buy | ✅ | The proposal modifies the size to 7% to respect the 30% drawdown cap, avoiding excessive single-trade risk. The entry at 1077.66 captures current momentum and y |
| CAG | PASS | hold | ✅ | CAG remains in a pre-provement phase with negative FCF margins and leverage that contradict the long-term wealth mandate. The Research Manager’s directive to wa |
| CAR | PASS | hold | ✅ | The consensus hold rating with a $134.14 target implies limited upside from the $156.35 current price, while the -6% FCF margin and -$27.14B net cash position p |
| CAT | PASS | buy | — | The Research Manager and Trader correctly identify a structural valuation disconnect, with a 43.7x P/E and 2.15 PEG ratio far exceeding the 22% revenue growth,  |
| CHWY | PASS | buy | — | REJECT due to lack of immediate entry signal: RSI 74 indicates overbought conditions with volume below the 20-day average, offering no margin of safety for a ne |
| CI | PASS | buy | — | The trader's proposal to size the position at 10% exceeds the 50% single-name cap and, more critically, exceeds the conservative debator's warning that the nega |
| CL | PASS | buy | — | The Trader’s WAIT stance is confirmed as the only prudent path given the unfavorable risk-reward asymmetry at $94.09. With the $96.6 consensus ceiling offering  |
| CLSK | PASS | buy | — | I concur with the Trader’s Hold stance. CleanSpark’s **-68% FCF margin** and **-$1.53B** net cash position present an unacceptable risk of permanent capital imp |
| CMCSA | APPROVE | hold | — | The position is approved at a reduced 5% size to mitigate single-name concentration risk in a stagnant value trap, limiting potential drawdown to 2.5% if suppor |
| COIN | PASS | buy | — | The portfolio is at a critical juncture where the RSI of 100 and the 15.6 P/E multiple create an asymmetric risk profile; a potential -25% drawdown from the cur |
| COST | PASS | buy | — | The proposal is a WAIT state, which correctly identifies that current consolidation at $948.05 lacks the technical conviction required for entry. The Research M |
| CPB | PASS | hold | ✅ | I am rejecting immediate entry as the Research Manager and Trader correctly identified that the technical setup—specifically the failure to clear the $23.67 bre |
| CRM | PASS | buy | — | The Trader’s WAIT recommendation is upheld due to the lack of technical conviction; entering at $171.09 with below-average volume violates the discipline requir |
| CVS | PASS | buy | — | REJECT: The Research Manager and Trader consensus is to WAIT due to the severe valuation disconnect between the 46.9 P/E and 1% FCF margin. Initiating a long po |
| CVX | PASS | buy | — | I align with the Research Manager's directive to WAIT; the RSI at 73 and volume below the 20-day average confirm exhausted momentum at $186.1, making this an in |
| CZR | PASS | hold | ✅ | The Research Manager and Trader correctly identified a violation of the long-term wealth mandate: a 42.4 P/E multiple paired with a -4% FCF margin and -$25,127M |
| DAL | APPROVE | buy | ✅ | The long thesis on Delta is approved with the position size modified to 1.5% to mitigate the -16.42B net debt risk and respect the 30% drawdown cap. While the 0 |
| DASH | APPROVE | buy | ✅ | I approve the 2.5% size, aligning with the Neutral Debator’s prudent calibration to manage the high 86.5x P/E risk while capturing the 34% upside to the $245.2  |
| DE | APPROVE | buy | ✅ | The position is capped at 3% to mitigate valuation risks posed by the -11% revenue contraction and 34.0 P/E ratio. A limit-order entry at $601.27 is preferred o |
| DELL | APPROVE | buy | ✅ | I am approving a conservative 3% entry at $389.10 to align with the 3/5 risk profile and the consolidation phase, avoiding the aggressive 5% sizing proposed by  |
| DHR | PASS | buy | — | The input provided is a JSON object rather than a prose verdict, which conflicts with the instruction to re-express the user message as a single JSON object sha |
| DIS | APPROVE | buy | ✅ | Approved with reduced sizing (4% vs 5%) to preserve portfolio capital against the structural debt risk (-$41.7B net cash) highlighted by the bear and conservati |
| DKNG | PASS | buy | — | DKNG fails the mandate’s long-term wealth horizon requirement given its fragile 1% FCF margin and -$918M net cash position, which introduces unacceptable tail r |
| DOCU | PASS | hold | ✅ | I agree with the Trader's WAIT decision; entering at $53.38 with an RSI of 89 ignores the immediate mean-reversion risk identified by the Bear and Conservative  |
| DUK | PASS | buy | — | The trader correctly identified that the mandatory breakout trigger at $130.38 has not been met, rendering the current $127.25 price a neutral entry with no mom |
| EBAY | PASS | hold | ✅ | Consensus leans WAIT as valuation (25.6x P/E, 1.75 PEG) exceeds the street anchor of $109.09 against the $110.91 reference, creating poor risk-reward for new en |
| EOG | APPROVE | buy | ✅ | The entry trigger is approved at $145.70 to align with technical consensus, while position size is reduced from 10% to 5% to strictly cap drawdown utilization.  |
| EQIX | PASS | buy | — | I concur with the WAIT directive; entering a long position in EQIX at $1020.95 presents an asymmetric risk profile where the potential -37% downside to $643 (fr |
| ETSY | PASS | hold | ✅ | I agree with the Trader’s WAIT stance; entering at $83.48 is premature given the high probability of mean reversion to the $74.12 consensus floor, which would i |
| EXPE | PASS | buy | — | The Trader’s proposal is technically a 'WAIT' with 0% size, which I approve as the correct execution strategy given the lack of volume confirmation above the $2 |
| F | PASS | hold | ✅ | The Research Manager’s directive to WAIT is enforced due to the structural disconnect between the 48.6 P/E multiple and the -3% FCF margin, which renders the 4. |
| FCEL | PASS | hold | ✅ | The Research Manager and Trader correctly identified FCEL as a structural burn trap with a -132% FCF margin and -5% revenue contraction, rendering the PEG 0.36  |
| FDX | APPROVE | buy | ✅ | The position is approved at a reduced size of 5% to mitigate liquidity risks associated with the Bear thesis while capturing potential upside. The entry is set  |
| GILD | APPROVE | buy | ✅ | The analyst approves the long-term thesis, citing the 2.41% yield and 31% FCF margin as sufficient for long-horizon compounding. The position size is increased  |
| GIS | PASS | hold | ✅ | The Research Manager synthesizes a conflict between high yield (6.3%) and structural stagnation (2% growth, 31.1 P/E) that the Trader correctly identifies as a  |
| GOOGL | PASS | buy | — | I agree with the Research Manager and Trader to PASS on entering GOOGL at $344.29; the neutral RSI of 54 and volume below the 20-day average offer no technical  |
| GS | APPROVE | hold | — | The consensus hold rating and flat target imply immediate upside is capped at current levels; therefore, the trade is structured as a breakout play rather than  |
| HON | PASS | buy | — | The proposed trade is a WAIT; I am enforcing this because the current price of $228.09 shows no reclamation of the $252.0 breakout level, and the RSI of 37 conf |
| HOOD | PASS | buy | — | The portfolio accepts the Trader's WAIT recommendation given the lack of technical confirmation at $100.67 and the high valuation risk posed by a 48.9x P/E with |
| HRL | APPROVE | hold | — | The position is approved at a reduced 5% allocation to cap single-name drawdown risk while maintaining exposure to the dividend compounding thesis. Entry is set |
| HUT | PASS | buy | — | The proposed HUT entry violates the 30% max drawdown constraint due to extreme volatility; a drop from $92.09 to the $18.68 support level represents an ~80% dec |
| INTC | APPROVE | hold | — | The Bull's 2% sizing aligns with the long-horizon wealth mandate, strictly limiting single-name drawdown risk despite the unresolved -6% FCF margin and $12.2B n |
| INTU | APPROVE | buy | ✅ | I approve the Trader’s 5% initial position at $291.42, as it aligns with the 3–10 year horizon while respecting the 50% single-name concentration cap and avoidi |
| ITW | PASS | hold | ✅ | I concur with the Trader's WAIT stance; the 26.2x P/E and 2.69 PEG offer no margin of safety against the $-8321M net debt load given the flat 5% revenue growth. |
| JBLU | PASS | hold | ✅ | The portfolio rejects any entry for JBLU because the bear case—structural debt of -$7,165M and -8% FCF margin—presents a binary risk that violates the 30% max d |
| JPM | PASS | buy | — | The Trader's proposal to WAIT is approved because the entry signal (breakout above $351.24) has not been confirmed by volume, and entering at $344.18 near resis |
| KHC | PASS | hold | ✅ | KHC is rejected due to structural valuation failure: a -23% FCF margin and -$17.04B net cash deficit make the 6.1% yield unsustainable, creating a direct violat |
| KO | PASS | buy | — | The proposal to enter via breakout above $85.68 fails to define a valid stop-loss; a trade cannot be approved if the maximum possible loss ($85.68 - $65.35 = 23 |
| KSS | PASS | hold | ✅ | I reject entry into KSS because the structural risks—specifically the $-6.1B net cash burden against a fragile 2% FCF margin—violate the long-term wealth preser |
| LCID | PASS | hold | ✅ | I reject the entry due to the Research Manager's consensus to AVOID, driven by the fatal -240% FCF margin and -$2,468M net cash deficit which pose unacceptable  |
| LEVI | PASS | buy | — | The Trader correctly identified the lack of technical confirmation, as the stock remains below the $25.58 breakout level with sub-average volume and neutral RSI |
| LIN | PASS | buy | — | LIN is a Basic Materials company, not an AI infrastructure provider; the 'Bloom Energy' headlines are hallucinated noise irrelevant to this name. The valuation  |
| LMT | PASS | hold | ✅ | I concur with the Research Manager and Trader to WAIT. Entering at $513.52 for a 0% growth stock at 24.9 P/E violates the long-term wealth mandate's efficiency  |
| LUV | PASS | hold | ✅ | The trader’s WAIT recommendation is aligned with the Research Manager’s consensus to avoid entry without technical validation at $53.13, which protects against  |
| LVS | APPROVE | buy | ✅ | The position is scaled to 4% to align with caution on momentum, as RSI and volume signals suggest incomplete trend confirmation. Entry is approved at $45.51 bas |
| LYFT | PASS | buy | — | Trade deferred: the Trader's limit order requires a confirmed daily close above $16.52 to trigger entry; at the current $15.52 price, the order remains inactive |
| M | PASS | hold | ✅ | The Research Manager and Trader both recommend a WAIT stance due to the structural decline in revenue and the high probability of a value trap, which directly c |
| MA | PASS | buy | — | The team correctly identifies that current momentum is lacking, with RSI at 70 and volume below the 20-day average, creating an invalid entry setup for a long-o |
| MARA | PASS | buy | — | The proposal is a WAIT, which aligns with the Mandate. MARA's structural insolvency, characterized by a -$1,950M net cash position and a -235% FCF margin, creat |
| MCHP | PASS | buy | — | I reject the entry at $81.53 because the trader's proposal is a WAIT, and the research consensus supports waiting for a breakout above $105.38 to avoid the liqu |
| MDLZ | PASS | buy | — | I concur with the Trader's WAIT stance. At $61.22, the 30.3x P/E and 7% FCF margin create a valuation trap with limited upside to the $67.27 target, offering in |
| META | PASS | buy | — | The input message contains a JSON object with an invalid action value 'MODIFY-AND-APPROVE', which does not conform to the required schema of 'APPROVE' or 'PASS' |
| MO | PASS | hold | ✅ | I reject the trade execution. The Trader correctly identified a wait-and-see posture, as the current price of $73.03 sits above the $70.64 consensus target and  |
| MU | PASS | buy | — | The mandate mandates a long-term wealth horizon, but the current technical setup offers no entry trigger; the RSI of 26 confirms a lack of momentum despite the  |
| NEE | PASS | buy | — | The Trader's proposal is currently a 'WAIT' state, requiring a breakout above $96.01 which has not yet occurred, making immediate entry premature. Entering at $ |
| NFLX | PASS | buy | — | The market is structurally broken below the $91.48 breakout level, with price action trapped in a no-trade zone that offers no confirmed trend reversal signal.  |
| NIO | PASS | buy | — | The input provided appears to be a structured JSON object rather than the expected prose-based verdict from the Portfolio Manager. Furthermore, the 'action' fie |
| NKE | APPROVE | buy | ✅ | I approve the long bias but reject the trader’s 5% sizing as excessive for a stagnating -1% revenue story with no volume confirmation. By scaling to 2.5%—the ne |
| NOW | PASS | buy | — | The Research Manager’s ‘wait’ stance is upheld: entering at $103.92 with below-average volume and an RSI of 59 offers no probabilistic edge ahead of the binary  |
| NVDA | PASS | buy | — | Trade rejected by mandate compliance: the Trader’s proposal of a 10% position size at breakout execution violates the hard single-name concentration cap of 50%  |
| OPEN | PASS | hold | ✅ | The Research Manager correctly identifies that OPEN's -38% TTM revenue contraction and -$339M net cash create unacceptable permanent capital impairment risk for |
| OSCR | PASS | hold | ✅ | REJECT: The trader proposed a 5% size, but I am modifying to a PASS decision pending entry discipline. The $28.86 entry is mid-consolidation with neutral RSI 51 |
| PG | PASS | buy | — | The Research Manager correctly identifies that entering at 22.1x P/E with a 4.1x PEG violates the margin-of-safety requirement for a risk-3 portfolio. The techn |
| PGR | APPROVE | hold | — | The position is approved with a reduced size of 5% to strictly manage the portfolio's drawdown cap, rejecting the originally proposed higher sizing due to conce |
| PINS | APPROVE | buy | ✅ | I approve the modified trade from the neutral debator, adjusting size to 3.5% and extending the stop to $20.50 to absorb volatility while capping single-positio |
| PLD | PASS | buy | — | The risk/reward profile is currently unacceptable for a new entry: the 37.4x P/E and $148.66 price leave only ~3% upside to the $153.43 consensus target, while  |
| PLTR | PASS | buy | — | The Research Manager’s PASS directive stands: entering at $133.12 with an RSI 77 and 149.6 P/E violates the risk mandate by exposing the portfolio to immediate  |
| PLUG | PASS | hold | ✅ | The Research Manager’s LEAN SHORT stance is confirmed: PLUG’s -227% FCF margin and $-777M net debt present a structural liquidity trap that violates the core ca |
| PM | PASS | buy | — | The Trader's WAIT recommendation is upheld; with current price at $191.65 and target at $194.86, the 1.6% upside offers no reward for the risk of a breakdown to |
| PYPL | PASS | hold | ✅ | The Research Manager and Trader correctly identified the RSI 85 reading and unverified $53B M&A noise as a speculative trap that offers negative risk-reward rel |
| QCOM | APPROVE | hold | — | The position is approved with a reduced size of 10% to align with the 3/5 risk profile and mitigate the aggressive 15% proposal. The entry is set at 170.61 with |
| QRVO | PASS | hold | ✅ | The portfolio manager rejects the proposed modification due to increased drawdown exposure and binary earnings risk. The decision remains on the previously esta |
| RBLX | PASS | buy | — | The trade fails the execution criteria: a limit order at $58.43 is a conditional entry, not an actionable trade for this session, and the risk/reward is distort |
| RDW | PASS | buy | — | I agree with the Trader's WAIT decision; the technical breakdown from $26.64 and RSI at 32 confirms insufficient buyer participation for a long entry. The 50.3x |
| RIOT | PASS | buy | — | The portfolio is rejected because RIOT’s -133% FCF margin and -$672M net cash violate the 30% max-drawdown safety floor for a long-horizon mandate. The RSI of 9 |
| RIVN | PASS | hold | ✅ | I concur with the WAIT stance: RIVN's -64% FCF margin and -$403M net cash create unacceptable liquidity risk for a long-term wealth mandate, making the current  |
| ROKU | PASS | buy | — | The consensus among the Research Manager and Trader is to WAIT due to the RSI 78 overbought condition and the 107.1x P/E valuation premium, which creates an asy |
| RSI | PASS | buy | — | The Trader's proposal to WAIT is validated by the unanimous consensus on insufficient risk/reward asymmetry at $32.34, particularly given the stock is trading n |
| RTX | APPROVE | buy | ✅ | The position is approved with a reduced size of 3.5% to mitigate leverage sensitivity associated with the significant net cash position. The entry is set at $19 |
| SCHW | PASS | buy | — | The Trader correctly identified the RSI 82 reading and low volume as signals for a mean reversion, advising a WAIT for the $83.96 support level. Approving a buy |
| SEDG | PASS | hold | ✅ | The Research Manager and Trader correctly identify a structural disconnect: 42% revenue growth is negated by a -29% FCF margin, creating a value trap that viola |
| SHOP | PASS | buy | — | The Trader’s WAIT proposal is approved; entering at $123.41 with a 119.8 P/E and 2.57 PEG exposes the portfolio to structural overvaluation without technical co |
| SLB | PASS | buy | — | The verdict is explicitly stated as rejecting the proposed trade due to excessive downside risk associated with the specified stop level, which exceeds the 30%  |
| SMCI | PASS | hold | ✅ | The $12.5x P/E is a value trap given the -$7.85B net cash liability and -$48.6% FCF yield, creating a binary accounting risk that violates the long_horizon mand |
| SNAP | PASS | hold | ✅ | The Trader's WAIT instruction is upheld as the only compliant path; SNAP is currently below the required $6.28 breakout level with negative free cash flow, crea |
| SO | PASS | hold | ✅ | The proposal to buy SO at $98.06 is rejected due to insufficient risk-adjusted reward: the $3.39 upside to the $101.45 target represents only a 3.5% gain, while |
| SOFI | PASS | hold | ✅ | I accept the Research Manager’s directive to wait; the consensus is that immediate entry at $16.51 violates the risk parameters for a long-term wealth mandate g |
| SOUN | APPROVE | buy | ✅ | The position is approved with a reduced 5% size to align with neutral tail-risk mitigation, while the stop is tightened to $6.00 to manage the drawdown cap. Alt |
| SPCE | PASS | hold | ✅ | The portfolio is strictly long-only with a 30% max drawdown cap, making SPCE's projected -50% downside risk and negative free cash flow an unacceptable violatio |
| SPGI | PASS | buy | — | Verdict: PASS (WAIT). Mandate enforcement dictates holding capital given the RSI of 77 and volume divergence, which present a high probability of mean reversion |
| SPOT | APPROVE | buy | ✅ | The portfolio manager approves the entry at $475.68 with a stop at $405.00 and a target of $599.23 over a 365-day horizon. The position size is modified to 5% t |
| STX | PASS | buy | — | The proposal is rejected because the technical setup fails to confirm the trend reversal required by the Research Manager, specifically the lack of a breakout a |
| STZ | APPROVE | buy | ✅ | The 10.4B net debt load necessitates a reduction in allocation to 7% to manage single-name drawdown risk within the 30% cap. The entry at $133.11 is paired with |
| SWKS | APPROVE | hold | — | The trade is approved with a 3.5% position size to maintain portfolio risk within constraints, leveraging high yield as a defensive buffer against Q3 earnings v |
| SYK | APPROVE | buy | ✅ | The position is scaled to 5% to cap single-name drawdown risk at approximately 10%, directly addressing concerns regarding portfolio fragility given the signifi |
| T | APPROVE | buy | ✅ | The position is approved at a reduced size of 5% to strictly enforce single-name concentration limits against the $150.4B net debt overhang, down from the propo |
| TAP | PASS | hold | ✅ | The portfolio manager rejects the current long-term wealth mandate due to a valuation trap indicated by a -19% FCF margin and a 51.4 P/E, which violates capital |
| TDOC | PASS | hold | ✅ | The portfolio is strictly prohibited from opening new positions when the research consensus is 'WAIT', as no immediate catalyst or technical confirmation exists |
| TMO | PASS | buy | — | The safety floor mandates rejection because the proposed stop-loss of $403.36 would incur a ~24.4% single-position loss, consuming 81% of the user's 30% max dra |
| TRIP | PASS | hold | ✅ | The proposal to WAIT is approved because the -4% TTM revenue growth confirms a structurally deteriorating core business that violates the long-term wealth manda |
| TSLA | APPROVE | buy | ✅ | The position is approved at a reduced size of 5% to mitigate risk associated with a high-beta, earnings-binary event and a P/E of 350.3. A tight stop is placed  |
| UAA | PASS | hold | ✅ | The proposal is rejected because it violates the long-only, long-horizon mandate; entering a short position in UAA is strictly prohibited by the hard compliance |
| UBER | PASS | buy | — | I am modifying the trader's proposal to reduce size from 12% to 5% and tightening the stop from $40.89 to the structural support level of $67.19 to prevent cata |
| UNH | PASS | buy | — | REJECT: The proposed 12% size violates the hard mandate cap on single-name concentration, which is strictly limited to 50% but effectively constrained further b |
| V | PASS | buy | — | The Research Manager and Trader correctly identified the low-probability setup due to weak volume and immediate resistance at $365.14. Initiating a position at  |
| VFC | PASS | hold | ✅ | PASS. The portfolio rejects entry into VFC. The Research Manager consensus is WAIT due to the unconfirmed structural debt overhang of -4159M and lack of institu |
| VRTX | APPROVE | buy | ✅ | The trader's proposed 10% size is rejected as it breaches the 30% portfolio drawdown cap given the original $362.50 hard stop. The position is approved at a red |
| VZ | PASS | buy | — | The requested action 'MODIFY-AND-APPROVE' is an invalid enum value for this strict schema, which permits only 'APPROVE' or 'PASS'. Consequently, no valid action |
| WBD | PASS | hold | ✅ | The trade is rejected due to a decisive failure of risk management alignment. The Research Manager and Trader both recommend a WAIT/AVOID stance, citing the $29 |
| WDC | APPROVE | buy | ✅ | I am modifying the size to 2.0% and tightening the stop to $382.27 (-20%) to ensure the user's portfolio remains resilient during the low-volume consolidation,  |
| WFC | PASS | buy | — | The user's mandate explicitly requires a 3–10 year horizon, but the trader's proposal specifies a 12-month horizon. Additionally, the research manager's synthes |
| WMT | APPROVE | buy | ✅ | The PM approves a modified long entry to align with the long-horizon wealth mandate while strictly managing the 30% drawdown cap. The original trader proposal o |
| WU | PASS | sell | — | The trader correctly identified the technical exhaustion at RSI 83 and the volume failure at the $9.00 breakout, making immediate entry inefficient for a long-h |
| WYNN | APPROVE | buy | ✅ | The PM rejects the trader's proposed 12% allocation as overly aggressive given the high net debt and low volume conviction. Instead, a conservative 6% size is a |
| XOM | PASS | buy | — | The Trader’s WAIT is approved; entering at $147.69 with a P/E of 24.9 violates the margin of safety required by our long-horizon mandate, as the Research Manage |
| XPEV | PASS | buy | — | Verdict: PASS. Mandate compliance FAIL: The user's horizon is 3–10 years (long-term wealth), but the Trader’s proposal is for a 3–10 month swing trade; this is  |
| XRX | PASS | hold | ✅ | The trader’s recommendation to hold is approved due to structural insolvency risk; the -$3.861B net cash deficit and -14% FCF margin create an unacceptable thre |

## Respected-site spot-check (Zacks Rank + MarketBeat)

Zacks Rank is Zacks' own earnings-revision model (1=Strong Buy … 5=Strong
Sell), not Street consensus — shown for reference, excluded from scoring.
MarketBeat consensus fetched for a 10-name spot set. TipRanks blocks
automated access (HTTP 403) and could not be included.

| Ticker | Room | Street (pooled) | Zacks Rank | MarketBeat |
|---|---|---|---|---|
| AAPL | APPROVE | buy | 3 Hold | Moderate Buy ($314.26) |
| ABBV | APPROVE | buy | — | — |
| ABNB | PASS | buy | — | — |
| ABT | APPROVE | buy | — | — |
| ADBE | PASS | hold | — | — |
| ADI | PASS | buy | — | — |
| ADP | PASS | hold | 3 Hold | — |
| AES | PASS | hold | — | — |
| AMC | PASS | hold | — | — |
| AMD | PASS | buy | — | — |
| AMZN | APPROVE | buy | 2 Buy | — |
| APD | PASS | buy | — | — |
| AVGO | APPROVE | buy | — | — |
| BA | PASS | buy | 3 Hold | — |
| BAC | PASS | buy | — | — |
| BBAI | PASS | hold | — | — |
| BBWI | PASS | hold | — | — |
| BGS | PASS | sell | 3 Hold | Reduce ($4.88) |
| BKNG | PASS | buy | — | — |
| BLK | APPROVE | buy | — | — |
| CAG | PASS | hold | — | — |
| CAR | PASS | hold | — | — |
| CAT | PASS | buy | — | — |
| CHWY | PASS | buy | — | — |
| CI | PASS | buy | — | — |
| CL | PASS | buy | — | — |
| CLSK | PASS | buy | — | — |
| CMCSA | APPROVE | hold | — | — |
| COIN | PASS | buy | — | — |
| COST | PASS | buy | — | — |
| CPB | PASS | hold | 4 Sell | — |
| CRM | PASS | buy | — | — |
| CVS | PASS | buy | — | — |
| CVX | PASS | buy | — | — |
| CZR | PASS | hold | — | — |
| DAL | APPROVE | buy | 3 Hold | — |
| DASH | APPROVE | buy | — | — |
| DE | APPROVE | buy | — | — |
| DELL | APPROVE | buy | — | — |
| DHR | PASS | buy | — | — |
| DIS | APPROVE | buy | — | — |
| DKNG | PASS | buy | — | — |
| DOCU | PASS | hold | — | — |
| DUK | PASS | buy | — | — |
| EBAY | PASS | hold | — | — |
| EOG | APPROVE | buy | — | — |
| EQIX | PASS | buy | — | — |
| ETSY | PASS | hold | 3 Hold | — |
| EXPE | PASS | buy | — | — |
| F | PASS | hold | 2 Buy | Hold ($14.72) |
| FCEL | PASS | hold | — | — |
| FDX | APPROVE | buy | — | — |
| GILD | APPROVE | buy | — | — |
| GIS | PASS | hold | 5 Strong Sell | — |
| GOOGL | PASS | buy | — | — |
| GS | APPROVE | hold | — | — |
| HON | PASS | buy | — | — |
| HOOD | PASS | buy | — | — |
| HRL | APPROVE | hold | — | — |
| HUT | PASS | buy | — | — |
| INTC | APPROVE | hold | 1 Strong Buy | Hold ($101.96) |
| INTU | APPROVE | buy | — | — |
| ITW | PASS | hold | — | — |
| JBLU | PASS | hold | 2 Buy | Reduce ($5.31) |
| JPM | PASS | buy | — | — |
| KHC | PASS | hold | 3 Hold | — |
| KO | PASS | buy | — | — |
| KSS | PASS | hold | 3 Hold | Reduce ($15.31) |
| LCID | PASS | hold | 4 Sell | Reduce ($9.56) |
| LEVI | PASS | buy | — | — |
| LIN | PASS | buy | — | — |
| LMT | PASS | hold | — | — |
| LUV | PASS | hold | — | — |
| LVS | APPROVE | buy | — | — |
| LYFT | PASS | buy | — | — |
| M | PASS | hold | — | — |
| MA | PASS | buy | — | — |
| MARA | PASS | buy | — | — |
| MCHP | PASS | buy | — | — |
| MDLZ | PASS | buy | — | — |
| META | PASS | buy | 3 Hold | — |
| MO | PASS | hold | — | — |
| MU | PASS | buy | — | — |
| NEE | PASS | buy | — | — |
| NFLX | PASS | buy | 4 Sell | — |
| NIO | PASS | buy | — | — |
| NKE | APPROVE | buy | — | — |
| NOW | PASS | buy | — | — |
| NVDA | PASS | buy | 2 Buy | Moderate Buy ($304.26) |
| OPEN | PASS | hold | — | — |
| OSCR | PASS | hold | — | — |
| PG | PASS | buy | — | — |
| PGR | APPROVE | hold | — | — |
| PINS | APPROVE | buy | — | — |
| PLD | PASS | buy | — | — |
| PLTR | PASS | buy | — | — |
| PLUG | PASS | hold | — | — |
| PM | PASS | buy | — | — |
| PYPL | PASS | hold | — | — |
| QCOM | APPROVE | hold | — | — |
| QRVO | PASS | hold | — | — |
| RBLX | PASS | buy | — | — |
| RDW | PASS | buy | 3 Hold | — |
| RIOT | PASS | buy | — | — |
| RIVN | PASS | hold | 3 Hold | — |
| ROKU | PASS | buy | — | — |
| RSI | PASS | buy | — | — |
| RTX | APPROVE | buy | — | — |
| SCHW | PASS | buy | — | — |
| SEDG | PASS | hold | — | — |
| SHOP | PASS | buy | — | — |
| SLB | PASS | buy | 3 Hold | — |
| SMCI | PASS | hold | 4 Sell | Hold ($38.71) |
| SNAP | PASS | hold | — | — |
| SO | PASS | hold | 2 Buy | — |
| SOFI | PASS | hold | — | — |
| SOUN | APPROVE | buy | — | — |
| SPCE | PASS | hold | — | — |
| SPGI | PASS | buy | — | — |
| SPOT | APPROVE | buy | — | — |
| STX | PASS | buy | — | — |
| STZ | APPROVE | buy | — | — |
| SWKS | APPROVE | hold | — | — |
| SYK | APPROVE | buy | — | — |
| T | APPROVE | buy | — | — |
| TAP | PASS | hold | — | — |
| TDOC | PASS | hold | — | — |
| TMO | PASS | buy | — | — |
| TRIP | PASS | hold | 3 Hold | — |
| TSLA | APPROVE | buy | — | — |
| UAA | PASS | hold | — | — |
| UBER | PASS | buy | — | — |
| UNH | PASS | buy | 3 Hold | — |
| V | PASS | buy | 2 Buy | — |
| VFC | PASS | hold | — | — |
| VRTX | APPROVE | buy | — | — |
| VZ | PASS | buy | — | — |
| WBD | PASS | hold | — | — |
| WDC | APPROVE | buy | — | — |
| WFC | PASS | buy | — | — |
| WMT | APPROVE | buy | 3 Hold | — |
| WU | PASS | sell | 4 Sell | Reduce ($8.55) |
| WYNN | APPROVE | buy | — | — |
| XOM | PASS | buy | — | — |
| XPEV | PASS | buy | — | — |
| XRX | PASS | hold | — | — |
