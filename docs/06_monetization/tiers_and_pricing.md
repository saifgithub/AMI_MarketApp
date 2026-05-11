# Tiers & Pricing

Three tiers. Same USD list price globally. Promotions adjust regionally and over time.

## The three tiers

| Axis | **Floor Pass** *(ads)* | **Trader** *($14.99/mo / $129/yr)* | **Floor Manager** *($34.99/mo / $299/yr)* |
|---|---|---|---|
| **Ads** | Yes (see [`ads.md`](ads.md)) | None | None |
| **Agent unlock** | Earn Path only (Academy modules) | Skip Path — all 12 instant | Skip Path — all 12 instant |
| **AI model tier** | Cheap/fast (Haiku, GPT-4o-mini, Gemini Flash) | Mid (Sonnet, GPT-5.4-mini, Gemini 3 Pro) | Premium (Claude Opus, GPT-5.4, Gemini 3 Ultra) |
| **Included credits/mo** | 13 credits (1 free Room + 5 free 1-on-1s) | **150 credits** (~10 Rooms or ~150 1-on-1s) | **500 credits** (~20 premium Rooms + unlimited 1-on-1s) |
| **Debate rounds in Room** | 1 | 1 | Up to 3 |
| **Market data** | 15-min delayed | 15-min delayed | Real-time (when phased in, v1.1+) |
| **Sim portfolios** | 1 ($10K, monthly reset) | 2 ($100K, reset on demand) | 5 ($1M, reset on demand) |
| **Decision Journal** | Last 30 days | Unlimited + search + tagging | Unlimited + search + tag + export (CSV / PDF) |
| **Coach Your Agent** | 3 edits per agent, lifetime | Unlimited, 20-version history | Unlimited, infinite history, diff viewer, Raw Mode |
| **Concierge** | Q&A + lesson routing (unlimited free) | + Assistant tools (schedule, reminders, journal summary, mute) | Same as Trader |
| **Morning briefing** | Text-only, email | Text + voice TTS, push + email + in-app | Text + premium voice + personalised analyst commentary |
| **Mandate Drift Alerts** | Weekly digest (email) | Daily (push + email) | Real-time + tunable thresholds |
| **Mandate complexity** | Full (basic + advanced) — **never gated** | Same | Same |
| **Languages** | All available — **never gated** | Same | Same |
| **Halal/Sharia screening** | **Always free** | Same | Same |
| **Lessons + Daily Challenges + Agent Academy** | All free, unlimited | Same | Same |
| **Support** | Concierge only | Concierge + standard email support | Concierge + priority email support (24h SLA) |
| **Leaderboard eligibility** (Phase 2) | View only | Eligible | Eligible + verified badge |
| **Streak freezes** (Phase 2) | None | 1 per year | 2 per year |
| **Themes / cosmetics** (Phase 2) | Default dark hex | Default + 2 alt palettes | Default + all palettes + custom hex |

## Pricing details

```
                              Monthly        Annual          Annual effective
  Floor Pass                  $0             $0              —
  Trader                      $14.99         $129            $10.75/mo  (28% off monthly)
  Floor Manager               $34.99         $299            $24.92/mo  (29% off monthly)

  Credit packs (one-time):    Starter $4.99 → 60 credits ($0.083/credit)
                              Standard $19.99 → 300 credits ($0.067/credit)
                              Power $49.99 → 850 credits ($0.059/credit)
```

## Why these prices

| Argument | Detail |
|---|---|
| **Trader matches Finelo head-on** | $14.99 = Finelo's tier-1. Same price, demonstrably more product. Marketing: *"Same price as Finelo. 12 AI analysts instead of 1 chart tool."* |
| **Inside the consumer ed/AI band** | Duolingo Super $13, Skillshare $14, MasterClass $15, ChatGPT Plus $20. Users have internalised $13–20 as "fair monthly cost for premium ed/AI." |
| **Floor Manager at 2.3× the Trader tier** | Standard premium multiplier. Spotify Family is 2× Solo; Netflix Premium is 2× Basic; Adobe All-Apps is 3× Photography. 2.3× signals "premium" without gouging. |
| **Annual discount ~28%** | Industry norm 20–35%; we're at the higher end to drive commitment. Annual cash up front buys us LLM-cost runway. |
| **Credit packs price-decreasing per volume** | Standard SaaS — bigger commitment, better unit price. |

See [`unit_economics.md`](unit_economics.md) for the cost-revenue math per tier.

## What the same USD price means by market

Same list, different *effective* burden:

| Market | $14.99 in local | % of avg monthly post-tax income (rough) |
|---|---|---|
| US | $14.99 | ~0.3% |
| Saudi Arabia | SAR 56 | ~0.5% |
| Malaysia | MYR 70 | ~1.2% — meaningful |
| Indonesia (Phase 2) | IDR 240K | ~2.5% — steep |

Malaysia and Indonesia will need the Launch-Country Promo doing real work for conversion. See [`offers.md`](offers.md#launch-country-promo).

## Tier in the product (consistent badges)

| Tier | Badge color | In-product persona narrative |
|---|---|---|
| **Floor Pass** | Slate | *"You're on the floor. Learn the room. Earn your team."* |
| **Trader** | Hex-blue (`#3b82f6`) | *"Licensed. All 12 analysts working for you."* |
| **Floor Manager** | Purple (`--hex-purple`) | *"You run the floor. Premium intelligence, real-time."* |

Upgrade prompts use this metaphor:
- *"Get your Trader's License"* — Floor Pass → Trader
- *"Take command of the floor"* — Trader → Floor Manager

## Payment infrastructure

| Platform | IAP system | Wrapped by |
|---|---|---|
| iOS | Apple IAP | RevenueCat |
| Android-GMS | Google Play Billing | RevenueCat |
| Android-HMS (v1.1) | HMS IAP | RevenueCat (via their HMS support) |
| Web direct (Phase 2) | Stripe | Direct |

RevenueCat unifies subscription state across all three mobile IAPs. Our app code calls RevenueCat's SDK; we don't write three separate billing integrations. See [`docs/08_tech/payments.md`](../08_tech/payments.md) for implementation details.

## Free trial mechanics

7-day Trader trial on first sign-up. **No auto-bill at expiry.** See [`trial.md`](trial.md).

## Cancellation & refunds

- Cancellation: in-app deep-link to App Store / Play Store / AppGallery subscription management (per platform rules — we can't directly cancel)
- Refunds: handled by platform (Apple / Google / Huawei) — we don't offer side-channel refunds
- **No cancellation friction** — no "are you sure?" dark patterns. One-tap deep-link out, and that's it. Brand-positive over short-term revenue.

## Mid-tier upgrade / downgrade

- **Upgrade Trader → Floor Manager**: pro-rated, takes effect immediately. New credit cap applies. Premium AI starts immediately.
- **Downgrade Floor Manager → Trader**: takes effect at end of billing period. Existing credit balance carries over. AI model tier downgrades at period end.
- **Downgrade Trader → Floor Pass**: same — takes effect at period end. Earn-Path agents remain unlocked; Skip-Path agents revert (see [`docs/04_education/dual_gating.md`](../04_education/dual_gating.md)).

## Cross-references

- The 24 paywall axes table: [`paywall_axes.md`](paywall_axes.md)
- Credit economics: [`credits.md`](credits.md)
- Trial mechanics: [`trial.md`](trial.md)
- Offer system: [`offers.md`](offers.md)
- Unit economics: [`unit_economics.md`](unit_economics.md)
- Ads (Floor Pass): [`ads.md`](ads.md)
