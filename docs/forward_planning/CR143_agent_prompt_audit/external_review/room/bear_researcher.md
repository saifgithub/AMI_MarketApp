# External review — bear_researcher

> Reviewer: `kimi-for-coding` · reasoning tokens 11052 · prompt 2716 tokens.
> **Hypotheses, not findings.** The reviewer cannot see our code; every claim needs a supplier check and a parser check before it becomes a defect.

## 1. JOB

Produce a concise, data-bound bearish assessment of AAPL for a long-only student: a stance line, a one-sentence avoid/wait thesis, and 3–5 bullet-backed risks using **only** the numbers supplied in the fact sheet.

---

## 2. CONTRADICTIONS

**Output structure is specified three incompatible ways.**
- `Lead with the risk thesis in one paragraph`
- vs. `Write 3–5 sentences (risk + quantification + invalidator)`
- vs. `Format: lead with a one-sentence thesis, then short bullet points for supporting evidence.`

**“Tabular” preference collides with the format ban.**
- `Tone preference: terse, tabular, declarative — minimise prose`
- vs. `Plain text otherwise — no headings, no tables, no code fences.`

**Short-structure instructions exist in a hard long-only session.**
- `If short selling is allowed, propose specific short structure (size, stop, hedge)`
- vs. `Compliance constraints (HARD — cannot violate): - LONG-ONLY. No short recommendations.` and `LONG-ONLY user — frame as 'avoid' or 'wait for better entry'. Do NOT propose shorts.`

**Risk count conflicts with the sentence budget.**
- `Identify the 2–3 most dangerous risks (not 10 minor ones)`
- vs. `Write 3–5 sentences (risk + quantification + invalidator)`. Two risks already need at least a thesis + risk + quantification + invalidator each; three risks cannot fit in 3–5 sentences while also including a stance line.

**The quantification example pressures the model to invent numbers the grounding directive forbids.**
- `Quantify downside: "if X happens, we're looking at -25%, and X is more likely than consensus thinks because..."`
- vs. `Use only the facts and numbers explicitly provided in this prompt... never fill the gap with an assumption.` The `-25%` figure is not in the data block.

**The role demands “against,” but the stance template permits neutrality/ambivalence.**
- `Build the strongest possible case AGAINST taking the position`
- vs. `STANCE: your view on taking this position now — 'for', 'against', or 'neutral' if you genuinely land in the middle.`

---

## 3. UNFOLLOWABLE

`Quantify downside: "if X happens, we're looking at -25%, and X is more likely than consensus thinks because..."`
No event “X” or impact magnitude is provided in the data block; producing that sentence requires inventing/deriving a number in violation of the grounding directive.

`Liquid only. Avoid microcaps (< $500M market cap)`
The fact sheet does **not** contain market cap, so the model cannot assess this constraint.

`Total open-risk cap: 10.5% — the sum of (position size % × stop distance %)/100 across all open positions, including this one.`
Stop distances for the existing `MSFT` and `NVDA` positions are not supplied, so the model cannot compute total open risk or verify compliance.

`If short selling is allowed, propose specific short structure (size, stop, hedge)`
In this session short selling is **not** allowed (`Compliance constraints (HARD — cannot violate): - LONG-ONLY`), so this instruction has no legal exit path.

---

## 4. FAILURE MODES

1. **Short recommendation leaks through despite the long-only mandate.**  
   Prompted by `Build the strongest possible case AGAINST taking the position` and `If short selling is allowed, propose specific short structure (size, stop, hedge)`, the model may output:  
   `[STANCE: against | CONVICTION: high | HEADLINE: short AAPL at 313.33]` followed by “short 3% of portfolio, stop at $340, hedge with QQQ puts.” This directly violates `LONG-ONLY. No short recommendations.`

2. **Hallucinated quantification to satisfy the “specific numbers” pressure.**  
   Because the prompt says `Use specific numbers wherever possible` and `Quantify downside: "if X happens, we're looking at -25%..."` but the data block lacks scenario impact numbers, the model may invent unsupported claims like: “If China iPhone revenue drops 10%, downside is -22% to ~$244.” No China or revenue-segment data is in the block, breaching the grounding directive.

3. **Format collapses under contradictory structural instructions.**  
   The model may emit a multi-paragraph essay, add headings, or create a table because `Lead with the risk thesis in one paragraph` and `terse, tabular, declarative` fight with `lead with a one-sentence thesis, then short bullet points` and `no headings, no tables`. A bad output would miss the required `[STANCE: ...]` line, exceed the 3–5 sentence budget, or present risks in a markdown table.

---

## 5. CUT

**Delete as noise / conflict:**

> `Skeptical but rigorous. You're not the doom-and-gloom guy — you're the disciplined "what could break this thesis" guy. Like a veteran short-seller writing a Sohn Conference presentation.`

This is flavor text that conflicts with `terse... minimise prose` and encourages verbose, conference-style prose rather than the mandated 3–5 sentences.

> `When asked something you can't answer`  
> `For the positive case → Bull Researcher. For the final call → Trader. For the synthesis → Research Manager.`

This agent is being asked to produce a bear case, not to route questions; the block is irrelevant boilerplate.

> `If short selling is allowed, propose specific short structure (size, stop, hedge)`

In this long-only session this clause is either dead text or a trap. Remove it or gate it behind a runtime variable that is false here.

> `Quantify downside: "if X happens, we're looking at -25%, and X is more likely than consensus thinks because..."`

The `-25%` example is an invented number that the grounding directive explicitly forbids. Replace with `Quantify downside using only the numbers in the data block; if no impact number is available, state so.`

> `- Tone preference: terse, tabular, declarative — minimise prose`

Remove the word `tabular`; it directly conflicts with `no tables`. Keep `terse, declarative — minimise prose`.

> `- max_drawdown_pct: 30 — PORTFOLIO-level cap on total drawdown, NOT a per-trade stop budget. A position of size P% with a stop S% below entry contributes about P×S/100 percentage points to portfolio drawdown.`

This duplicates the earlier full max-drawdown paragraph in the snapshot; delete the duplicate.

> `Sizing ceiling: any position size you suggest must respect the enforced single-name cap of 3.0% of portfolio (risk_score=3). Do NOT propose a larger allocation — the system clamps to this cap, so a bigger number is both wrong and misleading.`

This duplicates `Single-name position-size cap: 3.0% of portfolio in any one name — the SAME ceiling the Portfolio Manager clamps every trade to (CR101)` and is largely irrelevant to an avoid/wait recommendation.

**Load-bearing and must stay:**

- `Use only the facts and numbers explicitly provided in this prompt... never fill the gap with an assumption.`
- `Build the strongest possible case AGAINST taking the position... steelman the avoid/short thesis.`
- `LONG-ONLY. No short recommendations. Frame negative views as 'avoid' / 'wait'.`
- The fact sheet and source-disclosure block, including the explicit `Reference price`, `P/E`, `52-week range`, `Next earnings`, etc.
- The `[STANCE: for|against|neutral | CONVICTION: low|medium|high | HEADLINE: <max 32 characters>]` format and its “once at the top only” rule.
- `Write 3–5 sentences (risk + quantification + invalidator)` and `Use specific numbers wherever possible — but ONLY numbers from the data block above.`