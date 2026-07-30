# Pitch narrative and demo script

**Status: DRAFT. Not to be used before `investor_marketing_plan.md` §2's pre-conditions clear.**

For a **20-minute one-to-one conversation** with one named person. Not a deck, not a group
presentation, not a webinar — §1 of the plan explains why the format itself is a legal constraint.

**The demo is the pitch.** The documents are the follow-up. Someone who has watched thirteen
agents argue about a stock they know does not need to be convinced the product exists, and that is
most of the work.

---

## Shape of the 20 minutes

| Minutes | What |
|---|---|
| 0–2 | The problem, in their language |
| 2–4 | The thesis |
| 4–12 | **The demo** — start a Room early, talk over it while it runs |
| 12–15 | What's built, what isn't, and the zero |
| 15–17 | The cost position, both directions |
| 17–19 | The ask and the terms |
| 19–20 | What happens next. Then stop talking |

Adapt by archetype (`investor_marketing_plan.md` §3): with **A (relationship)** spend longer on
the demo and shorter on economics; with **B (operator-angel)** compress the demo and go deep on
§4 and the objections; with **C (domain believer)** put the Sharia screen at the centre.

---

## Beat 1 — the problem (2 min)

> "Two ways people learn to invest, and both are bad. You pay for opinions you can't evaluate —
> gurus, newsletters, Reddit — or you learn by losing real money.
>
> The apps that claim to fix this don't. Finelo has 300 lessons and a chart tool and a million
> users, and it teaches trading the way Duolingo teaches Spanish. You finish knowing *about*
> trading with no idea how to actually make a call.
>
> And if you think AI solved it — ask ChatGPT whether to buy Tesla. You'll get a balanced essay
> that leans whichever way you tilted the question, from something that doesn't know what you own,
> doesn't remember you panic-sold last month, and is never wrong on the record."

Do not rush this. If they nod at the second paragraph you have the whole conversation.

## Beat 2 — the thesis (2 min)

> "The thing nobody teaches is *process*. How does an analyst form an opinion? How does a research
> team weigh a bull case against a bear case? How does risk management constrain a position? How
> does a portfolio manager say no?
>
> You can't learn that from lessons. You have to watch it happen, then do it.
>
> So: teach people to manage a team that trades for them, not to trade alone. The team transfers.
> The mechanics rot. And it maps perfectly onto AI — every role becomes an agent, and the agents
> argue where you can see them."

## Beat 3 — the demo (8 min)

**Start the Room first, then talk.** A debate takes one to three minutes to reach a verdict, and
dead air while it runs is the most common way this demo goes wrong.

### Setup, before they arrive

- Release build on the device. Never a debug build.
- Signed in, mandate already set — **do not** demo the onboarding interview live, it is three
  minutes of typing.
- Portfolio has 3–4 holdings, mixed small gains and losses. **No large gain** — a big simulated
  number invites exactly the misreading we spend the whole conversation avoiding.
- Sharia flag **on**, one ethical exclusion on.
- Two or three past Rooms already in the journal, so beat 3e has something real to open.
- Network verified. `curl -s https://api-alpha.agenticmarketintel.ai/v1/health`

### Sequence

**3a. Show the mandate (1 min).** Settings → mandate.

> "This is mine. Goals, horizon, risk limits, constraints — long-only, Sharia screening on. AMI
> interviewed me for it in a conversation, not a form. Every one of the thirteen agents reads this
> before it says anything, so when they argue they're arguing about *my* portfolio."

**3b. Start the Room (30 sec).** Ask them for a ticker they have an opinion about. Their choice
matters — a stock they already argue about turns a demo into a conversation.

> "Pick something you've got a view on."

Tap Convene. **Now it is running, and you talk over it.**

**3c. Narrate the roster while it streams (3 min).** Point at each agent as it reports.

> "Four analysts first — fundamentals, market technicals, news, social sentiment. Real data;
> prices are Yahoo, delayed fifteen minutes, which is irrelevant in a simulator.
>
> Then it gets interesting. A bull researcher builds the long case. A bear researcher's *entire job*
> is to attack it. They're not being balanced — they're adversaries, and a research manager
> adjudicates between them.
>
> Then three risk analysts argue about size: aggressive, conservative, neutral. And a portfolio
> manager who has the final say and can refuse the trade.
>
> This is a real multi-agent system — 938 of these have completed, 97.7% of everything started."

**3d. The verdict, then the veto (2 min).** When the verdict lands, read the split, not the answer.

> "Note it doesn't just say buy. It shows me where they disagreed and how it resolved. That's the
> product — I'm not buying an answer, I'm reading an argument."

Then submit a trade that breaks the mandate.

> "Watch this. I'll try to buy more than my own risk limit allows."

It gets refused, with a reason.

> "My own portfolio manager just refused my trade for breaking my own stated rules. Try getting
> ChatGPT to do that."

**This is the moment that converts operator-angels.** It is the clearest possible demonstration
that this is a system, not a prompt.

**3e. Sharia screen + journal (1.5 min).** Show a ticker's screening verdict.

> "AAOIFI-based screen. 216 of the S&P 500 on the current list, and every verdict carries its
> as-of date. Unscreened names come back as *unknown*, not as a pass — that distinction matters
> enormously to the people who need this, and nobody in this category builds it. Same mechanism
> handles fossil-fuel, tobacco and alcohol exclusions."

Then the journal.

> "And every one of these is recorded — the debate, my call, my reasoning. In six months this is
> the only honest account of how I actually think under uncertainty. It's also why people don't
> leave: the journal gets more valuable the longer you stay."

**If the demo breaks:** say so plainly, move on, offer to send a recording. A founder who is
unbothered by a bug reads better than one who is flustered — and the person you are talking to has
seen software before.

## Beat 4 — what's built, and the zero (3 min)

Hand over the one-pager. Let them read the table.

> "One person, five months, 1,406 commits. 342 lessons, each in three languages — that's a
> thousand files of verified content. Thirteen agents. Live on TestFlight and Play internal
> testing today.
>
> And: **zero revenue. No payment has ever processed. Zero waitlist signups. No public store
> listing. No real users.**
>
> I'm telling you that before you ask, because you'd find it in one question and then you'd stop
> believing the numbers above it.
>
> The way to read this: the build risk is retired, the demand risk isn't. Which is the entire
> reason I'm asking you for money."

**Never soften the zero.** It is the most credibility-generating sentence in the conversation, and
it is also the logical foundation of the ask.

## Beat 5 — the cost position (2 min)

> "Two things make this unusually cheap to run.
>
> The AI runs on hardware I already own — a model server on my own network. Every competitor pays a
> cloud provider per token; my marginal cost per debate is electricity. **And it doesn't scale
> forever.** If I move to Google Cloud, infrastructure goes to somewhere between USD 750 and 2,550
> a month, which at the top end is more than the entire raise. That's disclosed in the agreement,
> not buried.
>
> Second: one person plus AI produces a team's output at one person's burn. That's also the bus
> factor, which you should ask me about."

**Always give both directions.** An operator-angel who spots a one-sided cost argument will
discount everything else you said.

If they push into unit economics: the spec's model projects a Trader-tier gross margin around 46%,
but that model prices cloud LLMs and reality is on-prem, so today's margin is better and it
inverts on migration. **Label it a projection every time.** There is no revenue to validate it
against.

## Beat 6 — the ask and the terms (2 min)

> "USD 24,000 over twelve months. Two thousand a month. Seventy percent of it is advertising —
> Apple Search Ads, Google App Campaigns, Reddit. The rest is app-store fees, hosting, electricity,
> tooling.
>
> What you're buying is the answer to one question: does this convert? The product exists. Nobody
> has ever tried to acquire a user for it.
>
> In exchange: [SET]% of monthly gross profit, pro rata to what you put in, until you've had
> [SET]× your money back. Then it stops. Not equity — no shares, no board seat, no vote. Not a
> loan — no repayment date, no interest. A contractual share of profit, and nothing else.
>
> You could get nothing. There's no minimum, no timeline, and if a month loses money nothing is
> owed. Only put in what you can lose completely."

## Beat 7 — next steps (1 min)

> "Take the agreement. Read it properly. Take it to your own advisor — I'd rather you did.
>
> If you're in, we agree an amount and a start date. If you're not, tell me and I'll stop asking."

**Then stop talking.** The most common failure in beat 7 is continuing to sell past the ask.

---

## Two things never to do

**Never improvise a legal answer.** "Is this a security?" → *"That's a question for a lawyer, and
mine is looking at it. I'm not going to guess in front of you."* Improvising here is the single
highest-cost mistake available in this conversation.

**Never imply momentum that doesn't exist.** If nobody has committed, the answer to "who else is
in?" is *"nobody yet — you'd be first."* Implied momentum is the one lie that, when it unravels,
retroactively poisons every true thing you said.

---

## Materials, in order of use

| Order | Item | When |
|---|---|---|
| 1 | The device | Beat 3 — the whole conversation |
| 2 | `one_pager.md` | Beat 4, handed over |
| 3 | `backer_faq.md` | Only if asked; do not pre-empt objections nobody raised |
| 4 | `quarterly_report_template.md` | Optional, and effective — a blank reporting template says the obligation was read |
| 5 | The agreement itself | **Counsel-cleared only**, after the meeting, to that named person |
