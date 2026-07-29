# AMI Trade — backer one-pager

> **DRAFT — DO NOT SEND.** Blocked on the pre-conditions in `investor_marketing_plan.md` §2:
> counsel review of the profit-participation agreement (P1), and Saiful's decisions on the two
> placeholder terms (P3, P4). Placeholders below are marked `[SET]`.
>
> This is a private document for one named person at a time. Never posted, never circulated,
> never linked.

---

## What it is

AMI Trade is a simulation-only investing-education app. You are the CEO of a thirteen-person AI
analyst team. Pick a stock, and they research it, debate it in front of you, and reach a verdict —
then **you** make the call, and it runs in a simulated portfolio that records your reasoning.

No real money. No brokerage. Not advice. Permanently, by design — that firewall is what keeps a
one-person company out of financial-services regulation.

## The problem

Education apps teach charts. Finelo and its neighbours teach trading the way Duolingo teaches
Spanish: short lessons, streaks, quizzes, a basic simulator, one AI helper bolted on the side. The
user ends up *knowing about* trading with no scaffolding for how to decide anything.

Generic AI has the opposite problem. It gives one confident opinion, forgets who you are, agrees
with whichever way you tilted the question, and is never held to account for being wrong.

Neither teaches **judgement**, which is the only thing that transfers.

## The thesis

> Teach people to manage a team that trades for them, not to trade alone.

The team transfers; the mechanics rot. It also maps naturally onto AI — each analyst role becomes
an agent, the agents disagree visibly, and the user learns by watching, then by briefing, then by
overriding.

## What is already built

Not a deck-stage idea. Measured 29–30 July 2026:

| | |
|---|---|
| Commits | **1,406** on `main`, 1,269 backend tests passing |
| Curriculum | **342 lessons**, each in English, Arabic and Malay — 1,026 files |
| Agents | **13** — 12 analyst-team roles plus AMI, the Concierge |
| Multi-agent debates run | **938 completed** of 960 started — a 97.7% completion rate |
| Sharia screening | **Live.** AAOIFI-based, 216 compliant of the 503-name S&P 500 index, as-of date on every verdict |
| Market data | Real Yahoo prices, 15-minute delayed |
| Shipping | `0.1.0+59`, on **TestFlight and Google Play internal testing** today |
| Languages | English, Arabic with full right-to-left, Malay |

Built by one person, with AI assistance, over roughly five months.

## What is not built, and what has not happened

| | |
|---|---|
| Revenue to date | **USD 0. No payment has ever processed.** |
| Public store listing | None. Closed testing only |
| Real user base | None. Closed alpha |
| Waitlist signups | **0** |
| Not yet built | Push notifications, daily briefings, referral sharing, GCC/Tadawul/Bursa coverage, real-time data |

**The build risk is retired. The demand risk is not.** That is exactly what this raise is for.

## The cost position

Two structural advantages, each with its limit stated:

**Inference runs on hardware the founder already owns.** An on-prem model server on his own
network serves every one of the thirteen agents. Competitors in this category pay a cloud provider
per token; today our marginal cost per debate is electricity.
*Limit:* it does not scale indefinitely. A planned migration to Google Cloud would put
infrastructure at roughly USD 750–2,550/month — disclosed in Schedule B of the agreement as a live
contingency, not a hypothetical.

**One founder plus AI produces a team's output at one person's burn.** 1,406 commits and a
trilingual 342-lesson corpus, solo.
*Limit:* it is also the bus factor, and it is the first question a careful backer should ask.

## The ask

**USD 24,000 over 12 months — USD 2,000/month.**

Per Schedule B, indicatively:

| | Monthly | 12 months | Share |
|---|---|---|---|
| Advertising & user acquisition | USD 1,400 | USD 16,800 | 70% |
| Infrastructure & tooling | USD 600 | USD 7,200 | 30% |

**70% of this money buys the answer to one question: does this convert?** Everything else is
already built. The infrastructure line is app-store fees, domain, hosting, electricity for
hardware already owned, and AI development tooling.

## The terms

| | |
|---|---|
| Instrument | Contractual profit participation. **Not equity, not a loan** |
| You receive | `[SET]`% of Monthly Gross Profit (revenue minus direct costs), pro rata to your contribution |
| Until | You have received `[SET]`× your contribution. Then payments stop |
| Starts | The month after AMI Trade first generates positive monthly gross profit |
| Reporting | A written summary each quarter: revenue, direct costs, gross profit, amounts paid |
| You do not receive | Shares, ownership, voting rights, a board seat, or any claim on assets or IP |
| Transferable | No — deliberately |
| Governing law | Malaysia |

## The risk

There is a real possibility of receiving **less than your contribution back, or nothing at all**.

There is no guaranteed minimum payment, no guaranteed timeline to profitability, and no obligation
to fund a shortfall from any other source. If a month is unprofitable, nothing is owed for that
month and the shortfall does not carry forward.

The venture is early-stage and unproven, with zero revenue to date. There is currently **no
incorporated entity**, so until one is formed and the agreement is novated to it, you are
contracting with Saiful personally.

**Contribute only money you can afford to lose in full.**

## What happens next

1. Read the agreement. Ask anything.
2. Take it to your own advisor if you want one. That is encouraged, not discouraged.
3. If you're in, we agree an amount and a start date, and you go on Schedule A.

---

*AMI Trade · Saiful · [contact] · This document describes a private arrangement between named
parties. It is not an offer to the public and is not a prospectus. Figures marked as measured were
measured on 29–30 July 2026; projections are labelled as such and are not forecasts.*
