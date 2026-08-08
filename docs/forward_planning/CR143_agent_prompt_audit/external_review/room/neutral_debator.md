# External review — neutral_debator

> Reviewer: `kimi-for-coding` · reasoning tokens 10022 · prompt 2633 tokens.
> **Hypotheses, not findings.** The reviewer cannot see our code; every claim needs a supplier check and a parser check before it becomes a defect.

## 1. JOB
Produce a stance‑tagged, concise recommendation on whether to buy AAPL now, proposing a middle‑path position size, entry, stop, and hedge that respects the user’s mandate and the supplied AAPL fact sheet.

## 2. CONTRADICTIONS

**A. The first line cannot be both the STANCE header and the “Splitting the difference…” opener.**

> “BEFORE the thesis sentence, your VERY FIRST line must be this one line, in exactly this shape, with your prose starting on the line after it:  
> `[STANCE: for|against|neutral | CONVICTION: low|medium|high | HEADLINE: <max 32 characters>]`”

versus

> “- Open with: “Splitting the difference, I’d propose [X]””

**B. The requested output is simultaneously limited to two sentences and required to contain multiple detailed elements.**

> “Write 2 sentences (middle size + one-line reason).”

versus

> “- State where you agree with each (Aggressive on conviction, Conservative on tail risk)”  
> “- Identify *inconsistencies* between the two that the data doesn’t resolve — surface them honestly”  
> “- Propose specific compromise: size, entry, stop, hedge”  
> “Format: lead with a one-sentence thesis, then short bullet points for supporting evidence.”

**C. Tone asks for tabular output; format forbids tables.**

> “Tone preference: terse, tabular, declarative — minimise prose”

versus

> “Plain text otherwise — no headings, no tables, no code fences.”

**D. The reference sizing example uses 5.0%, which directly conflicts with the 3.0% single‑name hard cap.**

> “Single-name position-size cap: 3.0% of portfolio in any one name — the SAME ceiling the Portfolio Manager clamps every trade to (CR101).”

versus

> “Reference position (risk-tier ceiling 5.0% size, entry 100.00, stop 81.00) → stop 19.0% below entry → portfolio-drawdown contribution ≈ 0.95 pt of the 30 pt cap (~3% of it). Size the actual trade against THIS figure, not the raw stop distance.”

**E. Voice asks for senior‑PM mediation prose while the tone preference asks to minimise prose.**

> “## Voice  
> Senior PM mediating between two analysts. Calm. Sees both sides. Decisive when needed.”

versus

> “Tone preference: terse, tabular, declarative — minimise prose”

## 3. UNFOLLOWABLE

**A. The agent is told to synthesise two debater arguments that are not supplied.**

> “## Inputs  
> - Trader’s proposal  
> - Aggressive Debator’s argument  
> - Conservative Debator’s argument  
> - The user’s mandate”

> “Synthesise both extremes.”

> “Note inconsistencies between Aggressive’s optimism and Conservative’s caution that data doesn’t resolve.”

> “- State where you agree with each (Aggressive on conviction, Conservative on tail risk)”

The only one of those inputs present in the prompt is the user’s mandate.

**B. “Propose specific compromise: size, entry, stop, hedge” cannot be done as a compromise when there are no Trader/Aggressive/Conservative positions to compromise between.**

> “Propose specific compromise: size, entry, stop, hedge”

**C. The total open‑risk cap cannot be checked because stop distances for the existing positions are missing.**

> “Total open-risk cap: 10.5% — the sum of (position size % × stop distance %)/100 across all open positions, including this one.”

The portfolio block gives MSFT and NVDA sizes but no stop distances, so the required sum is under‑determined.

## 4. FAILURE MODES

**1. Hallucinated synthesis.** Because the prompt repeatedly tells the model to “Synthesise both extremes” and to “State where you agree with each,” a competent model may simply invent Aggressive and Conservative arguments and then split them.

Bad output example:

> `[STANCE: neutral | CONVICTION: low | HEADLINE: split AAPL AI exposure]`  
> “Splitting the difference, I’d propose 1.5% of the book. Aggressive wanted 3% on the AI cycle, while Conservative only wanted 0.5% until the FOMC passes, so I land in the middle.”

This is bad because the Aggressive and Conservative cases were never provided.

**2. Format collision.** The model obeys one structural instruction and breaks another. It may dump the required STANCE header, or write two sentences and drop the size/entry/stop/hedge specifics, or obey the “tabular” preference and produce a table despite “no tables.”

Bad output example:

> `[STANCE: for | CONVICTION: medium | HEADLINE: AAPL at $313.33]`  
> “I’d buy AAPL at a middle weight. The valuation looks reasonable and the sector is Technology.”

This omits the required compromise details, bolded metrics, bullet evidence, and inconsistency notes.

**3. Oversized position from the 5% reference.** A model may follow the explicit instruction to “Size the actual trade against THIS figure,” producing a position above the 3.0% hard cap.

Bad output example:

> “Buy AAPL with a **5.0%** position at **$313.33**, stop **19%** below entry, no hedge.”

That breaches the single‑name cap and uses a stop derived from the generic reference rather than AAPL’s own ranges.

## 5. CUT

**Delete as noise / contradictions:**

- The conflicting opener:

> “- Open with: “Splitting the difference, I’d propose [X]””

- The impossible two‑sentence budget:

> “Write 2 sentences (middle size + one-line reason).”

- The “tabular” tone directive that collides with the no‑tables rule:

> “Tone preference: terse, tabular, declarative — minimise prose”

(Keep “terse, declarative — minimise prose” if desired; delete “tabular,” or delete “Plain text otherwise — no headings, no tables, no code fences.”)

- The senior‑PM voice block that fights the terse/tabular instruction:

> “## Voice  
> Senior PM mediating between two analysts. Calm. Sees both sides. Decisive when needed.”

- The contradictory 5.0% reference sizing example; replace it with a 3.0% example or remove it:

> “Reference position (risk-tier ceiling 5.0% size, entry 100.00, stop 81.00) → stop 19.0% below entry → portfolio-drawdown contribution ≈ 0.95 pt of the 30 pt cap (~3% of it). Size the actual trade against THIS figure, not the raw stop distance.”

**Must stay (load‑bearing):**

- The grounding directive:

> “Use only the facts and numbers explicitly provided in this prompt. Do not assume, infer, invent, or recall any datum you were not given…”

- All hard mandate caps and compliance rules: max drawdown, single‑name 3.0% cap, sector 40.0% cap, post‑loss cooldown, max open positions, trading pace cap, total open‑risk cap, LONG‑ONLY, and liquid‑only constraints.

- The simulated portfolio block:

> “Cash: $42,150.00 | Portfolio value: $61,634.00  
> Open positions:  
>   MSFT ×40 (26.1% of portfolio, unrealised +796.00)  
>   NVDA ×20 (5.5% of portfolio, unrealised +310.00)  
> You hold 0% of AAPL — no open position in it. Any BUY here opens a NEW position.”

- The AAPL fact sheet, including reference price, ranges, valuation, catalysts, and earnings date.

- The mandatory STANCE header format and the no‑preface/no‑headings formatting constraints.

- The Portfolio Manager routing instruction for final decisions.