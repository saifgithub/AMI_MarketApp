# 7-Day Trader Trial

Every new user gets a 7-day Trader-tier trial on first sign-up. No auto-bill.

## Trial activation

```
ACCOUNT CLAIMED (end of onboarding)
     ↓
Trader trial auto-activates
     ↓
trial.expires_at = now() + 7 days
plan = "trial_trader"
     ↓
User lands on Floor with all 12 agents unlocked
```

## What the trial includes

The user gets the **Trader tier experience** for 7 days:

- All 12 agents unlocked (Skip Path during trial)
- Ad-free
- Mid-tier AI models (Sonnet, GPT-5.4-mini, Gemini 3 Pro)
- 75 trial credits (= ~9 Rooms or 75 1-on-1s)
- 2 sim portfolios ($100K each)
- Voice morning briefing
- Unlimited 1-on-1s (within credit allowance)
- Unlimited Coach Your Agent edits
- Full Decision Journal history
- Assistant Concierge tools (scheduling, summaries, etc.)

The trial **does not include** Floor Manager features:
- Premium AI models (Opus / GPT-5.4 / Gemini 3 Ultra)
- Multi-round debate (only 1 round in trial Rooms)
- Real-time market data (15-min delayed during trial)
- Floor Manager–only future features

This is intentional — the trial lets users taste Trader, not the top tier. Floor Manager is for users who *want more* after Trader.

## No auto-bill

**Critical brand decision.** The trial does NOT auto-convert to a paid subscription on day 8. The user must explicitly choose to upgrade.

| Industry default | Our approach |
|---|---|
| Auto-bill on trial end (Apple/Google default) | **Opt-in to continue** — no surprise charges |
| Confusing cancellation flows | One-tap cancel; no friction |
| Hidden trial terms | Clear "7 days, then back to Floor Pass" messaging from day 1 |

This costs us some short-term conversion (some users would've forgotten and auto-billed). It earns long-term trust. AMI Trade users will tell their friends *"they don't try to trick you."*

## Day 8 — trial expiry

When the trial expires:

1. Push notification + email: *"Your trial ended. Here's where you stand."*
2. On next app open, a single-screen summary:

```
┌────────────────────────────────────────────────────────┐
│ YOUR 7-DAY TRADER TRIAL ENDED                          │
├────────────────────────────────────────────────────────┤
│ HERE'S WHAT YOU DID                                    │
│ • 3 Room sessions                                      │
│ • 12 1-on-1 chats                                      │
│ • Coached the Bear Researcher                          │
│ • Completed 2 Agent Academy modules                    │
│ • 6-day streak (still going!)                          │
├────────────────────────────────────────────────────────┤
│ EARNED & YOURS TO KEEP (free, forever)                 │
│ ⬢ FUNDAMENTALS ANALYST     unlocked via Module 1       │
│ ⬢ MARKET ANALYST           unlocked via Module 2       │
│ Coach edits on Bear Researcher — saved.                │
│ Your mandate — saved.                                  │
│ Your Decision Journal — accessible (last 30 days).     │
├────────────────────────────────────────────────────────┤
│ LOCKED (need Trader to keep using)                     │
│ ⬢ NEWS ANALYST                                         │
│ ⬢ SOCIAL MEDIA ANALYST                                 │
│ ⬢ BULL RESEARCHER                                      │
│ ⬢ BEAR RESEARCHER  (still keep your Coach edits!)      │
│ ⬢ RESEARCH MANAGER                                     │
│ ⬢ TRADER                                               │
│ ⬢ AGGRESSIVE / CONSERVATIVE / NEUTRAL DEBATORS         │
│ ⬢ PORTFOLIO MANAGER                                    │
├────────────────────────────────────────────────────────┤
│ WHAT NOW?                                              │
│                                                        │
│ Continue with Floor Pass — keep what you earned, free  │
│ [Continue free]                                        │
│                                                        │
│ Upgrade to Trader — keep all 12 agents, $14.99/mo     │
│ [Upgrade — see plans]                                  │
│                                                        │
│ Your Founders Pricing is still available:              │
│ 50% off for 12 months ($7.49/mo)                       │
│ [Claim Founders pricing]                               │
└────────────────────────────────────────────────────────┘
```

## Education-gate interaction

Per Saiful's decision: education gates work **normally during the trial**. If a user completes Agent Academy modules during the 7 days, those agents stay unlocked under Earn Path after trial ends.

In-trial prompt (day 3):

> *"Tip: complete the Agent Academy and your agents stay unlocked for free after your trial ends."*

This is the only direct in-product nudge about the dual-gating during the trial. It's brand-positive (honest) and converts BETTER long-term (users who *learn* + *trial* are stickier than users who just trial).

## State transitions

### Mandate persistence
- Mandate created during onboarding → persists indefinitely
- Coach Your Agent edits → persist indefinitely
- Decision Journal entries → persist (subject to tier caps post-trial)

### Sim portfolio
- 2 portfolios during trial
- At expiry: consolidates to 1 portfolio (Floor Pass limit)
- User picks which to keep; the other archives (data not deleted; readable in Journal but inactive)

### Credit balance
- 75 trial credits
- Unused balance is **lost** at expiry — credits don't carry over to Floor Pass
- The included 13 Floor Pass credits start fresh on the next monthly cycle

### Agent activation
- During trial: all 12 active (Skip Path mechanism)
- At expiry: agents revert based on `earn_path_completed_at`. Earn-Path-completed agents stay active; others lock.

## Resubscribing after expiry

If a user upgrades to Trader (paid) within the post-trial grace period (7 days after expiry):
- No re-trial — they've used theirs
- Founder pricing still applies if window is open
- Sim portfolio resumes from where it consolidated (no data loss)
- Coach edits, mandate, Decision Journal — all still there

If a user waits >7 days, then upgrades:
- Same as above (no re-trial), but the "transition" screen doesn't show
- Welcome-back tone: *"Welcome back. All 12 agents are working for you again."*

## Special cases

### Cancellation during trial
- User cancels before day 7 → trial ends immediately (server-side); user reverts to Floor Pass
- No charge ever incurred
- Concierge: *"Sorry to see you go. Your work is saved. Come back any time."*

### Trial conversion before day 7
- User upgrades to Trader (or Floor Manager) during trial → trial ends immediately
- Full paid subscription begins
- Any Founder / launch promo discounts apply

### Multiple devices
- Trial is per user account (not per device)
- Apple/Google/HMS receipt validation per RevenueCat handles cross-device entitlement state

### Anonymous session → account claim → trial
- The 24-hour anonymous session does NOT consume the trial
- Trial activates only after account is claimed
- A user can be in anonymous session for ~24 hours, then claim, then get a full 7-day trial

## Why 7 days

| Duration considered | Verdict |
|---|---|
| 3 days | Too short — users haven't formed a habit |
| **7 days** | ✓ Standard. Enough to complete several Academy modules + form a daily habit |
| 14 days | Too long — LLM cost exposure increases without proportional conversion improvement |
| 30 days | Apple/Google standard but reads as "they're desperate" for our category |

7 days is also the cadence of one full week of daily challenges — user gets the full streak experience.

## Cross-references

- Dual gating (Earn vs Skip): [`docs/04_education/dual_gating.md`](../04_education/dual_gating.md)
- Tier features: [`tiers_and_pricing.md`](tiers_and_pricing.md)
- Onboarding flow (sets up the trial activation): [`docs/03_onboarding/flow.md`](../03_onboarding/flow.md)
