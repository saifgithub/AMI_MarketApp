# Roadmap

Post-alpha to long-term. What lands when.

## v1.0-alpha (months 1–3) — Stealth Alpha

iOS, EN, free for Founders. See [`stealth_alpha_scope.md`](stealth_alpha_scope.md). 100–500 users.

## v1.0 public launch (months 4–9)

Goal: open the doors. Add the platforms, languages, and monetization that make AMI Trade a real consumer product.

### What lands in v1.0

| Feature | Why now |
|---|---|
| **Android-GMS** | The other half of the global mobile market |
| **Arabic + Malay locales** | Strategic positioning markets |
| **RTL polish** | Required for Arabic |
| **RevenueCat IAP** | We can charge money |
| **All 3 tiers active** (Floor Pass, Trader, Floor Manager) | Monetization live |
| **Credit pack purchases** | LLM-cost monetization |
| **Trader trial (7-day)** | Conversion mechanism |
| **All 5 launch offers** (Founders, Annual Launch, Referral, Country Promo, Ramadan Promo if seasonal) | Conversion levers |
| **Ads on Floor Pass** (AdMob + IronSource) | Free-tier revenue |
| **Push notifications** (APNs, FCM via OneSignal) | Retention |
| **Voice TTS briefings** | Habit hook |
| **Animated honeycomb** | Brand polish |
| **Convene visualisation upgrade** (face-off animations, risk triangle, verdict card animation) | The signature visual experience |
| **Coach Your Agent — Raw Mode** | Power-user feature |
| **Multi-round debate** for Floor Manager | Floor Manager differentiator |
| **Multi-portfolio** for paid tiers | Paid tier differentiator |
| **Real-time Mandate Drift Alerts** for Floor Manager | Floor Manager differentiator |
| **300 total lessons** (up from 100 at alpha) | Curriculum complete |
| **Free-text Predict-the-Call** in Agent Academy | Better Agent Academy experience |
| **Concierge full assistant tools** (every tool from the [`concierge.md`](../02_agents/concierge.md) catalogue) | Full Concierge functionality |
| **Marketing site** at agenticmarketintel.ai/trade | Acquisition channel |
| **App Store + Play Store listings** in EN/AR/MS | Discoverability |
| **GDPR / PDPL / PDPA full compliance review** | Legal go-live |

### v1.0 target metrics (6 months post-launch)

| Metric | Target |
|---|---|
| MAU | 5,000–10,000 |
| Paid conversion (Floor Pass → Trader or Floor Manager) | 8–12% |
| Trial → Paid conversion | 25–35% |
| D30 retention (Trader+) | 60% |
| Average reputation score | 200+ |
| Agent Academy completion rate (Floor Pass users) | 30% |

## v1.1 (months 10–12)

Goal: complete the platform coverage and add the next high-value features.

| Feature |
|---|
| **Huawei AppGallery (HMS)** launch — opens up Huawei user base in MENA + SEA |
| **HMS Push, HMS Account, HMS IAP, HMS Ads** integrations |
| **Phase-2 offers**: Bootcamp Graduate, Student, Reactivation |
| **Real-time market data** for Floor Manager (replace 15-min delay) |
| **Replay-as-case-study** — convert any past Room into a learning exercise |
| **Per-agent performance scorecard** (basic version) |
| **Streak freezes** for paid tiers |
| **Custom hex colour themes** for paid tiers |
| **Stripe web subs** for direct subscriptions via marketing site |

## Phase 2 (months 12–18)

Goal: scale-up features that need critical mass to ship well.

| Feature |
|---|
| **Per-agent mute/promote weights** — users can fire / amplify agents in the Research Manager's synthesis |
| **Reasoning-quality leaderboard** — public ranking by reasoning, not P&L |
| **Multi-mandate** — "Retirement" + "Speculative bucket" + others |
| **Public Decision Journal sharing** — users can share Room replays with attribution |
| **Community prompt-sets** — users publish their Coach Your Agent overlays for others to clone (start of marketplace dynamics) |
| **Voice morning briefings — premium narrative commentary** (Floor Manager) |
| **Hijri calendar option** for AR users |
| **Marketing site full build-out** with blog, case studies, founder stories |
| **Lesson authoring CMS** — for content team to write lessons via web UI |
| **Mobile attribution via AppsFlyer** when paid ad campaigns start |
| **Additional language: Indonesian** (id-ID) |
| **Tadawul (Saudi) equities** + Hijri-aware halal screening |
| **Bursa Malaysia equities** |
| **Web companion app** — read-only at first, then growing capabilities |

### Phase 2 target metrics (12 months post-public-launch)

| Metric | Target |
|---|---|
| MAU | 30,000–50,000 |
| Paid users | 4,000–6,000 |
| Monthly revenue | $80K–150K |
| Gross margin | 50%+ |
| Featured in App Store / Play Store | At least one feature placement |

## Phase 3 (months 18–24)

Goal: deepen the moat. AMI Trade becomes the *category-defining* AI-trading-education app.

| Feature |
|---|
| **Saudi-region GCP hosting** if KSA user base justifies |
| **Mandate sharing within trust groups** (e.g., father/son, advisor/client) — Phase 2.5 actually |
| **Voice STT for onboarding** (talk to Concierge, no typing) |
| **Local-model deployment** (Llama or Qwen for cheap tier — saves 70% of LLM cost) |
| **Direct broker brand-deal ads** (premium placements) |
| **AMI Trade-as-an-API** — partner brokers embed our agent intelligence |
| **B2B education licensing** — universities, training programs |
| **Indonesian market entry** (full localization + IDR pricing) |
| **Crypto markets** (regulated exchanges only) — if the team decides this fits |
| **Forex markets** — only if educational value clear; high regulatory caution |

## Far horizon — "what if it works"

Things to consider only if AMI Trade hits ≥250K MAU:

| Feature | Why |
|---|---|
| **Wealth-management partner offering** | License our agent stack to real money managers |
| **Real brokerage routing** | Long way away, requires licensing in every jurisdiction. Probably never under "AMI Trade" brand — would be a sister product. |
| **Bloomberg-like terminal mode** | Pro power-user feature, separate product |
| **Multi-agent debates on more than just stocks** — bonds, FX, commodities | Substantial data + content investment |
| **AMI parent-brand product lineup**: AMI Wealth (retirement planner), AMI Macro (newsletter), etc. | Other AMI sub-brands using the same agent infrastructure |

## What we won't do (decisive cuts)

| Feature | Why not |
|---|---|
| **Real-money trade execution** | Regulatory firewall — never |
| **Margin / leverage / derivatives** | Out of educational scope |
| **Margin lending / brokerage credit** | Out of scope |
| **Tax reporting integration** | Out of scope |
| **Rewarded video ads** | Brand decision — not a game |
| **Pump-and-dump community features** | Anti-pattern |
| **P&L-based leaderboards** | Encourages gambling psychology |
| **Children's version** | Not on our roadmap |

## Update cadence

This roadmap is reviewed:
- **Monthly** during alpha and v1.0 (rapid changes)
- **Quarterly** post-v1.0 (more stable)
- **Updated immediately** if a major decision (pricing, platform, feature) changes

Decision log lives at [`docs/11_decisions/decision_log.md`](../11_decisions/decision_log.md).

## Cross-references

- Alpha scope: [`stealth_alpha_scope.md`](stealth_alpha_scope.md)
- Open questions / future considerations: [`docs/11_decisions/open_questions.md`](../11_decisions/open_questions.md)
- Feature inventory by status: [`docs/01_product/core_loop_and_features.md`](../01_product/core_loop_and_features.md)
