# Credits

The metered LLM-operation system. 1 credit ≈ $0.10 retail value.

## Why credits

LLM cost is real and varies by operation type. Per-user-per-month flat-rate doesn't fit:
- A user who runs 50 Rooms/month costs us $150 in LLM calls
- A user who runs 2 Rooms/month costs us $6
- Same monthly fee subsidises the heavy user, overcharges the light user

Credits fix this. The base subscription includes a monthly credit allowance sized for typical use. Heavy users buy more.

## Operation costs

| Operation | Credits | Why |
|---|---|---|
| **1-on-1 chat** | 1 | One agent, short context, single LLM call thread |
| **Basic Room** (Floor Pass / Trader, 1 round) | 8 | 12 agents × short reasoning. ~$0.80 retail. |
| **Premium Room** (Floor Manager, multi-round) | 25 | 12 agents × 2–3 rounds × premium model. ~$2.50 retail. |
| **Brief Your Agent session** (Floor Pass overage only) | 2 | Mid-length conversation. Trader+ get unlimited free. |
| **Daily Challenge** | 0 | Free, generated once per locale per day, cached |
| **Lessons + AI-tutor wrapper** | 0 | Cached per (lesson, learning_style, locale, top compliance flags) tuple |
| **Quizzes + remedial lessons** | 0 | Cheap model, cached. |
| **Mandate Drift Alert** | 0 | Background check, no LLM per user |
| **Morning briefing** | 0 | Pre-generated overnight, batched, cached server-side |
| **Mandate edit / audit** | 0 | Deterministic — no LLM |
| **Concierge Q&A / lesson routing / search** | 0 | Always free |

Why some things are free even though they cost LLM compute:
- **Cached operations**: lessons + briefings hit the same cache key for many users
- **Batched operations**: overnight briefings run for many users at once (cheap per user)
- **Educational operations**: lessons, daily challenges, quizzes — we never meter learning
- **Concierge product help**: it's the navigation layer; metering would feel hostile

## Monthly inclusions per tier

| Tier | Credits/mo | Equivalent retail value |
|---|---|---|
| Floor Pass | 13 (= 5 1-on-1s + 1 Room) | $1.30 |
| Trader | 150 | $15 |
| Floor Manager | 500 | $50 |

**The included credits in Trader / Floor Manager exceed the subscription's $-value at retail.** This is intentional — most users won't use their full allowance, and we make money on the rolls. Heavy users buy packs.

Credits **reset monthly** (do not accumulate). This prevents hoarding and keeps the LLM-cost forecast predictable.

## Credit pack pricing

One-time IAP purchases:

| Pack | Price | Credits | Per-credit | Volume discount |
|---|---|---|---|---|
| Starter | $4.99 | 60 | $0.083 | — |
| Standard | $19.99 | 300 | $0.067 | 20% off |
| Power | $49.99 | 850 | $0.059 | 30% off |

Available to all tiers (yes, Floor Pass users can buy credits too).

## Credit ledger

Every credit transaction is recorded:

```python
CreditTransaction(
    id: uuid,
    user_id: uuid,
    type: "monthly_grant" | "purchase" | "spend" | "refund" | "founder_grant" | "streak_bonus" | "referral_reward",
    amount: int,             # positive for credits in, negative for spend
    balance_after: int,
    operation_ref: str | None,  # links to Room run / 1-on-1 session / etc.
    created_at: datetime,
)
```

User can view the ledger in **Wallet & Plan → Usage**:

```
─── CREDIT USAGE — November 2026 ───

Starting balance      150
Streak bonus +5         5     (Nov 1, 30-day streak)
Convene NVDA          -8     (Nov 2)
1-on-1 Bear           -1     (Nov 2)
Convene TSLA          -8     (Nov 3)
...
─────────────────────────
Current balance       127
```

## When credits run out

If a user has 0 credits and tries an operation:

```
┌──────────────────────────────────────────────┐
│ Out of credits                               │
│                                              │
│ You've used your 150 credits this month.     │
│ Next refill in 11 days.                      │
│                                              │
│ Options:                                     │
│ • Buy a pack ($4.99 / $19.99 / $49.99)       │
│ • Try Brief Your Agent (no credits needed)   │
│ • Wait for next month's refill               │
│                                              │
│ [Buy credits]   [Maybe later]                │
└──────────────────────────────────────────────┘
```

No surprise charges. No "you've gone over" silent burns. The transaction is blocked until the user explicitly buys.

## Pre-flight credit check

Every credit-charged operation runs a pre-flight check:
1. Read user's current balance
2. Check operation cost vs balance
3. If insufficient: show the out-of-credits modal (above)
4. If sufficient: proceed; debit AFTER the operation completes successfully

If an operation fails partway (e.g., LLM provider error), credits are refunded automatically.

## Free 1-on-1 / Free Room mechanics (Floor Pass)

Floor Pass gets a small monthly allowance even with 0 credit balance:
- **5 free 1-on-1s per month** (worth 5 credits)
- **1 free Room per month** (worth 8 credits)

These are tracked separately from the regular credit balance. Reset on the user's monthly anniversary.

UI shows clearly:
```
This month:
• Free 1-on-1s remaining: 2 of 5
• Free Room remaining:    1 of 1
• Credit balance:         0
```

## Why credits aren't "tokens"

We use "credits" — not "tokens" — even though the underlying cost driver is LLM tokens. Reasons:
- Tokens has a specific technical meaning users don't share
- Credits maps cleanly to "money I can spend"
- AMI brand voice prefers concrete language over jargon

Internal docs and code can say "tokens" where relevant. User-facing UI says **credits**.

## Cross-references

- Tier inclusions: [`tiers_and_pricing.md`](tiers_and_pricing.md)
- Unit economics (LLM cost vs credit revenue): [`unit_economics.md`](unit_economics.md)
- RevenueCat IAP integration: [`docs/initial_specs/08_tech/payments.md`](../08_tech/payments.md)
