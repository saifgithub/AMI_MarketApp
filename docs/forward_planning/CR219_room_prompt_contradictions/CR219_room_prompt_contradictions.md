# CR219 — the personas describe a fact sheet that stopped existing on 2026-08-13

**Status:** in_progress · **Opened:** 2026-09-02 · **Tag:** `AT:R75 CR219`

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
| 1 | `fundamentals_analyst.md:29` | "never describe a margin as rising, falling, expanding or compressing" | `Margin trend, YoY (LIVE): …bps` |
| 2 | `fundamentals_analyst.md:66` | "There is still no margin *trend* on the sheet — quote the levels, never a direction" | same |
| 3 | `fundamentals_analyst.md:48` | "Buybacks and M&A history are **not available** — never claim a number for either" | `Buybacks (LIVE)` + `Capital returned (LIVE)` (CR218) |
| 4 | `fundamentals_analyst.md:58` | "no *history* for any of them: every figure is a single point in time" | 6 multi-period figures |
| 5 | `market_analyst.md:20` | "any claim that needs a *series* … is not one this data can support" | `Window trend`, `Primary trend`, `Relative strength 52w` |
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
| 15 | `overlay_generator.py:445` | On a **short or medium** horizon the Fundamentals overlay flips to *"Emphasise momentum in fundamentals (earnings revisions, surprise history), guidance."* **None of the three exists.** Neither `earnings revisions` nor `surprise history` is fetched anywhere in the backend; the only `guidance` on the sheet is the disclaimer *"the Street's view, never the company's own guidance."* CR146 deleted four such demands from the **market analyst** block for exactly this reason and left the fundamentals one standing. Live for every short- and medium-horizon user. |

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

Honest limits: **0 of 66** replies ever *stated* the trend was unavailable, and undenied Dividend also sits low (16.7%, n=18). This is suppression by omission — the structure-vs-trend pair is the strong datum, buybacks corroborates.

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
