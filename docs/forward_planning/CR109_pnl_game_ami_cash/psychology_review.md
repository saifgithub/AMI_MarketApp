<!-- CR109 psychology review — a review of the game design through the lens of human
     psychology: what attracts a player, what keeps them, and where the development money
     should go first. Commissioned by Saiful before committing to the build cost. Additive
     to playability_review.md (is it playable) and final_review.md (what collides) — this
     asks whether the retention architecture is complete, and finds two structural gaps
     neither prior review caught. Design stage; changes nothing by itself. -->

# CR109 — psychology review

**Companion to [`CR109.md`](CR109.md).** `AT:Fable`, 2026-07-30.

Saiful: *"It is extensive and before I commit to a HUGE development cost, I need you to review it
with the goal of making it into an addictive game. You need to rely on human psychology to attract
players, and to keep players."*

Position against the two prior reviews: [`playability_review.md`](playability_review.md) asked *is
it playable* and fixed the dead start, the deleted streak and the flat first close;
[`final_review.md`](final_review.md) asked *what collides* and fenced ads, reminders and social.
Both hold. This review asks a third question — **is the retention architecture complete** — and the
answer is *almost*: the design's psychological foundations are unusually strong, but it has **two
structural gaps that no amount of ceremony will paper over**, and both are cheap to fix now and
expensive to fix after launch.

The output is not a critique — it is **ten concrete changes (§7) that improve the playability of
the game in line with the goal**: each one strengthens a specific loop (day, week or season, §5)
through a specific psychological mechanism, and all but two are XS/S.

---

## Verdict

| Question | Answer |
|---|---|
| **Will it attract players?** | The fantasy is legible — *beat the market, prove you're good* — but the MVP has almost no acquisition loop. One surface (the share card) carries all of it; §5 says how to arm it. |
| **Will it keep players?** | **The top quartile, yes — powerfully. The median player, no.** Placement scoring means roughly half the player base earns ≈ 0 career points per run forever; their Record flatlines at zero and the title ladder never starts (F1). Fix that and the loop is genuinely strong. |
| **Is the psychology sound?** | Yes — unusually so. The three-layer model, the peak-end ceremony, the loss-dignifying Wind-Up, the reminder rule and the refusal of rewarded ads are all *retention-positive*, not just compliance-positive (§4). |
| **Should Saiful commit the money?** | **Not all of it at once.** The addictive core is slices 1–3b plus the fixes below — roughly a third of the plan. The expensive machinery (placement, titles, five cadences, cosmetics) serves scale that doesn't exist yet, and psychology says it can wait for evidence (§6). |

---

## 1. What the design already gets right — the mechanism inventory

Named so nobody accidentally "improves" one of these away. Each maps a design choice to the
mechanism it exploits, deliberately or not.

| Design element | Psychological mechanism | Why it works |
|---|---|---|
| Fresh 10,000 per entry (§4) | **Fresh-start effect** | Failure never contaminates the next attempt; every run is a clean narrative unit. This is the single best retention decision in the design. |
| The Record, floored at zero (§6.5) | **Endowment + loss-aversion damping** | Losses hurt ~2× gains; the floor caps the spiral that churns losers. |
| +100 / −40 convex curve (§6.2) | **Asymmetric reinforcement** | Winning feels enormous, losing survivable — the damping lives in the curve, not in apology copy. |
| Settlement freeze, results withheld (§10) | **Anticipation > receipt** | Dopamine peaks *before* reward, not at it. Withholding the result for an hour is the cheapest ceremony in games, and the design knows it. |
| The Close as full-screen sequence (§10) | **Peak-end rule** | A period is remembered by its peak and its end; the design engineers both. |
| The Wind-Up loss ceremony (§10) | **Competence-need protection** | A dignified post-mortem reframes loss as a chapter. Rare in games; exactly right for a training brand. |
| Duels vs a named opponent (§11.1) | **Proximal social comparison** | A rival slightly ahead is the strongest motivator in the building (Festinger). *"VECTOR_11 is 1.1% ahead"* beats any leaderboard. |
| Disclosed strategy desks (§11.2) | **Mastery modelling** | A published rule you can study turns envy into curriculum. |
| One beat per close, never per tick (§10) | **Deliberate arousal ceiling** | Per-tick is a slot machine. Capping the loop protects both the store declaration and the user's trust — and trust is the long-run retention asset. |
| Reminder rule — decisions, not watching (§10.1) | **Channel protection** | Every junk push spends the credibility the Close notification needs. |
| Progress markers for every close (§8.4) | **Endowed progress** | The 25 of 26 who didn't win still see movement. Correctly identified as the bigger retention lever than the champion prize. |
| One live run per cadence (§4.1) | **Attachment focus** | One book per cadence keeps attention undiluted — an anti-farm rule that doubles as an engagement rule. |

The playability review's accepted set (rolling starts, re-homed streak, provisional rank, near-miss
lines, Rivals pulled forward, daily close ritual) is endorsed unchanged and assumed below.

---

## 2. Findings

Ordered by how much they matter, not by where they sit in the spec.

### F1 · The median player's Record flatlines at zero — half the base has no progression

**Defect-grade for retention.** Run the placement curve (§6.2) for the middle of the field:

```text
p = 0.60  →  base = +100 × (0.2)^1.5  ≈  +8.9
p = 0.55  →  base ≈ +3.2
p = 0.50  →  base =  0
p = 0.45  →  base ≈ −4
p = 0.40  →  base ≈ −8
```

A player oscillating between the 40th and 60th percentile — **which is, by definition, most
players, most of the time** — nets roughly zero per run. Their career total sits at 0 (the floor
absorbs the negative excursions), the first title needs 500, and the ladder never starts. The
playability review saw the symptom ("career points move slowly… mean little until titles are in
reach") but not the size: this is not *slow* progression, it is *no* progression for the median
player, indefinitely, by construction. Placement is zero-sum; a progression system bolted to a
zero-sum score excludes half the population every field.

The top quartile doesn't need this fixed — they're fed by the convex top. The fix is for everyone
else, and it must not corrupt the contest (the one-way rule survives either option; career points
are layer 3 and grant no advantage):

- **Option A — a finish stipend (recommended).** A small fixed career-point award for *finishing* a
  run: entered, at least one executed trade, never forfeited, held to the close. Order ~5 per
  weekly finish, scaled by cadence weight — sized so the counter visibly moves at every close but
  titles cannot be farmed by showing up (500 points at +5/run is two years of pure attendance; any
  real progression still runs through placement). It rewards exactly the behaviour the re-homed
  streak already celebrates — *finish what you start* — so it is one ethos, expressed twice. The
  guard conditions (≥1 trade, no forfeit, full hold) keep it from being a check-in in disguise.
- **Option B — milestone-gate the first rung.** Apprentice → Analyst becomes *finish 3 runs without
  a forfeit* rather than 500 points; points gate rung 2 upward. Faster to the first title, but the
  counter still doesn't move per-close for the median player, which is the actual wound.

Recommendation: **A, with B's spirit folded into F5.** Size the stipend with the §18 tuning values.

### F2 · The scoring every early player will actually meet has no formula

§6.6 decides thin fields score benchmark-relative, and §16.4 concedes that **at alpha this is the
default path for months**. The implementation plan ships `alpha_vs_benchmark(run_twr,
benchmark_twr)` — which returns an excess return, not points. **The mapping from alpha to career
points is specified nowhere** in any of the five documents. The placement curve — which will not
run until fields clear `n ≥ 8` — has a formula, a table and a balance check; the path every real
player will experience first has none.

This matters psychologically, not just contractually: the first close is the moment that decides
retention (playability §5), and its number is currently undefined. Requirements for the formula,
so the two bases feel like one game:

- **Same 2.5 : 1 asymmetry** as the placement curve — beating the market must feel like the convex
  top; losing to it must be survivable.
- **Capped at the placement extremes** (±100 base equivalent) so no alpha outcome ever pays more
  than winning a field outright.
- **Positive alpha must pay visibly** — *"you beat the S&P"* is the most legible boast in investing
  and the product's natural first-win framing (see F3).
- A simple honest shape is fine: piecewise-linear in alpha with a slope chosen so a typical good
  week (~+1–2% excess) pays in the same range as a good placement finish. Tune with §18; **decide
  the shape now**, because slice 3's acceptance tests need it.

### F3 · The first run should be a duel against the Index Desk

The playability review fixed *when* a new player can start (rolling fields) and flagged *how
unsupported* they are (§2, needs Saiful's call). Still unsolved is *what the first run is*: at
alpha the open field is thin, the first close reads "1st of 3, scored against the S&P," and the
new player's first act is unbounded stock-picking — the highest-choice-load task in the product
(choice overload is a documented first-session killer).

All three problems have one fix: **the first run is always a duel, auto-matched against the Index
Desk.** *"Your first run: you versus the market. Five trading days. Beat the Index Desk."*

- **Guaranteed opponent** — works at n=1 real players; no thin-field caveat on the first close.
- **Guaranteed narrative** — the first Close always says *you beat the market* or *the market beat
  you*, both of which are stories, unlike a benchmark footnote. It is F2's framing made concrete.
- **The most legible fantasy in investing** — "beat the market" needs no tutorial.
- **Bounded difficulty** — the Index Desk holds the benchmark; it never embarrasses a beginner the
  way a concentrated moonshot on the open board would.
- **Already in the build** — desks are slice 3c, duels are 3b; this is a routing rule, not a
  feature. Cost: XS on top of what's planned.

This composes with, and does not decide, the training-milestone gate (playability §2) — that
remains Saiful's call.

### F4 · The loop-back arrow is the whole game, and it has no spec

§3.3 draws `CLOSE → ENTER` as an arrow. Nothing in any document specifies the surface behind it.
Psychologically the 60 seconds after the Close is the highest-leverage moment in the entire design:
emotion is peaked (win or loss — the Wind-Up ends warm by design), the fresh-start effect is
primed, and the next field is at most a day away. If the player leaves that screen without
re-entering, every hook goes cold until a push notification — which doesn't exist yet — tries to
resurrect them.

- **The final panel of the Close and of the Wind-Up is an entry CTA**: the next field of that
  cadence, its countdown, its current entrant count, one tap to enter. Never a menu, never "back to
  lobby."
- **Instrument `close → re-entry` as the game's primary health metric** from slice 3 day one, with
  `first-run activation` (entered → finished) beside it. These two numbers are the evidence §6's
  funding gates need — decide their targets before the build, not after.

### F5 · The first title is a quarter of a year away — the goal gradient never engages

Thresholds (§6.4): Analyst at 500. A *good* player — consistently 75th percentile — earns ≈ +35
per weekly run, so the first rung lands after ~14 weeks. The median player (see F1) never lands it
at all. Goal-gradient motivation only engages when the goal is visibly approachable; a first rung
three months out for the *good* case is a poster, not a goal.

**Insert a rung at ~100 points** (with F1's stipend, reachable in weeks for an engaged median
player; days for a strong one), or milestone-gate the first rung per F1-B. First-cut thresholds
become ~100 / 500 / 2,500 / 10,000 / 30,000 — six titles, and the existing five names keep their
slots from Analyst up. Naming the new rung is Saiful's; sizing belongs with the §18 tuning set.

### F6 · The daily beat must carry attribution, not just rank

The daily card (playability §4) currently shows movement and standing. Add one line of
**attribution**: *"NVDA drove +1.9% of your +2.3%."* Computable from holdings × price change, no
new data.

The psychology: a no-rules weekly arena is substantially luck (§16.2, accepted), and players who
sense outcomes aren't contingent on their decisions stop playing — learned helplessness is the
quiet churn nobody exit-surveys. Attribution restores perceived contingency (*my pick did this*)
and it teaches, which is the brand. Same reason: surface **Best decision / Worst decision** on the
Close (largest positive and negative contribution), and ship roadmap #9 (risk-adjusted board, XS)
early as the skill-legible counterweight the design already knows it needs.

### F7 · Identity investment is thinner than it needs to be

Hooks close when the user puts something *in* (effort, data, identity) that makes the product more
theirs. At MVP: the handle is assigned, cosmetics are slice 8, notes are phase B, rivals are
post-slice-4. Three cheap moves:

- **Offer the one regeneration at first entry** — "trade as SLATE_07, or reroll once." The handle
  is already regenerable once; letting the player *choose* to keep or reroll converts an assigned
  label into a chosen identity at the moment it starts appearing on boards. Zero new mechanics.
- **Pull Phase A reactions (final_review §3) into the alpha window**, right after duels — a fixed
  vocabulary tap on a closed run is the minimum viable *being seen*, and relatedness is otherwise
  absent until fields populate.
- **Confirm the share card ships with slice 3**, not slice 8 — §10 lists it in the Close beats but
  the slice table only names ceremony at slice 5. It is also the acquisition surface (§5).

### F8 · Near-miss framing must only ever point up

The playability review added near-miss lines ("you were 0.3% off 2nd") — correct, and one rule
must ride with them into §10: **near-miss is used on the positive gradient only, never on losses.**
"You almost avoided the debit" is the slot-machine near-miss — the pattern that measurably
prolongs gambling persistence — and it teaches nothing. Upward near-miss motivates the next
attempt; loss near-miss manufactures arousal from damage. One sentence in the spec keeps a future
copywriter (or model) from crossing it.

### F9 · Matchmaking quality becomes a flow problem at scale — note only

Auto-matched duels at alpha pair whoever queues, which is right. At scale, repeated blowout
mismatches demotivate both sides (flow needs challenge ≈ skill). When the pool allows, pair on
career-point or title proximity; a W–L-informed Elo-lite is a natural later step. Nothing to build
now; recorded so slice 3b's queue design doesn't preclude a pairing key.

---

## 3. Acquisition — what actually brings players in

Mostly outside a game spec, but the game owns one loop and should arm it:

- **The share card is the entire MVP acquisition surface.** Arm it with the legible boast: *"Beat
  the S&P 500 by 3.1% this week"* — benchmark-named, percentage-first. "TWR +2.1%" means nothing
  to a non-user; *beat the market* travels. The duel variant ("Beat VECTOR_11 by 1.4%") travels
  almost as well.
- **Drafted runs (roadmap #7) are the viral mode** — a lineup is a screenshot before the run even
  starts. Worth remembering when sequencing the roadmap; not MVP.
- **Challenge-a-friend is the real invite loop** and stays gated exactly as §11.1 gates it
  (collusion). When it lands, the invite is the growth mechanic — points-free is fine; invites
  don't need points to work.

---

## 4. What NOT to build — the dark-pattern register

The design already refuses the big ones; this table exists so the refusals survive future feature
pressure, and adds two. Every row has a short-term metric lift and a longer-term bill.

| Pattern | Short-term lift | Why it loses | Status |
|---|---|---|---|
| Rewarded video (ad → restart/entry/cash) | ARPDAU | breaks the consideration leg — the whole legal position (§8.1) | refused in spec ✓ |
| Per-tick rank movement | session length | slot-machine arousal; trains the exact behaviour the curriculum warns against | refused in spec ✓ |
| "Your position moved" pushes | DAU | kills the channel the Close depends on (§10.1) | refused in spec ✓ |
| Check-in streaks | DAU | engagement farming; teaches nothing; brand-corrosive | refused in spec ✓ |
| Daily P&L cadence | retention curve | one-day P&L is noise; points would record luck; maximally gambling-shaped | refused in spec ✓ |
| **Loss near-miss framing** | arousal | the gambling-persistence pattern; see F8 | **add to §10** |
| **Decaying / expiring career points** | re-engagement spikes | loss-aversion as a whip; the Record's entire value is *never resets* (§3) — decay would poison the layer that funds long-term retention | **never** |
| **Variable "hot streak" multipliers** | excitement | variable-ratio reward on a money score = the gambling test's chance leg, invited back in | **never** |

**The strategic point:** these refusals are not a compliance tax on engagement — for a *training*
brand they are the retention strategy. Trust is why a user lets AMI teach them for a year. Every
dark pattern spends trust to buy a metric, and this product cannot buy trust back.

---

## 5. The three loops — the retention architecture in one view

The design's mechanics resolve into three nested loops. Every finding above strengthens exactly
one of them; anything that strengthens none of them is decoration.

| Loop | Cycle | Driver | Carried by | Keystone metric |
|---|---|---|---|---|
| **Day** | one US close | open positions (Zeigarnik) + the beat card | daily beat + attribution (F6) | beat-card opens/day |
| **Week** | one run | appointment + anticipation + peak-end | enter → beats → stretch → settle → Close → **re-enter** (F4) | **close → re-entry rate** |
| **Season** | the Record | endowment + status + goal gradient | stipend (F1) + first rung (F5) + titles + duel W–L + streak-of-finishes | % players with a moving counter |

The week loop is the game. The day loop keeps the week loop warm. The season loop is why the week
loop doesn't exhaust itself — it is also the loop both structural gaps (F1, F5) sit in, which is
why they are the two findings that matter most.

---

## 6. Where the money goes — staged commitment with evidence gates

The direct answer to *"before I commit to a HUGE development cost."* The plan's own phasing
(§17) is already thin-sliced; this adds the psychological priority and the gates.

**Stage 1 — the addictive core.** Slices 1, 2, 3, 3b, 3c (desks), plus: F1 stipend, F2 formula,
F3 first-run duel, F4 re-entry CTA + metrics, F6 attribution, F7 (handle, reactions A, share
card), the daily close ritual, provisional rank, near-miss (F8-fenced), Rivals. Ceremony ships in
its slice-3 form (the Close + Wind-Up screens), not the full slice-5 arc. **This is a complete
three-loop game at weekly cadence** — roughly a third of the full plan's surface, and it contains
every hook that matters.

**Gate 1 — before funding slice 4** (placement, titles, multiplier, demand-gated starts): first-run
activation and close→re-entry meet the targets Saiful sets now (targets are his call — set them
before the build so the gate can't be argued backward from the data). If re-entry is weak, no
amount of placement machinery fixes it — the week loop itself needs work.

**Stage 2.** Slice 4 + monthly cadence + full ceremony arc + push (its own CR — the final-stretch
beat is inert without it, §10.1).

**Gate 2 — before funding Q/H/Y + cosmetics + roadmap modes:** fields clearing `n ≥ 8` organically,
and the season loop showing life (title-rung crossings, duel records accruing).

**Stage 3.** Long cadences, slice 8 rewards, roadmap in the §-suggested order (risk-adjusted and
blind runs early — XS each and both skill-legible).

The expensive machinery — placement curve at scale, five concurrent cadences, cosmetics, Desks —
is all Stage 2+, and psychology is unambiguous that it can wait: **status systems only pay once
there is a crowd to hold status in.** The crowd is built by the week loop, which is Stage 1, which
is cheap.

---

## 7. Recommended changes, in priority order

| # | Change | Finding | Cost | Nature |
|---|---|---|---|---|
| 1 | Finish stipend — the median player's counter must move | F1 | S | scoring |
| 2 | Define the alpha→points formula (asymmetric, capped) now | F2 | S (spec: XS) | scoring |
| 3 | First run = auto-duel vs the Index Desk | F3 | XS over 3b/3c | routing |
| 4 | Re-entry CTA on Close + Wind-Up; instrument close→re-entry + activation | F4 | S | surface + metrics |
| 5 | First title rung at ~100 points (or milestone-gated) | F5 | XS | tuning |
| 6 | Attribution line on the daily beat; best/worst decision on the Close | F6 | S | content |
| 7 | Handle keep-or-reroll at first entry; reactions A early; share card in slice 3 | F7 | XS+XS+XS | identity |
| 8 | Near-miss points up only — one sentence into §10 | F8 | XS | spec fence |
| 9 | Duel queue keeps a pairing key for later proximity matching | F9 | XS | schema note |
| 10 | Stage the funding per §6; set gate targets before build | — | — | governance |

Items 1–2 are the structural pair: **1 makes the season loop exist for the median player, 2 makes
the first close a defined experience.** Everything else sharpens loops that already work.

---

## 8. What this review does not reopen

Decided and correct as-is: the training/game split, no arena rules (with the §5.1 market-hours
carve-out), the one-way rule, cosmetic-only rewards, no tokens, the ad invariant, disclosed desks,
auto-matched duels, the reminder rule, no free-text chat, and the deliberate arousal ceiling. The
playability review's eight changes and the final review's fences are endorsed wholesale. The
ceiling on addictiveness is capped by the product's ethics, and the cap is correct — this review's
job was to make sure the design actually reaches its own ceiling, and F1–F4 are the distance
between here and there.
