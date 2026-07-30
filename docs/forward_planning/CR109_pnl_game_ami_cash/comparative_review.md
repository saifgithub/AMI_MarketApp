<!-- CR109 comparative review — the game design benchmarked against the games that already
     won this genre's retention battles: the direct competitors (Investopedia, MarketWatch
     VSE, Wall Street Survivor), fantasy sports, and the mastery/ritual games whose loops
     CR109 is independently re-deriving (Duolingo, Chess.com, Strava, Wordle). Each
     comparator contributes its proven strength; the output is six concrete improvements
     (C1–C6) plus validations of choices already made. Companion to psychology_review.md.
     Design stage; changes nothing by itself. -->

# CR109 — comparative review

**Companion to [`CR109.md`](CR109.md) and [`psychology_review.md`](psychology_review.md).**
`AT:Fable`, 2026-07-30.

Saiful: *"you need to compare it to similar games and gain insight on how to improve it from
their strength."*

Method: each comparator is mined for the **one strength that made it retain players** — not its
feature list — and that strength is mapped onto CR109. Three groups: the direct genre (stock-sim
competitions), the adjacent genre (fantasy sports), and the mastery/ritual games whose loops
CR109's design independently re-derives. Where CR109 already has the mechanic, that is recorded
as validation, not restated as advice. The output is six additions, **C1–C6**, ranked in §5.

---

## 1. The direct genre — stock-market simulators

### Investopedia Stock Simulator · MarketWatch Virtual Stock Exchange · Wall Street Survivor

Two decades of paper-trading competitions, and their retention engine is the same in all three:
**the private league.** A teacher runs a class game; an office runs a bragging-rights pool; a
group of friends runs a season. The public leaderboard is furniture — **the game people stay for
is the one containing people they know.** MarketWatch VSE survives almost entirely on
create-your-own-game; the SIFMA Stock Market Game has put entire classrooms through team
portfolios for decades on the same loop.

**What CR109 is missing:** every competitive surface in the design faces *strangers* — the open
field, auto-matched duels, house desks. Roadmap #12 (invitational) has the machinery — a field
with an eligibility predicate — but frames it as end-game prestige. Nothing in the plan lets a
player say *"join my league"* to a friend, and that sentence is this genre's entire proven
acquisition loop: every private field recruits its own players and then holds them with social
obligation, the cheapest retention there is.

> **C1 — Private fields with a join code.** A field any player can create for a chosen cadence,
> joined by code. Rides the existing field/entry machinery plus one predicate. **Career points
> capped or zero in private fields** — the same collusion rule §11.1 already sets for
> challenge-a-friend (alt accounts are free; a private field must not be a farm). Bragging
> rights are the product; the code is the invite; the invite is the growth loop. Also the wedge
> into classrooms (AR/MS markets later) — the SIFMA model, config not code. Cost: **M**, mostly
> lobby UI. The single biggest gap the comparison found.

**Their weakness, for contrast:** all three are engagement deserts *between* closes — log in,
see a number, leave. CR109's period arc, daily beat and ceremony already out-design them there.
The comparison says: their strength is who you play with, CR109's is what a round feels like.
Take their strength.

### Best Brokers, Invstr, and the fantasy-finance long tail

Mobile paper-trading with social feeds bolted on. The instructive part is the failure mode:
open feeds fill with noise and signal-chasing, exactly what
`rejected_features_register.md` and §11.3's phased gating predict. **Validation, not advice** —
CR109's structured-reactions-first posture is right, and the comparison found no successful
counter-example of an unmoderated finance feed.

### StockBattle-style real-money micro-contests

Entry-fee, 15-minute, real-prize stock battles. Listed only for the register: this is the
genre's gambling edge, and every mechanic that makes it *feel* exciting — entry stakes, minutes-
long resolution, cash out — is one CR109 has structurally refused (§4.2, §8.1, one-beat-per-
close). **Anti-model.** Their churn is as fast as their thrill; a training brand cannot visit.

---

## 2. The adjacent genre — fantasy sports

### Season-long fantasy (ESPN / Yahoo leagues)

The stickiest game format ever shipped at consumer scale: people stay in one league with the
same ten humans for a decade. The strength is **C1 again** — the league of known rivals — plus
one ritual CR109 already holds: **the draft is the best day of fantasy.** A synchronous, social,
high-anticipation start line. CR109's bell + field-reveal (§10) is the same beat; drafted runs
(roadmap #7) are the format's direct translation and the most shareable mode on the roadmap
(a lineup is a screenshot). **Validation** — and a nudge that when #7 ships, its entry moment
deserves the full ceremony treatment, because the comparator says the *start* can carry as much
emotion as the close.

### Daily fantasy (DraftKings / FanDuel)

Strength: **there is always a contest starting** — no dead time between wanting to play and
playing. CR109 adopted exactly this with rolling daily fields after the playability review found
the dead start. **Validation.** Their contest-lobby variety (many formats, sizes, stakes) maps
to the games roadmap's mode list. Their anti-model half — real-money consideration and prize —
is already fenced by §15.

---

## 3. The mastery and ritual games — the loops CR109 is re-deriving

### Duolingo — the streak with mercy, and the human-scale league

Two strengths, both transferable:

1. **The streak freeze.** Duolingo learned that the streak's power cuts both ways: the longer
   it grows, the more its *loss* becomes a churn cliff — miss one day after 200 and the
   rational response is to quit entirely. The freeze (an earned/granted skip) keeps the
   commitment device without the cliff. CR109's re-homed streak (runs finished / periods
   entered, playability §3) has the same cliff waiting: one skipped week ends a six-month
   chain.

   > **C2 — A bye week for the game streak.** One earned skip per quarter (framed in-world: a
   > desk goes on leave; the book is flat). The streak survives one missed period; two ends it.
   > Cost: **XS** — a counter on the streak query.

2. **Leagues of thirty.** Duolingo's weekly league is deliberately ~30 names — small enough to
   *traverse*: you can see the person above you and catch them. Rank 2,317 of 5,000 is
   noise; rank 4th of 28 is a goal (goal-gradient needs a visible gradient). CR109's round 1
   had cohorts of ≤30 and Amendment B removed them *for the right reason at the wrong layer* —
   the problem was scoring process, not cohort size. When open fields grow past ~50, bracketed
   fields (roadmap #5) stop being a nice-to-have.

   > **C3 — Commit to human-scale boards as the growth trigger.** Not a build item now; a
   > recorded trigger: when a cadence's median field exceeds ~50, roadmap #5 promotes from
   > "later" to "next." The board must always be a ladder someone can climb, never a wall of
   > names. Cost: **zero today** — a line in the roadmap's ordering rationale.

### Chess.com / Lichess — the rating, and the post-game review

Two strengths, both aimed at CR109's thin spots:

1. **Rating as identity.** Chess separates the number that measures *skill* (Elo — can fall,
   converges, means the same thing for everyone) from grind currencies and permanent titles.
   CR109's career points confound the two: they accumulate with volume, so a mediocre
   high-volume player out-points a skilled occasional one, and the Record never answers the
   question the product exists to teach — *am I getting better?*

   > **C4 — A rolling skill stat on the Record.** Trailing-N-runs average alpha (or Sharpe, per
   > roadmap #9's machinery — `sharpe_ratio` already ships). Visible on the Record beside
   > career points; **never gates anything** (layer 3, one-way rule intact). It can fall, which
   > is precisely what makes it credible — a number volume cannot farm, for the veteran to
   > defend and the improver to watch rise. Numbers > adjectives is the brand; this is the
   > brand's own stat. Also the natural pairing key F9 wants. Cost: **S** — a windowed query
   > over data slice 3 already stores.

2. **The post-game review.** Chess.com's Game Review converts every loss into a lesson — the
   single feature most credited with making losing *retentive* instead of churning. CR109 owns
   a stronger version of this asset than any comparator ever had: **twelve named analysts the
   user already has a relationship with** — and the game deliberately excludes them during play
   (§2, correct). Post-close is a different matter: §11.3 already sketches "the 12 agents
   comment on a closed field" and leaves it unscheduled.

   > **C5 — Pull the agent post-mortem into the close path.** One agent (rotating, or matched
   > to the run's story — Risk on a blowup, Momentum on a hot streak) delivers a three-line
   > retrospective read on the Close/Wind-Up: what worked, what didn't, one thing to try.
   > Retrospective and educational only — never forward-looking (the §11.3 fence). This is the
   > product's moat in one feature: no competitor has characters that debrief your round. It is
   > also what makes the Wind-Up land — a loss with a coach beats a loss with a stat block.
   > Cost: **S–M** (one LLM call per close against data already assembled; the CR038 caveat
   > applies — structure the retrospective-only constraint, don't prompt it).

### Strava — the segment, and kudos

Strength: **you compete against yourself when nobody else is around.** Segments and PRs make an
empty field irrelevant — a personal best is always available, permanent, and unfarmable. CR109's
progress markers (§8.4) fire *transiently* at close; nothing displays them as a standing surface.

> **C6 — The PR board on the Record.** Best weekly TWR, best alpha, best drawdown control,
> longest hold, longest streak — personal records, permanently displayed, each stamped with the
> run that set it. Thin-field-proof by construction (needs zero other players — exactly the
> alpha condition), and it gives every close a second way to matter: *not a win, but your best
> April.* Extends §8.4 from moment to monument. Cost: **XS–S** — a max-query over
> `portfolio_nav_daily` + a Record section.

Kudos — one-tap, fixed-vocabulary acknowledgement with no reply thread — is the exact shape of
§11.3 Phase A reactions. **Validation** from the comparator that proved low-bandwidth social is
enough: being seen retains; conversation is optional.

### Wordle — the same puzzle, and the spoiler-free boast

Everyone plays the same board on the same day, and the share card is legible to someone who has
never played. CR109's same-field-same-market rule already delivers the first property.
The second is the psychology review's F7/§5 share-card requirement restated by the strongest
possible example: **"Beat the S&P 500 by 3.1%"** is CR109's emoji grid — instantly comparable,
meaningless to nobody. **Validation**, plus one sharpening: the card should carry the *field
context* ("Weekly · field of 24 · 3rd") so it invites comparison, not just admiration.

### Mobile ladder seasons (Clash-style) — the anti-model half

Their seasonal soft reset (everyone drops rungs, regrind monthly) manufactures engagement from
loss-aversion — the decaying-points pattern the psychology review's dark-pattern register
already marks **never**. CR109's threshold titles that don't reset are the right call;
**validation by counter-example.** (Their one good half — season-end reward ceremonies — is
already §10's Annual Awards.)

---

## 4. The comparison matrix

| Mechanic | Proven by | CR109 today | Action |
|---|---|---|---|
| Private leagues / join code | Investopedia, VSE, fantasy sports, SIFMA | **missing** | **C1** |
| Streak with mercy | Duolingo | streak re-homed, no mercy | **C2** |
| Human-scale boards | Duolingo (~30) | open field, unbounded | **C3** (trigger) |
| Skill rating ≠ grind points | Chess.com | career points only | **C4** |
| Post-game review | Chess.com | Wind-Up stats, no coach | **C5** |
| Self-competition (PRs) | Strava | transient markers only | **C6** |
| Rolling contests, no dead start | DFS | ✓ rolling daily fields | validated |
| Draft-day ritual | fantasy sports | ✓ bell + reveal; roadmap #7 | validated |
| Named-rival pressure | racing rivals, chess | ✓ duels + Rivals | validated |
| One-tap acknowledgement | Strava kudos | ✓ Phase A reactions | validated |
| Legible share ritual | Wordle | ✓ share card (arm per F7) | validated |
| No seasonal point decay | Clash (by counter-example) | ✓ threshold titles | validated |
| Real-money micro-battles | StockBattle | structurally refused | anti-model |
| Open finance feed | Invstr et al. | structurally refused | anti-model |

Seven validations, two anti-models confirmed, six additions. The design is *convergent* with the
genre's winners far more than it is divergent — which is the comparison's quiet good news: most
of what these games proved, CR109 independently derived.

---

## 5. C1–C6 ranked, and where they land

| # | Addition | Source strength | Loop it feeds | Cost | When |
|---|---|---|---|---|---|
| C1 | Private fields + join code (points-capped) | the genre's entire acquisition loop | week + season, **and acquisition** | M | Stage 2 — first social build after duels prove out |
| C5 | Agent post-mortem on the Close/Wind-Up | Chess.com review; **CR109's own moat** | week (the close), retention of losers | S–M | Stage 1–2 boundary; needs LLM path only |
| C6 | PR board on the Record | Strava | season; **thin-field-proof** | XS–S | **Stage 1** — it works at n = 1, which is alpha |
| C4 | Rolling skill stat (trailing alpha / Sharpe) | Chess rating | season; veteran identity | S | Stage 2, with the Record maturing |
| C2 | Streak bye week | Duolingo freeze | season (streak) | XS | Stage 1, with the re-homed streak |
| C3 | Human-scale board trigger (~50 → bracket) | Duolingo league | week at scale | 0 now | recorded trigger for roadmap #5 |

C6 and C2 are Stage-1 cheap and thin-field-proof — they strengthen the exact alpha window where
the psychology review found the field machinery inert. C1 is the largest miss but belongs after
the core loop proves itself: a private league of a broken game recruits nobody.

---

## 6. What was deliberately not imported

- **Variable-reward chests / loot mechanics** (mobile ladder genre) — variable-ratio reward on a
  money-adjacent score is the chance leg of §15, invited back in. Register: never.
- **Seasonal rank decay** — manufactured loss-aversion; the Record's value *is* "never resets."
- **Real-money anything** (DFS, StockBattle) — all three gambling legs at once.
- **Copy-trading / follower feeds** (eToro's social half, Invstr) — standing rejection holds;
  retrospective reveal (roadmap #3) remains the licensed-safe substitute.
- **Open chat** — no comparator's moderation economics work at a one-person team, and the
  finance-feed comparators are the cautionary tale, not the aspiration.

The pattern across all five: each imports engagement by importing risk the training brand cannot
carry. The comparators prove the *mechanics* CR109 can take are the identity, ritual and social-
graph ones — and that those are sufficient: the stickiest games on this list (fantasy leagues,
chess, Strava) run on exactly that set and nothing else.
