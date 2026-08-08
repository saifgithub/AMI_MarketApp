# External review — social_media_analyst

> Reviewer: `kimi-for-coding` · reasoning tokens 7868 · prompt 2949 tokens.
> **Hypotheses, not findings.** The reviewer cannot see our code; every claim needs a supplier check and a parser check before it becomes a defect.

1. JOB — This agent is supposed to produce a 2–3-sentence social-sentiment read on AAPL, opening with a single `[STANCE: ... | CONVICTION: ... | HEADLINE: ...]` line, using only numbers that appear in the provided data block and staying strictly inside the sentiment lane.

2. CONTRADICTIONS —

- **Numbers demand vs. absent social data.** The prompt says:  
  `"Use specific numbers wherever possible — but ONLY numbers from the data block above."`  
  But the only injected social datum is:  
  `"Retail sentiment: moderately bullish (typical intensity (illustrative))"`  
  and the fields are explicitly tagged:  
  `"Retail sentiment/mention/influencer fields: alpha simulation scaffolding — NOT a live social feed."`  
  There are no mention counts, buzz scores, or bull/bear splits to use.

- **Use other analysts’ context vs. forbidden to see it.** The prompt says:  
  `"When no real data is injected ... reason qualitatively and illustratively instead, using whatever real price/fundamentals/news context is available from the other analysts and the debate transcript."`  
  But it also says:  
  `"You are speaking AT THE SAME TIME as the other analysts and cannot see their contributions — the transcript above is empty by design. Do not reference, defer to, or assume another analyst's read."`

- **Extreme-signal framing vs. moderate data.** The prompt asks the agent to:  
  `"Distinguish *organic enthusiasm* from *coordinated activity*"`  
  and to  
  `"Surface contrarian signals (extreme greed → reversion risk; extreme fear → opportunity)"`  
  while the data only says:  
  `"Retail sentiment: moderately bullish (typical intensity (illustrative))."`  
  There is no basis for an organic/coordinated distinction or an extreme contrarian call.

- **Stay in your lane vs. output a trade stance.** The prompt says:  
  `"Sentiment is your lane. For everything else (chart, fundamentals, news, trade), redirect."`  
  Yet the required output opens with:  
  `"STANCE: your view on taking this position now — 'for', 'against', or 'neutral' if you genuinely land in the middle"`  
  and demands:  
  `"Use **bold** for key metrics (numbers, levels, deadlines)."`  
  The only numbers supplied are outside the agent’s lane, so the scaffold pushes it to cite fundamentals/technicals to have something to bold.

3. UNFOLLOWABLE —

- `"Use specific numbers wherever possible — but ONLY numbers from the data block above."`  
  Cannot be followed for the social-sentiment domain because no social numbers are injected.

- `"Distinguish *organic enthusiasm* from *coordinated activity* as a conceptual framing, not a claim about specific accounts"`  
  There is no account-level or coordination data to distinguish.

- `"Surface contrarian signals (extreme greed → reversion risk; extreme fear → opportunity)"`  
  The provided sentiment is "moderately bullish" and "typical," not extreme.

- `"using whatever real price/fundamentals/news context is available from the other analysts and the debate transcript"`  
  The transcript is empty and the model is forbidden to assume other analysts’ reads.

- `"Use **bold** for key metrics (numbers, levels, deadlines)"`  
  No social-media metrics exist in the data block for this agent to bold.

4. FAILURE MODES —

- **Hallucinated social metrics.** The model invents figures like “Reddit mentions up 18% WoW,” a “buzz score of 6.2/10,” or a “72/28 bullish/bearish split” to satisfy the numbers demand, directly violating:  
  `"Never present a specific number (a mention-trend %, a σ score, a sentiment index value) as if it were measured from a real source unless it was actually injected into this prompt."`

- **Lane drift into fundamentals/technicals.** The model cites `P/E 36.0`, `RSI 41`, `target $322.82`, or `FOMC in 39 days` to populate the bold-metrics/stance scaffold, producing output like:  
  `"[STANCE: for | CONVICTION: low | HEADLINE: RSI 41, target $322.82] Retail sentiment is moderately bullish while AAPL consolidates at **RSI 41** and trades below the **Street target of $322.82**. The **FOMC in 39 days** keeps fear contained, so the contrarian read is neutral-to-positive."`  
  This ignores the directive: `"Sentiment is your lane. For everything else (chart, fundamentals, news, trade), redirect."`

- **Vacuous or forced stance.** Either the model emits a number-free tautology:  
  `"Retail sentiment is moderately bullish and typical, so no contrarian signal; wait for extremes,"`  
  failing the “use specific numbers” and stance pressure, or it forces a trade view from no actual social signal:  
  `"[STANCE: for | CONVICTION: low | HEADLINE: moderately bullish retail] Retail mood is moderately bullish, which aligns with the buy-side consensus; no panic selling detected,"`  
  violating `"Sentiment is one input"` and the prohibition on making recommendations.

5. CUT —

**Delete as noise:**

- The duplicated financial-profile bloat, e.g.:

  ```
  Primary goal: long_term_wealth
  Horizon: long  (3–10 years)
  Target outcome: (no specific target)
  Path: long_horizon
  Risk score: 3/5
  Max acceptable drawdown: 30% — a PORTFOLIO-level cap on total drawdown, NOT a per-trade stop budget.
  ```

  and its near-verbatim echo in the “User mandate snapshot”:

  ```
  risk_score: 3 (1=most conservative, 5=most aggressive)
  max_drawdown_pct: 30 — PORTFOLIO-level cap on total drawdown, NOT a per-trade stop budget.
  long_only: long-only = no short/negative positions.
  ```

  Position-sizing, drawdown, stop, cooldown, and trading-pace constraints are Portfolio Manager logic, not inputs a first-speaking Social Media Analyst needs.

- The entire simulated portfolio section:

  ```
  ─── YOUR SIMULATED PORTFOLIO (AMI's portfolio of record — simulation-only) ───
  Cash: $42,150.00 | Portfolio value: $61,634.00
  Open positions:
    MSFT ×40 (26.1% of portfolio, unrealised +796.00)
    NVDA ×20 (5.5% of portfolio, unrealised +310.00)
  You hold 0% of AAPL — no open position in it. Any BUY here opens a NEW position.
  ```

  Holdings are irrelevant to a sentiment read; this is noise that also invites the agent to reason about portfolio fit.

- Non-social fields in the data block, e.g.:

  ```
  P/E: 36.0 trailing ... 32.9 forward
  TTM revenue growth: 16%, profit margin: 28%
  Net debt $21945M
  RSI: 41 (neither overbought nor oversold), trend: consolidating
  50-day range: $273.75–$344.57 ... Volume: in-line with 20-day average ... 52-week range: $223.78–$344.57
  Valuation (LIVE): P/S 9.8x, EV/EBITDA 27.4x, PEG 2.46 ...
  Dividend yield (LIVE): 0.34% ...
  Analyst consensus (LIVE, Street view — NOT company guidance): buy, target $322.82
  Next earnings (LIVE): 2026-10-29 (Q4) — in 82 days, consensus EPS est. $1.97643
  ```

  These belong to other analysts and bait this agent into lane drift.

- The redundant `## Role guidance — Social Media Analyst` section, which repeats the Inputs, Output style, and prohibitions already stated above.

**Load-bearing and must stay:**

- The grounding directive: `"Use only the facts and numbers explicitly provided in this prompt. Do not assume, infer, invent, or recall any datum you were not given..."`
- The lane boundary: `"Sentiment is your lane. For everything else (chart, fundamentals, news, trade), redirect."`
- The source limitation: `"Reddit-only aggregate sentiment ... No Twitter/X, StockTwits, Google Trends, or Discord access exists anywhere in the backend..."`
- The illustrative-data rule: `"When no real data is injected ... reason qualitatively and illustratively instead ... never present a specific number ... as if it were measured from a real source unless it was actually injected..."`
- The actual social datum: `"Retail sentiment: moderately bullish (typical intensity (illustrative))"`
- The output format and the stance/conviction/headline line instruction, including `"Plain text otherwise — no headings, no tables, no code fences."`