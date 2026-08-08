# External review — fundamentals_analyst

> Reviewer: `kimi-for-coding` · reasoning tokens 12427 · prompt 2972 tokens.
> **Hypotheses, not findings.** The reviewer cannot see our code; every claim needs a supplier check and a parser check before it becomes a defect.

# Audit: Fundamentals Analyst System Prompt

## 1. JOB
This agent is supposed to produce a one-line structured stance header, a one-sentence thesis, and 3–5 short bullet points of evidence about AAPL’s underlying business using only the explicit numbers in the provided data block, while refraining from buy/sell recommendations, price predictions, technical commentary, or news analysis.

## 2. CONTRADICTIONS

1. **Output length vs. output structure**
   - "Format: lead with a one-sentence thesis, then short bullet points for supporting evidence."
   - "Your turn. Speak as the Fundamentals Analyst. Write 2–4 sentences."
   A stance line + one-sentence thesis + bullets cannot be “2–4 sentences.”

2. **Tone/format**
   - "Tone preference: terse, tabular, declarative — minimise prose"
   - "Plain text otherwise — no headings, no tables, no code fences"
   The mandate asks for tabular output; the format instruction forbids tables.

3. **Field name vs. supplied value**
   - "TTM revenue growth, profit margin, net cash, 52-week range — real"
   - "Net debt $21945M"
   The input list calls the field “net cash”; the fact sheet delivers “Net debt.”

4. **What to prioritise vs. what is available**
   - "Prioritise durable margins, FCF consistency, balance sheet strength, capital allocation."
   - "Not available at all: full financial statements (income statement, balance sheet, cash flow statement)." and "Buybacks and M&A history are not available — never claim a number for either"
   The role asks for balance-sheet and capital-allocation analysis, then states the data needed for it does not exist.

5. **Scope firewall vs. data block contents**
   - "You DO NOT ... Comment on news flow. That's the News Analyst."
   - "Catalysts — recent: 'Dan Ives Says We're in the '3rd Inning' of the AI Revolution...' (Motley Fool, 1h ago); other recent coverage: 'OpenAI developing $300+ AI speaker to challenge Amazon Alexa' (Yahoo Finance Video, 13h ago); 'What we know about OpenAI's upcoming handheld device: Bloomberg' (Yahoo Finance Video, 20h ago); forward (REAL, Fed's published calendar): FOMC decision in 39 days"
   The role bars news/macroeconomic commentary, but the data block includes both.

6. **Technical analysis firewall vs. data block contents**
   - "You DO NOT ... Predict short-term price movements. That's the Market Analyst."
   - "RSI: 41 (neither overbought nor oversold), trend: consolidating" and "50-day range: $273.75–$344.57, last close $313.33 (56% of that range) Volume: in-line with 20-day average"
   The role bars technical/price analysis, but the data block is filled with RSI, trend, volume, and short-term ranges.

7. **Social sentiment firewall vs. data block contents**
   - "You DO NOT ... Discuss social sentiment. That's the Social Media Analyst."
   - "Retail sentiment: moderately bullish (typical intensity (illustrative))"
   The role bars social sentiment, but the data block includes it.

8. **Liquid-only rule vs. grounding directive**
   - "Liquid only. Avoid microcaps (< $500M market cap)."
   - "Use only the facts and numbers explicitly provided in this prompt. Do not assume, infer, invent, or recall any datum you were not given — such as holdings, positions, prices, balances, ratios, dates, or prior events."
   The liquid-only rule requires market cap, but market cap is not in the data block and the grounding directive forbids recalling it.

9. **Stated cap vs. portfolio data**
   - "Single-name position-size cap: 3.0% of portfolio in any one name"
   - "NVDA ×20 (5.5% of portfolio, unrealised +310.00)"
   The mandate declares a 3.0% single-name ceiling, but the simulated portfolio already holds NVDA at 5.5%.

## 3. UNFOLLOWABLE

1. "Write 2–4 sentences."
   Cannot be satisfied simultaneously with the stance-line + thesis + bullet format.

2. "Prioritise durable margins, FCF consistency, balance sheet strength, capital allocation."
   Cannot be followed because the prompt explicitly withholds full financial statements, buybacks, and M&A history.

3. "Use specific numbers; never vague language ('strong margins' → '32.4% gross margins, up 180bps YoY')"
   The data block does not contain gross margin, a 180bps YoY change, or margin type labels; the only margin figure is "profit margin: 28%." The example instructs the model to produce numbers that are not in the prompt.

4. "Liquid only. Avoid microcaps (< $500M market cap)."
   Unfollowable from the provided data because no market-cap figure is supplied and the grounding directive prohibits recalling external knowledge.

5. "Tone preference: terse, tabular, declarative — minimise prose" combined with "Plain text otherwise — no headings, no tables, no code fences."
   The model cannot render tabular output while also being forbidden from using tables.

## 4. FAILURE MODES

1. **Format collapse.** A model that weights the final instruction “Write 2–4 sentences” heavily will drop the required stance line and bullets, producing something like:
   > AAPL trades at a premium valuation with a 36.0 trailing P/E and 2.4% FCF yield. Revenue is growing 16% and margins are 28%, but net debt is $21,945M. The consensus is bullish with a $322.82 target.
   This misses the `[STANCE: ...]` header and the bullet-point evidence the rest of the prompt demands.

2. **Scope bleed into technicals and news.** Because the data block leads with price, RSI, trend, volume, ranges, catalysts, and retail sentiment, the model is likely to leak them into the “fundamental” output, e.g.:
   > The RSI of 41 and consolidating trend suggest limited downside, while the OpenAI speaker news may pressure AAPL’s consumer electronics business ahead of the FOMC decision in 39 days.
   This violates the explicit role firewalls for the Market Analyst and News Analyst.

3. **Fundamental hallucination.** To satisfy “balance sheet strength” and “capital allocation” without the underlying statements, the model may invent line items, e.g.:
   > Gross margins expanded 180bps YoY to 32.4%, the balance sheet carries net cash of $90bn, and AAPL returns most of its FCF via buybacks.
   None of those numbers appear in the data block; the prompt explicitly says buybacks are “not available, not claimed.”

## 5. CUT

**Delete as noise:**

- The entire technical and catalyst block:  
  "RSI: 41 (neither overbought nor oversold), trend: consolidating", "50-day range: $273.75–$344.57, last close $313.33 (56% of that range) Volume: in-line with 20-day average", "52-week range: $223.78–$344.57", "Catalysts — recent: 'Dan Ives Says We're in the '3rd Inning' of the AI Revolution...'", and "forward (REAL, Fed's published calendar): FOMC decision in 39 days".  
  These are for the Market Analyst and News Analyst, not the Fundamentals Analyst.

- "Retail sentiment: moderately bullish (typical intensity (illustrative))".  
  This is for the Social Media Analyst.

- The entire portfolio section:  
  "─── YOUR SIMULATED PORTFOLIO (AMI's portfolio of record — simulation-only) ─── Cash: $42,150.00 | Portfolio value: $61,634.00 Open positions: MSFT ×40 (26.1% of portfolio, unrealised +796.00) NVDA ×20 (5.5% of portfolio, unrealised +310.00) You hold 0% of AAPL — no open position in it. Any BUY here opens a NEW position."  
  Position sizing, cash, and open positions are the Portfolio Manager’s domain; giving them to the Fundamentals Analyst invites scope creep.

- The trading and risk-management paragraphs that are irrelevant to a fundamentals-only report:  
  "Max acceptable drawdown: 30% — a PORTFOLIO-level cap on total drawdown...", "Single-name position-size cap: 3.0%...", "Sector-concentration cap: 40.0%...", "Post-loss cooldown: 1.0h...", "Max open positions: 35...", "Trading pace cap: 4 per day, 12 per week...", "Total open-risk cap: 10.5%...".  
  Keep only the compliance constraints that shape how the view is framed: "LONG-ONLY" and "Liquid only."

- The misleading vague-language example:  
  "('strong margins' → '32.4% gross margins, up 180bps YoY')".  
  It uses figures not present in the data block and implicitly pushes the model toward inventing margin type and YoY change.

- The contradictory closing instruction:  
  "Your turn. Speak as the Fundamentals Analyst. Write 2–4 sentences."  
  Replace with a single sentence that restates the required format: stance line + one-sentence thesis + short bullets.

**Load-bearing and must stay:**

- The grounding directive: "Use only the facts and numbers explicitly provided in this prompt. Do not assume, infer, invent, or recall any datum you were not given..."
- The role definition and the "You DO NOT" list that keep the agent in its lane.
- The input list — but corrected so the field name matches the data (e.g., "net debt" instead of "net cash").
- The actual fundamental/valuation data: P/E (both bases with labels), P/S, EV/EBITDA, PEG, FCF yield, TTM revenue growth, profit margin, net debt, dividend yield, analyst consensus, next earnings date and consensus EPS.
- The output-style rules: one-sentence thesis, 3–5 bullets, specific numbers, bolded metrics.
- The `[STANCE: ... | CONVICTION: ... | HEADLINE: ...]` format and the instruction to write it once at the top.
- The LONG-ONLY and Liquid-only constraints, provided market cap is added to the data block or the liquid-only constraint is removed.