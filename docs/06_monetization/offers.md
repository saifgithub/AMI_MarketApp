# Offers & Promos

Same USD list price globally. Offers adjust regionally and over time.

## Launch offers (5 active at v1.0)

These 5 offers ship at v1.0 public launch. Three more (Student, Reactivation, Bootcamp Graduate) ship Phase 2.

### 1. Founders' Pricing

| Aspect | Detail |
|---|---|
| **Who** | First 10,000 paying subscribers |
| **What** | 50% off either paid tier for 12 months |
| **Trader at Founder price** | $7.49/mo (instead of $14.99) |
| **Floor Manager at Founder price** | $17.49/mo (instead of $34.99) |
| **Mechanic** | Auto-applied on first paid subscription within the founder window |
| **Founder window closes** | When 10,000th paid sub is created |
| **At year 2** | Regular pricing applies. Sticker shock prevented by clear messaging in month 11. |
| **Badge** | Permanent "Founder" badge on user profile |
| **Why it matters** | Reward early adopters publicly. Generates social proof. Builds the most loyal cohort. |

### 2. Launch-Country Promo

| Aspect | Detail |
|---|---|
| **Who** | Users in MY / SA / ID (initially) — any country where soft purchasing-power adjustment is needed |
| **What** | 30% off first 6 months of either paid tier |
| **Mechanic** | Geo-IP detected at sign-up; applied automatically if eligible |
| **Why** | Soft PPP adjustment without lowering global anchor. Critical for Malaysia (PPP burden 4× US) |
| **At month 7** | Regular pricing — user is reminded at month 6 |
| **Stackable?** | Not with Founders (Founders is better) — system picks the user's best offer |

### 3. Ramadan Promo

| Aspect | Detail |
|---|---|
| **Who** | Users in Muslim-majority markets, during Ramadan |
| **What** | 40% off annual upgrade (one-time, during Ramadan window) |
| **Mechanic** | Push + email + in-app banner during Ramadan; one-tap to upgrade with promo |
| **Why** | Cultural alignment. Halal-screening differentiator gets real airtime. Strong earned-media potential. |
| **At v1.0** | Active if launch is within Ramadan window; else activates at next Ramadan |
| **Brand voice** | Respectful, never opportunistic. Marketing copy reviewed by AR-native team. |

### 4. Annual Launch Promo

| Aspect | Detail |
|---|---|
| **Who** | All users, limited time at v1.0 launch |
| **What** | 40% off first-year annual on either paid tier |
| **Trader annual at promo** | $77.40 (instead of $129) — = $6.45/mo |
| **Floor Manager annual at promo** | $179.40 (instead of $299) — = $14.95/mo |
| **Duration** | First 30 days post-launch |
| **Mechanic** | Banner on splash + Wallet screen; one-tap to upgrade |
| **Why** | Drives commitment + cash up front; first 12 months of LLM cost is the highest-risk period for us |

### 5. Referral

| Aspect | Detail |
|---|---|
| **Who** | Any paying user |
| **What** | Refer 3 friends who sign up + complete onboarding → 1 free month Trader |
| **Friend reward** | 30 bonus credits (worth $3) on their account, regardless of plan |
| **Mechanic** | Unique share link from user profile; tracked via attribution (AppsFlyer Phase 2) |
| **Why** | Two-sided, accretive. Lowest-cost user acquisition channel. |

## Phase 2 offers

### 6. Student Discount

| Aspect | Detail |
|---|---|
| **Who** | Verified university students (.edu email or SheerID partnership) |
| **What** | 50% off Trader, 30% off Floor Manager — perpetual while student-verified |
| **Mechanic** | SheerID integration verifies status annually |
| **Why** | Captures future-LTV cohort cheaply. They graduate, they stay (often at higher tier). |

### 7. Reactivation

| Aspect | Detail |
|---|---|
| **Who** | Lapsed paying users (cancelled 60–180 days ago) |
| **What** | 50% off for 3 months |
| **Mechanic** | Email + push at 60, 90, 120 days post-cancellation; in-app banner on re-open |
| **Why** | Cheaper to win back than to acquire new. |

### 8. Bootcamp Graduate

| Aspect | Detail |
|---|---|
| **Who** | Users who complete all 12 Agent Academy modules on Floor Pass |
| **What** | 25% off first year of Trader |
| **Mechanic** | Triggered on 12th module completion; offer banner appears in next session |
| **Why** | Converts the highest-engagement free cohort at peak motivation. |

## Mechanics of "best offer wins"

When multiple offers could apply (e.g., Founders + Launch-Country), the system applies whichever is better for the user.

```python
def resolve_active_offer(user, plan) -> Offer | None:
    candidates = list_eligible_offers(user, plan)
    if not candidates:
        return None
    return max(candidates, key=lambda o: o.user_savings_per_year)
```

This is shown transparently:

> *"Your best available offer: Founders' Pricing (50% off for 12 months)."*

Users can see all offers they qualify for in **Wallet & Plan → Available Offers**.

## Offer schema

```python
Offer(
    id: str,
    type: enum,
    discount_pct: int,            # 0-100
    discount_duration_months: int | None,  # None = forever
    target_tier: Plan,
    eligibility: Eligibility,     # geo, cohort, prior-state, time-window
    starts_at: datetime,
    ends_at: datetime | None,
    max_redemptions: int | None,  # for Founders (10K cap)
    stackable_with: list[str],    # offer IDs that can stack (rare)
)
```

Offers are server-controlled — we can create new ones, end them, or modify eligibility without app updates.

## No dark patterns

Things we explicitly do not do:
- No "ends in 4 minutes!" fake urgency
- No pre-checked boxes on annual auto-renewal
- No hidden trial auto-bills (our trial is opt-in-to-continue, not opt-out)
- No upsell ads inside agent conversations
- No drip-drip discounts that train users to never pay full price

This is short-term less optimal. Long-term, it's how we build a brand people trust with their financial education.

## Cross-references

- Tier pricing: [`tiers_and_pricing.md`](tiers_and_pricing.md)
- Trial mechanics: [`trial.md`](trial.md)
- Marketing copy and brand voice: [`docs/00_overview/brand_and_glossary.md`](../00_overview/brand_and_glossary.md)
