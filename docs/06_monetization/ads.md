# Ads (Floor Pass tier only)

Ad-supported is the right call for the free tier. A *trading-education* app with sloppy ad ops will tank its brand fast. Hard policy + careful placement.

## What runs (allowed inventory)

| Category | Notes |
|---|---|
| **Reputable broker promos** | Interactive Brokers, Schwab, Fidelity, regulated regional brokers — direct deals only, not programmatic |
| **Financial certification & course providers** | CFA Institute, CMT Association, accredited financial programs |
| **Mainstream finance media** | Bloomberg, FT, WSJ subscriptions |
| **Bank / wealth manager brand campaigns** | Major banks, regulated wealth managers |
| **House ads** | Floor Pass → Trader upsell, Trader → Floor Manager upsell |
| **Programmatic display** | Through AdMob / Huawei Ads Kit / IronSource with **strict content filters** |

## What does NOT run (banned categories)

Hard policy. Any ad in these categories is grounds for terminating the source.

| Category | Banned |
|---|---|
| **Get-rich-quick** | Any "earn $X/day" / "guaranteed returns" claims |
| **Unregulated brokers** | Anyone without proper regulator registration in target market |
| **Binary options** | Predatory product category |
| **High-leverage CFDs** | Unregulated forex / CFD shops |
| **Crypto pump/dump schemes** | Including most token launches |
| **Pump newsletters / signal services** | Anyone promising "tips" |
| **Lottery / gambling** | Even regulated ones — wrong product category for us |
| **Adult content** | Obvious |
| **Politics** | Any partisan content |
| **Religious solicitation** | Out of scope, sensitive for AR/MS markets |

This list goes to programmatic networks as a blocklist + manual review for any direct buy. Brand safety is more important than ad revenue for the first 2 years.

## Where ads appear

| Placement | Format | OK? |
|---|---|---|
| Between lessons (interstitial after lesson completion) | Full-screen 5s skippable | **Yes** |
| Daily Challenge results screen | Native card under your result | **Yes** |
| Decision Journal — empty state | Sponsored card *"Open a real account when you're ready: [Broker]"* | **Yes** (marked as ad, mainstream brokers only) |
| Sim Portfolio — empty state (no positions) | Sponsored card | **Yes** |
| Academy Hub — bottom | Native card | **Yes** |
| Wallet & Plan screen | Native card | **Yes** (upsell-only) |

| Placement | Why **NO** |
|---|---|
| Floor home screen (the honeycomb) | Brand sanctity — the signature screen |
| Concierge conversation | Would destroy trust in the assistant |
| Convene the Room / 1-on-1 / Brief Your Agent | Would destroy product perception ("am I paying attention to my agent or to an ad?") |
| Inside Agent profile cards | The team metaphor breaks |
| Inside Mandate flows | Too sensitive a context |
| Onboarding / first-run | Set the brand cleanly before monetizing attention |
| Trade ticket | User is making a (sim) financial decision; not the moment for ads |

## Ad UX rules

- **Skippable after 5 seconds** for all interstitials (App Store / Play Store compliance + user respect)
- **Frequency cap**: max 1 interstitial per 5 lessons completed. Max 4 interstitials per session. Max 1 per 10 minutes.
- **Daily total cap**: ≤ 8 ad impressions per user per day on average
- **No autoplay video with sound** — sound off, tap to unmute
- **Clear "Ad" or "Sponsored" label** on every ad, in JetBrains Mono UPPERCASE
- **One-tap dismiss** on native cards (X in corner)
- **Don't mimic native UI** — ad cards have a different look than agent cards; no confusion possible
- **No rewarded ads** at MVP (per founder decision — "this is not a game")

## Ad networks per platform

| Platform | Primary SDK | Backup / mediation |
|---|---|---|
| iOS | **AdMob** | IronSource mediation |
| Android-GMS | **AdMob** | IronSource mediation |
| Android-HMS | **Huawei Ads Kit** | Pangle (Bytedance) as backup |

AdMob does not work without GMS. The Huawei build needs HMS Ads Kit. We build a **platform-service facade** (`AdsService`) with 3 implementations; app code calls the facade.

See [`docs/08_tech/platform_facade.md`](../08_tech/platform_facade.md) for facade pattern.

## House ads

**30% of all inventory is reserved for house ads** — our own upsell prompts:

| House ad slot | Content |
|---|---|
| Floor Pass user, has used all 5 free 1-on-1s | "Get unlimited 1-on-1s with Trader for $14.99/mo" |
| Floor Pass user, used 1 free Room | "Want 9 more Rooms a month? Try Trader." |
| Trader user near credit limit | "Hit your cap? Upgrade to Floor Manager for 500 credits/mo." |
| Trader user, halal-mandated | "Curious about Floor Manager's premium AI?" |

House ads are personalised based on usage patterns. Run on the same placements as paid ads.

## Performance expectations

| Metric | Target |
|---|---|
| Floor Pass MAU eCPM (programmatic) | $2–5 USD |
| Direct-deal brand campaign eCPM | $10–25 USD |
| House ad CTR to upsell flow | 3–5% |
| House ad → Trader conversion (from click) | 15–25% |
| Average Floor Pass ARPU/month from ads | $1–3 |

These are post-launch targets based on benchmarks for educational + finance apps. We'll measure at month 3 of v1.0 and tune.

## Compliance

- **Apple App Tracking Transparency (ATT)** prompt on first launch (or first ad request). User can decline; ads still serve, just less personalised.
- **GDPR consent banner** in EU markets, integrated with AdMob's GDPR flow.
- **CCPA "Do Not Sell"** toggle in Settings.
- **COPPA** — App is rated 17+ to avoid child-targeting requirements. (Finelo is similarly rated.)

## Removing ads

- Upgrading to Trader or Floor Manager removes all ads immediately
- "Remove ads" CTA never lives inside an ad — it lives in Wallet & Plan
- Downgrade back to Floor Pass: ads return on the next session

## Cross-references

- Platform service facade for ad SDKs: [`docs/08_tech/platform_facade.md`](../08_tech/platform_facade.md)
- Privacy policy required for ads: [`docs/09_compliance/disclaimers_and_privacy.md`](../09_compliance/disclaimers_and_privacy.md)
- App Store policies on ads in finance apps: [`docs/09_compliance/store_compliance.md`](../09_compliance/store_compliance.md)
