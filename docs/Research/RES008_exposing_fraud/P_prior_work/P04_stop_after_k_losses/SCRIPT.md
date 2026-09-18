# P04 — VOICE-OVER SCRIPT — "Stop after two losses"

**Week:** 12 · **Verdict:** `DISPROVED` mechanically; behavioural value untested and left standing ·
**Brief:** [VIDEO_BRIEF.md](VIDEO_BRIEF.md) · **Charts:** [charts/](charts/) ·
**Source study:** `docs/Research/RES001_finding_the_edge/06_absorption_and_elimination/`
(pre-registered `3b3c2e7d`, 2026-08-31)

**Length:** 974 spoken words = 6 min 30 s of speech at 150 words a minute; with the pauses marked
below (charts building in silence), ≈ 8 min 06 s

> **Two claims live here and only one was tested.** The mechanical claim — that the market rewards
> pausing after losses — was tested and failed. The behavioural claim — that a person makes worse
> decisions after a losing streak — was not tested and is not touched. Beat 7 exists to keep those
> apart. It is not optional.

## How to read this file

**VO** is what the voice reads, verbatim. **SCREEN** is what is visible while that line is read.
**№** traces every number in the beat to the file and section it came from. Numbers are spoken as
words so the read is unambiguous; the on-screen figure is always the digits.

---

## 1 · Cold open — 0:00 (speech 0:31)

**VO**
A common rule: stop trading after two or three losses in a row, because a streak means something's
wrong. We tested it against the only fair comparison — skipping the exact same number of trades, but
picked at random. In ten of twelve test cells, the actual rule did worse than random skipping. This
video is about why a rule that feels obviously right can be mechanically the wrong move — and where
its real value actually is.

**SCREEN**
`charts/02_four_cell_reveal.png` holds on its title, then "10 of 12 cells: rule below random skip"
stamps over the bar pair.

**№** "The rule mean is below the placebo mean in 10 of 12 cells" — `RESULTS.md`, "H3 — stop after k
losses".

---

## 2 · The stakes — 0:31 (speech 0:33)

**VO**
Here is what is at stake for somebody who adopts this. They believe the rule is protecting the
account from a bad market — that a streak of losses is the market telling them to step back. If the
market has no memory of their last two trades, then the rule cannot be doing that, whatever it feels
like. And if it cannot be doing that, it is worth knowing what it is actually doing instead, because
stepping aside is never free.

**SCREEN**
A mock panel we drew ourselves: "3 LOSSES IN A ROW — STOP". No real product UI, no platform chrome.

**№** No figures in this beat.

---

## 3 · What would convince us — 1:04 (speech 0:55 + 0:10 on the highlighted prediction)

**VO**
This one was written down before any code ran, on the thirty-first of August, in a commit you can
check. The test: compare the rule's forward returns after a stop against a placebo that skips the
identical number of trades, chosen at random. If the rule beats random skipping, the market is
rewarding it and the effect is real. If it does not, then whatever value the rule has is somewhere
other than the market. And the prediction was written down too — we said in advance we expected a
null, because trade outcomes on a mechanical rule are close to independent. Worth saying plainly:
this is a case where the result went the way we guessed. That is not always how it goes on this
channel, and we show you the ones that surprise us too.

**SCREEN**
`PREREGISTRATION.md` scrolls; commit `3b3c2e7d`, dated 2026-08-31. The line "We predict B − C is
zero" highlights.

**№** Prediction and design — `PREREGISTRATION.md`, "H3 — do trader-state filters beat trading less?".

---

## 4 · The test, as taught — 2:09 (speech 0:25 + 0:15 for the counter to run)

**VO**
The mechanism, exactly as it is taught. Count consecutive losing trades. When the count hits k — we
tested k equals two and k equals three — skip the next trade, then resume. Run on the S&P index,
long only, trades that do not overlap, and no costs modelled on either side, which keeps the
comparison clean rather than flattering one arm.

**SCREEN**
`charts/01_loss_streak_mechanism.png` — the counter ticks loss, loss, then SKIP, for both k values.

**№** k ∈ {2, 3}; SPY daily, non-overlapping trades — `PREREGISTRATION.md`, "H3" table.

---

## 5 · The fair test, and the reveal — 2:49 (speech 1:26 + 0:25 for the four-cell chart to build)

**VO**
Now the comparison that matters. Instead of asking "did the rule make money", ask "did the rule beat
simply skipping the same number of trades at random". Because if you skip trades, you change your
results — of course you do. The question is whether skipping *these particular* trades is better
than skipping any trades at all.

Four cells make the point. In the definition window, two thousand five to twenty eighteen, at a
one-day horizon with k equals two, the rule came in seventeen thousandths of a percent below the
placebo. At three days, seventy-eight thousandths below. In the holdout, twenty nineteen to twenty
twenty-six, with k equals three: one day, twenty-seven thousandths below; five days, eighty-three
thousandths below. All four negative. And in three of those four, the ninety-five percent interval
does not include zero — which means it is not just noise, it is reliably, if slightly, worse.

Now the honest framing of the whole picture. Across all twelve cells the rule was below the placebo
in ten. But nine of the twelve intervals do include zero. So the correct statement is not "every
test proved harm". It is: the rule lands below random skipping far more often than not, and every
interval that is decisive at all is decisive against it.

**SCREEN**
`charts/02_four_cell_reveal.png` builds row by row; the three intervals that exclude zero turn red
last. Footer stays visible showing 3 of 12.

**№** Def h1 k2 −0.017% (CI −0.045…+0.012); Def h3 k2 −0.078% (CI −0.148…−0.007); Hold h1 k3 −0.027%
(CI −0.053…−0.003); Hold h5 k3 −0.083% (CI −0.171…−0.006); "nine of twelve cells include zero"; "the
rule mean is below the placebo mean in 10 of 12 cells" — `RESULTS.md`, "H3" table and the paragraph
below it.

---

## 6 · Why — 4:40 (speech 0:36 + 0:15 for the sketch)

**VO**
The mechanical reason is not mysterious. The index shows mild mean reversion — after a down move,
the next move tends very slightly to recover. A rule that pauses right after losses is therefore
pausing at exactly the moment the small rebound tends to arrive. It is not reading the market and
deciding conditions are bad. It is stepping out of the doorway just as the rebound comes through it.
That is the entire mechanism, and it is why the direction of the miss is consistent rather than
random.

**SCREEN**
`charts/03_mean_reversion_sketch.png` — the dip, the rule triggering, the skipped trade sitting out
the rebound. Stamp visible: illustrative sketch, not a measured price path.

**№** "Mechanically that is what mild mean-reversion implies: sitting out after losses sits out part
of the rebound" — `RESULTS.md`, "H3".

---

## 7 · What is true — 5:31 (speech 1:22 + 0:15 for the card)

**VO**
Now the part that matters most, and the part a debunk video usually skips.

None of this shows the rule is worthless. It shows the rule's value is not where people think it is.
The market is not rewarding the pause. But the rule did not come from a study of the market — it
came from people noticing that after a run of losses, they themselves get worse. They chase. They
size up to make it back. They take setups they would have passed on an hour earlier. If that is
true, then stopping after three losses is not a market filter at all. It is a circuit breaker on the
person.

And here is the thing we have to say clearly: this test cannot speak to that. We tested whether the
market rewards the pause. We did not test whether people degrade after losses, and nothing here
counts as evidence against it. It is a real claim, it is testable, and it is a completely different
one. What we can say is that if you use this rule, you should know which of the two jobs it is
doing — because the reason you keep it should match the reason it works.

**SCREEN**
Card: "The rule's value: behavioural, not mechanical." Below it, two lines — "Tested: does the
market reward the pause? No." / "Not tested: do people get worse after losses?"

**№** "The entire value … lies in the trader, not the market" — `RESULTS.md`, "H3" section, and
"What this answers" §2–3. Behavioural-value-only classification — `01_prior_work.md`, P04 row.

---

## 8 · Check the next one yourself — 7:08 (speech 0:23 + 0:05 end card)

**VO**
So the question to carry into the next risk-rule video. Ask what the rule is claimed to protect you
from: the market, or your own next decision. Those are two different claims and they need two
completely different kinds of evidence — and most videos that teach a rule like this never say which
one they mean.

**SCREEN**
The question alone on a card: "Protecting you from the market — or from your next decision?"

**№** No figures in this beat.

---

## 9 · AMI + disclaimer — 7:36 (speech 0:20 + 0:10 end card) — ends ≈ 8:06

**VO**
AMI Trade is a simulator. You practise the process with a twelve-analyst team and no real money, and
AMI walks the reasoning with you. We promise no edge. What we can give you is somewhere to find out
which of your rules is doing the job you think it is.

**SCREEN**
AMI end card. Disclaimer: educational content; AMI Trade is simulation-only; nothing here is
investment advice.

**№** No figures in this beat.

---

## Production notes

- **Beat 7 is load-bearing and must survive the edit.** Without it this episode overstates its own
  finding: the source separates the mechanical null from the untested behavioural value, and the
  brief requires both on camera. Cut length from beat 2 or 6 if needed, never from 7.
- **Never say the rule is "useless" or "wrong".** The tested claim failed; the behavioural claim was
  not tested. The script is worded to keep that line and any trim must preserve it.
- **Do not imply every cell shows harm.** Nine of the twelve intervals include zero. Beat 5 states
  the 10-of-12 and the 9-include-zero facts in the same breath deliberately — they travel together.
- **The source names the rule's author and quotes him with a timestamp. This script does not, and
  must not.** If a future edit pulls a quote from `RESULTS.md`'s H3 section, strip the attribution
  before it reaches any committed file — this repo is public.
- **No costs are modelled in either arm.** If asked what would change the numbers: the source notes
  costs would make filtering arms look relatively better, which is a reason not to read this null as
  evidence *for* filtering — not a reason to doubt the finding.
- **Assets to produce before recording:** the beat-2 mock "3 LOSSES IN A ROW — STOP" panel and the
  beat-3 pre-registration scroll. Both are drawn by the editor; neither exists in `charts/`.
- **Runtime lands under the 8–10 min target.** If a longer cut is wanted, extend beat 5 with the
  remaining eight cells rather than padding elsewhere — the data is in `results.json` under
  `filters.*.H3`.
- EN script — flag for AR / MS translation at v1.0.
