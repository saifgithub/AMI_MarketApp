# Investor marketing plan — the $24k backer raise

**Objective:** raise **USD 24,000** (USD 2,000/month × 12 months) from **4–8 named private
backers** on the profit-participation instrument in
`legal/agreements/profit_sharing_agreement_template.md`, without creating a securities problem.

**Not in scope:** an equity round. Saiful chose the backer raise as drafted. That choice is
load-bearing for everything below — the instrument is a contractual profit share, not shares,
which changes who the audience is, what they get, and what we are legally allowed to do to find
them.

Read `_facts/claim_register.md` first. The traction block (T1–T6) is **required** in investor
material, including the zero.

---

## 1. The gate that shapes everything else

The agreement is **v0.3 — draft, unsent, unsigned**. It carries five `[LAWYER REVIEW REQUIRED]`
flags, two unset placeholder values, one `[FOUNDER TO CONFIRM]`, and it is written against a
founder with **no corporate entity**, so today every obligation in it is Saiful's personal
obligation, backed by his personal assets.

The document says this about itself, in its own header: *"Do not send this to a prospective
backer, and do not sign anything based on it, before a Malaysia-qualified lawyer reviews it."*

**Marketing an investment is solicitation.** Taking money from multiple people in exchange for a
share of profits is, as the agreement's own §1 flag says, "the textbook fact pattern for an
'investment contract' / collective-investment-scheme test" under the Malaysian Capital Markets
and Services Act 2007. Whether it needs a prospectus, fits an exemption, or has to be
restructured is a question for counsel — and the answer changes depending on **how we go looking
for backers**, not just on what the contract says.

So the plan is built on one constraint:

> **Private, named, pre-existing relationships only. One person at a time.**

Which rules out, until counsel clears otherwise:

| Not permitted | Why |
|---|---|
| An investor page on the website | Public offer. The agreement explicitly says this instrument is "never published to the website" |
| A LinkedIn / X post announcing a raise | Public solicitation |
| Cold outreach to anyone | No pre-existing relationship |
| A group email or WhatsApp group to prospects | Multiple offerees at once — exactly the aggregation risk in lawyer-checklist item #6 |
| A pitch deck circulated onward | We lose control of who received an offer |
| Anything on a startup/angel platform | Public offer, and platforms have their own regulatory posture |
| Sharing Schedule B's spend projections widely | Checklist item #7 flags that detailed spend projections "read more like a prospectus/PPM than a private contract" |

Permitted: a one-to-one conversation with someone Saiful already knows, followed by a document
handed to that named person.

**Note the asymmetry with the user plan.** `positioning_and_personas.md` Rule 1 says never lead
with AI agents — that is for *users*. For backers, the agent architecture **is** the story,
because it is the moat. The two plans lead with opposite things, deliberately.

---

## 2. Pre-conditions before conversation #1

None of these are marketing tasks. All of them block marketing.

| # | Item | Why it blocks | Status |
|---|---|---|---|
| P1 | **Counsel review** of the agreement — the lawyer-only checklist, items 1–7, is already written into the document | The securities characterisation determines whether this plan is legal as written | Not started |
| P2 | **Decide whether to incorporate first** (a Malaysian Sdn Bhd is the natural fit) | Until an entity exists, backers contract with Saiful personally. §10's novation mechanism handles the transition, but a backer who understands the difference will ask, and "we'll novate later" is a weaker answer than "here is the company" | Open |
| P3 | **Set `Backer Pool Percentage`** — currently a 20% placeholder marked `[FOUNDER TO SET]` | You cannot pitch terms you have not decided | Placeholder |
| P4 | **Set `Return Cap`** — currently 2.5×, `[FOUNDER TO SET]` | Same. This is the number a backer will anchor on | Placeholder |
| P5 | **Resolve the founder-compensation conflict** — §1 excludes the Founder's own salary from Direct Costs, flagged `[FOUNDER TO CONFIRM]` and described in the agreement as "a real conflict of interest to manage in practice" | A sophisticated backer will find this in one read. Have the answer before they ask, not after | Flagged, unresolved |
| P6 | **A working demo on a device** | The demo is the pitch (§7). A build that fails in front of a backer costs more than no meeting | `0.1.0+59` on TestFlight + Play internal ✅ |
| P7 | **Ask counsel about non-Malaysian backers**, especially US persons | Different jurisdictions, different exemptions. Checklist item #5 already flags tax treatment as unaddressed | Not started |

**P1 is a hard gate.** Every other item can proceed in parallel, but no conversation happens
before counsel has read the instrument.

---

## 3. Who to approach

Not "investors." The instrument is unusual — capped profit share, no equity, no voting rights, no
board seat, non-transferable — which makes it wrong for a professional investor and right for
someone who wants exposure to a specific person's specific project.

### Archetype A — Relationship backers

- **Who:** family, friends, former colleagues. Malaysia-resident, mostly.
- **Cheque:** USD 2,000–6,000 total (USD 167–500/month).
- **Decides on:** trust in Saiful, plus seeing the app actually work.
- **What they need:** the demo, the one-pager, and a plain explanation that they might get
  nothing back. Do not over-engineer the financials for this group; over-explaining reads as
  selling.
- **Risk to manage:** these are the relationships that survive a failed venture only if the
  downside was stated clearly and repeatedly. §8 of the agreement exists for this.

### Archetype B — Operator-angels

- **Who:** people in KL or Singapore who have shipped a consumer app or worked in fintech. The
  ones who will ask about CAC, churn and store economics.
- **Cheque:** USD 6,000–12,000.
- **Decides on:** the cost position (§4 beat d) and whether the moat is real.
- **What they need:** the unit-economics conversation with the on-prem correction *and* the GCP
  contingency (P1–P3 in the register, plus the both-directions rule). They will spot a
  one-directional argument.
- **Highest-value archetype**, because two of them close the raise and they bring judgement worth
  more than the money.

### Archetype C — Domain believers

- **Who:** people in halal-finance or trading-education circles who care that this exists.
- **Cheque:** varies, often small.
- **Decides on:** the mission — and now, on a **shipped** Sharia screen rather than a roadmap
  promise (N1). This archetype got materially more approachable when DEF094 was fixed.
- **What they need:** to see the screening work, with the as-of date, and to hear the `unknown`
  state described honestly. This audience is unusually good at detecting a superficial halal
  claim.

### Qualification bar, from the agreement's own §8

Every backer must genuinely understand: early-stage, unproven, real possibility of receiving
**less than their contribution back, or nothing at all**, and they are contributing money they
can afford to lose in full. If a prospect does not clear that bar, they are not a prospect —
regardless of enthusiasm or cheque size. Walking away from an unsuitable backer is cheaper than
the alternative.

---

## 4. The narrative — five beats

Full talk track in `assets/pitch_narrative.md`. The spine:

**(a) The category is broken.** Education apps teach charts. Finelo and its neighbours teach
trading the way Duolingo teaches Spanish — short lessons, streaks, quizzes, a basic simulator,
one AI helper bolted on the side. The user ends up *knowing about* trading with no scaffolding
for how to actually decide anything. And generic AI gives one confident opinion with no memory
of you and no accountability for being wrong.

**(b) The insight.** From `vision_and_positioning.md`:

> *"Teach people to manage a team that trades for them, not to trade alone."*

The team transfers; the mechanics rot. It also maps naturally onto AI — each role becomes an
agent, and the agents debate visibly, so the user learns by watching, then by briefing, then by
overriding.

**(c) It's built.** This is the beat that separates the conversation from a pitch deck. All
`VERIFIED`, all citable:

- 1,406 commits, 1,269 backend tests passing
- 342 lessons, each in English, Arabic and Malay — 1,026 files
- 13 agents; 938 completed multi-agent debates at a 97.7% completion rate
- Live AAOIFI Sharia screening — 216 compliant of the S&P 500, as-of dated per verdict
- Real Yahoo market data, 15-minute delayed
- Shipping on TestFlight **and** Play internal testing today, at `0.1.0+59`

**(d) The unfair cost position.** Two structural advantages, and the honest limits of each:

- **Inference runs on hardware Saiful already owns** — an on-prem vLLM host on his own LAN. Every
  competitor in this category pays per token to a cloud provider; today our marginal LLM cost is
  electricity. *Limit, stated in the same breath:* it does not scale past a point, and the
  planned GCP migration puts infrastructure at USD 750–2,550/month, which the agreement's own
  Schedule B discloses as a live contingency.
- **One founder plus AI produces a team's output at one person's burn.** 1,406 commits and a
  three-language content corpus, solo. *Limit:* it is also the bus factor, which is objection #1
  in `assets/backer_faq.md`.

**(e) The ask.** USD 24,000 over 12 months buys runway and, specifically, **the advertising to
find out whether this converts** — 70% of the raise goes to user acquisition per Schedule B.
What a backer is buying is *the answer to whether this works*, priced at 20% of monthly gross
profit until they have received 2.5× their contribution.

Say what it is not: not a loan, no repayment date, no interest, no equity, no shares, no voting
rights, no board seat, no claim on assets or IP. A contractual right to a share of profit,
nothing more.

---

## 5. The proof stack — including the zero

Present `VERIFIED` rows only. And present the traction block **completely**:

| | |
|---|---|
| Revenue to date | **USD 0. No payment has ever processed.** |
| Waitlist signups | **0**, on a live public site |
| Users | Closed alpha only. No public store listing. No real external user base |
| What is built | Everything in §4(c) |

**State T1 and T2 plainly rather than omitting them.** Three reasons. Diligence finds them in one
question. An operator-angel who discovers omitted zeros stops believing the verified numbers too.
And the zero is *the reason for the raise* — the money exists to buy the first real users, so a
raise pitched against zero traction is coherent, while a raise pitched against implied traction
is not.

The framing that is both honest and strong: **the build risk is retired; the demand risk is
not.** That is precisely what USD 24,000 is for.

---

## 6. Objections

Answers in `assets/backer_faq.md`. The eight that decide it:

| # | Objection | One-line posture |
|---|---|---|
| 1 | Solo founder — what if you're hit by a bus? | Real and unmitigated. Name it, describe what exists (documented repo, no undocumented tribal state), don't pretend it's solved |
| 2 | Zero revenue | Correct. Build risk retired, demand risk not. That's what the money buys |
| 3 | No entity — am I contracting with a person? | Yes, today. §10 novates on incorporation. P2 may change this before any conversation |
| 4 | Is this a security? | Counsel's call, not the founder's. Say so. Do not improvise a legal answer |
| 5 | Who else is in? | Answer honestly whatever the truth is. Never imply momentum that doesn't exist |
| 6 | What if Finelo copies the 12-agent debate? | `vision_and_positioning.md`'s moat analysis — the orchestration plus making it legible to non-technical users, plus mandate-level personalisation, plus the journal's compounding switching cost. Plausible, not certain |
| 7 | On-prem inference doesn't scale | Correct, and disclosed in Schedule B with the dollar range. It buys runway now, not forever |
| 8 | What happens in month 13? | The contribution period ends; profit share continues to the cap or until operations cease. Be specific about what a backer does and does not keep |

Two rules on all eight: **never improvise a legal answer** (route to counsel), and **never
answer #5 with anything other than the literal truth** — implied momentum is the objection that
destroys the other seven if it unravels.

---

## 7. Sequence — a 6-week campaign

| Week | Activity |
|---|---|
| 0 | **P1–P7 clear.** No conversation before counsel has read the instrument |
| 1 | Build the list: **30 names**, from Saiful's actual relationships. Tier each A/B/C. Anyone who fails §3's suitability bar comes off the list now, not later |
| 2 | Warm 1:1 approach — WhatsApp or email, to one named person, from `assets/outreach_templates.md`. Ask for a conversation, not for money |
| 2–4 | **20-minute demo on a real device.** Script in `assets/pitch_narrative.md`. The demo is the pitch; the documents are the follow-up |
| 2–4 | Leave the one-pager with anyone who asks a second question |
| 3–5 | 72-hour follow-up after each demo. If they need the agreement, it goes out **counsel-cleared**, to that named person only |
| 4–6 | Close: Schedule A entry, first instalment date, bank details. §2 allows a backer's participation to begin on their first payment, so the raise can close in stages rather than all at once |
| 6 | Whatever is unclosed goes to a "not now" list with a specific revisit trigger, not a vague one |

**Never a group message.** Not a BCC, not a WhatsApp group, not a shared deck link. One named
person per conversation — §1's constraint and checklist item #6's aggregation risk.

### Pipeline tracker

Keep this as a private local file, not in the repo — it contains third-party names.

| Field | Values |
|---|---|
| Name / relationship | — |
| Archetype | A / B / C |
| Suitability (§3 bar) | pass / fail — fail means remove |
| Stage | listed → approached → demo booked → demo done → docs sent → committed → paid → declined → not now |
| Indicated amount | USD |
| Jurisdiction | for P7 |
| Last touch | date |
| Next action + date | — |

### Pipeline targets

**Targets, not a forecast — there is no historical conversion data to project from:**

~30 conversations → ~12 demos → ~6 commitments at ~USD 4,000 average = USD 24,000.

Schedule A's note allows closing early or extending to more backers, adjusting each backer's pro
rata share accordingly — so 4 large or 8 small both work.

---

## 8. Reporting — build it before you need it

§5 of the agreement obliges a **brief written quarterly summary** to every backer: Monthly
Revenue, Direct Costs, Monthly Gross Profit, and amounts paid to the Backer Pool, for each month
in the quarter. Backers may request supporting detail once a year. No audited financials are
promised, and none exist.

Two reasons to build the template now (`assets/quarterly_report_template.md`) rather than at the
first quarter end:

- The first report is due one quarter after the first instalment, which will arrive during a busy
  month.
- Handing a prospective backer the *blank template* during the pitch is a credibility move. It
  says the reporting obligation was read and taken seriously, which is unusual at this size and
  costs nothing.

§9 obliges backers to keep those summaries confidential. Mention it when the template comes out.

---

## 9. Metrics and kill criteria

Track four numbers: conversations had, demos given, commitments, dollars committed.

**Kill criterion: 15 qualified conversations producing zero commitments means the instrument or
the story is wrong.** Stop and re-cut rather than grinding through the remaining names — a list
of 30 relationships is a finite, non-renewable asset, and burning it on a pitch that isn't
landing costs more than the raise.

Diagnostics to run at that point, in order of likelihood:

1. **The instrument.** A capped 2.5× profit share on a pre-revenue app may simply be unattractive
   versus the risk. P3/P4 are still placeholders — the numbers may need to move.
2. **The zero.** If T1/T2 are killing conversations, the raise may need to follow a first cohort
   rather than fund one. That inverts the sequencing with the user plan and is worth knowing.
3. **The archetype mix.** If A converts and B doesn't, the story is too technical. If B converts
   and A doesn't, it's too abstract.
4. **The ask size.** USD 24,000 from 4–8 people may be the wrong shape; one backer at USD 24,000
   is a different, simpler conversation with a different securities profile — a counsel question.

Record which one it was. A raise that fails without a diagnosis fails twice.

---

## 10. What this plan does not do

- **It does not send anything.** No document in `investors/` goes to any person before P1 clears.
- **It does not set the terms.** P3, P4 and P5 are Saiful's decisions.
- **It does not give legal advice.** Where a question is legal, the answer is "counsel."
- **It does not edit the agreement.** The instrument is `legal/`'s, not marketing's.
