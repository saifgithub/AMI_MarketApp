# CR167 — TradingAgents upstream drift review

**Status:** done · **Filed:** 2026-08-11 · **Category:** quality · **Scope:** docs only, no behaviour change

Saiful, 2026-08-11: *"we owe our DNA to the trading agent repo on github. lets have a look if they have
made any changes specially to the agent prompts."* And, on what to do with the answer: *"memo, file, no
build. I want to be able to study the differences."*

---

## 1. The two copies, and how to diff them

| Path | What it is | Rule |
|---|---|---|
| `/Volumes/Extreme Pro/TradingAgent/` | **The fork basis.** Frozen at `7e9e7b8` (2026-05-01). | Never fetch, never pull. This is the "where we came from" record. |
| `/Volumes/Extreme Pro/TradingAgent_upstream/` | **Tracks upstream `main`.** At `a33fd4c` (2026-07-18) when this was written. | `git -C "/Volumes/Extreme Pro/TradingAgent_upstream" pull --ff-only` |

Saiful's call, 2026-08-11: *"keep our snapshot as a basis of where we fork from. if needed, can we make
a second copy that will track the head?"*

`7e9e7b8` is an ancestor of upstream `main`, so the tracking clone produces every fork-basis→HEAD diff on
its own and the frozen copy is never touched:

```bash
UP="/Volumes/Extreme Pro/TradingAgent_upstream"
git -C "$UP" rev-list --count 7e9e7b8..HEAD                    # 106
git -C "$UP" diff 7e9e7b8 HEAD -- tradingagents/agents/        # the prompt layer
git -C "$UP" log --reverse --format='%h %s' 7e9e7b8..HEAD -- tradingagents/agents/   # the 21
```

**106 commits**, two releases (v0.3.0, v0.3.1), of which **21 touch `tradingagents/agents/`**. That count
is measured by the command above, not estimated.

The diffs are committed under [`upstream_diffs/`](upstream_diffs/) so this reads without either mount:
one file per agent or agent group, plus [`_commits.md`](upstream_diffs/_commits.md) — all 106 commits,
oldest first, with the 21 agent-touching ones starred.

---

## 2. We are not downstream of their code

[`backend/pyproject.toml:39`](../../../backend/pyproject.toml) has the install commented out:

```toml
# TradingAgents — installed from local mount for dev; published version in prod
# "tradingagents @ file:///Volumes/Extreme Pro/TradingAgent",
```

Our prompts are ours: 13 source files in `content/agents/*.md`, assembled through the 1,459-line
`backend/app/services/room_prompts.py`. CR143 Phase 1 measured the source file at **10–18%** of the
prompt the model actually receives; the rest is the fact sheet, the mandate overlay, the Brief overlay
and the safety floor.

So nothing here is a merge. What we inherited is the **graph shape** — four analysts → bull/bear →
research manager → trader → three risk debators → PM — which CR160 already records as
Apache-2.0 and not defensible IP. What is worth reading upstream for is **what they learned about
running that graph**, and on two counts they learned the same lessons we did, independently.

---

## 3. They hit two of our own failure classes

### 3.1 A prompt demanding data no tool could supply → the model invented it

Their `sentiment_analyst.py` header, verbatim, `0fcf136`:

> Previously named `social_media_analyst`. Renamed and redesigned because the old version had a prompt
> that demanded social-media analysis but the only tool available was Yahoo Finance news — which led
> LLMs to **fabricate Reddit/X/StockTwits content under prompt pressure (verified live)**.

That is DEF063 / CR024. Our Social Media Analyst invented sentiment off `crc32(ticker)` scaffolding from
the moment CR024 shipped until the Adanos keys were forwarded (2026-07-21), for the same structural
reason: the prompt promised a data source the runtime could not deliver, and the model closed the gap.

**Their fix is the shape we already run.** Pre-fetch all three feeds — Yahoo news, StockTwits by
cashtag, Reddit — and inject them as blocks before turn 0. Their own note: *"The agent does not use
tool-calling; the data is in the prompt from turn 0."* Our Room has always worked that way.

Two details of theirs we do not have:

- **Structured output on the sentiment header** (`e80636f`) — band + score + confidence come back schema-
  constrained, *"deterministic across runs and providers instead of free-form per-model prose."*
- **`7aef10a`** then tightened the narrative field's own description because the structured version came
  back thin. Worth noting as the second-order cost of constraining a field: you get consistency and lose
  substance unless you pay it back in the field description.

### 3.2 A prompt instruction shipped without the mechanism behind it

`47cbb32` (2026-05-31) added `get_verified_market_snapshot` and this clause to the market analyst:

> Before writing the final report, call `get_verified_market_snapshot` for this ticker and the current
> date, and treat it as the source of truth for any exact OHLCV, price-level, or indicator-value claim.
> If another tool's output conflicts with the verified snapshot, flag the discrepancy rather than
> inventing a reconciled number.

`4e7821d` (2026-06-14) — **fourteen days later** — registered the tool in the ToolNode. Their commit
message:

> …the tool was missing from the market ToolNode executor — so the call failed and the model reported
> it "unavailable" and skipped verification.

The instruction was live, the tool was unreachable, and the failure mode was the model quietly writing
the report without verification. That is [`failure_patterns.md`](../../initial_specs/08_tech/failure_patterns.md)
P1 — our DEF038, DEF063, DEF082, DEF084 — occurring in the project we forked from, on the very feature
whose purpose was to stop fabrication. Their fix shipped with a regression guard
(`tests/test_market_toolnode.py`) asserting the executor registers what the prompt requires, which is
the same move as our `test_config_compose_parity.py`.

**No action for us beyond one line in `failure_patterns.md`.** It is external corroboration that the
class is structural, not an AMI-specific sloppiness.

---

## 4. Two things they have that we do not

### 4.1 Resolved instrument identity — `d7b40a2` (their #814)

Resolved once per run and injected into **every** agent's prompt. Rendered from
`build_instrument_context()` in [`upstream_diffs/agent_utils.diff`](upstream_diffs/agent_utils.diff) —
the template text below is verbatim, the *values* are illustrative (not a captured run):

```
The instrument to analyze is `AAPL`. Use this exact ticker in every tool call, report, and
recommendation, preserving any exchange suffix (e.g. `.TO`, `.L`, `.HK`, `.T`, `-USD`).
Resolved identity: Company: <longName>; Business classification: <sector> / <industry>;
Exchange: <exchange>. Do not substitute a different company or ticker unless a tool result
explicitly disproves this resolved identity.
```

The four fields come from a cached `yf.Ticker(...).info` lookup that fails open — *"if yfinance is
unavailable, rate-limited, or doesn't recognise the ticker, we return `{}` and the caller falls back to
ticker-only context rather than failing before analysis starts."*

Their stated failure mode, from the docstring of `resolve_instrument_identity`:

> …without a ground-truth name, the market analyst would pattern-match the price action to a narrative
> and **invent an identity that then cascaded through every downstream agent**.

**Where we stand — measured, not assumed.** Grepping all 38 assembled prompts in
[`CR143/assembled/`](../CR143_agent_prompt_audit/assembled/) (4 surfaces × the agent roster) for the
string `Apple`:

```
$ grep -ril "apple" .
(no matches)
```

The company name appears in **zero** of them. What we *do* render is
`Sector/industry (LIVE): Technology / Consumer Electronics` — so we have 2 of their 4 identity fields.
Missing: **the name, the exchange, and the anti-substitution clause.** Our prompts identify the subject
by ticker alone, at line 90 of a 133-line prompt.

Filed as **CR168**, `proposed`, with an evidence gate — see §7.

**Adjacent, filed the same day by another track: [CR166](../_registry/CR166.row.md)** — a supply-side
census finding that the single `yf.Ticker().info` call we already make returns 180 keys, we read 23, and
**112 numeric fields are already in memory and never passed to any agent.** CR166 is the *numeric* half
of that supply; the identity fields here are the *string* half of **the same dict** — verified, not
assumed: `backend/app/services/fundamentals.py:163` calls `yf.Ticker(ticker.upper()).info` and `:306-311`
reads `sector`/`industry` off it, so `longName` and `exchange` are already in memory at that point.
**Zero additional calls**, same constraint CR166 works under. They arrive by different routes (their #814
vs. a census) but land on one fetch and one renderer, so whichever ships first should render both.

### 4.2 The as-of date at the top of the prompt — `2b2d685`

They moved `current_date` from after the system message to before it. Their reason:

> weaker models anchored to their training cutoff when generating tool-call date ranges

Before → after, on all four analysts:

```
- "\n{system_message}For your reference, the current date is {current_date}. {instrument_context}"
+ " Today's date is {current_date}; treat it as 'now' for all analysis and tool-call date ranges.
   {instrument_context}\n{system_message}"
```

**Where we stand.** In `assembled/room/market_analyst.txt` (133 lines):

| Line | Content |
|---|---|
| 1 | `─── GROUNDING DIRECTIVE (applies to every response) ───` |
| 90 | `Ticker: AAPL` |
| 91 | `Fact sheet as of 2026-08-08 (UTC) — every other date in this sheet is anchored to this one; do not estimate how far away a date is from your own sense of the current date.` |

The date sits at **68% depth**. The clause after it is already fighting the exact failure they describe —
*"do not estimate how far away a date is from your own sense of the current date"* — which says we found
the same problem and answered it with words rather than position.

Their specific trigger (tool-call date ranges) does not apply to us: our Room pre-fetches, it does not
tool-call. But date-derived claims do reach the user — `Next earnings (LIVE): 2026-10-29 (Q4) — in 82
days` is in the fact sheet, and prose like *"$608.23 by 2026-11-03 (88 days)"* appeared in the CR143
corpus. And we serve a 35B MoE on-prem, which is squarely the "weaker model" their fix is aimed at.

Filed as **CR169**, `proposed` — see §7.

---

## 5. Where we are ahead, and why it should stay that way

**Their number-grounding is a tool the model may elect to call. Ours is a fact sheet it cannot avoid
reading.**

`47cbb32`'s design asks the model to call `get_verified_market_snapshot` and trust the result. Ours
computes the same class of figures deterministically and renders them into the prompt under a GROUNDING
DIRECTIVE that is line 1 of every assembled prompt:

> Use only the facts and numbers explicitly provided in this prompt. Do not assume, infer, invent, or
> recall any datum you were not given […] If a fact you need is absent, say it is unavailable or omit
> the claim; never fill the gap with an assumption.

**Their own `4e7821d` is the argument against the tool form.** A tool can be unregistered, rate-limited,
or simply not called, and the failure is silent — theirs was, for fourteen days. A prompt block cannot
not-be-read. This is CLAUDE.md's *"prompt instructions are not controls; if it must hold, make it
structural"* applied one level up: **data the model must not invent belongs in the context, not behind a
tool call.**

**We should not adopt `get_verified_market_snapshot`.** Recorded here so a later session does not
re-open it as an obvious win.

The related idea — sweep the reply for numerals absent from the prompt — was separately rejected in
[CR143 §4](../CR143_agent_prompt_audit/PHASE5_feasibility_verdict.md) on measurement: 92.6% grounded,
3.1% inherited, **4.3% novel**, and every novel figure was hand-read and found legitimate (arithmetic on
a grounded target; explicitly hypothetical scenarios). On the measured epoch that guard fires at a
false-positive rate near 100%. It stays a measurement instrument (`scripts/prompt_quality_sweep.py`),
never a per-turn guard.

---

## 6. The rest of the drift, by theme

### 6.1 Structured output — a reference implementation *and* its two traps

They now run schema-constrained output for the Sentiment Analyst, Research Manager, Trader and Portfolio
Manager. The machinery is `agents/schemas.py` + `agents/utils/structured.py` — `bind_structured()`,
`invoke_structured_or_freetext()`, with a free-text fallback for providers that lack native support. See
[`upstream_diffs/schemas_structured.diff`](upstream_diffs/schemas_structured.diff).

This is exactly [CR143 §8](../CR143_agent_prompt_audit/PHASE5_feasibility_verdict.md)'s *"PM structured
output — FEASIBLE, proven live"*. Three of their follow-up fixes are free lessons for that build:

| SHA | Lesson |
|---|---|
| **`517eeaf`** | **Both halves apply to us directly.** (a) *"Local servers (LM Studio, vLLM) reject the object-form `tool_choice` langchain sends for function calling"* — bind the schema as a tool without forcing `tool_choice`. (b) *"A structured call can return no parsed result (a thinking model answering in plain text)"* — they now raise on `result is None` and fall back with a stated reason rather than an opaque render error. **We serve a thinking-capable Qwen3.6 MoE on vLLM.** |
| `0405168` | Coerce null-ish strings (`"none"`, `"n/a"`, `"nan"`, `"null"`) in optional float fields — models emit them as strings and the schema rejects the whole object. |
| `030b434` | Don't prime tool calls in schema-only structured agents. |

Scope note on `517eeaf`(a): CR143 §8's live probe against `192.168.20.74:8000` used
`response_format: {"type":"json_schema"}` and returned schema-conformant JSON first call. That is the
**constrained-decoding** path and it is fine. `517eeaf` is about the **tool-calling** path. If the PM
build goes via `response_format`, (a) does not bite; (b) still does.

### 6.2 Look-ahead hygiene — three traps CR164 will hit

| SHA | What broke |
|---|---|
| `3570f2e` | Alpha Vantage fundamentals were served without a look-ahead filter. |
| `0c1231a` | Future-dated and undated news leaked into historical windows. |
| `40774ca` | The Yahoo news window was neither UTC nor end-exclusive. |

CR164 (Room backtesting harness, as-of mode) walks into all three. Noted there.

### 6.3 i18n scope widened — `6b384f7`, and the docstring change in `agent_utils.py`

`get_language_instruction()` used to be applied to analysts and the PM only; internal debate agents
stayed English *"for reasoning quality"*. It now applies to every agent whose output reaches the saved
report — researchers, debators, research manager, trader — because:

> a non-English run produces a fully localized report rather than a mix of languages

Relevant to AR + MS at v1.0. Their earlier reasoning-quality argument for keeping debate English is the
tradeoff we will have to make explicitly rather than inherit. Noted on CR160.

### 6.4 Never invent a price — `1ff3f07`, `9fd54f8`

`1ff3f07`: an unrecognised symbol (`XAUUSD+`) could produce an invented price instead of an error. Fixed
by an alias table plus *"a clear 'data unavailable' result the agent reports verbatim, instead of a value
the model fills in."* `9fd54f8` rejects stale yfinance OHLCV rather than reporting wrong prices.

Same principle we already enforce — CR104 `field_state`, the LIVE/unavailable labelling in the fact
sheet, and the market analyst's own *"When live data isn't available for a ticker, say so rather than
inventing a specific number."* No gap found. Recorded as convergent, not actionable.

### 6.5 Crypto / non-US assets — `e7ec980`, `c93b92c`, `a102afa`

Analysis-only crypto mode, China A-share benchmarks, `asset_type` threaded through the graph so bull/bear
prompts say "asset" not "stock" and label fundamentals *"may be unavailable for crypto"*. Not our market
at MVP (US equities; GCC/Tadawul + Bursa later), but the mechanism — one `asset_type` on the state
driving per-agent label swaps — is the shape to copy when Tadawul lands.

### 6.6 Providers and data vendors — no action

Generic OpenAI-compatible endpoint for vLLM/LM Studio (`20d3b07`); Kimi, Groq, Mistral, NVIDIA NIM
(`295e84c`); Bedrock (`895ed13`, `43bd32b`); FRED macro (`ddfb840`); Polymarket (`db05903`). We already
run on-prem vLLM and already call Kimi for external prompt review. Noted, nothing to do.

### 6.7 Memory → decision log — `ebd2e12`, `8e7654f`

Per-agent BM25 memory replaced by a persistent append-only decision log. The prompt-hygiene half is worth
naming: `8e7654f` *"drop past-memory directive and placeholder from agent prompts when memory is empty"* —
they had been telling the model to weigh past lessons and then handing it an empty block. Same class as
DEF236 (instructions the runtime cannot satisfy). Our Decision Journal path should be checked against this
if it ever renders an empty section with a live directive above it — not checked here, out of scope.

---

## 7. What this filed

| ID | Item | Status |
|---|---|---|
| **CR167** | This review — tracking clone, memo, diff corpus | done |
| **CR168** | Resolved instrument identity in the Room fact sheet: company name + exchange + anti-substitution clause | proposed |
| **CR169** | Move the as-of date to the head of every assembled prompt | proposed |

**Both CR168 and CR169 carry an evidence gate before any build.** Neither is justified by upstream having
done it — upstream runs a tool-calling graph we do not.

- **CR168** — grep the committed CR143 corpus (`corpus/llm_audit_2026-08-07-epoch.json`, 216 turns) for
  wrong-company prose. If there is no instance, the change is prophylactic and should be priced as such.
- **CR169** — re-measure with `scripts/prompt_quality_sweep.py` against the frozen epoch.

Both are render-order changes across all 12 prose agents, so both inherit CR143's DEF236 constraint:
**subtract before you add, or re-derive `_AGENT_MAX_TOKENS` in the same commit.** Adding a block to a
prompt already 61–100% over its length guide buys truncation.

Cross-references appended (one line each, no rewrites): CR143 README, CR160, CR164,
`failure_patterns.md` P1, CLAUDE.md external-dependencies table.

---

## 8. Repeat cadence

Re-run at each upstream **release tag**, not on a schedule — 106 commits in 11 weeks is roughly one
review per release:

```bash
git -C "/Volumes/Extreme Pro/TradingAgent_upstream" pull --ff-only
git -C "/Volumes/Extreme Pro/TradingAgent_upstream" diff a33fd4c HEAD -- tradingagents/agents/
```

Update `a33fd4c` to whatever this review last read. The frozen mount at
`/Volumes/Extreme Pro/TradingAgent/` stays at `7e9e7b8` permanently — it answers "what did we fork
from", and that answer must not move.
