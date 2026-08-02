# CR136 — Portfolio Health: whole-portfolio, risk-based evaluation

**Status:** proposed · **Filed:** 2026-08-02 (AT:R65)
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

## The framework

Layered, each layer independently defensible — no single opaque score for v1
(rationale below):

| Layer | Metric(s) | Methodology | Code status |
|---|---|---|---|
| **Concentration** | HHI (`Σ weight²`) → effective-N holdings, per-position AND per-sector | Standard finance/econ concentration measure ([diversification.com](https://diversification.com/term/effective-number-of-stocks)) | New pure function; sector weights reuse `sector_allocation.allocate_by_sector` (CR026) |
| **Volatility / market exposure** | Portfolio σ, CAPM beta vs. S&P 500 | Markowitz Modern Portfolio Theory; CAPM | Built, dormant — `portfolio_stats.py::portfolio_variance`, `::beta` |
| **Risk-adjusted return** | Sharpe ratio (primary) | Excess return / total volatility — "most universally applicable" across the research ([ICFS](https://icfs.com/specialists-desk/risk-adjusted-returns)) | Built, dormant — `returns.py::sharpe_ratio` |
| **Tail / drawdown risk** | Max drawdown | Peak-to-trough over the value series — "the most intuitive, investor-relevant risk metric" ([PyQuantLab](https://pyquantlab.medium.com/essential-quantitative-measures-in-financial-risk-management-maximum-drawdown-var-and-cvar-b33d60753ff3)) | Built, dormant — `returns.py::max_drawdown_pct` |

**Backlog, not this CR** (need more history or a dependency sign-off to be
statistically honest): Sortino ratio, Treynor ratio (needs a name-level beta
series), VaR/CVaR (needs a long-enough return history to mean anything),
Fama-French/Barra-style factor exposure. `returns.py`'s own docstring already
flags Sortino/Calmar as gated on a new dependency (`empyrical-reloaded`,
Saiful's sign-off) — leave that gate as-is.

**Presentation — individual labeled metrics, NOT a composite score, for v1.**
Morningstar's 0–100 Portfolio Risk Score is the closest productized precedent,
but its exact factor weighting is proprietary — AMI can't cite or defend a
weighting scheme it invented. Each of the four metrics above traces to a
named, textbook methodology on its own. Revisit a composite score once CR054's
BOK lessons (`M11_portfolio_statistics.md`, `M12_return_metrics.md` — already
scoped to teach these exact metrics) have shipped and users can read the
components.

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

**3. Metrics engine** — new `backend/app/services/portfolio_health.py`: reads a
user's snapshot history, computes the four layers above by calling into
`portfolio_stats.py`/`returns.py` (never re-deriving the math). Every metric
returns `None` + an "insufficient history" flag below its minimum-observation
floor — the same discipline `variance`/`sharpe_ratio` already enforce (no
fabricated numbers, matches CR040 degrade-loudly). **Scope simplification:**
true Markowitz portfolio variance needs a covariance matrix across per-holding
return series; v1 computes portfolio-level beta/volatility directly from the
whole-portfolio value series vs. an S&P 500 proxy series (one series vs. one
series, `beta()` as-is) rather than building the full per-holding `wᵀΣw`
matrix — that's a stretch goal once per-holding history exists.

**4. API** — `GET /v1/portfolio/health/{user_id}` in `backend/app/api/portfolio.py`,
same `_own` guard + DI-provider style as the existing `sector-allocation` route.

**5. Backfill script** — `backend/scripts/cr136_backfill_portfolio_snapshots.py`,
mirroring `cr129_backfill_journal.py`'s pattern exactly: dry-run by default,
`--apply` to write, deployed via `scp` + `docker cp` into `ami_api_alpha` (Mac
has no DB — melehost-only, per the Mac-is-pure-editor rule). For each
portfolio: walk `SimTradeRow` history chronologically to reconstruct daily
holdings, pull historical daily closes via `yfinance` for every ticker
touched, compute `total_value`/`drawdown_pct` per calendar day since the
user's first trade, upsert (idempotent — skips existing `(portfolio_id,
as_of)` rows).

**6. Mobile UI** — extend `portfolio_screen.dart` (already the CR026/CR029/CR030
home per CR100) with a new "Portfolio Health" card using the same AMI hex
components: four labeled tiles (Sharpe, Max Drawdown, Effective-N/concentration,
Beta), each a number + one plain-language line (brand voice: numbers over
adjectives), each degrading to an explicit "insufficient history" state rather
than a blank or a zero.

**7. Content tie-in** — cross-reference CR054's M11/M12 BOK lessons (same
metrics, already scoped to be taught) — not a blocking dependency, just keeps
the live feature and the lesson content honest about teaching the same
numbers.

## Out of scope

- The Portfolio Room itself (CR137, below — committed, sequenced next, not
  designed yet)
- Sortino, Treynor, VaR/CVaR, Fama-French/Barra factor exposure
- Composite single risk score
- Multi-portfolio (already gated behind the existing v1.0/Floor Manager decision)

## Acceptance

- Backend unit tests (`pytest backend/tests/unit/ -q`, sqlite tempfile): HHI/
  effective-N pure functions, snapshot-tick idempotency (two ticks same day →
  one row), `/v1/portfolio/health/{user_id}` auth (`_own` 403) and
  "insufficient history" degradation paths.
- Backfill: dry-run against melehost's real data first, spot-check one known
  user's reconstructed series against their actual trade log, then `--apply`.
- `/promote-to-alpha`, confirm the new endpoint live, confirm the daily tick
  logs an idempotent no-op on its second same-day run (`ami_api_alpha` logs).
- Mobile: release-build install on the iPhone 13/17 test devices, confirm the
  Portfolio Health card renders correctly both populated and in the
  "insufficient history" state.

## Risk class

New table + new background job + new endpoint + new UI. No money movement, no
safety-floor change. Standard build risk, not a track-U item.

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
