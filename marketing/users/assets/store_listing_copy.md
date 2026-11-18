# Store listing copy — App Store + Google Play

**Status: DRAFT for Saiful's review. Not submitted.** Rev 2 (CR267 WP-29, 2026-11-18): re-led on
the learning outcome. The user learns to make and defend a trading decision; the Room is the
practice arena, a simulated desk of AMI analysts that debates in front of them. No stock-picking,
market-beating, return or performance claim anywhere.

Language: **EN only.** `retranslate:[ar,ms]` — AR and MS listings are a v1.0 item and, per
`_facts/claim_register.md` N1/H5, **any halal copy in AR or MS requires human review before it
ships**. Machine translation is not acceptable for observance-sensitive strings.

Built on the draft already in `docs/initial_specs/09_compliance/store_compliance.md`, with these
changes: led on outcome rather than agent count (`positioning_and_personas.md` Rule 1), Sharia
screening added (it ships — N1), every forbidden claim stripped. Rev 2 also: drops "risk-free" from
the subtitle (it can be read as a claim about investing rather than about the simulation), uses the
CR160 role titles (Chief Investment Officer, Risk Officers) instead of "Portfolio Manager", and
moves the headcount out of every lead position into one body sentence that describes the simulation.

⚠️ **BLOCKED: pricing.** The subscription block below is a marked placeholder. Three sources
disagree on price (`user_acquisition_plan.md` §11) and both stores require accurate price and
term disclosure — a wrong number is a rejection, not a correction.

---

## Apple App Store

### App name (30 char max)

```
AMI Trade
```
`9 chars.` Unchanged. Keep it short — the subtitle carries the meaning, and Apple truncates
aggressively on the search results row.

### Subtitle (30 char max)

Recommended:

```
Learn to defend your trades
```
`27 chars.` States the outcome. No "risk-free": the safety is the simulation, which the
description says in plain words.

Alternatives, all within limit:

| Option | Chars | Note |
|---|---|---|
| `Learn to defend your trades` | 27 | **Recommended** |
| `Make the call. Defend it.` | 25 | Punchier, less explicit about learning |
| `Practise the trading call` | 25 | Closest to the old "practice" framing |
| `Practice investing, risk-free` | 29 | Rev 1. **Retired** — "risk-free" next to "investing" reads as a claim |
| `Your 12 AI analysts.` | 20 | The old `store_compliance.md` draft. **Rejected** — leads with agents |

### Promotional text (170 char max, editable without review)

```
Learn to make and defend trading decisions. A simulated desk of AMI analysts debates in front of you; you make the call. Simulation only, no real money.
```
`152 chars` of 170. This field can be changed without resubmitting, so it is where seasonal or
feature-launch messaging goes. Verify the count in the console after any edit.

### Description

Opens with the outcome. The Room arrives in paragraph two, as the arena where the practice happens.

```
AMI Trade teaches you to make a trading decision and defend it. You practise on real market data, in a simulated portfolio, with none of your money at risk.

The practice arena is the Room: a simulated desk of AMI analysts. Choose a ticker and the desk works it in front of you — fundamentals, market technicals, news and events, retail positioning, a bull case, a bear case, three Risk Officers pressing the position size from three directions, and a Chief Investment Officer who rules on the trade. You read the debate. You question anyone you disagree with. Then you make your call, and AMI runs it in your simulated portfolio and records your reasoning.

It's the difference between reading about swimming and getting in the pool, except the pool has no sharks.

WHAT YOU PRACTISE

• Building a thesis and stress-testing it. Every call meets a bear case and three Risk Officers before you commit. You see the arguments, not just a conclusion.
• Defending a position against your own mandate. Your goals, risk limits, constraints and holdings shape what every analyst says. Submit a trade that breaks your own stated mandate and the Chief Investment Officer refuses it, with the reason.
• Reading analysis critically. The desk is twelve analysts plus AMI, your Concierge, and they disagree on the record. The Evaluation track teaches you to judge analyst output and spot a fabricated number.
• Learning from your own record. Every debate, call and reason is stored and replayable in your decision journal, so you can see how you actually reason.
• The foundations. 342 lessons in English, Arabic with full right-to-left support, and Malay, plus daily challenges, streaks and leagues.
• Sharia and ethical screening. Screen your universe against an AAOIFI-based compliant list, currently 216 of the S&P 500, with the as-of date shown on every verdict. Optional exclusions for fossil fuels, tobacco and alcohol.

WHO IT'S FOR

• You want to understand your own investments well enough to explain and defend them.
• You've traded before, it went badly, and you want to rebuild your process somewhere mistakes don't cost anything.
• You need your investing to respect Sharia or ethical constraints, and you're tired of apps that ignore that.

HOW IT WORKS

1. AMI interviews you about your goals, horizon, risk tolerance and constraints. That becomes your mandate, and it shapes every analyst.
2. Choose a ticker. Convene the Room and watch the desk work it through.
3. Make your call. AMI simulates it, tracks it, and remembers your reasoning.

IMPORTANT

AMI Trade is an educational simulation. It is not investment advice, not a brokerage, and not a recommendation service. All trading is simulated with virtual money. There is no real-money trading, no brokerage connection, and no way to buy or sell an actual security. What the Room produces is a training exercise, not guidance on what to buy or sell. Market data is delayed by 15 minutes. Sharia screening reports a screen against a published compliant list; it is not a religious ruling. Nothing in this app is a prediction, and nothing here forecasts a return.

[SUBSCRIPTION BLOCK — PLACEHOLDER, DO NOT SUBMIT WITHOUT SAIFUL'S CONFIRMED PRICING]
Floor Pass is free, permanently, with ads. Paid tiers unlock the full analyst desk, unlimited sessions and full journal history. Prices, terms, trial length and cancellation instructions go here — exact figures pending. Subscriptions renew automatically unless cancelled at least 24 hours before the period ends; manage or cancel in your App Store account settings.
Privacy Policy: https://www.agenticmarketintel.ai/privacy/
Terms of Service: https://www.agenticmarketintel.ai/terms/
```

### Keywords (100 char max, comma-separated, no spaces, don't repeat the name or subtitle)

```
halal,sharia,islamic,investing,paper,simulator,stocks,analysis,portfolio,course,practice,ethical
```
`96 chars.` Unchanged.

Reasoning: skip "trading" and "finance" — high-volume terms we lose to brokerages with ad
budgets. The **halal / sharia / islamic** cluster is where we can plausibly rank first, because
it is specific, intent-heavy, and nobody in this category serves it (N1,
`user_acquisition_plan.md` §5). "paper" catches *paper trading*, which is the closest
high-intent competitor term.

### Category, rating, URLs

| Field | Value |
|---|---|
| Primary category | Finance |
| Secondary category | Education |
| Age rating | 17+ (financial themes) |
| Simulated gambling | **No** — we do not gamify P&L. Keep it that way; see `ad_copy.md` §5 |
| Privacy Policy URL | `https://www.agenticmarketintel.ai/privacy/` |
| Support URL | `https://www.agenticmarketintel.ai/#contact` |
| Marketing URL | `https://www.agenticmarketintel.ai/` |

### What's New (first public release)

```
First public release. Learn to make and defend trading decisions in the Room, a simulated desk of AMI analysts, with 342 lessons in three languages, AAOIFI Sharia screening, and a journal that keeps your reasoning.
```

### App Review notes

```
AMI Trade is an educational simulation. There is no real-money trading, no brokerage
integration, and no mechanism to buy or sell an actual security — all portfolios are virtual.

Sandbox account: [SAIFUL TO SUPPLY]
Skip onboarding: [reviewer deep-link — SAIFUL TO SUPPLY]

The onboarding interview takes ~3 minutes; the deep-link above bypasses it. To see the core
feature, open the Floor tab, pick any ticker and tap CONVENE THE ROOM. The debate streams live
and takes 1–3 minutes to reach a verdict.

Market data is Yahoo Finance, delayed 15 minutes. The simulation-only disclaimer appears in
onboarding, in Settings, on the verdict screen, and in screenshot 6.
```

---

## Google Play

### Title (30 char max)

```
AMI Trade: Practise the Call
```
`28 chars.` Play gives more room in the title than Apple's name field and weights it for search,
so the outcome goes here. (Use "Practice" if the Play listing is US-English only; both are 28.)

### Short description (80 char max)

```
Learn to make and defend a trading call. A simulated desk debates; you decide.
```
`78 chars.` Counts are measured, not estimated — Play enforces strictly.

Alternatives:

| Option | Chars |
|---|---|
| `Learn to make and defend a trading call. A simulated desk debates; you decide.` | 78 |
| `Learn to make and defend trading decisions. Simulated money, real market data.` | 78 |
| `Learn to defend your trades. A simulated desk debates; you make the call.` | 73 |
| ~~`Learn to make and defend trading decisions. A simulated desk debates. You decide.`~~ | **81 — over limit** |

### Full description (4,000 char max)

Reuse the App Store description verbatim, with three substitutions:

1. "App Store account settings" → "Google Play subscription settings".
2. Add, in the IMPORTANT block: *"Account and data deletion: request at
   https://www.agenticmarketintel.ai/ami-trade/sad-to-see-you-go — no install required."* This
   satisfies Play's 2023 deletion policy, and the page is already live.
3. Play renders limited markup — check the bullet characters survive the console's formatter.

The App Store description is 3,689 characters (measured), so there is room for the Play additions.
Do not fill it with keywords; Play does not reward stuffing and it reads badly.

### Data Safety declaration

Per `store_compliance.md`. Declare: personal info (email) — required for app function; financial
info (mandate goals, simulated holdings) — required; app activity (lessons, debates) — required;
crash logs — optional, user can opt out; diagnostics — optional. All encrypted in transit and at
rest, deletion available.

⚠️ **Verify against what the app actually sends before submitting.** A Data Safety form that
disagrees with observed network traffic is a policy violation, and `SENTRY_DSN` being currently
unset (F12) means the crash-log row describes a capability that is installed but inactive —
declare the capability, since it will be switched on.

---

## Compliance checklist — run before submitting either listing

| Check | Where |
|---|---|
| Leads with the learning outcome (make and defend a decision) | Name, subtitle, description ¶1, review notes |
| The Room described as a simulated practice desk, not an advisor | Description ¶2, IMPORTANT block |
| Disclaimer visible in ≥1 screenshot | `screenshots_and_captions.md` frame 6 |
| No stock-picking, market-beating, return, gain or performance claim | Grep the file for `return`, `gain`, `beat`, `profit`, `outperform` — `return` appears only inside the negating disclaimer |
| No "advice" / "recommend" / "signal" / "picks" as a claim | Present only inside the negating disclaimer |
| No real-money or brokerage implication | ✅ |
| "AMI", never "the AI" | ✅ |
| No "12 AI analysts" / "13 agents" headline | ✅ — the count appears once, in body text, describing the simulated desk |
| Delayed data stated | ✅ IMPORTANT block |
| Sharia: universe scoped, ruling disclaimed, `unknown` not implied as pass | ✅ — "216 of the S&P 500", "not a religious ruling" |
| No user or download count | ✅ |
| No unbuilt feature (briefing, voice, push, share cards, badges, real-time) | ✅ — verify after any edit |
| Pricing confirmed by Saiful | ❌ **BLOCKED** |
