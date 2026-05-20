# Agent Academy

12 modules — one per agent. Completing a module unlocks that agent on the Floor (Earn Path).

The Academy is the bridge between *learning concepts* (Trading Fundamentals lessons) and *commanding a team* (using the 12 agents). Without it, a Floor Pass user has all the lessons but no way to use the team. The Academy is the unlock mechanism.

## What each module looks like

Each Agent Academy module is a 4-part flow:

```
1. READ (3-5 min)
   "Who is the Bear Researcher?"
   - Role description
   - What they do in a Room
   - What they don't do
   - Example reasoning excerpts
   
   ↓
   
2. EXPLAINER (2 min)
   Short animated explainer or video showing the agent in action.
   At alpha: an animated text + diagram walkthrough.
   At v1.0: optional video.
   
   ↓
   
3. PREDICT THE CALL (~5 min)        ← at v1.0; simpler at alpha
   The user is shown a real chart + financials + news.
   "What would the Bear Researcher say about this?"
   User writes their prediction.
   Then they see what the Bear actually said.
   The system scores their prediction quality.
   
   ↓
   
4. QUIZ (1-2 min)
   2-3 questions to confirm comprehension.
   Pass → agent unlocks.
   Fail → remedial walkthrough, then retry.
```

Total time per module: ~15 min. 12 modules × 15 min ≈ **3 hours of focused work** for the full Earn Path.

## Module ordering (recommended)

The Academy is non-linear — users can take modules in any order — but the recommended sequence is:

```
1.  Fundamentals Analyst          ← start here, easiest to grasp
2.  Market Analyst
3.  News Analyst
4.  Social Media Analyst
   (now have a "Partial Room" — can convene the 4 analysts only)
5.  Bull Researcher
6.  Bear Researcher  
7.  Research Manager
8.  Trader
   (now have everything except risk team — most decisions possible)
9.  Conservative Debator
10. Aggressive Debator
11. Neutral Debator
12. Portfolio Manager             ← end here — the gatekeeper
   (full team now active — Convene the Room available)
```

## "Partial Room" mode

If a user has unlocked at least 5 agents (minimum: Fundamentals, Market, Bull, Bear, PM), they can run a **Partial Room** — only their unlocked agents participate.

- Partial Rooms cost the same credits as full Rooms (LLM cost is similar — same orchestration)
- The verdict is clearly labelled "Partial Room — 5/12 agents"
- Concierge gently surfaces: "Unlock more agents to get a fuller picture"

This avoids the bad UX of "you can't do anything until you've finished all 12 modules" while still rewarding progression.

Below 5 unlocked: no Room available. The user can still do 1-on-1s with any unlocked agent.

## Module content per agent

Each module covers (at a minimum):

| Section | Content |
|---|---|
| **Who they are** | Role description, where they fit in the team |
| **Their inputs** | What data/tools they use |
| **Their outputs** | What they produce, in what format |
| **Their voice** | Tone, common phrasing patterns |
| **Their limits** | What they don't do (where to go for that instead) |
| **How they're personalised** | Which mandate fields shape their behaviour |
| **Common patterns** | What they say in bull markets vs bear markets vs sideways |
| **How to read them** | What to look for in their reasoning |
| **How to brief them** | Common Brief prompts users find useful |

## Predict the Call — design

The most distinctive Academy feature. At v1.0, every module includes a Predict the Call exercise:

```
┌─────────────────────────────────────────────────┐
│ PREDICT THE CALL — BEAR RESEARCHER              │
├─────────────────────────────────────────────────┤
│ Here's the situation:                           │
│                                                 │
│ Ticker:    NVDA                                 │
│ Price:     $152                                 │
│ P/E:       38                                   │
│ Q3 beat:   +4% revenue                          │
│ Macro:     Fed cut rates 25bps                  │
│ Sentiment: +1.3σ on r/investing                 │
│                                                 │
│ Your Bear Researcher's mandate: long-horizon,   │
│ moderate risk, halal-compliant.                 │
│                                                 │
│ What would the Bear say?                        │
│                                                 │
│ ┌─────────────────────────────────────────────┐ │
│ │ Type the Bear's top 2 risks...             │ │
│ └─────────────────────────────────────────────┘ │
│                                                 │
│ [I'm done]    [Show me what the Bear said]      │
└─────────────────────────────────────────────────┘
```

When the user submits, they see:
- What the Bear actually said
- A side-by-side comparison
- A score: how close was their prediction?
- Concierge offers: "Good read! You picked up the multiple-compression risk. The Bear also mentioned X you didn't catch — want to read more about that?"

This trains the user to *think like the agent* — which is the entire pedagogical goal.

**At alpha**: Predict the Call is a simpler "pick from 4 options" multiple-choice. The free-text version is v1.0.

## Quiz design

Pass criterion: ≥75% on a 3-question quiz.

| Tier | If user fails twice |
|---|---|
| **First fail** | Show remedial micro-lesson on the missed concept; retry quiz |
| **Second fail** | Concierge offers a 1-on-1 with the agent itself: "Try chatting with [Agent] for 2 minutes — they can help" |
| **Third fail** | Module marked "in progress, not yet passed" — user comes back later. No penalty. |

We never lock users out of progression. We slow them down.

## Skip Path

Subscribing (Trader or Floor Manager) unlocks all 12 agents immediately. The Academy stays available as optional content. Users who Skip Path get:

- A small ribbon: "Tip: complete the Academy to earn badges and stay unlocked even if you cancel."
- Academy badges show on profile (Phase 2 leaderboard relevance)
- Academy completion is a Bootcamp Graduate offer trigger (Phase 2): 25% off first year of Trader

The Earn Path and Skip Path are **not mutually exclusive** — most paying users will eventually complete the Academy for the badges and learning.

## What happens at trial expiry

Per the trial mechanics ([`docs/03_onboarding/flow.md`](../03_onboarding/flow.md)): if a user completes Academy modules during the 7-day Trader trial, those agents remain unlocked under Earn Path after the trial ends. This is the "we reward your investment" design.

## State tracking

```python
AcademyProgress(
    user_id: uuid,
    agent_id: str,
    started_at: datetime,
    completed_at: datetime | None,
    quiz_attempts: list[QuizAttempt],
    predict_the_call_results: list[PredictResult],
    badge_earned: bool,
    badge_earned_at: datetime | None,
)
```

Stored in Postgres. Per-agent per-user.

## Authoring at MVP

Each module is ~5,000–8,000 words of structured content. 12 modules × 6,000 words = 72,000 words. Claude writes all 12 at alpha; Saiful reviews. Translation to AR + MS happens at v1.0.

## Cross-references

- The dual-gating decision: [`dual_gating.md`](dual_gating.md)
- Per-agent details (used to seed module content): [`docs/02_agents/twelve_agents.md`](../02_agents/twelve_agents.md)
- Mandate overlays (used to explain "how this agent personalises"): [`docs/02_agents/mandate_overlays.md`](../02_agents/mandate_overlays.md)
