<!-- CR109 playability addendum — the "lab" framing and six additions that follow from it.
     Saiful reframed the game as AMI's version of paper trading: the place to try things,
     go wild, and discover from your own results that the wider you go, the less likely
     you are to make money. This addendum records what that framing changes (the game's
     support is measurement, not advice) and the six mechanics that operationalise it:
     intent tags, the wildness index, counterfactual closes, the book heat gauge,
     challenge cards, and a sanctioned wild arena. Additive to CR109.md; §4 lists the
     fold-ins. Design stage; not approved for build. -->

# CR109 — playability addendum: the lab

**Companion to [`CR109.md`](CR109.md), [`psychology_review.md`](psychology_review.md),
[`comparative_review.md`](comparative_review.md) and
[`trade_execution_addendum.md`](trade_execution_addendum.md).** `AT:Fable`, 2026-07-30.

Saiful, setting the frame:

> *"I see the games as our version of 'paper trading'. this is where you try things and go wild,
> and see that the wider you go, the less likely you are to make money"*

---

## 1. What the lab framing changes

The game is not just the exam to the Room's classroom (§2) — it is **the lab**: the sanctioned
place to run experiments with play money and read the results off a scoreboard. Three things
follow, and each resolves an open tension in the design:

1. **The game's job is not to prevent wildness but to make its consequence legible.** The
   support a beginner gets in the arena is not advice — that is the Room's job — it is
   **measurement.** This resolves risk §16.10 (*"the game is the app's unsupported mode"*): the
   mode isn't unsupported, it is differently supported — mirrors instead of guardrails.
2. **It inverts the D-060 worry.** The old objection was that a P&L game *teaches gambling
   psychology*. Under the lab framing the game does the opposite: it **falsifies gambling
   psychology with the player's own data.** "The wider you go, the less likely you make money"
   stops being a lesson in a curriculum and becomes a correlation the player watches emerge from
   their own run history — and personal data is the only evidence nobody argues with. Worth a
   sentence in the §15 compliance narrative: the P&L game is an instrument for *demonstrating*
   why wild trading loses, in play money, with no prize.
3. **The fee (trade addendum §2) is the lab's price signal, not a punishment.** Go wild — the
   cost meter runs. The experiment is honest because the market frictions are.

---

## 2. The six additions

Ranked by playability-per-cost. `L` for lab.

### L1 · Run intent tag — sanction the wildness · **XS**

At entry, one tap: **Going wild · Testing a thesis · Playing it disciplined.** The Close scores
the run against the player's own declared intent: *"You said wild. −7.2%. Your disciplined runs
average +0.4%."*

Naming "wild" as a sanctioned mode removes the shame that suppresses experimentation — more
experiments, more runs, more retention — while the intent-vs-outcome comparison does the
teaching. One enum on `game_entries`, surfaced at the Close and on the Record.

### L2 · The wildness index — measure behaviour, not just intent · **S**

A per-run **width score computed from data already stored**: concentration (max position %,
effective position count), turnover, book volatility. The Record then shows *returns by style*:

> *"Wild runs: 1 of 7 positive. Disciplined runs: 5 of 8 positive."*

This is Saiful's sentence turned into the player's own dataset. Two bonuses: the tag (L1) vs the
measured index is a coaching moment no comparator has — *"you said disciplined, you traded
wild"* — and the index is exactly the per-period compliance-adjacent record risk §16.2 wanted
kept for a future "Clean Run" mark, computed on the game side without touching the mandate.

### L3 · The counterfactual Close — the mirror · **S**

Two lines at every close, computable from the trade log and price series already stored:

- *"If you'd held your first picks untouched: +2.1%. You made −0.8% trading around them."*
- *"If you'd just held the S&P: +0.6%."* (the benchmark series already exists — §6.6)

The buy-and-hold counterfactual is the single most instructive stat an overtrader can see, and
the second line is the index-fund lesson delivered at the moment of maximum attention. Pairs
directly with the agent post-mortem (comparative C5): the agent narrates the gap. Slice 3 — it
belongs to the scoring pass, which already walks the same data.

### L4 · The book heat gauge — the mirror, live · **XS–S**

On the my-run screen, a hex-styled heat strip computed from the current book: *"82% in 2 names ·
high heat."* Not a rule, not a warning, no gate — **a mirror held up mid-run**, at the moment
width is being decided. Informational only, CR040-clean, and it makes L2's index visible before
the close instead of only after.

### L5 · Challenge cards — rules as chosen tools · **S**

Opt-in, self-imposed constraints offered at entry: *"This run: max 3 positions" · "every
position gets a stop" · "no trades after day 1."* Completion is a computable predicate over the
trade log; completing one earns a **progress marker** (§8.4) — never career points, which would
make constraints farmable.

This is the deepest fit with the lab framing: **the curriculum's discipline rules become
testable hypotheses.** The player doesn't obey the mandate — they *choose* a piece of it as an
experiment and discover from their own results that it helps. The no-rules arena (§7) is
untouched: nothing is imposed; constraints exist only because the player picked one up. That is
the product's whole thesis expressed as a mechanic.

### L6 · Give wildness its own arena — and keep the symmetry · **config only**

Survival runs (roadmap #10) are *discipline as a game*. The mirror image: a **high-volatility
theme run** — the universe is the market's wildest names, and everyone who enters has opted into
the same storm. The wild itch gets a home that doesn't distort the main boards, and the field
comparison stays fair because the whole field is wild. One config row on theme runs (roadmap
#6), plus the standing note from the comparative review: **risk-adjusted runs (#9) ship early**
as the board where width is priced into the score itself.

---

## 3. Guardrails

- **Never reward wildness itself.** No "wildest run" badge, no marker for going wide — wild runs
  are sanctioned, but only the *learning* is celebrated (finishes, personal bests, completed
  challenges, intent-vs-outcome insight). A farmable wild identity would invert the lesson.
- **Mirrors are private.** Intent tags, the wildness index, counterfactuals and heat never
  render on a board or another player's view — they are layer-1/Record-personal. Billboarding
  them would turn self-knowledge into performance.
- **Challenge markers are markers, not points.** The career ledger never pays for a constraint,
  or constraints become the farm §8.4 was written to avoid.
- **The counterfactual never scolds.** *"You made −0.8% trading around them"* is a number, not a
  judgment — the Wind-Up's dignity rule (§10) applies to every mirror in this addendum.

---

## 4. What changes where

**Fold into CR109.md at its next revision (listed, not applied):**

- §1 Why / §15 narrative: one paragraph on the lab framing and the D-060 inversion (§1 above).
- §8.4 progress markers: gains challenge completions and intent-vs-outcome insights.
- §10 the Close: gains the two counterfactual lines; the Wind-Up dignity rule extended to all
  mirrors (§3).
- §13.2 backend: wildness index + counterfactual computation in the scoring pass; intent enum on
  `game_entries`; challenge predicates.
- §13.3 mobile: intent tap on entry, heat strip on my-run, counterfactual block on the Close,
  returns-by-style on the Record.
- §16.10: re-worded per §1 — the game is differently supported, not unsupported.
- Roadmap: #6 gains the high-vol theme row; #9's ship-early note reconfirmed.

**Slices:** L1 + L4 ride slice 2–3 (entry + my-run surfaces); L3 + L2 ride slice 3 (the scoring
pass and the Record); L5 lands with slice 3–4 (needs markers live); L6 is roadmap config.

**Not minted here:** no new CR — part of the CR109 design package, sixth companion.
