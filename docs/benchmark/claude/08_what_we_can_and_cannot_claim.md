# 08 — What we can and cannot claim

Saiful's scope for this study included **investor/GTM material** and **in-app
teaching content**. Both put these numbers in front of people who will act on them,
so the line has to be drawn explicitly rather than left to judgement in the moment.

The governing constraint is not my caution. It is the project's own locked
decision: **AMI is a training simulator, simulation-only, forever; not licensed to
give investment advice; no brokerage integration ever** (`CLAUDE.md`,
`docs/initial_specs/11_decisions/decision_log.md`).

---

## The three tiers

### 🟢 Safe externally — measured, cited, about the past

Say these with the number, the n, and the window attached.

- The **human baselines** in `01`–`05`. They are third-party published facts about
  other people, not claims about us. "84% of active large-cap funds trailed the S&P
  500 over ten years" is S&P's finding, cited to S&P.
- The **architecture** claim, because it is structural and verifiable by reading the
  code: the Room runs opposed bull/bear researchers, three risk debators with
  conflicting mandates, and a structurally separate PM with a deterministic
  compliance check.
- **Measured process metrics**, with their n: "across 18 convenes, zero produced a
  unanimous verdict" (CR143). This is the strongest honest thing we can currently
  say, and it is strong.
- The **method** claim: that we score the Room against published human baselines and
  publish the sample size. Most of this category's competitors do not.

### 🟡 Teaching-only — true, but needs a classroom around it

Fine inside a lesson where the framing travels with the number. Not fine on a
landing page, an app-store screenshot, or an investor slide, where it will be
quoted without its qualifier.

- **"Your Room scored 78 on the same rubric the CFA Institute uses."** Excellent
  pedagogy (`04`), but note honestly that we have adapted the rubric and the CFA
  Institute publishes **no score distribution**, so "78" has no external
  percentile. The lesson must say so.
- **Comparisons to investment clubs.** "A team of amateurs did worse than a lone
  amateur — here is why structure matters" is one of the best teaching beats in the
  whole literature (`03`). It is also, stripped of context, a sentence that says
  teams lose money.
- **Any Room hit rate, ever, at current sample sizes.** Inside a lesson about
  sample size and confidence intervals, a noisy number is the *point*. Anywhere
  else it is a performance claim in disguise.
- **The 38% / 64% sell-side target benchmark.** Great teaching material about how
  little a price target means. Becomes an implied promise the moment it sits next
  to a Room figure without its interval.

### 🔴 Never — regardless of what the data says

- **Any forward-looking performance claim.** "The Room beats X% of analysts" said
  in the present or future tense. Past-tense, sample-bounded, window-bounded, or
  not at all.
- **Any implication of advice.** The Room issues a *verdict in a simulator*. Not a
  recommendation, not a signal, not a suggested trade.
- **Room performance next to fund performance as if commensurable.** `00` §4: the
  Room has no portfolio and no fees; SPIVA measures portfolios net of fees with
  survivorship correction. Putting a Room number beside "84% of funds underperform"
  invites a comparison neither number supports.
- **Any hit rate without its n and CI**, per the `07` gate.
- **A best-window highlight.** `01`: professional underperformance ranged 45%–87%
  across 24 years. Picking the good window proves nothing and is the easiest
  criticism to level at us.
- **Pooled target-hit rates** that mix `ami_default` minted levels with real
  forecasts (`06` M3a). That number would be partly measuring how often a stock
  rises 13%.

---

## Why the red line is drawn here

Three independent reasons, any one of which would be sufficient:

1. **Licensing.** We are not registered to give investment advice anywhere. A
   performance claim attached to a stock verdict is the substance of advice
   regardless of the disclaimer under it. The simulation-only decision is what
   keeps AMI outside that perimeter, and a performance claim walks it back in.
2. **App-store review.** Finance-category review is unforgiving about performance
   representations. This is a shipping risk, not a theoretical one.
3. **It would be false.** This is the reason that should carry the most weight.
   Per `00` §7, we cannot yet distinguish the Room from the base rate at any sample
   size we possess. A returns claim today would not be aggressive marketing of a
   true thing — it would be a statement we know we cannot support.

---

## The claim we should actually make

The evidence supports a specific, defensible, differentiated pitch. It is not
"better returns." It is:

> **Retail investors don't lose money because they pick badly. They lose it because
> they trade too much, on impulse, alone** — Barber & Odean measured the penalty at
> 1.5 points a year on average and 6.5 for the most active.
>
> **Adding people doesn't fix it.** Investment clubs did worse than lone
> individuals — 14.1% against 16.4% — because unstructured groups converge instead
> of arguing.
>
> **What fixes it is structure.** Teams running dialectical inquiry and devil's
> advocacy make measurably better decisions than consensus teams — and hate doing
> it, which is why voluntary human groups don't sustain it.
>
> **The Room runs that protocol and cannot get tired of it.** Across 18 sessions,
> zero produced a unanimous verdict.

Every clause is sourced. None is a performance claim. None requires a sample size
we don't have. And it is a genuinely differentiated position — the competitor set
is mostly selling signal quality, which is the thing nobody in this literature has
ever reliably delivered.

**The strongest available marketing asset is not a return number. It is the
honesty.** The `06` bands, published with their empty Room columns and their
"n required" gates, say something almost nobody else in this category is willing
to say: *here is exactly what would have to be true for us to claim an edge, here
is how many observations it takes, and here is why we are not claiming it yet.*

---

Back to [`README.md`](README.md).
