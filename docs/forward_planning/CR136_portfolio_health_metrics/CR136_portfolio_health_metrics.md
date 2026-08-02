# CR136 — Portfolio Health: whole-portfolio, risk-based evaluation

**Status:** proposed · **Filed:** 2026-08-02 (AT:R65)
**Revised:** 2026-08-02 (AT:R65) — **Rev 2, quant review. The Rev 1 math was
wrong in its foundation and has been replaced.** See "Rev 2 — quant review"
below for what was wrong, the measured evidence, and what replaced it. Do not
build from Rev 1; it survives only inside the review section as the record of
what was rejected.
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

This is also exactly where BlackRock's Aladdin draws its line — its headline
output is **TEV (tracking error volatility) and risk decomposition**, second-
moment quantities, not performance ratios (US10157419B1; see the review
section). The statistics, the professional precedent, and our actual data
constraint all point the same way.

## The framework

Two tiers. Tier 1 is the product; Tier 2 is descriptive history that
accumulates behind it.

### Tier 1 — forward-looking, holdings-based (works on day one, no portfolio history)

Computed from **current holdings × each holding's own return history** — the
Aladdin/Morningstar holdings-based approach, which needs the *securities* to
have history, not the *portfolio*. This is what makes the feature work for a
user who opened their account yesterday.

| Metric | Definition | Why it's defensible | Code |
|---|---|---|---|
| **Portfolio volatility** (annualised) | `√(wᵀΣw)`, Σ estimated with Ledoit–Wolf shrinkage | Markowitz; shrinkage is the standard fix for short-sample covariance instability ([Ledoit–Wolf 2004](https://alcapitaladvisory.com/research/frameworks/ledoit-wolf.html)) | `portfolio_stats.py::portfolio_variance` — **now the centrepiece**, not a stretch goal |
| **Beta vs. benchmark** + **R²** | Regression slope of portfolio returns on benchmark returns | CAPM. R² ships alongside because a beta with low R² is not a meaningful summary | `portfolio_stats.py::beta` (needs a **date-aligned** benchmark series — see defect 7) |
| **Effective independent bets** | `DR²` where `DR = (Σwᵢσᵢ)/σₚ` | Choueifaty & Coignard diversification ratio; Choueifaty–Froidure–Reynier (2012) show `DR²` = number of independent bets ([Portfolio Optimizer](https://portfoliooptimizer.io/blog/the-diversification-ratio-measuring-portfolio-diversification/)) | New pure function over the same Σ |
| **Risk contribution** by holding and by sector | `wᵢ·(Σw)ᵢ / σₚ²`, sums to 100% | The Aladdin-shaped output: "contribution to TEV by security, sector or factor" | New pure function over the same Σ; sector map reuses CR026 |
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

### The uncertainty contract (required, because an LLM consumes this)

Saiful's architecture is quants compute, agents interpret. That makes the
quant layer's output an **LLM input**, and an agent will confidently narrate
whatever it is handed — it cannot know a number is noise. Feeding bare point
estimates to the Room re-creates DEF059's failure class (confident output over
a silently-degraded input) as confident fake risk assessment.

So every metric in the API response carries, structurally:

```json
{ "value": 0.0, "standard_error": null, "n_observations": 0,
  "window_days": 0, "sufficient": false, "basis": "holdings" }
```

and the CR137 Room contract must **forbid narrating any metric with
`sufficient: false`**. Enforced deterministically at the serialisation
boundary, not by prompt instruction (CR038 — "prompt instructions are not
controls").

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
it is computed deterministically, and it is precisely what Aladdin outputs.

**7. Content tie-in** — cross-reference CR054's M11/M12 BOK lessons (same
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

### The framing error: Aladdin was cited, then contradicted

Rev 1 cited Aladdin as precedent and then designed the structurally opposite
system. BlackRock's own patent (**US10157419B1**, "Multi-factor risk modeling
platform") settles what Aladdin does:

| | Aladdin (per the patent) | CR136 Rev 1 |
|---|---|---|
| Primary input | **Current holdings** × security-level factor exposures | The portfolio's own historical value series |
| Method | Multi-factor model + Monte Carlo (~250k scenarios) | Backward-looking ratios on one series |
| Headline output | Factor exposures; contribution to **TEV** by security/sector/factor | Sharpe, max drawdown, beta, HHI |
| Needs a track record? | **No** — analyses what you hold today | **Yes** — 90+ days, plus a backfill script |

The patent is explicit that risk derives from current holdings × factor
exposures, *not* the portfolio's historical return track record. Holdings-based
analysis is also the documented industry choice for short track records
([CAIA](https://caia.org/blog/2024/10/28/holdings-based-vs-returns-based-analysis-deciphering-best-method-forecasting-fund)),
and it is why Morningstar runs both approaches. Rev 1 picked the one that
cannot work for a new user.

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
4. **Calendar-day snapshots would inflate Sharpe by 1.204×.** A daily tick with
   no trading-day gate writes ~113 flat weekend/holiday rows a year (~31% of
   the series); annualising that by √252 is inconsistent. No calendar exists,
   and `Quote.market_state` cannot serve as one — it is only populated by the
   legacy fallback provider, so the production path always reads `"CLOSED"`.
5. **Two different quantities, both called "drawdown," in the same row.**
   `portfolio.py::drawdown_pct` measures *vs starting capital*;
   `returns.py::max_drawdown_pct` measures *peak-to-trough*. For $10k → $15k →
   $12k the first reads **0.0%** and the second **20%**. Rev 1 persisted the
   first and computed the second under one label — DEF066's exact
   position-vs-portfolio scope confusion, which has already bitten this project.
6. **`wᵀΣw` was dismissed as a "stretch goal."** It is the one function that
   implements the Aladdin-shaped approach, and the covariance matrix is
   obtainable from each holding's own history. Rev 2 makes it the centrepiece.
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
- **Risk-contribution decomposition added** — the Aladdin-shaped output, and
  the highest-teaching-value tile in the feature.
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

End-to-end:

- Cross-check portfolio volatility against an independent implementation
  (e.g. a one-off `numpy`/`pandas` calculation on the same inputs) before
  shipping — the number must match to 2 dp.
- Backfill: dry-run against melehost's real data first, spot-check one known
  user's reconstructed series against their actual trade log, then `--apply`.
- `/promote-to-alpha`, confirm the new endpoint live, confirm the daily tick
  logs an idempotent no-op on its second same-day run (`ami_api_alpha` logs).
- Mobile: release-build install on the iPhone 13/17 test devices, confirm each
  tile renders both populated and in the explicit "not enough data yet" state.

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
