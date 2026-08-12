# CR168 — Name the company in the prompt

**Status:** **dropped as a standalone item — folded into [CR166](../CR166_fact_sheet_supply_census/)**
(2026-08-12) · **Filed:** 2026-08-11 · **Category:** quality ·
**Parent:** [CR167](../CR167_tradingagents_upstream_drift/CR167_tradingagents_upstream_drift.md) §4.1

> **Disposition.** The Step 0 gate ran and returned **prophylactic** — 0 wrong-company instances in
> 216 real turns. What survives is a two-string-field render on the **same `yf.Ticker().info` dict,
> the same fetch and the same `_format_profile`** that CR166 is already building — which §Coordination
> below anticipated (*"whichever ships first should render both"*). Deciding the same DEF236 byte
> budget and the same lane assignment twice is the per-field rediscovery CR166 exists to stop, so the
> whole of this CR — every measurement, all three amendments, and the `NBIS` fixture — now lives in
> **CR166's row**, and nothing is carried only by a dropped item.
> **Reopen as standalone only if CR166 is itself dropped.**

> **Gate result — and a correction to this document.** 0 wrong-company instances in 216 real turns,
> so per the fork table below this is prophylactic and priced as a render line.
> **The "zero prompts name the company" figure in §Why is wrong**: it was measured on `assembled/`,
> a synthetic single-ticker reconstruction. In the 216 real production prompts a company name reaches
> the model in **72.2%** of turns (66.7% after Batch 9's news recency floor) — via news headlines, never
> as identity — and is **never** supplied for AMD, AVGO or KTOS. The real case for this CR is
> *reliability*, not absence. Full result: [GATE_RESULT_2026-08-12.md](GATE_RESULT_2026-08-12.md).

---

## Why

Every Room prompt identifies its subject by ticker alone. The company has no name in it.

Measured, not assumed — across all 38 assembled prompts in
[`CR143/assembled/`](../CR143_agent_prompt_audit/assembled/) (4 surfaces × the agent roster, all built
on AAPL):

```
$ cd docs/forward_planning/CR143_agent_prompt_audit/assembled && grep -ril "apple" .
(no matches)
```

What the fact sheet *does* carry is `Sector/industry (LIVE): Technology / Consumer Electronics`. So the
model is told the business classification and never the business. The subject is named exactly once, as
`Ticker: AAPL`, at line 90 of a 133-line prompt.

### Where the concern comes from

TradingAgents `d7b40a2` (their issue #814). They resolve company name, sector, industry and exchange
once per run and inject the block into every agent, closing with:

> Do not substitute a different company or ticker unless a tool result explicitly disproves this
> resolved identity.

Their stated failure mode, from `resolve_instrument_identity`'s own docstring:

> …without a ground-truth name, the market analyst would pattern-match the price action to a narrative
> and **invent an identity that then cascaded through every downstream agent**.

Verbatim template (values illustrative — see [`../CR167_.../upstream_diffs/agent_utils.diff`](../CR167_tradingagents_upstream_drift/upstream_diffs/agent_utils.diff)):

```
The instrument to analyze is `AAPL`. Use this exact ticker in every tool call, report, and
recommendation, preserving any exchange suffix (e.g. `.TO`, `.L`, `.HK`, `.T`, `-USD`).
Resolved identity: Company: <longName>; Business classification: <sector> / <industry>;
Exchange: <exchange>. Do not substitute a different company or ticker unless a tool result
explicitly disproves this resolved identity.
```

### The cost is near zero

`backend/app/services/fundamentals.py:163` already calls `yf.Ticker(ticker.upper()).info`, and `:306-311`
reads `sector`/`industry` off that same dict. `longName`, `shortName` and `exchange` are therefore
**already in memory** at that point. **Zero additional network calls.**

---

## The evidence gate — run this before building anything

**This CR may not survive it, and that is the intended outcome if so.**

Upstream's #814 came from a **tool-calling** graph. Our Room pre-fetches every datum and the model
never chooses a data source, so the specific cascade they describe has no obvious analogue here. Doing
this because upstream did it would be exactly the reasoning CR167 §5 warns against.

**Step 0 (required):** grep the committed CR143 corpus for wrong-company prose.

```bash
# 216 agent turns, prompt + reply, epoch 2026-08-07 12:00
docs/forward_planning/CR143_agent_prompt_audit/corpus/llm_audit_2026-08-07-epoch.json
```

Look for: a reply naming a company other than the run's ticker; a reply describing a business line the
ticker does not have; sector-narrative drift (an analyst arguing a semiconductor thesis on a retailer).
**One epoch only** — pooling across a prompt change makes every rate meaningless (that error is what
made an 18.4% figure in CR143's original filing wrong).

Then fork:

| Corpus result | What this CR becomes |
|---|---|
| ≥1 real instance | A defect, not a CR. Mint a DEF, cite the turn, fix with the identity block. |
| Zero instances | Prophylactic. Price it as such — a cheap render line, not a correctness fix, and it competes on that basis against everything else in the CR143 queue. |

---

## Scope

**In:**

1. `company_name` and `exchange` added to the profile the Room builds, sourced from the `.info` dict
   already fetched — no new call, no new provider.
2. Both rendered in `_format_profile` ([`room_prompts.py:863`](../../../backend/app/services/room_prompts.py))
   alongside the existing `_sector_line` (`:1310`), under CR104 `field_state` so an absent name degrades
   to the declared-unavailable form rather than vanishing.
3. The anti-substitution clause — one sentence, and it belongs with the GROUNDING DIRECTIVE at line 1
   rather than buried in the fact sheet, since it is a rule about the whole reply, not a datum.
4. `test_prompt_data_parity.py` (DEF098's guard) extended so the two new fields are either rendered on
   every surface the consuming agent reads, or listed in `INTENTIONALLY_OMITTED` with a reason.

**Out:**

- The other 112 numeric fields in that dict — **that is [CR166](../CR166_fact_sheet_supply_census/)**, filed the
  same day. See "Coordination" below.
- Resolving identity by network lookup at run start (upstream's `resolve_instrument_identity` with its
  `lru_cache` and yfinance call). We already have the dict; adding a second fetch path would be the
  extra call CR166 is explicitly avoiding.
- Any change to how the ticker itself is rendered or validated.

---

## Coordination — CR166 is the same fetch and the same renderer

[CR166](../CR166_fact_sheet_supply_census/) is a supply-side census: the single `yf.Ticker().info` call
returns 180 keys, we read 23, and **112 numeric fields are already in memory and never passed to any
agent.** CR166 is the *numeric* half of that supply; this CR is the *string* half. Same dict, same fetch,
same `_format_profile`.

They arrived by different routes — upstream's #814 versus a census — which is precisely the
per-field rediscovery CR166 was filed to stop. **Whichever ships first should render both.** If CR166
lands first, this collapses to "add two string fields and the clause to the block CR166 already built."

---

## Constraints

**DEF236 binds this.** Every prose agent already runs 61–100% over its length guide, and
`_AGENT_MAX_TOKENS` was sized *to that guide* (DEF125). Adding a block buys truncation.
**Subtract before you add, or re-derive the token budgets in the same commit.** This is CR143 Phase 5's
standing rule for every render change, not advice specific to this CR.

**Blast radius is all 12 prose agents**, so acceptance is a post-promotion re-measure, not a unit test.

**Prompt bytes change ⇒ the CR158 version stamp moves ⇒ the measurement epoch resets.** Land separately
from [CR169](../CR169_asof_date_at_prompt_head/), which changes the same file for an unrelated reason.

---

## Acceptance

1. The corpus grep of Step 0 is recorded in this folder with its result, whichever way it went.
2. `company_name` and `exchange` appear in the assembled prompt for all 12 Room agents;
   `dump_assembled_prompts.py --verify` proves the reconstruction still matches what Alpha sends.
3. An absent/unresolvable name renders the CR104 declared-unavailable form — verified against a ticker
   yfinance does not recognise, not a mocked `None`.
4. `test_prompt_data_parity.py` fails if either field is dropped from any surface that should carry it.
5. No new network call on the Room path — proven by the fetch count, not by inspection.
6. Token budgets re-derived or subtraction landed in the same commit (DEF236).
7. Post-promotion re-measure with `scripts/prompt_quality_sweep.py` on a fresh epoch, compared against
   2026-08-07 — and the comparison states plainly if nothing moved.
