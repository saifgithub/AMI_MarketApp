# CR054 — The AMI Investment Body of Knowledge (BOK): from curriculum to canon

**Status:** planned — **master plan / umbrella CR** (implemented in waves by the architect team) · **Session:** AT:R63 · **Filed:** 2026-07-21

> Directive (Saiful): *"Create a CR I'll have coded by the architect team. Concentrate on
> making our investment body of knowledge rich. This should be the best investment BOK there is."*

This CR defines the **target state, standard, gap analysis, architecture, and production plan**
to elevate AMI Trade's educational corpus from a strong trading curriculum into a **comprehensive,
authoritative, best-in-class investment Body of Knowledge**. It is the plan the architect team
implements; it does not itself author lessons. Because the scope is large and ongoing, this is an
**umbrella CR** with phased waves (like CR004), each wave a shippable batch.

---

## 0. The bar we are setting

Today's corpus (270 lessons, 188 glossary terms, 280 coach Q&A, 183 daily challenges) is a
**good trading-skills curriculum**. "The best investment BOK there is" is a different, higher
target. Three things separate a curriculum from a body of knowledge:

1. **Completeness of the map.** A BOK covers the *whole* investable landscape and the disciplines
   that underpin it — not just the slices we started with (equities + TA + a strong strategy/psych
   spine). Right now a diligent user can finish every lesson we have and still never have been
   taught what a bond is, how the Fed moves markets, what an ETF costs them, how an option pays
   off, what insider trading is, or how to tell a real backtest from an overfit one.
2. **Authority.** A BOK is *sourced*. It stands on the recognized canon — the CFA/CMT/FRM bodies
   of knowledge and the classic literature — so a claim is defensible, not merely internally
   consistent. Today the corpus is self-referential.
3. **A defensible moat.** For *this* product the BOK's signature is the discipline no rival
   teaches: **being the discerning CEO of an analyst team** — the epistemics of evaluating
   analyst and AI output. That strand is what makes ours "the best" rather than "a good clone of
   a CFA prep book."

The goal: **comprehensive + authoritative + uniquely ours**, without breaking a single locked
constraint (simulation-only, AMI naming, frozen CR044 codes, the DEF064/065 quiz rules,
degrade-loudly, curated 5-lesson gateways).

---

## 1. Where the BOK stands today (grounded inventory)

| Corpus | Size | State |
|---|---|---|
| Lessons | **270** (`content/lessons/*.en.mdx`) | 77 foundation (M1–M12) + 180 expansion (100–279) + 13 legacy (280–292) |
| Glossary | **188** terms, 13 categories | `content/glossary/terms.en.json` |
| AI-coach Q&A | **280** | `content/ai_coach/` |
| Daily challenges | **183** | `content/daily_challenges/` |

Track / module coverage (from frontmatter):

| Track | Lessons | Verdict |
|---|---|---|
| `technical_analysis` | 45 | **Strong** — charts, indicators, patterns, multi-timeframe |
| `fundamentals_analysis` | 66 | **Strong** on ratios + statements; light on full valuation (DCF/DDM) |
| `edge_process` | 98 | **Strong** — strategies, failure modes, correlation, scams, AI-meta |
| `news_macro` | 19 | **Thin** — regime-labelled, not macro *mechanics* |
| `risk_portfolio` | 16 | **Moderate** — sizing/drawdown/Kelly; light on portfolio *theory* |
| `sentiment_behaviour` | 10 | **Thin** — greed/fear/FOMO + one bias inventory |
| `foundations` | 16 | Adequate for absolute basics |

**What is genuinely excellent already** (do not rebuild — extend at most): technical analysis;
fundamental *ratios* and statement literacy; the strategy library (trend/breakout/pullback/
mean-reversion/momentum + failure modes + rotation/correlation); scam protection (Module 11 — a
real differentiator); market-history/crash coverage (53 files reference real crashes); the AI-meta
module; and the 7-part lesson template itself (thesis → real-ticker example → the trap → ChatWith
→ synthesis quiz → action → takeaway), which is a genuinely good pedagogical spine with
falsifiability baked in.

---

## 2. The standard we benchmark to

A best-in-class investment BOK is measured against the field's recognized bodies of knowledge and
its canonical literature. We adopt these as the yardstick (and, in Wave 3, as *cited sources*):

- **CFA Candidate Body of Knowledge** — the broadest map: Ethics & Professional Standards,
  Quantitative Methods, Economics, Financial Statement Analysis, Corporate Issuers, Equity
  Investments, Fixed Income, Derivatives, Alternative Investments, Portfolio Management & Wealth
  Planning. (Note where AMI's coverage sits vs each area — §3.)
- **CMT (Chartered Market Technician)** — depth standard for technical analysis (we already meet
  much of this).
- **FRM (Financial Risk Manager)** — depth standard for risk, VaR, and portfolio risk.
- **The canon** (illustrative, for the Wave-3 sourcing spine): Graham *The Intelligent Investor*
  / Graham & Dodd *Security Analysis*; Damodaran on valuation; Bodie–Kane–Marcus *Investments*;
  Hull *Options, Futures & Other Derivatives*; Bogle *The Little Book of Common Sense Investing*;
  Kahneman *Thinking, Fast and Slow*; Taleb *Fooled by Randomness* / *The Black Swan*; Marks *The
  Most Important Thing*; Ellis *Winning the Loser's Game*; Lefèvre *Reminiscences of a Stock
  Operator*; Shiller *Irrational Exuberance / Narrative Economics*.

We are **not** turning AMI into an exam-cram product. We map to these to guarantee *coverage* and
*authority*, then teach in AMI's voice — analyst-to-analyst, numbers over adjectives, falsifiable,
simulation-framed.

---

## 3. Gap analysis — the meat

Measured against §2 and verified against the actual corpus (title + prose probes, 2026-07-21).
Three axes: **breadth** (is it covered?), **depth** (is it covered rigorously?), **pedagogy** (is
it taught, sourced, and assessed at BOK standard?).

### 3.1 Breadth gaps — whole disciplines missing or near-zero

| # | Domain | Evidence in corpus | Why it's load-bearing |
|---|---|---|---|
| G1 | **Fixed income & rates** | ~1 real prose treatment; no bond/duration/yield-curve/credit lesson | The discount rate *is* equity valuation; rates drive every regime. A BOK without bonds is not a BOK |
| G2 | **Options & derivatives** | **0** dedicated lessons, 1 body mention; glossary has 8 terms | Core asset class; hedging + payoff literacy is basic investor knowledge; retail loses on options *because* nobody taught them |
| G3 | **Funds & vehicles (ETF/index/passive)** | **0** dedicated lessons | How most retail actually invests (Bogle/indexing); expense ratios + tracking error are day-one literacy |
| G4 | **Economics / the macro machine** | ~4 title lessons, all CAPE/buyback; no Fed/inflation/cycle mechanics | Growth-inflation-rates is the engine under every ticker; ties directly to the News Analyst |
| G5 | **Ethics & market integrity** | **0 files** — insider trading, manipulation, fiduciary, conflicts, fair dealing | **CFA puts Ethics first.** We have zero. Also reinforces our own advice-vs-education regulatory frame |
| G6 | **Portfolio theory / MPT / factors** | 3 real lessons | CAPM/beta, efficient frontier, factor investing (value/momentum/quality/size/low-vol), asset allocation, rebalancing, risk parity — the "portfolio" half of `risk_portfolio` is mostly absent |
| G7 | **Quantitative & probabilistic literacy** | Kelly (1) + scattered tail content | Base rates, expected value, distributions, correlation≠causation, sample size, Bayesian updating — **the evaluator's math**; without it a user cannot judge an analyst's confidence |
| G8 | **Islamic finance / Sharia investing** | ~12 prose files, 0 dedicated module | The **mandate has a `halal` flag**; GCC/Tadawul + Bursa are target markets. Riba/gharar/screening/sukuk is a whole knowledge area we gate on but never teach |
| G9 | **Market mechanics / microstructure** | scattered | Order book, bid-ask/liquidity, settlement (T+1), short-selling & margin mechanics, corporate actions (splits/buybacks/M&A), index construction |

### 3.2 Depth gaps — covered, but not to BOK rigor

- **D1 Valuation.** DCF basics (167) + ROIC/WACC (199) exist, but DDM, reverse-DCF, scenario/
  sensitivity, EV/EBITDA depth, sum-of-parts are missing. Valuation is where fundamentals *pays
  off*; it deserves a full module, not two lessons.
- **D2 Behavioral finance.** Greed/fear/FOMO/revenge + one bias inventory (212). Missing: prospect
  theory, the full cognitive-bias catalogue, herding/reflexivity, narrative economics, mental
  accounting, disposition effect. `sentiment_behaviour` at 10 lessons is the thinnest track.
- **D3 Risk beyond sizing.** Sizing/drawdown/Kelly are strong; VaR, stress testing, tail hedging,
  correlation-under-stress (108 exists — good), liquidity risk, and portfolio-level risk budgeting
  are thin.
- **D4 ESG/sustainable investing.** 30 prose mentions, no structured treatment — and the mandate
  has an ESG flag. Same shape as G8.

### 3.3 Pedagogy gaps — what separates "good lessons" from "a canon"

- **P1 No sourcing / authority spine.** No lesson cites where its claim comes from. A BOK is
  defensible; ours is self-referential. (Wave 3.)
- **P2 Numbers are authored, not computed.** Worked examples are hand-written, so a wrong number
  can ship (DEF064-class risk). **CR046's `trading_math/` library** already computes indicators/
  sizing/fundamentals deterministically — the BOK's numbers should route through it, never be
  hallucinated. (Direct tie-in.)
- **P3 Assessment is single-lesson recall/synthesis only.** No module *capstones*, no
  cross-module synthesis, no confidence-calibrated questions (which teach the evaluator's skill
  of knowing what they don't know).
- **P4 The knowledge is a list, not a graph.** `prerequisites` + `see_also` + `agent_callouts` +
  glossary links exist but aren't maintained as a navigable concept graph. (Dovetails **CR053** —
  identifiable, linkable references — which becomes the graph's UI.)
- **P5 Single-market bias.** US-heavy; Bursa appears but GCC/Tadawul barely, despite being a
  target market and mandate context.

### 3.4 Coverage vs the CFA map (summary scorecard)

| CFA area | AMI today | Target after CR054 |
|---|---|---|
| Ethics & Professional Standards | ❌ none | ✅ Level 13 (G5) |
| Quantitative Methods | ⚠️ Kelly only | ✅ Level 12 (G7) |
| Economics | ⚠️ thin | ✅ Level 10 (G4) |
| Financial Statement Analysis | ✅ strong | ✅ + depth (D1) |
| Corporate Issuers | ⚠️ partial | ✅ (mechanics G9, buybacks/M&A) |
| Equity Investments | ✅ strong | ✅ maintained |
| Fixed Income | ❌ none | ✅ Level 9 / M13 (G1) |
| Derivatives | ❌ none | ✅ Level 9 / M15 (G2) |
| Alternative Investments | ⚠️ REIT mentions | ✅ funds/vehicles M14 (G3) + literacy |
| Portfolio Management | ⚠️ sizing only | ✅ Level 11 (G6, D3) |
| *(AMI-unique)* Evaluating analyst/AI output | ⚠️ M12 partial | ✅ **Level 14 — the moat** |

---

## 4. Target architecture — the enriched BOK

The design preserves the two-axis model (**Level/Module** = journey; **Track** = agent-unlock +
search facet) and the ID-range convention (foundation trunk + expansion companions). We **extend
the ladder** with new Levels 9–14 and deepen four existing tracks, add a sourcing spine, wire the
knowledge-graph, and route numbers through CR046.

### 4.1 New Levels & Modules (the breadth fix)

Continues the existing Level 1–8 / Module 1–12 sequence. Counts are **shape, not hard targets**
(per the standing curriculum philosophy — ship at quality, backfill later).

| Level | Module | Theme | Closes | ~Foundation lessons |
|---|---|---|---|---|
| **9 — The Investable Universe** | M13 Fixed income & rates | bonds, coupon/YTM, duration & convexity intuition, the yield curve, credit spreads/ratings, **how rates price equities**, rate-sensitive sectors | G1 | 7 |
| | M14 Funds & vehicles | ETFs vs mutual vs index funds, expense ratio & tracking error, passive vs active (Bogle), leveraged/inverse ETFs, REITs, ADRs, closed-end | G3 | 6 |
| | M15 Options & derivatives literacy | calls/puts, payoff diagrams, intrinsic/time value, the Greeks, covered call & protective put, implied vs realized vol, futures/forwards, **why retail options lose** | G2 | 7 |
| **10 — The Macro Machine** | M16 Growth, inflation & the cycle | GDP/CPI/employment, leading/coincident/lagging indicators, the business cycle, inflation mechanics | G4 | 6 |
| | M17 Central banks, policy & currency | the Fed & monetary policy, rate decisions, QE/QT, fiscal policy, FX basics, **US → Bursa/GCC transmission** | G4 | 6 |
| **11 — Building a Portfolio** | M18 Diversification & allocation | correlation done right, strategic vs tactical allocation, rebalancing discipline, home-country bias | G6 | 6 |
| | M19 Modern theory & factors | CAPM/beta, efficient-frontier intuition, factor investing (value/size/momentum/quality/low-vol), risk parity, portfolio risk budgeting, hedging a book | G6, D3 | 7 |
| **12 — The Evaluator's Math** | M20 Probability & evidence | expected value, base rates, distributions & fat tails, correlation≠causation, sample size & significance, Bayesian updating | G7 | 6 |
| | M21 Testing a claim | backtesting rigor, overfitting/curve-fitting, out-of-sample & walk-forward, Monte Carlo, data-mining & survivorship bias | G7 | 6 |
| **13 — Ethics & Market Integrity** | M22 Playing it straight | insider trading, market manipulation, front-running, pump-and-dump (bridges M11), fair dealing | G5 | 5 |
| | M23 Duty & conflicts | fiduciary duty, conflicts of interest, suitability, disclosure, **advice vs education** (reinforces our own regulatory frame) | G5 | 5 |
| **14 — The Discerning CEO** *(the moat)* | M24 Evaluating analyst & AI output | calibration & confidence, red-team/steelman a thesis, decision journaling & post-mortems, **process vs outcome**, when to override the Room, automation bias & cognitive offloading, aggregating disagreeing analysts | unique | 8 |

**Specialty strands (parallel, mandate-driven):**

- **M25 Islamic finance & Sharia investing** (G8) — riba/gharar, stock screening (business +
  financial ratios), sukuk vs bonds, purification, how the `halal` mandate flag maps to real
  screens. High priority: we *gate* on halal but never teach it. ~6 lessons.
- **M26 Sustainable / ESG investing** (D4) — what ESG scores are and aren't, greenwashing,
  exclusion vs integration, how the ESG mandate flag works. ~4 lessons.

**Depth deepenings inside existing tracks** (expansion IDs, not new modules):

- **Valuation deep-dive** (D1) under `fundamentals_analysis`: DDM, reverse-DCF, scenario/
  sensitivity, EV/EBITDA, sum-of-parts. ~8 lessons.
- **Behavioral finance deep-dive** (D2) under `sentiment_behaviour` (the thinnest track): prospect
  theory, full bias catalogue, herding/reflexivity, narrative economics, disposition effect. ~10
  lessons — roughly doubles the track.
- **Market mechanics** (G9) under `foundations`/`edge_process`: order book & liquidity, T+1
  settlement, short-selling & margin mechanics, corporate actions, index construction. ~6 lessons.

**Indicative total new lessons:** ~120 foundation-level + ~30–60 expansion deepenings ≈ **150–180
new lessons**, taking the corpus from 270 to ~**420–450** — a genuinely comprehensive BOK. Ship in
waves at quality; the count is a target shape.

### 4.2 The track decision (architect must wire the enum)

> **SUPERSEDED by CR059 (2026-07-21).** Saiful locked the new-group count at **6** (hex
> tessellation), not 4: the four below (ASST/MACRO/QUANT/ETHIC) **plus** net-new
> **`islamic_finance`** (SHARIA — from CR058) and **`decision_evaluation`** (EVAL — the
> Discerning-CEO moat). **ESG** folds into `ethics_integrity` rather than a `mandate_compliance`
> track. CR059 holds the authoritative 13-group table; the Option A/B text below is kept as history.

The new domains do not all fit the 7 existing tracks, and **track drives both agent-unlock routing
and the CR044 code prefix**. Two options — recommendation follows:

- **Option A (recommended): add 4 new tracks** for the orthogonal domains, keep deepenings in
  existing tracks. Proposed tracks + speakable prefixes (CR044 rules: prefix spoken aloud, must be
  unambiguous, frozen, contiguous 1..N):

  | New track | Prefix | Houses | Agent-callout mapping |
  |---|---|---|---|
  | `asset_classes` | **ASST** | M13–M15 (fixed income, funds, options) | fundamentals_analyst / market_analyst |
  | `economics_macro` | **MACRO** | M16–M17 | news_analyst (macro is its beat) |
  | `quant_methods` | **QUANT** | M20–M21 | research_manager |
  | `ethics_integrity` | **ETHIC** | M22–M23 | portfolio_manager / concierge |

  Islamic finance (M25) + ESG (M26) fold into `fundamentals_analysis` with a compliance lens (they
  are screening disciplines), or get a `mandate_compliance` track if Saiful wants them first-class.
  Portfolio theory (Level 11) deepens the existing `risk_portfolio` track (already named "Risk &
  Portfolio Construction" — it was scoped for this). The Discerning-CEO level (14) extends
  `edge_process`.

- **Option B: force everything into the 7 tracks.** Cheaper (no enum/UI/routing change) but
  dishonest — "what is a bond" is not `edge_process`, and the track facet stops meaning anything.

**Wiring touch-points for Option A (architect checklist):** the `track` enum
(`backend/app/schemas/lessons.py`), the display-name + prefix maps
(`backend/app/services/lessons_service.py:69-90`), the mobile `_trackShortLabel`
(`track_lessons_screen.dart:20-28`), agent-unlock routing (each new track's lessons still gate via
the curated `AGENT_GATEWAYS` — **gateways stay fixed at 5**, unchanged), the glossary category
enum, and the corpus-integrity test (new prefixes, contiguity). New tracks are additive — existing
CR044 codes are untouched, so DEF068/DEF071 are safe.

### 4.3 The sourcing / canon spine (the authority fix — P1)

- Add an optional `sources` frontmatter field + a "**Where this comes from**" one-line body
  affordance, mapping each lesson to the canon (§2). Not academic footnoting — one authoritative
  anchor per lesson ("This is the Graham margin-of-safety idea", "Kelly (1956), as applied by
  fractional-Kelly practitioners").
- A BOK-level index: `content/_authoring/canon.md` — the source map (which lessons rest on which
  works), so the corpus is *defensibly* authoritative and a reviewer can trace any claim.
- Regulatory guard unchanged: sources establish *concept lineage*, never "this book says buy X."

### 4.4 The knowledge-graph (P4 — dovetails CR053)

- Treat every lesson, glossary term, and agent as a **node**; `prerequisites`, `see_also`,
  `agent_callouts`, and inline links as **edges**. Maintain it as a real graph with integrity
  guards (acyclic prerequisites, no dangling refs, every concept reachable).
- **CR053** (curriculum reference identifiability + quick-links) is the *UI* of this graph — the
  tappable `<Lesson>` / `{{lesson:}}` links that let a user walk it. CR054 supplies the *content
  density* that makes the graph worth walking. Sequence CR053 before/with Wave 2 so new lessons
  are born linkable.

### 4.5 Computational rigor via CR046 (P2)

Every numeric worked example that can be computed deterministically routes through
`backend/app/trading_math/` (the CR046 ledger), not authored by hand. New math the BOK needs and
CR046 should absorb (each with its guard test, per CR046's standing policy): **bond price/YTM/
duration, option payoff & break-even, portfolio variance/correlation/beta, expected value & Kelly
(already M03), Sharpe/max-drawdown/CAGR** (CR046 already flagged adopting `empyrical-reloaded` for
these). The BOK never ships a wrong number; the coherence guard (shown == computed) applies.

### 4.6 Quality-bar upgrades to the 7-part template (P3)

Extend `content/_authoring/lesson_authoring_prompt.md` (v2) — additive, existing 270 lessons stay
valid:

- **Steelman/red-team beat** (optional 8th part for analytical lessons): after "the trap", state
  the *strongest opposing case* and its falsifier — trains the evaluator's habit of arguing the
  other side. Fits the Discerning-CEO thesis and the 12-agent debate model.
- **Calibration quiz variant**: a confidence-weighted question form ("how sure are you?") for
  Level 12/14, teaching users to know what they don't know. (New quiz *rendering*, so a scoped
  client change — architect notes it; falls under DEF064's multiple-choice invariant unless a new
  type is deliberately added with its own guards.)
- **Module capstones**: one synthesis lesson per new module requiring cross-lesson integration
  (the "last quiz tests synthesis" rule, scaled to module level).
- **`sources` line** (§4.3) and **multi-market example discipline** (US + Bursa + at least
  occasional GCC), currency-prefixed per the existing locale rule.

### 4.7 Parallel expansion of the other three corpora (they must mirror the lessons)

The BOK is not just lessons. Each gap must land across all four corpora or the Concierge and daily
loop will still be blind to it:

- **Glossary** (`terms.en.json`, 188 → target ~350): new categories **`asset_classes`, `economics`
  (rename/extend `macro`), `ethics`, `quantitative`, `islamic_finance`** — today there is **no
  ethics, asset-class, or quant category at all**. Options_derivatives (8) and macro (12) roughly
  triple.
- **AI-coach Q&A** (280 → +~150): the questions a user *actually asks* about bonds, options, ETFs,
  the Fed, insider trading, "is my backtest legit", "is this stock halal" — highest leverage
  because every user hits these via the Concierge.
- **Daily challenges** (183 → ongoing): new scenario stock for the new domains; consider new types
  (e.g. `value_the_bond`, `read_the_payoff`, `spot_the_conflict`) or reuse existing types on new
  content.

---

## 5. Production plan (what the architect team builds)

Phased so every wave is independently shippable and quality-gated. Each wave = author batch (via
the upgraded prompt) + guards + glossary/Q&A mirror.

**Wave 0 — Foundations for the expansion (enabling, small).**
- Architect decides the track question (§4.2); wire the enum/prefix/UI/routing/glossary-category if
  Option A. Extend the corpus-integrity test for new tracks/prefixes/contiguity.
- Author-prompt v2 (§4.6): new domains, `sources` line, steelman beat, capstone template, new
  glossary categories, new coach categories.
- CR046: open the bond/option/portfolio math entries (§4.5) with guard tests.

**Wave 1 — The four clean breadth gaps (highest leverage).** Foundation lessons for **Ethics
(M22–M23), Asset classes (M13–M15), Macro machine (M16–M17), Evaluator's math (M20–M21)** + their
glossary + coach mirrors. These are the domains where coverage is ~zero, so each lesson is pure
gain. Rough: ~40 lessons, ~120 glossary terms, ~80 Q&A.

**Wave 2 — The moat + mandate strands.** **Level 14 Discerning-CEO (M24)**, **Islamic finance
(M25)**, **ESG (M26)**, **Portfolio theory (Level 11 / M18–M19)**. Sequence **CR053** here so new
lessons ship linkable. Rough: ~35 lessons.

**Wave 3 — Depth + authority + graph.** Valuation deep-dive (D1), behavioral deep-dive (D2), market
mechanics (G9); the **canon sourcing spine** (§4.3, `canon.md` + `sources` backfill on high-value
lessons); the **knowledge-graph integrity guards** (§4.4); module capstones. Rough: ~30 lessons +
the spine + guards.

**Ongoing — living canon.** After Wave 3 the BOK is maintained, not frozen: new market events →
new case studies; usage data → deepen where users stall; annual canon review.

### 5.1 Guards (land in the same commit as their content — house rule)

Extend `backend/tests/unit/test_lesson_corpus_integrity.py`:
- new track prefixes present, unique, prefix-matches-track, contiguous 1..N (CR044 invariants
  extended to ASST/MACRO/QUANT/ETHIC);
- `prerequisites` form a **DAG** (no cycles), every ref resolves, difficulty non-decreasing within
  a module;
- every capstone is the last lesson in its module and its final quiz is synthesis;
- `sources` (when present) resolve to a `canon.md` entry;
- glossary: new categories are in the enum; every `related_lessons` id resolves.
- DEF064/DEF065 quiz invariants unchanged (multiple-choice only; no numeric option references).

---

## 6. Constraints honoured (non-negotiable)

- **Simulation-only, forever.** Bonds, options, ETFs, FX are taught as **literacy**, never as
  in-app tradable instruments and never as "act on this." Every new lesson keeps the training-
  artifact + not-investment-advice framing (authoring prompt §"Regulatory framing"). Derivatives
  and Islamic-finance lessons especially must not read as product solicitation.
- **AMI by name** in all user-facing copy; **LLM** only in code.
- **CR044 codes are frozen and contiguous.** New lessons take the next free number in their track;
  new tracks get new prefixes. Nothing renumbers existing codes → DEF068/DEF071 safe.
- **Gateways stay curated at 5 per agent.** New lessons may be `agent_callouts`, but the unlock set
  is edited deliberately in `agent_gateways.py`, never auto-derived.
- **Degrade loudly (CR040).** New config/tracks fail a corpus test, never a user's screen; the
  math-coherence guard (CR046) keeps shown == computed.
- **Quiz invariants (DEF064/DEF065).** Multiple-choice only; options required; no numeric option
  references; answer position varied. A new calibration quiz *type*, if built, ships with its own
  guards and its own client rendering — flagged, not assumed.

## 7. Registers & sequencing

- Row added to `docs/forward_planning/cr_list.md` (CR054, status `planned`, umbrella).
- **Relationship to other CRs:** consumes **CR046** (math ledger — the BOK's numbers); pairs with
  **CR053** (reference identifiability/quick-links — the graph's UI); supersedes the informal
  "expansion lessons" note in `curriculum_map.md` (which this CR's waves formalize and extend).
- **Companion docs to add in this folder as waves scope up:** `gap_analysis.md` (the full §3 with
  per-lesson probes), `bok_architecture.md` (the §4 module/track/ID map once the architect fixes
  the track decision), `canon.md` seed (§4.3).
- Commit tag for filing this plan: `(AT:R63 CR054)`. Wave commits: `(AT:R<N> CR054)`.

---

### One-paragraph brief for the architect team

Take AMI's 270-lesson trading curriculum to a comprehensive, sourced, best-in-class investment BOK
(~420–450 lessons) by adding the disciplines we're missing entirely — **fixed income, options,
funds/ETFs, macro-economics, ethics & market integrity, portfolio theory, quantitative literacy,
and Islamic/ESG screening** — plus a signature **Discerning-CEO** strand on evaluating analyst/AI
output that no rival teaches. Wire ~4 new tracks (or justify folding in), extend the authoring
prompt with a sourcing spine + steelman beat + capstones, route every number through CR046's math
library, and mirror each gap across glossary/Q&A/daily-challenge corpora. Ship in four waves,
Ethics + the clean breadth gaps first, guards in every commit, and **not one break** to
simulation-only framing, AMI naming, frozen CR044 codes, or the curated 5-lesson gateways.
