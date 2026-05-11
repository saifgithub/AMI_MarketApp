# Convene the Room

The flagship multi-agent debate session. All 12 agents run on a single ticker, producing a final verdict.

## What it is

A user selects a ticker and taps **Convene**. Over the next 30–60 seconds:
1. The 4 Analysts run in parallel — each producing a fact-base
2. Bull and Bear Researchers run in parallel — each building their case from the analysts' work
3. Research Manager synthesises Bull vs Bear
4. Trader proposes a specific trade
5. 3 Risk Debators argue (Aggressive, Conservative, Neutral)
6. Portfolio Manager runs compliance check + makes final call

The streaming reasoning is shown live (Matrix Console aesthetic). The final verdict card is saved to the Decision Journal.

## Triggers

A user can convene from:
- The **⬢ Convene** FAB on any screen
- Tap a ticker on the watchlist → "Convene the Room on this ticker"
- Tap a ticker in Concierge → Concierge offers Convene
- Schedule via Concierge (`convene_for_me`) — pre-paid, auto-runs at scheduled time
- Tap "Get a second opinion" on the trade ticket (pre-trade)

## Inputs

| Input | How obtained |
|---|---|
| Ticker | User-selected or auto-suggested (watchlist) |
| Mandate | From session state (always current) |
| Portfolio context | Current sim portfolio holdings + drawdown |
| Time horizon override (optional) | User can scope: "1 week" / "1 quarter" / "long-term" |
| Question (optional) | User can ask a specific question to focus the Room |

## Outputs

| Output | Description |
|---|---|
| **Verdict card** | Buy / Hold / Sell + sizing % + entry / target / stop + time horizon + 1-line rationale |
| **Full transcript** | Every agent's contribution, timestamped, role-colour-coded |
| **Decision Journal entry** | Permanent, replayable record |
| **Mandate compliance trace** | Which compliance checks were run, with results |
| **Credit ledger entry** | Credits debited for the run |

## Credit cost

| Tier | Per-Room cost (credits) | Reason |
|---|---|---|
| Floor Pass | 8 credits | Single round, cheap LLMs (Haiku / GPT-4o-mini / Gemini Flash) |
| Trader | 8 credits per Room | Single round, mid-tier LLMs (Sonnet / GPT-5.4-mini / Gemini 3 Pro) |
| Floor Manager | 25 credits per Room | Up to 3 debate rounds, premium LLMs (Opus / GPT-5.4 / Gemini 3 Ultra) |

Floor Pass and Trader differ in model tier (and therefore reasoning quality); both run a single round.

## The visualisation — what the user sees

### Alpha version (streaming text only)

```
┌──────────────────────────────────────────────────────┐
│ CONVENE  ›  NVDA  ›  v2025-11-12-14:32  ›  8 credits │
├──────────────────────────────────────────────────────┤
│                                                      │
│  ⬢ ANALYSTS                                          │
│  [FUNDAMENTALS] Q3 earnings beat by 4%. P/E now 38… │
│  [MARKET]       MACD bullish cross on weekly. Vol… │
│  [NEWS]         AI capex commentary from META…      │
│  [SOCIAL]       Sentiment +1.3σ on /r/inves…        │
│                                                      │
│  ⬢ RESEARCHERS                                       │
│  [BULL]   Strong fundamentals + technical break…    │
│  [BEAR]   Multiple compression risk if rates…       │
│  [RES-MGR] Synthesis: bullish bias, sized smaller…  │
│                                                      │
│  ⬢ EXECUTION                                         │
│  [TRADER] BUY 3% portfolio at $152. Stop $148…      │
│                                                      │
│  ⬢ RISK                                              │
│  [AGGRESSIVE]   Push to 5%. R:R is 3:1…             │
│  [CONSERVATIVE] 2% max. Earnings season risk…       │
│  [NEUTRAL]      3% looks right…                     │
│                                                      │
│  ⬢ VERDICT                                           │
│  [PM ◼ APPROVE]                                      │
│  BUY 3% AT $152  STOP $148  TARGET $172  HORIZON 6W│
│  Mandate check: PASS (halal: ✓, drawdown room: 24%) │
│                                                      │
│  [Save to Journal] [Open trade ticket] [Replay]      │
└──────────────────────────────────────────────────────┘
```

Each agent's line streams in real-time with a typewriter effect. The role-colour prefix (`[FUNDAMENTALS]` in cyan, `[BEAR]` in purple, etc.) makes who-said-what scannable.

### v1.0 version (animated visual deck)

Above the Matrix Console, a visual deck animates as the run progresses:
- Phase 1 — 4 cyan hex avatars pulse as Analysts speak
- Phase 2 — Bull and Bear face off across the screen, purple
- Phase 3 — Research Manager card slides in with synthesis
- Phase 4 — Trader card emerges in green
- Phase 5 — 3 amber Risk Debator hexes form a triangle, lines connecting them
- Phase 6 — PM verdict card slams down in the center, full screen, with the result

The animation is bookended by the Matrix Console transcript (always visible) — power users can collapse the visual deck and watch only the transcript.

## Multi-round debate (Floor Manager only)

For Floor Manager subscribers, the Room runs up to **3 rounds** instead of 1:

- **Round 1.** Standard sequence above.
- **Round 2.** Bull and Bear each get to respond to the *other's* round-1 argument. Research Manager reconsiders. Trader and Risk Debators iterate.
- **Round 3.** Final synthesis. PM verdict accounts for all 3 rounds.

Multi-round produces deeper, more nuanced verdicts at the cost of more LLM calls (hence Floor Manager only).

## Replay

Every Convene session is replayable from the Decision Journal:
- Stream the original transcript at original timing, or "fast" mode (instant)
- See which mandate version was in effect
- See which model tier was used
- View any user notes/tags

## Background scheduling (Concierge tool)

Floor Manager and Trader users can ask Concierge:

> *"Convene on TSLA, AMD, and AAPL tomorrow at 7am SGT. Use my morning briefing voice."*

Concierge:
1. Validates user has credits to cover all 3 (8 × 3 = 24 credits)
2. Schedules 3 background Room runs
3. At 7am: runs them, generates a combined audio briefing
4. Pushes notification: "Your team has 3 new reports."

## Failure modes

| Failure | Handling |
|---|---|
| LLM provider down | Auto-failover to backup provider via OpenRouter; user sees no impact |
| Insufficient credits | Pre-flight check; if user has no credits, show offer to buy a credit pack |
| Mandate prohibits all candidates | Research Manager outputs "PASS — nothing fits mandate today" — saved to Journal, credits *not* charged |
| One agent fails mid-run | Other agents continue; missing agent's slot shows "[Agent unavailable]"; Research Manager notes the gap |
| Network drop mid-run | LangGraph checkpoint resumes on reconnect; user picks up where the run left off |
| Compliance violation in user-coached agent | Trader/Researchers proceed as advocated; PM still rejects on violation — user learns *why* their coaching led to a violation |

## State persistence

Each Room run creates a record with:
```python
RoomRun(
    id: uuid,
    user_id: uuid,
    ticker: str,
    triggered_at: datetime,
    mandate_version: int,
    model_tier: "cheap" | "mid" | "premium",
    rounds: int,
    transcript: list[AgentMessage],  # ordered, all agent contributions
    verdict: Verdict,
    credit_cost: int,
    duration_seconds: float,
    status: "running" | "completed" | "failed" | "cancelled"
)
```

Stored in Postgres. The transcript is a JSONB column; if it gets large (Phase 2), we'd move to blob storage and reference by ID.

## Performance targets

| Phase | Target time |
|---|---|
| End-to-end Convene (single round, mid-tier) | 30–45 seconds |
| Multi-round Convene (3 rounds, premium) | 60–90 seconds |
| First token to user (perceived start) | < 2 seconds |
| Background Convene (Concierge-scheduled, batched overnight) | No user wait — push notification when done |
