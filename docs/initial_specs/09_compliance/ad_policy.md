# Ad Policy (detailed)

Extends [`docs/initial_specs/06_monetization/ads.md`](../06_monetization/ads.md) with the full content-policy specification.

## The principle

> Educational-context apps can be poisoned by predatory advertising. We are the venue. We carry the responsibility for what runs.

A user paying for a free service with their attention deserves the same protection a paying user gets. The policy below is the line we don't cross, even if it costs us short-term ad revenue.

## Allowed categories

### 1. Reputable retail brokers

**Examples**: Interactive Brokers, Charles Schwab, Fidelity, E*TRADE, Vanguard, regulated regional brokers in KSA (e.g., Al Rajhi Capital, SNB Capital), MY (e.g., Maybank Investment Bank), ID (when expanded).

**Requirements**:
- Must be registered with primary-jurisdiction regulator (SEC / FCA / SAMA / SC Malaysia / OJK Indonesia)
- Must NOT advertise leverage products > 1:5
- Must NOT advertise binary options, CFDs (unless regulator-licensed), or signal services
- Direct deals only (not via programmatic auction)

### 2. Financial education & certification

**Examples**: CFA Institute, CMT Association, accredited online courses (Khan Academy, Coursera finance), books from major publishers.

**Requirements**:
- Real organisations with real curricula
- No "earn $X/month" course pitches
- No "secret strategy" claims

### 3. Mainstream financial media

**Examples**: Bloomberg, FT, WSJ, The Economist, Reuters, regional equivalents (Asharq Business, The Edge Malaysia).

**Requirements**:
- Established outlets with editorial standards
- Subscription products only (not affiliate/sponsored content schemes)

### 4. Banks & wealth managers

**Examples**: Major retail banks promoting investment accounts, regulated wealth-management firms.

**Requirements**:
- Regulator registration
- No high-risk product promotion
- No "guaranteed returns" anywhere

### 5. House ads (our own)

**Examples**: Floor Pass → Trader upsell, Trader → Floor Manager upsell, founder offer reminders, Bootcamp-Graduate offers.

**Requirements**: comply with AMI Trade brand voice (no puffery, no false urgency).

## Banned categories

Any of these in any context = automatic block:

### 1. Get-rich-quick

| Pattern | Examples (banned) |
|---|---|
| "$X/day" claims | "Earn $500/day with this method" |
| "Free money" framing | "Get your free $1000" |
| Time-pressured wealth | "Become a millionaire in 30 days" |
| Lifestyle imagery | Lambos, beaches, retired-in-30s |
| "Secret" / "Insider" | "The trading secret Wall Street doesn't want you to know" |

### 2. Unregulated brokers

| Pattern | Examples (banned) |
|---|---|
| Offshore brokers without licensing | Many forex/CFD shops in obscure jurisdictions |
| Multi-level marketing schemes | "Trade and recruit" pitches |
| Pyramid schemes | Any compensation structure based on recruiting |

### 3. Binary options

Completely banned. Predatory product category banned by SEC, FCA, ESMA, multiple regulators.

### 4. High-leverage forex/CFD

| Limit | Detail |
|---|---|
| Max advertised leverage | 1:5 |
| Why | Higher leverage products have catastrophic loss rates among retail (>80% of accounts lose money at typical brokers). Educational app should not be a funnel into this. |

### 5. Crypto pump/dump schemes

| Pattern | Examples (banned) |
|---|---|
| Token launches not on major regulated exchanges | Random ERC-20 promotions |
| "Moonshot" / 100x claims | Any token marketing of multi-thousand-percent returns |
| ICO/IDO/IEO promotions | Generally banned (uncertain regulation, high fraud rate) |

Allowed: regulated crypto exchanges (Coinbase, Kraken, Binance regional regulated entities) running brand-level (not token-level) ads.

### 6. Pump newsletters / signal services

| Pattern | Examples (banned) |
|---|---|
| "Stock alerts" subscriptions | Predatory tip services |
| "Trade ideas" services | Most are FOMO-driven |
| "Insider info" services | Often outright fraud |

Allowed: actual published research from registered investment advisors (e.g., Morningstar Premium).

### 7. Lottery / gambling

Banned across the board. Wrong product category. Even regulated gambling — we explicitly position as "not a game."

### 8. Adult content

Obvious.

### 9. Politics

Any partisan content banned. Sensitive in our markets (KSA, MY).

### 10. Religious solicitation

Banned. Sensitive in AR/MS markets. We respect users' faith via halal mandate flag — we don't proselytise.

### 11. Tobacco, alcohol, gambling

Banned. Aligned with halal-aware positioning.

### 12. Inflammatory political content

Banned.

### 13. Health claims

Banned (out of scope and risk-laden).

### 14. Personal data harvesting schemes

| Pattern | Banned |
|---|---|
| "Win an iPhone" sweepstakes | Almost always lead-gen scams |
| "Free trial" with hidden auto-bill | Common predator pattern |
| "Click to download" generic incentives | Phishing-adjacent |

## Enforcement

### Programmatic networks (AdMob, Huawei Ads, IronSource)

We provide our network with the banned-categories blocklist. They filter at the auction. We additionally review reports weekly for any breach and report to network for refund / removal.

### Direct deals

Every direct ad deal goes through manual review:
1. Marketing reviews the creative
2. Compliance (Saiful + counsel as needed) reviews the brand
3. Legal review on contracts
4. Pre-launch test placement

### Reporting

Users can report ads they think violate our policy:
- Tap "Report this ad" in any ad placement
- Form captures: which ad, why it seems wrong, optional comment
- Triaged within 7 days
- Confirmed violations result in immediate removal + network notification

User reports help us catch issues programmatic filters miss.

## Brand-deal pricing

When we hit scale (~20K+ MAU), direct brand deals become viable. Floors:

| Deal type | Floor pricing (we charge advertiser) |
|---|---|
| Banner / native card | $10–15 eCPM |
| Sponsored Concierge tile (Phase 3) | $25+ eCPM |
| Lesson sponsorship (Phase 3, if at all) | Custom; reviewed individually |

Direct brand deals supplement (not replace) programmatic. House ads always get 30%.

## Phase 2: rewarded ads decision

Per Saiful's MVP decision, **no rewarded ads**. Reasoning: "this is not a game."

We may revisit if:
- User research shows demand for "watch ad → earn credits" as a respectful free-tier mechanic
- Implementation can be limited to non-trading contexts (e.g., "watch an ad → unlock a lesson early")
- Brand impact assessed positively

If revisited, the implementation would be tightly limited and **never** mid-lesson or in-Concierge.

## Cross-references

- Ad placements + networks: [`docs/initial_specs/06_monetization/ads.md`](../06_monetization/ads.md)
- Store policies on ads in finance apps: [`store_compliance.md`](store_compliance.md)
- Brand voice (which informs ad creative rules): [`docs/initial_specs/00_overview/brand_and_glossary.md`](../00_overview/brand_and_glossary.md)
