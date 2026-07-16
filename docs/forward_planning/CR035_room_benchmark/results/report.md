# CR035 Room-vs-Street benchmark report

Generated 2026-07-16 11:13 UTC · baseline batch `baseline-2026-07-16`

## Headline

- Scored runs: **25** (rejects: 0, unscored: 0, PM parse-fallbacks excluded per DEF058: 7 — CPB, DAL, META, NVDA, PEP, SLB, UNH)
- Agreement vs pooled Street consensus (all scored): **13/25 (52%)**
- Agreement on Buy/Hold-consensus names (Room's expressible space): **13/23 (57%)**, Cohen's κ = **-0.08**
- Red-line violations (Room Buy on Street-Sell name): **0/2**

## Confusion matrix (baseline)

| Room \ Street | Buy | Hold | Sell |
|---|---|---|---|
| **Buy** | 0 | 1 | 0 |
| **Hold** | 9 | 13 | 2 |

The Room is buy-side only (no Sell verdict exists), so the Sell column can
never be 'matched' — on Street-Sell names the pass criterion is Hold, not Buy.

## Per-source agreement (Buy/Hold-consensus names)

- yahoo: 13/21 (62%)
- stockanalysis: 13/23 (57%)

## Target sanity (Room target vs Yahoo mean analyst target, Buy verdicts)

Average diff: **+7.6%** over 1 names. Per ticker:

- RIVN: +7.6%

## Per-ticker detail (baseline)

| Ticker | Room | Street | Match | Reason (truncated) |
|---|---|---|---|---|
| AAPL | PASS | buy | — | The Research Manager and Trader correctly identify a structural lack of edge: price is trapped below the $328.73 breakout level with overbought RSI 70 and minim |
| ADP | PASS | hold | ✅ | The Trade Desk's WAIT is correct: RSI 73 and a 2.30 PEG on 7% growth signal a high probability of immediate multiple compression toward 15.8x EV/EBITDA, which t |
| AMZN | PASS | buy | — | The RSI of 72 indicates an overbought condition with volume below the 20-day average, creating a suboptimal entry point against a 36.0 P/E multiple that require |
| BA | PASS | buy | — | The Trader's WAIT directive is upheld. While the 14% TTM revenue growth supports the long-term thesis, the structural disconnection between current valuation (P |
| BGS | PASS | sell | — | The proposal to WAIT is approved; the existential risk from the -$1994M net debt burden and negative FCF margin violates the long-term wealth mandate's need for |
| ETSY | PASS | hold | ✅ | The Research Manager explicitly recommends WAIT due to the negative risk/reward asymmetry at $85.74 versus the $74.12 consensus target. The Trader’s proposal to |
| F | PASS | hold | ✅ | The RSI of 100 confirms extreme overbought conditions that invalidate immediate entry, making the trader's wait for a pullback to $380.12 the only prudent execu |
| GIS | PASS | hold | ✅ | The Research Manager's synthesis and the Trader's 'WAIT' stance are upheld; the 40.4x P/E on 2% growth presents an unacceptable valuation risk that violates the |
| HOG | PASS | hold | ✅ | The proposed side is WAIT, triggering an automatic PASS under the mandate's long-only and execution constraints. Entering a position in a value trap with -12% r |
| INTC | PASS | hold | ✅ | The Research Manager’s WAIT directive stands. A 54.5x P/E with a -6% FCF margin presents a valuation trap incompatible with long-term wealth mandates, and the u |
| JBLU | PASS | hold | ✅ | The proposal to initiate a long position in JBLU is rejected as it directly conflicts with the long-term wealth mandate and the Research Manager's synthesis. Th |
| KHC | PASS | hold | ✅ | The Trader correctly calls for a WAIT given the structural disconnect between the 41.0x P/E and 1% revenue growth, reinforced by the 6.38% yield being funded by |
| KSS | PASS | hold | ✅ | The Research Manager's 'AVOID' stance is validated by the high probability of equity erosion given the structural revenue decline (-2%) and critical net debt (- |
| LCID | PASS | hold | ✅ | PASS is mandated: the -240% FCF margin and -$2468M net debt create permanent impairment risk that directly violates the 30% max drawdown cap for a risk score 3  |
| LLY | PASS | buy | — | The proposal to WAIT is validated by the consensus across all layers: fundamental valuation (41.0 P/E) is stretched for the 30% drawdown tolerance, technicals s |
| LWAY | PASS | buy | — | The Research Manager and Trader correctly identify a lack of asymmetric risk-reward, citing only 9% upside to the $34.5 target against a 32.7x P/E and negative  |
| NFLX | PASS | buy | — | We are PASS because the Trader's proposal is a BUY, but the Research Manager explicitly recommends a 'Lean long with disciplined entry below $75.00' only if spe |
| RDW | PASS | buy | — | I concur with the Trader's decision to WAIT. Although the 58% revenue growth is compelling for a long-horizon mandate, the -81% FCF margin and lack of volume su |
| RIVN | APPROVE | hold | — | I approve the 3% size to balance the Bull's runway argument with the Bear's structural FCF risk, while tightening the stop to $15.5 as recommended by the Neutra |
| SMCI | PASS | hold | ✅ | The trade is rejected due to the negative Free Cash Flow yield of -42.8% and $-7846M net cash, which violates the long-horizon wealth mandate's requirement for  |
| SO | PASS | hold | ✅ | The trade is rejected due to a lack of conviction signal; the Trader’s proposal is to hold (0% new capital) and the Research Manager leans on weakness accumulat |
| TRIP | PASS | hold | ✅ | The debate is split between value dislocation (PEG 0.32) and value trap (revenue growth -4%), creating a structural uncertainty that violates the long-term weal |
| V | PASS | buy | — | The Trader’s WAIT directive is approved as the optimal path to preserve capital ahead of the $365.02 resistance and uncertain volume expansion. The 30% max draw |
| WMT | PASS | buy | — | The trade fails the mandate’s margin of safety test: a 40.0 P/E and 4.33 PEG relative to 7% growth offers insufficient protection for a long-horizon wealth port |
| WU | PASS | sell | — | The trader's proposal to WAIT is the correct execution of the Research Manager's guidance, as the 79 RSI reading at $8.04 presents a stretched technical entry w |

## Respected-site spot-check (Zacks Rank + MarketBeat)

Zacks Rank is Zacks' own earnings-revision model (1=Strong Buy … 5=Strong
Sell), not Street consensus — shown for reference, excluded from scoring.
MarketBeat consensus fetched for a 10-name spot set. TipRanks blocks
automated access (HTTP 403) and could not be included.

| Ticker | Room | Street (pooled) | Zacks Rank | MarketBeat |
|---|---|---|---|---|
| AAPL | PASS | buy | 3 Hold | Moderate Buy ($314.26) |
| ADP | PASS | hold | 3 Hold | — |
| AMZN | PASS | buy | 2 Buy | — |
| BA | PASS | buy | 3 Hold | — |
| BGS | PASS | sell | 3 Hold | Reduce ($4.88) |
| ETSY | PASS | hold | 3 Hold | — |
| F | PASS | hold | 2 Buy | Hold ($14.72) |
| GIS | PASS | hold | 5 Strong Sell | — |
| HOG | PASS | hold | 3 Hold | — |
| INTC | PASS | hold | 1 Strong Buy | Hold ($101.96) |
| JBLU | PASS | hold | 2 Buy | Reduce ($5.31) |
| KHC | PASS | hold | 3 Hold | — |
| KSS | PASS | hold | 3 Hold | Reduce ($15.31) |
| LCID | PASS | hold | 4 Sell | Reduce ($9.56) |
| LLY | PASS | buy | 3 Hold | — |
| LWAY | PASS | buy | — | — |
| NFLX | PASS | buy | 4 Sell | — |
| RDW | PASS | buy | 3 Hold | — |
| RIVN | APPROVE | hold | 3 Hold | — |
| SMCI | PASS | hold | 4 Sell | Hold ($38.71) |
| SO | PASS | hold | 2 Buy | — |
| TRIP | PASS | hold | 3 Hold | — |
| V | PASS | buy | 2 Buy | — |
| WMT | PASS | buy | 3 Hold | — |
| WU | PASS | sell | 4 Sell | Reduce ($8.55) |
