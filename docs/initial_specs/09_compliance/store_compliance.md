# Store Compliance

Apple App Store, Google Play, Huawei AppGallery — what they require for a finance / education app.

## Apple App Store

### Key guidelines

| Guideline | What it means for AMI Trade |
|---|---|
| **3.1.1 In-App Purchase** | All digital subs and credits MUST use Apple IAP. We do — via RevenueCat. |
| **3.2.1 Acceptable** (financial services) | Apps using financial-trading metaphors must be transparent about being simulations. We disclose extensively. |
| **3.2.2 Unacceptable** | "Provide false or fraudulent financial information." We don't. |
| **4.8 Sign in with Apple** | Required *only* if the app offers any third-party/social login on iOS. We do offer Sign in with Apple on iOS, and it is the **only** federated login on iOS — so 4.8 is satisfied. See the coupling note below. |
| **5.1.1 Privacy** | Privacy Policy required + ATT prompt if cross-app tracking. We comply. |
| **5.1.2 Data Use & Sharing** | Privacy Manifest required (iOS 17+). We provide one declaring data we collect. |
| **5.1.5 Location Services** | We don't collect location beyond country (IP-based). OK. |
| **2.5.1 Software Requirements** | Must compile with latest SDK. Standard. |

#### Guideline 4.8 coupling — why login stays per-platform (CR050)

Apple's Guideline 4.8 makes "Sign in with Apple" **mandatory** on iOS as soon as the
app presents *any* other social/third-party login (Google, Facebook, etc.) that
collects the equivalent of name/email. Our login is deliberately **per-platform**
(D-057): iOS shows **only** Sign in with Apple; Android shows **only** Google
Sign-In; email 6-digit-code (demoted behind a "Use email instead" disclosure) is a
first-party passwordless path, not a third-party social login, so it does not trip
4.8. Result: iOS is compliant today.

The trap to remember: **turning Google Sign-In on for iOS would immediately make
Sign in with Apple binding** on that screen. We already ship SIWA, so we'd still be
compliant — but the button ordering/parity rules in 4.8 would then apply. If a future
CR ever adds Google (or any social provider) to iOS, keep Sign in with Apple present
and at least as prominent. Backend `/v1/auth/google` is platform-agnostic, so this is
a UI-only risk to watch, not a backend one.

### App Review tips for trading-themed apps

Apple review can be prickly about "trading" / "investment" claims. To smooth review:

1. **Lead with "education" / "simulation"** in app name subtitle, description, screenshots, and metadata
2. **Show the disclaimer** prominently in at least one screenshot
3. **Sandbox account credentials** provided in App Review notes
4. **No real-money flows** anywhere in the app (we have none — sim only)
5. **No claims of returns** in marketing materials
6. **Demo onboarding** that an Apple reviewer can walk through quickly (we provide a "skip onboarding for review" deep-link)

### App Store listing copy

**App name**: AMI Trade

**Subtitle** (30 chars): *Your 12 AI analysts.*

**Short description**:
> *AMI Trade is an AI-first trading education simulation. Learn to manage a team of 12 specialised AI analysts who advise you in paper-money trades — personalised to your goals, risk, and constraints.*

**Long description** structured as:
- Hook (1 paragraph)
- What's different (12 agents, Brief Your Agent, Halal screening)
- Who it's for (beginners, prosumers, halal/ESG-conscious investors)
- How it works (3-step quick)
- Disclaimer paragraph (educational simulation, not advice)
- Subscription details (auto-renewable, prices, cancellation instructions)

**Keywords**: trading, education, AI, investing, halal, finance, simulator, learn, stocks, portfolio

**Category**: Finance (primary), Education (secondary)

**Age rating**: 17+ (financial themes — even though sim-only, the topic warrants 17+)

### Required URLs

- Privacy Policy URL
- Support URL
- Marketing URL (the agenticmarketintel.ai/trade splash page)
- EULA URL (or use Apple's standard)

## Google Play Store

### Key requirements

| Requirement | AMI Trade handling |
|---|---|
| **Financial Services policy** | If we promoted real-money trading we'd need extra docs. Sim-only avoids this. |
| **Personal & Sensitive User Data** | Privacy Policy required, declare in console |
| **Permissions** | Minimal (network, push) |
| **Data Safety form** | Filled out completely; published on listing |
| **Subscriptions** | Must use Google Play Billing. RevenueCat handles. |
| **Closed beta** for initial cohort | Use Internal Testing track for alpha |
| **Open testing** for soft launch | Phase before full release |

### Listing copy

Mirror of App Store with Play-specific tweaks:
- Short description ≤ 80 chars
- Full description ≤ 4000 chars
- Title ≤ 30 chars

### Data Safety declaration

We declare:
- Personal info (email, phone) — Required for app function
- Financial info (mandate goals etc.) — Required for app function
- App activity (lessons completed, etc.) — Required for app function
- Crash logs — Optional, user can opt out
- Diagnostic logs — Optional

All declared as encrypted in transit + at rest. User can request deletion.

## Huawei AppGallery (v1.1)

### Key requirements

| Requirement | Handling |
|---|---|
| **Real-name verification** for finance apps | Some markets require this. We argue we're educational, not financial services. |
| **Financial qualifications** | If categorised as finance, may require government license. We submit as "Education" primary category. |
| **HMS Core integration** | We integrate HMS Push, HMS Account, HMS IAP, HMS Ads |
| **Privacy Policy** | Same as other stores |
| **Sensitive Permissions** | Detailed justification for each permission |

### Review specifics

Huawei review is **stricter** than Apple/Google for finance content. Mitigations:
- Lead with "education" / "simulation" terminology in store listing
- Multiple disclaimers throughout marketing copy
- Submit in **Education** category (not Finance) to reduce friction
- Provide thorough App Review notes explaining the educational simulation nature
- Be prepared for 2–3 review iterations (vs typical 1 for App Store)
- Submit early in the v1.1 release window (week 22 of v1.0 build, conservatively)

### Listing in Arabic (for KSA AppGallery)

AppGallery has its own AR listing in Saudi Arabia. Marketing copy translated and submitted via the Arabic interface.

## Common requirements across all stores

### Age rating questionnaire

For all three stores, we answer the same questions:
- Gambling content: No
- Simulated gambling: No (we explicitly do not gamify trading P&L)
- Realistic violence: No
- Profanity: No
- Mature/suggestive themes: No
- Drugs/alcohol/tobacco references: No (educational only, never glorified)
- Medical/treatment info: No
- Unrestricted internet: Yes (Concierge / agent chats can search news; bounded)
- Frequent/intense alcohol/tobacco/drugs: No
- Frequent/intense violence: No
- Frequent/intense sexual content: No

Result: 17+ across stores (because of financial subject matter).

### Pricing & in-app purchases

Mirror across all three:

| Product | iOS | Android | Huawei | RevenueCat product ID |
|---|---|---|---|---|
| Trader Monthly | $14.99 | $14.99 | $14.99 | `ami_trader_monthly` |
| Trader Annual | $129 | $129 | $129 | `ami_trader_annual` |
| Floor Manager Monthly | $34.99 | $34.99 | $34.99 | `ami_floor_manager_monthly` |
| Floor Manager Annual | $299 | $299 | $299 | `ami_floor_manager_annual` |
| Credit Pack Starter | $4.99 | $4.99 | $4.99 | `ami_credit_pack_60` |
| Credit Pack Standard | $19.99 | $19.99 | $19.99 | `ami_credit_pack_300` |
| Credit Pack Power | $49.99 | $49.99 | $49.99 | `ami_credit_pack_850` |

All stores auto-convert to local currency. We don't manually set per-country.

### Subscription disclosures

Required text in app listings + in-app purchase screens:

> *"AMI Trader: $14.99/month, auto-renewable. Cancel any time in your [Apple ID Settings | Google Play subscriptions | AppGallery account]. Cancellation takes effect at the end of the current billing period. Free trial period: 7 days."*

(Adapted per platform.)

## Banned terms in marketing

Within marketing copy (store listings + landing page + ads), we avoid:

- "Make money"
- "Earn $X per day"
- "Guaranteed returns"
- "Get rich"
- "Beat the market"
- "Insider tips"

These would trigger review red flags on all three stores AND would conflict with our educational positioning.

## Cross-references

- Disclaimers full text: [`disclaimers_and_privacy.md`](disclaimers_and_privacy.md)
- Ad policy that affects store reviews: [`ad_policy.md`](ad_policy.md)
- Payment integration: [`docs/initial_specs/08_tech/payments.md`](../08_tech/payments.md)
