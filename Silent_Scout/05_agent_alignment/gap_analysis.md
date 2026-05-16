---
title: Gap Analysis — Agent Prompt vs Runtime Data Feed
updated: 2026-05-15
severity_scale: High / Medium / Low
---

# Gap Analysis

## Design context: what the synthetic-vs-live split is supposed to do

The backend maintains a deliberate split:

- **Live numeric fields** (`base_price`, `pe`, `rev_growth`, `fcf_margin`, `net_cash`,
  `low`, `high`) — pulled from yfinance when `USE_REAL_MARKET_DATA=true`. These are
  the numbers an LLM is most likely to misremember from training data, so getting
  them right matters most.

- **Synthetic narrative fields** (`catalyst`, `sentiment_tone`, `macro_tone`, etc.) —
  generated from deterministic templates. The rationale: yfinance doesn't provide
  real news or social sentiment, so fabricating them is honest (it's a simulation)
  and prevents the LLM from hallucinating specific news events.

This design is intentional and not a bug. The gaps that follow are either:
- **Structural** — data the app genuinely can't provide (no Bloomberg, no Reddit API),
  documented for transparency
- **Accidental** — data that exists in the pipeline but isn't wired to the agent,
  actionable bugs

---

## Gap 1 — Market Analyst in 1-on-1: no technical indicators at all

**Severity: High | Type: Accidental**

### What the prompt says
The Market Analyst expects "Price action across timeframes (1H, daily, weekly,
monthly)", "Indicators: MACD, RSI, moving averages, Bollinger Bands", "Volume
profile", "Support and resistance levels".

### What 1-on-1 actually delivers
`build_live_data_block()` returns: `Price`, `P/E`, `TTM revenue growth`,
`Profit margin`, `Net cash`, `52-week range`. The same 6 fundamentals fields
that the Fundamentals Analyst needs — not the technical fields the Market
Analyst needs.

### Impact
In 1-on-1 mode the Market Analyst has no technical data. The agent will either
hallucinate from training memory or give a vacuous response. Both are bad.
The 52-week range is a very coarse proxy for support/resistance — it doesn't
give the agent anything to work with on momentum, trend, or indicators.

### Fix
**File:** `backend/app/services/fundamentals.py`
**Function:** `build_live_data_block()`

Pass `agent_id` as an optional parameter. When called for `market_analyst`,
append the technical fields that already exist in the Room profile dict:

```python
def build_live_data_block(ticker: str, agent_id: str | None = None) -> str | None:
    ...
    # Existing fundamentals block (price, PE, growth, FCF, net_cash, range)
    ...
    if agent_id == "market_analyst":
        # RSI and support are synthetic in room_runner; replicate the same
        # synthetic derivation here so 1-on-1 matches Room quality.
        rng = random.Random(hash(ticker.upper()))
        rsi = rng.randint(35, 75)
        support = round(price * 0.90, 2)
        breakout = round(price * 1.03, 2)
        trend = "trading" if rng.random() > 0.5 else "consolidating"
        volume_tone = "above 20-day average" if rng.random() > 0.5 else "in-line"
        lines.append(f"RSI: {rsi}")
        lines.append(f"Trend: {trend}")
        lines.append(f"Support: ${support}, Breakout level: ${breakout}")
        lines.append(f"Volume: {volume_tone}")
        lines.append("(Note: RSI/trend/support are simulation scaffolding, not live.)")
```

**Caller:** `agent_runner.py:143` — pass `agent_id=str(agent_id.value)` to `build_live_data_block()`.

**Effort:** Small — 1 function signature change + 1 call-site change.
**Risk:** Zero — purely additive, existing output unchanged for other agents.

---

## Gap 2 — Trader sees Risk Debators' arguments before they exist

**Severity: High | Type: Accidental (phase-sequencing mismatch)**

### What the prompt says
The Trader prompt lists "Risk Debators' arguments (Aggressive, Conservative,
Neutral)" under Inputs and says "your size must reflect what they collectively
allow."

### What Room actually does
The 6-phase sequence is:
1. Analysts → 2. Researchers → 3. Research Manager → **4. Trader** → 5. Risk Debators → 6. PM

The Trader runs in Phase 4. The Risk Debators run in Phase 5. The Trader
cannot see the Debators' arguments because they haven't been generated yet.

### Impact
The Trader may propose a size that the Debators then argue against. The PM
re-adjudicates after the debate, so the final verdict can still be correct.
But the Trader's internal reasoning is broken — it claims to weigh inputs it
doesn't have. The Trader may produce inconsistent sizing with the final approved
trade, which is confusing to the user watching the debate.

### Fix option A — Reorder phases (preferred)
Swap Phase 4 and Phase 5: run the 3 Risk Debators first, then the Trader.

```
1. Analysts → 2. Researchers → 3. Research Manager →
4. Risk Debators (Aggressive, Conservative, Neutral) →
5. Trader (now has all 3 arguments in transcript) →
6. Portfolio Manager
```

**File:** `backend/app/services/room_runner.py` — reorder the `ROOM_PHASES` list
and update the `_RoomContext` dataclass (Debator outputs are populated in Phase 4,
Trader reads them in Phase 5).

**Effort:** Medium — phase reorder + transcript sequencing logic.
**Risk:** Low — the PM still runs last and applies the safety floor regardless.

### Fix option B — Update the Trader's prompt (minimal change)
Remove the claim that Trader inputs include Risk Debator arguments. Reframe:
Trader proposes independently; PM adjusts based on Debator debate.

**File:** `content/agents/trader.md`
Change "Risk Debators' arguments (Aggressive, Conservative, Neutral)" under
Inputs to "Risk appetite from mandate (risk_score, max_drawdown_pct)" and
remove "Ignore the Risk Debators' arguments — your size must reflect what they
collectively allow" from the constraints.

**Effort:** Trivial — prompt-only change.
**Risk:** Zero architecturally; but this weakens the narrative coherence of the Room.

**Recommendation:** Fix option A (phase reorder) for v1.0; apply Fix B as an
immediate patch to prevent the current hallucination in alpha.

---

## Gap 3 — Trader in 1-on-1: no portfolio state

**Severity: Medium | Type: Accidental**

### What the prompt says
"The user's current portfolio + remaining drawdown capacity."

### What 1-on-1 delivers
The mandate overlay includes `risk_score` and `max_drawdown_pct` (the ceiling),
but not the user's *current* drawdown level or portfolio value. The agent must
infer a percentage position without knowing whether the user is already at 8% of
a 10% drawdown cap.

### Impact
Trader will give position sizing advice that may inadvertently exceed mandate.
Not dangerous (it's a simulation), but the sizing output will be incoherent
if the user is already close to their drawdown ceiling.

### Fix
**File:** `backend/app/services/agent_prompts.py` — in `build_agent_prompt()`,
check if `agent_id == AgentId.TRADER` and append a portfolio-state block:

```python
if agent_id == AgentId.TRADER:
    # Fetch latest portfolio snapshot for this user
    portfolio = fetch_portfolio_snapshot(user_id)  # already exists for Room
    system_prompt += (
        f"\n\nPORTFOLIO STATE (for sizing calculations):\n"
        f"- Portfolio value: ${portfolio.value:,.0f}\n"
        f"- Current drawdown: {portfolio.current_drawdown_pct:.1f}%\n"
        f"- Remaining drawdown capacity: "
        f"{mandate.max_drawdown_pct - portfolio.current_drawdown_pct:.1f}%\n"
    )
```

**Effort:** Small — the portfolio fetch already exists for Room; just wire it to 1-on-1.
**Risk:** Low — additive only.

---

## Gap 4 — Risk Debators run in parallel, prompt implies they see each other

**Severity: Low | Type: Design**

### What the prompts say
Aggressive Debator's inputs list "Conservative Debator's argument" and "Neutral
Debator's argument". Same for the other two.

### What Room does
All 3 Debators are dispatched in parallel within Phase 5. None sees the others'
outputs — they generate independently.

### Impact
Minor. The debate is less interactive than the prompt implies (Debators don't
actually respond to each other — they respond to the Trader's proposal
independently). The PM then synthesises all three. The educational value is
preserved; the framing is slightly misleading.

### Fix option A — Run Debators sequentially (highest fidelity)
Run Aggressive first, Conservative reads Aggressive's output, Neutral reads both.

**Effort:** Medium — changes Room streaming order and transcript logic.
**Risk:** Adds latency (3 sequential LLM calls instead of parallel).

### Fix option B — Update prompt framing (recommended for now)
Change the Debator prompt `Inputs` section: replace "Aggressive/Conservative/
Neutral Debator's argument" with "The Risk Debate (you and your two counterparts
respond independently to the Trader's proposal; the PM synthesises all three)."

**File:** `content/agents/aggressive_debator.md`, `conservative_debator.md`,
`neutral_debator.md`

**Effort:** Trivial — 3 prompt files, one section each.
**Risk:** Zero.

**Recommendation:** Apply Fix B now. Fix A (sequential) is a nice-to-have for v1.0
if latency budget allows.

---

## Gap 5 — News Analyst and Social Media Analyst: synthetic data in 1-on-1

**Severity: Low | Type: Structural**

### What the prompts say
News Analyst: "Real-time news feeds (Reuters, Bloomberg, FT, regional sources)",
"Macro indicator calendar", "Earnings calendar", "Regulatory filings".

Social Media Analyst: Reddit, Twitter/X, StockTwits, Google Trends, Discord.

### What 1-on-1 delivers
Nothing. The 6-field yfinance block has no news or sentiment data.

### Why this is structural
There is no news feed API integrated. StockTwits/Reddit APIs are not in the stack.
Adding them is a future feature (likely tied to a Paid tier — real news data has
licensing cost). The Room provides synthetic placeholders (`catalyst`, `sentiment_tone`)
which the 1-on-1 path doesn't even pass through.

### Minimal fix (no new data sources required)
Append the same synthetic narrative block to the 1-on-1 system prompt for these
two agents, so they have at least the same scenario context as their Room counterparts.

**File:** `backend/app/services/agent_prompts.py`

```python
if agent_id in (AgentId.NEWS_ANALYST, AgentId.SOCIAL_MEDIA_ANALYST):
    profile = _profile_for_ticker(ticker)  # reuse room_runner's synthetic profile
    system_prompt += f"\n\nSIMULATION CONTEXT — {ticker}:\n"
    if agent_id == AgentId.NEWS_ANALYST:
        system_prompt += (
            f"Recent catalyst: {profile['catalyst']}\n"
            f"Forward catalyst: {profile['forward_catalyst']}\n"
            f"Macro tone: {profile['macro_tone']}\n"
            f"Fed stance: {profile['fed_tone']}\n"
            "(These are simulation scaffolding, not real news. Treat as a scenario.)"
        )
    else:  # social_media_analyst
        system_prompt += (
            f"Retail sentiment: {profile['sentiment_tone']} ({profile['sentiment_score']}σ)\n"
            f"Mention trend: {profile['mention_trend']}\n"
            f"Influencer read: {profile['influencer_take']}\n"
            f"Pattern: {profile['pattern']}\n"
            "(These are simulation scaffolding, not real social data.)"
        )
```

**Effort:** Small — reuse existing `_profile_for_ticker()` (already in room_runner).
**Risk:** Low. Requires importing `_profile_for_ticker` into agent_prompts — minor coupling.

---

## Gap 6 — Bull/Bear Researchers: Decision Journal not injected

**Severity: Low | Type: Accidental**

### What the prompts say
"Historical context from the Decision Journal."

### What's actually injected
Nothing. The Journal is loaded for the Concierge (via `load_concierge_context()`)
but not for the trading agents.

### Impact
Bull/Bear can't reference the user's prior decisions on this ticker (e.g., "last
time you were in AAPL you sold at the first sign of weakness — worth considering
that pattern"). Educational value is reduced.

### Fix
**File:** `backend/app/services/room_runner.py` — when building the Room context,
fetch the last 3 Journal entries for this ticker and append to the Bull + Bear
system prompts only (to keep prompt length manageable for other agents).

**Effort:** Medium — Journal query + selective prompt injection.
**Risk:** Low — additive. Journal query already exists (used by Concierge).
**Priority:** Post-alpha (nice-to-have for educational depth).

---

## Summary: action priority

| # | Gap | Severity | Type | Recommended action | Effort |
|---|---|---|---|---|---|
| 1 | Market Analyst: no technicals in 1-on-1 | High | Accidental | Add agent-aware data block | Small |
| 2 | Trader: runs before Risk Debators | High | Accidental | Phase reorder (v1.0) + prompt patch (now) | Medium / Trivial |
| 3 | Trader: no portfolio state in 1-on-1 | Medium | Accidental | Wire portfolio fetch to 1-on-1 | Small |
| 4 | Debators: parallel but prompt implies sequential | Low | Design | Update prompt framing | Trivial |
| 5 | News/Social: nothing in 1-on-1 | Low | Structural | Append synthetic context block | Small |
| 6 | Bull/Bear: no Journal history | Low | Accidental | Journal fetch in Room | Medium |

**Immediate actions (before next alpha build):**
- Apply Gap 2 prompt patch (`content/agents/trader.md`) — zero risk, closes misleading claim
- Apply Gap 4 prompt update (`aggressive_debator.md`, `conservative_debator.md`, `neutral_debator.md`)

**Alpha → Beta sprint:**
- Gap 1 (Market Analyst 1-on-1) — highest UX impact
- Gap 3 (Trader portfolio state)
- Gap 5 (News/Social context in 1-on-1)

**Post-beta:**
- Gap 2 phase reorder (architectural, needs test coverage)
- Gap 6 (Journal history for Bull/Bear)
