# CR132 — a Day Trader lesson track, grounded in the behavioural-finance research

**Filed:** 2026-07-30 (AT:R65) · **Origin:** Saiful: *"I need the education material to have the
research you just did. I want to create a set of lessons specifically for 'day trader'."*
**Status: scaffold** — the shape is specified here; the lessons themselves are the build.

## Why this exists

CR129 grounded the risk-limit presets in published research, and CR129 adds a **Day Trader** preset
that removes the guardrails on request. Two consequences follow:

1. **The research is currently trapped in a CR document.** Barber & Odean's turnover finding and the
   Taiwan survival curve are the strongest evidence this product has for its own core claim, and
   right now they exist only in `docs/forward_planning/` where no user will ever see them. Lesson
   **365** carries a summary; that is one lesson doing the work of a track.
2. **A user who takes the Day Trader preset is self-identifying as the exact cohort the research is
   about.** That is the moment to teach, and we currently have nothing addressed to them.

The existing curriculum teaches day-trading concepts (047 revenge trading, 051 discipline, 012 why
most traders fail) but **addresses a swing/position trader throughout**. Nothing speaks to someone
who has decided to trade intraday and wants to do it well.

## Editorial stance — decide this before writing a word

**Not abstinence.** Saiful: *"if we do not let them fail in a safe environment, they will fail with
real money."* A track that argues "don't day trade" will be dismissed by its own audience in the
first lesson and will have taught nothing. The evidence is not "never do this" — it is "this is
brutally hard, <1% sustain it, here is what separates them, and here is how to find out which group
you are in **while it is free**."

The honest frame: **this app is the cheapest possible place to discover you are not in the 1%.**
That is a genuinely useful service and it does not require pretending the odds are better than they
are.

## Proposed lessons (scaffold — titles and thesis, not final copy)

| # | Working title | Thesis | Core evidence |
|---|---|---|---|
| 1 | What the data actually says about day trading | The numbers, without editorial | Taiwan: <1% reliably profitable, >80% lose per half-year, survival 44/24/15% at 1/2/3yr |
| 2 | Why activity costs you, before costs | Most-active 11.4% vs least-active 18.5% — and both picked stocks about equally well | Barber & Odean 2000, 66,465 households |
| 3 | Overconfidence is the mechanism | Why a winning streak *causes* the next mistake; the disposition effect | Barber & Odean's own explanation for excess trading |
| 4 | The tilt spiral, measured | Cortisol, narrowed attention, the trade after a loss; extends lesson 047 to intraday | Existing 047 + the loss-response literature |
| 5 | What the surviving 1% do differently | Process, pre-commitment, records — the falsifiable habits, not mindset talk | Cross-Section of Speculator Skill (persistence of skill) |
| 6 | Running the experiment on yourself | How to use AMI's Day Trader preset + CR131's outcome comparison as a personal trial | CR129 preset, CR131 instrumentation |

Six is a proposal, not a mandate — the build may merge or split. Lesson 6 is the one that must
exist, because it closes the loop between the preset, the data and the user's own results.

## Hard requirements

- **Every numeric claim carries a `sources:` entry in frontmatter** (internal-only provenance per the
  standing BOK rule — users never see it). No number without a citation. This is the CR that most
  invites confident-sounding invention, and this project has already been bitten by numbers that
  arrived wearing a citation they had not earned.
- **Verify each claim against the primary source before writing it.** Do not quote the summaries in
  this doc or in CR129 — they are second-hand and were assembled from search results, not from the
  papers. Read the papers.
- **`retranslate:[ar,ms]`** on every new lesson.
- **Follow the house format**: frontmatter (id, title, duration_min, level, module, difficulty,
  track, code, prerequisites, topic, tags, sources, agent_callouts, locale_versions), a real-market
  worked example, a "trap" section, `<Quiz>` blocks with explanations that teach rather than
  restate. Model on `047_revenge_trading.en.mdx` and the new `365_your_risk_limits_in_ami.en.mdx`.
- **Prerequisites must chain properly** into the existing curriculum (009, 014, 017, 047, 365).
- **Voice**: analyst-to-analyst, numbers > adjectives, no moralising. The reader has already decided
  to day-trade; treat them as a colleague testing a hypothesis, not a patient to be talked down.

## Also owed — a correction the research created

**Lesson 047 now contains a false statement.** It says the post-loss cooldown is *"tracked in the
Decision Journal, not enforced by the app."* CR129 makes it enforced. That line must change, and it
carries `retranslate:[ar,ms]`. Tracked here so it is not lost between CRs.

## Dependencies

**DEPENDS-ON CR129** (the preset and the limits the track explains) and **CR131** (lesson 6 links to
the outcome comparison). The first five lessons can be written before either lands.

Related: **CR060** (BOK content-quality ownership — sourced and verified, provenance internal),
**DEF102** / **DEF117** (the phantom-mandate cohort this curriculum work finally makes true),
**CR129**, **CR131**, lesson **365**.
