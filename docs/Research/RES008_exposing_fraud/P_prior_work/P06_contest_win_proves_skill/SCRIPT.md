# P06 — VOICE-OVER SCRIPT — What a contest win can and cannot tell you

**Week:** 9 · **Verdict:** `NOT SUPPORTED` — a +100% month is what a big-enough contest produces on
its own · **Brief:** [VIDEO_BRIEF.md](VIDEO_BRIEF.md) · **Charts:** [charts/](charts/) ·
**Source study:** `docs/Research/RES001_finding_the_edge/03_volatility_regime_sizing/` §E
(pre-registered `55a66533`, 2026-08-30)

**Length:** 1,068 spoken words = 7 min 07 s of speech at 150 words a minute; with the pauses marked
below (charts building in silence), ≈ 8 min 37 s

> **This is the most constrained script in the series.** The finding is a conditional statistical
> statement whose antecedents were never verified against any real contest. It shows a headline
> return does not *require* skill to explain it. It cannot show skill was absent, and it says nothing
> about any individual. Beats 3 and 7 carry that limit and neither may be cut. No contest, person or
> channel is named or alluded to anywhere.

## How to read this file

**VO** is what the voice reads, verbatim. **SCREEN** is what is visible while that line is read.
**№** traces every number in the beat to the file and section it came from. Numbers are spoken as
words so the read is unambiguous; the on-screen figure is always the digits.

---

## 1 · Cold open — 0:00 (speech 0:29)

**VO**
A trading contest crowns a winner who turned an account into double in a month, and the pitch is:
this proves the method works. We tested that logic directly, using nothing but statistics — if you
put a few hundred people with no edge at all into a high-volatility contest, what does the winner's
return look like by pure chance? This video is about what a trophy can and can't tell you.

**SCREEN**
`charts/01_crowd_of_dots.png` — the cloud of zero-skill draws appears, then the single highest dot
is ringed and labelled.

**№** Mechanism only; no measured claim in this beat. Draw spread comes from
`E.by_n["300"].required_monthly_vol`.

---

## 2 · The stakes — 0:29 (speech 0:26)

**VO**
Why this matters. A contest result is one of the most persuasive things in this whole space,
because unlike a screenshot it looks audited and final. Somebody sees a champion's number, concludes
the method behind it is proven, and buys the course or copies the approach. That inference is doing
enormous work, and it is worth asking what has to be true for it to hold.

**SCREEN**
A card we drew ourselves: "+100% IN ONE MONTH — CHAMPION". Generic. No real contest branding, no
person, no logo.

**№** No figures in this beat.

---

## 3 · What would convince us, and what this test is not — 0:55 (speech 1:02 + 0:10 on the limits card)

**VO**
Now, before any number: this test is narrower than you might expect, and we want to be exact about
it.

We are not testing a contest. We are not testing a person. We did not measure how many people enter
any real competition, and we did not measure how volatile any real contestant's trading is. What we
did is a null model — a piece of arithmetic that asks: suppose nobody in the field has any skill
whatsoever, purely random outcomes. How big would the best result be, just because you took the
maximum of a few hundred random draws?

That question has an exact answer, and it was pre-registered on the thirtieth of August before the
arithmetic was run. What the answer can establish is narrow: whether a headline number *requires*
skill to explain. It cannot establish that skill was absent. Hold onto that distinction, because we
come back to it at the end.

**SCREEN**
`PREREGISTRATION.md` scrolls; commit `55a66533`, dated 2026-08-30. Then a limits card: "Tested: does
a +100% month require skill? / Not tested: any real contest, any real person."

**№** Pre-registration commit and date — the source study's `PREREGISTRATION.md`. The conditional
framing and unverified antecedents — `RESULTS.md` §E.

---

## 4 · The mechanism — 2:07 (speech 0:44 + 0:15 for the crowd to build)

**VO**
The mechanism is something most people already know but rarely apply here. Take enough random
draws, and the biggest one is large — not because any draw was special, but because you went looking
for the largest. Flip a thousand coins ten times each and somebody gets ten heads. They did not flip
better. There were just a lot of them.

A contest is precisely that structure. Every entrant is a draw. The trophy goes to the maximum. So
the question becomes arithmetic: how volatile does the trading have to be for the *expected*
maximum, across a field of a given size, to land at plus one hundred percent?

**SCREEN**
`charts/01_crowd_of_dots.png` builds: dots scatter, then the maximum is ringed. Stamp visible:
illustrative draw, mechanism only.

**№** No measured figures in this beat.

---

## 5 · The reveal — 3:06 (speech 1:50 + 0:25 for the bar chart to build)

**VO**
Here is the table, and it is the whole episode.

With fifty entrants, all of them with no skill at all, you need monthly volatility of about
thirty-three percent for a doubling to be the expected best result. With a hundred entrants,
twenty-nine percent. With three hundred, twenty-five percent. With five hundred, just under
twenty-four percent.

Notice the direction, because it is the opposite of what intuition suggests. The *bigger* the
contest, the *less* volatile anybody needs to be for a doubling to show up at the top. Going from
fifty entrants to five hundred drops the requirement by nine percentage points — from about
thirty-three down to about twenty-four. Nobody in that field got better at trading. There were
simply ten times as many draws, so the maximum reached further out into the tail on its own. More
draws, more extreme maximum. That is just how maxima work, and it is why a big field is a worse
place to look for evidence of skill than a small one, not a better one.

And the context for those percentages: the S&P index runs about five and a half percent monthly
volatility. So those requirements are roughly four to six times the index — the table puts them at
five point nine eight times for fifty entrants, down to four point three two times for five hundred.
That is a lot of volatility. It is also entirely achievable with leverage, which is common in
contest accounts. What we did not do is check whether any real contestants actually trade at those
levels, so treat that multiple as the condition it is, not as an observation.

**SCREEN**
`charts/02_entrant_count_vs_volatility.png` builds bar by bar, the SPY reference line already drawn,
multiples appearing inside each bar.

**№** 50 → 32.7% (5.98× SPY); 100 → 29.0% (5.30×); 300 → 25.0% (4.58×); 500 → 23.6% (4.32×); SPY
monthly volatility 5.5% — `RESULTS.md` §E table, from `E.by_n` and `E.spy_monthly_vol`.

---

## 6 · What it means — 5:21 (speech 0:34 + 0:10)

**VO**
So what does the arithmetic license us to say?

Only this: *if* a field is a few hundred strong, and *if* entrants are trading at four to six times
index volatility, then a doubling at the top of the leaderboard is simply the expected maximum. It
requires no skill anywhere in the field. Not unusual. Not remarkable. Just what taking the largest
of several hundred volatile draws produces.

Both of those "ifs" are real conditions, and we did not verify either one against any actual
contest.

**SCREEN**
The two conditions as a card, each with an unchecked box: "field of a few hundred — not verified" /
"entrants at 4–6× index volatility — not verified".

**№** "This is a conditional, and the antecedents are not verified" — `RESULTS.md` §E.

---

## 7 · What is true — 6:05 (speech 1:16 + 0:15 for the card)

**VO**
Now the part that keeps this honest, and it cuts against the easy version of this video.

"Consistent with luck" is not "was luck." This arithmetic cannot show that skill was absent from any
contest, and it does not try to. Somebody has to win. That person may well be the most skilled
trader in the field — nothing here argues otherwise, and we are not going to pretend it does.

What the result does is much smaller and still worth knowing: a championship return, on its own,
carries little information about skill. It is weak evidence, not because the win is fake, but
because the structure of a contest manufactures a large maximum regardless. If you want to know
whether somebody is skilled, the trophy is close to the least informative thing you could look at.
Process over time, on statements, across conditions — that is where the evidence would be.

And one more time, because it matters: we tested a piece of arithmetic about contests in general.
We did not test any contest, any result, or any person, and this episode should not be used as if we
had.

**SCREEN**
Card: "A championship return, on its own, carries little information about skill." Below: "It does
not show the winner lacked skill. Someone has to win."

**№** "'Consistent with luck' is not 'was luck'", "someone had to win — plausibly the best trader in
the field", and the narrow licence — `RESULTS.md` §E.

---

## 8 · Check the next one yourself — 7:36 (speech 0:24 + 0:05 end card)

**VO**
So the question for the next leaderboard you are shown. Ask how many people were in the field, and
how much leverage the format allows. Those two numbers decide how big the top result should be
before anybody does anything clever at all. If nobody will tell you the field size, you have learned
something about the claim already.

**SCREEN**
The question alone on a card: "How many entrants — and how much leverage does the format allow?"

**№** No figures in this beat.

---

## 9 · AMI + disclaimer — 8:05 (speech 0:22 + 0:10 end card) — ends ≈ 8:37

**VO**
AMI Trade is a simulator. You practise the process with a twelve-analyst team and no real money, and
AMI walks the reasoning with you. We promise no edge, and we will not show you a leaderboard. What
we can give you is a place to build the kind of record that would actually be evidence.

**SCREEN**
AMI end card. Disclaimer: educational content; AMI Trade is simulation-only; nothing here is
investment advice.

**№** No figures in this beat.

---

## Production notes

- **Beats 3 and 7 are load-bearing and neither may be cut.** Together they are the only places the
  episode states that the antecedents were never verified and that "consistent with luck" is not
  "was luck". Without both, this becomes a video accusing somebody of being lucky, which the source
  explicitly does not support. Trim beat 2 or 4 if length is needed.
- **Nothing is personalized, ever.** No contest name, no person, no channel, no logo, no year, no
  division, no dollar figure that could identify a real result. This claim in particular must not be
  personalized in any way. The beat-2 card is deliberately generic and must stay that way.
- **Do not introduce the audited-broker-statement point.** The source raises contest auditing and
  the wider monthly/quarterly selection surface as a separate, uncomputed consideration. It is not
  part of the tested statistic and must not appear in any numeric beat.
- **No annualising or extrapolating the volatility multiples.** They hold for those four entrant
  counts as computed, and nowhere else. Do not interpolate a figure for some other field size on
  screen.
- **The source struck an adjective for being unsupported** — an earlier draft called 4–6× index
  volatility "unremarkable" for leveraged micro futures. This script does not characterise how
  achievable those levels are beyond noting leverage is common in contest accounts, which is the
  furthest the source goes. Do not restore the stronger wording.
- **Assets to produce before recording:** the beat-2 generic "+100% IN ONE MONTH — CHAMPION" card,
  the beat-3 pre-registration scroll and limits card, and the beat-6 two-conditions card. All drawn
  by the editor; none exist in `charts/`.
- EN script — flag for AR / MS translation at v1.0.
