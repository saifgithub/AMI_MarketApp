# External review — research_manager

> Reviewer: `kimi-for-coding` · reasoning tokens 4867 · prompt 2681 tokens.
> **Hypotheses, not findings.** The reviewer cannot see our code; every claim needs a supplier check and a parser check before it becomes a defect.

1. **JOB** — The Research Manager is supposed to produce a terse, number-driven AAPL synthesis that begins with a one-line stance header, states a one-sentence thesis, and supports it with 4–6 bullet points of evidence, all while respecting the long-only mandate.

2. **CONTRADICTIONS**

   - **Three-part structure vs. thesis+bullets+STANCE-line format.**  
     The prompt says:  
     > "**1. Points of agreement.** What do Bull and Bear actually share? **2. Points of dispute.** Where do they diverge ... **3. Recommended stance.** Lean long / lean short / pass / wait."  
     But it also says:  
     > "Format: lead with a one-sentence thesis, then short bullet points for supporting evidence."  
     and:  
     > "BEFORE the thesis sentence, your VERY FIRST line must be this one line... [STANCE: for|against|neutral | CONVICTION: low|medium|high | HEADLINE: <max 32 characters>]."  
     A model cannot simultaneously produce three numbered sections and a single thesis followed by bullets.

   - **"Tabular" tone vs. explicit "no tables" rule.**  
     The prompt says:  
     > "Match learning_style tone: terse, tabular, declarative — minimise prose"  
     but also:  
     > "Plain text otherwise — no headings, no tables, no code fences."

   - **Role requires Bull/Bear inputs, but the agent is told it is first to speak.**  
     The prompt says:  
     > "You adjudicate between the Bull and Bear Researchers and write the synthesis."  
     and lists under **Inputs**:  
     > "- Bull Researcher's argument - Bear Researcher's argument"  
     but the transcript section says:  
     > "Transcript so far: (You are first to speak.)"  
     An adjudicator cannot adjudicate arguments that have not been entered.

   - **Stance vocabulary differs between the two output descriptions.**  
     The 3-part structure says:  
     > "Lean long / lean short / pass / wait."  
     The mandatory header says:  
     > "[STANCE: for|against|neutral | CONVICTION: low|medium|high | HEADLINE: <max 32 characters>]."  
     "Lean short" and "against" are also hard to reconcile with the long-only mandate.

   - **"Pick a stance" conflicts with "neutral" and "STANCE: none".**  
     The prompt says:  
     > "Hedge mealy-mouthedly. Pick a stance."  
     but the header instructions say:  
     > "'neutral' if you genuinely land in the middle"  
     and:  
     > "If your role this turn is not to take a side at all, write 'STANCE: none'."

3. **UNFOLLOWABLE**

   - > "You adjudicate between the Bull and Bear Researchers and write the synthesis."  
     There are no Bull or Bear arguments in the prompt.

   - > "**1. Points of agreement.** What do Bull and Bear actually share?"  
     Cannot be answered without the missing Bull and Bear arguments.

   - > "Write 4–6 sentences (asymmetry numbers + lean + size implication)."  
     "Asymmetry numbers" is never defined and does not appear in the data block.

   - > "...size implication."  
     The Research Manager has no sizing authority; the Portfolio Manager is the binding output agent, and no sizing tool or formula is provided here.

   - > "HEADLINE: <max 32 characters>"  
     Forcing a complex synthesis into a single 32-character headline may be impossible if no single number "carries the view," yet the instruction does not allow omission.

   - > "Build on the transcript — do not repeat what's already been said."  
     The transcript is empty, so there is nothing to build on and nothing to avoid repeating.

4. **FAILURE MODES**

   1. **Hallucinated Bull/Bear content.** Because the role repeatedly demands adjudication but the Bull and Bear arguments are absent, a competent model may fabricate "Bull says X / Bear says Y" paragraphs from training memory about AAPL, then synthesize them. The output would look like a real debate recap, but it would be invented.

   2. **Format collision.** The model may attempt to honor both the 3-part structure and the thesis+bullets+STANCE-line format, producing a response that includes numbered headings ("1. Points of agreement"), a table, or a repeated STANCE line — violating the explicit "no headings," "no tables," and "Write this line ONCE, at the top only" rules.

   3. **Compliance drift.** The prompt offers "lean short" and "STANCE: against" as stance options, while the mandate says "LONG-ONLY. No short recommendations. Frame negative views as 'avoid' / 'wait'." A competent model may produce a short recommendation or a "lean short" call, violating the hard compliance constraint.

5. **CUT**

   **Delete as noise:**

   - > "## Output structure (in 1-on-1)  
   > In 1-on-1, structure your answer in 3 parts. In the Room, follow the format instruction appended at the end of your prompt instead.  
   > **1. Points of agreement.** What do Bull and Bear actually share?  
   > **2. Points of dispute.** Where do they diverge, and on what dimension (timeframe, magnitude, probability)?  
   > **3. Recommended stance.** Lean long / lean short / pass / wait. With reasoning tied to the user's mandate."  
   This entire section is for a 1-on-1 mode that is not active here; the end-of-prompt format already controls this turn.

   - > "When asked something you can't answer  
   > If the user wants a specific trade structure → Trader. If they want risk pushback → Risk Debators. If they want the final call → Portfolio Manager."  
   This is a Q&A routing instruction, not a synthesis instruction for this turn.

   - > "User mandate snapshot:  
   > - risk_score: 3 ...  
   > - max_drawdown_pct: 30 ...  
   > - long_only: long-only ...  
   > - locale: en"  
   This duplicates the full user mandate block above and adds no new constraint.

   - > "Voice  
   > Adjudicator. Calm. Like a senior portfolio manager listening to two analysts argue, then writing the memo."  
   This conflicts with the terse/tabular/minimal-prose tone preference and the "no headings" format.

   - > "You DO NOT  
   > - Hedge mealy-mouthedly. Pick a stance."  
   This conflicts with the explicit STANCE options that include "neutral" and "none."

   **Must stay (load-bearing):**

   - The grounding directive ("Use only the facts and numbers explicitly provided in this prompt...").
   - The full user mandate and compliance constraints (long-only, liquidity, position caps, drawdown framing).
   - The simulated portfolio block (cash, open positions, AAPL not held).
   - The AAPL fact sheet with all explicit data tags.
   - The mandatory STANCE header format and the "Write this line ONCE, at the top only" instruction.
   - The "Write 4–6 sentences" and "lead with a one-sentence thesis, then short bullet points" format constraint.
   - The "no headings, no tables, no code fences" formatting rule.
   - The redirect that the Research Manager must not give the final trade call.