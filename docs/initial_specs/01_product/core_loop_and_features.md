# Core Loop & Feature Inventory

## The core loop

```
   ┌─────────────────────────────────────────────────────────┐
   │                                                         │
   │   ONBOARDING                                            │
   │   (Concierge conversation, mandate creation,            │
   │    7-day Trader trial activates)                        │
   │                                                         │
   └──────────────────────┬──────────────────────────────────┘
                          ↓
   ┌─────────────────────────────────────────────────────────┐
   │   EDUCATION                                             │
   │   ├── Trading Fundamentals (lessons + quizzes)          │
   │   └── Agent Academy (12 modules — unlocks agents)       │
   └──────────────────────┬──────────────────────────────────┘
                          ↓
   ┌─────────────────────────────────────────────────────────┐
   │   AGENT INTERACTION                                     │
   │   ├── 1-on-1 chat with any unlocked agent               │
   │   ├── Convene the Room (full 12-agent debate)           │
   │   └── Brief Your Agent (tune prompts via conversation)  │
   └──────────────────────┬──────────────────────────────────┘
                          ↓
   ┌─────────────────────────────────────────────────────────┐
   │   SIM DECISION                                          │
   │   (Buy / sell / hold in sim portfolio.                  │
   │    Portfolio Manager runs compliance check.             │
   │    Trade lands in Decision Journal.)                    │
   └──────────────────────┬──────────────────────────────────┘
                          ↓
   ┌─────────────────────────────────────────────────────────┐
   │   REFLECTION                                            │
   │   ├── Morning briefing                                  │
   │   ├── Mandate Drift Alerts                              │
   │   ├── Daily Challenges + Streaks                        │
   │   └── Per-agent performance (Phase 2)                   │
   └──────────────────────┬──────────────────────────────────┘
                          ↓
   ┌─────────────────────────────────────────────────────────┐
   │   MANDATE REFINEMENT                                    │
   │   (Edit mandate; re-run analyses; Coach an agent;       │
   │    repeat)                                              │
   └─────────────────────────────────────────────────────────┘
                          ↺ back to AGENT INTERACTION
```

The user is meant to live in steps 3–6 indefinitely. Steps 1–2 are one-time (mandate creation) or progressive (education unlocks).

## Feature inventory by release

Status legend:
- 🟢 **Alpha** — ships in stealth alpha (month 3)
- 🟡 **v1.0** — ships in public v1.0 (~month 9)
- 🔵 **v1.1** — first major post-launch release (~month 12)
- ⚪ **Phase 2** — months 12–18
- ⚫ **Far horizon** — uncertain

### Onboarding & mandate

| Feature | Status | Notes |
|---|---|---|
| Anonymous-first session start | 🟢 Alpha | No account required for first 24 hr |
| Concierge conversational interview (Express path, 6 questions + 3 risk scenarios) | 🟢 Alpha | Thorough path 🟡 v1.0 |
| Mandate readback in natural language | 🟢 Alpha | |
| Mandate edit (settings → My Mandate) | 🟢 Alpha | |
| Mandate Audit on hard changes | 🟢 Alpha | |
| Mandate version history (last 5) | 🟢 Alpha | Unlimited 🟡 v1.0 paid |
| Multi-mandate | ⚪ Phase 2 | "Retirement" + "Speculative" buckets |
| Mandate Drift Alerts | 🟢 Alpha | Daily email at alpha; real-time 🔵 v1.1 paid |

### The 12 agents

| Feature | Status | Notes |
|---|---|---|
| All 12 agents wired (TradingAgents on Cloud Run) | 🟢 Alpha | Core differentiator |
| Mandate overlay per agent prompt | 🟢 Alpha | |
| 1-on-1 chat with any agent | 🟢 Alpha | |
| Convene the Room (streaming logs + verdict) | 🟢 Alpha | Animated visual deck 🟡 v1.0 |
| Brief Your Agent (conversational mode) | 🟢 Alpha | Raw Mode editor 🟡 v1.0 |
| Coach version history | 🟢 Alpha | 20 versions paid; unlimited 🟡 v1.0 Floor Manager |
| Coach safety floor on Portfolio Manager | 🟢 Alpha | Non-negotiable |
| Multi-round debate (Floor Manager only) | 🟡 v1.0 | |
| Per-agent performance scorecards | ⚪ Phase 2 | |
| Mute / promote / weight agents | ⚪ Phase 2 | |

### AI Concierge (13th agent)

| Feature | Status | Notes |
|---|---|---|
| Q&A + product help | 🟢 Alpha | Always free, unlimited |
| Lesson routing | 🟢 Alpha | |
| Decision Journal summary | 🟢 Alpha | Paid only beyond Q&A |
| Schedule morning briefings | 🟢 Alpha | Paid only |
| Set reminders | 🟢 Alpha | Paid only |
| Mute / promote agents (via Concierge command) | 🟡 v1.0 | |
| `convene_for_me` (scheduled Room) | 🟡 v1.0 | |
| `book_review` (1-on-1 review session) | 🟡 v1.0 | |

### Education

| Feature | Status | Notes |
|---|---|---|
| Trading Fundamentals lessons | 🟢 Alpha 100; 🟡 v1.0 300+ | Static MDX, AI-tutor wrapped |
| AI-tutor wrapper (mandate-aware lesson delivery) | 🟢 Alpha | |
| Quizzes (AI-generated from user gap profile) | 🟢 Alpha | |
| Remedial micro-lessons on quiz fail | 🟢 Alpha | |
| Agent Academy (12 modules) | 🟢 Alpha | Simpler modules at alpha; "Predict the Call" challenge 🟡 v1.0 |
| Daily Challenges | 🟢 Alpha | |
| Streaks + Reputation points | 🟢 Alpha | |
| Lesson authoring CMS | ⚪ Phase 2 | Day 2 if app takes off |

### Sim & Decision Journal

| Feature | Status | Notes |
|---|---|---|
| Sim portfolio (paper money, 15-min delayed data) | 🟢 Alpha | 1 portfolio at alpha; multi-portfolio 🟡 v1.0 paid |
| Trade ticket with PM compliance pre-check | 🟢 Alpha | |
| Decision Journal (transcripts, search, replay) | 🟢 Alpha | 30 days free; unlimited 🟡 v1.0 paid |
| Journal entries tagged with mandate version | 🟢 Alpha | Traceability |
| Journal export (CSV / PDF) | 🟡 v1.0 | Floor Manager |
| Replay-as-case-study | ⚪ Phase 2 | |

### Compliance & differentiation

| Feature | Status | Notes |
|---|---|---|
| Halal / Sharia screening (mandate flag) | 🟢 Alpha | First-class. Universe filter + debt-ratio check + interest-bearing exclusion |
| ESG-lite mandate flag | 🟢 Alpha | |
| No tobacco / alcohol / gambling flag | 🟢 Alpha | |
| Long-only flag | 🟢 Alpha | |
| Custom ticker blocklist / allowlist | 🟢 Alpha | |

### Design & home

| Feature | Status | Notes |
|---|---|---|
| AMI hex design system applied | 🟢 Alpha | Full fidelity |
| 5-tab navigation (Floor / Sim / Convene / Academy / Journal) | 🟢 Alpha | |
| Persistent Concierge pill in header | 🟢 Alpha | |
| Honeycomb home (static) | 🟢 Alpha | Animated rotation/pulse 🟡 v1.0 |
| Convene FAB | 🟢 Alpha | |
| Dark-only theme | 🟢 Alpha | |
| RTL support (Arabic) | 🟡 v1.0 | |
| Cosmetic theme variants | ⚪ Phase 2 | |

### Monetization

| Feature | Status | Notes |
|---|---|---|
| Floor Pass / Trader / Floor Manager tiers | 🟡 v1.0 | At alpha: everyone is free Founders |
| 7-day Trader trial | 🟡 v1.0 | At alpha: irrelevant |
| Credit packs | 🟡 v1.0 | |
| RevenueCat integration | 🟡 v1.0 | |
| Apple IAP | 🟡 v1.0 | |
| Google Play Billing | 🟡 v1.0 | |
| HMS IAP | 🔵 v1.1 | |
| Stripe web subs (marketing-site direct) | ⚪ Phase 2 | |
| Founders Pricing offer | 🟡 v1.0 | |
| Annual Launch Promo | 🟡 v1.0 | |
| Referral offer | 🟡 v1.0 | |
| Launch-Country Promo | 🔵 v1.1 | |
| Ramadan Promo | 🔵 v1.1 | If launch is near Ramadan, advance to v1.0 |
| Student / Reactivation / Bootcamp Graduate offers | ⚪ Phase 2 | |

### Ads (Floor Pass tier)

| Feature | Status | Notes |
|---|---|---|
| AdMob (iOS + Android-GMS) | 🟡 v1.0 | |
| Huawei Ads Kit | 🔵 v1.1 | |
| IronSource mediation | 🟡 v1.0 | |
| Direct broker brand-deal ads | ⚪ Phase 2 | After scale |
| Hard category blocklist (no get-rich-quick, etc.) | 🟡 v1.0 | |
| House upsell ads (30% inventory) | 🟡 v1.0 | |

### Voice & briefing

| Feature | Status | Notes |
|---|---|---|
| Text morning briefing | 🟢 Alpha | Email-delivered at alpha; in-app + push 🟡 v1.0 |
| TTS voice morning briefing | 🟡 v1.0 paid | Azure Speech + ElevenLabs |
| In-app voice playback | 🟡 v1.0 | |

### Notifications

| Feature | Status | Notes |
|---|---|---|
| Email notifications (briefing, drift, streaks) | 🟢 Alpha | Resend |
| Push: APNs (iOS) | 🟡 v1.0 | |
| Push: FCM (Android-GMS) | 🟡 v1.0 | |
| Push: HMS Push (Huawei) | 🔵 v1.1 | |
| Push frequency controls | 🟡 v1.0 | |

### Platforms

| Platform | Status |
|---|---|
| iOS | 🟢 Alpha |
| Android (GMS) | 🟢 Alpha (Play Console internal track, per D-057) |
| Huawei AppGallery (HMS) | 🔵 v1.1 |
| Web companion | ⚪ Phase 2 |
| Samsung Galaxy Store | ⚪ Phase 2 (Android-GMS binary works there) |

### Languages

| Language | Status |
|---|---|
| English (en-US) | 🟢 Alpha |
| Arabic (ar-SA) | 🟡 v1.0 |
| Malay (ms-MY) | 🟡 v1.0 |
| Any others | ⚪ Phase 2 (architecture supports drop-in) |

### Markets

| Market | Status |
|---|---|
| US equities | 🟢 Alpha |
| Tadawul (Saudi) | ⚪ Phase 2 |
| Bursa Malaysia | ⚪ Phase 2 |
| Indonesian markets | ⚪ Phase 2 |
| Crypto / forex / derivatives | ⚫ Far horizon |

### Community (all Phase 2 or later)

| Feature | Status |
|---|---|
| Public Decision Journal entries / shareable replays | ⚪ Phase 2 |
| Reasoning-quality leaderboard | ⚪ Phase 2 |
| Community prompt-sets (publish Coach edits) | ⚫ Far horizon |
| Friends / following / public profiles | ⚫ Far horizon |
