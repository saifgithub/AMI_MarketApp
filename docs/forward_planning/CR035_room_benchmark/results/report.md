# CR035 Room-vs-Street benchmark report

Generated 2026-07-16 16:52 UTC · baseline batch `baseline2-2026-07-16` · ablation batch `ablation2-2026-07-16`

## Headline

- Scored runs: **32** (rejects: 0, unscored: 0, PM parse-fallbacks excluded per DEF058: 0)
- Agreement vs pooled Street consensus (all scored): **17/32 (53%)**
- Agreement on Buy/Hold-consensus names (Room's expressible space): **17/30 (57%)**, Cohen's κ = **0.08**
- Red-line violations (Room Buy on Street-Sell name): **0/2**

## Confusion matrix (baseline)

| Room \ Street | Buy | Hold | Sell |
|---|---|---|---|
| **Buy** | 2 | 1 | 0 |
| **Hold** | 12 | 15 | 2 |

The Room is buy-side only (no Sell verdict exists), so the Sell column can
never be 'matched' — on Street-Sell names the pass criterion is Hold, not Buy.

## Per-source agreement (Buy/Hold-consensus names)

- yahoo: 17/28 (61%)
- stockanalysis: 17/30 (57%)

## Target sanity (Room target vs Yahoo mean analyst target, Buy verdicts)

Average diff: **+4.3%** over 3 names. Per ticker:

- BA: +0.0%
- NFLX: -16.8%
- TRIP: +29.7%

## Per-ticker detail (baseline)

| Ticker | Room | Street | Match | Reason (truncated) |
|---|---|---|---|---|
| AAPL | PASS | buy | — | The Research Manager and Trader correctly identify a high-risk setup: a 39.7x P/E multiple at 70 RSI, following a failed breakout at $328.73 on below-average vo |
| ADP | PASS | hold | ✅ | The Trade Desk's proposal to WAIT is approved; current technicals (RSI 73, price $247.47) and valuation metrics (PEG 2.30) create an asymmetric risk profile aga |
| AMZN | PASS | buy | — | REJECT — Mandate Violation: The trader's proposed side is explicitly 'WAIT', which constitutes a non-executable instruction (0% size). A gatekeeper verdict requ |
| BA | APPROVE | buy | ✅ | Position approved as a lean long entry, scaled down to 3% from the proposed 5% to enforce single-name concentration limits and preserve drawdown capacity agains |
| BGS | PASS | sell | — | The proposed WAIT is correct as BGS presents a clear value trap with a structurally unsustainable 10.11% yield funded by a -4% FCF margin and -$1994M net cash,  |
| CPB | PASS | hold | ✅ | I reject immediate entry because the consensus Hold rating and $21.47 target indicate the market has not yet priced a breakout, leaving the stock vulnerable to  |
| DAL | PASS | buy | — | The verdict modifies the proposed entry size from 12% to 8% to align with prudent risk limits, but the action key defaults to PASS as the input format did not s |
| ETSY | PASS | hold | ✅ | The proposal to WAIT is correct; the risk-reward asymmetry is unacceptable for a risk_score of 3. A trade at $85.74 exposes the portfolio to a ~13.5% drop to th |
| F | PASS | hold | ✅ | The Research Manager correctly identifies that Ford’s negative free cash flow and $137.73B net debt create a solvency risk that violates the long-term wealth pr |
| GIS | PASS | hold | ✅ | The Research Manager and Trader correctly identify RSI 100 at $385.70 as a technical overextension incompatible with a precise entry for a 3–10 year horizon. Wh |
| HOG | PASS | hold | ✅ | The consensus to WAIT is validated by the structural conflict between the -12% revenue contraction and the -$1116M net cash burden, which renders the 6.2% FCF y |
| INTC | PASS | hold | ✅ | The proposal to WAIT is compliant and prudent; however, as Portfolio Manager, I explicitly reject the Bull's mean-reversion hypothesis due to the -6% FCF margin |
| JBLU | PASS | hold | ✅ | The mandate requires long-term wealth preservation, but JBLU's -52.8% FCF yield and -7165M net cash position present an unacceptable solvency risk that violates |
| KHC | PASS | hold | ✅ | The trade is rejected due to timing and valuation mismatch; entry at $25.45 offers no margin of safety given the $23.91 consensus target and stagnant 1% revenue |
| KSS | PASS | hold | ✅ | The trade is rejected due to a violation of the 30% max drawdown constraint. The bear case identifies a path to $9.42, implying a 45% loss that exceeds the user |
| LCID | PASS | hold | ✅ | I concur with the Trader's WAIT decision; entering at $5.95 exposes the portfolio to dilution risk from the -$2,468M net cash deficit that could easily breach t |
| LLY | PASS | buy | — | The proposal violates the long-only horizon constraint by setting a 30% stop-loss at $810, which implies accepting a drawdown incompatible with a 3-10 year weal |
| LWAY | PASS | buy | — | The Research Manager's synthesis correctly identifies a structural misalignment: a 32.7x P/E and -4.7% FCF yield for a long-horizon wealth mandate is unsustaina |
| META | PASS | buy | — | Verdict is to WAIT because the RSI of 73 signals an overbought condition and the Trader’s proposal requires a limit entry at $686.08, indicating the trade is no |
| NFLX | APPROVE | buy | ✅ | The position is approved as a long-only trade sized at 2.0% to balance the Bull's 29% FCF margin against the Bear's 25% drawdown risk. The entry is set at 73.68 |
| NVDA | PASS | buy | — | The portfolio remains in PASS (WAIT) mode as the Trader correctly identifies the absence of technical confirmation; entering at $212.50 ignores the untested $23 |
| PEP | PASS | hold | ✅ | The Research Manager and Trader correctly recommend a WAIT; the $155.71 breakout is unverified and the RSI of 40 indicates neutral momentum, not a confirmed upt |
| RDW | PASS | buy | — | The trade is rejected because the -81% FCF margin and 50.3x P/E create a speculative risk profile incompatible with the long-horizon wealth mandate. While the 5 |
| RIVN | PASS | hold | ✅ | The Trader's decision to hold cash is validated by the neutral RSI (63) and price consolidating below the critical $20.20 resistance, making entry premature. Wh |
| SLB | PASS | buy | — | The Research Manager’s WAIT directive is correct: entering at $47.55 with a P/E of 20.9x against 3% revenue growth creates asymmetric risk where a drop to the $ |
| SMCI | PASS | hold | ✅ | REJECT: The Trader's proposal is to WAIT, and I agree. The combination of -$7846M net cash and a -42.8% FCF yield creates a solvency risk that exceeds the 30% m |
| SO | PASS | hold | ✅ | I reject the proposed entry at $94.60 because the risk/reward asymmetry fails the mandate's 30% drawdown cap; a drop to the $83.80 support level represents an ~ |
| TRIP | APPROVE | hold | — | The portfolio manager modifies the trader's proposal to reduce size from 5% to 2.5% and raise the entry trigger to $14.81. This addresses concerns regarding hig |
| UNH | PASS | buy | — | The Risk Debators correctly identify that a break below $234.6 support results in a ~44% loss, which exceeds the 30% max drawdown cap, making the current breako |
| V | PASS | buy | — | No trade is being proposed. The Trader's proposal explicitly conditions entry on a future breakout above $365.02, which constitutes a conditional wait-state rat |
| WMT | PASS | buy | — | The proposal is rejected due to lack of conviction; the trader's WAIT signal aligns with the Research Manager's 'lean long' but 'limited margin of safety' asses |
| WU | PASS | sell | — | I am passing on this entry due to the severe overextension risk; an RSI of 79 at $8.04 signals immediate exhaustion, making the risk of mean reversion unaccepta |

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
| BA | APPROVE | buy | 3 Hold | — |
| BGS | PASS | sell | 3 Hold | Reduce ($4.88) |
| CPB | PASS | hold | 4 Sell | — |
| DAL | PASS | buy | 3 Hold | — |
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
| META | PASS | buy | 3 Hold | — |
| NFLX | APPROVE | buy | 4 Sell | — |
| NVDA | PASS | buy | 2 Buy | Moderate Buy ($304.26) |
| PEP | PASS | hold | 4 Sell | — |
| RDW | PASS | buy | 3 Hold | — |
| RIVN | PASS | hold | 3 Hold | — |
| SLB | PASS | buy | 3 Hold | — |
| SMCI | PASS | hold | 4 Sell | Hold ($38.71) |
| SO | PASS | hold | 2 Buy | — |
| TRIP | APPROVE | hold | 3 Hold | — |
| UNH | PASS | buy | 3 Hold | — |
| V | PASS | buy | 2 Buy | — |
| WMT | PASS | buy | 3 Hold | — |
| WU | PASS | sell | 4 Sell | Reduce ($8.55) |

## Ablation (analyst-consensus line suppressed)

- Ablation agreement vs Street: **17/32 (53%)** (baseline: 17/32 (53%))
- Verdict flips baseline → ablation: **4**

- BA: APPROVE → PASS
- ETSY: PASS → APPROVE
- SLB: PASS → APPROVE
- TRIP: APPROVE → PASS

A large agreement drop or heavy flipping means baseline agreement was
substantially the Room parroting the consensus it is fed; small deltas mean
the debate reaches the Street view from its own inputs.
