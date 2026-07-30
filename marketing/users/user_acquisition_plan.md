# User acquisition plan

**Objective:** get AMI Trade from effectively zero real users to a first genuine cohort, then to
paid acquisition we can *measure*.

**Budget posture, locked by Saiful:** $0 now, organic only. $1,400/month once backer money
lands (Schedule B of `legal/agreements/profit_sharing_agreement_template.md`). That money does
not exist yet — `investors/investor_marketing_plan.md` is the plan to raise it, and this plan
must produce results without it.

**Store posture, locked by Saiful:** go public on **both** stores.

Read `positioning_and_personas.md` and `_facts/claim_register.md` first. Every number below
traces to a register row.

---

## 1. Where we actually are

| | |
|---|---|
| Real external users | Effectively zero (T4 — we cannot state a number, and no asset may imply one) |
| Waitlist signups | **0**, all time, on a public live site (T2) |
| Revenue | **$0**. No payment has ever processed (T1) |
| Store presence | Closed testing only — TestFlight + Play internal (T5) |
| Product analytics | None |
| Install attribution | None |
| Crash reporting | `sentry_flutter` installed, `SENTRY_DSN` empty on Alpha (F12) |
| Push | Not built (F3) |
| Lifecycle email | Resend works, but only `send_magic_link` is implemented |

Two headlines matter more than the rest.

**The site has been live for months and has produced zero signups.** That is a *measurement*
problem before it is a traffic problem. With no analytics on `www.agenticmarketintel.ai`, we
cannot distinguish "nobody visits" from "hundreds visit and the page doesn't convert" — and
those two diagnoses have opposite fixes. Anything we do next without instrumenting first is
guesswork.

**The site leads with agent architecture.** *"13 AI agents. One decision. No shortcuts."* is a
builder's hero. `so_what.md` argues users buy outcomes, not agents, and it is right (Rule 1).
This is not proven to be the cause of the zero, but it is the cheapest hypothesis to test and
the first to fix.

So: this is a launch plan from zero. It is not a growth-optimisation plan, and treating it as
one — tuning channels against a funnel we cannot see — is the main way it could fail.

---

## 2. Three gates before a dollar is spent

Hard prerequisites, in this order. Spending Schedule B money before these are closed converts
the raise into an unmeasurable expense.

### Gate A — measurement

Without attribution, $1,400/month buys installs we cannot attribute, from creative we cannot
compare, into a funnel we cannot see. The first month of spend would produce one usable number
(total installs) and no decisions.

Minimum viable, in priority order:

1. **One product-analytics SDK** in `mobile/`, with a written event taxonomy — not ad-hoc
   `logEvent` calls. Minimum events: `app_open`, `onboarding_start`, `mandate_set`,
   `room_started`, `room_completed`, `trade_submitted`, `journal_viewed`, `lesson_completed`,
   `paywall_shown`, `paywall_dismissed`, `purchase_completed`.
2. **Install attribution**, so an install can be traced to a campaign. This is the piece with no
   workaround: Apple Search Ads and Google App Campaigns each report their own installs, and
   without a common attribution layer the two channels cannot be compared to each other or to
   organic.
3. **Set `SENTRY_DSN` on Alpha.** The SDK is already shipped and the DSN is empty, so we are
   currently blind to crashes in exactly the cohort whose retention we are about to buy.
4. **Instrument the website** — page views and waitlist conversion, so §1's ambiguity resolves.

**This is a build item to lane, not a marketing task.** This plan names it and stops. It is the
single highest-leverage engineering work for growth, and it blocks Phase 2 entirely.

### Gate B — public store listings

Both stores, per Saiful. What that requires, all of it already specified in
`docs/initial_specs/09_compliance/store_compliance.md`:

| Item | Where it's drafted | Blocked on |
|---|---|---|
| App Store + Play listing copy | `assets/store_listing_copy.md` ✅ | Pricing decision (§11) |
| 6 screenshots per platform | `assets/screenshots_and_captions.md` ✅ | Capture on device |
| Disclaimer visible in ≥1 screenshot | ditto — frame 6 | — |
| Privacy labels (iOS) + Data Safety form (Play) | `store_compliance.md` §Data Safety | Saiful, in console |
| 17+ age rating questionnaire | `store_compliance.md` §Age rating | Saiful, in console |
| Review notes + sandbox account | — | Saiful; a reviewer-skip deep-link already exists |
| Account-deletion page | ✅ live at `/ami-trade/sad-to-see-you-go` | — |
| Marketing URL | ✅ live | — |
| Play identity verification | In flight since AT:R39 | Google |

**Review-survival rules, non-negotiable** (`store_compliance.md` App Review tips): lead with
education and simulation in name, subtitle, description, screenshots and metadata; show the
disclaimer in a screenshot; provide sandbox credentials; make no claims of returns. Apple review
is documented as prickly about trading-themed apps. A rejection costs a week and a resubmission;
these rules cost nothing.

One channel consequence: **Apple Search Ads requires a public App Store release** — a TestFlight
build is not sufficient. Google App Campaigns requires a public or open-testing Play listing.
Until Gate B closes, the only paid row in Schedule B that can run at all is Reddit/creator.

### Gate C — a way to bring users back

Push is not built (F3). Email sends only magic-link codes. **A funnel with no return path wastes
every dollar spent at the top of it** — we would pay for installs, deliver a first session, and
have no mechanism to produce a second one.

Minimum: push (blocked on Saiful's OneSignal account + APNs cert — items A15/A16) plus one
lifecycle email sender beyond `send_magic_link`. Copy for both is already drafted in
`assets/lifecycle_copy.md`, so the day the channel exists the sequences ship.

**Gate C can be partially waived for Phase 1** — organic acquisition at low volume can survive
on in-app streaks and leagues alone. It cannot be waived for Phase 2.

---

## 3. Message hierarchy

Full derivation in `positioning_and_personas.md` §2. Summary:

| Level | Line |
|---|---|
| 5 words | Practice the call. No risk. |
| One line | Learn to invest by making real calls on real market data — with none of your money at risk. |
| Hook | It's the difference between reading about swimming and getting in the pool — except the pool has no sharks. |

**Outcome first, agents second, always.** Agents are the mechanism, named in sentence two.

Conventions:

- **13 = 12 analyst-team agents + the Concierge.** The live site says 13; standardise on 13 and
  explain the 12+1 once, in the long description only.
- **Competitive line** (`vs_finelo.md`): *"Same price as Finelo. 12 AI analysts instead of 1
  chart tool."* Sourced, feature-based, permitted. Do not extend it into quality disparagement
  (F19).
- **Never "the AI."** It is AMI, by name (F17).

---

## 4. The chat-AI objection

This gets a section rather than a headline because it is the single biggest thing between this
product and a subscription, and because the answer determines other decisions.

`so_what.md` concedes the ground that has to be conceded: for *answers*, a chat AI is faster,
freer and unbeatable. Pretending otherwise loses the argument with anyone who has tried it.

The answer is that AMI Trade is not selling answers. It sells **skill plus a track record**, and
it does three things a chat AI structurally cannot:

- **Memory** — it knows your book, your mandate, and what you did last month.
- **Disagreement** — the Bear Researcher's job is to attack your thesis; the Portfolio Manager
  can refuse a trade that breaks your own mandate (N6).
- **Receipts** — it forces a decision, runs it, and keeps the record. Six months in you have a
  track record of your own calls with your reasoning attached.

Use *"chat AI is a library; AMI Trade is a gym"* verbatim.

**Three consequences this plan takes literally**, because if the positioning is true then these
follow:

1. **Onboarding must reach a first Room inside one session** (§8). If a user's first session ends
   without a debate, we sold a library.
2. **The journal is the retention story, not a feature bullet** (§9).
3. **Every re-engagement message points at the user's own receipts**, never at a feature
   (`assets/lifecycle_copy.md`).

---

## 5. The halal wedge — a named workstream

Sharia screening is **shipped and reaching the client**: AAOIFI standard, 216 compliant of the
503-name S&P 500 parent index, as-of 2026-07-28, verdict serialized to the client since DEF094
was fixed (N1). Three ethical-exclusion mandate flags ship alongside it (N3).

**Our own website says it is "on the roadmap, not shipped."**

This is the only differentiator that is simultaneously:

- **Shipped** — today, verifiable;
- **Defensible** — `vs_finelo.md` identifies it as the thing mass-market competitors will not
  invest in, and that judgement looks right;
- **Free to market** — the audience lives in communities, newsletters and subreddits, not behind
  ad auctions;
- **A market wedge** — it is the natural entry into the AR/MS markets that are already
  content-ready (V3, V9), and it works in English first.

Workstream:

| # | Action | Owner | Where |
|---|---|---|---|
| H1 | Correct the stale website line | marketing-content | `assets/landing_page_changes.md` |
| H2 | Add screening to listing copy + keywords | marketing-content | `assets/store_listing_copy.md` |
| H3 | Add a Sharia-verdict screenshot frame | marketing-content + capture | `assets/screenshots_and_captions.md` |
| H4 | Open the communities honestly | Saiful | `assets/organic_playbook.md` |
| H5 | Human review of any AR/MS halal copy before it ships | Saiful | — |

**The guardrail is absolute and it is a defect-recurrence risk, not a tone preference.** DEF094
existed because an `unknown` verdict was indistinguishable from a pass — a user got silent
permission on a ticker no scholar body has ruled on. Marketing can recreate that in one sentence.
Every halal claim goes through N1's permitted/forbidden wording.

---

## 6. Phase 1 — organic, $0, weeks 1–8

Ranked by expected return per hour, given that hours are the only currency available.

### 6.1 ASO — the primary channel, once Gate B closes

Store search is where finance-education intent already exists, and it costs nothing. The listing
*is* the campaign: title, subtitle, keywords, screenshots and the first three lines of the
description do the work. Everything needed is drafted in `assets/store_listing_copy.md` and
`assets/screenshots_and_captions.md`.

Keyword posture: do not fight for "trading" or "stocks" — we will lose to brokerages with
budgets. Compete where the intent is specific and the competition thin: *learn investing*,
*trading simulator*, *paper trading*, *investing course*, *halal investing*, *sharia stocks*,
*stock analysis practice*. The halal cluster is the one where we can plausibly rank first.

### 6.2 The lesson corpus — the biggest unused asset in the repo

**342 lessons, in three languages, verified and sourced** under CR060's provenance regime
(V3) — and they are visible only inside a closed app. This is a content library most
content-marketing operations would spend six figures to produce, sitting idle.

Recipe (detail in `assets/organic_playbook.md`):

- Publish a subset as public SEO pages on `www.agenticmarketintel.ai`. Long-tail investing-term
  queries are winnable by good static content.
- Each page ends with the app as the *practice* step, not as a banner ad.
- Repurpose the same lesson into a social carousel and a short post. One lesson, three artifacts.
- **Provenance stays internal.** CR060's sourcing is an internal quality control; users never
  see it. Do not publish provenance notes.
- Any EN edit made while repurposing flags AR/MS retranslation per the project convention.

### 6.3 The Room replay as the shareable unit

A thirteen-agent debate about a stock people already argue about is inherently interesting
content — it is the product's most demonstrable moment and the hardest thing for a competitor to
fake. Format in `assets/organic_playbook.md`.

Note the constraint honestly: there is **no in-app share mechanic** (F4), so Phase 1 replays are
published by us, manually, not shared by users. The referral mechanic in §10 is what would change
that.

### 6.4 Reddit — participation, not placement

`so_what.md` is right that r/investing and r/stocks "hate marketing," and they are moderated by
humans who are good at spotting it. The rule is absolute: **answer questions, never drop a cold
link.** A useful comment history is the asset; the link is the by-product.

Targets: r/investing, r/stocks, r/algotrading, r/islamicfinance, r/MalaysianPF, r/singaporefi.
Rules of engagement in `assets/organic_playbook.md`, including which subreddits require mod
contact first.

### 6.5 Build-in-public

The solo-founder-plus-on-prem-inference story is genuinely interesting to a dev and indie
audience, and that audience overlaps the prosumer segment (`vision_and_positioning.md`'s
secondary audience). Free, and it suits Marcus and David.

Constraint: it must not become the *product* story. Investors care that one person plus AI ships
this; users do not.

### 6.6 Halal-investing communities

Per §5. Highest trust, lowest cost, most differentiated. Requires the most care.

### 6.7 Cost note

Every free user consumes real inference. On-prem hardware makes that electricity rather than API
spend, but it is not free and it is not infinitely scalable. The live `GTM_FUNNEL=winzip`
cooldown is what bounds free-tier cost, and it doubles as the upgrade prompt — a user who hits
the cooldown is a user who wants another Room, which is the best moment to ask.

---

## 7. Phase 2 — funded, $1,400/month

Starts the month the first backer instalment lands. Split per Schedule B:

| Channel | Monthly | Requires |
|---|---|---|
| Apple Search Ads | ~$600–700 | Public App Store release |
| Google App Campaigns | ~$600–700 | Public or open-testing Play listing |
| Reddit ads + micro-creator placements | ~$100–200 | Nothing — the only store-independent row |

Creative segmented by persona (Rule 3), drafted in `assets/ad_copy.md`.

**The first four weeks are a measurement buy, not a growth buy.** The deliverable of month one is
a CPI number we can trust and a working attribution path — not volume. Concretely: run few
keyword groups, run them long enough to reach significance, do not add channels while a channel
is still un-attributed, and do not judge creative on a hundred impressions.

Budget discipline notes:

- Schedule B is **indicative, not binding** (§3 of the agreement), and the Founder may reallocate.
  Say so to backers rather than treating the table as a promise.
- If the GCP Beta migration begins during the contribution period, infrastructure rises to
  USD 750–2,550/month and, per §3, the response is to **reallocate from advertising** — this
  plan's budget is the first thing cut. Plan for that rather than being surprised by it.

---

## 8. Funnel and targets

| Stage | Measured by | Target | Note |
|---|---|---|---|
| Impression → store page | Store console | — | ASO-driven |
| Store page → install | Store console | industry-typical conversion, to be established | Screenshots do this work |
| Install → onboarding complete (`mandate_set`) | Gate A event | — | Concierge conversation |
| **Onboarding → first Room, same session** | Gate A event | **the one that matters** | See below |
| First Room → D7 return | Gate A cohort | — | Needs Gate C |
| D7 → paid | RevenueCat | — | No baseline exists (T1) |

**Every rate above is a target to be established from our own first cohort, not a forecast.** We
have no historical conversion data — T1 and T4 mean there is nothing to extrapolate from, and
inventing benchmark numbers here would be exactly the extrapolation the register forbids. The
first funded month's job is to fill this table in with measured values.

**North-star metric** (`vision_and_positioning.md`): **weekly active users who completed at
least one Convene the Room in the last 7 days.** Lessons can be learned anywhere; a multi-agent
debate over the user's own mandate cannot.

**The one hard funnel requirement:** Floor Pass must deliver the first Room debate *and* the
first simulated call **inside one session**. `so_what.md` names this and §4 explains why — if the
first session ends without a debate, we sold a library, and the free tier is pure cost with no
conversion mechanism. If measurement shows first-session Room completion is low, that is a
product fix and it outranks every channel decision in this document.

---

## 9. Retention

**The journal is the retention story.** Not a feature — the reason the product compounds. A
user's own record of their calls and reasoning gets more valuable the longer they stay, which is
also the switching cost `vision_and_positioning.md` identifies as a moat. Every re-engagement
message points at it.

Live retention mechanics:

| Mechanic | State |
|---|---|
| Streaks (tied to learning days, not trade days) | ✅ |
| Daily challenges | ✅ 183 authored |
| Leagues + reputation | ✅ live — 6 leagues, 25 members, 215 events (N5) |
| Decision Journal | ✅ 1,171 entries |
| `winzip` cooldown as the upgrade moment | ✅ live on Alpha |
| Morning briefing | ✗ dropped (F1) |
| Push | ✗ not built (F3) |

**The 7-day Trader trial does not auto-bill at expiry**, and cancellation is a one-tap deep-link
with no dark patterns. That is an unusual choice in this category and it is marketable *as* a
choice — "we'll ask, not charge" is a trust claim we can actually make, and trust is the scarce
commodity when a finance app asks for a card.

---

## 10. Referral

None exists. `share_plus` is a dependency with no feature behind it (F4).

Cheapest mechanic that fits the product: **share a Room verdict card** — the debate outcome as an
image, with the ticker, the verdict, and the disclaimer baked in — where the recipient lands on
the store listing. It rides the product's most interesting moment instead of asking users to
advocate in the abstract.

**Build item.** Named here, not scheduled here. Copy is drafted in `assets/lifecycle_copy.md`
and stays dark until the mechanic ships.

---

## 11. Pricing communication — blocked, needs Saiful

Three sources disagree:

| Source | Says |
|---|---|
| `docs/initial_specs/06_monetization/tiers_and_pricing.md` | Trader $14.99/mo or $129/yr · Floor Manager $34.99/mo or $299/yr |
| `www.agenticmarketintel.ai` | "TBD / month", "Exact pricing revealed at launch" |
| The site's free tier | 3 analysts per session, 5 Convene sessions/week — which is **not** the spec's Floor Pass (13 credits, 1 Room, 5 one-on-ones) |

**No asset states a price until Saiful confirms which is current.** `assets/store_listing_copy.md`
leaves the subscription block as a marked placeholder, because Apple and Play both require
accurate price and term disclosure in the listing — a wrong number there is a rejection.

Recommendation, once confirmed: reveal at listing time using the Finelo parity line. And treat
the launch-country promo as load-bearing rather than cosmetic — $14.99 is ~1.2% of average
monthly post-tax income in Malaysia versus ~0.3% in the US (P5), so the same list price is a
materially different ask in the home market.

---

## 12. 90-day calendar

Ownership matters more than dates here: **marketing-content cannot start until Saiful-external
and build-lane items land**, and pretending otherwise is how the calendar becomes fiction.

| Weeks | Saiful-external | Build-lane | Marketing-content |
|---|---|---|---|
| 1–2 | Play identity verification; OneSignal + APNs cert; confirm pricing (§11) | Gate A: analytics SDK + event taxonomy; set `SENTRY_DSN` | Website: re-lead hero, correct the Sharia line, instrument waitlist |
| 3–4 | Privacy labels + Data Safety + age rating in both consoles | Gate A: install attribution | Capture screenshots; finalise listing copy |
| 5–6 | Submit both listings; review notes + sandbox account | Gate C: push + one lifecycle sender | Publish first 10 lesson SEO pages; begin Reddit participation |
| 7–8 | Handle review iterations | Referral: Room verdict share card | Halal community outreach (H4); first Room replays |
| 9–10 | — | Fix whatever Gate A's first data exposes | Read the funnel; fill in §8's target column with measured values |
| 11–12 | First backer instalment (if the raise closed) | — | Phase 2 opens: measurement buy only |

If the raise has not closed by week 11, Phase 2 does not open and Phase 1 continues. Organic work
is the hedge, which is a second reason to front-load it.

---

## 13. Metrics and kill criteria

**Weekly review, four numbers:** north-star WAU-with-a-Room; installs by source; first-session
Room completion rate; D7 return rate.

Per-channel kill criteria, applied only once Gate A can attribute:

| Channel | Kill when |
|---|---|
| Apple Search Ads | CPI exceeds 3× the blended organic cost-per-activated-user after ≥200 attributed installs |
| Google App Campaigns | same test, independently |
| Reddit ads | no attributable installs after 4 weeks at the Schedule B allocation |
| A creator placement | judged individually; single placements never get a second buy without an attributed result |
| An organic channel | 6 weeks of effort with no measurable arrivals |

**No silent truncation.** If a channel is cut, the reason and the number go in the weekly review.
A channel that quietly stops being worked reads later as a channel that was tried and failed,
which is how the same mistake gets made twice.

**The honest kill criterion for the whole plan:** if Gate B closes, listings go public, and the
first 500 organic installs produce a first-session Room-completion rate below roughly half, the
problem is the product's first session and no amount of acquisition spend fixes it. Stop buying
and fix onboarding.

---

## 14. Compliance guardrails for every user-facing word

Full list in `_facts/claim_register.md`. The short version, for anyone drafting copy:

**Always:** lead with education and simulation · say AMI, never "the AI" · 15-minute delayed
data · the disclaimer visible in at least one screenshot.

**Never:** a return, gain or performance figure · "advice", "recommendations", "signals",
"picks" · real money, brokerage or execution · a guarantee · a user or download count · a
feature from the FORBIDDEN block (briefing, voice, push, share cards, badges, credit-pack
purchases, real-time data, GCC/Tadawul/Bursa coverage) · halal copy that lets `unknown` read as
approval.

Run the register's grep sweeps against any new asset before it ships.
