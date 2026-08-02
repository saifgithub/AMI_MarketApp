# CR136 — Portfolio Health: whole-portfolio, risk-based evaluation

**Status:** proposed · **Filed:** 2026-08-02 (AT:R65)
**Revised:** 2026-08-02 (AT:R65) — **Rev 2, quant review. The Rev 1 math was
wrong in its foundation and has been replaced.** See "Rev 2 — quant review"
below for what was wrong, the measured evidence, and what replaced it. Do not
build from Rev 1; it survives only inside the review section as the record of
what was rejected.
**Revised:** 2026-08-02 (AT:R65) — **Rev 3, r1 audit integration.** Track-U
audit (round 1, `CR136.auditor.md`) independently confirmed all five
quantitative claims C1–C5 and the substance of C6, and returned 2 MAJORs + 5
MINORs. Rev 3 integrates the auditor's spec pack (`CR136.spec-pack.md`) with
two corrections found by verifying the pack itself (LW citation ambiguity;
journal idempotency needing app-level enforcement), pins every sufficiency
threshold and estimator choice, and adds the development-ready specs for the
Finding (user-facing report), the recommendation rule engine, the journal
integration, and the CR137 prompt contract.
**Precedes:** CR137 — Portfolio Room (reserved by number, not yet filed; see below)

## Why

AMI Trade's entire core loop is single-ticker: the 12-agent Room, the Portfolio
Manager's APPROVE/REJECT/MODIFY verdict, Convene the Room, Brief Your Agent — all
convene on **one ticker** and produce a verdict on **one proposed trade**
(`docs/initial_specs/02_agents/convene_the_room.md:3` — *"All 12 agents run on a
single ticker"*). Portfolio state is only ever read as *context* for that one-trade
verdict (`content/agents/portfolio_manager.md`'s declared inputs include "user's
current portfolio state," but the subject being judged is still the trade).

Saiful flagged the gap directly: nothing steps back and evaluates the **whole
portfolio** — diversification, risk-adjusted return, drawdown exposure, market
sensitivity — the way a real analyst or robo-advisor would. A codebase-wide check
confirmed this is real, not just a missing screen:

- The only genuinely portfolio-wide feature live today is **CR026** (sector
  allocation + concentration cap) — one dimension (sector weight) of many.
- Two math modules already exist, fully built, with **zero live call sites**:
  `backend/app/trading_math/portfolio_stats.py` (variance, covariance,
  correlation, CAPM beta, `wᵀΣw` portfolio variance) and
  `backend/app/trading_math/returns.py` (CAGR, max drawdown, Sharpe ratio).
  Both were built for CR046 (agent math ledger)/CR054 (BOK lesson content) —
  they compute the worked-example numbers in lessons, but nothing wires them to
  a real user's real holdings.
- No stored history of portfolio value over time exists — `SimHoldingRow` is a
  point-in-time position table, no equity curve.
- No existing CR or Defect scopes "evaluate the whole portfolio" — grepped
  `cr_list.md`/`def_list.md`/all of `docs/initial_specs` for every phrasing
  ("portfolio health," "portfolio risk," "holistic," etc.) — zero hits.

This CR adopts a framework that is **textbook** (CFA-curriculum standard),
**professionally used** (the same building blocks Morningstar's Portfolio Risk
Score, Wealthfront/Betterment, and institutional risk desks use), and
**defensible** (every number traces to a named, citable methodology — nothing
invented).

**Decided with Saiful:**
- Ship **phased, but go all-in on the agentic layer.** Saiful was direct:
  *"Full portfolio scoped room, phase B. We go all in. This is an agentic app.
  But all math must be deterministic."* The destination is a real multi-agent
  **Portfolio Room** (CR137, sketched below), not numbers with a paragraph
  bolted on. What's phased is *sequencing*, not ambition: this CR builds the
  deterministic metrics engine — it has to exist first, because the Room's
  agents will consume its numbers as ground truth and must never compute math
  themselves (CR046 discipline, CR040 "prompt instructions are not controls").
  CR137 is the portfolio-scoped Room built on top of it.
- History: **backfill AND persist going forward** — a daily snapshot job
  (required either way regardless of backfill), *and* a one-time backfill
  script reconstructing history for existing alpha testers' trades so they
  aren't staring at "insufficient history" for 90 days.
- **This filing is doc-only.** The build below is scoped and queued, not
  started — status stays `proposed` until a session picks it up.

## The governing principle — what is estimable, and what is not

Every metric decision below follows from one measured asymmetry. For an asset
with 20% annualised volatility, the standard error of the estimated **mean
return** is `σ/√years`, while the standard error of the estimated
**volatility** is `≈ σ/√(2T)`:

| Data available | Obs | SE of annualised **mean return** | SE of annualised **volatility** |
|---|---|---|---|
| 3 months (max the codebase can fetch today) | 64 | **40.0 pp** | 1.77 pp |
| 1 year | 252 | 20.0 pp | 0.89 pp |
| 5 years | 1,260 | 8.9 pp | 0.40 pp |
| 20 years | 5,040 | 4.5 pp | 0.20 pp |

Mean returns are **not estimable** at any horizon a retail user will ever
have. Second moments — volatility, covariance, correlation, beta — are
estimable from months.

**Therefore: any metric with a mean-return term in its numerator is not
shippable, and every metric without one is.** That single line decides the
whole feature:

- **Excluded** (mean-return numerator): Sharpe, Sortino, Treynor, Jensen's
  alpha, information ratio.
- **Included** (pure second-moment): portfolio volatility, beta, correlation,
  risk contribution, diversification ratio.

This is also exactly where institutional risk platforms draw their line —
**FMR LLC's (Fidelity's) risk-platform patent** (US10157419B1, the one
institutional methodology publicly documented at claim level) makes its
headline output **TEV (tracking error volatility) and risk decomposition**,
second-moment quantities, not performance ratios. *(Attribution corrected in
r1 audit — the patent was previously misattributed to BlackRock/Aladdin.
Aladdin's public materials describe the same holdings-based, factor-exposure,
scenario-simulation shape, but its methodology is not published at this level
of detail; the claim-level evidence is Fidelity's.)* The statistics, the
professional precedent, and our actual data constraint all point the same way.

## The framework

Two tiers. Tier 1 is the product; Tier 2 is descriptive history that
accumulates behind it.

### Tier 1 — forward-looking, holdings-based (works on day one, no portfolio history)

Computed from **current holdings × each holding's own return history** — the
institutional holdings-based approach (the FMR patent at claim level;
Morningstar and Aladdin's public materials describe the same shape), which
needs the *securities* to have history, not the *portfolio*. This is what
makes the feature work for a user who opened their account yesterday.

| Metric | Definition | Why it's defensible | Code |
|---|---|---|---|
| **Portfolio volatility** (annualised) | `√(wᵀΣw)`, Σ estimated with Ledoit–Wolf shrinkage | Markowitz; shrinkage is the standard fix for short-sample covariance instability (Ledoit & Wolf, [*Honey, I Shrunk the Sample Covariance Matrix*](http://www.ledoit.net/honey.pdf), JPM 2004 — constant-correlation target; see Estimator pins) | `portfolio_stats.py::portfolio_variance` — **now the centrepiece**, not a stretch goal |
| **Beta vs. benchmark** + **R²** | Regression slope of portfolio returns on benchmark returns | CAPM. R² ships alongside because a beta with low R² is not a meaningful summary | `portfolio_stats.py::beta` (needs a **date-aligned** benchmark series — see defect 7) |
| **Effective independent bets** | `DR²` where `DR = (Σwᵢσᵢ)/σₚ` | Choueifaty & Coignard diversification ratio; Choueifaty–Froidure–Reynier (2012) show `DR²` = number of independent bets ([Portfolio Optimizer](https://portfoliooptimizer.io/blog/the-diversification-ratio-measuring-portfolio-diversification/)) | New pure function over the same Σ |
| **Risk contribution** by holding and by sector | `wᵢ·(Σw)ᵢ / σₚ²`, sums to 100% | The institutional-platform headline output — the FMR patent's "contribution to TEV by security, sector or factor" | New pure function over the same Σ; sector map reuses CR026 |
| **Weight concentration** — HHI → effective-N | `Σwᵢ²`, `1/HHI` | Standard concentration measure — **but labelled "weight concentration," never "diversification"** (see defect 2) | New pure function |

The four Tier-1 risk metrics all fall out of **one covariance matrix**. Build Σ
once per request, derive everything from it.

### Tier 2 — realised, snapshot-based (accumulates; descriptive only)

| Metric | Status |
|---|---|
| Equity curve | Ships when history exists |
| **Realised max drawdown** (peak-to-trough), window-labelled | Ships — a *descriptive statistic* of what happened, making no inferential claim, so the sample-size objection doesn't apply. Must state its window ("worst fall in the 94 days observed"), never compared against a benchmark's different window |
| Realised return, window-labelled | Same |

**No composite score.** Morningstar's 0–100 is the closest productised
precedent but its weighting is proprietary — AMI cannot cite or defend a
weighting it invented. Each metric above stands on its own named methodology.

### Sufficiency contract (pinned per r1 audit M1)

All thresholds in **trading days**, counted as returns (65 bars → 64 returns).
Code reads them from one `SUFFICIENCY` constant block — never scattered
literals. Every pinned number carries its derivation so the choice is
re-derivable, not taken on anyone's word.

| Metric | Min observations | Derivation | `standard_error` |
|---|---|---|---|
| Portfolio volatility σₚ | **T ≥ 126** | SE(σ̂) = σ/√(2T): at 126 obs and σ=20%, SE = **1.26pp**; at the ~251 obs a 1y daily fetch yields, 0.89pp. 126 = 6 trading months — the first day the number is defensible | `σ/√(2T)` (Gaussian); doc carries the fat-tail caveat: at daily excess kurtosis ≈ 30 the true SE is ~1.9× wider — still ≪ any mean-term SE, conclusion unmoved |
| Beta + R² | **T ≥ 126**, same aligned window | Inherits the Σ window; the regression needs the same sample | OLS: `σ_ε/√(Σ(x−x̄)²)` |
| Diversification ratio DR² | inherits Σ sufficiency | Same matrix, same window | **null by decision** — a delta-method SE for a ratio of quadratic forms is not defensible at our T; documented, not computed |
| Risk contribution | inherits Σ sufficiency + conditioning rule | Same matrix | null (same decision) |
| HHI / effective-N (weight concentration) | **none** — pure accounting of today's weights | No estimation involved; `basis: "weights"` | null always |
| Benchmark volatility (context metric) | T ≥ 126 | Same formula on the benchmark leg | `σ/√(2T)` |
| Tier-2 realised max drawdown | **≥ 2 snapshots** | Descriptive, no inferential claim — but `window_days` mandatory; cross-window comparisons forbidden | null always |

- **Σ conditioning rule:** LW shrinkage applies at every T/N, but `sufficient`
  additionally requires **T/N ≥ 5** (25 holdings need 126 obs → 5.04 ✓; 40
  holdings need the 1y window). LW is valid well below this; 5 is the
  conservative retail-book floor.
- **Short-history holding rule** (recent IPO etc.): a holding with < T_min
  observations is **dropped from Σ**, weights renormalised over the remainder,
  metrics marked `partial: true` with `dropped_holdings: [...]`. If dropped
  weight exceeds **20% of invested value**, the whole Tier-1 block returns
  `sufficient: false` — a Σ that ignores a fifth of the book is not the user's
  portfolio.
- **R² companion flag** (not a sufficiency condition): `R² < 0.20` sets
  `low_explanatory_power: true` on the beta block. Beta still ships — with the
  flag, and the Finding's copy must say what it means.

### Estimator pins (per r1 audit m4/m5, with one correction to the audit itself)

- **Weight convention:** `w` spans **total portfolio value, cash included as a
  zero-vol row**. The user is shown the risk of their whole book as the app
  displays it; the invested-only alternative inflates every number for
  cash-heavy users and contradicts the tile copy (and DEF149 already made cash
  a position in the allocation denominator). Verified in r1: the Euler
  identity holds exactly with a cash row (Σ contributions = 1.000000, cash
  contributes 0.0000). Detailed section may additionally report the invested
  sleeve, labelled, never mixed.
- **Benchmark:** one series, **SPY adjusted close** (dividends included —
  avoids the ^GSPC price-only inconsistency), date-aligned by **inner join on
  candle timestamps**; misaligned or short → beta block `sufficient: false`,
  never silently re-gridded (defect 7).
- **Ledoit–Wolf — cite by title, and hand-roll stdlib-only.** *Correction to
  the r1 spec pack, found in the architect's verification pass:* "Ledoit–Wolf
  2004" pins nothing — there are **two** 2004 LW papers with different
  targets ("A Well-Conditioned Estimator for Large-Dimensional Covariance
  Matrices", JMVA 2004 → scaled-identity target; "Honey, I Shrunk the Sample
  Covariance Matrix", J. Portfolio Management 30(4) 2004 →
  constant-correlation target), and the 2003 J. Empirical Finance paper is the
  single-factor target, not identity as the r1 verdict stated. **The shipping
  estimator is the constant-correlation target of *Honey, I Shrunk the Sample
  Covariance Matrix* (Ledoit & Wolf, JPM 2004), cited by title everywhere.**
  Shrinkage intensity clamped to [0,1]; the shrunk matrix is PSD by convexity
  (a convex combination of PSD matrices), which closes the non-PSD worry.
- **Implementation home — `trading_math/`, stdlib-only, NO numpy.** *Second
  deviation from the r1 spec pack, with derivation:* the pack proposed
  declaring numpy; verification shows `trading_math/`'s package contract is
  explicitly **stdlib-only and copy-portable** (`trading_math/__init__.py` —
  "NO imports from anywhere else in `app` — only the Python stdlib"), CLAUDE.md
  bans undiscussed new deps, and CR046 D1 already hand-rolled its metrics for
  exactly this reason. The matrices are tiny (N ≤ ~50 holdings, T ≤ ~252 →
  O(N²T) ≈ 630k float ops), so pure Python is milliseconds — there is no
  performance case for numpy. LW closed form lands beside
  `portfolio_variance` in `trading_math/`. Known-answer tests use
  **precomputed fixtures** (generated once offline against an independent
  numpy implementation, stored as literals) — no test-time numpy import, so
  the suite never depends on an undeclared transitive.
- **Annualisation:** √252, applied only to trading-day series; the snapshot
  job writes trading days only (gated on candle timestamps, per scope 3a).

### The uncertainty contract (required, because an LLM consumes this)

Saiful's architecture is quants compute, agents interpret. That makes the
quant layer's output an **LLM input**, and an agent will confidently narrate
whatever it is handed — it cannot know a number is noise. Feeding bare point
estimates to the Room re-creates DEF059's failure class (confident output over
a silently-degraded input) as confident fake risk assessment.

Every metric block in the API response carries, structurally:

```json
{
  "metric": "portfolio_volatility",
  "value": null,
  "standard_error": null,
  "n_observations": 0,
  "window_days": 0,
  "sufficient": false,
  "partial": false,
  "dropped_holdings": [],
  "low_explanatory_power": null,
  "basis": "holdings",
  "engine_version": "cr136.v1"
}
```

Hard rules (r1 audit m2 — the null is what makes enforcement structural):

- `sufficient: false` ⇒ `value` **and** `standard_error` are **null**. Never
  `0.0` — a zero is a number an agent can narrate; a null is not. This is
  what makes serialisation-boundary enforcement structural rather than
  aspirational (CR038 — "prompt instructions are not controls").
- `partial: true` ⇒ `dropped_holdings` non-empty, and every surface (API
  consumer, Room context, Finding, journal payload) carries both.
- `engine_version` on every block — old journal entries stay interpretable
  after the estimator changes.

The CR137 context builder **strips** insufficient blocks before prompt
assembly (see "LLM prompt contract" below) — the model never sees the metric
name, so there is nothing to narrate.

## The Finding — the user-facing report

The engine's output reaches the user as a **critical financial analysis of
their whole portfolio**, filed like a report from their analyst team. Saiful's
audience requirement, verbatim into the standard this artefact must meet:
*"the next person to read the report will be the user and their human
portfolio manager. They will be extremely critical, to the point of being
rude."*

**The hostile-reader standard.** Every Finding must survive review by a
professional portfolio manager actively looking for a reason to dismiss it:

- Every number carries its **method, window, and sample size** — the three
  things a professional checks first. A number without them is the first
  thing a hostile reader circles in red.
- **Limitations are disclosed before the reader finds them**: gross-of-fees,
  simulation data, shrinkage estimator, observation window, any dropped
  holdings. A report that discloses its own weaknesses first cannot be
  ambushed by them.
- **No judgement adjectives anywhere** ("risky", "healthy", "dangerous",
  "impressive") — a professional reads those as salesmanship. Numbers and
  comparisons only; the reader supplies the judgement.
- **No claim outside the payload.** Every sentence must trace to a metric id
  or a triggered rule id. If a hostile reader asks "where does this number
  come from?", the answer is in the same document.
- Register split: **headlines, executive summary, and recommendations are
  plain language** (accessible to the user); **the detailed section is
  technical** (satisfies the PM). Neither register leaks into the other.

Five mandatory sections. Brand voice throughout: numbers over adjectives; AMI
by name, never "the AI".

**§F1 Headlines** (3–5 one-liners; each = one number + its plain meaning)

- Required items: portfolio volatility with benchmark volatility alongside;
  top risk contributor as "X% of risk vs Y% of money"; effective independent
  bets (DR²) next to raw holding count; realised max drawdown **with its
  window** (Tier-2, only when sufficient); beta, with the R² flag surfaced
  when set.
- Rules: no judgement adjectives; a headline built on a `partial` metric
  carries the partial marker inline.

**§F2 Executive summary** (4–8 sentences, descriptive only)

- Required: a risk-posture sentence (σₚ vs benchmark σ); a diversification
  sentence (DR² vs holding count — copy must honour the DR² caveat below:
  "effective independent bets", never a promise of a literal bet count); a
  concentration sentence (top contributor); a window + sufficiency disclosure
  sentence.
- Forbidden: advice verbs (recommendations live in §F5 only), any mean-return
  or performance claim, any number not in the payload.

**§F3 Detailed math analysis** (one block per metric — the PM's section)

- Required per block: value, `standard_error` where defined,
  `n_observations`, `window_days`, estimator name + citation (Markowitz;
  Ledoit & Wolf, *Honey, I Shrunk the Sample Covariance Matrix*, JPM 2004;
  Choueifaty & Coignard 2008; CAPM), one line of "what this measures",
  data-quality notes (`partial`, `dropped_holdings`, `low_explanatory_power`).
- Required once per section: the shrinkage disclosure ("covariance estimated
  with Ledoit–Wolf constant-correlation shrinkage for a short sample") and
  the gross-of-fees line (the sim deducts no fees or slippage — Rev 2
  finding; disclose wherever performance-adjacent numbers appear).
- This section cross-references CR054's M11/M12 BOK lessons — same metric
  names, same formulas — so the report teaches what the lessons teach.

**§F4 Conclusion** (2–4 sentences)

- Ties the three threads: risk level, diversification quality, concentration.
- Restates the window and any sufficiency limits. **No new numbers** — every
  figure cited already appeared above.

**§F5 Actionable recommendations** (deterministic rule engine — see below)

- Required per recommendation: the trigger values shown in the sentence
  ("because NVDA is 62% of your risk at 30% of your money"), the `based_on`
  metric ids, and a severity band. One to three per Finding; none triggered ⇒
  the section says so plainly — it never manufactures a suggestion.

**DR² copy caveat (r1 audit m3, upheld):** DR² equals a literal independent-
bet count only in the equal-vol/uniform-ρ case. The auditor's probe: a 60/40
two-asset book, vols 16%/7%, ρ=0 reads DR² = 1.54, not 2 — DR² also penalises
weight/vol imbalance. UI and lesson copy say "effective independent bets" as
a *measure*, never promise a literal count. (If a literal count is ever
wanted, Meucci's entropy-of-risk-contributions is the stricter tool — not
required here.)

Presentation surfaces: the Portfolio Health card (scope item 6) carries §F1
headlines + the entry point; the full Finding is a detail view. Any
`sufficient: false` block renders the explicit "not enough data yet" state —
never a blank, a zero, or a number.

## Recommendation rule engine (deterministic — the LLM never invents advice)

Rules fire on the stripped metric context; templates are fixed strings with
value slots. The LLM's only role is ordering and connective phrasing within
triggered templates. Thresholds live in one constant block with known-answer
fire/no-fire tests at every boundary.

| Rule | Trigger | Template (slots in braces) |
|---|---|---|
| R1 concentration | top contributor risk_share ≥ 40% | "{ticker} is {risk_share}% of your portfolio's risk at {weight}% of its value. Trimming it reduces total risk more per dollar than any other single change." |
| R2 correlated cluster | DR² < 2.0 AND holdings ≥ 8 | "You hold {n} positions but only {dr2} effective independent bets — they move together. Adding {count} more positions in the same sectors will not change this; a genuinely different exposure will." |
| R3 beta band | β ≥ 1.3 AND R² ≥ 0.2 | "Your portfolio amplifies the market: β = {beta}. A 10% market move has historically meant ~{beta_x10}% for this book over the window." |
| R4 cash drag | cash weight ≥ 40% | "{cash}% of your book is cash, which dilutes every risk number above. These metrics describe a smaller invested sleeve than your total suggests." |
| R5 data limits | any `partial: true` | "Metrics exclude {dropped} (insufficient history). Treat the numbers as describing {covered}% of your invested value." |

Simulation-only guard: recommendations phrase actions inside the sim ("trim",
"add an exposure") and never constitute investment advice — the app's
existing simulation-only framing applies to every template.

## LLM prompt contract (CR136's renderer now; CR137's Room later)

"Agents narrate, never compute" is only real if the context handed to the
model is pre-digested. Structural rules, in enforcement order:

1. **Strip before assembly.** The context builder drops any metric block with
   `sufficient: false` *before* prompt construction. The model never sees the
   number, the null, or the metric name — there is nothing to narrate.
2. **Comparisons are precomputed, not derived.** Agents are forbidden
   arithmetic, so any comparison the product wants stated must itself be a
   metric in the payload. Ship exactly one context metric: **benchmark
   volatility** (same window, same estimator). "23% vs the market's 15%" is
   then a citation, not a computation. No other ratios — if a comparison is
   not in the payload, it is not said.
3. **Prompt skeleton** (system side; verbatim slots):

   ```text
   You are the AMI analyst team filing a Portfolio Health finding.
   You may only cite numbers present in PORTFOLIO_CONTEXT below.
   Never compute, estimate, extrapolate, or compare beyond what is present.
   Never make return predictions or performance claims.
   Volatility, beta, diversification and risk contribution are estimates
   over the stated window — always keep the window attached.
   If a metric is absent, the data was insufficient — do not mention it.
   Headlines, executive summary and recommendations are plain language for
   a non-professional reader. The detailed analysis section is written for
   a professional reviewer. Do not mix the registers.
   Never use judgement adjectives (risky, healthy, dangerous, strong).
   PORTFOLIO_CONTEXT: {stripped_metric_blocks}
   FINDING_SECTIONS: {section_specs}
   TRIGGERED_RULES: {rule_ids_with_slot_values}
   ```

4. **Output is structured, not free prose.** The model returns the Finding as
   sectioned JSON matching §F1–§F5; the renderer — not the model — owns
   number formatting. Placeholders are filled from the same stripped context:
   the model selects and orders, the deterministic layer interpolates. CR046's
   discipline applied to prose.
5. **Post-generation validation (structural, not prompt-based):** the
   renderer rejects any model output containing a number absent from the
   payload (digit-sequence match against the context values) or any
   judgement adjective from a fixed lexicon, and falls back to the
   deterministic template rendering. The templates stand alone — the model
   adds fluency, never facts, so the fallback is always available (CR040:
   degrade loudly, and the degraded state is still a correct report).

## Journal storage plan

Every generated Finding persists to the user's journal. Verified against the
codebase 2026-08-02 (two corrections to the r1 spec pack marked ▲):

- **Machinery exists:** `journal_entries` table (models.py:262),
  `JournalStore.append` (journal_store.py:81), `EntryType(str, Enum)` at the
  schema layer over a plain String column (models.py:267, no DB enum, no
  CHECK) — adding `EntryType.PORTFOLIO_HEALTH_ANALYSIS =
  "portfolio_health_analysis"` needs **no backend migration**. The `/note`
  annotation endpoint (journal.py:119) works unchanged.
- **Row fit:** `title`, nullable `ticker`, `agents_involved` (JsonB list),
  `tags` (JsonB list), `payload` (JsonB dict) all exist. `title`: "Portfolio
  Health — {as_of}"; `ticker: null`; `agents_involved`: the CR137 roster when
  the Room narrates, else `[]`; `tags`: `["portfolio_health", "cr136"]`.
- **Payload:** the full stripped metric context (every block with uncertainty
  fields + `engine_version`), triggered rule ids with slot values, and the
  five rendered sections as markdown. Storing the context verbatim makes the
  entry self-explaining forever — no recomputation, no dependence on later
  engine versions.
- **▲ Idempotency needs app-level enforcement (spec-pack correction).** The
  table has **no** `portfolio_id`/`as_of` columns and no unique constraints
  (verified — `append` is an unconditional insert), so at-most-one Finding
  per `(portfolio_id, as_of)` cannot be a DB constraint without a migration.
  Decision: **application-level check-before-insert in the Finding service**
  (query newest `portfolio_health_analysis` entry for the user, compare
  payload `as_of` + `portfolio_id`), consistent with the store's existing
  patterns; a partial unique index stays open as a hardening follow-up if
  concurrent generation ever becomes possible (today it cannot — generation
  is user-triggered, per-user serial). Series keyed to `portfolio_id`, and a
  Finding **never spans a reset** — same rule as the value snapshots.
- **▲ Mobile requires real work (spec-pack correction).** The Flutter journal
  enum is hardcoded and coerces unknown wire types to `oneOnOne`
  (journal.dart:103-104), which would render an **empty payload block** for
  this entry type. Scope must include: the new enum value + wire mapping in
  `mobile/lib/models/journal.dart`, and a markdown-rendering branch in
  `journal_detail_screen.dart` (`_Block` currently renders bare `Text`;
  `flutter_markdown_plus` is already a dependency, used by the Room widgets —
  reuse it).
- Surfacing: the entry appears in the existing journal timeline; opening it
  renders the **stored** sections, never a live regeneration.

## Cohesion map

```text
holdings + market data ──► metrics engine (deterministic, this CR)
     │                         │  uncertainty contract on every block
     │                         ▼
     │                GET /v1/portfolio/health/{user_id}
     │                         │
     │            context builder (strip insufficient)
     │                         │
     │        ┌────────────────┼─────────────────┐
     │        ▼                ▼                 ▼
     │   Health card      CR137 Room        Finding renderer
     │   (§F1 headlines)  (narrate only,    (§F1–F5 templates
     │                    prompt contract)   + rule engine)
     │                                          │
     │                                          ▼
     │                               journal_entries row
     ▼
portfolio_value_snapshots (Tier 2, trading-day gated)
```

- **Versioning:** `engine_version` in every metric block, journal payload and
  Finding — estimator changes never make old artefacts ambiguous.
- **Degrade-loudly matrix:** mock market-data mode → engine refuses entirely;
  partial history → `partial` + disclosure everywhere; insufficient → null +
  strip + "not enough data yet"; benchmark misalignment → beta insufficient,
  never re-gridded; LLM unavailable or output rejected → deterministic
  template rendering (still a correct, complete report).
- **Sequencing unchanged:** CR136 engine first; CR137 Room consumes it. The
  Finding renderer works with or without the Room — templates stand alone;
  the Room adds debate, never numbers.

## Scope

**1. Data model** — `backend/app/db/models.py`: new `PortfolioValueSnapshotRow`
(`portfolio_value_snapshots`), mirroring the existing append-only snapshot
convention (`ClassificationUniverseSnapshotRow`, `ShariaUniverseSnapshotRow`):
`user_id`, `portfolio_id` (FK `sim_portfolios`), `as_of` (Date), `total_value`,
`cash`, `invested_value`, `drawdown_pct`, `source`, `captured_at`.
`UniqueConstraint(portfolio_id, as_of)` — idempotent, one row per portfolio per
day.

**2. Daily snapshot job** — new `backend/app/services/portfolio_snapshot.py`:
`run_portfolio_snapshot_tick()`, same idempotent-per-day shape as
`run_classification_refresh_tick()` (a tick that finds today's row already
written no-ops). Iterates `sim_portfolios`, calls the existing
`SimEngine.portfolio_marks_snapshot(user_id)` (already returns
total_value/drawdown_pct/source in one fetch — no new quote-fetching code),
upserts today's row. Wire into `backend/app/main.py` as
`_portfolio_snapshot_refresh()`, following the exact `to_thread` +
sleep-loop pattern already used by `_classification_universe_refresh`,
`_sharia_universe_refresh`, `_ticker_reference_refresh`.

**3. Metrics engine** — new `backend/app/services/portfolio_health.py`.
**Tier 1 (the primary path) does NOT read snapshot history at all** — it builds
one covariance matrix from each current holding's own return series and derives
volatility, beta, effective bets, and risk contribution from it. Tier 2 reads
snapshot history for the realised equity curve and max drawdown. Every metric
carries the uncertainty contract above; below its minimum-observation floor it
returns `sufficient: false` and no value, never a fabricated number (CR040
degrade-loudly).

**3a. Prerequisite infrastructure the metrics engine needs** (discovered in the
Rev 2 review; none of this exists today):

- **Longer daily history.** `market_data._PERIOD_MAP` (market_data.py:150-157)
  only returns a *daily* interval for `"1m"` (22 bars) and `"3m"` (65 bars);
  `"1y"` is weekly and `"5y"` is monthly. Max obtainable daily series today is
  **~64 returns**. Add a daily-interval long period (1y/2y). Highest-leverage
  single change in the CR — it moves SE(volatility) from 1.77pp to 0.63pp.
- **Persistent OHLC cache.** `CachingProvider._history_cache` has a **60-second
  TTL** (market_data.py:437) and there is no batch primitive and no OHLC table —
  an N-holding portfolio costs N sequential `Ticker.history()` round-trips per
  dashboard open. Needs a stored daily-bar table or a much longer history TTL.
- **Benchmark series** (`^GSPC`/`SPY`) — none is fetched anywhere today. Must be
  **date-aligned** to the holding series, not merely equal-length: `beta()`
  (portfolio_stats.py:58) checks length only, so two same-length series off
  different date grids silently produce a wrong beta.
- **Trading-day calendar.** None exists, and `Quote.market_state` is unusable as
  a gate — it is only populated by the *legacy fallback* provider, so the
  production `YfinanceProvider` path always takes the `"CLOSED"` default
  (market_data.py:69, 514-524). Derive trading days from **candle timestamps**
  (`Candle.t`) instead — yfinance only returns bars for real sessions, so this
  needs no new dependency.
- **Mock-data guard.** `settings.use_real_market_data` defaults **False**
  (config.py:141), in which case the provider is `MockWalkProvider` — a seeded
  random walk. The engine must **refuse to serve metrics** in that mode rather
  than computing immaculate statistics about a random number generator.
- **Risk-free rate** — still absent repo-wide. Not needed for Tier 1 (no metric
  has a mean-return term). Required only if a mean-term metric is ever revived.

**4. API** — `GET /v1/portfolio/health/{user_id}` in `backend/app/api/portfolio.py`,
same `_own` guard + DI-provider style as the existing `sector-allocation` route.

**5. Backfill script** — `backend/scripts/cr136_backfill_portfolio_snapshots.py`,
mirroring `cr129_backfill_journal.py`'s pattern exactly: dry-run by default,
`--apply` to write, deployed via `scp` + `docker cp` into `ami_api_alpha` (Mac
has no DB — melehost-only, per the Mac-is-pure-editor rule). For each
portfolio: walk `SimTradeRow` history chronologically to reconstruct daily
holdings, pull historical daily closes for every ticker touched, compute
`total_value` per **trading** day since the user's first trade, upsert
(idempotent on `(portfolio_id, as_of)`).

Demoted in Rev 2 from load-bearing to a **Tier-2 nicety** — Tier 1 no longer
depends on it, so it can slip without blocking the feature. Two hazards to
respect:

- **Reset boundary.** `POST /v1/sim/portfolio/{user_id}/reset` (sim.py:173-200)
  is a *destroy-and-recreate* — it deletes the trades and the portfolio row and
  recreates at $10k with a fresh `created_at` (sim_engine.py:394-403). Series
  must be keyed to `portfolio_id` and **must never span a reset**, or a wiped
  account gets spliced onto the old curve.
- **Split adjustment.** Reconstructing past value from today's adjusted closes
  against historical *share counts* double-counts any split. Use one basis
  consistently.

**6. Mobile UI** — extend `portfolio_screen.dart` (already the CR026/CR029/CR030
home per CR100) with a new "Portfolio Health" card using the same AMI hex
components. Tiles are the **Tier-1** metrics — Portfolio Volatility, Beta (with
R²), Effective Independent Bets, and the top risk contributors — each a number
plus one plain-language line (brand voice: numbers over adjectives). Realised
max drawdown appears as Tier-2 history with its window stated. Any metric with
`sufficient: false` renders an explicit "not enough data yet" state, never a
blank, a zero, or a number.

The **risk-contribution decomposition is the tile with the most teaching value**
and has no analogue anywhere in the app today: "62% of your portfolio's risk
comes from NVDA, which is 30% of your money" is a sentence a user learns from,
it is computed deterministically, and it is precisely the decomposition the
FMR risk-platform patent describes as the institutional headline output.

**7. Finding renderer + recommendation rule engine** — new
`backend/app/services/portfolio_finding.py`: builds the stripped metric
context, fires the rule engine (fixed templates, thresholds in one constant
block), renders §F1–§F5 deterministically, and — when the LLM path is enabled
— sends the prompt-contract skeleton and validates the structured output
(post-generation number/adjective check, deterministic fallback). LW closed
form (constant-correlation target, *Honey, I Shrunk the Sample Covariance
Matrix*) lands in `trading_math/` stdlib-only beside `portfolio_variance`.

**8. Journal integration** — new
`EntryType.PORTFOLIO_HEALTH_ANALYSIS` (schema-layer only, no backend
migration); Finding service persists via `JournalStore.append` with the
app-level `(portfolio_id, as_of)` check-before-insert; mobile:
`journal.dart` enum value + wire mapping, and a markdown-rendering branch in
`journal_detail_screen.dart` (reuse `flutter_markdown_plus`, already a
dependency).

**9. Content tie-in** — cross-reference CR054's M11/M12 BOK lessons (same
metrics, already scoped to be taught) — not a blocking dependency, just keeps
the live feature and the lesson content honest about teaching the same
numbers.

## Out of scope

- The Portfolio Room itself (CR137, below — committed, sequenced next, not
  designed yet)
- **Sharpe, Sortino, Treynor, Jensen's alpha, information ratio** — all carry a
  mean-return numerator; not estimable at any horizon our users will have (see
  the governing principle). Rev 2 removed Sharpe from the shipping set.
- VaR/CVaR, Fama-French/Barra factor exposure
- Composite single risk score
- Multi-portfolio (already gated behind the existing v1.0/Floor Manager decision)

---

## Rev 2 — quant review (2026-08-02)

Saiful challenged the Rev 1 math: *"The quant based of Aladdin as been proven?
Do we know what it does? … So look deeper into the quant maths. Are we doing it
right? Be critical."* The review found the Rev 1 foundation wrong. Record of
what was found, since the failure modes are reusable.

### The framing error: institutional precedent was cited, then contradicted

Rev 1 cited institutional holdings-based risk platforms as precedent and then
designed the structurally opposite system. **FMR LLC's (Fidelity's) patent**
(**US10157419B1**, "Multi-factor risk modeling platform" — *attribution
corrected in the r1 audit; the Rev 2 draft wrongly called this "BlackRock's
own patent." The claim-level substance below was verified line-by-line by the
auditor against the patent text; only the assignee was wrong*) documents the
institutional methodology at claim level:

| | Institutional platform (per the FMR patent) | CR136 Rev 1 |
|---|---|---|
| Primary input | **Current holdings** × security-level factor exposures ("multiply the current factor exposures by the simulated future market scenarios") | The portfolio's own historical value series |
| Method | Multi-factor model; "historical parametric, historical simulation and Monte Carlo" | Backward-looking ratios on one series |
| Headline output | "estimates tracking error volatility (TEV)"; contribution to TEV **by security, sector or factor** | Sharpe, max drawdown, beta, HHI |
| Needs a track record? | **No** — analyses what you hold today | **Yes** — 90+ days, plus a backfill script |

The patent is explicit that risk derives from current holdings × factor
exposures, *not* the portfolio's historical return track record. Holdings-based
analysis is also the documented industry choice for short track records
([CAIA](https://caia.org/blog/2024/10/28/holdings-based-vs-returns-based-analysis-deciphering-best-method-forecasting-fund)),
and it is why Morningstar runs both approaches. Aladdin's public materials
describe the same shape (holdings-based, factor exposures, scenario
simulation) but are not published at claim level — the design pivot rests on
the verified patent text, C2, and the day-one data constraint, not on any
one firm's name. Rev 1 picked the approach that cannot work for a new user.

### Seven defects in the Rev 1 math

1. **Sharpe was statistically meaningless at the planned horizon.** Using Lo
   (2002)'s standard error: at 90 observations a *measured* Sharpe of 1.0 has a
   95% CI of **[−2.28, +4.28]** — the sign is undetermined. A true Sharpe of 1.0
   needs **971 trading days (~3.9 years)** to be distinguishable from zero.
   Alpha users will never have that. Shipping it as a headline tile is
   presenting noise as signal — the exact thing degrade-loudly exists to stop.
2. **Naive HHI overstates diversification by up to 8.2×.** It is
   correlation-blind. Ten equal-weighted mega-cap tech names: HHI effective-N
   reads **10.0**; correlation-aware independent bets (`DR²`) at ρ=0.8 is
   **1.22**. Worse, going 10 → 30 holdings at ρ=0.8 moves real diversification
   1.22 → 1.24 while HHI reports 10 → 30. A false-comfort machine, about the
   one concept this app most needs to teach correctly. **Fix:** ship the
   diversification ratio; keep HHI only under the honest label "weight
   concentration."
3. **Risk-free rate defaults to 0.0** and no source exists anywhere in the repo
   (verified: no env var, no constant, no `^IRX`/`^TNX` fetch). At rf=4.5% an
   8%-return/15%-vol portfolio shows Sharpe 0.53 instead of 0.23 — a **2.29×
   overstatement** — and at 5% return, rf=0 turns a portfolio that
   *underperformed T-bills* into a positive Sharpe. Moot in Rev 2 (no
   mean-term metric ships), but it must not silently return if one is revived.
4. **Calendar-day snapshots would UNDERSTATE portfolio volatility by ~15%.**
   A daily tick with no trading-day gate writes ~113 flat weekend/holiday rows
   a year (~31% of the series); annualising that padded series by √252
   understates annualised volatility by a factor of `√(252/365) = 0.831`
   (40-year Monte Carlo: true vol 15.87%, naive padded 13.41% — **0.845×**).
   *Corrected 2026-08-02: the first Rev 2 draft stated this backwards as a
   1.204× Sharpe inflation. The real direction matters more, not less —
   volatility is a Rev 2 **shipping** metric, so the naive implementation
   would tell users their portfolio is ~15% safer than it is.* Fix: gate the
   snapshot to trading days (preferred), or annualise by the observed
   frequency. No calendar exists, and `Quote.market_state` cannot serve as one
   — it is only populated by the legacy fallback provider, so the production
   path always reads `"CLOSED"`.
5. **Two different quantities, both called "drawdown," in the same row.**
   `portfolio.py::drawdown_pct` measures *vs starting capital*;
   `returns.py::max_drawdown_pct` measures *peak-to-trough*. For $10k → $15k →
   $12k the first reads **0.0%** and the second **20%**. Rev 1 persisted the
   first and computed the second under one label — DEF066's exact
   position-vs-portfolio scope confusion, which has already bitten this project.
6. **`wᵀΣw` was dismissed as a "stretch goal."** It is the one function that
   implements the institutional holdings-based approach, and the covariance
   matrix is obtainable from each holding's own history. Rev 2 makes it the
   centrepiece.
   Caveat it needs: sample covariance is unstable at low T/N (20 holdings on 64
   observations is poorly conditioned), so **Ledoit–Wolf shrinkage** is required,
   not optional.
7. **`beta()` checks length, not dates.** Two same-length series drawn off
   different date grids silently produce a wrong beta. Any benchmark leg must be
   date-aligned before it reaches the function.

### One Rev 1 worry that the codebase cleared

Time-weighted return is **not** required. Every write to `current_cash` is
creation, buy, or sell (sim_engine.py:387/891/915); `starting_capital` is
written once at creation and never mutated. No top-ups, no admin credits, no
bonus cash — verified across `credit_service`, `league_service`,
`daily_challenge_service`, `merge_service`, and Alpaca (which is read-only and
disjoint). Within one portfolio lifetime, value moves only from marks and
trades, so naive period returns are arithmetically valid. The reset endpoint is
a *series discontinuity*, not a cash flow — handled in scope item 5.

Also noted: there is **no fee, commission, or slippage** deduction in the buy
path, so all returns are gross. Worth disclosing wherever performance is shown.

### What changed

- Primary engine flipped **returns-based → holdings-based**; works on day one,
  no backfill dependency.
- **Sharpe and every other mean-numerator ratio dropped** from the shipping set.
- **Diversification ratio / effective independent bets** replaces naive HHI as
  the diversification metric; HHI demoted and relabelled.
- **Risk-contribution decomposition added** — the institutional-platform
  headline output (per the FMR patent), and the highest-teaching-value tile in
  the feature.
- **Uncertainty contract added** to every metric, because the CR137 agents
  consume these numbers and cannot themselves detect noise.
- Backfill demoted from load-bearing to a Tier-2 nicety.
- Six prerequisite infrastructure gaps documented (scope item 3a) — the
  binding one being that the codebase can currently fetch only **~64 daily
  bars**.

## Acceptance

Backend unit tests (`pytest backend/tests/unit/ -q`, sqlite tempfile):

- **Known-answer tests against closed-form cases**, not just smoke tests. For N
  equal-weighted assets with uniform pairwise correlation ρ, independent bets
  must equal `1/((1/N) + (1−1/N)ρ)` — e.g. N=10, ρ=0.8 → **1.22**, N=10, ρ=0.2 →
  **3.57**. This is the test that would have caught the naive-HHI defect.
- **Risk contributions sum to 100%** (±1e-6) for any weight vector and any PSD Σ.
- **Σ estimation guards**: a poorly-conditioned or non-PSD matrix must degrade to
  `sufficient: false`, never emit a number. Shrinkage must be exercised at low
  T/N (e.g. 20 holdings, 64 observations).
- **Date alignment**: a benchmark series that is equal-length but off a different
  date grid must be rejected, not silently used (defect 7).
- **Mock-mode refusal**: with `use_real_market_data=false` the engine returns no
  metrics, and the test asserts that (not a number computed off the random walk).
- **Uncertainty contract**: every serialised metric carries `n_observations`,
  `window_days`, `sufficient`; nothing with `sufficient: false` carries a value.
- Snapshot-tick idempotency (two ticks same day → one row); a tick must not write
  on a non-trading day; a series must not span a portfolio reset.
- `/v1/portfolio/health/{user_id}` auth (`_own` 403).
- **Sufficiency thresholds**: every floor in the SUFFICIENCY block exercised at
  boundary±1 (125/126 obs; T/N 4.99/5.0; dropped weight 19.9%/20.1%); LW
  fixture tests against precomputed known answers (generated offline vs an
  independent numpy implementation, stored as literals — no test-time numpy).
- **Rule engine fire/no-fire at every boundary** (R1 39.9/40.1% risk share; R2
  DR² 1.99/2.01 × holdings 7/8; R3 β 1.29/1.31 × R² 0.19/0.21; R4 cash
  39.9/40.1%; R5 partial true/false). Rendered slots match the triggering
  values exactly.
- **Strip test**: a context with any `sufficient: false` block produces a
  prompt (and a deterministic rendering) in which that metric's name appears
  nowhere.
- **Post-generation validation**: a model output containing a digit sequence
  absent from the payload, or a lexicon adjective, is rejected and the
  deterministic fallback is served — asserted on a fabricated bad output.
- **Journal idempotency**: two generate calls same `(portfolio_id, as_of)` →
  one `portfolio_health_analysis` entry; a post-reset portfolio does not
  attach findings to the old portfolio's series.

End-to-end:

- Cross-check portfolio volatility against an independent implementation
  (e.g. a one-off `numpy`/`pandas` calculation on the same inputs) before
  shipping — the number must match to 2 dp.
- Backfill: dry-run against melehost's real data first, spot-check one known
  user's reconstructed series against their actual trade log, then `--apply`.
- `/promote-to-alpha`, confirm the new endpoint live, confirm the daily tick
  logs an idempotent no-op on its second same-day run (`ami_api_alpha` logs).
- Mobile: release-build install on the iPhone 13/17 test devices, confirm each
  tile renders both populated and in the explicit "not enough data yet" state;
  confirm a stored Finding renders its five sections as markdown in the
  journal detail view (not an empty payload block).
- **The hostile-reader pass**: before the Finding ships, one full generated
  report is reviewed against the hostile-reader standard checklist (every
  number has method/window/n; limitations disclosed first; no judgement
  adjectives; every claim traceable) — Saiful's acceptance test, wearing the
  rude-PM hat.

## Risk class

New table + new background job + new endpoint + new UI. No money movement, no
safety-floor change.

**Raised in Rev 2 to warrant independent audit.** Not for the code — for the
**math**. The Rev 1 review found seven defects, several of which (Sharpe's
confidence interval, HHI's correlation blindness) produce numbers that look
completely plausible while being wrong or meaningless. That is the DEF059 class:
a silent, confident-looking failure. It is also the class least likely to be
caught by ordinary code review, because the code can be flawless while the
statistic is invalid — and once CR137's agents narrate these numbers in AMI's
voice, a wrong statistic becomes a confident wrong statement to a user who is
here to learn. Recommend a track-U audit scoped specifically to the estimator
choices and the sufficiency thresholds.

---

## Phase B — Portfolio Room (CR137, reserved, designed in a follow-up session)

Not built in this CR — this CR's metrics engine is Phase B's prerequisite
ground truth. Reserved here so the commitment is visible, not lost as a vague
"someday": a **portfolio-scoped Convene the Room**, same multi-agent
architecture, same UI family (Verdict Board / collapsed transcript per CR106),
but convening on the whole portfolio instead of one ticker. All math the
agents cite comes from this CR's API — **agents narrate and debate, they never
compute** (the CR046/CR040 line holds inside the Room exactly like it holds
for lesson content).

Rough agent-role mapping to work out in that session (not decided here):

- **Aggressive / Conservative / Neutral Debators** — the most natural fit
  as-is: real risk-management teams already reason about risk at the
  portfolio level, not per-ticker (confirmed in the upstream TradingAgents
  framework's own Risk Management Team scoping). Likely need the least rework.
- **Portfolio Manager** — already the most portfolio-aware of the 12 (reads
  whole-portfolio state today); natural chair for the Room's final verdict/
  narrative here too.
- **Trader** — per-ticker today ("propose a trade"); portfolio version
  plausibly becomes "propose a rebalancing action" (trim an overweight
  sector, add a diversifier) — a standard whole-portfolio output in the
  research, not a stretch.
- **Research Manager** — could adjudicate/synthesize the Risk Debators'
  portfolio arguments instead of Bull vs. Bear.
- **Fundamentals / Market / News / Social Media Analysts, Bull/Bear
  Researchers** — genuinely ticker-scoped; no obvious 1:1 portfolio analog.
  Open question for the CR137 session: leave them out of the Portfolio Room
  entirely, or find a portfolio-wide framing (e.g., Fundamentals →
  weighted-average valuation across holdings)? Don't force it — a smaller,
  coherent agent roster beats stretching all 12 into a shape they don't fit.

**Precedent (checked 2026-08-01):** BlackRock's
[Aladdin](https://www.blackrock.com/aladdin/products/aladdin-risk) proves
unemotional, systematic portfolio risk evaluation at trillion-dollar
institutional scale — but it's a quant/rules risk engine, not LLM agents.
[FinRobot](https://github.com/ai4finance-foundation/finrobot) (open-source,
AI4Finance Foundation — sibling lineage to Tauric's TradingAgents) already
runs "Risk Assessment Agents and Portfolio Construction Agents [that] debate
and refine collective conclusions," explicitly framed as simulating "the
structure of elite investment committees" — closest existing precedent to
CR137's shape. 2026 academic work moving the same direction:
[AlphaAgents](https://www.emergentmind.com/papers/2508.11152) (multi-agent
LLM over equity *portfolios*), ["Expert Investment
Teams"](https://www.emergentmind.com/papers/2602.23330). None of these
combine institutional-grade deterministic math + a real agent committee + a
consumer education product with the user as CEO — that combination is white
space. The "unflappable" framing has its own peer-reviewed backing
independent of agenticness: robo-advisor rebalancing measurably reduces the
disposition effect and trend-chasing vs. human self-directed decisions
([Frontiers in Behavioral
Economics](https://www.frontiersin.org/journals/behavioral-economics/articles/10.3389/frbhe.2024.1489159/full)).

**Governance note:** CR137 is reserved by number only — no row file, no doc,
until that follow-up design session actually scopes it.
