# External review — aggressive_debator

> Reviewer: `kimi-for-coding` · reasoning tokens 8485 · prompt 2677 tokens.
> **Hypotheses, not findings.** The reviewer cannot see our code; every claim needs a supplier check and a parser check before it becomes a defect.

1. **JOB**

Produce a brief, structured risk-on argument for initiating a long AAPL position that begins with the mandatory `[STANCE: ... | CONVICTION: ... | HEADLINE: ...]` header, complies with the user mandate, and uses only numbers from the provided data block.

---

2. **CONTRADICTIONS**

**Output opener vs. mandatory header**
- "Open with: \"I'd push for [bigger / longer / less hedged]\""
- "BEFORE the thesis sentence, your VERY FIRST line must be this one line, in exactly this shape, with your prose starting on the line after it: `[STANCE: for|against|neutral | CONVICTION: low|medium|high | HEADLINE: <max 32 characters>]`"

**Bullets vs. two-sentence limit**
- "Format: lead with a one-sentence thesis, then short bullet points for supporting evidence."
- "Your turn. Speak as the Aggressive Debator. Write 2 sentences (size push + one-line reason)."

**Tone**
- "Tone preference: terse, tabular, declarative — minimise prose"
- "Voice — Conviction-forward. Not reckless. Like a hedge fund PM arguing with their risk officer — they know they're going to compromise, but they push for their view."

**Single-name cap vs. simulated portfolio**
- "Single-name position-size cap: 3.0% of portfolio in any one name — the SAME ceiling the Portfolio Manager clamps every trade to (CR101)."
- "Open positions: MSFT ×40 (26.1% of portfolio, unrealised +796.00)"

**Single-name cap vs. reference-position ceiling**
- "Single-name position-size cap: 3.0% of portfolio in any one name"
- "Reference position (risk-tier ceiling 5.0% size, entry 100.00, stop 81.00) → stop 19.0% below entry → portfolio-drawdown contribution ≈ 0.95 pt of the 30 pt cap (~3% of it). Size the actual trade against THIS figure, not the raw stop distance."

---

3. **UNFOLLOWABLE**

- "Cite opportunity cost: \"If we sit at half-size and the thesis plays out, we leave X% on the table\"" — there is no target price, position-size scenario, or expected return in the data block, so `X` cannot be computed from provided numbers.

- "HARD CONSTRAINT: a position's portfolio-drawdown contribution (size% × stop-distance%) plus existing drawdown cannot exceed 30%." — the proposed AAPL stop distance is not supplied and the portfolio's current drawdown is not supplied.

- "Total open-risk cap: 10.5% — the sum of (position size % × stop distance %)/100 across all open positions, including this one." — stop distances for MSFT and NVDA are not supplied, so the running sum cannot be calculated.

- "Sector-concentration cap: 40.0% of portfolio in any one GICS sector — the SAME ceiling the safety floor blocks a proposed BUY against." — current GICS-sector weights of the simulated portfolio are not supplied.

- "Trading pace cap: 4 per day, 12 per week (UTC calendar day / Monday-start ISO week)." — today's trade count and this week's trade count are not supplied.

---

4. **FAILURE MODES**

1. **Structural/format failure.** The model will emit a flowing hedge-fund-PM paragraph, omit or misplace the `[STANCE: ...]` header, and/or include tables, because the prompt simultaneously demands an opener quote, a mandatory header before the thesis, bullets, and a two-sentence limit.

2. **Hallucinated opportunity cost.** The model will invent a number for `X` in "we leave X% on the table" because the prompt both supplies that template and instructs "Use specific numbers wherever possible" without providing the inputs needed to compute it.

3. **Silent cap breach.** The model will recommend a concrete AAPL size and stop (e.g., "size to 3% with a 12% stop") without checking it against the 10.5% total open-risk cap or the 30% drawdown cap, because the prompt asks for specific sizing but withholds the existing-stop and drawdown data required to verify compliance.

---

5. **CUT**

**Delete as noise**

- The entire **Output style** block:
  > "Open with: \"I'd push for [bigger / longer / less hedged]\""  
  > "Cite opportunity cost: \"If we sit at half-size and the thesis plays out, we leave X% on the table\""  
  > "Address the Conservative's specific concerns — don't strawman"  
  > "Acknowledge the hard floor: you can advocate up to the user's mandate, never past it"  
  It conflicts with the precise `Your turn` format and the opportunity-cost quote is unfollowable.

- The **Voice** paragraph:
  > "Conviction-forward. Not reckless. Like a hedge fund PM arguing with their risk officer — they know they're going to compromise, but they push for their view."  
  It directly contradicts "Tone preference: terse, tabular, declarative — minimise prose" and "no headings, no tables, no code fences".

- The **When asked something you can't answer** block:
  > "For the conservative case → Conservative Debator. For balance → Neutral Debator. For final → Portfolio Manager."  
  This agent is first to speak; no routing question is being asked.

- The redundant **User mandate snapshot** lines that merely repeat the full mandate above:
  > "max_drawdown_pct: 30 — PORTFOLIO-level cap on total drawdown, NOT a per-trade stop budget. A position of size P% with a stop S% below entry contributes about P×S/100 percentage points to portfolio drawdown."  
  > "long_only: long-only = no short/negative positions. It does NOT forbid buying, adding to, or holding a name."  
  > "locale: en"

- The **Reference position** example:
  > "Reference position (risk-tier ceiling 5.0% size, entry 100.00, stop 81.00) → stop 19.0% below entry → portfolio-drawdown contribution ≈ 0.95 pt of the 30 pt cap (~3% of it). Size the actual trade against THIS figure, not the raw stop distance."  
  It introduces a 5.0% ceiling that conflicts with the 3.0% single-name cap and the arithmetic is irrelevant without a supplied AAPL stop.

**Must stay**

- The grounding directive: "Use only the facts and numbers explicitly provided in this prompt."
- The mandatory `[STANCE: for|against|neutral | CONVICTION: low|medium|high | HEADLINE: <max 32 characters>]` line rule and the `Your turn` format instructions (thesis, bullets, bold numbers, no headings/tables).
- Each hard cap from the mandate: 30% max drawdown, 3.0% single-name, 40.0% sector, 10.5% total open-risk, 35 max positions, trading-pace limits.
- The single added nuance in role guidance: "plus existing drawdown cannot exceed 30%."
- The simulated portfolio and the AAPL data block.