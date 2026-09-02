# CR219 — the personas describe a fact sheet that stopped existing on 2026-08-13

**Status:** in_progress · **Opened:** 2026-09-02 · **Tag:** `AT:R75 CR219`

> **For an external reviewer.** This CR is an investigation. **No code, prompt or persona has
> been changed** — it documents 17 findings and proposes a fix that has not been built.
>
> Everything rests on primary evidence in [`evidence/`](evidence/), which stores **84 complete
> LLM turns** — for each, the exact system prompt sent, the user message, the model's full
> reasoning trace and its answer. Start with [`evidence/README.md`](evidence/README.md); it
> lists what is here, how to regenerate it, and — under *"Two things the record does NOT
> support"* — the two places where the data is weaker than it might first appear.
>
> Three claims worth checking first, because the argument stands or falls on them:
> 1. `evidence/analysis/verify_citations.py` — every `file:line` this doc cites still points
>    at the text it claims (exit 0).
> 2. `evidence/analysis/citation_rates.py` — the suppression measurement, from the banked
>    corpus, independent of anything Gemini said.
> 3. `evidence/rendered/fundamentals_analyst.txt` — the assembled prompt with both halves of
>    the contradiction in one file. Search it for `never describe a margin` and for
>    `Margin trend, YoY (LIVE)`.
>
> The convene model is **Gemini 3.1 Pro**, not the incumbent. It was chosen because it emits a
> visible reasoning trace; the production model emits none, which is why these contradictions
> went unseen. Gemini's replies are used as *evidence of what the prompt does to a reader*,
> never as ground truth about CAT.

---

## Why this exists

An agent's prompt is assembled from two halves that nothing binds together:

| Half | Where | How it changes | How it is reviewed |
|---|---|---|---|
| The **persona** — role, `## Inputs`, output style, "You DO NOT" | `content/agents/*.md`, 13 hand-written files | rarely, by hand | by **reading** |
| The **fact sheet** — the numbers | `room_prompts.py::_format_profile`, generated per lane per field-state | every time a CR adds a field | by **tests** |

A CR that adds a field touches only the second, and its tests ask *"does this field render?"* — never *"does anything now contradict it?"* So the personas still describe the sheet as it was on **2026-08-13 at 08:50**, the last time CR166 aligned them.

At **16:43 that same day** CR179 shipped `margin_trend_line` and `buyback_line`; at **20:34** it shipped the window trend. Every persona denial about those fields became false that afternoon and has been false since. CR164 (08-19), CR160 (08-20) and CR218 (09-02) each edited those exact files afterwards without noticing.

**This is not a missed review.** CR143 audited all 38 assembled prompts on 2026-08-08 and was *correct*: `Margin trend` appears **0 times** in `assembled/room/fundamentals_analyst.txt`, and the buyback denial was echoed by the sheet's own `(buybacks/M&A: not available, not claimed)`. The two halves agreed. The audit is a snapshot; the sheet is a moving target; nothing regenerates the snapshot.

---

## What is wrong

### Class A — the persona denies a field the sheet marks LIVE

Found by rendering each agent's real sheet through `_format_profile` and diffing against its persona, then confirmed independently by a Gemini 3.1 Pro convene that was asked to report its own prompt's contradictions.

| # | Where | Claim | Contradicted by |
|---|---|---|---|
| 1 | `fundamentals_analyst.md:29-31` | "never describe a margin as rising, falling, expanding or compressing" | `Margin trend, YoY (LIVE): …bps` |
| 2 | `fundamentals_analyst.md:66` | "There is still no margin *trend* on the sheet — quote the levels, never a direction" | same |
| 3 | `fundamentals_analyst.md:48-49` | "Buybacks and M&A history are **not available** — never claim a number for either" | `Buybacks (LIVE)` + `Capital returned (LIVE)` (CR218) |
| 4 | `fundamentals_analyst.md:56-60` | "no *history* for any of them: every figure is a single point in time" | 6 multi-period figures |
| 5 | `market_analyst.md:19-22` | "any claim that needs a *series* … is not one this data can support" | `Window trend`, `Primary trend`, `Relative strength 52w` |
| 6 | `market_analyst.md:54` | "you do not have a series, so you cannot say an indicator is *clearing*, *rolling over*" | same |
| 7 | `news_analyst.md:25` | "You are **not supplied consensus estimates**" | `consensus EPS est. $X` on the same sheet line as the earnings date |
| 8 | `social_media_analyst.md:28` | "You have no historical baseline for this ticker" | `Mentions: … over 33d, trend: …` — weaker; it restricts *sentiment* elevation, the sheet gives a *mention* trend |

Three denials check out and must **stay**: no peer-basket P/E, no MACD/Bollinger, no Twitter/X.

**Every one of these is doubled.** The same persona feeds the 1-on-1 surface, and `fundamentals.build_live_data_block()` carries `Margin trend, YoY`, `Buybacks`, `Capital returned`, `Window trend`, `Primary trend`, `Relative strength`. 7 false denials × 2 surfaces = **14 live instances**. Two further surfaces (concierge, Brief Your Agent) are **not yet swept**.

### Class B — instruction fights instruction

Not availability claims, so a persona-text scan cannot see them. Every one was reported by the model itself, quoting both sides.

| # | Agent | The collision |
|---|---|---|
| 9 | Technical | mandate overlay says *"Emphasise monthly/quarterly trend"*; persona says no series claim is supportable. It obeyed the persona and called the 64-day window a *"proxy"*. |
| 10 | Bull | *"End with your CONVICTION"* vs *"Write this line ONCE, at the top only. Do not repeat it at the end."* |
| 11 | Bull | *"if you pair it with a date, the date is yours and you must say so"* vs *"Do not speculate beyond the data the Analysts provided."* |
| 12 | Trader | `Side: WAIT` vs *"You DO NOT… skip the stop-loss."* Emitted `Stop: N/A (0% position size)`. |
| 13 | Aggressive RO | *"Push for full mandate-allowed sizing"* (3.0% cap) vs *"use the drawdown figure as written — do not recompute it"* — that figure was computed for **2.5%**. Advocated 3.0% while quoting the 2.5% cost. |
| 14 | Balanced RO | Told to propose a specific size **and** stop, forbidden from multiplying them. Proposed 2.0% × 5.0% and refused to compute the result. |

**#12 overlaps live work.** An uncommitted `trader_block_regex` hunk in `room_prompts.py` fixes exactly this for the **Size** field on HOLD/WAIT. The **Stop** field has the identical defect and is not covered.

**#13 and #14 are CR179 Leg 4 inverted** — the rule is *"hand over the derived figure rather than the two operands and an instruction."* These hand over the operands and forbid the arithmetic.

### Class C — the overlay demands data no tool supplies (DEF063 shape)

| # | Where | Problem |
|---|---|---|
| 15 | `overlay_generator.py:447` | On a **short or medium** horizon the Fundamentals overlay flips to *"Emphasise momentum in fundamentals (earnings revisions, surprise history), guidance."* **None of the three exists.** Neither `earnings revisions` nor `surprise history` is fetched anywhere in the backend; the only `guidance` on the sheet is the disclaimer *"the Street's view, never the company's own guidance."* CR146 deleted four such demands from the **market analyst** block for exactly this reason and left the fundamentals one standing. Live for every short- and medium-horizon user. |

### Class D — the sheet reaches agents whose brief never mentions it

All 8 downstream agents (Bull, Bear, Research Manager, Trader, 3 Risk Officers, CIO) receive the **full 50-line, 5,746-char sheet** — `_AGENT_LANES` restricts only the four analysts — and not one of their `## Inputs` sections mentions a fact sheet, a price, or any numeric field. They are briefed to argue from the analysts' prose while holding the primary numbers.

### Class E — a lane gap on the 1-on-1 surface only

`build_live_data_block()` hands the Fundamentals Analyst `Day move`, `Primary trend`, `Beta`, `Short interest` and `Relative strength vs S&P` while its persona says *"You DO NOT predict short-term price movements. That's the Technical Strategist."* On the Room surface `_AGENT_LANES` gates those away; on 1-on-1 nothing does.

---

## Why no guard caught it

`backend/tests/unit/test_cr105_analyst_inputs_field_state_guard.py` binds **45 positive claims** to real `field_state` keys, in both directions, and is a good guard. Its blind spots:

1. **Negative claims are checked for *presence*, never for *truth*.** There are 2, and both merely must still appear verbatim.
2. **`_inputs_section()` scans `## Inputs` → `## Output` only.** Findings 2, 6, 7 and 8 all live in `## Output style` or `## Voice`, outside the window entirely.
3. Its own comment, written at 08:50 on 2026-08-13 — *"Note what did NOT change: no margin trend is available, the .md still says so"* — was false by 16:43 that day, and reads as verified.

The guard covers *"claims data it does not have."* Nothing covers *"denies data it does have."*

---

## What it costs

**Measured** on the banked `llm_audit` corpus — 66 real Fundamentals turns whose sheet carried a LIVE margin trend. Cleanest available comparison: two adjacent margin lines on the identical sheets, one denied and one not.

| LIVE line | named in reply | persona |
|---|---|---|
| Margin **structure** | **95.5%** | — |
| FCF | 68.2% | — |
| ROE / ROA | 45.5% | — |
| Margin **TREND** | **24.2%** | denies it exists |
| Buybacks | 13.3% (4/30) | denies it exists |

Honest limits: only **1 of 66** replies ever *stated* the trend was unavailable, and undenied Dividend also sits low (16.7%, n=18). This is suppression by omission, not refusal — the structure-vs-trend pair is the strong datum, buybacks corroborates. Reproduce with `evidence/analysis/citation_rates.py`, which is the artifact of record for these numbers.

**The mechanism, caught directly.** In the Gemini convene the Fundamentals Analyst's *thinking* reads *"margins are up significantly YoY — gross 30% (+327bps), operating +365bps, net +434bps"*; its *answer* cites the numbers but states it *"strictly avoided the forbidden active verbs (rising, falling, expanding, compressing)."* It reasoned with the trend and sanitised it out of the output.

**And the agent believes we did it on purpose.** Asked what data it lacked, the Fundamentals Analyst tagged multi-year FCF history as:

> **(c) WITHHELD** (the prompt explicitly stated: *"no history for any of them: every figure is a single point in time"*)

It classified a real data need as deliberately withheld by us, on the strength of a sentence that is false, and stopped asking.

---

## Data the Room says it needs (same convene)

Ranked by how many agents independently asked, unprompted:

| Gap | Asked by | Impact |
|---|---|---|
| **Historical median multiples** (5/10-yr P/E, EV/EBITDA) | Bull, Bear, RM, Trader, **CIO** — 5/12 | **Flipped the verdict.** PM returned **PASS** citing *"24.5x EV/EBITDA"*; its own gap report says *"if I had proof that 24.5x was a normal mid-cycle baseline rather than an extreme cyclical peak, I might have approved."* |
| **Debt split: industrial vs. captive finance** | all 3 Risk Officers + CIO — 4/12 | The Room built an insolvency narrative on CAT's $39.2B "net debt", which is largely matched-book customer leasing. |
| **Segment revenue breakdown** | Bull, Bear, RM, News — 4/12 | Nobody could adjudicate whether a Deere/AGCO agricultural read-through applies to CAT at all. |
| **Multi-year FCF / capex** | Fundamentals, Aggressive | Tagged WITHHELD — see above. |
| **Higher-timeframe indicators** | Technical | Mandate horizon is **3–10 years**; we supply daily bars only. A design gap, not stale prose. |

---

## Method

1. `evidence/dump_sheets.py` — renders the real per-agent sheet through `_format_profile`, reusing `test_prompt_data_parity`'s sentinel injection so it comes out of the production renderers.
2. `evidence/assemble_room.py` — assembles all 12 **complete** Room prompts at HEAD (persona + overlay + sheet + tail), then mechanically extracts every availability claim. The persona file is only 10–18% of the prompt; a contradiction exists only in the concatenation.
3. `evidence/convene_gemini.py` — runs a full 12-agent sequential convene against a thinking model, production prompts byte-identical, with an addendum on the **user** message only asking each agent (a) what data it lacked and (b) where its own prompt contradicted itself, quoting both sides.
4. Corpus counting over `CR143_agent_prompt_audit/corpus/llm_audit_2026-08-14*.json` for the citation rates.

**Why a thinking model was necessary.** The incumbent emits zero reasoning tokens. It has been resolving these contradictions silently, one way or another, on every convene. GLM-5.3 surfaced the margin conflict by accident inside its reasoning during CR217; this CR asks for it deliberately.

---

## Scope

1. Correct the **8 Class-A denials** in the four analyst personas; keep the 3 that are true.
2. Resolve the **6 Class-B collisions** — for #13/#14, apply Leg 4 properly and precompute the drawdown contribution rather than forbidding the multiplication.
3. Delete or back the **Class-C** short/medium-horizon demand (#15).
4. Decide Class D — whether the 8 downstream briefs should name the sheet. Changes what 8 agents argue from, so it wants its own before/after measurement.
5. Close the guard gap: every **negative** claim must be checked TRUE against the rendered sheet, scanning the whole persona rather than `## Inputs` alone.
6. Sweep the two unswept surfaces (concierge, Brief Your Agent).

**Structural over prose, per CR038** — agents ignore even emphatic instructions ~70% of the time, so a correction that is only better wording is worth less than a check that fails the build.

---

## Acceptance

1. Every negative claim in every `content/agents/*.md` resolves against the rendered sheet; the guard fails red when a field is added that contradicts one, demonstrated with a deliberate fixture.
2. The guard scans the whole file, not `## Inputs` alone — proven by a fixture placing a false denial in `## Voice`.
3. `pytest backend/tests/unit/ -q` green, including `test_cr105_*`, `test_prompt_data_parity.py`, `test_config_compose_parity.py`.
4. Re-run the corpus citation count on post-fix Alpha traffic; margin-trend and buyback citation rates move toward their undenied neighbours. The banked corpus is the before-arm and already exists.
5. `evidence/` regenerates from the committed scripts.

---

## Evidence

| Path | What |
|---|---|
| `evidence/convene_CAT_long_wealth/` | The 12-agent Gemini convene: per-agent thinking, answers, and `convene.json` carrying every prompt sent |
| `evidence/arms/` | Mandate-variation arms (horizon short/medium/long/very_long; goal income_now/learning_to_trade) against one cached profile |
| `evidence/profile_CAT.json` | The single CAT profile every arm shares, so a verdict difference is attributable to the mandate and nothing else |
| `evidence/*.py` | The four scripts above, version-controlled so the finding is reproducible |

---

## Open

- Concierge and Brief Your Agent surfaces unswept — 26 of the 38 prompts.
- `primary_goal` is rendered (`overlay_generator.py:93`) but **nothing branches on it** — only `horizon` does. Collected at onboarding, printed, never acted on. Confirm against the variation arms before filing.
- The PM broke its JSON-only contract to answer an appended instruction. That addendum was ours, so it is not a production defect — but given DEF067 lost ~13% of verdicts to parser fragility, an agent that writes outside the JSON contract on request is worth its own look.

---

## Mandate-variation arms (2026-09-02)

Six 12-agent convenes, all against **one cached CAT profile** so the mandate is the only
variable. 72 turns, 0 errors. `evidence/arms/`.

| arm | horizon | goal | PM verdict |
|---|---|---|---|
| `h_short` | short | long_term_wealth | APPROVE 2.0% |
| `h_medium` | medium | long_term_wealth | PASS |
| `h_long` | long | long_term_wealth | APPROVE 2.0% |
| `h_very_long` | very_long | long_term_wealth | PASS |
| `g_income_now` | long | income_now | PASS |
| `g_learning` | long | learning_to_trade | PASS |

**The verdict column is not interpretable.** `pm_self_consistency_samples` defaults to **1**
and the measured flip rate at n=1 is ~19.7% (`risk_officer.py`), so a single draw is close to
a coin toss — and the result is non-monotonic in horizon (short and long approve, medium and
very_long pass), which a real horizon effect would not be. Nothing here attributes a verdict
to a mandate. The prompt-level findings below are about the prompt, not a sampled decision,
and are robust.

### Findings the arms added

**#15 confirmed live.** Both short and medium arms received
`- Emphasise momentum in fundamentals (earnings revisions, surprise history), guidance.`
and in both, the Fundamentals Analyst's first data-gap entries are exactly those three,
tagged ABSENT. `h_medium` states the cost outright:

> *"I would have increased my conviction level if I could verify that fundamental momentum
> was supported by a history of beats and upward revisions, **as requested by the user
> mandate**."*

The overlay lowers conviction by asking for data no tool supplies.

**#16 — new.** The same overlay demands `guidance` while the sheet disclaims it
(*"the Street's view, never the company's own guidance"*). `h_short`'s report:
*"ABSENT (and partially FORBIDDEN by the mandate to focus on Street consensus over company
guidance, though guidance is standard fundamental data)."*

**#17 — new.** `primary_goal` is rendered at `overlay_generator.py:93` and **nothing branches
on it.** Only `horizon` does (`:437`). Six goal values are collected at onboarding, printed
into every prompt, and never change a single instruction. The two goal arms differ from the
`long` baseline in no prompt text but the one printed line.

**Contradictions are Room-wide, not analyst-only.** 11 of 12 agents reported at least one in
at least 3 of 6 arms; the Fundamentals Analyst in **6/6**.

The Portfolio Manager is the twelfth and is **excluded**: its prompt requires the entire reply
to be one JSON object, this harness's addendum asks for two appended sections, and that
collision is ours rather than production's. Excluding it drops the PM from 6/6 arms to 1/6 —
counting it would have inflated the headline by a whole agent. `aggregate_arms.py` does the
exclusion in code, not by hand.

### What the Room says it needs — 102 requests over 72 turns

| Requested | × | agents |
|---|---|---|
| **Debt: maturity schedule / fixed-vs-floating / interest coverage** | **21** | **9 of 12** |
| Historical valuation multiples (5–10y median P/E, EV/EBITDA) | 11 | 6 |
| Capex / cash-flow statement detail | 9 | 4 |
| Order book / institutional & options flow | 8 | 3 |
| Price series, higher timeframe, MACD / volume-at-price | 7 | market analyst |
| News depth / catalyst detail | 6 | news analyst |
| Segment / geographic revenue split | 5 | 3 |
| Earnings revisions / surprise history / guidance | 4 | fundamentals (driven by #15) |
| Raw social split / buzz / mention counts | 4 | social |
| **Volatility for stop sizing (ATR, gap risk)** | 4 | trader + both cautious ROs |
| Macro series (CPI, PPI, PMI, Fed path) | 4 | 3 |
| Dividend & buyback sustainability / pacing | 4 | 4 |
| Peer / sector comparables | 2 | 2 |

16 of the 102 resist clustering and are left unbucketed rather than forced; the ranking is
stable without them. Regenerate the whole table with `evidence/analysis/aggregate_arms.py`.

The ATR row is worth its own line: the Execution Desk is required to set a stop on every BUY
and is given **no volatility measure of any kind** to set it from. Both cautious Risk Officers
independently asked for overnight gap-down statistics around FOMC for the same reason.

### The free ones

`_fetch_statement_facts_uncached` already pulls **`quarterly_income_stmt` and
`quarterly_cashflow`** behind a 6h TTL and reads only three rows from them
(`Operating Income`, `Repurchase Of Capital Stock`, `Cash Dividends Paid`). Therefore, at
**zero additional network cost**, from bytes already in memory:

- **Interest coverage** = operating income ÷ interest expense — the #1 request, 21× from 9 of
  12 agents, and the Room built an insolvency narrative on CAT's debt without it.
- **Capex** — already implicit in the FCF we render, then discarded.
- **Buyback pacing** — the four-quarter series is already fetched, summed to TTM, and thrown away.

This is exactly CR218's pattern and should be its own CR.
