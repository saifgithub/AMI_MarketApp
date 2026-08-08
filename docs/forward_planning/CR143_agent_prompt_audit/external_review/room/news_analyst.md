# External review — news_analyst

> Reviewer: `kimi-for-coding` · reasoning tokens 5486 · prompt 2817 tokens.
> **Hypotheses, not findings.** The reviewer cannot see our code; every claim needs a supplier check and a parser check before it becomes a defect.

## 1. JOB

Synthesize the news impact on AAPL from the provided headlines and data block, formatted as a one-sentence thesis followed by 2–3 short evidence bullets, and prefixed with a required `[STANCE: ... | CONVICTION: ... | HEADLINE: ...]` line.

## 2. CONTRADICTIONS

**A. Output length and structure contradict each other.**
- `"Like a Bloomberg wire report compressed to two paragraphs."`
- vs. `"Write 2–3 sentences."` and `"Format: lead with a one-sentence thesis, then short bullet points for supporting evidence."`

A Bloomberg wire report in two paragraphs is not the same as 2–3 sentences plus bullets.

**B. The agent is told not to predict direction, but the output format forces a directional stance.**
- `"You DO NOT — Predict whether a stock will go up or down based on news. That's a coordinated call."`
- vs. `"STANCE: your view on taking this position now — 'for', 'against', or 'neutral' if you genuinely land in the middle."`

`for`/`against` on "taking this position now" is a directional call on the stock, which the role explicitly forbids.

**C. Quantity guidance conflicts.**
- `"3 items max per response — quality over quantity"`
- vs. `"Write 2–3 sentences."` plus `"short bullet points for supporting evidence."`

One thesis plus two supporting bullets already exceeds three items, and the sentence cap makes "3 items max" either redundant or unachievable.

## 3. UNFOLLOWABLE

**A. Holdings relevance cannot be filtered because AAPL is not held.**
- `"Filter headlines to user's holdings + watchlist relevance."`

The simulated portfolio only lists `MSFT ×40` and `NVDA ×20`; it explicitly states `"You hold 0% of AAPL — no open position in it."` There is no AAPL holding or watchlist to filter against.

**B. Expected-vs-actual comparison is impossible.**
- `"State the expected vs actual (e.g., 'consensus was +2.1%, actual was +4.3% — beat')"`

The data block only provides a future earnings estimate: `"Next earnings (LIVE): 2026-10-29 (Q4) — in 82 days, consensus EPS est. $1.97643."` No actual reported results are provided.

**C. Second-order effects cannot be grounded.**
- `"Identify second-order effects (peers, suppliers, customers)"`

No peer, supplier, or customer list appears in the data block. The only related entities mentioned are OpenAI and Nvidia, but no explicit relationship to AAPL is supplied.

**D. Macro weighting has no macro signal to weight.**
- `"Weight macro structural news (Fed cycle, fiscal policy) higher than single events."`

The only macro item is a forward date: `"forward (REAL, Fed's published calendar): FOMC decision in 39 days."` No Fed path, CPI print, fiscal policy headline, or macro narrative is present.

**E. Specific numbers for the news stories do not exist.**
- `"Use specific numbers wherever possible — but ONLY numbers from the data block above."`

The provided headlines (`"Dan Ives Says We're in the '3rd Inning' of the AI Revolution..."`, `"OpenAI developing $300+ AI speaker..."`, `"What we know about OpenAI's upcoming handheld device..."`) contain no hard AAPL-related figures in the data block.

## 4. FAILURE MODES

1. **Stance conflict output.** A competent model will either emit `STANCE: for|against` and thereby violate `"Predict whether a stock will go up or down based on news. That's a coordinated call"`, or it will default to `neutral`/`none` and violate the explicit format instruction that requires picking a side. The safest-looking output is still a compliance failure on one side of the contradiction.

2. **Hallucinated AAPL-specific signal.** The only provided "recent catalyst" is a Motley Fool headline about Nvidia, and the other two are OpenAI product rumors. To satisfy `"Lead with the highest-signal item"` and `"State the expected vs actual,"` the model is likely to invent an AAPL earnings beat, iPhone shipment number, or regulatory event that never appeared in the prompt.

3. **Wrong length or format.** The model will either write two paragraphs of Bloomberg-style prose and violate `"Write 2–3 sentences"` / `"no headings"`, or it will emit exactly 2–3 sentences and drop the required bullet evidence or the mandatory stance line. The `HEADLINE: <max 32 characters>` constraint also frequently gets ignored or filled with a summary sentence rather than a single fact.

## 5. CUT

**Delete as noise:**

> `─── YOUR SIMULATED PORTFOLIO (AMI's portfolio of record — simulation-only) ───`
> `Cash: $42,150.00 | Portfolio value: $61,634.00`
> `Open positions:`
> `  MSFT ×40 (26.1% of portfolio, unrealised +796.00)`
> `  NVDA ×20 (5.5% of portfolio, unrealised +310.00)`
> `You hold 0% of AAPL — no open position in it. Any BUY here opens a NEW position.`

This portfolio snapshot belongs to the Portfolio Manager, not the News Analyst. It adds no news-relevant signal and invites the model to drift into holdings analysis.

> `Max acceptable drawdown: 30% — a PORTFOLIO-level cap on total drawdown, NOT a per-trade stop budget. A single position of size P% (of portfolio) with a stop S% below entry contributes only about P×S/100 percentage points to portfolio drawdown (e.g. 5% size, 20% stop → 1.0 pt, i.e. 1/30th of a 30% cap). Do not compare a stop's distance directly against this cap.`
> `Single-name position-size cap: 3.0% of portfolio in any one name — the SAME ceiling the Portfolio Manager clamps every trade to (CR101).`
> `Sector-concentration cap: 40.0% of portfolio in any one GICS sector — the SAME ceiling the safety floor blocks a proposed BUY against.`
> `Post-loss cooldown: 1.0h after a stop-out — enforced as a hard block on the next BUY, not a suggestion.`
> `Max open positions: 35 — a ceiling on distinct tickers held concurrently; adding to an existing holding doesn't count against it.`
> `Trading pace cap: 4 per day, 12 per week (UTC calendar day / Monday-start ISO week).`
> `Total open-risk cap: 10.5% — the sum of (position size % × stop distance %)/100 across all open positions, including this one.`

These are trading-execution constraints for the Portfolio Manager / Trader. The News Analyst has no position-sizing function; including them adds ~1,500 characters of irrelevant detail.

> `User mandate snapshot:`
> `- risk_score: 3 (1=most conservative, 5=most aggressive)`
> `- max_drawdown_pct: 30 — PORTFOLIO-level cap on total drawdown, NOT a per-trade stop budget. A position of size P% with a stop S% below entry contributes about P×S/100 percentage points to portfolio drawdown.`
> `- long_only: long-only = no short/negative positions. It does NOT forbid buying, adding to, or holding a name.`
> `- locale: en`

This is a near-verbatim repetition of the preceding user mandate. It should be cut or reduced to a single-line reminder.

> `"Like a Bloomberg wire report compressed to two paragraphs."`

This conflicts with the turn-level format (`Write 2–3 sentences`, `bullet points`). The Bloomberg voice can be preserved in tone, but the "two paragraphs" length target should go.

**Load-bearing and must stay:**

- The grounding directive (`"Use only the facts and numbers explicitly provided in this prompt..."`).
- The role boundary list (`"You DO NOT — Predict whether a stock will go up or down..."` etc.).
- The turn-level format instructions, including the exact stance-line template and `"Do not preface with 'As the X' or 'Speaking as'."`
- The data block with source tags, because the grounding rule depends on it.
- The instruction `"Stay strictly inside your OWN domain... give only your lens on the data."`