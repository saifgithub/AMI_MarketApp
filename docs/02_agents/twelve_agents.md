# The 12 Agents

The 12 agents are powered by the [TradingAgents](https://github.com/TauricResearch/TradingAgents) framework (mounted at `/Volumes/Extreme Pro/TradingAgent/`). Their roles are inherited; their *behaviour for our users* is customised through:
- **Mandate overlays** (auto-derived, non-editable — see [`mandate_overlays.md`](mandate_overlays.md))
- **User overlays** (from Brief Your Agent — see [`brief_your_agent.md`](brief_your_agent.md))
- **Safety floor** (uncoachable, only on Portfolio Manager — see [`safety_floor.md`](safety_floor.md))

## The roster

| # | Agent ID | Display name | Family | Role color | One-line role |
|---|---|---|---|---|---|
| 1 | `fundamentals_analyst` | Fundamentals Analyst | Analyst | Cyan | Financials, intrinsic value, red flags |
| 2 | `market_analyst` | Market Analyst | Analyst | Cyan | Technicals (MACD, RSI, chart patterns) |
| 3 | `news_analyst` | News Analyst | Analyst | Cyan | Macro events, headline impact |
| 4 | `social_media_analyst` | Social Media Analyst | Analyst | Cyan | Sentiment, social mood |
| 5 | `bull_researcher` | Bull Researcher | Researcher | Purple | Builds the long case |
| 6 | `bear_researcher` | Bear Researcher | Researcher | Purple | Builds the short case (or "avoid" if long-only) |
| 7 | `research_manager` | Research Manager | Manager | Purple | Adjudicates Bull vs Bear, writes synthesis |
| 8 | `trader` | Trader | Execution | Green | Translates synthesis into a trade idea (size, timing) |
| 9 | `aggressive_debator` | Aggressive Debator | Risk | Amber | Argues for risk-on |
| 10 | `conservative_debator` | Conservative Debator | Risk | Amber | Argues for capital preservation |
| 11 | `neutral_debator` | Neutral Debator | Risk | Amber | Balances aggressive vs conservative |
| 12 | `portfolio_manager` | Portfolio Manager | Manager / Gatekeeper | Purple | Approves/rejects against mandate. Final call. |

Plus, distinct from the 12:

| Agent ID | Display name | Color | Role |
|---|---|---|---|
| `concierge` | AI Concierge | Pink | Personal assistant — lessons, journal, scheduling, product Q&A. Never trades. |

## Agent details

### 1. Fundamentals Analyst (cyan)

**Role.** Evaluates company financials and performance metrics. Identifies intrinsic value and red flags.

**Tools (from TradingAgents).** Financial statements (income, balance sheet, cash flow), earnings history, peer comparison, valuation models (DCF, multiples).

**Mandate sensitivity.**
- `horizon: long` → prioritises durable margins, FCF, balance-sheet strength
- `horizon: short` → de-prioritises (this agent's contribution is weighted lower in short-horizon Rooms)
- `halal: true` → applies Sharia compliance check on every candidate (interest-bearing instruments excluded, debt ratios checked, non-halal sectors filtered)
- `risk_score: 1–2` → emphasises capital preservation metrics
- `risk_score: 4–5` → emphasises growth and re-rating potential

**Typical 1-on-1 question.** *"Is NVDA expensive at these levels?"*

### 2. Market Analyst (cyan)

**Role.** Technical analysis. Patterns, indicators, momentum, volume.

**Tools.** Indicators (MACD, RSI, MA, Bollinger), pattern recognition, support/resistance, trend identification, volume analysis.

**Mandate sensitivity.**
- `path: active` → emphasises short-timeframe signals (intraday-to-weekly)
- `path: long_horizon` → emphasises monthly/quarterly trend
- `risk_score: high` → comfortable with breakout/breakdown setups
- `risk_score: low` → emphasises mean-reversion and clear levels

**Typical 1-on-1 question.** *"What does the chart on TSLA tell you?"*

### 3. News Analyst (cyan)

**Role.** Macro events, headline impact, regulatory news, earnings news.

**Tools.** Real-time news feeds, macro indicator calendar, earnings calendar.

**Mandate sensitivity.**
- `compliance flags` → filters relevant headlines (e.g., halal user gets flagged on news of newly-acquired conventional-finance subsidiaries)
- `path: long_horizon` → weights macro structural news higher than short-term reactions

**Typical 1-on-1 question.** *"What happened with the Fed announcement yesterday, and what does it mean for tech?"*

### 4. Social Media Analyst (cyan)

**Role.** Sentiment, social mood, retail-investor positioning.

**Tools.** Reddit (r/wallstreetbets, r/investing), Twitter/X cashtags, StockTwits sentiment, Google Trends.

**Mandate sensitivity.**
- `risk_score: 1–2` → down-weights /r/wallstreetbets-style noise heavily
- `risk_score: 4–5` → considers it as alpha source, with caveats
- `path: active` → uses sentiment for entry/exit timing
- `path: long_horizon` → uses sentiment for contrarian signal only

**Typical 1-on-1 question.** *"Is sentiment on AMC hot right now?"*

### 5. Bull Researcher (purple)

**Role.** Builds the long case. Synthesises analyst inputs into the strongest argument for going long.

**Behaviour.** Steelmans the buy thesis. Cites specific analyst evidence. Anticipates the Bear's counter-arguments.

**Mandate sensitivity.**
- `compliance` → does not advocate names from `ticker_blocklist`. Respects `halal`, `esg_lite`, `no_tobacco_alcohol_gambling`.
- `long_only: true` → standard mode
- `long_only: false` → may suggest pair trades (long X / short Y)

### 6. Bear Researcher (purple)

**Role.** Builds the short/avoid case. Synthesises analyst inputs into the strongest argument against the position.

**Behaviour.** Steelmans the sell/avoid thesis. Identifies risks the Bull is glossing over.

**Mandate sensitivity.**
- `long_only: true` → frames as *"avoid"* rather than *"short"*
- `long_only: false` → explicit short recommendations allowed
- Other compliance flags respected (will not advocate shorting an excluded sector if it would still violate flags)

### 7. Research Manager (purple)

**Role.** Adjudicates the Bull vs Bear debate. Writes the synthesis.

**Behaviour.** Reads both researchers' arguments. Weighs evidence. Identifies which is more compelling, on which dimensions, and *why*. Outputs a 3-part synthesis: (1) what we agree on, (2) what's in dispute, (3) recommended stance.

**Mandate sensitivity.**
- If both Bull and Bear produce ideas that violate compliance, returns *"PASS — nothing fits mandate today"*
- Synthesis tone respects `learning_style` (story-led for "story", terse for "quick")

### 8. Trader (green)

**Role.** Execution proposal. Translates the synthesis into a *specific* trade idea: instrument, side, size, entry, exit, time horizon.

**Behaviour.** Concrete and actionable. Numbers, not adjectives. Always specifies position size as a % of portfolio and tags it with risk-reward.

**Mandate sensitivity.**
- Size is constrained by `risk_score` (low risk = smaller sizes, high risk = bigger sizes within mandate)
- Position size never exceeds remaining drawdown capacity
- Respects `long_only` flag

### 9. Aggressive Debator (amber)

**Role.** Argues for risk-on positioning in the Risk Management debate.

**Behaviour.** Pushes for full mandate-allowed sizing, longer exposure, lower hedging. Cites opportunity cost of timidity.

**Mandate constraint (hard).** Cannot advocate a position whose downside profile exceeds `max_drawdown_pct`.

### 10. Conservative Debator (amber)

**Role.** Argues for capital preservation.

**Behaviour.** Pushes for smaller sizing, more hedging, faster exits. Cites downside scenarios.

**Mandate sensitivity.** `max_drawdown_pct` is the ceiling it works toward — for risk-score-1 users it argues toward zero drawdown.

### 11. Neutral Debator (amber)

**Role.** Balances Aggressive vs Conservative. Proposes the middle path.

**Behaviour.** Synthesises both extremes. Often the agent the Portfolio Manager weighs heaviest if Aggressive and Conservative are far apart.

### 12. Portfolio Manager (purple / gatekeeper)

**Role.** Final call. Approves or rejects the proposed trade.

**Behaviour.**
- Reviews Trader's proposal, Research Manager's synthesis, and the 3 Risk Debators' arguments
- Runs the **deterministic compliance-check function** against the user's mandate
- Issues a verdict: `APPROVE` / `REJECT` / `MODIFY-AND-APPROVE`
- Logs the verdict + full reasoning to the Decision Journal

**Mandate enforcement.** This is the gatekeeper. The **safety floor** lives here — see [`safety_floor.md`](safety_floor.md).

**Briefing.** Users can brief PM's *style* and *prioritisation* via Brief Your Agent. They **cannot** brief away the mandate-enforcement safety floor.

## Agent families & role colors (in product)

| Family | Color | Members | Hex token |
|---|---|---|---|
| **Analysts** | Cyan | Fundamentals, Market, News, Social Media | `--hex-cyan` |
| **Researchers + Managers** | Purple | Bull, Bear, Research Manager, Portfolio Manager | `--hex-purple` |
| **Risk Debators** | Amber | Aggressive, Conservative, Neutral | `--hex-amber` |
| **Execution** | Green | Trader | `--hex-green` |
| **Concierge** (separate, 13th) | Pink | Concierge | `--hex-pink` |

These colours are used consistently throughout the product:
- Agent hex avatar borders on the Floor home screen
- Chat bubble accent colour in 1-on-1 and Convene sessions
- Status dots
- Section headers in agent profile pages

## Agent activation model

All 12 agents are gated by tier + (when Earn Path ships) Agent Academy completion.

**Today (Alpha):** Activation state is computed by `backend/app/api/lessons.py::activations()` from the user's plan + completed lessons. The Earn-Path / Skip-Path / trial-bridging mechanics are documented as the intended design; what's actually wired is the plan-gated unlock. See [`docs/04_education/dual_gating.md`](../04_education/dual_gating.md) for the full intended mechanics.

**Intended end state:**
- **Floor Pass (free) → Earn Path:** Complete the corresponding Agent Academy module → agent activates.
- **Trader / Floor Manager → Skip Path:** Subscribe → all 12 agents instantly active.
- **During 7-day Trader trial:** All 12 unlocked Skip-Path-style. If user completes Academy modules during trial, those agents stay unlocked on Earn Path after trial expires.

## Mapping to TradingAgents codebase

| Our agent ID | TradingAgents file |
|---|---|
| `fundamentals_analyst` | `tradingagents/agents/analysts/fundamentals_analyst.py` |
| `market_analyst` | `tradingagents/agents/analysts/market_analyst.py` |
| `news_analyst` | `tradingagents/agents/analysts/news_analyst.py` |
| `social_media_analyst` | `tradingagents/agents/analysts/social_media_analyst.py` |
| `bull_researcher` | `tradingagents/agents/researchers/bull_researcher.py` |
| `bear_researcher` | `tradingagents/agents/researchers/bear_researcher.py` |
| `research_manager` | `tradingagents/agents/managers/research_manager.py` |
| `trader` | `tradingagents/agents/trader/trader.py` |
| `aggressive_debator` | `tradingagents/agents/risk_mgmt/aggressive_debator.py` |
| `conservative_debator` | `tradingagents/agents/risk_mgmt/conservative_debator.py` |
| `neutral_debator` | `tradingagents/agents/risk_mgmt/neutral_debator.py` |
| `portfolio_manager` | `tradingagents/agents/managers/portfolio_manager.py` |

**Status:** This mapping is the intended Beta+ end state. **Alpha does not call TradingAgents at runtime** — each agent's behaviour is driven by a deterministic prompt in `backend/app/services/agent_prompts.py` running through the LLM gateway (on-prem vLLM Gemma 4 31B today). The `tradingagent_integration.md` doc describes the planned swap-in; the actual integration lands when the Beta cloud-migration stream picks it up. See [`docs/08_tech/tradingagent_integration.md`](../08_tech/tradingagent_integration.md).

---

## Not yet delivered

- **Agent Academy modules** (Earn Path mechanics). `lessons` table + activation tracking exist; per-agent Academy module content + the unlock event don't. See `docs/04_education/dual_gating.md` for the design.
- **Live TradingAgents integration.** Alpha uses our own prompt+gateway pipeline; the TradingAgents library is a Beta+ swap. The mapping table above is forward-looking.
- **Per-agent activation state surfaced via `/v1/agents`** (BL7). Mobile currently uses a client-side 12-agent manifest + `/v1/lessons/activations/{u}` for state.
