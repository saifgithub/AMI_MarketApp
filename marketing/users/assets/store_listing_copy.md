# Store listing copy — App Store + Google Play

**Status: DRAFT for Saiful's review. Not submitted.**

Language: **EN only.** `retranslate:[ar,ms]` — AR and MS listings are a v1.0 item and, per
`_facts/claim_register.md` N1/H5, **any halal copy in AR or MS requires human review before it
ships**. Machine translation is not acceptable for observance-sensitive strings.

Built on the draft already in `docs/initial_specs/09_compliance/store_compliance.md`, with three
changes: re-led on outcome rather than agent count (`positioning_and_personas.md` Rule 1), Sharia
screening added (it ships — N1), and every forbidden claim stripped.

⚠️ **BLOCKED: pricing.** The subscription block below is a marked placeholder. Three sources
disagree on price (`user_acquisition_plan.md` §11) and both stores require accurate price and
term disclosure — a wrong number is a rejection, not a correction.

---

## Apple App Store

### App name (30 char max)

```
AMI Trade
```
`9 chars.` Keep it short — the subtitle carries the meaning, and Apple truncates aggressively on
the search results row.

### Subtitle (30 char max)

Recommended:

```
Practice investing, risk-free
```
`29 chars.` Leads with the outcome and puts "risk-free" — which here means *simulation*, not
*guaranteed* — next to the verb.

Alternatives, all within limit:

| Option | Chars | Note |
|---|---|---|
| `Practice investing, risk-free` | 29 | **Recommended** |
| `Learn investing by doing it` | 27 | Softer, more education-forward for review |
| `Your 13-analyst practice floor` | 30 | Distinctive, but leads with the mechanism |
| `Your 12 AI analysts.` | 20 | The old `store_compliance.md` draft. **Rejected** — leads with agents |

### Promotional text (170 char max, editable without review)

```
342 lessons in English, Arabic and Malay. Thirteen specialists debate any stock in front of
you. Screen your universe against an AAOIFI compliant list before you decide.
```
`169 chars` of 170 — tight. Verify in the console after any edit. This field can be changed
without resubmitting, so it is where seasonal or feature-launch messaging goes.

### Description

Opens with the outcome. Agents arrive in paragraph two.

```
Most people learn investing the expensive way — they follow opinions they can't evaluate, or
they lose real money finding out. AMI Trade is the third way: practise making the actual call,
on real market data, with none of your money at risk.

Pick a stock. A team of thirteen specialists goes to work on it in front of you — fundamentals,
market technicals, news, social sentiment, someone building the bull case, someone attacking it,
three risk analysts arguing about position size. You read the debate. You cross-examine anyone
you disagree with. Then you make the call, and AMI runs it in your simulated portfolio.

It's the difference between reading about swimming and getting in the pool — except the pool has
no sharks.

WHAT MAKES THIS DIFFERENT

• A team, not a chatbot. Thirteen specialists with defined roles and visible reasoning — twelve
  analysts plus AMI, your Concierge. They disagree with each other, on the record.
• They know your book. Your goals, your risk limits, your constraints and your holdings shape
  what every one of them says. The debate is about your portfolio, not a hypothetical.
• Your Portfolio Manager can say no. Submit a trade that breaks your own stated mandate and it
  gets refused, with the reason. Structured disagreement is the point.
• Ethical and Sharia screening, built in. Screen your universe against an AAOIFI-based compliant
  list — currently 216 of the S&P 500 — with the as-of date shown on every verdict. Optional
  exclusions for fossil fuels, tobacco and alcohol.
• A decision journal that compounds. Every debate, every call and every reason is recorded and
  replayable. Six months in, you can see exactly how you think — including the biases you'd
  rather not.
• 342 lessons, in three languages. English, Arabic with full right-to-left support, and Malay.
  Plus daily challenges, streaks and leagues.

WHO IT'S FOR

• You want to understand your own investments well enough to defend them.
• You've traded before, it went badly, and you want to rebuild the discipline somewhere losses
  don't cost anything.
• You want to know whether you're actually any good at this before you find out expensively.
• You need your investing to respect Sharia or ethical constraints, and you're tired of apps
  that ignore that.

HOW IT WORKS

1. AMI interviews you about your goals, horizon, risk tolerance and constraints. That becomes
   your mandate, and it shapes every agent.
2. Pick a stock. Convene the room. Watch thirteen specialists work through it and reach a
   verdict.
3. Make your call. AMI simulates it, tracks it, and remembers your reasoning.

IMPORTANT

AMI Trade is an educational simulation. It is not investment advice, not a brokerage, and not a
recommendation service. All trading is simulated with virtual money — there is no real-money
trading, no brokerage connection, and no way to buy or sell an actual security. Market data is
delayed by 15 minutes. Sharia screening reports a screen against a published compliant list; it
is not a religious ruling. Nothing in this app is a prediction, and nothing here forecasts a
return.

[SUBSCRIPTION BLOCK — PLACEHOLDER, DO NOT SUBMIT WITHOUT SAIFUL'S CONFIRMED PRICING]
Floor Pass is free, permanently, with ads. Paid tiers unlock the full analyst team, unlimited
sessions and full journal history. Prices, terms, trial length and cancellation instructions go
here — exact figures pending. Subscriptions renew automatically unless cancelled at least 24
hours before the period ends; manage or cancel in your App Store account settings.
Privacy Policy: https://www.agenticmarketintel.ai/privacy/
Terms of Service: https://www.agenticmarketintel.ai/terms/
```

### Keywords (100 char max, comma-separated, no spaces, don't repeat the name or subtitle)

```
halal,sharia,islamic,investing,paper,simulator,stocks,analysis,portfolio,course,practice,ethical
```
`96 chars.`

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
First public release. Thirteen specialists, 342 lessons in three languages, AAOIFI Sharia
screening, and a simulated portfolio that remembers why you did what you did.
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
AMI Trade: Practice Investing
```
`29 chars.` Play gives more room in the title than Apple's name field and weights it for search,
so the outcome verb goes here.

### Short description (80 char max)

```
Thirteen analysts debate any stock. You make the call. Nothing at risk.
```
`71 chars.` Counts below are measured, not estimated — Play enforces strictly and the obvious
phrasing (`…None of your money at risk.`) is **82 chars and would be rejected.**

Alternatives:

| Option | Chars |
|---|---|
| `Thirteen analysts debate any stock. You make the call. Nothing at risk.` | 71 |
| `13 analysts debate any stock. You make the call. None of your money at risk.` | 76 |
| `Practise investing for real. Simulated money, real data, a team that argues.` | 76 |
| `Learn investing by making the call. Halal screening built in. Zero risk.` | 72 |
| ~~`Thirteen analysts debate any stock. You make the call. None of your money at risk.`~~ | **82 — over limit** |

### Full description (4,000 char max)

Reuse the App Store description verbatim, with three substitutions:

1. "App Store account settings" → "Google Play subscription settings".
2. Add, in the IMPORTANT block: *"Account and data deletion: request at
   https://www.agenticmarketintel.ai/ami-trade/sad-to-see-you-go — no install required."* This
   satisfies Play's 2023 deletion policy, and the page is already live.
3. Play renders limited markup — check the bullet characters survive the console's formatter.

Current draft length is ~2,900 characters, so there is room. Do not fill it with keywords; Play
does not reward stuffing and it reads badly.

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
| Leads with education / simulation | Name, subtitle, description ¶1, review notes ✅ |
| Disclaimer visible in ≥1 screenshot | `screenshots_and_captions.md` frame 6 |
| No return, gain or performance claim | Grep the file for `return`, `gain`, `beat`, `profit` |
| No "advice" / "recommend" / "signal" / "picks" | Present only inside the negating disclaimer ✅ |
| No real-money or brokerage implication | ✅ |
| "AMI", never "the AI" | ✅ — appears twice, both as the name |
| Delayed data stated | ✅ IMPORTANT block |
| Sharia: universe scoped, ruling disclaimed, `unknown` not implied as pass | ✅ — "216 of the S&P 500", "not a religious ruling" |
| No user or download count | ✅ |
| No unbuilt feature (briefing, voice, push, share cards, badges, real-time) | ✅ — verify after any edit |
| Pricing confirmed by Saiful | ❌ **BLOCKED** |
