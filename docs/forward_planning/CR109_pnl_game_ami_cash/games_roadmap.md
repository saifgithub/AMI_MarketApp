<!-- Games roadmap — every game mode beyond CR109's MVP. Saiful, 2026-07-30: "these are
     very interesting new games ideas. Lets put this into a games roadmap. Out all the
     variations as a list and as much details we already have. what we deliver in MVP is
     only open games, meaning all players all at the same time, no duals." Companion to
     CR109.md; nothing here is approved for build. -->

# Games roadmap

**Companion to [`CR109.md`](CR109.md).** CR109 specifies the MVP; this file holds every mode
beyond it. Nothing here is laned. Filed 2026-07-30, `AT:Gamer`.

Saiful, on the C2C mechanics he was shown:

> *"these are very interesting new games ideas. Lets put this into a "games roadmap". Out all
> the variations as a list and as much details we already have. what we deliver in MVP is only
> open games, meaning all players all at the same time, no duals."*

---

## MVP — the Open Run (CR109)

One board per cadence per period. **Every player in the same field, at the same time.** Fresh
10,000 AMI Cash at entry, scored on time-weighted return, no arena rules, no duels, no teams.
One live run per cadence, maximum five books. Weekly ships first.

Everything below is a **variation on that same machinery.** That is the point of the ordering:
the MVP builds runs, fields, entries, a NAV series and a scoring pass, and eleven of the
fourteen modes below are configuration or a small addition over those five things.

---

## Boundaries that apply to every mode

Three constraints are not negotiable per mode — they bound the whole space:

1. **No free-text chat, ever.** A one-person team has no moderation capacity. Structured
   interaction only: fixed-vocabulary reactions, numbers, records, titles.
2. **The copy-trading rejection holds.** `rejected_features_register.md` rejects copy-trading
   and follower feeds on brand grounds. Mode #3 (retrospective reveal) is the resolution, not
   an exception — the reveal happens after a position can no longer be copied.
3. **Nothing of monetary value is awarded on a P&L outcome** until a lawyer clears it. That is
   mode #15, and it gates itself.

Permanently out, not "later": follower feeds, copy-trade buttons, live position broadcast,
prediction markets.

---

## The modes

### 1. Duels — one-versus-one · **PROMOTED OUT OF THIS ROADMAP**

**Now slice 3b in [`implementation_plan.md`](implementation_plan.md); designed in
[`CR109.md`](CR109.md) §11.1.** Saiful: *"I really like the Dual….. how can we bring it back?"*

Kept here only as a pointer, because the reasoning matters for how the rest of this list is
ordered: **a duel needs two players and the open board needs eight.** At alpha every field is below
the placement threshold, so the flagship competitive surface is inert exactly when the product most
needs players to feel something — and the duel is the only competitive format that still works.
That inverts its position: it is not a post-MVP luxury, it is the fix for the thin-field problem.

Two constraints carried into the design: head-to-head scoring must be carved out of the placement
curve (at `n = 2`, `p` is exactly 1.0 or 0.0) and out of the benchmark path (`n = 2` is intended,
not a shortfall); and **MVP duels are auto-matched only**, because anonymous-first onboarding makes
alt accounts nearly free and direct challenge would be a trivial collusion farm.

### 2. Rivals — pin up to three

**Cost: XS.** Pin up to three players from the open field. Their TWR delta versus yours renders
on your home card and inside the daily beats.

The leanest item on this list by a wide margin: no invite, no consent surface, no moderation
surface, no social graph beyond a list of pinned user ids. It is pure numbers, which is dead
on-brand for *analyst-to-analyst, numbers > adjectives*.

Design question when it lands: is pinning visible to the person pinned? Recommendation: no —
one-way and silent, so there is no social pressure and no harassment vector.

### 3. Retrospective reveal

**Cost: S.** Trades stay hidden while a run is open. At close, the trades of ranked players
become visible for that run.

**This is the resolution of the copy-trading rejection rather than an exception to it.** While a
run is live, nothing is visible, so there is no copying and no front-running, and the contest
stays a contest. After close, a position can no longer be copied — so what remains is
education: you find out what first place actually did.

It also answers the question every leaderboard provokes and the MVP has no answer to ("what did
the winner *do*?"), and it doubles as content for the Close ceremony (CR109 §7).

With Rooms out of the game there are no verdicts to reveal — only trades — which makes this
simpler than it looked when first specced against the round-1 design. The data already exists in
`SimTradeRow`.

### 4. Desks — teams of five to eight

**Cost: L.** Players form a Desk. Desk score for a period is the **median** of its members'
placements, and Desks are ranked against each other on their own board.

**Median, not sum, and not mean.** Median resists one carry *and* one blowup, so a Desk cannot
be farmed by recruiting a single whale, and one member's catastrophe does not destroy everyone
else's period. That single choice is most of the design.

This is the strongest retention mechanic on the list — people do not quit on a team — and the
most expensive: it needs net-new social-graph tables (the repo has **zero** today), invite and
membership flows, a leave/kick policy, and a rule for what happens to a Desk's score when a
member forfeits.

**Fixed-vocabulary reactions only, no chat** (boundary #1). A Desk that cannot talk is a weaker
Desk; that is the accepted cost of having no moderator.

### 5. Bracketed fields

**Cost: S.** Split the open field by career title, so a day-one apprentice is ranked against
apprentices rather than against floor veterans.

This is round 1's cohorts-of-≤30 idea, re-homed. It is unnecessary while fields are small — with
a handful of alpha players, splitting them is worse than not splitting them — and becomes
necessary as fields grow. The shipped `league_service._assemble_week()` shuffle-and-chunk is the
pattern to copy when it does.

Interacts with `title_multiplier`: if brackets are title-matched, the multiplier's
harder-cohort justification weakens and it becomes purely a progression reward. Resolve both
together.

### 6. Sector and theme runs

**Cost: S.** A run whose universe is restricted — semiconductors only, energy only, dividend
payers only, small caps only, "the Magnificent Seven".

Cheap recurring content: each new theme is a config row, not a feature. It tests one specific
skill instead of general selection, and it makes for a natural editorial calendar (an earnings
season run, a rate-decision run). Reuses `default_sector_map()`, already shipped and already
used by the sector-concentration cap.

Also the safest way to introduce difficulty variety without touching the scoring curve.

### 7. Drafted runs

**Cost: S.** Pick N names at entry. No trading after the bell. Scored on the basket's TWR at
close.

Pure selection skill with zero monitoring — you enter and you are done until the close. That
makes it the cheapest mode to *operate* (no live trade path at all) and the most shareable (a
lineup is a screenshot). It is the most fantasy-sports-shaped variant on the list, and it is the
one most likely to pull in players who will not watch a live book.

Strong candidate to ship *before* duels despite being less exciting, because it needs no social
schema whatsoever.

### 8. Blind runs

**Cost: XS.** You see your own P&L and your own curve, but not the board, until close.

A trivial config flag over MVP that changes the psychology completely: it removes
leaderboard-chasing tilt and tests conviction instead of reaction. Pedagogically the most
defensible mode on this list — it is closest to how a real mandate-bound manager operates — and
it pairs naturally with the settlement-freeze reveal in the Close ceremony.

### 9. Risk-adjusted runs

**Cost: XS.** Ranked on Sharpe ratio rather than raw TWR.

`sharpe_ratio(returns_pct, ...)` already ships in `backend/app/trading_math/returns.py`, pure
and tested, operating directly on the NAV series the MVP builds. So this is a scoring-function
swap and a label.

It rewards a completely different skill from every other mode here, and it is **the natural
counterweight to the MVP's no-rules arena** (CR109 §5): if the open boards do turn out to be
won by whoever concentrated hardest, this is where skill still shows. Cheap enough that it
should probably ship early for exactly that reason.

### 10. Survival runs

**Cost: M.** A drawdown floor eliminates you. Last players standing are ranked by TWR.

Elimination is inherently dramatic and it is *free ceremony* — the moment a player busts is a
moment. It also creates genuine tension every single day rather than only in the final stretch.

**This is the home for the position and drawdown discipline the MVP deliberately has none of.**
CR109 §5 removed all arena rules by decision; an opt-in survival mode reintroduces risk
management as a *game*, which is a different product from a global rule, and it lets the
curriculum's actual lessons matter competitively somewhere.

Needs: an intraday or daily elimination check, an elimination ceremony, and a rule for whether
an eliminated player's placement is frozen at bust or ranked last.

### 11. Ladder seasons

**Cost: M.** Divisions with promotion and relegation across consecutive runs, rather than a
single career-point threshold.

The shipped `league_service.weekly_roll()` promote/relegate logic is the pattern to copy — worth
reading before it is deleted, even though the league itself is being removed by CR109's
Amendment A. Note the tension with CR109 §4.4: titles were deliberately made *thresholds* so
that rolling starts would not need a synchronized boundary. A ladder season reintroduces that
boundary, so it needs its own synchronized cadence rather than riding the rolling one.

### 12. Invitational runs

**Cost: XS.** Entry restricted — prior winners only, or a title floor, or by invitation.

Pure config over MVP: a field with an eligibility predicate. Its whole value is prestige, which
means it costs almost nothing and pays into exactly the "veterans" half of CR109 §6. A "Champions
Run" of last year's twelve monthly winners is one config row and a name.

### 13. Relay runs

**Cost: M.** A Desk passes one shared book between members, period to period — one member
trades it this week, the next takes it over as-is.

Highly social, genuinely novel, and it produces the strongest version of team accountability:
you inherit someone else's positions and their unrealised losses. Depends entirely on #4, and
needs a handover ceremony plus a rule for open positions at handover.

### 14. Handicapped stake

**Cost: S.** Leaders receive less starting capital in their next run; trailing players receive
more.

Rubber-banding keeps fields competitive and helps new players, but it directly contradicts CR109
§4.1's TWR reasoning: if everyone is scored on percentage return, a smaller stake is not
actually a handicap, so this only bites if scoring changes to absolute terms — which the
invariant forbids. **Flagged as contested and probably incoherent with the current scoring.**
Recorded because it was raised, not because it works.

### 15. Credits payout

**Cost: gated, not sized.** Awarding credits — the purchasable currency, packs at $4.99–$49.99
— on the outcome of a P&L contest.

**This is the step that needs the lawyer**, and it is the only item on this list where that is
true. CR109 §11 sets out why: no entry fee removes *consideration* and no prize of value removes
*prize*, which is what keeps today's design on the skill-versus-chance footing that
`competition_rules.md` §8 already claims. Adding a prize of monetary value removes that
protection.

Saiful: *"this may change, but likely credit will come into play at some point, but for now just
points."* So the schema should carry a payout hook from day one while paying only points.

---

## Suggested order

Not a commitment — a default, ordered by cost-to-value rather than by excitement:

| Order | Mode | Why here |
|---|---|---|
| 1 | **#9 Risk-adjusted** | XS, and it is the insurance policy against the no-rules arena being pure luck |
| 2 | **#2 Rivals** | XS, no social schema, immediate emotional payoff |
| 3 | **#8 Blind** | XS config flag, best pedagogy on the list |
| 4 | **#3 Retrospective reveal** | S, answers "what did the winner do", feeds the ceremony |
| 5 | **#6 Sector/theme** | S, turns content into a calendar |
| 6 | **#7 Drafted** | S, no live book, widest audience |
| 7 | **#1 Duels** | S, the Sunday-night hook — first item needing an invite flow |
| 8 | **#12 Invitational** | XS but needs a season of history to draw on first |
| 9 | **#10 Survival** | M, where risk discipline finally counts |
| 10 | **#5 Bracketed** | S, but only once fields are big enough to need it |
| 11 | **#4 Desks** | L, the retention payoff, first item needing social-graph tables |
| 12 | **#11 Ladder seasons** | M, and it fights §4.4's threshold design — resolve that first |
| 13 | **#13 Relay** | M, depends on #4 |
| 14 | **#14 Handicapped stake** | contested; may be incoherent with TWR scoring |
| 15 | **#15 Credits** | lawyer-gated |

**Prerequisite that sits outside this list:** push notifications. CR109 §7 records that they do
not exist — the only trace in the repo is `note="TODO B1: fire APNs push notification here"` at
`api/room.py:134`. Several modes here (duels especially — an opponent's move is meaningless if
you don't hear about it) are substantially weaker until push lands.
