<!-- CR109 final review — the closing pass. Covers the last three asks (retention,
     ad-supported free players, social), the collisions each one creates with decisions
     already made, and the recommended shape for each. Closes the CR documentation.
     Design stage; not approved for build. -->

# CR109 — final review

**Closes the CR109 documentation.** `AT:Gamer`, 2026-07-30.
Package: [`CR109.md`](CR109.md) · [`implementation_plan.md`](implementation_plan.md) ·
[`playability_review.md`](playability_review.md) · [`games_roadmap.md`](games_roadmap.md) ·
this document.

Saiful: *"We need to make this addictive. We need to remind them to play. The players will be a
source of income if they view adverts etc… and we need to enable the social aspect of the game.
they can discuss trades, and give tips."*

Three asks. Each collides with something already decided, and one of them could sink the whole
compliance position if built the obvious way.

---

## 1. Ads — and the trap that would break §15

**The finding that matters most in this document.**

CR109 §15 rests on a three-leg test: **consideration absent** (entry is free), **prize absent**
(rewards are cosmetic and non-purchasable), leaving skill-versus-chance as the only live leg. That
is the entire reason a P&L competition is defensible here.

**Rewarded video is the standard mobile ad pattern, and it injects consideration.** The natural
things an ad-funded game reaches for are exactly the fatal ones:

| Tempting | Why it breaks the design |
|---|---|
| *"Watch an ad to restart"* | restart becomes purchasable with attention — **consideration** |
| *"Watch an ad for a second entry"* | entry is no longer free, and it breaks §4.1's one-run-per-cadence farm guard |
| *"Watch an ad for extra AMI Cash"* | money buys Stake — **violates the one-way rule (§3.1)** |
| *"Remove ads to see the board sooner"* | pay-to-advantage inside the Contest layer |

Non-monetary consideration counts in several jurisdictions, and requiring ad viewing has value to
the promoter by definition. So:

> **INVARIANT — no ad may ever be required, rewarded, or gate anything in the game.**
> Not entry, not re-entry, not restart, not capital, not information, not timing, not cosmetics
> that double as competition rewards.

Note the one-way rule catches all four rows above on its own — which is a good sign that §3 is
doing real work rather than decorating.

**What is left is still worth money.** Ads run as **ambient inventory on non-contest surfaces**, and
the game monetises *indirectly*: more sessions → more impressions on screens that already carry
them. The game's contribution is attention, not placement inside the contest.

**Where ads may appear:** the lobby, the Record, the roadmap/browse surfaces, app open.
**Where they may not:** the board, the trade ticket, and — emphatically — **the Close.** An ad in
the trophy moment cheapens the one emotional payoff the design has, and the Close is the beat the
whole period arc exists to deliver.

**Infrastructure reality check: none of this exists.** A repo-wide search finds **no ad SDK, no
AdMob, no ad units, no mediation, no consent flow.** "Floor Pass" is a tier name in
`tiers_and_pricing.md`, not an implementation. Ads mean an SDK integration, ATT on iOS, a GDPR/UMP
consent flow, and a store-declaration update. **That is its own CR, not a slice of this one** — and
it should not be entangled with the game's schedule.

---

## 2. Retention — reminders that survive contact with the user

The playability review found the game has no daily heartbeat once the streak is deleted with
`reputation_service.py`. Push is the fix, and it is already a prerequisite CR (§10.1).

**The design rule that makes reminders work is also the one that keeps them honest:**

> **Remind on events that need a decision. Never on events that only invite watching.**

| Good — a decision is available | Bad — pure "come look" |
|---|---|
| Entries close in 2 hours, you are not entered | AAPL is up 2% |
| Your run closes tomorrow | your position moved |
| Momentum Desk has challenged you | someone else traded |
| Your run has settled — results are ready | the market opened |
| You dropped out of the top 10 *(once per run)* | rank changed *(every time)* |
| Your last run closed 6 days ago | — |

This is not restraint for its own sake. **Notification fatigue destroys the channel:** ship
"your position moved" daily and users disable push, and then the *Close* — the one message that
carries the entire emotional payoff — never arrives. Restraint is what protects the message that
matters.

**Caps:** at most one push per day and four per week, with the Close and a received challenge
exempt from suppression but never duplicated. Quiet hours in the user's timezone.

It also lines up with a decision §10 already made for a different reason — *one beat per market
close, never per tick*. Per-tick movement is a slot machine, and this is a training product whose
curriculum warns against exactly the behaviour a "your position moved" push would train.

**Accepted from the playability review, and now the retention backbone:** re-home the streak onto
**runs finished / periods entered** (never check-ins), progress markers at every close, provisional
rank from the first trade, near-miss lines, and Rivals pulled forward.

---

## 3. Social — the ask with a hard checklist attached

*"They can discuss trades, and give tips."*

**The app has zero user-generated content today.** The only user-authored value anywhere is the
pseudonymous handle, which is system-generated and regenerable once. A repo-wide search finds **no
report mechanism, no block, no profanity filter, no moderation tooling of any kind.**

So this is not an incremental feature. **Apple Guideline 1.2 requires four things of any app with
user-generated content**, and shipping without them is a rejection, not a warning:

1. a method for **filtering objectionable material**
2. a mechanism to **report** offensive content, with timely response
3. the ability to **block abusive users**
4. published **contact information**, with action taken within **24 hours**

That fourth one is the binding constraint for a one-person team: a 24-hour action commitment is an
operational obligation, every day, indefinitely.

On top of that, an unmoderated stock-tip channel is the highest-risk UGC category there is: pump
schemes, "DM me for signals" funnels, affiliate scams, and unlicensed advice sitting on a platform
run by an entity **explicitly not licensed to give investment advice**. Content in Arabic and Malay
compounds it — Saiful cannot personally moderate what he cannot read.

### The shape that delivers most of the value

**Phase A — structured reactions. No typing, no moderation surface.**
A fixed vocabulary on a closed run: *clean run · brave · lucky · disciplined · ouch.* Zero
moderation cost because there is no free text. Delivers acknowledgement, which is most of what
social presence actually provides.

**Phase B — post-close rationale notes.** A short, length-capped note attached to **your own trades
in a run that has already closed**. This is roadmap mode #3 (retrospective reveal) plus a sentence
of *why*.

It is the safest possible version of "discuss trades" because of what it structurally cannot be:

| | Effect |
|---|---|
| **Retrospective only** | cannot be a signal — the position is already resolved |
| **Scoped to your own trades** | cannot become a generic tip channel |
| **Length-capped** | limits the abuse surface and the moderation load |
| **Attached to a real, scored decision** | it is analysis, not opinion — the brand's own register |

Still requires the full Guideline 1.2 checklist. There is no version of UGC that doesn't.

**Phase C — open discussion.** Only with a moderation budget that exists, which today it does not.
Naming it as gated is the honest position rather than promising it.

### The "tips" itch is already largely served

Two things in the design deliver the value without the liability:

- **The strategy desks (§11.2).** Their rules are published, so *"what is Momentum Desk doing and
  why is it beating me"* is a tip from a source that cannot scam anyone. Saiful's own instinct —
  *"I would copy the bots trading!"* — is this working.
- **The 12 agents.** The product already owns a licensed-safe way to comment on trades. A post-close
  agent read on the field is on-brand, moderation-free, and closer to what a user actually wants
  than a stranger's hot take. It must stay retrospective and educational — never a forward
  recommendation.

---

## 4. What this review changes

| # | Change | Where |
|---|---|---|
| 1 | **Ad invariant** — no ad may be required, rewarded, or gate anything | CR109 §8.1, §15 |
| 2 | Ads are ambient, on non-contest surfaces; **never in the Close** | CR109 §8.1 |
| 3 | Ads are **their own CR** — no SDK, consent flow or units exist | here |
| 4 | **Reminder rule** — decisions, not watching; caps and quiet hours | CR109 §10.1 |
| 5 | **Social phased A→B→C**, each gated on Guideline 1.2 | CR109 §11.4 |
| 6 | Playability recommendations accepted as the retention backbone | CR109 §10.1 |

---

## 5. Closing the documentation

**The design is complete and internally consistent.** It survived five rounds of review — the
account split, thin fields, playability, the disclosure reversal, and this one — and each round
found something real. The three-layer model (§3) has now caught two problems on its own (rewarded
ads, and the champion-reward question), which is the sign it was worth writing.

**Decided and stable:** the training/game split, entries with fresh capital, one run per cadence,
TWR scoring, placement-with-benchmark-fallback, no arena rules, market-hours filling, the reward
ladder, disclosed strategy desks, the eligibility rule, duels as slice 3b, and thin-slice phasing.

**Open, and none of it blocks slices 1–3:** the eight tuning values in §18 (thin-field thresholds,
benchmark choice, minimum forfeit debit, title thresholds, blowup threshold, settlement freeze,
queued-order visibility) and **naming** — the game, a run, and the boards are all still unnamed;
AMI Cash is settled as the money.

**Not engineering, and on the critical path to launch rather than to build:** the §15 compliance
work — D-060 superseded, `roadmap.md:138` amended, `daily_and_streaks.md` amended,
`competition_rules.md` re-versioned to v2.0 with the §8.5 eligibility clause, and the App Store
declaration re-validated. Slices 1–2 carry zero compliance surface, so this runs in parallel rather
than in front.

**Ready for the Architect.** [`implementation_plan.md`](implementation_plan.md) carries the schema,
contracts, fences, lane split and test matrix; a lane assign should reference it rather than restate
it.
