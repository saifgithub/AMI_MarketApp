# RES005 — What is the trainable skill, and can AMI train it?

Premise accepted (Saiful, 2026-08-30): Creamer is skilled. RES003 Test C supports it — the
mechanism he describes beat the placebo 6/6, where Rader's directional claim died 0/18.
Question is no longer *whether*; it is *what*, and *can a simulator train it*.

Source: `PL7LKUsCgIQ` transcript, timestamps in brackets.

## The skill, in his words — and it is not the setup

He is explicit that the entry is the small part:

> *"I used to put that as the holy grail, thinking that if I can just find the right setup or
> the right candlestick pattern... what changed was I needed to understand what am I
> participating in, who are the other participants, what are they trying to do, what are their
> limitations, and where do they need to start actually participating."* [03:35]

> *"Entries, setups — it comes down to like the final 5 to 10%."* [04:06]

> *"The money is the byproduct of proper execution."* [04:36]

Eight components:

| # | Component | Where |
|:--|:--|:--|
| 1 | Model the other participants — who is forced to act, and when | [05:07] |
| 2 | Effort vs result — *"who is being successful in that effort in causing price progression and who is not"* | [35:27] |
| 3 | Selective participation — *"your biggest advantage is that you have selective participation, and most traders don't take advantage of that"* | [35:58] |
| 4 | Confirm, never anticipate — *"I try and guess and I don't let it confirm itself first"* is his definition of a bad trade | [43:09] |
| 5 | Good loss vs bad loss — and *"if that trade wins... it's reinforcing bad behavior"* | [43:40] |
| 6 | A/B/C sessions graded on execution — *"They have nothing to do with the P&L"*; *"back-end optimization, not front-end"* | [40:05] |
| 7 | Rules need an action attached — *"'don't overtrade' is not a rule"* | [44:10] |
| 8 | Find your own breaking point **from your own data** — hard shutoff 90 min in; stop after 2 consecutive losses because 3 is where he tilts | [46:12] |

## The asymmetry that makes this a product

He discovered #8 by hand, over years, and says the thing that matters most:

> *"A lot of the times when it comes to these things where you're trying to self-diagnose them,
> they're invisible to the person it's happening to."* [45:12]

> *"If a trader tilts and you ask them where did this start breaking down, they'll probably
> point at the big trade that lost. That's not where things broke. Some sequence of events
> occurred, and you have to find out where it is."* [45:42]

**A simulator has the event log. He did not.** What cost him years of manual self-observation
is a query for us. This is the one place we can do something he cannot do for himself.

## What we can train, and what it maps onto

The raw material already exists and is already deterministic:

- **`ComplianceResult.violations`** ([schemas/trade.py:203](../../backend/app/schemas/trade.py#L203))
  — a deterministic mandate-compliance check runs on every proposed trade *already*. This is
  exactly "did the user follow their own rules", computed, not inferred.
- `Verdict` with `action`/`size_pct`/`entry`/`target`/`stop`, incl. `VerdictAction.PASS`.
- `journal_store`, trade timestamps, `mandate_store`.

| Trainable | How | Status |
|:--|:--|:--|
| **Good loss vs bad loss** | cross `violations` (process) with P&L (outcome) → 2×2. The dangerous cell is **win + violation** — his "reinforcing bad behavior" | new |
| **A/B/C session grade** | same input aggregated per session, graded on adherence, **never on P&L** | new |
| **Personal breaking point** | sequence analysis: does adherence degrade after the Nth trade, after k consecutive losses, after X minutes? | new |
| **Where the tilt started** | the inflection in that sequence — the thing he says is invisible from the inside | new |
| **Selective participation** | no-trade rate; `VerdictAction.PASS` already exists | partly |
| **Rules with actions attached** | sharpens Brief Your Agent's mandate UI (#7) | partly |

## What already exists — do not rebuild

- **CR062 (done)** already *teaches* all of this: EVAL 1–8, lessons 357–364 — process vs
  outcome, decision journaling, pre/post-mortem, self-scoring — sourced to Duke, Taleb, Marks.
- **The gap is instrumentation, not curriculum.** We teach the concept and compute none of it.
- Worth naming a tension: `reputation_service` awards points for **engagement** — streaks,
  lesson starts, journal entries. Creamer's whole argument is that consistency comes from
  *eliminating bad sessions*, not accumulating activity. A system that rewards showing up
  while teaching process-over-outcome is pulling against its own lesson.

## What we cannot train

Component #2 at his resolution needs footprint/delta/level-2 data we do not have, on an
instrument and horizon we do not run. Components #1 and #2 are teachable as *concepts*
(BOK material); they are not trainable as *reps* here.

## Sufficiency — the constraint that must ship with it

Behavioural detection is estimation, and CR136's rule applies unchanged: a user with 8 trades
has no estimable breaking point. Every read must carry a sufficiency gate and return null
rather than a confident number — an LLM cannot detect that a behavioural claim is noise, and
a fabricated "you tilt after 2 losses" is worse than silence.

## Recommendation

One CR: **decision-quality instrumentation** — the 2×2, the session grade, the sequence read.
It is a new service over data we already collect, it changes no decision path, and it makes
the EVAL curriculum measurable instead of merely taught.
