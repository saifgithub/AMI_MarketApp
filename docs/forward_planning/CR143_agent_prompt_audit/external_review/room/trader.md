# External review — trader

> Reviewer: `kimi-for-coding` · reasoning tokens 11203 · prompt 2655 tokens.
> **Hypotheses, not findings.** The reviewer cannot see our code; every claim needs a supplier check and a parser check before it becomes a defect.

# 1. JOB

Produce a concrete, long-only AAPL trade proposal (instrument, side, size, entry, target, stop, time horizon, and rationale) using only the provided data and respecting the user's mandate.

---

# 2. CONTRADICTIONS

### 1. Required output format is given twice in incompatible forms
The prompt first demands a code-fenced template and a prose rationale, then later forbids code fences, tables, and headings and demands a one-line stance header plus bullet points.

Early format:

> `Output structure (always specific)`
> 
> ```
> Instrument:     {ticker}
> Side:           BUY | SELL | HOLD | WAIT
> Size:           X% of portfolio  (within mandate caps)
> Entry:          ${price}  (or "market" for market order)
> Target:         ${price}  (with rationale)
> Stop:           ${price}  (max acceptable loss)
> Time horizon:   {days/weeks/months}
> R:R:            {ratio}
> ```
> 
> `Followed by a 2–3 sentence rationale.`

Late format:

> `Your turn. Speak as the Trader. Write 3–4 sentences (instrument + side + size + entry + stop + target + horizon).`  
> `Format: lead with a one-sentence thesis, then short bullet points for supporting evidence. Use **bold** for key metrics (numbers, levels, deadlines). Plain text otherwise — no headings, no tables, no code fences.`  
> `BEFORE the thesis sentence, your VERY FIRST line must be this one line, in exactly this shape, with your prose starting on the line after it:`  
> `[STANCE: for|against|neutral | CONVICTION: low|medium|high | HEADLINE: <max 32 characters>]`

### 2. `Side` permits `SELL` while the mandate is long-only
The output schema explicitly includes `SELL`, but the user holds no AAPL, so a `SELL` would be a short recommendation, which is forbidden.

> `Side:           BUY | SELL | HOLD | WAIT`

vs.

> `LONG-ONLY. No short recommendations. Frame negative views as 'avoid' / 'wait'.`

and

> `long_only: long-only = no short/negative positions.`

### 3. "Tabular" tone is asked for and then forbidden
> `Voice`  
> `Direct. Numerical. Like a buy-side trader explaining their book to the PM.`

and

> `Tone preference: terse, tabular, declarative — minimise prose`

vs.

> `Plain text otherwise — no headings, no tables, no code fences.`

### 4. The output must be concrete on target/stop/horizon, but the grounding rule forbids inventing them
> `Target:         ${price}  (with rationale)`  
> `Stop:           ${price}  (max acceptable loss)`  
> `Time horizon:   {days/weeks/months}`

vs.

> `Use only the facts and numbers explicitly provided in this prompt. Do not assume, infer, invent, or recall any datum you were not given`

and

> `Use specific numbers wherever possible — but ONLY numbers from the data block above.`

The data block contains no pre-computed stop, trade target, or horizon.

---

# 3. UNFOLLOWABLE

### 1. The Trader is told to reflect inputs that are not in the prompt
> `Inputs`  
> `- Research Manager's synthesis`  
> `- Risk Debators' arguments (Aggressive, Conservative, Neutral)`

and

> `Ignore the Risk Debators' arguments — your size must reflect what they collectively allow`

The transcript is empty:

> `Transcript so far:`  
> `(You are first to speak.)`

A model cannot size a position based on arguments that were never provided.

### 2. Total open-risk cap cannot be verified
> `Total open-risk cap: 10.5% — the sum of (position size % × stop distance %)/100 across all open positions, including this one.`

The existing positions are listed without stops:

> `Open positions:`  
> `  MSFT ×40 (26.1% of portfolio, unrealised +796.00)`  
> `  NVDA ×20 (5.5% of portfolio, unrealised +310.00)`

There is no way to compute the current open-risk sum, so the model cannot ensure the new trade keeps total risk under 10.5%.

### 3. Stop, target, and horizon are required but not supplied
Same quotes as in contradiction #4 above. The only price levels available are:

> `Reference price: $313.33`  
> `Analyst consensus ... target $322.82`  
> `50-day range: $273.75–$344.57`  
> `52-week range: $223.78–$344.57`

There is no "stop" or "time horizon" datum, so a model must either violate the grounding rule or violate the output requirement.

### 4. Trading-pace and cooldown constraints cannot be checked
> `Trading pace cap: 4 per day, 12 per week (UTC calendar day / Monday-start ISO week).`

and

> `Post-loss cooldown: 1.0h after a stop-out — enforced as a hard block on the next BUY, not a suggestion.`

No trade history or recent stop-out status is provided, so the model cannot determine whether a new BUY is currently blocked.

---

# 4. FAILURE MODES

### 1. The model emits the early code-fenced template instead of the late plain-text format
Because the prompt opens with a detailed schema, a competent model may output:

```
Instrument: AAPL
Side: BUY
Size: 3.0%
Entry: $313.33
Target: $322.82
Stop: $280.00
Time horizon: 4 weeks
R:R: 1.3
```

This misses the required `[STANCE: ...]` first line, uses a code fence, and ignores the "one-sentence thesis + bullet points" format, failing the final rendering instructions.

### 2. The model invents a stop and target because the prompt demands them
With no stop level in the data block, the model may fabricate something plausible, e.g.:

> `Stop: $280 (drawn from the 50-day low)`  
> `Target: $340 (near the 52-week high)`

or use a round number from memory. This violates the grounding directive ("Do not assume, infer, invent..."), especially because choosing a stop from a range is an inference, not a provided number.

### 3. The model proposes a full 3.0% position without checking aggregate open risk
The prompt loudly states the 3.0% per-name cap:

> `Single-name position-size cap: 3.0% of portfolio in any one name`

and

> `Position size capped at 3.0% per name (risk_score=3).`

A model may output:

> `Size: 3.0%`

while ignoring the 10.5% total open-risk cap. Since MSFT already occupies 26.1% of the book and no stop distances are given, the model cannot know whether adding a 3.0% AAPL position with any stop would breach the aggregate cap. The output therefore looks compliant on one dimension but is unverifiable on another.

---

# 5. CUT

### Delete as noise

1. The early `Output structure` block is entirely overridden by the later formatting instruction.

> `Output structure (always specific)`
> 
> ```
> Instrument:     {ticker}
> Side:           BUY | SELL | HOLD | WAIT
> Size:           X% of portfolio  (within mandate caps)
> Entry:          ${price}  (or "market" for market order)
> Target:         ${price}  (with rationale)
> Stop:           ${price}  (max acceptable loss)
> Time horizon:   {days/weeks/months}
> R:R:            {ratio}
> ```
> 
> `Followed by a 2–3 sentence rationale.`

2. The `You DO NOT` list is mostly redundant with the `USER MANDATE` that already follows.

> `## You DO NOT`
> 
> `- Recommend leverage above what the user's drawdown cap can absorb`  
> `- Size a position over the cap implied by the user's risk_score`  
> `- Propose shorts when long_only=true`  
> `- Ignore the Risk Debators' arguments — your size must reflect what they collectively allow`  
> `- Skip the stop-loss`

3. The `Role guidance — Trader` section repeats the role description and the mandate caps already stated elsewhere.

> `─── Role guidance — Trader`  
> `You translate synthesis into a trade idea. Given this mandate:`  
> `- Output specific: instrument, side, size (% portfolio), entry, target, stop-loss, time horizon.`  
> `- Position size capped at 3.0% per name (risk_score=3).`  
> `- A position's contribution to portfolio drawdown is size% × stop-distance%, and total portfolio drawdown must stay within 30% (portfolio-level).`  
> `- Long-only mandate enforced.`

4. The `User mandate snapshot` duplicates the full `USER MANDATE` that appears earlier in the same prompt.

> `User mandate snapshot:`  
> `- risk_score: 3 (1=most conservative, 5=most aggressive)`  
> `- max_drawdown_pct: 30 — PORTFOLIO-level cap on total drawdown, NOT a per-trade stop budget. A position of size P% with a stop S% below entry contributes about P×S/100 percentage points to portfolio drawdown.`  
> `- long_only: long-only = no short/negative positions. It does NOT forbid buying, adding to, or holding a name.`  
> `- locale: en`

5. The long `Data source disclosure` preamble is redundant with the top-level grounding directive.

> `Data source disclosure — every fact below is tagged with where it came from. A field with no live source is marked not available below, never silently filled in — do NOT estimate, recall from training memory, or invent a number for it:`  
> `- Numeric fundamentals (price, P/E, growth, margin, net cash, 52-week range): each field below is tagged individually — a provider gap on one field does not make the others fake. Only the fields explicitly marked available/LIVE below are real; any field marked 'not available' has no data behind it.`  
> `- RSI, trend, volume, 50-day range: LIVE, computed from real yfinance price history as of this call. No MACD, moving-average crossover signal, or Bollinger Bands are computed — do not cite them.`  
> `- Recent catalyst/headline: LIVE, real news as of this call (publisher + recency shown below). Some headlines may carry a sentiment tag; treat it as one input, not a verdict.`  
> `- Retail sentiment/mention/influencer fields: alpha simulation scaffolding — NOT a live social feed.`  
> `- Forward catalyst: the FOMC decision countdown below is REAL, from the Fed's published calendar.`

### What must stay

- The **Grounding Directive** at the top: it is the only guardrail that prevents hallucination of prices, targets, and stops.
- The **User Mandate** caps and constraints: `max_drawdown_pct`, `single-name position-size cap`, `sector-concentration cap`, `long_only`, `trading pace`, `open positions`, `total open-risk cap`, and `post-loss cooldown`.
- The **Fact Sheet**: reference price, valuation metrics, ranges, analyst consensus, catalysts, and earnings date — these are the only numbers the model is allowed to use.
- The **Simulated Portfolio**: cash, portfolio value, and the list of open positions (even though stops are missing, the position sizes and AAPL status are needed to know it is a new position).
- The **final "Your turn" formatting block**: the stance header, one-sentence thesis, bullet-point evidence, bolded metrics, and "no headings / tables / code fences" rule. This is the only output spec that should be enforced, because it is the one that is actually rendered to the user.