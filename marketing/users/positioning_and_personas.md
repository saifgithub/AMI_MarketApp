# Positioning and personas — `so_what.md` reconciled against what ships

`marketing/user_poc/so_what.md` is the canonical source for **voice, framing and personas**.
This document does not replace it and does not restate it. It does the three things that
document cannot do for itself:

1. Claim-check its promises against production, because four of them describe features that do
   not exist.
2. Promote three of its conclusions to binding rules for every user-facing asset.
3. Reconcile its channel list against the money that actually exists.

Read `so_what.md` first. Read this before writing a single line of copy.

---

## 1. Claim check

`so_what.md` was written from the user's seat, which is exactly right and is also why it
describes the product as intended rather than as shipped. Four claims fail. Each is either
re-cut to a surface that exists, or parked with the feature that unlocks it.

| `so_what.md` says | Reality | Resolution |
|---|---|---|
| *"You open the app and your analyst team has already done the work"* (Q1, day-in-the-life) | **The briefing does not exist.** A17 was never started and was deliberately dropped via CR115 on 2026-07-29 — no scheduler, no sender, no TTS (`claim_register.md` F1) | **Re-cut, don't park.** The pull version is true today and is arguably better copy: *"You pick a stock. Your team goes to work on it while you watch."* The Room is on-demand and the debate streams live — that is a more honest and more vivid promise than overnight homework. |
| *"Daily brief, a challenge, a journal entry"* as the habit loop (Q1) | Daily challenges ✅ live (183 authored), journal ✅ live (1,171 entries), **daily brief ✗** | Drop the brief from the loop. The loop is **challenge → Room → journal**, and leagues (live, 6 of them) are the competitive layer `so_what.md` didn't know had shipped. |
| *"shareable P&L cards"* (Persona 5, Leo) | No share mechanic exists. `share_plus` is a dependency with no feature behind it (F4) | **Park.** Leo's surface becomes leagues + fast Room runs + aggressive mandate templates, all live. Copy for share cards is drafted in `assets/lifecycle_copy.md` and stays dark until the mechanic ships. |
| *"Credit packs"* (Personas 3, 5) | No purchase of any kind has ever completed (T1) | **Park the mechanic, keep the tier.** Personas may be assigned to Trader / Floor Manager as *intended* tiers; no asset may describe a credit-pack purchase as a thing users do. |

One more, softer: *"The data is wired in — live prices, news, your positions"* (Q2, point 4).
Prices ✅ (Yahoo, **15-minute delayed** — never say real-time, F7). Positions ✅. Social
sentiment ✅ (Adanos, live — N4). News is Yahoo-only; `ALPHA_VANTAGE_API_KEY` is unset, so
CR023's second source is dark (F10). "Wired in" survives; "real-time" does not.

### And one claim `so_what.md` under-sold

It never mentions halal screening — reasonably, since the website says it isn't shipped. **It
is** (N1): AAOIFI standard, 216 compliant of the 503-name S&P 500 parent index, as-of
2026-07-28, verdict reaching the client since DEF094 was fixed. Plus three ethical-exclusion
mandate flags (N3). See §4.

---

## 2. Three rules, adopted from `so_what.md`

These bind every user-facing asset. Each replaces something this project was otherwise about
to do.

### Rule 1 — never lead with "AI agents"

> *"Never lead with 'AI agents.' Users don't buy agents. They buy 'I'll finally understand my
> own investments' and 'I can practice without losing money.' The agents are just how it's
> delivered."* — `so_what.md`, Q1

**This overrides the live website.** `www.agenticmarketintel.ai` currently leads with *"13 AI
agents. One decision. No shortcuts."* — a builder's line, an architecture spec as a hero. That
site has produced **zero waitlist signups** in months (T2). The lead is not the only candidate
explanation, but it is the cheapest one to fix and the first to try.

Corrected hierarchy:

| Level | Line |
|---|---|
| **5 words** | Practice the call. No risk. |
| **One line** | Learn to invest by making real calls on real market data — with none of your money at risk. |
| **One paragraph** | Most people learn investing the expensive way: they read opinions they can't evaluate, or they lose real money finding out. AMI Trade is the third option. Pick a stock and a team of thirteen specialists goes to work on it in front of you — fundamentals, news, sentiment, a bull case, a bear case, three risk analysts arguing it out. You read the debate, cross-examine anyone you disagree with, and then you make the call. AMI runs it in simulation and keeps the receipts, so six months from now you can see exactly how you think. |

Agents appear in sentence two, as the mechanism. The paragraph never says "AI agents" as a
feature bullet; it describes what they *do*.

**One-line version, for anything that needs a hook:** *it's the difference between reading about
swimming and getting in the pool — except the pool has no sharks.* (`so_what.md`'s line. Use it.)

### Rule 2 — the chat-AI objection is answered with memory, disagreement, receipts

> *"Chat AI is a library; AMI Trade is a gym."* — `so_what.md`, Q2

This is the product's single biggest objection in 2026 and the reason it needs a plan-level
answer rather than one ad headline: **a chat AI is free and better at answers.** `so_what.md`
concedes it outright — *"If you want an answer, chat AI is faster. Full stop"* — which is what
makes the rest credible.

The three differentiators, verbatim in objection copy:

| | Why chat AI can't | Shipped? |
|---|---|---|
| **Memory** | It doesn't know you panic-sold last month, that your mandate caps position size, or what you're holding. Portfolio, journal, mandate and streaks *are* the product; the debate is about your book | ✅ 1,171 journal entries, 13 mandates |
| **Disagreement** | Ask "should I buy TSLA?" and you get a balanced essay leaning whichever way you tilted the question. Here the Bear Researcher's *job* is to attack your thesis, three risk analysts argue it out, and the Portfolio Manager can refuse a trade that breaks your own mandate | ✅ N6 — the PM veto reaches the client |
| **Receipts** | Chat AI ends at advice. AMI forces a decision, runs it, and holds the record. Six months later you have a track record of *your* calls with your reasoning attached. No feedback loop, no skill | ✅ Decision Journal, replayable |

**The consequence `so_what.md` names, and this plan takes literally:** AMI Trade only justifies
$14.99/mo for users whose goal is *skill plus a track record*, not answers. That single sentence
determines three other things — onboarding must reach a first Room inside one session, the
journal is the retention story rather than a feature, and every re-engagement message points at
the user's own receipts instead of at a feature. Those are carried into
`user_acquisition_plan.md` §4, §8 and §9.

### Rule 3 — segment creative by persona, not by channel

One generic ad serves none of the six. `assets/ad_copy.md` is organised persona-first, and each
persona's creative is written to its **message test** below — the thing that has to be true for
that person to convert. The beginner converts on safety and habit; the burnt trader converts on
respect; the optimizer converts on competition. Those are different ads, not different
placements of one ad.

---

## 3. The six personas, with shipped surfaces only

Taken from `so_what.md` §"Target user profiles". The **hook** and **message test** columns are
its work, unchanged. The **surface** column is corrected to what exists, and the **channel**
column is reconciled against the budget in §5.

### 1. The Curious Beginner — "Aisha, 26"

- **Hook:** *"Learn to invest by doing it — with none of your money at risk."*
- **Message test:** would she say "I'd actually open that every day"? Converts on safety and
  habit, never on a feature list.
- **Shipped surface:** Concierge onboarding → mandate conversation → lessons (342, all three
  languages) → a guided first Room → daily challenges. Floor Pass entry.
- **Channel now:** ASO (primary), organic lesson content, Reddit answers.
- **Channel post-raise:** Google App Campaigns. *(Not TikTok/IG — see §5.)*

### 2. The Burnt Retail Trader — "Marcus, 34"

- **Hook:** *"You already paid tuition once. Rebuild your edge where losses don't cost you."*
- **Message test:** converts on **respect** — the app must take trading seriously, not read as
  a toy. Show the risk debaters shutting down a bad trade.
- **Shipped surface:** the Room (he will respect the Bear Researcher), the journal with
  receipts, the **Portfolio Manager veto** (N6 — the single best proof the app is serious),
  portfolio stats.
- **Channel now:** Reddit participation (r/stocks, r/investing — `so_what.md` correctly notes
  they hate marketing; rules of engagement in `assets/organic_playbook.md`), build-in-public
  on X.
- **Channel post-raise:** Apple Search Ads on competitor and category terms.
- **Highest-value persona for paid**, because he already has the vocabulary and the intent, so
  he needs no education spend to understand the offer.

### 3. The Competitive Optimizer — "Priya, 29"

- **Hook:** *"Prove you'd beat the market. We keep score."* — **rewrite required.** As written
  this is an implied performance claim, which F13 forbids and Apple review flags. Use:
  *"Your calls, scored. Your streak, tracked. Your rank, public."*
- **Message test:** leaderboards and streak mechanics inside the first 30 seconds.
- **Shipped surface:** **leagues are live** — 6 leagues, 25 members, 215 reputation events (N5)
  — plus daily challenges and streaks. `so_what.md` listed this speculatively; it shipped.
- **Channel now:** ASO, Discord communities (free to participate in).
- **Channel post-raise:** Apple Search Ads.

### 4. The Serious Learner — "David, 45"

- **Hook:** *"Understand every investment you own — well enough to defend it."*
- **Message test:** depth and calm. **No gamification in his creative** — show research quality
  and the interrogate-your-own-thesis loop.
- **Shipped surface:** 1-on-1 agent interrogation, Fundamentals Analyst depth, the journal as a
  thinking tool. *(Not briefings — F1.)*
- **Channel now:** LinkedIn organic, long-form content from the lesson corpus, newsletters we
  are already read in.
- **Channel post-raise:** nothing affordable. Podcast sponsorship is his channel and it does not
  fit the budget — see §5.

### 5. The Young Speculator — "Leo, 21"

- **Hook:** *"Run the riskiest strategy you can dream up. Only the wins are real."* — keep, but
  see below.
- **Message test:** speed and bragging rights.
- **Shipped surface:** fast Room runs, aggressive mandate templates, leagues. *(Not shareable
  P&L cards — F4.)*
- **Channel now:** organic short-form if Saiful wants to make it; campus finance clubs.
- **Positioning note worth keeping from `so_what.md`:** this is deliberately **protective**
  positioning — redirect the adrenaline into simulation before real leverage finds him. That
  framing is also the right answer if an app reviewer or a journalist asks why a 21-year-old
  should use this.
- **Caution:** Leo's creative sits closest to the F13/F16 line and to Apple's simulated-gambling
  question, which `store_compliance.md` answers **No** on the basis that we explicitly do not
  gamify P&L. Copy that celebrates simulated wins as wins undermines that answer. Every Leo
  variant gets checked against the register before use.

### 6. The Observant Investor — **new, and shippable today**

`so_what.md` §6 bundles this into a v1.0 "Language-First Learner." That bundle needs splitting,
because the two halves have different ship dates:

- **The language half is still v1.0** — AR and MS content ships (V3, V9), but the AR/MS *market
  push* waits on translated store listings and local review.
- **The observance half ships now** (N1, N3) — and in **English first**, because halal-conscious
  investors in the US, UK, Canada and Southeast Asia are an English-speaking segment that no
  mass-market competitor serves. `vs_finelo.md` calls this out as the differentiator competitors
  will not invest in.
- **Hook:** *"Screen your universe first. Then argue about the stock."*
- **Message test:** does it read as *rigorous* rather than as a marketing checkbox? This
  audience has been burned by superficial "halal" labels. The as-of date on every verdict is the
  credibility signal — lead with it.
- **Shipped surface:** mandate flags at onboarding → AAOIFI screen (216 of 503, as-of dated) →
  the screen visible per ticker → the Portfolio Manager enforcing it → ethical-exclusion flags.
- **Channel now:** halal-investing communities, Islamic-finance newsletters, r/islamicfinance,
  Muslim personal-finance creators. All free, all high-trust, all requiring honesty.
- **The guardrail is absolute.** `claim_register.md` N1 governs every word: the universe is the
  S&P 500, not "all stocks"; AMI reports a screen against a published list, it does not issue a
  religious ruling; `unknown` is a real fourth state and must never read as approval; and no
  AR/MS halal copy ships without human review. DEF094 was a code defect that let `unknown` look
  like a pass — one careless sentence recreates it in marketing.

---

## 4. What this means for the plan

`so_what.md`'s own closing section, adopted with one addition:

- **Lead with the pool-without-sharks framing, not the technology.** (Rule 1.)
- **Segment creative by persona.** (Rule 3.)
- **Free tier is the funnel** — Floor Pass must deliver the "aha" (first Room debate + first
  simulated call) **within one session**. This is now a funnel requirement in
  `user_acquisition_plan.md` §8, not an aspiration.
- **The journal is the retention story** — every re-engagement message points at the user's own
  track record. Carried into `assets/lifecycle_copy.md`.
- **Position against both extremes** — smarter than a tip, safer than a brokerage. The chat-AI
  objection is answered by memory + disagreement + receipts, verbatim. (Rule 2.)
- **Added: the halal screen is the wedge, and we are currently denying it in public.** It is the
  only differentiator that is simultaneously shipped, defensible, and reachable through free
  community channels. Correcting the website is the highest-value single edit in
  `assets/landing_page_changes.md`.

---

## 5. Channels reconciled against the money

`so_what.md` proposes TikTok/IG short-form, app-store featuring, finfluencer partnerships,
YouTube trading-education channels, X/FinTwit, podcast sponsorships, newsletters, LinkedIn,
Discord, campus clubs and regional bank partnerships. Every one of those is a reasonable channel
for its persona. **Almost none of them fits $1,400/month**, which is the entire advertising
allocation in the backer agreement's Schedule B — and that money does not exist yet.

| `so_what.md` channel | Cost reality | Verdict |
|---|---|---|
| ASO / app-store search | Free | **Primary organic channel**, once listings are public |
| Reddit participation | Free | **Now** — rules of engagement required |
| Organic content from the lesson corpus | Free (342 lessons already written) | **Now** — the biggest unused asset we have |
| X/FinTwit, LinkedIn organic | Free | **Now** — build-in-public suits Marcus and David |
| Discord communities | Free | **Now** |
| Halal-investing communities | Free | **Now** — see Persona 6 |
| Campus finance clubs | Free / travel | **Now**, if Saiful wants to |
| Apple Search Ads | ~$600–700/mo | **Post-raise**, Schedule B row 1 |
| Google App Campaigns | ~$600–700/mo | **Post-raise**, Schedule B row 2 |
| Reddit *ads* + creator placements | ~$100–200/mo | **Post-raise**, Schedule B row 3 — and the only paid row with no store-listing dependency |
| Finfluencer / creator partnerships | Low four figures per placement, typical | **Post-raise, and only at the small end.** Schedule B's creator line is $100–200/mo — that buys micro-creators, not partnerships |
| TikTok / IG paid short-form | Meaningful paid spend to escape the noise floor | **Not funded.** Organic only, and only if Saiful is willing to be on camera |
| Podcast sponsorships | ~$500–5,000 per episode | **Not funded.** One mid-tier read consumes a month or more of the entire budget. David's best channel is unaffordable, so he is served organically or not at all this cycle |
| App-store *featuring* | Free, but editorially awarded | Not a channel. An outcome — pursue via the listing quality Gate B produces |
| Bank / fintech literacy partnerships | Long sales cycle, needs an entity | **Post-entity, post-traction.** Named so it isn't forgotten |

**Why this table exists.** Leaving `so_what.md`'s channel list and Schedule B's $1,400 side by
side without reconciling them is how a plan quietly becomes undeliverable — the channels get
copied into a calendar, the money runs out in week two, and nobody can say which channel was
supposed to be cut. The cut is made here, in advance, on the record.
