# External review — conservative_debator

> Reviewer: `kimi-for-coding` · reasoning tokens 5958 · prompt 2646 tokens.
> **Hypotheses, not findings.** The reviewer cannot see our code; every claim needs a supplier check and a parser check before it becomes a defect.

1. **JOB** — This agent is supposed to produce a structured conservative risk assessment of the AAPL trade, with a `[STANCE/CONVICTION/HEADLINE]` header, a thesis, and bullets quantifying a downside scenario and protective measures, using only numbers provided in the prompt.

2. **CONTRADICTIONS**

   **a. The requested deliverable is both a multi-part analysis and a two-sentence reply.**  
   - The "Output style" section requires:  
     `"Open with: 'I'd argue for [smaller / shorter / hedged / wait]'"`,  
     `"Identify the *specific* downside scenario you're protecting against"`,  
     `"Quantify: 'if X happens, we're down Y%, and that uses up Z% of our drawdown cap'"`, and  
     `"Propose specific protective measures (size cap, stop-loss, hedge)"`.  
   - The final instruction says:  
     `"Your turn. Speak as the Conservative Debator. Write 2 sentences (size cap + one-line reason)."`  
   A model cannot satisfy both; one must be ignored.

   **b. The model is told to engage arguments that do not exist.**  
   - `"Inputs"` lists: `"- Aggressive Debator's argument"`, `"- Neutral Debator's argument"`.  
   - `"You DO NOT"` includes: `"- Ignore the Aggressive Debator's points — engage them."`  
   - But the transcript states: `"Transcript so far: (You are first to speak.)"`  
   There is nothing to engage.

   **c. The output format is simultaneously tabular and bulleted.**  
   - `"Tone preference: terse, tabular, declarative — minimise prose"`  
   - `"Format: lead with a one-sentence thesis, then short bullet points for supporting evidence."`  
   A model cannot be both tabular and use bullet points.

   **d. The single-name cap conflicts with the worked sizing example.**  
   - `"Single-name position-size cap: 3.0% of portfolio in any one name — the SAME ceiling the Portfolio Manager clamps every trade to (CR101)."`  
   - `"Reference position (risk-tier ceiling 5.0% size, entry 100.00, stop 81.00) → stop 19.0% below entry → portfolio-drawdown contribution ≈ 0.95 pt of the 30 pt cap (~3% of it). Size the actual trade against THIS figure, not the raw stop distance."`  
   The reference uses 5.0% while the hard cap is 3.0%.

   **e. The conservative role is neutered by an instruction not to oppose trades the risk score supports.**  
   - `"## Role"` and `"Role guidance"` say: `"Push for smaller sizing, tighter stops, faster exits."`  
   - `"You DO NOT"` includes: `"- Recommend against trades that the user's risk_score clearly supports."`  
   The prompt never defines what risk_score `3/5` "clearly supports," so the conservative push is conditional on secret knowledge.

3. **UNFOLLOWABLE**

   - `"Inputs: - Trader's proposal - Aggressive Debator's argument - Neutral Debator's argument - The user's mandate, current drawdown, and any recent loss patterns"` — the prompt lists `current drawdown` and `recent loss patterns` as inputs but never provides them; the debator arguments are absent because the transcript is empty.

   - `"You DO NOT ... - Ignore the Aggressive Debator's points — engage them."` — impossible to comply with when the Aggressive Debator has not spoken.

   - `"Identify the *specific* downside scenario you're protecting against"` and `"Quantify: 'if X happens, we're down Y%, and that uses up Z% of our drawdown cap'"` — both require the Trader's proposal (entry price, intended size, stop level, holding period) which is not in the prompt.

   - `"Propose specific protective measures (size cap, stop-loss, hedge)"` — requires a proposal to protect; there is no proposal to modify.

   - `"Build on the transcript — do not repeat what's already been said."` — the transcript is `"Transcript so far: (You are first to speak.)"`, so there is nothing to build on.

   - `"Use specific numbers wherever possible — but ONLY numbers from the data block above."` — many required numbers (current open risk contribution from MSFT/NVDA, current drawdown, recent stops, today's trade count, the Trader's proposal) are absent.

   - `"Total open-risk cap: 10.5% — the sum of (position size % × stop distance %)/100 across all open positions, including this one."` — cannot be computed because the stop distances for the existing MSFT and NVDA positions are not provided.

   - `"Do not... Recommend against trades that the user's risk_score clearly supports."` — unfollowable because no mapping from `risk_score: 3` to a specific trade recommendation is provided.

4. **FAILURE MODES**

   1. **Scope collapse or bloat.** A competent model will either (a) obey `"Write 2 sentences"` and drop the required downside scenario, quantification, and protective measures, or (b) obey the `"Output style"` section and produce a full paragraph with bullets, violating the two-sentence constraint. Either output is malformed for this prompt.

   2. **Hallucination of missing inputs.** The model will invent the Trader's proposal, the Aggressive Debator's points, the current drawdown, or recent loss patterns in order to satisfy `"engage them"` and `"Build on the transcript"` — directly violating the GROUNDING DIRECTIVE that says `"Use only the facts and numbers explicitly provided in this prompt."`

   3. **Position-size / drawdown math error.** The model will use the salient `"5.0% size"` reference example instead of the `"3.0% of portfolio"` single-name cap, or it will compare the raw stop distance to the `"30% portfolio drawdown"` cap despite the explicit prohibition: `"Do not compare a stop's distance directly against this cap."`

5. **CUT**

   **Delete as noise or conflicting instructions:**

   - `"Output style"` section:  
     `"Open with: 'I'd argue for [smaller / shorter / hedged / wait]'"`  
     `"Identify the *specific* downside scenario you're protecting against"`  
     `"Quantify: 'if X happens, we're down Y%, and that uses up Z% of our drawdown cap'"`  
     `"Propose specific protective measures (size cap, stop-loss, hedge)"`  
     This entire block conflicts with the later `"Write 2 sentences"` instruction and with the required `[STANCE/CONVICTION/HEADLINE]` header. Keep one consistent output spec.

   - `"Risk officer voice. Steady. Quantitative. Like the veteran in the room who's seen too many cycles. Not panicky — just disciplined."`  
     This is prose-heavy flavor text that conflicts with `"terse, tabular, declarative — minimise prose"`. The first sentence is enough; the "veteran" clause is noise.

   - `"Reference position (risk-tier ceiling 5.0% size, entry 100.00, stop 81.00) → stop 19.0% below entry → portfolio-drawdown contribution ≈ 0.95 pt of the 30 pt cap (~3% of it). Size the actual trade against THIS figure, not the raw stop distance."`  
     Delete or rewrite: a 5.0% example directly contradicts the 3.0% single-name cap. If the goal is to teach drawdown arithmetic, the example should use the 3.0% cap, not a fictional 5.0% tier.

   - `"You DO NOT ... - Recommend against trades that the user's risk_score clearly supports."`  
     Delete. It is vague, unfollowable, and undermines the conservative role. If the intent is to keep the debator from always saying "no," specify concrete thresholds.

   **Load-bearing and must stay:**

   - `"─── GROUNDING DIRECTIVE (applies to every response) ─── Use only the facts and numbers explicitly provided in this prompt. Do not assume, infer, invent, or recall any datum you were not given..."`
   - `"Max acceptable drawdown: 30% — a PORTFOLIO-level cap on total drawdown, NOT a per-trade stop budget. A single position of size P% (of portfolio) with a stop S% below entry contributes only about P×S/100 percentage points to portfolio drawdown..."`
   - `"Single-name position-size cap: 3.0% of portfolio in any one name — the SAME ceiling the Portfolio Manager clamps every trade to (CR101)."`
   - `"BEFORE the thesis sentence, your VERY FIRST line must be this one line, in exactly this shape, with your prose starting on the line after it: [STANCE: for|against|neutral | CONVICTION: low|medium|high | HEADLINE: <max 32 characters>]"`
   - The AAPL data block (`Reference price: $313.33`, `P/E: 36.0 trailing...`, `50-day range...`, `Next earnings...`, etc.) — it is the only permitted source of numbers.
   - `"Your turn. Speak as the Conservative Debator. ... Use specific numbers wherever possible — but ONLY numbers from the data block above. Do NOT cite figures (P/E, growth, price targets, market cap) from training memory..."` — the anti-hallucination constraint is essential.