# Brand & Glossary

## Brand hierarchy

```
AMI  (Agentic Market Intel)         ← parent / company brand
 └── AMI Trade                       ← product brand (this app)
 └── [future products]               ← (e.g. AMI Wealth, AMI Macro)
```

The parent brand **AMI = Agentic Market Intel** signals "we build AI agent teams for financial market problems." AMI Trade is product #1: a trading-education app.

## Sub-brand: AMI Trade

| | |
|---|---|
| **Name** | AMI Trade |
| **Tagline (primary)** | Your team of analysts. Your call. |
| **Tagline (alt 1)** | Twelve agents. One mandate. Your decisions. |
| **Tagline (alt 2)** | Trading floor in your pocket. |
| **Logo** | The AMI hex logo (`logo_hex.svg` from the design system) + wordmark "AMI Trade" in Inter Bold. Wordmark is hex-blue (`#3b82f6`) on dark. |

## Tier identity (consistent across product + marketing)

Three tiers, each with a hex-clipped tier badge in product:

| Tier | Badge color | Persona narrative |
|---|---|---|
| **Floor Pass** | Slate (`--slate-base`) | *"You're on the floor. Learn the room. Earn your team."* |
| **Trader** | Hex-blue (`#3b82f6`) | *"Licensed. All 12 analysts working for you."* |
| **Floor Manager** | Purple (`--hex-purple`) | *"You run the floor. Premium intelligence, real-time."* |

Upgrade prompts use this metaphor:
- *"Get your Trader's License"* — Floor Pass → Trader
- *"Take command of the floor"* — Trader → Floor Manager

## Voice

Inherited from AMI's "Hex-Reinforced Precision" brand voice, but **slightly warmer** for the consumer surface:

- **Confident, pragmatic, peer-to-peer.** Speak to the user like a respected colleague, not a child.
- **Numbers over adjectives.** *"Up 3.2% overnight"* not *"performing strongly"*.
- **Short declarative sentences.** Periods, not exclamation marks.
- **No marketing puffery.** Banned words: *revolutionary, synergy, AI-powered, game-changing, disruptive, supercharge*.
- **UPPERCASE MONO** (JetBrains Mono, 0.1em letter-spacing) for labels, tags, badges, and button text — this is a core motif.
- **Title Case** for H1 / H2. Sentence case for body.
- **Second person** for the user (*"your ATMs"* → *"your team"*, *"your mandate"*). Never *"I"*.
- **En-dashes** for ranges (`3–10 years`, `SAR 56–70`).

Consumer-warming adjustments vs core AMI:
- Concierge is friendly and uses contractions ("you've", "let's").
- Lesson narration uses examples and analogies (the lesson rendering layer is AI-tutor-wrapped — see [`docs/04_education/lessons.md`](../04_education/lessons.md)).
- Daily challenges can use light emoji (🔥 for streaks, ⬢ for the brand glyph). Lessons cannot.

## Forbidden patterns

- Get-rich-quick language. Ever.
- "Guaranteed returns" or anything implying outcome.
- Comparing AMI Trade's sim performance to real-money portfolios.
- Pictures of stacks of cash, Lambos, beaches, retired-in-30s influencer imagery.
- Patronising tone toward beginners.

## Glossary

| Term | Definition |
|---|---|
| **Mandate** | The structured object — derived from onboarding — that captures the user's financial goals, horizon, risk profile, drawdown cap, compliance flags (halal, ESG, etc.), and preferences. Injected into every agent's system prompt as an overlay. See [`docs/03_onboarding/mandate_schema.md`](../03_onboarding/mandate_schema.md). |
| **The 12 agents** | The team of TradingAgents-powered LLM agents: 4 Analysts (Fundamentals, Market, News, Social Media), 2 Researchers (Bull, Bear), Research Manager, Trader, 3 Risk Debators (Aggressive, Conservative, Neutral), and Portfolio Manager. See [`docs/02_agents/twelve_agents.md`](../02_agents/twelve_agents.md). |
| **Concierge** | The 13th agent. User's personal assistant: lesson routing, journal summary, briefing scheduling, mute/promote helpers, product Q&A. Always free. Never gives trading advice. |
| **Convene the Room** | A full multi-agent debate session — all 12 agents run on a ticker. The streaming reasoning is visualised; the final verdict (Buy/Hold/Sell + sizing) is recorded to the Decision Journal. Costs credits. |
| **1-on-1** | A solo chat with a single agent. Cheaper than a Room. |
| **Brief Your Agent** | The feature where a user tunes an agent's prompt via conversation. The agent proposes prompt diffs; user accepts/refines/rejects. Versioned. Portfolio Manager's mandate enforcement is a *safety floor* — uncoachable. |
| **Decision Journal** | The permanent, searchable log of every Room, 1-on-1, sim trade, and mandate edit. Replayable. 30 days for Floor Pass; unlimited for paid. |
| **Floor** | The home screen — the user's "trading floor" with the Concierge at the centre and the 12 agents in a honeycomb tessellation around her. See [`docs/05_design/floor_home_honeycomb.md`](../05_design/floor_home_honeycomb.md). |
| **Earn Path** | The free progression: complete an Agent Academy module → unlock that agent. Costs time, not money. |
| **Skip Path** | The paid progression: subscribe → all 12 agents instantly active. |
| **Mandate overlay** | The block of text appended to an agent's base system prompt that contains the user's mandate constraints. Auto-generated, non-editable by the user. |
| **User overlay** | The user's Coach-Your-Agent customisations to an agent's prompt. Editable. Versioned. |
| **Safety floor** | The uncoachable block at the end of the Portfolio Manager's prompt that re-asserts mandate enforcement. Plus a deterministic compliance-check function. The user *cannot* coach their way past this. |
| **Mandate Drift** | When the user's sim portfolio has drifted from their stated mandate (e.g., risk profile, halal compliance, drawdown cap). Triggers an alert. |
| **Trader Trial** | The 7-day free trial of Trader tier on signup. No auto-bill at expiry. |
| **Founders cohort** | The first 10,000 paying subscribers, who get 50% off for 12 months under the "Founders Pricing" promo. |
| **TradingAgents** | The open-source multi-agent LLM framework powering our 12 agents. [Repo](https://github.com/TauricResearch/TradingAgents). |
| **The hex** | The flat-topped hexagon — the AMI brand's organising motif. Used as logo, layout, badges, button shape. See AMI design system README. |
