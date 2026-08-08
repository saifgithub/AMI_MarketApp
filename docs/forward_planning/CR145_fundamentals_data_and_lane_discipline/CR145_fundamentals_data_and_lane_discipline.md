# CR145 — Give the analysts the data they're asked for, and only the data that's theirs

**Filed:** 2026-08-08 · **Status:** proposed · **Decision:** Saiful, 2026-08-08 — *"just file them all as one CR."*
**Source:** CR143 Phase 1/3b + two independent reviews of the Fundamentals Analyst — a blind
prompt-coherence audit ([`external_review/room/fundamentals_analyst.md`](../CR143_agent_prompt_audit/external_review/room/fundamentals_analyst.md))
and a codebase-verified data-sufficiency audit ([`external_review/room/kimi/fundamentals_analyst_data_sufficiency.md`](../CR143_agent_prompt_audit/external_review/room/kimi/fundamentals_analyst_data_sufficiency.md)).

## Why

Two problems, opposite directions, same root: **the fact sheet is one shared block and nobody owns
what any given agent sees.**

1. **Agents are asked for analysis the data can't support.** The role guidance says *"Prioritise
   durable margins, FCF consistency, balance sheet strength, capital allocation"* while the prompt
   states full financial statements and buyback history are unavailable. The output-style example —
   *"32.4% gross margins, up 180bps YoY"* — models a number the system cannot supply, inside a prompt
   whose grounding directive forbids exactly that.
2. **Agents are handed data that isn't theirs, and they use it.** `_format_profile(profile)` takes no
   `agent_id`; every one of the 12 gets a byte-identical fact sheet carrying RSI, headlines, retail
   sentiment, portfolio and every risk cap. Measured over 18 convenes (72 analyst turns):

   | analyst | cites another lane's data |
   |---|---|
   | news_analyst | valuation **16/18**, technicals 13/18, sentiment 9/18 |
   | social_media_analyst | technicals **13/18** |
   | fundamentals_analyst | technicals 8/18, news 3/18 |
   | market_analyst | sentiment 2/18, news 1/18 |

   The four-analyst separation exists to produce four independent lenses. It is the product's core
   claim and it is leaking.

**A correction this CR is built on.** CR143's Phase 3b rejected the scope-firewall concern using the
M2b differentiation result (the four analysts were the least-similar pairing in the corpus, 0.128).
That was the wrong instrument: agents can differ sharply in emphasis and vocabulary while still
borrowing each other's facts. Differentiation is not lane discipline. The table above is the right
measurement and it says the opposite.

## Scope — four tiers, ordered by cost

### Tier A — render data already fetched and discarded (no new provider)

| field | fetched | fate today |
|---|---|---|
| `marketCap` | `fundamentals.py:248` | denominator of the FCF-yield calc, never shown |
| `freeCashflow` | `:247` | collapsed to a % |
| `totalDebt` | `:220` | consumed inside `net_cash_millions` |

Rendering market cap also **fixes an unfollowable compliance rule**: the mandate says *"Liquid only.
Avoid microcaps (< $500M market cap)"* while the same prompt forbids recalling market cap from
training memory and never supplies it.

Also here: delete the `32.4% gross margins, up 180bps YoY` example; correct the input list's
*"net cash"* to match the *"Net debt"* the sheet actually renders.

### Tier B — resolve the prompt-layer conflicts (DEF235, DEF236)

- **DEF236** — `_LENGTH_GUIDE` ("2 sentences") vs `_PROSE_FORMAT` ("thesis + bullet points") vs
  `_STANCE_FORMAT` (a line before the thesis). Pick one; re-derive `_AGENT_MAX_TOKENS` from measured
  output rather than from the guide nobody follows.
- **DEF235** — `_LEVEL_PATTERNS` needs the fenced ticket layout that `_PROSE_FORMAT` forbids; 11 of 16
  Trader turns state levels inline, which is where a share price gets read as a position size and a
  drawdown figure ships 63× too large under *"These are the figures of record"*.
- `LearningStyle.QUICK` renders *"terse, tabular"* against `_PROSE_FORMAT`'s *"no tables"*.

Small diffs, **large blast radius** — every one changes what all 11 prose agents receive. CR142
**Tier A**, and the acceptance is a post-promotion re-measure against CR143's existing baselines.

### Tier C — per-agent fact sheet (the substantive work)

`_format_profile(profile)` → `_format_profile(profile, agent_id)`, with a per-agent visibility
matrix. Not a mechanical gate:

- Bull/Bear/Research Manager/Trader/PM **legitimately** need cross-lane data — the matrix is a design
  decision, not a filter.
- Interacts with CR098 (withheld analysts already strip fact-sheet lines) and with `field_state`
  provenance (CR104).
- `test_prompt_data_parity.py` (558 lines) asserts computed fields reach the prompt; it must learn
  the difference between "dropped" and "not this agent's lane", or it turns red.

### Tier D — wire the fundamentals we don't read (cache is mandatory, not a follow-up)

- Margin trend via `.income_stmt` / `.quarterly_income_stmt`; buybacks via `.cashflow` /
  `get_shares_full()`. Both available from the existing provider, neither wired — the only yfinance
  fundamentals call today is `yf.Ticker(t).info` (`fundamentals.py:141`).
- **Blocker: `fundamentals.py` has no caching of any kind.** Every Room convene and every 1-on-1
  message fetches live. Quotes/news/earnings have TTLs via `CachingProvider`; fundamentals have
  nothing. Adding 2–3 heavier statement calls per run multiplies Yahoo rate-limit exposure, so a TTL
  fundamentals cache ships **in this tier or the tier doesn't ship**.
- Wiring buybacks retires a baked-in disclosure: `fundamentals.py:253-254`, the base prompt in
  `content/agents/`, and `CR143_agent_prompt_audit/PHASE1_ground_truth.md` all currently state
  buybacks are unavailable — true of `.info`, false once statement endpoints are used.

**Out of scope:** revenue segments, M&A history, company guidance. All need a new provider (SEC EDGAR
or Alpha Vantage); separate decision. The existing "not available" disclosures for these stay correct.

## Acceptance

- Tier A: market cap, FCF $ and gross debt appear in the fact sheet; no prompt anywhere instructs a
  number the fact sheet cannot supply. The `32.4%` example is gone.
- Tier B: the six CR143 baselines re-measured post-promotion — over-budget rate per agent, bullet
  usage, stance emission, truncation, PM first-pass parse, banned-action rate. A prompt edit whose
  effect is not re-measured is the CR105 Amendment-1 trap.
- Tier C: cross-lane citation rate falls materially from the table above, re-measured on ≥30 convenes.
  `test_prompt_data_parity.py` green and non-vacuous.
- Tier D: no uncached fundamentals fetch on the convene path; margin trend and buyback history render
  with `field_state` provenance; every "buybacks not available" claim removed in the same commit.
- `pytest backend/tests/unit/ -q` green throughout.

## Notes

Tier A is free and independent — it can ship alone. Tier B carries the user-visible defect (DEF235's
63× figure) and should not wait. Tier C is the one that needs a design decision from Saiful before
any code. Tier D is gated on the cache.
