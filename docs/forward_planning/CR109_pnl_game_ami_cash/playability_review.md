<!-- CR109 playability review — is the game easy to start, is it addictive, and what
     brings a player back. A critique of the design in CR109.md, not a restatement of it.
     Several findings require design changes; those are marked and carry a recommendation.
     Design stage. -->

# CR109 — playability review

**Companion to [`CR109.md`](CR109.md).** `AT:Gamer`, 2026-07-30.

Saiful: *"you need review the playability of the game. will this game be easy to start? will it be
addictive? what brings back the player."*

Three questions, answered honestly. The design is coherent; **it is not yet playable**, and the
worst problem is one this design introduced.

---

## Verdict

| Question | Answer |
|---|---|
| **Easy to start?** | **No.** A new player can wait up to six days before they may enter, and when they do, the game is the one mode with no analyst support. |
| **Addictive?** | **Moderately, and less than what it replaces.** The strongest hook is inherent (money at risk), but the design's heartbeat is weekly and it deletes the only daily mechanic the app has. |
| **What brings them back?** | Ranked below. The honest answer is *open positions* — which is also the mechanic closest to the psychology the product exists to teach against. |

---

## 1. The dead start — the worst flaw, and it is mine

CR109 §4 says **entry closes at the bell**, and weekly fields run on fixed calendar starts. Put
those together:

> A player who downloads the app on **Tuesday** cannot enter a game until **the following Monday.**

Their first experience of the headline feature is *"come back in six days."* No game survives that.
I introduced the rule for a good reason — a race needs a start line, and mid-period entry breaks
the same-clock fairness — but I never checked it against a first session.

**Fix — rolling weekly fields.** A new weekly field opens **every trading day**, each running five
trading days. Wednesday's field runs Wed→Tue. Everyone inside a field still starts on the same day
against the same market, so the fairness argument is untouched; the wait drops from up to six days
to at most one.

This is the demand-gated rolling-start machinery §6.6 already specifies for the long cadences,
applied to weekly as well. It costs almost nothing because it is the same code path.

**Status: recommended, and I consider it a defect in the design rather than a preference.**

---

## 2. The game is the app's *unsupported* mode

*"Games is only about trade"* means no Room, no 12 agents, no mandate. Thematically right — the
classroom/exam frame is good. But look at what it does to a beginner:

| | Training | The Game |
|---|---|---|
| Help choosing a position | 12 analysts, a Room verdict | **none** |
| Guardrails | the safety floor rejects bad sizing | **none** |
| Consequences | none, reset freely | **scored, permanent** |

So the **harder, unsupported, permanently-scored mode is the one on the front page**, and a new
player's first action there is "pick a stock" with no help and real consequences. That is backwards.

**Fix — gate the first entry behind a small training milestone.** One completed Room run, or a
short lesson block. This does three things at once: the player arrives with a method rather than a
guess, the game becomes something *earned* rather than something defaulted into, and the training
side gets a reason to exist that isn't homework.

**Status: DECIDED 2026-08-16 (Saiful) — gate it.** First entry gated behind a training milestone.
It deliberately delays access to the headline feature, which is a real cost he accepted.

---

## 3. We are deleting the only daily mechanic — verified

Amendment A removes `reputation_service.py`. **The streak lives there** —
`reputation_service.streak()`, `def streak(...)`, with milestones at 7 / 30 / 100 / 365 days.

| | Today | After CR109 |
|---|---|---|
| Reason to open the app **daily** | streak, daily challenge, lesson progress | *the daily rank beat, once a live run exists* |
| Reason to open **weekly** | league roll | the Close |
| Resolution tempo | daily | **weekly** |

The daily challenge content and endpoint survive (they only stop *awarding*), but the streak — the
single most reliable daily-return mechanic in consumer apps — is deleted outright. **The game is
more interesting than the league and has a slower heartbeat.** That is a net engagement risk we are
walking into with our eyes closed unless it is named.

**Fix — re-home a streak onto the game, but change what it counts.** Not check-ins: a check-in
streak is engagement farming and it teaches nothing. Count **runs finished without forfeiting**, and
**consecutive periods entered**. Both are real commitments, both reward the behaviour the product
wants (finish what you start), and neither can be farmed by opening the app.

**Status: recommended.** Cheap — it is a query over `game_entries`, not a new subsystem.

---

## 4. Time to first feedback is about five days

Games hook in the first session. This one's first session is:

```text
enter  →  pick 2–3 stocks  →  ...nothing...  →  (5 days)  →  a score
```

There is no day-0 payoff at all. The market moves slowly and we cannot change that — but we can
stop leaving the first day empty.

**Fixes, all cheap:**

- **Provisional rank from the first trade.** "You're 4th of 26 as things stand." It is meaningless
  on day 1 and that is fine — it makes the field *present*.
- **Make the pre-start a moment.** The bell, the field reveal, the entry countdown are already in
  §10; they are the only content that exists before the market does anything. Use them.
- **A daily close ritual in-app**, not only via push: one card, once per US close, showing what
  moved and where you sit. This is the heartbeat, and it must not depend on the push CR.

**Do not add a daily cadence to solve this.** One-day P&L is almost pure noise, it would make
career points record luck, and a daily win/lose cycle on money is the most gambling-shaped thing we
could build. The answer is better day-0 *content*, not a faster scoring loop.

---

## 5. The first close decides retention, and at alpha it will be flat

The Close is the emotional payoff of the entire design. A new player's first one, at alpha field
sizes, currently reads:

> **1st of 3.** Scored against the S&P 500, not against the field. No title.

Technically correct (§6.6), and completely deflating.

**Fix — the first close must always deliver something.** Either seed the first field so it is
never trivially small, or make the first close celebrate something that is true regardless of field
size: your actual return, your best decision, your drawdown control, "you finished." §8.4's
progress markers exist for exactly this and should be prioritised **with slice 3, not deferred to
slice 8.**

---

## 6. What actually brings a player back — ranked honestly

| Rank | Hook | Strength | Note |
|---|---|---|---|
| 1 | **Open positions** | strongest | You have money at risk, so you check. Reliable, and **the closest thing here to the psychology the product exists to teach against.** Worth being deliberate rather than accidental. |
| 2 | **Rank threat** | strong | Someone passed you. Requires a populated field — inert at alpha. |
| 3 | **The Close** | strong but rare | A scheduled appointment. Once per period. |
| 4 | **Rivals** (roadmap #2) | moderate, **cheap** | A named opponent 0.4% ahead is a daily reason to look. XS to build, no social graph. **Worth pulling forward.** |
| 5 | **Progression** | weak early | Career points move slowly and mean little until titles are in reach. |
| 6 | **Streaks** | strong — **currently being deleted** | See §3. |

**The uncomfortable observation:** the most addictive mechanic available to us is the one we should
be most careful with. A P&L game with money at risk, a restart button and no position limits is
engaging *because* of the pull we spend 292 lessons warning about. That does not make it wrong —
Saiful set the frame knowingly — but the design should get its engagement from **rank, ritual and
rivalry**, not from encouraging position-checking. Which is, concretely, why §10's *one beat per
market close, never per tick* rule matters more than it looks: per-tick movement is a slot machine.

---

## 7. Is it addictive? — the honest answer

Present in the design:

- **variable reward** — inherent to markets ✓
- **appointment mechanic** — the Close ✓
- **loss aversion** — open positions ✓
- **social comparison** — the board ✓ (inert until fields populate)
- **progression** — career points, titles ✓ (slow)

Missing or removed:

- **a daily reason** — being deleted with the streak ✗
- **near-miss feedback** — "you were 0.3% off 2nd" is free and not specified anywhere ✗
- **collection** — badges exist and are dark; cosmetics are slice 8 ✗
- **fast first payoff** — five days ✗

The levers that would make it *more* addictive — real stakes, faster resolution, variable-ratio
rewards — are exactly the ones a simulation-only training product should not pull. **So the ceiling
on addictiveness is deliberately capped, and that is correct.** The work is to reach that ceiling
through ritual and rivalry rather than to land accidentally below it.

---

## 8. Recommended changes, in priority order

| # | Change | Cost | Status |
|---|---|---|---|
| 0 | **Duels, as slice 3b** — the only competitive format that works at alpha | S | **Accepted (Saiful).** See below. |
| 1 | **Rolling weekly fields** — a new field every trading day | S | **Defect-grade. Folded into CR109 §4.** |
| 2 | **Progress markers at the first close** — move from slice 8 to slice 3 | S | Recommended |
| 3 | **Daily close ritual in-app**, independent of push | S | Recommended |
| 4 | **Re-home the streak onto runs finished / periods entered** | S | Recommended |
| 5 | **Provisional rank + near-miss lines** | XS | Recommended |
| 6 | **Pull Rivals (roadmap #2) forward** to just after slice 4 | XS | Recommended |
| 7 | **Gate first entry behind a training milestone** | S | **DECIDED 2026-08-16 — yes, gate it** |
| 8 | **Seed or guarantee a minimum first field** | M | Needs a decision alongside the §6.6 thresholds |

Items 1–6 are all small, and together they change the game from *coherent* to *playable*. Item 7 is
the only one with a real product tradeoff.

---

## 9. Duels — accepted, and this review is the argument for them

Saiful, on reading the above: *"I really like the Dual….. how can we bring it back?"*

**It comes back by inverting where it sat.** This review's central complaint is that at alpha
*nothing social works*: §6.6 needs `n ≥ 8` before placement means anything, §16.4 concedes every
alpha field is below that, and §6 of this review ranks "rank threat" as a strong hook that is
**inert until fields populate**. The open board — the flagship — is the one surface that cannot
function at launch.

**A duel needs two players.** It is therefore not a post-MVP luxury sitting behind the board; it is
the only competitive format that works *at the exact moment the board cannot*, which makes it the
answer to hooks #2 and #4 simultaneously.

It also fixes §5 of this review. Compare the first close a new player can actually get:

| | Open board at alpha | Duel at alpha |
|---|---|---|
| What it says | *"1st of 3. Scored against the S&P. No title."* | *"You beat VECTOR_11 by 1.4%."* |
| Emotional read | flat, faintly embarrassing | a result |

Two constraints, both carried into [`CR109.md`](CR109.md) §11.1 and slice 3b:

- **Head-to-head scoring, carved out of both existing paths.** A duel must never touch the
  placement curve — at `n = 2`, `p` is exactly 1.0 or 0.0, so the winner would take the largest
  award in the game and the loser the largest debit — and must never route to the benchmark path
  either, because here `n = 2` is intended rather than a shortfall.
- **Auto-matched only at MVP.** Onboarding is anonymous-first, so alt accounts are nearly free.
  Direct challenge-by-handle plus cheap accounts is a trivial farm: make an alt, throw the duel,
  bank the win, repeat. Auto-matching removes the ability to choose your victim, closing it
  structurally rather than by detection. Challenge-a-friend can come later, awarding no career
  points or capped per period.

**Sequencing:** slice 3b, *before* the open board rather than after — duels work at five players
and the board needs fifty.
