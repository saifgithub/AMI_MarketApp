# External review — market_analyst

> Reviewer: `kimi-for-coding` · reasoning tokens 8796 · prompt 2784 tokens.
> **Hypotheses, not findings.** The reviewer cannot see our code; every claim needs a supplier check and a parser check before it becomes a defect.

1. **JOB**
This agent is supposed to produce a concise, technical-analysis-only verdict on AAPL’s chart setup — including a stance line, a one-sentence thesis, bullet-point evidence, and (when justified) entry/target/stop levels and R:R — using only the provided price-derived indicators.

---

2. **CONTRADICTIONS**

**a. The grounding directive forbids inference; the output style requires inferred levels and ratios.**
- "Use only the facts and numbers explicitly provided in this prompt. Do not assume, infer, invent, or recall any datum you were not given — such as holdings, positions, prices, balances, ratios, dates, or prior events."
- "Provide specific levels: entry, target, stop-loss" and "Risk-reward ratio (e.g., '3:1 R:R')"

**b. The user wants a tabular tone, but the format forbids tables.**
- "Tone preference: terse, tabular, declarative — minimise prose"
- "Plain text otherwise — no headings, no tables, no code fences."

**c. The agent is told to read charts, but no chart is supplied — only derived numbers.**
- "You read charts and technical signals."
- "Use only the facts and numbers explicitly provided in this prompt" and the data block contains only pre-computed indicators (RSI, 50-day range, volume) rather than OHLCV or a chart.

**d. The length cap conflicts with the required structure.**
- "Write 2–4 sentences."
- "Format: lead with a one-sentence thesis, then short bullet points for supporting evidence." and "Use **bold** for key metrics (numbers, levels, deadlines)."

---

3. **UNFOLLOWABLE**

- "You read charts and technical signals." — There is no chart in the prompt; only a handful of derived numeric readings are provided.
- "Daily price history (yfinance OHLCV), when live market data is enabled" — The data block does not contain OHLCV history; it only supplies computed values.
- "Provide specific levels: entry, target, stop-loss" — The agent cannot derive these from a 50-day range and a single close without inferring a chart structure that is not provided.
- "Risk-reward ratio (e.g., '3:1 R:R')" — This depends on entry/target/stop values that are not in the data block.
- "Use chart vocabulary precisely (e.g., 'breakout from a 3-month base', 'RSI clearing 70 off an oversold base')" — No 3-month base data is supplied; the data states RSI is 41 and the trend is "consolidating," so the examples describe conditions not present in the sheet.
- "RSI(14), a 20/50-day moving-average trend read, and volume vs. a 20-day average" — The data block only says "trend: consolidating" without providing the 20/50-day moving-average values, so the agent cannot verify or independently use that read.

---

4. **FAILURE MODES**

**a. Hallucinated levels and R:R.** Because the output style demands "entry, target, stop-loss" and a "Risk-reward ratio," the model will fabricate concrete prices and a ratio, e.g., *"Enter at **$314.00**, target **$330.00**, stop **$300.00**, ~2.3:1 R:R"* — none of which can be derived from the data block and all of which violate the grounding directive.

**b. Domain bleed into fundamentals and news.** The data block overloads the agent with non-technical facts, so the model will produce output like *"AAPL trades at **36.0x trailing P/E** and **32.9x forward P/E**, net debt is **$21,945M**, and the OpenAI speaker news plus the **FOMC decision in 39 days** create headline risk"* — all of which belong to the Fundamentals Analyst or News Analyst, not the Market Analyst.

**c. Format and length violations.** The model will omit the required `[STANCE: ...]` line, add headings or tables, or produce a six-sentence paragraph despite the "Write 2–4 sentences" cap.

---

5. **CUT**

**Cut as noise:**
- The entire simulated portfolio block:  
  `"Cash: $42,150.00 | Portfolio value: $61,634.00 Open positions: MSFT ×40 (26.1% of portfolio, unrealised +796.00) NVDA ×20 (5.5% of portfolio, unrealised +310.00) You hold 0% of AAPL — no open position in it. Any BUY here opens a NEW position."`  
  This is Portfolio Manager/Trader context, not chart input.

- The financial profile/mandate section except the long-only rule:  
  `"Primary goal: long_term_wealth ... Max open positions: 35 ... Trading pace cap: 4 per day, 12 per week ..."`  
  Position sizing, drawdown budgets, and trading pace are not the Market Analyst’s job; only `"LONG-ONLY. No short recommendations. Frame negative views as 'avoid' / 'wait'."` and the leverage warning need to remain.

- The redundant `"User mandate snapshot:"` block at the bottom.

- The non-technical data fields in the fact sheet: P/E, TTM revenue, profit margin, net debt, valuation multiples, dividend yield, sector/industry, analyst consensus, next earnings, news catalysts, FOMC countdown, and retail sentiment. These belong to other agents and invite domain bleed.

**Keep as load-bearing:**
- The grounding directive: `"Use only the facts and numbers explicitly provided in this prompt. Do not assume, infer, invent, or recall any datum you were not given ..."`
- The role boundaries: `"You DO NOT — Read fundamentals or earnings ... React to news catalysts ... Recommend final position sizing."`
- The proscribed indicators: `"No MACD, moving-average crossover signal, or Bollinger Bands are computed anywhere in this app — do not cite them"` and `"No intraday (1H) timeframe — only the daily bars actually fetched"`
- The `[STANCE: ... | CONVICTION: ... | HEADLINE: ...]` format requirement.
- The technical data fields: reference price, RSI, trend label, volume vs. 20-day average, 50-day range, 52-week range, and the source tags that say which fields are live.