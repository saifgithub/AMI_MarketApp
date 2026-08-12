# 09 — The Floor header, revised in review (addendum)

Added 2026-08-12, from Saiful's live review of `04`/`08`. His brief, condensed: concentrate
on the Floor; **the Room is the hero, the Daily Challenge the second hero**; the header
should answer the questions on the user's mind immediately — value of holdings, how the last
Room calls are doing, maybe sector news — **as a carousel with a nice big display**; the
Weekly League may be unnecessary "since we will have the full game"; and *"I am not sure if
the carousel will make the page feel cluttered. This is where you do the research."* Second
round: two inputs (ticker + ask AMI) read as still cluttered → merged into one omnibox
(§9.3).

Mockup: frame **A′** in `prototype/concepts.html` (revision of concept A, same DOM-read stat
strip). Persona renames from the same review, applied to `08`: **P1 — The Curious User**,
**P4 — The Learner**.

## 9.1 The league question is already answered — by Saiful, in CR109

No new decision is needed: **CR109 ("The Game: a P&L competition in AMI Cash") deletes the
league.** Amendment A records Saiful's own instruction — *"remove the current (boring!)
reputation game"* — and CR109's removal scope explicitly stops rendering
`league_screen.dart`, `league_card.dart` (the Floor's league card) and `_LeagueSection`,
stops the weekly roll, and stops the six reputation `.award()` call sites
(`docs/forward_planning/CR109_pnl_game_ami_cash/CR109.md`, Amendment A + §removal scope).
CR109 is approved for build (Amendment F, 2026-08-09), slices 1–3 shipped dark behind
`kGamesEnabled`. Frame A′ therefore mocks the Floor **without** the league card — that is
CR109's Floor, not a new proposal.

Two notes the registers should not lose:

- **The empirical support nobody cited:** no league-usage number has ever been measured —
  `league_members` appears in no research query — while the challenge that feeds its scoring
  has 4 users of 172 (`08_personas.md` §8.1, PROVEN in `VERIFICATION.md`). The surface CR109
  removes was never observed being used.
- **A governance loose end:** the decision log still carries **D-060** ("competition is
  reputation-based weekly leagues") with no entry recording CR109's reversal. When CR109
  un-darks, D-060 needs an amending entry. Same moment: the streak chip and the challenge
  card's "keep your streak" copy — CR109 re-homes streaks onto game runs and stops rendering
  `streak_chip.dart`, so A′ keeps them only as today's shipped state, to be re-copied when
  the game lands.

## 9.2 Carousel vs clutter — what the evidence actually says

The anti-carousel canon is real, and it convicts a specific thing: **auto-rotating
promotional banners**. Verified against live fetches (2026-08-12; full list in
`sources.md`):

- Erik Runyon's Notre Dame data (2013), the field's most-cited numbers: **1.07%** of 3.76M
  homepage visits interacted with the carousel at all, and **89.1%** of those clicks were on
  slide 1. Across his five measured sites, slide 1 took 55–89% of all clicks.
- NN/g (Pernice, 2013, reviewed 2026): users *"often immediately scroll past these large
  images and miss all of the content within them, or at least the content that's in any
  frame other than the first."*
- Baymard (Scott, 2019, updated 2025): *"Most users won't see all the slides in a homepage
  carousel, even if it autorotates"*; their better-performing alternative is *"static
  content sections."* 46% of sites with a homepage carousel have implementation issues.

**Why the header carousel is not that thing.** Those studies measure promo banners whose
value requires the user to *click through the deck*. An answer-card header delivers its
value by being **read, not clicked** — card 1 answers "what am I worth?" at a glance, which
is the header's whole job. The carousel here is progressive disclosure turned horizontal:
one card's cognitive load at rest, more answers on request — the same "verdict first, people
on request" rule the rest of the research runs on. The failure mode the evidence warns
about (content beyond slide 1 is invisible) becomes a design *constraint*, not a
disqualifier.

**The five rules the evidence imposes** (violate any and the canon applies in full):

1. **Never auto-rotate.** NN/g: *"Do not auto-forward on mobile devices"*; Baymard:
   *"carousel autorotation should be avoided on mobile sites."* The carousel moves only
   under the thumb.
2. **Order = priority, and nothing load-bearing beyond card 1.** Runyon's 89% is the
   planning number: assume most users only ever read card 1. Portfolio value is card 1.
   Cards 2–3 are earned depth, never the only home of something critical.
3. **Always show a peek.** Friedman (Smashing, 2022): *"Always indicate a slice of the
   upcoming slide"*; NN/g calls it "bleeding". A′ shows ~30px of the next card.
4. **Five cards maximum.** NN/g: *"Include 5 or fewer frames within the carousel, as it's
   unlikely users will engage with more than that."* A′ ships 3.
5. **Swipe + visible dots inside the surface.** Baymard: mobile users *"have come to
   expect"* the swipe gesture; NN/g wants controls inside the carousel, not below a fold.

One source could not be verified: Material 3's carousel guidance (m3.material.io renders
client-side; the fetch returned only the page title) — recorded in `sources.md`, not cited.

## 9.3 Measured: A′ does not re-clutter the surface

Same method as `04` (390×720 frame, fold 632px, DOM-read):

| Frame | Identity marks | Tap targets | CTA | Column |
|---|---|---|---|---|
| 0 — shipped Floor | 13 (10 above fold) | 23 | 1.63 folds | 1178px |
| A — as parked | 1 | 13 | 0.43 folds | 717px |
| **A′ — carousel header + omnibox** | **1** | **12** | **0.47 folds** | **632px** |

The carousel costs 25px of CTA height against A (0.43 → 0.47 folds — still screen one), and
the column lands at **exactly one fold (632px)**: the entire Floor fits one screen with zero
scroll, which neither the baseline (1178px) nor parked A (717px) achieved. The at-rest
surface is: one answer card (+ peek), one omnibox, CONVENE, the challenge, the firm row.
**Honesty note:** the DOM counter checks vertical position only, so the two off-canvas
carousel cards count among the 12 taps; visually at rest the user faces 10 targets and *one*
card. Clutter verdict: A′ is A with a better-informed header, not a regression toward the
baseline.

**One input, two intents (review round 2).** The first A′ draft had two fields — a ticker
input and an "Ask AMI" pill — and Saiful read it as still cluttered. Original concept A had
only ever had one input: the ask pill inside the Concierge card, with CONVENE as a chip.
A′ keeps that one-input rule but gives it both jobs: a single omnibox where text that parses
as a ticker arms CONVENE THE ROOM and anything else opens the AMI chat. The routing is
**deterministic and client-side** (symbol-shape match against the instrument list) — not an
LLM classification, per the house rule that prompt instructions are not controls (CR038) —
so it costs nothing and cannot misroute a mandate-relevant action. The pink CNC mark lives
inside the field, which keeps the Concierge as the surface's one identity and the field
honest about who answers.

Day-0 state (the P1 majority): card 1 is never empty — the sim stake reads *"$100,000 ready
to deploy"* — and cards 2–3 collapse until they have data, with their empty states pointing
at the hero ("No verdicts yet — convene on your first ticker").

## 9.4 The card set

| Card | Answers | Source | Cost |
|---|---|---|---|
| 1 · SIM PORTFOLIO | "What am I worth?" — holdings + cash + positions | client state | zero |
| 2 · YOUR TEAM'S CALLS | "Were they right?" — last verdicts, delta since | client state | zero |
| 3 · SECTOR WATCH | "What's moving where I look?" | needs a feed | the only card with a dependency — cheap version is yfinance headlines for touched tickers; richer is phase 2 (News-analyst live-feed gap is a known open item) |

Card 2 is quietly a light Decision Journal: verdict accountability is P2's defining need and
the daily reason-to-return the shipped Floor never had; it also starts the P2→P3 bridge.
Later candidates, in strength order: continue-lesson (17% go lessons-first), watchlist
movers ("AMD +4.2% — convene?"), and post-CR109 the game's daily beat — the natural
replacement for what the league card pretended to do. Cap remains 5 (rule 4).

Persona fit (re-run of `08` §8.3 for the header): P1 gets one card + one obvious hero;
P2 gets card 2 and the CTA on screen one; P3 loses nothing (depth = firm row, one tap);
P4 gets one card grammar to translate instead of a roster.

## 9.5 What this review settles and what stays open

- **Settled here:** header = answer-card carousel under the five rules; heroes = CONVENE
  (with ticker-in + ask AMI) then Daily Challenge; league card never returns (CR109);
  status content is client-composed — which resolves open decision **#5** in
  `07_open_decisions.md` in the direction already recommended.
- **Still open, still gating a build:** #2 (voice of the ask affordance / card set —
  Concierge recommended) and #4 (CR159 re-scope to the firm-row depth screen). #1 (tab-0
  name) and #3 (E's default) unchanged.
- **Unchanged by this revision:** concept E (the Room's live phase) and the step-0 funnel
  instrumentation from `08` §8.4 — the interview leak is upstream of any header.
