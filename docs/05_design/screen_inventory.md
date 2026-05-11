# Screen Inventory

Every MVP screen with purpose, key elements, and interactions.

| # | Screen | Path | Purpose |
|---|---|---|---|
| 01 | Splash | `/` | AMI Trade logo loads, transitions to onboarding or Floor |
| 02 | Concierge Conversation | `/onboarding` | Mandate creation interview |
| 02b | Account Claim | `/onboarding/claim` | Apple / Google / HMS / Email / Phone sign-in to save mandate |
| 03 | Floor (Home) | `/floor` | Honeycomb home — Concierge + 12 agents + mandate health + briefing |
| 04 | 1-on-1 Bottom Sheet | overlay | Quick chat with one agent (from long-press on hex) |
| 05 | Agent Profile | `/agent/{id}` | Overview / Past Calls / Performance / Coach tabs |
| 06 | Coach Session | `/agent/{id}/coach` | Conversational prompt tuning with diff card |
| 07 | Sim Portfolio | `/sim` | Holdings, P&L, drawdown gauge, recent trades |
| 08 | Position Detail | `/sim/{ticker}` | Single position deep-dive with agent takes |
| 09 | Trade Ticket | `/sim/trade` | Submit a sim trade with PM compliance pre-check |
| 10 | Convene Quickstart | `/convene` | Recent Rooms list + quick-start ticker picker |
| 11 | Convene the Room | `/convene/{run_id}` | Live multi-agent debate visualiser |
| 12 | Academy Hub | `/academy` | Fundamentals + Agent Academy + Daily Challenge tiles |
| 13 | Lesson Player | `/academy/lesson/{id}` | AI-tutor wrapped lesson with quiz |
| 14 | Agent Academy Module | `/academy/agent/{id}` | Per-agent training module |
| 15 | Daily Challenge | `/academy/daily` | Today's challenge |
| 16 | Journal Index | `/journal` | All journal entries, search, filter |
| 17 | Journal Transcript | `/journal/{entry_id}` | Full replayable transcript of a past entry |
| 18 | My Mandate | `/settings/mandate` | View / edit current mandate, version history |
| 19 | Wallet & Plan | `/settings/wallet` | Plan tier, credit balance, IAP, top-up |
| 20 | About & Legal | `/settings/about` | Disclaimers, ToS, Privacy, version, support |

Plus the persistent **Concierge full-screen modal** reachable from the header pill on any screen.

## Screen specs (key screens only — others are conventional)

### 02 Concierge Conversation

| Aspect | Spec |
|---|---|
| **Layout** | Full-screen vertical chat. Concierge avatar top, message stream, input field bottom. |
| **Visual** | Pink Concierge avatar centred top. Glass-panel messages. Voice-input mic icon. |
| **Inputs** | Text + chip suggestions (auto-shown on hesitation). Mic icon (Phase 2). |
| **Special** | Cannot back out without confirmation: "Quit setup? Your progress saves for 24h." |

### 03 Floor Home

See [`floor_home_honeycomb.md`](floor_home_honeycomb.md) — full spec.

### 05 Agent Profile

| Aspect | Spec |
|---|---|
| **Top** | Hex avatar (3× size), agent name in Inter Bold, role family badge (small hex, role-colour) |
| **Tabs** | Overview / Past Calls / Performance (Phase 2) / Coach |
| **Overview** | What they do + their current overlay summary (English) + last 3 calls + button "Start 1-on-1" / "Coach" |
| **Past Calls** | Timeline of every Room and 1-on-1 this agent was in. Tap to replay. |
| **Performance** (Phase 2) | Hit rate, alignment with user mandate, override rate |
| **Coach** | Entry to [`06_coach_session`](#06-coach-session) |

### 06 Coach Session

See [`docs/02_agents/coach_your_agent.md`](../02_agents/coach_your_agent.md) — full spec including the diff card design.

### 07 Sim Portfolio

| Aspect | Spec |
|---|---|
| **Top KPIs** | Portfolio value (JetBrains Mono large), day change %, total return %, **drawdown hex gauge** (color-coded vs cap) |
| **Holdings** | Hex-clipped cards per position. Symbol + last 1-on-1 agent + P&L. |
| **Cash bar** | Shows current cash position; if "cash drag" alert active, amber. |
| **Recent trades** | Mini-timeline; tap → trade record / journal entry |
| **FAB** | "+" Trade — opens trade ticket |

### 09 Trade Ticket

| Aspect | Spec |
|---|---|
| **Inputs** | Symbol (autocomplete), Side (Buy/Sell hex toggle), Quantity, Order type (Market/Limit) |
| **Compliance pre-check** | Inline panel that runs PM check as user types. Live mandate-violation feedback. |
| **Second opinion** | Two CTAs above Submit: "1-on-1 (1 credit) — quick gut-check" / "Convene the Room (8 credits) — full analysis" |
| **Submit** | Disabled if PM check fails. Failure shows specific violation. |
| **Confirmation** | Single-screen confirmation with PM verdict + journal entry link |

### 11 Convene the Room

See [`docs/02_agents/convene_the_room.md`](../02_agents/convene_the_room.md) — full spec.

### 12 Academy Hub

| Aspect | Spec |
|---|---|
| **Top** | Two giant hexagonal "track maps": Trading Fundamentals (left) + Agent Academy (right) |
| **Trading Fundamentals tile** | Progress: 47 / 150 lessons. Tap → curriculum browser. |
| **Agent Academy tile** | 12 hex avatars in a mini-honeycomb. Completed lit; in-progress half-lit; locked dim. Tap → that module. |
| **Daily Challenge card** | Today's challenge, status (not done / done / tried), streak counter |
| **Reputation strip** | Reputation score + tier name (Apprentice / Analyst / etc.) |

### 13 Lesson Player

| Aspect | Spec |
|---|---|
| **Layout** | Reader view. Progress bar top. Body in Inter for narrative, JetBrains Mono for inline numbers. |
| **AI-tutor wrap** | Opening line tailored to user's mandate (see [`docs/04_education/lessons.md`](../04_education/lessons.md)) |
| **Embeds** | `<Quiz>` and `<ChatWith>` blocks rendered inline |
| **Bottom** | Quiz section, then next-lesson CTA |

### 16 Journal Index

| Aspect | Spec |
|---|---|
| **Filters** | Ticker (autocomplete chip), Agent (multi-select), Date range, Outcome (W/L/Pending), Mandate version |
| **Search bar** | Full-text across transcripts |
| **List item** | Date + ticker + type icon (Room / 1-on-1 / Trade / Mandate-edit) + verdict + tags |
| **Empty state** | Concierge: "Nothing logged yet. Every Room, 1-on-1, and trade lands here." |

### 17 Journal Transcript

| Aspect | Spec |
|---|---|
| **Top** | Entry metadata: date, ticker, type, mandate version in effect, model tier used, credits used |
| **Body** | Full transcript (replayable). For Rooms: agent-by-agent contribution, role-colour bubbles. |
| **Replay controls** | "Replay at original speed" / "Replay instantly" |
| **Actions** | Tag, Add note, Share (Phase 2), Re-run with current mandate (Phase 2) |

### 18 My Mandate

| Aspect | Spec |
|---|---|
| **Hex ID card** | Top — large hex-clipped card with mandate name + key facts |
| **Sections** | Goals, Risk, Constraints (compliance flags as hex chips), Briefing, Preferences. Each tap-to-edit. |
| **Hard-edit flow** | On compliance change, runs Mandate Audit and shows results modal (see [`docs/03_onboarding/lifecycle.md`](../03_onboarding/lifecycle.md)) |
| **Version history button** | Shows last N versions per tier |

### 19 Wallet & Plan

| Aspect | Spec |
|---|---|
| **Tier card** | Floor Pass / Trader / Floor Manager hex badge + features list |
| **Credit balance** | Big JetBrains Mono number, "150 / 150 included this month" |
| **Top-up** | 3 credit pack tiles ($4.99 / $19.99 / $49.99) |
| **Upgrade CTA** | If on lower tier, "Take command — Floor Manager" CTA |
| **Subscription mgmt** | "Manage in App Store" link (RevenueCat handles redirect) |
| **Usage breakdown** (paid tiers) | Credits spent per category: Rooms, 1-on-1s, etc. |

### 20 About & Legal

| Aspect | Spec |
|---|---|
| **Legal links** | Terms of Service, Privacy Policy, Disclaimers, Data Subject Request, Open Source Notices |
| **Support** | Concierge link + (paid tier) email-a-human form |
| **App info** | Version, build, locale, time zone |
| **Account actions** | Sign out, Change password (if email), **Delete account** (per GDPR / PDPL) |

## Modal: Concierge Full-Screen

| Aspect | Spec |
|---|---|
| **Layout** | Full-screen vertical chat thread. Persistent — never session-scoped. |
| **Tool chips** | Above input: "Lessons", "Journal", "Schedule", "Mandate" — tap for quick tool invocation |
| **Streaming** | Concierge responses stream token-by-token. Tool use shows: "🔍 searching journal..." |
| **No ads** | Concierge surface is brand-sacred. No ads here, ever. |

## Cross-references

- The Floor: [`floor_home_honeycomb.md`](floor_home_honeycomb.md)
- IA overview: [`information_architecture.md`](information_architecture.md)
- Hex widget implementations: [`ami_hex_in_flutter.md`](ami_hex_in_flutter.md)
