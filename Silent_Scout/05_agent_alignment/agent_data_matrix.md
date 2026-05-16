---
title: Agent Data Matrix — Prompt Claims vs Runtime Feed
updated: 2026-05-15
source_files:
  - content/agents/*.md
  - backend/app/services/room_runner.py (_profile_for_ticker, lines 185–272)
  - backend/app/services/room_prompts.py (_format_profile, lines 136–173)
  - backend/app/services/agent_runner.py (stream_one_on_one_message, lines 128–145)
  - backend/app/services/fundamentals.py (build_live_data_block, lines 138–174)
---

# Agent Data Matrix

## Legend

- **✅ Covered** — field explicitly named in prompt exists in the injected block
- **⚠️ Partial** — field category exists but is coarser than the prompt implies
- **❌ Missing** — prompt names a data source with zero injected equivalent
- **N/A** — mode doesn't apply (Tier-2+ agents only run in Room, not 1-on-1)
- **Structural** — gap is by design (no live news/social feed in simulation)
- **Accidental** — data exists in the pipeline but isn't routed to this agent

---

## What the Room profile dict contains (all agents share this)

Built once per run by `_profile_for_ticker()` (`room_runner.py:185`), formatted
by `_format_profile()` (`room_prompts.py:136`), and appended to every agent's
system prompt alongside the growing debate transcript.

### Fields injected into every Room agent

**Numeric (live from yfinance when `USE_REAL_MARKET_DATA=true`, otherwise synthetic):**

| Field key | Displayed as | Live? |
|---|---|---|
| `base_price` | "Reference price: $X" | ✅ yfinance `currentPrice` |
| `pe` | "P/E: X (sector ~Y)" | ✅ yfinance `trailingPE` |
| `sector_pe` | "P/E: X (sector ~Y)" | ❌ always synthetic |
| `rev_growth` | "TTM revenue growth: X%" | ✅ yfinance `revenueGrowth` |
| `fcf_margin` | "FCF margin: X%" | ✅ yfinance `profitMargins` |
| `net_cash` | "Net cash: XM" | ✅ yfinance totalCash - totalDebt |
| `rsi` | "RSI: X" | ❌ always synthetic |
| `trend` | "trend: trading/consolidating" | ❌ always synthetic |
| `low` / `high` | "Recent range: $X–$Y" | ✅ yfinance `fiftyTwoWeekLow/High` |
| `breakout` | "breakout level: $X" | ❌ derived as price × 1.03 |
| `volume_tone` | "Volume: above/in-line 20-day avg" | ❌ always synthetic (string) |

**Narrative (always synthetic — no live news/social feed):**

| Field key | Content |
|---|---|
| `catalyst` | "Q3 earnings (beat by ~4%)" — hardcoded template |
| `forward_catalyst` | "FOMC decision in 11 days, sector earnings in 3 weeks" — hardcoded template |
| `macro_tone` | "constructive but fragile" — hardcoded |
| `fed_tone` | "data-dependent with a dovish lean" — hardcoded |
| `sentiment_tone` | "moderately bullish" or "mixed" — coin-flip |
| `sentiment_score` | "+0.3 to +1.8σ" — random within range |
| `mention_trend` | "up 40% week-over-week" — hardcoded |
| `influencer_take` | "broadly constructive, no euphoria" — hardcoded |
| `pattern` | "sentiment confirming price..." — hardcoded |
| `bull_evidence` / `bull_missing` / `bull_falsifier` | Bull thesis scaffolding — hardcoded |
| `bear_catalyst` / `bear_invalidator` | Bear risk scaffolding — hardcoded |

**Transcript visibility (progressive — agents only see prior speakers):**

| Phase | Agents | Sees in transcript |
|---|---|---|
| 1 — Analysts | Fundamentals, Market, News, Social | Nothing (speak first) |
| 2 — Researchers | Bull, Bear | Phase 1 outputs |
| 3 — Synthesis | Research Manager | Phase 1 + 2 outputs |
| 4 — Execution | Trader | Phase 1 + 2 + 3 outputs |
| 5 — Risk | Aggressive, Conservative, Neutral | Phase 1–4 outputs |
| 6 — Verdict | Portfolio Manager | Phase 1–5 outputs + pre-computed safety-floor verdict |

---

## What the 1-on-1 live block contains (all agents share this)

Built by `build_live_data_block()` (`fundamentals.py:138`). The same 6-field
block is appended to every agent's system prompt regardless of their role.
Only fires when `USE_REAL_MARKET_DATA=true` AND yfinance returns data.

```
─── LIVE MARKET DATA — {SYMBOL} ───
Price: $X
P/E: Y
TTM revenue growth: Z%
Profit margin: W%
Net cash: $XM
52-week range: $A–$B
(yfinance live snapshot. Use these numbers. Do NOT cite figures from training memory.)
```

Fields: `base_price`, `pe`, `rev_growth`, `fcf_margin`, `net_cash`, `low`, `high`.
No RSI, no technical indicators, no news, no sentiment.

---

## Per-agent coverage table

### Tier 1 — Analysts

#### 1. Fundamentals Analyst (`fundamentals_analyst.md`)

**Prompt claims to receive:**
- Financial statements (income, balance sheet, cash flow)
- Earnings history and forward guidance
- Valuation multiples (P/E, P/S, EV/EBITDA, FCF yield)
- Peer comparisons
- Capital allocation history (buybacks, dividends, M&A)

| Claimed input | Room | 1-on-1 | Gap type |
|---|---|---|---|
| Price / P/E | ✅ `base_price`, `pe` | ✅ `base_price`, `pe` | — |
| Revenue growth | ✅ `rev_growth` | ✅ `rev_growth` | — |
| FCF margin | ✅ `fcf_margin` | ✅ `fcf_margin` | — |
| Net cash | ✅ `net_cash` | ✅ `net_cash` | — |
| P/S, EV/EBITDA, FCF yield | ❌ not in profile | ❌ not in block | Structural |
| Earnings history / guidance | ⚠️ synthetic `catalyst` only | ❌ nothing | Structural |
| Peer comparisons | ⚠️ `sector_pe` (one number) | ❌ nothing | Structural |
| Buybacks / dividends / M&A | ❌ not in profile | ❌ not in block | Structural |
| Balance sheet detail | ❌ only net cash | ❌ only net cash | Structural |

**Overall:** ⚠️ Partial. Core price/growth/FCF numbers are covered. Deeper financials
(P/S, EV/EBITDA, balance sheet beyond net cash) are structurally absent — simulation constraint.

---

#### 2. Market Analyst (`market_analyst.md`)

**Prompt claims to receive:**
- Price action across timeframes (1H, daily, weekly, monthly)
- Indicators: MACD, RSI, moving averages, Bollinger Bands
- Volume profile
- Support and resistance levels
- Trend identification

| Claimed input | Room | 1-on-1 | Gap type |
|---|---|---|---|
| Price (current) | ✅ `base_price` | ✅ `base_price` | — |
| 52-week range (proxy for range) | ✅ `low`, `high` | ✅ `low`, `high` | — |
| RSI | ✅ `rsi` (synthetic only) | ❌ not in block | **Accidental** |
| Trend | ✅ `trend` (coarse: "trading"/"consolidating") | ❌ not in block | **Accidental** |
| Support level | ✅ `support` (one level, = price × 0.90) | ❌ not in block | **Accidental** |
| Breakout level | ✅ `breakout` (= price × 1.03) | ❌ not in block | **Accidental** |
| Volume tone | ✅ `volume_tone` (above/in-line — string) | ❌ not in block | **Accidental** |
| MACD | ❌ not in profile | ❌ not in block | Structural |
| Moving averages (20MA, 50MA, 200MA) | ❌ not in profile | ❌ not in block | Structural |
| Bollinger Bands | ❌ not in profile | ❌ not in block | Structural |
| Volume profile (distribution) | ❌ only volume tone | ❌ not in block | Structural |
| Multi-timeframe (1H, daily, weekly, monthly) | ❌ not in profile | ❌ not in block | Structural |

**Overall:** ⚠️ Partial in Room / ❌ Missing in 1-on-1.
Room gives RSI + one S/R level + volume tone + trend tag — enough for a scaffolded answer.
1-on-1 gives only price + 52-week range — the Market Analyst has nothing to work with.
RSI, support, breakout, volume tone, and trend already exist in the Room profile dict
but are not included in `build_live_data_block()`. This is the highest-severity accidental gap.

---

#### 3. News Analyst (`news_analyst.md`)

**Prompt claims to receive:**
- Real-time news feeds (Reuters, Bloomberg, FT, regional sources)
- Macro indicator calendar (CPI, NFP, Fed decisions, ECB, etc.)
- Earnings calendar
- Regulatory filings (8-K, S-1, etc.)

| Claimed input | Room | 1-on-1 | Gap type |
|---|---|---|---|
| Recent earnings catalyst | ⚠️ synthetic `catalyst` field | ❌ nothing | Structural |
| Forward macro catalyst | ⚠️ synthetic `forward_catalyst` field | ❌ nothing | Structural |
| Macro tone | ⚠️ synthetic `macro_tone` string | ❌ nothing | Structural |
| Fed stance | ⚠️ synthetic `fed_tone` string | ❌ nothing | Structural |
| Real-time news feeds | ❌ not available | ❌ not available | Structural |
| Macro calendar (CPI, NFP dates) | ❌ not available | ❌ not available | Structural |
| Regulatory filings | ❌ not available | ❌ not available | Structural |
| Earnings calendar | ❌ not available | ❌ not available | Structural |

**Overall:** ⚠️ Partial in Room (synthetic placeholders) / ❌ Missing in 1-on-1.
Room's synthetic catalyst/macro fields are better than nothing — the agent can narrate
a plausible scenario. But they are hardcoded templates (not derived from real news).
In 1-on-1 the News Analyst has zero news context. All gaps are structural.

---

#### 4. Social Media Analyst (`social_media_analyst.md`)

**Prompt claims to receive:**
- Reddit (r/investing, r/wallstreetbets, r/stocks)
- Twitter/X cashtags + finance-influencer feeds
- StockTwits sentiment scores
- Google Trends
- Discord communities

| Claimed input | Room | 1-on-1 | Gap type |
|---|---|---|---|
| Sentiment tone | ⚠️ synthetic `sentiment_tone` (coin-flip) | ❌ nothing | Structural |
| Sentiment score (σ units) | ⚠️ synthetic `sentiment_score` (random +0.3–+1.8) | ❌ nothing | Structural |
| Mention trend | ⚠️ synthetic `mention_trend` (hardcoded "up 40% WoW") | ❌ nothing | Structural |
| Influencer take | ⚠️ synthetic `influencer_take` (hardcoded phrase) | ❌ nothing | Structural |
| Sentiment pattern | ⚠️ synthetic `pattern` (hardcoded) | ❌ nothing | Structural |
| Reddit thread data | ❌ not available | ❌ not available | Structural |
| Twitter/X cashtag data | ❌ not available | ❌ not available | Structural |
| StockTwits real scores | ❌ not available | ❌ not available | Structural |
| Google Trends | ❌ not available | ❌ not available | Structural |

**Overall:** ⚠️ Partial in Room (synthetic sentiment block) / ❌ Missing in 1-on-1.
Room gives 5 synthetic sentiment fields — enough for the agent to narrate a scenario.
1-on-1 has nothing. All gaps are structural (no live social feed in simulation).

---

### Tier 2 — Researchers

#### 5. Bull Researcher (`bull_researcher.md`)

**Prompt claims to receive:**
- Outputs from the 4 Analysts
- User's mandate (horizon, risk tolerance, constraints)
- Historical context from Decision Journal

| Claimed input | Room | 1-on-1 | Gap type |
|---|---|---|---|
| 4 Analyst outputs | ✅ full transcript (Phase 1 complete when Bull speaks) | N/A | — |
| Mandate (risk_score, constraints) | ✅ mandate snapshot in system prompt | N/A | — |
| Decision Journal context | ❌ not injected | N/A | Accidental |

**Overall:** ✅ Well-covered in Room. Decision Journal history is absent — minor gap
(the agent can reason without it, but won't recall the user's prior trades).

---

#### 6. Bear Researcher (`bear_researcher.md`)

Same inputs as Bull Researcher. Same coverage assessment.

| Claimed input | Room | 1-on-1 | Gap type |
|---|---|---|---|
| 4 Analyst outputs | ✅ transcript | N/A | — |
| Mandate | ✅ mandate snapshot | N/A | — |
| Decision Journal context | ❌ not injected | N/A | Accidental |

**Overall:** ✅ Well-covered in Room. Same Journal gap as Bull.

---

### Tier 3 — Synthesis

#### 7. Research Manager (`research_manager.md`)

**Prompt claims to receive:**
- Bull Researcher's argument
- Bear Researcher's argument
- The 4 Analysts' outputs
- User's mandate

| Claimed input | Room | 1-on-1 | Gap type |
|---|---|---|---|
| Bull + Bear outputs | ✅ transcript (Phase 2 complete) | N/A | — |
| All 4 Analyst outputs | ✅ transcript | N/A | — |
| Mandate | ✅ mandate snapshot | N/A | — |

**Overall:** ✅ Fully covered in Room.

---

### Tier 4 — Execution

#### 8. Trader (`trader.md`)

**Prompt claims to receive:**
- Research Manager's synthesis
- Risk Debators' arguments (Aggressive, Conservative, Neutral)
- User's current portfolio + remaining drawdown capacity
- User's mandate

| Claimed input | Room | 1-on-1 | Gap type |
|---|---|---|---|
| Research Manager synthesis | ✅ transcript (Phase 3 complete) | ⚠️ can discuss via chat | — |
| Risk Debators' arguments | ❌ **Trader runs in Phase 4; Debators run in Phase 5** | ❌ not applicable | **Accidental / Design** |
| Portfolio value | ✅ passed via `ctx.portfolio_value` (formatted by Room) | ❌ not injected | Accidental |
| Remaining drawdown capacity | ✅ `ctx.current_drawdown_pct` + `mandate.max_drawdown_pct` | ❌ not injected | Accidental |
| Mandate | ✅ mandate snapshot | ✅ via mandate overlay | — |

**Overall:** ⚠️ Phase-sequencing issue. The Trader's prompt says it uses the Risk
Debators' arguments, but in the Room's 6-phase sequence the Trader (Phase 4) runs
*before* the Risk Debators (Phase 5). The PM re-adjudicates after the debate, but
the Trader is writing a proposal without having seen the Debators' arguments.
This is a prompt-vs-architecture mismatch that may cause Trader to mis-size.
In 1-on-1, portfolio state is not injected.

---

### Tier 5 — Risk Debators

#### 9. Aggressive Debator (`aggressive_debator.md`)

**Prompt claims to receive:**
- Trader's proposal
- Conservative Debator's argument
- Neutral Debator's argument
- User's mandate

| Claimed input | Room | 1-on-1 | Gap type |
|---|---|---|---|
| Trader's proposal | ✅ transcript (Phase 4 complete) | N/A | — |
| Other Debators' arguments | ❌ all 3 Debators run in parallel within Phase 5 | N/A | Design |
| Mandate | ✅ mandate snapshot | N/A | — |

**Overall:** ⚠️ Partial. The 3 Debators run in parallel — none sees the others'
arguments. This is acceptable (they're meant to be independent voices), but the
prompt implies they see each other's arguments before responding. Minor framing mismatch.

---

#### 10. Conservative Debator / 11. Neutral Debator

Same as Aggressive Debator — same phase-parallel issue, same assessment.

---

### Tier 6 — Gatekeeper

#### 12. Portfolio Manager (`portfolio_manager.md`)

**Prompt claims to receive:**
- Trader's proposal
- Research Manager's synthesis
- All 3 Risk Debators' arguments
- User's current portfolio state + remaining drawdown
- User's full mandate

| Claimed input | Room | 1-on-1 | Gap type |
|---|---|---|---|
| Trader's proposal | ✅ transcript (Phase 4) | ⚠️ can discuss, no structure | — |
| Research Manager synthesis | ✅ transcript (Phase 3) | ⚠️ can discuss | — |
| All 3 Debator arguments | ✅ transcript (Phase 5) | N/A | — |
| Portfolio state / drawdown | ✅ injected via `_assemble_verdict()` | ❌ not injected | Accidental |
| Full mandate | ✅ mandate snapshot + safety floor | ✅ via mandate overlay | — |
| Pre-computed verdict | ✅ `pm_predetermined_action` appended to prompt | N/A | — |

**Overall:** ✅ Well-covered in Room. Portfolio state not available in 1-on-1
(expected — PM's 1-on-1 use case is hypothetical discussion, not live verdicts).

---

## Summary table

| # | Agent | Room | 1-on-1 | Worst gap type |
|---|---|---|---|---|
| 1 | Fundamentals Analyst | ⚠️ Partial | ⚠️ Partial | Structural |
| 2 | Market Analyst | ⚠️ Partial | ❌ Missing | **Accidental (High)** |
| 3 | News Analyst | ⚠️ Partial | ❌ Missing | Structural |
| 4 | Social Media Analyst | ⚠️ Partial | ❌ Missing | Structural |
| 5 | Bull Researcher | ✅ Covered | N/A | Accidental (Low) |
| 6 | Bear Researcher | ✅ Covered | N/A | Accidental (Low) |
| 7 | Research Manager | ✅ Covered | N/A | — |
| 8 | Trader | ⚠️ Partial | ⚠️ Partial | **Accidental (High)** |
| 9 | Aggressive Debator | ⚠️ Partial | N/A | Design |
| 10 | Conservative Debator | ⚠️ Partial | N/A | Design |
| 11 | Neutral Debator | ⚠️ Partial | N/A | Design |
| 12 | Portfolio Manager | ✅ Covered | ⚠️ Partial | Accidental (Low) |
