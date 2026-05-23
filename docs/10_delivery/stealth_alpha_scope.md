# Stealth Alpha Scope (v1.0-alpha)

What ships in 12 weeks. **iOS TestFlight + Android-GMS Play Console internal track** (Android pulled forward from v1.0 — see [D-057](../11_decisions/decision_log.md#d-057--android-gms-pulled-forward-from-v10-to-alpha)). English only at alpha; Tier 1 AR + MS translations landed at AT:R35 but not yet wired into the build pipeline. Free for Founders cohort. The 12 agents are the centerpiece.

## Guiding principles

1. **The 12 agents are the show.** Everything else exists to serve them.
2. **Cut polish before cutting differentiators.** Better to ship the right product slightly rough than the wrong product perfectly.
3. **Founders cohort goal is *learning*, not revenue.** Free for them. No ads. No billing infra.
4. **Set quality expectations honestly.** Alpha = "early access." Brand impression matters.

## What ships at alpha

### Tier 1 — Must ship (or no product)

| Feature | Status |
|---|---|
| iOS TestFlight app | ✓ |
| Android-GMS Play Console internal-track app | ✓ (per D-057) |
| English only (no AR/MS) | ✓ |
| Anonymous-first onboarding (Concierge conversation) | ✓ |
| Mandate creation — Express path with 3 risk scenarios | ✓ |
| Account claim (Apple on iOS, Google on Android, Email magic-link cross-platform) | ✓ |
| Mandate edit + version history (last 5) | ✓ |
| All 12 agents wired (TradingAgents on Cloud Run) | ✓ |
| Mandate overlay per agent prompt | ✓ |
| 1-on-1 chat with any agent | ✓ |
| Convene the Room (streaming logs + verdict card) | ✓ |
| Brief Your Agent (conversational mode + diff + version history + safety floor) | ✓ |
| Concierge — Q&A + lesson routing + journal summary + basic scheduling | ✓ |
| Decision Journal (all entries, full transcripts) | ✓ |
| Sim portfolio + trade ticket + PM compliance pre-check | ✓ |
| Agent Academy (12 modules — simpler version) | ✓ |
| 100 Trading Fundamentals lessons (EN, written by Claude, reviewed by Saiful) | ✓ |
| AI-tutor wrapper for lessons | ✓ |
| Daily Challenges (auto-generated) | ✓ |
| Streaks + reputation points | ✓ |
| Halal/Sharia screening + universe filter | ✓ |
| Mandate Drift Alerts (daily email digest) | ✓ |
| Email notifications via Resend | ✓ |
| Static honeycomb home (no animations) | ✓ |
| 5-tab navigation (Floor/Sim/Convene/Academy/Journal) | ✓ |
| Persistent Concierge pill in header | ✓ |
| Convene FAB | ✓ |
| Dark-only AMI hex theme | ✓ |
| Splash page at agenticmarketintel.ai/trade | ✓ |
| Privacy Policy + ToS + Disclaimers (draft by Claude, lawyer-reviewed by Saiful mid-step) | ✓ |
| Account deletion (GDPR/PDPL) | ✓ |
| Data export | ✓ |
| Sentry crash reporting | ✓ |
| PostHog analytics | ✓ |
| TradingAgents backend on Cloud Run with mandate overlay injection | ✓ |
| LLM router via OpenRouter | ✓ |

### Skip at alpha (defer to v1.0)

| Feature | Defer to |
|---|---|
| Android-HMS (Huawei AppGallery) | v1.1 |
| Arabic + Malay languages + RTL | v1.0 |
| Voice TTS briefings | v1.0 |
| Animated honeycomb (rotations, pulses) | v1.0 |
| Fancier Convene visualisation (face-off, risk triangle) | v1.0 |
| Multi-round debate for Floor Manager | v1.0 |
| Multi-portfolio for paid tiers | v1.0 |
| Push notifications (APNs / FCM / HMS) | v1.0 — alpha uses email only |
| RevenueCat IAP integration | v1.0 — alpha is free for Founders |
| Subscription tiers, credits, billing | v1.0 |
| Ads (AdMob, Huawei Ads, mediation) | v1.0 |
| Promo offer system | v1.0 (Founders Pricing applies retroactively to alpha users) |
| Mandate Drift Alerts real-time | v1.0 |
| Predict-the-Call free-text version | v1.0 (alpha is multiple-choice) |
| 300 lessons (alpha ships with 100; ramp to 300 over v1.0 build) | v1.0 |
| Brief Your Agent Raw Mode | v1.0 |
| Real-time market data | v1.1 |
| HMS AppGallery launch | v1.1 |
| Per-agent performance scorecards + mute/promote | Phase 2 |
| Reasoning-quality leaderboard | Phase 2 |
| Replay-as-case-study | Phase 2 |
| Public Decision Journal sharing | Phase 2 |
| Lesson CMS / authoring tool | Phase 2 (Day 2 if takes off) |
| Multi-mandate | Phase 2 |
| Tadawul / Bursa equities | Phase 2 |
| Hijri calendar | Phase 3 |

## Alpha success criteria

The Founders cohort gives us:

| Goal | What we measure |
|---|---|
| **Validate the core loop** | Do users actually run Rooms? Do they brief agents? Do they come back? |
| **Validate the 12-agent value proposition** | Do users find the multi-agent debate valuable? Do they understand each agent's role? |
| **Validate mandate-driven personalisation** | Do users feel the agents are "theirs"? |
| **Surface critical bugs** | Crash rate, broken flows, RTL edge cases (postponed to v1.0 anyway), agent quality issues |
| **Refine pricing intuition** | Even though alpha is free, do users *say* they'd pay? At what price? |
| **Build word-of-mouth** | The Founders cohort tells their networks. Earn-media for v1.0 launch. |

## Founders cohort

- **Size**: 100–500 users at alpha
- **Recruitment**: Saiful's network + an HN/Twitter/r/algotrading post when there's a working build to show
- **Compensation**: free Trader-tier-equivalent access during alpha; 50% off Trader for 12 months when v1.0 launches (Founders Pricing); permanent "Founder" badge on profile
- **Feedback channels**: in-app Concierge "feedback" tool + a Slack/Discord (Saiful's call) for Founders only
- **Iteration cadence**: weekly TestFlight builds for the first month, then bi-weekly

## Alpha → v1.0 transition

The alpha runs for ~2 months after launch. During that time we're:
- Adding Android (GMS)
- Adding AR + MS translation
- Adding the remaining 200 lessons
- Adding RevenueCat + billing
- Adding push notifications
- Building real-money-cohort scaling tests

At v1.0 launch (around month 9 from project start), Founders transition to discounted paying users. We open public sign-ups. Marketing site goes live. We expect ~5K MAU in the first quarter.

## What "alpha" means to users (positioning)

Communicated explicitly:

> *"AMI Trade is in Stealth Alpha. You're an early Founder. Things may break. We need your feedback. In exchange, you get permanent Founder status and 50% off when we launch publicly."*

This sets the expectation that "alpha" ≠ "polished product." Users who sign up know what they're getting.

## Cross-references

- 12-week schedule: [`timeline.md`](timeline.md)
- Roadmap to v1.0 and beyond: [`roadmap.md`](roadmap.md)
- Who builds what: [`you_do_i_do.md`](you_do_i_do.md)
- Pre-alpha checklist: [`pre_alpha_checklist.md`](pre_alpha_checklist.md)
- Risks: [`risks.md`](risks.md)
