# Ad copy — persona first, channel second

**Status: DRAFT for Saiful's review. Nothing is live; no ad account is running.**

Organised by **persona**, not by channel, per `positioning_and_personas.md` Rule 3 — one generic
ad serves none of the six. Each persona's variants are written to its **message test**: the thing
that has to be true for that person to convert.

Two gates before any of this runs:

- **Gate A (measurement)** — without attribution these variants cannot be compared, so running
  them is spending money to learn nothing (`user_acquisition_plan.md` §2).
- **Gate B (public listings)** — Apple Search Ads needs a public App Store release; Google App
  Campaigns needs a public or open-testing Play listing. Reddit is the only channel that runs
  without either.

**Every variant below has been checked against `_facts/claim_register.md`.** No returns, no
advice, no real money, no guarantees, no unbuilt features, no "the AI". §5 lists the traps
specific to ad formats.

---

## Character limits, for reference

| Format | Limit |
|---|---|
| Apple Search Ads | No creative — Apple assembles from your listing metadata and screenshots. **Your listing *is* your ad**, so `store_listing_copy.md` is the creative and the only levers here are keywords, match type and bid |
| Google App Campaign headline | 30 chars |
| Google App Campaign description | 90 chars |
| Reddit ad title | 300 chars, but treat 80 as the practical limit |

Apple's model is worth internalising: **there is no ASA ad copy to write.** Money spent there is
a bet on the listing, which is why Gate B's quality bar matters more than any ad variant on this
page.

---

## 1. The Burnt Retail Trader — "Marcus, 34"

**Message test:** converts on **respect**. The app must read as taking trading seriously, not as
a toy. Show the risk analysts shutting down a bad trade.

**Priority for paid: highest.** He already has the vocabulary and the intent, so we spend nothing
educating him on what the product is.

### Google App Campaign

Headlines (30):

```
You already paid the tuition
Rebuild the edge, not the loss
A team that argues with you
Your rules, actually enforced
Practise. No money at risk.
The Bear attacks your thesis
```

Descriptions (90):

```
Thirteen analysts debate your stock. A bear attacks your thesis. You still make the call.
Break your own risk limit and your Portfolio Manager refuses the trade, with reasons.
Simulated portfolio, real market data, and a journal that remembers why you did it.
```
`89 / 85 / 83` chars.

### Reddit

Reddit rewards a specific claim in a flat voice. Marketing register dies there.

```
Thirteen analysts argue about your stock. One of them is paid to attack your thesis.
You read the debate and make the call — simulated portfolio, real data, nothing at risk.
```

```
A trading sim where your Portfolio Manager can refuse your trade for breaking your own
stated risk limits. Simulated money. It tells you why.
```

---

## 2. The Curious Beginner — "Aisha, 26"

**Message test:** would she say "I'd actually open that every day"? Converts on **safety and
habit**, never on a feature list.

### Google App Campaign

Headlines (30):

```
Learn investing by doing it
None of your money at risk
342 lessons. Start free.
Practise before you invest
Understand what you own
Free forever. Ads, not fees.
```

Descriptions (90):

```
Learn investing by making real calls on real data — none of your money at risk.
342 lessons, daily challenges, and analysts who explain their reasoning as they work.
Find out if investing is for you before it costs you anything. Free tier, no card.
```
`79 / 85 / 82` chars.

### Reddit

```
342 investing lessons and a simulator where thirteen analysts talk through each stock
before you decide. Free tier, no card. Simulated money only.
```

---

## 3. The Competitive Optimizer — "Priya, 29"

**Message test:** leaderboards and streaks inside the first 30 seconds.

⚠️ **`so_what.md`'s hook for this persona is unusable as written.** *"Prove you'd beat the
market. We keep score"* is an implied performance claim — F13, and precisely the phrasing Apple
review flags on trading apps. Replaced.

### Google App Campaign

Headlines (30):

```
Your calls, scored
Your streak. Your rank.
Six leagues. Real scoring.
Scored on reasoning, not luck
Keep the streak. Climb.
Prove you can defend a call
```

Descriptions (90):

```
Make the call, get scored, climb the league. Simulated portfolios, real market data.
Reputation is earned on reasoning quality, not on how lucky your last trade was.
Daily challenges, streaks and leagues. Nothing at risk except your ranking.
```

**Note:** "scored on reasoning, not luck" is the honest version of the competitive pitch and it
also self-selects *against* gambling-loop users, which `vs_finelo.md` says is deliberate. Do not
soften it back toward P&L bragging.

---

## 4. The Observant Investor — halal / ethical

**Message test:** does it read as **rigorous** rather than as a marketing checkbox? This audience
has been burned by superficial "halal" labels. **The as-of date is the credibility signal — lead
with the specifics.**

Highest-differentiation persona, lowest competition, and the one with the strictest guardrail.

### Google App Campaign

Headlines (30):

```
Screen first. Then decide.
AAOIFI screening, built in
216 of the S&P 500. Dated.
Halal screening, not a label
Your constraints, enforced
```

Descriptions (90):

```
Screen your universe against an AAOIFI-based list, with an as-of date on every verdict.
216 of the S&P 500 on the current list. Your Portfolio Manager enforces it on every trade.
Optional exclusions for fossil fuels, tobacco and alcohol. A screen, not a ruling.
```
`87 / 90 / 82` chars. The second is at the limit exactly — re-measure if it is ever edited.

### Reddit / community

```
A trading simulator that screens against an AAOIFI-based compliant list — currently 216 of
the S&P 500, with the as-of date shown on every verdict. It reports a screen, not a ruling;
unscreened names are marked unknown rather than passed. Simulated money only.
```

### The guardrail — read before editing a single word here

Per `_facts/claim_register.md` N1:

| Never write | Because |
|---|---|
| "All stocks screened" | The universe is the S&P 500 parent index, not all equities |
| "AMI tells you if a stock is halal" | It reports a screen against a published list. `legal_plan_ami_trade.md` escalates actual rulings to qualified scholars |
| "Halal-certified" / "Sharia-compliant app" | We are not certified by anyone |
| Anything letting `unknown` read as approval | DEF094 was filed for exactly this failure in code. One sentence recreates it in marketing |
| AR or MS halal copy without human review | Observance-sensitive strings are excluded from machine translation. This rule extends to ads |

---

## 5. The Serious Learner — "David, 45"

**Message test:** depth and calm. **No gamification in his creative.** No streaks, no leagues, no
scores.

His natural channel — podcast sponsorship — is not funded (`positioning_and_personas.md` §5), so
these variants exist for Google App Campaigns audience targeting and organic use.

### Google App Campaign

Headlines (30):

```
Defend every position you own
Interrogate your own thesis
Ask the analyst directly
Understand what you own
Reasoning, on the record
```

Descriptions (90):

```
Understand every investment you own well enough to defend it. Visible reasoning.
Disagree with the fundamentals analyst? Ask directly, one to one, and see the argument.
A decision journal that records every call and every reason, replayable months later.
```
`80 / 87 / 85` chars.

---

## 6. The Young Speculator — "Leo, 21"

**Message test:** speed and bragging rights.

⚠️ **The most compliance-sensitive persona on the page.** `store_compliance.md` answers Apple's
*simulated gambling* question **No**, on the stated basis that we explicitly do not gamify
trading P&L. Creative that celebrates simulated wins as wins undermines that answer, and it is
the answer that keeps the 17+ rating from becoming something worse.

`so_what.md`'s hook — *"Run the riskiest strategy you can dream up. Only the wins are real"* —
has a nice ring and the second clause is a problem: it implies wins are the outcome. Use the
framing without that implication.

### Google App Campaign

Headlines (30):

```
Run the risky strategy first
Find out here, not later
Test it where it can't hurt
Your worst idea, safely
```

Descriptions (90):

```
Try the strategy you'd never risk real money on. Simulated portfolio, real market data.
Thirteen analysts will tell you why it's a bad idea. Then you can do it anyway and see.
Find out how you handle risk before leverage finds you.
```

**Rejected variants**, recorded so they don't get reinvented: anything with "moon", "10x", "big
win", "gains", "print", or a simulated P&L number. Each is either F13 or the simulated-gambling
problem, and several are both.

---

## Apple Search Ads — keyword plan

There is no creative to write. These are the four groups, all exact match to start, because broad
match on finance terms burns a $600 budget in days against brokerage bidders.

| Group | Keywords | Posture |
|---|---|---|
| **Brand** | `ami trade`, `agentic market intel`, `ami investing` | Always on. Cheap, defensive, prevents competitors buying our name |
| **Category** | `trading simulator`, `paper trading`, `investing practice`, `learn investing`, `stock market simulator`, `investing course` | The core buy. Specific enough to be affordable, high intent |
| **Halal** | `halal investing`, `halal stocks`, `sharia investing`, `sharia compliant stocks`, `islamic investing app` | **The differentiated buy.** Low competition, high intent, and we have the only real answer |
| **Competitor** | `finelo`, `investmate` | Test small. Competitor bidding is expensive and sometimes disallowed by policy — check current ASA rules first |

Rules for the first four weeks (§7 of the user plan: this is a measurement buy):

1. **Exact match only.** Add broad match only after a keyword has proven itself on exact.
2. **Cap daily spend** so no single group can consume the month.
3. **Do not add a fifth group** until the first four have attributable data.
4. **Judge nothing on under 200 attributed installs.** Creative and keyword decisions made on
   dozens of installs are noise.
5. **The halal group is the one to protect.** If the budget has to shrink, cut Category before
   Halal — Category is where we are one of many, Halal is where we are one of one.

---

## Format-specific traps

| Trap | Rule |
|---|---|
| Google auto-assembles headlines and descriptions in combinations you did not write | Every headline must be safe **next to every description**. Check the cross-product, not the list |
| Google may auto-generate assets from the listing | Turn asset auto-generation **off** until the listing is final. An auto-written headline is an unreviewed claim |
| A screenshot inside an ad creative is a claim | Reuse only frames cleared in `screenshots_and_captions.md`, including the no-large-gain rule |
| Reddit's audience treats marketing register as hostile | Flat, specific, no exclamation marks, no emoji. Say the mechanism, not the benefit |
| Creator/influencer placements put words in someone else's mouth | Brief them with the FORBIDDEN list explicitly. A creator saying "you'll make money" is our liability. Written brief in `organic_playbook.md` |
| Ad copy drifts from the listing over time | Any variant that outperforms should be promoted into the listing, so the two never contradict |

---

## Pre-flight check for any new variant

```bash
cd "/Volumes/Extreme Pro/AMI_MarketApp"
grep -niE "guarantee|returns|gains?|beat the market|profit|advice|recommend|signal|picks|\bthe AI\b|real[- ]time|briefing|share card" marketing/users/assets/ad_copy.md
```

Every hit must be inside a negation, a rejected-variant list, or a guardrail table. Anything else
is a defect in the copy.
