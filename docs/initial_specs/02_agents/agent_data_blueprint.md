---
title: Agent Data Blueprint — the inputs every agent MUST receive, per surface
status: normative (delivery is measured against this)
owner: Room-quality lane (AT:R59) — files & maintains; build team delivers against it
updated: 2026-07-24
supersedes: docs/forward_planning/CR023_news_analyst_live_feed/original_silent_scout_research/05_agent_alignment/agent_data_matrix.md (stale, Room+1-on-1 only, pre-live-feeds)
source_of_truth_for_claims: content/agents/*.md ("## Inputs" of each agent)
enforced_by: DEF098 prompt-data parity guard (owned by the architect — do NOT edit DEF098 from here)
---

# Agent Data Blueprint

**What this is.** The *target state*: for every agent, on every surface it runs, the
complete set of data inputs it is **expected** to be handed so it can do its declared
job. This is a **blueprint, not an audit.** It states what delivery must supply — not
what today's code happens to render. When an agent's rendered context and this document
disagree, **this document is the specification and the code is the defect.**

**Its relationship to DEF098.** DEF098 builds the *guard* — a prompt-data parity test
that fails the build when a computed field reaches no surface. This document is the
*expectation that guard checks against*: the per-agent, per-surface field list a parity
test binds to. DEF098 is owned by the architect and is not modified here; this file feeds
it.

**Source of an agent's claim.** Each agent's `## Inputs` section in
`content/agents/<agent>.md` is the authoritative statement of what that agent asserts it
receives. Those files were corrected to match honest data availability under
DEF052/DEF053/DEF054/DEF055 and CR023/CR024 — so they are the current truth of *what is
claimed*, and this blueprint is the truth of *what must therefore be delivered*. If a
claim and this blueprint drift, reconcile both in the same change.

---

## Agent prompts on file

Each agent's full prompt — role, `## Inputs`, output style, guardrails, and voice — lives
in `content/agents/`. These are the authoritative statement of what each agent claims to
receive and how it is told to use it; this blueprint is the target that claim implies.

| Agent | Family | Prompt file |
|---|---|---|
| Fundamentals Analyst | analyst | [fundamentals_analyst.md](../../../content/agents/fundamentals_analyst.md) |
| Market Analyst | analyst | [market_analyst.md](../../../content/agents/market_analyst.md) |
| News Analyst | analyst | [news_analyst.md](../../../content/agents/news_analyst.md) |
| Social Media Analyst | analyst | [social_media_analyst.md](../../../content/agents/social_media_analyst.md) |
| Bull Researcher | researcher | [bull_researcher.md](../../../content/agents/bull_researcher.md) |
| Bear Researcher | researcher | [bear_researcher.md](../../../content/agents/bear_researcher.md) |
| Research Manager | manager | [research_manager.md](../../../content/agents/research_manager.md) |
| Trader | execution | [trader.md](../../../content/agents/trader.md) |
| Aggressive Debator | risk | [aggressive_debator.md](../../../content/agents/aggressive_debator.md) |
| Conservative Debator | risk | [conservative_debator.md](../../../content/agents/conservative_debator.md) |
| Neutral Debator | risk | [neutral_debator.md](../../../content/agents/neutral_debator.md) |
| Portfolio Manager | gatekeeper | [portfolio_manager.md](../../../content/agents/portfolio_manager.md) |
| AMI Concierge (13th — not a trading agent) | concierge | [concierge.md](../../../content/agents/concierge.md) |

---

## How to read it

- **MUST** — the agent cannot do its declared job without this; absence is a defect.
- **SHOULD** — materially improves the answer; absence is a gap to schedule, not a break.
- **N/A** — the surface does not run this agent, or the domain is out of the agent's role.
- **Source exists / no source** — whether a live provider can supply the field today. Where
  no source exists, the expectation is **not** "invent it" — it is the honest-degradation
  rule (§7): the prompt must not claim the field, and the surface must say so plainly.

Field names are written to match the code vocabulary (fetcher output / profile keys) so a
parity test can bind to them directly.

---

## 1. Data dictionary — the canonical domains

Every expectation below is expressed in these domains. A domain is "delivered" only when
**every MUST field in it** is rendered into the block the agent reads.

| Domain | MUST fields | Authoritative source | Not available (never claim) |
|---|---|---|---|
| **Fundamentals** | reference price · P/E · P/S · EV/EBITDA · PEG · FCF yield · TTM revenue growth · profit margin · net cash · 52-week range · sector/industry · dividend yield · analyst consensus (rating + target) · next-earnings date + consensus EPS | `fundamentals.py` (yfinance) | full financial statements · buybacks/M&A history · forward guidance · numeric peer-basket P/E |
| **Technicals** | RSI(14) · trend read (20/50-day MA) · volume vs 20-day avg · recent-range support · recent-range breakout · (daily timeframe) | `technicals.py` (yfinance OHLCV) | MACD · MA-crossover signal · Bollinger Bands · intraday (1H) |
| **News** | recent headlines (publisher + recency) · per-headline sentiment tag (where supplied) · next-earnings date (≤90d) | `news_context.py` (Yahoo + Alpha Vantage) | macro-indicator calendar (CPI/NFP/Fed) · regulatory filings (8-K/S-1) |
| **Social** | sentiment tone · sentiment score · mention volume + trend · most-active communities · buzz score · numeric bullish/bearish split | `social_context.py` (Adanos / Reddit aggregate) | Twitter/X · StockTwits real scores · Google Trends · Discord |
| **Mandate** | primary goal · horizon · risk_score · max_drawdown_pct · compliance (long_only, halal, ESG, blocklist, sector exclusions) · starting capital · locale | user mandate | — (always available) |
| **Portfolio state** | portfolio value · current drawdown % · remaining drawdown capacity · cash/buying power · holdings (ticker, shares, cost basis, weight) | `sim_engine` / portfolio store; Alpaca snapshot (1-on-1 link) | — |
| **Decision Journal** | past Room verdicts + trades **for this ticker** (date, action, outcome, summary) | `journal_store` → `build_journal_context_block` | — |
| **Transcript** (Room only) | prior-phase agent outputs, per the phase gate | `room_runner` phase loop | — |
| **Derived trade math** | entry / stop / target · R:R ratio · drawdown contribution (stop-distance × size) · coherence flag | `trading_math` (`risk_reward`, `drawdown_contribution`, `rr_is_coherent`) | — |
| **Safety-floor verdict** (PM only) | deterministic compliance pre-check result (`pm_predetermined_action`) | `room_runner` safety floor | — |
| **Lessons catalogue** (Concierge only) | full lesson index (code + id + title) · unlocked agents · unlock requirements | `concierge_prompts.py` | — |

---

## 2. Surfaces

| Surface | Code | Who runs | Context shape |
|---|---|---|---|
| **Room** (Convene) | `room_runner.py` + `room_prompts.py::_format_profile()` | all 12, in 6 phases | one shared profile (Fundamentals+Technicals+News+Social) + growing transcript, gated by phase |
| **1-on-1 chat** | `agent_runner.py::stream_one_on_one_message` (injection at `:186–225`) | any single agent + Concierge | per-agent gated blocks, keyed off tickers the user mentions |
| **Brief Your Agent** ("Coach", renamed AT:R27) | `brief_engine.py` | any single agent | base prompt + current overlay + mandate + **safety floor**; no market/ticker data |
| **Concierge** | `concierge_prompts.py` | Concierge only | mandate one-liner + journal + unlocked agents + unlock paths + lessons catalogue; no market/ticker data |
| **Daily Challenge** | content-retrieval service | n/a | out of class — retrieves stored content, assembles no live agent prompt |

**Room phase gate** (who sees what in the transcript):

| Phase | Agents | Transcript visible |
|---|---|---|
| 1 · Analysts | Fundamentals, Market, News, Social | nothing (speak first) |
| 2 · Researchers | Bull, Bear | phase 1 |
| 3 · Synthesis | Research Manager | phases 1–2 |
| 4 · Execution | Trader | phases 1–3 |
| 5 · Risk | Aggressive, Conservative, Neutral | phases 1–4 |
| 6 · Verdict | Portfolio Manager | phases 1–5 + safety-floor verdict |

---

## 3. Room — per-agent expectation

All Room agents receive the shared profile and the Mandate. The table states each agent's
**job-critical** domains — the ones whose absence means it cannot do its declared job.
"Has all the data it needs" (Saiful's standing ask) = every MUST cell below is delivered.

| Agent | Fundamentals | Technicals | News | Social | Mandate | Transcript | Portfolio | Journal | Derived math | Safety floor |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| Fundamentals Analyst | **MUST** | — | — | — | MUST | — | — | — | — | — |
| Market Analyst | price only | **MUST** | — | — | MUST | — | — | — | — | — |
| News Analyst | price only | — | **MUST** | — | MUST | — | — | — | — | — |
| Social Media Analyst | price only | — | — | **MUST** | MUST | — | — | — | — | — |
| Bull Researcher | SHOULD | SHOULD | SHOULD | SHOULD | MUST | **MUST** (ph1) | — | **MUST** (ticker) | — | — |
| Bear Researcher | SHOULD | SHOULD | SHOULD | SHOULD | MUST | **MUST** (ph1) | — | **MUST** (ticker) | — | — |
| Research Manager | — | — | — | — | MUST | **MUST** (ph1–2) | — | — | — | — |
| Trader | SHOULD | SHOULD | — | — | MUST | **MUST** (ph1–3) | **MUST** | — | **MUST** (own proposal) | — |
| Aggressive Debator | — | — | — | — | MUST | **MUST** (ph1–4) | SHOULD | — | **MUST** (proposal) | — |
| Conservative Debator | — | — | — | — | MUST | **MUST** (ph1–4) | **MUST** (drawdown) | — | **MUST** (proposal) | — |
| Neutral Debator | — | — | — | — | MUST | **MUST** (ph1–4) | SHOULD | — | **MUST** (proposal) | — |
| Portfolio Manager | — | — | — | — | **MUST** (full) | **MUST** (ph1–5) | **MUST** | — | **MUST** | **MUST** |

**Notes that bind delivery:**

- **Social Media Analyst MUST get all 6 Social fields** — tone, score, mention volume,
  communities, buzz score, and the numeric bull/bear split. Rendering only tone + score
  is a defect (this is the hole DEF096 names). Its job (`social_media_analyst.md:16,23`)
  explicitly grounds its read in mention counts, buzz score, and the split.
- **Trader MUST get Derived trade math for its own proposal** — the R:R and
  drawdown-contribution figures, computed by `trading_math`, for the entry/stop/target it
  is stating. Making the Trader narrate a ratio nothing computed is a defect (DEF066 gates
  these to RISK/VERDICT today; DEF095 shows the resulting figures are wrong on live
  trades). The Debators and PM read the Trader's stated numbers, so the figure must be
  real before they inherit it.
- **PM MUST get the Safety-floor verdict** (`pm_predetermined_action`) plus full Portfolio
  state — it is the gatekeeper and adjudicates against the mandate.
- **Analysts get `price only` from Fundamentals** because each non-fundamentals analyst
  needs the reference price to anchor levels, not the full ratio set. That is sufficient,
  not a gap.

---

## 4. 1-on-1 chat — per-agent expectation

1-on-1 has no transcript. Each agent reasons from the live blocks injected for the tickers
the user mentions, plus its mandate. **Parity principle (§6): an agent's job-critical
domain in the Room is job-critical in 1-on-1 too.** The current injection gates each
domain to one agent (`agent_runner.py:196–225`); the expectation is that the gated block
is the *full* domain, not a thinner subset.

| Agent | MUST receive (1-on-1) | Source-gated to it today | Expectation vs. today |
|---|---|---|---|
| Fundamentals Analyst | Fundamentals (full §1 set) + Mandate | live-data block (all agents) | block must carry the **full** DEF053 set, not the 7-field subset |
| Market Analyst | Technicals (full) + price + Mandate | technicals block (Market only) | full — matches |
| News Analyst | News + Mandate | news block (News only) | full — matches |
| Social Media Analyst | Social (all 6) + Mandate | social block (Social only) | richer than Room today; keep it full |
| Bull Researcher | Journal (ticker) + Fundamentals + Mandate | journal block (Bull/Bear only) | full |
| Bear Researcher | Journal (ticker) + Fundamentals + Mandate | journal block (Bull/Bear only) | full |
| Research Manager | Fundamentals + Mandate | live-data block | SHOULD; reasons without a transcript here |
| Trader | Fundamentals + Mandate + **Portfolio state** | live-data block | **Portfolio state not injected today — gap.** Trader mis-sizes without it |
| Aggressive/Conservative/Neutral Debator | Mandate (+ Fundamentals) | live-data block | SHOULD |
| Portfolio Manager | Mandate (+ Fundamentals) | live-data block | Portfolio state SHOULD (1-on-1 PM is hypothetical discussion, not a live verdict) |
| Concierge | see §6 Concierge row | — | — |

**Binds delivery:**

- **Next-earnings date/EPS MUST reach the 1-on-1 Fundamentals path.** It is computed in the
  Room but the 1-on-1 fundamentals block omits it. Neither renderer is a superset of the
  other — the asymmetry DEF098 documents. The blueprint's expectation is that both surfaces
  render the full Fundamentals domain.
- **Trader/PM Portfolio state in 1-on-1** is a scheduled SHOULD→MUST for the Trader:
  without portfolio value and remaining drawdown it cannot size.

---

## 5. Brief Your Agent + Concierge — per-agent expectation

**Brief Your Agent** (`brief_engine.py`) edits an agent's *standing instructions*, not a
ticker analysis. No market/ticker data is expected or wanted.

| Input | Level | Source |
|---|---|---|
| The agent's own base prompt | MUST | `build_agent_prompt` |
| Current active overlay (what the user briefed so far) | MUST | `OverlayStore` |
| Mandate | MUST | session mandate |
| **Deterministic safety-floor refusal check** | **MUST (structural)** | `heuristic_refusal_check` |

- The safety floor is the load-bearing input: PM mandate enforcement is **uncoachable**,
  and the refusal is a deterministic pre-check (`brief_engine.py:130–162`), **not** a
  prompt instruction — because prompt instructions are ignored ~70% of the time (CR038).
  A brief that would weaken compliance/drawdown/single-name caps must be refused by code
  before the LLM sees it.

**Concierge** (`concierge_prompts.py`) helps the user *use the product*; it gives no
trading advice, so it expects **no market/ticker/live data**.

| Input | Level | Source |
|---|---|---|
| Mandate one-liner | MUST | `_mandate_one_liner` |
| Recent Decision Journal entries (route target) | MUST | `recent_journal` |
| Currently unlocked trading agents | MUST | `unlocked_agents` |
| Unlock requirements per locked agent | MUST | `unlock_requirements` |
| Full lessons catalogue index (code + id + title) | MUST | `_lesson_context_block` (full_context) |

- The Concierge MUST be able to name a lesson/agent/journal entry **by its real
  identifier** — the whole catalogue is injected precisely so it routes instead of
  hallucinating titles. It does not analyse an entry (it renders title/type/ticker, not
  summary/note) — that omission is **intentional** and must be *declared* in the parity
  registry, not left to look accidental.

---

## 6. Cross-surface parity principle

The single rule the guard enforces, stated once:

> **A domain that is job-critical (MUST) for an agent on one surface is job-critical for
> that agent on every surface that runs it — and "delivered" means the *full* domain, not
> a thinner subset.**

Two ways this rule is currently violated, both already filed (do not re-file):

1. **Room drops 3 of 6 Social fields** for the Social Media Analyst → DEF096.
2. **1-on-1 Fundamentals omits next-earnings** that the Room renders → the asymmetry in
   DEF098.

Any *new* violation the guard catches is a new defect; route it through intake, not this
file.

---

## 7. Honest-degradation rule (no source ≠ invent)

Where the dictionary says **no source exists**, the expectation is **not** to fabricate a
plausible number. It is:

1. The agent's `## Inputs` MUST NOT claim the field (the DEF052/DEF053 correction pattern).
2. The surface MUST say plainly that the field is unavailable rather than substitute a
   look-alike (e.g. the Social analyst reaching for *price* volume when denied *mention*
   volume — the live INGN failure in DEF096).
3. Silent fallback to a synthetic value is forbidden — CR040 "degrade loudly." A dropped
   computed field and a fabricated missing field are the same lie in opposite directions.

---

## 8. Maintenance

- This file and `content/agents/*.md` move together. Changing what an agent claims, or
  what a surface renders, updates both in the same change.
- The stale `agent_data_matrix.md` under CR023's research folder is **superseded** by this
  file; treat it as history.
- This is a *blueprint*. It records the target; DEF098's guard (architect-owned) makes the
  target enforceable. Keep the two consistent; do not edit DEF098 from this lane.
