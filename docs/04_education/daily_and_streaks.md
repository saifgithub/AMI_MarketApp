# Daily Challenges, Streaks & Reputation

The retention loop. Always free. No gambling-loop psychology.

## Daily Challenges

A single bite-size scenario per day. Same challenge for everyone in the same locale on the same day (avoids confusion, easier to discuss). Generated server-side overnight by the cheap-tier LLM.

### Challenge types

| Type | Example |
|---|---|
| **"Predict the Call"** | "Here's the data on AAPL. What would the Bear Researcher say?" |
| **"Read the chart"** | "Here's NVDA's daily chart. What's the Market Analyst's setup?" |
| **"Spot the violation"** | "This trade was rejected by PM. Why? Pick the violation." |
| **"Match the agent"** | "Which of the 12 agents would say this exact line?" |
| **"What's missing?"** | "This Room verdict looks complete. But which agent's input is missing?" |

### Scoring

Each challenge has 3 ways to score:

| Result | Streak impact | Reputation |
|---|---|---|
| **Got it right** | Streak +1 | +5 reputation points |
| **Got it close** (partial credit) | Streak +1 | +2 points |
| **Got it wrong but tried** | Streak +1 | +1 point |
| **Skipped** | Streak unchanged | 0 points |

**Critical:** the streak counts *trying*, not *getting it right*. We want users to come back daily, not to feel punished for being wrong. This is the anti-gambling-loop design.

### Daily delivery

- Available 24 hours per challenge
- New challenge appears at user's local midnight
- Reminder push (paid tier) or email (free) at user's preferred time

## Streaks

A streak counts consecutive days the user engaged with a daily challenge OR completed a lesson OR ran an agent interaction.

| Streak length | Reward |
|---|---|
| 7 days | "Week One" badge + 5 bonus credits |
| 30 days | "Month Strong" badge + 25 bonus credits |
| 100 days | "Centurion" badge + 100 bonus credits |
| 365 days | "Marathoner" badge + permanent profile flair + 500 bonus credits |
| 1000 days | Custom hex profile mark + special status (we'll see) |

### Streak-loss rules

| Event | Effect |
|---|---|
| Missed a day | Streak ends. Show "your streak is over — start a new one tomorrow." No shaming. |
| Pre-emptive freeze | Floor Manager perk: 2 freezes/year — pause your streak for a single day (e.g., travel) |
| App outage | Auto-extends streaks by the outage duration |
| Locale change | Streak continues — daily challenge is replaced by user's new locale |

## Reputation

A non-monetary score that captures *reasoning quality*. Earned through:

| Activity | Reputation |
|---|---|
| Daily challenge — right | +5 |
| Daily challenge — close | +2 |
| Daily challenge — attempted | +1 |
| Lesson completed | +3 |
| Agent Academy module completed | +20 |
| Quiz passed first try | +5 |
| Predicted an agent's call correctly | +10 |
| Decision Journal entry with self-reflection note | +2 |
| Mandate edit | 0 (not gamified) |
| Sim P&L | **0 — explicitly not counted** |

**Why P&L doesn't count toward reputation.** This is critical. Counting P&L would:
- Encourage risk-seeking (chase higher-variance for higher score)
- Penalise conservative users (who are the lowest-risk cohort but might not have highest returns)
- Recreate gambling-loop dynamics we explicitly want to avoid

Reputation measures *the quality of your reasoning*, not *the outcome of your luck*.

### Reputation tiers (informational, no functional gate)

| Reputation | Tier name |
|---|---|
| 0–100 | Apprentice |
| 100–500 | Analyst |
| 500–2,000 | Trader (yes, same word as plan — that's intentional, the plan tier and reputation tier reinforce each other) |
| 2,000–10,000 | Senior |
| 10,000+ | Floor Veteran |

These are visible on the user's profile and (Phase 2) on the reasoning-quality leaderboard.

## Badges

Hex-clipped, role-colour-coded. Visible on profile and (Phase 2) on shared journal entries.

| Badge | How to earn |
|---|---|
| **Bear-Whisperer** | Correctly predicted the Bear's call 10 times |
| **Bull Run** | Correctly predicted the Bull's call 10 times |
| **Mandate Keeper** | Zero PM rejections for 30 consecutive days |
| **Convener** | Ran 50 Room sessions |
| **Briefer** | Successfully briefed 5+ agents |
| **Halal Veteran** | 100 days as a halal-mandated user |
| **Long Game** | 1-year streak on long_horizon path |
| **Risk Manager** | Triggered PM-veto, then correctly responded by reducing position |
| **Polyglot** | Used the app in 2+ languages |
| **Founder** | Joined during the Founders cohort (first 10K) |
| **Academy Graduate** | Completed all 12 Agent Academy modules |
| **Conservative Streak** | Stayed within 50% of max_drawdown_pct for 90 days |
| **Diversifier** | Held 8+ positions, none > 20%, for 30 days |

### Locked badges

Some badges are visible-but-locked, with a description hint. Encourages collection without making goals opaque.

## Daily challenge generation (technical)

Overnight, the system:

1. Picks a challenge type (rotates through the 5)
2. Picks a relevant ticker (from the news / earnings calendar / sentiment heat)
3. Generates the challenge in EN
4. Translates to AR and MS (v1.0+)
5. Caches the challenge for all users in each locale
6. Schedules delivery push at each user's preferred time

Cost: ~$0.05 per locale per day. Negligible at any scale.

## What we explicitly DON'T do

| Anti-pattern | Why we don't do it |
|---|---|
| **Loss streaks** | Punishing missed days = shaming = churn |
| **P&L leaderboards** | Encourages gambling. See reputation rationale above. |
| **Rewarded video ads for streak freezes** | User decision: "not a game." |
| **Pop-up "claim your reward!" psychology** | Cheap, generic. Doesn't fit AMI brand voice. |
| **Daily login bonuses** | Trains transactional habit, not learning habit. |
| **Skill-based gambling mechanics** | Out of scope by design. |

The daily and streak system is **anti-addictive by construction**. We want users who come back because the agents add value, not because they're trapped in a loop.

## Cross-references

- Tier differences (paid streak freezes etc.): [`docs/06_monetization/tiers_and_pricing.md`](../06_monetization/tiers_and_pricing.md)
- Reasoning-quality leaderboard (Phase 2): [`docs/01_product/core_loop_and_features.md`](../01_product/core_loop_and_features.md)
