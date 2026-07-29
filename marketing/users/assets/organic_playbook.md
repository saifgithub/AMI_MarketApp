# Organic playbook — Phase 1, $0, weeks 1–8

**Status: DRAFT for Saiful's review. Nothing published yet.**

This is the plan for the period where there is no advertising budget — which is now, and possibly
for a while, since Schedule B's money depends on a raise that has not started
(`investors/investor_marketing_plan.md`).

The operating constraint: **hours are the only currency**, so everything here is ranked by return
per hour, and the cheapest high-return item is the one nobody has touched.

---

## 1. The lesson corpus — start here

**342 lessons, in English, Arabic and Malay, verified and sourced under CR060's provenance
regime.** 1,026 files. Visible only inside a closed alpha app.

This is a content library that most content-marketing operations would spend six figures and a
year to produce, and it is currently generating zero traffic. Nothing else in this playbook has a
comparable ratio of value-already-created to value-being-captured.

### The recipe

One lesson → three artifacts:

1. **A public SEO page** on `www.agenticmarketintel.ai`. Long-tail investing-term queries ("what
   is a stock split", "how to read a P/E ratio") are winnable with good static content, and the
   site already has the design system, the fonts and the deploy path.
2. **A social carousel** — the same lesson as 5–7 slides, for LinkedIn and Instagram.
3. **A short post** — the single sharpest sentence from the lesson, standalone.

### Rules

- **Each page ends with the app as the *practice* step**, not as a banner. "You now know what a
  P/E ratio is. Here is what happens when thirteen analysts argue about whether this one is
  cheap." That is the honest bridge and it is also the better CTA.
- **Provenance stays internal.** CR060's sourcing is a quality control for us; users never see it.
  Do not publish source lists — it reads as defensive and it exposes the authoring pipeline.
- **Any EN edit made while repurposing flags AR/MS retranslation**, per the project convention.
  Repurposing usually means tightening a sentence, which desynchronises the three locales. Note
  the lesson `id` and flag it; do not silently edit one locale.
- **Start with 10 pages, not 50.** Publish, wait for the site instrumentation from Gate A, and
  find out whether anything ranks before scaling the effort.
- Pick lessons where the search intent is obvious and the concept is evergreen. Skip anything
  tied to a specific market moment.

### Priority order

| Batch | Lessons to pick | Why |
|---|---|---|
| 1 (weeks 1–2) | 10 foundational terms — stock, share issuance, P/E, market cap, dividend, order types | Highest search volume, most evergreen, least likely to need revision |
| 2 (weeks 3–5) | 10 on the reasoning process — how to read a bull case, what a bear case looks for | Closest to the product's actual differentiator |
| 3 (weeks 6–8) | 5 on Sharia and ethical screening | Feeds the halal channel below, where we have the least competition |

---

## 2. Reddit — participation, not placement

`so_what.md` is right: r/investing and r/stocks "hate marketing," and they are moderated by
humans who are good at spotting it. A single promotional post can get the domain banned, which
would cost more than the channel is worth.

**The rule is absolute: answer questions, never drop a cold link.** A useful comment history is
the asset. The link is a by-product that only appears when someone asks what you built.

### Rules of engagement

| Rule | Detail |
|---|---|
| Read the sidebar first | Every target subreddit has a self-promotion rule. Some ban links outright; some allow them in a monthly thread; some require mod contact. Check per subreddit, not once |
| Post from a real account with history | A fresh account commenting on investing threads with a link reads as spam because it is |
| Answer without the link nine times out of ten | The tenth time, when someone asks "is there an app that does this", the link is welcome instead of hostile |
| Never argue with a moderator | If a comment is removed, it is removed |
| Disclose the affiliation | "I built this" every single time. Undisclosed promotion is the thing that gets a domain banned |
| Flat voice, no marketing register | No exclamation marks, no emoji, no benefit-speak. Say the mechanism |

### Targets

| Subreddit | Persona | Note |
|---|---|---|
| r/investing | Aisha, David | Large, strict. Answer-only for a long while |
| r/stocks | Marcus | Strict on promotion |
| r/algotrading | Marcus | More receptive to a technical description of the agent architecture — the one place where leading with the mechanism is right |
| r/islamicfinance | Observant Investor | Highest-value, smallest, most trust-sensitive. See §4 |
| r/MalaysianPF | home market | Saiful's local credibility is an asset here |
| r/singaporefi | regional | Adjacent, affluent, English-speaking |
| r/Bogleheads | — | **Skip.** Philosophically opposed to active stock selection. Our product reads as the enemy, and they are not wrong to think so |

---

## 3. The Room replay as content

A thirteen-agent debate about a stock people already argue about is inherently interesting, and it
is the hardest thing in the product for a competitor to fake.

### Format

- Pick a ticker with a live public argument. Run a Room. Publish the debate as a readable
  artifact: the stances, the disagreement, the verdict.
- **Lead with the disagreement, not the verdict.** "Our bull and bear analysts split on NVDA;
  here is where the argument actually turned" is content. "AMI says NVDA is a buy" is a signal,
  which is F14, and is forbidden.
- Always carry: simulation-only, not advice, 15-minute delayed data, and the date. A dated
  artifact ages honestly; an undated one becomes a stale recommendation.
- **Never publish a verdict as a prediction, and never follow up with "we were right."** That is
  a performance claim (F13) and it is the exact failure mode that turns an education brand into a
  signals brand.

### Honest constraint

There is **no in-app share mechanic** (F4). Phase 1 replays are published by us, manually. Users
cannot share their own. The referral item in `user_acquisition_plan.md` §10 is what would change
that, and until it ships this channel scales with Saiful's hours, not with users.

---

## 4. Halal and ethical-investing communities

The highest-trust, lowest-cost, most differentiated channel we have — and the one where a
careless sentence does the most damage.

Sharia screening is **live**: AAOIFI standard, 216 compliant of the 503-name S&P 500 parent
index, as-of dated per verdict (N1). Our own website currently says it is not shipped, which is
the first thing to fix (`landing_page_changes.md` H1).

### Approach

1. **Fix the website first.** Arriving in a community that will check, with a site that contradicts
   the claim, is worse than not arriving.
2. **Lead with the specifics, not the label.** This audience has seen superficial "halal" badges.
   "AAOIFI-based, 216 of the S&P 500, as-of date on every verdict, unscreened names marked unknown
   rather than passed" earns more trust than any adjective.
3. **Volunteer the limits.** The universe is the S&P 500, not all equities. It is a screen, not a
   ruling. Saying so unprompted is the credibility move — and it is also just true.
4. **Islamic-finance newsletters and creators** before subreddits. Smaller audiences, much higher
   trust transfer.
5. **No AR or MS halal copy without human review** (H5). Observance-sensitive strings are excluded
   from machine translation in the product; the same rule binds marketing.

### The guardrail

Full permitted/forbidden wording in `_facts/claim_register.md` N1 and `ad_copy.md` §4. The
one-line version: **`unknown` must never read as approval.** DEF094 was a code defect that let an
unscreened ticker look screened-and-cleared. Marketing can recreate it in a sentence, in front of
the audience least willing to forgive it.

---

## 5. Build-in-public

The solo-founder-plus-on-prem-inference story is genuinely interesting to a developer and indie
audience, and that audience overlaps `vision_and_positioning.md`'s secondary segment — prosumers
who want institutional-style reasoning at consumer prices.

Angles that are true and specific:

- One person, 1,406 commits, a 342-lesson trilingual corpus, thirteen agents.
- Running inference on your own hardware instead of paying per token — including what that costs
  and where it stops working.
- Making a multi-agent debate legible to someone who is not technical. This is the actual hard
  problem and the most interesting thing to talk about.
- Governance as a solo founder: every change as a CR or a defect, with a register.

**Constraint: this must not become the product story.** Backers care that one person plus AI ships
this. Users do not — they care that it works. Keep the two audiences separate, which is the same
asymmetry `investor_marketing_plan.md` §1 notes in the other direction.

---

## 6. Eight-week calendar

Marketing-content work only. Saiful-external and build-lane items are in
`user_acquisition_plan.md` §12, and several items below are gated on them.

| Week | Do |
|---|---|
| 1 | Website: re-lead the hero, correct the Sharia line, instrument the waitlist (`landing_page_changes.md`). Draft the first 5 SEO pages |
| 2 | Publish SEO batch 1 (5 pages). Begin Reddit presence — answer only, no links. Start the build-in-public thread |
| 3 | Publish SEO batch 1 remainder (5 pages). First Room replay. Identify 10 Islamic-finance creators and newsletters |
| 4 | Capture store screenshots (needs a release build). First carousel set. Continue Reddit |
| 5 | SEO batch 2 begins. Second Room replay. **First halal-community outreach** — only if the website correction has shipped |
| 6 | Store listings submitted (Saiful). Third Room replay. Creator outreach round 1 |
| 7 | Handle review iterations. SEO batch 2 completes. Carousel set 2 |
| 8 | **Read the data.** Which pages get traffic, which subreddits sent anyone, whether the waitlist converts now. Fill in `user_acquisition_plan.md` §8's target column with measured values |

Week 8 is the point of the whole calendar. Everything before it is instrumentation plus content;
week 8 is when guessing stops.

---

## 7. Boilerplate and factsheet

For creator outreach, press enquiries and community bios. Cleared against the claim register.

### One-sentence

> AMI Trade is a simulation-only investing-education app where a team of thirteen AI specialists
> debates any stock in front of you, and you make the call.

### Short paragraph

> AMI Trade teaches investing judgement rather than investing mechanics. Pick a stock and thirteen
> specialists — fundamentals, market, news and sentiment analysts, a bull and bear researcher,
> three risk analysts, a trader and a portfolio manager, plus AMI as your concierge — work through
> it and debate it in front of you. You cross-examine anyone you disagree with, then you make the
> call, and it runs in a simulated portfolio that records your reasoning. It ships 342 lessons in
> English, Arabic and Malay, and screens against an AAOIFI-based Sharia-compliant list. It is a
> simulation: no real money, no brokerage, no advice.

### Factsheet

| | |
|---|---|
| Product | AMI Trade — simulation-only investing education |
| Company | Agentic Market Intel (AMI). No incorporated entity yet |
| Founder | Saiful, solo founder, Malaysia |
| Platforms | iOS, Android. Closed testing — TestFlight + Play internal |
| Status | Closed alpha. No public launch yet |
| Agents | 13 — 12 analyst-team roles plus AMI, the Concierge |
| Content | 342 lessons, each in EN / AR / MS |
| Screening | AAOIFI-based Sharia screen, 216 of the S&P 500, as-of 28 July 2026; plus fossil-fuel, tobacco and alcohol exclusions |
| Market data | Yahoo Finance, delayed 15 minutes |
| Markets | US equities |
| Languages | English, Arabic (full RTL), Malay |
| Website | `www.agenticmarketintel.ai` |
| Not | A brokerage, a signals service, an advice service, or real-money trading |

### Creator brief — the part that protects us

Any creator placement gets this verbatim, because a creator's words become our liability:

> **What you can say:** it is a simulation; the analysts disagree with each other on the record;
> your portfolio manager can refuse your trade for breaking your own rules; 342 lessons in three
> languages; it screens against an AAOIFI-based compliant list with the as-of date shown.
>
> **What you must not say:** anything about returns, gains, profit or beating the market; that it
> gives advice, recommendations, signals or picks; that it involves real money or a brokerage;
> that any outcome is guaranteed; that data is real-time (it is delayed 15 minutes); that a stock
> is "halal" (it reports a screen against a published list, not a religious ruling).
>
> **Please disclose the partnership.** We would rather a smaller audience than an undisclosed one.
