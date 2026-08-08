# External review — bull_researcher

> Reviewer: `kimi-for-coding` · reasoning tokens 8987 · prompt 2739 tokens.
> **Hypotheses, not findings.** The reviewer cannot see our code; every claim needs a supplier check and a parser check before it becomes a defect.

## 1. JOB
Produce a concise, data-bound bullish case for AAPL under the user's mandate, beginning with a required STANCE header and a one-sentence thesis, followed by bullet evidence, a falsifier, and a sizing suggestion.

## 2. CONTRADICTIONS

- **"Lead with the thesis in one paragraph"** vs. **"BEFORE the thesis sentence, your VERY FIRST line must be this one line, in exactly this shape, with your prose starting on the line after it:"** — the STANCE meta-line must precede the thesis, so the thesis cannot both "lead" and be the first substantive prose. The later instruction also says **"lead with a one-sentence thesis, then short bullet points"**, not a paragraph.

- **"End with a sizing suggestion based on conviction × user's risk tolerance"** vs. **"Write 3–5 sentences (thesis + evidence + falsifier)"** — the length/content prescription has no room for the sizing conclusion that the Output style requires.

- **"Cite 3–5 specific analyst points as evidence (e.g., 'Fundamentals Analyst flagged 32% gross margins…')"** vs. **"Use only the facts and numbers explicitly provided in this prompt. Do not assume, infer, invent, or recall any datum you were not given"** — the example models citing a non-existent analyst and a number (32% gross margin) that is not in the fact sheet, while the grounding directive forbids invention.

- **"Build the strongest possible case FOR going long. You steelman the buy thesis."** vs. **"STANCE: your view on taking this position now — 'for', 'against', or 'neutral' if you genuinely land in the middle."** — the role compels a 'for' stance, but the header permits against/neutral and even instructs **"If your role this turn is not to take a side at all, write 'STANCE: none'. Never guess a side to fill the field."**

- **"Frame upside numerically: '$X by Y' not 'could go up significantly'"** + **"Horizon: long (3–10 years)"** vs. the data block, which only supplies an 82-day earnings date and a consensus target of **$322.82** tied to no explicit date. To hit the user's horizon with "$X by Y" the model must invent a price or a date, which the grounding directive forbids.

## 3. UNFOLLOWABLE

- **"Cite 3–5 specific analyst points as evidence (e.g., 'Fundamentals Analyst flagged 32% gross margins…')"** — no analyst-by-analyst outputs are present; the fact sheet is not broken out by Fundamentals / Market / News / Social agents.

- **"Outputs from the analyst opinions present this session (there may be fewer than four)"** — this is listed as an input, but the transcript is empty and no such outputs are provided.

- **"End with a sizing suggestion based on conviction × user's risk tolerance"** — no conviction scale and no risk-tolerance-to-size mapping are defined; only a hard 3.0% cap is given.

- **"Respect ticker_blocklist absolutely."** — no ticker blocklist appears anywhere in the prompt.

- **"Build on the transcript — do not repeat what's already been said"** given **"Transcript so far: (You are first to speak.)"** — there is no prior content to build on or avoid repeating.

## 4. FAILURE MODES

1. **Hallucinated analyst attributions.** The model will invent lines like *"Fundamentals Analyst flagged 28% profit margins"* because it is told to **"Cite 3–5 specific analyst points as evidence"** and is shown the pattern **"(e.g., 'Fundamentals Analyst flagged 32% gross margins…')"**, even though the transcript is empty and the grounding directive forbids invention.

2. **Wrong STANCE or format.** The model outputs **"STANCE: neutral"** or **"STANCE: against"** because the header permits it and even suggests **"STANCE: none"** when not taking a side, conflicting with the Bull's required **"FOR going long"** role; alternatively it omits the header, puts prose on the same line, or adds headings/tables despite **"no headings, no tables, no code fences."**

3. **Invented long-horizon price target.** The model produces something like *"$425 by 2029"* because it must obey **"Frame upside numerically: '$X by Y'"** and the user's horizon is **"long (3–10 years)"**, but the data only contain a consensus target of **$322.82** with no date and an earnings date 82 days out.

## 5. CUT

**Delete as noise:**

- **"If the user wants the opposing view, redirect to the Bear Researcher. If they want a final call, redirect to the Trader or convene the Room."** — irrelevant on a first-turn monologue where there is no user question.

- The duplicate **"User mandate snapshot"** block:
  > User mandate snapshot:
  > - risk_score: 3 (1=most conservative, 5=most aggressive)
  > - max_drawdown_pct: 30 — PORTFOLIO-level cap on total drawdown, NOT a per-trade stop budget. A position of size P% with a stop S% below entry contributes about P×S/100 percentage points to portfolio drawdown.
  > - long_only: long-only = no short/negative positions. It does NOT forbid buying, adding to, or holding a name.
  > - locale: en

- The example **"(e.g., 'Fundamentals Analyst flagged 32% gross margins…')"** — it actively trains hallucination of both an analyst role and a number not in the data block.

- **"Tone preference: terse, tabular, declarative — minimise prose"** — "tabular" and "minimise prose" conflict with the required prose-and-bullet output format.

**Load-bearing and must stay:**

- The grounding directive: **"Use only the facts and numbers explicitly provided in this prompt..."**
- The role instruction: **"Build the strongest possible case FOR going long. You steelman the buy thesis."**
- The STANCE header format requirement.
- The output format: **"lead with a one-sentence thesis, then short bullet points... no headings, no tables, no code fences."**
- The AAPL fact-sheet numbers and explicit source tags.
- The hard mandate caps: **"Single-name position-size cap: 3.0% of portfolio"**, **"LONG-ONLY"**, and the drawdown/risk definitions.