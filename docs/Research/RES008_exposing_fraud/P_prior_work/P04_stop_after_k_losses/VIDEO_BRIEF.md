# P04 — VIDEO BRIEF — "Stop after two losses" doesn't help the market. It helps you.

**Verdict:** `DISPROVED` mechanically — below placebo in 10/12 cells; behavioural value only
(as recorded in `01_prior_work.md` / `TRACKER.md`) · **Source study:**
`docs/Research/RES001_finding_the_edge/06_absorption_and_elimination/` (pre-registration commit
`3b3c2e7d`, dated 2026-08-31) · **Results:**
[`06_absorption_and_elimination/RESULTS.md`](../../../RES001_finding_the_edge/06_absorption_and_elimination/RESULTS.md)
**Runtime target:** 8–10 min · **Format:** faceless, chart-driven, voice-over
**Claim class reach:** not measured — prior work

## Search intent

- **Primary keyword:** stop trading after losses tested
- **Secondary:** loss streak rule strategy · stop after 2 losses trading rule · does a loss limit work
- The primary keyword appears in the title, the first spoken sentence, and the first line of the description.

## Title options (≤ 60 characters, all literally true)

1. *We tested "stop after 2 losses." It did not help.* (50)
2. *Stop-after-losses rule tested: below placebo in 10/12.* (55)
3. *A losing-streak rule tested: it's about you, not the market.* (60)

## Thumbnail concept

One chart, one number, at most four words. A simple stop-sign icon over a small red bar (rule)
next to a taller bar (random skip, the placebo). Four words: "Rule loses to random."

## Hook (0:00–0:20) — spoken, verbatim

> "A common rule: stop trading after two or three losses in a row, because a streak means
> something's wrong. We tested it against the only fair comparison — skipping the exact same
> number of trades, but picked at random. In ten of twelve test cells, the actual rule did worse
> than random skipping. This video is about why a rule that feels obviously right can be
> mechanically the wrong move — and where its real value actually is."

## Beat sheet

| # | Beat | Time | Voice-over (gist) | On screen | Source of every number |
|:--|:--|:--|:--|:--|:--|
| 1 | Cold open | 0:00–0:20 | Hook above. | "10 of 12 cells: rule < random skip" stamped over a bar pair. | `RESULTS.md` "H3 — stop after k losses" section: "The rule mean is below the placebo mean in 10 of 12 cells" |
| 2 | The stakes | 0:20–0:50 | A viewer adopts a hard stop-after-losses rule believing it protects them from a bad market. If the market has no memory of their last two trades, the rule can't be doing what they think it's doing — and it may quietly be costing them the rebound. | Generic "3 losses in a row — STOP" mock panel we drew ourselves. | — |
| 3 | What would convince us | 0:50–2:00 | Written down before any code ran: compare the rule's forward returns after a stop to a placebo that skips the identical number of trades, chosen at random. If the rule beats random skipping, it's a real market effect. If it doesn't, the rule's value — if any — is somewhere else. The prediction was written down in advance too: we expected this one to be a null, because trade outcomes on a mechanical rule are close to independent. | Scroll of `PREREGISTRATION.md`; commit `3b3c2e7d`, dated 2026-08-31; the "We predict B − C is zero" line highlighted. | `PREREGISTRATION.md` "H3 — do trader-state filters beat trading less?" section: "We predict B − C is zero. Trade outcomes on a mechanical rule are close to independent…" |
| 4 | The test, as taught | 2:00–4:00 | The mechanism exactly as taught: after k consecutive losing trades (k = 2 or 3), skip the next trade. Run it on SPY, non-overlapping trades, long-only, no costs modelling either arm favourably. | Simple loss-streak counter animation ticking to k, then "skip". | `PREREGISTRATION.md` "H3" table: k ∈ {2, 3}; SPY daily, non-overlapping trades every h days |
| 5 | The fair test + reveal | 4:00–6:30 | Now compare against skipping the same number of trades at random instead. Across the definition window (2005–2018) and the holdout (2019–2026), four cells tested: the rule underperformed the random-skip placebo in all four, and three of those four gaps don't include zero — meaning the rule isn't just noisy, it's reliably a bit worse. Overall the rule mean sits below the placebo mean in 10 of the 12 cells run across this and the related tests. | The four-cell table on screen, the three "excludes zero" cells highlighted red. | `RESULTS.md` "H3" table: Def h1 k2 rule−placebo −0.017% (CI −0.045…+0.012); Def h3 k2 −0.078% (CI **−0.148…−0.007**); Hold h1 k3 −0.027% (CI **−0.053…−0.003**); Hold h5 k3 −0.083% (CI **−0.171…−0.006**). "The rule mean is below the placebo mean in 10 of 12 cells" |
| 6 | Why | 6:30–8:00 | The mechanical reason: SPY shows mild mean reversion, so sitting out right after a loss means sitting out part of the rebound that tends to follow. A machine that mechanically pauses after losses isn't reading anything about the market — it's just skipping the recovery. | Simple reversion diagram: a dip, a rebound, the "skipped" trade highlighted sitting out the rebound. | `RESULTS.md` "H3" section: "Mechanically that is what mild mean-reversion implies: sitting out after losses sits out part of the rebound." |
| 7 | What is true | 8:00–9:00 | This doesn't mean the rule is worthless — it means its value isn't in the market, it's in the trader. The rule exists because a person degrades after a losing streak: worse decisions follow, not because price action changes. That's a real, testable, and completely different claim — a behavioural one, not a market one — and this test can't and doesn't speak against it. | "The rule's value: behavioural, not mechanical" card. | `RESULTS.md` H3 section, the sentence concluding that the rule's entire value "lies in the trader, not the market" (the source names the rule's author; the brief does not), and "What this answers" §2–3 sections; `01_prior_work.md` P04 row: "behavioural value only" |
| 8 | Check the next one yourself | 9:00–9:40 | One question for any "risk rule" video: is the claim that this protects the account from the market, or from the trader's own next decision? Those need completely different evidence. | The question as a card. | — |
| 9 | AMI + disclaimer | last 15 s | AMI Trade is a simulator: practise process with a twelve-analyst team and no real money. We promise no edge. | AMI end card, disclaimer. | — |

## The one idea

A losing streak is a fact about your last few trades, not a signal from the market — so a
mechanical rule that reacts to it isn't managing risk, it's just occasionally skipping the rebound.

## What we must not say

- Do not say the rule is "useless" or "wrong" outright — the source explicitly separates the
  mechanical null (real, and mildly harmful) from the rule's behavioural value (real, untested here,
  and plausibly the whole reason it works for a person). Say both.
- Do not claim this test speaks to human decision quality after a losing streak — that's a
  behavioural claim the study does not test; it only tests whether the *market* rewards the rule.
- Nine of the twelve cells include zero in their interval — don't imply every cell shows harm; the
  finding is "below placebo in 10/12" and "three CIs exclude zero on the harmful side," not
  "every cell proves harm."
- No costs are modelled in this test; say so if asked what would change the numbers (the source
  notes costs would make filtering arms look relatively better, which is a reason not to read the
  null as evidence *for* filtering, not evidence against this finding).
- No creator, channel, video title or thumbnail is named or shown.

## Description (first 160 characters are the search snippet)

We tested "stop trading after 2–3 losses in a row." Compared against skipping the same number of
trades at random: the rule did worse in 10 of 12 test cells.

Pre-registered before the code ran (commit `3b3c2e7d`), predicting exactly this outcome: mechanical
trade outcomes are close to independent, so a streak-based stop can't help a machine. Its value, if
any, is in the trader who degrades after losses — not in the market.

Links: source study (pre-registration · results) · episode page · AMI Trade (UTM).
Disclaimer: educational content; AMI Trade is a simulation-only training product; nothing here is
investment advice. By policy we test claims and name no channel.

## Pinned comment

Pre-registered on 2026-08-31 in commit `3b3c2e7d`, before any test ran — and the outcome shown here
was the one predicted in advance. Source:
`docs/Research/RES001_finding_the_edge/06_absorption_and_elimination/`. Found an error? Tell us; a
verified one gets a pinned correction.

## Shorts cut-down (≤ 40 s)

"Stop after 2 losses — tested against random skipping." → the four-cell table, red bars below zero
→ "The rule lost to random. Its real value is in you, not the market." Full test on the channel.

## Chart pack (from source study)

No rendered chart images exist in `06_absorption_and_elimination/out/` (only `results.json` and
`spy_ohlcv.csv`) — everything below needs to be drawn.

| Figure | Use | Restyle notes (AMI hex, 16:9, dark) — source numbers |
|:--|:--|:--|
| Loss-streak counter animation (to draw) | Beat 4 | Illustrative mechanism only, no numeric claim — k ∈ {2, 3} per `PREREGISTRATION.md` "H3" |
| Four-cell rule-vs-placebo table (to draw) | Beat 5 | Def h1 k2: −0.017% (−0.045…+0.012); Def h3 k2: −0.078% (−0.148…−0.007); Hold h1 k3: −0.027% (−0.053…−0.003); Hold h5 k3: −0.083% (−0.171…−0.006), from `RESULTS.md` "H3" table |
| Mean-reversion sketch (to draw) | Beat 6 | Illustrative mechanism diagram only — no numeric overlay needed beyond the beat 5 table already shown |

## Compliance checklist

- [ ] No creator / channel / title / clip / thumbnail referenced, on screen or spoken
- [ ] "We tested this claim" language; no *fraud*, *scam*, *liar*
- [ ] Every number traced to `RESULTS.md`, with its window and interval
- [ ] Limits of the test stated on camera, including the behavioural-value distinction
- [ ] No strategy offered in return; ends on method
- [ ] AMI by name; simulation-only; not investment advice
- [ ] EN script flagged for AR / MS translation at v1.0
